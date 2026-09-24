-- Pair-wise judge verdicts, persisted (Q33).
--
-- Stage 3.2 compares every execution of a candidate run with its case's
-- baseline reply, in both orderings (D23). Until now the verdicts lived in a
-- JSON cache on one machine: they survived a lost kernel, but nothing in the
-- database said a run had ever been compared, and the result of the
-- regression stage sat outside the record it is joined with. Point-wise
-- scores had the same problem until D71 gave them `study_scores`; this is the
-- same fix for the other half of the judge.
--
-- Shaped after `study_scores` deliberately:
--
--   * keyed to what was compared plus WHICH judge compared it. The
--     uniqueness is (candidate execution, baseline execution, model, prompt
--     version), so re-judging under a new prompt adds a row instead of
--     overwriting one, and comparing against a different baseline does too.
--   * append-only in spirit: a verdict is never edited to say something
--     else. The one overwrite is a judge refusal being replaced by the verdict
--     a later retry obtained for the same key.
--   * a verdict is either decided or explained. `error` carries a judge
--     refusal; otherwise both orderings and the result are present.
--
-- `baseline_kind` and `baseline_key` say which baseline the verdict was taken
-- against: the adopted file (cases/baseline.json) or a test baseline, and a
-- hash of its entries. A rehearsal's verdicts can therefore never be read as
-- stage 3.2's.

create table if not exists "public"."study_comparisons" (
  "id"                     uuid primary key default gen_random_uuid(),
  "run_id"                 uuid not null references "public"."study_runs" ("id") on delete cascade,
  "execution_id"           uuid not null
                             references "public"."study_case_executions" ("id") on delete cascade,
  "baseline_execution_id"  uuid not null
                             references "public"."study_case_executions" ("id") on delete cascade,
  -- Denormalised so a verdict is readable without a join.
  "case_id"                text not null,
  "repetition"             integer not null,
  "attempt"                integer not null default 1,

  "baseline_kind"          text not null
                             constraint "study_comparisons_baseline_kind" check ("baseline_kind" in ('adopted', 'test')),
  "baseline_key"           text not null,

  "judge_model"            text not null,
  "judge_prompt_version"   text not null,

  -- The candidate execution's structural verdict when it was compared. D23
  -- lets a structural `detected` fail the execution whatever the judge says,
  -- so the pass decision needs it; a snapshot, because verdicts are appended
  -- (D76) and a later checker version may say something else.
  "structural_outcome"     text,

  -- The judge's two answers: the first with the candidate shown as B, the
  -- second with it shown as A (D23's position-bias control).
  "ordering_candidate_b"   text
                             constraint "study_comparisons_ordering_b" check ("ordering_candidate_b" in ('A', 'B', 'tie')),
  "ordering_candidate_a"   text
                             constraint "study_comparisons_ordering_a" check ("ordering_candidate_a" in ('A', 'B', 'tie')),
  "at_least_as_good"       boolean,
  "rationale"              text not null default '',
  "error"                  text,

  "created_at"             timestamptz not null default now(),

  constraint "study_comparisons_decided_or_explained" check (
    "error" is not null
    or ("ordering_candidate_b" is not null and "ordering_candidate_a" is not null
        and "at_least_as_good" is not null)
  ),
  constraint "study_comparisons_one_per_judge"
    unique ("execution_id", "baseline_execution_id", "judge_model", "judge_prompt_version")
);

create index if not exists "study_comparisons_run_idx" on "public"."study_comparisons" ("run_id");

comment on table "public"."study_comparisons" is
  'Pair-wise judge verdicts of a candidate execution against its case''s baseline reply, per judge version (Q33, D23). Both orderings kept. Mirrors study_scores, which does the same for point-wise scores.';

comment on column "public"."study_comparisons"."baseline_kind" is
  '''adopted'' for cases/baseline.json, ''test'' for a rehearsal baseline. A test verdict is never stage 3.2''s result.';

-- This database grants nothing by default and table privileges are checked
-- before RLS. Harness-written tables are service_role only: the harness holds
-- the secret key, and nothing in the application reads these.
alter table "public"."study_comparisons" enable row level security;
grant all on table "public"."study_comparisons" to "service_role";
