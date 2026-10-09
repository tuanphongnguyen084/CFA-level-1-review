"""Resuming a round whose exam lost a question while it was saved.

FSA Q70 was withdrawn mid-flight. The views walk current_questions(), which
drops ids the exam no longer has, but the saved "order" still listed all 22.
From the gap onwards the two lists ran one apart: "checked" was read off
order[idx] (answered) while the card rendered questions[idx] (not answered),
and the quiz died on `q["answers"][cur["id"]]`.
"""
import os
import sys

import pytest

os.environ.setdefault("CFA_DISABLE_LOCALSTORAGE", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from core import progress, quiz  # noqa: E402
from core.content import Exam, Library, Subject  # noqa: E402

LIVE = ["Q67", "Q68", "Q69", "Q71", "Q72"]      # Q70 withdrawn
SAVED = ["Q67", "Q68", "Q69", "Q70", "Q71", "Q72"]


@pytest.fixture
def library():
    fsa = Subject("fsa", "FSA", "x", 1, "", "", exams=[
        Exam(subject_id="fsa", exam_id="1000-fsa-4", name="n", group="g",
             questions=[{"id": i, "answer": "A"} for i in LIVE],
             path="x", private=False),
    ])
    return Library(subjects=[fsa], errors=[])


class State(dict):
    """session_state is read both ways (st.session_state.quiz and ["quiz"])."""
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


@pytest.fixture
def session(monkeypatch):
    state = State(progress={})
    monkeypatch.setattr(st, "session_state", state, raising=False)
    monkeypatch.setattr(st, "rerun", lambda *a, **k: None)
    return state


def _save(session, idx, answered):
    session["progress"]["fsa/1000-fsa-4"] = {
        "in_progress": {"idx": idx, "n": len(SAVED), "mode": "full",
                        "order": list(SAVED),
                        "answers": {q: "A" for q in answered}},
    }


def test_resumed_round_drops_the_withdrawn_question(session, library):
    _save(session, 4, ["Q67", "Q68", "Q69", "Q70"])
    quiz.resume(library, "fsa", "1000-fsa-4")
    assert session["quiz"]["order"] == LIVE


def test_checked_matches_the_question_actually_shown(session, library):
    """The crash: flag said "answered", the card showed an unanswered one."""
    _save(session, 4, ["Q67", "Q68", "Q69", "Q70"])
    quiz.resume(library, "fsa", "1000-fsa-4")
    q = session["quiz"]
    shown = quiz.current_questions(library)[q["idx"]]
    assert q["checked"] == (shown["id"] in q["answers"])
    assert len(quiz.current_questions(library)) == len(q["order"])


def test_place_is_kept_not_reset(session, library):
    """Three answered before the gap, so the student lands on the fourth."""
    _save(session, 4, ["Q67", "Q68", "Q69", "Q70"])
    quiz.resume(library, "fsa", "1000-fsa-4")
    assert session["quiz"]["idx"] == 3
    assert quiz.current_questions(library)[3]["id"] == "Q71"


def test_answer_to_the_withdrawn_question_is_forgotten(session, library):
    _save(session, 4, ["Q67", "Q70"])
    quiz.resume(library, "fsa", "1000-fsa-4")
    assert "Q70" not in session["quiz"]["answers"]
    assert session["quiz"]["answers"] == {"Q67": "A"}


def test_place_before_the_gap_is_unaffected(session, library):
    _save(session, 1, ["Q67"])
    quiz.resume(library, "fsa", "1000-fsa-4")
    assert session["quiz"]["idx"] == 1
    assert quiz.current_questions(library)[1]["id"] == "Q68"


def test_round_of_only_withdrawn_questions_starts_fresh(session, library):
    session["progress"]["fsa/1000-fsa-4"] = {
        "in_progress": {"idx": 0, "n": 1, "mode": "full",
                        "order": ["Q70"], "answers": {}},
    }
    quiz.resume(library, "fsa", "1000-fsa-4")
    assert sorted(session["quiz"]["order"]) == sorted(LIVE)
    assert session["quiz"]["idx"] == 0
