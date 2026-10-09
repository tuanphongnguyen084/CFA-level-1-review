"""
CFA Quiz — multi-subject practice app (Streamlit).

Data-driven: every folder in content/ is a subject and every *.json in it is an
exam, so adding an exam = drop a JSON file + redeploy (see docs/ADD_EXAM.md).
Progress is saved per-browser via localStorage — no login, no backend.
"""
import os
import sys

# Make `core`/`views` importable no matter how the app is launched
# (streamlit run adds this dir, but AppTest / other launchers may not).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st  # noqa: E402

from core import access, content, progress, ui  # noqa: E402
from views import exam as exam_view  # noqa: E402
from views import home, quiz, result, review, subject  # noqa: E402

st.set_page_config(page_title="CFA Quiz", layout="centered",
                   initial_sidebar_state="expanded")
ui.inject_css()

# Google sign-in + buyer allowlist. No-op unless [auth] is configured in
# secrets — see core/access.py.
access.require_access()

# localStorage component + hydrate progress (must run every script run).
progress.init()

# Everyone signed in may study; only owner accounts see the buyers-only
# material, and for everyone else it is absent rather than locked.
_full = content.load_library()
library = content.visible_library(_full, access.is_owner())

# Progress saved before a question was withdrawn still names it. Clean that up
# once the browser has handed back the stored copy, and against the full
# library — pruning against the filtered one would read every buyers-only exam
# as missing and wipe that history for ordinary visitors.
if st.session_state.get("_prog_hydrated") and not st.session_state.get("_prog_pruned"):
    st.session_state["_prog_pruned"] = True
    if progress.prune_missing_questions(_full):
        progress.save()

ui.sidebar(library)
access.sidebar_account()

if "view" not in st.session_state:
    st.session_state.view = "home"

# A session carried over from an owner account (or from before an exam was
# hidden) can still point at content this viewer may no longer open, and the
# views would fail on the missing exam. Send those back home.
_open = (st.session_state.get("quiz") or st.session_state.get("exam") or {})
if _open and not library.exam(_open.get("subject_id"), _open.get("exam_id")):
    for key in ("quiz", "exam", "review_exam"):
        st.session_state.pop(key, None)
    st.session_state.view = "home"

VIEWS = {
    "home": home.render,
    "subject": subject.render,
    "quiz": quiz.render,
    "result": result.render,
    "review": review.render,
    "exam": exam_view.render,
    "exam_result": exam_view.render_result,
}
VIEWS.get(st.session_state.view, home.render)(library)
