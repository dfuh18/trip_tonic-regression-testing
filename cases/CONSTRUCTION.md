# How the test cases were constructed

The suite has **31 test cases: 13 seeds and 18 metamorphic follow-ups**, over
the four functions of the agent. Seeds run eight times and follow-ups four
(D21), so one full run is 13 × 8 + 18 × 4 = **176 executions**.

This file is the account of *how* they came to be: the order of the steps,
the rules each step followed, and the decision behind each rule. For the file
format read `README.md`; for what a reviewer checks read `REVIEW_CRITERIA.md`.
Decision numbers (`D…`) and log entries (`L…`) point into `../docs/`.

| function | seeds | follow-ups | total |
|---|---|---|---|
| advisory | 2 | 4 | 6 |
| factual_qa | 5 | 4 | 9 |
| scheduling | 4 | 5 | 9 |
| venue_lookup | 2 | 5 | 7 |
| **total** | **13** | **18** | **31** |

---

## 1. The fixture trip comes first

Every case is written against one trip, `fixture.json`: Lisbon and Sintra,
Friday 6 to Monday 9 November 2026, the member plus two travellers, and five
saved stops, three of them scheduled (Tram 28 on Friday morning, the Time Out
Market lunch on Friday, Pena Palace on Sunday). A case's expectations name
this state: "after the lunch already on Friday", "the tram ride", "the Sintra
day". What a case assumes about the trip is listed in its
`fixture_depends_on`, and the loader refuses a case that names a stop or day
the fixture does not have.

- **A fresh trip for every repetition** (D38). Each execution gets its own copy
  built from the fixture, so every repetition starts from exactly the same
  state and nothing is ever deleted. The ids the build produced and the
  build's own writes are recorded on the execution (D26), so every later write
  can be traced back to what the case did rather than what the build did.
- **One case moves the calendar** (D54). A forecast exists only 16 days ahead,
  so `factual_qa_lisbon_trip_forecast` runs on the same trip dated to start
  three days after the run (`fixture_dates: near`). Every other case keeps the
  fixed November dates, which is what lets a criterion say "the Sunday" and
  mean it.

## 2. The seeds

**The starting point was two seeds per function** (D21): eight cases that
cover the minimum functionality of the four functions of §1.4. They were
drafted with LLM help and then reviewed (step 5), as §3.1 describes.

**The suite then grew by tool coverage, not by budget** (D50). A tool coverage
report showed which agent tools no case could reach, and seeds were added only
where a tool was otherwise unreachable, or where a behaviour the study depends
on was untested:

| seed | function | why it exists |
|---|---|---|
| `advisory_packing_list` | advisory | the original eight (D21) |
| `advisory_sintra_full_or_half_day` | advisory | the original eight |
| `factual_qa_alfama_history` | factual_qa | the original eight |
| `factual_qa_lisbon_november_weather` | factual_qa | the original eight |
| `venue_lookup_seafood_lisbon` | venue_lookup | the original eight |
| `venue_lookup_sintra_lunch` | venue_lookup | the original eight |
| `scheduling_belem_morning` | scheduling | the original eight |
| `scheduling_move_tram` | scheduling | the original eight |
| `factual_qa_lisbon_surf_conditions` | factual_qa | the only way to reach `get_climate_normals`; no slash command, so choosing the tool is the agent's own judgement (D51) |
| `factual_qa_lisbon_trip_forecast` | factual_qa | a forecast for the trip's own days, on the near-dated trip (D54) |
| `factual_qa_lisbon_forecast_next_days` | factual_qa | its pair: a forecast for the coming days, which must not drift into the trip's dates (D54, D56) |
| `scheduling_dinner_from_offer` | scheduling | two acting turns: a search, then a draft of one of its results (D81) |
| `scheduling_afternoon_then_tram` | scheduling | two acting turns: a draft, then a live move relative to it (D81) |

The two multi-step seeds exist because no earlier case had more than one turn
that acts, so the agent had never been asked to act on something its own
earlier reply offered (Q30, D81). They run at priority 2: they are not the
minimum functionality of any one function, but two of them joined.

## 3. What a case consists of

Each case is one YAML file (`README.md` has the full format):

| part | what it holds | rule |
|---|---|---|
| `user_profile`, `goal` | who the simulated member is and what satisfies them | the simulator plays the member from these; the goal also says when to stop |
| `opening_turn` | the first message, the only fixed text | written the way a member types: "the 7th", "Saturday afternoon", never ISO dates, coordinates or tool names |
| `intent` | the slash command, if the member uses one | `/find`, `/plan`, `/reschedule` restrict the agent's tools, so a case uses one only where a member would |
| `expected_tool_sequence` | the tools that must appear, in order | a subsequence of the trace; the ordering constraint itself |
| `declared_constraints.checks` | what the execution's outcome must satisfy | see step 4 |
| `scoring_criteria` | the judge's rubric, one line each | scored on the first reply (D34); a criterion must be decidable from the request, the reply and the trip summary |
| `references` | source material, factual_qa only | what the judge checks a factual answer against (D35) |
| `repetitions_n` | 8 for seeds, 4 for follow-ups | D21 |
| `fixture_depends_on` | stops and days of the fixture the case assumes | validated by the loader |

## 4. The rules the checks follow

A check is a claim about the outcome of **one execution**, read from a field
the event model records (D27, D37). Six rules shaped every case, each learned
from a defect in an earlier draft:

1. **Deny by default for tools** (D28). A case permits the tools it names and
   nothing else; an unexpected tool call is a structural failure, because a
   behaviour nobody anticipated is exactly what a regression suite exists to
   notice. The three trip-reading tools are always allowed.
2. **Assert the outcome, not the route** (D30). Where the application refuses a
   reasonable first attempt and the agent recovers, the case accepts the
   recovery (`tool_errors: corrected`) and the retry is reported, not failed.
3. **A time is a window and a length, never a clock reading** (D31). "Around 8"
   becomes `starts_between: [19:30, 20:30]`.
4. **The kind of place, never which place** (D32). A search is checked for how
   many places it surfaced and named, and where they are (`places_near`); no
   case names a venue, except one the member named herself.
5. **A case constrains what its own request implies** (D29). Asking for a
   packing list implies the trip does not change, so the advisory seeds assert
   zero writes. That follows from the request, not from a rule about the
   function.
6. **No bound sits on observed behaviour** (D58, D75). Where a correct agent
   used exactly the maximum a case allowed, the bound was raised: a correct
   agent searching once more would otherwise have failed, and a false
   regression is ranked the worse of the two errors (D30).

Checks compare nothing across executions. Comparing two replies is the judge's
job, which is why the scoring criteria exist beside the checks (D27, D49).

## 5. The metamorphic follow-ups

Each follow-up changes its seed's request in one controlled way, a
**metamorphic relation** from a fixed catalogue (D22):

| relation | kind | what changes | expected effect |
|---|---|---|---|
| INV-1 paraphrase | invariance | the same request, reworded | same outcome |
| INV-2 typos | invariance | typos and casing | same outcome |
| INV-3 irrelevant detail | invariance | a detail that should not matter | same outcome |
| INV-4 language | invariance | the request in German | same outcome |
| DIR-1 constraint | directional | a constraint added or changed | a stated change |
| DIR-2 day | directional | a different day | the plan moves with it |
| DIR-3 count | directional | a different number of things | a different count |
| DIR-4 negation | directional | something ruled out | it is absent |

**Which relations a seed may take depends on its function** (D22). Venue
lookup and scheduling take all eight. Factual QA takes the invariance
relations and DIR-1 (a different fact). Advisory takes invariance only, since
advice has no structural delta to state.

**Each follow-up was chosen by hand, not generated** (`derivations.py`, D21,
D22). At most one follow-up per relation per seed; every relation is used at
least once (D61, which added the one typo case so the catalogue's claim of
eight relations is true). The suite's 18 follow-ups:

| relation | cases |
|---|---|
| INV-1 paraphrase | 4 |
| INV-2 typos | 1 |
| INV-3 irrelevant detail | 1 |
| INV-4 German | 1 |
| DIR-1 constraint | 5 |
| DIR-2 day | 3 |
| DIR-3 count | 1 |
| DIR-4 negation | 2 |

**How a relation becomes something checkable** (D49). A directional follow-up
inherits its seed's checks and **overrides the ones the change affects**: a
different day gets a different `slot_days`, a ruled-out meal gets excluded
place types. An invariance follow-up inherits the checks unchanged, and
whether the answer stayed the same is left to the judge. Comparing the two
executions' outputs directly was tried and dropped: across four runs of one
seed only one place appeared in all four, so "the same venues as the seed"
would have failed a correct agent.

**A follow-up is a cold open, not an edit of its seed.** Every repetition
starts a new conversation on a fresh trip, so a follow-up never says
"instead" about a request the agent has not seen. It may say "instead" about
something on the trip the agent can read ("move the tram ride to Sunday
instead"): the relation holds between two cases and is never visible inside
either sentence.

**One obvious relation was rejected**: "ask for something narrower, expect
fewer results". `search_places` returns at most five places per call, so a
tighter constraint makes the agent search again and the count goes *up*.

## 6. Review

"LLM-generated and human-reviewed" took **three adversarial rounds** (L07).
The first reading by hand caught wording and missed every defect that
mattered. Three further rounds, each by an independent agent with read access
to the application and a written criteria list (`REVIEW_CRITERIA.md`: 14
criteria per case, 7 per follow-up, questions about the suite as a whole),
found in turn:

- constraints stricter than the member's request, which would have recorded
  false regressions (D30, D31);
- a check with no source, pointing at a logged field that could not decide it;
- a case that permitted a probe it could never forgive, and an unpinned
  question about which reply the judge scores (D33, D34).

**Every case carries the author's approval, bound to the exact text read**
(D74, D78, D84). A review mark records who approved, when, and the case's
`case_version`: a content hash of the file. Editing a case after approval
shows as drift until it is reviewed again. All 31 cases report `current`
(`reviewed.json`).

## 7. Versions and traceability

- **`case_version`**: 12 hex characters of SHA-256 over the case file (D74).
- **`suite_version`**: a hash over every case and the fixture as resolved
  (D62). Two runs compare only when it matches.
- **Per execution**: the fixture ids of its trip and the build's own writes
  (D26, D38), so each state change is traceable to the turn that made it.
- **The baseline**: each case's best structurally clean execution of run
  `1a872c09`, adopted by the author into `baseline.json` (D86, D96).

## Where to find things

| what | where |
|---|---|
| the cases | `*.yaml` in this folder, one per case |
| the format | `README.md` |
| the review criteria | `REVIEW_CRITERIA.md` |
| the hand-chosen follow-ups and their reasons | `derivations.py`, applied in `../notebooks/sim/02_expand` |
| the fixture trip | `fixture.json`, built by `../src/fixture.py` |
| review marks | `reviewed.json` |
| the adopted baseline | `baseline.json` |
| the loader and the case shape | `../src/cases.py` |
| the checker | `../src/checker.py` |
