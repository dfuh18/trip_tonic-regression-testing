"""Tests for ``src.signature``.

Every case builds a trace literally, in the shape ``study_suggestions.
tool_call_trace`` stores it, so the suite pins the rule rather than the
implementation's own helpers.
"""

from __future__ import annotations

from src.signature import SIGNATURE_RULE_VERSION, signature

REQUEST_TYPE = "venue_lookup"


def call(seq: int, tool: str, **args: object) -> dict:
    return {"seq": seq, "tool": tool, "args": dict(args)}


def a_trace() -> list[dict]:
    return [
        call(1, "search_places", query="pizza in Rome", lat=41.9, lng=12.5),
        call(2, "propose_plan", days=[{"day_date": "2026-07-01", "slots": []}]),
    ]


def test_rule_version_is_recorded() -> None:
    """That a version is declared, not which one it is (D80).

    Bumping the signature rule is a planned, versioned act — D24 says results
    computed under different versions are not comparable, which is an argument
    for recording it, not for freezing it. Pinning the literal would fail the
    first time someone did the thing the constant exists to support.
    """
    import re

    assert re.fullmatch(r"\d+", SIGNATURE_RULE_VERSION), SIGNATURE_RULE_VERSION


def test_identical_traces_give_equal_signatures() -> None:
    assert signature(a_trace(), 2, REQUEST_TYPE) == signature(a_trace(), 2, REQUEST_TYPE)


def test_a_signature_is_hashable() -> None:
    # Coverage is a set membership test in 06_analysis, so the value has to be
    # usable as a dict key.
    assert len({signature(a_trace(), 2, REQUEST_TYPE), signature(a_trace(), 2, REQUEST_TYPE)}) == 1


def test_request_type_is_part_of_the_signature() -> None:
    assert signature(a_trace(), 2, "venue_lookup") != signature(a_trace(), 2, "scheduling")


def test_a_reordered_sequence_differs() -> None:
    forward = [call(1, "search_places", query="x"), call(2, "propose_plan", title="y")]
    reversed_ = [call(1, "propose_plan", title="y"), call(2, "search_places", query="x")]
    assert signature(forward, 1, REQUEST_TYPE) != signature(reversed_, 1, REQUEST_TYPE)


def test_the_trace_is_read_in_seq_order_not_list_order() -> None:
    ordered = [call(1, "search_places", query="x"), call(2, "propose_plan", title="y")]
    shuffled = [ordered[1], ordered[0]]
    assert signature(shuffled, 1, REQUEST_TYPE) == signature(ordered, 1, REQUEST_TYPE)


def test_consecutive_duplicates_collapse() -> None:
    trace = [
        call(1, "search_places", query="a"),
        call(2, "search_places", query="b"),
        call(3, "get_weather", lat=1, lng=2),
        call(4, "search_places", query="c"),
    ]
    assert signature(trace, 1, REQUEST_TYPE)[1] == ("search_places", "get_weather", "search_places")


def test_non_consecutive_repeats_are_kept() -> None:
    trace = [
        call(1, "search_places", query="a"),
        call(2, "get_weather", lat=1, lng=2),
        call(3, "search_places", query="b"),
    ]
    collapsed = [
        call(1, "search_places", query="a"),
        call(2, "search_places", query="b"),
        call(3, "get_weather", lat=1, lng=2),
    ]
    assert signature(trace, 1, REQUEST_TYPE)[1] != signature(collapsed, 1, REQUEST_TYPE)[1]


def test_counts_bucket_at_one_two_and_three_plus() -> None:
    def counts_for(n: int) -> tuple:
        trace = [call(i + 1, "search_places", query=str(i)) for i in range(n)]
        return signature(trace, 1, REQUEST_TYPE)[2]

    assert counts_for(1) == (("search_places", "1"),)
    assert counts_for(2) == (("search_places", "2"),)
    assert counts_for(3) == (("search_places", "3+"),)
    assert counts_for(4) == (("search_places", "3+"),)


def test_counts_are_sorted_and_per_tool() -> None:
    trace = [
        call(1, "search_places", query="a"),
        call(2, "get_weather", lat=1, lng=2),
        call(3, "search_places", query="b"),
    ]
    assert signature(trace, 1, REQUEST_TYPE)[2] == (
        ("get_weather", "1"),
        ("search_places", "2"),
    )


def test_counts_ignore_the_order_calls_arrive_in() -> None:
    interleaved = [
        call(1, "search_places", query="a"),
        call(2, "get_weather", lat=1, lng=2),
        call(3, "search_places", query="b"),
    ]
    grouped = [
        call(1, "search_places", query="a"),
        call(2, "search_places", query="b"),
        call(3, "get_weather", lat=1, lng=2),
    ]
    assert signature(interleaved, 1, REQUEST_TYPE)[2] == signature(grouped, 1, REQUEST_TYPE)[2]


def test_turns_bucket_at_one_two_and_three_plus() -> None:
    def bucket_for(turns: int) -> str:
        return signature([call(1, "search_places", query="x")], turns, REQUEST_TYPE)[3]

    assert bucket_for(1) == "1"
    assert bucket_for(2) == "2"
    assert bucket_for(3) == "3+"
    assert bucket_for(4) == "3+"


def test_an_empty_trace_is_a_signature() -> None:
    # Advisory turns call no tool at all; they still have a shape.
    assert signature([], 1, "advisory") == ("advisory", (), (), "1", (False, False, False, False))


def test_has_location_from_coordinates_only() -> None:
    trace = [call(1, "get_weather", lat=41.9, lng=12.5)]
    assert signature(trace, 1, REQUEST_TYPE)[4] == (True, False, False, False)


def test_has_location_from_an_address_without_a_day_date() -> None:
    trace = [call(1, "add_block", address="Via Appia 1")]
    assert signature(trace, 1, REQUEST_TYPE)[4] == (True, False, False, False)


def test_an_address_inside_a_proposed_day_is_not_a_location() -> None:
    trace = [
        call(
            1,
            "propose_plan",
            days=[{"day_date": "2026-07-01", "slots": [{"block": {"address": "Via Appia 1"}}]}],
        )
    ]
    # The day's own date still sets has_date; only has_location is withheld.
    assert signature(trace, 1, "scheduling")[4] == (False, True, False, False)


def test_a_lone_latitude_is_not_a_location() -> None:
    trace = [call(1, "search_places", query="somewhere", lat=41.9)]
    assert signature(trace, 1, REQUEST_TYPE)[4] == (False, False, False, False)


def test_has_date_only() -> None:
    trace = [call(1, "get_itinerary", day_date="2026-07-01")]
    assert signature(trace, 1, "factual_qa")[4] == (False, True, False, False)


def test_has_price_term_only() -> None:
    trace = [call(1, "search_places", query="Cheap trattoria")]
    assert signature(trace, 1, REQUEST_TYPE)[4] == (False, False, True, False)


def test_has_dietary_term_only() -> None:
    trace = [call(1, "search_places", query="vegan bakery")]
    assert signature(trace, 1, REQUEST_TYPE)[4] == (False, False, False, True)


def test_parameter_terms_are_found_at_any_depth() -> None:
    trace = [call(1, "propose_plan", days=[{"slots": [{"block": {"tags": ["gluten-free"]}}]}])]
    assert signature(trace, 1, "scheduling")[4] == (False, False, False, True)


def test_parameter_terms_do_not_span_two_values() -> None:
    # "2026-07" and "-01" are not a date; joining the values without a
    # separator would make them one.
    trace = [call(1, "search_places", query="2026-07", note="-01")]
    assert signature(trace, 1, REQUEST_TYPE)[4] == (False, False, False, False)


def test_a_missing_args_key_is_tolerated() -> None:
    trace = [{"seq": 1, "tool": "get_trip_details"}]
    assert signature(trace, 1, "advisory") == (
        "advisory",
        ("get_trip_details",),
        (("get_trip_details", "1"),),
        "1",
        (False, False, False, False),
    )
