"""Mixed timed drill: 20 questions pulled from every subject at once.

Why this exists. Working an exam at a time means every question arrives with
its topic already known, which is the one hint the real exam never gives. A
drill shuffles the subjects together and puts a clock on it, so it trains the
two things subject-by-subject practice cannot: recognising what a question is
about, and holding 90 seconds per question.

Two rules shape how questions are picked.

*Weighted by the exam, not by the bank.* Sampling the pool uniformly would
hand over a quarter of every drill to Equity, which holds 476 of the 1,873
questions but is worth 12.5% of the exam, while FSA at the same weight holds
129. The drill apportions its 20 slots by exam weight instead, so it reads
like the real paper rather than like this collection.

*Nothing repeats until everything has been served.* Each drill records the
questions it used; later drills draw only from what is left. When fewer than
a full drill remains, the last one is short, and the cycle then resets - so
the bank is covered once before any question comes round again.

The drill runs through the ordinary timed-exam machinery in core/exam.py. It
is handed over as a synthetic Exam injected into the library (see
``as_exam``), which is why nothing here duplicates the timer, the question
grid or the submit flow.
"""
import random
from collections import Counter

import streamlit as st

from core import content

# Share of the Level 1 paper, in percent, per subject folder. Midpoints of the
# published ranges; they total a little over 100, which does not matter since
# only their ratios are used.
EXAM_WEIGHT = {
    "ethics": 17.5,
    "fsa": 12.5,
    "equity": 12.5,
    "fixed-income": 12.5,
    "portfolio": 10.0,
    "alternatives": 8.5,
    "corporate": 7.5,
    "economics": 7.5,
    "quant": 7.5,
    "derivatives": 6.5,
}

DRILL_SUBJECT = "drill"
DRILL_EXAM = "current"
DEFAULT_N = 20
MINUTES_PER_QUESTION = 1.5   # 180 questions over 270 minutes, as on the day

_STATE_KEY = "_drill"


# --------------------------------------------------------------------------- #
# Seen-set bookkeeping (persisted with the rest of progress)                   #
# --------------------------------------------------------------------------- #
def _state():
    prog = st.session_state.setdefault("progress", {})
    state = prog.setdefault(_STATE_KEY, {})
    state.setdefault("seen", [])
    state.setdefault("cycle", 1)
    state.setdefault("history", [])
    return state


def key_of(subject_id, exam_id, qid):
    """Stable identity for one question across the whole bank.

    Question ids are only unique inside their own exam - half the subjects
    have a "Q12" - so the seen-set and the drill's own order both need the
    full path.
    """
    return f"{subject_id}/{exam_id}/{qid}"


def pool(library):
    """Every question eligible for drills, as (key, question, subject_id).

    Mock exams are left out: they are whole papers kept for the final
    fortnight, and spending them 20 questions at a time would waste them.
    """
    out = []
    for s in library.subjects:
        if s.subject_id not in EXAM_WEIGHT:
            continue
        for e in s.exams:
            for q in e.questions:
                out.append((key_of(s.subject_id, e.exam_id, q["id"]), q,
                            s.subject_id))
    return out


def cycle_progress(library):
    """(seen, total, cycle number) for the drill's coverage of the bank."""
    total = len(pool(library))
    state = _state()
    return min(len(state["seen"]), total), total, state["cycle"]


def history():
    return list(_state()["history"])


# --------------------------------------------------------------------------- #
# Picking the questions                                                        #
# --------------------------------------------------------------------------- #
def apportion(n, available):
    """Split n slots across subjects by exam weight (largest remainder).

    ``available`` maps subject_id to how many unseen questions it still has;
    a subject can never be asked for more than it holds, and whatever cannot
    be placed is handed to the subjects that still have room.
    """
    subs = [s for s in available if available[s] > 0]
    if not subs:
        return {}
    total_w = sum(EXAM_WEIGHT[s] for s in subs)
    exact = {s: n * EXAM_WEIGHT[s] / total_w for s in subs}
    take = {s: min(int(exact[s]), available[s]) for s in subs}

    # Largest remainder, then plain round-robin for anything still unplaced
    # because a subject hit its ceiling.
    short = n - sum(take.values())
    by_rem = sorted(subs, key=lambda s: exact[s] - int(exact[s]), reverse=True)
    for s in by_rem:
        if short <= 0:
            break
        if take[s] < available[s]:
            take[s] += 1
            short -= 1
    while short > 0:
        room = [s for s in subs if take[s] < available[s]]
        if not room:
            break
        for s in room:
            if short <= 0:
                break
            take[s] += 1
            short -= 1
    return {s: c for s, c in take.items() if c}


def build(library, n=DEFAULT_N, rng=None):
    """Choose this drill's questions. Returns (questions, reset_happened).

    Resets the cycle when the unseen pool has run dry, so a drill is always
    possible; the caller is told, because it is worth saying out loud.
    """
    rng = rng or random
    state = _state()
    seen = set(state["seen"])
    everything = pool(library)

    unseen = [p for p in everything if p[0] not in seen]
    reset = False
    if not unseen:
        # Whole bank covered - start the next cycle rather than refusing.
        state["seen"] = []
        state["cycle"] += 1
        seen, unseen, reset = set(), list(everything), True

    by_subject = {}
    for key, q, sid in unseen:
        by_subject.setdefault(sid, []).append((key, q, sid))

    take = apportion(min(n, len(unseen)),
                     {s: len(v) for s, v in by_subject.items()})
    picked = []
    for sid, count in take.items():
        picked.extend(rng.sample(by_subject[sid], count))
    rng.shuffle(picked)
    return picked, reset


def as_exam(picked, exam_id=None, seq=None):
    """Wrap the picked questions as an Exam the timed machinery can run.

    Each question is copied with its full key as the id: core/exam.py indexes
    answers by question id, and the raw ids collide across source exams.

    Each drill gets its own exam_id so that finishing one does not erase the
    last. That is what makes a drill reviewable afterwards exactly like any
    other exam, wrong answers and all.
    """
    questions = []
    for key, q, _sid in picked:
        c = dict(q)
        c["id"] = key
        questions.append(c)
    minutes = max(1, round(len(questions) * MINUTES_PER_QUESTION))
    return content.Exam(
        subject_id=DRILL_SUBJECT,
        exam_id=exam_id or DRILL_EXAM,
        name=f"Drill {seq} — {len(questions)} questions" if seq
             else f"Mixed drill — {len(questions)} questions",
        group="Mixed drills",
        questions=questions,
        path="(drill)",
        timed_minutes=minutes,
    )


def inject(library, exams):
    """Put the drill exams into the library, in place, newest first."""
    s = library.subject(DRILL_SUBJECT)
    if s is None:
        s = content.Subject(subject_id=DRILL_SUBJECT, name="Mixed drills",
                            icon="", order=-1, weight="", description="",
                            exams=[])
        library.subjects.append(s)
    s.exams = list(exams)
    return library


def record(exam, result):
    """Mark this drill's questions as seen and log its score.

    Called once the drill is submitted, not when it starts: an abandoned
    attempt should not burn questions out of the cycle.
    """
    state = _state()
    seen = set(state["seen"])
    seen.update(q["id"] for q in exam.questions)
    state["seen"] = sorted(seen)
    # Which subject each miss came from is free here and nowhere else: the
    # drill's question ids carry their source, and the per-exam record under
    # "drill/current" is overwritten by the next drill. Count it now or lose it.
    served = Counter(q["id"].split("/")[0] for q in exam.questions)
    missed = Counter(w.split("/")[0] for w in result.get("wrong_ids", []))
    state["history"].append({
        "n": result.get("total", len(exam.questions)),
        "correct": result.get("correct", 0),
        "elapsed_s": result.get("elapsed_s"),
        "duration_s": (exam.timed_minutes or 0) * 60,
        "cycle": state["cycle"],
        "served": dict(served),
        "missed": dict(missed),
        "at": result.get("submitted_at"),
    })
    state["history"] = state["history"][-20:]


# --------------------------------------------------------------------------- #
# Session wiring                                                               #
# --------------------------------------------------------------------------- #
# Keep a bounded history. Each entry is twenty keys, so fifty drills is a few
# tens of KB in localStorage — small, but not unbounded.
MAX_KEPT = 50


def _drills():
    return _state().setdefault("drills", [])


def rebuild(library):
    """Re-create every stored drill as an Exam, newest first.

    Streamlit keeps no object graph between reruns, and the drill has no file
    on disk, so the questions are looked up again from the real library each
    run. The keys live in progress rather than session state: a drill left
    half-finished has to survive a closed tab, a sleeping app or a redeploy,
    which session state does not.
    """
    index = {k: (k, q, sid) for k, q, sid in pool(library)}
    exams = []
    for d in reversed(_drills()):
        picked = [index[k] for k in d["keys"] if k in index]
        if picked:
            exams.append(as_exam(picked, d["id"], d.get("seq")))
    return exams


def active_id():
    """The drill with a timed session still open, if there is one."""
    prog = st.session_state.get("progress", {})
    for d in reversed(_drills()):
        e = prog.get(f"{DRILL_SUBJECT}/{d['id']}")
        if e and e.get("exam_session") and not e.get("finished"):
            return d["id"]
    return None


def begin(library, n=DEFAULT_N):
    """Pick a fresh drill and hand it to the timed-exam machinery."""
    from core import exam as exam_core

    picked, reset = build(library, n)
    state = _state()
    seq = state.get("next_seq", len(_drills()) + 1)
    state["next_seq"] = seq + 1
    exam_id = f"d{seq}"

    _drills().append({"id": exam_id, "seq": seq,
                      "keys": [p[0] for p in picked]})
    # Drop the oldest once past the cap, and with them the progress entries
    # that would otherwise linger with nothing to resolve against.
    while len(_drills()) > MAX_KEPT:
        gone = _drills().pop(0)
        st.session_state.get("progress", {}).pop(
            f"{DRILL_SUBJECT}/{gone['id']}", None)

    st.session_state["drill_reset_notice"] = reset
    inject(library, rebuild(library))
    exam_core.start(library, DRILL_SUBJECT, exam_id)
