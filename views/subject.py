"""Subject: list exams (grouped) with status + start/retry/review actions."""
import streamlit as st

from core import progress, quiz
from core.ui import go
from views import exam as exam_view


def render(library):
    subject_id = st.session_state.get("subject_id")
    s = library.subject(subject_id)
    if s is None:
        go("home")
        return

    if st.button("Back"):
        go("home")
    st.title(s.name)
    if s.description:
        st.caption(s.description)

    if not s.exams:
        st.info("This topic has no exams yet. Add a JSON file to "
                f"`content/{s.subject_id}/` (see `docs/ADD_EXAM.md`).")
        return

    last_group = None
    for exam in s.exams:
        if exam.group and exam.group != last_group:
            st.subheader(exam.group)
            last_group = exam.group

        if exam.timed_minutes:
            exam_view.render_exam_card(library, exam)
            continue

        txt, _ = progress.status(s.subject_id, exam.exam_id, exam.n)
        e = progress.entry(s.subject_id, exam.exam_id) or {}
        with st.container(border=True):
            st.markdown(f"**{exam.name}**  ·  {exam.n} questions")
            st.write(txt)

            # "Start over" only exists while a round is unfinished, so the row
            # grows to four rather than leaving it stranded on a line of its
            # own. It sits beside "Continue" because the two are the same
            # choice — carry on with this round, or throw it away.
            running = bool(e.get("in_progress"))
            cols = st.columns(4 if running else 3)
            with cols[0]:
                if running:
                    label = "Continue"
                elif e.get("finished"):
                    label = "Restart (full)"
                else:
                    label = "Start"
                if st.button(label, key=f"start_{exam.exam_id}",
                             use_container_width=True, type="primary"):
                    if running:
                        quiz.resume(library, s.subject_id, exam.exam_id)
                    else:
                        quiz.start(library, s.subject_id, exam.exam_id, "full")
            if running:
                with cols[1]:
                    if st.button("Start over", key=f"restart_{exam.exam_id}",
                                 use_container_width=True):
                        e.pop("in_progress", None)
                        progress.save()
                        quiz.start(library, s.subject_id, exam.exam_id, "full")
            with cols[-2]:
                n_wrong = len(e.get("wrong_ids", []))
                if st.button(f"Retry {n_wrong} wrong",
                             key=f"wrong_{exam.exam_id}",
                             disabled=n_wrong == 0, use_container_width=True):
                    quiz.start(library, s.subject_id, exam.exam_id, "wrong")
            with cols[-1]:
                if st.button("View answers", key=f"rev_{exam.exam_id}",
                             use_container_width=True):
                    go("review", subject_id=s.subject_id, review_exam=exam.exam_id)
