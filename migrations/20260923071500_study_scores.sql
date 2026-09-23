-- Point-wise judge scores, persisted (D71).
--
-- Until now they were not. `score_run` returned an in-memory object and the
-- numbers existed only in a notebook's output cell: a lost kernel cost a full
-- judge pass, and nothing could join a score to the structural verdict for the
-- same execution without re-judging. The structural side has had
-- `study_verdicts` since the beginning, so this was an asymmetry rather than a
-- decision — the analysis in 4.3 reads both.
--
-- Shaped after `study_verdicts` deliberately:
--
--   * keyed to what was judged plus WHICH judge judged it, so re-scoring under
--     a new prompt or a new model adds a row instead of overwriting one. The
--     uniqueness is (execution, model, prompt version) for that reason.
--   * append-only. Nothing here is ever edited; a disagreement between two
--     judge versions is data, and resolving it by overwriting would destroy
--     the only evidence that they disagreed.
--   * `score` is nullable, because "not scored" is a real outcome with its own
--     cause: the execution produced no reply, or the judge itself refused.
--     `error` carries which. A row with a null score and a null error would be
--     a bug, and the check below says so.
--
-- It is keyed to the EXECUTION and not to a suggestion, unlike the structural
-- verdict: D34 settles that the judge scores the first reply of an execution
-- against the case's rubric, while the checker describes the whole execution
-- turn by turn. Different subjects, different keys.

create table if not exists "public"."study_scores" (
  "id"                   uuid primary key default gen_random_uuid(),
  "execution_id"         uuid not null
                           references "public"."study_case_executions" ("id") on delete cascade,
  -- Denormalised so a score is readable without a join, and so a run's scores
  -- survive as an interpretable record. The execution is still the key.
  "run_id"               uuid not null references "public"."study_runs" ("id") on delete cascade,
  "case_id"              text not null,
  "repetition"           integer not null,
  "attempt"              integer not null default 1,

  "judge_model"          text not null,
  "judge_prompt_version" text not null,

  "score"                integer
                           constraint "study_scores_range" check ("score" between 1 and 10),
  "rationale"            text not null default '',
  "reply_chars"          integer not null default 0,
  -- Why there is no score: 'no reply to score (the execution produced none)',
  -- or the judge's own refusal after its retries were spent.
  "error"                text,

  "created_at"           timestamptz not null default now(),

  constraint "study_scores_scored_or_explained"
    check ("score" is not null or "error" is not null),
  constraint "study_scores_one_per_judge"
    unique ("execution_id", "judge_model", "judge_prompt_version")
);

create index if not exists "study_scores_run_idx" on "public"."study_scores" ("run_id");

comment on table "public"."study_scores" is
  'Point-wise judge scores per execution and judge version (D71). Append-only: re-scoring under a new judge model or prompt version adds a row, nothing is edited. Mirrors study_verdicts, which does the same for the structural checker.';

comment on column "public"."study_scores"."score" is
  '1..10, or null when the execution could not be scored — see error. The judge is an instrument, so a refusal from it is a missing measurement rather than a low score (D70).';

comment on column "public"."study_scores"."attempt" is
  'Which attempt of the repetition was scored. D53 keeps every attempt; the pass rate reads the highest, and so does the judge.';

-- This database grants nothing by default and table privileges are checked
-- before RLS, so a policy without a grant fails with 42501 before any policy
-- is consulted. Harness-written tables are service_role only: the harness
-- holds the secret key, and nothing in the application reads these.
alter table "public"."study_scores" enable row level security;
grant all on table "public"."study_scores" to "service_role";
