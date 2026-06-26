"""Result: score + review of wrong answers + retry actions."""
import streamlit as st

from core import progress, quiz
from core.ui import go, md


def render(library):
    q = st.session_state.get("quiz")
    if not q or "result" not in q:
        go("home")
        return

    r = q["result"]
    exam = library.exam(q["subject_id"], q["exam_id"])
    st.title("Results")
    st.subheader(exam.name)

    pct = round(r["correct"] / r["total"] * 100) if r["total"] else 0
    st.metric("Score", f"{r['correct']}/{r['total']}", f"{pct}%")
    if not r["wrong"]:
        st.success("All correct!")
        st.balloons()
    else:
        st.warning(f"You missed {len(r['wrong'])} questions.")

    by_id = {x["id"]: x for x in exam.questions}
    if r["wrong"]:
        with st.expander(f"Review {len(r['wrong'])} wrong", expanded=False):
            for qid in r["wrong"]:
                c = by_id[qid]
                st.markdown(f"**{md(c['question'])}**")
                st.write(f"You chose: {q['answers'].get(qid, '—')} · "
                         f"Correct: **{c['answer']}) {md(c['options'][c['answer']])}**")
                st.caption(md(c.get("explanation")))
                st.divider()

    e = progress.entry(q["subject_id"], q["exam_id"]) or {}
    n_wrong = len(e.get("wrong_ids", []))
    cols = st.columns(3)
    with cols[0]:
        if st.button(f"Retry {n_wrong} wrong", disabled=n_wrong == 0,
                     use_container_width=True):
            quiz.start(library, q["subject_id"], q["exam_id"], "wrong")
    with cols[1]:
        if st.button("Restart (full)", use_container_width=True):
            quiz.start(library, q["subject_id"], q["exam_id"], "full")
    with cols[2]:
        if st.button("Back to exams", type="primary", use_container_width=True):
            go("subject", subject_id=q["subject_id"])
