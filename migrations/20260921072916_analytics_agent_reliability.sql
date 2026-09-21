-- How often an agent turn fails, and why — for the super-admin dashboard.
--
-- The provider being busy is not the same thing as the agent failing to
-- answer: one may need a capacity decision (a paid tier, reserved throughput,
-- a different model), the other is a product bug. Until now both landed in
-- api_usage_events as status = 'error' and were indistinguishable, so nobody
-- could tell whether a bad week was Google's or ours.
--
-- `status` is constrained to ok|error, so the reason rides in
-- metadata->>'failureKind' (agent.service.ts, AgentFailureKind).
--
-- Aggregate, non-content and pseudonymous, per the no-admin-view-of-user-
-- content decision (docs/DECISION_ai_conversation_privacy.md): counts and
-- rates only, no user_id, no trip, no message text. Nothing here can be
-- resolved back to a person.

create or replace function "public"."analytics_agent_reliability"(
  "p_from" timestamp with time zone,
  "p_to"   timestamp with time zone,
  "p_group" text default 'day'
)
returns table(
  "bucket"      text,
  "turns"       bigint,
  "ok"          bigint,
  "capacity"    bigint,
  "timeout"     bigint,
  "call_limit"  bigint,
  "empty_reply" bigint,
  "other"       bigint,
  "failure_rate"  numeric,
  "capacity_rate" numeric
)
  language plpgsql
  stable
  security definer
  set "search_path" to 'public'
as $$
begin
  if p_group not in ('day', 'hour') then
    raise exception 'invalid group: %', p_group;
  end if;

  return query
  with rolled as (
    select
      case p_group
        when 'day'  then to_char(date_trunc('day',  e.created_at), 'YYYY-MM-DD')
        when 'hour' then to_char(date_trunc('hour', e.created_at), 'YYYY-MM-DD HH24:00')
      end as b,
      count(*) as turns,
      count(*) filter (where e.status = 'ok') as ok,
      -- An older row predates failureKind; it is a failure of unknown reason
      -- and counts as 'other' rather than being dropped, so the totals add up.
      count(*) filter (where e.status = 'error' and e.metadata->>'failureKind' = 'capacity')    as capacity,
      count(*) filter (where e.status = 'error' and e.metadata->>'failureKind' = 'timeout')     as timeout,
      count(*) filter (where e.status = 'error' and e.metadata->>'failureKind' = 'call_limit')  as call_limit,
      count(*) filter (where e.status = 'error' and e.metadata->>'failureKind' = 'empty_reply') as empty_reply,
      count(*) filter (
        where e.status = 'error'
          and coalesce(e.metadata->>'failureKind', 'other') not in
              ('capacity', 'timeout', 'call_limit', 'empty_reply')
      ) as other
    from public.api_usage_events e
    where e.created_at >= p_from
      and e.created_at <  p_to
      and e.call_type = 'agent_chat'
    group by 1
  )
  select
    r.b,
    r.turns, r.ok, r.capacity, r.timeout, r.call_limit, r.empty_reply, r.other,
    round((r.turns - r.ok)::numeric / nullif(r.turns, 0), 4) as failure_rate,
    round(r.capacity::numeric      / nullif(r.turns, 0), 4)  as capacity_rate
  from rolled r
  order by r.b;
end;
$$;

alter function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text)
  owner to "postgres";

-- This database grants nothing by default, and a policy is not a permission:
-- without this the RPC fails with 42501 before any check runs. The route is
-- additionally gated on super admin in the API (routes/analytics/guards.ts),
-- the same as every other analytics rollup.
revoke all on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) from public;
grant execute on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) to "authenticated";

comment on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) is
  'Per-bucket counts of agent turns by outcome, from api_usage_events where call_type = agent_chat. Separates provider overload (metadata.failureKind = capacity) from the agent''s own failures. Aggregate and pseudonymous: no user, trip or message content.';
