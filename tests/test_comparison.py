"""D23's pass rule and the case verdicts, on hand-built comparisons."""

from src.comparison import Comparison, pass_rates

SEED = "venue_lookup_seafood_lisbon"
FOLLOW = "venue_lookup_seafood_lisbon__inv2_typos"


def C(case, rep, structural="none", good=True, error=None):
    return Comparison(case, rep, f"{case}-{rep}", "base", structural, good, ["tie", "tie"], "", error)


def test_structural_detected_fails_regardless_of_the_judge():
    assert C(SEED, 1, structural="detected", good=True).passed is False


def test_an_unchecked_or_unjudged_execution_decides_nothing():
    assert C(SEED, 1, structural=None).passed is None
    assert C(SEED, 1, good=None, error="judge: 429").passed is None


def test_a_seed_needs_every_repetition():
    rates = pass_rates([C(SEED, r) for r in range(1, 8)] + [C(SEED, 8, good=False)])
    assert rates.loc[SEED, "verdict"] == "fail"
    assert rates.loc[SEED, "judge says worse"] == 1


def test_an_expanded_case_passes_at_three_of_four():
    rates = pass_rates([C(FOLLOW, 1), C(FOLLOW, 2), C(FOLLOW, 3), C(FOLLOW, 4, structural="detected")])
    assert rates.loc[FOLLOW, "verdict"] == "pass"
    assert rates.loc[FOLLOW, "structural fails"] == 1


def test_a_missing_measurement_makes_the_case_incomplete_not_passed():
    rates = pass_rates([C(SEED, 1), C(SEED, 2, good=None, error="judge: 429")])
    assert rates.loc[SEED, "verdict"] == "incomplete"
    assert rates.loc[SEED, "not compared"] == 1


def test_a_verdict_survives_the_round_trip_through_its_row(monkeypatch):
    """What `_persist` writes is what `_from_row` reads back (Q33), including
    both orderings in their positions and the kind of baseline."""
    from src import comparison as cmp

    monkeypatch.setattr(cmp, "_judge_identity", lambda: ("judge-model", "judge-pairwise/1"))
    c = C(SEED, 2, good=False)
    c.orderings = ["A", "tie"]
    row = cmp._record("run-1", {"attempt": 1}, c, {"_kind": "test", "cases": {SEED: {"execution_id": "base"}}})
    assert row["ordering_candidate_b"] == "A" and row["ordering_candidate_a"] == "tie"
    assert row["baseline_kind"] == "test" and len(row["baseline_key"]) == 12
    back = cmp._from_row(row)
    assert (back.orderings, back.at_least_as_good, back.passed) == (["A", "tie"], False, False)


def test_a_refusal_is_recorded_without_orderings(monkeypatch):
    from src import comparison as cmp

    monkeypatch.setattr(cmp, "_judge_identity", lambda: ("m", "v"))
    refused = C(SEED, 1, good=None, error="judge: 429")
    refused.orderings = []  # a refusal has no answers, as compare_run records it
    row = cmp._record("run-1", {}, refused, {"cases": {}})
    assert row["ordering_candidate_b"] is None and row["error"] == "judge: 429"
    assert cmp._from_row(row).passed is None


# --- position bias (Q34) ---------------------------------------------------

from src.comparison import holds, passed_under, pattern, wilson  # noqa: E402


def test_patterns_are_read_from_the_candidates_side():
    assert pattern(["B", "A"]) == "consistent: candidate better"
    assert pattern(["A", "B"]) == "consistent: baseline better"
    assert pattern(["A", "A"]) == "same slot both times: first (A)"
    assert pattern(["B", "B"]) == "same slot both times: second (B)"
    assert pattern(["A", "tie"]) == "leans baseline (one ordering)"
    assert pattern(["tie", "B"]) == "leans baseline (one ordering)"
    assert pattern(["B", "tie"]) == "leans candidate (one ordering)"


def test_strict_is_d23_and_the_draw_readings_only_ever_loosen_it():
    for o in (["A", "A"], ["B", "B"], ["A", "tie"], ["tie", "B"], ["A", "B"], ["B", "A"], ["tie", "tie"]):
        strict, slot, anyd = holds(o, "strict"), holds(o, "slot_draw"), holds(o, "any_draw")
        assert strict <= slot <= anyd, o
    assert holds(["A", "A"], "strict") is False and holds(["A", "A"], "slot_draw") is True
    assert holds(["A", "tie"], "slot_draw") is False and holds(["A", "tie"], "any_draw") is True
    assert holds(["A", "B"], "any_draw") is False  # a consistent preference fails under every reading


def test_structural_detected_fails_under_every_reading():
    c = C(SEED, 1, structural="detected")
    assert all(passed_under(c, r) is False for r in ("strict", "slot_draw", "any_draw"))


def test_wilson_interval_brackets_the_share():
    p, lo, hi = wilson(3, 31)
    assert lo < p < hi and 0 <= lo and hi <= 1
