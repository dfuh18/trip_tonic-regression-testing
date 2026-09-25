-- Live test of study_anonymise_expired() (D91) that leaves nothing behind.
--
-- Builds two pilot sessions on a simulation account (one consented nine
-- months ago, one last month), runs the job, checks every promise the consent
-- form makes, and then RAISES. The exception aborts the transaction, so every
-- row written here is rolled back whatever happens; the message says whether
-- the checks passed. Never commits.
--
--   pnpm supabase db query --linked -f research/regression-testing/tools/anonymise_rollback_test.sql
--
-- Expected output: an error reading "ANONYMISE_TEST_OK ...". Anything else is
-- a failure. Before the migration is pushed, prepend the migration file.
--
-- Checked since 20260925125438_study_privacy_hardening: account links, text
-- and ids removed; every timestamp of the old session rounded to the day (the
-- tool trace's started_at included) while durations and tokens stay; place
-- ids stripped from action targets; the participant's api_usage_events rows
-- inside [consent, last turn + 1 hour] lose user/trip/session while rows
-- outside it keep them; the recent session untouched; a second run a no-op.

begin;

do $$
declare
  v_user uuid := (select user_id from public.study_sessions where run_type = 'simulation' and user_id is not null limit 1);
  v_trip uuid := (select id from public.trips limit 1);
  v_old uuid := gen_random_uuid();
  v_new uuid := gen_random_uuid();
  v_turn uuid := gen_random_uuid();
  v_turn_new uuid := gen_random_uuid();
  -- Consent at 10:17:03 nine months ago, so every rounding is observable.
  v_day timestamptz := date_trunc('day', now() - interval '9 months');
  v_t0 timestamptz := date_trunc('day', now() - interval '9 months') + interval '10 hours 17 minutes 3 seconds';
  v_recent timestamptz := now() - interval '1 month';
  v_use_in uuid := gen_random_uuid();
  v_use_before uuid := gen_random_uuid();
  v_use_after uuid := gen_random_uuid();
  v_count integer;
  r record;
begin
  if v_user is null then
    raise exception 'ANONYMISE_TEST_SETUP: no simulation account to borrow';
  end if;

  insert into public.study_sessions (id, user_id, run_type, consent_version, consent_at, device_type, client_session_id, created_at)
  values (v_old, v_user, 'pilot', 'test', v_t0, 'desktop', 'browser-old', v_t0),
         (v_new, v_user, 'pilot', 'test', v_recent, 'desktop', 'browser-new', v_recent);

  insert into public.study_suggestions (id, session_id, user_id, turn_index, user_turn, occurred_at, completed_at, latency_ms, tool_call_trace, resulting_state_shape, request_type)
  values (v_turn, v_old, v_user, 1, 'seafood near Alfama for my sister', v_t0 + interval '5 minutes', v_t0 + interval '6 minutes', 60000,
          jsonb_build_array(
            '{"kind":"llm","seq":1,"model":"m"}'::jsonb,
            jsonb_build_object('kind', 'tool', 'seq', 2, 'tool', 'search_places',
                               'args', '{"query":"seafood","near":{"lat":38.7,"names":["Alfama"]}}'::jsonb,
                               'started_at', to_char((v_t0 + interval '5 minutes 1 second') at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                               'duration_ms', 812, 'result_found', true)),
          '{"draft":{"suggestion_id":"11111111-1111-1111-1111-111111111111","slots":3},"trip_after":{"blocks":4,"slots":2}}',
          'venue_lookup'),
         (v_turn_new, v_new, v_user, 1, 'recent request', v_recent, v_recent, 1000, '[]', '{"draft":null}', 'advisory');

  insert into public.study_survey_demographics (session_id, user_id, age, gender, education_level, llm_familiarity, submitted_at)
  values (v_old, v_user, 30, 'prefer_not_to_say', 'bachelor', 'weekly', v_t0 + interval '1 minute');
  insert into public.study_survey_post_task (session_id, user_id, umux_lite_capability, umux_lite_ease, free_text, submitted_at)
  values (v_old, v_user, 6, 5, 'my own words', v_t0 + interval '30 minutes');
  insert into public.study_feedback (session_id, user_id, value, created_at, updated_at)
  values (v_old, v_user, 'up', v_t0 + interval '7 minutes', v_t0 + interval '8 minutes');
  insert into public.study_user_actions (suggestion_id, target, action, actor_user_id, created_at)
  values (v_turn, 'slot:2026-11-07:0', 'accepted', v_user, v_t0 + interval '9 minutes'),
         (v_turn, 'place:ChIJN1t_tDeuEmsRUsoyG83frY4', 'accepted', v_user, v_t0 + interval '9 minutes');
  insert into public.study_mutations (table_name, row_id, op, changed_keys, projection, origin_suggestion_id, origin_kind, actor_user_id, session_id, occurred_at)
  values ('itinerary_slots', gen_random_uuid(), 'INSERT', array['trip_block_id'],
          '{"day_date":"2026-11-07","start_time":"10:00","trip_block_id":"22222222-2222-2222-2222-222222222222","itinerary_day_id":"33333333-3333-3333-3333-333333333333"}',
          v_turn, 'agent_draft_accepted', v_user, v_old, v_t0 + interval '10 minutes');

  -- The participant's usage rows: one inside the window, one before consent,
  -- one more than an hour after the last turn completed.
  insert into public.api_usage_events (id, user_id, trip_id, session_id, provider, call_type, tokens_input, tokens_output, latency_ms, created_at)
  values (v_use_in,     v_user, v_trip, 'sess-in',     'vertex', 'agent', 100, 20, 900, v_t0 + interval '5 minutes 30 seconds'),
         (v_use_before, v_user, v_trip, 'sess-before', 'vertex', 'agent', 100, 20, 900, v_t0 - interval '1 hour'),
         (v_use_after,  v_user, v_trip, 'sess-after',  'vertex', 'agent', 100, 20, 900, v_t0 + interval '67 minutes');

  v_count := public.study_anonymise_expired();
  if v_count <> 1 then raise exception 'ANONYMISE_TEST_FAIL: expected 1 session, got %', v_count; end if;

  select * into r from public.study_sessions where id = v_old;
  if r.user_id is not null or r.client_session_id is not null or r.anonymised_at is null
     or r.consent_at is distinct from v_day or r.created_at is distinct from v_day then
    raise exception 'ANONYMISE_TEST_FAIL: old session %', row_to_json(r); end if;

  select * into r from public.study_suggestions where id = v_turn;
  if r.user_id is not null or r.user_turn is not null or r.request_type <> 'venue_lookup'
     or r.occurred_at is distinct from v_day or r.completed_at is distinct from v_day
     or r.latency_ms <> 60000
     or r.tool_call_trace -> 1 ->> 'tool' <> 'search_places'
     or r.tool_call_trace -> 1 -> 'args' <> '{"query":null,"near":{"lat":null,"names":[null]}}'::jsonb
     or r.tool_call_trace -> 1 -> 'result_found' <> 'true'::jsonb
     or r.tool_call_trace -> 1 -> 'duration_ms' <> '812'::jsonb
     or r.tool_call_trace -> 1 ->> 'started_at' <> to_char(v_day at time zone 'UTC', 'YYYY-MM-DD') || 'T00:00:00.000Z'
     or r.tool_call_trace -> 0 ->> 'model' <> 'm'
     or r.resulting_state_shape -> 'draft' ? 'suggestion_id'
     or r.resulting_state_shape -> 'draft' -> 'slots' <> '3'::jsonb
     or r.resulting_state_shape -> 'trip_after' <> '{"blocks":4,"slots":2}'::jsonb then
    raise exception 'ANONYMISE_TEST_FAIL: old turn %', row_to_json(r); end if;

  if exists (select 1 from public.study_survey_demographics where session_id = v_old
             and (user_id is not null or age <> 30 or submitted_at is distinct from v_day))
     or exists (select 1 from public.study_survey_post_task where session_id = v_old
                and (user_id is not null or free_text is not null or umux_lite_capability <> 6 or submitted_at is distinct from v_day))
     or exists (select 1 from public.study_feedback where session_id = v_old
                and (user_id is not null or value <> 'up' or created_at is distinct from v_day or updated_at is distinct from v_day))
     or exists (select 1 from public.study_user_actions where suggestion_id = v_turn
                and (actor_user_id is not null or action <> 'accepted' or created_at is distinct from v_day
                     or target not in ('slot:2026-11-07:0', 'place')))
     or (select count(*) from public.study_user_actions where suggestion_id = v_turn and target = 'place') <> 1
     or exists (select 1 from public.study_mutations where session_id = v_old
                and (actor_user_id is not null or row_id is not null or origin_suggestion_id <> v_turn
                     or occurred_at is distinct from v_day
                     or projection <> '{"day_date":"2026-11-07","start_time":"10:00"}'::jsonb)) then
    raise exception 'ANONYMISE_TEST_FAIL: a dependent row kept a link, lost a value, kept an id or kept an exact time';
  end if;

  if exists (select 1 from public.api_usage_events where id = v_use_in
             and (user_id is not null or trip_id is not null or session_id is not null or tokens_input <> 100)) then
    raise exception 'ANONYMISE_TEST_FAIL: the usage row inside the window kept its link'; end if;
  if (select count(*) from public.api_usage_events where id in (v_use_before, v_use_after)
      and user_id = v_user and trip_id is not distinct from v_trip and session_id is not null) <> 2 then
    raise exception 'ANONYMISE_TEST_FAIL: a usage row outside the window lost its link'; end if;

  select * into r from public.study_suggestions where id = v_turn_new;
  if r.user_id is null or r.user_turn <> 'recent request' or r.occurred_at is distinct from v_recent
     or (select anonymised_at from public.study_sessions where id = v_new) is not null
     or (select consent_at from public.study_sessions where id = v_new) is distinct from v_recent then
    raise exception 'ANONYMISE_TEST_FAIL: the recent session was touched'; end if;

  if public.study_anonymise_expired() <> 0 then
    raise exception 'ANONYMISE_TEST_FAIL: a second run found work'; end if;

  raise exception 'ANONYMISE_TEST_OK: 1 expired session anonymised (times rounded to the day, place id stripped, the usage row in the window cut and the 2 outside kept), the recent one untouched, a second run is a no-op';
end $$;

rollback;
