"""Tool and parameter coverage: the suite's evidence that it exercises the
agent it tests (D50).

A regression suite that never calls a tool cannot notice that tool breaking.
Before this module the measurement had never been taken, and taking it found
that **six of the agent's twelve tools were never called** by any execution of
any case — including `schedule_block` and `unschedule_block`, two of the four
tools that write the itinerary. The agent could have lost both outright and
every run would have reported clean.

Two measurements, deliberately separate, because they answer different
questions and fail for different reasons:

**Declared coverage** is static. Which tools does the suite *name* — in an
`expected_tool_sequence`, a `tool_counts` bound or a `tools_any_of`? A tool no
case names is a tool nothing asserts anything about, and that is a property of
the cases alone. `tests/test_tool_coverage.py` checks it, so it runs with the
unit tests and fails a commit rather than a study.

**Observed coverage** is empirical. Which tools did a run actually *call*, and
with which parameters? A tool can be declared and never reached — three cases
name `get_climate_normals` and no execution has ever called it, because the
agent reaches for `get_region_climate` first and answers. Declared coverage
would call that covered; only the run says otherwise.

The two together are the evidence. Neither alone is.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from src.cases import ALL_TOOL_NAMES, ALWAYS_ALLOWED_TOOLS, Case, load_cases

#: Tools the agent reaches for only when its preloaded context falls short, so
#: whether they appear varies between runs of one case (D28). A case cannot
#: sensibly require one, so they are excluded from the *declared* requirement
#: and reported separately under observed coverage.
READ_TOOLS = frozenset(ALWAYS_ALLOWED_TOOLS)

#: Tools every suite must declare. The read tools are exempt above; everything
#: else is a capability a case is expected to make a claim about.
MUST_BE_DECLARED = frozenset(ALL_TOOL_NAMES) - READ_TOOLS


@dataclass
class Coverage:
    declared: dict[str, list[str]] = field(default_factory=dict)
    observed: dict[str, int] = field(default_factory=dict)
    parameters: dict[str, set[str]] = field(default_factory=dict)

    @property
    def undeclared(self) -> list[str]:
        return sorted(t for t in MUST_BE_DECLARED if not self.declared.get(t))

    @property
    def declared_but_never_called(self) -> list[str]:
        """Named by a case and reached by no execution — the gap that a static
        check alone reports as covered."""
        return sorted(
            t for t in MUST_BE_DECLARED if self.declared.get(t) and not self.observed.get(t)
        )


def tools_named_by(case: Case) -> set[str]:
    """Every tool this case makes a claim about."""
    checks = case.declared_constraints.checks
    return (
        set(case.expected_tool_sequence)
        | set(checks.tool_counts or {})
        | set(checks.tools_any_of or [])
    )


def declared_coverage(cases: Optional[Iterable[Case]] = None) -> dict[str, list[str]]:
    """tool -> the case ids that name it."""
    by_tool: dict[str, list[str]] = defaultdict(list)
    for case in cases if cases is not None else load_cases():
        for tool in tools_named_by(case):
            by_tool[tool].append(case.case_id)
    return {t: sorted(ids) for t, ids in by_tool.items()}


def observed_coverage(run_id: str) -> tuple[dict[str, int], dict[str, set[str]]]:
    """tool -> calls, and tool -> the argument names actually used, for one run.

    Parameters matter as well as tools: `move_slot` called only ever with day,
    start and end together says nothing about a day-only move, and a suite that
    reports `move_slot` covered on that evidence is overstating itself.
    """
    from src import db, execution as exmod

    calls: dict[str, int] = defaultdict(int)
    params: dict[str, set[str]] = defaultdict(set)
    rows = (
        db.admin()
        .table("study_case_executions")
        .select("*")
        .eq("run_id", run_id)
        .execute()
        .data
    )
    for row in rows:
        for call in exmod.load(row).trace:
            calls[call["tool"]] += 1
            params[call["tool"]] |= set((call.get("args") or {}).keys())
    return dict(calls), {t: set(p) for t, p in params.items()}


def for_run(run_id: str) -> Coverage:
    calls, params = observed_coverage(run_id)
    return Coverage(declared=declared_coverage(), observed=calls, parameters=params)


def bounds_at_their_cap(run_id: str) -> list[tuple[str, str, int, int]]:
    """Checks an execution sat exactly at, which is a false regression waiting.

    A `tool_counts` cap the agent reaches has no headroom: one more call — for
    a reason the case did not anticipate but a person would accept — fails a
    correct agent, and under D23's 8/8 one such repetition fails the seed.
    Found by reading a run rather than the cases, because a bound only looks
    tight next to what actually happened: `venue_lookup_seafood_lisbon` capped
    `search_places` at three and used three in four runs of six.

    Reported per run rather than asserted in a test, since it needs execution
    data. Returns (case_id, tool, cap, observed).
    """
    from src import db, execution as exmod
    from src.cases import as_bound, load_cases

    by_id = {c.case_id: c for c in load_cases()}
    tight: list[tuple[str, str, int, int]] = []
    rows = (
        db.admin().table("study_case_executions").select("*").eq("run_id", run_id).execute().data
    )
    for row in rows:
        case = by_id.get(row["case_id"])
        if case is None or row.get("error"):
            continue
        called = exmod.load(row).tool_sequence()
        for tool, bound in (case.declared_constraints.checks.tool_counts or {}).items():
            b = as_bound(bound)
            seen = called.count(tool)
            if b.max is not None and seen == b.max and seen > 0:
                tight.append((row["case_id"], tool, b.max, seen))
    return tight


def report(coverage: Coverage, run_id: Optional[str] = None) -> str:
    """The evidence, as a reader sees it."""
    lines = [
        f"{'tool':22s} {'cases':>5s} {'calls':>6s}  parameters exercised",
        "-" * 78,
    ]
    for tool in sorted(ALL_TOOL_NAMES):
        cases = coverage.declared.get(tool, [])
        calls = coverage.observed.get(tool, 0)
        note = " (read)" if tool in READ_TOOLS else ""
        params = ", ".join(sorted(coverage.parameters.get(tool, ()))) or "-"
        flag = ""
        if tool in MUST_BE_DECLARED and not cases:
            flag = "  UNDECLARED"
        elif tool in MUST_BE_DECLARED and not calls:
            flag = "  never called"
        lines.append(f"{tool + note:22s} {len(cases):5d} {calls:6d}  {params}{flag}")

    lines.append("")
    if coverage.undeclared:
        lines.append(f"NO CASE NAMES: {', '.join(coverage.undeclared)}")
    if coverage.declared_but_never_called:
        lines.append(
            "declared but never called: "
            + ", ".join(coverage.declared_but_never_called)
            + "  (a case asserts it; no execution reached it)"
        )
    if not coverage.undeclared and not coverage.declared_but_never_called:
        lines.append("every non-read tool is both declared by a case and called by this run.")

    if run_id:
        tight = bounds_at_their_cap(run_id)
        if tight:
            lines.append("")
            lines.append("bounds this run sat exactly at (no headroom for a correct agent):")
            for case_id, tool, cap, seen in tight:
                lines.append(f"  {case_id}: {tool} capped at {cap}, used {seen}")
    return "\n".join(lines)
