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
