"""The judge is told the day the agent answered on, in UTC (D94).

An overnight run judged the next morning used to tell the judge the judging
day: every execution before midnight was judged against "tomorrow", and a
near-dated case's trip was rebuilt a day later than the one the agent planned.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from src import fixture, judge, scoring


def test_execution_day_is_the_utc_day_of_started_at():
    assert scoring.execution_day({"started_at": "2026-09-25T23:40:12.5+00:00"}) == date(2026, 9, 25)
    assert scoring.execution_day({"started_at": "2026-09-26T00:10:00Z"}) == date(2026, 9, 26)
    # 01:30 CEST is still the previous day in UTC, which is what the agent saw.
    assert scoring.execution_day({"started_at": "2026-09-26T01:30:00+02:00"}) == date(2026, 9, 25)
    assert scoring.execution_day({}) is None


def test_the_judge_is_told_the_given_day():
    block = judge._today_block(date(2026, 9, 25))
    assert "Friday 25 September 2026 (2026-09-25)" in block


def test_a_near_dated_trip_is_built_from_the_given_day():
    near = SimpleNamespace(fixture_dates="near")
    trip = fixture.for_case(near, date(2026, 9, 25))["trip"]
    assert trip["start_date"] == "2026-09-28"
    later = fixture.for_case(near, date(2026, 9, 26))["trip"]
    assert later["start_date"] == "2026-09-29"
