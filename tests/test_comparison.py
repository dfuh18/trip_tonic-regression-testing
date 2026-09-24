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
