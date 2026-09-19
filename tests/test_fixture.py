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


def test_travellers_sharing_a_name_are_refused(tmp_path):
    """A placeholder is identified by its display name, and ensure_members
    adds the ones the trip lacks by name — two of a name would add neither."""
    import json

    import pytest

    from src.fixture import load_fixture as load

    fixture = load_fixture()
    fixture["members"].append({**fixture["members"][0]})
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        load(path)
    assert fixture["members"][0]["display_name"] in str(exc.value)


def test_the_trip_has_travellers_for_the_cases_that_assume_them():
    """Two seeds ask about a group. Without members the trip is one person and
    the criterion is scored against a trip that does not match the request."""
    fixture = load_fixture()
    assert len(fixture["members"]) == 2
    assert all(m.get("display_name") and "user_id" not in m for m in fixture["members"])


def test_summary_states_what_the_judge_has_to_know():
    """The criteria that lean on it: the dates, the regions, the group size,
    and which stops are already scheduled on which day."""
    from src.fixture import summary

    fixture = load_fixture()
    text = summary(fixture)
    assert fixture["trip"]["start_date"] in text and fixture["trip"]["end_date"] in text
    for region in fixture["regions"]:
        assert region["name"] in text
    assert "3 people" in text
    for block in fixture["blocks"]:
        assert block["title"] in text
    # Pena Palace is scheduled; the hotel is not. Both readings must be there,
    # because one advisory case scores a reply for naming the scheduled one.
    assert "Pena Palace (sightseeing) - scheduled 2026-11-08" in text
    assert "Hotel near Baixa (hotel) - not scheduled" in text


def test_summary_is_the_before_state_not_a_database_read():
    """P3: the judge may know what every repetition starts from, never what
    the member did next. summary() takes the fixture and touches no client."""
    import inspect

    from src import fixture as fixture_module

    source = inspect.getsource(fixture_module.summary)
    assert "db." not in source and "admin" not in source
