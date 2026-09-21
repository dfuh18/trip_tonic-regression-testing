"""The structural checker (B08).

Hand-built executions, so each test states exactly the one thing it is about.
The shapes here are the shapes the application actually records — they were
copied from a probe run's rows, not invented, which is the mistake L05 is about.
"""
import pytest

from src.cases import Case
from src.checker import check
from src.execution import Execution

FIXTURE_BLOCKS = {
    "Tram 28 ride through Alfama": "block-tram",
    "Jerónimos Monastery": "block-monastery",
    "Pena Palace": "block-pena",
    "Time Out Market lunch": "block-market",
    "Hotel near Baixa": "block-hotel",
}


def tool(seq, name, args=None, error=None, found=None, turn=1):
    return {
        "seq": seq,
        "kind": "tool",
        "tool": name,
        "args": args or {},
        "result_error": error,
        "result_chars": 100,
        "result_found": found,
        "turn_index": turn,
    }


def turn_row(index=1, *, shape=None, error_code=None):
    return {
        "turn_index": index,
        "error_code": error_code,
        "llm_calls": 2,
        "tool_calls": 1,
        "latency_ms": 3000,
        "tokens_input": 100,
        "tokens_output": 50,
        "retry_count": 0,
        "resulting_state_shape": shape
        if shape is not None
        else {
            "draft": None,
            "edits": {"move": 0, "schedule": 0, "unschedule": 0},
            "reply": {"chars": 600, "draft_refs": 0, "place_refs": 3},
            "trip_after": {"blocks": 5, "slots": 3},
            "places_surfaced": 5,
        },
    }


def execution(**kwargs) -> Execution:
    base = dict(
        case_id="venue_lookup_sintra_lunch",
        repetition=1,
        turns=[turn_row()],
        trace=[tool(1, "search_places")],
        mutations=[],
        drafts=[],
        place_ids={"ChIJ-a", "ChIJ-b"},
        blocks=dict(FIXTURE_BLOCKS),
        fixture_ids={"blocks": dict(FIXTURE_BLOCKS)},
        telemetry={"turns": 1},
    )
    base.update(kwargs)
    return Execution(**base)


def case(**kwargs) -> Case:
    base = dict(
        case_id="venue_lookup_sintra_lunch",
        provenance="seeded",
        run_priority=1,
        function="venue_lookup",
        user_profile="Tom, 41.",
        goal="Lunch near the palace.",
        opening_turn="/find lunch near the palace",
        intent="find",
        expected_tool_sequence=["search_places"],
        declared_constraints={
            "checks": {
                "tool_counts": {"search_places": {"min": 1, "max": 3}},
                "places_surfaced": {"min": 1},
                "places_named": {"min": 2},
                "tool_errors": "none",
                "turn_errors": "none",
                "mutation_counts": {"trip_blocks.INSERT": 0},
                "trip_after": {"blocks": "fixture", "slots": "fixture"},
            },
            "predicates": [],
        },
        scoring_criteria=["Names real places."],
        repetitions_n=8,
    )
    base.update(kwargs)
    return Case.model_validate(base)


# --- the two the spec's done-when names ------------------------------------


def test_a_passing_execution_is_none():
    verdict = check(case(), execution())
    assert verdict.outcome == "none", verdict.findings
    assert verdict.findings == []


def test_a_missing_tool_call_is_detected_and_named():
    verdict = check(case(), execution(trace=[]))
    assert verdict.outcome == "detected"
    assert any("search_places" in f for f in verdict.findings)


def test_a_draft_on_the_wrong_day_is_detected_and_named():
    """The check the recorded state shape could not have made: it carries slot
    counts and no dates, so a Belém morning drafted onto the Sintra day would
    have passed everything else."""
    drafting = case(
        function="scheduling",
        intent="plan",
        expected_tool_sequence=["search_places", "propose_plan"],
        declared_constraints={
            "checks": {"slot_days": ["2026-11-07"], "slot_count": {"min": 2, "max": 4}},
            "predicates": [],
        },
    )
    ex = execution(
        trace=[tool(1, "search_places"), tool(2, "propose_plan")],
        drafts=[{"days": [{"day_date": "2026-11-08", "slots": [
            {"start_time": "09:00", "block": {"title": "A"}},
            {"start_time": "10:30", "block": {"title": "B"}},
        ]}]}],
    )
    verdict = check(drafting, ex)
    assert verdict.outcome == "detected"
    assert any("2026-11-08" in f and "2026-11-07" in f for f in verdict.findings)


# --- the rules that are easy to get subtly wrong ---------------------------


def test_a_source_that_found_nothing_has_not_answered():
    """`tools_any_of` means ran AND came back with something. The reference
    tools report a miss as `found: false` with no error, which is why the
    trace carries `result_found` at all (D37)."""
    qa = case(
        function="factual_qa",
        intent=None,
        expected_tool_sequence=[],
        declared_constraints={"checks": {"tools_any_of": ["read_wikipedia"]}, "predicates": []},
        references=[{"title": "Alfama", "path": "alfama_history.md"}],
    )
    missed = execution(trace=[tool(1, "read_wikipedia", found=False)])
    assert check(qa, missed).outcome == "detected"

    hit = execution(trace=[tool(1, "read_wikipedia", found=True)])
    assert check(qa, hit).outcome == "none"


def test_an_unexpected_tool_is_detected_because_a_case_denies_by_default():
    """D28: a case permits what it names plus the read tools. Everything else
    is a behaviour change, which is what a regression run exists to notice."""
    verdict = check(case(), execution(trace=[tool(1, "search_places"), tool(2, "propose_plan")]))
    assert verdict.outcome == "detected"
    assert any("propose_plan" in f and "does not permit" in f for f in verdict.findings)


def test_a_read_tool_is_never_an_unexpected_call():
    """The agent reaches for these when its preloaded context falls short, and
    that varies between runs of one case — failing on it would be failing on
    variance rather than on a regression (D28)."""
    ex = execution(trace=[tool(1, "get_itinerary"), tool(2, "search_places")])
    assert check(case(), ex).outcome == "none"


def test_an_abandoned_probe_counts_as_the_correction():
    """D33 as amended: a probe is capped at one call so it cannot be retried,
    and walking away from a source that could not answer is the only recovery
    available."""
    weather = case(
        function="factual_qa",
        intent=None,
        expected_tool_sequence=[],
        declared_constraints={
            "checks": {
                "tool_counts": {"get_weather": {"min": 0, "max": 1}},
                "tools_any_of": ["get_region_climate"],
                "tool_errors": "corrected",
            },
            "predicates": [],
        },
        references=[{"title": "Lisbon", "path": "lisbon_climate.md"}],
    )
    ex = execution(trace=[
        tool(1, "get_weather", error="Open-Meteo error: 400"),
        tool(2, "get_region_climate", found=True),
    ])
    assert check(weather, ex).outcome == "none"


def test_an_error_nothing_recovers_is_detected():
    weather = case(
        function="factual_qa",
        intent=None,
        expected_tool_sequence=[],
        declared_constraints={
            "checks": {"tools_any_of": ["get_region_climate"], "tool_errors": "corrected"},
            "predicates": [],
        },
        references=[{"title": "Lisbon", "path": "lisbon_climate.md"}],
    )
    ex = execution(trace=[tool(1, "get_region_climate", error="boom")])
    verdict = check(weather, ex)
    assert verdict.outcome == "detected"
    assert any("nothing recovered it" in f for f in verdict.findings)


def test_a_turn_that_did_not_complete_is_detected():
    """`empty_reply` and `llm_error` come back as a turn that produced nothing;
    without this the simulator answers the blank in character and every other
    check of a read-only case passes against a trip nothing touched."""
    ex = execution(turns=[turn_row(error_code="llm_error")])
    verdict = check(case(), ex)
    assert verdict.outcome == "detected"
    assert any("did not complete" in f for f in verdict.findings)


def test_a_write_that_touched_more_columns_than_the_case_permits():
    """`mutation_changed_keys` reads like D28 reads tools: only the listed
    columns may change, and a listed one that did not is not a failure."""
    move = case(
        function="scheduling",
        intent="reschedule",
        expected_tool_sequence=["move_slot"],
        declared_constraints={
            "checks": {
                "mutation_changed_keys": {
                    "itinerary_slots.UPDATE": ["itinerary_day_id", "start_time", "end_time"]
                }
            },
            "predicates": [],
        },
    )
    clean = execution(trace=[tool(1, "move_slot")], mutations=[{
        "id": "m1", "table_name": "itinerary_slots", "op": "UPDATE",
        "changed_keys": ["itinerary_day_id", "start_time"], "projection": {}, "origin_kind": "agent_live_edit",
    }])
    assert check(move, clean).outcome == "none"

    sneaky = execution(trace=[tool(1, "move_slot")], mutations=[{
        "id": "m1", "table_name": "itinerary_slots", "op": "UPDATE",
        "changed_keys": ["itinerary_day_id", "start_time", "is_locked"], "projection": {},
        "origin_kind": "agent_live_edit",
    }])
    verdict = check(move, sneaky)
    assert verdict.outcome == "detected"
    assert any("is_locked" in f for f in verdict.findings)


def test_trip_after_fixture_resolves_to_the_fixtures_own_counts():
    """`blocks: fixture` says "as many as we started with" rather than a number
    that silently stops matching when the fixture changes."""
    grown = execution(turns=[turn_row(shape={
        "draft": None,
        "edits": {"move": 0, "schedule": 0, "unschedule": 0},
        "reply": {"chars": 600, "draft_refs": 0, "place_refs": 3},
        "trip_after": {"blocks": 6, "slots": 3},
        "places_surfaced": 5,
    })])
    verdict = check(case(), grown)
    assert verdict.outcome == "detected"
    assert any("blocks on the trip afterwards" in f for f in verdict.findings)


def test_a_check_describes_the_execution_and_not_one_turn():
    """Counts sum across turns and places take the maximum, so a closing
    "thanks, that's great" does not fail a case whose first turn answered."""
    quiet_closer = turn_row(index=2, shape={
        "draft": None,
        "edits": {"move": 0, "schedule": 0, "unschedule": 0},
        "reply": {"chars": 40, "draft_refs": 0, "place_refs": 0},
        "trip_after": {"blocks": 5, "slots": 3},
        "places_surfaced": 0,
    })
    ex = execution(turns=[turn_row(), quiet_closer])
    assert check(case(), ex).outcome == "none"


def test_telemetry_is_reported_and_never_asserted():
    """D37/Q22: the five signals travel with the verdict, and no case can
    bound them — there is no baseline to bound them against yet."""
    verdict = check(case(), execution(telemetry={"turns": 1, "llm_calls": 9, "reply_chars_max": 40}))
    assert verdict.outcome == "none"
    assert verdict.telemetry["llm_calls"] == 9
