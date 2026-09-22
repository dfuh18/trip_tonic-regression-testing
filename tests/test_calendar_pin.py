"""The fixture's calendar (D55) and the near-dated variant (D54)."""

from datetime import date, timedelta

import pytest

from src import calendar_pin as cp
from src.cases import fixture as pinned_fixture

TEMPLATE = date(2026, 11, 6)  # a Friday, as cases/fixture.json stores it


@pytest.mark.parametrize(
    "today",
    [date(2026, 1, 1), date(2026, 9, 22), date(2026, 11, 20), date(2027, 3, 1), date(2031, 7, 4)],
)
def test_the_trip_is_always_in_the_future(today):
    """The point of the pin: a simulated trip is never a trip that happened."""
    assert cp.pinned_start(TEMPLATE, today) >= today


@pytest.mark.parametrize("year", range(2026, 2040))
def test_the_weekday_is_preserved_forever(year):
    """Seven cases say "Saturday" in prose and assert a date. They agree only
    while the pin keeps the weekday — rolling the year and keeping the 6th
    would make those cases ask for one day and check another."""
    placed = cp.place(TEMPLATE, year)
    assert placed.weekday() == TEMPLATE.weekday()
    assert placed.month == 11
    # and the whole four-day trip stays inside November
    assert (placed + timedelta(days=3)).month == 11


def test_the_trip_still_contains_a_saturday_and_a_sunday():
    days = {(cp.place(TEMPLATE, y) + timedelta(days=i)).strftime("%A") for y in range(2026, 2040) for i in range(4)}
    assert {"Friday", "Saturday", "Sunday", "Monday"} <= days


def test_case_dates_move_with_the_fixture():
    raw = {"checks": {"day": "2026-11-07"}, "untouched": "2025-01-01", "n": 3}
    out = cp.shift_case_dates(raw, (TEMPLATE, date(2026, 11, 9)), timedelta(days=364))
    assert out["checks"]["day"] == "2027-11-06"
    assert out["untouched"] == "2025-01-01"  # outside the template range
    assert out["n"] == 3


def test_ordinal_days_finds_a_day_named_in_prose():
    assert cp.ordinal_days("can you put it on the 9th") == {9}
    assert cp.ordinal_days("around 4pm on Saturday") == set()


def test_the_pinned_fixture_is_what_the_loader_serves():
    trip = pinned_fixture()["trip"]
    assert date.fromisoformat(trip["start_date"]) == cp.pinned_start(TEMPLATE)
    assert date.fromisoformat(trip["start_date"]) >= date.today()


def test_a_case_naming_a_day_by_number_is_refused_once_the_pin_moves(monkeypatch):
    """The failure mode this guard exists for, forced to happen now.

    In November 2027 the trip runs the 5th to the 8th, so
    ``scheduling_belem_morning__dir2_on_the_9th`` asks for a day the trip does
    not have. Without the guard the agent would schedule something sensible,
    the check would name a day the member never asked for, and the suite would
    report a regression that is really a stale case file.
    """
    from pathlib import Path

    from src import cases as cases_mod

    monkeypatch.setattr(cp, "pinned_start", lambda template, today=None: cp.place(template, 2027))
    path = Path(cases_mod.CASES_DIR) / "scheduling_belem_morning__dir2_on_the_9th.yaml"
    with pytest.raises(cases_mod.CaseFileError) as err:
        cases_mod.load_case(path)
    assert "names day(s) [9]" in str(err.value)
    assert "2026" not in str(err.value)


def test_every_other_case_survives_the_pin_moving(monkeypatch):
    """Only the one prose-dated case should be affected."""
    from pathlib import Path

    from src import cases as cases_mod

    monkeypatch.setattr(cp, "pinned_start", lambda template, today=None: cp.place(template, 2027))
    refused = []
    for path in sorted(Path(cases_mod.CASES_DIR).glob("*.yaml")):
        try:
            cases_mod.load_case(path)
        except cases_mod.CaseFileError as exc:
            refused.append((path.stem, str(exc)[:80]))
    assert [r[0] for r in refused] == ["scheduling_belem_morning__dir2_on_the_9th"], refused
