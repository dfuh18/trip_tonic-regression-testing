-- Correct the grant on analytics_agent_reliability.
--
-- 20260921072916 granted EXECUTE to "authenticated", which was wrong twice
-- over. It is not enough: the analytics service calls this RPC with the
-- service-key client, so the call failed with 42501 for the only caller there
-- is. And it is too much: every other analytics rollup is granted to
-- service_role alone, because granting "authenticated" lets any signed-in
-- member call an admin-only aggregate straight through PostgREST, where the
-- API's requireSuperAdmin guard is not in the path at all.
--
-- The rule this is an instance of: the guard lives in the API, so the grant
-- must not hand the function to anyone who can reach PostgREST directly.

revoke all on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) from "authenticated";
revoke all on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) from "anon";
grant execute on function "public"."analytics_agent_reliability"(timestamp with time zone, timestamp with time zone, text) to "service_role";
