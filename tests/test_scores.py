"""Scores shown on the lists, so a finished exam can be judged without opening it."""
import os
import sys

import pytest

os.environ.setdefault("CFA_DISABLE_LOCALSTORAGE", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from core import progress  # noqa: E402


class FakeExam:
    def __init__(self, exam_id, n):
        self.exam_id, self.n = exam_id, n


@pytest.fixture
def store(monkeypatch):
    data = {}
    monkeypatch.setattr(st, "session_state", {"progress": data}, raising=False)
    return data


def test_unfinished_exam_has_no_score(store):
    store["ethics/e1"] = {"in_progress": {"idx": 2, "n": 10}}
    assert progress.score("ethics", "e1", 10) is None


def test_perfect_exam_reads_100_percent(store):
    store["ethics/e1"] = {"finished": True, "wrong_ids": []}
    assert progress.score("ethics", "e1", 10) == (10, 10, 100)
    label, kind = progress.status("ethics", "e1", 10)
    assert "100%" in label and kind == "done"


def test_partial_score_is_visible_in_the_label(store):
    """The old label said only "5 wrong left" — no score at all."""
    store["ethics/e1"] = {"finished": True, "wrong_ids": ["a", "b", "c", "d", "e"]}
    label, kind = progress.status("ethics", "e1", 21)
    assert "76%" in label          # 16 of 21
    assert "16/21" in label
    assert "5 wrong left" in label
    assert kind == "todo"


def test_subject_score_sums_only_finished_exams(store):
    store["ethics/e1"] = {"finished": True, "wrong_ids": ["a"]}       # 9/10
    store["ethics/e2"] = {"finished": True, "wrong_ids": []}          # 10/10
    store["ethics/e3"] = {"in_progress": {"idx": 1, "n": 10}}         # ignored
    exams = [FakeExam("e1", 10), FakeExam("e2", 10), FakeExam("e3", 10)]
    assert progress.subject_score("ethics", exams) == (19, 20, 95)


def test_subject_score_is_none_before_anything_is_finished(store):
    store["ethics/e1"] = {"in_progress": {"idx": 0, "n": 10}}
    assert progress.subject_score("ethics", [FakeExam("e1", 10)]) is None


def test_score_never_goes_negative_if_wrong_ids_outnumber_questions(store):
    store["ethics/e1"] = {"finished": True, "wrong_ids": list("abcdefghijkl")}
    assert progress.score("ethics", "e1", 10) == (0, 10, 0)
