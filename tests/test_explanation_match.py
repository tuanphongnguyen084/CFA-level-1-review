"""An explanation must belong to the question it sits under.

FSA Q96 asked which debt ranks highest in priority of payment and was
answered with a paragraph about G-spreads and I-spreads — and keyed from it,
so the stored answer was "Subordinated debt", the lowest-ranking of the three
options rather than the highest. The source's solutions are numbered one
behind its questions in that stretch, because question 95 is missing from the
question PDF, and the extraction followed the numbers.

Catching this needs more than "the explanation shares no words with the stem":
Ethics vignettes legitimately look like that, answering a story about a named
analyst by citing a Standard, and a worked calculation shares little prose
with anything. The signal that is actually specific is *displacement* — an
explanation that matches some other question in the same file far better than
its own. Q96's stray paragraph shared nothing with its own stem and 69% with
the I-spread question three slots up.

Thresholds are set where the whole bank is clean: nothing currently trips
this, and restoring Q96's old explanation trips it immediately.
"""
import glob
import json
import os
import re

CONTENT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content")

# Filler that appears everywhere and so carries no topic signal.
STOP = set("""the a an of to in for on at by with and or is are was were be been
being as that this these those it its from than then if not no such which who
whom whose will would can could may might must shall should do does did have
has had more most less least same other others only also both each any all when
while because about into over under between during per within without correct
incorrect""".split())

MIN_LENGTH = 150      # too short to judge
OWN_MAX = 0.05        # shares essentially nothing with its own question
OTHER_MIN = 0.35      # yet plainly belongs to a different one


def _words(text):
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower())
            if w not in STOP}


def _overlap(stem, expl):
    return len(stem & expl) / len(stem) if stem else 0.0


def test_no_explanation_belongs_to_a_different_question():
    bad = []
    for path in sorted(glob.glob(os.path.join(CONTENT, "*", "*.json"))):
        if path.endswith("_subject.json"):
            continue
        with open(path, encoding="utf-8") as fh:
            questions = json.load(fh).get("questions", [])

        stems = [_words(q.get("question", "")) |
                 set().union(*[_words(v)
                               for v in (q.get("options") or {}).values()]
                             or [set()])
                 for q in questions]

        for i, q in enumerate(questions):
            expl = q.get("explanation") or ""
            if len(expl) < MIN_LENGTH:
                continue
            words = _words(expl)
            if _overlap(stems[i], words) >= OWN_MAX:
                continue
            others = [(_overlap(s, words), j)
                      for j, s in enumerate(stems) if j != i]
            if not others:
                continue
            best, j = max(others)
            if best >= OTHER_MIN:
                rel = os.path.relpath(path, CONTENT)
                bad.append(
                    f"{rel} #{q.get('num', i)}: explanation matches "
                    f"#{questions[j].get('num', j)} ({best:.0%}) far better "
                    f"than its own question")
    assert not bad, "explanation attached to the wrong question:\n" + "\n".join(bad)
