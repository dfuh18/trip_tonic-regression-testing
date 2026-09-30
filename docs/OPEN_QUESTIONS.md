# Open questions

Things the manuscript or the event model leaves unspecified, which an
implementation cannot proceed past without deciding. **Listed here, not decided
here.** When the author rules on one, it moves to `DECISIONS.md` with a `D` id
and is struck from this list.

An agent adds to this file freely. An agent never removes from it.

## Format

```markdown
### Q05 — Repetitions per test case
Raised: 2026-09-20 by agent · Blocks: T12, T14 · Phase: B
The manuscript requires each case to run n times and a pass rate across runs,
but does not fix n.
Options: n=3 (cheap, weak pass-rate resolution) · n=5 (defensible, ~2x cost) ·
n=10 (strong, cost likely prohibitive at suite scale)
Trade-off: pass-rate granularity against Vertex spend and wall-clock per run.
Recommendation: n=5.
Status: open
```

`Blocks` is what makes this list actionable — a question blocking nothing can
wait; one blocking a Phase A task cannot.

---

<!-- TEMPLATE-END — questions below. -->

## Open

### Q37 — [RESOLVED 2026-09-30, see D109] — The criterion each proposition is judged against
Raised: 2026-09-28 by agent (from D104) · Blocks: C05 (the freeze), the study round · Phase: C

After D104 no proposition is tested, so each needs a criterion stated before
the participant data: the observed value it must reach to count as supported.
Without one, the numbers are reported and their meaning decided afterwards.
The notebooks carry a `CRITERIA` parameter and print the observed value beside
it.

Proposals, for the author to fix or replace:
- **P1:** *supported if more than half of participant requests are covered*
  (unit: the request, D100). Per turn and per participant are reported but not
  assessed. Note that the pilot dry run gives 7 of 16 (44 %), which would not
  support it.
- **P2:** *supported if the tools with the highest recovered-error rate in the
  simulated runs are also the tools with the highest rate in the participant
  round, among the tools participants called at least k times.* Needs k, how
  many "highest" means (top 3?), and a stated outcome for when participants
  never call those tools (as in the pilot): **not assessable** rather than
  "not supported".
- **P3:** *supported if the median judge score of positively received replies
  is higher than that of negatively received ones, for thumbs and for
  accept/reject separately.* Needs a rule for a signal with too few replies in
  a group (e.g. not assessable below 3), and it depends on Q35. Alternative:
  demote P3 to an exploratory comparison, which the manuscript then has to say.
Status: resolved — D109 (P1 more than half covered; P2 at least 2 of the top 3
over tools with ≥ 10 calls in each round; P3 thumbs-up mean ≥ 1 point higher,
thumbs only, ≥ 10 replies per group).

### Q36 — [RESOLVED 2026-09-28, see D103] — The simulated round has no execution failures, so P2 has nothing to rank
Raised: 2026-09-28 by agent (from the first run of `study/06_analysis`) · Blocks: P2's claim, C05 (the P2 expectation) · Phase: C

Under D101's definition (a turn with `error_code` set, latest attempts only,
D53), the compared runs `1a872c09` and `e097f78e` show **0 failures in 426
simulated turns**. Every per-type simulated rate is 0, so the ranking P2
compares against is flat and Kendall's τ is undefined whatever the
participants do. The failures the simulation did see sit elsewhere:
- superseded attempts (the platform, D53): 0 in these two runs;
- tool calls that came back an error and were recovered within the turn:
  11 of 43 `get_weather` calls, 3 of 43 `move_slot`, 2 of 19
  `get_climate_normals`. These are not execution failures by §4.2.3's
  definition.

Options: **A** keep the definition, and report P2 as "no execution failure in
simulation, n = 426; the participant rate is compared against zero", with no
τ · **B** count every attempt, including superseded ones, in both rounds
(0 here, but not 0 across all runs) · **C** add tool-level errors as a
secondary P2 reading, "failures the agent recovered from", ranked the same way.
Trade-off: A is honest and leaves P2 without a rank claim. C gives the ranking
something to rank, but it is not what §4.2.3 calls an execution failure.
Recommendation: **A as the primary result, C reported beside it**, with the
manuscript stating that the simulation surfaced no execution failures.
Added 2026-09-28: C is computed in `06_analysis` §6 as a descriptive
secondary reading (`analysis.recovered_error_rates`, per tool and per request
type, Wilson intervals, τ-b without p), pending this ruling. On the pilot, none
of the three tools that errored in simulation was called.
Status: resolved — D103 (C as P2's measure, compared per tool; request type and
shape secondary)

### Q35 — How the judge scores participant replies (P3)
Raised: 2026-09-28 by agent (building C02) · Blocks: P3, C05 (the judge protocol version) · Phase: C

P3 needs a point-wise score for each participant reply, and the judge cannot
produce one as built:
1. **Rubric.** `score_pointwise` takes a `Case` and scores against that case's
   own criteria. P3 asks for "criteria applied according to the assigned
   request type", and no per-`request_type` rubric exists.
2. **Context.** Every call prepends the fixture trip (D54). A participant asks
   about their own trip, so the fixture would mislead the judge. Their trip's
   summary would have to be built from their data at the time of the turn.
3. **Storage.** `study_scores` is keyed to a simulated execution
   (`execution_id`) and is documented as simulation-only. Participant scores
   need a table or a nullable key: an event-model change, and a new place
   where a judge rationale about participant content is stored.
4. **Which turns.** D82: P3 scores the opening turn of each request, which D100
   now defines. Follow-ups are excluded.

Options for 1: write four request-type rubrics (a new judge prompt version,
reviewed like the case criteria) · reuse a representative case's criteria per
type. For 2: summarise the member's trip as of the turn · no trip context, with
trip-dependent criteria removed from the rubrics. For 3: a
`study_participant_scores` table (service role only, cascading from the
session like every study table, D14) · no persistence, scores kept only in the
notebook run.
Recommendation: four new request-type rubrics; no trip context and no
trip-dependent criteria (the smallest change to what the judge sees); a new
cascading table, so a withdrawal deletes the scores with everything else.
`06_analysis` §4 is written to consume the scores the moment they exist.
Status: open

### Q34 — [RESOLVED 2026-09-24, see D88] — What a seed verdict means against a best-of baseline
Raised: 2026-09-24 by agent (from the comparison rehearsal, `sim/04_regress`) · Blocks: reading B11's verdicts · Phase: B

Rehearsal: n = 1 run 5f4f6841 against a test baseline of each case's best
execution (D86). 8 of 31 cases fail: 1 structurally (the duplication defect),
4 with both orderings preferring the baseline on stylistic grounds the judge
calls "slightly better" (candidates scoring 9–10 point-wise), and 3 because
the two orderings disagree (position bias, 3 of 31). Three of 13 seeds
already fail on the judge at n = 1. At n = 8 with D23's 8/8 rule, most seeds
will likely fail, and a seed `fail` will mostly mean "not reliably as good as
its best reply" rather than "regressed".

Options:
- **A — keep D23 and D86 as they are** and report seed verdicts with that
  reading stated. Judge fails are read one by one, as `04_regress` §5 does.
- **B — count a disagreeing pair as undecided** rather than failed: position
  bias becomes a measured judge variance, not a failure of the agent.
- **C — let the pair-wise prompt say what a tie is**: differences it would
  itself call "slight" are a tie. This changes the judge protocol (a new
  prompt version) and the D23 threshold in effect.
- **D — calibrate first**: compare the baseline run against *itself*
  across repetitions (rep 1 vs rep 2 …) at full n. That measures how often
  the judge prefers one of two replies from the *same* system, which is the
  noise floor a regression has to clear.

Trade-off: A is honest but may make seed verdicts uninformative. B and C
change what counts as a failure. D costs judge calls but turns the question
into a number before any rule is changed.
Recommendation: **D on the real baseline run, then decide between A and B.**
C only if D shows the judge's "slightly better" is mostly noise.
Status: resolved — D88 (any contradictory pair is a position draw: passes, counted and listed)

### Q33 — [RESOLVED 2026-09-24, see D87] — Where pair-wise verdicts are stored
Raised: 2026-09-24 by agent · Blocks: B11 at full n (not the rehearsal) · Phase: B

`src/comparison.py` judges a candidate run against the adopted baseline
(D23, both orderings). The verdicts are the regression run's result, and
today they live in a JSON cache under `runs/comparisons/`, which git
ignores. That survives a lost kernel (it resumes rather than re-judges), but
it is on one machine, outside the record, and nothing in the database says
a run was ever compared. Point-wise scores had the same problem until D71
gave them `study_scores`.

Options: **A** a `study_comparisons` table shaped like `study_scores`
(candidate execution, baseline execution, judge model, pair-wise prompt
version, both orderings, rationale, error), append-only, unique per
(candidate execution, baseline execution, judge model, prompt version) ·
**B** keep the JSON cache and commit the regression notebook's outputs as
the record · **C** store the verdicts on the candidate's
`study_case_executions` row.
Trade-off: A is a migration and a new table in the event model, but it makes
the result queryable next to everything it is joined with, which is the
reason D71 exists. B leaves the result of stage 3.2 outside the database. C
mixes a comparison into the execution record, and an execution can be
compared against more than one baseline.
Recommendation: **A**, added before the full regression run. The rehearsal
can proceed on the cache.
Status: resolved — D87 (A, `study_comparisons`)

### Q32 — [RESOLVED 2026-09-24, see D82: A] — What the judge scores when a request spans turns
Raised: 2026-09-24 by author · Blocks: marking D81's seeds, C02 (P3), C05 (freeze) · Phase: B and C

D34 has the judge score the first reply against `case.opening_turn`. §3.4
says the judge receives "a textual response", and P3 says it is given "the
user's request and the agent's response only". The unit is one (request,
reply) pair. For the two multi-step seeds that pair is the turn *before* the
continuity, so whether the agent did what the member meant on turn two is
scored by nothing (Q31 item 6).

Scoring turn two is easy in code (`score_pointwise` takes any request and
reply). Three things make it a design question rather than a code change:

1. **Turn two's request is not fixed.** The simulator writes it, and it
   differs between repetitions and between the baseline and the regression
   run. Pair-wise comparison (D23) then compares answers to *different*
   requests.
2. **Turn two is unjudgeable without turn one.** "The second one" and "the
   end of that afternoon" only mean something next to the reply before them.
   Giving the judge that context goes beyond "request and response only".
3. **The same problem exists in the participant round, where it matters
   more.** A participant's follow-up turn is a suggestion that gets thumbs
   (D08), and P3 scores it blind to context. Scored alone, "yes, add the
   second one" → "Done, drafted for Saturday at 8" cannot be judged. So
   P3 needs to know which turn opens a request, which is Q29's segmentation.
   A segmentation error then becomes a P3 sampling error.

Options:
- **A — keep D34.** Score only the opening turn, check continuity
  structurally, state the limit. In P3, score only turns that open a request
  (by Q29's rule) and exclude follow-ups.
- **B — score the continuation turn with its context.** A second criteria list
  per multi-step case, and a second point-wise score for the continuation
  turn, whose input is the request's earlier turns plus that turn's request
  and reply. Pair-wise is used on the opening turn only; the continuation is
  compared point-wise, because its request differs between runs. In P3,
  follow-up turns are scored the same way, with context from Q29's segment.
- **C — score the whole transcript** against a conversation-level rubric.
  This departs furthest from §3.4's "a textual response" and from D23's
  pair-wise design.

Trade-off: A keeps the manuscript's wording and the judge untouched, but
leaves continuity to the checks and drops follow-up turns from P3. B covers
the gap in both rounds, but changes the judge's input (a new prompt version),
amends P3's "request and response only" to "request, its earlier turns, and
response", and makes P3 depend on Q29.
Recommendation: **A for the simulation now, B decided together with Q29.**
Whether the participant round needs follow-up turns in P3 depends on how
many turns are follow-ups, which the pilot shows. Record in C05 whichever
is chosen.
Status: resolved — D82 (A; B revisited with Q29 after the pilot)

### Q31 — [RESOLVED 2026-09-24, see D84] — What the two multi-step seeds needed beyond their case files
Raised: 2026-09-24 by agent (from D81) · Blocks: marking the two seeds reviewed · Phase: B

Each item is implemented so that the suite loads and the gates run. Each is on
the stop-and-ask list, so none is decided until the author rules at review.

1. **Two new check keys** (D37: added when a case needs them, and each reads
   a field the application already records).
   - `draft_uses_earlier_place`: the latest draft holds a place a reply on an
     *earlier* turn named. It compares the propose_plan argument
     `block.google_place_id` with that reply's
     `chat_messages.metadata.refs[].googlePlaceId`. It cannot check *which*
     offered place was meant ("the second one"): the refs are not stored in
     reply order and include places the reply did not mention.
   - `slot_moved.after_latest_draft`: the moved stop starts no earlier than
     the latest draft's last slot on that day ends.
2. **A third admission route.** D50 admits a case beyond D21's budget only as
   the sole route to a tool or a relation. Neither seed reaches a new tool,
   so `tables.unique_contribution` now also counts a check key only that case
   asserts. That also credits three existing follow-ups with keys they alone
   assert (`places_excluded_types`, `slot_scheduled`, `slot_unscheduled`). None
   of those needed it: each was already admitted on a tool or a relation.
3. **Execution ceiling 160 → 176** (two seeds × 8).
4. **`run_priority: 2`** for both, so that a priority-only run still means
   "the minimum-functionality seeds".
5. **No metamorphic follow-ups yet.** D21 budgets two per seed. D51 set the
   precedent that a seed may take none when a perturbation buys nothing new.
   Whether these seeds should take any is open.
6. **What neither round verifies.** The judge scores the first reply only
   (D34), which for both seeds is the turn before the continuity. So whether
   the agent picked the place the member *meant* is checked by nothing.

Recommendation: accept 1 to 4, and take no follow-ups (5) until a probe run
shows the seeds pass reliably. Record 6 as a stated limit rather than
widening the judge protocol.
Status: resolved — D84 (seeds approved as written; no follow-ups for now; item 6 a stated limit)

### Q30 — [RESOLVED 2026-09-24, see D81] — The suite has no multi-step request
Raised: 2026-09-23 (from Q29) · Blocks: validating any Q29 rule against the split error · Phase: B

Every one of the 29 cases has exactly one turn that calls a tool (42cab17a).
Nothing in the suite looks like "find seafood" → "add the second one", which
is one request carried across two acting turns of different shape. Two
consequences follow:
- **Q29's split error is unmeasurable.** The fusion bench (`07_shapes` §8)
  can only produce merges.
- **The agent is untested on it.** Acting on a place it surfaced a turn
  earlier is a behaviour of its own (it must resolve "the second one"
  against its previous reply), and no case exercises it.

Options: add one seed, e.g. a venue search followed by scheduling one of the
results, with its metamorphic follow-ups derived as usual · add two (the
second from draft → edit) · leave the suite as is and report the split error
as unmeasured.
Trade-off: each seed adds executions to the baseline and review work, and
changes `suite_version`. Without one, a Q29 rule is validated in one error
direction only.
Status: resolved — D81 (two seeds)

### Q29 — [RESOLVED 2026-09-28, see D100] — The participant round has no request boundary
Raised: 2026-09-23 by author · Blocks: C02 (coverage per request, D24's `turns`), C05 (freeze) · Phase: C

In the simulation a case is one request, and in 42cab17a one Tonic run. In the
participant round only turns are separated (one `study_suggestions` row
each). The one grouping above a turn is the Tonic run, which collects a
member's turns until 30 minutes of silence, so it can hold several requests.
D24's signature needs member turns per interaction. Per-turn labels fill
`advisory` with "thanks" and "yes, do it". And the two rounds count
different units.

Options: **A** a request is one turn (D07) · **B** a request is one Tonic
run · **C** split a run wherever the acting shape changes, with no-tool
turns joining the request before them (`shapes.segment`) · an offline
segmenter model over `user_turn` (admissible, but adds a model to pin and
validate). Letting the agent tag a new request is excluded: it changes the
agent's prompt and output (root rule 4).

Evidence (`notebooks/sim/07_shapes` §8): recorded executions fused into
synthetic runs, with their true boundaries known. Under shapes7, C splits
83.5 % of the 812 ordered pairs correctly and finds ~80 % of boundaries in
random runs of 3/5/8 requests. **Every miss is two same-shape requests
merging.** Of 8 388 recovered requests, none carries a shape absent from
its run. Mean distortion of shape shares per 5-request run is 0.086 (total
variation). The split error (one request whose turns change shape, e.g.
search → "add the second one") cannot be produced from the recorded cases
and is unmeasured.

Trade-off: C is deterministic and never mislabels, but it undercounts
requests, and its split error is unknown until participant data exists. A
is simplest but pollutes `advisory`. B hides mixed sessions inside `other`.
Recommendation: **C** for shape distribution and coverage (P1). Keep turns as
the unit for failure rates (P2), thumbs and `user_action`. Report coverage
per turn and per segment side by side, and base no claim on a request count.

**Added 2026-09-24 (author): slash and reference as optional boundary
signals.** `shapes.segment_with` extends C. A turn that acts on an id the
current request offered joins it (reference). Otherwise a turn with a slash
command starts a new request. Otherwise the shape rule applies. Both signals
are evidence when present and say nothing when absent, because the agent
reaches every path without a command. The rule is causal, so running it
after every agent response and running it once over the logs give identical
labels. Dry run on 42cab17a (`notebooks/sim/08_segmentation`): slash raises
the boundaries found in fused pairs from 83.5 % to 90.9 %, and gives nothing
once slashes are stripped. Reference finds no correct boundary there
(nothing continues) and wrongly merges 6 of 812 pairs that share a place
(the three Belém drafts).
**To be tested on the first run that includes D81's two seeds**, with
predictions stated in the notebook before the run. The dinner seed should
be one request only with reference. The afternoon seed should split under
every variant: the move acts on the tram, which no earlier turn offered, so
nothing in the record links the two turns.
Open alongside: a request's label. `interaction_label` calls a
search-then-draft request `other`, while the same tools inside one turn are
`scheduling.draft`. Labelling a request by the union of its turns' tools
would make the two agree.
Status: resolved — D100 (C + slash, no reference) and D106 (a request's label
is shapes7 over the union of its turns' tools).

### Q28 — [RESOLVED 2026-09-28, see D99 and D105] — The request-shape rule for the participant round's automatic labels
Raised: 2026-09-23 by author and agent · Blocks: C02 (§4.3 (3), "the shapes where uncovered concentrates"), C05 (freeze) · Phase: C

D09's `request_type` (4 classes) is too coarse to say where uncovered
participant turns concentrate. D24's signature is too fine to carry a
per-class failure rate. A **request shape** sits between them. It is derived
after the fact from `tool_call_trace` in `src/shapes.py`, so it needs no app
change and no event-model change. `notebooks/sim/07_shapes` computes every
candidate over run `42cab17a` (full suite, n=1, 2026-09-23).

Options:
- **d09** — keep the four classes only.
- **shapes7** — advisory · factual.reference · factual.climate ·
  factual.forecast · venue.search · scheduling.draft · scheduling.edit, plus
  `other`. No precedence: a turn doing two things is `other`, except that
  search then draft counts as the draft.
- **shapes9** — shapes7 with the live edit split into move / place / remove.
- **families** — the joined set of D09 families (Q08 option b).

What the run showed:
1. **All four rules miss the same 6/29: every advisory case.** The agent
   consults a reference tool before advising (packing → `get_region_climate`,
   Sintra → `read_wikipedia`), so no trace rule yields `advisory` on the
   suite. This also affects D09/P2: there is no advisory cell in either round.
2. Invariance relations keep their label under every rule. Only shapes9
   exposes the two directional relations that change the needed tool, at one
   execution per class.
3. `other` = 0. The suite has no mixed turn, so mixed participant turns are
   uncovered by construction.

Sub-decision forced by (1), whichever rule is chosen: **(i)** accept that
`advisory` means "called no tool" and that the suite's advisory cases are
factual shapes by what the agent did; **(ii)** add a case whose advisory
answer needs no tool, so the class is reachable. Relabelling from the request
text is not offered: it would add a model and would label what was asked, not
what was done (D09).

Trade-off: a finer rule names the uncovered shapes more precisely but thins
the per-class rates. shapes9's singletons cannot carry a rate even at the
baseline's n.
Recommendation: **shapes7 with (i)**, `other` reported as its own row in
C02, rule frozen at C05. Keep shapes9 computable as a secondary view, the way
D09 keeps the composite derivable.
Status: resolved — D99 (shapes7, unchanged) and D105 (sub-decision (i):
`advisory` means a turn that called no acting tool).

### Q27 — [RESOLVED 2026-09-28, see D102] — Table 12's label has no round that can produce it
Raised: 2026-09-23 (from D73) · Blocks: the participant-round analysis, not the baseline

Table 12 derives a label from `structural_check_outcome` x `user_action`:
Positive, Neutral, Lacks quality, Failure. Every row needs both.

After D73 no round produces both:

| | structural verdict | `user_action` |
|---|---|---|
| simulated | yes, on the execution row | no — observed 0 of 32 turns |
| participant | no, by D73 | yes |

- **Option A — drop Table 12 and report the two axes separately.** The
  simulated round reports structural pass rates and judge scores; the
  participant round reports `user_action` and thumbs. Honest, loses the
  cross-tabulation the manuscript describes.
- **Option B — substitute the judge for the checker in the participant round.**
  The judge needs only a request and a reply (P3), so it transfers where the
  structural checks do not. The label becomes "judge verdict x user action",
  which is computable in both rounds and keeps the shape of Table 12. Changes
  what the label means, and the manuscript says structural.
- **Option C — give the simulated round a `user_action` proxy.** The personas
  already accept or decline in prose; a rule could map that to the enum. Cheap,
  but it is a simulated user action standing in for a real one, and §4.2.2
  calls `user_action` indirect feedback from a person.

**Recommendation: B**, with the manuscript amended to say the label's
structural axis is the judge outside the simulated round. It is the only option
that leaves Table 12 computable in both rounds, and P3 already establishes the
judge as blind to everything but request, reply and rubric. A is the fallback
if the manuscript cannot move.
Status: resolved — D102 (A: two axes side by side)


### Q26 — [RESOLVED 2026-09-22, see D68] — Should a case require `get_region_climate` specifically?
Raised: 2026-09-22 (from D66) · Blocks: nothing; the suite runs either way

`get_region_climate` is required by no case. The three `november_weather` cases
name it in a `tools_any_of` beside `get_climate_normals`, which means either
satisfies them — so the tool could break and every one of them would pass.

The agent's own prompt treats them as different tools with different jobs:
`get_region_climate` for a month or a season by place NAME, `get_climate_normals`
for surf and marine questions from coordinates. The suite does not currently
hold it to that.

- **Option A — tighten the existing seed.** Make `factual_qa_lisbon_november_weather`
  require `get_region_climate` alone, leaving `get_climate_normals` as the surf
  case's tool. No new case, no extra executions, and it matches what the prompt
  actually says. It narrows what counts as a pass: an agent that answers a
  November question correctly *from climate normals* would now fail.
- **Option B — add a seed.** Costs 8 executions and, by the admission rule
  (D50/D51/D61), is only justified if nothing existing can be tightened. Here
  something can, so this is the weaker option.
- **Option C — leave it.** Accept that the pair is tested as interchangeable.
  Honest, but then the report should stop implying the tools are separately
  covered, and §4.3 should say the suite would not notice one of them failing.

**Recommendation: A.** It closes the gap for nothing, and it encodes a
distinction the application already makes. It needs the author because it
changes what counts as a pass (CLAUDE.md stop-and-ask).

**Resolved: leave the cases alone; the report was wrong.** Both tools answer
correctly, so requiring one asserts the route (D30); the fallback is legitimate
and a future case with coordinates and no usable place name will need it; and
`get_climate_normals` is already required outright by the surf case. The
recommendation above (Option A) was rejected. The report now distinguishes
"required as one of a group" from "permitted only", and on that reading the
suite has no coverage gap.

### Q23 — `get_weather` cannot succeed against the fixture trip
Raised: 2026-09-20 by agent · Blocks: nothing hard; bears on B04, B10 · Phase: B

The B15 probe showed `get_weather` returning `Weather forecast unavailable:
Open-Meteo error: 400` on the packing-list case. This is not the D36 defect
returning: the fixture trip runs 2026-11-06 to 2026-11-09, about seven weeks
out, and a forecast API answers roughly sixteen days. The agent recovered by
calling `get_region_climate`, which is exactly the probe-and-abandon behaviour
D33 permits, so nothing failed. But the consequence is that **one of the
agent's twelve tools can never return a success against this fixture**, and no
case can ever assert one.

Options: **(a)** accept it — `get_weather` stays a permitted probe that never
satisfies a check, and §3.7 records that the forecast path is untested ·
**(b)** move the fixture trip inside the forecast horizon, which means dating
it *relative to the run* rather than fixing it, since a fixed near date drifts
out of the horizon within a fortnight · **(c)** add a ninth seed with a
near-dated trip of its own, so the forecast path has one case.
Trade-off: (b) buys coverage of one tool and costs the fixture its fixed dates
— every case that names `2026-11-07`, every `fixture_depends_on` entry and the
`suite_version` hash would become run-dependent, and a case could no longer be
read against a trip anyone can look at. (c) is the smaller version of the same
thing, contained to one case, but it breaks the rule that every case runs
against one fixture.
Recommendation: (a) for this round, and say so in §3.7. The forecast tool is
one of twelve, the agent's fallback to climate normals is itself the behaviour
worth testing, and a relative-dated fixture would make every case harder to
read for one tool's sake.
Status: open

### Q22 — Bounds on the recorded telemetry, once a baseline exists
Raised: 2026-09-20 by agent · Blocks: nothing yet · Phase: B, C

D37 adopted the assertable half of the signals the application records and left
five out on purpose: `reply.chars`, `latency_ms`, the token counts, `llm_calls`
and `tool_calls`. Each is carried on every execution and reported per case, and
none is a check key, because a bound on any of them is a threshold and there is
nothing yet to set it against. A turn that starts needing eight LLM round trips
where it needed three has regressed in a way the pass rate hides, but "eight is
too many" is not a statement anyone can defend before the baseline run has said
what three looks like.

The question to answer after B10, on that run's own numbers: does any of the
five earn a bound, and what shape — an absolute window per case, a multiple of
the case's baseline median, or a reported rate with no pass criterion at all.

Options: **(a)** leave all five reported, never asserted, and let C02 show the
drift · **(b)** bound the ones whose baseline spread turns out narrow, per case,
as a multiple of the baseline median · **(c)** bound them globally, one window
for the suite.
Trade-off: a bound catches a regression the pass rate hides; a bound set on a
noisy signal manufactures false failures, and a false regression costs the
suite its credibility the first time someone chases one (D30).
Recommendation: decide on the B10 numbers, not before. (a) is the honest
default if the spread is wide.
Status: open — deferred by construction until B10 has produced a baseline.


### Q02 — §4.3 is scaffolding, not yet an analysis specification
Raised: 2026-09-17 by agent · Updated: 2026-09-17 · Blocks: Phase C · Phase: C

§4.3 is deliberately unwritten at this point — the author confirms it is
scaffolding with no real content yet, and the stale note it carried has been
removed. Phase C builds `study/06_analysis` from it, and the gate before the
participant round requires that notebook to produce the coverage and
failure-rate outputs described there.

This does not block the plan being produced. It blocks Phase C tasks being
specified tightly enough to delegate.

**Recommendation:** produce the plan now, and tag every Phase C task `[FABLE]`
until §4.3 is written. Revisit the tags then; several will likely become
`[STANDARD]` once the analysis steps are concrete.

Status: open — no action needed before `/thesis-plan`.
Plan tasks blocked (added 2026-09-17 by the planning session): C02.

### Q03 — Remaining unresolved fields in the event model
Raised: 2026-09-17 by agent · Updated: 2026-09-17 · Blocks: Phase A (one item)
· Phase: A, B

Three `TODO(author)` markers remain in `docs/event-model.md` after the author's
review. One blocks Phase A:

- **When is `ignored` written?** The name is settled (D05), the trigger is not.
  `accepted` and `rejected` have observable events; `ignored` is the absence of
  one, so it needs a rule — session end, a fixed interval, or some definition of
  the conversation moving on. Until that rule exists the application cannot
  write the value, and §4.3's label distribution rests on it.

Two do not block Phase A:

- **Thumbs control scope.** §4.2.2 puts it on every agent message; Table 11 logs
  it at suggestion level. A message is not always a suggestion. This changes the
  UI, so it wants deciding before the Phase A instrumentation task is written,
  even though the schema can accommodate either.
- **Which trip mutations are in scope** for origin tracking. This repo mutates
  `trip_blocks`, `itinerary_slots`, `branches`, `trip_todos` and more. Logging
  all of them is cheap; deciding afterwards which ones counted is not possible.

A fourth, Phase B only: **how `declared_constraints` are represented**
(declarative schema, predicates, or hybrid). Worth settling in `DECISIONS.md`
before code exists rather than after.

Status: resolved — D17 (`ignored` rule), D18 (scales), D08 (thumbs scope), D13
(mutation scope), D19 (`declared_constraints`).
Plan tasks blocked (added 2026-09-17 by the planning session): the `ignored`
rule blocks A05; thumbs scope blocks A06 (see also Q12); mutation scope blocks
A04 (see also Q13); the response scales for the survey items block A08, A09 and
C02; `declared_constraints` blocks B03 and B08.

### Q04 — Which environment the simulation and the participant round run on
Raised: 2026-09-17 by agent · Blocks: A01, B01, B07, C04 · Phase: A, B, C

Neither chapter says where the simulator runs or where participants land. The
repo has one Supabase project (prod, treated as disposable test data — see
`supabase/README.md`), a local stack via `supabase start` (Docker), and a Render
deployment of the API. Two consequences follow from the choice:

1. **`run_type` needs a third value.** The event model's enum is `pilot | study`,
   but the simulator drives the same app and the same tables (§3.3: "the
   simulator interacts with the same interface regular users do"). Without a
   `simulation` value, simulated sessions are indistinguishable from real ones
   in the study tables — the exact failure `run_type` was introduced to prevent.
2. **AI quota.** `lib/ai-quota.ts` meters every agent turn per user against a
   per-minute burst and a monthly cap by tier. A simulated user on the `free`
   tier hits the monthly cap in the first run. `DEFAULT_SUBSCRIPTION_TIER=pro`
   in the simulation environment lifts it by config, without touching code.

Options:
- **(a) One project for everything** (the current prod). Simplest; the
  participant round and the simulation share tables and are separated only by
  `run_type` and by session. Simulation rows sit in the same DB participants use.
- **(b) Local stack for simulation, prod for participants.** Clean separation;
  the migrations are the same so the schema is identical. The simulator hits a
  locally-run API and DB (Docker). Adds a second env to keep in sync; the
  "same deployed system" claim in §3.3 weakens slightly (same code, different
  host).
- **(c) A dedicated Supabase project for the study**, both rounds. Isolates
  participant data from the team's showcase trips and from any prod reset;
  requires linking a second project and a second API deployment.

Trade-off: isolation and the cleanliness of the retention/access statement
(event-model.md, "Retention and access") against the number of environments to
keep migrated and configured.
Recommendation: **(c)** for the participant round — the consent form has to say
where data lives and who can read it, and a project that holds only study data
answers that in one sentence — and **(b)-style local runs** for the bulk of the
simulation during development, with the baseline and regression runs of record
executed against (c) so the run metadata names the same host the participants
used. In all cases add `simulation` to `run_type`.
Status: resolved — D15 (2026-09-17/18)

### Q05 — What a study session is, and how the app knows a user is a participant
Raised: 2026-09-17 by agent · Blocks: A01, A02, A07, A12 · Phase: A

§4.2.2 fixes the order (link → log in or sign up → consent → demographics → use
the app) and says "observation covers the authenticated session that follows
consent". The application has no notion of a study participant, and two things
called "session" already exist, neither of which fits: the Supabase auth session
(not observable as a row) and the analytics tab id (`lib/analytics/session.ts`,
rotates after 30 minutes idle, per tab). Cookie consent (`lib/consent.ts`) is
localStorage-only and unversioned — not a model for study consent, which must be
recorded server-side with a version.

Four sub-questions, all needed before the schema can be written:

1. **Identity of `session_id`.** (a) one row per consent event, created when the
   participant consents, and every suggestion the participant produces after
   `consent_at` attaches to it — the tab id is recorded on top as a secondary
   field; (b) the analytics tab id, which is what `api_usage_events.session_id`
   already carries. (b) fragments a participant across tabs and idle gaps and
   has no consent attached to it.
2. **Enrolment.** How does the app know this user is in the study? (a) the
   study link (`/study/join?cohort=study|pilot`) stamps enrolment into
   `user_metadata` — the mechanism the existing `onboarded` gate uses in the
   `_protected` loader — so it survives tabs and devices and can be checked
   server-side; (b) everyone who signs up in the study window is a participant;
   (c) a separate deployment where every user is a participant (see Q04 c).
3. **Gating.** "Consent cannot be bypassed by URL or back button" implies that an
   enrolled, un-consented user is redirected to the consent page from every
   protected route. This is a loader redirect in `_protected.tsx` for enrolled
   users only; it does not alter how the agent handles a request, but it is a
   change to a request path for those users and should be stated as such.
4. **Declining.** Where does a participant who declines go? Recommend: the
   decline is recorded (`study_sessions` row with `declined_at`, no consent),
   enrolment is cleared, the user is signed out, and a short page says thanks.
   Also: the **consent version identifier** — a string constant beside the
   consent text in the web app, bumped by hand when the text changes, recorded
   on the session row.

Trade-off: (1a)+(2a) is more code than reusing what exists, but it is the only
combination where a session is a row with a consent on it.
Recommendation: (1a), (2a), loader gate for enrolled users, decline as above.
`run_type` comes from the cohort on the join link and is fixed at session
creation.
Status: resolved — D16 (2026-09-17/18)

### Q06 — What counts as an "interaction" for the post-task trigger
Raised: 2026-09-17 by agent · Blocks: A02, A09 · Phase: A

§4.2.2: participants "interact with the Trip Tonic agent through the chat
interface at least three times", and the post-task screen appears "once the
third interaction has been logged". The unit is not defined. Candidates: an
agent turn (one `POST /api/ai/agent/chat`), a planning run (`tonic_runs`, which
groups many turns into one card), or any chat message.

Options: (a) one completed agent turn, counted whether the agent replied or
failed, as long as a suggestion row was written — requests refused before the
agent ran (quota, validation, membership) do not count; (b) only successful
replies; (c) one planning run.
Trade-off: (a) treats a failure as an interaction the participant had, which it
is, and keeps the count equal to the number of suggestion rows, so the trigger
needs no second definition; (b) can leave a participant who hit three failures
never seeing the survey; (c) undercounts badly — a run absorbs every turn within
30 minutes.
Recommendation: (a). The client learns the count from the study API (a `GET`
that returns the session's suggestion count) rather than from the chat response,
so the agent endpoint's response shape stays untouched.
Status: resolved — D07 (2026-09-17/18)

### Q07 — `user_action` granularity: multi-slot drafts, live edits, and `user_initiated`
Raised: 2026-09-17 by agent · Blocks: A01, A05 · Phase: A

Table 11 records one `user_action` per suggestion. In this application one agent
turn can produce a **draft of N slots** (`propose_plan`), each of which a member
accepts or rejects separately (`PATCH /trips/:tripId/drafts/:id/slots/:i`), or
can **edit the live itinerary immediately** (`move_slot`, `unschedule_block`,
`schedule_block`), which no one accepts — it is already done, and the only
explicit reaction is the undo (`POST /ai/agent/revert`). Three of five slots
accepted is not one of the four enum values, and neither is "applied and not
undone".

Also unspecified: what `user_initiated` means at suggestion level. The most
coherent reading is "the user did what was suggested through their own path"
— e.g. added the venue Tonic named from the map rather than from the reply —
which is detectable from mutation rows (same `google_place_id`) but not at the
moment the suggestion is written.

Options for drafts: (a) one aggregate label per turn by a fixed rule — any slot
accepted → `accepted`; every slot rejected → `rejected`; otherwise the `ignored`
rule (Q03); (b) per-slot action rows only, label derived in analysis; (c) both —
the app appends one row per target (`slot:i`, `place:<id>`, `edits`) to a
`study_user_actions` table *and* maintains the turn-level column by rule (a).
Options for live edits: (i) `accepted` unless reverted; (ii) `rejected` on
revert, otherwise the `ignored` rule applies (Table 12 reads it as Neutral);
(iii) a fifth value.
Trade-off: (c) costs one more table but keeps the exact record and the field the
pilot assertion checks; (i) overstates approval, (ii) understates it but never
invents a reaction the participant did not have.
Recommendation: (c) with rule (a); (ii) for live edits; `user_initiated` derived
in analysis from `study_mutations` (origin `user_manual` + a `google_place_id`
matching a place ref on an earlier suggestion in the same session), never
written by the app.
Status: resolved — D12 (2026-09-17/18)

### Q08 — The `request_type` bucketing rule
Raised: 2026-09-17 by agent · Blocks: A02, A03, B12, C02 · Phase: A

§4.2.2: "a bucketed class label based on the tool calls the agent made to
produce a suggestion", assigned at completion. The rule is not given. The agent
has eleven tools in four families (`agent.tool-policy.ts`): read (`get_trip_details`,
`list_trip_blocks`, `get_itinerary`), reference (`get_weather`,
`get_climate_normals`, `read_wikipedia`, `get_region_climate`), search
(`search_places`), draft (`propose_plan`) and live edit (`move_slot`,
`unschedule_block`, `schedule_block`). A turn commonly calls several families
(search then draft), so a precedence is needed. Note the slash-command `intent`
(`find | plan | reschedule`, already stored on `api_usage_events.agent_intent`)
is what the member *asked*; `request_type` is what the agent *did*. They differ
and both are worth keeping.

Options: (a) precedence onto the four functions of §1.4 — `scheduling` if any
draft or live-edit tool ran; else `venue_lookup` if `search_places` ran; else
`factual_qa` if any reference tool ran; else `advisory`; (b) the exact set of
tool families as a composite label (`search+draft`), no precedence; (c) the
slash intent where present, (a) otherwise.
Trade-off: (a) maps directly onto the manuscript's four functions and P2's
per-type failure rates, at the cost of hiding mixed turns; (b) is lossless but
produces sparse cells; (c) mixes what was asked with what happened.
Recommendation: (a), implemented as one pure function with a
`request_type_rule_version` stored beside the label, and the ordered tool list
always stored too — so (b) remains derivable later.
Status: resolved — D09 (2026-09-17/18)

### Q09 — What `resulting_state_shape` contains
Raised: 2026-09-17 by agent · Blocks: A02, B08 · Phase: A, B

Table 11 lists "resulting state shape" per suggestion with no content given.
The structural checker (Stage 1, P5: "resulting state shape declared per case;
checked against the recorded trace") needs a concrete, deterministic object.

Options: (a) a compact shape derived from what `AgentService.chat` already holds
at completion — `{draft: {suggestion_id, days, slots, slot_types[]} | null,
edits: {move, unschedule, schedule}, places_surfaced, reply: {chars,
place_refs, draft_refs}}`; (b) (a) plus post-turn counts of the trip's
`trip_blocks` and `itinerary_slots` (two count queries), so a check can assert on
the database rather than on the agent's own journal; (c) a full before/after
snapshot of the trip's plan tables.
Trade-off: (a) is free and exact but is the agent's account of itself; (b)
adds two cheap queries and a real state assertion; (c) is expensive per turn
and copies the participant's whole trip into the study table.
Recommendation: (b).
Status: resolved — D10 (2026-09-17/18)

### Q10 — `user_turn` verbatim: copy or reference
Raised: 2026-09-17 by agent · Blocks: A02 · Phase: A

Table 11: "user turn, recorded verbatim". The member's message already exists as
a `chat_messages` row (written by the client before the agent is called). A
reference would avoid a duplicate, but that row can be edited (`is_edited`) and
is deleted with the trip; the study record would then change or vanish
underneath the analysis.

Options: (a) copy the text into the suggestion row at turn start; (b) store the
`chat_messages.id` only; (c) both.
Trade-off: (a) duplicates personal data the app already holds — which Q14 has
to cover in the export and erasure rules either way; (b) is not verbatim after
an edit, and is nothing after a trip deletion.
Recommendation: (c) — the copy is the record, the id is the join.
Status: resolved — D06 (2026-09-17/18)

### Q11 — Execution failure taxonomy, and what P2 counts as an execution failure
Raised: 2026-09-17 by agent · Blocks: A02, C02 · Phase: A, C

Table 11: "error code, where a check or API call fails". P2: "execution failures
are errors that arise while the agent computes a suggestion". In this agent,
failures occur at three levels and only one is visible from the outside:

1. **Turn-level** — `AgentService.chat` throws: timeout (`CHAT_TIMEOUT_MS`),
   LLM call limit (`MAX_LLM_CALLS`), empty reply, persist failure. The member
   sees a system message.
2. **Tool-level** — every tool catches and **returns** `{error: …}` as its
   result instead of throwing (`agent.tools.ts`, `agent.itinerary-tools.ts`), so
   the ADK `onToolErrorCallback` never fires; the model reads the error and
   carries on. Invisible unless the trace inspects results.
3. **Model-level, recovered** — 429/5xx and `MALFORMED_FUNCTION_CALL` retried
   inside `adk-llm.ts` below the plugin. Invisible unless the retry loop counts.

Options for the definition of an execution failure: (a) turn-level only; (b)
turn-level or any tool-level error; (c) (b) plus "recovered retries" as a
separate rate.
Trade-off: (a) undercounts — a failed `search_places` produces a reply built on
nothing; (b) is what "an error while computing" plainly means; (c) is (b) with
the retry signal kept visible.
Recommendation: (c). Record `error_code` at turn level from a closed set
(`timeout | llm_call_limit | empty_reply | llm_error | persist_failed | other`),
record each tool call's `error` string in the trace entry, and count retries
into `retry_count` via a counter on the model instance (an additive change to
`adk-llm.ts`). Report P2 on definition (b) as primary.
Status: resolved — D11 (2026-09-17/18)

### Q12 — Thumbs control: dedicated control or the existing reactions
Raised: 2026-09-17 by agent · Blocks: A06 · Phase: A

Complements the scope item in Q03. The chat already has 👍/👎 among its emoji
reactions (`use-chat-reactions.ts`, table `chat_reactions`), but those are
social — visible to every member, one per emoji per member, no study scoping,
and the same table serves 😂 and 🎉.

Also: **every agent turn writes exactly one reply row** (`message_type = 'ai'`,
carrying `metadata.agent`), with the edit-receipt row (`run_id` NULL, written
only for a private turn — which nothing sets today) the sole exception. If a
suggestion is defined as an agent turn, then "a control on every agent message"
and "feedback at suggestion level" are the same statement and the Q03 tension
dissolves.

Options: (a) a dedicated up/down control on every Tonic reply, private to the
member, one row per member per message in a study table, changeable; (b) reuse
`chat_reactions` 👍/👎 and treat them as the signal; (c) both, with (b) as a
secondary signal.
Trade-off: (a) is a new control and one more table; (b) is free but its meaning
is social and it never fires for members who don't use reactions anyway.
Recommendation: (a), keyed to the reply's `chat_messages.id`, joined to the
suggestion through that id; and define suggestion = agent turn.
Status: resolved — D08 (2026-09-17/18)

### Q13 — Mutation origin taxonomy and mechanism
Raised: 2026-09-17 by agent · Blocks: A01, A04 · Phase: A

§3.2 (point 4, "the paragraph that matters most") and the event model's
`origin_kind` need a closed set of values, and the mechanism constrains the
values that can be captured. Writes reach the plan tables by three paths:
agent tools during a turn (through the request's RLS client), the API on a
member's behalf (accept a draft slot, add a place, drag a slot), and the browser
directly through PostgREST (chat, reactions, comments, some block edits). Only a
database trigger fires on all three — the `user_stats` triggers already rely on
that. A trigger cannot know the origin on its own, but PostgREST exposes request
headers to SQL (`current_setting('request.headers', true)`), so a client that
knows the suggestion sends it as a header and the trigger reads it; agent-turn
writes need the per-turn client built with that header (same JWT, same RLS, one
extra header — a rule-4 consideration worth stating).

Options for `origin_kind`: (a) `agent_live_edit | agent_draft_accepted |
agent_place_added | user_manual | system`; (b) two values, `agent | user`; (c)
(a) plus the slash intent of the originating turn.
Options for scope (Q03): the plan tables only (`trip_blocks`, `itinerary_slots`,
`itinerary_days`, `ai_suggestions` inserts and verdict updates, `branches`), or
every trip table.
Trade-off: (a) distinguishes "Tonic did it" from "the member did what Tonic
proposed", which Table 12 and P3 need; (b) cannot. Plan-tables-only matches §1.4
("manages internal database state to maintain a persistent trip plan"); every
table is cheap but muddies the label distribution with Prep-list ticks and
expenses.
Recommendation: (a), scoped to the plan tables, via triggers + header, with the
`system` value for writes made by SQL functions and cleanup (`reconcileDayConflicts`,
retention). Store `table, row_id, op, changed_keys, minimal projection` per
mutation; never the full row.
Status: resolved — D13 (2026-09-17/18)

### Q14 — Withdrawal, erasure and export for study rows
Raised: 2026-09-17 by agent · Blocks: A01 · Phase: A

The migration has to choose an `ON DELETE` behaviour for every study table's
reference to the participant, and `account.export-tables.ts` has to classify
every new table carrying a subject column — `security-audit/permissions.test.ts`
fails the PR otherwise. Both are consent-form facts, and the information sheet
is not written yet.

Options for erasure: (a) `CASCADE` everywhere — an account deletion is a full
withdrawal and removes behavioural rows too; (b) surveys `CASCADE`, behavioural
rows `SET NULL` on `user_id` — pseudonymous rows survive, matching the app's
existing practice for `ux_events` and `api_usage_events`; (c) no FK to
`auth.users`, erasure handled by the analysis excluding withdrawn sessions.
Options for export: survey tables and `study_suggestions.user_turn` (personal
data the subject authored) in `EXPORT_BY_USER_ID`; mutations, feedback and
verdicts in `EXPORT_EXCLUDED` with reasons.
Trade-off: (a) is the cleanest promise but loses consented data on any account
deletion, including one unrelated to withdrawal; (b) keeps the study whole and
is defensible only if the information sheet says pseudonymous behavioural data
is retained.
Recommendation: (b), with the export split as above, and the retention statement
in the information sheet written to match.
Status: resolved — D14 (2026-09-17/18)

### Q15 — Which models play the simulator and the judge
Raised: 2026-09-17 by agent · Blocks: B06, B09, B14 · Phase: B

`.env.example` names `SIMULATOR_MODEL` and `JUDGE_MODEL` and leaves them empty.
Model selection is on the stop-and-ask list. Both must be dated releases and are
recorded in every run's metadata beside the agent's.

Options: (a) `gemini-3.5-flash` for both — one vendor, one key, cheapest; (b)
Gemini simulator, a judge from a different family (Claude or another vendor) —
avoids the self-preference bias an LLM judge shows toward its own family's
output, at the cost of a second key and SDK; (c) a different family for both.
Trade-off: (a) is simplest and its bias risk is real for the pair-wise
comparison; (b) isolates the judge, which is the component whose bias would
directly shape the pass rate; (c) buys nothing for the simulator that (b) does
not.
Recommendation: (b). The simulator only has to play a persona and the agent's
own family does that fine. Whichever judge is chosen, its id must be a pinned
snapshot with a release date the harness can record — verify that for the
chosen vendor before deciding.
Status: resolved — D20 (2026-09-17/18)

### Q16 — Suite size, repetitions for expanded cases, and the simulator's turn cap
Raised: 2026-09-17 by agent · Blocks: B03, B04, B05, B06 · Phase: B

§3.1 fixes n = 8 for the minimum-functionality (seed) cases and says the number
"may be reduced for resource efficiency" elsewhere — the reduced value is not
given. The number of seeds per function, follow-ups per seed, and the maximum
number of turns the simulator may take per case are unspecified. All four are
thresholds.

For scale: three seeds per function (12 seeds at n = 8) and two follow-ups per
seed (24 at n = 4) is 192 executions per run; baseline plus regression is 384;
at two to four turns per case and roughly 20 s per turn with the Vertex spacing,
a run is on the order of five to eight hours serial.

Options: expanded n ∈ {8, 4, 3}; seeds per function ∈ {2, 3}; follow-ups per
seed ∈ {2, 3}; turn cap ∈ {3, 4, 6}.
Trade-off: pass-rate resolution and coverage of the perturbation space against
Vertex spend, wall clock and the per-minute quota.
Recommendation: n = 4 for expanded cases, 3 seeds per function, 2 follow-ups
per seed, turn cap 4 with an earlier stop when the simulator declares the goal
reached.
Status: resolved — D21 (2026-09-17/18)

### Q17 — The metamorphic relation catalogue
Raised: 2026-09-17 by agent · Blocks: B05 · Phase: B

§3.1 says follow-up cases are derived "via metamorphic relations" and §2.5.1
names the two CheckList families (invariance, directional expectation) but no
concrete relations for this agent. The catalogue determines what Stage 2 asserts
("expected change / no-change relation", Table 9), so it is a pass criterion.

Proposed catalogue for the author to confirm, extend or cut:
- INV-1 paraphrase (same intent, reworded) · INV-2 typos and casing · INV-3
  irrelevant detail added · INV-4 language switch (German) — expected: same
  `request_type`, same tool sequence, same structural outcome.
- DIR-1 constraint added or changed (dietary, budget, "with kids") — expected:
  the `search_places` query or the draft reflects it and the venue set differs.
  DIR-2 day changed — expected: slots land on the new day. DIR-3 count changed
  ("two restaurants" → "four") — expected: slot count follows. DIR-4 negation
  ("not in Alfama") — expected: results exclude it.
- Per function: venue lookup and scheduling take all; factual QA takes INV-1..4
  and DIR-1 (a different fact); advisory takes INV only — it leaves no
  structural trace (P4).

Options: the catalogue above · a smaller INV-only catalogue · templates with
placeholders per CheckList to generate many follow-ups per relation.
Trade-off: directional relations are where the structural checks earn their
keep, and each one is a case-specific expected delta someone has to write.
Recommendation: the catalogue above, one follow-up per relation per seed at
most, chosen by hand in `sim/02_expand`.
Status: resolved — D22 (2026-09-17/18)

### Q18 — Pass criteria: case threshold, judge protocol, and the weather reference
Raised: 2026-09-17 by agent · Blocks: B09, B11 · Phase: B

§3.1 states the ten-point point-wise scale and the pair-wise "at least as good"
judgement, and P3 says "a pass rate against a threshold" — the threshold is not
given, nor how a structural failure and a judge verdict combine, nor how the
judge's position bias is handled. Separately, Stage 1 stores Wikipedia sections
and weather forecasts as references for factual QA, but a forecast changes
daily, so a stored forecast cannot be the reference for a run made later.

Options, case threshold: 8/8 for seed cases (they are minimum functionality) and
≥ 75 % for expanded; a uniform ≥ 75 %; report rates only, no threshold.
Options, combination: structural `detected` fails the execution regardless of
the judge; or the judge decides and the structural outcome is reported beside.
Options, pair-wise protocol: single call; both orderings and pass only when both
say "at least as good"; both orderings, tie → pass.
Options, weather: the judge scores faithfulness to the forecast the agent
actually retrieved (recorded in the trace as the tool result); or exclude
weather from judged QA and check it structurally only (right tool, right
coordinates, right dates).
Recommendation: 8/8 seeds, ≥ 75 % expanded; structural `detected` fails
outright; both orderings, pass only on agreement, temperature 0; weather judged
against the retrieved forecast from the trace, Wikipedia against the stored
section.
Status: resolved — D23 (2026-09-17/18)

### Q19 — The coverage signature and its matching tolerance (P1)
Raised: 2026-09-17 by agent · Blocks: B12, C02, C05 · Phase: B, C

P1 defines an interaction shape (tools and order, calls per tool, turns, tool
parameters) and requires the matching tolerance "fixed before participant data
is collected". It is not fixed yet, and the signature has to be computable from
the trace alone (no reading of conversation text), for simulated and participant
turns alike.

Options: exact on everything (few matches); exact on the ordered tool sequence
with consecutive repeats collapsed plus `request_type`, bucketed on calls per
tool {1, 2, 3+} and turns {1, 2, 3+}, parameters reduced to booleans
(`has_location`, `has_date`, `has_price_term`, `has_dietary_term`); or match on
`request_type` and tool *set* only.
Trade-off: the finer the signature, the more informative "uncovered" is and the
lower the coverage; the coarser, the closer P1 comes to being true by
construction.
Recommendation: the middle option, versioned (`signature_rule_version`), applied
identically in Phase B storage and Phase C matching.
Status: resolved — D24 (2026-09-17/18)

### Q20 — `prompt_version` / `tool_version` in the deployed container
Raised: 2026-09-18 by agent · Blocks: nothing yet (A10 is done; bites only if a
run is recorded against the Docker image) · Phase: A

A10's spec states that "the esbuild bundle is `--packages=external` and keeps
`src` on disk in the image". It does not: `apps/api/Dockerfile`'s runtime stage
copies only `/repo/apps/api/dist`, so the agent sources `study-versions.ts`
hashes are absent in the image. Run from source (`tsx`, the dev server, the
test suite) the hashes resolve correctly; run from the container,
`getStudyVersions()` throws and `GET /api/study/versions` returns 500 — so a
run recorded against a deployed API would carry no `prompt_version` or
`tool_version`, two fields the event model lists (invariant 3).

Options: (a) add `COPY --from=build /repo/apps/api/src ./src` to the runtime
stage — one line, ships source into the image; (b) compute the two hashes at
build time and bake them in as build args / a generated module — image stays
source-free, but the build must not be skippable or the hash goes stale;
(c) leave it, and require that every recorded run be produced by an API running
from source.
Trade-off: (a) is trivial and always correct but puts the agent's prompt and
toolset in the shipped image; (b) keeps the image clean at the cost of a build
step that can silently drift; (c) costs nothing now but makes an unannounced
container deploy silently drop two fields.
Recommendation: (a) if any study traffic will hit the deployed API; (c) plus a
line in the run book if the study only ever runs against a local server.
Status: resolved — D25 (agent, 2026-09-18)

---

## Resolved

### Q24 — The harness exhausts its own Vertex quota, and a lost execution fails a seed at 8/8
Raised: 2026-09-20 by agent · Updated: 2026-09-20 after reading the API log ·
Blocks: B10, B11 · Phase: B

In the B15 probe, `factual_qa_lisbon_november_weather` ended with
`error_code = llm_error`, `retry_count = 2`, and the API returning 502. The
tool call before it had succeeded; the model call after it did not.

**The cause is not flakiness, which is how this was first written here.** The
API log names it: `429 RESOURCE_EXHAUSTED` from Vertex, retried to
`MAX_LLM_ATTEMPTS = 3` with 1s and 2s of backoff, all three attempts inside the
same exhausted window, then `collectRun` throws and `AgentService.chat` turns
it into `AppError 502`. The harness runs two Vertex clients against one express
key and neither knows about the other: `VERTEX_MIN_INTERVAL_MS` is enforced on
an instance field of a `Gemini` built per request, so it spaces calls **within
one turn** and nothing spaces them across turns or executions; and the
harness's own path (`src/llm.py`, simulator and judge) has no spacing at all,
only retry backoff. Run 2 issued roughly 30-40 model calls in about 150
seconds. The rate is ours, and so is the fix.

D11 defines P2's execution failure as a turn-level error or any tool-level
error, and D23 requires a seed case to pass **8/8**. Taken together, a single
transient 502 anywhere in a seed's eight repetitions fails that seed — and at
128 executions per full run, at the rate observed, that is not a rare event.
The pass rate would then be measuring Vertex's availability alongside the
agent's consistency, and §4.3's failure-rate comparison would carry both
without distinguishing them.

D30 already settled the shape of the answer for *tools*: assert the outcome,
report the retries. The open question is whether the same reading extends to a
turn-level failure the agent had no part in.

**Update, 2026-09-21, after D39 shipped the pacing.** It was not enough. Run
`11af8ef7` lost `advisory_packing_list` to the same 429 — on the **first turn
of the run**, roughly seven seconds into a window that had been idle for
twenty-three minutes, on that turn's third model call. The limiter is working
(it blocks correctly in isolation) and it never reached its cap, so the key's
real quota is below ten calls a minute, or it is not counted in calls at all: a
Tonic turn carries four to sixteen thousand input tokens, and three of them in
seven seconds is a lot of tokens for a small window.

Two things follow. The failure is a **burst**, not an average — a per-minute
budget grants its whole allowance at the start of every window, and the agent
spends four permits in seven seconds — so the budget needs a minimum interval
as well as a cap, or it needs to count tokens. And the agent's own spacing,
`VERTEX_MIN_INTERVAL_MS`, is **already an environment variable** (default
1500), so raising it spreads a turn's internal calls without touching a line of
application code, which makes it the cheapest lever available and no rule-4
concern at all.

There are two questions here and the first one is not the author's.

**Pacing (agent's, under "do not ask about" — it is a harness change,
reversible by editing a file, and touches no application code).** One rate
limiter in the harness, shared by the path that drives the agent and the path
that runs the simulator and the judge, set below the key's per-minute quota;
and a 429-specific wait that clears the window rather than three attempts
inside it. Doing this in the harness and not in `adk-llm.ts` keeps rule 4
intact — a change to the application's retry behaviour is a change to how it
handles a request, and would also alter what the participant round measures.

**What to do with an execution that fails anyway — the author's**, because it
is a pass criterion. Options: **(a)** count it, and report how many failures
were quota rather than the agent · **(b)** re-run an execution that ended in
`llm_error`, `timeout` or `persist_failed`, up to a fixed cap, record both
attempts and score the completed one · **(c)** exclude such executions from the
pass rate and report a separate availability rate.
Trade-off: (a) is the honest raw measure, but with D23's 8/8 it lets one quota
error fail a minimum-functionality seed, and a false regression in the record
costs the suite its credibility (D30). (b) keeps the pass rate about the agent,
at the cost of a retry policy that must be declared in advance and reported,
and of executions that are not independent draws in the strict sense. (c) is
(b) without the re-run, so a case can end a run with fewer than n observations.
Recommendation: pace first, then **(b)** with a cap of one re-run per
execution, both attempts recorded and the count reported in C02. With pacing in
place the re-run should be rare, and its rarity is itself the evidence that the
pass rate is about the agent. Worth deciding only after the paced baseline
shows how often it still happens.
Status: resolved — D43 (the backoff, after research established the 429 is shared capacity) and D44 (a lost execution counts as a failure; the author chose the raw measure over the recommended capped re-run)


### Q25 — The Belém morning window fails a good plan by fifteen minutes
Raised: 2026-09-21 by agent · Blocks: B05, B10 · Phase: B

The first full eight-seed run under the repaired pipeline (`11af8ef7`) produced
six clean executions and two `detected`. One is the quota failure below. The
other is `scheduling_belem_morning`, and the plan it flagged is a good one:

```
09:00-09:45  Pastéis de Belém
10:00-12:00  Jerónimos Monastery     (matched by title, not reuse_block_id)
12:15-13:15  Belém Tower             <- flagged
```

`draft_slot_starts_between: [07:00, 12:00]` fails the third slot. The member
asked for "a Belém morning for the 7th, two or three stops"; three stops whose
last begins at 12:15 is a morning that runs into lunch, not an afternoon
mislabelled as a morning. That is a **false regression**, which D30 calls the
worse of the two errors a constraint can make, and under D23's 8/8 seed
criterion a single occurrence in eight repetitions fails the case.

The check is worth keeping: without it an agent that drafts an afternoon and
calls it a morning passes, because the drafting tool instructs the reply not to
repeat every slot and so a criterion about the times the reply names is vacuous
exactly when it is needed. The question is the boundary, not the check.

This blocks B05 as well as B10: sixteen follow-ups inherit their seed's
constraints, so deriving them from a window that false-fails propagates it
sixteen times.

Options: **(a)** widen to `[07:00, 12:30]` — a morning's last stop may begin
around noon, and an afternoon draft still fails · **(b)** assert the draft's
**first** slot is in the morning and drop the per-slot window, so the claim is
"this is a morning plan" rather than "every part of it is before noon" ·
**(c)** widen to `[07:00, 13:00]` · **(d)** keep `12:00` and treat 12:15 as a
miss.
Trade-off: (a) is the smallest change that removes the false failure and keeps
the detection; the 12:30 boundary is a judgement, but so was 12:00, and this
one has an observed plan behind it. (b) is the most faithful reading of what
the case means and the weakest check — a plan whose first stop is at 09:00 and
whose rest is at 16:00 would pass. (c) is (a) with more room and starts to
admit genuine afternoons. (d) keeps the suite strict and accepts that this seed
will fail runs for a reason nobody will defend when they chase it.
Recommendation: (a). The check exists to catch a draft that starts in the
afternoon, and 12:30 still catches every one of those.
Status: resolved — D42 (2026-09-21); the author chose 13:00 over the recommended 12:30


### Q21 — The check vocabulary was invented rather than derived from the event model
Raised: 2026-09-20 by agent · Blocks: B08, and the value of every case already
written · Phase: B

`declared_constraints.checks` was specified in B03 from the D19/D27 discussion
of what a constraint is, and never cross-checked against
`docs/event-model.md` and the Phase A tables that actually record a turn. The
consequence is not a wrong vocabulary but a thin one: the application already
writes several signals a case cannot currently assert, and two of them
(`draft.slot_types`, `reply.place_refs`) were found by accident while fixing
something else and became `draft_slot_types` and `places_named` the same day.
Others are still unused. A case cannot say any of the following, though the
data is already in the row:

- **`resulting_state_shape.edits`** (`{move, unschedule, schedule}` counts) —
  a direct statement of what a rescheduling turn did, which the tram case
  currently approximates through `mutation_counts` on `itinerary_slots`.
- **`resulting_state_shape.trip_after`** (`{blocks, slots}` after the turn) — a
  read-only case could assert the trip is unchanged as a post-state rather than
  as four mutation zeros, which is the same claim stated positively and does
  not depend on the mutation trigger firing.
- **`study_mutations.changed_keys`** — which columns a write touched. "The move
  changed the day and the times and nothing else" is currently unsayable.
- **`study_suggestions.error_code`** (`timeout | llm_call_limit | empty_reply |
  llm_error | persist_failed`) — a case cannot require that the turn completed
  cleanly. `empty_reply` in particular returns HTTP 200, so the simulator does
  not stop and no check notices.
- **`agent_intent` and `request_type`** — the app's own classification of the
  turn. A case declares `intent` and `function`; comparing the two is free and
  would catch a regression in the classifier that no case can currently see.
- **`llm_calls`, `tool_calls`, `latency_ms`, `tokens_*`** — a turn that starts
  needing eight LLM round trips has regressed in a way the pass rate hides.
- **`reply.chars`** — "brief, a short paragraph" is judge-scored in the Alfama
  case and is partly a number.
- **`resulting_state_shape.draft.slot_types`** — slots per block type in the
  latest draft. Defined as a check key on 2026-09-20 and withdrawn the same day
  once `draft_reuses_blocks` carried what the Belem case actually needed: no
  seed asserts a type composition, and by this question's own recommendation a
  key without a case is a key nobody validates. It is the obvious first
  addition if a later case wants "this day has somewhere to eat".

Options: **(a)** adopt none, and record the thinness as a limitation in §3.7 ·
**(b)** adopt only the keys a currently-written case would use — `edits`,
`trip_after`, `error_code` · **(c)** adopt the full list above, and revise the
eight seeds to use them · **(d)** adopt (b) now and hold the rest behind a rule
that a key is added when a case needs it.
Trade-off: every key is cheap to define and not free to keep — B08 has to
evaluate it, a case that uses it has to justify it (criterion 4), and a
vocabulary larger than the suite is a vocabulary nobody validates. Against
that, a signal the application already records and the suite cannot assert is
the cheapest possible detection being left on the floor, which is exactly what
§2.6.1 claims structural verification is good at.
Recommendation: (d). Adopt `edits`, `trip_after` and `error_code` now, because
a seed would use each one today; leave the rest listed here and add one when a
case needs it, so the vocabulary stays something every key of which is
exercised. Either way B03 and B08 gain the derivation rule, so the next key is
found by reading the event model rather than by accident.
Status: resolved — D37 (2026-09-20)


<!-- Moved to DECISIONS.md. Keep the id and a one-line pointer. -->

- **Q01** — the agent model. Resolved by **D04**: the premise was wrong.
  `gemini-3.5-flash` is a pinned release, not a moving alias, so invariant 2 was
  already satisfied; the release date is now recorded alongside the id, and the
  model is not to be upgraded while the study runs.
- **Survey storage** — resolved by **D02**: two separate tables.
- **State reset confirmation** — resolved by **D03**: a precondition check, not
  a logged field.
- **`left` vs `Ignored`** — resolved by **D05**: `ignored` throughout.
- **Q04**–**Q19** — the sixteen questions the planning session raised were
  ruled on by the author on 2026-09-17/18: Q04→D15, Q05→D16, Q06→D07,
  Q07→D12, Q08→D09, Q09→D10, Q10→D06, Q11→D11, Q12→D08, Q13→D13, Q14→D14,
  Q15→D20, Q16→D21, Q17→D22, Q18→D23, Q19→D24. Q03's four items → D17, D18,
  D08, D13, D19. Full text kept above for the record; only Q02 remains open.
- **Q20** — source hashes in the container. Resolved by **D25** (agent): the
  runtime image copies `src`.
