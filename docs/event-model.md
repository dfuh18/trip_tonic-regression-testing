# Event model

> **STATUS: reviewed by the author, 2026-09-17.** Derived from Table 11, Table 12
> and the prose of §3.3 and §4.2.2 of the manuscript, then corrected. Field names
> and types remain **proposals** — the manuscript names the data points, not the
> schema — but the open questions that blocked Phase A have been ruled on and are
> recorded in `DECISIONS.md` (D02, D03, D05).
>
> The `TODO(author)` markers were ruled on 2026-09-17/18 (D06–D19); each is
> replaced below by a pointer to its decision. The "Field → writer" mapping is
> added by task A01 once the schema exists.

## Why this file is load-bearing

Hard invariant 3: a field that is not logged is data that does not exist, and
the participant round happens once. This file is the list that invariant refers
to. `docs/IMPLEMENTATION_PLAN.md` derives its Phase A tasks from it, and the
pilot notebook asserts that every field here is populated in at least one real
record before the study round opens.

## Levels

The manuscript records at four levels plus a general level. §4.2.2 fixes which
levels come from where:

| Level | Produced during | Notes |
|---|---|---|
| Run | Simulation (pre-recorded) | One regression/baseline execution |
| Test case | Simulation (pre-recorded) | One case, run n times per run |
| Suggestion | **Both** simulation and participant round | The comparison unit |
| State mutation | **Both** | Links a trip change back to what caused it |
| General | Both | Device and timestamp, attached to suggestions |

The suggestion and state-mutation levels are the ones that must exist in the
**live application**, because the participant round produces them. Run and test
case levels are written by the harness in this subtree.

---

## Session level

`session_id` and `user_id` are the author's additions to Table 11 (2026-09-17);
the rest of this level is required by the pilot (see `CLAUDE.md`, Phases).
Without `run_type`, pilot sessions and real sessions are indistinguishable after
the fact.

| Field | Type | Set by | Source | Notes |
|---|---|---|---|---|
| `session_id` | uuid | app | Table 11 (author addition) | The authenticated session observation covers (§4.2.2) |
| `user_id` | uuid | app | Table 11 (author addition) | Pseudonymous in all analysis output |
| `run_type` | enum `pilot` \| `study` \| `simulation` | app, at session creation | extension | Never inferred later from timestamp or email. `simulation` on the harness's sessions (D15) — same tables, same app |
| `consent_version` | text | app | §4.2.2 | Consent is recorded *with a version identifier* |
| `consent_at` | timestamptz | app | §4.2.2 | Consent gates everything after it |
| `device_type` | text | app | §4.2.2 | Derived from accessible browser data |

## Survey levels — two separate tables (D02)

The demographic questionnaire and the post-task instrument are **their own
tables**, not columns on the session, keeping survey responses separated from
behavioural telemetry. Each row references `session_id`.

The separation is also what makes the consent commitments tractable: survey
responses are self-reported personal data, behavioural rows are not, and a
deletion or access request is answerable per table rather than per column.

### `survey_demographics` — one row per session

| Field | Type | Source | Notes |
|---|---|---|---|
| `session_id` | uuid FK | §4.2.2 | |
| `age` | — | §4.2.2 | |
| `gender` | — | §4.2.2 | |
| `education_level` | — | §4.2.2 | |
| `llm_familiarity` | — | §4.2.2 | Expected to influence behaviour, hence recorded |
| `submitted_at` | timestamptz | extension | |

### `survey_post_task` — one row per session

Appears on a dismissible in-app screen once the **third** interaction has been
logged (§4.2.2). Dismissible means a row may be absent, or present and partial —
the analysis must handle both, and the pilot should produce one of each.

| Field | Type | Source | Notes |
|---|---|---|---|
| `session_id` | uuid FK | §4.2.2 | |
| `umux_lite_capability` | — | §4.2.2 | UMUX-LITE item 1 (Lewis et al., 2013) |
| `umux_lite_ease` | — | §4.2.2 | UMUX-LITE item 2 |
| `real_trip` | boolean | §4.2.2 | Task involvement |
| `likelihood_to_recommend` | integer 1–7 | §4.2.2 | |
| `free_text` | text \| null | §4.2.2 | Optional |
| `submitted_at` | timestamptz | extension | |
| `dismissed_at` | timestamptz \| null | extension | Distinguishes "dismissed" from "never reached" |

**Scales (D18):** `age` exact integer; `gender` woman / man / non-binary /
prefer not to say; `education_level` compulsory / apprenticeship or vocational
/ matura or high school / bachelor / master or higher; `llm_familiarity` never
/ rarely / monthly / weekly / daily. UMUX-LITE items 1..7, likelihood to
recommend 1..7.

---

## Run level

*Simulation only. Written by the harness.*

| Field | Type | Source | Notes |
|---|---|---|---|
| `run_id` | uuid | Table 11 | |
| `model_version` | text | Table 11 | **Dated release, never an alias** (invariant 2, §3.3) |
| `model_released_on` | date | Table 11 | The release date of `model_version`. Table 11 asks for the *dated release*; an id alone does not evidence a pin. From `DEFAULT_VERTEX_MODEL_RELEASED` in `apps/api/src/lib/env.ts` |
| `prompt_version` | text | Table 11 | |
| `tool_version` | text | Table 11 | |
| `suite_version` | text | Table 11 | Regression test suite version |
| `baseline_ref` | text | Table 11 | Which baseline this run is compared against |
| `tool_call_trace` | jsonb | Table 11 | Ordered; the coverage signature in P1 is built from it. One tool entry is `{kind, seq, tool, args, started_at, duration_ms, result_error, result_chars, result_found}`. Results are reduced to a size — they carry trip content that lives in the trip's own tables — with two exceptions kept because they exist nowhere else: `result_error` (D11's tool-level failure, the `error` key a tool returns instead of throwing) and **`result_found`** (the tool's own `found` flag, for `read_wikipedia` and `get_region_climate`; null elsewhere). A miss is not an error, and without `result_found` a case asserting "answered from a source" is satisfied by a source that had nothing (D40) |
| `cost` | numeric | Table 11 | |
| `latency_ms` | integer | Table 11 | |
| `token_count` | integer | Table 11 | |

### State reset is a precondition, not a field (D03)

Table 11 lists "confirmation of state reset between repetitions" as a recorded
data point. It is implemented instead as **a check that runs before a run starts
and refuses to start it if the slate is not clean**.

The reasoning: as a logged field it is near-constant by construction — a run
that proceeded would always carry `true`, so the column evidences nothing. As a
gate it does the work invariant 1 actually asks for ("assert on this; do not
assume it"), because a dirty state produces no run rather than a run with a
quiet flag on it.

Table 11 says so too. The row now reads "Confirmation of state reset between
repetitions; **Necessary precondition, else no run**" (author, 2026-09-17), so
the implementation and the published schema agree and no reader has to infer it.

One consequence worth holding on to: **a refusal is still worth recording** —
not as a run field, since no run exists, but so that "the harness refused to
start" is distinguishable from "nobody ran it". A line in the harness log is
enough; this is not a schema question.

---

## Test case level

*Simulation only.*

| Field | Type | Source | Notes |
|---|---|---|---|
| `case_id` | text | Table 11 | |
| `base_case_id` | text \| null | Table 11 | Null for a seed case; set for a metamorphic derivation |
| `run_priority` | integer | Table 11 | |
| `declared_constraints` | — | Table 11 | See the open question below |
| `expected_tool_sequence` | jsonb | Table 11 | |
| `scoring_criteria` | — | Table 11 | Point-wise for baseline, pair-wise for regression (§3.4) |
| `provenance` | enum `seeded` \| `metamorphic` \| `retained` | Table 11 | |
| `repetitions_n` | integer | extension | 8 for seeds, 4 for expanded (D21) |
| `fixture_ids` | jsonb | extension (D26) | The ids the fixture build produced for this repetition — trip, blocks, days, slots, regions by name. New every repetition, and the only way to resolve a `study_mutations` `row_id` or a slot id in `resulting_state_shape` back to the stop it names |
| `build_mutation_ids` | uuid[] | extension (D38) | The `study_mutations` rows this repetition's fixture build wrote, before the case began. Since D38 nothing is deleted between repetitions, so the build's own writes sit on the trip beside the case's; the runner and the checker both exclude these by id. Recorded rather than inferred — the inference is available but an argument, and the ids are a fact |
| `structural_findings` | jsonb | extension (D41) | The checker's findings for this execution, an ordered array of strings. Empty when `structural_outcome` is `none`. A check is a claim about the execution and not about one turn (D27), so the findings sit beside `structural_outcome` on this row rather than on `study_verdicts`, which is keyed per suggestion |

**Representation (D19):** hybrid — declarative YAML keys for the common checks,
named Python predicates in `cases/predicates.py` for sequence-dependent ones.

---

## Suggestion level

*Both rounds. This is the comparison unit and the part that must exist in the
live application.*

| Field | Type | Set by | Source | Notes |
|---|---|---|---|---|
| `suggestion_id` | uuid | app | Table 11 | |
| `conversation_id` | uuid | app | Table 11 | Maps to `chat_messages` / `tonic_runs` in this repo |
| `turn_index` | integer | app | Table 11 | |
| `user_turn` | text | app | Table 11 | **Recorded verbatim** |
| `resulting_state_shape` | jsonb | app | Table 11 | |
| `structural_check_outcome` | enum `none` \| `detected` | **nobody — not written** | Table 11 | **Superseded 2026-09-23 (D73).** A structural verdict belongs to an EXECUTION, not a turn, and is written to `study_case_executions.structural_outcome` / `.structural_findings` (ruling of 2026-09-21). Structural checking is simulation-only: the cases match the simulated fixture closely and do not transfer to a participant's own trip — measured, 10 of 20 check keys are fixture-anchored and `trip_after` is in all 29 cases, so no case transfers whole. The column stays for the record; nothing populates it |
| `request_type` | text | derived | Table 11, §4.2.2 | **Bucketed class label from the tool calls made**, assigned at suggestion completion |
| `session_id` | uuid FK | app | Table 11 (author addition) | Joins a suggestion to its session, and so to `run_type` |
| `user_action` | enum `accepted` \| `rejected` \| `ignored` \| `user_initiated` | app | Table 11 | Indirect feedback (§4.2.2). `ignored` throughout — the manuscript's `left` was renamed 2026-09-17 (D05) so Table 11 and Table 12 agree |
| `thumb_feedback` | enum `up` \| `down` \| null | app | Table 11 | Direct feedback, per agent message |
| `retry_count` | integer | app | Table 11 | |
| `error_code` | text \| null | app | Table 11 | Where a check or API call fails |

**Suggestion = agent turn (D08).** Every turn writes exactly one reply row, so a
control on every agent message *is* feedback at suggestion level; it is stored
in `study_feedback` keyed by the reply's message id. `resulting_state_shape` is
the compact shape plus post-turn counts of D10; `error_code` is the closed set
of D11; `user_turn` is a copy with the chat row id beside it (D06).

**When `ignored` is written (D17):** a scheduled job stamps it on rows older
than 24 hours whose `user_action` is still null; nothing ever overwrites a
non-null value. **Granularity (D12):** the app also appends one
`study_user_actions` row per target (slot, place, edits); the turn-level column
follows the rule any-slot-accepted → `accepted`, all-rejected → `rejected`,
else `ignored`; a reverted live edit is `rejected`; `user_initiated` is derived
in analysis, never written by the app.

---

## State mutation level

*Both rounds.*

| Field | Type | Set by | Source | Notes |
|---|---|---|---|---|
| `mutation_id` | uuid | app | Table 11 | |
| `origin_suggestion_id` | uuid \| null | app | Table 11 | **Linked to the suggestion that produced it** |
| `origin_kind` | enum | app | §3.3 | Agent-originated vs user-originated; null link is not enough to tell them apart |

**Scope and values (D13):** `trip_blocks`, `itinerary_slots`, `itinerary_days`,
`ai_suggestions`, `branches`; `origin_kind ∈ {agent_live_edit,
agent_draft_accepted, agent_place_added, user_manual, system}`, captured by
triggers reading the `x-study-origin` request header.

---

## General level

| Field | Type | Source | Notes |
|---|---|---|---|
| `occurred_at` | timestamptz | Table 11 | Exact timestamp |
| `device_type` | text | Table 11, §4.2.2 | From accessible browser info; attached to logged suggestions |

---

## Derived labels — Table 12

Not stored; computed in analysis from `structural_check_outcome` and
`user_action`. Recorded here so the derivation is versioned with the schema.

> **Open (2026-09-23, Q27).** As written this table needs both inputs, and
> after D73 no round produces both: the simulated round has structural
> verdicts and no `user_action` (the simulator declines in prose, it never
> accepts or rejects a suggestion — observed 0 of 32 turns), and the
> participant round has `user_action` and, by the same ruling, no structural
> verdict. The derivation therefore cannot be computed as specified. It needs
> the author's decision before the participant round; the options are in
> `OPEN_QUESTIONS.md`.

| Structural defect | User action | Label | Interpretation |
|---|---|---|---|
| None | Accepted | Positive | Structurally sound and accepted |
| None | Ignored | Neutral | Structurally sound |
| None | Rejected | Lacks quality | Structurally sound, but rejected |
| Detected | Any | Failure | The system failed to produce a valid suggestion |
| None | Feedback | Thumb up | Indication the suggestion was helpful |
| None | Feedback | Thumb down | Indication the suggestion was not helpful |

Table 11 and Table 12 both say `ignored` (D05); when it is written is D17.

---

## Retention and access

Consent commitments depend on facts outside this repo. Confirm both before
writing the participant information sheet:

- **Region.** Where the Supabase project is hosted determines what the
  participant information says about where data is processed and stored.
- **Row-level security and read access.** "The data stays in Supabase" is only a
  safeguard if access is actually restricted. State who can read participant
  rows.

## Field → writer

Added by task A01 (2026-09-18) with the migration
`supabase/migrations/20260918090000_study_instrumentation.sql`. Every field
above maps to a column; "writer" names the code path that fills it, by plan
task. A13 verifies each writer actually wrote.

| Field (level) | Column | Writer |
|---|---|---|
| `session_id`, `user_id`, `run_type`, `consent_version`, `consent_at`, `device_type` (session) | `study_sessions.id / user_id / run_type / consent_version / consent_at / device_type` | study API on consent (A12); `declined_at` on decline; `client_session_id` from the `X-Session-Id` header |
| `survey_demographics.*` | `study_survey_demographics.*` | study API on submit (A12), from the form (A08) |
| `survey_post_task.*` | `study_survey_post_task.*` | study API on submit or dismiss (A12), from the dialog (A09) |
| `suggestion_id`, `conversation_id`, `turn_index`, `user_turn` | `study_suggestions.id / run_id / turn_index / user_turn` (+ `user_message_id`) | turn logger at turn start (A02) |
| `resulting_state_shape`, `request_type`, `retry_count`, `error_code`, tokens, latency, model, trace | `study_suggestions.resulting_state_shape / request_type (+ _rule_version) / retry_count / error_code / tokens_* / latency_ms / model_version / model_released_on / tool_call_trace / llm_calls / tool_calls / completed_at / reply_message_id` | turn logger at turn end (A02); `request_type` via A03 |
| `session_id` (suggestion) | `study_suggestions.session_id` | turn logger, from the caller's consented session (A02) |
| `structural_check_outcome` | **`study_case_executions.structural_outcome` + `.structural_findings`** for simulation, because a check describes the execution and not a turn (D27, D41); `study_verdicts` for post-hoc verdicts over participant rows, which have no case. `study_suggestions.structural_check_outcome` is left null in simulation — A13 already exempts it | harness / analysis — never the app |
| `user_action` | `study_suggestions.user_action`, with the per-target record in `study_user_actions` | A05 on accept/reject/revert; the `study-finalize-ignored` job after 24 h (D17) |
| `thumb_feedback` | `study_feedback.value`, keyed by `chat_message_id` = the reply row | thumbs control via the study API (A06, A12) |
| `mutation_id`, `origin_suggestion_id`, `origin_kind` | `study_mutations.id / origin_suggestion_id / origin_kind` (+ `table_name`, `row_id`, `op`, `changed_keys`, `projection`, `actor_user_id`, `session_id`) | triggers on the plan tables reading `x-study-origin` (A04) |
| `occurred_at`, `device_type` (general) | `study_suggestions.occurred_at / device_type` (device also on the session) | turn logger (A02), from the `X-Device-Type` header (A11) |
| run level | `study_runs.*` (`baseline_ref` is a run id; cost as `cost_usd`) | runner (B07), versions from `GET /api/study/versions` (A10) |
| test case level | `study_case_executions.*` (`repetitions_n`, `provenance`, constraints, criteria, `suggestion_ids`, `fixture_ids`) | runner (B07) from the case loader (B03) and the fixture rebuild (B02) |

## Changes to this file

Adding a field is additive and cheap. **Removing or renaming one after the
participant round has started is not possible** — it invalidates the comparison
between rounds. After Phase A ships, changes here go through `DECISIONS.md`.
