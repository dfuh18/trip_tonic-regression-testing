-- A repetition may be attempted more than once when the provider refuses it.
--
-- D44 ruled that an execution lost to provider overload counts as a failure of
-- the case. Measurement then put a number on that ruling: across 133 recorded
-- executions, 3.8% failed on a provider 429 or 504. Under D23's 8/8 seed
-- criterion that is a 1 - 0.962^8 = roughly 27% chance that any given seed
-- fails a baseline run for a reason that has nothing to do with the agent --
-- two or three of ten seeds per run, and a published pass rate carrying the
-- provider's availability inside it.
--
-- So a repetition refused by the provider is attempted once more. Both
-- attempts are kept: the failure is evidence about the platform and the
-- completed one is evidence about the agent, and collapsing them would lose
-- the first. `attempt` starts at 1 and the uniqueness moves with it.
--
-- Reading it afterwards: the pass rate takes the HIGHEST attempt per (run,
-- case, repetition); the platform-failure rate counts the superseded rows.
-- Neither is recoverable if the rows are merged, which is why this is a
-- column and not an overwrite.

alter table "public"."study_case_executions"
  add column if not exists "attempt" integer not null default 1;

alter table "public"."study_case_executions"
  drop constraint if exists "study_case_executions_one_per_repetition";

alter table "public"."study_case_executions"
  add constraint "study_case_executions_one_per_attempt"
  unique ("run_id", "case_id", "repetition", "attempt");

comment on column "public"."study_case_executions"."attempt" is
  'Which attempt at this repetition this row is. 1 unless the provider refused the first (429/504) and the runner re-ran it once (D53). The pass rate reads the highest attempt per repetition; the superseded rows are the platform failure rate.';
