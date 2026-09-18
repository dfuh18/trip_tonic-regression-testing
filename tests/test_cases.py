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


def test_advisory_carries_no_constraints(tmp_path):
    data = {**VALID, "case_id": "advice", "function": "advisory", "intent": None,
            "expected_tool_sequence": [], "declared_constraints": {"checks": {}, "predicates": []}}
    assert load_case(write(tmp_path, "advice", data)).declared_constraints.is_empty()
    with pytest.raises(CaseFileError):
        load_case(write(tmp_path, "advice", {**data, "declared_constraints": {"checks": {"no_tool_errors": True}}}))


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


def test_slot_moved_names_a_stop_a_day_and_optionally_a_time(tmp_path):
    moved = {"block": "Tram 28 ride through Alfama", "day": "2026-11-07", "start_time": "16:00"}
    case = load_case(write(tmp_path, "venue_lookup_seafood",
                           {**VALID, "declared_constraints": {"checks": {"slot_moved": moved}, "predicates": []}}))
    assert case.declared_constraints.checks.slot_moved.start_time == "16:00"
    without_time = {k: v for k, v in moved.items() if k != "start_time"}
    case = load_case(write(tmp_path, "venue_lookup_seafood",
                           {**VALID, "declared_constraints": {"checks": {"slot_moved": without_time}, "predicates": []}}))
    assert case.declared_constraints.checks.slot_moved.start_time is None
    with pytest.raises(CaseFileError) as exc:
        load_case(write(tmp_path, "venue_lookup_seafood",
                        {**VALID, "declared_constraints": {"checks": {"slot_moved": {"day": "2026-11-07"}}, "predicates": []}}))
    assert "block" in str(exc.value)


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
