# Decisions

What was chosen, when, by whom, and why. Feeds §3.3 and §4.4 of the manuscript,
and provides the escalation record for the transparency paragraph in §3.4.

A question the author has not yet ruled on lives in `OPEN_QUESTIONS.md`, not
here. This file records rulings, including rulings that later reversed — a
reversal is appended as a new entry, never an edit to the old one. The record of
what was believed at the time is the point.

Newest entries at the top.

## Format

```markdown
### D04 — Constraint expression format
Date: 2026-09-22 · Decided by: author (escalated by agent)
Options: declarative JSON schema · Python predicates · hybrid
Chosen: Python predicates
Reason: venue-count and radius conditions cannot be expressed declaratively
without inventing a mini-language.
Affects: T07, T11 · Reverses: none
```

`Decided by` is one of: **author**, **author (escalated by agent)**, or
**agent**. An agent may only record `agent` for choices the nested `CLAUDE.md`
lists under "do not ask about". Anything on the stop-and-ask list is the
author's, and recording it otherwise misstates the transparency record.

---

<!-- TEMPLATE-END — entries below, newest first. -->

### D36 — the weather tool's dated calls are fixed before the baseline
Date: 2026-09-20 · Decided by: author
Options: fix before the baseline · leave it for the whole study and document
the defect · fix and add a ninth seed covering the dated forecast path · record
it as an open question and decide later
Chosen: the first. `getWeatherForecast` no longer sends `forecast_days`
alongside an explicit range; dates win when the caller gives them and the
sixteen-day window is the default otherwise.
Reason: the author's, on evidence from the third case review. Open-Meteo treats
the two as mutually exclusive and answers 400 when both are sent, and the tool
set the window unconditionally before adding the dates — so every dated call
failed, including one for tomorrow, and including the use the standing prompt
names by name ("use get_weather for upcoming conditions during the trip
dates"). Verified against the live API before and after: a range inside the
horizon now returns days where it previously returned 400, an undated call is
unchanged at sixteen days, and a date beyond the horizon still fails, which is
Open-Meteo's own limit and not this bug.
**This is a rule-4 change to application behaviour, and the timing is the
decision.** It had to happen before the baseline or not at all: fixed between
the baseline and the regression run it would appear in the data as an agent
behaviour change with nothing to attribute it to. The baseline and the
participant round now both measure the fixed system. `git_sha` on every
`study_runs` row is what ties a run to the code that produced it.
No seed case changes: the fixture trip is in November, which is beyond the
forecast horizon either way, so the permitted probe in the two scheduling seeds
still errors and D33's abandoned-probe rule still carries it.
Affects: apps/api/src/routes/ai/lib/weather.ts (+ weather.test.ts, four
regression tests on the query string) · Reverses: none

### D35 — a case with stored references is judged against them
Date: 2026-09-20 · Decided by: author
Options: D23's rule unchanged (a weather question is judged against the
forecast the agent retrieved) · the stored references always win · the
reference material is whatever the case declares, and the retrieved result only
where it declares none
Chosen: the third. A case that declares `references` is judged against them;
the tool result the agent retrieved is the reference only for a case that
declares none.
Reason: the author's, on a contradiction the third review found. D23 says a
weather question is judged against the forecast the agent fetched, and the
weather seed's notes overrule it in prose — it asks what November is *usually*
like, which is a climate question, so it carries two stored climate sources
instead. Nothing in the harness resolved the two, and the judge scores whatever
the caller hands it. The rule has to live in one place, and "what the case
declares" is the place, because the case is where someone decided what a good
answer agrees with. It also fails safe: the dated forecast call returns an
error, so under D23 unamended the weather case would have been judged against
an error object.
Affects: D23 (amended), B09, B10, cases/README.md · Reverses: D23's
retrieved-forecast rule, for cases that declare references

### D34 — the judge scores the first reply, against the opening turn
Date: 2026-09-20 · Decided by: author
Options: score the last reply · score a concatenation of every reply · score
the first reply against the case's `opening_turn`
Chosen: the third. B09 and B10 pass `user_request = case.opening_turn` and
`reply` = the first agent reply of the execution. Structural checks stay
execution-wide, and that asymmetry is deliberate and stated in
`cases/README.md`.
Reason: the author's. Nothing had pinned it, and the personas made it decisive:
six of eight goals now end with the member declining an offer to schedule, so a
typical execution's *last* reply is a sign-off like "no problem, enjoy Lisbon",
which scores near one against every rubric in the suite. The rubrics were
written for the answer to the opening turn, so that is the reply to score. The
checks go the other way for their own reason — a draft written on turn two is
still a draft the member got — and the asymmetry is the honest consequence of
the judge scoring an answer while the checks score an outcome.
Affects: src/judge.py, B09, B10, cases/README.md, every scoring_criteria in
the suite · Reverses: none — it fills a gap rather than changing a rule

### D33 — a tool error is forbidden or correctable, never just absent
Date: 2026-09-20 · Decided by: author
Options: keep `no_tool_errors: true|false` · drop the key where recovery is
legitimate · replace it with `tool_errors: none | corrected`
Chosen: the third. `none` forbids any tool error; `corrected` permits one only
where the agent recovers from that error, so a later call to the tool that
failed, or to one named in `tools_any_of`, has to succeed; leaving the key out
constrains nothing. The weather, tram and Belem cases use `corrected`.
Amended 2026-09-20: `corrected` also covers a **probe the agent abandons** —
a tool permitted at `min: 0`, named in no other check, whose result nothing
depends on. Walking away from a source that could not answer is a recovery, and
for a probe it is the only one available, because a probe is capped at one call
and cannot be retried. Without this the drafting case was unsatisfiable: it
permits one forecast call precisely because trying is reasonable, and then had
no way to forgive the error that call returns.
Amended the same day: `corrected` first read "a later call to a tool this case
names". That is too loose wherever a case names more than one source — in the
weather case a failed climate lookup followed by a successful forecast call
satisfied it, and the answer then came from a sixteen-day forecast, which is
exactly what the case exists to forbid. `tools_any_of` was tightened in the
same pass to mean ran *and returned without an error*, for the same reason: a
source that failed supplied nothing.
Reason: the author's. The boolean could only say "never happened", and D30 had
already established that an agent which meets a refusal and recovers is
behaving correctly — so the only way to permit the recovery was to drop the
check, which also permits an agent that errors and gives up. The weather case
made the gap concrete and self-contradictory: it permits the forecast probe at
up to one call because trying the wrong source and noticing is reasonable,
while `no_tool_errors: true` failed exactly that probe, since asking the
forecast endpoint for a date seven weeks out returns an error object and the
trace records a returned error like a thrown one. What the case wants to say is
that the agent may reach for the wrong function provided it reads the error,
recognises the mistake and calls the right one — which is a third state, not
the absence of a constraint.
Affects: src/cases.py (Checks.tool_errors), all eight cases,
cases/README.md, cases/REVIEW_CRITERIA.md (criterion 9), B08 · Reverses: the
`no_tool_errors` boolean from B03

### D32 — a case asserts the kind of place, never which one
Date: 2026-09-20 · Decided by: author
Options: assert the venues a good answer would name · assert only counts ·
assert the kind of place the request implies, with identity reserved for a stop
the member named
Chosen: the third. A search is checked with `places_surfaced` and
`places_named`; no case names a venue. The exception is a place the *member*
named: `slot_moved.block` for the stop she pointed at, and
`draft_reuses_blocks` for one she said the trip already has. Both are exact and
both are validated against the fixture by the loader.
Amended the same day: this first read "a draft is checked with
`draft_slot_types` (slots per block type)". That key was withdrawn before any
case used one (Q21) — what the Belem case actually needed was the monastery by
name, which is the exception rather than the rule, and a type composition no
seed asserts is a key nobody validates.
Reason: the author's. Which restaurant near Cais do Sodre or which monument in
Belem is the agent's judgement, and a case that named one would make the
author's taste the pass criterion — and would fail the day that venue closed or
Google reranked it, which is a false regression arriving on someone else's
schedule. The kind of place is what the request actually implies: "somewhere
for lunch" is a restaurant in a region, and that is assertable, stable and
still catches a plan of three museums and no food. Identity is different where
the member supplied it: "the tram ride" is one stop, so any other stop landing
in that window is an answer to a different question, and the exactness is the
member's rather than the author's.
Affects: src/cases.py (draft_reuses_blocks, places_named, slot_moved),
cases/scheduling_belem_morning.yaml, both venue-lookup cases, cases/README.md,
cases/REVIEW_CRITERIA.md (criterion 9), B08 · Reverses: none

### D31 — a time is asserted as a window and a length, never a clock reading
Date: 2026-09-19 · Decided by: author
Options: assert the exact resolved time · assert the day only · assert the
window the member's words license, plus the stop's length, plus that it cleared
whatever else was on the day
Chosen: the third. `slot_moved` now takes `starts_between` (an inclusive
`[earliest, latest]` pair), `duration_minutes` (exact or bounded) and
`clear_of_other_slots`. `start_time` and `end_time` are gone; a case that means
one minute writes the same value twice.
Reason: the author's, on reading the tram case's `end_time`. Two separate
problems, one answer. The member says "around 4", which is a range — an agent
writing 16:15 has understood her, and 16:00-exactly would have failed it. And
the fixture will grow: as soon as the target day holds something near the time
the member named, moving off that time is the *correct* behaviour, so a case
pinned to the minute would start failing correct agents as the starting trip
gets fuller. Widening the window and asserting that the agent found a free slot
says what the request actually requires. Length is a separate key because it is
a separate failure: `move_slot` takes the end time as an optional argument and
nothing derives it from the stop's duration, so an agent can land the start
correctly and leave an hour-long stop running to the end of the day. The day
itself carries no tolerance — the trip has one Saturday.
Affects: src/cases.py (SlotMoved), cases/scheduling_move_tram.yaml,
cases/README.md, cases/REVIEW_CRITERIA.md (criterion 9), B08 · Reverses: the
exact-time reading of `slot_moved` in B03, and the `end_time` field added
earlier the same day

### D30 — a case asserts the outcome; retries are reported, not punished
Date: 2026-09-19 · Decided by: author
Options: assert first-try correctness (a tight bound plus `no_tool_errors`) ·
assert the final state and report retries separately · assert the final state
and record nothing about retries
Chosen: the second. Where the application refuses a reasonable first attempt
and the agent recovers within the turn, the case widens the bound and drops
`no_tool_errors`; C02 reports tool errors and retries per case from the trace.
Reason: the author's, on a finding from the case review. `scheduling_move_tram`
asserted exactly one `move_slot` call and no tool errors, and the API refuses a
move that sets a later start without also moving the end — the stored end would
precede the new start. An agent that retries with both is behaving correctly and
would have failed the case, which is the worse of the two errors a constraint
can make: a false regression in the record costs the suite its credibility the
first time someone chases one. Dropping the signal entirely was rejected as the
opposite mistake — an agent that starts needing two calls where it needed one
has changed, and a pass rate alone would not show it.
The same reading settles a second case. Dropping `get_weather` from the
weather case's `tools_any_of` also forbade it, because a case permits the union
of the tools it names — and with no slash command the agent holds every tool, so
one that tries the forecast, finds it cannot reach November and falls back to
the climate table has behaved well. It is now named in `tool_counts` with a
minimum of zero: permitted, and never satisfying. Permitted and satisfying are
different questions, and the case vocabulary already had a key for each.
Affects: cases/scheduling_move_tram.yaml,
cases/factual_qa_lisbon_november_weather.yaml, cases/README.md, C02 · Reverses:
the first-try reading of `no_tool_errors` in B03

### D29 - a case constrains what its request implies, not what its function is
Date: 2026-09-19 - Decided by: author
Options: advisory carries no constraints at all (P4 read as a rule) - advisory
must change nothing, as a rule of the function - a case constrains what its own
request implies, whatever its function
Chosen: the third. The two advisory seeds assert the four mutation zeros,
because asking for a packing list or a recommendation implies the trip does not
change. This is not a rule about advisory: a future case of any function is free
to imply something different. Neither advisory case constrains tools, and the
model now refuses one that tries.
Reason: the author's, on reviewing the mutation counts. A message carrying no
slash command keeps the agent's whole toolset deliberately - a member who forgets
the command should still be helped - so which tools inform an answer is the
agent's judgement and not a case's to fix. What the member asked for is a
different matter, and "advise me" asks for nothing to be written. The previous
rule, that advisory carries no constraints, came from reading P4's "leaves no
structural trace" as a licence not to check rather than as a claim worth testing:
both seeds carry no command, so the agent could draft a plan in answer to "what
should we pack" and nothing would have caught it.
Affects: B03 (the model rule it reverses), B04, B08 - Reverses: the empty-
constraints rule for advisory written in B03

### D28 - a case permits the tools it names and no others
Date: 2026-09-19 - Decided by: author
Options: name the tools expected and assert a zero for each one forbidden -
deny by default, so anything unnamed is a structural failure - report an
unexpected tool as a finding without failing the case
Chosen: deny by default. A case's allowed set is the union of
`expected_tool_sequence`, the keys of `tool_counts` and `tools_any_of`, plus
the three read tools; any other tool call is `detected`. Two carve-outs, both
the author's: the read tools (`get_trip_details`, `list_trip_blocks`,
`get_itinerary`) are always allowed, because the agent calls them only when its
preloaded context falls short and that varies between runs of one case; and a
case naming no tool at all constrains none, which keeps the advisory seeds free
to ground their advice.
Reason: simpler to write and strictly stronger. The previous shape required a
zero per forbidden tool, so it caught only what the case author thought to
forbid - and the zeros that were written were mostly for tools the slash
command already made unreachable, which tested `agent.tool-policy.ts` rather
than the agent. Under deny by default a case states what it expects, and every
tool nobody anticipated is forbidden for free. An unexpected tool call is a
behaviour change, which is what a regression run exists to notice.
Affects: B03, B04, B05, B08 - Reverses: the explicit zeros in the seed cases

### D27 - checks describe one execution, predicates compare two
Date: 2026-09-18 - Decided by: author (raised on reviewing the seed cases)
Options: keep D19's line as written (declarative where possible, predicates for
"sequence-dependent" constraints) - move everything statable into checks and
reserve predicates for comparisons - drop predicates and invent a mini-language
Chosen: the declarative `Checks` vocabulary carries everything that describes
**one** execution, including `slot_moved {block, day, start_time}`,
`tools_any_of`, `no_tool_errors` and `places_surfaced`. `predicates` are only
for constraints that compare an execution with **another** one, which is what
every metamorphic relation is and what no schema can state.
Reason: D19 drew the line at "can it be expressed declaratively", and the first
eight cases misapplied it. Five of the seven predicates written described a
single execution - `no_tool_errors`, `surfaced_real_places`,
`used_a_reference_tool`, `search_before_draft` (already covered by the ordering
field) and `tram_landed_on_saturday_afternoon`, which was hardcoded to one stop
and one window and so could not have served a second rescheduling case. Arity is
the line that holds: one execution can be described, two must be compared.
Consequence: every constraint a case declares is now a schema key the loader
validates, so a case can no longer smuggle an unevaluated assertion past it as a
predicate name.
Affects: B03, B04, B05, B08 - Reverses: none - Refines: D19

### D26 — A case execution records the ids its fixture rebuild produced
Date: 2026-09-18 · Decided by: author
Options: record the ids per execution · resolve them afterwards from the trip ·
identify fixture rows by title alone
Chosen: `study_case_executions.fixture_ids` — trip, blocks, days, slots and
regions, by name, as the rebuild created them for that repetition.
Reason: the author's instruction, "everything needs to be exactly traceable".
The fixture is deleted and rebuilt before every repetition, so a stop's id is
new each time; a `study_mutations` row carries `row_id` and a
`resulting_state_shape` carries slot ids, neither of which can be read back to
a stop once the next repetition has replaced it. Resolving afterwards is
impossible for the same reason, and titles alone are ambiguous the moment two
stops share one — which the fixture loader now refuses outright, but which the
ids make moot.
Affects: event-model.md (test case level), B02, B07, B08, C02
Reverses: none
Note: additive — a nullable column and a field the harness fills. No existing
field changes meaning.

### D25 — The API image carries `src`, so version hashes resolve in the container
Date: 2026-09-18 · Decided by: agent
Options: copy `src` into the runtime image · bake the hashes at build time ·
require every recorded run to hit a source-run API
Chosen: `COPY --from=build /repo/apps/api/src ./src` in the runtime stage of
`apps/api/Dockerfile`.
Reason: A10's spec assumed the image kept `src`; it did not (raised as Q20 by
the standard subagent). Without the sources, `GET /api/study/versions` fails
in the container and a run recorded against the deployed API carries no
`prompt_version` or `tool_version` — two event-model fields, so invariant 3.
One line, always correct, and reversible by editing a file, which is why this
is an agent decision under "do not ask about" rather than an escalation. The
cost is the agent's prompt and tool sources shipping in the image; the
bundle already contains both in compiled form.
Affects: apps/api/Dockerfile, A10 · Reverses: none · Closes: Q20

### D24 — Coverage signature and matching tolerance (P1)
Date: 2026-09-18 · Decided by: author (escalated by agent as Q19)
Options: exact on everything · exact sequence + request_type with bucketed
counts and boolean parameters · request_type and tool set only
Chosen: the ordered tool sequence with consecutive repeats collapsed, plus
`request_type`, matched exactly; calls per tool and turns bucketed {1, 2, 3+};
parameters reduced to `has_location`, `has_date`, `has_price_term`,
`has_dietary_term`; rule versioned (`SIGNATURE_RULE_VERSION`).
Reason: fine enough that "uncovered" names a real shape, coarse enough that P1
is not true by construction. Fixed now, before participant data, as §4.2.3
requires.
Affects: B12, C02, C05 · Reverses: none · Closes: Q19

### D23 — Pass criteria, judge protocol and the weather reference
Date: 2026-09-18 · Decided by: author (escalated by agent as Q18)
Options: 8/8 seeds and ≥ 75 % expanded · uniform ≥ 75 % · rates only
Chosen: seed cases pass only at 8/8; expanded cases at ≥ 75 %; a structural
`detected` fails the execution regardless of the judge; pair-wise comparison
runs in both orderings at temperature 0 and passes only when both say "at
least as good"; weather questions are judged against the forecast the agent
actually retrieved (the tool result in the trace), Wikipedia questions against
the stored section.
Reason: seeds are minimum functionality (§3.1, P7), so one failure in eight is a
failure; structural signals do not depend on a baseline and outrank the judge;
two orderings control position bias; a stored forecast cannot be a reference
for a run made on another day.
Affects: B09, B11 · Reverses: none · Closes: Q18

### D22 — Metamorphic relation catalogue
Date: 2026-09-18 · Decided by: author (escalated by agent as Q17)
Options: full catalogue · invariance only · full catalogue plus templates
Chosen: the full catalogue — INV-1 paraphrase, INV-2 typos and casing, INV-3
irrelevant detail added, INV-4 language switch (German); DIR-1 constraint added
or changed, DIR-2 day changed, DIR-3 count changed, DIR-4 negation — at most
one follow-up per relation per seed, chosen by hand in `sim/02_expand`. Venue
lookup and scheduling take all eight; factual QA takes INV-1..4 and DIR-1 (a
different fact); advisory takes invariance only.
Reason: directional relations are where the structural checks earn their keep;
templates would exceed the D21 budget without cutting n.
Affects: B05 · Reverses: none · Closes: Q17

### D21 — Suite size, repetitions and the simulator's turn cap
Date: 2026-09-18 · Decided by: author (escalated by agent as Q16)
Options: 3 seeds/function, 2 follow-ups, n = 4 expanded, cap 4 · same with
n = 8 uniform · 2 seeds/function, 2 follow-ups, n = 4 expanded, cap 3
Chosen: 2 seeds per function (8 seeds at n = 8, per §3.1), 2 follow-ups per
seed (16 expanded at n = 4), simulator turn cap 3 with an earlier stop when the
simulator declares the goal reached. 128 executions per run.
Reason: cost. §3.1 allows n to be reduced outside the minimum-functionality
cases; the reduction is recorded here so the pass-rate resolution it implies is
stated rather than discovered.
Affects: B03, B04, B05, B06, B07 · Reverses: none · Closes: Q16

### D20 — Simulator and judge models
Date: 2026-09-18 · Decided by: author (escalated by agent as Q15)
Options: Gemini 3.5 Flash for both · Gemini simulator with a Claude judge ·
Claude for both
Chosen: `gemini-3.5-flash` (released 2026-05-19, D04) for both the simulator
and the judge, through the same Vertex express key.
Reason: one vendor, one key, one SDK, lowest cost. The agent recommended a
judge from a different family to avoid self-preference bias; the author chose
against it. The judge therefore shares a family with the agent it scores, and
§3.7 / §4.5 must name that as a limitation of the pair-wise comparison.
Affects: B06, B09, B14, `.env.example` (`SIMULATOR_MODEL`, `JUDGE_MODEL`)
Reverses: none · Closes: Q15

### D19 — Constraint representation: predicates with a declarative core
Date: 2026-09-17 · Decided by: author (escalated by agent as Q03, fourth item)
Options: declarative YAML only · Python predicates only · hybrid
Chosen: hybrid. Common checks (expected tool sequence, call counts, slot day
and count, mutation counts per table) are YAML keys the case loader validates;
anything sequence-dependent (retry, widening, "same venues as the seed") is a
named predicate in `cases/predicates.py`, referenced from the case by name.
Reason: declarative alone cannot express a constraint that depends on a
preceding call's outcome; predicates alone put code where the notebook should
show a declaration.
Affects: event-model.md (test case level), B03, B05, B08 · Reverses: none

### D18 — Survey response scales and coding
Date: 2026-09-17 · Decided by: author (escalated by agent as Q03, first item)
Options: 7-point UMUX-LITE with 0–10 recommend · 7-point for all three ·
5-point for all three; banded vs exact age
Chosen: UMUX-LITE items 1 and 2 on 1..7 (strongly disagree → strongly agree);
likelihood to recommend on 1..7 as §4.2.2 states; `real_trip` boolean;
free text optional. Demographics: `age` as an exact integer; `gender` one of
woman / man / non-binary / prefer not to say; `education_level` one of
compulsory / apprenticeship or vocational / matura or high school / bachelor /
master or higher; `llm_familiarity` one of never / rarely / monthly / weekly /
daily. Stored as integers and text codes.
Reason: the Sauro–Lewis UMUX-LITE regression is calibrated on 7 points and
rescaling after collection is impossible; exact age is the author's preference
over bands, accepting that it is more identifying in a small sample.
Affects: event-model.md (survey levels), A01, A08, A09, C02 · Reverses: none

### D17 — When `ignored` is written
Date: 2026-09-17 · Decided by: author (escalated by agent as Q03, "ignored"
item; the operational half of D05)
Options: fixed interval via a scheduled job · when the conversation moves on ·
at session end
Chosen: a pg_cron job stamps `user_action = 'ignored'` on every
`study_suggestions` row older than **24 hours** whose `user_action` is still
null. Only nulls are filled; a non-null value is never overwritten by anything.
Reason: it fires for abandoned sessions, which the other two options never
reach; 24 h is past any single sitting. Consequence, accepted: an explicit
action arriving after 24 h is lost as such.
Affects: event-model.md (suggestion level), A01, A05 · Reverses: none

### D16 — Study session, enrolment, consent gate and decline
Date: 2026-09-17 · Decided by: author (escalated by agent as Q05)
Options: consent row + user_metadata enrolment + loader gate · analytics tab id
as session · everyone in the window is a participant
Chosen: `session_id` is one `study_sessions` row created at consent; every
suggestion the participant produces after `consent_at` attaches to it, the
analytics tab id recorded beside as `client_session_id`. Enrolment: the study
link `/study/join?cohort=study|pilot` stamps enrolment into `user_metadata`,
the mechanism the existing `onboarded` gate uses; `run_type` is the cohort.
Gate: the `_protected` loader redirects an enrolled user with no consented
session to `/study/consent` from every protected route. Decline: `declined_at`
recorded, enrolment cleared, sign-out to a thank-you page. Consent version is a
constant beside the consent text, bumped by hand.
Reason: the only combination where a session is a row with a consent on it and
the gate is server-side. The loader condition is a request-path change for
enrolled users only; it does not touch how the agent handles a request.
Affects: event-model.md (session level), A01, A02, A07, A12 · Reverses: none
Closes: Q05

### D15 — One Supabase project for everything
Date: 2026-09-17 · Decided by: author (escalated by agent as Q04)
Options: dedicated study project with local development runs · one project
for everything · local stack for simulation, prod for participants
Chosen: the existing project, for the simulation and the participant round
alike. `run_type` gains the value `simulation`, set on the harness's sessions.
The simulation API runs with `DEFAULT_SUBSCRIPTION_TIER=pro` so the monthly AI
cap never refuses a run.
Reason: participants' trips and chat already live in this project, so a
second one separates nothing that matters; simulation records must be durable
and queryable next to participant rows for the Chapter 4 comparison, which a
local stack cannot give. The agent's recommendation (a dedicated project, for
a one-sentence retention statement) was rejected on those grounds.
Affects: event-model.md (session level `run_type`), A01, B01, B02, B07, C04
Reverses: none · Closes: Q04

### D14 — Erasure cascades everywhere; export split
Date: 2026-09-17 · Decided by: author (escalated by agent as Q14)
Options: cascade everywhere · surveys cascade, behavioural rows pseudonymous ·
no FK to auth.users
Chosen: every study table references the participant with `ON DELETE CASCADE`.
An account deletion is a withdrawal and removes the behavioural rows too.
Export: `study_survey_demographics`, `study_survey_post_task` and
`study_suggestions` (the verbatim `user_turn`) in `EXPORT_BY_USER_ID`;
`study_user_actions`, `study_feedback`, `study_mutations`, `study_verdicts`
in `EXPORT_EXCLUDED` with reasons.
Reason: the simplest promise to state and keep. Consequence, accepted: a
participant who deletes their account after the round takes their rows with
them, and the information sheet must say that deletion is withdrawal.
Affects: A01, A12, `account.export-tables.ts` · Reverses: none · Closes: Q14

### D13 — Mutation origin taxonomy, scope and mechanism
Date: 2026-09-17 · Decided by: author (escalated by agent as Q13 and the Q03
scope item)
Options: five kinds on the plan tables · five kinds on every trip table · two
kinds
Chosen: `origin_kind ∈ {agent_live_edit, agent_draft_accepted,
agent_place_added, user_manual, system}` on `trip_blocks`, `itinerary_slots`,
`itinerary_days`, `ai_suggestions` (inserts and verdict updates) and
`branches`. Mechanism: `AFTER` triggers reading the `x-study-origin` request
header PostgREST exposes; absent header → `user_manual`; SECURITY DEFINER
functions and the retention job → `system`. Agent-turn writes go through a
per-turn client built from the same JWT with that header. Rows carry table,
row id, op, changed keys and a minimal projection — never the full row.
Reason: only a trigger fires on all three write paths; the five kinds are what
Table 12 and P3 need to separate "Tonic did it" from "the member did what Tonic
proposed"; the plan tables are what §1.4 calls the persistent trip plan.
Affects: event-model.md (state mutation level), A01, A04 · Reverses: none
Closes: Q13

### D12 — `user_action` granularity
Date: 2026-09-17 · Decided by: author (escalated by agent as Q07)
Options: per-target rows + turn label by rule · same with "not undone =
accepted" · one aggregate label only
Chosen: the app appends one `study_user_actions` row per target (`slot:i`,
`place:<id>`, `edits`) and maintains `study_suggestions.user_action` by the
rule: any slot accepted → `accepted`; every slot rejected → `rejected`;
otherwise the `ignored` rule (D17). A live edit is `rejected` on revert and
otherwise follows the `ignored` rule (Table 12: Neutral). `user_initiated` is
derived in analysis from `study_mutations` (origin `user_manual` with a
`google_place_id` matching a place ref on an earlier suggestion in the same
session) and is never written by the app.
Reason: the exact record and the field the pilot assertion checks, without
inventing a reaction the participant did not have.
Affects: event-model.md (suggestion level), A01, A05, C02 · Reverses: none
Closes: Q07

### D11 — Execution failure taxonomy
Date: 2026-09-17 · Decided by: author (escalated by agent as Q11)
Options: turn level only · turn and tool level · all three levels
Chosen: `error_code` at turn level from the closed set `timeout |
llm_call_limit | empty_reply | llm_error | persist_failed | other`; each tool
call's returned `error` string kept in its trace entry; retries counted into
`retry_count` by a counter on the model instance in `adk-llm.ts`. P2's
execution failure = a turn-level error or any tool-level error; recovered
retries reported as a separate rate.
Reason: a failed `search_places` the model talks past is a failure while
computing a suggestion; the retry signal costs one counter and would otherwise
not exist.
Affects: event-model.md (suggestion level), A02, C02 · Reverses: none
Closes: Q11

### D10 — `resulting_state_shape`
Date: 2026-09-17 · Decided by: author (escalated by agent as Q09)
Options: compact shape · compact shape plus post-turn counts · full snapshot
Chosen: `{draft: {suggestion_id, days, slots, slot_types[]} | null, edits:
{move, unschedule, schedule}, places_surfaced, reply: {chars, place_refs,
draft_refs}, trip_after: {blocks, slots}}` — the first four from objects the
service already holds, the last from two count queries after the turn.
Reason: a check can assert on the database, not only on the agent's own
journal, for the price of two counts.
Affects: event-model.md (suggestion level), A02, B08 · Reverses: none
Closes: Q09

### D09 — `request_type` precedence rule
Date: 2026-09-17 · Decided by: author (escalated by agent as Q08)
Options: precedence onto the four functions · composite family label · slash
intent where present
Chosen: `scheduling` if any of `propose_plan`, `move_slot`, `unschedule_block`,
`schedule_block` ran; else `venue_lookup` if `search_places` ran; else
`factual_qa` if any of `get_weather`, `get_climate_normals`, `read_wikipedia`,
`get_region_climate` ran; else `advisory`. One pure function,
`REQUEST_TYPE_RULE_VERSION` stored beside the label; the ordered tool list is
always stored so the composite label stays derivable.
Reason: maps onto the four functions of §1.4 and P2's per-type rates; the
information a precedence hides is recoverable from the trace.
Affects: A02, A03, B12, C02 · Reverses: none · Closes: Q08

### D08 — Thumbs: a dedicated control, and suggestion = agent turn
Date: 2026-09-17 · Decided by: author (escalated by agent as Q12 and the Q03
scope item)
Options: dedicated control · reuse chat reactions · both
Chosen: a dedicated up/down control under every Tonic reply, visible to
participants only, one `study_feedback` row per member per message, changeable.
A suggestion is defined as one agent turn; every turn writes exactly one reply
row, so "a control on every agent message" and "feedback at suggestion level"
(Table 11 vs §4.2.2) are the same statement, keyed by the reply's message id.
Reason: reactions are social and shared; the definition dissolves the Q03
tension instead of adding a level to the event model.
Affects: event-model.md (suggestion level), A01, A06 · Reverses: none
Closes: Q12

### D07 — An interaction is one agent turn
Date: 2026-09-17 · Decided by: author (escalated by agent as Q06)
Options: one agent turn, success or failure · successful replies only · one
planning run
Chosen: one completed agent turn, counted whenever a `study_suggestions` row
was written, whether the agent replied or failed. Requests refused before the
agent ran (quota, validation, membership) do not count. The client reads the
count from the study API, not from the chat response.
Reason: keeps the trigger equal to the number of suggestion rows and the agent
endpoint's response shape untouched.
Affects: A02, A09, A12 · Reverses: none · Closes: Q06

### D06 — `user_turn` is copied, and the chat row id is kept
Date: 2026-09-17 · Decided by: author (escalated by agent as Q10)
Options: copy and keep the id · copy only · reference only
Chosen: the suggestion row stores the member's message text verbatim at turn
start and the `chat_messages.id` beside it.
Reason: the chat row can be edited and is deleted with the trip; the copy is
the record, the id is the join.
Affects: event-model.md (suggestion level), A01, A02 · Reverses: none
Closes: Q10

### D05 — `ignored` replaces `left` as the user action
Date: 2026-09-17 · Decided by: author
Options: keep both names · standardise on `left` · standardise on `ignored`
Chosen: `ignored`, in Table 11 and Table 12 alike; the manuscript was corrected.
Reason: Table 11 said `left` and Table 12 said `Ignored` for the same state,
which would have become two columns and then two label distributions.
Affects: event-model.md (suggestion level), Phase A logging, §4.3 analysis
Reverses: none
Note: the *operational definition* — what event causes `ignored` to be written,
and when it becomes final — is still open. See event-model.md.

### D04 — Model stays on `gemini-3.5-flash`; the release date is recorded too
Date: 2026-09-17 · Decided by: author (escalated by agent as Q01)
Options: pin a dated snapshot of 3.5 Flash · upgrade to the newest Flash
release · keep 3.5 Flash and record its release date
Chosen: keep `gemini-3.5-flash`, and record `DEFAULT_VERTEX_MODEL_RELEASED`
(2026-05-19) alongside it in run metadata.
Reason: Q01 was raised on a false premise. In the Gemini 3.x Flash family the
release *is* the id — 3.5, 3.6, 3.7 and 3.8 are separate models with separate
release dates, and there are no `-001` snapshot suffixes. `gemini-3.5-flash`
does not move on its own, so invariant 2 was already satisfied; what was missing
was the date, which is what Table 11 actually asks for. Separately, 3.5 Flash is
guaranteed until at least 2027-05-19 while 3.6/3.7/3.8 are documented as
short-term availability models — so for a once-only participant round, staying
on 3.5 is the safer choice, not the conservative one.
Affects: apps/api/src/lib/env.ts, apps/api/.env.example, root CLAUDE.md rule 2,
event-model.md (run level `model_released_on`)
Reverses: none · Closes: Q01
Constraint: do not upgrade the model while the study is running.
Evidence: a live `generateContent` call against the Vertex express endpoint
returns `modelVersion: "gemini-3.5-flash"` — the id unchanged. Where an
underlying snapshot exists the response resolves to it (a 2.x model returns
`gemini-2.0-flash-001`), so the absence of a suffix here confirms the id is
itself the version rather than a pointer to one.

### D03 — State reset is a precondition, not a logged field
Date: 2026-09-17 · Decided by: author (escalated by agent)
Options: log per repetition · log once per run · check before the run and
refuse to start it
Chosen: a check that runs before a run starts and refuses to start it if the
slate is not clean.
Reason: as a logged field it is near-constant by construction — a run that
proceeded would always carry `true`, so the column evidences nothing. As a gate
it does what invariant 1 asks ("assert on this; do not assume it"): a dirty
state produces no run at all.
Affects: event-model.md (run level), Phase B harness
Reverses: the field as listed in Table 11
Manuscript: updated the same day. The Table 11 row now reads "Confirmation of
state reset between repetitions; Necessary precondition, else no run", so the
implementation and the published schema agree. No follow-up outstanding.

### D02 — Surveys are separate tables
Date: 2026-09-17 · Decided by: author (escalated by agent)
Options: columns on the session row · one table per instrument
Chosen: `survey_demographics` and `survey_post_task`, each keyed to
`session_id`.
Reason: clean separation of self-reported survey data from behavioural
telemetry. It also makes the consent commitments tractable — a deletion or
access request is answerable per table rather than per column.
Affects: event-model.md (session and survey levels), Phase A
Reverses: none

### D01 — The model pin lives in code, repo-wide
Date: 2026-09-17 · Decided by: author
Options: pin in deployment config only · pin in code as the repo-wide default ·
pin for study and simulation runs only
Chosen: in code, as the repo-wide default in `apps/api/src/lib/env.ts`.
Reason: §3.3 claims the simulator exercises the same paths as ordinary use. A
production alias with a study-only pin would contradict that claim in the one
place it matters, and a pin that lives only in deployment config is invisible to
any reader of the repository.
Affects: apps/api/src/lib/env.ts · Reverses: none
