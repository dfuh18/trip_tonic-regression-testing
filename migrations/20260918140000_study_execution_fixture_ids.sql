-- Exact traceability for a case execution (research/regression-testing, D26).
--
-- The fixture trip is deleted and rebuilt before every repetition, so every
-- repetition's stops, days and slots are NEW rows with new ids. A
-- study_mutations row records `row_id`, not a title, and study_suggestions'
-- resulting_state_shape records slot and draft ids — none of which can be
-- resolved back to "the Tram 28 ride" once the next repetition has replaced
-- them.
--
-- This column is that resolution: the ids the rebuild produced, for the
-- repetition the row describes. Without it, the identity of everything a run
-- touched is recoverable only while that repetition is the current state,
-- which is to say not at all by the time the run finishes (P6: every run
-- reproducible and attributable).
--
-- Shape, written by src/runner.py:
--   {"trip": uuid,
--    "blocks":  {"Tram 28 ride through Alfama": uuid, ...},
--    "days":    {"2026-11-06": uuid, ...},
--    "slots":   {"Tram 28 ride through Alfama": uuid, ...},
--    "regions": {"Lisbon": uuid, ...}}
--
-- Titles as keys because that is the one vocabulary the fixture, the trip and
-- the cases share; the values are what makes a title unambiguous even if two
-- stops were ever to share one.

alter table "public"."study_case_executions"
  add column if not exists "fixture_ids" jsonb;

comment on column "public"."study_case_executions"."fixture_ids" is
  'The ids the fixture rebuild produced for this repetition: trip, blocks, days, slots and regions by name. Resolves a study_mutations row_id back to the stop it touched.';
