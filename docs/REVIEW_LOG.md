# Review log

What was reviewed, and what was accepted.

`DECISIONS.md` gives the escalation record for free — it shows what was referred
upward. What it cannot show is **what was checked and found sound**, which is
the specific answer to the transparency caveat in §3.4: work produced by an
agent was verified, and here is the record of the verification.

This cannot be reconstructed afterwards. A review that happened but was not
recorded is, for the purposes of the thesis, a review that did not happen.

One entry per `[FABLE]` review pass. Written by the reviewing session, which is
always Fable tier.

## Format

```markdown
### R02 — 2026-10-04
Reviewed: T08, T09, T10 ([STANDARD], completed since 2026-09-28)
Checked against: task specs in IMPLEMENTATION_PLAN.md; hard invariants 1, 3, 5
Findings:
  - T09 wrote the repetition loop without asserting state reset (invariant 1).
    Fixed in this pass; task reopened and re-verified.
  - T08, T10 conform to spec. No divergence.
Accepted: T08, T10 as delivered; T09 after the fix above.
Not covered: the Supabase round trip in T10 was read, not executed.
```

`Not covered` matters as much as `Findings`. A review that states its own limits
is evidence; one that implies it checked everything is not.

---

<!-- TEMPLATE-END — entries below, newest first. -->

### R04 — 2026-09-18
Reviewed: the Phase A `[FABLE]` work landed since R03 — A01, A02, A04, A05,
A06, A07, A09, A12, A13 (commits 009ebd5 … 01ae095) — plus a re-read of the
`[STANDARD]` deliverables already accepted in R01–R03. **Caveat stated up
front:** the reviewing session is the session that wrote this work. It is a
second look, not an independent one; `/thesis-review` from a fresh session
after Phase B is where independence is recovered.
Checked against: each task's spec and Done-when in IMPLEMENTATION_PLAN.md;
the six hard invariants; the additive-changes guardrail over the whole
`apps/` diff since 48cedff; the stop-and-ask list for choices made in code
without a `D` entry; `python tools/check_notebooks.py`; a scan of the
committed diff for keys or tokens; the live database for leftover rows from
the verification scripts.
Findings:
  - **Cascade risk in the mutation trigger (A04), fixed.** The trigger fires
    inside a trip deletion and an account erasure, when the rows its foreign
    keys point at may already be gone; the insert would then have aborted the
    member's own delete. Found by reading, not by an observed failure. A
    guard keeps each reference only while its target exists
    (20260918123000, pushed with the author's go); a participant's own
    trip-delete (204, rows kept, `trip_id` nulled) and an account erasure
    (sessions cascade, D14) were then exercised live.
  - **Gate cost (A07), fixed.** `fetchStudyGate` re-fetched the user on every
    protected navigation for every account. The loader now consults the
    enrolment flag it already holds and calls the server function for
    enrolled accounts only. Behaviour unchanged; one auth round trip fewer.
  - Invariant 2 holds: `model_version` and `model_released_on` are written on
    every suggestion row and served by `/api/study/versions`; observed live.
  - Invariant 3 holds: all 56 event-model fields map to a column (scripted
    check), and A13's walk found every app-set column populated.
  - Invariant 4: `check_notebooks.py` clean; no exported rows in any commit;
    the verification scripts print ids to the terminal only and delete what
    they create (confirmed: zero leftover trips, profiles or study rows).
  - Invariant 5: no key in the diff; the one hit is a test's monkeypatched
    placeholder.
  - Rule 4: the full `apps/` diff contains four request-path changes, all
    documented — the `/api/study` registration, the optional header on the
    client factory, `X-Device-Type` on web requests, and the enrolled-only
    loader gate. The agent's handling of a turn is untouched; a
    participant's turn differs only in the plugin that records it and the
    header its tool client carries.
  - Quiet decisions: none found. Every threshold in code (three
    interactions, 24 h, 15 s poll) traces to a ruling or is a UI cadence.
    Two readings the session made itself are recorded on the tasks: the
    `slot:<day>:<index>` target format and the header grammar.
  - A participant can send a forged `x-study-origin` on a manual write and
    mislabel their own mutation rows. Bounded to their own study data;
    noted, not fixed.
Accepted: A01, A02, A05, A06, A09, A12, A13 as delivered; A04 and A07 after
the fixes above.
Not covered: invariants 1 and 6 are Phase B concerns and have no code yet.
No browser was available, so every click path — join, consent buttons, the
form, the thumbs, the post-task dialog — is verified only through the calls
it makes. The hourly `ignored` job's existence in `cron.job` was not
inspected (no SQL access from the harness). The Docker image was not rebuilt
for D25. The cascade guard was not shown to be necessary, only sufficient.


### R03 — 2026-09-18
Reviewed: A08 ([STANDARD], dispatched and reviewed inside the second
`/thesis-resume` session)
Checked against: the A08 spec as amended for the A07 stub; D18 (codes and
labels compared item by item); the 250-line limit (198); `pnpm typecheck`,
`pnpm lint` and prettier run by the reviewing session with the file present.
Findings:
  - Conforms. Codes are the stored values and the labels are separate
    constants, with a comment saying why — a label edit later cannot re-code
    collected answers. Client-side validation mirrors the API schema (18..120,
    integer, every item required). Submit calls `submitDemographics`, then
    `router.invalidate()` so the `_protected` gate re-reads the row, then
    navigates to `/home` with `replace`. Native radio groups, since
    `packages/ui` has no radio primitive; 44 px rows under `coarse:`.
  - Nothing beyond the spec was added.
Accepted: A08 as delivered.
Not covered: no browser was available to any session, so the form was not
submitted through the UI; the API path it calls was verified in A12.


### R02 — 2026-09-18
Reviewed: B12 ([STANDARD], dispatched and reviewed inside the second
`/thesis-resume` session)
Checked against: the B12 spec; D24; the "pure, no I/O, no `src.config`"
constraint; the subtree test suite run by the reviewing session (41 passed).
Findings:
  - Two readings of D24 the subagent had to make and flagged rather than
    hid. (1) `has_location`: no tool takes a top-level `address`, so argument
    keys are collected recursively and an `address` inside a `propose_plan`
    day (which also carries `day_date`) is not a location, while a lookup
    carrying one is. (2) The three term booleans run over argument values
    joined by newlines so a match cannot span two values. Both are the
    reading the ruling intended; accepted as the definition of
    `SIGNATURE_RULE_VERSION = '1'`. C05 freezes it.
  - `_bucket(0)` returns `'1'`; unreachable from the callers and D24 defines
    no zero bucket. Left as is.
Accepted: B12 as delivered.
Not covered: the signature has not yet been run over a real
`tool_call_trace` from `study_suggestions`; C02 is where that happens.


### R01 — 2026-09-18
Reviewed: A03, A10, A11, B13 ([STANDARD], dispatched in one batch by the
`/thesis-resume` session and reviewed inside it; B14 reviewed in the same
session once it returned — see the addendum below)
Checked against: each task's spec in IMPLEMENTATION_PLAN.md; D09 (A03); the
additive-changes guardrail (root CLAUDE.md rule 4) for every file under
`apps/`; hard invariants 2 (A10) and 3 (A10, A11); the repo gates
(`pnpm typecheck`, `pnpm lint`, `pnpm --filter api test`,
`pnpm --filter web test`, both DB-free security-audit suites) run by the
reviewing session after all four landed.
Findings:
  - A03 conforms to D09 exactly. One test beyond the spec (the three families
    plus the read tools partition `ALL_TOOL_NAMES`) was kept: it forces the
    rule-version question when a tool is added rather than letting a new tool
    be silently labelled `advisory`. Tool names are written out rather than
    imported, deliberately, so a rename in `agent.tool-policy.ts` cannot
    reclassify collected rows without a visible change.
  - A10 conforms. The subagent found the spec's premise false — the runtime
    image copies only `dist`, so the source hashes would fail in the container
    — and raised Q20 instead of guessing. Resolved as D25 (agent: one `COPY`
    line in the Dockerfile). The endpoint was exercised in-process with
    `app.inject()`; the curl against a running dev server was not.
  - A11 conforms. Header added before the caller's own headers so a caller
    keeps precedence; `window.navigator` read instead of the bare global so
    SSR and tests share one guard. The API-log observation was not executed
    (no dev server was running).
  - B13: two errors in the spec, both the reviewing session's own. The root
    `.gitattributes` does not carry an ipynb filter (the operative one is
    `notebooks/study/.gitattributes`), and the `run`/`working-directory` pair
    resolved to a path that does not exist. The subagent flagged both, kept
    `working-directory` and made the command relative, and added a redundant
    subtree-root attributes file because the spec's literal condition held.
    Spec corrected in the plan; the redundant file removed in this pass. The
    job itself is correct and was verified locally with a dirty temporary
    notebook (exit 1) and the clean directory (exit 0).
  - Rule 4: the only changes to existing request paths are one header on every
    web request (A11) and one route registration (A10). No existing response
    shape changed; the agent's handling of a request is untouched.
Accepted: A03, A10, A11 as delivered; B13 after the file removal above.
Not covered: no dev server was started by any of the five sessions, so the
two live observations (A10 curl, A11 header in the API log) remain unexecuted
and are noted on the tasks' status lines. The Docker image was not rebuilt to
confirm D25 resolves the hashing in the container.

Addendum, B14 (returned after the entry above was written): conforms. The
spec said `settings` raises "at import"; the subagent bound it lazily through
a module `__getattr__` so that importing `load_settings` or `REQUIRED_VARS`
does not itself demand a filled `.env` — the behaviour at the specified
access path is unchanged, and the test file could not have imported the
module otherwise. Verified by the reviewing session: 18 tests pass in the
subtree venv; `print(settings)`, an f-string and a containing list all render
`Settings(<redacted>)`; `.venv` is already ignored by the root `.gitignore`.
One finding against the reviewing session, not the subagent: its own
`git add -A` for the Phase A commit swept B14's `conftest.py` into `009ebd5`
while the task was still running. Content identical, nothing lost; the lesson
is to stage by path while a subagent is live.
Accepted: B14 as delivered.

