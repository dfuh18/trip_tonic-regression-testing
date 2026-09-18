# Implementation plan

Produced by the `/thesis-plan` session on 2026-09-17 (Fable tier), from the
manuscript revision `MA_Thesis_Gian Andri Hofmann_260917.docx` (§1.4, §3.1,
§3.3, §3.4, §4.2.1–4.2.3, §4.3, plus §2.5.1 for the metamorphic relations),
`docs/event-model.md` as reviewed by the author the same day, and a survey of
the application code Phase A attaches to. Revisions go through `/thesis-resume`
and are recorded in `DECISIONS.md`.

## Task format

```markdown
### T07 — Structural checker: constraint evaluation
Phase: B
Tier: [STANDARD]
Depends on: T03, T05
Estimate: 3h
Status: not started
Spec: <precise enough that no design decision remains>
Done when: <observable condition>
```

`Status` is one of: `not started` · `in progress` · `done` · `blocked`. A
`blocked` task names what it is blocked on — usually a `Q` id in
`OPEN_QUESTIONS.md`.

## The three rules the plan must satisfy

**1. Tier.** Tag a task `[STANDARD]` only if a session starting with **no prior
context at all** could execute the spec without making a design decision.
Subagents start cold — they do not inherit the dispatching session's context, so
a `[STANDARD]` spec has to be self-contained or it cannot be executed. If it
cannot be specified that tightly, it is `[FABLE]`.

**2. Estimate.** Every task carries one, `[FABLE]` and `[STANDARD]` alike.
`IMPLEMENTATION_LOG.md` records effort *relative to estimate*, and an estimate
written after the work is not an estimate. Rough is fine.

**3. Phase.** A, B or C, per `CLAUDE.md`. Phase B consumes what Phase A emits.
Phase C must be validated against simulated data before the participant round
opens — that gate is itself a task (C03), and it is the one task in the plan
that cannot be skipped or reordered.

## Progress

| Phase | Tasks | Done | Blocked |
|---|---|---|---|
| A — application instrumentation | 13 (9 `[FABLE]`, 4 `[STANDARD]`) | 5 | 0 |
| B — pipeline stages 1 to 3.2 | 14 (11 `[FABLE]`, 3 `[STANDARD]`) | 2 | 0 |
| C — analysis and pilot | 6 (6 `[FABLE]`, 0 `[STANDARD]`) | 0 | 1 |

Estimate total: about 152 h (A 51.5 h · B 73.5 h · C 27 h). Vertex compute for
the simulation runs is not in these numbers.

**Rulings landed 2026-09-17/18 (D06–D24):** every Phase A and Phase B task is
unblocked; only C02 waits, on Q02 (§4.3). Specs below cite the decision they
build on. Dispatchable `[STANDARD]` tasks with no open dependency: A03, A10,
A11, B13, B14 (A08 and B12 once A07/A12 and B14 exist).

---

## What Phase A attaches to

Written down so the Phase A specs are against the application as it is, not as
guessed. Every path here was read during planning.

**One agent turn.** `POST /api/ai/agent/chat` → `AgentService.chat()`
(`apps/api/src/routes/ai/agent/agent.service.ts`). The member's own message is
inserted into `chat_messages` **by the browser** before the call
(`hooks/use-realtime-chat.tsx`), and its id travels as `message_id`. The service
resolves a `tonic_runs` row (the conversation — every turn belongs to one), builds
an ADK `LlmAgent` with tools closing over the caller's RLS client, runs it with
`AgentObservabilityPlugin` (`agent.plugin.ts`) which sees every LLM round-trip
and every tool call (`before/after/onError` callbacks, args and results), and
persists exactly one reply row (`chat_messages`, `message_type = 'ai'`,
`metadata.agent = {model, tokensUsed, intent, edits?}`) plus one
`api_usage_events` row (tokens, model, latency, `status`, `agent_intent`,
`metadata.{llmCalls,toolCalls,editCount,draftCount}`). On failure a `system`
row is written under the run and the request throws 502/504.

**What a turn produces.** Places surfaced by `search_places` become `place` refs
on the reply; `propose_plan` inserts an `ai_suggestions` row (`suggestion_type =
'itinerary'`, `suggested_data.days[].slots[]`) and expires the trip's previous
pending draft; `move_slot`/`unschedule_block`/`schedule_block` write the live
itinerary immediately and journal `AppliedEdit`s onto the reply for undo. Tool
failures are **returned** as `{error}` results, never thrown.

**How a member reacts.** Accept or reject one draft slot: `PATCH
/trips/:tripId/drafts/:id/slots/:i` (`drafts.service.ts` → RPC
`apply_draft_slot_verdict`, stamps `accepted_at/_by` or `rejected_at/_by` into the
slot; then the web creates the block and slot via the blocks and itinerary
APIs — `lib/draft-accept.ts`). Whole draft: `POST /api/ai/suggestions/action`
(`ai.service.ts handleSuggestionAction`, sets `ai_suggestions.status`). Add a
place Tonic named: `components/chat/use-add-place-to-trip.ts` → `POST
/trips/:tripId/blocks` with `source: 'ai_suggestion'`; the same places are also
pushed into the map's suggestion pool (`notifyPlacesSuggested`) and can be added
from there. Undo a live edit: `POST /api/ai/agent/revert`. Reject a ghost slot:
`use-ghost-draft.ts`, `use-artifact-slot-actions.ts`.

**What does not exist.** A prompt or tool version identifier. A study session,
enrolment or server-recorded consent (`lib/consent.ts` is cookie consent in
localStorage). A thumbs control (👍/👎 exist only as social `chat_reactions`).
Any origin on `itinerary_slots` rows (`trip_blocks.source` exists). A device
type anywhere. `retry_count` — retries happen inside `adk-llm.ts` below the
plugin.

**Constraints every Phase A task inherits.** The database grants nothing by
default: a new table needs `GRANT` and RLS in the same migration, and
`security-audit/permissions.test.ts` (CI) fails a PR whose code touches a table
its role cannot reach, and fails one whose new table with a `user_id` is neither
in `EXPORT_BY_USER_ID` nor `EXPORT_EXCLUDED` (`account.export-tables.ts`). The
retention job deletes `expired` `ai_suggestions` after 90 days, so a study row
must not depend on a draft row surviving (FK `SET NULL`, snapshot what it
needs). Frontend files stay under 250 lines. Changes under `apps/` are additive
(root `CLAUDE.md`, rule 4): every logging call is fire-and-forget and never
throws into the request; no existing request path or response shape changes.
Instrumentation is written for one deployable `apps/` — there is no study
build; `run_type` and enrolment decide what a row means, not a flag on the
server.

---

## Phase A — application instrumentation

### A01 — Study schema migration
Phase: A
Tier: [FABLE]
Depends on: —
Estimate: 4h
Status: done (2026-09-18; pushed to the linked project after repairing the unrecorded 20260915074919 history entry; both DB-free suites pass)
Spec: One migration under `supabase/migrations/` creating every table the event
model needs in the live application, `study_`-prefixed in `public`:
`study_sessions` (session level per D16: `id`, `user_id`, `run_type` ∈ `pilot |
study | simulation` (D15), `consent_version`, `consent_at`, `declined_at`,
`device_type`, `client_session_id`, `created_at`),
`study_survey_demographics` and `study_survey_post_task` (D02; one row per
session; columns and scales per D18 — `age integer`, text codes for the other
three, UMUX-LITE and recommend as `integer` 1..7),
`study_suggestions` (suggestion level: every field in event-model.md plus
`chat_message_id` of the user turn and of the reply, `run_id`, `trip_id`,
`tool_call_trace jsonb`, `llm_calls`, `tokens_input`, `tokens_output`,
`latency_ms`, `model_version`, `model_released_on`, `request_type_rule_version`,
`structural_check_outcome` nullable — set only by the harness/analysis),
`study_user_actions` (per-target rows, D12), `study_feedback` (D08: `session_id`,
`chat_message_id`, `value up|down`, unique per member and message),
`study_mutations` (D13: `table, row_id, op, changed_keys, projection,
origin_suggestion_id, origin_kind, actor_user_id, occurred_at`), and, for the
harness, `study_runs` and
`study_case_executions` (run and test-case levels — written by the service key
only, no `authenticated` grant). `study_verdicts` (structural checker output,
append-only, `suggestion_id + checker_version` unique) also lands here so the
app rows are never updated by analysis. RLS: participants insert their own
session/survey/feedback rows and read nothing back except their own session
(the post-task trigger needs the count); no member reads another's rows; no
admin policy — analysis reads with the service key (privacy decision). Grants
per `CLAUDE.md` "a policy is not a permission". Every reference to the
participant is `ON DELETE CASCADE` (D14); references to `ai_suggestions` are
`SET NULL`. `account.export-tables.ts`: the two survey tables and
`study_suggestions` in `EXPORT_BY_USER_ID`; `study_user_actions`,
`study_feedback`, `study_mutations`, `study_verdicts` in `EXPORT_EXCLUDED` with
reasons (D14). Also in this migration: the pg_cron job of D17 (daily, stamps
`user_action = 'ignored'` on `study_suggestions` rows older than 24 h whose
`user_action` is null) and a trigger that rejects any update changing a
non-null `user_action`. Add a "Field → writer" column to `docs/event-model.md` naming the table and
column for every field (this is what A13 verifies).
Done when: `pnpm db:push` applies cleanly to the study project; `node --test
security-audit/permissions.test.ts` and `schema-hardening.test.ts` pass; every
field in `docs/event-model.md` maps to a column, and the mapping is written into
that file.

### A02 — Turn logger and trace plugin
Phase: A
Tier: [FABLE]
Depends on: A01, A03, A10, A11
Estimate: 6h
Status: done (2026-09-18; offline tests pass; live turn from a consented throwaway user produced one row with every app-set field populated, a non-participant's turn produced none)
Spec: A `StudyTracePlugin` (second ADK `BasePlugin`, registered beside
`AgentObservabilityPlugin`, never replacing it) that accumulates an ordered
`tool_call_trace`: for each tool call `{seq, tool, args, started_at,
duration_ms, result_error: string | null, result_chars}` — args verbatim (P1
needs the parameters), results summarised to `error` and size — and for each LLM
call `{seq, model, tokens_in, tokens_out, duration_ms}`. A `StudyTurnLogger`
(`apps/api/src/routes/ai/agent/agent.study-log.ts`) that (1) at turn start,
after the run is resolved, looks up the caller's latest consented, undeclined
`study_sessions` row (D16 — none → the logger is a no-op for this turn, nothing
else changes),
generates the `study_suggestions` id and inserts the row with `user_turn`,
`turn_index` (count of the caller's prior turns in this run + 1),
`conversation_id = run.id`, `device_type` from the `X-Device-Type` header (A11),
`occurred_at`; (2) at turn end — success or the catch block — updates it with
the trace, counts, `model_version` and `model_released_on` (from `lib/env.ts`
when the reported model equals `DEFAULT_VERTEX_MODEL`, else the reported id and
null), `latency_ms`, `error_code` from `timeout | llm_call_limit | empty_reply | llm_error |
persist_failed | other` (D11), `retry_count` (from a counter added to
`VertexExpressGemini` and read after the run, D11), `resulting_state_shape`
per D10 — `{draft: {suggestion_id, days, slots, slot_types[]} | null, edits:
{move, unschedule, schedule}, places_surfaced, reply: {chars, place_refs,
draft_refs}, trip_after: {blocks, slots}}`, the last from two count queries —
`request_type` via A03 with its rule version (D09), `user_turn` copied verbatim
with its `chat_messages.id` (D06), and the reply's `chat_message_id`. Both writes use the admin client
(the row is not the member's to read), are awaited nowhere on the response
path (`void … .then(log error)`), and are wrapped so an exception can never
reach the request. No existing log line, response field or ordering changes.
Done when: an offline test (`node --test`) drives the plugin with synthetic
callbacks — including a tool result carrying `error` — and asserts the trace
shape; a turn on the dev server against a consented session produces one
`study_suggestions` row with every app-set field non-null; a turn without a
session produces no row and an identical reply; `pnpm --filter api test` passes.

### A03 — `request_type` classifier
Phase: A
Tier: [STANDARD]
Depends on: —
Estimate: 2h
Status: done (2026-09-18, standard subagent; reviewed R01)
Spec: Create `apps/api/src/routes/ai/agent/agent.request-type.ts` exporting
`REQUEST_TYPE_RULE_VERSION` (a string constant, `'1'`) and
`classifyRequestType(toolNames: ReadonlyArray<string>): RequestType` where
`RequestType = 'scheduling' | 'venue_lookup' | 'factual_qa' | 'advisory'`,
by this precedence (D09): `'scheduling'` if `toolNames` contains any of
`propose_plan`, `move_slot`, `unschedule_block`, `schedule_block`; else
`'venue_lookup'` if it contains `search_places`; else `'factual_qa'` if it
contains any of `get_weather`, `get_climate_normals`, `read_wikipedia`,
`get_region_climate`; else `'advisory'` (this covers the empty list and lists
holding only `get_trip_details`, `list_trip_blocks`, `get_itinerary`). Pure function, no imports from
`@google/adk`. Add `agent.request-type.test.ts` beside it (node test runner,
same style as `agent.tool-policy` tests in `agent.e2e.test.ts`) with one case
per label, one mixed-family case per precedence step, and the empty list.
Done when: `pnpm --filter api test` passes including the new file; the function
is exported and unused by anything else (A02 wires it).

### A04 — Mutation origin tracking
Phase: A
Tier: [FABLE]
Depends on: A01
Estimate: 6h
Status: not started
Spec: Per D13: `AFTER INSERT OR UPDATE OR DELETE` triggers on `trip_blocks`,
`itinerary_slots`, `itinerary_days`, `ai_suggestions`, `branches` writing `study_mutations` rows `{id, table, row_id, op,
changed_keys, projection, origin_suggestion_id, origin_kind, actor_user_id,
occurred_at}`; origin read from the PostgREST request header
`x-study-origin` (`current_setting('request.headers', true)`), value
`<suggestion_id>:<origin_kind>` with `origin_kind ∈ {agent_live_edit,
agent_draft_accepted, agent_place_added}`; absent header → `user_manual`; writes by
SECURITY DEFINER functions and the retention job → `system`. Header senders: the
per-turn client the agent tools use (built in `AgentService.chat` from the same
JWT with the extra header, passed to `buildAgentTools` in place of
`this.supabase` — the only change to the agent's construction, and it changes
no query); the web `api-client.ts` (optional `studyOrigin` on `apiRequest`) on
the accept-slot, accept-all, add-place-from-chat and add-from-suggestion-pool
paths; the browser Supabase client on direct writes in scope, via
`.setHeader()`. Rows are written only when the actor has an active study
session (trigger checks `study_sessions`), so members outside the study leave
no rows. The migration lives in the same file as A01 or a second one — one
`db:push` either way.
Done when: on the dev server, each of the five origin kinds is produced by the
path that should produce it (a table in the task's PR description lists path →
row), a write without a session produces no row, `permissions.test.ts` passes,
and the trigger is covered by `schema-hardening.test.ts`'s definer/search_path
invariants.

### A05 — User action capture
Phase: A
Tier: [FABLE]
Depends on: A01, A02
Estimate: 5h
Status: not started
Spec: Append `study_user_actions` rows (`suggestion_id`, `target` ∈ `slot:<i>` |
`place:<google_place_id>` | `edits`, `action`, `actor_user_id`, `at`) and
maintain `study_suggestions.user_action` by the D12 rule — any slot accepted →
`accepted`; every slot rejected → `rejected`; a reverted live edit → `rejected`;
otherwise left null for the D17 job — at: slot verdict (`drafts.service.ts applySlotVerdict`, only when
`applied === true`), whole-draft accept/reject (`ai.service.ts
handleSuggestionAction`), add-place-from-reply and from the suggestion pool
(the `POST /trips/:tripId/blocks` handler when the body carries `source =
'ai_suggestion'` and an `x-study-origin` header names a suggestion), and revert
(`agent.service.ts revert` → `rejected` for the suggestion whose reply carries
the edits). The `ignored` finalisation is the pg_cron job from A01 (D17) and only ever
fills a null. `user_initiated` is never written here (D12). Every write is admin-client, fire-and-forget, never on the response path.
Done when: each trigger path above produces the expected action row and column
value on the dev server; a suggestion left alone acquires `ignored` from the job (run it by hand with
a shortened interval on the dev database) and nothing else ever overwrites a
non-null `user_action` (the A01 trigger); `pnpm --filter api test`
passes.

### A06 — Thumbs control on agent replies
Phase: A
Tier: [FABLE]
Depends on: A01, A12
Estimate: 3h
Status: not started
Spec: Per D08: a two-button control rendered under every
`message_type = 'ai'` bubble in `chat-message-item.tsx` (extracted into
`chat-thumb-feedback.tsx` to keep the file under 250 lines), visible only when
the viewer has an active study session (from a `useStudySession()` hook, A07),
Phosphor icons, `coarse:` 44 px hit areas, writes `study_feedback {session_id,
chat_message_id, value up|down, at}` through the study API (A12), toggles and
changes in place, one row per member per message (upsert). The control is
chrome-neutral: no `highlight`, no Tonic violet on the buttons themselves.
Done when: a participant can rate any Tonic reply up or down and change their
mind; a non-participant sees no control; the row lands with the message id that
joins to `study_suggestions.reply_message_id`; `pnpm typecheck` and `pnpm lint`
pass.

### A07 — Enrolment, consent and study routes (web)
Phase: A
Tier: [FABLE]
Depends on: A01, A12
Estimate: 8h
Status: not started
Spec: Per D16. Routes under `apps/web/src/routes/`: a public
`/study/join` (reads `cohort`, stores enrolment, sends the visitor to login or
sign-up with `redirect` preserved), and under `_protected`: `/study/consent`
(the university template text with a `CONSENT_VERSION` constant beside it, an
explicit accept action using `variant="cta"` and a decline action), `/study/
demographics` (hosts A08's form), `/study/declined`. The `_protected` loader
gains one condition mirroring the `onboarded` gate: an enrolled user with no
consented session is redirected to `/study/consent` from every protected route;
this is the "cannot be bypassed by URL or back button" property, and Back from
the app cannot land on consent because consent navigates with `replace`.
Consent creates the `study_sessions` row through A12 (server records
`consent_at`, `consent_version`, `run_type` from the cohort, `device_type` from
A11). Declining records `declined_at`, clears enrolment, signs out. A
`useStudySession()` hook exposes the active session (or null) to A06 and A09.
Files stay under 250 lines each; MOBILE.md rules apply even though the study
excludes phones.
Done when: the pilot checklist in `CLAUDE.md` passes on the dev server: consent
cannot be skipped by URL or Back, is recorded with a version, declining exits
cleanly, and `run_type` is `pilot` or `study` according to the link used;
`pnpm typecheck`, `lint` and the web build pass.

### A08 — Demographic questionnaire form
Phase: A
Tier: [STANDARD]
Depends on: A07, A12
Estimate: 3h
Status: not started
Spec: Create `apps/web/src/components/study/demographics-form.tsx` rendered by
the `/study/demographics` route (A07). Fields, in order (D18): `age` — a number input, integer 18..120, required;
`gender` — radio group, stored codes `woman`, `man`, `non_binary`,
`prefer_not_to_say`, labels "Woman", "Man", "Non-binary", "Prefer not to say";
`education_level` — radio group, codes `compulsory`, `vocational`,
`high_school`, `bachelor`, `master_or_higher`, labels "Compulsory school",
"Apprenticeship / vocational", "Matura / high school", "Bachelor", "Master or
higher"; `llm_familiarity` — radio group, codes `never`, `rarely`, `monthly`,
`weekly`, `daily`, labels "Never", "Rarely", "About monthly", "About weekly",
"Daily", under the prompt "How often do you use LLM chatbots such as ChatGPT
or Gemini?". All four required. Use `@workspace/ui` form
primitives, one submit button `variant="cta"` labelled "Continue", client-side
required-field validation, submit via the study API wrapper
`lib/study-api.ts submitDemographics()` (A12), then navigate to `/home` with
`replace: true`. No skip: §4.2.2 makes the questionnaire part of the flow. Under
250 lines.
Done when: submitting writes one `study_survey_demographics` row with every
column populated and navigates on; a second visit to the route with a row
already present redirects to `/home`; `pnpm typecheck` and `lint` pass.

### A09 — Post-task prompt
Phase: A
Tier: [FABLE]
Depends on: A02, A07, A12
Estimate: 4h
Status: not started
Spec: A `Dialog` (overlays are modals, per `CLAUDE.md`) mounted on the trip page
shell for participants only, opened once per session when the session's
suggestion count (from `GET /api/study/session`, polled after each agent turn
the participant sends, or pushed through the existing realtime chat arrival)
reaches three (D07: one row in `study_suggestions` per turn, failed turns
included). Items (D18): UMUX-LITE 1 "Trip Tonic's capabilities meet my
requirements" and 2 "Trip Tonic is easy to use", each 1..7 strongly disagree →
strongly agree; `real_trip` yes/no "Were you planning an actual upcoming
trip?"; `likelihood_to_recommend` 1..7; optional free text. Submit writes
`study_survey_post_task` with `submitted_at`; dismiss writes the row with
`dismissed_at` and whatever was filled; the dialog never reopens (server-side:
a row exists). Partial rows are legal (event-model.md).
Done when: on the dev server the dialog opens exactly once after the third
interaction as defined by D07, not before, not on the fourth; submit
and dismiss each produce the documented row; a reload after either does not
reopen it.

### A10 — Version identifiers
Phase: A
Tier: [STANDARD]
Depends on: —
Estimate: 2h
Status: done (2026-09-18, standard subagent; reviewed R01; live curl pending a running dev server)
Spec: Create `apps/api/src/lib/study-versions.ts` exporting `getStudyVersions()`
returning `{ model_version, model_released_on, git_sha, prompt_version,
tool_version, computed_at }` where: `model_version = env.VERTEX_MODEL ??
DEFAULT_VERTEX_MODEL`; `model_released_on = DEFAULT_VERTEX_MODEL_RELEASED` when
`model_version === DEFAULT_VERTEX_MODEL`, else `null`; `git_sha` = the contents
of `process.env.GIT_SHA` if set, else the output of `git rev-parse HEAD` run once
at module load with `child_process.execSync` inside a try/catch (null on
failure — the Docker image has no `.git`); `prompt_version` = first 12 hex chars
of the SHA-256 of the UTF-8 source of `routes/ai/agent/agent.prompts.ts`;
`tool_version` = first 12 hex chars of the SHA-256 of the concatenated sources
of `agent.tools.ts`, `agent.itinerary-tools.ts`, `agent.tool-policy.ts`,
`define-tool.ts` in that order, joined by `\n`. Read the files with
`fs.readFileSync` from `__dirname`-relative paths; the esbuild bundle is
`--packages=external` and keeps `src` on disk in the image, so resolve relative
to the repository layout, not to `dist`. Cache the result for the process
lifetime. Register `GET /api/study/versions` (authenticated, any user) in a new
`apps/api/src/routes/study/study.routes.ts` that A12 later extends; wire it in
`app.ts` under `/api/study`. Add `study-versions.test.ts` asserting the hashes
are 12 hex chars, stable across two calls, and change when a temp copy of the
prompt file with one extra character is hashed through the same helper.
Done when: `curl` with a valid Bearer against the dev server returns the six
fields; `pnpm --filter api test` and `pnpm typecheck` pass.

### A11 — Device type on the client and as a request header
Phase: A
Tier: [STANDARD]
Depends on: —
Estimate: 1.5h
Status: done (2026-09-18, standard subagent; reviewed R01; API-log observation pending a running dev server)
Spec: Create `apps/web/src/lib/device-type.ts` exporting `getDeviceType(): 'desktop'
| 'tablet' | 'mobile' | 'unknown'`: SSR (`typeof window === 'undefined'`) →
`'unknown'`; if `navigator.userAgentData?.mobile === true` → `'mobile'`; else
if the user agent matches `/iPad|Tablet|Android(?!.*Mobile)/i` → `'tablet'`;
else if it matches `/Mobi|Android|iPhone/i` → `'mobile'`; else `'desktop'`. In
`lib/api-client.ts`, add the header `X-Device-Type: <getDeviceType()>` to every
request, next to the existing `X-Session-Id`, without changing anything else
about the request. Add `device-type.test.ts` (same runner as
`trip-view-search.test.ts`) covering the four outcomes with stubbed
`navigator` objects.
Done when: the header appears on a dev-server request in the API log
(`request.headers['x-device-type']`); the tests pass; `pnpm typecheck` and
`lint` pass.

### A12 — Study API domain
Phase: A
Tier: [FABLE]
Depends on: A01, A10
Estimate: 4h
Status: not started
Spec: `apps/api/src/routes/study/` in the three-file pattern: `POST /session`
(consent: creates `study_sessions` from `{cohort, consent_version}`, `user_id`
from the JWT, `device_type` from the header, rejects a second consented, undeclined session for the same user — D16), `POST /session/decline`, `GET /session` (the caller's active
session with its suggestion count — the post-task trigger's source of truth),
`POST /survey/demographics`, `POST /survey/post-task` (submit or dismiss),
`PUT /feedback` (thumbs upsert). Zod at the boundary; service throws
`AppError`; writes with the admin client after verifying ownership, because
participants hold no read grant on the behavioural tables. `lib/study-api.ts`
on the web wraps each call. Register under `/api/study` in `app.ts` (extending
A10's router).
Done when: each endpoint is exercised on the dev server from the web wrapper;
ownership is enforced (a second user cannot read or write another's session);
`pnpm --filter api test` gains a schema test per endpoint; `permissions.test.ts`
passes.

### A13 — Phase A closure: field traceability and end-to-end check
Phase: A
Tier: [FABLE]
Depends on: A02, A04, A05, A06, A07, A08, A09, A12
Estimate: 3h
Status: not started
Spec: Walk the whole participant flow on the dev server against the showcase
trip with a pilot-cohort link: join → consent → demographics → three agent turns
covering venue lookup, a draft with a slot accepted and one rejected, a live
edit and its undo, one thumbs up, one add-place from the reply → post-task
dialog dismissed. Then, with the service key, assert in a throwaway script that
every field in `docs/event-model.md` marked "app" is non-null in at least one
row, and that the "Field → writer" column from A01 names a writer that actually
wrote. Fix what is missing; record any spec drift in `DECISIONS.md` (agent
decisions only where `CLAUDE.md` allows). Confirm rule 4 by reading the diff of
`apps/` for any changed request path or response shape and listing the two
deliberate exceptions (the `_protected` loader gate for enrolled users; the
per-turn client with the origin header) in `IMPLEMENTATION_LOG.md` if either
proved contentious.
Done when: the assertion script passes; the traceability column is complete;
`pnpm typecheck`, `lint`, `--filter api test`, and both security-audit suites
pass; the branch is ready for `/thesis-review`.

---

## Phase B — pipeline stages 1 to 3.2

Phase B lives in `research/regression-testing/src/` (Python) and drives the
application over HTTP as a member would: sign in as a simulated user, insert
the member message into `chat_messages` with the browser-side client the way
`use-realtime-chat.tsx` does, then `POST /api/ai/agent/chat` with that
`message_id` and an `X-Study-Origin`-free request (the simulator originates
nothing). Reading back what happened is a query on the study tables Phase A
writes, never a parse of the reply text.

### B01 — Harness environment, configuration and simulated users
Phase: B
Tier: [FABLE]
Depends on: B14, A13
Estimate: 4h
Status: not started
Spec: D15 — the existing Supabase project and its deployed API serve both the
simulation and the participant round; there is no separate study project and
no local stack for runs of record. `src/config.py` (from B14) extended with
the API base URL and the simulated users' credentials source; the three model
ids are all `gemini-3.5-flash` (D20). `src/auth.py`: create N simulated users with the admin API
(`auth.admin.create_user`, deterministic emails under a reserved domain, password
from env), sign one in with the publishable key to obtain a JWT, and enrol each
in a `study_sessions` row with `run_type = 'simulation'` (so every turn is
logged by A02). `DEFAULT_SUBSCRIPTION_TIER=pro` on the API for the duration of the runs so
the monthly AI cap never refuses a simulated user (D15). Document the environment in
`src/README.md`.
Done when: `python -m src.auth --check` signs in as each simulated user, prints
only pseudonymous ids, and a hand-sent turn from that JWT produces a
`study_suggestions` row with `run_type = 'simulation'` on its session.

### B02 — Fixture, state reset and the precondition gate
Phase: B
Tier: [FABLE]
Depends on: B01
Estimate: 5h
Status: not started
Spec: `src/fixture.py`: one fixture trip per simulated user (owner + trip +
regions + a small set of saved blocks + itinerary days, dates in the future so
weather and scheduling cases resolve), defined as data in `cases/fixture.json`
— *not* `scripts/showcase-trip.mjs`, which targets super admins at a fixed id and
carries chat history. `src/reset.py reset(trip_id)`: delete the trip's
`chat_messages`, `chat_reactions`, `tonic_runs`, `ai_suggestions`,
`itinerary_slots`, `trip_blocks`, `itinerary_days`, `branches`, and every
`study_*` row scoped to the trip, then rebuild from the fixture. The
**`tonic_runs` deletion is load-bearing**: `RunService.findResumable` joins a
turn to the caller's live run within 30 minutes, so without it repetition two
would land inside repetition one's conversation. `assert_clean(trip_id)`: zero
rows in each of those tables except the rebuilt fixture rows, whose digest
(sorted titles, types, day/time) must equal the fixture's; on failure raise
`DirtyState` with the offending table and write one line to the harness log
(`runs/harness.log`) — D03: a refusal is recorded, a run is not.
Done when: `reset` followed by `assert_clean` passes; a turn followed by
`assert_clean` fails naming `chat_messages`; a second `reset` returns the trip
to a state whose digest equals the first.

### B03 — Case model and loader
Phase: B
Tier: [FABLE]
Depends on: B14
Estimate: 5h
Status: not started
Spec: `cases/<case_id>.yaml` with: `case_id`, `base_case_id`, `provenance`,
`run_priority`, `function` (`venue_lookup | scheduling | factual_qa | advisory`),
`user_profile` (persona text), `goal` (what the simulator wants), `opening_turn`
(verbatim), `expected_tool_sequence`, `declared_constraints` (D19: a `checks:` mapping of declarative keys —
`tool_sequence`, `tool_counts`, `slot_days`, `slot_count`, `mutation_counts`
— validated by the loader, plus an optional `predicates:` list of function
names resolved in `cases/predicates.py`), `scoring_criteria` (the
point-wise rubric, ten-point), `references` (for factual QA: Wikipedia title +
section + the stored text), `repetitions_n`, `metamorphic_relation` for
follow-ups. `src/cases.py`: load, validate (pydantic), and compute
`suite_version` = SHA-256 over the sorted case files. Advisory cases carry
criteria and no constraints; the loader accepts that.
Done when: the loader validates every file in `cases/` and rejects a file
missing any required key with the key named; `suite_version` changes when a
case file changes.

### B04 — Stage 1: seed cases and `sim/01_cases`
Phase: B
Tier: [FABLE]
Depends on: B03
Estimate: 6h
Status: not started
Spec: Author the seed set: two cases per function, eight in all (D21), each a
minimum-functionality scenario generated with LLM help and reviewed by hand
(§3.1), with constraints, expected tool sequence, criteria and — for factual
QA — the retrieved Wikipedia sections stored under `cases/references/`.
`notebooks/sim/01_cases.ipynb` shows every case, its constraints and criteria,
and records which were edited after generation and why. Outputs committed.
Done when: `src.cases` loads the set; the notebook runs top to bottom; the author
has marked each case reviewed in the notebook.

### B05 — Stage 2: metamorphic expansion and `sim/02_expand`
Phase: B
Tier: [FABLE]
Depends on: B04
Estimate: 6h
Status: not started
Spec: `src/metamorphic.py`: one function per relation in D22 (INV-1..4,
DIR-1..4), taking a seed case
and returning a follow-up with `base_case_id`, `provenance = metamorphic`,
inherited criteria, the perturbed `opening_turn`, and the relation's expected
delta expressed in the same constraint representation as B03 (invariance: same
`request_type`, same tool sequence, same structural outcome as the seed's
recorded run; directional: the stated change). `notebooks/sim/02_expand.ipynb`
applies the catalogue — two follow-ups per seed chosen by hand (D21), the
per-function eligibility of D22 — shows each derived case beside its seed, and
records hand edits. Outputs committed.
Done when: the expanded set loads; every follow-up names its relation and its
base; the notebook runs top to bottom.

### B06 — Simulator
Phase: B
Tier: [FABLE]
Depends on: B01
Estimate: 8h
Status: not started
Spec: `src/simulator.py`: an LLM persona (`SIMULATOR_MODEL`, dated) given the
case's profile and goal, which reads the agent's reply from `chat_messages` and
produces the next member turn or declares `done`, up to three turns per
case (D21); `SIMULATOR_MODEL = gemini-3.5-flash` via the `google-genai` SDK
against the Vertex express endpoint with the same key (D20) — add the SDK to
`requirements.txt` here; sends
each turn exactly as the browser does (insert message row → call
`/api/ai/agent/chat` with `message_id`; slash commands only when the case says
so). The simulator prompt is a versioned file under `src/prompts/`. It never
touches the trip directly. Its own tokens are metered into the run's cost.
Done when: one seed case runs end to end against the simulation environment
producing the expected number of `study_suggestions` rows; the transcript is
readable from `chat_messages`; the simulator's prompt version is recorded.

### B07 — Runner
Phase: B
Tier: [FABLE]
Depends on: B02, B03, B06
Estimate: 8h
Status: not started
Spec: `src/runner.py run(suite, n_override=None, priority_only=False)`: opens
a `study_runs` row (run level per event-model.md: `model_version`,
`model_released_on`, `prompt_version`, `tool_version` from
`GET /api/study/versions`; `suite_version` from B03; `baseline_ref`; simulator
and judge model ids; `started_at`), then for each case in priority order and
each repetition (seeds n = 8, expanded n = 4, D21): `reset` → `assert_clean` (refusal aborts the run and is
logged) → simulate → collect the case execution's suggestion ids, traces,
mutations, cost (sum of `tokens_*` × `lib/pricing.ts` rates, mirrored in
`src/pricing.py` with the same `PRICING_VERSION`), latency → write a
`study_case_executions` row. Resumable: a run that stops mid-way continues
from the last completed execution. Concurrency 1 — the Vertex spacing and the
per-minute quota are per user, and independence between repetitions is the
invariant.
Done when: a two-case, n = 2 dry run produces one run row and four execution
rows with every run-level and case-level field non-null; killing the process
mid-run and restarting completes without duplicating an execution.

### B08 — Structural checker
Phase: B
Tier: [FABLE]
Depends on: B03, B07
Estimate: 8h
Status: not started
Spec: `src/checker.py check(case, execution) -> Verdict{outcome: none |
detected, findings: [...], checker_version}` evaluating `declared_constraints`
and `expected_tool_sequence` against the execution's traces,
`resulting_state_shape`s and `study_mutations`, plus the metamorphic delta for
follow-ups (which needs the seed's recorded execution — pass both). Writes
`study_verdicts` (append-only; never updates `study_suggestions`). Findings are
strings a reader can act on ("expected search_places before propose_plan; got
propose_plan first").
Done when: a hand-constructed passing execution and a failing one (a slot on
the wrong day; a missing tool call) produce `none` and `detected` with the
finding named; the checker runs over B07's dry run without error.

### B09 — Judge
Phase: B
Tier: [FABLE]
Depends on: B03
Estimate: 6h
Status: not started
Spec: `src/judge.py`: `score_pointwise(case, reply, references) -> {score
1..10, rationale}` and `compare_pairwise(case, baseline_reply, candidate_reply)
-> {at_least_as_good: bool, rationale}`, both with explicit prompts stored as
versioned files under `src/prompts/` (invariant 6 — no managed evaluation
service), `JUDGE_MODEL = gemini-3.5-flash` (D20 — the judge shares a family
with the agent; §3.7 names it), temperature 0, the case's criteria and
references inlined; `compare_pairwise` calls the model in both orderings and
returns `at_least_as_good` only when both agree (D23); for weather cases the
reference passed is the forecast tool result taken from the execution's trace,
for Wikipedia cases the stored section (D23). The judge sees the user request and the agent's
reply only (P3: blind to user reaction). Judge tokens metered into the run's
cost.
Done when: the two functions run against B07's dry-run replies and return
well-formed results; the prompt files carry a version header that the results
record.

### B10 — Stage 3.1: baseline run and `sim/03_baseline`
Phase: B
Tier: [FABLE]
Depends on: B05, B07, B08, B09
Estimate: 6h (plus compute)
Status: not started
Spec: Execute the full suite once (`run_priority` order, seeds at n = 8,
expanded at n = 4 — D21). `notebooks/sim/03_baseline.ipynb`: per case, the
structural outcomes across repetitions, the point-wise scores, cost and latency;
the top-scoring reply per case shown for review; the author marks the adopted
baseline reply per case in `cases/baseline.json` (`case_id → execution_id`,
`suggestion_id`), which is the `baseline_ref` later runs cite. Outputs
committed. Failures shown, not hidden (§3.5: "one worked example of a failure is
worth more than three of successes").
Done when: `cases/baseline.json` names one execution per case; the notebook runs
top to bottom from the stored run; the run row records every version field.

### B11 — Stage 3.2: regression run and `sim/04_regress`
Phase: B
Tier: [FABLE]
Depends on: B10
Estimate: 6h (plus compute)
Status: not started
Spec: Execute the suite a second time with no configuration change, `baseline_ref`
set. `notebooks/sim/04_regress.ipynb`: pair-wise verdicts against the baseline
per repetition, structural outcomes, the pass rate per case, pass/fail per D23 (seed cases pass only at 8/8,
expanded at ≥ 75 %; a structural `detected` fails the execution outright), variance discussion per §3.1 ("where variability is high,
measures to reduce it are explored"), cost and latency per run. Outputs
committed. Where a finding would change how someone else built this, an
`IMPLEMENTATION_LOG.md` entry.
Done when: every case has a pass rate and a verdict; the notebook runs top to
bottom; the two run rows are distinguishable by `baseline_ref` alone.

### B12 — Coverage signature
Phase: B
Tier: [STANDARD]
Depends on: B14
Estimate: 3h
Status: not started
Spec: Create `src/signature.py` exporting `SIGNATURE_RULE_VERSION = '1'` and
`signature(trace: list[dict], turns: int, request_type: str) -> tuple` where
`trace` is the `tool_call_trace` array from `study_suggestions` (entries with
keys `seq`, `tool`, `args`) and the tuple is `(request_type, sequence, counts, turn_bucket, params)`
where (D24): `sequence` = the tuple of `entry['tool']` in `seq` order with
consecutive duplicates collapsed (`a a b a` → `a b a`); `counts` = a sorted
tuple of `(tool, bucket)` for every distinct tool, bucket `'1'`, `'2'` or
`'3+'` from its number of calls; `turn_bucket` = `'1'`, `'2'` or `'3+'` from
`turns`; `params` = a tuple of four booleans over all `args` values
concatenated as lower-case text — `has_location` (any call has both `lat` and
`lng` args, or a `day_date`-free `address` arg), `has_date` (any arg matches
`\d{4}-\d{2}-\d{2}`), `has_price_term` (matches `cheap|budget|expensive|
€|\$|price|affordable|luxury`), `has_dietary_term` (matches `vegan|vegetarian|
gluten|halal|kosher|dairy|allerg`). Pure,
deterministic, no I/O. `tests/test_signature.py` (pytest): identical traces →
equal signatures; a reordered sequence → different; the bucketing boundaries
(1 → '1', 2 → '2', 3 and 4 → '3+'); consecutive-duplicate collapsing; each of
the four parameter booleans from a sample `args` that sets exactly one.
Done when: `pytest tests/test_signature.py` passes; the function is imported by
nothing yet (C02 uses it).

### B13 — Notebook output check in CI
Phase: B
Tier: [STANDARD]
Depends on: —
Estimate: 1h
Status: done
Spec: Add a job `research-notebooks` to `.github/workflows/security-checks.yml`
after `schema-invariants`: `actions/checkout@v4`, `actions/setup-python@v5` with
`python-version: '3.11'`, then a step with `working-directory:
research/regression-testing` and `run: python tools/check_notebooks.py`. No
dependencies to install (the script is stdlib only). The nbstripout filter
already exists at `research/regression-testing/notebooks/study/.gitattributes`
(the path `nbstripout --install --attributes` writes); add no second attributes
file.
Done when: the workflow file parses (`act -l`, or `yaml.safe_load` when `act`
is not installed); the job passes with the current empty `notebooks/study`;
adding a temporary notebook with an output cell under `notebooks/study` makes
the script exit 1 locally.
Executed 2026-09-18 by the standard subagent; the spec as first written had a
false premise (a root-level ipynb filter) and a self-contradictory `run` path —
both caught by the subagent, corrected here, and recorded in `REVIEW_LOG.md`.
### B14 — Python dependencies and configuration module
Phase: B
Tier: [STANDARD]
Depends on: —
Estimate: 1.5h
Status: done (2026-09-18, standard subagent; reviewed R01)
Spec: Append to `research/regression-testing/requirements.txt`, each pinned to
a major version: `supabase`, `httpx`, `pydantic`, `python-dotenv`, `pyyaml`,
`pandas`, `matplotlib`, `pytest`. Do not add any LLM SDK (B06 adds `google-genai`,
per D20). Create `src/__init__.py` (empty) and `src/config.py`
exporting a `Settings` pydantic model with exactly the variables named in
`.env.example` (`SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_PUBLISHABLE_KEY`,
`VERTEX_API_KEY`, `VERTEX_MODEL`, `SIMULATOR_MODEL`, `JUDGE_MODEL`, optional
`MA_MANUSCRIPT`, `MA_MANUSCRIPT_DIR`), loaded from `.env` in the subtree via
`python-dotenv` then the environment, raising `RuntimeError` naming every
missing required variable at import of `settings`. Its `__repr__` and `__str__`
must return `Settings(<redacted>)` — invariant 5: a config object printed into a
notebook cell must not leak a key. `tests/test_config.py`: missing variable
raises with the name; `repr` contains no value.
Done when: `pip install -r requirements.txt` succeeds in a fresh venv; `pytest
tests/test_config.py` passes; `python -c "from src.config import settings;
print(settings)"` prints the redacted form.

---

## Phase C — analysis and pilot

All `[FABLE]` while Q02 stands (§4.3 is scaffolding). Retag when it is written.

### C01 — Pilot notebook `study/05_pilot`
Phase: C
Tier: [FABLE]
Depends on: A13, B14
Estimate: 5h
Status: not started
Spec: `notebooks/study/05_pilot.ipynb`, outputs stripped. Parameterised on
`run_type` (default `pilot`). Section 1: **the field-population assertion** —
for every field in `docs/event-model.md` (read the table from the file, do not
retype it), assert at least one non-null value across the session, survey,
suggestion, mutation and feedback tables for the chosen `run_type`, and fail
loudly listing every field that is always null. Section 2: the flow checks the
`CLAUDE.md` pilot asks for, as queries — consent rows carry a version, a
declined session has no consent, the post-task row exists at most once per
session, `dismissed_at` and `submitted_at` are mutually exclusive. Section 3: a
pseudonymous summary (counts only; no `user_turn` text printed).
Done when: the notebook fails on an empty database with the full field list,
and passes after A13's end-to-end walk with `run_type = 'pilot'`;
`python tools/check_notebooks.py` passes.

### C02 — Analysis notebook `study/06_analysis`
Phase: C
Tier: [FABLE]
Depends on: B11, B12, C01
Estimate: 12h
Status: blocked — Q02 (§4.3 unwritten), Q19 (signature tolerance), Q03
(survey scales)
Spec: `notebooks/study/06_analysis.ipynb`, outputs stripped, parameterised on
the participant `run_type` and the simulation run ids to compare against.
Following the §4.3 skeleton in order: (1) descriptive — interaction counts,
session lengths, `request_type` distribution, Table 12 label distribution
(derived from `structural_check_outcome` and `user_action`; say plainly if
`ignored` dominates); (2) execution failure base rates for both rounds with
confidence intervals (P2), failure-type distributions compared; (3) coverage
(P1): signatures via B12 over simulated and participant traces, proportion
covered, and the shapes where uncovered concentrates; (4) outcome agreement on
covered shapes — contingency table of suite-detected against participant
labels; P3 — judge scores (B09, run blind over participant replies with
criteria by `request_type`) split by thumbs and by accept/reject, the two
signals never pooled; (5) UMUX-LITE (1..7, D18) via the Sauro–Lewis curved grading scale and the
recommend item; (6) every inferential statistic with assumptions
checked and n stated. Structural verdicts for participant suggestions are
written to `study_verdicts` by B08, never onto the app rows.
Done when: the notebook runs end to end **on simulated data only**
(`run_type = 'simulation'` as the stand-in participant round, compared against
itself) and produces every output §4.3 names; `check_notebooks.py` passes.

### C03 — THE GATE: end-to-end validation before the participant round
Phase: C
Tier: [FABLE]
Depends on: C01, C02, C04
Estimate: 4h
Status: not started
Spec: The one task that cannot be skipped or reordered. Run `05_pilot` against
the pilot sessions and `06_analysis` against simulated data, on the deployment
the participants will use (the existing project and API, D15), at the commit that will be live. Check: every
event-model field populated; every §4.3 output produced; the signature rule,
`request_type` rule, judge prompts and checker version recorded and frozen
(C05); the retention and access statement in `docs/event-model.md` confirmed
against the project's region and grants; `check_notebooks.py` clean; the information sheet's data statements match D14 (deletion is withdrawal)
and D15 (where the data lives). Record the check as a
`DECISIONS.md` entry by the author ("participant round opened on <date> at
<sha>") and a `REVIEW_LOG.md` entry naming what was and was not covered.
Done when: the author's entry exists and every item above is ticked in it.
Until then the study link is not sent to anyone.

### C04 — Pilot execution
Phase: C
Tier: [FABLE]
Depends on: A13, C01
Estimate: 3h
Status: not started
Spec: Author and one colleague run the full flow on the deployed app with the
`pilot` link (D15): sign-up, consent, demographics, at least three interactions
spanning the four functions, thumbs, accept and reject, the post-task screen
(one submits, one dismisses — event-model.md asks for one of each), and one
decline on a throwaway account. Then `05_pilot`. Findings become fixes on the
thesis branch or `OPEN_QUESTIONS.md` entries; re-run `05_pilot` after fixes.
Pilot sessions stay in the tables and are excluded by `run_type`.
Done when: `05_pilot` passes on the pilot sessions with no field always null,
and the findings list is recorded in `IMPLEMENTATION_LOG.md` if any bears on
the approach.

### C05 — Propositions freeze: material for the pre-registration entry
Phase: C
Tier: [FABLE]
Depends on: B11, B12
Estimate: 2h
Status: not started
Spec: §4.2.3 fixes the propositions "after the simulation runs have been
analysed and before any participant data is collected". Prepare, from
`04_regress`, the per-`request_type` execution failure ranking (P2's
expectation), the signature rule version and tolerance (P1), the judge protocol
version (P3), and hand them to the author for a `DECISIONS.md` entry that
freezes them with a date. The agent writes nothing into `DECISIONS.md` here.
Done when: the author's freeze entry exists and cites the run ids.

### C06 — First-session assertion during the real round
Phase: C
Tier: [FABLE]
Depends on: C03
Estimate: 1h
Status: not started
Spec: After the **first** `study` session completes (not the last), run
`05_pilot` with `run_type = 'study'`. A field that is always null now is still
fixable for the sessions that follow; after the round it is not.
Done when: the run is recorded (date, result) in `IMPLEMENTATION_LOG.md` only
if it found something, otherwise as a one-line note under this task's status.

---

## Order of work

Every Phase A and Phase B task is unblocked as of 2026-09-18. Critical path:
A01 → A02 → A04/A05 → A13 → B01 → B02 → B07 → B10 → B11 → C02 → C03. B03–B06,
B08 and B09 can be written in parallel with Phase A; they need Phase A only to
execute. A10, A11, B13 and B14 are `[STANDARD]` and dispatchable now; A03 as
soon as it is wanted.

## Decisions the tasks build on

| Decision | Settles | Tasks |
|---|---|---|
| D06 | `user_turn` copy + id | A01, A02 |
| D07 | interaction = agent turn | A02, A09, A12 |
| D08 | thumbs control; suggestion = turn | A01, A06 |
| D09 | `request_type` precedence | A02, A03, B12, C02 |
| D10 | `resulting_state_shape` | A02, B08 |
| D11 | failure taxonomy, `retry_count` | A02, C02 |
| D12 | `user_action` granularity | A01, A05, C02 |
| D13 | origin kinds, scope, header mechanism | A01, A04 |
| D14 | cascade erasure, export split | A01, A12 |
| D15 | one project; `run_type = simulation` | A01, B01, B02, B07, C03, C04 |
| D16 | session, enrolment, gate, decline | A01, A02, A07, A12 |
| D17 | `ignored` after 24 h by job | A01, A05 |
| D18 | survey scales | A01, A08, A09, C02 |
| D19 | constraints: hybrid | B03, B05, B08 |
| D20 | Gemini 3.5 Flash simulator and judge | B01, B06, B09 |
| D21 | 2 seeds/function, 2 follow-ups, n = 4, cap 3 | B03–B07 |
| D22 | metamorphic catalogue | B05 |
| D23 | pass criteria, judge protocol, weather reference | B09, B11 |
| D24 | coverage signature | B12, C02, C05 |

Still open: Q02 (§4.3), blocking C02.
