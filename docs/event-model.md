# Event model

> **STATUS: reviewed by the author, 2026-09-17.** Derived from Table 11, Table 12
> and the prose of §3.3 and §4.2.2 of the manuscript, then corrected. Field names
> and types remain **proposals** — the manuscript names the data points, not the
> schema — but the open questions that blocked Phase A have been ruled on and are
> recorded in `DECISIONS.md` (D02, D03, D05).
>
> Three **`TODO(author)`** markers remain, none of which blocks Phase A. They are
> where the manuscript is silent and a guess would be invisible later.

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
| `run_type` | enum `pilot` \| `study` | app, at session creation | extension | Never inferred later from timestamp or email |
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

**`TODO(author)`** — response scales and coding for the demographic items and
the two UMUX-LITE items. UMUX-LITE is conventionally 7-point; fix it before the
pilot, since rescaling after collection is not possible.

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
| `tool_call_trace` | jsonb | Table 11 | Ordered; the coverage signature in P1 is built from it |
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
| `repetitions_n` | integer | extension | **Threshold — requires a decision** |

**`TODO(author)`** — `declared_constraints` has no stated representation.
Declarative schema, predicates, or hybrid is exactly the kind of choice that
belongs in `DECISIONS.md` before code exists, not after.

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
| `structural_check_outcome` | enum `none` \| `detected` | harness | Table 11 | Drives the label in Table 12 |
| `request_type` | text | derived | Table 11, §4.2.2 | **Bucketed class label from the tool calls made**, assigned at suggestion completion |
| `session_id` | uuid FK | app | Table 11 (author addition) | Joins a suggestion to its session, and so to `run_type` |
| `user_action` | enum `accepted` \| `rejected` \| `ignored` \| `user_initiated` | app | Table 11 | Indirect feedback (§4.2.2). `ignored` throughout — the manuscript's `left` was renamed 2026-09-17 (D05) so Table 11 and Table 12 agree |
| `thumb_feedback` | enum `up` \| `down` \| null | app | Table 11 | Direct feedback, per agent message |
| `retry_count` | integer | app | Table 11 | |
| `error_code` | text \| null | app | Table 11 | Where a check or API call fails |

**`TODO(author)`** — Table 11 records `thumb_feedback` at suggestion level, but
§4.2.2 puts a thumbs control on **every agent message**. A message is not always
a suggestion. Either the control is restricted to suggestion messages, or
feedback needs its own level keyed to the message. This one changes the UI.

**`TODO(author)`** — the naming is settled (`ignored`); **when to write it is
not.** `accepted` and `rejected` have observable triggers. `ignored` is the
absence of one, so it needs a rule: is it written when the session ends, after a
fixed interval, or when the conversation moves on by some definition? Until that
rule exists the application cannot write the value at all, and §4.3's label
distribution rests on it. Distinct from the rename — this is the operational
definition, not the word.

---

## State mutation level

*Both rounds.*

| Field | Type | Set by | Source | Notes |
|---|---|---|---|---|
| `mutation_id` | uuid | app | Table 11 | |
| `origin_suggestion_id` | uuid \| null | app | Table 11 | **Linked to the suggestion that produced it** |
| `origin_kind` | enum | app | §3.3 | Agent-originated vs user-originated; null link is not enough to tell them apart |

**`TODO(author)`** — which trip mutations are in scope? This repo mutates
`trip_blocks`, `itinerary_slots`, `branches`, `trip_todos` and more. Logging all
of them is cheap; deciding afterwards which ones counted is not possible.

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

| Structural defect | User action | Label | Interpretation |
|---|---|---|---|
| None | Accepted | Positive | Structurally sound and accepted |
| None | Ignored | Neutral | Structurally sound |
| None | Rejected | Lacks quality | Structurally sound, but rejected |
| Detected | Any | Failure | The system failed to produce a valid suggestion |
| None | Feedback | Thumb up | Indication the suggestion was helpful |
| None | Feedback | Thumb down | Indication the suggestion was not helpful |

Table 11 and Table 12 now both say `ignored` (D05). The remaining question is
when the application writes it — see the suggestion level above.

---

## Retention and access

Consent commitments depend on facts outside this repo. Confirm both before
writing the participant information sheet:

- **Region.** Where the Supabase project is hosted determines what the
  participant information says about where data is processed and stored.
- **Row-level security and read access.** "The data stays in Supabase" is only a
  safeguard if access is actually restricted. State who can read participant
  rows.

## Changes to this file

Adding a field is additive and cheap. **Removing or renaming one after the
participant round has started is not possible** — it invalidates the comparison
between rounds. After Phase A ships, changes here go through `DECISIONS.md`.
