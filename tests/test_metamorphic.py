"""Deriving follow-up cases (B05).

The derivation decides the *shape* of a follow-up; the wording and the expected
delta are the author's, in cases/derivations.py. These tests are about the
shape, and about the one rule that keeps the suite inside its catalogue.
"""
import pytest

from src.cases import load_cases
from src.metamorphic import (
    ELIGIBLE,
    EXPANDED_N,
    Derivation,
    IneligibleRelation,
    derive,
    implied_predicates,
)


#: The most executions the suite may cost without a fresh decision. D21 set the
#: budget at 128; D50, D51 and D61 each raised it for a case that was the only
#: route to a tool or a relation, and D81 for the two multi-step seeds (Q31).
#: Stated as a ceiling because the rule is "keep it at a minimum to cover all
#: tools" — a number to stay under, not to hit.
D21_EXECUTION_CEILING = 176


def seeds():
    return {c.case_id: c for c in load_cases() if c.provenance == "seeded"}


def test_advisory_cannot_take_a_directional_relation():
    """D22: there is no directional perturbation of 'what should we pack'
    whose expected delta a case could state without inventing a rule about
    advice — so the derivation refuses rather than letting a notebook write
    a case the catalogue does not permit."""
    with pytest.raises(IneligibleRelation) as exc:
        derive(seeds()["advisory_packing_list"],
               Derivation(relation="DIR-4", suffix="x", opening_turn="..."))
    assert "not permitted for advisory" in str(exc.value)


def test_factual_qa_takes_dir1_and_no_other_directional():
    assert "DIR-1" in ELIGIBLE["factual_qa"]
    for relation in ("DIR-2", "DIR-3", "DIR-4"):
        assert relation not in ELIGIBLE["factual_qa"]


def test_a_follow_up_names_its_base_and_runs_at_the_expanded_n():
    seed = seeds()["venue_lookup_sintra_lunch"]
    data = derive(seed, Derivation(relation="INV-1", suffix="inv1_x", opening_turn="where for lunch?"))
    assert data["base_case_id"] == seed.case_id
    assert data["provenance"] == "metamorphic"
    assert data["metamorphic_relation"] == "INV-1"
    assert data["repetitions_n"] == EXPANDED_N


def test_a_follow_up_inherits_every_check_it_does_not_override():
    """Most of a directional case's detection comes from what the
    perturbation did NOT touch."""
    seed = seeds()["scheduling_belem_morning"]
    data = derive(seed, Derivation(
        relation="DIR-2", suffix="dir2_x", opening_turn="...",
        checks={"slot_days": ["2026-11-09"]},
    ))
    checks = data["declared_constraints"]["checks"]
    assert checks["slot_days"] == ["2026-11-09"]           # overridden
    assert checks["draft_reuses_blocks"] == ["Jerónimos Monastery"]  # inherited
    assert checks["turn_errors"] == "none"                 # inherited


def test_a_perturbation_can_drop_a_check_it_makes_untrue():
    """A morning window has no business on a case that asks for a full day;
    leaving it to fail would be a false regression the suite authored itself."""
    seed = seeds()["scheduling_belem_morning"]
    data = derive(seed, Derivation(
        relation="DIR-3", suffix="dir3_x", opening_turn="...",
        drop_checks=("draft_slot_starts_between",),
    ))
    assert "draft_slot_starts_between" not in data["declared_constraints"]["checks"]


def test_no_relation_implies_a_predicate_any_more():
    """D49, measured rather than argued. Four runs of the seeds showed that
    both comparisons were unusable: tool sequences vary (advisory_packing_list
    ran two different ones), and venue sets vary so much that requiring
    equality would fail almost every repetition while requiring difference
    passes on noise. A directional delta is a check override instead."""
    for relation in ("INV-1", "INV-2", "INV-3", "INV-4", "DIR-1", "DIR-2", "DIR-3", "DIR-4"):
        for seed_id in ("venue_lookup_sintra_lunch", "advisory_packing_list",
                        "factual_qa_alfama_history", "scheduling_move_tram"):
            if relation in ELIGIBLE[seeds()[seed_id].function]:
                assert implied_predicates(seeds()[seed_id], relation) == []


def test_derived_checks_carry_no_tuples():
    """PyYAML writes a tuple as !!python/tuple, which safe_load then refuses —
    so a derived case would round-trip to a file the loader cannot read."""
    seed = seeds()["scheduling_move_tram"]
    data = derive(seed, Derivation(relation="INV-1", suffix="inv1_x", opening_turn="..."))

    def no_tuples(value):
        assert not isinstance(value, tuple), value
        if isinstance(value, dict):
            for v in value.values():
                no_tuples(v)
        elif isinstance(value, list):
            for v in value:
                no_tuples(v)

    no_tuples(data)


def test_every_seed_has_its_follow_ups_and_they_all_load():
    """D21's budget as amended by D50, checked against the files.

    Two per seed, except `scheduling_move_tram`, which takes a third. Both
    `schedule_block` and `unschedule_block` are reachable only under the
    `/reschedule` command — `/plan` exposes `propose_plan` and no live edit
    tool — so both cases that reach them must derive from that seed.
    """
    from cases.derivations import DERIVATIONS

    cases = load_cases()
    expanded = [c for c in cases if c.provenance == "metamorphic"]

    # Derived, not pinned: the follow-up count IS what `derivations.py`
    # declares, so asserting a literal would only restate it and would fail
    # every time a derivation is added — which D50, D51 and D61 each did.
    declared = sum(len(pair) for pair in DERIVATIONS.values())
    assert len(expanded) == declared, "a generated case exists with no derivation behind it"

    assert set(DERIVATIONS) <= set(seeds())
    for seed_id, pair in DERIVATIONS.items():
        got = sum(1 for c in expanded if c.base_case_id == seed_id)
        assert got == len(pair), f"{seed_id}: {got} files for {len(pair)} derivations"

    # D21 budgeted two follow-ups per seed. Where a seed takes a third, the
    # reason is recorded — `scheduling_move_tram` because schedule_block and
    # unschedule_block are both reachable only under /reschedule (D52), and
    # `venue_lookup_seafood_lisbon` because it is the one seed whose request
    # can carry a typo to a tool (D61). The property, rather than the names:
    # nothing exceeds two without a recorded exception.
    over_budget = {s: len(p) for s, p in DERIVATIONS.items() if len(p) > 2}
    assert all(n == 3 for n in over_budget.values()), over_budget
    assert len(over_budget) <= 2, (
        f"{len(over_budget)} seeds now exceed D21's two-per-seed budget: "
        f"{sorted(over_budget)} — each needs a decision recording why"
    )

    # A ceiling, not an equality. The budget has moved three times already
    # (128 -> 140 -> 160, D50/D51/D61) and D50 states the rule as "keep it at
    # a minimum to cover all tools", not as a number. An equality here fails
    # the moment the author does the thing the rule allows; a ceiling still
    # catches the case set growing without anyone deciding to grow it.
    executions = sum(c.repetitions_n for c in cases)
    assert executions <= D21_EXECUTION_CEILING, (
        f"{executions} executions exceeds the ceiling of {D21_EXECUTION_CEILING}; "
        f"raise it deliberately, with a decision saying what the extra cases reach"
    )


def test_no_generated_case_has_drifted_from_its_derivation():
    """The YAML is generated; nothing should edit it by hand, and a seed edit
    must reach every follow-up that inherits from it.

    This is the third defect of its class: a fix applied to a seed did not
    reach the follow-ups until the notebook happened to be re-run. Deriving is
    cheap and comparing is exact, so the drift has no reason to survive a test
    run.
    """
    import yaml

    from cases.derivations import DERIVATIONS
    from src.cases import CASES_DIR
    from src.metamorphic import derive

    seed_by_id = seeds()
    drifted = []
    for seed_id, pair in DERIVATIONS.items():
        for derivation in pair:
            want = derive(seed_by_id[seed_id], derivation)
            path = CASES_DIR / f"{want['case_id']}.yaml"
            on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
            if on_disk != want:
                changed = [k for k in want if on_disk.get(k) != want[k]]
                drifted.append(f"{want['case_id']} ({', '.join(changed)})")
    assert not drifted, (
        "generated cases differ from cases/derivations.py: "
        + "; ".join(drifted)
        + ". Re-run notebooks/sim/02_expand.ipynb."
    )


def test_no_persona_carries_harness_commentary():
    """`user_profile` is what the simulator is given to stay in character, so
    anything written there changes what is measured.

    A paste error once appended a paragraph about structural verdicts reading
    `none` to a persona, on four executions, and no verdict would have shown
    it — the case still passed. Harness commentary belongs in `notes`.
    """
    from src.cases import load_cases

    for case in load_cases():
        for phrase in ("structural verdict", "the judge sees", "failure report", "checker"):
            assert phrase not in case.user_profile.lower(), (
                f"{case.case_id}: user_profile contains {phrase!r} — that text is read by the "
                f"simulator as character, not by a person as commentary. Move it to notes."
            )
        assert len(case.user_profile) < 300, (
            f"{case.case_id}: user_profile is {len(case.user_profile)} characters, which is a "
            f"brief that has stopped being a brief."
        )


def test_every_relation_in_the_catalogue_is_instantiated():
    """D22 declares eight relations; the suite must not silently use seven.

    INV-2 had none. Nothing failed, because nothing checks a catalogue against
    itself — and a coverage argument that names eight relations while
    exercising seven is exactly the kind of overstatement D52 was about. If a
    relation is genuinely not worth testing, it should be removed from the
    catalogue and argued for, not quietly skipped.
    """
    from collections import Counter

    from src.metamorphic import RELATION_NAMES as RELATIONS

    got = Counter(c.metamorphic_relation for c in load_cases() if c.metamorphic_relation)
    missing = sorted(set(RELATIONS) - set(got))
    assert not missing, (
        f"the catalogue declares {sorted(RELATIONS)} but no case instantiates {missing}. "
        f"Add one, or remove the relation from D22's catalogue and say why."
    )


def test_a_relation_is_never_used_where_it_is_not_eligible():
    """The defence of the uneven distribution rests on the eligibility matrix,
    so the matrix has to actually bind (D61)."""
    from src.metamorphic import ELIGIBLE

    seed_by_id = seeds()
    for case in load_cases():
        if not case.metamorphic_relation:
            continue
        seed = seed_by_id[case.base_case_id]
        assert case.metamorphic_relation in ELIGIBLE[seed.function], (
            f"{case.case_id} applies {case.metamorphic_relation} to a {seed.function} seed, "
            f"which D22 does not permit"
        )


def test_the_relation_report_states_its_own_limitation():
    """A single-instance relation must say so in the evidence, not only in
    prose — the limitation has to travel with the numbers."""
    from src.metamorphic import relation_report

    out = relation_report()
    assert "single instance" in out
    assert "not a sample" in out


def test_the_expansion_notebook_states_the_real_counts():
    """Prose in a published notebook drifts silently, and this one had drifted
    twice: it claimed sixteen follow-ups derived from eight seeds after the
    suite had grown to eighteen from eleven, and said "those four seeds" of a
    group that had become seven. A reader has no way to check a number that is
    only ever written down.

    Asserted against the case files rather than against a constant, so the
    notebook cannot be right on the day it is edited and wrong afterwards.
    """
    import json
    from pathlib import Path

    from src.cases import CASES_DIR

    nb = json.loads((Path(CASES_DIR).parent / "notebooks" / "sim" / "02_expand.ipynb")
                    .read_text(encoding="utf-8"))
    prose = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")

    cases = load_cases()
    seeds_n = sum(1 for c in cases if c.provenance == "seeded")
    follow_n = sum(1 for c in cases if c.provenance == "metamorphic")
    # Either spelling. The prose was tightened to a report register, where a
    # digit reads better than a word; what matters is that the NUMBER is stated
    # and correct, not how it is spelled.
    # A dict of spellings raises KeyError for a count it has no word for,
    # which is a worse failure than an assertion — the test would crash rather
    # than report. Digits are what the prose uses since it was tightened to a
    # report register; the word form is accepted where it survives.
    words = {8: "eight", 11: "eleven", 18: "eighteen", 29: "twenty-nine"}

    def states(n: int) -> bool:
        low = prose.lower()
        return str(n) in low or (words.get(n) is not None and words[n] in low)

    assert states(follow_n), f"notebook does not say there are {follow_n} follow-ups"
    assert states(seeds_n), f"notebook does not say there are {seeds_n} seeds"
    assert states(len(cases)), f"notebook does not say there are {len(cases)} cases"
    assert str(sum(c.repetitions_n for c in cases)) in prose, "notebook does not state the execution total"
    # The stale phrasings that were actually there.
    for stale in ("sixteen follow-up", "from the eight seeds", "those four seeds"):
        assert stale not in prose.lower(), f"stale count in notebook prose: {stale!r}"


def test_the_admission_table_in_the_notebook_is_not_stale():
    """A stored output describes the code as it was when the cell last ran.

    Caught twice by a reader rather than by a test. Most recently: D71 lowered
    `JOINT_LIMIT` from 3 to 2 — the over-credit an independent review found —
    and the notebook kept showing the 16 cases the old rule credited, including
    three (`factual_qa_alfama_history` and its follow-ups) that the corrected
    rule does not. A published notebook whose table contradicts the code is
    worse than one with no table.

    Only the case list is asserted, not the formatting: pandas may widen,
    wrap or reorder columns between versions and none of that is a claim.
    """
    import json
    from pathlib import Path

    from src import tables
    from src.cases import CASES_DIR

    nb = json.loads((Path(CASES_DIR).parent / "notebooks" / "sim" / "02_expand.ipynb")
                    .read_text(encoding="utf-8"))
    cell = next(
        c for c in nb["cells"]
        if c["cell_type"] == "code" and "unique_contribution" in "".join(c["source"])
    )
    stored = "".join(
        "".join(o.get("data", {}).get("text/plain") or o.get("text") or "")
        for o in cell.get("outputs", [])
    )
    assert stored.strip(), "the admission-rule cell has no stored output — re-run the notebook"

    frame = tables.unique_contribution()
    expected = set(frame[frame["carries coverage"]].index)
    absent = set(frame[~frame["carries coverage"]].index)

    # Whole ids, not substrings: case ids nest (`scheduling_move_tram` is a
    # prefix of `scheduling_move_tram__dir1_...`), so a substring test reports
    # a seed as present whenever one of its follow-ups is listed. The first
    # version of this test had exactly that bug.
    listed = {
        line.split()[0]
        for line in stored.splitlines()
        if line[:1].isalpha() and line.split()
    }
    listed &= expected | absent

    missing = sorted(expected - listed)
    assert not missing, f"notebook's admission table is stale; missing {missing} — re-run it"

    stray = sorted(listed & absent)
    assert not stray, f"notebook's admission table still credits {stray} — re-run it"
