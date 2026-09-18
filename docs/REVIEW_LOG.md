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

