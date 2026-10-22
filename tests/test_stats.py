"""Error log: the ranking has to answer "where do I gain most", not "what looks worst"."""
import os
import sys

import pytest

os.environ.setdefault("CFA_DISABLE_LOCALSTORAGE", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import drill, stats  # noqa: E402
from core.content import Exam, Library, Subject  # noqa: E402


def _subject(sid, exams):
    return Subject(sid, sid.title(), "", 1, "", "", exams=exams)


def _exam(sid, eid, n):
    return Exam(subject_id=sid, exam_id=eid, name=f"{sid} {eid}", group="g",
                questions=[{"id": f"Q{i}"} for i in range(n)], path="x")


@pytest.fixture
def library():
    return Library(subjects=[
        _subject("ethics", [_exam("ethics", "e1", 100)]),
        _subject("derivatives", [_exam("derivatives", "d1", 100)]),
    ], errors=[])


def test_ranked_by_marks_at_risk_not_by_error_rate(library):
    """Derivatives looks worse; Ethics costs more."""
    prog = {
        "ethics/e1": {"finished": True, "wrong_ids": [f"Q{i}" for i in range(25)]},
        "derivatives/d1": {"finished": True,
                           "wrong_ids": [f"Q{i}" for i in range(40)]},
    }
    rows = stats.by_subject(library, prog)
    assert rows[0]["subject_id"] == "ethics"        # 25% x 17.5 = 4.4
    assert rows[1]["subject_id"] == "derivatives"   # 40% x 6.5  = 2.6
    assert rows[1]["rate"] > rows[0]["rate"]        # and yet it looks worse


def test_drill_misses_land_on_their_own_subject(library):
    """A derivatives question missed inside a mixed drill is a derivatives miss."""
    prog = {drill._STATE_KEY: {"history": [
        {"served": {"ethics": 3, "derivatives": 1},
         "missed": {"derivatives": 1}}]}}
    rows = {r["subject_id"]: r for r in stats.by_subject(library, prog)}
    assert rows["derivatives"]["answered"] == 1
    assert rows["derivatives"]["wrong"] == 1
    assert rows["ethics"]["wrong"] == 0
    assert "drill" not in rows


def test_exam_and_drill_counts_add_up(library):
    prog = {
        "ethics/e1": {"finished": True, "wrong_ids": ["Q1", "Q2"]},
        drill._STATE_KEY: {"history": [
            {"served": {"ethics": 5}, "missed": {"ethics": 3}}]},
    }
    row = stats.by_subject(library, prog)[0]
    assert row["answered"] == 105 and row["wrong"] == 5


def test_unfinished_work_is_not_counted(library):
    prog = {"ethics/e1": {"in_progress": {"idx": 4, "n": 100}}}
    assert stats.by_subject(library, prog) == []


def test_an_exam_no_longer_in_the_library_is_skipped(library):
    """Withdrawn or hidden content must not inflate the denominator."""
    prog = {"gone/x1": {"finished": True, "wrong_ids": ["Q1"]}}
    assert stats.by_subject(library, prog) == []


def test_ethics_is_held_to_a_higher_bar(library):
    prog = {
        "ethics/e1": {"finished": True, "wrong_ids": [f"Q{i}" for i in range(25)]},
        "derivatives/d1": {"finished": True,
                           "wrong_ids": [f"Q{i}" for i in range(25)]},
    }
    weak = stats.weak_exams(library, prog)
    # Both scored 75%: that clears 70% but fails Ethics' 80%.
    assert [w["subject_id"] for w in weak] == ["ethics"]


def test_totals_match_the_rows(library):
    prog = {"ethics/e1": {"finished": True, "wrong_ids": ["Q1", "Q2", "Q3"]}}
    rows = stats.by_subject(library, prog)
    assert stats.totals(rows) == (100, 3, 0.03)


# --- the drill's own score ------------------------------------------------ #

def test_drill_score_pools_questions_rather_than_averaging_drills():
    """A short end-of-round drill must not weigh as much as a full one."""
    prog = {drill._STATE_KEY: {"history": [
        {"correct": 16, "n": 20}, {"correct": 14, "n": 20},
        {"correct": 5, "n": 7}]}}
    correct, answered, rate = stats.drill_summary(prog)
    assert (correct, answered) == (35, 47)
    assert round(rate, 3) == 0.745             # pooled
    mean_of_percentages = (16 / 20 + 14 / 20 + 5 / 7) / 3
    assert round(mean_of_percentages, 3) == 0.738    # what it is not


def test_drill_score_is_zero_safe_before_any_drill():
    assert stats.drill_summary({}) == (0, 0, 0.0)
