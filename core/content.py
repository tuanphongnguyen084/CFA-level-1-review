"""
Content discovery & loading.

Every folder under content/ is a SUBJECT (its display metadata lives in
``_subject.json``). Every other ``*.json`` file in that folder is one EXAM.
Adding an exam therefore means dropping a JSON file in the right folder — no
code change needed. Malformed files are skipped and reported (see
``Library.errors``) instead of crashing the app.
"""
import json
import os
import re
from dataclasses import dataclass, field, replace

import streamlit as st

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(REPO_ROOT, "content")


# Anyone may browse the 1000-question bank and the mock exams; everything
# else (review tests, practice sets, reading drills) is for signed-in buyers
# only. A file can opt out either way with a "private": true/false field.
PUBLIC_EXAM_PREFIXES = ("1000-",)
PUBLIC_SUBJECTS = frozenset({"mock"})


def is_private_exam(subject_id, exam_id, data=None):
    """Whether an exam is buyers-only. Pure, so it is directly testable."""
    if data and "private" in data:
        return bool(data["private"])
    if subject_id in PUBLIC_SUBJECTS:
        return False
    return not exam_id.startswith(PUBLIC_EXAM_PREFIXES)


@dataclass
class Exam:
    subject_id: str
    exam_id: str          # filename stem — unique within a subject
    name: str
    group: str
    questions: list
    path: str
    timed_minutes: int | None = None   # set => exam-mode; None => practice-quiz mode
    private: bool = False              # hidden from visitors who aren't buyers

    @property
    def n(self):
        return len(self.questions)


@dataclass
class Subject:
    subject_id: str       # folder name
    name: str
    icon: str
    order: int
    weight: str
    description: str
    exams: list = field(default_factory=list)

    @property
    def n_questions(self):
        return sum(e.n for e in self.exams)


@dataclass
class Library:
    subjects: list
    errors: list          # list of (path, message)

    def subject(self, subject_id):
        return next((s for s in self.subjects if s.subject_id == subject_id), None)

    def exam(self, subject_id, exam_id):
        s = self.subject(subject_id)
        if not s:
            return None
        return next((e for e in s.exams if e.exam_id == exam_id), None)


def _natural_key(text):
    """Sort so 'Reading 9' comes before 'Reading 10'."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", str(text))]


def _valid_question(q):
    if not isinstance(q, dict):
        return False
    if not q.get("question") or "answer" not in q:
        return False
    opts = q.get("options")
    if not isinstance(opts, dict) or len(opts) < 2:
        return False
    return q["answer"] in opts


def _load_subject(subject_id, sdir, errors):
    meta = {}
    mpath = os.path.join(sdir, "_subject.json")
    if os.path.exists(mpath):
        try:
            with open(mpath, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:  # noqa: BLE001
            errors.append((mpath, f"_subject.json could not be read: {e}"))

    subject = Subject(
        subject_id=subject_id,
        name=meta.get("name", subject_id.replace("-", " ").title()),
        icon=meta.get("icon", "📘"),
        order=int(meta.get("order", 999)),
        weight=meta.get("weight", ""),
        description=meta.get("description", ""),
    )

    for fn in sorted(os.listdir(sdir)):
        if not fn.endswith(".json") or fn == "_subject.json":
            continue
        fpath = os.path.join(sdir, fn)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:  # noqa: BLE001
            errors.append((fpath, f"JSON error: {e}"))
            continue

        exam_id = os.path.splitext(fn)[0]
        questions = data.get("questions", [])
        if not isinstance(questions, list) or not questions:
            errors.append((fpath, "no questions found"))
            continue

        good = []
        for i, q in enumerate(questions):
            if _valid_question(q):
                q.setdefault("id", f"{exam_id}-{i + 1}")
                good.append(q)
        bad = len(questions) - len(good)
        if bad:
            errors.append((fpath, f"{bad} invalid question(s) (skipped)"))
        if not good:
            continue

        subject.exams.append(Exam(
            subject_id=subject_id,
            exam_id=exam_id,
            name=data.get("name", exam_id),
            group=data.get("group", ""),
            questions=good,
            path=fpath,
            timed_minutes=data.get("timed_minutes"),
            private=is_private_exam(subject_id, exam_id, data),
        ))

    subject.exams.sort(key=lambda e: (e.group, _natural_key(e.name)))
    return subject


@st.cache_data(show_spinner=False)
def load_library():
    """Scan content/ and return the full Library (cached per process)."""
    errors = []
    subjects = []
    if not os.path.isdir(CONTENT_DIR):
        return Library(subjects=[], errors=[(CONTENT_DIR, "Missing content/ folder")])

    for subject_id in sorted(os.listdir(CONTENT_DIR)):
        sdir = os.path.join(CONTENT_DIR, subject_id)
        if not os.path.isdir(sdir) or subject_id.startswith("."):
            continue
        subjects.append(_load_subject(subject_id, sdir, errors))

    subjects.sort(key=lambda s: (s.order, s.name))
    return Library(subjects=subjects, errors=errors)


def visible_library(library, privileged):
    """The library as a given viewer may see it.

    Buyers-only exams are removed for everyone else, and every view reaches
    content through ``library.exam()``, so filtering here also makes a hidden
    exam unreachable by a stale session or a hand-crafted state — not merely
    absent from the listings.

    Removed rather than shown-but-locked: an ordinary viewer should have no
    way to tell a higher tier exists. That is also why the loader's error
    list is dropped here — it names files, and a complaint about
    ``ethics-review-test-1.json`` would advertise exactly what it hides.
    """
    if privileged:
        return library
    subjects = []
    for s in library.subjects:
        visible = [e for e in s.exams if not e.private]
        if not visible:
            continue          # nothing left worth showing this topic for
        subjects.append(replace(s, exams=visible))
    return Library(subjects=subjects, errors=[])
