-- Which version of the case produced this execution (D74).
--
-- `suite_version` already hashes the whole case set, which answers "did the
-- suite change" and cannot answer "did THIS case change". That distinction
-- started mattering once cases were edited between runs: D48 added a check to
-- both venue seeds, D55 moved the fixture calendar under every dated check,
-- D58 raised a cap, and D72 inverted the drinks assertion. Two executions of
-- one case id, either side of such an edit, are not executions of the same
-- test — and nothing in the record said so.
--
-- Derived from the case file's contents, not declared. A hand-maintained
-- version is a number nobody bumps; the two package.json versions in this
-- repository sat at their scaffold defaults for 377 commits, which is the same
-- lesson from the other side. A content hash cannot drift from what it names.
--
-- The same value binds a review mark to the text that was reviewed
-- (`cases/reviewed.json`), so "the author approved this case" stops being a
-- claim about a filename and becomes a claim about a version.
--
-- Null for executions recorded before 2026-09-23. Not backfilled: the hash of
-- the file as it stands today is not the hash of what those runs executed, and
-- writing it would assert something false.

alter table "public"."study_case_executions"
  add column if not exists "case_version" text;

comment on column "public"."study_case_executions"."case_version" is
  'Short content hash of the case file this execution ran (D74). Per-case resolution that suite_version cannot give: two executions of one case id either side of an edit are not the same test. Null before 2026-09-23; never backfilled.';
