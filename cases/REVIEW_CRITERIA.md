# Reviewing a test case

A case is adopted into the suite when the author has read it and recorded that
in `reviewed.json`. This is what the reading is for. §3.1 calls the seeds
LLM-generated and human-reviewed, so the review is the step that makes them the
author's rather than the model's, and a case that passes review badly is a case
that will measure the wrong thing eight times per run.

Fourteen criteria, grouped. A case fails review on any one of them.

## The request

1. **A member would type this.** The opening turn uses the words and formats
   people use: "the 7th", "Saturday afternoon", "around 4", "the Sintra day".
   Never an ISO date, coordinates, a tool name or a field name. A turn phrased
   for the agent's convenience measures an easier system than participants use
   and quietly weakens the Chapter 4 comparison.
2. **The persona is playable.** `user_profile` and `goal` give the simulator
   enough to stay in character for up to three turns (D21) and to know when it
   is satisfied, without scripting what it must say.
3. **The goal is reachable in the fixture.** What the member wants exists in
   the starting trip: the stop, the day, the region. A goal the fixture cannot
   satisfy tests error handling under the label of the function.

## What it asserts

4. **Every check follows from the request.** Each key in
   `declared_constraints.checks` is something this member's request actually
   implies. A check nobody could justify from the turn is the harness's opinion,
   not a requirement.
5. **The constraints follow the request, not the label.** What a case asserts
   comes from what this member asked for. An advisory request asking for advice
   implies nothing is written, and says so; it constrains no tools, because a
   message without a slash command keeps the whole toolset deliberately (D29).
   **The tool list is complete, and contains nothing spare.** Every tool the
   agent legitimately needs for this request is named, because anything not
   named is a structural failure (D28, deny by default). Equally, a tool named
   but not needed silently permits behaviour the case should have caught. No
   zeros — a tool is forbidden by being absent — and the three read tools are
   always allowed, so they are never listed.
6. **Nothing load-bearing is missing.** All four mutation counts are stated —
   `trip_blocks.INSERT`, `itinerary_slots.INSERT`, `itinerary_slots.UPDATE`,
   `ai_suggestions.INSERT` — with the deviations the request implies and zeros
   elsewhere. A count that is incidental to the request rather than implied by
   it is left out, and `notes` says why. If the request implies a specific stop
   in a specific window, `slot_moved` says so — and criterion 9 governs how
   tightly.
7. **Consistent with its siblings.** Cases of the same function carry the same
   bounds unless `notes` say why they differ. An unexplained difference between
   two cases of one function is an accident in a pass criterion.
8. **Ordering lives in `expected_tool_sequence`.** A grounded plan writes
   `[search_places, propose_plan]`; the order is not restated anywhere else,
   and no check duplicates it.
9. **Every assertion is as loose as the request allows.** An assertion has to
   hold for *every* correct agent, and for the fixture as it will be rather
   than only as it is. A constraint tighter than the request is the most
   expensive mistake a case can make: it puts a false regression in the record,
   and the first person to chase one stops trusting the suite. Four habits,
   each from a case that had the tight version first:

   - **A time is a window and a length, never a clock reading** (D31). The
     member says "around 4" or "Saturday afternoon", and those are ranges — an
     agent writing 16:15 for the first understood her. `starts_between` takes
     the pair her words license; a case meaning one minute writes it twice, so
     the tolerance is always on the page. A day is the exception and is exact.
   - **Read the assertion against a fuller fixture.** If the target day already
     holds something near the time she named, moving off that time is the
     *correct* behaviour — so the case widens the window to the part of the day
     she actually named and asserts `clear_of_other_slots`. A case pinned to the
     minute silently rots as the starting trip gains stops.
   - **Assert the outcome, not the route to it** (D30). Where the application
     refuses a reasonable first attempt and the agent recovers inside the turn,
     widen the bound and write `tool_errors: corrected` rather than `none`, so
     the recovery passes while an error the agent never fixes still fails
     (D33). Nothing is lost: the analysis reports tool errors and retries, so
     first-try success stays readable without being a pass criterion.
   - **Assert the kind of place, never which one** (D32). A request for lunch
     near a palace implies a restaurant in a region, and the venue is the
     agent's judgement — a case that named one would make the author's taste
     the pass criterion and would break when that restaurant closed. Use
     `places_surfaced` and `places_named`. The exception is about **who named
     the place**: one the member named is hers, so a stop she pointed at goes
     in `slot_moved.block` and one she said the trip already has goes in
     `draft_reuses_blocks`, both exact. Check both directions — a case naming a
     venue the member did not is too tight, and a case that answers "we already
     have the monastery saved" with a type count is too loose.
   - **Read the persona against what the agent is instructed to say.** Both the
     find-mode and free-text instructions require Tonic to close by offering to
     pre-schedule, and the free-text one names accepting that offer as a reason
     to draft in the same turn. The simulator answers in character for up to
     three turns and a turn with no slash command restores the whole toolset,
     so a case asserting `ai_suggestions.INSERT: 0` needs a goal that says what
     the member does when the offer comes. Saying when a member is satisfied is
     not scripting them (criterion 2).
   - **Never encode an incidental fact about the fixture.** A count that holds
     only because of how the starting trip happens to be arranged tests the
     fixture, not the agent — `itinerary_days.INSERT` on a day the fixture left
     empty is the example, and it is left unasserted with `notes` saying so.

   The counter-pressure is real and criterion 10 is where it lives: loosening
   an assertion until nothing fails it asserts nothing. The test is whether a
   *specific wrong behaviour* still trips it. Dropping the length from
   `slot_moved` would have loosened it past that line, because an agent that
   moves the start and leaves an hour-long stop running to midnight would pass.

## What it scores

10. **The judge can apply every criterion from the request and the reply
    alone.** P3 keeps the judge blind to what the member did afterwards, so a
    criterion needing the trace, the database or the user's reaction is not
    scorable and belongs in `checks` instead.
11. **The criteria discriminate.** Each one can separate a good reply from a
    mediocre one. A criterion every plausible reply satisfies costs a point of
    the ten-point scale and buys nothing.
12. **Factual cases carry a sufficient reference.** For `factual_qa`, the
    stored reference actually contains what the criteria ask the reply to get
    right (D23). A criterion about a fact the reference does not cover cannot
    be scored honestly.

## As part of the suite

13. **The pair earns its place.** Two seeds per function (D21), and the second
    differs from the first in something that matters — a different region, a
    different resolution the member leaves implicit, a different failure mode —
    rather than being the same case with new nouns.

14. **The notes stand alone.** `notes` explains this case without leaning on
    another one: no "the same as the seafood case", no "the second advisory
    seed", no "same reason as above". A case is read on its own — in a diff, in
    a failure report, in the notebook a year later — and a note pointing
    sideways is a reason the reader has to go and find. Give the reason here,
    even where it repeats one given elsewhere. The notes should also still be
    true: an explanation of why something is asserted has to survive the rule
    that made it necessary changing.

## Four questions about the suite

The fourteen criteria are asked of one case at a time, and a suite can pass all
of them case by case while still being wrong as a whole. These four are asked
once, after the cases have been read.

**A. Would the pairs catch a regression in each of the four functions?** For
venue lookup, scheduling, factual question answering and advisory in turn: if
the agent got worse at that function tomorrow, would one of its two cases
notice? Name what a whole function's pair would miss. Criterion 13 asks whether
the second case differs from the first; this asks whether the two together are
enough, which is a different question and the one §3.1 means by a minimum
functionality baseline.

**B. Which scoring criteria would a mediocre reply still pass?** Criterion 11
asks this of each criterion in isolation, where it is easy to answer yes. Asked
across the suite it exposes the pattern: rubrics drift towards restating the
request, and a rubric every plausible reply satisfies makes the ten-point scale
shorter than it looks and the baseline in §3.1 easier to match than intended.

**C. Is any scoring criterion unscorable by a judge that sees only the request
and the reply?** The same sweep for criterion 10. P3 keeps the judge blind to
what the member did afterwards, and a criterion needing the trace, the database
or the user's reaction cannot be scored honestly — it has to move into `checks`
or be dropped.

**D. Is any declared constraint wrong — would it fail a correct agent, or pass
an incorrect one?** This matters more than the other three together. A case
that fails a correct agent puts a false regression in the record and costs the
suite its credibility the first time someone chases one; a case that passes an
incorrect agent is worse, because it is silent. Criteria 4 to 8 ask whether a
constraint follows from the request and is complete, and criterion 9 whether it
leaves a correct agent room; this asks whether it is *true*, which no amount of
internal consistency guarantees.

## A follow-up case as well (15 to 21)

A metamorphic follow-up is reviewed against all fourteen criteria above — it is
a case — and then against these, which are about the **relation** rather than
the case. A follow-up can be a perfectly good case and a worthless test.

15. **The perturbation is a change a member would actually make.** Someone
    rewords, changes their mind about the day, adds a constraint, asks for more.
    Nobody types a systematically mutated sentence. A perturbation that reads
    like a mutation tests a string nobody sends.

16. **The expected delta follows from the perturbation, and only from it.**
    Every check the follow-up overrides must be a consequence of the words that
    changed. A delta that also encodes some other opinion — a tighter bound, a
    different tool budget — has smuggled a second test in, and a failure will
    not say which half caused it.

17. **What the perturbation invalidates is dropped, not left to fail.** A
    follow-up asking for a full day must not inherit the seed's morning window.
    An inherited check the new request contradicts is a false regression the
    suite wrote itself, which criterion D calls the worst kind.

18. **Everything the perturbation did NOT touch is still inherited.** This is
    where most of a directional case's detection comes from, and it is easy to
    lose by rebuilding the constraints instead of overriding them.

19. **The relation could actually fail.** Describe, concretely, an agent
    behaviour this follow-up catches that its seed does not. "The agent ignores
    the day and answers for the original one" is such a behaviour; "the agent
    is worse" is not. If no such behaviour can be named, the follow-up costs
    four executions and buys nothing.

20. **An invariance case does not assert something that legitimately varies.**
    The agent is non-deterministic and so is the place search. "Same venues as
    the seed" is a safe claim only where the seed's answer is genuinely stable;
    asserted over a live search it fails on variance and reports it as a
    regression. Where a relation's claim cannot survive re-running the *seed*
    against itself, it is not a claim.

21. **The two follow-ups of one seed catch different regressions.** Criterion
    13 asks this of the two seeds per function; this asks it of the two
    follow-ups per seed. Two perturbations that a single agent fault would
    break together have spent eight executions to learn one thing.

## Two more questions about the expanded suite (E and F)

**E. Does any relation claim a delta the record cannot show?** A follow-up
whose expected change is real but invisible — the same tools, the same
mutations, a different sentence — is scored by the judge alone, and its
structural verdict will read `none` whether or not the agent answered the new
question. That is legitimate, and it has to be *stated*, because a reader
seeing `none` will otherwise believe something was verified. Name every case
in this position.

**F. Is any predicate or check key defined but never exercised?** The suite's
own rule is that a key nobody asserts is a key nobody validates. A comparison
function that no case names, or one every case satisfies trivially — comparing
two empty sets, for instance — is dead weight that reads like coverage.

## The suite as an instrument (22 to 24)

The first twenty-one criteria ask whether each case is a good case. These ask
whether the suite is a good *instrument*, which is a different question and
the one a regression suite lives or dies by. They are checked automatically by
`tests/test_tool_coverage.py` and reported per run by `src/coverage.py`, so a
suite that stops satisfying them fails a commit rather than a study.

22. **Every tool the agent has is named by some case.** A tool no case names
    is a capability the suite asserts nothing about, so a regression in it is
    invisible — the run comes back clean and the tool is gone. When this was
    first measured, six of the agent's twelve tools were named by no case,
    including `schedule_block` and `unschedule_block`: two of the four tools
    that write the itinerary. The three read tools are exempt, and only
    those: the agent calls them when its preloaded context falls short, which
    varies between runs, so a case cannot require one.

23. **Every tool a case names is actually reached by a run.** Declaring is not
    covering. Three cases name `get_climate_normals` and no execution has ever
    called it, because the agent reaches `get_region_climate` first and
    answers — so a static check calls it covered and the tool has never run. A
    tool that is declared and never observed needs either a request only that
    tool can serve, or an honest note that it is uncovered. Silence is the one
    option that is not available.

24. **A range of parameters, not just a range of tools.** `move_slot` called
    only ever with day, start and end together says nothing about a day-only
    move; `get_weather` exercised only on dates beyond the forecast horizon
    says nothing about the path that succeeds. The per-run report lists the
    argument names each tool was actually called with, and a tool whose
    parameters never vary is covered in name only.

## Reporting a review

Per case: adopt, adopt with a named change, or reject with the reason. Cite the
criterion number. Where a case is fine, say so briefly rather than padding;
where it is not, say what specifically to change.

Then answer A to D, and E and F where follow-up cases are in scope. Finally, state what was not checked and could not be
verified — a review that names its own limits is evidence, and one that implies
it checked everything is not.
