"""Quiz: one question at a time, check-then-explain, then next/submit."""
import streamlit as st

from core import quiz
from core.ui import md, render_question


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
    render_question(f"Question {idx + 1} / {total}", cur["question"])

    letters = quiz.option_letters(cur)
    chosen = q["answers"].get(cur["id"])
    opts = [f"{L}) {md(cur['options'][L])}" for L in letters]
    pick = st.radio(
        "Choose an answer:", opts,
        index=letters.index(chosen) if chosen in letters else None,
        key=f"radio_{cur['id']}_{idx}",
        disabled=q["checked"],
    )

    if not q["checked"]:
        if st.button("Check", type="primary", disabled=pick is None):
            q["answers"][cur["id"]] = pick.split(")")[0]
            q["checked"] = True
            quiz.persist_in_progress()
            st.rerun()
        return

    chosen = q["answers"][cur["id"]]
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
        if idx > 0 and st.button("Previous", use_container_width=True):
            q["idx"] -= 1
            q["checked"] = True
            st.rerun()
    with nav[1]:
        if idx + 1 < total:
            if st.button("Next", type="primary", use_container_width=True):
                q["idx"] += 1
                q["checked"] = q["order"][q["idx"]] in q["answers"]
                quiz.persist_in_progress()
                st.rerun()
        else:
            if st.button("Submit & see results", type="primary",
                         use_container_width=True):
                quiz.finish(library)
