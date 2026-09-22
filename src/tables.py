"""The suite's reports as DataFrames, for the notebooks (D64).

Every report in this package is built twice, on purpose. The plain-text form
goes to a run's log, where it has to survive a terminal, a redirected file and
whoever reads it six months later with no Python; the frame form goes to a
notebook, where a fixed-width block of text is the worst of both worlds — it
cannot be sorted, filtered, styled or joined, and it renders as an escaped
string in the published HTML.

The text is the source of truth and the frames are built from the same
functions, so the two cannot drift into disagreeing. pandas is imported inside
each function rather than at module scope: the runner must not gain a plotting
dependency because a notebook wanted a nicer table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pandas import DataFrame


def _pd():
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - notebooks only
        raise ImportError(
            "pandas is needed for the frame views; the text reports need nothing. "
            "pip install pandas, or use the report() function instead."
        ) from exc
    return pd


def relations() -> "DataFrame":
    """Metamorphic relations against their opportunity (D61).

    The share column is what the table is for: raw counts make the suite look
    arbitrary, and use-against-eligibility is what shows the unevenness is
    mostly forced by D22's matrix rather than chosen.
    """
    from src.metamorphic import relation_coverage

    pd = _pd()
    rows = [
        {
            "relation": rel,
            "perturbation": name,
            "kind": "directional" if rel.startswith("DIR") else "invariance",
            "eligible seeds": opportunity,
            "follow-ups": used,
            "share of opportunity": round(used / opportunity, 3) if opportunity else None,
        }
        for rel, name, opportunity, used in relation_coverage()
    ]
    return pd.DataFrame(rows).set_index("relation")


def eligibility() -> "DataFrame":
    """Which function may take which relation (D22), as a tick grid.

    A grid rather than a list per function, because the question a reader
    actually has is "why does THIS relation have so few cases", and that is a
    column, not a row.
    """
    from src.metamorphic import ELIGIBLE, RELATION_NAMES

    pd = _pd()
    functions = sorted(ELIGIBLE)
    frame = pd.DataFrame(
        {
            fn: ["yes" if rel in ELIGIBLE[fn] else "-" for rel in sorted(RELATION_NAMES)]
            for fn in functions
        },
        index=sorted(RELATION_NAMES),
    )
    frame.insert(0, "perturbation", [RELATION_NAMES[r] for r in sorted(RELATION_NAMES)])
    frame.insert(len(frame.columns), "eligible seeds", relations()["eligible seeds"])
    frame.index.name = "relation"
    return frame


def tool_coverage(run_id: str) -> "DataFrame":
    """Per-tool declaration and observation for one run (D50).

    `every call errored` is the column that matters and the reason this report
    exists: a tool can be declared, called, and broken, and the suite stays
    green because every case permits it at min 0.
    """
    from src.coverage import for_run

    pd = _pd()
    cov = for_run(run_id)
    tools = sorted(set(cov.declared) | set(cov.observed))
    rows = []
    for tool in tools:
        calls = cov.observed.get(tool, 0)
        errors = cov.errored.get(tool, 0)
        rows.append(
            {
                "tool": tool,
                "cases requiring": len(cov.required.get(tool, [])),
                "cases permitting": len(cov.declared.get(tool, [])),
                "calls": calls,
                "errors": errors,
                "all errored": bool(calls and errors == calls),
                "parameters exercised": ", ".join(sorted(cov.parameters.get(tool, set()))) or "-",
            }
        )
    return pd.DataFrame(rows).set_index("tool")


def failures(run_id: str) -> "DataFrame":
    """Failed executions with the evidence that says who is to blame (D59).

    `suspect` is the flag worth reading: an execution blamed on the agent where
    no model call completed is a misclassification, not a result.
    """
    from src.failures import for_run

    pd = _pd()
    rows = []
    for f in for_run(run_id):
        last = f.turns[-1] if f.turns else None
        rows.append(
            {
                "case": f.case_id,
                "rep": f.repetition,
                "attempt": f.attempt,
                "blame": f.blame,
                "error": f.error[:60],
                "turn": last.turn_index if last else None,
                "code": last.error_code if last else None,
                "retries": last.retry_count if last else None,
                "latency ms": last.latency_ms if last else None,
                "tokens in/out": f"{last.tokens_in}/{last.tokens_out}" if last else None,
                "suspect": bool(last and f.blame == "agent" and last.never_answered and last.retry_count),
            }
        )
    frame = pd.DataFrame(rows)
    return frame if frame.empty else frame.set_index(["case", "rep", "attempt"])


def scores(run: Any) -> "DataFrame":
    """A judge pass as a table, highest attempt per repetition already applied.

    Takes the ScoreRun rather than a run id so a notebook does not pay for a
    second judge pass just to draw the table.
    """
    pd = _pd()
    rows = [
        {
            "case": r.case_id,
            "rep": r.repetition,
            "score": r.score,
            "reply chars": r.reply_chars,
            "not scored": r.error or "",
            "rationale": (r.rationale or "")[:120],
        }
        for r in run.results
    ]
    return pd.DataFrame(rows).set_index(["case", "rep"])


def suite(cases: Optional[list] = None) -> "DataFrame":
    """The case set itself: what each case is and how much of the run it is."""
    from src.cases import load_cases

    pd = _pd()
    rows = [
        {
            "case": c.case_id,
            "function": c.function,
            "provenance": c.provenance,
            "relation": c.metamorphic_relation or "-",
            "base case": c.base_case_id or "-",
            "fixture": c.fixture_dates,
            "n": c.repetitions_n,
            "tools required": ", ".join(sorted(t for t, b in (c.declared_constraints.checks.tool_counts or {}).items() if b.min)) or "-",
        }
        for c in (cases if cases is not None else load_cases())
    ]
    return pd.DataFrame(rows).set_index("case")


def structural(results: Any) -> "DataFrame":
    """Structural verdicts for one run (B08), one row per execution.

    Takes `check_run`'s results rather than a run id, so a notebook draws the
    table from the pass it already paid for instead of checking twice.

    `findings` is kept as text in a column rather than exploded into rows: a
    finding belongs to its execution, and one execution per row is what makes
    the seed/follow-up comparison below line up.
    """
    from src.cases import load_cases

    pd = _pd()
    by_id = {c.case_id: c for c in load_cases()}
    rows = []
    for row, verdict in results:
        case = by_id.get(row["case_id"])
        rows.append(
            {
                "case": row["case_id"],
                "rep": row["repetition"],
                # D53 keeps every attempt, so (case, rep) is not unique and an
                # index without this silently draws two identical-looking rows.
                "attempt": row.get("attempt") or 1,
                "kind": "seed" if row["provenance"] == "seeded" else (case.metamorphic_relation if case else "?"),
                "outcome": verdict.outcome,
                "findings": len(verdict.findings),
                "detail": " | ".join(verdict.findings)[:150] or "",
            }
        )
    frame = pd.DataFrame(rows)
    return frame if frame.empty else frame.set_index(["case", "rep", "attempt"])


def perturbation(results: Any) -> "DataFrame":
    """Did each follow-up actually differ from its seed (D61)?

    The part a passing structural verdict can hide: a follow-up whose venue set
    is identical to its seed's has not been perturbed, whatever its checks say.
    `shared` is the column to read — for a DIRECTIONAL relation a high overlap
    is a warning, and for an invariance relation it is the expected result.
    """
    from src import execution as exmod
    from src.cases import load_cases

    pd = _pd()
    by_id = {c.case_id: c for c in load_cases()}
    # Highest attempt per repetition, as D53 specifies for anything that reads
    # a result. Keying by (case, rep) alone kept whichever row came last, which
    # is arbitrary and could compare a seed's completed run against a
    # follow-up's refused one.
    rows_by_key: dict[tuple[str, int], dict] = {}
    for r, _ in results:
        key = (r["case_id"], r["repetition"])
        if key not in rows_by_key or (r.get("attempt") or 1) > (rows_by_key[key].get("attempt") or 1):
            rows_by_key[key] = r
    out = []
    for (case_id, rep), row in sorted(rows_by_key.items()):
        if row["provenance"] != "metamorphic":
            continue
        base_row = rows_by_key.get((row["base_case_id"], rep))
        if not base_row:
            continue
        case = by_id.get(case_id)
        relation = case.metamorphic_relation if case else "?"
        try:
            ex, base = exmod.load(row), exmod.load(base_row)
        except Exception as exc:  # a lost execution is not a perturbation failure
            out.append({"follow-up": case_id, "relation": relation, "note": f"unreadable: {exc}"[:60]})
            continue
        shared = len(ex.place_ids & base.place_ids)
        union = len(ex.place_ids | base.place_ids)
        out.append(
            {
                "follow-up": case_id,
                "relation": relation,
                "kind": "directional" if relation.startswith("DIR") else "invariance",
                "places": len(ex.place_ids),
                "seed places": len(base.place_ids),
                "shared": shared,
                "overlap": round(shared / union, 2) if union else None,
                "tools": "same" if ex.tool_sequence() == base.tool_sequence() else "differ",
                # A directional follow-up that returned exactly its seed's
                # venues did not perturb anything, however green its checks.
                "suspect": bool(relation.startswith("DIR") and union and shared == union),
            }
        )
    frame = pd.DataFrame(out)
    return frame if frame.empty else frame.set_index("follow-up")


def unique_contribution() -> "DataFrame":
    """What would be lost if each case were deleted (D50, D51, D61).

    The rule every extra case was admitted under: a case beyond D21's budget
    earns its place only by being the **only route** to something — a tool no
    other case requires, or a relation no other case instantiates. A case that
    reaches only what the suite already reaches is a second sample of a
    measurement it already has, and n is the cheaper way to buy that.

    So this is the justification made checkable rather than argued. `only route
    to` is empty for most cases, and that is correct: the seeds of D21's
    original budget overlap deliberately, because the suite is meant to notice
    a tool breaking from more than one direction. It is the EXTRA cases whose
    column must not be empty.
    """
    from collections import Counter

    from src.cases import load_cases
    from src.coverage import tools_required_by

    pd = _pd()
    cases = load_cases()
    required = {c.case_id: tools_required_by(c) for c in cases}
    tool_users = Counter(tool for tools in required.values() for tool in tools)
    relation_users = Counter(c.metamorphic_relation for c in cases if c.metamorphic_relation)

    rows = []
    for c in cases:
        only_tools = sorted(t for t in required[c.case_id] if tool_users[t] == 1)
        rel = c.metamorphic_relation
        only_relation = rel if rel and relation_users[rel] == 1 else None
        unique = only_tools + ([f"relation {only_relation}"] if only_relation else [])
        rows.append(
            {
                "case": c.case_id,
                "provenance": c.provenance,
                "requires": ", ".join(sorted(required[c.case_id])) or "-",
                "only route to": ", ".join(unique) or "-",
                "sole coverage": bool(unique),
            }
        )
    return pd.DataFrame(rows).set_index("case")
