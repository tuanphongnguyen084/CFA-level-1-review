"""Buyers-only content must be invisible AND unreachable for other viewers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.content import (  # noqa: E402
    Exam, Library, Subject, is_private_exam, visible_library,
)


def _exam(subject_id, exam_id, private):
    return Exam(subject_id=subject_id, exam_id=exam_id, name=exam_id,
                group="g", questions=[{"id": "q1"}], path="x", private=private)


def _library():
    ethics = Subject("ethics", "Ethics", "x", 1, "", "", exams=[
        _exam("ethics", "1000-ethics-1", False),
        _exam("ethics", "ethics-review-test-1", True),
    ])
    mock = Subject("mock", "Mock", "x", 2, "", "", exams=[
        _exam("mock", "mock-1-session-1", False),
    ])
    equity = Subject("equity", "Equity", "x", 3, "", "", exams=[
        _exam("equity", "reading-48-part-1", True),
    ])
    return Library(subjects=[ethics, mock, equity],
                   errors=[("content/ethics/ethics-review-test-1.json", "oops")])


# --- the rule itself ---------------------------------------------------- #

def test_question_bank_and_mocks_are_public():
    assert is_private_exam("ethics", "1000-ethics-1") is False
    assert is_private_exam("mock", "mock-3-session-2") is False


def test_everything_else_is_private():
    for subject_id, exam_id in [("ethics", "ethics-review-test-1"),
                                ("portfolio", "pm-review-test-2"),
                                ("economics", "economics-practice-5"),
                                ("equity", "reading-48-part-1")]:
        assert is_private_exam(subject_id, exam_id) is True


def test_a_file_can_override_the_rule_either_way():
    assert is_private_exam("ethics", "1000-ethics-1", {"private": True}) is True
    assert is_private_exam("ethics", "ethics-review-test-1", {"private": False}) is False


# --- filtering ----------------------------------------------------------- #

def test_owner_sees_everything_untouched():
    lib = _library()
    assert visible_library(lib, True) is lib


def test_ordinary_viewer_loses_private_exams():
    vis = visible_library(_library(), False)
    ethics = vis.subject("ethics")
    assert [e.exam_id for e in ethics.exams] == ["1000-ethics-1"]
    assert vis.subject("mock") is not None


def test_private_exams_are_unreachable_not_just_unlisted():
    """Views resolve content through library.exam(); a stale session id must
    not be able to open a hidden exam."""
    vis = visible_library(_library(), False)
    assert vis.exam("ethics", "ethics-review-test-1") is None
    assert vis.exam("ethics", "1000-ethics-1") is not None


def test_subject_with_only_private_exams_disappears_entirely():
    vis = visible_library(_library(), False)
    assert vis.subject("equity") is None
    assert [s.subject_id for s in vis.subjects] == ["ethics", "mock"]


def test_loader_errors_are_withheld_from_ordinary_viewers():
    """They name files, which would reveal the hidden material exists."""
    assert visible_library(_library(), False).errors == []
    assert visible_library(_library(), True).errors != []
