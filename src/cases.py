"""Test cases: the unit of the suite (§3.4, Table 11 test-case level).

A case is one YAML file under ``cases/``. This module is the only place the
shape is defined, so a case a notebook shows, a case the runner executes and a
case the checker evaluates are the same object. Validation errors name the
file and the key: a case that loads is a case that can run.

``declared_constraints`` follows D19 — a ``checks`` mapping of declarative keys
the loader validates, plus an optional ``predicates`` list naming functions in
``cases/predicates.py`` for anything sequence-dependent. Advisory cases carry
scoring criteria and no constraints, because the advisory function leaves no
structural trace (P4).

``suite_version`` is the SHA-256 over the sorted case files and is what a run
records (Table 11): a suite that changed is a different suite.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SUBTREE_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = SUBTREE_ROOT / "cases"
REFERENCES_DIR = CASES_DIR / "references"
PREDICATES_FILE = CASES_DIR / "predicates.py"

Function = Literal["venue_lookup", "scheduling", "factual_qa", "advisory"]
Provenance = Literal["seeded", "metamorphic", "retained"]
Intent = Literal["find", "plan", "reschedule"]

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


class Checks(BaseModel):
    """The declarative half of D19. Every key is optional; an absent key is not
    a constraint. Keys are the ones the structural checker (B08) knows."""

    model_config = ConfigDict(extra="forbid")
    #: Tools that must appear in this order (as a subsequence of the trace).
    tool_sequence: Optional[list[str]] = None
    #: Calls per tool, exact or bounded.
    tool_counts: Optional[dict[str, BoundLike]] = None
    #: Every draft slot's day must be one of these (YYYY-MM-DD).
    slot_days: Optional[list[str]] = None
    #: Number of slots the draft holds.
    slot_count: Optional[BoundLike] = None
    #: study_mutations rows per (table, op) — e.g. ``itinerary_slots.INSERT: 1``.
    mutation_counts: Optional[dict[str, BoundLike]] = None


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checks: Checks = Field(default_factory=Checks)
    #: Names of functions in cases/predicates.py (the sequence-dependent half).
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
    expected_tool_sequence: list[str] = Field(default_factory=list)
    declared_constraints: Constraints = Field(default_factory=Constraints)
    #: The point-wise rubric, one criterion per line, scored 1..10 (§3.1).
    scoring_criteria: list[str] = Field(min_length=1)
    references: list[Reference] = Field(default_factory=list)
    repetitions_n: int = Field(ge=1)
    metamorphic_relation: Optional[str] = None
    #: Free text for the notebook: why this case exists, what it exercises.
    notes: Optional[str] = None

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
        if self.function == "advisory" and not self.declared_constraints.is_empty():
            raise ValueError("an advisory case carries no structural constraints (P4)")
        return self


class CaseFileError(ValueError):
    """A case file that cannot be loaded, naming the file and what is wrong."""


def _predicate_names() -> set[str]:
    if not PREDICATES_FILE.exists():
        return set()
    spec = importlib.util.spec_from_file_location("study_predicates", PREDICATES_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return {name for name, value in vars(module).items() if callable(value) and not name.startswith("_")}


def case_files(directory: Path = CASES_DIR) -> list[Path]:
    """Every case file, sorted by name. Underscore-prefixed files are drafts."""
    return sorted(p for p in directory.glob("*.yaml") if not p.name.startswith("_"))


def load_case(path: Path, known_predicates: Optional[set[str]] = None) -> Case:
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
    return case


def load_cases(directory: Path = CASES_DIR) -> list[Case]:
    """Every case, validated, with base cases checked to exist."""
    known = _predicate_names()
    cases = [load_case(path, known) for path in case_files(directory)]
    ids = {c.case_id for c in cases}
    for c in cases:
        if c.base_case_id and c.base_case_id not in ids:
            raise CaseFileError(f"{c.case_id}.yaml: base_case_id {c.base_case_id!r} is not a case")
    return cases


def suite_version(directory: Path = CASES_DIR) -> str:
    """SHA-256 over the sorted case files, names and contents (Table 11)."""
    digest = hashlib.sha256()
    for path in case_files(directory):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def by_priority(cases: list[Case]) -> list[Case]:
    """P7: run order — priority first, seeds before their follow-ups, then name."""
    return sorted(cases, key=lambda c: (c.run_priority, c.provenance != "seeded", c.case_id))
