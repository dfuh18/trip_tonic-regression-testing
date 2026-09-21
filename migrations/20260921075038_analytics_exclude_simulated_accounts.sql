-- Keep the regression harness out of the product's own numbers.
--
-- There is one Supabase project for everything (D15), so the simulated
-- accounts the thesis harness drives live beside real users. Every product
-- rollup counted them: a baseline and a regression run is ~256 agent turns and
-- ~256 trips from one fake account, which would show up as a very busy user in
-- DAU, cost-per-user and the funnel.
--
-- Two signals, neither of which depends on configuration:
--   * a `.invalid` email. RFC 2606 reserves the TLD as permanently
--     undeliverable, so an account on one is by construction not a person.
--     `src/auth.py` mints the harness accounts under sim.triptonic.invalid.
--   * a study session with run_type = 'simulation', which the harness sets at
--     session creation (D15/D16).
--
-- Deliberately NOT excluded from `analytics_agent_reliability`: that panel
-- measures how often the model provider is busy, and harness turns are
-- evidence for exactly that question.

create or replace function "public"."is_simulated_account"("p_user" uuid)
returns boolean
  language sql
  stable
  security definer
  set "search_path" to 'public'
as $$
  select p_user is not null and (
    exists (
      select 1 from auth.users u
      where u.id = p_user and u.email ilike '%.invalid'
    )
    or exists (
      select 1 from public.study_sessions s
      where s.user_id = p_user and s.run_type = 'simulation'
    )
  );
$$;

alter function "public"."is_simulated_account"(uuid) owner to "postgres";
revoke all on function "public"."is_simulated_account"(uuid) from public;
revoke all on function "public"."is_simulated_account"(uuid) from "anon";
revoke all on function "public"."is_simulated_account"(uuid) from "authenticated";
grant execute on function "public"."is_simulated_account"(uuid) to "service_role";

comment on function "public"."is_simulated_account"(uuid) is
  'True for a regression-harness account: a reserved .invalid email (RFC 2606) or a study session with run_type = simulation. Used to keep the harness out of product analytics; deliberately not applied to analytics_agent_reliability.';


-- analytics_cost_rollup ------------------------------------------------------

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
    CASE WHEN p_group = 'user' THEN
      (SELECT COALESCE(p.display_name, p.username) FROM public.profiles p WHERE p.id::TEXT = r.b)
    END,
    r.calls,
    COALESCE(r.tokens_input, 0),
    COALESCE(r.tokens_output, 0),
    COALESCE(r.cost_usd, 0)
  FROM rolled r
  ORDER BY CASE WHEN p_group = 'day' THEN r.b END ASC,
           CASE WHEN p_group <> 'day' THEN r.cost_usd END DESC NULLS LAST;
END;
$$;


-- analytics_event_rollup -----------------------------------------------------

create or replace function "public"."analytics_event_rollup"("p_from" timestamp with time zone, "p_to" timestamp with time zone, "p_group" "text") returns table("bucket" "text", "events" bigint, "users" bigint, "sessions" bigint)
    language "plpgsql" stable security definer
    set "search_path" to 'public'
    as $$
BEGIN
  IF p_group NOT IN ('day', 'event_name', 'path') THEN
    RAISE EXCEPTION 'invalid group: %', p_group;
  END IF;

  RETURN QUERY
  WITH rolled AS (
    SELECT
      CASE p_group
        WHEN 'day'        THEN to_char(date_trunc('day', e.created_at), 'YYYY-MM-DD')
        WHEN 'event_name' THEN e.event_name
        WHEN 'path'       THEN COALESCE(e.path, '(none)')
      END                          AS b,
      COUNT(*)                     AS ev,
      COUNT(DISTINCT e.user_id)    AS us,
      COUNT(DISTINCT e.session_id) AS se
    FROM public.ux_events e
    WHERE e.created_at >= p_from AND e.created_at < p_to
      AND NOT public.is_simulated_account(e.user_id)
    GROUP BY 1
  )
  SELECT r.b, r.ev, r.us, r.se
  FROM rolled r
  ORDER BY CASE WHEN p_group = 'day' THEN r.b END ASC,
           CASE WHEN p_group <> 'day' THEN r.ev END DESC NULLS LAST;
END;
$$;


-- analytics_active_users -----------------------------------------------------

create or replace function "public"."analytics_active_users"("p_from" timestamp with time zone, "p_to" timestamp with time zone) returns table("day" "text", "dau" bigint, "wau" bigint)
    language "sql" stable security definer
    set "search_path" to 'public'
    as $$
  SELECT
    to_char(d.day, 'YYYY-MM-DD'),
    (SELECT COUNT(DISTINCT e.user_id) FROM public.ux_events e
      WHERE e.user_id IS NOT NULL
        AND NOT public.is_simulated_account(e.user_id)
        AND e.created_at >= d.day AND e.created_at < d.day + INTERVAL '1 day'),
    (SELECT COUNT(DISTINCT e.user_id) FROM public.ux_events e
      WHERE e.user_id IS NOT NULL
        AND NOT public.is_simulated_account(e.user_id)
        AND e.created_at >= d.day - INTERVAL '6 days' AND e.created_at < d.day + INTERVAL '1 day')
  FROM generate_series(date_trunc('day', p_from), date_trunc('day', p_to), INTERVAL '1 day') AS d(day)
  ORDER BY 1;
$$;


-- analytics_funnel -----------------------------------------------------------

create or replace function "public"."analytics_funnel"("p_from" timestamp with time zone, "p_to" timestamp with time zone, "p_steps" "text"[]) returns table("step" "text", "sessions" bigint)
    language "sql" stable security definer
    set "search_path" to 'public'
    as $$
  SELECT
    s.step,
    (SELECT COUNT(DISTINCT e.session_id) FROM public.ux_events e
      WHERE e.event_name = s.step
        AND NOT public.is_simulated_account(e.user_id)
        AND e.created_at >= p_from AND e.created_at < p_to)
  FROM unnest(p_steps) WITH ORDINALITY AS s(step, ord)
  ORDER BY s.ord;
$$;
