"""Review: read all questions with answers shown (not scored)."""
import streamlit as st

from core import quiz
from core.ui import go, md, render_question


def render(library):
    subject_id = st.session_state.get("subject_id")
    exam = library.exam(subject_id, st.session_state.get("review_exam"))
    if exam is None:
        go("subject", subject_id=subject_id)
        return

    if st.button("Back to exams"):
        go("subject", subject_id=subject_id)
    st.title(exam.name)
    st.caption("Answer view (not scored).")

    for i, c in enumerate(exam.questions, 1):
        with st.container(border=True):
            render_question(f"Question {i}", c["question"])
            for L in quiz.option_letters(c):
                mark = "  (correct)" if L == c["answer"] else ""
                st.write(f"{L}) {md(c['options'][L])}{mark}")
            st.info(f"**Explanation:** {md(c.get('explanation')) or '(none)'}")
