"""The structural checker (B08, §3.4): does an execution match what its case
declared?

Three things are evaluated, and all three must hold for ``none``:

1. every key of ``declared_constraints.checks`` — the closed vocabulary of
   D27 as extended by D37, each one declarative and already validated by the
   loader, so the checker never meets a key it does not know;
2. ``expected_tool_sequence`` as an ordered **subsequence** of the tools
   called, and ``Case.allowed_tools()`` as deny by default (D28);
3. the named ``predicates``, which by D27 are only the comparisons with
   another execution, so a metamorphic follow-up is passed its seed's.

**Scope: a check is a claim about the execution, not about one turn.** Counts
sum across turns; places surfaced and named take the maximum, so a closing
"thanks, that's great" does not fail a case whose first turn answered well.

**Outcome, not effort** (D30). Where the application refuses a reasonable
first attempt and the agent recovers, the case widens its bound and the retry
is reported rather than punished. The checker never fails an execution for
taking two calls where one would do, unless the case said so.

A finding is a sentence a reader can act on. "expected search_places before
propose_plan; got propose_plan first" is a finding; "constraint violated" is
not, and the difference is whether someone chasing a failed run has to open
the trace to learn anything.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from src.cases import (
    ALWAYS_ALLOWED_TOOLS,
    Bound,
    BoundLike,
    Case,
    Checks,
    SlotMoved,
    SlotScheduled,
    as_bound,
    fixture_counts,
    minutes_of,
)
from src.execution import Execution, as_mapping

#: Bumped when a rule here changes meaning, never when a message is reworded.
#: `study_case_executions` keeps one outcome per execution, so a re-check under
#: a new version is a new column value and the old verdict is in the record.
CHECKER_VERSION = "checker/1"

PREDICATES_MODULE = "cases.predicates"


@dataclass
class Verdict:
    outcome: str  # 'none' | 'detected'
    findings: list[str] = field(default_factory=list)
    checker_version: str = CHECKER_VERSION
    #: Reported, never asserted (D37, Q22).
    telemetry: dict = field(default_factory=dict)

    @property
    def detected(self) -> bool:
        return self.outcome == "detected"


def _bound_text(bound: Bound) -> str:
    if bound.min is not None and bound.min == bound.max:
        return f"exactly {bound.min}"
    if bound.min is not None and bound.max is not None:
        return f"between {bound.min} and {bound.max}"
    if bound.min is not None:
        return f"at least {bound.min}"
    return f"at most {bound.max}"


def _check_bound(label: str, bound: BoundLike, observed: int, findings: list[str]) -> None:
    b = as_bound(bound)
    if not b.holds(observed):
        findings.append(f"{label}: expected {_bound_text(b)}, got {observed}")


def _is_subsequence(expected: list[str], actual: list[str]) -> bool:
    it = iter(actual)
    return all(tool in it for tool in expected)


def _slot_entries(draft: dict) -> list[dict]:
    """Every slot of a ``propose_plan`` argument object, with its day attached.

    The tool takes ``days[].slots[]`` and the day's date lives on the day, so a
    slot on its own cannot say which day it is on — which is exactly the check
    ``slot_days`` makes.
    """
    entries: list[dict] = []
    for day in draft.get("days") or []:
        date = day.get("day_date") or day.get("date")
        for slot in day.get("slots") or []:
            entries.append({**slot, "_day": date})
    return entries


def _titles_match(a: str, b: str) -> bool:
    """The application's own containment rule (``matchExistingVenue``),
    mirrored: an agent that honours "we already have it" by naming the stop
    has honoured it, and failing that would be a false regression."""
    x, y = (a or "").strip().casefold(), (b or "").strip().casefold()
    return bool(x) and bool(y) and (x in y or y in x)


#: Google returns a place's primary type from a large vocabulary, and several
#: of its values mean the same thing to a member. A case says what it means -
#: "somewhere to stay", "a coffee" - and should not have to enumerate Google's
#: spellings of it.
#:
#: Both halves of this were found by running the suite rather than by reading
#: it. `lodging` and `hotel` share no characters, so a reply that correctly
#: returned a hotel was failed. And a request for a coffee is answered in
#: Sintra with `pastry_shop` - Casa Piriquita and Aurora Queijadas are pastry
#: shops, and they are the right answer - which no amount of string matching
#: relates to `cafe`.
PLACE_TYPE_SYNONYMS: tuple[frozenset[str], ...] = (
    frozenset({
        "lodging", "hotel", "motel", "resort_hotel", "guest_house", "hostel",
        "bed_and_breakfast", "inn", "extended_stay_hotel", "apartment_hotel",
    }),
    frozenset({"restaurant", "food", "meal_takeaway", "meal_delivery", "food_court"}),
    frozenset({
        "cafe", "coffee_shop", "bakery", "pastry_shop", "dessert_shop",
        "tea_house", "breakfast_restaurant", "cafeteria",
    }),
    frozenset({"bar", "pub", "wine_bar", "cocktail_bar", "beer_garden", "bar_and_grill"}),
)


def _type_tokens(value: str) -> set[str]:
    return {part for part in value.lower().strip().split("_") if part}


def _same_place_type(wanted: str, observed: str) -> bool:
    """One Google place type satisfies a case's request for another.

    Three ways: the same value, the wanted type appearing as a **whole word**
    of the observed one (`seafood_restaurant` answers `restaurant`), or both
    values falling in one synonym group.

    Word-wise rather than substring, and the difference is not pedantic:
    `bar` is a substring of `barbecue_restaurant`, so under substring matching
    a case asking for somewhere to drink was satisfied by a grill house. A
    check that passes an incorrect agent is the quieter of D30's two errors
    and the worse one.
    """
    w, o = wanted.lower().strip(), observed.lower().strip()
    if not w or not o:
        return False
    if w == o:
        return True
    if _type_tokens(w) <= _type_tokens(o) or _type_tokens(o) <= _type_tokens(w):
        return True
    return any(w in group and o in group for group in PLACE_TYPE_SYNONYMS)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance. Mirrors `apps/api/src/lib/geo-sanity.ts`, which is
    how the application measures the same thing."""
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _check_places_near(ex: Execution, near: Any, findings: list[str]) -> None:
    """Every named place sits within the radius of the anchor stop.

    The anchor's coordinates come from the fixture, not the case, so a case
    cannot drift away from the trip it is written against.
    """
    from src.cases import fixture

    anchor = next((b for b in fixture()["blocks"] if b["title"] == near.anchor), None)
    if anchor is None:  # the loader refuses this, so it is a harness fault
        findings.append(f"places_near anchor {near.anchor!r} is not in the fixture")
        return
    at = anchor["coordinates"]

    if not ex.place_locations:
        findings.append(
            f"no place the reply named carries a location, so being within "
            f"{near.within_km} km of {near.anchor!r} cannot be evaluated"
        )
        return

    for name, lat, lng in ex.place_locations:
        km = _haversine_km(lat, lng, at["lat"], at["lng"])
        if km > near.within_km:
            findings.append(
                f"{name!r} is {km:.1f} km from {near.anchor!r}, outside the "
                f"{near.within_km} km the request implies"
            )


def _count_mutations(execution: Execution, table: str, op: str) -> int:
    return sum(1 for m in execution.mutations if m["table_name"] == table and m["op"] == op)


def _resolve_count(value: Any, key: str) -> int:
    """``trip_after`` counts: a number, a bound, or the fixture's own (D37)."""
    if value == "fixture":
        return fixture_counts()[key]
    return value


# --- the individual checks -------------------------------------------------


def _check_tools(case: Case, ex: Execution, checks: Checks, findings: list[str]) -> None:
    called = ex.tool_sequence()

    for tool, bound in (checks.tool_counts or {}).items():
        _check_bound(f"{tool} calls", bound, called.count(tool), findings)

    if checks.tools_any_of:
        satisfied = [
            c["tool"]
            for c in ex.trace
            # Ran, returned no error, and did not come back empty-handed. A
            # miss is not an error: the reference tools answer `found: false`
            # with no `error` key, and a source that found nothing answered
            # nothing (D37 put `result_found` in the trace for exactly this).
            if c.get("tool") in checks.tools_any_of
            and not c.get("result_error")
            and c.get("result_found") is not False
        ]
        if not satisfied:
            tried = sorted({c["tool"] for c in ex.trace if c.get("tool") in checks.tools_any_of})
            detail = (
                f"called {tried} but none returned a usable answer"
                if tried
                else f"none of {sorted(checks.tools_any_of)} ran"
            )
            findings.append(f"no source answered this: {detail}")

    if case.expected_tool_sequence and not _is_subsequence(case.expected_tool_sequence, called):
        findings.append(
            f"expected {' before '.join(case.expected_tool_sequence)}; got {called or '(no tool calls)'}"
        )

    allowed = case.allowed_tools()
    if allowed is not None:
        for tool in dict.fromkeys(called):
            if tool not in allowed:
                findings.append(
                    f"called {tool}, which this case does not permit "
                    f"(allowed: {sorted(allowed - set(ALWAYS_ALLOWED_TOOLS))} plus the read tools)"
                )


def _check_errors(ex: Execution, checks: Checks, findings: list[str]) -> None:
    if checks.turn_errors == "none":
        codes = ex.error_codes()
        if codes:
            findings.append(f"the turn did not complete: error_code {codes}")

    if checks.tool_errors is None:
        return
    failed = [c for c in ex.trace if c.get("result_error")]
    if not failed:
        return
    if checks.tool_errors == "none":
        for call in failed:
            findings.append(f"{call['tool']} returned an error: {str(call['result_error'])[:160]}")
        return

    # 'corrected' (D33): every error is recovered from, or was a probe the
    # agent walked away from. A probe cannot be retried — it is capped at one
    # call — so abandoning it is the only recovery available, and often the
    # right one.
    checks_names = set(checks.tools_any_of or [])
    probes = {
        tool
        for tool, bound in (checks.tool_counts or {}).items()
        if as_bound(bound).min == 0 and tool not in checks_names
    }
    for call in failed:
        tool = call["tool"]
        if tool in probes:
            continue  # abandoned, and nothing depends on it
        later = [
            c
            for c in ex.trace
            if c["seq"] > call["seq"]
            and not c.get("result_error")
            and c.get("result_found") is not False
            and (c["tool"] == tool or c["tool"] in checks_names)
        ]
        if not later:
            findings.append(
                f"{tool} failed and nothing recovered it: {str(call['result_error'])[:160]}"
            )


def _check_surfaced(ex: Execution, checks: Checks, findings: list[str]) -> None:
    shapes = ex.state_shapes()
    if checks.places_surfaced is not None:
        observed = max((s.get("places_surfaced") or 0 for s in shapes), default=0)
        _check_bound("places surfaced by search", checks.places_surfaced, observed, findings)
    if checks.places_named is not None:
        observed = max((s.get("reply", {}).get("place_refs") or 0 for s in shapes), default=0)
        _check_bound("places named in the reply", checks.places_named, observed, findings)
    if checks.places_near is not None:
        _check_places_near(ex, checks.places_near, findings)
    if checks.places_named_types:
        have = ex.place_types
        for wanted in checks.places_named_types:
            if not any(_same_place_type(wanted, t) for t in have):
                findings.append(
                    f"the reply names no {wanted!r} place; it named {sorted(have) or 'none'}"
                )


def _check_draft(ex: Execution, checks: Checks, findings: list[str]) -> None:
    wants_draft = any(
        v is not None
        for v in (checks.slot_days, checks.slot_count, checks.draft_slot_starts_between, checks.draft_reuses_blocks)
    )
    if not wants_draft:
        return
    draft = ex.latest_draft
    if draft is None:
        findings.append("no plan was proposed: the case asserts a draft and propose_plan never succeeded")
        return
    slots = _slot_entries(draft)

    if checks.slot_count is not None:
        _check_bound("draft slots", checks.slot_count, len(slots), findings)

    if checks.slot_days is not None:
        wrong = sorted({s["_day"] for s in slots if s.get("_day") not in checks.slot_days})
        if wrong:
            findings.append(f"draft is on {wrong}; the case asks for {checks.slot_days}")

    if checks.draft_slot_starts_between is not None:
        earliest, latest = checks.draft_slot_starts_between
        lo, hi = minutes_of(earliest), minutes_of(latest)
        outside = []
        for slot in slots:
            start = (slot.get("start_time") or "")[:5]
            if not start:
                outside.append(f"{slot.get('block', {}).get('title', '?')} (no start time)")
            elif not lo <= minutes_of(start) <= hi:
                outside.append(f"{slot.get('block', {}).get('title', '?')} at {start}")
        if outside:
            findings.append(f"draft slots outside {earliest}-{latest}: {outside}")

    if checks.draft_reuses_blocks:
        for title in checks.draft_reuses_blocks:
            wanted_id = ex.blocks.get(title)
            reused = any(
                (slot.get("reuse_block_id") and slot["reuse_block_id"] == wanted_id)
                or _titles_match(title, (slot.get("block") or {}).get("title", ""))
                or _titles_match(title, slot.get("title", ""))
                for slot in slots
            )
            if not reused:
                findings.append(
                    f"draft does not build on {title!r}, which the member said the trip already has"
                )


def _check_edits(ex: Execution, checks: Checks, findings: list[str]) -> None:
    if checks.edits is None:
        return
    shapes = ex.state_shapes()
    for op in ("move", "unschedule", "schedule"):
        bound = getattr(checks.edits, op)
        if bound is None:
            continue
        observed = sum((s.get("edits") or {}).get(op) or 0 for s in shapes)
        _check_bound(f"{op} edits", bound, observed, findings)


def _check_slot_moved(ex: Execution, moved: SlotMoved, findings: list[str]) -> None:
    """Where a named stop ended up, read from the mutation the move wrote.

    The projection carries the resolved ``day_date`` alongside the times, which
    is what makes this answerable without a second query: the slot row itself
    holds only a day id.
    """
    block_id = ex.blocks.get(moved.block)
    updates = [
        m
        for m in ex.mutations
        if m["table_name"] == "itinerary_slots"
        and m["op"] == "UPDATE"
        and (not block_id or (m.get("projection") or {}).get("trip_block_id") == block_id)
    ]
    if not updates:
        findings.append(f"{moved.block!r} was never moved: no itinerary_slots update for it")
        return
    final = (updates[-1].get("projection") or {})
    day = final.get("day_date")
    start = (final.get("start_time") or "")[:5]
    end = (final.get("end_time") or "")[:5]

    if day != moved.day:
        findings.append(f"{moved.block!r} ended up on {day}, not {moved.day}")

    if moved.starts_between and start:
        lo, hi = (minutes_of(t) for t in moved.starts_between)
        if not lo <= minutes_of(start) <= hi:
            findings.append(
                f"{moved.block!r} starts at {start}, outside "
                f"{moved.starts_between[0]}-{moved.starts_between[1]}"
            )

    if moved.duration_minutes is not None and start and end:
        _check_bound(f"{moved.block!r} length in minutes", moved.duration_minutes,
                     minutes_of(end) - minutes_of(start), findings)

    if moved.clear_of_other_slots and start and end:
        _check_clear_of_others(ex, moved, day, start, end, findings)


def _check_clear_of_others(
    ex: Execution, moved: SlotMoved, day: Optional[str], start: str, end: str, findings: list[str]
) -> None:
    """Nothing else on that day overlaps the window the stop landed in.

    The other slots' windows come from ``cases/fixture.json`` — the fixture is
    what every repetition builds, ``assert_clean`` verifies the digest before
    the case runs, and the file is hashed into ``suite_version``, so it is the
    authority on where the day's other stops sit. ``fixture_ids`` cannot serve:
    it maps a title to an id and carries no times.

    Any slot this execution *also* moved is then overridden from its mutation
    projection, so the comparison is against where things ended up rather than
    where they started.
    """
    from src.cases import fixture as load_fixture

    moved_id = ex.blocks.get(moved.block)
    windows: dict[str, tuple[str, str, str]] = {}
    for slot in load_fixture().get("slots", []):
        windows[slot["block"]] = (slot["day_date"], slot["start_time"][:5], slot["end_time"][:5])

    id_to_title = {block_id: title for title, block_id in ex.blocks.items()}
    for m in ex.mutations:
        if m["table_name"] != "itinerary_slots" or m["op"] != "UPDATE":
            continue
        proj = m.get("projection") or {}
        title = id_to_title.get(proj.get("trip_block_id"))
        if title and proj.get("day_date"):
            windows[title] = (
                proj["day_date"],
                (proj.get("start_time") or "")[:5],
                (proj.get("end_time") or "")[:5],
            )

    lo, hi = minutes_of(start), minutes_of(end)
    for title, (other_day, other_start, other_end) in windows.items():
        if ex.blocks.get(title) == moved_id or _titles_match(title, moved.block):
            continue
        if other_day != day or not other_start or not other_end:
            continue
        if lo < minutes_of(other_end) and minutes_of(other_start) < hi:
            findings.append(
                f"{moved.block!r} at {start}-{end} overlaps {title!r} at "
                f"{other_start}-{other_end} on {day}"
            )


def _check_slot_scheduled(ex: Execution, want: SlotScheduled, findings: list[str]) -> None:
    """Where a stop the trip already had ended up, read from the INSERT the
    scheduling wrote. `slot_moved` cannot serve: it reads UPDATE rows, and
    putting an unscheduled stop on the itinerary is an INSERT."""
    block_id = ex.blocks.get(want.block)
    inserts = [
        m
        for m in ex.mutations
        if m["table_name"] == "itinerary_slots"
        and m["op"] == "INSERT"
        and (not block_id or (m.get("projection") or {}).get("trip_block_id") == block_id)
    ]
    if not inserts:
        findings.append(f"{want.block!r} was never scheduled: no itinerary_slots insert for it")
        return
    final = inserts[-1].get("projection") or {}
    day = final.get("day_date")
    start = (final.get("start_time") or "")[:5]
    end = (final.get("end_time") or "")[:5]

    if day != want.day:
        findings.append(f"{want.block!r} was scheduled on {day}, not {want.day}")
    if want.starts_between and start:
        lo, hi = (minutes_of(t) for t in want.starts_between)
        if not lo <= minutes_of(start) <= hi:
            findings.append(
                f"{want.block!r} starts at {start}, outside "
                f"{want.starts_between[0]}-{want.starts_between[1]}"
            )
    if want.duration_minutes is not None and start and end:
        _check_bound(f"{want.block!r} length in minutes", want.duration_minutes,
                     minutes_of(end) - minutes_of(start), findings)


def _check_mutations(ex: Execution, checks: Checks, findings: list[str]) -> None:
    for key, bound in (checks.mutation_counts or {}).items():
        table, _, op = key.partition(".")
        _check_bound(f"{key} rows", bound, _count_mutations(ex, table, op), findings)

    for key, allowed in (checks.mutation_changed_keys or {}).items():
        table, _, op = key.partition(".")
        permitted = set(allowed)
        for m in ex.mutations:
            if m["table_name"] != table or m["op"] != op:
                continue
            extra = sorted(set(m.get("changed_keys") or []) - permitted)
            if extra:
                findings.append(
                    f"{key} also changed {extra}; the case permits only {sorted(permitted)}"
                )


def _check_trip_after(ex: Execution, checks: Checks, findings: list[str]) -> None:
    if checks.trip_after is None:
        return
    shapes = ex.state_shapes()
    # The LAST turn's post-state: how much trip there is when the execution ends.
    after = next((s.get("trip_after") for s in reversed(shapes) if s.get("trip_after")), None)
    if after is None:
        findings.append("no post-turn trip state was recorded, so trip_after cannot be evaluated")
        return
    for key in ("blocks", "slots"):
        declared = getattr(checks.trip_after, key)
        if declared is None:
            continue
        _check_bound(f"{key} on the trip afterwards", _resolve_count(declared, key),
                     after.get(key) or 0, findings)


# --- predicates ------------------------------------------------------------


def _load_predicates() -> dict[str, Callable]:
    from src.cases import PREDICATES_FILE

    spec = importlib.util.spec_from_file_location("study_predicates", PREDICATES_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return {name: fn for name, fn in vars(module).items() if callable(fn) and not name.startswith("_")}


def _check_predicates(case: Case, ex: Execution, findings: list[str]) -> None:
    names = case.declared_constraints.predicates
    if not names:
        return
    available = _load_predicates()
    mapping = as_mapping(ex)
    for name in names:
        fn = available.get(name)
        if fn is None:  # the loader refuses this, so it is a harness fault
            findings.append(f"predicate {name!r} is not defined in cases/predicates.py")
            continue
        result = fn(mapping)
        if result:
            findings.append(f"{name}: {result}")


# --- the entry point -------------------------------------------------------


def check(case: Case, execution: Execution) -> Verdict:
    """Evaluate one execution against its case. Never raises on a failed
    check — a failure is a finding, and only a fault in the harness is an
    exception."""
    checks = case.declared_constraints.checks
    findings: list[str] = []

    _check_tools(case, execution, checks, findings)
    _check_errors(execution, checks, findings)
    _check_surfaced(execution, checks, findings)
    _check_draft(execution, checks, findings)
    _check_edits(execution, checks, findings)
    if checks.slot_moved is not None:
        _check_slot_moved(execution, checks.slot_moved, findings)
    if checks.slot_scheduled is not None:
        _check_slot_scheduled(execution, checks.slot_scheduled, findings)
    _check_mutations(execution, checks, findings)
    _check_trip_after(execution, checks, findings)
    _check_predicates(case, execution, findings)

    return Verdict(
        outcome="detected" if findings else "none",
        findings=findings,
        telemetry=execution.telemetry,
    )


def check_run(run_id: str, *, persist: bool = True) -> list[tuple[dict, Verdict]]:
    """Every execution of one run, checked against its case.

    What B10 and B11 call, and what a re-check under a new ``CHECKER_VERSION``
    calls: the executions are read back from the record, so a verdict can be
    recomputed long after the run without re-running anything.

    A metamorphic follow-up is handed its seed's execution at the same
    repetition as ``base`` (D27) — the comparison predicates need the other
    execution in hand, and pairing repetition to repetition keeps the two
    draws independent in the same way.
    """
    from src import db, execution as exmod
    from src.cases import load_cases

    cases = {c.case_id: c for c in load_cases()}
    rows = (
        db.admin()
        .table("study_case_executions")
        .select("*")
        .eq("run_id", run_id)
        .order("case_id")
        .execute()
        .data
    )
    by_key = {(r["case_id"], r["repetition"]): r for r in rows}
    loaded: dict[tuple[str, int], Any] = {}

    def execution_for(row: dict):
        key = (row["case_id"], row["repetition"])
        if key not in loaded:
            base_row = (
                by_key.get((row["base_case_id"], row["repetition"]))
                if row.get("base_case_id")
                else None
            )
            base = execution_for(base_row) if base_row else None
            loaded[key] = exmod.load(row, base=base)
        return loaded[key]

    results: list[tuple[dict, Verdict]] = []
    for row in rows:
        case = cases.get(row["case_id"])
        if case is None:  # the suite moved on; the record still stands
            continue
        verdict = check(case, execution_for(row))
        if persist:
            record(row["id"], verdict)
        results.append((row, verdict))
    return results


def record(execution_row_id: str, verdict: Verdict) -> None:
    """Write the verdict where the execution is (D27, and the author's ruling
    of 2026-09-21): outcome and findings beside each other on
    ``study_case_executions``. ``study_verdicts`` is the participant round's,
    for verdicts computed after the fact over rows that have no case."""
    from src import db

    db.admin().table("study_case_executions").update(
        {
            "structural_outcome": verdict.outcome,
            "structural_findings": verdict.findings,
        }
    ).eq("id", execution_row_id).execute()
