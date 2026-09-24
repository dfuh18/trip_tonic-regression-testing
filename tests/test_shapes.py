"""Tests for ``src.shapes`` — the candidate request-shape rules (Q28).

Traces are built literally, in the shape ``study_suggestions.tool_call_trace``
stores them (``llm`` entries interleaved with ``tool`` entries).
"""

from __future__ import annotations

import pytest

from src.shapes import (
    ADVISORY,
    OTHER,
    RULES,
    d09,
    declared_label,
    families,
    interaction_label,
    shapes7,
    shapes9,
    tools_of,
)


def test_tools_of_skips_llm_entries_and_orders_by_seq() -> None:
    trace = [
        {"kind": "llm", "seq": 1},
        {"kind": "tool", "seq": 3, "tool": "propose_plan"},
        {"kind": "tool", "seq": 2, "tool": "search_places"},
        {"kind": "llm", "seq": 4},
    ]
    assert tools_of(trace) == ["search_places", "propose_plan"]


@pytest.mark.parametrize("tools, seven, nine", [
    ([], ADVISORY, ADVISORY),
    (["get_itinerary", "list_trip_blocks"], ADVISORY, ADVISORY),
    (["read_wikipedia"], "factual.reference", "factual.reference"),
    (["get_region_climate", "get_climate_normals"], "factual.climate", "factual.climate"),
    (["get_weather"], "factual.forecast", "factual.forecast"),
    (["search_places", "search_places"], "venue.search", "venue.search"),
    (["search_places", "propose_plan"], "scheduling.draft", "scheduling.draft"),
    (["move_slot"], "scheduling.edit", "scheduling.move"),
    (["schedule_block"], "scheduling.edit", "scheduling.place"),
    (["unschedule_block"], "scheduling.edit", "scheduling.remove"),
    # Mixed turns are other, never resolved by precedence.
    (["get_weather", "move_slot"], OTHER, OTHER),
    (["read_wikipedia", "search_places"], OTHER, OTHER),
    (["propose_plan", "move_slot"], OTHER, OTHER),
    # Two kinds of live edit: one shape at 7, two at 9.
    (["move_slot", "unschedule_block"], "scheduling.edit", OTHER),
    # A tool the rule does not know is other, not guessed.
    (["book_a_table"], OTHER, OTHER),
])
def test_shapes(tools, seven, nine) -> None:
    assert shapes7(tools) == seven
    assert shapes9(tools) == nine


def test_d09_is_a_precedence_with_advisory_fall_through() -> None:
    assert d09(["get_weather", "move_slot"]) == "scheduling"
    assert d09(["read_wikipedia", "search_places"]) == "venue_lookup"
    assert d09(["get_region_climate"]) == "factual_qa"
    assert d09(["get_itinerary"]) == ADVISORY


def test_families_is_the_composite() -> None:
    assert families(["search_places", "propose_plan"]) == "scheduling+venue_lookup"
    assert families([]) == ADVISORY


def test_interaction_ignores_a_closing_turn_that_called_nothing() -> None:
    assert interaction_label(["factual.climate", ADVISORY]) == "factual.climate"
    assert interaction_label([ADVISORY, ADVISORY]) == ADVISORY
    assert interaction_label(["venue.search", "scheduling.draft"]) == OTHER


def test_declared_label_reads_a_disjunction_as_one_tool() -> None:
    group = frozenset({"get_region_climate", "get_climate_normals"})
    assert declared_label(set(), [group], "shapes7") == "factual.climate"
    assert declared_label({"search_places", "propose_plan"}, [], "shapes9") == "scheduling.draft"
    assert declared_label(set(), [], "d09") == ADVISORY


def test_declared_label_refuses_a_group_that_straddles_shapes() -> None:
    with pytest.raises(AssertionError):
        declared_label(set(), [frozenset({"get_weather", "read_wikipedia"})], "shapes7")


def test_every_rule_is_registered() -> None:
    assert set(RULES) == {"d09", "shapes7", "shapes9", "families"}


def test_segment_splits_on_a_change_of_acting_label() -> None:
    from src.shapes import segment

    labels = ["venue.search", ADVISORY, "factual.climate", "factual.climate", ADVISORY]
    assert segment(labels) == [[0, 1], [2, 3, 4]]


def test_segment_gives_an_opening_no_tool_turn_its_own_request() -> None:
    from src.shapes import segment

    assert segment([ADVISORY, ADVISORY, "venue.search"]) == [[0, 1], [2]]
    assert segment([]) == []


def test_segment_cannot_see_two_same_label_requests() -> None:
    from src.shapes import segment

    assert segment(["venue.search", ADVISORY, "venue.search"]) == [[0, 1, 2]]


# --- segment_with: slash and reference as optional signals -----------------

from src.shapes import TurnSignals, segment, segment_with, signals_of  # noqa: E402


def T(label, intent=None, acted=(), offered=()):
    return TurnSignals(label, intent, frozenset(acted), frozenset(offered))


def test_segment_with_no_signals_is_segment_exactly() -> None:
    labels = ["venue.search", ADVISORY, "venue.search", "factual.climate", ADVISORY,
              "scheduling.draft", "scheduling.draft", ADVISORY]
    turns = [T(x) for x in labels]
    assert segment_with(turns, use_intent=False, use_reference=False) == segment(labels)
    assert segment_with([T(ADVISORY), T("venue.search")], use_intent=False, use_reference=False) == [[0], [1]]


def test_a_reference_joins_a_shape_change() -> None:
    """Search, then "add the second one": the draft acts on a place the search
    offered, so it is one request although the shape changed."""
    turns = [T("venue.search", "find", offered={"ChIJ-a", "ChIJ-b"}),
             T("scheduling.draft", acted={"ChIJ-b"}, offered={"ChIJ-b"})]
    assert segment_with(turns) == [[0, 1]]
    assert segment_with(turns, use_reference=False) == [[0], [1]]


def test_a_reference_outranks_a_slash() -> None:
    turns = [T("venue.search", "find", offered={"ChIJ-a"}),
             T("scheduling.draft", "plan", acted={"ChIJ-a"})]
    assert segment_with(turns) == [[0, 1]]


def test_a_slash_splits_two_requests_of_one_shape() -> None:
    """The blind spot of the shape rule: two searches in a row."""
    turns = [T("venue.search", "find", offered={"ChIJ-a"}), T("venue.search", "find", offered={"ChIJ-z"})]
    assert segment_with(turns) == [[0], [1]]
    assert segment_with(turns, use_intent=False) == [[0, 1]]


def test_no_slash_is_no_evidence() -> None:
    turns = [T("venue.search", offered={"ChIJ-a"}), T("venue.search", offered={"ChIJ-z"})]
    assert segment_with(turns) == [[0, 1]]


def test_a_reference_only_reaches_back_to_the_current_request() -> None:
    turns = [T("venue.search", "find", offered={"ChIJ-a"}),
             T("factual.climate", "find"),
             T("scheduling.draft", acted={"ChIJ-a"})]
    assert segment_with(turns) == [[0], [1], [2]]


def test_a_revised_draft_after_a_joined_turn_stays_in_the_request() -> None:
    turns = [T("venue.search", "find", offered={"ChIJ-a"}),
             T("scheduling.draft", acted={"ChIJ-a"}),
             T("scheduling.draft")]
    assert segment_with(turns) == [[0, 1, 2]]


def test_ids_match_by_the_applications_eight_character_prefix() -> None:
    turns = [T("scheduling.draft", "plan", offered={"bc224bfd-1111-2222-3333-444455556666"}),
             T("scheduling.edit", acted={"bc224bfd"})]
    assert segment_with(turns) == [[0, 1]]
    short = [T("scheduling.draft", "plan", offered={"bc22"}), T("scheduling.edit", acted={"bc22ffff"})]
    assert segment_with(short) == [[0], [1]]


def test_signals_are_read_from_the_recorded_shapes() -> None:
    trace = [
        {"kind": "llm", "seq": 1},
        {"kind": "tool", "seq": 2, "tool": "get_itinerary", "args": {}},
        {"kind": "tool", "seq": 3, "tool": "propose_plan", "args": {"days": [{"slots": [
            {"block": {"title": "Dinner", "google_place_id": "ChIJ-b"}},
            {"block": {"title": "Monastery", "reuse_block_id": "bc224bfd"}},
        ]}]}},
    ]
    s = signals_of(trace, ["ChIJ-b"], None)
    assert s.label == "scheduling.draft"
    assert s.intent is None
    assert s.acted_on == {"ChIJ-b", "bc224bfd"}
    assert s.offered == {"ChIJ-b", "bc224bfd"}
