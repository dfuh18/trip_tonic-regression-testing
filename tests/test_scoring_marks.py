"""The judge scores turn 1 only (D34, D82); a report must say so where an
execution ran further turns, so a score never reads as the whole exchange."""

from src.scoring import ScoreRun, Scored, report


def test_a_multi_turn_score_is_marked_as_turn_one_only() -> None:
    run = ScoreRun(run_id="r", results=[
        Scored("scheduling_dinner_from_offer", 1, 9, "fine", 400, turns=2, later_acting_turns=1),
        Scored("venue_lookup_seafood_lisbon", 1, 10, "fine", 300),
    ])
    text = report(run)
    assert "judged turn 1 only (D34)" in text
    assert "scheduling_dinner_from_offer" in text.splitlines()[1]
    assert "venue_lookup_seafood_lisbon" not in text.splitlines()[1]
    assert "[judged turn 1 of 2; turns 2-2 not judged]" in text


def test_a_closing_turn_that_did_nothing_carries_no_mark() -> None:
    run = ScoreRun(run_id="r", results=[Scored("advisory_packing_list", 1, 9, "fine", 300, turns=2)])
    assert "judged turn 1 only" not in report(run)
