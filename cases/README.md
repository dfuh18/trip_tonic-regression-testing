# Test cases

One YAML file per case, named after its `case_id`. `src/cases.py` is the one
definition of the shape; a file it rejects names the file and the key. Files
starting with `_` are drafts and are not loaded.

```yaml
case_id: venue_lookup_seafood_lisbon          # = file name
base_case_id: null                            # set for a metamorphic follow-up
provenance: seeded                            # seeded | metamorphic | retained
run_priority: 1                               # P7: 1 = minimum functionality, first
function: venue_lookup                        # venue_lookup | scheduling | factual_qa | advisory
user_profile: >
  Marta, 34, planning a long weekend in Lisbon with two friends. Eats fish,
  budget-conscious, types short messages.
goal: Get two or three well-rated seafood restaurants near Cais do Sodré.
opening_turn: "/find good seafood places near Cais do Sodré, not too pricey"
intent: find                                  # the slash command, or omit
expected_tool_sequence: [search_places]
declared_constraints:                         # D19: declarative checks + named predicates
  checks:
    tool_sequence: [search_places]
    tool_counts: { search_places: { min: 1, max: 2 } }
    mutation_counts: { "trip_blocks.INSERT": 0 }
  predicates: [no_tool_errors]
scoring_criteria:                             # the ten-point rubric, one line each
  - Names two or three real restaurants, each with a reason it fits.
  - Stays near Cais do Sodré; does not wander to another city.
  - Reflects the budget cue without lecturing about it.
references: []                                # factual_qa only: title, section, path
repetitions_n: 8                              # 8 for seeds (§3.1), 4 for follow-ups (D21)
metamorphic_relation: null                    # INV-1..4 / DIR-1..4 for follow-ups (D22)
fixture_depends_on:                           # stop titles / days in fixture.json the case assumes
  - Tram 28 ride through Alfama
  - '2026-11-07'
notes: Minimum-functionality case for the venue lookup function.
```

- `declared_constraints.checks` keys the checker (B08) knows: `tool_sequence`
  (an ordered subsequence of the trace), `tool_counts`, `slot_days`,
  `slot_count`, `mutation_counts` (`table.OP`). A count is an integer or
  `{min, max}`.
- `declared_constraints.predicates` name functions in `predicates.py`.
- Advisory cases carry criteria and no constraints (P4). Factual-QA cases
  carry at least one reference; the stored text lives under `references/`.
- `repetitions_n` and the relation catalogue are rulings (D21, D22), not
  choices a case makes on its own.
- `fixture_depends_on` names what the case reads off the starting trip: stop
  titles from `fixture.json` and day dates inside the trip's range. Titles,
  because that is what the trip, the mutation rows and the case's own opening
  turn call a stop — there is no second vocabulary to translate. The loader
  rejects a name the fixture does not have, so renaming a stop out from under
  a case fails loudly instead of changing what the case tests.

## The fixture

Every repetition starts from the trip in `fixture.json`, rebuilt through the
application's own API and checked by the precondition gate before the case runs
(invariant 1, D03 — see `src/reset.py`). Cases are written against it: a stop it
does not contain cannot be rescheduled, and a day outside its range cannot be
planned. `notebooks/sim/01_cases.ipynb` renders it in full.
