"""Tests for ``src.examples`` — the parts that decide what a printout says."""

from src import examples


def test_findings_name_the_check_that_raised_them():
    # The sentences the checker wrote for the tram case in run e097f78e.
    assert examples.finding_check("draft slots: expected between 2 and 3, got 4") == "slot_count"
    assert examples.finding_check("draft slots outside 14:00-18:00: ['Time Out Market lunch at 12:30']") \
        == "draft_slot_starts_between"
    assert examples.finding_check("'Tram 28 ride through Alfama' starts at 17:00, before the draft on 2026-11-06 "
                                  "ends at 18:30") == "slot_moved.after_latest_draft"
    assert examples.finding_check("move_slot calls: expected between 1 and 2, got 4") == "tool_counts"
    assert examples.finding_check("called read_wikipedia, which this case does not permit (allowed: [])") \
        == "permitted tools (deny by default, D28)"
    assert examples.finding_check("get_climate_normals failed and nothing recovered it: timeout") == "tool_errors"


def test_an_unknown_finding_is_not_guessed():
    assert examples.finding_check("something the checker says for the first time") == "—"


def test_ids_become_stable_tokens_everywhere():
    ps = examples.Pseudonyms()
    uid = "1a872c09-7070-4789-a806-904969f9185d"
    out = ps({"id": uid, "nested": [f"ref {uid}", {"x": uid}], "n": 3})
    assert out == {"id": "‹id 1›", "nested": ["ref ‹id 1›", {"x": "‹id 1›"}], "n": 3}


def test_signature_reads_as_words():
    sig = ("scheduling", ("search_places", "propose_plan"), (("propose_plan", "1"), ("search_places", "3+")), "1",
           (True, True, False, False))
    assert examples._signature_text(sig) == ("scheduling · search_places → propose_plan · calls: propose_plan ×1, "
                                             "search_places ×3+ · turns: 1 · parameters: location, date")


def test_checks_become_one_row_each_and_null_checks_are_left_out():
    text = """
case_id: c
declared_constraints:
  checks:
    tool_counts: {search_places: {min: 1, max: 4}, get_weather: {min: 0, max: 1}}
    places_surfaced: {min: 1}
    slot_days: ['2026-11-06']
    draft_slot_starts_between: ['14:00', '18:00']
    slot_moved: {block: Tram 28, starts_between: ['15:00', '19:30'], duration_minutes: {min: 45, max: 90},
                 clear_of_other_slots: true}
    mutation_counts: {trip_blocks.INSERT: 0}
    edits: null
"""
    rows = {r["check"]: r["what it expects"] for r in examples.case_checks(text)}
    assert "edits" not in rows
    assert rows["tool_counts"] == "search_places 1–4, get_weather 0–1"
    assert rows["places_surfaced"] == "≥ 1"
    assert rows["slot_days"] == "2026-11-06"
    assert rows["draft_slot_starts_between"] == "14:00–18:00"
    assert rows["slot_moved"] == "block Tram 28; starts between 15:00–19:30; duration minutes 45–90; clear of other slots"
    assert rows["mutation_counts"] == "trip_blocks.INSERT 0"
    assert "declared_constraints" not in examples._case_summary(text)
