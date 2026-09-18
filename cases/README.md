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
