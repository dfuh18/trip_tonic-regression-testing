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
        place_types=set(),
        place_locations=[],
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


def test_a_venue_in_the_wrong_town_is_detected_by_distance():
    """The check that makes a day-change case mean something.

    `different_venues_from_base` is satisfied by two different *Sintra*
    restaurants when the member asked about Lisbon — the exact answer a day
    change is supposed to rule out. Only distance says the agent answered
    about the right place.
    """
    lunch = case(
        declared_constraints={
            "checks": {"places_near": {"anchor": "Hotel near Baixa", "within_km": 5}},
            "predicates": [],
        },
    )
    # Sintra: Pena Palace is 23.5 km from the fixture's Baixa hotel.
    in_sintra = execution(place_locations=[("Tasco do Strauss", 38.7920, -9.3900)])
    verdict = check(lunch, in_sintra)
    assert verdict.outcome == "detected"
    assert any("km from 'Hotel near Baixa'" in f for f in verdict.findings)

    in_baixa = execution(place_locations=[("Taberna da Baixa", 38.7110, -9.1390)])
    assert check(lunch, in_baixa).outcome == "none"


def test_the_geographic_check_says_so_when_it_cannot_be_evaluated():
    """A reply that named no located place must not pass by silence — the
    whole point is that the answer is somewhere."""
    lunch = case(
        declared_constraints={
            "checks": {"places_near": {"anchor": "Pena Palace", "within_km": 8}},
            "predicates": [],
        },
    )
    verdict = check(lunch, execution(place_locations=[]))
    assert verdict.outcome == "detected"
    assert any("cannot be evaluated" in f for f in verdict.findings)


def test_a_hotel_satisfies_a_request_for_lodging():
    """Google reports the same thing as `lodging` and as `hotel`, and a case
    should not have to know which. Substring matching cannot bridge them —
    they share no characters — which is how a correct answer was once failed.
    """
    stay = case(
        declared_constraints={
            "checks": {"places_named_types": ["restaurant", "lodging"]},
            "predicates": [],
        },
    )
    ex = execution(place_types={"hotel", "seafood_restaurant"})
    assert check(stay, ex).outcome == "none"

    no_stay = execution(place_types={"seafood_restaurant", "restaurant"})
    verdict = check(stay, no_stay)
    assert verdict.outcome == "detected"
    assert any("'lodging'" in f for f in verdict.findings)


# --- continuity across turns (Q30) -----------------------------------------


def _picking_case(**checks):
    return case(
        function="scheduling",
        expected_tool_sequence=["search_places", "propose_plan"],
        declared_constraints={"checks": checks, "predicates": []},
    )


def _draft(place_id, day="2026-11-07", start="20:00", end="21:30"):
    return {"days": [{"day_date": day, "slots": [
        {"start_time": start, "end_time": end, "block": {"title": "Dinner", "google_place_id": place_id}},
    ]}]}


def test_a_draft_of_a_place_offered_earlier_passes():
    ex = execution(
        trace=[tool(1, "search_places"), tool(2, "propose_plan", turn=2)],
        drafts=[_draft("ChIJ-b")], draft_turns=[2],
        place_ids_by_turn={1: {"ChIJ-a", "ChIJ-b"}, 2: {"ChIJ-b"}},
    )
    verdict = check(_picking_case(draft_uses_earlier_place=True), ex)
    assert verdict.outcome == "none", verdict.findings


def test_a_draft_of_a_place_nobody_offered_is_detected():
    """The agent searched afresh on the drafting turn and drafted what that
    search found; the reply on the same turn naming it does not count."""
    ex = execution(
        trace=[tool(1, "search_places"), tool(2, "search_places", turn=2), tool(3, "propose_plan", turn=2)],
        drafts=[_draft("ChIJ-z")], draft_turns=[2],
        place_ids_by_turn={1: {"ChIJ-a", "ChIJ-b"}, 2: {"ChIJ-z"}},
    )
    verdict = check(_picking_case(draft_uses_earlier_place=True), ex)
    assert verdict.outcome == "detected"
    assert any("offered on an earlier turn" in f for f in verdict.findings)


def test_a_draft_on_the_first_turn_had_nothing_to_pick_from():
    ex = execution(
        trace=[tool(1, "search_places"), tool(2, "propose_plan")],
        drafts=[_draft("ChIJ-a")], draft_turns=[1],
        place_ids_by_turn={1: {"ChIJ-a"}},
    )
    verdict = check(_picking_case(draft_uses_earlier_place=True), ex)
    assert verdict.outcome == "detected"
    assert any("nothing was offered" in f for f in verdict.findings)


def _moving_case():
    return case(
        function="scheduling",
        expected_tool_sequence=["search_places", "propose_plan", "move_slot"],
        declared_constraints={"checks": {"slot_moved": {
            "block": "Tram 28 ride through Alfama", "day": "2026-11-06", "after_latest_draft": True,
        }}, "predicates": []},
    )


def _move(start, end):
    return {"table_name": "itinerary_slots", "op": "UPDATE", "row_id": "slot-tram",
            "changed_keys": ["start_time", "end_time"], "origin_kind": "agent_live_edit",
            "projection": {"trip_block_id": "block-tram", "day_date": "2026-11-06",
                           "start_time": start, "end_time": end}}


def test_a_stop_moved_to_after_the_draft_passes():
    ex = execution(
        trace=[tool(1, "search_places"), tool(2, "propose_plan"), tool(3, "move_slot", turn=2)],
        drafts=[_draft("ChIJ-a", day="2026-11-06", start="14:30", end="17:00")], draft_turns=[1],
        mutations=[_move("17:00:00", "18:00:00")],
    )
    verdict = check(_moving_case(), ex)
    assert verdict.outcome == "none", verdict.findings


def test_a_stop_moved_into_the_draft_is_detected():
    ex = execution(
        trace=[tool(1, "search_places"), tool(2, "propose_plan"), tool(3, "move_slot", turn=2)],
        drafts=[_draft("ChIJ-a", day="2026-11-06", start="14:30", end="17:00")], draft_turns=[1],
        mutations=[_move("16:00:00", "17:00:00")],
    )
    verdict = check(_moving_case(), ex)
    assert verdict.outcome == "detected"
    assert any("before the draft" in f and "17:00" in f for f in verdict.findings)


# --- the two probe-found check faults (287e7780) ---------------------------


def test_the_moved_stop_is_not_compared_against_its_own_slot_in_a_redraft():
    redraft = {"days": [{"day_date": "2026-11-06", "slots": [
        {"start_time": "14:30", "end_time": "17:15", "block": {"title": "Castle", "google_place_id": "ChIJ-a"}},
        {"start_time": "17:30", "end_time": "18:30",
         "block": {"title": "Tram 28 ride through Alfama", "reuse_block_id": "block-tr"}},
    ]}]}
    ex = execution(
        trace=[tool(1, "search_places"), tool(2, "propose_plan"), tool(3, "move_slot", turn=2),
               tool(4, "propose_plan", turn=2)],
        drafts=[redraft], draft_turns=[2],
        mutations=[_move("17:30:00", "18:30:00")],
    )
    verdict = check(_moving_case(), ex)
    assert verdict.outcome == "none", verdict.findings


def _near_case():
    return case(
        function="scheduling",
        expected_tool_sequence=["search_places", "propose_plan"],
        declared_constraints={"checks": {"places_near": {
            "anchor": "Tram 28 ride through Alfama", "within_km": 3}}, "predicates": []},
    )


def test_a_drafting_turn_is_located_by_what_it_drafted_not_by_every_ref():
    """The reply named "Santo António"; the application also attached a
    same-named bakery 6.7 km away. The draft held the Alfama one."""
    alfama, lumiar = (38.7114, -9.1330), (38.7740, -9.1601)
    ex = execution(
        trace=[tool(1, "search_places"), tool(2, "propose_plan")],
        drafts=[_draft("ChIJ-alfama", day="2026-11-06")], draft_turns=[1],
        place_refs_by_turn={1: [("Santo António", *alfama, "ChIJ-alfama"),
                                ("Pastelaria Santo António", *lumiar, "ChIJ-lumiar")]},
    )
    assert check(_near_case(), ex).outcome == "none"


def test_a_turn_that_only_searched_is_still_located_by_every_ref():
    lumiar = (38.7740, -9.1601)
    ex = execution(
        trace=[tool(1, "search_places")],
        place_refs_by_turn={1: [("Far away", *lumiar, "ChIJ-lumiar")]},
    )
    verdict = check(_near_case(), ex)
    assert any("Far away" in f for f in verdict.findings)
