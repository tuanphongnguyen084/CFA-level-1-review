"""
Timed exam mode: subject-page card, the exam-taking screen (timer, free
navigation, flagging, silent answer capture), and the durable post-submit
review screen.

Kept fully separate from views/quiz.py — real exam questions are never
shuffled and give no feedback until submission, the opposite of how
practice-quiz works, so the two views don't share a state machine (see
core/exam.py's module docstring for the full rationale). The one
deliberate exception: a finished exam's wrong answers can be practiced
untimed via the existing, battle-tested core.quiz "wrong" mode.
"""
import time

import streamlit as st

from core import content, exam as exam_core, progress, quiz
from core.ui import go, md, render_question

_NEGATIVE = "#f3727f"   # matches docs/DESIGN-spotify.md semantic colors
_WARNING = "#ffa42b"
_GRID_COLS = 10


# --------------------------------------------------------------------- #
# Subject-page card                                                     #
# --------------------------------------------------------------------- #
def render_exam_card(library, exam):
    e = progress.entry(exam.subject_id, exam.exam_id) or {}
    es = e.get("exam_session")
    result = e.get("exam_result")

    with st.container(border=True):
        st.markdown(f"**{exam.name}**  ·  {exam.n} questions · "
                    f"{exam.timed_minutes} min")

        if es:
            mins_left = exam_core.remaining(es["start_ts"], es["duration_s"],
                                             time.time())
            st.write(f"In progress — {int(mins_left) // 60} min remaining")
        elif result:
            pct = round(result["correct"] / result["total"] * 100) \
                if result["total"] else 0
            st.write(f"Completed — {result['correct']}/{result['total']} "
                      f"({pct}%)")
        else:
            st.write("Not started")

        cols = st.columns(3) if result else st.columns(1)
        with cols[0]:
            label = "Continue" if es else ("Retake" if result else "Start Exam")
            if st.button(label, key=f"examstart_{exam.exam_id}",
                         type="primary", use_container_width=True):
                if es:
                    exam_core.resume(library, exam.subject_id, exam.exam_id)
                else:
                    exam_core.start(library, exam.subject_id, exam.exam_id)
        if result:
            with cols[1]:
                if st.button("Review", key=f"examrev_{exam.exam_id}",
                             use_container_width=True):
                    go("exam_result", subject_id=exam.subject_id,
                       review_exam_id=exam.exam_id)
            with cols[2]:
                n_wrong = len(result.get("wrong_ids", []))
                if st.button(f"Practice {n_wrong} wrong (untimed)",
                             key=f"examwrong_{exam.exam_id}",
                             disabled=n_wrong == 0, use_container_width=True):
                    quiz.start(library, exam.subject_id, exam.exam_id, "wrong")


# --------------------------------------------------------------------- #
# Exam-taking screen                                                    #
# --------------------------------------------------------------------- #
@st.fragment(run_every=1)
def _timer(library):
    if exam_core.is_expired():
        exam_core.finish(library, auto=True)   # st.rerun() inside runs at app
        return                                  # scope, ending this exam view
    remaining = exam_core.remaining_seconds()
    hh, rem = divmod(int(remaining), 3600)
    mm, ss = divmod(rem, 60)
    color = _NEGATIVE if remaining < 300 else (
        _WARNING if remaining < 900 else "inherit")
    st.markdown(
        f'<div style="text-align:center;font-size:1.6rem;font-weight:700;'
        f'color:{color};">⏱ {hh}:{mm:02d}:{ss:02d}</div>',
        unsafe_allow_html=True,
    )


def _question_grid(ex, questions):
    for start in range(0, len(questions), _GRID_COLS):
        row = list(enumerate(questions))[start:start + _GRID_COLS]
        cols = st.columns(len(row))
        for col, (pos, q) in zip(cols, row):
            with col:
                answered = q["id"] in ex["answers"]
                flagged = q["id"] in ex["flagged"]
                kind = ("primary" if pos == ex["idx"]
                        else "secondary" if answered else "tertiary")
                label = f"🚩{pos + 1}" if flagged else str(pos + 1)
                if st.button(label, key=f"grid_{q['id']}", type=kind,
                             use_container_width=True):
                    ex["idx"] = pos
                    exam_core.persist_session()
                    st.rerun()


def _confirm_submit(library, answered, total, flagged_n):
    with st.popover("Submit Exam", use_container_width=True):
        st.write(f"**{answered}/{total}** answered · **{total - answered}** "
                 f"unanswered · **{flagged_n}** flagged.")
        st.write("You won't be able to change any answers after submitting.")
        if st.button("Submit", type="primary", use_container_width=True):
            exam_core.finish(library, auto=False)


def render(library):
    ex = st.session_state.get("exam")
    if not ex:
        st.session_state.view = "home"
        st.rerun()
        return

    # Time may have already run out while the user was on a different view
    # (or the tab was closed) — the periodic tick below only fires while
    # this view is actively rendering, so this catches that gap the moment
    # it's discoverable, before drawing any exam content.
    if exam_core.is_expired():
        exam_core.finish(library, auto=True)
        return

    exam_meta = library.exam(ex["subject_id"], ex["exam_id"])
    questions = exam_core.current_questions(library)
    total = len(questions)
    idx = ex["idx"]
    cur = questions[idx]

    top = st.columns([1, 3])
    with top[0]:
        if st.button("Exit"):
            exam_core.exit_to_subject()
    with top[1]:
        st.caption(f"{exam_meta.name} · Question {idx + 1}/{total}")

    _timer(library)
    _question_grid(ex, questions)

    render_question(f"Question {idx + 1} / {total}", cur["question"])

    letters = exam_core.option_letters(cur)
    chosen = ex["answers"].get(cur["id"])
    opts = [f"{L}) {md(cur['options'][L])}" for L in letters]
    pick = st.radio(
        "Choose an answer:", opts,
        index=letters.index(chosen) if chosen in letters else None,
        key=f"exam_radio_{cur['id']}",
    )
    if pick is not None:
        picked = pick.split(")")[0]
        if picked != chosen:
            exam_core.set_answer(cur["id"], picked)
            st.rerun()

    flagged = cur["id"] in ex["flagged"]
    if st.button("🚩 Flagged — click to unflag" if flagged else "Flag for review",
                 key=f"flagbtn_{cur['id']}"):
        exam_core.toggle_flag(cur["id"])
        st.rerun()

    nav = st.columns(2)
    with nav[0]:
        if idx > 0 and st.button("Previous", use_container_width=True):
            ex["idx"] -= 1
            exam_core.persist_session()
            st.rerun()
    with nav[1]:
        if idx + 1 < total and st.button("Next", type="primary",
                                          use_container_width=True):
            ex["idx"] += 1
            exam_core.persist_session()
            st.rerun()

    st.divider()
    answered = len(ex["answers"])
    st.caption(f"{answered}/{total} answered · {len(ex['flagged'])} flagged")
    _confirm_submit(library, answered, total, len(ex["flagged"]))


# --------------------------------------------------------------------- #
# Post-submit review screen — durable, works any time after submission  #
# --------------------------------------------------------------------- #
def render_result(library):
    subject_id = st.session_state.get("subject_id")
    exam_id = st.session_state.get("review_exam_id")
    exam_meta = library.exam(subject_id, exam_id) if subject_id and exam_id else None
    if exam_meta is None:
        st.session_state.view = "home"
        st.rerun()
        return

    entry = progress.entry(subject_id, exam_id) or {}
    result = entry.get("exam_result")
    if result is None:
        go("subject", subject_id=subject_id)
        return

    if st.button("Back to exams"):
        go("subject", subject_id=subject_id)

    st.title(exam_meta.name)
    pct = round(result["correct"] / result["total"] * 100) if result["total"] else 0
    st.metric("Score", f"{result['correct']}/{result['total']}", f"{pct}%")
    mins, secs = divmod(int(result["elapsed_s"]), 60)
    note = " · Auto-submitted (time expired)" if result["auto_submitted"] else ""
    st.caption(f"Time used: {mins}m {secs}s of {result['duration_minutes']}m{note}")

    filt = st.segmented_control("Filter", ["All", "Wrong", "Flagged"],
                                 default="All")

    # Exam-mode never shuffles (order = sorted by "num"), so the original
    # sequence is fully reproducible from content alone — no need to have
    # persisted it separately in exam_result.
    ordered = sorted(exam_meta.questions, key=lambda q: q.get("num", 0))
    wrong_set = set(result["wrong_ids"])
    flagged_set = set(result.get("flagged", []))

    for q in ordered:
        if filt == "Wrong" and q["id"] not in wrong_set:
            continue
        if filt == "Flagged" and q["id"] not in flagged_set:
            continue
        chosen = result["answers"].get(q["id"])
        icon = "❌" if q["id"] in wrong_set else "✅"
        stem_preview = q["question"][:80] + ("…" if len(q["question"]) > 80 else "")
        with st.expander(f"Q{q.get('num', '?')}. {stem_preview}", icon=icon):
            render_question(f"Question {q.get('num', '?')}", q["question"])
            for L in exam_core.option_letters(q):
                marks = []
                if L == q["answer"]:
                    marks.append("correct")
                if L == chosen:
                    marks.append("your answer")
                suffix = f"  _({', '.join(marks)})_" if marks else ""
                st.write(f"{L}) {md(q['options'][L])}{suffix}")
            if chosen is None:
                st.caption("(not answered)")
            st.info(f"**Explanation:** {md(q.get('explanation')) or '(none)'}")
