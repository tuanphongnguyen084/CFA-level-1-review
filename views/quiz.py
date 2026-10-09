"""Quiz: one question at a time, check-then-explain, then next/submit."""
import streamlit as st

from core import quiz
from core.ui import md, render_question


def _go_to(q, new_idx):
    """Move to another question, re-deriving whether it has been answered."""
    q["idx"] = new_idx
    q["checked"] = q["order"][new_idx] in q["answers"]
    quiz.persist_in_progress()
    st.rerun()


def render(library):
    q = st.session_state.get("quiz")
    if not q:
        st.session_state.view = "home"
        st.rerun()
        return

    exam = library.exam(q["subject_id"], q["exam_id"])
    questions = quiz.current_questions(library)
    total = len(questions)
    if total == 0:
        st.warning("No questions for this round.")
        if st.button("Back"):
            quiz.exit_to_subject()
        return

    idx = q["idx"]
    top = st.columns([1, 3])
    with top[0]:
        if st.button("Exit"):
            quiz.exit_to_subject()
    with top[1]:
        st.caption(f"Question {idx + 1}/{total} · {exam.name}")
        st.progress(idx / total)

    cur = questions[idx]
    render_question(f"Question {idx + 1} / {total}", cur["question"],
                    key=f'{q["exam_id"]}-{cur["id"]}')

    letters = quiz.option_letters(cur)
    chosen = q["answers"].get(cur["id"])
    # Read "revealed?" off the question on screen rather than the stored flag.
    # The two can disagree — they did when a withdrawn question shortened the
    # round under a saved order — and then the flag says an answer exists for
    # a question that was never answered.
    checked = chosen is not None
    opts = [f"{L}) {md(cur['options'][L])}" for L in letters]
    pick = st.radio(
        "Choose an answer:", opts,
        index=letters.index(chosen) if chosen in letters else None,
        key=f"radio_{cur['id']}_{idx}",
        disabled=checked,
    )

    if not checked:
        # Checking used to be the only way forward, so a question you couldn't
        # answer stopped the round dead. Skipping leaves it unanswered, which
        # grades as wrong and therefore comes back in "Retry wrong" — exactly
        # where a question you couldn't do belongs.
        act = st.columns([2, 1, 1]) if idx > 0 else st.columns([2, 1])
        with act[0]:
            if st.button("Check", type="primary", disabled=pick is None,
                         use_container_width=True):
                q["answers"][cur["id"]] = pick.split(")")[0]
                q["checked"] = True
                quiz.persist_in_progress()
                st.rerun()
        with act[1]:
            last = idx + 1 >= total
            if st.button("Skip" if not last else "Skip & finish",
                         use_container_width=True):
                if last:
                    quiz.finish(library)
                else:
                    _go_to(q, idx + 1)
        if idx > 0:
            with act[2]:
                if st.button("Previous", use_container_width=True,
                             key="prev_unchecked"):
                    _go_to(q, idx - 1)
        return

    correct = cur["answer"]
    if chosen == correct:
        st.success(f"Correct! Answer: **{correct})**")
    else:
        st.error(f"Incorrect. You chose **{chosen})** · "
                 f"Correct answer: **{correct}) {md(cur['options'][correct])}**")
    if cur.get("answer_source") == "manual":
        st.caption("Answer inferred from the explanation (not bolded in the "
                   "source).")
    st.info(f"**Explanation:** {md(cur.get('explanation')) or '(none)'}")

    nav = st.columns(2)
    with nav[0]:
        # Must re-derive "checked" rather than assume True: going back to a
        # question that was skipped would otherwise try to show an answer
        # that was never given.
        if idx > 0 and st.button("Previous", use_container_width=True):
            _go_to(q, idx - 1)
    with nav[1]:
        if idx + 1 < total:
            if st.button("Next", type="primary", use_container_width=True):
                _go_to(q, idx + 1)
        else:
            if st.button("Submit & see results", type="primary",
                         use_container_width=True):
                quiz.finish(library)
