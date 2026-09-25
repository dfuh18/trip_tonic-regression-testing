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

begin;

do $$
declare
  v_user uuid := (select user_id from public.study_sessions where run_type = 'simulation' and user_id is not null limit 1);
  v_old uuid := gen_random_uuid();
  v_new uuid := gen_random_uuid();
  v_turn uuid := gen_random_uuid();
  v_turn_new uuid := gen_random_uuid();
  v_count integer;
  r record;
begin
  if v_user is null then
    raise exception 'ANONYMISE_TEST_SETUP: no simulation account to borrow';
  end if;

  insert into public.study_sessions (id, user_id, run_type, consent_version, consent_at, device_type, client_session_id, created_at)
  values (v_old, v_user, 'pilot', 'test', now() - interval '9 months', 'desktop', 'browser-old', now() - interval '9 months'),
         (v_new, v_user, 'pilot', 'test', now() - interval '1 month', 'desktop', 'browser-new', now() - interval '1 month');

  insert into public.study_suggestions (id, session_id, user_id, turn_index, user_turn, occurred_at, tool_call_trace, resulting_state_shape, request_type)
  values (v_turn, v_old, v_user, 1, 'seafood near Alfama for my sister', now() - interval '9 months',
          '[{"kind":"llm","seq":1,"model":"m"},{"kind":"tool","seq":2,"tool":"search_places","args":{"query":"seafood","near":{"lat":38.7,"names":["Alfama"]}},"result_found":true}]',
          '{"draft":{"suggestion_id":"11111111-1111-1111-1111-111111111111","slots":3},"trip_after":{"blocks":4,"slots":2}}',
          'venue_lookup'),
         (v_turn_new, v_new, v_user, 1, 'recent request', now() - interval '1 month', '[]', '{"draft":null}', 'advisory');

  insert into public.study_survey_demographics (session_id, user_id, age, gender, education_level, llm_familiarity)
  values (v_old, v_user, 30, 'prefer_not_to_say', 'bachelor', 'weekly');
  insert into public.study_survey_post_task (session_id, user_id, umux_lite_capability, umux_lite_ease, free_text, submitted_at)
  values (v_old, v_user, 6, 5, 'my own words', now() - interval '9 months');
  insert into public.study_feedback (session_id, user_id, value) values (v_old, v_user, 'up');
  insert into public.study_user_actions (suggestion_id, target, action, actor_user_id)
  values (v_turn, 'slot:2026-11-07:0', 'accepted', v_user);
  insert into public.study_mutations (table_name, row_id, op, changed_keys, projection, origin_suggestion_id, origin_kind, actor_user_id, session_id)
  values ('itinerary_slots', gen_random_uuid(), 'INSERT', array['trip_block_id'],
          '{"day_date":"2026-11-07","start_time":"10:00","trip_block_id":"22222222-2222-2222-2222-222222222222","itinerary_day_id":"33333333-3333-3333-3333-333333333333"}',
          v_turn, 'agent_draft_accepted', v_user, v_old);

  v_count := public.study_anonymise_expired();
  if v_count <> 1 then raise exception 'ANONYMISE_TEST_FAIL: expected 1 session, got %', v_count; end if;

  select * into r from public.study_sessions where id = v_old;
  if r.user_id is not null or r.client_session_id is not null or r.anonymised_at is null or r.consent_at is null then
    raise exception 'ANONYMISE_TEST_FAIL: old session %', row_to_json(r); end if;

  select * into r from public.study_suggestions where id = v_turn;
  if r.user_id is not null or r.user_turn is not null or r.request_type <> 'venue_lookup'
     or r.tool_call_trace -> 1 ->> 'tool' <> 'search_places'
     or r.tool_call_trace -> 1 -> 'args' <> '{"query":null,"near":{"lat":null,"names":[null]}}'::jsonb
     or r.tool_call_trace -> 1 -> 'result_found' <> 'true'::jsonb
     or r.tool_call_trace -> 0 ->> 'model' <> 'm'
     or r.resulting_state_shape -> 'draft' ? 'suggestion_id'
     or r.resulting_state_shape -> 'draft' -> 'slots' <> '3'::jsonb
     or r.resulting_state_shape -> 'trip_after' <> '{"blocks":4,"slots":2}'::jsonb then
    raise exception 'ANONYMISE_TEST_FAIL: old turn %', row_to_json(r); end if;

  if exists (select 1 from public.study_survey_demographics where session_id = v_old and (user_id is not null or age <> 30))
     or exists (select 1 from public.study_survey_post_task where session_id = v_old and (user_id is not null or free_text is not null or umux_lite_capability <> 6))
     or exists (select 1 from public.study_feedback where session_id = v_old and (user_id is not null or value <> 'up'))
     or exists (select 1 from public.study_user_actions where suggestion_id = v_turn and (actor_user_id is not null or action <> 'accepted'))
     or exists (select 1 from public.study_mutations where session_id = v_old
                and (actor_user_id is not null or row_id is not null or origin_suggestion_id <> v_turn
                     or projection <> '{"day_date":"2026-11-07","start_time":"10:00"}'::jsonb)) then
    raise exception 'ANONYMISE_TEST_FAIL: a dependent row kept a link, lost a value, or kept an id';
  end if;

  select * into r from public.study_suggestions where id = v_turn_new;
  if r.user_id is null or r.user_turn <> 'recent request'
     or (select anonymised_at from public.study_sessions where id = v_new) is not null then
    raise exception 'ANONYMISE_TEST_FAIL: the recent session was touched'; end if;

  if public.study_anonymise_expired() <> 0 then
    raise exception 'ANONYMISE_TEST_FAIL: a second run found work'; end if;

  raise exception 'ANONYMISE_TEST_OK: 1 expired session anonymised, the recent one untouched, a second run is a no-op';
end $$;

rollback;
