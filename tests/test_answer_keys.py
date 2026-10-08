"""The stored answer must not contradict the question's own explanation.

Corporate Practice 3 #1 shipped keyed "A" while its explanation ended
"...which occurs with a capital structure of 100% debt" — option C.

Read the limits of this file honestly: it would NOT have caught that one.
That explanation names no letter, and the rules that would catch it do not
survive contact with the bank. Matching an option's text verbatim inside
the explanation flags 197 questions, almost all of them sound, because a
good explanation refutes the distractors by quoting them. Scoring
explanations by distinctive words flags 68 more for the same reason. Both
were tried and discarded; a check that cries wolf 197 times teaches
everyone to skip it.

What is left is narrow but exact. Roughly 2,600 of 3,129 explanations name
their own letter outright ("B is correct"), and for those, disagreement
with the key is a fact rather than a guess. The remaining ~500 — chiefly
the Equity Valuation and Derivatives sets, whose sources mark answers with
coloured icons and print no prose — have no mechanical check at all and
were read by hand instead.
"""
import glob
import json
import os
import re

CONTENT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content")

# "B is correct", and the same claim written in Vietnamese.
NAMES_LETTER = re.compile(r"\b([ABC])\s+is correct|Đáp\s*án\s*[:\-]?\s*([ABC])")


def _questions():
    for path in sorted(glob.glob(os.path.join(CONTENT, "*", "*.json"))):
        if path.endswith("_subject.json"):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for i, q in enumerate(data.get("questions", [])):
            yield os.path.relpath(path, CONTENT), i, q


def test_no_explanation_names_a_letter_other_than_the_stored_answer():
    bad = []
    for rel, i, q in _questions():
        m = NAMES_LETTER.search(q.get("explanation") or "")
        if not m:
            continue
        claimed = m.group(1) or m.group(2)
        if claimed != q.get("answer"):
            num = q.get("num", i)
            bad.append(f"{rel} #{num}: key={q.get('answer')} "
                       f"but explanation says {claimed}")
    assert not bad, "explanation contradicts the answer key:\n" + "\n".join(bad)


def test_every_answer_points_at_an_option_that_exists():
    bad = [f"{rel} #{q.get('num', i)}: answer={q.get('answer')!r} "
           f"not in {sorted((q.get('options') or {}))}"
           for rel, i, q in _questions()
           if q.get("answer") not in (q.get("options") or {})]
    assert not bad, "answer key points nowhere:\n" + "\n".join(bad)
