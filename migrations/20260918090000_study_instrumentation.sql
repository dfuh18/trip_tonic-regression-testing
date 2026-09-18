-- Study instrumentation: the tables the regression-testing thesis logs into.
--
-- The event model in research/regression-testing/docs/event-model.md is the
-- list hard invariant 3 refers to ("a field that is not logged is data that
-- does not exist"), and this migration is that list as DDL. Every level that
-- must exist in the live application — session, the two survey instruments,
-- suggestion, user action, feedback, state mutation — plus the run and
-- test-case levels the simulation harness writes, and an append-only verdict
-- table so analysis never updates an application row.
--
-- Rulings this encodes (research/regression-testing/docs/DECISIONS.md):
--   D02  surveys are their own tables
--   D06  user_turn is copied verbatim, the chat row id kept beside it
--   D08  a suggestion is one agent turn; thumbs are keyed by the reply message
--   D12  one study_user_actions row per target; the turn label follows a rule
--   D13  five origin kinds on the plan tables
--   D14  every reference to the participant cascades — deletion is withdrawal
--   D15  one project; run_type gains 'simulation'
--   D16  a session is one row per consent event
--   D17  'ignored' is stamped by a scheduled job after 24 hours, nulls only
--   D18  survey scales
--
-- Who writes what: the API writes with the service key (participants hold no
-- INSERT grant — ownership is checked in the route), the harness writes the
-- run and case tables with the service key, and `authenticated` may SELECT
-- only its own session, survey and suggestion rows, which is what the account
-- export reads. Nothing here is readable by an admin surface (see
-- docs/DECISION_ai_conversation_privacy.md); analysis reads with the service
-- key, in notebooks, under consent.

-- 1. Session ---------------------------------------------------------------------

create table if not exists "public"."study_sessions" (
  "id"                uuid primary key default gen_random_uuid(),
  "user_id"           uuid not null references "public"."profiles" ("id") on delete cascade,
  "run_type"          text not null
                        constraint "study_sessions_run_type" check ("run_type" in ('pilot', 'study', 'simulation')),
  "consent_version"   text,
  "consent_at"        timestamptz,
  "declined_at"       timestamptz,
  "device_type"       text,
  -- The analytics tab id (lib/analytics/session.ts), recorded beside the
  -- session so behavioural rows join to api_usage_events and ux_events.
  "client_session_id" text,
  "created_at"        timestamptz not null default now(),
  -- A row is either a consent (with its version) or a decline, never both and
  -- never neither: an unconsented, undeclined session would log nothing and
  -- prove nothing.
  constraint "study_sessions_consent_or_decline" check (
    ("consent_at" is not null and "consent_version" is not null and "declined_at" is null)
    or ("consent_at" is null and "declined_at" is not null)
  )
);

comment on table "public"."study_sessions" is
  'One row per consent event (or decline) in the regression-testing study. run_type separates pilot, study and simulation sessions in the same tables.';

create index if not exists "study_sessions_user_idx"
  on "public"."study_sessions" ("user_id", "consent_at" desc);

-- 2. Surveys (D02, D18) ----------------------------------------------------------

create table if not exists "public"."study_survey_demographics" (
  "session_id"      uuid primary key references "public"."study_sessions" ("id") on delete cascade,
  "user_id"         uuid not null references "public"."profiles" ("id") on delete cascade,
  "age"             integer not null
                      constraint "study_survey_demographics_age" check ("age" between 18 and 120),
  "gender"          text not null
                      constraint "study_survey_demographics_gender"
                      check ("gender" in ('woman', 'man', 'non_binary', 'prefer_not_to_say')),
  "education_level" text not null
                      constraint "study_survey_demographics_education"
                      check ("education_level" in ('compulsory', 'vocational', 'high_school', 'bachelor', 'master_or_higher')),
  "llm_familiarity" text not null
                      constraint "study_survey_demographics_familiarity"
                      check ("llm_familiarity" in ('never', 'rarely', 'monthly', 'weekly', 'daily')),
  "submitted_at"    timestamptz not null default now()
);

comment on table "public"."study_survey_demographics" is
  'Demographic questionnaire, one row per study session (§4.2.2; scales D18).';

create table if not exists "public"."study_survey_post_task" (
  "session_id"              uuid primary key references "public"."study_sessions" ("id") on delete cascade,
  "user_id"                 uuid not null references "public"."profiles" ("id") on delete cascade,
  "umux_lite_capability"    integer
                              constraint "study_survey_post_task_umux1" check ("umux_lite_capability" between 1 and 7),
  "umux_lite_ease"          integer
                              constraint "study_survey_post_task_umux2" check ("umux_lite_ease" between 1 and 7),
  "real_trip"               boolean,
  "likelihood_to_recommend" integer
                              constraint "study_survey_post_task_ltr" check ("likelihood_to_recommend" between 1 and 7),
  "free_text"               text
                              constraint "study_survey_post_task_free_text_length" check (char_length("free_text") <= 4000),
  "submitted_at"            timestamptz,
  "dismissed_at"            timestamptz,
  -- A row exists because the participant submitted or dismissed — exactly one.
  -- Partial answers on a dismissed row are legal (event-model.md).
  constraint "study_survey_post_task_outcome" check (num_nonnulls("submitted_at", "dismissed_at") = 1)
);

comment on table "public"."study_survey_post_task" is
  'Post-task instrument (UMUX-LITE, task involvement, likelihood to recommend, free text), one row per session; absent = never reached, dismissed_at = dismissed.';

-- 3. Suggestion = one agent turn (D08) -------------------------------------------

create table if not exists "public"."study_suggestions" (
  "id"                        uuid primary key default gen_random_uuid(),
  "session_id"                uuid not null references "public"."study_sessions" ("id") on delete cascade,
  "user_id"                   uuid not null references "public"."profiles" ("id") on delete cascade,
  -- SET NULL, not cascade: the study record outlives the trip it was made on.
  "trip_id"                   uuid references "public"."trips" ("id") on delete set null,
  -- The conversation (event-model.md conversation_id): the tonic_runs row.
  "run_id"                    uuid references "public"."tonic_runs" ("id") on delete set null,
  "turn_index"                integer not null,
  -- Verbatim copy (D06); the row the browser wrote, for the join.
  "user_turn"                 text not null,
  "user_message_id"           uuid references "public"."chat_messages" ("id") on delete set null,
  "reply_message_id"          uuid references "public"."chat_messages" ("id") on delete set null,
  "agent_intent"              text
                                constraint "study_suggestions_intent" check ("agent_intent" is null or "agent_intent" in ('find', 'plan', 'reschedule')),
  "device_type"               text,
  "occurred_at"               timestamptz not null default now(),
  "completed_at"              timestamptz,
  "latency_ms"                integer,
  "llm_calls"                 integer,
  "tool_calls"                integer,
  "tokens_input"              integer,
  "tokens_output"             integer,
  "retry_count"               integer not null default 0,
  "model_version"             text,
  "model_released_on"         date,
  -- Ordered; the P1 coverage signature is built from it. Args verbatim, results
  -- reduced to error and size (D11).
  "tool_call_trace"           jsonb,
  -- D10: compact shape plus post-turn counts.
  "resulting_state_shape"     jsonb,
  "request_type"              text
                                constraint "study_suggestions_request_type"
                                check ("request_type" is null or "request_type" in ('scheduling', 'venue_lookup', 'factual_qa', 'advisory')),
  "request_type_rule_version" text,
  "error_code"                text
                                constraint "study_suggestions_error_code"
                                check ("error_code" is null or "error_code" in ('timeout', 'llm_call_limit', 'empty_reply', 'llm_error', 'persist_failed', 'other')),
  -- Written by the app (D12) or the scheduled job (D17); final once set.
  -- 'user_initiated' is derived in analysis and never written by the app; it
  -- stays in the check so the enum matches Table 11.
  "user_action"               text
                                constraint "study_suggestions_user_action"
                                check ("user_action" is null or "user_action" in ('accepted', 'rejected', 'ignored', 'user_initiated')),
  -- Simulation rows: written by the harness from the structural checker at run
  -- time. Participant rows: never written here — verdicts computed after the
  -- fact go to study_verdicts, so an application row is never updated by
  -- analysis.
  "structural_check_outcome"  text
                                constraint "study_suggestions_structural_outcome"
                                check ("structural_check_outcome" is null or "structural_check_outcome" in ('none', 'detected'))
);

comment on table "public"."study_suggestions" is
  'One row per agent turn (the comparison unit of the study). Written by the API at turn start and completed at turn end; never read by the agent.';

create index if not exists "study_suggestions_session_idx"
  on "public"."study_suggestions" ("session_id", "occurred_at");

create index if not exists "study_suggestions_run_idx"
  on "public"."study_suggestions" ("run_id", "turn_index");

create index if not exists "study_suggestions_reply_idx"
  on "public"."study_suggestions" ("reply_message_id");

-- The D17 job fills nulls; nothing overwrites a value. Enforced here rather
-- than trusted, because two writers (the app and the job) race by design.
create or replace function "public"."study_suggestions_user_action_immutable"()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if old.user_action is not null and new.user_action is distinct from old.user_action then
    raise exception 'study_suggestions.user_action is final once set (was %, got %)', old.user_action, new.user_action
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists "study_suggestions_user_action_final" on "public"."study_suggestions";
create trigger "study_suggestions_user_action_final"
  before update of "user_action" on "public"."study_suggestions"
  for each row execute function "public"."study_suggestions_user_action_immutable"();

-- 4. User actions, per target (D12) -------------------------------------------------

create table if not exists "public"."study_user_actions" (
  "id"            uuid primary key default gen_random_uuid(),
  "suggestion_id" uuid not null references "public"."study_suggestions" ("id") on delete cascade,
  -- 'slot:<index>' for a draft slot, 'place:<google_place_id>' for a place the
  -- reply named, 'edits' for the live edits of a reschedule turn.
  "target"        text not null,
  "action"        text not null
                    constraint "study_user_actions_action" check ("action" in ('accepted', 'rejected')),
  -- Who acted. Usually the participant; a co-member may accept a slot of a
  -- shared draft, and that is still a reaction to the suggestion.
  "actor_user_id" uuid references "public"."profiles" ("id") on delete cascade,
  "created_at"    timestamptz not null default now()
);

comment on table "public"."study_user_actions" is
  'Every explicit reaction to a suggestion, one row per target. The turn-level label on study_suggestions is derived from these by the D12 rule.';

create index if not exists "study_user_actions_suggestion_idx"
  on "public"."study_user_actions" ("suggestion_id", "created_at");

-- 5. Thumbs (D08) ---------------------------------------------------------------------

create table if not exists "public"."study_feedback" (
  "id"              uuid primary key default gen_random_uuid(),
  "session_id"      uuid not null references "public"."study_sessions" ("id") on delete cascade,
  "user_id"         uuid not null references "public"."profiles" ("id") on delete cascade,
  -- The Tonic reply the control sits under; joins to study_suggestions.reply_message_id.
  "chat_message_id" uuid references "public"."chat_messages" ("id") on delete set null,
  "value"           text not null
                      constraint "study_feedback_value" check ("value" in ('up', 'down')),
  "created_at"      timestamptz not null default now(),
  "updated_at"      timestamptz not null default now(),
  -- One rating per member per reply; changing one's mind updates the row.
  constraint "study_feedback_one_per_message" unique ("user_id", "chat_message_id")
);

comment on table "public"."study_feedback" is
  'Direct feedback: the thumbs control under every Tonic reply, private to the member (D08).';

create or replace trigger "set_updated_at"
  before update on "public"."study_feedback"
  for each row execute function "public"."handle_updated_at"();

-- 6. State mutations with origin (D13) -------------------------------------------------

create table if not exists "public"."study_mutations" (
  "id"                   uuid primary key default gen_random_uuid(),
  "table_name"           text not null,
  "row_id"               uuid not null,
  "op"                   text not null
                           constraint "study_mutations_op" check ("op" in ('INSERT', 'UPDATE', 'DELETE')),
  "changed_keys"         text[],
  -- A minimal projection of the row (day, time, block, type, place id …),
  -- never the whole row.
  "projection"           jsonb,
  "origin_suggestion_id" uuid references "public"."study_suggestions" ("id") on delete set null,
  "origin_kind"          text not null
                           constraint "study_mutations_origin_kind"
                           check ("origin_kind" in ('agent_live_edit', 'agent_draft_accepted', 'agent_place_added', 'user_manual', 'system')),
  "actor_user_id"        uuid references "public"."profiles" ("id") on delete cascade,
  "session_id"           uuid references "public"."study_sessions" ("id") on delete cascade,
  "trip_id"              uuid references "public"."trips" ("id") on delete set null,
  "occurred_at"          timestamptz not null default now()
);

comment on table "public"."study_mutations" is
  'Every write to the plan tables during a study session, linked to the suggestion that caused it (§3.2 point 4). Written by triggers installed in a later migration (task A04).';

create index if not exists "study_mutations_origin_idx"
  on "public"."study_mutations" ("origin_suggestion_id");

create index if not exists "study_mutations_session_idx"
  on "public"."study_mutations" ("session_id", "occurred_at");

-- 7. Structural verdicts, append-only ---------------------------------------------------

create table if not exists "public"."study_verdicts" (
  "id"              uuid primary key default gen_random_uuid(),
  "suggestion_id"   uuid not null references "public"."study_suggestions" ("id") on delete cascade,
  "checker_version" text not null,
  "outcome"         text not null
                      constraint "study_verdicts_outcome" check ("outcome" in ('none', 'detected')),
  "findings"        jsonb not null default '[]'::jsonb,
  "created_at"      timestamptz not null default now(),
  constraint "study_verdicts_one_per_version" unique ("suggestion_id", "checker_version")
);

comment on table "public"."study_verdicts" is
  'Structural checker output per suggestion and checker version. Append-only: a new checker version adds a row, nothing is edited.';

-- 8. Run and test-case levels (simulation only; harness-written) ------------------------

create table if not exists "public"."study_runs" (
  "id"                       uuid primary key default gen_random_uuid(),
  "started_at"               timestamptz not null default now(),
  "finished_at"              timestamptz,
  -- Dated release, never an alias (invariant 2). The date is what Table 11
  -- asks for; the id alone does not evidence a pin.
  "model_version"            text not null,
  "model_released_on"        date,
  "prompt_version"           text,
  "tool_version"             text,
  "git_sha"                  text,
  "suite_version"            text not null,
  -- The run whose adopted replies this one is compared against; null for the
  -- baseline run itself.
  "baseline_ref"             uuid references "public"."study_runs" ("id") on delete set null,
  "simulator_model"          text,
  "simulator_prompt_version" text,
  "judge_model"              text,
  "judge_prompt_version"     text,
  "cost_usd"                 numeric(12, 6),
  "latency_ms"               integer,
  "token_count"              integer,
  "notes"                    text
);

comment on table "public"."study_runs" is
  'One baseline or regression execution of the suite (Table 11, run level). State reset is a precondition checked before this row exists (D03), not a column.';

create table if not exists "public"."study_case_executions" (
  "id"                     uuid primary key default gen_random_uuid(),
  "run_id"                 uuid not null references "public"."study_runs" ("id") on delete cascade,
  "case_id"                text not null,
  "base_case_id"           text,
  "provenance"             text not null
                             constraint "study_case_executions_provenance" check ("provenance" in ('seeded', 'metamorphic', 'retained')),
  "run_priority"           integer,
  "repetition"             integer not null,
  "repetitions_n"          integer,
  "session_id"             uuid references "public"."study_sessions" ("id") on delete set null,
  "trip_id"                uuid references "public"."trips" ("id") on delete set null,
  "declared_constraints"   jsonb,
  "expected_tool_sequence" jsonb,
  "scoring_criteria"       jsonb,
  -- The turns this execution produced, in order.
  "suggestion_ids"         uuid[] not null default '{}',
  "structural_outcome"     text
                             constraint "study_case_executions_structural_outcome"
                             check ("structural_outcome" is null or "structural_outcome" in ('none', 'detected')),
  "cost_usd"               numeric(12, 6),
  "latency_ms"             integer,
  "token_count"            integer,
  "error"                  text,
  "started_at"             timestamptz not null default now(),
  "finished_at"            timestamptz,
  constraint "study_case_executions_one_per_repetition" unique ("run_id", "case_id", "repetition")
);

comment on table "public"."study_case_executions" is
  'One case run once (Table 11, test case level). n rows per case per run.';

-- 9. The 'ignored' job (D17) ----------------------------------------------------------------

create or replace function "public"."study_finalize_ignored"()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count integer;
begin
  update public.study_suggestions
  set user_action = 'ignored'
  where user_action is null
    and occurred_at < now() - interval '24 hours';
  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

revoke all on function "public"."study_finalize_ignored"() from public;

do $$
begin
  perform cron.unschedule(jobid)
  from cron.job
  where jobname = 'study-finalize-ignored';
exception when others then
  null;
end $$;

select cron.schedule(
  'study-finalize-ignored',
  '5 * * * *',
  $$ select public.study_finalize_ignored(); $$
);

-- 10. RLS and grants ------------------------------------------------------------------------
--
-- Participants read their own session, survey and suggestion rows (the account
-- export needs SELECT on the RLS client) and nothing else; every write goes
-- through the API with the service key after an ownership check. The tables
-- without a policy are reachable by service_role only. This database grants
-- nothing by default, so each grant below is load-bearing.

alter table "public"."study_sessions"            enable row level security;
alter table "public"."study_survey_demographics" enable row level security;
alter table "public"."study_survey_post_task"    enable row level security;
alter table "public"."study_suggestions"         enable row level security;
alter table "public"."study_user_actions"        enable row level security;
alter table "public"."study_feedback"            enable row level security;
alter table "public"."study_mutations"           enable row level security;
alter table "public"."study_verdicts"            enable row level security;
alter table "public"."study_runs"                enable row level security;
alter table "public"."study_case_executions"     enable row level security;

create policy "Participants view own study_sessions" on "public"."study_sessions"
  for select using ((select auth.uid()) = "user_id");

create policy "Participants view own study_survey_demographics" on "public"."study_survey_demographics"
  for select using ((select auth.uid()) = "user_id");

create policy "Participants view own study_survey_post_task" on "public"."study_survey_post_task"
  for select using ((select auth.uid()) = "user_id");

create policy "Participants view own study_suggestions" on "public"."study_suggestions"
  for select using ((select auth.uid()) = "user_id");

grant select on table "public"."study_sessions"            to "authenticated";
grant select on table "public"."study_survey_demographics" to "authenticated";
grant select on table "public"."study_survey_post_task"    to "authenticated";
grant select on table "public"."study_suggestions"         to "authenticated";

grant all on table "public"."study_sessions"            to "service_role";
grant all on table "public"."study_survey_demographics" to "service_role";
grant all on table "public"."study_survey_post_task"    to "service_role";
grant all on table "public"."study_suggestions"         to "service_role";
grant all on table "public"."study_user_actions"        to "service_role";
grant all on table "public"."study_feedback"            to "service_role";
grant all on table "public"."study_mutations"           to "service_role";
grant all on table "public"."study_verdicts"            to "service_role";
grant all on table "public"."study_runs"                to "service_role";
grant all on table "public"."study_case_executions"     to "service_role";
