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
goal: Get two or three well-rated seafood restaurants near Cais do Sodre.
opening_turn: "/find good seafood places near Cais do Sodre, nothing too pricey"
intent: find                                  # the slash command, or omit
expected_tool_sequence: [search_places]       # the ordering constraint itself, see below
declared_constraints:
  checks:                                     # everything about THIS execution
    tool_counts: { search_places: { min: 1, max: 3 } }
    no_tool_errors: true
    places_surfaced: { min: 1 }
    mutation_counts: { "trip_blocks.INSERT": 0 }
  predicates: []                              # only comparisons with ANOTHER execution
scoring_criteria:                             # the ten-point rubric, one line each
  - Names two or three real restaurants, each with a reason it fits.
  - Stays near Cais do Sodre; does not wander to another city.
  - Reflects the budget cue without lecturing about it.
references: []                                # factual_qa only: title, section, path
repetitions_n: 8                              # 8 for seeds (3.1), 4 for follow-ups (D21)
metamorphic_relation: null                    # INV-1..4 / DIR-1..4 for follow-ups (D22)
fixture_depends_on: []                        # stop titles / days in fixture.json the case assumes
notes: Minimum-functionality case for the venue lookup function.
```

## How a case is written

**The opening turn is what a member would type.** Not a machine-readable
request: no ISO dates, no coordinates, no tool names. A member says "the 7th",
"Saturday afternoon", "the Sintra day" or "around 4", and resolving those is
part of what the case tests. A case phrased for the agent's convenience
measures an easier system than the one participants use, which would quietly
undermine the comparison Chapter 4 rests on.

**`expected_tool_sequence` is the ordering constraint**, not a description of
one. The tools listed must appear in the trace in that order, as a subsequence.
A grounded plan therefore writes `[search_places, propose_plan]` and gets both
the presence and the order from one field; there is no second place to say it.

**Cases of the same function carry the same bounds** unless the case's `notes`
say why they differ. `search_places` is `{min: 1, max: 3}` in both venue-lookup
seeds: at least one search, and up to three because the agent may search once
per constraint the member gave, or re-search after the region guard drops a
result. A number that differs between two cases without a reason is an
accident, and an accident in a pass criterion is a finding about the harness
rather than about the agent.

**A case lists the tools it expects; every other tool is forbidden.** Deny by
default (D28). There are no zeros to write: `propose_plan` is already forbidden
in a `/find` case because the case never names it, and so is every tool nobody
thought to forbid — which is the point, since an unexpected tool call is
exactly the kind of behaviour change a regression run exists to catch.

Two things follow. The three read tools — `get_trip_details`,
`list_trip_blocks`, `get_itinerary` — are always allowed: they read the trip's
own state, write nothing, and the agent calls them only when its preloaded
context falls short, which varies between runs of one case. And a case that
names no tool at all constrains none, which is how the advisory seeds stay free
to ground their advice in a forecast.

## checks and predicates

The split is about **arity, not about where the data comes from** (D19, D27).
Both read the same recorded execution.

- `checks` describe **one** execution: which tools ran and how often, whether
  any tool errored, what the draft held, which stop ended up in which window,
  what the database recorded. All of it is declarative, and the loader
  validates every key, so a constraint nothing evaluates cannot be written.
- `predicates` compare **two** executions, which no schema can state because
  the other execution has to be in hand. Every one of them is a metamorphic
  relation: `same_venues_as_base`, `different_venues_from_base`,
  `same_tool_sequence_as_base`.

The check keys the checker (B08) knows: `tool_counts`, `tools_any_of`,
`no_tool_errors`, `places_surfaced`, `slot_days`, `slot_count`, `slot_moved`
(`{block, day, start_time?}`), `mutation_counts` (`table.OP`). A count is an
integer or `{min, max}`.

- Advisory cases carry criteria and no constraints (P4). Factual-QA cases carry
  at least one reference; the stored text lives under `references/`.
- `repetitions_n` and the relation catalogue are rulings (D21, D22), not
  choices a case makes on its own.
- `fixture_depends_on` names what the case reads off the starting trip: stop
  titles from `fixture.json` and day dates inside the trip's range. Titles,
  because that is what the trip, the mutation rows and the case's own opening
  turn call a stop - there is no second vocabulary to translate. The loader
  rejects a name the fixture does not have, so renaming a stop out from under a
  case fails loudly instead of changing what the case tests.

## The fixture

Every repetition starts from the trip in `fixture.json`, rebuilt through the
application's own API and checked by the precondition gate before the case runs
(invariant 1, D03 — see `src/reset.py`). Cases are written against it: a stop it
does not contain cannot be rescheduled, and a day outside its range cannot be
planned. `notebooks/sim/01_cases.ipynb` renders it in full.
