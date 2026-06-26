"""Home: grid of subjects with per-subject progress."""
import streamlit as st

from core import progress
from core.ui import go


def render(library):
    st.markdown("# CFA Level 1")
    st.caption("Choose a topic to begin. Progress is saved in your browser.")

    if not library.subjects:
        st.info("No content yet. Add exams to the `content/` folder "
                "(see `docs/ADD_EXAM.md`).")
        return

    for s in library.subjects:
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 3, 2], vertical_alignment="center")
            with c1:
                st.markdown(f"**{s.name}**")
                meta = f"{len(s.exams)} exams · {s.n_questions} questions"
                if s.weight:
                    meta += f" · {s.weight}"
                st.caption(meta)
            with c2:
                if s.exams:
                    done = sum(1 for e in s.exams
                               if progress.is_finished(s.subject_id, e.exam_id))
                    st.progress(done / len(s.exams),
                                text=f"{done}/{len(s.exams)} done")
                else:
                    st.caption("Coming soon")
            with c3:
                if s.exams and st.button("Open", key=f"open_{s.subject_id}",
                                         use_container_width=True,
                                         type="primary"):
                    go("subject", subject_id=s.subject_id)
