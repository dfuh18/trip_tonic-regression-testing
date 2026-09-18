"""The fixture digest, offline: deterministic, order-independent, and sensitive
to what the gate must notice."""
import copy

from src.fixture import expected_digest, load_fixture


def test_fixture_file_loads_and_is_internally_consistent():
    fixture = load_fixture()
    titles = {b["title"] for b in fixture["blocks"]}
    assert all(s["block"] in titles for s in fixture["slots"])
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
    extra_block["blocks"].append({"type": "activity", "title": "Left over from a run", "coordinates": {"lat": 0, "lng": 0}})
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


def test_duplicate_stop_titles_are_refused(tmp_path):
    """A title identifies a stop; two stops sharing one would collide in the
    builder's id map and drop a block silently."""
    import json

    import pytest

    from src.fixture import load_fixture as load

    fixture = load_fixture()
    fixture["blocks"].append({**fixture["blocks"][0]})
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        load(path)
    assert fixture["blocks"][0]["title"] in str(exc.value)


def test_a_slot_for_an_undefined_stop_is_refused(tmp_path):
    import json

    import pytest

    from src.fixture import load_fixture as load

    fixture = load_fixture()
    fixture["slots"].append({"block": "Not in the fixture", "day_date": "2026-11-07",
                             "start_time": "09:00", "end_time": "10:00"})
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        load(path)
    assert "Not in the fixture" in str(exc.value)
