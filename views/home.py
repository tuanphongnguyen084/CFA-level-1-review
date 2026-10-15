"""Home: the mixed drill, then a grid of subjects with per-subject progress."""
import streamlit as st

from core import drill, progress
from core.ui import go


def _mixed_drill(library):
    """Entry point for a timed set drawn from every subject at once.

    Lives above the subject list because it is the one thing here that is not
    organised by topic — which is the point of it.
    """
    seen, total, cycle = drill.cycle_progress(library)
    if not total:
        return

    with st.container(border=True):
        st.markdown(f"**Mixed drill — {drill.DEFAULT_N} questions · "
                    f"{round(drill.DEFAULT_N * drill.MINUTES_PER_QUESTION)} min**")
        st.caption("All ten subjects at once, apportioned by exam weight, "
                   "timed at 1.5 minutes a question. Nothing repeats until "
                   "the whole bank has been served.")

        c1, c2 = st.columns([3, 2], vertical_alignment="center")
        with c1:
            left = total - seen
            st.progress(seen / total,
                        text=f"Round {cycle} — {seen}/{total} used, "
                             f"{left} left")
        with c2:
            label = "Start drill" if left >= drill.DEFAULT_N else \
                    (f"Start drill ({left} left)" if left else "Start new round")
            if st.button(label, key="start_drill", type="primary",
                         use_container_width=True):
                drill.begin(library)

        past = drill.history()
        if past:
            recent = " · ".join(
                f"{h['correct']}/{h['n']}" for h in past[-5:])
            st.caption(f"Last drills: {recent}")


def render(library):
    st.markdown("# CFA Level 1")
    st.caption("Choose a topic to begin. Progress is saved in your browser.")

    if not library.subjects:
        st.info("No content yet. Add exams to the `content/` folder "
                "(see `docs/ADD_EXAM.md`).")
        return

    _mixed_drill(library)

    for s in library.subjects:
        if s.subject_id == drill.DRILL_SUBJECT:
            continue   # synthetic; it has its own card above
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
                    label = f"{done}/{len(s.exams)} done"
                    # Carry the score up to this level too, so a glance at the
                    # home page answers "how am I doing in Ethics?" without
                    # opening the topic and reading every exam.
                    sc = progress.subject_score(s.subject_id, s.exams)
                    if sc:
                        label += f" · {sc[2]}% correct"
                    st.progress(done / len(s.exams), text=label)
                else:
                    st.caption("Coming soon")
            with c3:
                if s.exams and st.button("Open", key=f"open_{s.subject_id}",
                                         use_container_width=True,
                                         type="primary"):
                    go("subject", subject_id=s.subject_id)
