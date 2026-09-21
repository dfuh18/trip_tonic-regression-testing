-- Show recovered capacity pressure, not just the failures it eventually causes.
--
-- The first version of this rollup counted failed turns. But a 429 that the
-- backoff waits out leaves a *successful* turn behind (D43 — verified: a turn
-- retried once and completed where the old policy would have lost it), so the
-- panel read `capacity = 0` on a run that had in fact hit capacity. Retries are
-- the leading indicator: they climb before anything starts failing, which is
-- the point at which a capacity decision is still cheap.
--
-- `retryCount` now rides on the usage metadata of every agent turn, successful
-- or not (agent.service.ts, all three log sites).
--
-- The return type changes, so the function is dropped and recreated rather
-- than replaced.

drop function if exists "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text);

create function "public"."analytics_agent_reliability"(
  "p_from" timestamp with time zone,
  "p_to"   timestamp with time zone,
  "p_group" text default 'day'
)
returns table(
  "bucket"        text,
  "turns"         bigint,
  "ok"            bigint,
  "capacity"      bigint,
  "timeout"       bigint,
  "call_limit"    bigint,
  "empty_reply"   bigint,
  "other"         bigint,
  "turns_retried" bigint,
  "retries"       bigint,
  "failure_rate"  numeric,
  "capacity_rate" numeric,
  "retry_rate"    numeric
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
      count(*) filter (where e.status = 'error' and e.metadata->>'failureKind' = 'capacity')    as capacity,
      count(*) filter (where e.status = 'error' and e.metadata->>'failureKind' = 'timeout')     as timeout,
      count(*) filter (where e.status = 'error' and e.metadata->>'failureKind' = 'call_limit')  as call_limit,
      count(*) filter (where e.status = 'error' and e.metadata->>'failureKind' = 'empty_reply') as empty_reply,
      count(*) filter (
        where e.status = 'error'
          and coalesce(e.metadata->>'failureKind', 'other') not in
              ('capacity', 'timeout', 'call_limit', 'empty_reply')
      ) as other,
      -- A turn that was re-issued at least once, however it ended.
      count(*) filter (where coalesce((e.metadata->>'retryCount')::int, 0) > 0) as turns_retried,
      coalesce(sum(coalesce((e.metadata->>'retryCount')::int, 0)), 0)           as retries
    from public.api_usage_events e
    where e.created_at >= p_from
      and e.created_at <  p_to
      and e.call_type = 'agent_chat'
    group by 1
  )
  select
    r.b,
    r.turns, r.ok, r.capacity, r.timeout, r.call_limit, r.empty_reply, r.other,
    r.turns_retried, r.retries,
    round((r.turns - r.ok)::numeric  / nullif(r.turns, 0), 4) as failure_rate,
    round(r.capacity::numeric        / nullif(r.turns, 0), 4) as capacity_rate,
    round(r.turns_retried::numeric   / nullif(r.turns, 0), 4) as retry_rate
  from rolled r
  order by r.b;
end;
$$;

alter function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text)
  owner to "postgres";

-- service_role only: the API gates this on super admin, and a grant to
-- "authenticated" would let any signed-in member read it straight through
-- PostgREST where that guard is not in the path (see 20260921073500).
revoke all on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) from public;
revoke all on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) from "anon";
revoke all on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) from "authenticated";
grant execute on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) to "service_role";

comment on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) is
  'Per-bucket agent turns by outcome, plus retries. Separates provider overload (metadata.failureKind = capacity) from the agent''s own failures, and counts retries so recovered capacity pressure is visible before it costs turns. Aggregate and pseudonymous: no user, trip or message content.';
