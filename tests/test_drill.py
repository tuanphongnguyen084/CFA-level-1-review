"""The mixed drill: weighted sampling, and no repeats until the bank is spent.

The rule that matters is the second one. A drill that can serve the same
question twice while hundreds sit untouched is worse than useless for
coverage, so most of this file is about the seen-set surviving across drills
and resetting only when there is genuinely nothing left.
"""
import os
import random
import sys

import pytest

os.environ.setdefault("CFA_DISABLE_LOCALSTORAGE", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from core import drill  # noqa: E402
from core.content import Exam, Library, Subject  # noqa: E402


def _subject(sid, n):
    qs = [{"id": f"Q{i}", "question": f"{sid} {i}",
           "options": {"A": "a", "B": "b", "C": "c"}, "answer": "A"}
          for i in range(n)]
    return Subject(sid, sid.title(), "", 1, "", "",
                   exams=[Exam(subject_id=sid, exam_id="e1", name="E1",
                               group="g", questions=qs, path="x")])


@pytest.fixture
def library():
    # Every weighted subject present, with room to spare.
    return Library(subjects=[_subject(s, 40) for s in drill.EXAM_WEIGHT],
                   errors=[])


@pytest.fixture
def session(monkeypatch):
    state = {"progress": {}}
    monkeypatch.setattr(st, "session_state", state, raising=False)
    return state


# --- apportionment ------------------------------------------------------- #

def test_slots_follow_exam_weight_not_bank_size(session, library):
    take = drill.apportion(20, {s: 500 for s in drill.EXAM_WEIGHT})
    assert sum(take.values()) == 20
    # Ethics is the heaviest topic, derivatives the lightest.
    assert take["ethics"] > take["derivatives"]


def test_a_subject_is_never_asked_for_more_than_it_has(session, library):
    avail = {s: 1 for s in drill.EXAM_WEIGHT}
    take = drill.apportion(20, avail)
    assert all(take[s] <= 1 for s in take)
    assert sum(take.values()) == 10          # ten subjects, one each


def test_slots_spill_to_subjects_with_room(session, library):
    avail = dict.fromkeys(drill.EXAM_WEIGHT, 50)
    avail["ethics"] = 1                       # the heaviest is nearly empty
    take = drill.apportion(20, avail)
    assert take["ethics"] == 1
    assert sum(take.values()) == 20           # the rest absorb the shortfall


# --- the no-repeat rule --------------------------------------------------- #

def test_a_drill_draws_the_requested_number(session, library):
    picked, reset = drill.build(library, 20, rng=random.Random(1))
    assert len(picked) == 20 and reset is False
    assert len({p[0] for p in picked}) == 20


def test_questions_served_once_do_not_come_back(session, library):
    first, _ = drill.build(library, 20, rng=random.Random(1))
    drill.record(drill.as_exam(first), {"total": 20, "correct": 15})
    second, _ = drill.build(library, 20, rng=random.Random(2))
    assert not ({p[0] for p in first} & {p[0] for p in second})


def test_an_abandoned_drill_burns_nothing(session, library):
    first, _ = drill.build(library, 20, rng=random.Random(1))
    # No record() — the drill was never submitted.
    second, _ = drill.build(library, 20, rng=random.Random(1))
    assert {p[0] for p in first} == {p[0] for p in second}


def test_the_whole_bank_is_covered_before_anything_repeats(session, library):
    total = len(drill.pool(library))
    served = []
    for _ in range(200):                      # generous upper bound
        picked, reset = drill.build(library, 20, rng=random.Random(len(served)))
        if reset:
            break
        drill.record(drill.as_exam(picked), {"total": len(picked)})
        served += [p[0] for p in picked]
    assert len(served) == total               # nothing served twice, none skipped
    assert len(set(served)) == total


def test_the_last_drill_of_a_round_is_short_not_empty(session, library):
    everything = [k for k, _q, _s in drill.pool(library)]
    drill._state()["seen"] = everything[:-7]  # seven left
    picked, reset = drill.build(library, 20, rng=random.Random(3))
    assert reset is False and len(picked) == 7


def test_an_exhausted_bank_starts_a_new_round(session, library):
    drill._state()["seen"] = [k for k, _q, _s in drill.pool(library)]
    picked, reset = drill.build(library, 20, rng=random.Random(4))
    assert reset is True and len(picked) == 20
    assert drill._state()["cycle"] == 2


# --- the synthetic exam --------------------------------------------------- #

def test_ids_stay_unique_across_source_exams(session, library):
    picked, _ = drill.build(library, 20, rng=random.Random(5))
    exam = drill.as_exam(picked)
    ids = [q["id"] for q in exam.questions]
    assert len(set(ids)) == len(ids) == 20
    # Raw ids collide ("Q3" exists in every subject); the full path does not.
    assert all(i.count("/") == 2 for i in ids)


def test_the_clock_matches_the_real_exam_pace(session, library):
    picked, _ = drill.build(library, 20, rng=random.Random(6))
    assert drill.as_exam(picked).timed_minutes == 30      # 20 x 1.5


def test_history_records_each_submitted_drill(session, library):
    picked, _ = drill.build(library, 20, rng=random.Random(7))
    drill.record(drill.as_exam(picked), {"total": 20, "correct": 14})
    assert drill.history()[-1]["correct"] == 14
