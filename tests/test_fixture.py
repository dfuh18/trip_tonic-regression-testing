"""The fixture digest, offline: deterministic, order-independent, and sensitive
to what the gate must notice."""
import copy

from src.fixture import expected_digest, load_fixture


def test_fixture_file_loads_and_is_internally_consistent():
    fixture = load_fixture()
    keys = {b["key"] for b in fixture["blocks"]}
    assert all(s["block"] in keys for s in fixture["slots"])
    assert fixture["trip"]["start_date"] <= min(s["day_date"] for s in fixture["slots"])
    assert fixture["trip"]["end_date"] >= max(s["day_date"] for s in fixture["slots"])


def test_digest_is_stable_and_order_independent():
    fixture = load_fixture()
    first = expected_digest(fixture)
    shuffled = copy.deepcopy(fixture)
    shuffled["blocks"].reverse()
    shuffled["slots"].reverse()
    shuffled["regions"].reverse()  # regions are not in the digest at all
    assert expected_digest(shuffled) == first


def test_digest_changes_with_state_the_gate_must_notice():
    fixture = load_fixture()
    base = expected_digest(fixture)
    extra_block = copy.deepcopy(fixture)
    extra_block["blocks"].append({"key": "x", "type": "activity", "title": "Left over from a run", "coordinates": {"lat": 0, "lng": 0}})
    assert expected_digest(extra_block) != base
    moved = copy.deepcopy(fixture)
    moved["slots"][0]["start_time"] = "11:00"
    assert expected_digest(moved) != base


def test_digest_ignores_what_is_not_state():
    fixture = load_fixture()
    base = expected_digest(fixture)
    described = copy.deepcopy(fixture)
    described["trip"]["description"] = "reworded"
    described["blocks"][0]["address"] = "somewhere else"
    assert expected_digest(described) == base
