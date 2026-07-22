"""Tests for core/exam.py — the timed exam-mode engine.

Two tiers:
- test_grade_*/test_remaining_* exercise the pure helpers (_grade,
  _remaining) directly with plain pytest, no Streamlit involved.
- Everything else goes through Streamlit's AppTest, because start()/
  resume()/finish() touch st.session_state and call st.rerun(), which
  need an active script-run context to work at all. Each script calls
  progress.init() first (as streamlit_app.py always does) and
  monkeypatches core.content.CONTENT_DIR to a tmp_path fixture subject,
  so no real content/ file is ever touched. CFA_DISABLE_LOCALSTORAGE=1
  (see core/progress.py) skips the browser localStorage round-trip,
  which has no frontend to answer it here.

IMPORTANT: start()/resume()/finish() all call st.rerun(), which makes
AppTest re-execute the whole script from the top. Every script below
therefore guards its one-time setup behind a session_state flag checked
*before* calling the rerun-triggering function — otherwise the script
would call it again on the rerun, rerun again, and loop forever.
"""
import json
import os
import sys

import pytest

os.environ.setdefault("CFA_DISABLE_LOCALSTORAGE", "1")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from streamlit.testing.v1 import AppTest  # noqa: E402
from core.exam import _grade, remaining  # noqa: E402

# Deliberately out of source order, to prove start() sorts by "num" rather
# than trusting file order (and does NOT shuffle, unlike core/quiz.py).
FIXTURE_QUESTIONS = [
    {"id": f"Q{i}", "num": i, "question": f"Question {i}?",
     "options": {"A": "wrong a", "B": "correct b", "C": "wrong c"},
     "answer": "B", "explanation": f"exp {i}"}
    for i in (3, 1, 2)
]


# --------------------------------------------------------------------- #
# Tier 1: pure logic, no Streamlit                                      #
# --------------------------------------------------------------------- #
def test_grade_all_correct():
    by_id = {q["id"]: q for q in FIXTURE_QUESTIONS}
    answers = {"Q1": "B", "Q2": "B", "Q3": "B"}
    assert _grade(["Q1", "Q2", "Q3"], answers, by_id) == []


def test_grade_some_wrong_and_unanswered():
    by_id = {q["id"]: q for q in FIXTURE_QUESTIONS}
    answers = {"Q1": "B", "Q2": "A"}  # Q2 wrong, Q3 unanswered
    assert _grade(["Q1", "Q2", "Q3"], answers, by_id) == ["Q2", "Q3"]


def test_remaining_counts_down():
    assert remaining(start_ts=1000.0, duration_s=120, now=1030.0) == 90.0


def test_remaining_never_negative():
    assert remaining(start_ts=1000.0, duration_s=120, now=5000.0) == 0.0


# --------------------------------------------------------------------- #
# Tier 2: AppTest integration                                           #
# --------------------------------------------------------------------- #
@pytest.fixture
def fixture_content_dir(tmp_path, monkeypatch):
    mockdir = tmp_path / "mock"
    mockdir.mkdir()
    (mockdir / "_subject.json").write_text(json.dumps(
        {"name": "Mock Exams", "icon": "🎯", "order": 11}))
    (mockdir / "fixture-exam.json").write_text(json.dumps({
        "schema_version": 1, "name": "Fixture", "group": "Fixture",
        "timed_minutes": 2, "questions": FIXTURE_QUESTIONS,
    }))
    monkeypatch.setenv("_FIXTURE_CONTENT_DIR", str(tmp_path))
    return str(tmp_path)


def _run(script_fn):
    at = AppTest.from_function(script_fn)
    at.run(timeout=30)
    assert len(at.exception) == 0, [str(e) for e in at.exception]
    return at


def test_start_sorts_by_num_not_shuffled(fixture_content_dir):
    def script():
        import os
        import streamlit as st
        from core import content, exam, progress
        content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
        content.load_library.clear()
        progress.init()
        lib = content.load_library()
        if not st.session_state.get("_done"):
            st.session_state["_done"] = True
            exam.start(lib, "mock", "fixture-exam")

    at = _run(script)
    ex = at.session_state["exam"]
    assert ex["order"] == ["Q1", "Q2", "Q3"]
    assert ex["idx"] == 0
    assert ex["answers"] == {}
    assert ex["flagged"] == []
    assert ex["duration_s"] == 120
    # persisted immediately, so a refresh a second later can't lose start_ts
    entry = at.session_state["progress"]["mock/fixture-exam"]
    assert entry["exam_session"]["start_ts"] == ex["start_ts"]
    assert entry["exam_session"]["order"] == ["Q1", "Q2", "Q3"]


def test_set_answer_and_flag_persist(fixture_content_dir):
    def script():
        import os
        import streamlit as st
        from core import content, exam, progress
        content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
        content.load_library.clear()
        progress.init()
        lib = content.load_library()
        if not st.session_state.get("_done"):
            st.session_state["_done"] = True
            exam.start(lib, "mock", "fixture-exam")
        elif st.session_state.get("exam"):
            # second run (post-rerun from start()): mutate now that the
            # exam session actually exists, no further rerun triggered.
            exam.set_answer("Q1", "B")
            exam.toggle_flag("Q2")

    at = _run(script)
    ex = at.session_state["exam"]
    assert ex["answers"] == {"Q1": "B"}
    assert ex["flagged"] == ["Q2"]
    persisted = at.session_state["progress"]["mock/fixture-exam"]["exam_session"]
    assert persisted["answers"] == {"Q1": "B"}
    assert persisted["flagged"] == ["Q2"]


def test_toggle_flag_twice_unflags(fixture_content_dir):
    def script():
        import os
        import streamlit as st
        from core import content, exam, progress
        content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
        content.load_library.clear()
        progress.init()
        lib = content.load_library()
        if not st.session_state.get("_done"):
            st.session_state["_done"] = True
            exam.start(lib, "mock", "fixture-exam")
        elif st.session_state.get("exam"):
            exam.toggle_flag("Q1")
            exam.toggle_flag("Q1")

    at = _run(script)
    assert at.session_state["exam"]["flagged"] == []


def test_resume_preserves_start_ts_and_state(fixture_content_dir):
    seeded_start_ts = 1_700_000_000.0

    def script():
        import os
        import streamlit as st
        from core import content, exam, progress
        content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
        content.load_library.clear()
        progress.init()
        lib = content.load_library()
        if not st.session_state.get("_done"):
            st.session_state["_done"] = True
            # Seed a plausible "saved yesterday, mid-session" snapshot
            # directly, rather than chaining two separate AppTest runs
            # (there's no real localStorage here to carry state between
            # them anyway).
            e = progress.get_or_create("mock", "fixture-exam")
            e["exam_session"] = {
                "start_ts": 1_700_000_000.0,
                "duration_s": 120,
                "order": ["Q1", "Q2", "Q3"],
                "answers": {"Q1": "B"},
                "flagged": ["Q3"],
                "idx": 1,
            }
            exam.resume(lib, "mock", "fixture-exam")

    at = _run(script)
    ex = at.session_state["exam"]
    assert ex["start_ts"] == seeded_start_ts  # never recomputed
    assert ex["idx"] == 1
    assert ex["answers"] == {"Q1": "B"}
    assert ex["flagged"] == ["Q3"]
    assert ex["order"] == ["Q1", "Q2", "Q3"]


def test_resume_without_snapshot_falls_back_to_fresh_start(fixture_content_dir):
    def script():
        import os
        import streamlit as st
        from core import content, exam, progress
        content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
        content.load_library.clear()
        progress.init()
        lib = content.load_library()
        if not st.session_state.get("_done"):
            st.session_state["_done"] = True
            # No exam_session seeded at all (e.g. never started, or
            # progress saved before this field existed) — must not crash.
            exam.resume(lib, "mock", "fixture-exam")

    at = _run(script)
    ex = at.session_state["exam"]
    assert ex["idx"] == 0
    assert ex["answers"] == {}
    assert ex["order"] == ["Q1", "Q2", "Q3"]


def test_finish_grades_and_persists_result(fixture_content_dir):
    def script():
        import os
        import streamlit as st
        from core import content, exam, progress
        content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
        content.load_library.clear()
        progress.init()
        lib = content.load_library()
        if not st.session_state.get("_started"):
            st.session_state["_started"] = True
            exam.start(lib, "mock", "fixture-exam")
        elif not st.session_state.get("_finished") and st.session_state.get("exam"):
            st.session_state["_finished"] = True
            st.session_state["exam"]["answers"] = {"Q1": "B", "Q2": "A", "Q3": "B"}
            exam.finish(lib, auto=False)

    at = _run(script)
    entry = at.session_state["progress"]["mock/fixture-exam"]
    assert "exam_session" not in entry
    assert entry["finished"] is True
    r = entry["exam_result"]
    assert r["total"] == 3
    assert r["correct"] == 2
    assert r["wrong_ids"] == ["Q2"]
    assert r["auto_submitted"] is False
    assert entry["wrong_ids"] == ["Q2"]  # mirrored for quiz.start(mode="wrong")


def test_finish_auto_submitted_flag(fixture_content_dir):
    def script():
        import os
        import streamlit as st
        from core import content, exam, progress
        content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
        content.load_library.clear()
        progress.init()
        lib = content.load_library()
        if not st.session_state.get("_started"):
            st.session_state["_started"] = True
            exam.start(lib, "mock", "fixture-exam")
        elif not st.session_state.get("_finished") and st.session_state.get("exam"):
            st.session_state["_finished"] = True
            exam.finish(lib, auto=True)  # simulates the timer-expiry path

    at = _run(script)
    r = at.session_state["progress"]["mock/fixture-exam"]["exam_result"]
    assert r["auto_submitted"] is True
    assert r["wrong_ids"] == ["Q1", "Q2", "Q3"]  # nothing was answered


def test_is_expired_reflects_wall_clock(fixture_content_dir):
    def script():
        import os
        import streamlit as st
        from core import content, exam, progress
        content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
        content.load_library.clear()
        progress.init()
        lib = content.load_library()
        if not st.session_state.get("_done"):
            st.session_state["_done"] = True
            e = progress.get_or_create("mock", "fixture-exam")
            e["exam_session"] = {
                "start_ts": 1.0,  # epoch second 1 — expired long ago
                "duration_s": 120,
                "order": ["Q1", "Q2", "Q3"],
                "answers": {}, "flagged": [], "idx": 0,
            }
            exam.resume(lib, "mock", "fixture-exam")
        elif st.session_state.get("exam"):
            st.session_state["_expired"] = exam.is_expired()
            st.session_state["_remaining"] = exam.remaining_seconds()

    at = _run(script)
    assert at.session_state["_expired"] is True
    assert at.session_state["_remaining"] == 0.0


def test_is_expired_false_when_fresh(fixture_content_dir):
    def script():
        import os
        import streamlit as st
        from core import content, exam, progress
        content.CONTENT_DIR = os.environ["_FIXTURE_CONTENT_DIR"]
        content.load_library.clear()
        progress.init()
        lib = content.load_library()
        if not st.session_state.get("_done"):
            st.session_state["_done"] = True
            exam.start(lib, "mock", "fixture-exam")
        elif st.session_state.get("exam"):
            st.session_state["_expired"] = exam.is_expired()

    at = _run(script)
    assert at.session_state["_expired"] is False
