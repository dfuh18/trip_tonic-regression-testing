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

### D94 — The judge is told the day the execution ran, in UTC
Date: 2026-09-25 · Decided by: author ("judge and agent get today as
context"; raised while scheduling the overnight B10 run)
Before: the judge's "today" block (D79) used `date.today()` at judging time,
and a near-dated case's trip in the judge's fixture summary was rebuilt from
that same day. Judged the morning after an overnight run, every execution
before midnight was scored against the next day, and the near-dated trip the
judge saw started a day later than the one the agent planned.
Chosen: every date the three parties see is the execution's UTC day.
`scoring.execution_day()` takes it from `study_case_executions.started_at`;
`score_pointwise(..., today=)` passes it to the today block and to
`fixture.for_case()`. The harness builds near-dated trips with
`fixture.utc_today()`, matching the agent, whose "TODAY IS" line is UTC
(D92). A local date disagreed with UTC between 00:00 and 02:00 CEST, which is
when an overnight run executes.
The judge prompt template is unchanged (`judge_pointwise_v1`); only the date
it is given differs, and only for executions judged on a later day. Rehearsal
scores judged the same day are unaffected. Pair-wise comparison (B11) still
uses the judging day and must be revisited before B11: baseline and candidate
replies are from different days.
Affects: B09, B10, B11, `src/judge.py`, `src/scoring.py`, `src/fixture.py`,
`tools/overnight_baseline.py`, `tests/test_judge_date.py` · Amends: D79

### D93 — Participants see the empty chat's one-tap examples
Date: 2026-09-25 · Decided by: author (escalated by agent)
Options: hide the examples for participants · keep them as the app ships ·
show them as text but not tappable
Chosen: keep them. An empty trip chat offers five one-tap requests
(`components/chat/chat-empty-state.tsx`: `/find rooftop bars near the old
town`, `/plan our first day here`, `/reschedule free up Saturday for a day
trip`, and two `@Tonic` questions on weather and a neighbourhood). The task
briefing also shows that empty chat, as the real component, so participants
recognise where to start.
Reason: the study measures the app as participants get it; hiding product
guidance for participants would make the participant round a different
system from the product.
Consequence for the analysis: some participant requests will be these texts
verbatim. They are identifiable exactly (the `user_turn` equals an example,
with or without the command prefix), so the coverage comparison (P1) should
report them separately or with and without them — and must be computed while
`user_turn` still exists (before the eight-month anonymisation, D91).
Affects: C02 (P1 reporting) · Reverses: none

### D92 — Pre-merge privacy hardening: the consent form made true
Date: 2026-09-25 · Decided by: author (after the pre-merge audit; fixes
approved as a batch, "round the timestamps", "show the options permanently",
"always communicate errors to the user")
The audit (8 auditors over the branch diff) found statements in the consent
form and privacy notice that the code did not keep, and data gaps that would
have been found only after the round. Chosen, per finding:
- **Lookups disclosed.** Tonic also sends search terms and article titles to
  Wikipedia (US) and coordinates and dates to Open-Meteo; the form, the
  privacy notice and participant-data-facts.md now name both, and say display
  names reach Vertex. The form was edited in place and keeps version
  `2026-09-25`: no pilot or study session existed, so no consent was given
  to the earlier wording.
- **Anonymisation amends D91.** At eight months every timestamp is also
  truncated to the day, `place:` ids are stripped from action targets, and the
  participant's `api_usage_events` rows inside [consent, last turn + 1 h] lose
  user, trip and session ids — exact times had let anonymised rows be joined
  back to the account. Order within a day is lost for mutations and actions;
  `turn_index` keeps the turns' order.
- **Only consenting actors are recorded.** A co-member's accept or reject on
  a participant's draft is stored with `actor_user_id` null (the reaction
  still counts for the turn's D12 label). The withdrawal script also nulls a
  person's actor links on others' suggestions.
- **A decline stores only** account id, cohort and time.
- **Export** now includes the participant's thumbs and reactions (own-row
  SELECT policies; the export reads with the caller's RLS client).
- **Study thumbs always visible** for participants, labelled, apart from the
  group reactions (which keep 👍/👎); every failed direct study action shows an
  error to the participant.
- **Logging errors are no longer silent:** a failed lookup or count in the
  turn logger and StudyActions is logged, and `trip_after` is null rather than
  a fabricated 0 (rule 3).
- **Integrity:** `x-study-origin` `suggestion=` must belong to the trip;
  device and session headers are validated; the mutation trigger can no
  longer abort a member's write on a malformed header; default table
  privileges revoked on the study tables.
- **Admin:** the cost rollup no longer resolves user ids to names (D1); the
  admin table shows ids.
- **Prompt:** the "TODAY IS" line is computed in UTC throughout. Identical
  text on Render (UTC); `prompt_version` changes because the file's hash does.
  Before B10, so no run is affected.
Migration `20260925125438_study_privacy_hardening.sql`, tested live inside a
rolled-back transaction (`tools/anonymise_rollback_test.sql`).
Affects: D91, D14, A02, A05, A07, A12, C01 · Reverses: none

### D91 — Study data is anonymised eight months after consent
Date: 2026-09-25 · Decided by: author (retention in the consent form; the
implementation escalated by agent and approved)
Options: delete everything at eight months · remove account links and text,
keep anonymous records · keep until the author deletes by hand
Chosen: the form's wording: eight months from consent, "the link to your
account and the text of your messages are removed automatically, and only
anonymous records of the kinds of requests made and their outcomes remain".
Implemented as `study_anonymise_expired()`, a daily pg_cron job
(`20260925122418_study_anonymise_after_retention.sql`), for `pilot` and
`study` sessions only. It nulls every account link (`user_id`,
`actor_user_id`), everything a participant wrote (`user_turn`, `free_text`),
every id that leads back into the trip and so to the account (trip, run and
chat-message ids, `study_mutations.row_id`, `*_id` keys of projections, the
draft id in the state shape, `client_session_id`), and the **values** of tool
arguments, keeping their keys; it stamps `study_sessions.anonymised_at`.
Seven columns become nullable; nothing is renamed or dropped.
Reason: the form promises it, and a promise with no job behind it is false
the day it matures. Keys-without-values keeps the shape of each request (what
kind of lookup it was) while removing what the person asked for.
**Consequence for the analysis:** anything that needs the removed values
(argument text in a P1 signature, the verbatim `user_turn`, joins into trips)
must be computed within eight months of the first consent.
Deletion on request without deleting the account (the form's other promise):
`tools/withdraw_participant.py`, tested end to end on a throwaway account.
Tested: the migration and the job ran on the live project inside a
transaction that always rolls back (`tools/anonymise_rollback_test.sql`):
the expired session anonymised, the recent one untouched, a second run a
no-op; nothing persisted.
Affects: event-model.md (Retention), C01 (`anonymised_at` exempt), C02/C03 ·
Reverses: none

### D90 — A failed turn records the configured model
Date: 2026-09-25 · Decided by: author (escalated by agent)
Options: leave failed turns without a model (report only) · fall back to the
configured model when the response carries none
Chosen: fall back. `modelColumns` in `agent.study-log.ts` now uses
`model || env.VERTEX_MODEL || DEFAULT_VERTEX_MODEL`, resolved as `createAdkLlm`
resolves it, so `model_version` and `model_released_on` are set on every
completed turn, failed or not.
Reason: the C01 pilot checks, run over the 379 simulation turns, found 6 turns
that ended in `llm_error` before the model answered and were logged with no
model: the logger read the id from the response usage only. Table 11 asks for
the dated release on every suggestion, and a failed turn is exactly the row P2
counts. The fallback names the model the request was sent to, which is the
fact the column records. Logging only; the turn itself is unchanged (rule 4).
The 6 historical simulation rows stay null; nothing is backfilled.
Affects: A02, C01 (`check_turns` fails a missing model again) · Reverses: none

### D89 — Every Vertex call goes to the EU multi-region endpoint
Date: 2026-09-25 · Decided by: author (escalated by agent)
Options: keep the global endpoint · EU multi-region
(`aiplatform.eu.rep.googleapis.com`) · Frankfurt only (`europe-west3`)
Chosen: **EU multi-region**, for the agent, the simulator and the judge alike.
It is the code default in both places (`DEFAULT_VERTEX_BASE_URL` in
`apps/api/src/lib/env.ts`, `VERTEX_BASE_URL` in `src/config.py`), not an env
var, so no deployment or harness machine can drift back to global. The
endpoint is **not** added to `study_runs` (author: "config only"); this entry
and the two defaults are the record.
Reason: with Supabase in Stockholm and Render in Frankfurt, the global endpoint
was the one path that could process participant requests outside the EU
(and the judge re-reads participant replies, P3). Probed 2026-09-25 with the
express key: `gemini-3.5-flash` answers on global, the EU multi-region and
europe-west3; europe-west1 and europe-west4 return 404. Multi-region over
Frankfurt because capacity is pooled across EU regions, and capacity failures
count as failures (D44, Q24).
**Timing is the point:** the endpoint is part of what the rounds measure —
latency, 429s and so retries and lost executions differ by serving pool — so
the simulation and the participant round must share it. Switched before B10;
the rehearsal runs to date (incl. 42cab17a) ran on global and are not
comparable on latency or capacity failures. The pinned model is unchanged.
Affects: B10, B11, C03, apps/api `lib/env.ts` + `adk-llm.ts`, `src/config.py`,
`src/llm.py`, the privacy notice, `docs/participant-data-facts.md` ·
Reverses: none

### D88 — A fail from position alone is a draw, and passes visibly (resolves Q34)
Date: 2026-09-24 · Decided by: author (escalated by agent as Q34)
Options: D23 strict (a contradictory pair fails) · a same-slot pick is a draw ·
any contradictory pair is a draw
Chosen: **any contradictory pair is a draw** ("if only position would make a
fail it should pass, but record it clearly"). The judge still compares in
both orderings (D23's control is unchanged). An execution now fails on the
judge only when **both** orderings prefer the baseline. When the orderings
contradict each other (the same slot winning both times, or the baseline
preferred in one order only), the fail would come from position alone. That
is a **position draw**: it passes, and it is recorded as one:
- `Comparison.position_draw` marks it; `pass_rates` counts `position draws`
  per case and shows `pass rate (strict)` (D23's reading) beside the verdict;
- `compare_run` logs it as `DRAW`, not `pass`;
- `sim/04_regress` lists every draw separately from the failures and
  recomputes all verdicts under the strict reading next to the rule in force.
Nothing is lost: both orderings are stored in `study_comparisons` (D87), so
every reading can be recomputed.
Structural `detected` still fails whatever the judge says. A consistent
preference for the baseline still fails, so a real regression is caught.
Reason: the order-swap exposes position bias, and the pass rule decides what
it costs. On the rehearsal, 3 of 30 pairs (10 %) were draws, which projects to a
~57 % chance that a seed fails on position alone at 8/8 under the strict
reading. That would be a property of the judge charged to the agent.
Effect on the rehearsal: 5 of 31 cases fail (was 8 under strict); 3 cases
pass with one position draw each.
Affects: src/comparison.py · notebooks/sim/04_regress · tests/test_comparison.py ·
Amends: D23 (how a contradictory pair counts) · Closes: Q34

### D87 — Pair-wise verdicts get a table (resolves Q33)
Date: 2026-09-24 · Decided by: author (escalated by agent as Q33)
Options: A a `study_comparisons` table · B the local JSON cache plus committed
notebook outputs · C verdicts on the candidate's execution row
Chosen: **A.** Migration `20260924194027_study_comparisons.sql`, pushed. Shaped
after `study_scores` (D71):
- one row per candidate execution, baseline execution, judge model and
  pair-wise prompt version;
- both orderings kept in their positions (`ordering_candidate_b`,
  `ordering_candidate_a`), with the verdict, the rationale and the candidate's
  structural outcome as a snapshot;
- `baseline_kind` (`adopted` | `test`) and `baseline_key` (a hash of the
  baseline's entries), so a rehearsal's verdicts can never be read as
  stage 3.2's;
- a check refuses a row that is neither decided nor explained by an `error`;
- RLS on, service_role only, as every harness table.

`comparison.compare_run` writes each verdict as it is made and resumes from
the table. The JSON cache is gone. `survey` counts the table in the run's
completeness report, and a run with no comparisons is explained there (a
baseline run never has any).
Verified against the live table, 2026-09-24:
- the rehearsal's 31 verdicts were written through the new path and read back
  identically, with a judge that raises if called, so resuming makes no judge
  calls;
- a fresh judged comparison of the probe run wrote 6 rows, and the two
  executions that *are* the baseline came back `tie`/`tie`;
- the table refused a row that was neither decided nor explained;
- `sim/04_regress` re-executed from the table with the same 23 pass / 8 fail;
- the schema-hardening (65) and permissions (10) audits pass.
Reason: the result of stage 3.2 belongs in the record it is joined with, for
the same reason D71 gave point-wise scores a table.
Affects: supabase/migrations · src/comparison.py · src/survey.py ·
notebooks/sim/04_regress · Reverses: none · Closes: Q33

### D86 — The baseline is each case's best clean execution
Date: 2026-09-24 · Decided by: author (raised by agent from the comparison rehearsal)
Options: the top-scoring structurally clean execution · a median one · the
first clean one
Chosen: **top-scoring**, as `comparison.propose_baseline` ranks it:
structurally clean first, then the highest point-wise score, then the
earliest repetition. The author still reads and adopts per case (B10).
Reason: the author's. The higher the reference, the more a comparison can
tell. Against a median reply, a prompt change that makes answers slightly
better would pass unnoticed, because "at least as good as average" is easy.
Against the best reply, it shows. The cost is stated and accepted: ordinary
variance fails some repetitions that are merely a little weaker than the
best, and under D23 a seed needs all eight. The rehearsal showed this
already: two packing-list executions scoring 9 and 10 point-wise lost both
orderings to a 10/10 baseline. Those failures are read, not counted blindly:
`04_regress` shows every failure's judge rationale beside its structural
verdict, and the structural checks do not depend on the baseline at all.
Affects: src/comparison.py (unchanged: it already ranks this way) ·
notebooks/sim/03_baseline · notebooks/sim/04_regress · Reverses: none

### D85 — A score on an execution that acted again after turn 1 says so
Date: 2026-09-24 · Decided by: agent (asked for by the author: "it should be clearly marked")
The judge scores turn 1 only (D34), and D82 kept that for the multi-step
seeds. What was missing was the marking. `Scored` now carries `turns` and
`later_acting_turns` (turns after the first with at least one tool call), and
the scoring log and report tag every execution where a later turn acted:
`[judged turn 1 of 2; turns 2-2 not judged]`, plus a header line naming
those cases. A later turn that only signs off is not marked, because nothing
was left unjudged. Checked on the two recorded runs: all six executions of
the probe are marked, and none of the 29 in 42cab17a. No change to what is
scored, or to `study_scores`. Surfacing the mark in the database would be an
event-model change, and is not made here.
Affects: src/scoring.py · tests/test_scoring_marks.py

### D84 — The two multi-step seeds are approved
Date: 2026-09-24 · Decided by: author
The author approved `scheduling_dinner_from_offer` and
`scheduling_afternoon_then_tram` as they stand after D83. Marks written on
that instruction, bound to the reviewed text (sha `3fe5226c1d73` and
`b47d5630ba76`), so both report `current`. Every case in the suite now
carries an author mark.
Approving the seeds as written settles what Q31 left open for them: the two
check keys, the sole-check-key admission route and the ceiling of 176 are
final rather than provisional; `run_priority: 2` stands; they take **no
metamorphic follow-ups** for now (as D51 did for the surf seed); and
"whether the agent picked the place the member meant" stays a stated limit
(Q32 → A, D82).
Affects: cases/reviewed.json · Closes: Q31

### D83 — Both multi-step seeds stay; two check faults fixed; the landmark criterion goes
Date: 2026-09-24 · Decided by: author (escalated by agent after probe 287e7780)
Options: apply D82 as written and drop the afternoon seed · keep both
Chosen: **keep both.** The probe met D82's keep rule for the dinner seed:
reference joined search → draft in 3 of 3 repetitions, and its false merges
stayed with the three Belém drafts. The afternoon seed turned out to have a
purpose D82 did not know about. In all three repetitions the agent moved the
tram correctly (Friday, one hour, after the plan), but unasked it also
re-proposed the draft with stops already on the live itinerary: the Time Out
Market lunch in two repetitions, and the tram itself in one. Accepting such a
slot schedules a second slot of the same saved stop
(`draft-accept.ts`: a `reuse_block_id` goes straight to `addBlockToDay`), so
the group would see the lunch twice on Friday. No other case can reach this
behaviour. The seed's `slot_count` and `draft_slot_starts_between` catch it.
**Two check faults found by the probe, fixed:**
- `slot_moved.after_latest_draft` compared the tram against a re-proposed
  draft that contained the tram, so it failed because the tram was the
  draft's last slot. The moved stop's own slot is now left out.
- `places_near` read every ref a reply carried. The application attaches refs
  by name, so a reply naming "Santo António" (drafted, in Alfama) also
  carried a same-named bakery 6.7 km away in Lumiar. On a turn that drafted,
  it now reads only the drafted places; every other turn is unchanged, so no
  existing case is affected (none asserts places_near with a draft).
**The dinner seed's criterion "placed by a street or landmark" is dropped.**
The member named Alfama in the opening turn, so where the options are is
given by the request, and places_near checks it. It cost the seed 3–4
points in every repetition: 6, 7, 7 before; 9, 10, 10 in an unpersisted
re-score after.
After the fixes the probe's only structural failures are the two
repetitions that re-drafted live stops.
Reason: the author's, on the probe's evidence.
Affects: cases/scheduling_*_{from_offer,then_tram}.yaml · src/checker.py ·
src/execution.py · Reverses: D82's "drop the afternoon seed"

### D82 — A probe decides whether the multi-step seeds stay; the judge keeps D34
Date: 2026-09-24 · Decided by: author (escalated by agent as Q31, Q32)
Options: remove both seeds now · keep both · probe first. For the probe: n 2,
3 or 8; keep the dinner seed if reference links it in every, most or any
repetition; the new check keys accepted provisionally or stripped. For the
judge (Q32): A first reply only · B also the continuation with context ·
C whole transcript.
Chosen: probe both seeds at **n = 3** before deciding. The dinner seed
validates reference (Q29) only if reference joins search → draft into one
request in **every** repetition, and its false merges stay confined to
requests that share a place. If it does, keep that seed and drop the afternoon
seed, whose split is predicted and can be stated in prose. If it does not,
remove both, remove reference from the rule, and treat follow-ups as
unidentifiable. Q31 items 1–3 (the two check keys, the sole-check-key admission route,
the ceiling of 176) are **accepted provisionally** for the probe, so that its
structural checks can separate "reference failed" from "the agent did not do
what the case asked". They leave with the seeds if the seeds leave. **Q32: A.**
The judge scores the first reply (D34) for these seeds too. In the
participant round P3 scores the opening turn of each request, and B is
reconsidered with Q29 once the pilot shows how many turns are follow-ups.
Reason: the author's test for the seeds is whether they make follow-ups
identifiable in the user study. Otherwise they only add complication. That
question has an answer only on data containing follow-ups, and the probe is
the cheapest such data.
Affects: cases/ (D81's seeds) · Q29 · Q31 · Q32 · notebooks/sim/08_segmentation
Reverses: none · Closes: Q32 (A); Q31 items 1–3 provisionally

### D81 — Two multi-step seeds (resolves Q30)
Date: 2026-09-24 · Decided by: author (escalated by agent as Q30)
Options: one seed · two seeds (search → draft, draft → edit) · none, and
report the split error as unmeasured
Chosen: two seeds — `scheduling_dinner_from_offer` (a `/find` whose second
turn drafts one of the offered places) and `scheduling_afternoon_then_tram`
(a `/plan` whose second turn moves a live stop to the end of the draft).
Reason: no case had more than one turn that acts, so the agent was untested on
acting on its own earlier turn, and Q29's segmentation rule could be tested
for merged requests only, never for a request that changes shape mid-way.
What the seeds needed beyond the case files is raised as **Q31** rather than
recorded here: two new check keys, a third admission route, and the execution
ceiling. They are implemented so the suite runs, and are the author's to rule
on at review.
Affects: cases/ · src/cases.py · src/checker.py · src/execution.py ·
src/tables.py · tests/test_metamorphic.py · Reverses: none · Closes: Q30

### D80 — Assert the relation, not the reading
Date: 2026-09-23 · Decided by: author (commissioned the audit, directed the fixes)
An independent audit of all 252 tests, prompted by four tests being falsified
in one week by *correct* work rather than by regressions.

**Verdict: systemic in mechanism, cheap in consequence, and the real damage was
outside the test suite.** The evidence for the mechanism is total — every one
of ~40 commits touching `src/` also touched `tests/` in the same commit, never
once separately. Tests here are written as *evidence the change works*, which
is the posture that writes down a reading. A docstring since deleted said so
outright: *"Pinned so adopting them is a deliberate act… When the author
reviews them this test changes — which is the point."* That is the defect
stated as a design goal.
The audit also found the project's own design encourages it, and named the
confusion exactly: `suite_version`, `case_version`, `CHECKER_VERSION` and
`judge_prompt_version` are deliberate content pins, because the artifact's
thesis is that change must be detectable. The test suite adopted that reasoning
about itself. But **a hash reports drift; a test blocks the commit** — which is
why `test_tables.py`'s hard gate on unmarked cases sat in direct contradiction
to `runner.py`'s considered choice to warn and not refuse.
Counter-evidence, recorded because it bounds the claim: ~190 of 209 tests
encode real invariants, one line in 375 asserts was dead, and all four
falsified tests lived a day or less.

**The rule.** *Assert the relation, not the reading.* A test may compute both
sides from the artifact, or bound one side; it must not contain a side that
project data determines. If someone doing correct planned work would have to
edit your test to record what they just did, you wrote down an observation.
Corollaries: a version is a **shape**, never a value; a count is a **bound or a
derivation**, never an equality.

**Fixed.** Two literal version pins that survived D79's fix — one of them two
assertions below the fixed version of itself, the fourth instance of the
one-of-N pattern (D70's `study?.fail` sites, D73's four `study_verdicts`
claims). Three count pins in `test_metamorphic.py` became a derivation from
`DERIVATIONS`, a property about which seeds may exceed the budget, and a named
`D21_EXECUTION_CEILING`. Two hard-coded case-id lists became properties over
`unique_contribution()`. A `words` dict that would raise `KeyError` rather than
fail an assertion. The hard review gate became a tracking invariant plus a
mechanism test on a temp copy.

**The published notebook was the real cost.** `01_cases` — the stage-1 worked
example — told readers for three days that the suite had **8 cases** and was
**8 of 8 reviewed**, against 29 and 29/29. `02_expand` had two guards of
exactly the right shape; nobody generalised them, so the notebook that was
wrong had none. `tests/test_notebook_freshness.py` now parametrizes them over
every published notebook, deriving every expected number from `load_cases()`.
Run-scoped notebooks are exempt by *stating the run they describe*, not by
filename.

**And the mechanised part took three attempts, which is the part worth
keeping.** The dead-assert sweep was written, passed, and was then shown to
pass with a dead assert planted in front of it — a vacuous check for vacuous
checks. Two causes, both mine: a tracer matching frame filenames by string
prefix against an absolute path, recording nothing; and a `continue` written
for "this file was skipped" that turned total failure into green. The second
attempt fixed the matching and took over fifteen minutes, because a
Python-level trace callback over a 253-test suite is what C-accelerated
coverage tooling exists for. The third uses `coverage.py`, runs in two minutes,
fails when the sweep measures nothing, and was verified by planting a dead
assert and watching it name the line.
It immediately found one I had left: an `elif` branch unreachable because every
mark now carries a sha, so the test could not exercise the state it was named
after. Both mark shapes are now constructed rather than looked for.
Docs were checked and are **not** affected: counts in `DECISIONS.md` and
`REVIEW_LOG.md` sit in dated append-only entries, where a count is a historical
fact rather than a stale spec.
Affects: tests/test_no_dead_asserts.py (new) · tests/test_notebook_freshness.py
(new) · tests/test_metamorphic.py · tests/test_tables.py · tests/test_signature.py
· tests/test_judge_simulator.py · conftest.py · notebooks/sim/01_cases.ipynb ·
requirements.txt
Reverses: none

### D79 — The judge is told what day it is, and every case is now approved
Date: 2026-09-23 · Decided by: author
**The judge scored half of two criteria.** It was given the trip's dates via
the fixture summary and never the current date, so a criterion contrasting
"now" with the trip was only partly evaluable:
- `factual_qa_lisbon_forecast_next_days` — "answers about the next few days,
  and does not drift into the trip's own dates". It could confirm the reply
  avoided November, because it knew the trip was in November; it could not
  confirm the dates given *were* the next few days. Its own rationale said
  exactly that and no more.
- `factual_qa_lisbon_trip_forecast` — "answers about the trip's own days rather
  than about today or the coming week". The near-dated fixture starts three
  days out, so the two alternatives overlap and the contrast was unevaluable
  outright.
Those two cases are a **pair** precisely because what is under test is which
calendar the agent resolved against (D54) — and the only instrument scoring
them could not see the distinction. The judge now gets today's date beside the
trip summary, the same fix D57 applied to the agent for the same reason.
`judge_prompt_version` bumped to `judge-pointwise/2`, so scores from before and
after stay distinguishable in `study_scores` (D71's versioning earning its
keep). Nothing citable is invalidated: every run so far is an n=1 probe.

**Every case is now approved, bound to its text.** The author reviewed the 18
metamorphic cases (D78) and then the 11 seeds, including the eight marked
before D74 whose wording had since been sharpened by their own guidance.
State: **29/29 `current`** — every case marked, every mark carrying the
`case_version` of the text that would run. §3.1's claim that the cases are the
author's rather than the model's is evidenced for the first time.

**Three tests were pinning snapshots rather than claims** and were rewritten as
each was falsified by the review itself — "no mark carries a hash yet", "three
seeds are still unreviewed", "unverifiable and unreviewed both exist". Each was
a description of one afternoon. What replaced them: nothing runs unmarked,
nothing runs drifted, and an edit after approval is visible as drift —
exercised on a temp copy rather than observed in the live ledger. A fourth
pinned the literal judge prompt version, which would have failed on every
legitimate bump; it now asserts the version is declared and recorded, not which
one it is.
Affects: src/judge.py · src/prompts/judge_pointwise_v1.md · cases/reviewed.json
· tests/test_tables.py · tests/test_judge_simulator.py
Reverses: none

### D78 — The metamorphic cases are approved, and review covers every case
Date: 2026-09-23 · Decided by: author
The author reviewed all 18 metamorphic cases and approved them. Marks written
on that instruction, each carrying the `case_version` of the text read (D74),
so all 18 report `current` rather than `unverifiable`.
Two things this changed in the mechanism:
- **`review_status` now covers every case, not only the seeds.** A follow-up is
  hand-chosen too — the perturbation and the expected delta in
  `cases/derivations.py` are authored decisions (D21, D22), not derivations of
  the seed — so it is the author's or the model's on the same terms. Reporting
  only seeds had left 18 of 29 cases outside the provenance record entirely.
- **`review_report` splits by provenance**, because the two populations are
  approved separately and at different times: the seeds one by one in
  `sim/01_cases`, the follow-ups as a set once their derivations settled. One
  number over both hides which is unevidenced.
State now: metamorphic 18/18 `current`; seeded 8/11 marked but all eight
`unverifiable` (marked before D74 carried a version) and three unreviewed.
**Also: the three added seeds were introduced in prose and never shown.**
`sim/01_cases` presented eight; D51 and D54 added three more under the coverage
rule rather than D21's budget, and no notebook displayed them. `sim/02_expand`
now presents them where the admission rule justifies them — the request each
makes, the tool it is the only route to, and why the two forecast seeds are a
pair rather than a duplicate (which calendar the agent resolves against cannot
be tested by a case that does not say which period it means).
A test that pinned "no mark carries a content hash yet" was rewritten: it was
asserting a transient state rather than the distinction, and the author's
approval falsified it within a week of being written. It now asserts that a
mark with a sha reports `current` or `drifted` and one without reports
`unverifiable`, which is the claim that holds regardless of how much has been
reviewed.
Affects: src/cases.py · notebooks/sim/02_expand.ipynb · cases/reviewed.json ·
tests/test_tables.py
Reverses: none

### D77 — Both routes to a finished row spend the retry budget
Date: 2026-09-23 · Decided by: author
The third review's one genuinely new defect (its D1). A repetition that
recovered from a simulator refusal and then returned a **platform** failure was
handed straight to `settle()`, outside the retry loop — so its remaining
attempts were never spent, `platform_losses` counted it as lost, and the log
said "LOST to the platform after 4 attempts" when two had been used.
Same class as the defect `settle()` was extracted to fix one round earlier: a
second path that skipped a policy the first path applied. The fix is the same
shape — `drive()` now holds the retry loop, both routes call it, and neither
can diverge from the other without the other changing too.
Two smaller things fell out of it. The simulator handler restarted its attempt
numbering at `first` even when the failure happened later in the loop, so a
`progress` cell now carries the attempt outward; and a recovered repetition
that then succeeds is no longer reported as a platform loss.
**The test that was supposed to catch this certified it instead.** It scripted
four outcomes, consumed two, and asserted on the log string — so it passed on
the broken path, which is how the defect survived D71's round. The replacement
asserts on the **attempts actually consumed**, because that is the thing that
was wrong; a log line is not evidence about control flow. Verified by
reintroducing the bug: two tests fail with it, seventeen pass without it. That
check is worth more than the fix.
Affects: src/runner.py (`drive`) · tests/test_runner_loop.py
Reverses: none; completes D71's `settle()` extraction

### D76 — Verdicts are appended and versioned; the completeness gate can see its own gaps
Date: 2026-09-23 · Decided by: author (directed the fixes after the third review)
The third review found all seven of D71's fixes real — a first, after two
rounds where a shipped fix was a no-op or backwards — and three defects worth
acting on before a baseline.

**Structural verdicts were mutable and unversioned, and the damage was already
in the record.** `checker.record()` was an UPDATE on `study_case_executions`,
and `CHECKER_VERSION` was computed and never written. So re-checking a run
rewrote its verdicts in place. After D72 inverted the drinks assertion, the
runs that happened to be re-checked changed and the ones that were not kept
their old value:

    09f288e9  ..._dir4_not_a_meal  detected (1 finding)
    3cf2fd09  same case            none     (silently overwritten)

Two runs disagreeing for a reason the record could not explain. The
`study_scores` migration had made the opposite argument three days earlier — "a
disagreement between two versions is data, and resolving it by overwriting
would destroy the only evidence that they disagreed" — and it had been applied
to the judge and not to the checker.
`study_structural_verdicts` now holds one row per (execution, checker version),
appended, carrying the `case_version` it judged. A verdict is only
interpretable against the case it was computed from, and cases are edited (D48,
D55, D58, D72). The column on the execution stays as a convenience mirror of
the newest verdict, because every existing reader uses it; it is no longer the
only copy.
**Stated plainly: backfilling this destroyed the inconsistency rather than
preserving it.** Re-checking all four runs under `checker/1` made the record
coherent — every verdict now names its checker and its case version — but the
old `detected` on `09f288e9` is gone. That value was an artefact of my own
uneven re-checking rather than a finding, and it was uninterpretable (no case
version, no checker version). The trade is defensible and it is still a
deletion, so it is recorded as one.

**The completeness gate was hiding one of the things it looks for.**
`EXPECTED_SPARSE` was keyed by bare column name, so the reason written for
`study_scores.judge_prompt_version` (NOT NULL there) silenced
`study_runs.judge_prompt_version`, which genuinely had no writer. It is now
keyed by (table, column). The gate also inspected 5 of 11 study tables and
named two that do not exist under those names — it had been written from the
event model rather than from the schema, so it inherited the document's blind
spots. Rebuilt against the schema: 12 tables, every empty one either excused by
name or reported.
`open_run` now records `judge_prompt_version`, closing the field the leak hid.

**The new write paths were exercised before the baseline, not by it.** A
two-case probe run (`94eec75a`, $0.03) wrote `case_version` per execution,
`judge_prompt_version` on the run, and appended verdicts carrying both. This
repository's own lesson from D71's N1 is that verifying which rows a function
SELECTS says nothing about whether the next write lands; a 160-execution
baseline as the first exercise of three new columns would have been the same
mistake at 80× the cost.
Every survey now reports **zero gaps** across the probe, `edcfa1b4` and
`3cf2fd09`.
Affects: supabase/migrations/20260923120000_study_structural_verdicts.sql ·
src/checker.py · src/runner.py · src/survey.py ·
notebooks/sim/run_survey.ipynb
Reverses: none; corrects the verdict half of the 2026-09-21 ruling, which put
the verdict on the execution row and left it unversioned

### D75 — The Sintra lunch search_places cap goes to four
Date: 2026-09-23 · Decided by: author
Chosen: four, on the seed, which is where the bound lives and where its two
follow-ups inherit it from.
Reason: the same finding as D58 and found the same way. D50's coverage report
flagged `venue_lookup_sintra_lunch__dir2_lisbon_day` using three of three
searches — a bound sitting exactly on observed behaviour, so a correct agent
that searched once more would fail the case. That is a false regression, which
D30 ranks as the worse of the two constraint errors.
Raised on the seed rather than the follow-up alone, as D58 was: the DIR-2
perturbation changes the day and should not also carry a different tool budget.
All three of the family now cap at four.
Worth noting the instrument did its job twice now without being asked to: the
"bounds this run sat exactly at" line exists to surface a cap before a run
depends on it, and both times it has named the case before the case failed.
Affects: cases/venue_lookup_sintra_lunch.yaml and its two regenerated
follow-ups
Reverses: none

### D74 — Every case carries a version, derived from its contents
Date: 2026-09-23 · Decided by: author
Options: a declared `version` field in each case file · a content hash · leave
`suite_version` to cover it
Chosen: a content hash, 12 hex of SHA-256 over the case file
(`cases.case_version`).
Reason: the author noticed while reviewing that cases need a version
identifier, which is the missing half of a problem already recorded. A review
mark says `{by, on}` — who approved and when, but not WHICH TEXT — and every
marked seed has been edited since it was marked: D48 added `places_near` to
both venue seeds, D55 moved the fixture calendar under every dated check, D58
raised a cap, D72 inverted the drinks assertion. Eight of eleven marks attest
to a version that no longer exists, and `review_status` could only report them
`unverifiable`.
`suite_version` does not solve it: it hashes the whole case set, so it answers
"did the suite change" and cannot answer "did THIS case change". Two executions
of one case id either side of an edit are not executions of the same test, and
nothing in the record said so.
**Derived rather than declared**, for a reason this repository has already
demonstrated: a hand-maintained version is a number nobody bumps. The two
`package.json` versions sat at their scaffold defaults for 377 commits (D63).
A content hash cannot drift from the thing it names, and needs no discipline.
Two consumers:
- `study_case_executions.case_version` — an execution now says which version
  of the case produced it. Null before today and **not backfilled**: the hash
  of the file as it stands is not the hash of what those runs executed, and
  writing it would assert something false.
- `cases.mark_reviewed()` — writes a mark carrying the version. It exists so
  that a mark made from now on binds to text, and the next edit shows as drift
  instead of passing unnoticed. **The author calls it; the agent never does** —
  `reviewed.json` says the mark is what makes a seed the author's rather than
  the model's (§3.1), so an agent writing one forges the provenance the study
  rests on. A test asserts there is no call site in `src/`.
Affects: src/cases.py · src/runner.py ·
supabase/migrations/20260923094500_study_execution_case_version.sql ·
tests/test_tables.py
Reverses: none; completes what D71's review-status reporting could only name

### D73 — Structural checking is simulation-only
Date: 2026-09-23 · Decided by: author
Options: apply the cases' structural checks to participant turns via
shape-matching · apply a transferable subset of them · keep structural checking
to the simulated round
Chosen: keep it separate. Participant conversations are not structurally
checked.
Reason: the checks are written against the fixture trip and the cases match it
closely, so they do not transfer. Measured before the ruling: of the 20 check
keys in use, **10 are fixture-anchored** (`trip_after`, `places_near`,
`slot_scheduled`, `slot_moved`, `slot_days`, `edits`, `draft_reuses_blocks`,
`mutation_changed_keys`, `slot_unscheduled`, `draft_slot_starts_between`'s
day anchors) and `trip_after` appears in **all 29 cases** — so no case could
transfer whole, only a subset, and a subset of a case's constraints is not that
case's claim.
Consequences, recorded because they are easy to discover late:
- `study_suggestions.structural_check_outcome` has no writer and will not get
  one. The event model listed it as harness-written; it is now marked
  superseded there rather than quietly left empty. The column stays — dropping
  a column to tidy a record is how a record stops being append-only.
- `study_verdicts` now has no writer in **either** round. It was kept for the
  participant round under the 2026-09-21 ruling; that use is gone. Left in
  place, empty and documented, for the same reason.
- Table 12's derived label becomes uncomputable, since it crosses
  `structural_check_outcome` with `user_action` and no round produces both.
  Raised as Q27 rather than resolved here — it is a manuscript question.
The simulated round's record is unaffected and is complete: verdict and
findings on every execution, judge score per execution in `study_scores`
(D71), turns, mutations and versions, joined by `src/survey.py`.
Affects: docs/event-model.md · docs/OPEN_QUESTIONS.md (Q27) · src/survey.py
Reverses: the participant-round half of the 2026-09-21 verdict-location ruling

### D72 — The "not a meal" case asserts the absence, not the presence
Date: 2026-09-23 · Decided by: author
Options: keep `places_named_types: ['bar']` and report the failures as an agent
regression · widen the accepted types · drop the structural type claim and let
the judge own it · assert the NEGATION instead
Chosen: assert the negation. `places_excluded_types: ['seafood_restaurant']`.
Reason: the case detected in both runs it was checked against, so the question
was whether the agent had regressed or the check was wrong. The evidence says
the check:
- the agent **searched for a bar every time** — `bar by the river…`, then
  `bar river view…` and `waterfront bar…`. Its understanding of the request was
  never in doubt;
- what changed was what Google returned for those searches. `placeType` is
  Google's `primaryType` verbatim, and the same riverside spots came back
  `cocktail_bar` on three runs and `restaurant` on two. Javá, one of the
  "failures", is literally a rooftop restaurant **and bar**;
- the judge scored those executions 9 and 10 out of 10.
So the assertion was measuring Google's taxonomy rather than the agent, and
failing a correct answer — a false regression, which D30 calls the worse error.
This is the third instance of that pattern after `cafe`/`pastry_shop` and
`bar`/`barbecue_restaurant`.
Widening the accepted list was rejected because `restaurant` is exactly what
the seed returns, so the check would no longer discriminate the follow-up from
its base at all. Dropping the claim was rejected because DIR-4 is one of the
few relations with a checkable delta and the delta is real — it is just the
other way round. The seafood seed names a `seafood_*` venue in **10 of 13**
recorded executions; the "not a meal" follow-up in **0 of 5**. The absence is
the stable fact.
**A second defect surfaced while implementing it.** `_same_place_type` matches
loosely in both directions, which is right for "must name a restaurant" (a
`seafood_restaurant` satisfies it) and wrong for exclusion — it made "no
seafood restaurants" exclude every plain `restaurant`, so the new check fired
on exactly the answers it was written to accept. Exclusion is now directional
(`_is_kind_of`): the observed type must carry everything the excluded kind
names. Both previously-detecting runs are now 29/29 clean.
Stated limit: `primaryType` is one string and Google types some seafood places
plain `restaurant`, which is why the seed is 10 of 13 and not 13. A regressed
agent whose seafood venues were all typed `restaurant` would slip through. It
fails **open** rather than closed, which is the direction D30 asks for.
Affects: src/cases.py (`places_excluded_types`) · src/checker.py (`_is_kind_of`)
· cases/derivations.py · the regenerated case · tests/test_tables.py
Reverses: the `places_named_types` half of D42's treatment of this case

### D71 — The second review's findings, and judge scores get a table
Date: 2026-09-23 · Decided by: author (commissioned the re-review, directed the fixes)
The reviewer was asked to check the D69/D70 remediation rather than re-derive
the picture. Verdict: **converging, not converged** — eight of ten prior
findings genuinely fixed, but two of the fixes were wrong in instructive ways.

**The resume fix traded a lossy resume for a FATAL one (N1).** Withholding a
repetition was correct; re-executing it at `attempt=1` was not. Every attempt
is a row, `(run_id, case_id, repetition, attempt)` is unique, and a postgrest
violation *raises* — so it escaped `execute_case` as neither `SimulatorFailed`
nor `RunAborted` and would have killed a resumed run outright, leaving the run
row unfinalised. A two-hour baseline dying at ninety minutes could not have
been continued at all. Attempt numbering now continues from what the record
already holds (`attempts_used`), and the same off-by-one is fixed in the
simulator handler (N2), which restarted its own counter at 1.
This was reported to the author as working, on the strength of checking the
decision function and not the write. The lesson is narrow and worth keeping:
verifying which rows a function *selects* says nothing about whether the next
write *lands*.

**The recovery fix had landed on dead code (N3).** D69 claimed a recovered
repetition "contributed nothing to the run's cost, latency or token counts".
False — `totals` is write-only and the run row is summed from a database
re-read, both before and after. The fix was a no-op and its test was a
tautology (`assert ... or True`). What recovery actually skipped was the
**failure policy**: a repetition that recovered from a simulator refusal and
then returned 429 sailed straight past the rule that says our own quota stops
the run. The policy is now one function, `settle()`, that both paths call.

**A threshold was set without escalating it (N4).** `JOINT_LIMIT = 3` credited
a tool required by *three* cases as a sole route — delete one and it is still
covered twice. Six cases were credited with coverage they do not carry. Now 2,
which is the rule D69 describes. Recorded here because CLAUDE.md's
stop-and-ask list covers thresholds and this one was not escalated when set.

**D70's drift detector fired on D70 (N5).** `failures.report()` flags an
agent-blamed failure where no tokens moved as a suspect classification — which
is exactly what a correct deadline failure looks like, by D70's own evidence.
Deadline failures are now excluded from that warning.

**D70's logging repair covered one of three sites (N7).** The main invoke catch
had already computed `failureKind` and did not pass it, so a capacity error
thrown raw out of `generateContentAsync` still landed as `other` — the precise
defect D70 claimed to have fixed, surviving at the sibling call.

**Judge scores now have a table.** `study_scores`, shaped after
`study_verdicts`: keyed by (execution, judge model, prompt version),
append-only, `score` nullable with an `error` explaining why, and a check that
one of the two is present. Until now `score_run` returned an in-memory object
and 160 scores would have existed only in a notebook output cell — a lost
kernel costing a full judge pass, and no way to join a score to the structural
verdict for the same execution without re-judging. The structural side has had
its table since the beginning; this was an asymmetry rather than a decision.

**Both write paths were then exercised live** against a throwaway run, which is
the assurance the payload-keys check could not give: `record_simulator_failure`
writes its rows, `study_scores` accepts a scored row and an unscored one, two
judge versions coexist, the unique index **does** reject a repeated attempt
(confirming N1 was real), and the cascade cleans up. Nothing was left behind.
Also fixed: the printed legend still described 504 as retried (contradicting
D70 in the artefact a reader sees), a dead `is_platform_refusal`, an unread
binding in `scoring`, and a constant comment describing the wrong tuple.
`run()` now has 15 tests including four that do not stub the resume logic —
stubbing it is why N1 survived the first review.
Affects: src/runner.py · src/scoring.py · src/failures.py · src/tables.py ·
tests/test_runner_loop.py · apps/api/src/routes/ai/agent/agent.service.ts ·
supabase/migrations/20260923071500_study_scores.sql
Reverses: the resume half of D69; corrects D69's finding-2 claim outright

### D70 — Where a 504 came from decides what it means
Date: 2026-09-22 · Decided by: author
Options: retry every 504 as a platform refusal (D59's position) · fail every
504 · split it by origin
Chosen: **split it by origin.** The number is the same and the fault is not.
- **`agent returned 504` is OUR OWN 85-second turn deadline, and is a
  FAILURE.** Not retried. The author's reasoning, which is the product's
  rather than the harness's: 85 seconds is a very long time, a member who
  waited it has been failed, and an agent that starts doing it has regressed —
  something on our side could destabilise the platform. Retrying it would score
  only the surviving attempt and leave the pass rate flat through exactly the
  regression §3.1 claims the pipeline catches.
- **`simulator: … 504` is Vertex's deadline on the HARNESS's own call, and is
  retried.** The simulator is not the system under test; we want the execution,
  not a measurement of the simulator. The same goes for a 429 or 503 reaching
  it — those are the provider's, not our quota.
- **503 stays a platform refusal on both sides**: the provider being busy is
  nobody's regression.
**And the judge is retried where the agent never is** (up to three attempts, on
transient refusals only). Same principle from the other side: the agent is the
system under test, so its failure is a *result*; the judge is an instrument, so
its refusal is a *missing measurement*. Two runs lost five scores to judge
429s, including the two lowest in the suite, and an unscored execution is worse
than a slowly-scored one. A malformed rubric or an out-of-range score is a real
fault and is not retried.
Evidence this was ruled on: across 229 recorded turns the median completed in
5.0s, p95 in 26.9s, and the slowest success took 70.0s — 15 seconds of headroom
under the deadline. Exactly two turns hit it, both with **zero tokens in and
out**, i.e. the provider never answered; D60's 25-second backoff cap addresses
that cause directly. So the new policy costs nothing on the record to date and
starts counting the thing it is meant to count.
Supersedes D59's inclusion of 504 in `PLATFORM_REFUSAL_STATUSES`; the rest of
D59 (platform retried, our own quota fatal, agent failures never retried)
stands.
**The record has to be able to tell them apart, and at turn level it could
not.** Asked whether the logs distinguish "the platform refused" from "the
agent took too long", the answer was yes at execution level (the `error` string
carries the status, and `failure_class` turns it into a blame column) and **no
at turn level**. `study_suggestions.error_code` has a `timeout` value that had
never once been recorded, because `classifyTurnError` reads an error's MESSAGE
and D59's split throws prose written for a member — "Agent took too long…",
"Tonic is overloaded…" — which matches none of its patterns. Three of the five
failure shapes were landing as `other`. A logging regression introduced by D59
and caught only by asking the question.
Fixed by passing the kind rather than re-deriving it: `StudyTurnFailure` takes
an optional `errorCode`, and the empty-reply branch supplies it from the
`emptyKind` it has already computed. The matcher is left alone and a test now
documents why — those strings are prose aimed at a person and will be reworded,
so a logger depending on their wording breaks the next time someone improves a
sentence.
Affects: src/runner.py (`failure_class`, the status tuples) · src/scoring.py
(judge retry) · src/failures.py (deadline failures reported as the latency
regression they are) · tests/test_failure_policy.py ·
apps/api/src/routes/ai/agent/agent.study-log.ts (+ .core.test.ts) ·
apps/api/src/routes/ai/agent/agent.service.ts
Reverses: the 504 half of D59

### D69 — The convergence review's findings, and what was done about them
Date: 2026-09-22 · Decided by: author (commissioned the review, directed the fixes)
An independent reviewer was asked one question — is this converging? — with
read-only access and instructions to report rather than change. Verdict:
**converging, with reservations**; the design has settled and the instrument
had not. Its central finding was that the weakness was concentrated in one
file, `src/runner.py`, and that it was the one file with no tests. That was
correct. Everything below was fixed in one pass.

**Two real defects in the retry loop, both mine, both from D67.**
1. The simulator loss path inferred recovery from `simulator_failures`, a
   counter any success resets to zero — so a repetition lost outright *after a
   passing one* was treated as recovered: no final row, no `platform_losses`,
   no abort counter, and the run carried on as if nothing had been lost. The
   behaviour depended on whether the PREVIOUS repetition had passed, which
   cannot be intended. Recovery is now an explicit flag.
2. Recovery used `continue`, which skipped the totals, so a repetition that
   succeeded on attempt 2 contributed nothing to the run's cost, latency or
   token counts. It now falls through.

**Resume was lossy.** `executions_done()` treated any row as "done", and since
D53/D67 every refused attempt writes one — so resuming a killed run
permanently skipped any repetition holding only refusals. It now requires a
result: completed, agent-failed, or attempts exhausted.

**Three more readers counted superseded attempts** — `observed_coverage`,
`bounds_at_their_cap` and `latency_profile`. A refused attempt carries partial
tool calls, so it inflated call counts and could manufacture a "bound sat at
its cap" finding. D53's reading rule now has ONE implementation
(`execution.latest_attempts`) that four readers share; keeping copies is how
they came to disagree. That makes **six** places this rule had to reach, which
is the real lesson: a new dimension on an identity is not done when the column
exists, it is done when every reader and writer has been walked, and the way to
make that true is to have one implementation rather than to walk carefully.

**A harness fault was blamed on the agent.** A malformed persona returned
`agent` from `failure_class` and printed under "the agent genuinely failed to
answer". It is now `harness` — the agent never saw the turn.

**The admission rule missed a joint route.** `unique_contribution` recognised
only a single sole owner, so the two forecast seeds — which jointly require
`get_weather` and are the only cases that do — reported as contributing
nothing, while the notebook two cells away said they existed to reach a tool
nothing else could. That is D66's disjunction error one level up, at the case
level, and it is the same fix: a case is admitted when nothing else would
reach the thing without it, whether alone or with a named few.

**A 504 is our own deadline and is retried as the platform's.** Kept, because
the usual cause is capacity the agent waited on — but an agent that regressed
into being slow would have every such turn retried and only the survivor
scored, so the pass rate would never show it. The count now gets its own line
that says exactly that. If the author prefers, moving 504 out of
`PLATFORM_REFUSAL_STATUSES` makes it fail instead; that changes what counts as
a pass and stays the author's.

**Three seeds carry no author review mark** (`factual_qa_lisbon_surf_conditions`
and the two forecast seeds — the ones the agent added under D51 and D54).
`reviewed.json` says the mark "is what makes a seed the author's rather than
the model's (§3.1)" and that an agent never writes one, so none was written.
`review_status()` now reports it, a run warns at the start, and a test pins the
current state so adopting them is a deliberate act. The same function exposes a
second thing the file could not say: a mark records `{by, on}`, not WHICH text
was read, and every marked seed has been edited since (D48, D55, D58). Old
marks are reported `unverifiable` rather than verified; new marks may carry a
content hash.

**Overstatements the reviewer named, all corrected.** The plan's bolded "the
suite found a defect in the artifact under study, which is the claim §3.1 makes
for it" — the coverage *instrument* found it and no case failed, which is a
weaker and different mechanism. D68's "no gaps at all" — true of tool-level
coverage and nothing else, and silent on parameter coverage and on the eight of
eighteen follow-ups with no structural delta. The INV-2 mechanism, falsified by
D61 and corrected only in `derivations.py`, still stood in the plan and the
notebook. D60 changed request handling without the rule-4 label its two
predecessors carry.

**One finding rejected.** The reviewer read `scheduling_move_tram`'s route
assertion as contradicting D68, and the agent relayed that. The author
corrected both: a route may be asserted when it is **load-bearing for a
well-grounded answer** — a plan naming places must have searched for them, and
`move_slot` is a different edit from unschedule-then-schedule even where the
end state matches — and not when two routes reach an equally good answer, as
with either climate tool for "will it rain". D68 now states that distinction
instead of implying a blanket ban.

`run()` now has ten tests covering every retry, loss, abort and recovery path
(`tests/test_runner_loop.py`). 238 tests total.
Affects: src/runner.py · src/execution.py · src/coverage.py · src/failures.py ·
src/scoring.py · src/cases.py · src/tables.py · tests/test_runner_loop.py (new)
· tests/test_failure_policy.py · tests/test_tables.py · docs · the expansion
notebook
Reverses: none; completes D53/D59/D67 and scopes D68

### D68 — A disjunction is coverage of a capability, not a gap in coverage of a tool
Date: 2026-09-22 · Decided by: author (overruling the agent's recommendation)
Options: tighten a case to require `get_region_climate` · add a seed for it ·
leave the cases alone and fix the report
Chosen: the third. No case changes.
Reason: D66 found that no case requires `get_region_climate`, and the agent
recommended tightening the November seed to pin it. The author rejected that,
correctly, on three grounds. **Both tools produce a correct answer**, so
requiring one asserts the ROUTE rather than the outcome — which is what D30
forbids, and an agent that picked the other would be failed for nothing. **The
fallback is legitimate and will be exercised**: the prompt's own rule is to use
`get_climate_normals` when there are coordinates but no usable place name, so
pinning the seed would pre-emptively forbid a path a future case needs. And
**`get_climate_normals` is already required outright** by the surf case, so the
climate capability is asserted somewhere regardless.
The defect was therefore in the report, not in the cases. It collapsed three
states into two — required outright, required as one of a group, permitted only
— and filed the middle one under the last, with the line "the suite would not
notice it vanishing". That is false for a disjunction member: if it vanished the
agent would use the alternative and answer correctly, which is not a regression.
`Coverage.groups` now carries the disjunctions and the report states them as
coverage. After the fix the suite has **eight tools required outright, one
covered as a group, and **no TOOL coverage gaps**.

Scope, stated because the short form invites over-reading: this is tool-level
declared/required coverage and nothing more. It says nothing about parameter
coverage (`move_slot` has only ever been observed with day, start and end
together, which `observed_coverage`'s own docstring calls out as exactly the
gap it exists to expose) and nothing about the eight of eighteen follow-ups
that carry no structural delta.

**What this does NOT say: that asserting a tool route is always wrong.** The
rule is that a route may be asserted when the route is *load-bearing for a
well-grounded answer*, and not when two routes reach an equally valid one. A
plan that names places must search for them first — an unsearched plan is
invented, so `search_places` before `propose_plan` is a claim about the answer,
not about the implementation. `scheduling_move_tram` requiring `move_slot`
rather than unschedule-then-schedule is the same kind of claim: the end state
matches but the edit does not, and the intermediate state differs. By contrast
"how rainy will it be, should I bring an umbrella" is answered equally well by
either climate tool, so pinning one asserts nothing about the answer. That
distinction, not a blanket ban, is the principle.
The governing principle the author stated, and which this encodes: the suite
should be **easy to expand and only as strict as needed**. A constraint tighter
than what catches a real regression costs false failures and makes every future
case harder to write.
Affects: src/coverage.py · tests/test_tables.py
Reverses: nothing in D66's measurement; overrules its recommended remedy.
Resolves: Q26

### D67 — A refused simulator attempt is a row, not just a log line
Date: 2026-09-22 · Decided by: agent (completes D53/D59 on the path that missed them)
D53 keeps every attempt because the refusal is evidence about the platform and
the completed one is evidence about the agent. The **agent** path did that: each
attempt writes its own execution row. The **simulator** path did not — the
refusal is raised before any row exists, so a repetition the simulator lost and
then recovered kept only the successful row, and the refusal survived in
`runs/harness.log` and nowhere countable.
Seen live, in the run this was found during: `advisory_packing_list__inv1_paraphrase`
was refused with a 504, retried, and completed on attempt 2 — one row, attempt
2, no trace of the refusal in the table. The platform-failure rate would have
read that repetition as clean, which is precisely the number D59 exists to keep
honest.
Every refused attempt now writes a row with its own `attempt` and an empty
`suggestion_ids` — empty because nothing reached the agent, which is what
distinguishes it from an execution the agent failed.
This is the fourth reader or writer to miss the attempt rule (after scoring,
the checker and the structural table). The pattern worth naming: adding a
dimension to an identity is not done when the column exists, it is done when
every path that writes or reads that identity has been walked.
Affects: src/runner.py (`record_simulator_failure`)
Reverses: none (completes D53 and D59)

### D66 — `tools_any_of` is a disjunction, and the coverage metric now reads it as one
Date: 2026-09-22 · Decided by: agent (a defect in the instrument, found while documenting it)
`tools_required_by` counted every member of a `tools_any_of` as required. It is
a disjunction — the case passes if **any one** of the named tools ran — so a
two-element `any_of` requires neither of them individually.
Consequence, measured: the report claimed three cases required
`get_region_climate`. None does. If that tool broke tomorrow, all three weather
cases would still pass by falling back to `get_climate_normals`, and the
coverage report would have gone on saying the tool was required by three cases.
This is the same overstatement D52 was about, sitting in the instrument that
decides whether a case may be added — the worst place for one, because it makes
the suite look more covered exactly where it is deciding it needs no more
coverage.
Fixed: a one-element `any_of` is a requirement (nothing else can satisfy it); a
longer one is reported separately by `tools_alternatively_required_by`, so
neither reading is lost. `get_climate_normals` correspondingly drops from four
requirers to one, which **confirms** D51's claim that the surf case is its only
unconditional route rather than weakening it.
**Left open, and deliberately not fixed here:** no case now requires
`get_region_climate`. Closing it means tightening an existing weather case to
name that tool specifically rather than adding a case — which is the cheaper
option and the one the admission rule prefers — but it changes what counts as a
pass, so it is the author's. Recorded in OPEN_QUESTIONS.
Affects: src/coverage.py · src/tables.py (`unique_contribution`) ·
tests/test_tables.py · notebooks/sim/02_expand.ipynb
Reverses: none (corrects D50's metric, not its ruling)

### D65 — The attempt is part of an execution's identity, everywhere that reads one
Date: 2026-09-22 · Decided by: agent (a defect in D53's own rule, not a new choice)
D53 added `attempt` and stated that a reader takes the highest per repetition.
Three readers did not, because they predated it and `(case_id, repetition)` had
identified a row for the whole project until then:
  - `scoring.score_run` scored BOTH attempts (fixed with D59's commit),
  - `checker.check_run` memoised executions by `(case, repetition)`, so the
    second attempt was served the first one's execution out of the cache — a
    repetition the provider refused and that then SUCCEEDED was reported as
    still failing, carrying the refusal's findings,
  - `tables.structural` indexed by `(case, repetition)` and drew two
    identical-looking rows for one repetition.
The checker one was the serious one: it is a false regression of the kind D30
calls the worse error, and it was invisible because the wrong verdict looked
exactly like a real failure. Found by drawing the table, which is the argument
for drawing tables.
Fixed by keying the memo on the attempt and looking a SEED up by its highest
attempt — comparing a follow-up against a seed's refused attempt compares it to
nothing. Both now under test.
Affects: src/checker.py · src/tables.py · tests/test_tables.py
Reverses: none (completes D53)

### D64 — Every report exists as text and as a frame
Date: 2026-09-22 · Decided by: agent (presentation; reversible by editing a file)
Options: keep the fixed-width text everywhere · replace it with DataFrames ·
build both from one source
Chosen: both, from one source. `src/tables.py` returns DataFrames for the
relation coverage, the eligibility grid, the tool coverage, the failure
diagnosis, a judge pass and the case set; the existing `report()` functions
still return text.
Reason: the two audiences want different things and neither can use the
other's. A run's log has to survive a terminal, a redirected file and a reader
with no Python, so it stays text. A notebook is published alongside the thesis,
and there a fixed-width block cannot be sorted, filtered or styled and renders
as an escaped string — the worst of both. The frames are built from the same
functions as the text, and a test asserts they agree, so the notebook and the
run log cannot come to make different claims about one suite.
pandas is imported inside each function: the runner must not acquire a
dependency because a notebook wanted a nicer table.
The eligibility grid is the one that earns its place. As a list per function it
answered "what may this function take"; as a grid it answers the question a
reader actually has — *why does this relation have so few cases* — because the
blanks under `advisory` and `factual_qa` for DIR-2/3/4 are the whole defence of
the uneven distribution, visible at a glance.
Affects: src/tables.py (new) · tests/test_tables.py · notebooks/sim/02_expand.ipynb
Reverses: none

### D63 — Both apps carry a real version, bumped automatically, and the API's is read from the running process
Date: 2026-09-22 · Decided by: author
Options: log the package.json versions as they stand · derive a version from
git · log the commit only and drop the idea · adopt real versions and force a
bump on every commit
Chosen: the last. Both apps start at **0.1.0** and `.githooks/pre-commit` bumps
the patch number of whichever app the commit touches. The run row records
`api_version`, `api_commit` and `app_version`.
Reason: asked for a version number, the honest first answer was that there
wasn't one. `apps/api` sat at `1.0.0` (the `npm init` default) and `apps/web` at
`0.0.1` (the template's), each touched exactly once in 377 commits, with zero
git tags. Logging those would have recorded a **constant that looks like a
version** — strictly worse than logging nothing, because a reader of the run
table would reasonably conclude two runs with `api_version = 1.0.0` exercised
the same API. Deriving from `git describe` was rejected as it would just be the
commit again until tags exist; a bump per commit costs no discipline and gives
each app a monotonic counter. It is scoped to the app the commit touched,
because bumping the web app for an API-only change would make the number noise
again.
**`api_version` and `api_commit` are read from the running API's `/health`, not
from the repository, and that is the point of the field.** A full 27-case suite
was once measured against a stale dev server: the code on disk carried the fix
under test, the process on port 3001 predated it, and the run row's `git_sha`
pointed confidently at the new commit. The record could not have revealed it,
because every version in it was read from the same working tree that was
already known to be right. The harness now warns when `api_commit` and
`git_sha` disagree — a warning and not an abort, since running against a
deployed build is legitimate and only the operator knows which was meant.
`app_version` is read from the repository, since the harness never calls the web
app and there is no process to ask.
Older runs stay NULL rather than being backfilled with a number that was never
true.
Affects: apps/api/src/lib/build-info.ts (new) · apps/api/src/app.ts (/health) ·
apps/api/package.json · apps/web/package.json · .githooks/pre-commit ·
supabase/migrations/20260922164500_study_run_app_versions.sql · src/runner.py
Reverses: none

### D62 — suite_version hashes the fixture as resolved, not as stored
Date: 2026-09-22 · Decided by: author
Options: keep hashing the file and document the caveat · hash the resolved
fixture · add the resolved dates as a separate run field
Chosen: hash the resolved fixture.
Reason: a consequence of D55 that the pin itself did not chase. `suite_version`
hashes `cases/fixture.json`, but since the pin that file holds a **template**
and the trip actually built is it placed on the next upcoming November. So two
runs a year apart would have carried the same suite version while running
against different calendars — precisely the case the hash exists to
distinguish, and the one its own docstring promised to catch ("the same case
text against a different starting trip is a different test"). A field that
asserts something it no longer guarantees is worse than one that asserts less.
The near-dated case (D54) is deliberately excluded: its trip is resolved
relative to the run, so folding it in would move the suite version every day and
make two runs in the same week incomparable for no gain. The hash therefore
identifies the fixed calendar that every other case shares, and that one case's
calendar is recoverable from its own trip row. Tested both ways — the version
moves across the pin boundary and is stable within it.
Affects: src/cases.py (`suite_version`) · src/calendar_pin.py (tolerates a
partial fixture, so hashing a stub cannot crash) · tests/test_calendar_pin.py
Reverses: none (completes D55)

### D61 — Every relation is instantiated, and the uneven distribution is defended by its denominator
Date: 2026-09-22 · Decided by: author
Options: leave INV-2 uninstantiated and say typos are weak · remove INV-2 from
D22's catalogue · instantiate it once, on the seed where it can actually fail
Chosen: instantiate it once, on `venue_lookup_seafood_lisbon`.
Reason: the author noticed INV-2 had **zero** cases while D22's catalogue names
eight relations. Nothing failed, because nothing checked the catalogue against
itself — and a coverage argument that claims eight relations while exercising
seven is the same overstatement D52 was about. Removing it from the catalogue
was the honest alternative, but the relation is not worthless, only
*misplaced*: a typo is weak wherever the text is read by the model alone, which
is what language models are good at. The venue lookup is the closest the suite
gets to a typo reaching a **tool** rather than only the model — the request is
about a named place and the answer is scored on location as well as on taste —
so that is where the case sits.

**Corrected 2026-09-22, same day, by the first run of it.** The justification
above originally claimed the member's words *become* a `search_places` query
argument, so a typo would be handed to the Places API. That is not what
happens: the agent **authors** the query and normalised every typo before the
tool saw anything. The seed searched `marisqueira Cais do Sodre Lisbon`; the
typo follow-up searched the byte-identical string. The case scored 10/10 with
its structural checks passing.
The placement stands and the stated mechanism does not. Recording it this way
is the point of the entry — the relation's weakness is now *measured*, with a
specific cause (query rewriting, not tolerant matching downstream), which also
says where to look if a typo case ever does fail.
If it passes 8/8, that is the finding, and the relation is reported as one the
agent is insensitive to — which is worth more than omitting it and leaving a
reader to wonder whether it was tried.

**On the uneven distribution.** The raw counts (DIR-1 five, DIR-3 one, INV-2/3/4
one each) look arbitrary and were undefended. The denominator is the defence,
and it is now computed rather than asserted (`metamorphic.relation_report()`):

    DIR-1  eligible 9  used 5  56%      INV-1  eligible 11  used 4  36%
    DIR-2  eligible 4  used 3  75%      INV-2  eligible 11  used 1   9%
    DIR-3  eligible 4  used 1  25%      INV-3  eligible 11  used 1   9%
    DIR-4  eligible 4  used 2  50%      INV-4  eligible 11  used 1   9%

Two things follow. First, the unevenness is largely **forced by D22's
eligibility matrix, not chosen**: DIR-2/3/4 are eligible on four seeds rather
than eleven, because "change the day" and "change the count" are not
perturbations of *what happened in the 1755 earthquake*. Equal raw counts would
require applying relations where they are nonsense. Second, where there was a
choice, **directional relations were preferred** — 25–75% of opportunity against
9–36% for invariance — and deliberately: a directional relation asserts a
*changed* outcome and can fail in a specific, checkable way, while an invariance
relation asserts sameness, which is what an LLM is most robust to. A suite
weighted toward invariance would report its own insensitivity as coverage.

**The residual limitation is stated, not dressed up.** INV-2, INV-3 and INV-4
sit at one case each. That is a floor chosen to keep the catalogue instantiated,
not a sample, and nothing statistical may be claimed per-relation for them. The
report prints that warning itself, so the limitation travels with the evidence
rather than living only in prose. §3.7 should carry it.
Affects: cases/derivations.py (`SEAFOOD_TYPOS`) · the generated case ·
src/metamorphic.py (`relation_coverage`, `relation_report`) ·
tests/test_metamorphic.py (a relation with no case now fails the suite)
Reverses: extends D21's budget again, as D50 and D51 already did

### D60 — The capacity retry gets a clock budget, and latency is read per population
Date: 2026-09-22 · Decided by: author
Options (retry): cap the total backoff, keep six attempts · cut attempts to
three and let the harness do the waiting · leave it and fix only the reporting
Chosen: **cap the total backoff at 25s** (`CAPACITY_TOTAL_BUDGET_MS`), attempts
unchanged at six.
Reason: D59 asked whether our own retry is a stability problem, and measurement
said yes — but inside the API, not in the harness. Across 194 recorded turns,
11.3% hit at least one internal retry; of those, 15 recovered and 7 did not, and
the median latency was 13.0s against 4.5s for a clean turn. The attempt cap
never bounded the clock: one call can wait 1+2+4+8+16s and a grounded turn makes
several calls, so waiting could consume the whole 85s deadline and leave nothing
to answer with. Two turns did exactly that.
The inner retry also had the worse deal of the two. It must fit inside the
deadline, so it gives up mid-backoff and forfeits the turn, while the harness
retry starts with a fresh 85s. We were waiting twice for the same queue and the
inner wait was the destructive one.
25s keeps roughly a minute of working time and — the point that decided it over
cutting attempts — means a turn that gives up gives up **while it can still say
so**: the member gets the 503 "overloaded, wait about a minute" with a retry
hint instead of a deadline timeout that reads as their request being too hard.
Cutting attempts to three was rejected because real users have no outer retry;
six quick 429s should still be ridden out, and it is the clock that needed
bounding, not the persistence.
Options (latency): report clean and retried separately · add a `wait_ms` field ·
stop using latency as a signal
Chosen: **report both, compare on clean turns.** No new logged field:
`retry_count` already separates the populations, it simply was not being read,
and adding a field would touch the event model the manuscript's Table 11
describes. `failures.latency_profile()` prints both medians and the queued share
at the end of every run, and warns when more than a quarter of turns queued —
at which point a latency comparison against another run is measuring the
provider, not the agent.
**Rule-4 note, added after review.** This changes how the application handles a
request and was not labelled as such, unlike D56 and D57 which both carry the
disclosure. An overloaded turn now returns a 503 with a retry hint where it
previously ran to the deadline and returned a 504 — the member sees a different
message. Same standing as its two predecessors: taken knowingly, before any
baseline exists, so no recorded run is invalidated, and not to be repeated once
the baseline is fixed.
Affects: apps/api/src/routes/ai/lib/adk-llm.ts (+ tests) · src/failures.py ·
src/runner.py
Reverses: none (bounds D43, which set the attempt policy)

### D59 — Retry the platform, never our own limit, and say which is which
Date: 2026-09-22 · Decided by: author
Options: keep D53's single retry · retry any failure until it passes · retry
platform refusals several times, fail our own limits outright
Chosen: the third. `MAX_ATTEMPTS_PER_REPETITION` goes from 2 to **4**, and only
for a failure the **platform** caused. Our own rate limit or monthly quota (429,
`rate_limited_by_us`) is never retried and **aborts the run**. A genuine agent
failure (502) is never retried at all — it is a result.
Reason: a baseline needs every planned execution, and one spare attempt was not
enough — a 27-case run still lost executions. Retrying everything was rejected
for the reason D53 already gives: it would launder a real agent failure into a
pass. Our own limit is the third case and behaves differently from both — it is
a statement about this harness's configuration, every later execution would hit
the same wall, and retrying is *what causes* being rate limited. Failing loudly,
naming the tier and the file to look in, is cheaper than a run that spends an
hour producing refusals.
The simulator is retried on the same terms: it runs on the same provider and
meets the same queue, and a member turn lost to a 504 there costs the whole
repetition while saying nothing about the agent.
**This ruling only became possible because the classification was fixed first.**
Two executions in the last run were recorded as `agent returned 502` and were in
fact turns killed by our own 85-second deadline: zero tokens in, zero out, two
internal retries, 85_007ms and 85_015ms against an 85_000ms budget. ADK returns
an aborted run as an empty event stream rather than as an error, so the
empty-reply branch had been collecting three different failures — our deadline,
a provider that never answered, and the agent genuinely having nothing to say —
and reporting all three as the agent's fault. They now separate into 504, 503
and 502 respectively, which is what a retry policy keyed on status can act on.
`src/failures.py` reads the same evidence at the end of every run and prints who
is to blame per failed execution, with the turn's error code, retry count,
latency against the deadline and token movement. It flags an execution blamed on
the agent where no model call completed — the exact pattern above — so the next
drift is caught by the run rather than by someone thinking to look.
Affects: apps/api/src/routes/ai/agent/agent.service.ts (empty-reply split,
richer failure log) · src/runner.py · src/failures.py (new) ·
tests/test_failure_policy.py
Reverses: supersedes D53's single attempt; D53's rule that both attempts stay in
the record, and that the pass rate takes the highest, is unchanged

### D58 — The Belem search_places cap goes to four
Date: 2026-09-22 · Decided by: author
Options: leave it at three · raise the seed's cap to four · raise only the
follow-up's
Chosen: four, on the seed, which is where the bound lives.
Reason: D50's coverage report flagged it — `scheduling_belem_morning__dir2_on_the_9th`
used exactly three of three, so a correct agent that searched once more would
have failed the case. That is a false regression, which D30 rules the worse of
the two constraint errors, and a bound sitting exactly on observed behaviour is
one run away from producing one.
Raised on the seed rather than on the follow-up alone: DIR-2 changes the day and
nothing else, and a perturbation that also carries a different tool budget stops
being a clean directional claim. `__dir3_a_full_day` keeps its own cap of seven,
which it declares for its own reason (a full day is more searching than a
morning). Instrument working as intended: the report exists to surface a bound
with no headroom before a run depends on it.
Affects: cases/scheduling_belem_morning.yaml · the regenerated
cases/scheduling_belem_morning__dir2_on_the_9th.yaml
Reverses: none

### D57 — Tonic is told what day it is
Date: 2026-09-22 · Decided by: author (found while verifying D56)
Options: leave it and word the weather cases around it · pass today's date only
to the weather tools · put today's date in the system prompt
Chosen: the system prompt. Every turn now opens with today's date, spelled out
and in ISO, plus an instruction to resolve relative dates against it and to
distrust a date the member asserts that contradicts it.
Reason: D56's rewrite did not work, and the reason it did not work is that the
agent had no idea what day it was. Nothing dated reached it except the trip, so
"the next couple of days" had only the trip's own November dates to resolve
against — it asked for a forecast seven weeks out, and when the simulated member
pushed back it accepted an invented "today is May 18" at face value and
requested forecasts for 2024 and 2025. Telling it to use TODAY as the reference
is not an instruction it could follow.
This is the more fundamental of the two findings and its reach is wider than
weather: whether a trip is tomorrow or in seven weeks is what decides forecast
versus climate average, whether a date is in the past, and what "this week"
means. The suite found it because a weather case was the first thing that forced
the agent to say which calendar it was answering about.
The conflicting instruction was fixed in the same pass: "will it be rainy" had
been routed to `get_region_climate` unconditionally, so a trip three days out was
answered with September averages. That line is now explicitly about a month or a
season and defers to `get_weather` inside the sixteen-day horizon.
Measured effect, same cases, same day: `factual_qa_lisbon_forecast_next_days`
1/10 → 10/10 in one turn; `factual_qa_lisbon_trip_forecast` 3/10 → 9/10. Across
both, `get_weather` made one call each with **zero** errors — the first
error-free calls of that tool in the record.
**A change to how the application handles a request** (root CLAUDE.md rule 4),
same authorisation and same caveat as D56: taken before any baseline exists, so
no recorded run is invalidated, and not to be repeated once the baseline is
fixed.
Affects: apps/api/src/routes/ai/agent/agent.prompts.ts
Reverses: none (completes D56, which was necessary but not sufficient)

### D56 — get_weather is told which calendar to answer about
Date: 2026-09-22 · Decided by: author
Options: leave the instruction and drop the forecast case as unpassable · widen
the case until the existing behaviour passes · rewrite the instruction so the
member's own wording picks the reference
Chosen: rewrite it. The agent now orders three cases explicitly — near-term
wording ("the next few days", "tomorrow") means TODAY is the reference; a
question about the trip means the trip's dates; no dates set or genuinely
ambiguous means ask before calling. Beyond the sixteen-day horizon it is sent to
`get_region_climate` and told to say those are averages, not a forecast.
Reason: the old line said "use get_weather for upcoming conditions during the
trip dates", full stop. Measured consequence: across 118 recorded executions
every single `get_weather` call returned `Open-Meteo error: 400`, because the
fixture trip sat seven weeks out and a forecast reaches sixteen days. The tool
was exercised constantly and its working path never once — a hole the suite
could see (D51 added the seed for exactly this) but could not fix from the case
side, because no wording of a case changes what the prompt tells the agent to
do. The horizon rule is part of the same fix and not an extra: without it the
far-dated case still routes to a call that cannot succeed.
**This is a change to how the application handles a request** — root CLAUDE.md
rule 4 — taken knowingly and before any baseline exists, so no recorded run is
invalidated. It must not be repeated after the baseline is fixed.
Also changed, in the same spirit: `getWeatherForecast` now refuses an
out-of-horizon date itself, with a message naming the climate tools, instead of
passing Open-Meteo's bare `400` on. A `400` reads as transient and the agent was
retrying the identical call; a tool's error text is the agent's only view of it.
Affects: apps/api/src/routes/ai/agent/agent.prompts.ts ·
apps/api/src/routes/ai/lib/weather.ts (+ tests) · the two weather cases
Reverses: none

### D55 — The fixture trip is pinned to the next upcoming November
Date: 2026-09-22 · Decided by: author
Options: keep the hard-coded 2026 dates · roll the year and keep the day of the
month · roll to the next upcoming November preserving the weekday
Chosen: the weekday. `cases/fixture.json` is a **template**; the trip built is
that shape placed on the next November still ahead of today.
Reason: hard-coded dates make the fixture a past trip from December 2026
onward, and every reply grounded in "your trip next month" would then be about
a trip that already happened — wrong in a way nothing in the suite checks for.
Preserving the weekday rather than the day number is forced by the cases: seven
say "Saturday" or "the Sunday" in the member's own words while their checks name
a date, and the two agree only because 2026-11-07 *is* a Saturday. Rolling the
year and keeping the 6th makes it a Sunday in 2027, and every scheduling case
would then ask for one day and assert another — the suite reporting a
regression that is really a stale fixture. Keeping the weekday costs the day
number instead, which one case names ("put it on the 9th"); that case is
refused **by name at load time** rather than failed at run time, so the day the
pin first moves, the suite says which file to reword.
Case files move with the fixture: the loader shifts every date inside the
template's range by the same delta, so a check, an anchor and the built trip
name the same day. Prose cannot be shifted, which is what the ordinal guard is
for. Verified to 2040: the weekday holds, the trip stays inside November, and
only that one case is ever refused.
Affects: src/calendar_pin.py (new) · src/cases.py · src/fixture.py ·
tests/test_calendar_pin.py
Reverses: none. No-op on the day it was taken — November 2026 is still ahead —
so it changes no run in this study round.

### D54 — One case runs on a near-dated fixture
Date: 2026-09-22 · Decided by: author
Options: one weather case on the fixed calendar · a second fixture file · a
per-case `fixture_dates` variant that moves the same trip
Chosen: the variant. `fixture_dates: near` moves the fixture trip to start three
days from the run; every other case keeps the fixed November calendar.
Reason: a forecast exists only within sixteen days of being asked for, so no
fixed date can test the during-the-trip path and still be inside the window next
month. The two weather cases then cover the two branches D56 created — one asks
about the trip and must be answered from the trip's dates, one asks about the
next few days and must be answered from today — and neither can test that
alone, because what is being checked is which reference the agent picks. Three
days out, not zero, so the two branches stay distinguishable: on a trip starting
today the two questions name the same range and a wrong pick would pass.
A second fixture file was rejected as two trips to keep in step and two sets of
anchors for cases to name; the variant preserves the shape exactly and moves
only the calendar.
**Cost, stated rather than hidden:** that case's trip differs run to run, so its
digest does too and two runs cannot be shown to have started from the same days.
Invariant 1 still holds in the sense that matters — the gate computes expected
and observed from the same function, so it still proves the trip is exactly what
was asked for. It just cannot prove two runs shared a calendar, which for a
forecast is not a property that can exist. Confined to one case by design; the
loader refuses a day anchor on a near-dated case.
Affects: src/cases.py (`fixture_dates`) · src/fixture.py (`for_case`) ·
src/runner.py · src/judge.py (the judge is shown the calendar the case ran on)
Reverses: none

### D53 — A repetition the provider refused is attempted once more
Date: 2026-09-22 · Decided by: author
Options: keep D44 as-is (a refusal is a failure of the case) · retry until it
succeeds · one extra attempt, both kept
Chosen: one extra attempt, and both rows stay in the record. `attempt` starts
at 1; the pass rate reads the highest attempt per repetition, the superseded
rows are the platform-failure rate.
Reason: D44 ruled a lost execution counts as a failure, and measurement then
put a number on that ruling — 3.8% of 133 executions failed on a provider 429
or 504, which under D23's 8/8 is roughly a 27% chance of losing any given seed
per baseline run to something that is not the agent. Two or three seeds of ten
per run, and a published pass rate with the provider's availability inside it.
It is deliberately **not** a general retry. D45 gave capacity its own status, so
the trigger is precise: 503 (provider busy) and 504 (timeout) are re-run, 502 —
the agent failing to produce a reply, or exhausting its reasoning limit — is
not. Retrying that would launder a real failure into a pass.
Both attempts are kept because they are evidence about different things, and
merging them loses the refusal entirely.
Affects: supabase/migrations/20260922075028_study_execution_attempt.sql ·
src/runner.py
Reverses: refines D44 (the failure policy stands; the sampling changes)

### D52 — The negation case names the stop it removes, and coverage stops overstating itself
Date: 2026-09-22 · Decided by: agent, on a third review round
Chosen: three additions, each closing a defect a review found and measurement
confirmed.
**`slot_unscheduled {block}`** — the one case exercising `unschedule_block`
asserted only that *something* came off: an agent that removed the Time Out
Market lunch instead of the tram ride satisfied every check it declared — the
tool ran, one slot fewer, the same number of stops — and the verdict read
`none`. Its sibling names its stop through `slot_scheduled`; the negation had
no counterpart. Read off the `itinerary_slots.DELETE` projection's
`trip_block_id`, which the record already carries. Verified: it passes the
real execution and reports "'Time Out Market lunch' is still on the itinerary;
what came off was ['Tram 28 ride through Alfama']" when the wrong stop is
named.
**Required versus permitted in the coverage report.** Eleven cases named
`get_weather` and all eleven bounded it at `{min: 0}` — a probe the agent may
try and need not — so the report read as though the tool were thoroughly
asserted when no case required it at all. The report now separates the two and
says so: *permitted but never REQUIRED: get_weather*. It also flags a tool
whose every observed call errored, which `get_weather` does, because the
fixture sits beyond the forecast horizon (Q23).
**Two guards against defect classes that have now recurred.** A test that
re-derives every follow-up and compares it to disk — a seed edit failed to
reach its follow-ups twice, and only a notebook re-run happened to fix it. And
a test that refuses harness commentary in `user_profile`: a paste error
appended a paragraph about structural verdicts to a persona, which is what the
simulator reads to stay in character, so it altered what was measured on four
executions and no verdict would have shown it.
Recorded as an agent decision: all three close holes rather than opening
choices, change no threshold and no logging, and are reversible by editing a
file. The one question they raise — whether a case should exercise
`get_weather`'s success path, which this fixture cannot do at all — is the
author's and stays open as Q23.
Affects: src/cases.py, src/checker.py, src/coverage.py, cases/derivations.py,
tests/ · Reverses: none

### D51 — A ninth seed, for the one tool nothing could reach
Date: 2026-09-21 · Decided by: author (asked for directly)
Options: swap the weather seed's DIR-1 from July to a marine question · add a
third follow-up to the weather seed · accept the gap and document it · add a
seed written for the tool
Chosen: `factual_qa_lisbon_surf_conditions`, a ninth seed asking what the waves
and wind are like around Lisbon in November. It carries **no slash command**
deliberately: free text leaves the agent its whole toolset, so reaching the
right tool is the agent's judgement rather than the command's.
Reason: the coverage report showed `get_climate_normals` declared by three
cases and called by none. The cause is not a defect — `get_region_climate`
reads a Wikipedia climate table, the agent is instructed to prefer it when it
has a place name, and Lisbon has one, so the documented fallback never fires.
Zero calls was the primary working. But a fallback nothing exercises is a tool
that can break unnoticed until the day a destination has no table, and a
marine question is the one request only `get_climate_normals` can answer:
wave height and period come from its `include_marine` path and no other tool
in the agent carries them.
The reference is stored as the tool itself returns it
(`references/lisbon_climate_normals_marine.md`, fetched by calling
`getClimateNormals` directly), so the criteria quote real figures — November
1.5 m at a 10.8 s period, wind 17.7 km/h — and a source-faithful answer is
scorable where an invented one is not.
It takes **no follow-ups**, which D21's two-per-seed does not anticipate: a
perturbation of it would buy no tool the suite does not already have, and the
budget is better left unspent.
Affects: cases/factual_qa_lisbon_surf_conditions.yaml, cases/references/,
D21's seed count · Reverses: none

### D50 — The suite is sized by tool coverage, not only by D21's budget
Date: 2026-09-21 · Decided by: author (asked for directly)
Options: keep D21's 8 seeds and 16 follow-ups and document the uncovered tools
· swap weak follow-ups for tool-covering ones at constant size · add the
minimum needed to cover every tool
Chosen: the third, "a few more for the scheduling tasks, but keep it at a
minimum to cover all tools". The suite is now **9 seeds and 17 follow-ups,
140 executions**, against D21's 8 and 16 at 128.
Where the extra cases went and why they could not go anywhere else:
`schedule_block` and `unschedule_block` are exposed **only** by the
`/reschedule` command (`agent.tool-policy.ts`: `/plan` gets `propose_plan` and
no live-edit tool), so both cases that reach them must derive from
`scheduling_move_tram`, which therefore takes three follow-ups. The first
attempt put the schedule case on the planning seed and it could not call the
tool however it was worded — the agent correctly drafted instead, and the
coverage report caught it on the first run.
Also here: an automatic coverage instrument, because the gap had gone unnoticed
for the life of the suite. `tests/test_tool_coverage.py` fails a commit if a
tool is named by no case; `src/coverage.py` reports, per run, which tools were
actually **called** and with which parameters. The two are separate on purpose:
declaring is not covering, which `get_climate_normals` demonstrated by being
declared three times and never reached (D51).
Cost, stated: 140 executions against 128 changes the per-run spend and the
wall clock by about 9%. §3.1's pass-rate resolution is unaffected — n per case
is unchanged at 8 and 4.
Affects: cases/derivations.py, src/coverage.py, tests/test_tool_coverage.py,
REVIEW_CRITERIA.md (22-24), D21's budget, B05, B10 · Reverses: D21's "16
expanded / 128 executions", which was a cost ruling and not a methodological
one

### D49 — Metamorphic relations are asserted as checks, not as predicates
Date: 2026-09-21 · Decided by: agent, on measurement
Options: keep the predicate comparisons · weaken them to tolerate variance ·
drop them and state the delta as a check
Chosen: the third. `implied_predicates()` returns nothing for every relation,
and no case names a predicate. A directional delta is a check override; an
invariance claim is carried by the inherited checks and by the judge.
Reason: measured across four runs of the same seeds, not argued.
`same_tool_sequence_as_base` re-introduced exactly the variance
`ALWAYS_ALLOWED_TOOLS` exists to excuse — `advisory_packing_list` ran
`[get_weather, get_region_climate]` on some runs and `[get_weather]` on others
— and on an advisory case it was a tool constraint by another name, walking
past `Case._coherent`, which refuses to let advisory constrain tools at all
(D29). `same_venues_as_base` was worse: four runs of `venue_lookup_sintra_lunch`
returned three places each and shared **one** across all four, so requiring
equality would fail almost every repetition. And its twin
`different_venues_from_base` fails only on exact set equality, which never
happens, so it passed on noise and verified nothing — while on a scheduling
case it was backwards, since moving a draft to another day does not change
which monuments are in Belém.
What replaces it is **the kind of place, not its identity**: place types are
stable between runs where venues are not (`restaurant` and
`seafood_restaurant` appeared in every run of the seafood seed), and
`places_named_types` states that declaratively, which is where D27 says a
single-execution claim belongs.
Consequence to record rather than hide: the predicate half of the D19/D27
split is now **unused**. `cases/predicates.py` and the `base=` pairing in the
checker are kept because a future relation may need a genuine comparison, but
§3.7 should say that in this instantiation every metamorphic relation turned
out to be expressible as a check or left to the judge.
Recorded as an agent decision: it removes constraints rather than adding them,
changes no threshold and no logging, and is reversible by editing a file.
Affects: src/metamorphic.py, cases/predicates.py (now unused), cases/*.yaml,
B05, B10 · Reverses: the implied predicates written into B05

### D48 — A venue-lookup case says where the answer has to be
Date: 2026-09-21 · Decided by: author (asked for directly, on reading the case)
Chosen: a `places_near {anchor, within_km}` check. Every place the reply names
must sit within the radius of a **fixture stop**, whose coordinates come from
`cases/fixture.json` — not from the case, for the same reason
`slot_moved.block` names a stop rather than an id: the fixture already knows
where its stops are, the loader validates the name, and a case that typed its
own latitude would drift the first time the fixture moved.
Applied to `venue_lookup_sintra_lunch__dir2_lisbon_day` (5 km of the Baixa
hotel), and to **both venue-lookup seeds**, which had the same defect: 8 km of
Pena Palace, 3 km of the Time Out Market — the fixture stop 800 m from the Cais
do Sodre the member names.
Reason: the author read the day-change case and called it weak, correctly. Its
only structural claim was `different_venues_from_base`, which **two different
Sintra restaurants satisfy** — precisely the answer a day change is meant to
rule out. The seeds were no better: "in or near Sintra, not back in Lisbon"
was a scoring criterion and nothing else.
The radius is the member's words as a distance, the way D31 renders "around 4"
as a window. It is deliberately **not** the application's `VENUE_SANITY_KM` of
300, which exists to catch Lisbon-versus-Porto and would pass every answer this
check exists to fail: Pena Palace and Baixa are 23.5 km apart.
Verified both ways against the recorded run. Every real answer passes with
room — 0.9 km against a 3 km radius, 1.5 against 8, 0.3 against 5 — so it
manufactures no false regression. And crossing the anchors detects: the Baixa
answer judged against Pena Palace names all three venues at 23.4-23.6 km, and
the Sintra answer against the hotel at 22.4-23.9 km.
Also here, from the same run: `places_named_types` gained synonym groups.
`lodging` and `hotel` share no characters, so substring matching failed a reply
that had correctly returned a hotel — a false regression the suite authored
itself, found by running it.
Affects: src/cases.py, src/checker.py, src/execution.py, cases/derivations.py,
both venue_lookup seeds, B05 · Reverses: none · Note: adds a key under D37's
rule — found by reading what the record carries (`refs[].location`), added
because a case needed it.

### D47 — Fixture trips are retired by run, keeping the latest and its baseline
Date: 2026-09-21 · Decided by: author (proposed the rule directly)
Options: never delete until submission · keep the latest run and its baseline ·
delete on a time-based retention window
Chosen: the second, as `src/cleanup.py` (B17). Keep the most recent run and any
run a kept run names as its `baseline_ref` — exactly the pair stage 3.2
compares (D23) — and retire every other run's fixture trips. The rule falls out
of the data rather than being a list someone maintains.
Every fixture trip is traceable to its run through
`study_case_executions.trip_id` + `run_id`, which is what makes this possible
at all.
What is lost, stated because it is irreversible: `chat_messages` cascades with
the trip, and it is the only copy of the agent's reply text **and** of the
Google place ids the metamorphic predicates compare. A retired run cannot be
re-judged or re-checked. What survives: `study_case_executions` keeps its
outcome, findings, costs and constraints, and `study_suggestions.trip_id` is
`ON DELETE SET NULL`, so the record of what happened outlives the trip.
Safety: dry run unless `--apply`, and three independent guards — a trip must
belong to a simulated account, carry the fixture name prefix, and not belong to
a kept run. Any trip failing one is skipped and reported.
**Not applied yet.** There is no baseline run, so today the rule would retire
every probe run except the newest, and several decisions (D38, D41, D42) cite
those runs. Storage is not a reason to hurry: two full runs are ~256 trips.
Affects: src/cleanup.py, tests/test_cleanup.py, B17 · Reverses: none

### D46 — The harness is kept out of the product's analytics
Date: 2026-09-21 · Decided by: author (asked for directly)
Chosen: `public.is_simulated_account(uuid)`, and a `NOT` of it in
`analytics_cost_rollup`, `analytics_event_rollup`, `analytics_active_users`
and `analytics_funnel`. An account counts as simulated on either of two
signals, neither of which depends on configuration: a `.invalid` email (RFC
2606 reserves the TLD as permanently undeliverable, so it can never be a
person) or a study session with `run_type = 'simulation'`.
Reason: D15 puts everything in one Supabase project, so the harness's accounts
sit beside real users and every product rollup was counting them. At the point
this was found that was already **297 `api_usage_events` worth $10.89 and 292
`ux_events`** from one fake account, and a baseline plus a regression run would
add ~256 agent turns and ~256 trips more — enough to visibly distort DAU,
cost-per-user and the funnel.
`analytics_agent_reliability` is **deliberately not** filtered: it measures how
often the model provider is busy, and harness turns are evidence for exactly
that question.
Affects: supabase migration 20260921075038, admin dashboard · Reverses: none
Note: the same two signals identify which trips `src/cleanup.py` may delete
(D47), so "is this the harness" has one definition rather than two.

### D45 — A member is told when the model is overloaded, and an admin can count it
Date: 2026-09-21 · Decided by: author (asked for directly)
Chosen: three additive pieces. (1) A capacity failure returns **503** with
"Tonic is overloaded at the moment — this is not your message. Please wait
about a minute and send it again." and `details.retryAfterSeconds`; the web
shows the server's wording for 503 only, since the other failure messages
("Agent reached its reasoning limit") are internal. (2) Every failed agent turn
records `metadata.failureKind` ∈ `capacity | timeout | call_limit |
empty_reply | other` on its `api_usage_events` row — the `status` column is
constrained to `ok|error`, so the reason rides in the metadata and needs no
enum migration. (3) `analytics_agent_reliability` rolls it up per day and an
**Agent reliability** tile on the admin dashboard shows turns, failure rate,
overload rate and the worst day.
Reason: the author's. Overload is not something a member can fix by rewording,
so "please try again" alone reads as blaming them for a queue they cannot see;
and without a number nobody can tell whether a bad week was Google's or ours,
which is the decision that would justify paying for reserved throughput.
The wait is **our estimate and is worded as one** — Vertex sends no
`Retry-After` and the 429 carries no `RetryInfo`, so a precise countdown would
be a fabricated number.
Privacy: the rollup is counts only — no user id, no trip, no message content —
so it stays inside `docs/DECISION_ai_conversation_privacy.md`.
Caught in review: the first migration granted EXECUTE to `authenticated`, which
both failed for the only real caller (the service-key client, 42501) and would
have let any signed-in member call an admin aggregate straight through
PostgREST, where `requireSuperAdmin` is not in the path. Corrected to
`service_role` only, matching every other analytics rollup
(`20260921073500_analytics_agent_reliability_grant_fix`).
Extended the same day, after D43's verification exposed the gap: the panel
counted *failed* turns, so the 429 the new backoff waited out left a
successful turn and the panel read `capacity = 0` on a run that had hit
capacity. `retryCount` now rides on the usage metadata of every agent turn,
successful or not, and the rollup carries `turns_retried`, `retries` and
`retry_rate` with a **Retried** stat beside Overloaded. Retries climb before
anything fails, which is the point at which a capacity decision is still
cheap. Verified end to end: a fresh turn's usage row carries
`"retryCount": 0`.
Affects: agent.service.ts (all three usage log sites), adk-llm.ts,
api-client.ts (new `ApiError` carrying status and details), use-agent-chat.ts,
analytics.{routes,service,schema}.ts, admin-analytics-api.ts,
agent-reliability-tile.tsx, four migrations
Reverses: none · **Rule 4: this changes what a member sees on a failed turn**,
so it is frozen now and both rounds run against this version.

### D44 — An execution lost to provider overload counts as a failure
Date: 2026-09-21 · Decided by: author (escalated by agent as Q24)
Options: count it, reporting how many were capacity · re-run it once and score
the completed attempt · re-run up to twice · exclude it and report an
availability rate separately
Chosen: count it. No re-run policy; a turn that failed is a failed execution,
and C02 reports the capacity share separately from the trace.
Reason: the author's, taking the methodologically strictest option. The agent
recommended a capped re-run to keep the pass rate about the agent rather than
about Google's capacity; the author chose the raw measure, which needs no
retry policy declared in advance and keeps every execution an independent
draw. The consequence is accepted and should be stated in §3.7: under D23's
8/8 seed criterion, a capacity failure anywhere in a seed's eight repetitions
fails that seed, so a published pass rate carries some of the provider's
availability in it. D43 is what makes that acceptable — it should make the
event rare — and D45's rollup is how we will know whether it did.
Affects: B07, B10, B11, C02, §3.7 · Reverses: none · Closes: Q24

### D43 — The agent waits a capacity error out instead of giving up in eight seconds
Date: 2026-09-21 · Decided by: author (escalated by agent after researching the 429)
Options: adopt Google's documented backoff · a milder version capped near 10s ·
leave the application alone and absorb it in the harness
Chosen: Google's, fitted to the turn budget. `MAX_CAPACITY_ATTEMPTS = 6` with
equal-jitter waits of about 1, 2, 4, 8 and 16 seconds (~31s worst case, inside
`CHAT_TIMEOUT_MS` of 85s). A `MALFORMED_FUNCTION_CALL` keeps its short
three-attempt retry: it is sampling noise that usually succeeds immediately,
and waiting sixteen seconds for it would spend the turn budget on nothing.
Reason: **the premise of D39 was wrong, and this entry corrects it.** Newer
Gemini models are served from a *dynamic shared quota* — Google's own guidance
calls the 429 "basically a 'server is too busy' error" — so there is no fixed
per-project ceiling to budget under, and no client-side rate limit can prevent
it. Our own measurements say the same: across four runs, failures did not
track our request rate at all (the run with the highest sustained throughput
passed; the lowest failed), and at 3–5 requests a minute we were nowhere near
any plausible RPM limit. The old policy retried three times, one and two
seconds apart, entirely inside the same bad window. Google's published
evidence is 4-of-5 attempts failing without backoff and 5-of-5 succeeding with
it.
Deviation from the vendor example, deliberately: it caps the wait at 60s and
retries until success, which suits a batch job. An interactive turn has 85
seconds in total, so the cap is 16s and `abortSignal` remains the real ceiling.
Equal jitter rather than the example's full jitter, because a wait that
randomises down to almost nothing lands back in the window being waited out.
What this means for D39: the limiter stays — it bounds our own contribution and
smooths bursts, and it cost 0.0 minutes of pacing in practice — but it is no
longer claimed to prevent 429s, and its 10-calls-a-minute budget is a bound we
chose rather than a quota we measured.
Verified live (run `8b6f3e7b`, eight seeds at n = 1, the same suite that lost
an execution twice under the old policy): **0 failed turns, 8/8 structurally
clean** — the suite's first fully passing run. A capacity error still occurred
and is the evidence that matters, because it shows the mechanism working
rather than the weather being kind: one turn retried **once** and completed
(`error_code` null), where the equivalent turn in the previous run retried
three times and died (`error_code = llm_error`). Shared capacity cannot be
prevented; being killed by it now can.
Affects: apps/api/src/routes/ai/lib/adk-llm.ts (+ new adk-llm.test.ts, 9
tests), D39 · Reverses: the three-attempt / 1s-2s retry policy
**Rule 4: this changes how the application handles every request**, including a
participant's, so it is frozen now and both the simulation runs and the
participant round run against this version. The four probe runs of 2026-09-20/21
were made against the old policy and are not comparable to later runs on
reliability grounds.

### D42 — A Belém morning may run to 13:00
Date: 2026-09-21 · Decided by: author (escalated by agent as Q25)
Options: widen `draft_slot_starts_between` to 12:30 · assert only that the
first slot is in the morning · widen to 13:00 · keep 12:00
Chosen: `[07:00, 13:00]` in `cases/scheduling_belem_morning.yaml`. The agent
recommended 12:30 as the smallest change; the author took the wider boundary.
Reason: the first full eight-seed run under the repaired pipeline (`11af8ef7`)
flagged a good plan — Pastéis 09:00, the monastery 10:00–12:00, Belém Tower
12:15–13:15 — because the third slot began fifteen minutes past noon. A morning
of two or three stops that runs into lunch is what the member asked for, and
failing it is a false regression, which D30 calls the worse of the two errors a
constraint can make; under D23's 8/8 seed criterion one occurrence in eight
would fail a minimum-functionality case.
Only the boundary moved. The check stays, because without it a draft of an
afternoon described as a morning passes: the drafting tool instructs the reply
not to repeat every slot, so a scoring criterion about the times the reply
names is vacuous exactly when it is needed. An afternoon draft still fails at
13:00.
Timing matters here: this had to be settled before B05, because sixteen
follow-ups inherit their seed's constraints and would have propagated the false
failure sixteen times.
Affects: cases/scheduling_belem_morning.yaml, tests/test_cases.py, B05, B10
Reverses: the 12:00 boundary set in B04 · Closes: Q25

### D41 — An execution's structural verdict lives on the execution row
Date: 2026-09-21 · Decided by: author (escalated by agent while writing B08)
Options: add `structural_findings` to `study_case_executions` · anchor the
findings to the execution's first turn in `study_verdicts` · give
`study_verdicts` a nullable `execution_id` and two mutually exclusive keys
Chosen: the first. Migration `20260921063256_study_execution_structural_
findings` adds a `jsonb` `structural_findings` beside the `structural_outcome`
the table already had. A second migration in the same change,
`20260921063446_study_execution_build_mutation_ids`, records which mutation
rows were the fixture build's — agent-decided, and the mechanism D38 already
specified ("excluded by id, not by timestamp"): the runner excluded them in
memory, but the checker also runs after the fact, and re-reading the trip then
would have counted the fixture as the case's work. `study_verdicts` is left entirely
to the participant round, which is what A01's own comment on it says it is for:
post-hoc verdicts over rows that have no case. `study_suggestions
.structural_check_outcome` stays null in simulation, which A13 had already
exempted by design.
Reason: `study_verdicts` is unique on `(suggestion_id, checker_version)` and
cascades from `study_suggestions`, so it is keyed to a **turn** — while D27
says a check is a claim about the **execution**. Anchoring an execution's
findings to one of its turns files a finding about turn three under turn one.
Affects: supabase migration, src/checker.py, docs/event-model.md, B08, C02
Reverses: B08's "writes `study_verdicts`" · Note: additive, one nullable
column on a harness-written simulation-only table; no grant needed, privileges
are per table.

### D40 — The trace records whether a lookup found anything
Date: 2026-09-21 · Decided by: author (escalated by agent while writing B08)
Options: add `result_found` to a tool trace entry · infer a miss from
`result_chars` · weaken `tools_any_of` to "ran without error"
Chosen: `result_found: boolean | null` on `ToolTraceEntry` — the tool's own
`found` flag where it has one (`read_wikipedia`, `get_region_climate`), null
for every other tool and for a call that threw.
Reason: B08's spec assumed the checker could see `found: false`. It could not.
`agent.study-trace.core.ts` reduces a result to its size on purpose — "they
carry trip content that already lives in the trip's own tables" — and that
reasoning holds for `search_places`, whose results reach the reply's refs, but
not for the reference tools, whose miss lands nowhere. So the record could not
tell "answered from a source" from "asked a source and it had nothing", which
is the one distinction `factual_qa_lisbon_november_weather` exists to make.
A boolean is not trip content, so the size-only rule is intact.
Rejected: inferring from `result_chars` needs a cut-off nobody can defend — a
`found: false` article miss carries alternatives and a note and runs to a
couple of hundred characters — and a false regression costs the suite its
credibility (D30). Weakening the check gives up the case.
Rule 4: additive to a fire-and-forget logging path. No request path, no
response shape, no behaviour change; three tests added to
`agent.study-trace.test.ts`, 158 API tests pass.
Affects: apps/api/src/routes/ai/agent/agent.study-trace.core.ts (+ its test),
docs/event-model.md, src/checker.py, B08 · Reverses: none

### D39 — One Vertex budget for every call the harness causes
Date: 2026-09-21 · Decided by: agent
Options: pace in the harness against one shared budget · lengthen the
application's own 429 backoff in `adk-llm.ts` · leave the rate alone and
handle the failures with a re-run policy
Chosen: the first. `src/ratelimit.py` holds one process-wide sliding-window
limiter, `VERTEX_CALLS_PER_MINUTE` (default 10, configurable). `src/llm.py`
claims one permit per model call **per attempt**; `src/simulator.py` claims
`AGENT_CALLS_PER_TURN` (default 4) before it posts a turn, because that
request makes model calls the harness does not make itself against the same
key. The run logs the seconds it spent pacing, so a budget set too low shows
up as a number rather than as a slow evening.
Reason: the B15 probe lost an execution to `429 RESOURCE_EXHAUSTED`. The rate
was ours — roughly 30-40 model calls in 150 seconds from two clients that did
not know about each other. `VERTEX_MIN_INTERVAL_MS` had not failed: it is
enforced on an instance field of a `Gemini` the API builds per request, so it
paces calls *within* one turn and says nothing about the next.
The budget is counted in model calls rather than in harness actions because a
turn that searches twice and drafts costs four calls where one that answers
from the prompt costs one; counting turns would budget the wrong unit.
Recorded as an agent decision under "do not ask about": it is a harness
parameter, reversible by editing a file, and it changes nothing about what is
measured. The alternative that would have been the author's is explicitly
rejected — lengthening the application's backoff changes how it handles every
member's request (root `CLAUDE.md`, rule 4) and would alter what the
participant round measures.
Cost, stated because it is not small: at 10 calls a minute an execution of two
agent turns and two simulator calls is a full minute, so a 128-execution run
is hours rather than tens of minutes. Runs are unattended and resumable, so
this is accepted; if the key's real quota is higher, one line raises it.
What it does not fix: a 429 that still gets through is retried three times a
second or two apart by the application and then returned as a 502, and the
execution is lost. That is Q24's second half and the author's.
Affects: src/ratelimit.py (new), src/config.py, src/llm.py, src/simulator.py,
src/runner.py, B10, B11 · Reverses: none · Partly closes: Q24

### D38 — a repetition gets a trip of its own, and nothing is ever deleted
Date: 2026-09-20 · Decided by: author (escalated by agent on the B15 probe)
Options: a fresh fixture trip per repetition, deleting nothing · keep one trip,
stop deleting the study rows, and copy the reply text onto `study_suggestions`
· keep the reset and snapshot each execution's record into
`study_case_executions`
Chosen: the first. `reset.provision()` builds a new fixture trip for every
repetition; `reset()`, `ensure_trip()`, `find_trip()` and both delete helpers
are gone. `RunHandle` no longer carries a trip. The opening gate provisions a
real trip and hands it to the first execution rather than rehearsing on one.
`study_mutations` leaves `MUST_BE_EMPTY` — building the fixture through the
member's API writes mutation rows by construction — and the build's own rows
are excluded from the execution **by id** (`ResetResult.build_mutation_ids`),
not by timestamp, because those rows carry the database's clock and the
harness reads its own.
Reason: the B15 probe run found that the reset was deleting the record. Of
eight executions, seven had no `study_suggestions` rows left: each repetition's
reset wiped `chat_messages`, `study_suggestions` and `study_mutations` for the
trip, and only the last execution survived. Two consequences, the second
fatal. The checker and the analysis read `tool_call_trace` and
`resulting_state_shape` *after* a run, and would have found almost nothing.
And the reply text exists **only** in `chat_messages` — `study_suggestions`
copies the user turn verbatim (D06) but keeps the reply as a
`reply_message_id` — so a baseline run would have destroyed its own replies as
it went, and D23's pair-wise comparison against the baseline would have had
nothing to compare with. B07's dry run did not catch it because its done-when
read `study_case_executions`, which is keyed to the run and survives; the rows
it *points at* did not.
Why a fresh trip over the other two: isolation by construction is a stronger
reading of invariant 1 than deleting the right list of tables, and it removes
the mechanism that was destroying the record rather than working around it. It
needs **no application change at all** (rule 4 is best satisfied by not
touching `apps/`) and no migration, because the reply text simply stays in
`chat_messages` where `reply_message_id` already points. The costs are
accepted: ~128 fixture trips per full run in a disposable database (the API
has no per-user trip limit), and the gate's emptiness check becomes the
assertion that provisioning really did hand back a new trip. D26 is unaffected
— the ids were already new every repetition.
Affects: src/reset.py, src/fixture.py, src/runner.py, B02, B07, B08, B10, B11,
C02 · Reverses: the delete-and-rebuild reset of B02, and `MUST_BE_EMPTY`
containing `study_mutations`

### D37 — the check vocabulary is derived from the event model, and telemetry is reported rather than bounded
Date: 2026-09-20 · Decided by: author (escalated by agent as Q21)
Options: adopt none and record the thinness as a limitation · adopt only the
keys a written case would use today · adopt the full list of unused signals ·
adopt the three and hold the rest behind a rule
Chosen: adopt the full list, split by what can be judged now. Four become check
keys the loader validates and B08 evaluates — `edits`
(`resulting_state_shape.edits`), `trip_after` (`resulting_state_shape
.trip_after`), `mutation_changed_keys` (`study_mutations.changed_keys`) and
`turn_errors` (`study_suggestions.error_code`). Five are **recorded and
reported per execution but not assertable**: `reply.chars`, `latency_ms`, the
token counts, `llm_calls` and `tool_calls` — a window over them is a threshold,
and there is no baseline to set one against until B10 has run (carried as Q22).
`request_type` and `agent_intent` stay out of the case vocabulary: they are the
participant round's labels and B12's signature field, not something a case
asserts.
And the rule that replaces the accident: a candidate key is found by reading
`docs/event-model.md`, and it is added when a case needs it, so every key in
the vocabulary is exercised by at least one case.
Reason: the author's. The vocabulary was written from the D19/D27 discussion
and never cross-checked against what the application records, so two keys were
found by accident and the rest were not found at all. A signal the app already
logs and no case can assert is the cheapest possible detection left on the
floor, which is what §2.6.1 claims structural verification is good at. Against
that, a key with no case behind it is a key nobody validates — hence the second
half of the rule, and hence the telemetry being reported rather than guessed at.
The eight seeds were revised in the same change: all eight gained `turn_errors:
none` and `trip_after: {blocks: fixture, slots: fixture}`, and
`scheduling_move_tram` gained `edits` and `mutation_changed_keys`. `turn_errors`
closes a real hole — `empty_reply` returns HTTP 200, so the simulator answers
the blank in character and every other check of a read-only case passes against
a trip nothing touched.
Affects: src/cases.py, cases/*.yaml (all eight), cases/README.md,
cases/reviewed.json, B03, B04, B08, C02 · Reverses: none · Closes: Q21
Note: the revision changes eight cases the author marked reviewed on
2026-09-20. The marks are left standing for the case text, which is unchanged;
the added keys are the author's own ruling here.

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
