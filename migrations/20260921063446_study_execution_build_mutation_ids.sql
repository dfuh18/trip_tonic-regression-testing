-- Which mutation rows on this execution's trip were the fixture build's.
--
-- Since D38 every repetition gets its own trip and nothing is deleted, so the
-- build's own writes — five stops, four days, three slots, through the
-- member's API — sit on the trip beside whatever the case did. The runner
-- excludes them while it collects, but the structural checker also runs after
-- the fact, and re-reading the trip afterwards would count the fixture as the
-- case's work.
--
-- Recorded as ids rather than inferred. The inference is available (on a
-- simulation trip a `user_manual` row with no origin suggestion can only be
-- the build) but it is an argument, and an argument stops being true the first
-- time a case does something nobody anticipated. The ids are a fact.
--
-- Additive: one nullable column on a harness-written, simulation-only table;
-- no grant needed, privileges are per table.

alter table "public"."study_case_executions"
  add column if not exists "build_mutation_ids" uuid[] not null default '{}'::uuid[];

comment on column "public"."study_case_executions"."build_mutation_ids" is
  'study_mutations ids written by this repetition''s fixture build, before the case began (D38). Excluded from the execution''s own mutations by the runner and by the structural checker. Empty is a legitimate value only for a build that wrote nothing.';
