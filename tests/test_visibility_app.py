"""A session left pointing at hidden content must not survive a tier change.

Filtering the library removes buyers-only exams from every listing, but a
session started by an owner (or before an exam was hidden) still carries the
exam id. Without a guard the views would resolve it to None and fail — or
worse, keep rendering it.
"""
import os
import sys

from streamlit.testing.v1 import AppTest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

APP = os.path.join(REPO, "streamlit_app.py")
# Mirrors the shape core.quiz.start() writes, so the "left alone" case
# actually renders instead of failing on a missing key.
HIDDEN = {"subject_id": "ethics", "exam_id": "ethics-review-test-1",
          "mode": "full", "order": ["Q1"], "idx": 0, "answers": {},
          "checked": False}


def _run_with(view, **state):
    os.environ["CFA_DISABLE_LOCALSTORAGE"] = "1"
    # These cases read the real content/ folder, so drop any library another
    # test cached from its fixture directory — otherwise the outcome depends
    # on test ordering.
    from core import content
    content.load_library.clear()
    at = AppTest.from_file(APP)
    at.session_state["view"] = view
    for k, v in state.items():
        at.session_state[k] = v
    at.run(timeout=60)
    return at


def test_stale_quiz_on_hidden_exam_is_dropped():
    at = _run_with("quiz", quiz=dict(HIDDEN))
    assert not at.exception
    assert at.session_state["view"] == "home"
    assert "quiz" not in at.session_state


def test_stale_exam_mode_session_on_hidden_exam_is_dropped():
    at = _run_with("exam", exam=dict(HIDDEN))
    assert not at.exception
    assert at.session_state["view"] == "home"
    assert "exam" not in at.session_state


def test_session_on_visible_exam_is_left_alone():
    visible = dict(HIDDEN, exam_id="1000-ethics-1")
    visible["order"] = ["Q1"]           # a real question id in that file
    at = _run_with("quiz", quiz=visible)
    assert not at.exception
    assert at.session_state["view"] == "quiz"
