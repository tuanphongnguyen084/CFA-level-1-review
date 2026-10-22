"""Error log: where the marks are actually going.

Everything here is derived from what progress already stores — per-exam
``wrong_ids`` plus the drill history — so nothing new has to be tracked and
old attempts count retroactively.

One limit worth stating plainly, because it shapes what this can show: the
questions carry no topic tags. Only the Equity Valuation set ends its
explanations with "(Module 48.2, LOS 48.h)", 140 of 3,132 questions, so a
breakdown finer than subject is not available for 96% of the bank. Subject
is therefore as deep as this goes, and pretending otherwise would mean
inventing tags.

The ordering is the point. A 40% error rate in Derivatives costs less than
25% in Ethics, because Ethics is worth nearly three times as much of the
paper. Rows are ranked by *marks at risk* — error rate times exam weight —
so the top of the table is where studying pays most, not merely where the
percentage looks worst.
"""
from core import drill


def _entries(library, prog):
    """(exam, entry) for every finished exam still present in the library."""
    for key, e in prog.items():
        if not isinstance(e, dict) or not e.get("finished"):
            continue
        subject_id, _, exam_id = key.partition("/")
        exam = library.exam(subject_id, exam_id)
        if exam is not None:
            yield exam, e


def by_subject(library, prog):
    """Per-subject answered/wrong/rate/risk, worst marks-at-risk first.

    Drills are folded in by source subject, not lumped under "drill": a
    Derivatives question missed inside a mixed drill is a Derivatives miss.
    """
    answered = {}
    wrong = {}

    for exam, e in _entries(library, prog):
        if exam.subject_id == drill.DRILL_SUBJECT:
            continue            # counted from drill history instead
        answered[exam.subject_id] = answered.get(exam.subject_id, 0) + exam.n
        wrong[exam.subject_id] = (wrong.get(exam.subject_id, 0)
                                  + len(e.get("wrong_ids", [])))

    for h in (prog.get(drill._STATE_KEY) or {}).get("history", []):
        for sid, n in (h.get("served") or {}).items():
            answered[sid] = answered.get(sid, 0) + n
        for sid, n in (h.get("missed") or {}).items():
            wrong[sid] = wrong.get(sid, 0) + n

    rows = []
    for sid, n in answered.items():
        if not n:
            continue
        w = wrong.get(sid, 0)
        rate = w / n
        weight = drill.EXAM_WEIGHT.get(sid, 0.0)
        rows.append({
            "subject_id": sid,
            "answered": n,
            "wrong": w,
            "rate": rate,
            "weight": weight,
            "risk": rate * weight,     # share of the paper being lost here
        })
    rows.sort(key=lambda r: (-r["risk"], -r["rate"]))
    return rows


def weak_exams(library, prog, floor=0.70, ethics_floor=0.80):
    """Finished exams that came in under their checkpoint, worst first."""
    out = []
    for exam, e in _entries(library, prog):
        if exam.subject_id == drill.DRILL_SUBJECT or not exam.n:
            continue
        pct = (exam.n - len(e.get("wrong_ids", []))) / exam.n
        bar = ethics_floor if exam.subject_id == "ethics" else floor
        if pct < bar:
            out.append({"subject_id": exam.subject_id, "name": exam.name,
                        "pct": pct, "bar": bar, "n": exam.n,
                        "wrong": len(e.get("wrong_ids", []))})
    out.sort(key=lambda r: r["pct"])
    return out


def drill_summary(prog):
    """(correct, answered, rate) pooled across every submitted drill.

    Pooled rather than the mean of each drill's percentage, because the last
    drill of a round is short by design — whatever is left of the bank — and
    averaging percentages would let a seven-question drill weigh as heavily
    as a twenty-question one. Here every question counts the same, which is
    what "how often am I right" actually means.
    """
    hist = (prog.get(drill._STATE_KEY) or {}).get("history", [])
    correct = sum(h.get("correct", 0) for h in hist)
    answered = sum(h.get("n", 0) for h in hist)
    return correct, answered, (correct / answered if answered else 0.0)


def drill_count(prog):
    return len((prog.get(drill._STATE_KEY) or {}).get("history", []))


def drill_trend(prog, last=8):
    """Recent drill scores, oldest first, for a sense of direction."""
    hist = (prog.get(drill._STATE_KEY) or {}).get("history", [])
    return [{"correct": h.get("correct", 0), "n": h.get("n", 0),
             "elapsed_s": h.get("elapsed_s"),
             "duration_s": h.get("duration_s")}
            for h in hist[-last:]]


def totals(rows):
    answered = sum(r["answered"] for r in rows)
    wrong = sum(r["wrong"] for r in rows)
    return answered, wrong, (wrong / answered if answered else 0.0)
