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

# Seconds to let the browser actually perform a queued localStorage write
# before the caller's st.rerun() tears the script down (see save()).
_WRITE_SETTLE_S = 0.8

# Reruns allowed while waiting for the browser to hand back saved progress.
_MAX_HYDRATE_TRIES = 4

# Escape hatch: set CFA_DISABLE_LOCALSTORAGE=1 to run session-only (no browser
# component). Used by AppTest/headless checks where there is no frontend to
# answer the component's round-trip.
_DISABLED = bool(os.environ.get("CFA_DISABLE_LOCALSTORAGE"))


def _pkey(subject_id, exam_id):
    return f"{subject_id}/{exam_id}"


def init():
    """Build the localStorage component and hydrate progress (call once/run)."""
    ls = None
    if not _DISABLED:
        try:
            from streamlit_local_storage import LocalStorage
            ls = LocalStorage()
        except Exception:  # noqa: BLE001 — component optional
            ls = None
    st.session_state["_ls"] = ls

    if "progress" not in st.session_state:
        st.session_state.progress = {}

    # Once we own the state (hydrated from the browser or the user has written),
    # never re-read — that would clobber unsaved in-session changes.
    if st.session_state.get("_prog_hydrated"):
        return

    if ls is None:
        st.session_state["_prog_hydrated"] = True   # session-only mode
        return

    try:
        raw = ls.getItem(_KEY)
    except Exception:  # noqa: BLE001
        raw = None

    if raw not in (None, ""):
        try:
            st.session_state.progress = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:  # noqa: BLE001
            st.session_state.progress = {}
        st.session_state["_prog_hydrated"] = True
        return

    # Component still mounting: it returns its default on the first run of a
    # session and only delivers the browser payload on a later one. "Retry on
    # the next run" only works if a next run actually happens, and on a fresh
    # page load nothing triggers one — so saved progress stayed invisible
    # until the user happened to click something. Drive the retries here,
    # bounded so a genuinely empty store still settles into session-only mode.
    tries = st.session_state.get("_prog_tries", 0)
    if tries < _MAX_HYDRATE_TRIES:
        st.session_state["_prog_tries"] = tries + 1
        time.sleep(0.3)
        st.rerun()
    st.session_state["_prog_hydrated"] = True


def save():
    """Write the working copy back to the browser.

    ``setItem`` only queues a component render; the browser executes the
    actual localStorage write when it receives that delta. Every caller here
    reruns immediately afterwards (exit_to_subject, finish, ...), and a rerun
    tears the script down before the delta is delivered — so without the
    short pause below nothing was ever persisted and all progress silently
    vanished on refresh. Verified in a real browser: no pause -> the
    ``cfa_progress_v1`` key never appears; with it -> the key is written.
    """
    st.session_state["_prog_hydrated"] = True   # we now own the state
    ls = st.session_state.get("_ls")
    if ls is None:
        return
    try:
        ls.setItem(_KEY, json.dumps(st.session_state.progress, ensure_ascii=False),
                   key="cfa_prog_writer")
        time.sleep(_WRITE_SETTLE_S)
    except Exception:  # noqa: BLE001
        pass


def reset():
    """Clear all progress (session + browser)."""
    st.session_state.progress = {}
    st.session_state["_prog_hydrated"] = True
    ls = st.session_state.get("_ls")
    if ls is not None:
        try:
            ls.deleteItem(_KEY, key="cfa_prog_del")
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
