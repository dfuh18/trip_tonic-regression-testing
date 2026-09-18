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

