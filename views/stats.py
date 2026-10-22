"""Error log — a standing answer to "where am I losing marks?"."""
import streamlit as st

from core import content, stats
from core.ui import go

_NAMES = {}


def _label(library, subject_id):
    if not _NAMES:
        for s in library.subjects:
            _NAMES[s.subject_id] = s.name
    return _NAMES.get(subject_id, subject_id)


def render(library):
    if st.button("Back"):
        go("home")

    st.markdown("# Error log")
    prog = st.session_state.get("progress", {})
    rows = stats.by_subject(library, prog)

    # Drills recorded before the per-subject counts existed contribute no rows,
    # so bail only when there is genuinely nothing — otherwise their score is
    # still worth showing further down.
    if not rows and not stats.drill_count(prog):
        st.info("Nothing to report yet — finish an exam or a drill first.")
        return

    if not rows:
        st.caption("No per-subject breakdown yet — the drills on record "
                   "predate it. The next one will appear here.")
    answered, wrong, rate = stats.totals(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("Answered", answered)
    c2.metric("Wrong", wrong)
    c3.metric("Error rate", f"{rate * 100:.0f}%")

    if rows:
        st.markdown("### Where the marks are going")
        st.caption("Ranked by error rate × exam weight — the top row is "
                   "where study pays most, which is not always the worst "
                   "percentage.")
        st.dataframe(
            [{"Subject": _label(library, r["subject_id"]),
              "Answered": r["answered"],
              "Wrong": r["wrong"],
              "Error rate": f"{r['rate'] * 100:.0f}%",
              "Exam weight": f"{r['weight']:.1f}%",
              "Marks at risk": f"{r['risk']:.1f}%"} for r in rows],
            hide_index=True, width="stretch")

    weak = stats.weak_exams(library, prog)
    st.markdown("### Below checkpoint")
    if not weak:
        st.success("Every finished exam cleared its bar "
                   "(70%, Ethics 80%).")
    else:
        st.caption(f"{len(weak)} exam(s) under the bar. These are the "
                   "retakes with the most to give.")
        for w in weak:
            st.write(f"**{w['pct'] * 100:.0f}%** · {w['name']} "
                     f"— {_label(library, w['subject_id'])} "
                     f"({w['wrong']} wrong of {w['n']}, bar "
                     f"{w['bar'] * 100:.0f}%)")

    trend = stats.drill_trend(prog)
    if trend:
        st.markdown("### Mixed drills")
        correct, answered, rate = stats.drill_summary(prog)
        st.write(f"**{correct}/{answered} = {rate * 100:.0f}%** "
                 f"across {stats.drill_count(prog)} drill(s)")
        st.caption("Pooled over every question, not averaged per drill — the "
                   "last drill of a round is short, and would otherwise count "
                   "as much as a full one.")
        line = " · ".join(f"{d['correct']}/{d['n']}" for d in trend)
        st.write(f"Recent: {line}")
        paced = [d for d in trend if d.get("elapsed_s") and d.get("duration_s")]
        if paced:
            last = paced[-1]
            over = last["elapsed_s"] - last["duration_s"]
            if abs(over) < 60:
                st.caption("Last drill finished on the 1.5 min/question pace.")
            else:
                st.caption(
                    f"Last drill ran {abs(over) / 60:.0f} min "
                    f"{'over' if over > 0 else 'under'} the "
                    f"1.5 min/question pace."
                )
