"""The retention rule (B17): which runs' fixture trips survive.

Only the rule is tested here, and deliberately: it is the whole safety
argument, deleting a trip is irreversible, and the rule should be checkable
without a database in front of it.
"""
from src.cleanup import keep_run_ids

# Newest first, as study_runs is read.
RUNS = [
    {"id": "r4", "baseline_ref": "r2"},   # latest regression run, judged against r2
    {"id": "r3", "baseline_ref": "r2"},
    {"id": "r2", "baseline_ref": None},   # the adopted baseline
    {"id": "r1", "baseline_ref": None},   # a superseded baseline
]


def test_the_latest_run_and_its_baseline_are_kept():
    """Exactly the pair stage 3.2 compares (D23): a candidate is judged
    against the adopted baseline's replies, so deleting either makes the
    comparison impossible."""
    assert keep_run_ids(RUNS) == {"r4", "r2"}


def test_a_superseded_run_is_not_kept_by_association():
    """r3 names the same baseline, but nothing compares against r3 any more."""
    assert "r3" not in keep_run_ids(RUNS)
    assert "r1" not in keep_run_ids(RUNS)


def test_keeping_more_runs_pulls_in_their_baselines_too():
    assert keep_run_ids(RUNS, keep_latest=2) == {"r4", "r3", "r2"}


def test_a_baseline_run_keeps_only_itself():
    """A run with no baseline_ref is a baseline; there is no earlier half of
    a pair to preserve."""
    assert keep_run_ids([{"id": "b", "baseline_ref": None}]) == {"b"}


def test_nothing_is_kept_when_there_are_no_runs():
    # And build_plan then has an empty keep set, so every fixture trip is a
    # deletion candidate — which is why --apply is never the default.
    assert keep_run_ids([]) == set()
