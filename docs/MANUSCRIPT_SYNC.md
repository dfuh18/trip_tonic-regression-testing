# Manuscript sync — where the implementation has moved past the text

State as of 2026-09-24 (branch `feat/thesis-regression-testing`, after `ac3a1cb`),
read against manuscript revision `260917`. Before the baseline run and the pilot.
Every item names the decision (`D…`), log entry (`L…`) or open question (`Q…`)
that holds the full reasoning.

---

## Part 1 — Where the manuscript is behind

### A. Must change: the text now describes something that was not built

| # | Manuscript says | Now | Source | Where |
|---|---|---|---|---|
| 1 | Stage 2 asserts an "expected change / no-change relation between source and follow-up **output**" (Table 9) | Relations are **not** checked by comparing outputs. A directional relation becomes a changed check on the follow-up; an invariance relation is covered by the checks it inherits plus the judge. Measured, not argued: across four runs of one venue seed only **one** place appeared in all four, so "same venues as the seed" would fail a correct agent. | D27, D49 | §3.1 text + Table 9 row 2 |
| 2 | Stage 4 / P4: participant turns are "matched against existing cases" and "structural outcomes compared with user feedback" | **Structural checking is simulation-only.** Checks are written against the fixture trip: 10 of 20 check keys depend on it, and `trip_after` is in all 29 cases, so none carries over to a real trip. Participant turns get coverage matching (signature, request shape) and the judge, not structural verdicts. | D73 | §3.1 Stage 4, P4, P2 row "Stage 4", Table 9 row 4 |
| 3 | Table 12 crosses the structural check outcome with the user's action | **No round produces both.** Simulation has verdicts but no real user action; the participant round has user actions but no verdicts. Recommended: replace the structural axis with the judge's verdict outside simulation (option B). | Q27 (open) | §4.3, Table 12, Table 11 "Structural check outcome" row |
| 4 | "Each case is run eight times" | Seeds n = 8, metamorphic follow-ups n = 4 (§3.1 already permits reducing n). | D21 | §3.1 |
| 5 | Stage 1 = two seeds per function (the planned 8 seeds, 16 follow-ups, 128 executions) | **13 seeds + 18 follow-ups = 31 cases, ceiling 176 executions.** The suite is **sized by tool coverage** (every agent tool must be reachable by some case), not only by budget. Added seeds: surf (the only way to reach `get_climate_normals`), a trip-dated vs. next-days forecast pair, and two seeds that act over two turns. | D50, D51, D54, D81–D84 | §3.1 Stage 1 |
| 6 | P1: simulation covers "the whole stack **from frontend** to backend"; §3.3: the simulator "interacts with the same interface regular users do" | The simulator writes the member's message row the way the browser does and calls the same API endpoint (`POST /api/ai/agent/chat`). **The web UI is not driven.** Everything from the API down is the production path. | `src/simulator.py` | P1 row, §3.3 |
| 7 | Runner "makes sure application states are reset in between executions" | **Nothing is reset. Each repetition gets a new fixture trip**, and nothing is ever deleted. Resetting the state destroyed the previous repetition's record, and with it the replies the pair-wise stage needs. | D38, L08 | §3.4 Runner, Table 11 run row |
| 8 | Test case = "expected tool calls **and their order**" | A case lists the tools it **permits**, and every other tool is forbidden. It asserts the **outcome**: a time is a window plus a length, a place is a kind (never a specific venue), a retry is reported and not failed. The three read tools are always allowed. | D28, D30, D31, D32 | §3.4 Test cases, P5 |

### B. Should add: facts the text does not have yet

- **Pass rule** (D23): seed passes only at 8/8; follow-up at ≥ 75 %; a structural
  `detected` fails the execution whatever the judge says; the pair-wise judge runs
  in **both orderings** at temperature 0 and passes only if both say "at least as
  good".
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
- **Position bias in the pair-wise judge** (D23, Q34): an LLM judge comparing two
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
  regression. Q34 proposes counting a disagreeing pair as **undecided** and
  reporting the disagreement rate as a property of the judge. A real regression
  still shows as a consistent preference for the baseline in both orderings.
  Name this as a threat to validity in §3.7/§4.5 whichever way Q34 goes.
- **Request shapes / segmentation** (Q28, Q29, open): the four `request_type`
  classes are too coarse and the D24 signature too fine for §4.3; a 7-class
  "request shape" and a rule that splits runs into requests are proposed. The
  participant round records **turns**, not requests.

### C. Must reword: a claim that changed meaning

- **Advisory "leaves no structural trace"** (P4). The advisory seeds do assert
  something: nothing may be written (D29). But the agent looks things up before
  advising (packing → climate, Sintra → Wikipedia), so no rule based on the
  tool trace ever labels a turn `advisory` (Q28). The advisory baseline is
  **scored, not checked**, which makes it a weaker instrument (L06).
- **§3.3 "execution follows the same paths as ordinary use"** is still true, but
  the system under test **changed during the build**, before any baseline. These
  were author rulings on findings, not instrumentation (see §3.4 draft, "changes
  to the app").
- **§2.6.1 / §3.1 "structural verification is the cheap half"**: holds per
  assertion. The cost is in *establishing* that an assertion is true (L05, L07, L09).

---

## Part 2 — Rough draft, §3.4 Implementation

> Draft prose. Numbers verified against the repository on 2026-09-24; items marked
> **[fill]** are still to be measured (baseline, regression run, pilot).

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
  **[decide: fix before baseline or record as known regression target]**

### 3.4.7 Results so far — [fill]

- **Comparison rehearsal** (`sim/03_baseline`, `sim/04_regress`): n = 1 run
  `5f4f6841` (31 cases, judge mean 9.35) against a test baseline of each case's
  best execution (D86). The flow works end to end (31/31 compared, 0 judge
  errors; a self-comparison of 29 identical pairs returned `tie`,`tie` every
  time). **8 of 31 cases fail: 1 structurally** (the D83 duplication), **4 with
  both orderings preferring the baseline** on points the judge itself calls
  "slightly better" (candidates scoring 9–10 point-wise), and **3 on position
  bias** (orderings disagree). Against a best-of baseline, a seed `fail` will
  mostly mean "not reliably as good as its best reply" rather than "regressed"
  (Q34).

- Verification runs so far are at n = 1 only (e.g. `42cab17a`, 29 cases, all
  structurally clean after fixes). **[fill: baseline run id, n = 8/4,
  executions, cost, duration, score distribution]**
- **[fill: regression run pass rates per case; share of failures that are
  structural vs. judge vs. capacity]**
- **[fill: pilot — consent, event-model completeness assertion after first
  session]**

---

## Open before the manuscript can be final

- **Q27** Table 12 — which axis replaces the structural verdict in the participant round.
- **Q28** Request-shape rule, and whether "advisory" means "called no tool".
- **Q29** Request boundary for participant data (segmentation rule C + slash/reference).
- **Q22** Telemetry bounds — deferred until a baseline exists.
- **D83 finding** — fix the duplicate-scheduling behaviour before the baseline or keep it as a known target.
- **Q33** Where pair-wise verdicts are stored (a `study_comparisons` table, as `study_scores` for point-wise).
- **Q34** What a seed verdict means against a best-of baseline: position bias and "slightly better" preferences, measured first as the judge's own noise floor.
