"""Runtime arithmetic on hand-built runs: pauses, phases and the schedules."""

import pandas as pd
import pytest

from src.runtime_estimate import active_seconds, per_case, per_execution, phases, say, schedules

T0 = pd.Timestamp("2026-09-26T10:00:00Z")


def at(seconds):
    return T0 + pd.Timedelta(seconds=seconds)


def run(executions, scores=(), comparisons=()):
    """`executions` as (case, provenance, start s, finish s)."""
    ex = pd.DataFrame([{"id": f"e{i}", "case_id": c, "provenance": p, "repetition": i,
                        "started_at": at(s), "finished_at": at(f)}
                       for i, (c, p, s, f) in enumerate(executions)])
    judge = lambda ts: pd.DataFrame({"execution_id": [f"e{i}" for i in range(len(ts))],
                                     "created_at": [at(t) for t in ts]})
    return {"run": pd.DataFrame(), "executions": ex,
            "scores": judge(scores) if scores else pd.DataFrame(),
            "comparisons": judge(comparisons) if comparisons else pd.DataFrame()}


def test_a_long_gap_is_a_pause_and_is_reported():
    span, active, idle = active_seconds(pd.Series([at(0), at(10), at(1000), at(1010)]))
    assert span == 1010
    assert active == 20
    assert list(idle) == [990]


def test_an_overnight_gap_between_executions_is_not_work():
    r = run([("a", "seeded", 0, 30), ("a", "seeded", 40, 70), ("a", "seeded", 10_000, 10_030)])
    ph = phases(r)
    assert ph.loc["execution", "pauses"] == 1
    assert ph.loc["execution", "active min"] * 60 == pytest.approx(100)  # three conversations and one 10 s gap


def test_a_long_execution_is_never_a_pause():
    r = run([("a", "seeded", 0, 1000), ("a", "seeded", 1010, 1020)])
    assert phases(r).loc["execution", "pauses"] == 0


def test_the_first_judge_call_is_credited_with_the_mean_gap():
    r = run([("a", "seeded", 0, 30), ("a", "seeded", 40, 70)], scores=[100, 105])
    assert phases(r).loc["point-wise judge", "per execution s"] == pytest.approx(5)


def test_overhead_is_the_active_time_the_conversations_do_not_account_for():
    r = run([("a", "seeded", 0, 30), ("a", "seeded", 40, 70)])
    ex = per_execution(r)
    assert ex["overhead s"].iloc[0] == pytest.approx(5)  # 70 active, 60 talking, 2 executions


def test_a_parallel_case_takes_its_slowest_repetition():
    r = run([("a", "seeded", 0, 30), ("a", "seeded", 30, 80), ("b", "metamorphic", 80, 90)])
    cases = per_case(per_execution(r))
    assert cases.loc["a", "sequential s"] == pytest.approx(80)
    assert cases.loc["a", "parallel s"] == pytest.approx(50)
    s = schedules(per_execution(r))
    assert s["everything in sequence (measured)"] == pytest.approx(90)
    assert s["cases in parallel, repetitions in sequence"] == pytest.approx(80)
    assert s["everything in parallel"] == pytest.approx(50)


def test_prose_rounding():
    assert say(54) == "about 55 seconds"
    assert say(7.4 * 60) == "about 7.5 minutes"
    assert say(60) == "about 60 seconds"
    assert say(158.8 * 60) == "about 2 h 40 min"
    assert say(106 * 60) == "about 1 h 50 min"
