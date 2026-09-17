# Open questions

Things the manuscript or the event model leaves unspecified, which an
implementation cannot proceed past without deciding. **Listed here, not decided
here.** When the author rules on one, it moves to `DECISIONS.md` with a `D` id
and is struck from this list.

An agent adds to this file freely. An agent never removes from it.

## Format

```markdown
### Q05 — Repetitions per test case
Raised: 2026-09-20 by agent · Blocks: T12, T14 · Phase: B
The manuscript requires each case to run n times and a pass rate across runs,
but does not fix n.
Options: n=3 (cheap, weak pass-rate resolution) · n=5 (defensible, ~2x cost) ·
n=10 (strong, cost likely prohibitive at suite scale)
Trade-off: pass-rate granularity against Vertex spend and wall-clock per run.
Recommendation: n=5.
Status: open
```

`Blocks` is what makes this list actionable — a question blocking nothing can
wait; one blocking a Phase A task cannot.

---

<!-- TEMPLATE-END — questions below. -->

## Open

### Q02 — §4.3 is scaffolding, not yet an analysis specification
Raised: 2026-09-17 by agent · Updated: 2026-09-17 · Blocks: Phase C · Phase: C

§4.3 is deliberately unwritten at this point — the author confirms it is
scaffolding with no real content yet, and the stale note it carried has been
removed. Phase C builds `study/06_analysis` from it, and the gate before the
participant round requires that notebook to produce the coverage and
failure-rate outputs described there.

This does not block the plan being produced. It blocks Phase C tasks being
specified tightly enough to delegate.

**Recommendation:** produce the plan now, and tag every Phase C task `[FABLE]`
until §4.3 is written. Revisit the tags then; several will likely become
`[STANDARD]` once the analysis steps are concrete.

Status: open — no action needed before `/thesis-plan`.

### Q03 — Remaining unresolved fields in the event model
Raised: 2026-09-17 by agent · Updated: 2026-09-17 · Blocks: Phase A (one item)
· Phase: A, B

Three `TODO(author)` markers remain in `docs/event-model.md` after the author's
review. One blocks Phase A:

- **When is `ignored` written?** The name is settled (D05), the trigger is not.
  `accepted` and `rejected` have observable events; `ignored` is the absence of
  one, so it needs a rule — session end, a fixed interval, or some definition of
  the conversation moving on. Until that rule exists the application cannot
  write the value, and §4.3's label distribution rests on it.

Two do not block Phase A:

- **Thumbs control scope.** §4.2.2 puts it on every agent message; Table 11 logs
  it at suggestion level. A message is not always a suggestion. This changes the
  UI, so it wants deciding before the Phase A instrumentation task is written,
  even though the schema can accommodate either.
- **Which trip mutations are in scope** for origin tracking. This repo mutates
  `trip_blocks`, `itinerary_slots`, `branches`, `trip_todos` and more. Logging
  all of them is cheap; deciding afterwards which ones counted is not possible.

A fourth, Phase B only: **how `declared_constraints` are represented**
(declarative schema, predicates, or hybrid). Worth settling in `DECISIONS.md`
before code exists rather than after.

Status: open — see the file for the detail.

---

## Resolved

<!-- Moved to DECISIONS.md. Keep the id and a one-line pointer. -->

- **Q01** — the agent model. Resolved by **D04**: the premise was wrong.
  `gemini-3.5-flash` is a pinned release, not a moving alias, so invariant 2 was
  already satisfied; the release date is now recorded alongside the id, and the
  model is not to be upgraded while the study runs.
- **Survey storage** — resolved by **D02**: two separate tables.
- **State reset confirmation** — resolved by **D03**: a precondition check, not
  a logged field.
- **`left` vs `Ignored`** — resolved by **D05**: `ignored` throughout.
