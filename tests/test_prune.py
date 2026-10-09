"""Withdrawing a question must not leave wreckage in anyone's saved progress.

FSA Q70 was removed because the accumulated-depreciation figures the vendor
printed make it unanswerable by the correct method (7m + 4m - 3m implies 8m of
accumulated depreciation on equipment that cost 5m). Anyone who had already
answered it carries its id in their wrong list.
"""
import os
import sys

import pytest

os.environ.setdefault("CFA_DISABLE_LOCALSTORAGE", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from core import progress  # noqa: E402
from core.content import Exam, Library, Subject  # noqa: E402


def _exam(subject_id, exam_id, qids):
    return Exam(subject_id=subject_id, exam_id=exam_id, name=exam_id, group="g",
                questions=[{"id": q} for q in qids], path="x", private=False)


@pytest.fixture
def library():
    fsa = Subject("fsa", "FSA", "x", 1, "", "", exams=[
        _exam("fsa", "1000-fsa-4", ["Q67", "Q68", "Q71"]),
    ])
    return Library(subjects=[fsa], errors=[])


@pytest.fixture
def store(monkeypatch):
    data = {}
    monkeypatch.setattr(st, "session_state", {"progress": data}, raising=False)
    return data


def test_withdrawn_question_is_dropped(store, library):
    store["fsa/1000-fsa-4"] = {"finished": True, "wrong_ids": ["Q68", "Q70"]}
    assert progress.prune_missing_questions(library) is True
    assert store["fsa/1000-fsa-4"]["wrong_ids"] == ["Q68"]


def test_score_reflects_the_shorter_exam(store, library):
    """Q70 lingering would read as a miss on an exam it is no longer part of."""
    store["fsa/1000-fsa-4"] = {"finished": True, "wrong_ids": ["Q70"]}
    assert progress.score("fsa", "1000-fsa-4", 3) == (2, 3, 67)
    progress.prune_missing_questions(library)
    assert progress.score("fsa", "1000-fsa-4", 3) == (3, 3, 100)


def test_live_ids_survive(store, library):
    store["fsa/1000-fsa-4"] = {"finished": True, "wrong_ids": ["Q67", "Q71"]}
    assert progress.prune_missing_questions(library) is False
    assert store["fsa/1000-fsa-4"]["wrong_ids"] == ["Q67", "Q71"]


def test_progress_for_an_absent_exam_is_left_alone(store, library):
    """The dangerous case.

    Given a viewer's filtered library, every buyers-only exam looks missing.
    An absent exam must therefore mean "cannot judge", never "delete" — the
    same guard covers a content file that fails to load for a single run.
    """
    store["ethics/ethics-review-test-1"] = {"finished": True,
                                            "wrong_ids": ["Q1", "Q2"]}
    assert progress.prune_missing_questions(library) is False
    assert store["ethics/ethics-review-test-1"]["wrong_ids"] == ["Q1", "Q2"]


def test_entries_without_a_wrong_list_are_untouched(store, library):
    store["fsa/1000-fsa-4"] = {"in_progress": {"idx": 2, "n": 3}}
    assert progress.prune_missing_questions(library) is False
    assert store["fsa/1000-fsa-4"] == {"in_progress": {"idx": 2, "n": 3}}
