# Manuscript sync — where the implementation has moved past the text

State as of 2026-09-28 (branch `feat/thesis-regression-testing`), read against
manuscript revision `260917`. After the baseline run (B10), the regression run
(B11) and the pilot sessions; the participant-round analysis is built but not
yet run on study data. Items added or changed since the 2026-09-24 sync are
marked *(09-28)*.
Every item names the decision (`D…`), log entry (`L…`) or open question (`Q…`)
that holds the full reasoning.

---

## Part 1 — Where the manuscript is behind

### A. Must change: the text now describes something that was not built

| # | Manuscript says | Now | Source | Where |
|---|---|---|---|---|
| 1 | Stage 2 asserts an "expected change / no-change relation between source and follow-up **output**" (Table 9) | Relations are **not** checked by comparing outputs. A directional relation becomes a changed check on the follow-up; an invariance relation is covered by the checks it inherits plus the judge. Measured, not argued: across four runs of one venue seed only **one** place appeared in all four, so "same venues as the seed" would fail a correct agent. | D27, D49 | §3.1 text + Table 9 row 2 |
| 2 | Stage 4 / P4: participant turns are "matched against existing cases" and "structural outcomes compared with user feedback" | **Structural checking is simulation-only.** Checks are written against the fixture trip: 10 of 20 check keys depend on it, and `trip_after` is in all 29 cases, so none carries over to a real trip. Participant turns get coverage matching (signature, request shape) and the judge, not structural verdicts. | D73 | §3.1 Stage 4, P4, P2 row "Stage 4", Table 9 row 4 |
| 3 | Table 12 crosses the structural check outcome with the user's action | **No round produces both.** Simulation has verdicts but no real user action; the participant round has user actions but no verdicts. *(09-28)* **Ruled: the two axes are reported side by side, not crossed** (option A). The derived label (Positive / Neutral / Lacks quality / Failure) goes. | D102 (closes Q27) | §4.3, Table 12, Table 11 "Structural check outcome" row |
| 4 | "Each case is run eight times" | Seeds n = 8, metamorphic follow-ups n = 4 (§3.1 already permits reducing n). | D21 | §3.1 |
| 5 | Stage 1 = two seeds per function (the planned 8 seeds, 16 follow-ups, 128 executions) | **13 seeds + 18 follow-ups = 31 cases, ceiling 176 executions.** The suite is **sized by tool coverage** (every agent tool must be reachable by some case), not only by budget. Added seeds: surf (the only way to reach `get_climate_normals`), a trip-dated vs. next-days forecast pair, and two seeds that act over two turns. | D50, D51, D54, D81–D84 | §3.1 Stage 1 |
| 6 | P1: simulation covers "the whole stack **from frontend** to backend"; §3.3: the simulator "interacts with the same interface regular users do" | The simulator writes the member's message row the way the browser does and calls the same API endpoint (`POST /api/ai/agent/chat`). **The web UI is not driven.** Everything from the API down is the production path. | `src/simulator.py` | P1 row, §3.3 |
| 7 | Runner "makes sure application states are reset in between executions" | **Nothing is reset. Each repetition gets a new fixture trip**, and nothing is ever deleted. Resetting the state destroyed the previous repetition's record, and with it the replies the pair-wise stage needs. | D38, L08 | §3.4 Runner, Table 11 run row |
| 8 | Test case = "expected tool calls **and their order**" | A case lists the tools it **permits**, and every other tool is forbidden. It asserts the **outcome**: a time is a window plus a length, a place is a kind (never a specific venue), a retry is reported and not failed. The three read tools are always allowed. | D28, D30, D31, D32 | §3.4 Test cases, P5 |
| 9 | P1: an interaction is covered "when a **test case** with the same signature exists in the suite" | *(09-28)* A case has no signature until it runs: the signature is read off a recorded trace. A participant **request** (a Tonic run split by shape change and slash command, D100) is covered when a **recorded simulated execution** (runs `1a872c09` + `e097f78e`) has the same D24 signature. Its request type is D09 over all of the request's tools. Coverage is also reported per turn, and no claim rests on a request count. | D24, D100, D101 | §4.2.3 P1, §4.3 (3) |
| 10 | P3: "point-wise judging criteria are applied according to the assigned **request type**" | *(09-28)* **Not built; blocked.** The judge's rubrics are per test case, it is shown the fixture trip, and its scores are stored against simulated executions only. Scoring participant replies needs per-type rubrics, a decision on trip context, and a new table (an event-model change). | Q35 (open) | §4.2.3 P3 |
| 11 | P2: failures are "errors that arise while the agent computes a suggestion", ranked **by request type** | *(09-28)* The simulation produced **0 execution failures in 426 turns**. What it did produce are tool errors the agent absorbed: 16 of 649 tool calls (2.5 %) came back an error in turns that still answered. **P2 now counts those, per tool call, and compares them per tool** (each tool's errored share of its calls, both rounds, Wilson intervals); request type and shape are secondary views. Kendall's τ-b over the tools both rounds called, descriptive. Turns without any response are still reported, separately. P2's wording needs both changes: the unit (tool, not request type) and the failure (absorbed, not fatal). | D101, D103 (closes Q36) | §4.2.3 P2, §4.3 (2) |

### B. Should add: facts the text does not have yet

- **Pass rule** (D23, amended by D88): seed passes only at 8/8; follow-up at
  ≥ 75 %; a structural `detected` fails the execution whatever the judge says.
  The pair-wise judge runs in **both orderings** at temperature 0. An execution
  fails on the judge only when **both** orderings prefer the baseline. When the
  orderings contradict each other, it is a **position draw**: it passes, and is
  counted per case with D23's strict pass rate shown beside it.
- **Judge protocol**: scores the **first reply against the opening turn** (D34),
  is told today's date (D79), and is the **same model family as the agent**
  (`gemini-3.5-flash`, D20). The last point is a limitation to name in §3.7/§4.5.
- **Baseline adoption**: per case, the highest judge score among executions that
  passed the structural check; the author adopts it and it is stored as a file
  (`cases/baseline.json`). Test baselines are kept apart so a rehearsal cannot be
  mistaken for the real one.
- **Failure accounting**: an execution lost to provider overload **counts as a
  failure** (D44, author chose the strict measure). Our own 85 s turn deadline is a
  failure. A timeout on the simulator's own model call is retried, because it is
  a harness failure (D70, L10). → The published pass rate includes some of the
  provider's availability. State this.
- **Judge verdicts are persisted, both kinds**: point-wise scores in
  `study_scores` (D71), pair-wise verdicts with both orderings in
  `study_comparisons` (D87), each keyed by judge model and prompt version and
  tagged with the baseline they were taken against.
- **Versioning beyond Table 11** (P6): `case_version` (content hash per case,
  D74), `suite_version` over the fixture as resolved (D62), real `api_version`/
  `app_version`/`api_commit` (D63), a checker version whose verdicts are
  **appended, never overwritten** (D76), `judge_prompt_version` (D71/D79), fixture ids
  per execution (D26), model **release date** next to the id (D04).
- **Author review is evidenced**: 31/31 cases carry an author mark tied to the
  exact text reviewed. Editing a case after review shows as drift (D74, D78, D79, D84).
- **Tool coverage is a first-class output**: calls, errors and misses per tool
  per run. It is also the rule for letting a case into the suite (D50, D66, D68). This is
  the instrument that found the weather defect (L11).
- **Position bias in the pair-wise judge** (D23, D88): an LLM judge comparing two
  replies can prefer one for *where* it appears, not for what it says, and it
  does so most when the two are close. The comparison is therefore asked twice
  with the order swapped (baseline as A, then candidate as A). A judge deciding
  on content answers consistently: `A`,`B` when the baseline is better, `B`,`A`
  when the candidate is, `tie`,`tie` when equal. A judge deciding on position
  answers inconsistently, e.g. `A`,`A`, which picks the first slot once for each
  reply. The candidate passes only if **both** orderings hold, so position bias
  can fail an execution but never pass one: the control is conservative by
  design. Measured in the rehearsal (n = 1 run `5f4f6841` against a best-of
  test baseline): **3 of 31 comparisons disagreed (~10 %)**. Examples:
  `A`,`A` on the Belém full day (pure slot preference), `A`,`tie` on the
  Sunday tram move, `tie`,`B` on the riverside-drink search. In each the judge
  could not rank the two replies consistently, which is evidence they were
  about equally good, and D23 charges each to the agent. **Consequence for
  §3.1's 8/8 seed rule:** at ~10 % per comparison, a seed has about a **56 %**
  chance (1 − 0.9⁸) that at least one of its eight repetitions disagrees, so
  position bias alone could fail roughly half the seeds before any real
  regression. **Ruled (D88): a contradictory pair is a position draw.** It
  passes, is counted and listed per case, and D23's strict pass rate is reported
  beside the rule in force. A real regression still shows as a consistent
  preference for the baseline in both orderings, and still fails. Under D88 the
  rehearsal has 5 of 31 cases failing instead of 8. Name position bias and this
  ruling in §3.7/§4.5: the judge's own noise is measured and reported, not
  charged to the agent.
  **[cite: source needed.]** The manuscript currently cites nothing for
  position bias. The swap-both-orderings control (§3.1, D23) and this ruling
  both need a source where the judge is introduced (§2.6 / §3.4 Judge).
  Candidates, to verify before citing: Zheng et al. (2023), *Judging
  LLM-as-a-Judge with MT-Bench and Chatbot Arena* (NeurIPS Datasets and
  Benchmarks), which documents position bias and evaluates swapping the order
  as a mitigation; Wang et al. (2023), *Large Language Models are not Fair
  Evaluators*, which shows verdicts flip with answer order and proposes
  evaluating both positions. Check whether Guan et al. (2025), already cited
  for point-wise vs pair-wise, covers it too.
- **Request shapes / segmentation** (D99, D100): the four `request_type`
  classes are too coarse and the D24 signature too fine for §4.3. A 7-class
  "request shape" (shapes7) labels each turn: advisory · factual.reference ·
  factual.climate · factual.forecast · venue.search · scheduling.draft ·
  scheduling.edit, plus `other` for a turn doing two things (except search
  feeding a draft). A participant's Tonic run is split into requests where the
  shape changes or a slash command starts one. The participant round records
  **turns**, not requests; segments serve coverage (P1), turns serve failure
  rates (P2). *(09-28)* Reference to an earlier turn's place is deliberately
  **not** a boundary signal, although the probe showed it joins search → "add
  the second one" correctly: such a request counts as two. State this as the
  segmentation's known split error.
- *(09-28)* **Statistics** (D101), since §4.3 names none: failure and coverage
  rates with 95 % **Wilson** intervals; P2's rank agreement as **Kendall's
  τ-b**, descriptive; P3 as a one-sided **Mann–Whitney U** (positive > negative,
  α = .05) with the **rank-biserial r** and a percentile-bootstrap interval,
  thumbs and accept/reject never pooled.
- *(09-28)* **Usability scoring**: the **UMUX-LITE → SUS conversion**. UMUX-LITE
  (0–100) is converted to an estimated SUS score, SUS-equivalent ≈ 0.65 ×
  UMUX-LITE + 22.9 (a published linear fit between the two questionnaires),
  and graded on the Sauro–Lewis curved grading scale. Report it as an
  estimate, not a measured SUS.
- *(09-28)* **P2's failures are the ones the agent absorbed** (D103): tool
  calls that errored in a turn that still answered. Simulation: `get_weather`
  11/43 (10 beyond the 16-day forecast horizon, 1 timeout),
  `get_climate_normals` 2/19 (timeouts), `move_slot` 3/43 (2 invalid
  arguments, 1 rejected value); every other tool 0. The kind of error is read
  off the message by pattern; the message is never shown.
- *(09-28)* **Why a request is uncovered** is reported per request (the parts in
  which the closest recorded signature differs), separating near misses (one
  bucket off) from shapes the suite never produces.
  **[cite: sources needed]** for the statistics and the usability conversion.
  Candidates, to verify before citing: Wilson (1927) for the score interval;
  Kendall (1938/1945) for τ-b; Mann & Whitney (1947); Kerby (2014) for the
  rank-biserial as an effect size; Lewis, Utesch & Maher (2013) for UMUX-LITE
  and the UMUX-LITE → SUS conversion; Sauro & Lewis (2016), *Quantifying the User
  Experience*, for the curved grading scale.

### C. Must reword: a claim that changed meaning

- **Advisory "leaves no structural trace"** (P4). The advisory seeds do assert
  something: nothing may be written (D29). But the agent looks things up before
  advising (packing → climate, Sintra → Wikipedia), so no rule based on the
  tool trace ever labels a turn `advisory` (Q28). The advisory baseline is
  **scored, not checked**, which makes it a weaker instrument (L06).
  *(09-28)* In the pilot, the one `advisory` turn is one that called no tool.
  Whether `advisory` is *defined* that way is still open (Q28 sub-decision).
- **§3.3 "execution follows the same paths as ordinary use"** is still true, but
  the system under test **changed during the build**, before any baseline. These
  were author rulings on findings, not instrumentation (see §3.4 draft, "changes
  to the app").
- **§2.6.1 / §3.1 "structural verification is the cheap half"**: holds per
  assertion. The cost is in *establishing* that an assertion is true (L05, L07, L09).

---

## Part 2 — Rough draft, §3.4 Implementation

> Draft prose. Numbers verified against the repository on 2026-09-24 unless
> marked *(09-28)*; items marked **[fill]** are still to be measured.
>
> *(09-28)* **Counts to refresh at the freeze.** Now: **103 decision entries**
> (still **9** taken by the agent), **36 questions** raised, **6 open**; the
> harness is **29 modules, ~9,070 lines** of Python with **317 test functions**.
> Recount commits and application changes from git at the freeze rather than
> patching the figures below one by one.

### 3.4.1 Build process and effort

The instantiation was built over **eight consecutive days (17–24 September
2026)** on one long-lived branch, in **71 commits**. **60** of them change code,
test cases, tests or the database schema; the rest are planning and
documentation. **19** commits touch the Trip Tonic application itself (`apps/`,
`supabase/`). The build falls into two phases. Phase A instrumented the
application in one day (18 September): 12 database migrations, turn and state
mutation logging, mutation origin tracking, the thumbs control, consent and
enrolment, and the post-task dialog. In total ~7,000 lines were added to the
application. Phase B, the pipeline for stages 1 to 3.2, took the remaining six
days. It consists of ~7,450 lines of Python across 26 modules, ~3,900 lines of
tests (318 tests), six worked-example notebooks and 31 test cases.

The coding agent (Fable 5.1 in Claude Code) worked from a written plan with
tasks tagged by tier. `[FABLE]` tasks involve design judgement.
`[STANDARD]` tasks were specified tightly enough for a subagent with no context to
execute them. Every choice on the stop-and-ask list was put to the author. The
decision log holds **85 decisions**. **76** were taken by the author, mostly
after the agent escalated them with options and a recommendation. **9** were
taken by the agent within its delegated scope. About **30 questions** were
raised. The ones still open that matter for the manuscript are Q27–Q29, and
Q22 is deferred until a baseline exists.

Agent code was verified at four levels:
1. **Tests**, written in the same commit as the change.
2. **Reading back recorded rows** after a live run. Checking status codes was
   not enough (L02, L08).
3. **Independent review rounds.** A separate agent with read-only access, the
   application source and a written list of criteria reviewed the cases three
   times (L07) and the harness three times (D69, D71, D76).
4. **An audit of the test suite itself** (D80). It found that tests were
   recording observations rather than invariants, and it added a coverage-based
   check that no test contains a dead assert.

### 3.4.2 Components as built

- **Test case.** One YAML file per case. It holds the opening turn, a persona
  and the goal, the checks, the scoring criteria, the provenance
  (seeded / metamorphic) and the run priority. Checks describe a single
  execution, using a closed vocabulary that the case loader validates. That
  vocabulary was derived from what the event model records, not invented
  (D27, D37).
- **Tool rule.** A case permits the tools it names, and every other tool is
  forbidden (D28). Cases assert the outcome, not the route: time windows,
  kinds of place, retries reported rather than failed (D30–D32).
- **Metamorphic expansion.** Eight relations: four invariance (paraphrase,
  typos, irrelevant detail, German) and four directional (constraint, day,
  count, negation). Each relation is used at least once, and each seed gets at
  most one follow-up per relation (D22, D61). A follow-up inherits its seed's
  checks and criteria, and a directional relation overrides the checks the
  perturbation changes (D49).
- **Simulator.** A persona prompt on `gemini-3.5-flash`. It drives the
  production chat endpoint with a real member session. It stops at 3 turns or
  when its goal is met.
- **Structure checker.** Produces a `none`/`detected` verdict with findings for
  each execution. Verdicts are appended per checker version and case version
  (D76).
- **Judge.** Written as an explicit, versioned prompt; no managed evaluation
  service is used. It scores the first reply out of 10 against the case
  criteria. It then compares the reply pair-wise against the baseline in both
  orderings (D23, D34).
- **Runner.** Provisions a fresh fixture trip for each repetition. A gate
  before the run refuses to start on unclean state. The runner resumes after
  interruption and runs within a budget on Vertex calls. It separates platform
  failures from failures of the harness itself (D38, D39, D59, D70).
- **Reports.** Tool coverage, check coverage, telemetry per population, and a
  completeness survey that fails if an event-model field has no writer (D64, D76).

### 3.4.3 Main challenges

1. **Isolation and logging conflicted.** Resetting state to keep repetitions
   independent deleted the record a later stage needed. The fix was to
   provision a new trip each time instead of cleaning up (L08). Two invariants
   stated in different sections were each obvious on its own terms and still
   clashed.
2. **The check vocabulary and the log schema were specified separately.** A
   field can exist and still not carry what a check needs (L05, L09). The
   step that worked was to name the recorded field each assertion is
   evaluated from, before writing the checker.
3. **"LLM-generated, human-reviewed" took three adversarial rounds** (L07). The
   first read by the author caught wording and missed every defect that
   mattered. The later rounds used written criteria (14 per case, 4 for the
   suite) and found constraints stricter than the member's request, which
   would have produced false regressions.
4. **Provider capacity.** Newer Gemini models share a dynamic quota, so 429s
   and 504s occur at any load. The agent, the harness and the rules for scoring
   failures each needed their own policy (D43, D44, D70, L10).
5. **Time.** A fixed-date fixture expires, forecasts exist only 16 days ahead,
   and neither the agent nor the judge knew the current date (D54–D57, D79).
6. **The harness's own tests** recorded snapshots rather than claims (D80).
   **[optional for §3.7]**

### 3.4.4 What the suite converged on

- **Arity divides checks from predicates.** A check describes one execution;
  comparing two executions is left to the judge (D27, D49).
- **Assert the outcome, not the route; the kind of place, not which place; a
  window, not a clock time.** A false regression was ranked the worse error
  (D30).
- **Deny by default for tools.** A tool no one anticipated is a behaviour
  change, and a behaviour change is what a regression suite exists to notice
  (D28).
- **Size the suite by coverage.** Every tool is reachable, and every relation
  is used at least once (D50, D61).
- **Nothing is overwritten.** Verdicts, scores and attempts are appended and
  versioned (D71, D76).

### 3.4.5 How coverage was assessed and what it revealed

Three measures were used:
- **Tool coverage** per run: calls, errors and misses per tool. This is also the
  rule for letting a case into the suite.
- **Check-key and relation coverage** over the case set.
- **Coverage signature** (D24) over recorded executions. It is later matched
  against participant turns.

What coverage revealed:
- **`get_weather` had never once succeeded** in over 100 recorded executions,
  and the suite was still green. Cases permitted the tool without requiring
  it, so an agent that fell back to another source passed (L11).
- **`get_climate_normals` was declared by three cases and called by none**
  (D51).
- **`schedule_block`/`unschedule_block` are reachable only through
  `/reschedule`** (D50).
- **One metamorphic relation (typos) had zero cases** (D61).
- **Several tool caps sat exactly on observed behaviour.** One more search by a
  correct agent would have failed the case (D58, D75).
- **The advisory class is unreachable by any rule based on the tool trace**
  (Q28).
- *(09-28)* **On the pilot, 7 of 16 requests (44 %) match a recorded
  signature** (dry run only; pilot sessions are excluded from analysis). The
  misses were mostly shapes the suite never produces: drafting from places
  already on the trip without a search (3), revising a draft (1), and mixed
  requests (3). Only 1 was a near miss (off by the turn bucket alone). This is
  the kind of result §4.2.3 says matters more than the proportion.

### 3.4.6 Changes to the application it has already caused

All were author rulings, made before any baseline:
- **Weather tool fixed** (D36). Every dated forecast call had been failing
  with an Open-Meteo 400. The defect predates the study, and manual use had
  not surfaced it.
- **Tonic is told today's date** (D57). Before, it resolved "the next few
  days" against the trip's November dates. It also accepted a date the member
  made up, and requested forecasts for 2024 and 2025.
- **The weather instruction chooses the calendar from the member's wording**
  (D56).
- **Capacity backoff** (D43). The agent now waits out a 429 (~31 s worst
  case) instead of failing after about 8 s.
- **Overload is visible** (D45). Members see a 503 message saying the model is
  overloaded. Failures are recorded by kind, and admins get an aggregate
  reliability view.
- **Real app versions** (D63). Both apps had carried their scaffold defaults
  through 377 commits.
- **Found, not yet fixed** (D83): when asked to extend a plan, the agent
  re-proposes stops already on the itinerary, so accepting the new plan
  schedules a stop twice. Only the new two-turn seed can reach this.
  *(09-28)* It was **not fixed before the baseline**: the baseline run shows it
  in 6 of 8 repetitions of the tram case, and in the regression run that case
  is the one stable agent failure (structural, 8/8). It is therefore in the
  record as a known behaviour the suite detects.

### 3.4.7 Results so far — [fill]

- **Comparison rehearsal** (`sim/03_baseline`, `sim/04_regress`): n = 1 run
  `5f4f6841` (31 cases, judge mean 9.35) against a test baseline of each case's
  best execution (D86). The flow works end to end (31/31 compared, 0 judge
  errors; a self-comparison of 29 identical pairs returned `tie`,`tie` every
  time). Under D88, **5 of 31 cases fail: 1 structurally** (the D83
  duplication) and **4 with both orderings preferring the baseline** on points
  the judge itself calls "slightly better" (candidates scoring 9–10
  point-wise). **3 more pass as position draws** (orderings disagree); under
  D23's strict reading they failed. Against a best-of baseline (D86), what
  remains of a seed `fail` on the judge is a consistent preference for the best
  reply: a high bar that notices small changes, read one failure at a time.

- *(09-28)* **Baseline (stage 3.1, B10):** run `1a872c09`, 31 cases at n = 8/4,
  **176 executions, 0 failed, 165 structurally clean**, all 176 scored (mean
  **9.26**), **$4.52**. Resumed once after the harness's session lapsed (D95).
  Adopted by the author unchanged (D96, baseline key `0575abe1f224`). Findings:
  `get_climate_normals` times out under the API's 8 s budget (2 of 8 surf
  repetitions), and the D83 duplication (6 of 8). **[fill: duration, score
  distribution figure from `sim/03_baseline`]**
- *(09-28)* **Regression run (stage 3.2, B11):** run `e097f78e`, **no
  configuration change** (every version field matches but `api_commit`, whose
  application code is identical). 176 executions, 0 failed, 168 structurally
  clean, all compared pair-wise (`judge-pairwise/2`, D97). **22 of 31 cases
  pass, 9 fail** (D23 strict: 14/17); 27 position draws (16 %). One failure is
  structural (the D83 case, 8/8); the other **eight fail on the judge**: their
  executions pass every structural check of the case, and the judge finds the
  reply not at least as good as the baseline, which is each case's best
  execution (baseline entries 9.65 point-wise, this run 9.48). The
  configuration did not change between the runs. This bears on §3.1's
  variance claim and on the thresholds (the author's call; an
  IMPLEMENTATION_LOG entry is owed).
- *(09-28)* **Pilot:** `05_pilot` passed on 2026-09-26 over 4 sessions: every
  event-model field populated, consent versioned, a decline records nothing,
  post-task fires once after turn 3, the pinned model, the `ignored` job.
  There are 7 pilot sessions now; **[fill: re-run `05_pilot` on all of them
  and record C04]**. The propositions notebook ran end to end on the pilot as
  a dry run (`06_analysis`); `08`/`09` are its clean copies for the study.

---

## Open before the manuscript can be final

- **Citation** for LLM-judge position bias and the order-swap control (see Part 1 B, "Position bias").
- **Citations** for the statistics and the UMUX-LITE conversion (see Part 1 B, "Statistics").
- **Judge-only failures in the regression run** (B11): 8 of 31 cases pass their
  structural checks and fail because the judge finds the replies not at least
  as good as the best-of baseline, with no configuration change. Keep the rule
  and report this, or revisit the thresholds or the baseline choice (D86).

- **Table 12** (D102): reported as two axes side by side; the manuscript's
  derived label (Positive / Neutral / Lacks quality / Failure) must go.
- **Q35** How the judge scores participant replies (rubric per request type,
  trip context, storage).
- **P2's wording** (D103): the claim is now made per tool, over tool errors the
  agent absorbed, not per request type over fatal errors.
- **Q28** Whether "advisory" means "called no tool". The rule itself is
  ruled: shapes7 (D99).
- **Q29** The request label (`interaction_label` vs the union of tools). The
  boundary is ruled: C + slash, no reference (D100).
- **Q22** Telemetry bounds — deferred until a baseline exists.
- ~~**D83 finding**~~ — settled by events: not fixed before the baseline, so it
  is a known behaviour the suite detects (see 3.4.6).


