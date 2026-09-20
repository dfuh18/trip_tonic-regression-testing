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

