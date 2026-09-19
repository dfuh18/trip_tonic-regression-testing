"""The case loader: what it accepts, what it names when it refuses, and that
the suite version follows the files."""
from pathlib import Path

import pytest
import yaml

from src.cases import CaseFileError, by_priority, load_case, load_cases, suite_version

VALID = {
    "case_id": "venue_lookup_seafood",
    "base_case_id": None,
    "provenance": "seeded",
    "run_priority": 1,
    "function": "venue_lookup",
    "user_profile": "Marta, 34, weekend in Lisbon.",
    "goal": "Two seafood places near Cais do Sodré.",
    "opening_turn": "/find seafood near Cais do Sodré",
    "intent": "find",
    "expected_tool_sequence": ["search_places"],
    "declared_constraints": {
        "checks": {"tool_counts": {"search_places": {"min": 1, "max": 2}}, "no_tool_errors": True},
        "predicates": [],
    },
    "scoring_criteria": ["Names real places.", "Stays in the area."],
    "references": [],
    "repetitions_n": 8,
    "metamorphic_relation": None,
}


def write(tmp_path: Path, name: str, data: dict) -> Path:
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_valid_case_loads(tmp_path):
    case = load_case(write(tmp_path, "venue_lookup_seafood", VALID))
    assert case.function == "venue_lookup"
    assert case.declared_constraints.checks.tool_counts["search_places"].min == 1


@pytest.mark.parametrize("key", ["case_id", "provenance", "run_priority", "function", "user_profile",
                                 "goal", "opening_turn", "scoring_criteria", "repetitions_n"])
def test_missing_required_key_is_named(tmp_path, key):
    data = {k: v for k, v in VALID.items() if k != key}
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "venue_lookup_seafood", data))
    assert key in str(exc.value) or key == "case_id"
    assert "venue_lookup_seafood.yaml" in str(exc.value)


def test_unknown_key_is_refused(tmp_path):
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "venue_lookup_seafood", {**VALID, "threshold": 3}))
    assert "threshold" in str(exc.value)


def test_file_name_must_match_case_id(tmp_path):
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "other_name", VALID))
    assert "must equal the file name" in str(exc.value)


def test_metamorphic_needs_base_and_relation(tmp_path):
    data = {**VALID, "case_id": "follow", "provenance": "metamorphic"}
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "follow", data))
    assert "base_case_id" in str(exc.value)
    data.update(base_case_id="venue_lookup_seafood", metamorphic_relation="INV-9")
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "follow", data))
    assert "metamorphic_relation" in str(exc.value)
    data["metamorphic_relation"] = "INV-1"
    assert load_case(write(tmp_path, "follow", data)).metamorphic_relation == "INV-1"


def test_base_case_must_exist_in_suite(tmp_path):
    write(tmp_path, "follow", {**VALID, "case_id": "follow", "provenance": "metamorphic",
                               "base_case_id": "nope", "metamorphic_relation": "INV-2"})
    with pytest.raises(CaseFileError) as exc:
        load_cases(tmp_path)
    assert "nope" in str(exc.value)


def test_advisory_constrains_the_trip_but_never_the_tools(tmp_path):
    """D29: a case constrains what its request implies. An advisory request
    implies nothing is written, so it may say so — but it may not fix which
    tools inform the answer, because a message with no slash command keeps the
    whole toolset on purpose and that choice is the agent's."""
    base = {**VALID, "case_id": "advice", "function": "advisory", "intent": None,
            "expected_tool_sequence": [], "declared_constraints": {"checks": {}, "predicates": []}}

    writes = {"checks": {"mutation_counts": {"trip_blocks.INSERT": 0, "ai_suggestions.INSERT": 0}}, "predicates": []}
    case = load_case(write(tmp_path, "advice", {**base, "declared_constraints": writes}))
    assert case.declared_constraints.checks.mutation_counts["ai_suggestions.INSERT"] == 0
    assert case.constrains_tools() is False
    assert case.allowed_tools() is None

    for tool_constraint in (
        {"expected_tool_sequence": ["read_wikipedia"]},
        {"declared_constraints": {"checks": {"tool_counts": {"search_places": 1}}, "predicates": []}},
        {"declared_constraints": {"checks": {"tools_any_of": ["get_weather"]}, "predicates": []}},
    ):
        with pytest.raises(CaseFileError) as exc:
            load_case(write(tmp_path, "advice", {**base, **tool_constraint}))
        assert "does not constrain tools" in str(exc.value)


def test_the_advisory_seeds_assert_that_nothing_is_written():
    from src.cases import CASES_DIR, load_cases

    for case in load_cases(CASES_DIR):
        if case.function != "advisory":
            continue
        counts = case.declared_constraints.checks.mutation_counts
        assert counts and set(counts.values()) == {0}, f"{case.case_id} should assert the trip is unchanged"
        assert case.allowed_tools() is None, f"{case.case_id} must not constrain tools"


def test_factual_qa_needs_a_reference(tmp_path):
    data = {**VALID, "case_id": "fact", "function": "factual_qa", "intent": None}
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "fact", data))
    assert "reference" in str(exc.value)


def test_unknown_check_key_is_refused(tmp_path):
    """A constraint nothing evaluates is worse than no constraint."""
    data = {**VALID, "declared_constraints": {"checks": {"tool_sequence": ["search_places"]}, "predicates": []}}
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "venue_lookup_seafood", data))
    assert "tool_sequence" in str(exc.value)


def test_slot_moved_names_a_stop_a_day_and_optionally_a_window(tmp_path):
    def built(moved):
        return load_case(write(tmp_path, "venue_lookup_seafood",
                               {**VALID, "declared_constraints": {"checks": {"slot_moved": moved},
                                                                  "predicates": []}}))

    moved = {"block": "Tram 28 ride through Alfama", "day": "2026-11-07",
             "starts_between": ["15:30", "16:30"]}
    assert built(moved).declared_constraints.checks.slot_moved.starts_between == ("15:30", "16:30")
    without_time = {k: v for k, v in moved.items() if k != "starts_between"}
    assert built(without_time).declared_constraints.checks.slot_moved.starts_between is None
    with pytest.raises(CaseFileError) as exc:
        built({"day": "2026-11-07"})
    assert "block" in str(exc.value)


def test_a_window_read_backwards_is_refused(tmp_path):
    """The pair is [earliest, latest]. Reversed it is satisfiable by nothing,
    and a constraint nothing can satisfy fails every correct agent silently."""
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "venue_lookup_seafood", {**VALID, "declared_constraints": {
            "checks": {"slot_moved": {"block": "x", "day": "2026-11-07",
                                      "starts_between": ["16:30", "15:30"]}},
            "predicates": []}}))
    assert "earliest first" in str(exc.value)


def test_a_window_takes_clock_times(tmp_path):
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "venue_lookup_seafood", {**VALID, "declared_constraints": {
            "checks": {"slot_moved": {"block": "x", "day": "2026-11-07",
                                      "starts_between": ["4pm", "5pm"]}},
            "predicates": []}}))
    assert "HH:MM" in str(exc.value)


def test_an_exact_time_is_written_as_a_window_of_one_minute(tmp_path):
    """There is no exact-time key on purpose (D31). A case that means one
    minute says so twice, so the tolerance it intends is never implied by the
    absence of one."""
    case = load_case(write(tmp_path, "venue_lookup_seafood", {**VALID, "declared_constraints": {
        "checks": {"slot_moved": {"block": "x", "day": "2026-11-07",
                                  "starts_between": ["09:00", "09:00"]}},
        "predicates": []}}))
    assert case.declared_constraints.checks.slot_moved.starts_between == ("09:00", "09:00")


def test_a_case_permits_what_it_names_plus_the_read_tools(tmp_path):
    """D28: deny by default. The allowed set is what the case names, plus the
    three read tools, and nothing else."""
    from src.cases import ALWAYS_ALLOWED_TOOLS

    case = load_case(write(tmp_path, "venue_lookup_seafood", VALID))
    assert case.allowed_tools() == {"search_places", *ALWAYS_ALLOWED_TOOLS}
    assert "propose_plan" not in case.allowed_tools()
    assert "read_wikipedia" not in case.allowed_tools()


def test_every_way_of_naming_a_tool_permits_it(tmp_path):
    from src.cases import ALWAYS_ALLOWED_TOOLS

    base = {**VALID, "expected_tool_sequence": [], "declared_constraints": {"checks": {}, "predicates": []}}
    by_sequence = load_case(write(tmp_path, "venue_lookup_seafood",
                                  {**base, "expected_tool_sequence": ["search_places", "propose_plan"]}))
    assert by_sequence.allowed_tools() == {"search_places", "propose_plan", *ALWAYS_ALLOWED_TOOLS}
    by_counts = load_case(write(tmp_path, "venue_lookup_seafood",
                                {**base, "declared_constraints": {"checks": {"tool_counts": {"move_slot": 1}}, "predicates": []}}))
    assert by_counts.allowed_tools() == {"move_slot", *ALWAYS_ALLOWED_TOOLS}
    by_any_of = load_case(write(tmp_path, "venue_lookup_seafood",
                                {**base, "declared_constraints": {"checks": {"tools_any_of": ["read_wikipedia", "get_weather"]}, "predicates": []}}))
    assert by_any_of.allowed_tools() == {"read_wikipedia", "get_weather", *ALWAYS_ALLOWED_TOOLS}


def test_a_tool_bounded_at_zero_is_forbidden_not_permitted(tmp_path):
    """Naming a tool to forbid it must not accidentally allow it."""
    data = {**VALID, "declared_constraints": {
        "checks": {"tool_counts": {"search_places": {"min": 1, "max": 2}, "propose_plan": 0}}, "predicates": []}}
    case = load_case(write(tmp_path, "venue_lookup_seafood", data))
    assert "propose_plan" not in case.allowed_tools()
    assert "search_places" in case.allowed_tools()


def test_a_case_naming_no_tool_constrains_none(tmp_path):
    """The advisory seeds: no tool constraint means no tool checking, not an
    empty allowlist that would fail the first grounded answer."""
    data = {**VALID, "case_id": "advice", "function": "advisory", "intent": None,
            "expected_tool_sequence": [], "declared_constraints": {"checks": {}, "predicates": []}}
    case = load_case(write(tmp_path, "advice", data))
    assert case.constrains_tools() is False
    assert case.allowed_tools() is None


def test_the_seed_suite_permits_what_each_function_needs():
    from src.cases import CASES_DIR, load_cases

    allowed = {c.case_id: c.allowed_tools() for c in load_cases(CASES_DIR)}
    assert "propose_plan" in allowed["scheduling_belem_morning"]
    assert "propose_plan" not in allowed["venue_lookup_seafood_lisbon"]
    assert "search_places" not in allowed["scheduling_move_tram"]
    assert allowed["advisory_packing_list"] is None


def test_predicates_are_only_the_comparative_ones():
    """D27: a predicate exists to compare two executions. Anything describing
    one execution belongs in Checks, where the loader can validate it."""
    from src.cases import _predicate_names

    assert _predicate_names() == {"same_venues_as_base", "different_venues_from_base", "same_tool_sequence_as_base"}


def test_unknown_predicate_is_refused(tmp_path):
    data = {**VALID, "declared_constraints": {"checks": {}, "predicates": ["does_not_exist"]}}
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "venue_lookup_seafood", data))
    assert "does_not_exist" in str(exc.value)


def test_fixture_dependency_must_name_something_the_fixture_has(tmp_path):
    from src.cases import fixture_anchors

    anchors = fixture_anchors()
    ok = load_case(write(tmp_path, "venue_lookup_seafood", {**VALID, "fixture_depends_on": ["Tram 28 ride through Alfama", "2026-11-07"]}), known_anchors=anchors)
    assert ok.fixture_depends_on == ["Tram 28 ride through Alfama", "2026-11-07"]
    for bad in ("no_such_block", "2027-01-01"):
        with pytest.raises(CaseFileError) as exc:
            load_case(write(tmp_path, "venue_lookup_seafood", {**VALID, "fixture_depends_on": [bad]}), known_anchors=anchors)
        assert bad in str(exc.value) and "fixture" in str(exc.value)


def test_fixture_anchors_are_the_block_keys_and_the_trip_days():
    from src.cases import fixture, fixture_anchors

    fx = fixture()
    anchors = fixture_anchors(fx)
    assert {b["title"] for b in fx["blocks"]} <= anchors
    assert fx["trip"]["start_date"] in anchors and fx["trip"]["end_date"] in anchors
    assert "2026-11-10" not in anchors  # the day after the trip ends


def test_every_seed_case_declares_what_it_leans_on():
    """A case whose text names a fixture stop must say so, or the loader cannot
    protect it when the fixture changes."""
    from src.cases import CASES_DIR, fixture, load_cases

    titles = [b["title"] for b in fixture()["blocks"]]
    for case in load_cases(CASES_DIR):
        text = f"{case.opening_turn} {case.goal}".lower()
        for title in titles:
            first_words = " ".join(title.lower().split()[:2])
            if first_words in text:
                assert title in case.fixture_depends_on, f"{case.case_id} names {title!r} but does not declare it"


def test_suite_version_follows_the_files(tmp_path):
    write(tmp_path, "venue_lookup_seafood", VALID)
    first = suite_version(tmp_path)
    (tmp_path / "fixture.json").write_text('{"trip": {"start_date": "2026-11-06"}}', encoding="utf-8")
    with_fixture = suite_version(tmp_path)
    assert with_fixture != first, "the fixture is part of the suite version"
    (tmp_path / "fixture.json").unlink()
    assert len(first) == 64 and suite_version(tmp_path) == first
    write(tmp_path, "venue_lookup_seafood", {**VALID, "goal": "Three places."})
    assert suite_version(tmp_path) != first
    (tmp_path / "_draft.yaml").write_text("x: 1", encoding="utf-8")
    assert suite_version(tmp_path) != first  # unchanged by drafts
    assert len(load_cases(tmp_path)) == 1


def test_priority_order(tmp_path):
    write(tmp_path, "b_seed", {**VALID, "case_id": "b_seed", "run_priority": 2})
    write(tmp_path, "a_seed", {**VALID, "case_id": "a_seed", "run_priority": 1})
    write(tmp_path, "a_follow", {**VALID, "case_id": "a_follow", "run_priority": 1, "provenance": "metamorphic",
                                 "base_case_id": "a_seed", "metamorphic_relation": "INV-1", "repetitions_n": 4})
    assert [c.case_id for c in by_priority(load_cases(tmp_path))] == ["a_seed", "a_follow", "b_seed"]


def test_the_tram_window_brackets_what_the_member_actually_said():
    """The member says "Saturday afternoon ... around 4". A case demanding
    16:00 exactly fails an agent that wrote 16:15 and understood her (D31)."""
    from src.cases import minutes_of

    case = {c.case_id: c for c in load_cases()}["scheduling_move_tram"]
    moved = case.declared_constraints.checks.slot_moved
    earliest, latest = moved.starts_between
    assert minutes_of(latest) - minutes_of(earliest) >= 30
    assert minutes_of(earliest) <= minutes_of("16:00") <= minutes_of(latest)


def test_the_tram_duration_bound_brackets_the_length_the_fixture_gives_it():
    """"Keeps its hour" is only a constraint while the fixture's hour is inside
    the bound. Stated in the case rather than inherited, so a fixture change
    that moves the length shows up here instead of silently passing."""
    from src.cases import as_bound, fixture, minutes_of

    case = {c.case_id: c for c in load_cases()}["scheduling_move_tram"]
    moved = case.declared_constraints.checks.slot_moved
    slot = next(s for s in fixture()["slots"] if s["block"] == moved.block)
    current = minutes_of(slot["end_time"]) - minutes_of(slot["start_time"])
    assert as_bound(moved.duration_minutes).holds(current)


def test_a_case_asserting_a_landing_time_also_asserts_a_length():
    """The two failures are different: the start can be right while the stored
    end runs the stop to the end of the day, and move_slot takes the end as an
    optional argument that nothing derives from the stop's duration."""
    for case in load_cases():
        moved = case.declared_constraints.checks.slot_moved
        if moved and moved.starts_between:
            assert moved.duration_minutes is not None, case.case_id


def test_every_reference_a_case_names_exists_and_is_not_empty():
    """A reference is what the reply is scored against. An empty or missing
    one scores the reply against nothing and says nothing about it."""
    for case in load_cases():
        for ref in case.references:
            assert ref.text().strip(), f"{case.case_id}: empty reference {ref.path}"


def test_the_forecast_tool_is_a_probe_the_weather_case_cannot_answer_from():
    """get_weather is a 16-day forecast and cannot reach the trip's November,
    so answering a typical-November question from it is answering about the
    wrong weeks. Trying it and falling back is not a failure, though, so it is
    permitted and does not satisfy (the review's finding D, and D30)."""
    case = {c.case_id: c for c in load_cases()}["factual_qa_lisbon_november_weather"]
    checks = case.declared_constraints.checks
    assert "get_weather" not in (checks.tools_any_of or [])
    assert "get_weather" in case.allowed_tools()


def test_a_tool_bounded_at_zero_is_forbidden_rather_than_permitted():
    """The same key spells both, so the difference must hold: {min: 0} names a
    probe, {max: 0} names a ban."""
    from src.cases import Case

    def built(bound):
        return Case(**{**VALID, "declared_constraints": {
            "checks": {"tool_counts": {"get_weather": bound}}, "predicates": []}})

    assert "get_weather" in built({"min": 0, "max": 1}).allowed_tools()
    assert "get_weather" not in built({"min": 0, "max": 0}).allowed_tools()
