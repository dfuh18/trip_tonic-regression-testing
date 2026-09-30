-- Judge scores for participant replies (P3; D110 in research/regression-testing/
-- docs/DECISIONS.md, closing Q35).
--
-- study_scores is keyed to a simulated execution. A participant reply has no
-- execution: it is a study_suggestions row (the opening turn of a request),
-- so its score gets its own table, keyed to that row.
--
-- Deletion (D14): suggestion_id cascades, so a score goes with its turn, and a
-- turn goes with its session and its account. Deleting the account or
-- withdrawing (tools/withdraw_participant.py) removes the scores with
-- everything else. session_id is denormalised for the anonymisation job below
-- and cascades too.
--
-- Anonymisation (D91): the rationale is the judge's description of a reply to
-- a participant's words, so the eight-month job removes it with the rest of
-- the text and rounds the timestamp to the day. The score, the request type
-- and the judge version stay: they are the anonymous record the consent form
-- says remains.
--
-- Append-only per judge version, like study_scores: re-scoring under the same
-- (model, prompt version) is idempotent, under a new one it adds a row.
--
-- Access: written and read by the harness with the service key only. The
-- baseline's default privileges hand a new public table SELECT + INSERT for
-- authenticated (see 20260925125438 §3), so both are revoked explicitly.

create table if not exists "public"."study_participant_scores" (
  "id"                   uuid primary key default gen_random_uuid(),
  "suggestion_id"        uuid not null
                           references "public"."study_suggestions" ("id") on delete cascade,
  "session_id"           uuid not null
                           references "public"."study_sessions" ("id") on delete cascade,
  -- The rubric the reply was scored against: the opening turn's D09 type.
  "request_type"         text not null
                           constraint "study_participant_scores_request_type"
                           check ("request_type" in ('scheduling', 'venue_lookup', 'factual_qa', 'advisory')),

  "judge_model"          text not null,
  "judge_prompt_version" text not null,

  "score"                integer
                           constraint "study_participant_scores_range" check ("score" between 1 and 10),
  -- Nullable: the anonymisation job removes it.
  "rationale"            text,
  "reply_chars"          integer not null default 0,
  "error"                text,

  "created_at"           timestamptz not null default now(),

  constraint "study_participant_scores_scored_or_explained"
    check ("score" is not null or "error" is not null),
  constraint "study_participant_scores_one_per_judge"
    unique ("suggestion_id", "judge_model", "judge_prompt_version")
);

create index if not exists "study_participant_scores_session_idx"
  on "public"."study_participant_scores" ("session_id");

comment on table "public"."study_participant_scores" is
  'P3 (D110): point-wise judge scores of participant replies, one per opening turn of a request and judge version. Cascades from the suggestion and the session (D14); the rationale is removed by study_anonymise_expired() (D91). Service role only.';

alter table "public"."study_participant_scores" enable row level security;
revoke all on table "public"."study_participant_scores" from "anon";
revoke all on table "public"."study_participant_scores" from "authenticated";
grant all on table "public"."study_participant_scores" to "service_role";


-- The anonymisation job, as in 20260925125438 §1b, plus the scores' rationale.
create or replace function "public"."study_anonymise_expired"()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_sessions uuid[];
begin
  select coalesce(array_agg(s.id), '{}')
  into v_sessions
  from public.study_sessions s
  where s.run_type in ('pilot', 'study')
    and s.anonymised_at is null
    and coalesce(s.consent_at, s.declined_at, s.created_at) < now() - interval '8 months';

  if cardinality(v_sessions) = 0 then
    return 0;
  end if;

  -- The participant's usage rows, first: the window is read from the exact
  -- timestamps and the user id this job removes below. From consent to an hour
  -- after the last turn finished (or started, for a turn that never finished).
  -- A session that never consented has no turns and no window.
  update public.api_usage_events e
  set user_id = null,
      trip_id = null,
      session_id = null
  from (
    select s.user_id,
           s.consent_at as w_from,
           coalesce(greatest(max(g.completed_at), max(g.occurred_at)), s.consent_at) + interval '1 hour' as w_to
    from public.study_sessions s
    left join public.study_suggestions g on g.session_id = s.id
    where s.id = any (v_sessions)
      and s.user_id is not null
      and s.consent_at is not null
    group by s.id, s.user_id, s.consent_at
  ) w
  where e.user_id = w.user_id
    and e.created_at >= w.w_from
    and e.created_at <= w.w_to;

  update public.study_user_actions a
  set actor_user_id = null,
      target = case when a.target like 'place:%' then 'place' else a.target end,
      created_at = date_trunc('day', a.created_at)
  from public.study_suggestions g
  where a.suggestion_id = g.id and g.session_id = any (v_sessions);

  update public.study_suggestions
  set user_id = null,
      user_turn = null,
      trip_id = null,
      run_id = null,
      user_message_id = null,
      reply_message_id = null,
      occurred_at = date_trunc('day', occurred_at),
      completed_at = date_trunc('day', completed_at),
      resulting_state_shape = case
        when resulting_state_shape -> 'draft' ? 'suggestion_id'
          then jsonb_set(resulting_state_shape, '{draft}', (resulting_state_shape -> 'draft') - 'suggestion_id')
        else resulting_state_shape
      end,
      -- Per entry: argument values removed (keys kept), started_at rounded to
      -- the day in the ISO form the API writes, or dropped if it is not one.
      tool_call_trace = case
        when jsonb_typeof(tool_call_trace) = 'array' then coalesce(
          (select jsonb_agg(
                    case when jsonb_typeof(t.value) = 'object' and t.value ? 'started_at' then
                      case when t.value ->> 'started_at' ~ '^\d{4}-\d{2}-\d{2}T'
                        then jsonb_set(t.value, '{started_at}', to_jsonb(left(t.value ->> 'started_at', 10) || 'T00:00:00.000Z'))
                        else t.value - 'started_at'
                      end
                    else t.value
                    end
                    order by t.ord)
           from (
             select case when jsonb_typeof(e.value) = 'object' and e.value ? 'args'
                      then jsonb_set(e.value, '{args}', public.study_json_skeleton(e.value -> 'args'))
                      else e.value
                    end as value,
                    e.ord
             from jsonb_array_elements(tool_call_trace) with ordinality e(value, ord)
           ) t),
          '[]'::jsonb)
        else tool_call_trace
      end
  where session_id = any (v_sessions);

  update public.study_survey_demographics
  set user_id = null,
      submitted_at = date_trunc('day', submitted_at)
  where session_id = any (v_sessions);

  update public.study_survey_post_task
  set user_id = null,
      free_text = null,
      submitted_at = date_trunc('day', submitted_at),
      dismissed_at = date_trunc('day', dismissed_at)
  where session_id = any (v_sessions);

  -- user_id null in the same statement, so set_updated_at (1a) keeps the
  -- rounded updated_at instead of stamping now().
  update public.study_feedback
  set user_id = null,
      chat_message_id = null,
      created_at = date_trunc('day', created_at),
      updated_at = date_trunc('day', updated_at)
  where session_id = any (v_sessions);

  update public.study_mutations
  set actor_user_id = null,
      trip_id = null,
      row_id = null,
      occurred_at = date_trunc('day', occurred_at),
      projection = (
        select coalesce(jsonb_object_agg(e.key, e.value), '{}'::jsonb)
        from jsonb_each(coalesce(projection, '{}'::jsonb)) e
        where e.key not like '%\_id' escape '\'
      )
  where session_id = any (v_sessions);

  update public.study_participant_scores
  set rationale = null,
      created_at = date_trunc('day', created_at)
  where session_id = any (v_sessions);

  update public.study_sessions
  set user_id = null,
      client_session_id = null,
      consent_at = date_trunc('day', consent_at),
      declined_at = date_trunc('day', declined_at),
      created_at = date_trunc('day', created_at),
      anonymised_at = now()
  where id = any (v_sessions);

  return cardinality(v_sessions);
end;
$$;

revoke all on function "public"."study_anonymise_expired"() from public;
revoke all on function "public"."study_anonymise_expired"() from "anon";
revoke all on function "public"."study_anonymise_expired"() from "authenticated";
revoke all on function "public"."study_json_skeleton"(jsonb) from public;
revoke all on function "public"."study_json_skeleton"(jsonb) from "anon";
revoke all on function "public"."study_json_skeleton"(jsonb) from "authenticated";

comment on function "public"."study_anonymise_expired"() is
  'D91: eight months after consent, removes account links, text, trip/chat ids and place ids from a pilot/study session, rounds its timestamps to the day, and cuts the participant''s api_usage_events rows in the session window, and removes the judge''s rationale on the participant''s replies (D110). Once per session.';

