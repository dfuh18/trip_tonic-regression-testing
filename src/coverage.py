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

from src.cases import ALL_TOOL_NAMES, ALWAYS_ALLOWED_TOOLS, Case, as_bound, load_cases

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
    #: Cases that assert the tool RAN, not merely that it may.
    required: dict[str, list[str]] = field(default_factory=dict)
    observed: dict[str, int] = field(default_factory=dict)
    #: Calls that came back with an error, per tool.
    errored: dict[str, int] = field(default_factory=dict)
    parameters: dict[str, set[str]] = field(default_factory=dict)
    #: Groups a case requires ONE of (``tools_any_of`` with more than one
    #: member), and the cases that declare them. A disjunction is coverage of a
    #: CAPABILITY rather than of a tool (D68).
    groups: dict[frozenset[str], list[str]] = field(default_factory=dict)

    @property
    def covered_by_group(self) -> set[str]:
        """Tools asserted only as a member of a disjunction.

        Not a gap. If one member broke, the agent would use the other and
        answer correctly — which is not a regression, so a case that failed it
        would be asserting the route rather than the outcome (D30).
        """
        return {tool for group in self.groups for tool in group} - set(self.required)

    @property
    def permitted_but_never_required(self) -> list[str]:
        """Named only as a probe: no case asserts it ran, and none names an
        alternative to it either. This is the real gap — the suite would not
        notice the capability disappearing, not merely the tool."""
        return sorted(
            t
            for t in MUST_BE_DECLARED
            if self.declared.get(t) and not self.required.get(t) and t not in self.covered_by_group
        )

    @property
    def never_succeeded(self) -> list[str]:
        """Every observed call came back an error — the tool is exercised and
        its working path is not."""
        return sorted(
            t for t in MUST_BE_DECLARED
            if self.observed.get(t) and self.errored.get(t) == self.observed.get(t)
        )

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


def tools_required_by(case: Case) -> set[str]:
    """Tools this case asserts actually **ran** — as opposed to merely
    permitting them.

    The distinction is not pedantic. Eleven cases name `get_weather`, and all
    eleven bound it at `{min: 0, max: 1}`: a probe the agent may try and need
    not. Counting those as eleven declarations made the coverage report read
    as though the tool were thoroughly asserted, when no case requires it at
    all and the suite would not notice it disappearing.

    A second overstatement of the same kind lived here (D66). ``tools_any_of``
    is a DISJUNCTION — the case passes if any one of the named tools ran — so a
    two-element ``any_of`` requires neither of them individually. Counting both
    made three weather cases read as requiring ``get_region_climate`` when the
    suite would not have noticed it disappearing: the agent would have fallen
    back to ``get_climate_normals`` and every one of them would still pass.
    A one-element ``any_of`` is a requirement, because there is nothing else
    that can satisfy it.
    """
    checks = case.declared_constraints.checks
    any_of = list(checks.tools_any_of or [])
    required = set(case.expected_tool_sequence) | (set(any_of) if len(any_of) == 1 else set())
    for tool, bound in (checks.tool_counts or {}).items():
        if as_bound(bound).min:
            required.add(tool)
    return required


def tools_alternatively_required_by(case: Case) -> list[frozenset[str]]:
    """Disjunctive requirements: groups where the case needs ONE of the tools.

    Kept separate rather than folded into ``tools_required_by`` so neither
    reading is lost. A tool that appears only here is asserted, but weakly: no
    case would fail if it vanished, provided its alternative still works.
    """
    any_of = list(case.declared_constraints.checks.tools_any_of or [])
    return [frozenset(any_of)] if len(any_of) > 1 else []


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


def observed_coverage(run_id: str) -> tuple[dict[str, int], dict[str, set[str]], dict[str, int]]:
    """tool -> calls, and tool -> the argument names actually used, for one run.

    Parameters matter as well as tools: `move_slot` called only ever with day,
    start and end together says nothing about a day-only move, and a suite that
    reports `move_slot` covered on that evidence is overstating itself.
    """
    from src import db, execution as exmod

    calls: dict[str, int] = defaultdict(int)
    errs: dict[str, int] = defaultdict(int)
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
            if call.get("result_error"):
                errs[call["tool"]] += 1
            params[call["tool"]] |= set((call.get("args") or {}).keys())
    return dict(calls), {t: set(p) for t, p in params.items()}, dict(errs)


def for_run(run_id: str) -> Coverage:
    calls, params, errs = observed_coverage(run_id)
    cases = list(load_cases())
    required: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        for tool in tools_required_by(case):
            required[tool].append(case.case_id)
    return Coverage(
        declared=declared_coverage(cases),
        required={t: sorted(ids) for t, ids in required.items()},
        observed=calls,
        errored=errs,
        parameters=params,
        groups=declared_groups(cases),
    )


def declared_groups(cases=None) -> dict[frozenset[str], list[str]]:
    """Disjunctive requirements across the suite, and who declares them."""
    from collections import defaultdict

    from src.cases import load_cases

    out: dict[frozenset[str], list[str]] = defaultdict(list)
    for case in cases if cases is not None else load_cases():
        for group in tools_alternatively_required_by(case):
            out[group].append(case.case_id)
    return dict(out)


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
        f"{'tool':22s} {'req':>4s} {'perm':>5s} {'calls':>6s} {'err':>4s}  parameters exercised",
        "-" * 78,
    ]
    for tool in sorted(ALL_TOOL_NAMES):
        cases = coverage.declared.get(tool, [])
        req = coverage.required.get(tool, [])
        calls = coverage.observed.get(tool, 0)
        errs = coverage.errored.get(tool, 0)
        note = " (read)" if tool in READ_TOOLS else ""
        params = ", ".join(sorted(coverage.parameters.get(tool, ()))) or "-"
        flag = ""
        if tool in MUST_BE_DECLARED and not cases:
            flag = "  UNDECLARED"
        elif tool in MUST_BE_DECLARED and not calls:
            flag = "  never called"
        elif calls and errs == calls:
            flag = "  every call errored"
        lines.append(
            f"{tool + note:22s} {len(req):4d} {len(cases) - len(req):5d} {calls:6d} {errs:4d}  {params}{flag}"
        )

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
        lines.append("every non-read tool is declared by a case and called by this run.")
    for group, cases_naming in sorted(coverage.groups.items(), key=lambda kv: sorted(kv[0])):
        lines.append(
            "covered as a group: one of {"
            + " | ".join(sorted(group))
            + "} is required by "
            + f"{len(cases_naming)} case(s)"
            + "  (either answers correctly, so neither is pinned — D68)"
        )
    if coverage.permitted_but_never_required:
        lines.append(
            "permitted but never REQUIRED: "
            + ", ".join(coverage.permitted_but_never_required)
            + "  (named only at min 0, with no alternative named either — the suite would not "
            "notice the capability vanishing)"
        )
    if coverage.never_succeeded:
        lines.append(
            "every observed call errored: "
            + ", ".join(coverage.never_succeeded)
            + "  (the tool is exercised; its working path is not)"
        )

    if run_id:
        tight = bounds_at_their_cap(run_id)
        if tight:
            lines.append("")
            lines.append("bounds this run sat exactly at (no headroom for a correct agent):")
            for case_id, tool, cap, seen in tight:
                lines.append(f"  {case_id}: {tool} capped at {cap}, used {seen}")
    return "\n".join(lines)
