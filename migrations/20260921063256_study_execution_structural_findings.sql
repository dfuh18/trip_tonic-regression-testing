-- The structural checker's findings live with the execution they describe.
--
-- `study_case_executions.structural_outcome` already records none|detected,
-- but had nowhere to say *why*. A check is a claim about the whole execution
-- and not about one turn (D27), so the findings belong on the execution row
-- rather than on `study_verdicts`, which is keyed per suggestion and is
-- reserved for verdicts computed after the fact over participant rows.
--
-- Additive: one nullable column on a harness-written, simulation-only table.
-- No grant is needed — privileges are per table and `study_case_executions`
-- already carries its own from 20260918090000.

alter table "public"."study_case_executions"
  add column if not exists "structural_findings" jsonb not null default '[]'::jsonb;

comment on column "public"."study_case_executions"."structural_findings" is
  'Structural checker findings for this execution, as an ordered array of strings a reader can act on ("expected search_places before propose_plan; got propose_plan first"). Empty when the outcome is none. Written by the harness beside structural_outcome (D27, B08); never by the application.';
