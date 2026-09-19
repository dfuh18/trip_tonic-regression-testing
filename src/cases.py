"""Test cases: the unit of the suite (§3.4, Table 11 test-case level).

A case is one YAML file under ``cases/``. This module is the only place the
shape is defined, so a case a notebook shows, a case the runner executes and a
case the checker evaluates are the same object. Validation errors name the
file and the key: a case that loads is a case that can run.

``declared_constraints`` follows D19 as refined by D27: a ``checks`` mapping of
declarative keys carries everything that can be stated about **one** execution,
and the ``predicates`` list names functions in ``cases/predicates.py`` for the
one thing a schema cannot state — a comparison with **another** execution, which
is what every metamorphic relation is.

What a case constrains follows from **what its request asks for**, not from its
function label (D29). An advisory request that asks for advice implies the trip
does not change, so it says so; it does not constrain tools, because a message
carrying no slash command keeps the whole toolset deliberately and whether to
look something up is the agent's judgement.

Every case is written against the fixture trip in ``cases/fixture.json`` (built
and reset by ``src/reset.py``), and ``fixture_depends_on`` names the parts of it
a case assumes — validated here, so a case cannot outlive the state it reads.

``suite_version`` is the SHA-256 over the sorted case files **and the fixture**,
and is what a run records (Table 11): a suite that changed is a different suite,
and so is the same suite against a different starting trip.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SUBTREE_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = SUBTREE_ROOT / "cases"
REFERENCES_DIR = CASES_DIR / "references"
PREDICATES_FILE = CASES_DIR / "predicates.py"
FIXTURE_FILE = CASES_DIR / "fixture.json"

Function = Literal["venue_lookup", "scheduling", "factual_qa", "advisory"]
Provenance = Literal["seeded", "metamorphic", "retained"]
Intent = Literal["find", "plan", "reschedule"]

#: Tools that read the trip's own state and write nothing. Never a violation
#: under deny-by-default (D28): the agent calls them only when its preloaded
#: prompt context is not enough, which varies between runs of one case, so
#: treating them as unexpected would fail a case on variance rather than on a
#: regression. Mirrors READ_TOOLS in apps/api/src/routes/ai/agent/agent.tool-policy.ts.
ALWAYS_ALLOWED_TOOLS = ("get_trip_details", "list_trip_blocks", "get_itinerary")

#: The D22 catalogue. A follow-up case names exactly one.
METAMORPHIC_RELATIONS = (
    "INV-1", "INV-2", "INV-3", "INV-4",
    "DIR-1", "DIR-2", "DIR-3", "DIR-4",
)


class Bound(BaseModel):
    """An integer requirement: exact, or a closed range."""

    model_config = ConfigDict(extra="forbid")
    min: Optional[int] = None
    max: Optional[int] = None

    def holds(self, n: int) -> bool:
        return (self.min is None or n >= self.min) and (self.max is None or n <= self.max)


BoundLike = Union[int, Bound]


def as_bound(value: BoundLike) -> Bound:
    return Bound(min=value, max=value) if isinstance(value, int) else value


class SlotMoved(BaseModel):
    """One stop ends up in one window. Named, not hardcoded: the same check
    serves every rescheduling case."""

    model_config = ConfigDict(extra="forbid")
    #: The stop's title, as the fixture and the trip call it.
    block: str
    #: YYYY-MM-DD.
    day: str
    #: HH:MM. Omit where the case asks for a day and not a time.
    start_time: Optional[str] = None
    #: HH:MM. Assert it wherever the stop has a length worth preserving: a
    #: move that sets the start and leaves the end at the day's edge lands the
    #: stop in the right window and still gets it wrong.
    end_time: Optional[str] = None


class Checks(BaseModel):
    """What a case asserts about an execution, declaratively (D19, D27).

    Every key is optional and an absent key is not a constraint. The checker
    (B08) knows exactly these; a case cannot invent one, because a constraint
    nothing evaluates is worse than no constraint.
    """

    model_config = ConfigDict(extra="forbid")

    # --- what the agent called ---
    #: Calls per tool, exact or bounded. Under D28 a zero is never needed: a
    #: tool the case does not name is already forbidden.
    tool_counts: Optional[dict[str, BoundLike]] = None
    #: At least one of these ran — "answered from a source", not from memory.
    tools_any_of: Optional[list[str]] = None
    #: No tool returned or threw an error (D11's tool-level failure).
    no_tool_errors: Optional[bool] = None

    # --- what it surfaced ---
    #: Google places the replies named, bounded.
    places_surfaced: Optional[BoundLike] = None

    # --- the draft it proposed ---
    #: Every draft slot's day must be one of these (YYYY-MM-DD).
    slot_days: Optional[list[str]] = None
    #: Number of slots the draft holds.
    slot_count: Optional[BoundLike] = None

    # --- what it changed on the live itinerary ---
    #: A named stop ends up in a named window.
    slot_moved: Optional[SlotMoved] = None

    # --- what the database recorded ---
    #: study_mutations rows per (table, op) — e.g. ``itinerary_slots.INSERT: 1``.
    mutation_counts: Optional[dict[str, BoundLike]] = None


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checks: Checks = Field(default_factory=Checks)
    #: Names of functions in cases/predicates.py — the comparisons with another
    #: execution, which no schema key can state (D27).
    predicates: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return self.checks == Checks() and not self.predicates


class Reference(BaseModel):
    """A stored source a factual-QA answer is judged against (D23)."""

    model_config = ConfigDict(extra="forbid")
    title: str
    section: Optional[str] = None
    #: File under cases/references/ holding the stored text.
    path: str

    def text(self) -> str:
        return (REFERENCES_DIR / self.path).read_text(encoding="utf-8")


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    base_case_id: Optional[str] = None
    provenance: Provenance
    run_priority: int = Field(ge=1)
    function: Function
    user_profile: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    opening_turn: str = Field(min_length=1)
    #: The slash command the simulator opens with, if the case says so.
    intent: Optional[Intent] = None
    #: The tools the case expects, in order (Table 11). This is the ordering
    #: constraint itself, not a description of one: the checker requires them
    #: to appear in the trace in this order, as a subsequence, so a case that
    #: expects a grounded plan writes [search_places, propose_plan] and gets
    #: both the presence and the order from one field. Empty constrains nothing.
    expected_tool_sequence: list[str] = Field(default_factory=list)
    declared_constraints: Constraints = Field(default_factory=Constraints)
    #: The point-wise rubric, one criterion per line, scored 1..10 (§3.1).
    scoring_criteria: list[str] = Field(min_length=1)
    references: list[Reference] = Field(default_factory=list)
    repetitions_n: int = Field(ge=1)
    metamorphic_relation: Optional[str] = None
    #: What the case leans on in the fixture trip: stop titles from
    #: cases/fixture.json and/or day dates inside the trip's range. The loader
    #: checks them, so a case cannot quietly outlive the state it assumes —
    #: "move the Tram 28 ride" is only a case while that stop is in the
    #: fixture. Empty means the case reads nothing off the trip.
    fixture_depends_on: list[str] = Field(default_factory=list)
    #: Free text for the notebook: why this case exists, what it exercises.
    notes: Optional[str] = None

    def constrains_tools(self) -> bool:
        """True when the case says anything about which tools may run. A case
        that says nothing constrains nothing (D28): that is how the advisory
        seeds stay free to ground their advice."""
        checks = self.declared_constraints.checks
        return bool(self.expected_tool_sequence or checks.tool_counts or checks.tools_any_of)

    def allowed_tools(self) -> Optional[set[str]]:
        """Every tool this case permits, or None when it constrains none.

        Deny by default (D28): the union of what the case names, plus the read
        tools, and any other call is a structural failure. Listing what a case
        expects is therefore the whole of its tool constraint — there are no
        zeros to write, and a tool nobody thought to forbid is forbidden
        anyway, which is the point.
        """
        if not self.constrains_tools():
            return None
        checks = self.declared_constraints.checks
        allowed = set(ALWAYS_ALLOWED_TOOLS) | set(self.expected_tool_sequence)
        allowed |= set(checks.tool_counts or {})
        allowed |= set(checks.tools_any_of or [])
        # A tool bounded at zero is named in order to be forbidden, not allowed.
        for tool, bound in (checks.tool_counts or {}).items():
            if as_bound(bound).max == 0:
                allowed.discard(tool)
        return allowed

    @model_validator(mode="after")
    def _coherent(self) -> "Case":
        if self.provenance == "metamorphic":
            if not self.base_case_id:
                raise ValueError("a metamorphic case needs base_case_id")
            if self.metamorphic_relation not in METAMORPHIC_RELATIONS:
                raise ValueError(
                    f"metamorphic_relation must be one of {', '.join(METAMORPHIC_RELATIONS)}"
                )
        elif self.metamorphic_relation is not None:
            raise ValueError("only a metamorphic case carries metamorphic_relation")
        if self.function == "factual_qa" and not self.references:
            raise ValueError("a factual_qa case needs at least one reference")
        if self.function == "advisory" and self.constrains_tools():
            raise ValueError(
                "an advisory case does not constrain tools: it carries no slash command, so the "
                "agent keeps its whole toolset and whether to look anything up is its call (D29). "
                "Constrain what the request implies about the trip instead."
            )
        return self


class CaseFileError(ValueError):
    """A case file that cannot be loaded, naming the file and what is wrong."""


def fixture() -> dict:
    """The trip every repetition starts from (cases/fixture.json, built by B02)."""
    return json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))


def fixture_anchors(data: Optional[dict] = None) -> set[str]:
    """What a case may declare a dependency on: stop titles and trip days.

    Titles, not an alias invented for the fixture file: a stop is called the
    same thing here, in the trip the harness builds, in a ``study_mutations``
    projection and in the case's own opening turn. One vocabulary means a
    declaration can be checked against the case's prose, and a reader of a
    failed run does not have to translate.
    """
    data = data or fixture()
    anchors = {block["title"] for block in data["blocks"]}
    start = date.fromisoformat(data["trip"]["start_date"])
    end = date.fromisoformat(data["trip"]["end_date"])
    day = start
    while day <= end:
        anchors.add(day.isoformat())
        day += timedelta(days=1)
    return anchors


def _predicate_names() -> set[str]:
    if not PREDICATES_FILE.exists():
        return set()
    spec = importlib.util.spec_from_file_location("study_predicates", PREDICATES_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    # Functions DEFINED there, not everything callable in its namespace: the
    # module imports Mapping and Optional, and a case naming one of those as a
    # predicate would have passed validation and then failed at check time.
    return {
        name
        for name, value in vars(module).items()
        if inspect.isfunction(value) and value.__module__ == module.__name__ and not name.startswith("_")
    }


def case_files(directory: Path = CASES_DIR) -> list[Path]:
    """Every case file, sorted by name. Underscore-prefixed files are drafts."""
    return sorted(p for p in directory.glob("*.yaml") if not p.name.startswith("_"))


def load_case(
    path: Path,
    known_predicates: Optional[set[str]] = None,
    known_anchors: Optional[set[str]] = None,
) -> Case:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CaseFileError(f"{path.name}: not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise CaseFileError(f"{path.name}: expected a mapping at the top level")
    try:
        case = Case.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['msg']}" for e in exc.errors()
        )
        raise CaseFileError(f"{path.name}: {problems}") from exc
    if case.case_id != path.stem:
        raise CaseFileError(f"{path.name}: case_id {case.case_id!r} must equal the file name")
    known = _predicate_names() if known_predicates is None else known_predicates
    unknown = [p for p in case.declared_constraints.predicates if p not in known]
    if unknown:
        raise CaseFileError(f"{path.name}: unknown predicate(s) {unknown} — define them in cases/predicates.py")
    for ref in case.references:
        if not (REFERENCES_DIR / ref.path).exists():
            raise CaseFileError(f"{path.name}: reference file missing: references/{ref.path}")
    anchors = fixture_anchors() if known_anchors is None else known_anchors
    unknown_anchors = [a for a in case.fixture_depends_on if a not in anchors]
    if unknown_anchors:
        raise CaseFileError(
            f"{path.name}: fixture_depends_on names {unknown_anchors}, which the fixture does not "
            f"have — a stop title from cases/fixture.json or a day inside the trip's range"
        )
    return case


def load_cases(directory: Path = CASES_DIR) -> list[Case]:
    """Every case, validated, with base cases checked to exist."""
    known = _predicate_names()
    anchors = fixture_anchors()
    cases = [load_case(path, known, anchors) for path in case_files(directory)]
    ids = {c.case_id for c in cases}
    for c in cases:
        if c.base_case_id and c.base_case_id not in ids:
            raise CaseFileError(f"{c.case_id}.yaml: base_case_id {c.base_case_id!r} is not a case")
    return cases


def suite_version(directory: Path = CASES_DIR) -> str:
    """SHA-256 over the sorted case files and the fixture they run against.

    The fixture is in the hash on purpose: the same case text against a
    different starting trip is a different test, and Table 11's suite version
    has to say so.
    """
    digest = hashlib.sha256()
    fixture_path = directory / "fixture.json"
    if fixture_path.exists():
        digest.update(b"fixture.json\0")
        digest.update(fixture_path.read_bytes())
        digest.update(b"\0")
    for path in case_files(directory):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def by_priority(cases: list[Case]) -> list[Case]:
    """P7: run order — priority first, seeds before their follow-ups, then name."""
    return sorted(cases, key=lambda c: (c.run_priority, c.provenance != "seeded", c.case_id))
