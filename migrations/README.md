# Migrations

The database migrations written for the instantiation, from the first study
schema (`20260918090000_study_instrumentation.sql`) onward, collected here so the
artifact can be read on its own.

These are **copies**. The schema of record is `supabase/migrations/` at the
repository root, and that is what `pnpm db:push` applies. Do not edit a file
here; author a new migration there and copy it in.

Four files are application-side rather than `study_*` schema, and are included
because they landed during the instantiation:
`20260921072916_analytics_agent_reliability.sql`,
`20260921073500_analytics_agent_reliability_grant_fix.sql`,
`20260921075038_analytics_exclude_simulated_accounts.sql` and
`20260921080822_analytics_agent_reliability_retries.sql`.
