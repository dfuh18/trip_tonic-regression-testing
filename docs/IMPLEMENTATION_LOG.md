# Implementation log

Where the difficulty and the effort actually went. Feeds §3.7 (learnings and
limitations) and the appendix.

**The risk this file exists to avoid is becoming a development diary**, which is
worth nothing in a thesis. One filter keeps it useful:

> Record an entry only if it would change how someone else built this, or if it
> bears on a claim made in Chapter 2. Debugging an async call does not qualify.
> Discovering that constraints cannot be expressed declaratively does.

**Only the Fable tier writes here.** A cheaper session lacks the context to
judge what is noteworthy, and its entries would be noise to filter out later.

**Omit an entry rather than padding one.** If stages 1 to 3.2 build without
substantial friction, the honest §3.7 says so — and that supports the
specifiability argument more strongly than a list of struggles would.

## Format

```markdown
### L03 — Structural checker: constraints resisted declarative form
Phase: B · Related tasks: T07
Effort: roughly three times the estimate
What happened: the expected-state constraints for venue lookup (minimum result
count, radius widening after an insufficient result) could not be expressed as
a static schema, because they depend on the outcome of the preceding call.
Why it matters: §2.6.1 treats structural verification as comparatively cheap.
For sequence-dependent constraints it is not.
Design consequence: D04. Constraints are predicates, not schemas.
Generalises: any agent whose tool policy includes retry or widening behaviour
will hit this.
```

**`Why it matters` and `Generalises` are what make an entry citable.** An entry
without them is a diary line — omit it instead.

`Effort` is recorded relative to the estimate carried in
`IMPLEMENTATION_PLAN.md`. This is why every task carries one: "three times the
estimate" is a finding about the approach and cannot be reconstructed after the
fact. Rough is fine; absent is not.

---

<!-- TEMPLATE-END — entries below, newest first. -->

### L10 — The harness's own dependencies need the same treatment as the system under test
Phase: B · Related tasks: B06, B07, B05
Effort: the fix was twenty minutes; the run it killed was fifteen, and a
baseline run would have been hours

What happened: a 26-case run died after four executions. Not from the agent —
from the **simulator's** own model call, a `504 DEADLINE_EXCEEDED` that
exhausted `src/llm.py`'s three retries and propagated out of `execute_case`,
through the run loop, and ended the process. Every failure mode of the *agent*
was handled: a 429, a timeout, an empty reply, a tool error all end as
`stopped=agent_error` with the execution recorded and the run continuing. The
simulator had no such treatment, because it is harness code and harness code
was implicitly trusted.

Why it matters: the harness and the system under test call the same provider,
and the provider does not care which is which. L04 already recorded that an
unattended run needs a timeout on every external call. This is its other half
— **a timeout is not enough if the failure it produces takes the run with it**
— and the asymmetry is the interesting part: the failure handling was built
where the failures were expected, and the expectation came from thinking of
the agent as the risky component. At 140 executions an upstream hiccup ends an
unattended evening, and it did.

The fix distinguishes the two rather than merging them, which matters for the
record: a simulator failure is a harness failure and D44's ruling that a lost
execution counts against the case does not apply to it. It is written as an
execution that did not happen — no suggestion ids, `error` prefixed
`simulator:` — so the analysis can separate "the agent failed" from "our own
tooling failed", and the run aborts only after three consecutive ones, because
a simulator that is genuinely down should not spend the budget one case at a
time.

It generalises: anything an unattended measurement depends on needs a failure
policy, and the components you did not think of as risky are exactly the ones
that will not have one.

### L09 — A field existing is not the same as a field carrying what a check needs
Phase: B · Related tasks: B08, A02, B03
Effort: B08 came in near its 8h estimate; the two premise failures cost about
an hour between them, because both were found by reading a recorded row before
writing the code rather than by debugging afterwards

What happened: B08's spec said the checker would read a tool's `found: false`
out of the trace, and would write its verdict to `study_verdicts`. Neither was
possible. The trace reduces every tool result to `result_chars` and
`result_error` — deliberately, and with a good reason written down beside it:
"they carry trip content that already lives in the trip's own tables." That
reasoning is sound for `search_places`, whose results reach the reply's refs,
and silently wrong for `read_wikipedia`, whose miss reaches nothing. And
`study_verdicts` is keyed `(suggestion_id, checker_version)` — a turn — while
D27 had settled that a check describes an execution. A third gap surfaced the
same way: the place ids the metamorphic predicates compare exist only in
`chat_messages.metadata.refs[].googlePlaceId`, not in any study table.

Why it matters: this is the **second** instance of the same class after L05,
and the recurrence is the finding rather than either instance. L05's lesson was
"derive the assertion vocabulary from the log schema" — which was done, and was
not enough. A field can be present, correctly named and still not carry what an
oracle needs, because a logging decision that is right for volume (store a
size, not a payload) is invisible to anyone reading a schema. The question that
would have caught all three is narrower than "what does the log contain": it is
**"take each assertion the suite can make, and name the recorded field it will
be evaluated from"** — a table with one row per check key, filled in before the
checker is written. Two of the three gaps here are entries that could not have
been filled in.

It generalises past this study. Any oracle built over an existing telemetry
pipeline inherits that pipeline's reductions, and those reductions were chosen
against a different question. Verify evaluability per assertion, not coverage
per field.

### L08 — The state reset was deleting the evidence, and only running it showed that
Phase: B · Related tasks: B02, B07, B15, B10, B11
Effort: the probe itself was two minutes of wall clock and $0.18; the repair
was about two hours, against a B15 estimate of 2h that did not exist until the
probe was proposed

What happened: invariant 1 says each repetition must start from a clean state,
and B02 implemented it the obvious way — delete the trip's children and
rebuild the fixture. The delete list grew to include `study_suggestions` and
`study_mutations`, because the precondition gate demanded the trip hold no
study rows and the fixture build itself writes mutation rows. So each
repetition deleted the previous repetition's record. A probe run of the eight
seeds at n = 1 showed it immediately: seven of eight executions had no
readable `study_suggestions` row left. Worse, the reply text lives only in
`chat_messages`, which went the same way — so a baseline run would have
deleted its own replies as it produced them, and the pair-wise comparison that
the whole regression stage rests on (D23) would have had nothing on the other
side.

Why it matters, and what generalises: **the cleanup that enforces one
invariant destroyed the data another one depends on**, and the two invariants
are written in different places — state reset in §3.4, complete logging in
§3.3. Nothing in either says "and the reset must not delete the log", because
from inside either one it is obvious. Isolation by *construction* — a new
fixture trip per repetition — satisfies the first invariant more strongly and
cannot violate the second, because it deletes nothing. If you are building
this, provision rather than clean up wherever the cost allows it.

The second half is about verification, and it is the part that would have cost
the study a round. B07's "done when" was one run row and four execution rows
with every field non-null, and it passed honestly: `study_case_executions` is
keyed to the run, so it survives; the rows it *points at* do not. A
done-when that checks the rows a component writes, and not the rows a later
stage will read back from them, will not catch a deletion downstream of
itself. The cheapest fix is the one that found this: run the thing once,
end to end, and read the record back afterwards rather than during.

### L07 — "LLM-generated and human-reviewed" took three adversarial rounds
Phase: B · Related tasks: B04, B03
Effort: several times the 6h estimate, almost all of it in review rather than
in authoring
What happened: the eight seed cases were generated with LLM help and read by
hand, which is what §3.1 describes. That first reading caught wording and
plausibility problems and missed every defect that mattered. Three further
rounds, each by an independent agent working from a written criteria list and
with read access to the application, found in order: constraints tighter than
the member's request, which would have recorded false regressions (D30, D31);
a check with no source, where the drafting case's central assertion pointed at
a logged field carrying counts and no dates, so a plan drafted onto the wrong
day would have passed; and a case permitting a probe it could never forgive,
plus an unpinned question about which reply the judge scores that the personas
had quietly made decisive (D33 as amended, D34). The third round also probed
the live weather API and found a production bug: every dated forecast call had
been failing, on the path the agent's own prompt names (D36).
Why it matters: §3.1 treats "generated with LLM help and reviewed by hand" as
one step, and §2.6.1 treats structural verification as the cheap half. Both
survive, but with a correction worth stating. The cheapness is real *per
assertion* and it is not where the work is. The work is in establishing that an
assertion is true — that it cannot fail a correct agent, that it can fail an
incorrect one, and that something in the log can actually evaluate it — and
none of those is visible from reading the case. Each round needed the
application source, and the round that found the most needed the network.
A single review by the author is not enough for a suite that will run eight
times per case and whose failures will be read as regressions in the system
under test. What made the later rounds productive was writing the criteria down
first (`cases/REVIEW_CRITERIA.md`, fourteen criteria and four suite-level
questions): the first review had no list and produced style notes, and the
three that had one produced defects. The reviews are also the honest reason the
seed set is eight cases and not sixteen.

### L06 — Advisory's minimum-functionality baseline is scored, not checked
Phase: B · Related tasks: B03, B04, B09
Effort: no effort; a limitation found by reviewing, and one §3.7 has to state
What happened: the advisory pair constrains no tools, by ruling (D29 — a
message with no slash command keeps the agent's whole toolset, so which sources
inform advice is the agent's judgement), and asserts only that nothing is
written. Everything else about an advisory reply is the judge's. A regression in
which the agent stops consulting anything and advises from recall is therefore
undetectable by either case: the structural checks pass unchanged and only the
score moves, which P4 already predicts is the noisiest signal in the suite.
Why it matters: §3.1 describes a minimum-functionality baseline per function,
and for three of the four functions that baseline is structural and cheap to
re-run. For advisory it is a scored baseline, which is a materially weaker
claim — it needs the judge, it inherits the judge's variance, and a small
regression will not clear it. The honest framing for §3.7 is that conversational
regression testing covers the functions that leave a trace, and that the
function which leaves none is covered by a different and weaker instrument. It
is a consequence of D29 rather than a fault in it: constraining an advisory
case's tools would have tested the author's idea of how advice should be
grounded rather than whether the advice was good.

### L05 — The structural vocabulary was specified without reading the log schema
Phase: B · Related tasks: B03, B08, A02
Effort: not the issue; the cost is what was not asserted for two weeks
What happened: `declared_constraints.checks` was designed from the manuscript's
account of what a constraint is, and the Phase A instrumentation was designed
from the event model. Nothing joined them. The application was already
recording each draft's slot types, the number of places a reply referenced, the
counts of move/unschedule/schedule edits, the post-turn size of the trip and
the columns each write touched — and the case vocabulary could express none of
it. Two of those became check keys only because an unrelated review sent me
into `buildStateShape` for a different reason.
Why it matters: §2.6.1 argues that structural verification is the cheap half of
regression testing for agents, and the argument is right — each of these keys
took minutes to define once found. The finding is about *where the cost
actually sits*: not in evaluating a structural constraint but in discovering
which ones the system can support. That discovery is a reading of the
instrumentation, it does not fall out of the requirements, and specifying the
two halves from two different documents is enough to lose it. Anyone building
this should derive the assertion vocabulary from the log schema as a step, not
assume the two will meet.
How it closed (D37, 2026-09-20): the reading was done, and it produced four
keys, not one — `edits`, `trip_after`, `mutation_changed_keys` and
`turn_errors`. The last of those is the one that justifies the whole exercise:
an `empty_reply` comes back as HTTP 200, so the simulator answers the blank in
character and a read-only case passes every other check against a turn that
never happened. Two halves of a rule came out of it, and the second is the one
that is easy to miss: derive candidates from the log schema, **and add a key
only when a case needs it**, because a vocabulary larger than the suite is a
vocabulary nobody validates. Five signals the application records
(`reply.chars`, latency, tokens, `llm_calls`, `tool_calls`) stayed out for a
third reason — a bound on any of them is a threshold, and there was no baseline
to set one against.

### L04 — An unattended run needs a timeout on every external call and a heartbeat outside its process
Phase: B · Related tasks: B06, B07
Effort: the runner itself came in under its estimate; the first dry run then
sat for forty minutes on one call before anyone noticed.
What happened: the Gemini SDK's default request timeout is none. A single
persona call hung, the runner waited on it indefinitely, and nothing outside
the process showed anything but silence — the run's own log was piped into
a buffer that flushes at exit. Fixed with a ninety-second per-call timeout
(retried like a 5xx) and a line per execution in `runs/harness.log`.
Why it matters: §3.1 describes runs of a hundred-plus executions over hours,
run once. A run that can stall silently is a run that can lose its window,
and neither the tests nor the specification asked for a timeout because
neither imagined the absence of one.
Design consequence: every external call the harness makes carries a timeout,
and progress is written to disk, not only to stdout.
Generalises: any simulation harness built on an SDK whose defaults assume an
interactive caller.

### L03 — A fixture digest can only contain what the application does not derive
Phase: B · Related tasks: B02, B07
Effort: below estimate for B02; the fault appeared two tasks later.
What happened: the state-reset gate compared a digest of the rebuilt fixture
(blocks, slots, regions) with the fixture file. On the third rebuild the
application's city-aware region assignment created a region the fixture had
not named, the digests differed, and the gate refused a perfectly clean trip.
Regions are now checked for presence only; the digest holds what the fixture
declares and the application copies verbatim.
Why it matters: invariant 1 asks the gate to assert on a clean state, and an
assertion that is stricter than the application's own determinism produces
refusals that look like dirt. The line between "what the fixture put there"
and "what the application derived from it" has to be drawn explicitly, and it
is not visible from the fixture file alone.
Design consequence: `observed_digest` excludes derived state; declared state
is checked by digest, derived state by presence.
Generalises: any end-to-end harness whose fixture is built through the
product's own write paths rather than inserted as rows.


### L02 — Origin carried in a header has to survive every hop, including the API's own database client
Phase: A · Related tasks: A04
Effort: about the estimate (six hours planned, roughly five spent), but the
first live run was wrong in a way no test or reading had shown.
What happened: D13 puts the origin of a write in a request header that a
PostgreSQL trigger reads through PostgREST. The browser sent it, the Fastify
API received it, and the trigger never saw it: the API talks to PostgREST
through its own per-request Supabase client, which copied the JWT and nothing
else. Every member-path write came out `user_manual`. The fix is one line —
forward the header when building that client — and it was found only by
reading the rows a real run produced.
Why it matters: §2.6.1 treats the system-shell layer as the place where
tool boundaries are observable. This is a reminder that the shell has more
than one boundary: an attribution that rides on transport metadata is lost at
any hop that rebuilds the request, and the hop nobody lists is the service's
own client to its database. Unit tests cannot catch it, because the loss is
in configuration, not logic.
Design consequence: `getSupabaseClient` forwards `x-study-origin`; the live
check for every instrumentation task now reads back the rows it should have
produced rather than the status code of the call that produced them.
Generalises: any tracing or attribution scheme that carries context in
headers across a BFF-style API — the same failure OpenTelemetry context
propagation has to solve, and for the same reason.


### L01 — Cold subagents caught two false premises the planning session wrote into its own specs
Phase: A, B · Related tasks: A10, B13 (and B14 for the pattern)
Effort: the five `[STANDARD]` tasks of the first batch ran three to eight
minutes each against estimates of one to three hours; A01 and A02 took about
ninety minutes each against four and six.
What happened: two of the five `[STANDARD]` specs asserted facts about the
environment that were false — that the API image kept `src` on disk (A10) and
that the repository root carried an ipynb filter (B13) — and a third contained
a self-contradictory path. All were written by the Fable planning session
from a code survey it had actually performed; the errors were misreadings of
what it read, not gaps in what it read. In every case the cold subagent
noticed the premise did not hold, said so, and either stopped (A10 raised
Q20) or made the mechanical fix and reported it (B13). None guessed.
Why it matters: §3.4 rests on the claim that a tightly specified task can be
executed by a session with no context without design decisions leaking in.
The first batch supports the claim, but not in the way the plan assumed: the
value of the cold start was not only that the subagent could not make a
decision, it was that it could not share the planner's misreading. A spec
premise is checked twice for free.
Design consequence: D25. And a rule for the reviewer, applied from R01 on:
a `[STANDARD]` spec's statements about the environment (paths, files that
exist, what a build copies) are checked by the reviewing session before
dispatch when cheap, and their failure is expected, not treated as a
subagent fault.
Generalises: any tiered agent workflow where a higher-context session writes
specs for lower-context executors. The executor's ignorance is a check on the
planner's confidence, which is a stronger argument for tiering than cost.

