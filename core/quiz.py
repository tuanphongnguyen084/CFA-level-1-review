"""
Quiz state machine. The active quiz lives entirely in ``st.session_state.quiz``
so a localStorage rerun can never disturb it. Durable progress is written to
the browser via ``core.progress``.

Quiz shape::

    {
      "subject_id": str, "exam_id": str,
      "mode": "full" | "wrong",
      "order": [question_id, ...],   # shuffled
      "idx": int,
      "answers": {question_id: chosen_letter},
      "checked": bool,               # current question revealed?
      "result": {...}                # set on finish
    }
"""
import random

import streamlit as st

from core import progress


def option_letters(question):
    """Option keys in display order (supports A/B/C and A/B/C/D)."""
    return sorted(question["options"].keys())


def start(library, subject_id, exam_id, mode):
    exam = library.exam(subject_id, exam_id)
    e = progress.entry(subject_id, exam_id) or {}
    if mode == "wrong":
        wrong = set(e.get("wrong_ids", []))
        pool = [q for q in exam.questions if q["id"] in wrong]
    else:
        pool = list(exam.questions)
    random.shuffle(pool)
    st.session_state.quiz = {
        "subject_id": subject_id,
        "exam_id": exam_id,
        "mode": mode,
        "order": [q["id"] for q in pool],
        "idx": 0,
        "answers": {},
        "checked": False,
    }
    st.session_state.view = "quiz"
    st.rerun()


def resume(library, subject_id, exam_id):
    e = progress.entry(subject_id, exam_id) or {}
    ip = e.get("in_progress") or {}
    order = ip.get("order")
    if not order or ip["idx"] >= len(order):
        # No resumable snapshot (e.g. saved before "order"/"answers" were
        # tracked, or now out of range) — start a fresh round in the same mode
        # rather than crashing.
        start(library, subject_id, exam_id, ip.get("mode", "full"))
        return

    # A question can be withdrawn while a round is saved mid-flight. The views
    # walk current_questions(), which silently drops ids the exam no longer
    # has, so leaving them in "order" makes the two lists disagree from the
    # gap onwards: "checked" is read off order[idx] while the card on screen
    # is questions[idx], one place further along. That mismatch crashed the
    # quiz on a question the student had not answered yet. Prune here instead,
    # keeping their place and their work.
    exam = library.exam(subject_id, exam_id)
    live = {x["id"] for x in exam.questions} if exam else set()
    kept = [qid for qid in order if qid in live]
    if not kept:
        start(library, subject_id, exam_id, ip.get("mode", "full"))
        return
    # Land on the same question when it survived, otherwise on the one that
    # now occupies its place.
    idx = min(sum(1 for qid in order[:ip["idx"]] if qid in live), len(kept) - 1)
    order = kept
    answers = {k: v for k, v in (ip.get("answers") or {}).items() if k in live}

    st.session_state.quiz = {
        "subject_id": subject_id,
        "exam_id": exam_id,
        "mode": ip["mode"],
        "order": order,
        "idx": idx,
        "answers": answers,
        "checked": order[idx] in answers,
    }
    st.session_state.view = "quiz"
    st.rerun()


def current_questions(library):
    q = st.session_state.quiz
    exam = library.exam(q["subject_id"], q["exam_id"])
    by_id = {x["id"]: x for x in exam.questions}
    return [by_id[i] for i in q["order"] if i in by_id]


def persist_in_progress():
    q = st.session_state.quiz
    e = progress.get_or_create(q["subject_id"], q["exam_id"])
    if q["idx"] < len(q["order"]) and not q.get("done"):
        e["in_progress"] = {
            "idx": q["idx"],
            "n": len(q["order"]),
            "mode": q["mode"],
            "order": q["order"],
            "answers": q["answers"],
        }
    progress.save()


def exit_to_subject():
    q = st.session_state.quiz
    persist_in_progress()
    st.session_state.view = "subject"
    st.session_state.subject_id = q["subject_id"]
    st.rerun()


def finish(library):
    q = st.session_state.quiz
    exam = library.exam(q["subject_id"], q["exam_id"])
    by_id = {x["id"]: x for x in exam.questions}
    wrong_now = [qid for qid in q["order"]
                 if q["answers"].get(qid) != by_id[qid]["answer"]]

    e = progress.get_or_create(q["subject_id"], q["exam_id"])
    e["finished"] = True
    e["last_mode"] = q["mode"]
    e.pop("in_progress", None)
    if q["mode"] == "wrong":
        prev = set(e.get("wrong_ids", []))
        fixed = {qid for qid in q["order"]
                 if q["answers"].get(qid) == by_id[qid]["answer"]}
        e["wrong_ids"] = sorted(prev - fixed)
    else:
        e["wrong_ids"] = sorted(wrong_now)
    progress.save()

    q["result"] = {
        "total": len(q["order"]),
        "wrong": wrong_now,
        "correct": len(q["order"]) - len(wrong_now),
    }
    st.session_state.view = "result"
    st.rerun()
