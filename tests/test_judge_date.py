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


# --- pair-wise: each reply against its own day (D97) ------------------------

import json  # noqa: E402

from src.cases import Case  # noqa: E402
from src.llm import LlmReply  # noqa: E402


class _FakeLlm:
    model = "fake"

    def __init__(self):
        self.calls = []

    def generate(self, system, user, *, json_schema=None, temperature=0.0):
        self.calls.append(system)
        answer = {"better": "tie", "rationale": ""}
        return LlmReply(text=json.dumps(answer), parsed=answer, tokens_input=1, tokens_output=1, model="fake", retries=0)


def _near_case():
    return Case(
        case_id="advisory_near", provenance="seeded", run_priority=1, function="advisory",
        user_profile="x", goal="x", opening_turn="@Tonic weather while we're there?", intent=None,
        scoring_criteria=["Gives the forecast for the trip days."], repetitions_n=8, fixture_dates="near",
    )


def _section(prompt: str, label: str) -> str:
    start = prompt.index(f"### {label}\n")
    end = prompt.index("###", start + 4) if label == "Reply A" else prompt.index("A difference that exists")
    return prompt[start:end]


def test_each_reply_is_told_its_own_day_in_both_orderings():
    llm = _FakeLlm()
    judge.compare_pairwise(_near_case(), "q", "BASE", "CAND", llm=llm,
                           baseline_day=date(2026, 9, 25), candidate_day=date(2026, 10, 3))
    first, second = llm.calls
    # Ordering 1: baseline is A. Ordering 2: candidate is A.
    assert "25 September 2026" in _section(first, "Reply A") and "03 October 2026" in _section(first, "Reply B")
    assert "03 October 2026" in _section(second, "Reply A") and "25 September 2026" in _section(second, "Reply B")


def test_a_near_dated_trip_moves_with_each_replys_day():
    llm = _FakeLlm()
    judge.compare_pairwise(_near_case(), "q", "BASE", "CAND", llm=llm,
                           baseline_day=date(2026, 9, 25), candidate_day=date(2026, 10, 3))
    first = llm.calls[0]
    assert "2026-09-28" in _section(first, "Reply A")   # 25 Sep + 3 days
    assert "2026-10-06" in _section(first, "Reply B")   # 3 Oct + 3 days
