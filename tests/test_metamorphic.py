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
    assert len(expanded) == 17
    # Every seed with follow-ups takes two, except scheduling_move_tram, which
    # takes three: both schedule_block and unschedule_block are reachable only
    # under /reschedule, so both cases that reach them derive from that seed.
    # factual_qa_lisbon_surf_conditions has none — it was added for tool
    # coverage, is the only case that can reach get_climate_normals, and a
    # perturbation of it would buy no tool the suite does not already have.
    assert set(DERIVATIONS) <= set(seeds())
    for seed_id in DERIVATIONS:
        got = sum(1 for c in expanded if c.base_case_id == seed_id)
        assert got == (3 if seed_id == "scheduling_move_tram" else 2), seed_id
    assert sum(c.repetitions_n for c in cases) == 140


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
