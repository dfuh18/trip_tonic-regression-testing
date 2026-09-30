"""Tests for ``src.analysis`` — the C02 statistics, on hand-built rows."""

import math

import pytest

from src import analysis


def turn(tid, *tools, error=None, run="r1", session="s1", index=1, intent=None, request_type=None, action=None,
         reply=None, errored_tools=()):
    trace = [{"kind": "tool", "seq": i, "tool": t, "args": {}, "result_error": t in errored_tools}
             for i, t in enumerate(tools)]
    return {"id": tid, "run_id": run, "session_id": session, "turn_index": index, "agent_intent": intent,
            "tool_call_trace": trace, "error_code": error, "request_type": request_type,
            "user_action": action, "reply_message_id": reply or f"m-{tid}"}


# --- P1 ------------------------------------------------------------------------


def test_a_slash_starts_a_request_and_reference_is_not_used():
    run = [
        turn("a", "search_places", index=1, intent="find"),
        turn("b", "search_places", index=2),
        turn("c", "search_places", index=3, intent="find"),
    ]
    assert [[t["id"] for t in s] for s in analysis.segments(run)] == [["a", "b"], ["c"]]


def test_a_request_across_two_turns_is_typed_by_all_its_tools():
    sig = analysis.interaction_signature([turn("a", "search_places"), turn("b", "propose_plan", index=2)])
    assert sig[0] == "scheduling"
    assert sig[1] == ("search_places", "propose_plan")
    assert sig[3] == "2"


def test_coverage_matches_on_the_whole_signature():
    suite = [[turn("s1", "search_places")]]
    part = [[turn("p1", "search_places")], [turn("p2", "get_weather")]]
    rows = analysis.coverage(part, suite, "request")
    assert [r.covered for r in rows] == [True, False]
    assert analysis.uncovered_by(rows) == {"factual.forecast": 1}
    summary = analysis.coverage_summary(rows)
    assert (summary["n"], summary["covered"]) == (2, 1)


def test_nearest_miss_names_the_differing_parts():
    suite = [[turn("s1", "search_places"), turn("s2", "propose_plan", index=2)]]
    one_turn = [[turn("p1", "search_places", "propose_plan")]]
    rows = analysis.uncovered_diagnosis(one_turn, suite)
    assert [(r["shape"], r["differs in"], r["parts off"]) for r in rows] == [("scheduling.draft", "turns", 1)]


def test_nearest_miss_skips_covered_requests_and_handles_an_empty_suite():
    suite = [[turn("s1", "search_places")]]
    assert analysis.uncovered_diagnosis([[turn("p1", "search_places")]], suite) == []
    assert analysis.nearest_miss(("a",), []) == list(analysis.SIGNATURE_PARTS)


def test_simulated_executions_are_segmented_like_participant_runs():
    execution = [turn("s1", "search_places", intent="find"), turn("s2", "propose_plan", index=2)]
    units = analysis.simulated_requests([execution])
    assert [[t["id"] for t in u] for u in units] == [["s1"], ["s2"]]
    part = [[turn("p1", "propose_plan")]]
    assert analysis.coverage(part, [execution], "request")[0].covered is False
    assert analysis.coverage(part, units, "request")[0].covered is True


def test_turn_coverage_compares_single_turns():
    suite = [[turn("s1", "search_places"), turn("s2", "propose_plan", index=2)]]
    part = [[turn("p1", "propose_plan")]]
    assert analysis.coverage(part, suite, "request")[0].covered is False
    assert analysis.coverage(part, suite, "turn")[0].covered is True


# --- P2 ------------------------------------------------------------------------


def test_failure_rates_per_class_are_plain_ratios():
    turns = [turn("a", request_type="scheduling", error="agent_timeout"),
             turn("b", request_type="scheduling"),
             turn("c", request_type="venue_lookup")]
    rates = {r.group: r for r in analysis.failure_rates(turns)}
    assert rates["scheduling"] == analysis.Rate("scheduling", 2, 1, 0.5)
    assert rates["venue_lookup"].failures == 0


def test_a_share_of_nothing_is_nan_not_zero():
    assert math.isnan(analysis.share(0, 0)) and analysis.share(1, 4) == 0.25
    assert math.isnan(analysis.coverage_summary([])["share covered"])


def test_tool_errors_count_recoveries():
    turns = [turn("a", "get_weather", "get_climate_normals", errored_tools={"get_weather"}),
             turn("b", "get_weather", errored_tools={"get_weather"}, error="tool_failed")]
    rows = {r["tool"]: r for r in analysis.tool_errors(turns)}
    assert rows["get_weather"] == {"tool": "get_weather", "calls": 2, "errored calls": 2,
                                   "turns completed after an error": 1}


def test_recovered_errors_count_only_completed_turns():
    turns = [turn("a", "get_weather", "get_climate_normals", errored_tools={"get_weather"}, request_type="factual_qa"),
             turn("b", "get_weather", request_type="factual_qa"),
             turn("c", "get_weather", errored_tools={"get_weather"}, error="tool_failed", request_type="factual_qa")]
    by_tool = {r.group: r for r in analysis.recovered_error_rates(turns)}
    assert (by_tool["get_weather"].n, by_tool["get_weather"].failures) == (2, 1)
    assert by_tool["get_climate_normals"].failures == 0
    by_type = {r.group: r for r in analysis.recovered_error_rates(turns, key="request_type")}
    assert (by_type["factual_qa"].n, by_type["factual_qa"].failures) == (2, 1)


def test_error_kinds_are_read_off_the_message_without_showing_it():
    assert analysis.error_kind("Weather forecast unavailable: 2026-11-06 is beyond the 16-day forecast horizon") \
        == "beyond forecast horizon"
    assert analysis.error_kind("Climate data unavailable: The operation was aborted due to timeout") == "timeout"
    assert analysis.error_kind("Error in tool 'move_slot': [{\"code\": \"invalid_type\"}]") == "invalid arguments"
    assert analysis.error_kind("End time must be after start time for a single-day slot") == "rejected value"
    assert analysis.error_kind("something new") == "other"


def test_error_summary_separates_failed_turns_from_recovered_ones():
    turns = [turn("a", "get_weather", "get_climate_normals", errored_tools={"get_weather"}),
             turn("b", "search_places"),
             turn("c", "get_weather", errored_tools={"get_weather"}, error="agent_timeout")]
    s = analysis.error_summary(turns)
    assert (s["turns"], s["failed without a response"], s["turns with a recovered tool error"]) == (3, 1, 1)
    assert (s["tool calls"], s["errored tool calls"]) == (3, 1)
    kinds = analysis.error_kinds([dict(turns[0], tool_call_trace=[
        {"kind": "tool", "seq": 0, "tool": "get_weather", "result_error": "beyond the 16-day forecast horizon"}])])
    assert kinds == {("get_weather", "beyond forecast horizon"): 1}


def test_empty_lookups_count_misses_not_errors_and_only_tools_with_a_found_flag():
    t = turn("a", "read_wikipedia", "read_wikipedia", "read_wikipedia", "search_places")
    t["tool_call_trace"][0]["result_found"] = False
    t["tool_call_trace"][1]["result_found"] = True
    t["tool_call_trace"][2].update(result_found=False, result_error="timeout")  # an error, not a miss
    t["tool_call_trace"][3]["result_found"] = None                              # no found flag
    rates = {r.group: r for r in analysis.empty_lookup_rates([t])}
    assert list(rates) == ["read_wikipedia"]
    assert (rates["read_wikipedia"].n, rates["read_wikipedia"].failures) == (2, 1)


def test_recovered_errors_by_shape():
    turns = [turn("a", "get_weather", errored_tools={"get_weather"}), turn("b", "search_places")]
    by_shape = {r.group: r for r in analysis.recovered_error_rates(turns, key="shape")}
    assert by_shape["factual.forecast"].failures == 1 and by_shape["venue.search"].failures == 0


# --- P3 ------------------------------------------------------------------------


def test_feedback_signals_are_never_pooled():
    turns = [turn("a", action="accepted", reply="ma"), turn("b", action="rejected", reply="mb"),
             turn("c", action="ignored", reply="mc")]
    feedback = [{"chat_message_id": "ma", "value": "down"}, {"chat_message_id": "mc", "value": "up"}]
    groups = analysis.feedback_groups(turns, feedback, {"a": 8, "b": 3, "c": 9})
    assert groups["thumbs"] == {"positive": [9.0], "negative": [8.0]}
    assert groups["accept/reject"] == {"positive": [8.0], "negative": [3.0]}


def test_p3_is_a_side_by_side_score_distribution_not_a_test():
    rows = analysis.feedback_scores({"thumbs": {"positive": [9.0, 10.0, 8.0], "negative": []}})
    assert rows[0] == {"signal": "thumbs", "group": "positive", "n": 3, "median": 9.0, "mean": 9.0,
                       "min": 8.0, "max": 10.0}
    assert rows[1]["n"] == 0 and rows[1]["median"] is None
    assert not {"p", "U", "r_rb"} & set(rows[0])


# --- per participant -----------------------------------------------------------------


def test_participant_overview_is_pseudonymous_and_counts_per_person():
    sessions = [{"id": "s1", "consent_at": "t"}, {"id": "s2", "consent_at": "t"}, {"id": "d1", "consent_at": None}]
    names = {"s1": "S1", "s2": "S2", "d1": "D1"}
    r1 = [dict(turn("a", "search_places", errored_tools={"search_places"}), session_id="s1", user_action="accepted")]
    r2 = [dict(turn("b", "propose_plan"), session_id="s1")]
    r3 = [dict(turn("c", "get_weather", error="timeout"), session_id="s2")]
    feedback = [{"session_id": "s1", "value": "up"}, {"session_id": "s1", "value": "down"}]
    post = [{"session_id": "s2", "submitted_at": "t", "umux_lite_capability": 7, "umux_lite_ease": 7}]
    rows = analysis.participant_overview(sessions, names, [r1, r2, r3], [True, False, False], feedback, post)
    assert [r["participant"] for r in rows] == ["S1", "S2"]  # declined sessions are left out
    s1, s2 = rows
    assert (s1["requests"], s1["requests covered"], s1["requests uncovered"]) == (2, 1, 1)
    assert (s1["errored tool calls"], s1["accepted / rejected turns"], s1["thumbs up / down"]) == (1, "1 / 0", "1 / 1")
    assert (s2["failed turns"], s2["tool calls"], s2["SUS-equivalent"]) == (1, 0, 87.9)
    assert all("id" not in k for r in rows for k in r)


# --- UMUX-LITE -----------------------------------------------------------------


def test_umux_lite_scale_and_grades():
    assert analysis.umux_lite(7, 7) == 100 and analysis.umux_lite(1, 1) == 0
    assert analysis.sus_equivalent(100) == pytest.approx(87.9)
    assert analysis.curved_grade(87.9) == "A+"
    assert analysis.curved_grade(68.0) == "C"
    assert analysis.curved_grade(51.6) == "F"


def test_usability_skips_dismissed_rows():
    rows = analysis.usability([
        {"submitted_at": "t", "umux_lite_capability": 6, "umux_lite_ease": 7, "likelihood_to_recommend": 6},
        {"dismissed_at": "t"},
    ])
    assert len(rows) == 1 and math.isclose(rows[0]["umux_lite"], 11 / 12 * 100)


# --- criteria (D109) -------------------------------------------------------------


def _cov(*covered):
    return [analysis.CoverageRow("request", "venue.search", "venue_lookup", c) for c in covered]


def test_p1_needs_more_than_half():
    assert analysis.p1_verdict(_cov(True, False)).outcome == analysis.NOT_SUPPORTED
    assert analysis.p1_verdict(_cov(True, True, False)).outcome == analysis.SUPPORTED
    assert analysis.p1_verdict([]).outcome == analysis.NOT_ASSESSED


def _rates(**tools):
    return [analysis.Rate(t, n, k, k / n) for t, (k, n) in tools.items()]


SIM = _rates(get_weather=(11, 43), get_climate_normals=(2, 19), move_slot=(3, 43), search_places=(0, 306))


def test_p2_two_shared_top_tools_support_it():
    part = _rates(get_weather=(3, 12), move_slot=(1, 20), search_places=(1, 50), get_climate_normals=(0, 11))
    assert analysis.p2_verdict(SIM, part).outcome == analysis.SUPPORTED


def test_p2_one_shared_tool_does_not():
    part = _rates(get_weather=(3, 12), move_slot=(0, 20), search_places=(1, 50), get_climate_normals=(0, 11))
    assert analysis.p2_verdict(SIM, part).outcome == analysis.NOT_SUPPORTED


def test_p2_is_not_assessed_when_participants_rarely_call_the_tools():
    part = _rates(get_weather=(1, 4), move_slot=(0, 20), search_places=(0, 50))
    assert analysis.p2_verdict(SIM, part).outcome == analysis.NOT_ASSESSED


def test_a_tie_at_the_cut_is_included():
    rates = _rates(a=(2, 10), b=(1, 10), c=(1, 10), d=(1, 10))
    assert analysis.top_error_tools(rates, "abcd", k=2) == ["a", "b", "c", "d"]


def test_p3_needs_ten_each_and_one_point():
    assert analysis.p3_verdict({"positive": [9.0] * 10, "negative": [8.0] * 9}).outcome == analysis.NOT_ASSESSED
    assert analysis.p3_verdict({"positive": [9.0] * 10, "negative": [8.0] * 10}).outcome == analysis.SUPPORTED
    assert analysis.p3_verdict({"positive": [9.0] * 10, "negative": [8.5] * 10}).outcome == analysis.NOT_SUPPORTED


def test_the_review_sample_is_fixed_by_its_seed_and_balanced():
    requests = [[turn(f"t{i}", "search_places" if i % 2 else "get_weather")] for i in range(30)]
    rows = analysis.coverage(requests, [[turn("s", "search_places")]], "request")
    a = analysis.review_sample(rows, requests, 10, seed=7)
    assert a == analysis.review_sample(rows, requests, 10, seed=7)
    assert [r["covered"] for r in a].count(True) == 10 and [r["covered"] for r in a].count(False) == 10
    assert all(rows[r["index"]].covered is r["covered"] for r in a)


def test_the_review_sample_takes_all_of_a_small_group():
    requests = [[turn("a", "search_places")], [turn("b", "get_weather")]]
    rows = analysis.coverage(requests, [[turn("s", "search_places")]], "request")
    assert len(analysis.review_sample(rows, requests, 10, seed=1)) == 2
