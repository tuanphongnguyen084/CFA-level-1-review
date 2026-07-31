"""
Per-user progress, persisted in the BROWSER (localStorage) — no login, no
backend, no shared server file.

Why not write to disk like the old app? On Streamlit Community Cloud the
filesystem is ephemeral (reset on every redeploy/sleep) and shared across all
visitors, so a server-side ``progress.json`` is both unreliable and leaks one
user's progress to everyone. localStorage keeps each browser's progress local
to that browser.

Design notes
------------
* ``init()`` runs once at the top of every script run. It (re)creates the
  ``LocalStorage`` component and hydrates ``st.session_state.progress`` from the
  browser. The component needs to render on each run, so we do NOT cache the
  instance across reruns.
* The working copy of progress lives in ``st.session_state.progress``. All
  transient quiz state lives elsewhere in session_state, so a localStorage
  rerun never disturbs an in-progress question.
* Everything is wrapped in try/except: if the component is unavailable the app
  silently falls back to session-only progress (lost on refresh), and the
  Export/Import buttons in the sidebar still give reliable persistence.

Progress shape (keyed by ``"<subject_id>/<exam_id>"``)::

    {
      "finished": bool,
      "last_mode": "full" | "wrong",
      "wrong_ids": [question_id, ...],
      "in_progress": {                              # optional
        "idx": int, "n": int, "mode": str,
        "order": [question_id, ...],                # shuffled snapshot
        "answers": {question_id: chosen_letter},
      }
    }
"""
import json
import os
import time

import streamlit as st

_KEY = "cfa_progress_v1"

# Let the browser actually perform a queued write before the caller reruns.
_WRITE_SETTLE_S = 0.8

# Escape hatch: set CFA_DISABLE_LOCALSTORAGE=1 to run session-only (no browser
# component). Used by AppTest/headless checks where there is no frontend to
# answer the component's round-trip.
_DISABLED = bool(os.environ.get("CFA_DISABLE_LOCALSTORAGE"))


def _pkey(subject_id, exam_id):
    return f"{subject_id}/{exam_id}"


def _component():
    """Return streamlit_local_storage's raw component function, or None.

    We deliberately bypass the library's ``LocalStorage`` class. Its
    constructor ends with ``while st.session_state[key] is None:
    time.sleep(0.1)`` — a blocking spin waiting for the browser to answer.
    Calling the component function directly is non-blocking: it simply
    returns ``default`` until the browser delivers a payload on a later run.

    That distinction is why the deployed app went blank: Streamlit Community
    Cloud upgraded itself to 1.60 (requirements only pinned >=1.40), the spin
    never resolved there, so the script never finished its first run and no
    UI was ever emitted — a hang, which is why the logs showed a healthy boot
    and no traceback. Under 1.60 locally the same spin cost ~12s per load.
    """
    if _DISABLED:
        return None
    try:
        from streamlit_local_storage import _st_local_storage
        return _st_local_storage
    except Exception:  # noqa: BLE001 — component optional
        return None


def _read_all(comp):
    """Whole localStorage payload as a dict ({} while still mounting)."""
    try:
        got = comp(method="getAll", key="cfa_ls_read", default={})
    except Exception:  # noqa: BLE001
        return {}
    return got if isinstance(got, dict) else {}


def init():
    """Mount the storage component and hydrate progress (call once/run)."""
    comp = _component()
    st.session_state["_ls"] = comp

    if "progress" not in st.session_state:
        st.session_state.progress = {}

    # Once we own the state (hydrated from the browser or the user has written),
    # never re-read — that would clobber unsaved in-session changes.
    if st.session_state.get("_prog_hydrated"):
        return

    if comp is None:
        st.session_state["_prog_hydrated"] = True   # session-only mode
        return

    raw = _read_all(comp).get(_KEY)

    if raw not in (None, ""):
        try:
            st.session_state.progress = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:  # noqa: BLE001
            st.session_state.progress = {}
        st.session_state["_prog_hydrated"] = True
    # else: component still mounting (or nothing saved) — a later run reads it.


def save():
    """Write the working copy back to the browser."""
    st.session_state["_prog_hydrated"] = True   # we now own the state
    comp = st.session_state.get("_ls")
    if comp is None:
        return
    try:
        comp(method="setItem", itemKey=_KEY,
             itemValue=json.dumps(st.session_state.progress, ensure_ascii=False),
             key="cfa_prog_writer")
        # The browser performs the write when it receives this element; every
        # caller reruns immediately after saving, which would tear the script
        # down first, so give the round-trip a moment to land.
        time.sleep(_WRITE_SETTLE_S)
    except Exception:  # noqa: BLE001
        pass


def reset():
    """Clear all progress (session + browser)."""
    st.session_state.progress = {}
    st.session_state["_prog_hydrated"] = True
    comp = st.session_state.get("_ls")
    if comp is not None:
        try:
            comp(method="deleteItem", itemKey=_KEY, key="cfa_prog_del")
            time.sleep(_WRITE_SETTLE_S)
        except Exception:  # noqa: BLE001
            pass


def load_from_dict(data):
    """Replace progress with an imported dict and persist it."""
    if isinstance(data, dict):
        st.session_state.progress = data
        save()


# --------------------------------------------------------------------------- #
# Read helpers                                                                 #
# --------------------------------------------------------------------------- #
def entry(subject_id, exam_id):
    return st.session_state.get("progress", {}).get(_pkey(subject_id, exam_id))


def get_or_create(subject_id, exam_id):
    return st.session_state.progress.setdefault(_pkey(subject_id, exam_id), {})


def status(subject_id, exam_id, total):
    """Return (label, kind) describing an exam's progress for badges."""
    e = entry(subject_id, exam_id)
    if not e:
        return "Not started", "off"
    if e.get("in_progress"):
        ip = e["in_progress"]
        return f"In progress — question {ip['idx'] + 1}/{ip['n']}", "running"
    if not e.get("finished"):
        return "Not started", "off"
    wrong = len(e.get("wrong_ids", []))
    if wrong == 0:
        return f"Completed — all correct ({total}/{total})", "done"
    mode_txt = "full" if e.get("last_mode", "full") == "full" else "wrong"
    return f"Done ({mode_txt}) — {wrong} wrong left", "todo"


def is_finished(subject_id, exam_id):
    e = entry(subject_id, exam_id)
    return bool(e and e.get("finished"))
