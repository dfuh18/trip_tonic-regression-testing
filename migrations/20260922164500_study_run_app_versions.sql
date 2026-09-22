-- The version of the two applications a run exercised.
--
-- `git_sha` already recorded the harness's working tree, which is not the same
-- question as "what was actually serving". A full regression suite once ran
-- against a stale dev server: the code on disk carried the fix, the process on
-- port 3001 did not, and every number in that run described the old behaviour
-- while the record pointed at the new commit. Nothing in the schema could have
-- revealed it.
--
-- `api_version` and `api_commit` are therefore read from the RUNNING API's own
-- /health endpoint, not from the repository. When `api_commit` and `git_sha`
-- disagree, the run measured something other than what the record claims, and
-- the harness now says so at the start rather than after the fact.
--
-- `app_version` is the web app, read from its package.json: the harness does
-- not talk to the web app, so there is no running process to ask.
--
-- Both versions are real numbers as of 2026-09-22 and not before. They sat at
-- their scaffold defaults ("1.0.0" from npm init, "0.0.1" from the template)
-- for 377 commits, so a NULL here means "this run predates versioning" and a
-- value means the patch number was bumped by .githooks/pre-commit for the app
-- the commit touched. Older runs are left NULL rather than backfilled with a
-- number that was never true.

alter table "public"."study_runs"
  add column if not exists "api_version" text,
  add column if not exists "api_commit" text,
  add column if not exists "app_version" text;

comment on column "public"."study_runs"."api_version" is
  'Semver of the API that served this run, read from its /health endpoint at run start (D63). NULL for runs before 2026-09-22, when both apps still carried scaffold defaults.';

comment on column "public"."study_runs"."api_commit" is
  'Commit the serving API process was built from, read from /health. Disagreeing with git_sha means the run did not measure the working tree.';

comment on column "public"."study_runs"."app_version" is
  'Semver of apps/web, read from package.json. The harness does not call the web app, so this is the repository''s value rather than a running process''s.';
