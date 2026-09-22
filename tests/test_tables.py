"""The frame views agree with the text reports they are built from (D64)."""

import pytest

pd = pytest.importorskip("pandas")

from src import tables
from src.metamorphic import ELIGIBLE, RELATION_NAMES


def test_relations_frame_matches_the_text_report():
    """Two views, one source. If these drift, a notebook and a run log would
    make different claims about the same suite."""
    from src.metamorphic import relation_coverage

    frame = tables.relations()
    for rel, _, opportunity, used in relation_coverage():
        assert frame.loc[rel, "eligible seeds"] == opportunity
        assert frame.loc[rel, "follow-ups"] == used


def test_every_relation_appears_in_both_tables():
    assert set(tables.relations().index) == set(RELATION_NAMES)
    assert set(tables.eligibility().index) == set(RELATION_NAMES)


def test_the_eligibility_grid_says_yes_exactly_where_the_matrix_does():
    """The grid is the defence of the uneven distribution, so it has to be the
    matrix and not a hand-written copy of it."""
    grid = tables.eligibility()
    for function, allowed in ELIGIBLE.items():
        for relation in RELATION_NAMES:
            expected = "yes" if relation in allowed else "-"
            assert grid.loc[relation, function] == expected, (relation, function)


def test_the_grid_shows_why_dir_relations_have_fewer_cases():
    """The point of the table: DIR-2/3/4 are blank for the two functions where
    changing a day or a count is not a perturbation of anything."""
    grid = tables.eligibility()
    for relation in ("DIR-2", "DIR-3", "DIR-4"):
        assert grid.loc[relation, "advisory"] == "-"
        assert grid.loc[relation, "factual_qa"] == "-"
        assert grid.loc[relation, "scheduling"] == "yes"


def test_suite_frame_covers_every_case():
    from src.cases import load_cases

    frame = tables.suite()
    assert len(frame) == len(load_cases())
    assert set(frame["fixture"]) <= {"fixture", "near"}


class _V:
    def __init__(self, outcome="none", findings=()):
        self.outcome, self.findings = outcome, list(findings)


def _row(case, rep=1, attempt=1, provenance="seeded", base=None, error=None):
    return {"case_id": case, "repetition": rep, "attempt": attempt, "provenance": provenance,
            "base_case_id": base, "error": error}


def test_structural_rows_stay_distinguishable_across_attempts():
    """D53 keeps every attempt, so (case, rep) stopped identifying a row.

    Without the attempt in the index the table drew two identical-looking rows
    for one repetition — and the same missing key in the CHECKER's memo served
    the second attempt the first one's verdict, reporting a repetition that had
    recovered as still failing.
    """
    results = [
        (_row("a", attempt=1, error="agent returned 503 on turn 1"), _V("detected", ["llm_error"])),
        (_row("a", attempt=2), _V("none")),
    ]
    frame = tables.structural(results)
    assert frame.index.is_unique
    assert list(frame["outcome"]) == ["detected", "none"]


def test_perturbation_compares_the_highest_attempt():
    """A follow-up must be compared against the seed attempt that actually
    ran, not against whichever row happened to come last."""
    import src.execution as exmod

    seen = []

    def fake_load(row, base=None):
        seen.append((row["case_id"], row["attempt"]))

        class E:
            place_ids = set()

            def tool_sequence(self):
                return ()

        return E()

    original, exmod.load = exmod.load, fake_load
    try:
        results = [
            (_row("seed", attempt=1, error="agent returned 503 on turn 1"), _V()),
            (_row("seed", attempt=2), _V()),
            (_row("seed__dir1", provenance="metamorphic", base="seed"), _V()),
        ]
        tables.perturbation(results)
    finally:
        exmod.load = original
    assert ("seed", 2) in seen and ("seed", 1) not in seen
