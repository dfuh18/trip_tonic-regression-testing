# Decisions

What was chosen, when, by whom, and why. Feeds §3.3 and §4.4 of the manuscript,
and provides the escalation record for the transparency paragraph in §3.4.

A question the author has not yet ruled on lives in `OPEN_QUESTIONS.md`, not
here. This file records rulings, including rulings that later reversed — a
reversal is appended as a new entry, never an edit to the old one. The record of
what was believed at the time is the point.

Newest entries at the top.

## Format

```markdown
### D04 — Constraint expression format
Date: 2026-09-22 · Decided by: author (escalated by agent)
Options: declarative JSON schema · Python predicates · hybrid
Chosen: Python predicates
Reason: venue-count and radius conditions cannot be expressed declaratively
without inventing a mini-language.
Affects: T07, T11 · Reverses: none
```

`Decided by` is one of: **author**, **author (escalated by agent)**, or
**agent**. An agent may only record `agent` for choices the nested `CLAUDE.md`
lists under "do not ask about". Anything on the stop-and-ask list is the
author's, and recording it otherwise misstates the transparency record.

---

<!-- TEMPLATE-END — entries below, newest first. -->

### D05 — `ignored` replaces `left` as the user action
Date: 2026-09-17 · Decided by: author
Options: keep both names · standardise on `left` · standardise on `ignored`
Chosen: `ignored`, in Table 11 and Table 12 alike; the manuscript was corrected.
Reason: Table 11 said `left` and Table 12 said `Ignored` for the same state,
which would have become two columns and then two label distributions.
Affects: event-model.md (suggestion level), Phase A logging, §4.3 analysis
Reverses: none
Note: the *operational definition* — what event causes `ignored` to be written,
and when it becomes final — is still open. See event-model.md.

### D04 — Model stays on `gemini-3.5-flash`; the release date is recorded too
Date: 2026-09-17 · Decided by: author (escalated by agent as Q01)
Options: pin a dated snapshot of 3.5 Flash · upgrade to the newest Flash
release · keep 3.5 Flash and record its release date
Chosen: keep `gemini-3.5-flash`, and record `DEFAULT_VERTEX_MODEL_RELEASED`
(2026-05-19) alongside it in run metadata.
Reason: Q01 was raised on a false premise. In the Gemini 3.x Flash family the
release *is* the id — 3.5, 3.6, 3.7 and 3.8 are separate models with separate
release dates, and there are no `-001` snapshot suffixes. `gemini-3.5-flash`
does not move on its own, so invariant 2 was already satisfied; what was missing
was the date, which is what Table 11 actually asks for. Separately, 3.5 Flash is
guaranteed until at least 2027-05-19 while 3.6/3.7/3.8 are documented as
short-term availability models — so for a once-only participant round, staying
on 3.5 is the safer choice, not the conservative one.
Affects: apps/api/src/lib/env.ts, apps/api/.env.example, root CLAUDE.md rule 2,
event-model.md (run level `model_released_on`)
Reverses: none · Closes: Q01
Constraint: do not upgrade the model while the study is running.

### D03 — State reset is a precondition, not a logged field
Date: 2026-09-17 · Decided by: author (escalated by agent)
Options: log per repetition · log once per run · check before the run and
refuse to start it
Chosen: a check that runs before a run starts and refuses to start it if the
slate is not clean.
Reason: as a logged field it is near-constant by construction — a run that
proceeded would always carry `true`, so the column evidences nothing. As a gate
it does what invariant 1 asks ("assert on this; do not assume it"): a dirty
state produces no run at all.
Affects: event-model.md (run level), Phase B harness
Reverses: the field as listed in Table 11
Manuscript: updated the same day. The Table 11 row now reads "Confirmation of
state reset between repetitions; Necessary precondition, else no run", so the
implementation and the published schema agree. No follow-up outstanding.

### D02 — Surveys are separate tables
Date: 2026-09-17 · Decided by: author (escalated by agent)
Options: columns on the session row · one table per instrument
Chosen: `survey_demographics` and `survey_post_task`, each keyed to
`session_id`.
Reason: clean separation of self-reported survey data from behavioural
telemetry. It also makes the consent commitments tractable — a deletion or
access request is answerable per table rather than per column.
Affects: event-model.md (session and survey levels), Phase A
Reverses: none

### D01 — The model pin lives in code, repo-wide
Date: 2026-09-17 · Decided by: author
Options: pin in deployment config only · pin in code as the repo-wide default ·
pin for study and simulation runs only
Chosen: in code, as the repo-wide default in `apps/api/src/lib/env.ts`.
Reason: §3.3 claims the simulator exercises the same paths as ordinary use. A
production alias with a study-only pin would contradict that claim in the one
place it matters, and a pin that lives only in deployment config is invisible to
any reader of the repository.
Affects: apps/api/src/lib/env.ts · Reverses: none
