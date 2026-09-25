-- Anonymise participant study data eight months after consent (D91).
--
-- The participant information (research/regression-testing/docs/
-- participant-information-and-consent_260925.md, "How long is it kept?")
-- promises: "Your data is retained for eight months from the date you give
-- consent. After that, the link to your account and the text of your messages
-- are removed automatically, and only anonymous records of the kinds of
-- requests made and their outcomes remain." This is that removal.
--
-- For every pilot or study session older than eight months (from consent, or
-- from the decline or creation for a session that never consented), once:
--
--   * every account link is cut: user_id / actor_user_id → null;
--   * everything a participant wrote is removed: user_turn → null,
--     post-task free_text → null;
--   * every id that leads back into the trip — and through the trip to the
--     account — is removed: trip, run and chat-message ids, the mutated row's
--     id, the id-valued keys of mutation projections, the draft id in the
--     state shape, the browser session id;
--   * tool arguments keep their keys and lose their values (the search terms
--     a participant's request produced); tool names, order, timing, errors
--     and outcomes stay;
--   * study_sessions.anonymised_at is stamped, so a session is done once.
--
-- What remains is anonymous: request types, outcomes, counts, timings, survey
-- scales, device type, and the links between one session's own rows.
--
-- Simulation sessions are not touched: they are the harness's own accounts.
-- Deleting an account before this point still erases everything (D14): the
-- account-link columns keep ON DELETE CASCADE. After it, there is nothing
-- left that belongs to an account, which is what "until the point of complete
-- anonymisation" in the form refers to.
--
-- Additive: columns become nullable and one column is added. Nothing is
-- renamed or dropped, and no row changes until a session is eight months old.

-- 1. Columns that must be able to hold "removed" -------------------------------

alter table "public"."study_sessions"            alter column "user_id"   drop not null;
alter table "public"."study_survey_demographics" alter column "user_id"   drop not null;
alter table "public"."study_survey_post_task"    alter column "user_id"   drop not null;
alter table "public"."study_suggestions"         alter column "user_id"   drop not null;
alter table "public"."study_suggestions"         alter column "user_turn" drop not null;
alter table "public"."study_feedback"            alter column "user_id"   drop not null;
alter table "public"."study_mutations"           alter column "row_id"    drop not null;

alter table "public"."study_sessions"
  add column if not exists "anonymised_at" timestamptz;

comment on column "public"."study_sessions"."anonymised_at" is
  'When study_anonymise_expired() removed this session''s account links and text (D91). Null until eight months after consent.';

-- 2. Keys without values ----------------------------------------------------------

-- The same JSON with every scalar replaced by null: objects keep their keys,
-- arrays keep their length. Used for tool arguments, whose keys describe what
-- kind of request it was and whose values are what the participant asked for.
-- plpgsql rather than sql: the function calls itself, and a sql body is
-- resolved at creation, before the function exists.
create or replace function "public"."study_json_skeleton"(p_value jsonb)
returns jsonb
language plpgsql
immutable
set search_path = public
as $$
begin
  case jsonb_typeof(p_value)
    when 'object' then
      return coalesce(
        (select jsonb_object_agg(e.key, public.study_json_skeleton(e.value)) from jsonb_each(p_value) e),
        '{}'::jsonb);
    when 'array' then
      return coalesce(
        (select jsonb_agg(public.study_json_skeleton(e.value) order by e.ord)
         from jsonb_array_elements(p_value) with ordinality e(value, ord)),
        '[]'::jsonb);
    else
      return case when p_value is null then null else 'null'::jsonb end;
  end case;
end;
$$;

-- 3. The job ------------------------------------------------------------------------

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

  update public.study_user_actions a
  set actor_user_id = null
  from public.study_suggestions g
  where a.suggestion_id = g.id and g.session_id = any (v_sessions);

  update public.study_suggestions
  set user_id = null,
      user_turn = null,
      trip_id = null,
      run_id = null,
      user_message_id = null,
      reply_message_id = null,
      resulting_state_shape = case
        when resulting_state_shape -> 'draft' ? 'suggestion_id'
          then jsonb_set(resulting_state_shape, '{draft}', (resulting_state_shape -> 'draft') - 'suggestion_id')
        else resulting_state_shape
      end,
      tool_call_trace = case
        when jsonb_typeof(tool_call_trace) = 'array' then coalesce(
          (select jsonb_agg(
                    case when e.value ? 'args'
                      then jsonb_set(e.value, '{args}', public.study_json_skeleton(e.value -> 'args'))
                      else e.value
                    end
                    order by e.ord)
           from jsonb_array_elements(tool_call_trace) with ordinality e(value, ord)),
          '[]'::jsonb)
        else tool_call_trace
      end
  where session_id = any (v_sessions);

  update public.study_survey_demographics set user_id = null where session_id = any (v_sessions);
  update public.study_survey_post_task set user_id = null, free_text = null where session_id = any (v_sessions);
  update public.study_feedback set user_id = null, chat_message_id = null where session_id = any (v_sessions);

  update public.study_mutations
  set actor_user_id = null,
      trip_id = null,
      row_id = null,
      projection = (
        select coalesce(jsonb_object_agg(e.key, e.value), '{}'::jsonb)
        from jsonb_each(coalesce(projection, '{}'::jsonb)) e
        where e.key not like '%\_id' escape '\'
      )
  where session_id = any (v_sessions);

  update public.study_sessions
  set user_id = null,
      client_session_id = null,
      anonymised_at = now()
  where id = any (v_sessions);

  return cardinality(v_sessions);
end;
$$;

revoke all on function "public"."study_anonymise_expired"() from public;
revoke all on function "public"."study_json_skeleton"(jsonb) from public;

-- 4. Daily at 03:17 UTC --------------------------------------------------------------

do $$
begin
  perform cron.unschedule(jobid)
  from cron.job
  where jobname = 'study-anonymise-expired';
exception when others then
  null;
end $$;

select cron.schedule(
  'study-anonymise-expired',
  '17 3 * * *',
  $$ select public.study_anonymise_expired(); $$
);
