"""Skipping a question you can't answer, and coming back to it.

Before this existed, "Check" was the only way forward, so a question you
couldn't answer ended the round. The pieces that matter: skipping advances
without recording an answer, returning to a skipped question does not pretend
it was answered (which used to crash, because the old Previous button set
checked=True unconditionally), and an unanswered question grades as wrong so
it resurfaces under "Retry wrong".
"""
import os
import sys

import pytest

os.environ.setdefault("CFA_DISABLE_LOCALSTORAGE", "1")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from streamlit.testing.v1 import AppTest  # noqa: E402

QUESTIONS = [
    {"id": f"Q{i}", "num": i, "question": f"Question {i}?",
     "options": {"A": "a", "B": "b", "C": "c"}, "answer": "B",
     "explanation": f"because {i}"}
    for i in (1, 2, 3)
]


@pytest.fixture
def fixture_dir(tmp_path, monkeypatch):
    import json

    from core import content
    sub = tmp_path / "ethics"
    sub.mkdir()
    (sub / "_subject.json").write_text(json.dumps({"name": "T", "order": 1}))
    (sub / "1000-t-1.json").write_text(json.dumps(
        {"name": "Fixture", "group": "g", "questions": QUESTIONS}))
    monkeypatch.setenv("_FIXTURE_CONTENT_DIR", str(tmp_path))
    monkeypatch.setattr(content, "CONTENT_DIR", str(tmp_path))
    content.load_library.clear()
    yield str(tmp_path)
    content.load_library.clear()


def _script():
    import os

    import streamlit as st
    from core import content, quiz, progress
    from views import quiz as quiz_view
    content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
    content.load_library.clear()
    progress.init()
    lib = content.load_library()
    if not st.session_state.get("_started"):
        st.session_state["_started"] = True
        quiz.start(lib, "ethics", "1000-t-1", "full")   # reruns
    quiz_view.render(lib)


def _started():
    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def test_skip_is_offered_before_answering(fixture_dir):
    at = _started()
    labels = [b.label for b in at.button]
    assert "Check" in labels
    assert "Skip" in labels


def test_skip_advances_without_recording_an_answer(fixture_dir):
    at = _started()
    q = at.session_state["quiz"]
    first = q["order"][0]
    [b for b in at.button if b.label == "Skip"][0].click().run(timeout=30)
    assert not at.exception
    q = at.session_state["quiz"]
    assert q["idx"] == 1
    assert first not in q["answers"]      # nothing was answered on their behalf
    assert q["checked"] is False          # next question starts unanswered


def test_returning_to_a_skipped_question_does_not_claim_it_was_answered(fixture_dir):
    at = _started()
    [b for b in at.button if b.label == "Skip"][0].click().run(timeout=30)
    [b for b in at.button if b.label == "Previous"][0].click().run(timeout=30)
    assert not at.exception, [str(e) for e in at.exception]
    q = at.session_state["quiz"]
    assert q["idx"] == 0
    assert q["checked"] is False


def test_skipped_questions_count_as_wrong(fixture_dir):
    at = _started()
    for _ in range(2):                    # skip to the last question
        [b for b in at.button if b.label == "Skip"][0].click().run(timeout=30)
    finish = [b for b in at.button if b.label == "Skip & finish"]
    assert finish, [b.label for b in at.button]
    finish[0].click().run(timeout=30)
    assert not at.exception, [str(e) for e in at.exception]
    result = at.session_state["quiz"]["result"]
    assert result["total"] == 3
    assert result["correct"] == 0
    assert len(result["wrong"]) == 3      # all three come back under Retry wrong
