"""A question must carry the data its own answer is computed from.

Equity Q48 shipped as the bare line "Q. The best estimate of the company's
dividend growth rate is:" — no price, no P/E, no rates. The vendor's question
PDF omits the table too, so nothing was lost in extraction; the question
simply arrived unanswerable. It was rebuilt from the explanation, which names
every input, and the rebuild was confirmed by the fact that those inputs
regenerate all three printed options, both distractors included.

The check is deliberately narrow. It only looks at questions that point at
something ("the company's ...") while containing no figure at all, and only
complains when the explanation then works with several figures the reader was
never given. That combination is not a style quibble — it means the question
cannot be answered.
"""
import glob
import json
import os
import re

CONTENT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content")

REFERS = re.compile(
    r"\bthe (company|portfolio|bond|fund|firm|stock|investor|security|issuer)'?s?\b",
    re.I)
NUMBER = re.compile(r"\d+(?:\.\d+)?")

# Below this many unexplained figures, the explanation is probably just
# restating a formula rather than relying on data the stem withheld.
MIN_MISSING = 4


def test_no_question_hides_its_data_in_the_explanation():
    bad = []
    for path in sorted(glob.glob(os.path.join(CONTENT, "*", "*.json"))):
        if path.endswith("_subject.json"):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for i, q in enumerate(data.get("questions", [])):
            stem = q.get("question") or ""
            if not REFERS.search(stem) or NUMBER.search(stem):
                continue
            in_answer = set(NUMBER.findall(
                " ".join((q.get("options") or {}).values())))
            missing = set(NUMBER.findall(q.get("explanation") or "")) - in_answer
            if len(missing) >= MIN_MISSING:
                rel = os.path.relpath(path, CONTENT)
                bad.append(f"{rel} #{q.get('num', i)}: stem has no figures, "
                           f"explanation uses {len(missing)}")
    assert not bad, "question missing the data it is answered from:\n" + "\n".join(bad)
