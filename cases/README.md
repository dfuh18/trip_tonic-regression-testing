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
    tool_errors: none                         # none | corrected
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
per constraint the member gave, or re-query after a thin result set. A number
that differs between two cases without a reason is an accident, and an accident
in a pass criterion is a finding about the harness rather than about the agent.

The agent's wrong-region guard is **not** a reason for a higher bound, and not
a substitute for a criterion either. It drops a result more than 300 km from
the nearest trip anchor and, if that empties the list, refetches restricted to
that radius — all inside one `search_places` call, so it never adds a call to
the trace. At 300 km it is a right-continent check: Sintra and Lisbon are 25 km
apart, so a Lisbon restaurant offered for the Sintra day sails through it. That
a search stayed in the region the member named is judged, not checked.

**A case's tool constraints bind the mode its first turn opens in.** The slash
command is on turn one, and the simulator sends later turns without one — which
is deliberate, because a member who has been answered does not re-issue a
command (D28's note on deny-by-default). So a goal that ends in something
schedulable invites a second turn in which the agent legitimately holds every
tool, and the case then fails an agent doing exactly as it was asked. Write the
goal so the member is satisfied by the reply the case is about.

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

**Permitted and satisfying are different things.** `tool_counts` says a tool
may run and how often; `tools_any_of` says the answer has to come from one of
these. A tool named only in `tool_counts`, with `{min: 0}`, is a probe the
agent may make and may not answer from. The weather case uses it: `get_weather`
is a sixteen-day forecast that cannot reach the trip's November, so answering
from it would be answering about the wrong weeks — but trying it, finding that,
and falling back to the climate table is good behaviour, and forbidding the
probe outright would fail an agent for recovering well (D30).

**A case constrains what its request implies, not what its function is.** An
advisory request asking for a packing list implies the trip does not change, so
the case says so — but it constrains no tools, because a message without a slash
command keeps the agent's whole toolset on purpose and whether to check the
forecast first is the agent's judgement (D29). Read the request, not the label.

**Every case whose request implies something about the trip states the same
four mutation counts.** The write
classes an agent turn can cause on the plan are `trip_blocks.INSERT`,
`itinerary_slots.INSERT`, `itinerary_slots.UPDATE` and
`ai_suggestions.INSERT`. A case states all four, so "this request changes
nothing" and "this request writes exactly one draft" are the same sentence with
one word different, and a line that is missing is visible rather than implied.
Deviations are the point of the case: `/plan` sets `ai_suggestions.INSERT: 1`,
`/reschedule` sets `itinerary_slots.UPDATE: 1`, and both leave the rest at zero.

This is a second signal, not a restatement of the tool constraint: deny by
default reads the trace, the mutation counts read the database. For a case with
no slash command — the factual and advisory ones — the agent keeps its whole
toolset, so the zeros are a real constraint rather than a restatement of
anything.

Counts that are *incidental* to the request are left unasserted, and the case's
`notes` say why: `ai_suggestions.UPDATE` after a draft (the thread-id backfill
is an implementation detail), `itinerary_days.INSERT` when a stop moves onto a
day the fixture left empty (that encodes the fixture, not the agent).

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
`tool_errors` (`none` | `corrected`), `places_surfaced`, `places_named`,
`slot_days`, `slot_count`, `draft_reuses_blocks`, `slot_moved`
(`{block, day, starts_between?, duration_minutes?, clear_of_other_slots?}`),
`mutation_counts` (`table.OP`). A count is an integer or `{min, max}`.

**A case asserts the kind of place, never which one** (D32). "Somewhere for
lunch near Pena Palace" is a type and a region; the venue the agent picks is
its judgement, and a case that named one would make the suite's taste the pass
criterion — and would break the first time that restaurant closed. So a search
is checked with `places_surfaced` and `places_named`, never with a venue list.

**The exception is about who named the place.** A place the *member* named is
hers, and the case asserts it exactly: `slot_moved.block` for the stop she
pointed at, `draft_reuses_blocks` for one she told the agent it already has.
"We already have the monastery saved" is an instruction, and a draft that
ignores the saved stop and finds its own monument has answered a different
request — so the case names it, while saying nothing about which *other* stops
fill the morning. These two keys are the only ones that name a place, the
loader checks both against `fixture.json`, and a case that names a venue the
member did not has crossed back over the line.

**`places_surfaced` and `places_named` are different claims.** The first counts
what `search_places` returned, the second what the reply referenced
(`resulting_state_shape.reply.place_refs`). A search whose results the agent
never mentions satisfies the first and not the second, which is why a
venue-lookup case states both: one says it looked, the other says it answered.

**The draft keys read the latest draft**, which is the one the application
records in `resulting_state_shape.draft` and the plan the member is left with.
A case that permits a revision therefore still has a defined target.

**`tool_errors` has three settings, and the middle one is the interesting
one** (D33). `none` forbids any tool error. `corrected` permits one only where
the agent recovers inside the turn — a later call to a tool the case names has
to succeed — so an error it notices and fixes passes and an error it lives with
does not. Leaving the key out constrains nothing. Write `corrected` where the
application legitimately refuses a reasonable first attempt, or where a tool
the agent may sensibly reach for cannot answer the question it was reached for:
the weather case permits the forecast probe and requires the climate tool
afterwards, because noticing you asked the wrong function and asking the right
one is good behaviour, not a failure.

**A time is asserted as a window, never as a clock reading** (D31). A member
says "around 4" or "Saturday afternoon", and both are ranges — an agent writing
16:15 for the first has understood the request. `starts_between` takes the
inclusive `[earliest, latest]` pair those words license, and a case that really
does mean one minute writes it twice, so the tolerance it intends is always on
the page rather than implied by the absence of one. The day is the exception and
carries no tolerance: the trip has one Saturday.

This is what makes the check survive a fuller fixture. Where the target day
already holds something near the time the member named, shifting off that time
is the *correct* behaviour, so the case widens `starts_between` to the part of
the day the member actually named and asserts `clear_of_other_slots` — the
requirement being that the agent found a free window, not that it found one
particular minute. Narrow windows are for days the fixture leaves empty.

**Length is asserted separately from the start.** `move_slot` takes the end
time as an optional argument and nothing derives it from the stop's duration,
so an agent that sets the start correctly and leaves the stored end alone turns
an hour-long stop into one running to the end of the day — and no assertion
about the start notices. `duration_minutes` is stated in full even where the
case means "unchanged", so that a case cannot silently inherit a length the
fixture changed underneath it.

**A case asserts the outcome, not the route to it.** Where the application
refuses a reasonable first attempt and the agent can recover within the turn,
the bound is widened and `tool_errors` set to `corrected` rather than `none`,
so the recovery passes and an uncorrected error still fails. The retry is not invisible: the analysis
reports tool errors and retries per case, so first-try success stays a readable
number without being a pass criterion.

- Advisory cases constrain no tools (D29); what they constrain about the trip
  follows from the request like any other case. Factual-QA cases carry at least
  one reference; the stored text lives under `references/`.
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

It carries two placeholder travellers besides the simulated member, so that a
request about "the three of us" is about a group the trip actually has. They
are placeholders in the application's own sense — a display name and no account
— and nothing in a repetition can remove them, so they are ensured once rather
than rebuilt, and the gate checks their presence the way it checks regions.

**The judge sees a summary of it on every call** (`fixture.summary`): the
dates, the regions, the travellers, the stops and which of them are scheduled.
Criteria like "fits this trip" or "refers to the palace already on that day"
are otherwise unscorable — a judge that sees only the request and the reply has
no way to know what the trip holds, and would be scoring them on plausibility.
P3 is untouched: the summary is the before-state every repetition starts from,
never what the member did next.

**A case's references are what the agent's own tools return**, not a better
version assembled by hand. `references/alfama_history.md` is the payload of
`read_wikipedia({query: "Alfama"})` verbatim; `lisbon_climate.md` is what
`get_region_climate({place: "Lisbon"})` returns, capped where the tool caps it;
`lisbon_climate_normals.md` is `get_climate_normals` at the fixture's Lisbon
centre. Re-extracting the same articles in the harness produced a richer source
than the tools hand the agent — a section the tool's character cap cuts, a
table its plain-text endpoint strips — and scoring a reply against that is
judging it for not having read what it could not read. Where a case permits
more than one source, every permitted source is stored and the criteria are
worded to hold for each.
