-- Study mutation origin, follow-up (A04): the first live run showed that an
-- upsert of an itinerary day that changes nothing — which every schedule
-- performs — logged an UPDATE with no changed keys. A no-op is not a mutation.
-- Same function, one guard added; the triggers stay as installed.

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
  if v_session is null then
    return null;
  end if;

  -- The declared origin, if the client sent one.
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
    v_suggestion := substring(v_header from 'suggestion=([0-9a-fA-F-]{36})')::uuid;
    v_draft      := substring(v_header from 'draft=([0-9a-fA-F-]{36})')::uuid;
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
      'slots', (select count(*) from jsonb_array_elements(coalesce(v_new -> 'suggested_data' -> 'days', '[]'::jsonb)) d,
                                    jsonb_array_elements(coalesce(d -> 'slots', '[]'::jsonb)) s),
      'settled', (select count(*) from jsonb_array_elements(coalesce(v_new -> 'suggested_data' -> 'days', '[]'::jsonb)) d,
                                      jsonb_array_elements(coalesce(d -> 'slots', '[]'::jsonb)) s
                  where s ? 'accepted_at' or s ? 'rejected_at'))
    when 'branches' then jsonb_build_object(
      'itinerary_slot_id', v_new -> 'itinerary_slot_id', 'trip_block_id', v_new -> 'trip_block_id',
      'resolution_mode', v_new -> 'resolution_mode', 'is_main', v_new -> 'is_main',
      'is_resolved', v_new -> 'is_resolved', 'conflict_group_id', v_new -> 'conflict_group_id')
    else '{}'::jsonb
  end;

  insert into public.study_mutations
    (table_name, row_id, op, changed_keys, projection, origin_suggestion_id, origin_kind,
     actor_user_id, session_id, trip_id)
  values
    (tg_table_name, v_row_id, tg_op, v_keys, v_proj, v_suggestion, v_kind,
     v_actor, v_session, v_trip);
  return null;
end;
$$;

revoke all on function "public"."study_log_mutation"() from public;
