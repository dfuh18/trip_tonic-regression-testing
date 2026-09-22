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


def test_a_disjunctive_requirement_requires_neither_tool_alone():
    """D66. `tools_any_of: [a, b]` passes if EITHER ran, so the case does not
    require `a` and does not require `b`.

    Counting both made three weather cases read as requiring
    `get_region_climate` when the suite would not have noticed it vanishing —
    the agent falls back to `get_climate_normals` and every one still passes.
    An overstatement of coverage inside the instrument that justifies adding
    cases, which is the worst place for one.
    """
    from src.cases import load_cases
    from src.coverage import tools_alternatively_required_by, tools_required_by

    by_id = {c.case_id: c for c in load_cases()}
    weather = by_id["factual_qa_lisbon_november_weather"]
    required = tools_required_by(weather)
    assert "get_region_climate" not in required
    assert "get_climate_normals" not in required
    groups = tools_alternatively_required_by(weather)
    assert groups and {"get_region_climate", "get_climate_normals"} == set(groups[0])


def test_a_single_element_any_of_is_a_real_requirement():
    """Nothing else can satisfy it, so it is a requirement."""
    from src.cases import load_cases
    from src.coverage import tools_required_by

    by_id = {c.case_id: c for c in load_cases()}
    assert "get_climate_normals" in tools_required_by(by_id["factual_qa_lisbon_surf_conditions"])


def test_every_extra_case_is_the_only_route_to_something():
    """The admission rule of D50/D51/D61, enforced rather than argued.

    A case carrying a relation that no other case instantiates, or requiring a
    tool no other case requires, has earned its executions. This asserts the
    inverse of the usual worry: not that coverage is missing, but that a case
    added FOR coverage actually supplies some.
    """
    sole = tables.unique_contribution()
    sole = sole[sole["sole coverage"]]
    for expected in ("venue_lookup_seafood_lisbon__inv2_typos",
                     "scheduling_move_tram__dir1_put_the_monastery_on",
                     "scheduling_move_tram__dir4_off_the_itinerary"):
        assert expected in sole.index, f"{expected} was added for coverage but supplies none"


def test_a_disjunction_is_coverage_not_a_gap():
    """D68. Two tools that both answer correctly are covered as a GROUP.

    Pinning the case to one of them would assert the route rather than the
    outcome (D30) and would forbid a legitimate fallback — the prompt's own
    rule is to use `get_climate_normals` when there are coordinates but no
    usable place name. The suite is only as strict as catches a real
    regression, and an agent that picks the other correct tool has not
    regressed.
    """
    from src.coverage import for_run  # noqa: F401  (import guard only)
    from src.coverage import Coverage

    cov = Coverage(
        declared={"a": ["case1"], "b": ["case1"]},
        required={},
        groups={frozenset({"a", "b"}): ["case1"]},
    )
    assert cov.covered_by_group == {"a", "b"}
    # and neither is reported as the kind of gap that needs a new case
    assert "a" not in cov.permitted_but_never_required
    assert "b" not in cov.permitted_but_never_required


def test_a_tool_with_no_alternative_named_is_still_a_gap():
    """The real gap survives: permitted at min 0, with nothing named in its
    place, means the suite would not notice the capability disappearing."""
    from src.coverage import Coverage

    cov = Coverage(declared={"search_places": ["case1"]}, required={}, groups={})
    assert "search_places" in cov.permitted_but_never_required
