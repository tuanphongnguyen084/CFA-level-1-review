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

from core import content, progress, ui  # noqa: E402
from views import home, quiz, result, review, subject  # noqa: E402

st.set_page_config(page_title="CFA Quiz", layout="centered",
                   initial_sidebar_state="expanded")
ui.inject_css()

# localStorage component + hydrate progress (must run every script run).
progress.init()

library = content.load_library()
ui.sidebar(library)

if "view" not in st.session_state:
    st.session_state.view = "home"

VIEWS = {
    "home": home.render,
    "subject": subject.render,
    "quiz": quiz.render,
    "result": result.render,
    "review": review.render,
}
VIEWS.get(st.session_state.view, home.render)(library)
