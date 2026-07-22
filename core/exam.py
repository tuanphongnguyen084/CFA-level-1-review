"""
Timed exam-mode state machine — separate from core/quiz.py on purpose.

Practice-quiz (core/quiz.py) always shuffles and reveals each answer
immediately; a timed mock exam must preserve source question order and
show no feedback until submission, so the two never share code, not even
the one-line option_letters() helper (duplicated below).

Live state lives in st.session_state.exam, mirroring core/quiz.py's
st.session_state.quiz pattern: a localStorage hydration round-trip can
wholesale-replace st.session_state.progress, so in-flight answers must
never live there directly (see core/progress.py's docstring).

Durable, per-exam state lives in progress.entry(subject_id, exam_id):

    {
      "finished": bool,
      "exam_session": {                          # active/resumable snapshot
        "start_ts": float, "duration_s": int,
        "order": [question_id, ...], "idx": int,
        "answers": {question_id: letter}, "flagged": [question_id, ...],
      },
      "exam_result": {                            # durable, re-viewable any time
        "total": int, "correct": int, "wrong_ids": [...],
        "answers": {...}, "flagged": [...],
        "submitted_at": float, "auto_submitted": bool,
        "duration_minutes": int, "elapsed_s": float,
      },
      "wrong_ids": [...],   # mirror of exam_result.wrong_ids, so
                             # quiz.start(mode="wrong") can reuse this exam's
                             # question pool for untimed practice
    }

start_ts is a wall-clock time.time() timestamp set once and never touched
again — remaining time is always duration_s - (time.time() - start_ts), so
stepping away (or refreshing) never grants extra time.
"""
import time

import streamlit as st

from core import progress


def option_letters(question):
    return sorted(question["options"].keys())


def _grade(order, answers, by_id):
    """Pure grading logic (no Streamlit dependency) — directly unit-testable."""
    return [qid for qid in order if answers.get(qid) != by_id[qid]["answer"]]


def remaining(start_ts, duration_s, now):
    """Pure time math (no Streamlit dependency) — directly unit-testable.
    Public: also used by views/exam.py to show remaining time for a
    persisted (not-yet-resumed) session on the subject-page card."""
    return max(0.0, duration_s - (now - start_ts))


def start(library, subject_id, exam_id):
    exam = library.exam(subject_id, exam_id)
    ordered = sorted(exam.questions, key=lambda q: q.get("num", 0))
    st.session_state.exam = {
        "subject_id": subject_id,
        "exam_id": exam_id,
        "order": [q["id"] for q in ordered],
        "idx": 0,
        "answers": {},
        "flagged": [],
        "start_ts": time.time(),
        "duration_s": int(exam.timed_minutes) * 60,
    }
    persist_session()
    st.session_state.view = "exam"
    st.rerun()


def resume(library, subject_id, exam_id):
    e = progress.entry(subject_id, exam_id) or {}
    es = e.get("exam_session")
    if not es or not es.get("order"):
        # No resumable snapshot (never started, or saved before this field
        # existed) — start a fresh timed attempt instead of crashing.
        start(library, subject_id, exam_id)
        return
    order = es["order"]
    st.session_state.exam = {
        "subject_id": subject_id,
        "exam_id": exam_id,
        "order": order,
        "idx": min(es.get("idx", 0), len(order) - 1),
        "answers": dict(es.get("answers", {})),
        "flagged": list(es.get("flagged", [])),
        "start_ts": es["start_ts"],
        "duration_s": es["duration_s"],
    }
    st.session_state.view = "exam"
    st.rerun()


def current_questions(library):
    ex = st.session_state.exam
    exam = library.exam(ex["subject_id"], ex["exam_id"])
    by_id = {q["id"]: q for q in exam.questions}
    return [by_id[i] for i in ex["order"] if i in by_id]


def set_answer(qid, letter):
    st.session_state.exam["answers"][qid] = letter
    persist_session()


def toggle_flag(qid):
    flagged = st.session_state.exam["flagged"]
    if qid in flagged:
        flagged.remove(qid)
    else:
        flagged.append(qid)
    persist_session()


def persist_session():
    ex = st.session_state.exam
    e = progress.get_or_create(ex["subject_id"], ex["exam_id"])
    e["exam_session"] = {k: ex[k] for k in
                          ("start_ts", "duration_s", "order", "answers",
                           "flagged", "idx")}
    progress.save()


def remaining_seconds():
    ex = st.session_state.get("exam")
    if not ex:
        return 0.0
    return remaining(ex["start_ts"], ex["duration_s"], time.time())


def is_expired():
    return remaining_seconds() <= 0


def finish(library, auto=False):
    ex = st.session_state.exam
    exam = library.exam(ex["subject_id"], ex["exam_id"])
    by_id = {q["id"]: q for q in exam.questions}
    wrong_ids = _grade(ex["order"], ex["answers"], by_id)
    now = time.time()

    e = progress.get_or_create(ex["subject_id"], ex["exam_id"])
    e["finished"] = True
    e.pop("exam_session", None)
    e["exam_result"] = {
        "total": len(ex["order"]),
        "correct": len(ex["order"]) - len(wrong_ids),
        "wrong_ids": wrong_ids,
        "answers": dict(ex["answers"]),
        "flagged": list(ex["flagged"]),
        "submitted_at": now,
        "auto_submitted": auto,
        "duration_minutes": ex["duration_s"] // 60,
        "elapsed_s": now - ex["start_ts"],
    }
    e["wrong_ids"] = wrong_ids
    progress.save()

    st.session_state.subject_id = ex["subject_id"]
    st.session_state.review_exam_id = ex["exam_id"]
    st.session_state.view = "exam_result"
    st.rerun()


def exit_to_subject():
    persist_session()
    st.session_state.view = "subject"
    st.session_state.subject_id = st.session_state.exam["subject_id"]
    st.rerun()
