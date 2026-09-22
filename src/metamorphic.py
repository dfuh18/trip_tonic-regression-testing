"""Stage 2: deriving follow-up cases from the seeds (B05, §3.4).

A follow-up is a seed with its request perturbed and an **expected delta**
stated in the same constraint vocabulary as the seed (D19/D27). Two per seed,
chosen by hand (D21), one relation each from the D22 catalogue.

**What is automatic and what is not.** The relation decides the *shape* of the
follow-up — what it inherits, which predicates it carries, that it runs at
n = 4 and names its base. The perturbed wording is the author's, because no
function writes "ask the same thing in German" convincingly, and the expected
delta is the author's, because that is the claim the case makes. This module
holds the shape; `notebooks/sim/02_expand.ipynb` holds the choices.

**Eligibility (D22).** Venue lookup and scheduling take all eight relations.
Factual QA takes INV-1..4 and DIR-1 (a different fact). Advisory takes
invariance only — there is no directional perturbation of "what should we
pack" whose expected delta a case could state without inventing a rule about
advice. `derive` refuses anything else rather than letting a notebook write a
case the catalogue does not permit.

**Invariance carries its claim in predicates, not in checks.** "Same answer"
is a statement about two executions, and D27 puts those in `predicates`. The
inherited checks come along unchanged, which is itself part of the claim: a
reworded request must still satisfy everything the seed did.

**Directional states its delta as an override.** A follow-up that moves the day
overrides `slot_days`; one that changes the count overrides `slot_count`. What
it does not override, it inherits — so a directional case still asserts
everything about the seed that the perturbation did not touch, which is where
most of its detection comes from.

One thing learned before writing any of these, recorded here because it
invalidates an obvious relation: **`search_places` is capped at five results
per call**, so narrowing a request never reduces `places_surfaced`. An agent
given a tighter constraint issues *another* search and the count goes up.
"Ask for something more specific and expect fewer results" is not a
metamorphic relation for this system; "expect different venues" is, and
"expect a second kind of place" is stronger still.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.cases import Case, Function

#: D22, per function. A relation outside its function's set is refused.
ELIGIBLE: dict[str, frozenset[str]] = {
    "venue_lookup": frozenset({"INV-1", "INV-2", "INV-3", "INV-4", "DIR-1", "DIR-2", "DIR-3", "DIR-4"}),
    "scheduling": frozenset({"INV-1", "INV-2", "INV-3", "INV-4", "DIR-1", "DIR-2", "DIR-3", "DIR-4"}),
    "factual_qa": frozenset({"INV-1", "INV-2", "INV-3", "INV-4", "DIR-1"}),
    "advisory": frozenset({"INV-1", "INV-2", "INV-3", "INV-4"}),
}

RELATION_NAMES = {
    "INV-1": "paraphrase",
    "INV-2": "typos and casing",
    "INV-3": "irrelevant detail added",
    "INV-4": "language switch (German)",
    "DIR-1": "constraint added or changed",
    "DIR-2": "day changed",
    "DIR-3": "count changed",
    "DIR-4": "negation",
}

#: Expanded cases run at n = 4 (D21); seeds run at 8.
EXPANDED_N = 4


class IneligibleRelation(ValueError):
    """The catalogue does not permit this relation for this function (D22)."""


@dataclass
class Derivation:
    """One hand-chosen follow-up. Everything not given here is inherited."""

    relation: str
    #: Suffix appended to the seed's id — the file name, so it is readable.
    suffix: str
    #: The perturbed request. The author's words, always.
    opening_turn: str
    #: What the persona now wants. Inherited unless the perturbation changes it,
    #: which it does for every directional relation: a case whose request moved
    #: to another day and whose goal still names the old one is incoherent, and
    #: the simulator reads the goal, not the check.
    goal: Optional[str] = None
    user_profile: Optional[str] = None
    intent: Optional[str] = None
    #: Checks to add or replace on top of the seed's.
    checks: dict[str, Any] = field(default_factory=dict)
    #: Seed checks this perturbation makes untrue, removed rather than left to
    #: fail. Naming them is deliberate: "what the perturbation invalidates" is
    #: a claim about the relation and belongs in the record.
    drop_checks: tuple[str, ...] = ()
    #: Extra predicates beyond the ones the relation implies.
    predicates: tuple[str, ...] = ()
    expected_tool_sequence: Optional[list[str]] = None
    scoring_criteria: Optional[list[str]] = None
    fixture_depends_on: Optional[list[str]] = None
    notes: str = ""


def _surfaces_places(seed: Case) -> bool:
    checks = seed.declared_constraints.checks
    return bool(
        checks.places_surfaced is not None
        or checks.places_named is not None
        or "search_places" in (seed.expected_tool_sequence or [])
        or "search_places" in (checks.tool_counts or {})
    )


def implied_predicates(seed: Case, relation: str) -> list[str]:
    """What the relation itself claims, before the author adds anything.

    **Invariance implies nothing** (D49). It used to imply
    `same_tool_sequence_as_base`, which four runs of the seeds showed to be
    two different mistakes at once. It re-introduces exactly the variance
    `ALWAYS_ALLOWED_TOOLS` exists to excuse — the read tools are called only
    when the preloaded context falls short, and `advisory_packing_list` ran
    `[get_weather, get_region_climate]` on some runs and `[get_weather]` on
    others. And on an advisory case it is a tool constraint by another name,
    walking straight past `Case._coherent`, which refuses to let advisory
    constrain tools at all (D29). Where a case wants to claim a source was
    consulted, `tools_any_of` says it directly and survives the variance.

    `same_venues_as_base` is not implied either, for a blunter reason: the
    same request returns different venues on every run. Four runs of
    `venue_lookup_sintra_lunch` returned three places each and shared exactly
    one across all four. Requiring equality would fail almost every
    repetition.

    **Directional implies nothing either**, and the reason is the same
    measurement. `different_venues_from_base` fails only when two place-id
    sets are *exactly* equal, and they never are — so it passed on noise and
    verified nothing. It was also backwards wherever it was applied to
    scheduling: moving a draft to another day does not change which monuments
    are in Belém, so proposing the same venues is the correct answer and the
    predicate would have called it a regression.

    What replaces it is **the kind of place, not its identity** (D49). A
    request's venue *types* are a property of what was asked for and are
    stable between runs, where the venues themselves are not; `places_named_
    types` states them declaratively, as a check about one execution, which is
    where D27 says a single-execution claim belongs. A directional delta is
    therefore always a check override, never a predicate.
    """
    return []


def _plain(value: Any) -> Any:
    """Tuples to lists, all the way down.

    ``Checks.model_dump()`` returns the time windows as tuples, and PyYAML
    writes a tuple as ``!!python/tuple``, which ``yaml.safe_load`` then refuses
    — so a derived case would round-trip to an unloadable file. Normalised here
    rather than at the dump site, because every caller would otherwise have to
    remember.
    """
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def derive(seed: Case, derivation: Derivation) -> dict:
    """The follow-up case, as a mapping ready to be written as YAML."""
    if seed.provenance != "seeded":
        raise ValueError(f"{seed.case_id} is not a seed; follow-ups derive from seeds only")
    eligible = ELIGIBLE[seed.function]
    if derivation.relation not in eligible:
        raise IneligibleRelation(
            f"{derivation.relation} is not permitted for {seed.function} (D22): "
            f"{seed.function} takes {', '.join(sorted(eligible))}"
        )

    checks = _plain(seed.declared_constraints.checks.model_dump(exclude_none=True))
    for key in derivation.drop_checks:
        checks.pop(key, None)
    checks.update(_plain(derivation.checks))

    predicates = list(dict.fromkeys(
        implied_predicates(seed, derivation.relation) + list(derivation.predicates)
    ))

    return {
        "case_id": f"{seed.case_id}__{derivation.suffix}",
        "base_case_id": seed.case_id,
        "provenance": "metamorphic",
        "run_priority": seed.run_priority,
        "function": seed.function,
        "user_profile": derivation.user_profile or seed.user_profile,
        "goal": derivation.goal or seed.goal,
        "opening_turn": derivation.opening_turn,
        "intent": derivation.intent if derivation.intent is not None else seed.intent,
        "expected_tool_sequence": (
            derivation.expected_tool_sequence
            if derivation.expected_tool_sequence is not None
            else list(seed.expected_tool_sequence)
        ),
        "declared_constraints": {"checks": checks, "predicates": predicates},
        "scoring_criteria": derivation.scoring_criteria or list(seed.scoring_criteria),
        "references": [r.model_dump(exclude_none=True) for r in seed.references],
        "repetitions_n": EXPANDED_N,
        "metamorphic_relation": derivation.relation,
        "fixture_depends_on": (
            derivation.fixture_depends_on
            if derivation.fixture_depends_on is not None
            else list(seed.fixture_depends_on)
        ),
        "notes": derivation.notes,
    }


def relation_coverage() -> list[tuple[str, str, int, int]]:
    """(relation, name, eligible seeds, follow-ups) — D61's evidence.

    Raw counts of the relations make the suite look arbitrary: five DIR-1 and
    one DIR-3 invites the question why. The denominator is what answers it. A
    relation is not applicable to every function (D22), so the opportunity to
    use one is uneven before any choice is made, and the honest measure is use
    against opportunity rather than against the other relations.
    """
    from collections import Counter

    from src.cases import load_cases

    cases = load_cases()
    seeds = [c for c in cases if c.provenance == "seeded"]
    used = Counter(c.metamorphic_relation for c in cases if c.metamorphic_relation)
    return [
        (rel, RELATION_NAMES[rel], sum(1 for s in seeds if rel in ELIGIBLE[s.function]), used.get(rel, 0))
        for rel in sorted(RELATION_NAMES)
    ]


def relation_report() -> str:
    """The relation table, for the expansion notebook and a run's own record."""
    rows = relation_coverage()
    lines = [
        f"{'rel':<7}{'perturbation':<30}{'eligible':>9}{'used':>6}{'of opp.':>9}",
        "-" * 61,
    ]
    for rel, name, opportunity, used in rows:
        share = f"{100 * used / opportunity:.0f}%" if opportunity else "-"
        lines.append(f"{rel:<7}{name:<30}{opportunity:>9}{used:>6}{share:>9}")
    absent = [rel for rel, _, _, used in rows if not used]
    if absent:
        lines.append("")
        lines.append(f"NOT INSTANTIATED: {', '.join(absent)} — the catalogue claims a relation the "
                     f"suite does not exercise (D61)")
    singles = [rel for rel, _, opportunity, used in rows if used == 1 and opportunity > 4]
    if singles:
        lines.append("")
        lines.append(
            f"single instance: {', '.join(singles)} — instantiated and exercised, but one case is not "
            f"a sample. Nothing statistical may be claimed per-relation for these (D61)."
        )
    return "\n".join(lines)
