"""Tests for ``src.segmentation_bench`` — the Q29 scoring, on hand-built turns."""

from __future__ import annotations

from src.segmentation_bench import VARIANTS, all_pairs, fuse, random_runs, score, strip_slashes, within
from src.shapes import ADVISORY, TurnSignals


def T(label, intent=None, acted=(), offered=()):
    return TurnSignals(label, intent, frozenset(acted), frozenset(offered))


EXECUTIONS = {
    # a one-step search, and a second one of the same shape
    "seafood": [T("venue.search", "find", offered={"ChIJ-a"}), T(ADVISORY)],
    "lunch": [T("venue.search", "find", offered={"ChIJ-z"})],
    # a multi-step request: search, then draft one of the results
    "dinner": [T("venue.search", "find", offered={"ChIJ-d"}), T("scheduling.draft", acted={"ChIJ-d"})],
}


def test_within_counts_a_split_multi_step_request() -> None:
    assert within(EXECUTIONS, "shape only")["dinner"] == 2
    assert within(EXECUTIONS, "+ reference")["dinner"] == 1
    assert within(EXECUTIONS, "shape only")["seafood"] == 1


def test_fuse_marks_each_seam() -> None:
    turns, truth = fuse(EXECUTIONS, ["seafood", "lunch", "dinner"])
    assert len(turns) == 5
    assert truth == {2, 3}


def test_score_separates_merge_from_split() -> None:
    pairs = [("seafood", "lunch")]
    merged = score(EXECUTIONS, "shape only", pairs)
    assert merged["boundaries found"] == 0.0 and merged["false boundaries per run"] == 0.0
    assert score(EXECUTIONS, "+ slash", pairs)["runs exact"] == 1.0

    split = score(EXECUTIONS, "shape only", [("lunch", "dinner")])
    assert split["false boundaries per run"] == 1.0
    assert score(EXECUTIONS, "+ slash + reference", [("lunch", "dinner")])["runs exact"] == 1.0


def test_stripping_slashes_leaves_only_what_free_text_gives() -> None:
    stripped = strip_slashes(EXECUTIONS)
    assert all(t.intent is None for turns in stripped.values() for t in turns)
    assert score(stripped, "+ slash", [("seafood", "lunch")]) == score(stripped, "shape only", [("seafood", "lunch")])


def test_the_samplers_are_deterministic() -> None:
    assert len(all_pairs(EXECUTIONS)) == 6
    assert random_runs(EXECUTIONS, 4, 10) == random_runs(EXECUTIONS, 4, 10)
    assert set(VARIANTS) == {"shape only", "+ slash", "+ reference", "+ slash + reference"}
