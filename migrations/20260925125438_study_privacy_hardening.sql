-- Study privacy hardening (pre-merge audit of feat/thesis-regression-testing).
--
-- 1. Anonymisation, stronger (D91 amendment). After the eight months the
--    consent form names, removing the account link was not enough on its own:
--    exact timestamps still joined every study row back to chat_messages and
--    api_usage_events, whose rows name the account; api_usage_events kept the
--    participant's user, trip and session; and study_user_actions.target kept
--    the Google place id a participant reacted to. The job now also
--      * rounds every study timestamp of the session to the day (the tool
--        trace's started_at included), keeping durations, latencies and token
--        counts, which are the analysis;
--      * cuts user_id / trip_id / session_id on the participant's
--        api_usage_events rows inside the session's window
--        [consent_at, last turn + 1 hour];
--      * reduces 'place:<google place id>' targets to 'place'.
--    Still once per session, still pilot/study only.
-- 2. The mutation trigger can no longer abort a member's write on a malformed
--    x-study-origin header or a malformed ai_suggestions.suggested_data: the
--    ids it casts must be canonical UUIDs, and the slot counts only walk arrays.
--    No blanket exception handler — a swallowed error is a lost log row.
-- 3. Grants. The baseline's default privileges hand every new public table
--    SELECT + INSERT for authenticated, so every study table carried both,
--    contrary to what the study migrations say. INSERT goes everywhere; SELECT
--    stays only where a "Participants view own …" policy exists.
-- 4. analytics_cost_rollup no longer resolves a user id to a name for the admin
--    dashboard (docs/DECISION_ai_conversation_privacy.md: admin views never
--    resolve user_id to a name). bucket_label stays in the result, null.
-- 5. The jobs are not callable by anon / authenticated.


-- 1a. study_feedback.updated_at must survive the job ---------------------------------
--
-- handle_updated_at() stamps now() on every update, so the job's own update
-- would overwrite the rounded value with the time of anonymisation. A row
-- without a user is one the job wrote — the app only ever writes feedback for a
-- signed-in member — so the stamp is skipped exactly there. App writes are
-- unchanged.

drop trigger if exists "set_updated_at" on "public"."study_feedback";
create trigger "set_updated_at"
  before update on "public"."study_feedback"
  for each row
  when (new.user_id is not null)
  execute function "public"."handle_updated_at"();


-- 1b. The job ------------------------------------------------------------------------

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
  'D91: eight months after consent, removes account links, text, trip/chat ids and place ids from a pilot/study session, rounds its timestamps to the day, and cuts the participant''s api_usage_events rows in the session window. Once per session.';


-- 2. Mutation trigger: malformed input never aborts the member's write ---------------

create or replace function "public"."study_log_mutation"()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_new        jsonb;
  v_old        jsonb;
  v_row_id     uuid;
  v_trip       uuid;
  v_actor      uuid := auth.uid();
  v_session    uuid;
  v_header     text;
  v_kind       text;
  v_suggestion uuid;
  v_draft      uuid;
  v_keys       text[];
  v_proj       jsonb;
  v_days       jsonb;
begin
  if tg_op = 'DELETE' then
    v_new := to_jsonb(old);
  else
    v_new := to_jsonb(new);
  end if;
  if tg_op = 'UPDATE' then
    v_old := to_jsonb(old);
  end if;
  v_row_id := (v_new ->> 'id')::uuid;

  -- The trip the row belongs to. Slots reach it through their day.
  if tg_table_name = 'itinerary_slots' then
    select d.trip_id into v_trip
    from public.itinerary_days d
    where d.id = (v_new ->> 'itinerary_day_id')::uuid;
  else
    v_trip := (v_new ->> 'trip_id')::uuid;
  end if;

  -- Whose session this belongs to. A member: their own. Nobody (service key,
  -- cron, definer functions): the trip's participant, if it has one.
  if v_actor is not null then
    select s.id into v_session
    from public.study_sessions s
    where s.user_id = v_actor
      and s.consent_at is not null
      and s.declined_at is null
    order by s.consent_at desc
    limit 1;
  elsif v_trip is not null then
    select s.id into v_session
    from public.study_sessions s
    join public.trip_members m on m.user_id = s.user_id
    where m.trip_id = v_trip
      and s.consent_at is not null
      and s.declined_at is null
    order by s.consent_at desc
    limit 1;
  end if;
  if v_session is null or not exists (select 1 from public.study_sessions z where z.id = v_session) then
    return null;
  end if;

  -- The declared origin, if the client sent one. Only a canonical UUID is
  -- captured, so the casts below cannot raise on a malformed header.
  begin
    v_header := nullif(current_setting('request.headers', true), '')::json ->> 'x-study-origin';
  exception when others then
    v_header := null;
  end;
  if v_header is not null then
    v_kind := split_part(v_header, ';', 1);
    if v_kind not in ('agent_live_edit', 'agent_draft_accepted', 'agent_place_added') then
      v_kind := null;
    end if;
    v_suggestion := substring(v_header from 'suggestion=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')::uuid;
    v_draft      := substring(v_header from 'draft=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')::uuid;
    if v_suggestion is null and v_draft is not null then
      select id into v_suggestion
      from public.study_suggestions
      where resulting_state_shape -> 'draft' ->> 'suggestion_id' = v_draft::text
      order by occurred_at desc
      limit 1;
    end if;
  end if;
  if v_actor is null then
    v_kind := 'system';
  elsif v_kind is null then
    v_kind := 'user_manual';
  end if;

  -- Which columns an update touched (updated_at is noise). An update that
  -- changed nothing else — the day upsert every schedule performs — is not a
  -- mutation and gets no row.
  if tg_op = 'UPDATE' then
    select array_agg(k order by k) into v_keys
    from jsonb_object_keys(v_new) k
    where k <> 'updated_at'
      and v_old -> k is distinct from v_new -> k;
    if v_keys is null or cardinality(v_keys) = 0 then
      return null;
    end if;
  end if;

  -- A draft's days, only if they are an array; each day's slots likewise.
  -- Anything else counts as no slots rather than failing the member's write.
  v_days := case when jsonb_typeof(v_new -> 'suggested_data' -> 'days') = 'array'
                 then v_new -> 'suggested_data' -> 'days' else '[]'::jsonb end;

  -- The structural projection, per table.
  v_proj := case tg_table_name
    when 'trip_blocks' then jsonb_build_object(
      'type', v_new -> 'type', 'source', v_new -> 'source',
      'place_id', v_new -> 'place_id', 'place_link', v_new -> 'place_link',
      'region_id', v_new -> 'region_id', 'trip_leg_id', v_new -> 'trip_leg_id')
    when 'itinerary_slots' then jsonb_build_object(
      'itinerary_day_id', v_new -> 'itinerary_day_id',
      'day_date', (select d.day_date from public.itinerary_days d where d.id = (v_new ->> 'itinerary_day_id')::uuid),
      'start_time', v_new -> 'start_time', 'end_time', v_new -> 'end_time',
      'end_day_date', v_new -> 'end_day_date', 'time_precision', v_new -> 'time_precision',
      'trip_block_id', v_new -> 'trip_block_id', 'is_locked', v_new -> 'is_locked')
    when 'itinerary_days' then jsonb_build_object('day_date', v_new -> 'day_date')
    when 'ai_suggestions' then jsonb_build_object(
      'suggestion_type', v_new -> 'suggestion_type', 'status', v_new -> 'status',
      'version', v_new -> 'version', 'plan_thread_id', v_new -> 'plan_thread_id',
      'slots', (select count(*) from jsonb_array_elements(v_days) d,
                                    jsonb_array_elements(case when jsonb_typeof(d -> 'slots') = 'array'
                                                              then d -> 'slots' else '[]'::jsonb end) s),
      'settled', (select count(*) from jsonb_array_elements(v_days) d,
                                      jsonb_array_elements(case when jsonb_typeof(d -> 'slots') = 'array'
                                                                then d -> 'slots' else '[]'::jsonb end) s
                  where s ? 'accepted_at' or s ? 'rejected_at'))
    when 'branches' then jsonb_build_object(
      'itinerary_slot_id', v_new -> 'itinerary_slot_id', 'trip_block_id', v_new -> 'trip_block_id',
      'resolution_mode', v_new -> 'resolution_mode', 'is_main', v_new -> 'is_main',
      'is_resolved', v_new -> 'is_resolved', 'conflict_group_id', v_new -> 'conflict_group_id')
    else '{}'::jsonb
  end;

  -- A cascade fires this trigger while its parent rows are already gone: a
  -- trip being deleted, a participant's account being erased. A reference to
  -- a row that no longer exists would fail the foreign key and abort the
  -- member's own delete, so each reference is kept only while its target is.
  insert into public.study_mutations
    (table_name, row_id, op, changed_keys, projection, origin_suggestion_id, origin_kind,
     actor_user_id, session_id, trip_id)
  values
    (tg_table_name, v_row_id, tg_op, v_keys, v_proj,
     case when exists (select 1 from public.study_suggestions x where x.id = v_suggestion) then v_suggestion end,
     v_kind,
     case when exists (select 1 from public.profiles p where p.id = v_actor) then v_actor end,
     v_session,
     case when exists (select 1 from public.trips t where t.id = v_trip) then v_trip end);
  return null;
end;
$$;

revoke all on function "public"."study_log_mutation"() from public;
revoke all on function "public"."study_log_mutation"() from "anon";
revoke all on function "public"."study_log_mutation"() from "authenticated";


-- 3. Study table grants --------------------------------------------------------------
--
-- Every study write goes through the API or the harness with the service key.
-- Participants read their own session, surveys, turns, thumbs and reactions
-- (the web consent gate and the account export); nothing else is readable
-- with a user's token.

revoke insert on table "public"."study_sessions"            from "authenticated";
revoke insert on table "public"."study_survey_demographics" from "authenticated";
revoke insert on table "public"."study_survey_post_task"    from "authenticated";
revoke insert on table "public"."study_suggestions"         from "authenticated";

revoke insert on table "public"."study_user_actions"        from "authenticated";
revoke insert on table "public"."study_feedback"            from "authenticated";

-- A participant's own thumbs and reactions are theirs to export: *Export my
-- data* reads through the caller's RLS client (account.service.ts), and the
-- consent form promises ratings and reactions are in it. Own rows only.
grant select on table "public"."study_feedback"     to "authenticated";
grant select on table "public"."study_user_actions" to "authenticated";

drop policy if exists "Participants view own study_feedback" on "public"."study_feedback";
create policy "Participants view own study_feedback" on "public"."study_feedback"
  for select using ((select auth.uid()) = "user_id");

drop policy if exists "Participants view own study_user_actions" on "public"."study_user_actions";
create policy "Participants view own study_user_actions" on "public"."study_user_actions"
  for select using ((select auth.uid()) = "actor_user_id");
revoke select, insert on table "public"."study_mutations"           from "authenticated";
revoke select, insert on table "public"."study_verdicts"            from "authenticated";
revoke select, insert on table "public"."study_runs"                from "authenticated";
revoke select, insert on table "public"."study_case_executions"     from "authenticated";
revoke select, insert on table "public"."study_scores"              from "authenticated";
revoke select, insert on table "public"."study_structural_verdicts" from "authenticated";
revoke select, insert on table "public"."study_comparisons"         from "authenticated";

revoke all on table "public"."study_sessions"            from "anon";
revoke all on table "public"."study_survey_demographics" from "anon";
revoke all on table "public"."study_survey_post_task"    from "anon";
revoke all on table "public"."study_suggestions"         from "anon";
revoke all on table "public"."study_user_actions"        from "anon";
revoke all on table "public"."study_feedback"            from "anon";
revoke all on table "public"."study_mutations"           from "anon";
revoke all on table "public"."study_verdicts"            from "anon";
revoke all on table "public"."study_runs"                from "anon";
revoke all on table "public"."study_case_executions"     from "anon";
revoke all on table "public"."study_scores"              from "anon";
revoke all on table "public"."study_structural_verdicts" from "anon";
revoke all on table "public"."study_comparisons"         from "anon";


-- 4. analytics_cost_rollup: no names in the admin dashboard --------------------------

create or replace function "public"."analytics_cost_rollup"("p_from" timestamp with time zone, "p_to" timestamp with time zone, "p_group" "text", "p_provider" "text" default null::"text", "p_user" "uuid" default null::"uuid") returns table("bucket" "text", "bucket_label" "text", "calls" bigint, "tokens_input" bigint, "tokens_output" bigint, "cost_usd" numeric)
    language "plpgsql" stable security definer
    set "search_path" to 'public'
    as $$
BEGIN
  IF p_group NOT IN ('day', 'user', 'provider', 'call_type', 'session') THEN
    RAISE EXCEPTION 'invalid group: %', p_group;
  END IF;

  RETURN QUERY
  WITH rolled AS (
    SELECT
      CASE p_group
        WHEN 'day'       THEN to_char(date_trunc('day', e.created_at), 'YYYY-MM-DD')
        WHEN 'user'      THEN COALESCE(e.user_id::TEXT, 'anonymous')
        WHEN 'provider'  THEN e.provider
        WHEN 'call_type' THEN e.provider || ':' || e.call_type
        WHEN 'session'   THEN COALESCE(e.session_id, 'unknown')
      END                       AS b,
      COUNT(*)                  AS calls,
      SUM(e.tokens_input)       AS tokens_input,
      SUM(e.tokens_output)      AS tokens_output,
      SUM(e.estimated_cost_usd) AS cost_usd
    FROM public.api_usage_events e
    WHERE e.created_at >= p_from
      AND e.created_at < p_to
      AND (p_provider IS NULL OR e.provider = p_provider)
      AND (p_user IS NULL OR e.user_id = p_user)
      -- The harness is not a customer.
      AND NOT public.is_simulated_account(e.user_id)
    GROUP BY 1
  )
  SELECT
    r.b,
    -- Admin views stay pseudonymous: a user bucket is its id, never a name.
    NULL::TEXT,
    r.calls,
    COALESCE(r.tokens_input, 0),
    COALESCE(r.tokens_output, 0),
    COALESCE(r.cost_usd, 0)
  FROM rolled r
  ORDER BY CASE WHEN p_group = 'day' THEN r.b END ASC,
           CASE WHEN p_group <> 'day' THEN r.cost_usd END DESC NULLS LAST;
END;
$$;

revoke all on function "public"."analytics_cost_rollup"(timestamp with time zone, timestamp with time zone, text, text, uuid) from public;
revoke all on function "public"."analytics_cost_rollup"(timestamp with time zone, timestamp with time zone, text, text, uuid) from "anon";
revoke all on function "public"."analytics_cost_rollup"(timestamp with time zone, timestamp with time zone, text, text, uuid) from "authenticated";
grant execute on function "public"."analytics_cost_rollup"(timestamp with time zone, timestamp with time zone, text, text, uuid) to "service_role";
