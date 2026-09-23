-- Structural verdicts, appended and versioned (D76).
--
-- `checker.record()` was an UPDATE on `study_case_executions`, and
-- `CHECKER_VERSION` existed but was never persisted. Re-checking a run
-- therefore rewrote its verdicts in place, with nothing saying which checker
-- or which case text produced either the old value or the new one.
--
-- The damage is in the record already and is what prompted this. After D72
-- rewrote the drinks case, the runs that happened to be re-checked were
-- silently changed and the ones that were not kept their old verdict:
--
--     09f288e9  venue_lookup_..._dir4_not_a_meal  detected (1 finding)
--     3cf2fd09  same case                          none     (overwritten)
--
-- Two runs disagree in the record for a reason the record cannot explain. The
-- `study_scores` migration made the opposite argument three days earlier —
-- "a disagreement between two judge versions is data, and resolving it by
-- overwriting would destroy the only evidence that they disagreed" — and that
-- argument applies here unchanged. It was applied to scores and not to
-- verdicts.
--
-- So: one row per (execution, checker version), appended. Re-checking under a
-- new checker adds a row. `case_version` records which text was judged, which
-- is the other half of the question — a verdict is only interpretable against
-- the case it was computed from, and cases are edited (D48, D55, D58, D72).
--
-- `study_case_executions.structural_outcome` stays as a convenience mirror of
-- the most recent verdict, because every existing reader uses it. It is no
-- longer the only copy, which is the point.

create table if not exists "public"."study_structural_verdicts" (
  "id"              uuid primary key default gen_random_uuid(),
  "execution_id"    uuid not null
                      references "public"."study_case_executions" ("id") on delete cascade,
  "run_id"          uuid not null references "public"."study_runs" ("id") on delete cascade,
  "case_id"         text not null,
  "repetition"      integer not null,
  "attempt"         integer not null default 1,

  -- Which checker produced this, and which case text it judged.
  "checker_version" text not null,
  "case_version"    text,

  "outcome"         text not null
                      constraint "study_structural_verdicts_outcome"
                      check ("outcome" in ('none', 'detected')),
  "findings"        jsonb not null default '[]'::jsonb,

  "created_at"      timestamptz not null default now(),

  -- A verdict is identified by what produced it. Re-running the same checker
  -- over the same execution is idempotent; a new checker appends.
  constraint "study_structural_verdicts_one_per_checker"
    unique ("execution_id", "checker_version")
);

create index if not exists "study_structural_verdicts_run_idx"
  on "public"."study_structural_verdicts" ("run_id");

comment on table "public"."study_structural_verdicts" is
  'Structural checker output per execution and checker version (D76). Append-only: a new checker version adds a row, nothing is edited. Mirrors study_scores, which does the same for the judge. study_case_executions.structural_outcome remains a convenience mirror of the latest verdict.';

comment on column "public"."study_structural_verdicts"."case_version" is
  'The case text this verdict judged (D74). A verdict is only interpretable against the case it was computed from, and cases are edited — D72 inverted an assertion, which is how two runs came to disagree in the record with nothing explaining why.';

-- Nothing is granted by default and privileges are checked before RLS, so a
-- policy without a grant fails with 42501. Harness-written, service_role only.
alter table "public"."study_structural_verdicts" enable row level security;
grant all on table "public"."study_structural_verdicts" to "service_role";
