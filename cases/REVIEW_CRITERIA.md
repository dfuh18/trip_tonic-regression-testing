# Reviewing a test case

A case is adopted into the suite when the author has read it and recorded that
in `reviewed.json`. This is what the reading is for. §3.1 calls the seeds
LLM-generated and human-reviewed, so the review is the step that makes them the
author's rather than the model's, and a case that passes review badly is a case
that will measure the wrong thing eight times per run.

Thirteen criteria, grouped. A case fails review on any one of them.

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
   in a specific window, `slot_moved` says so — as a window and a length, never
   a clock reading (D31). Check the tolerance against the member's own words: if
   they said "around 4" and the case demands 16:00 exactly, it will fail an
   agent that understood them. Check it against the fixture too: if the target
   day already holds something near that time, the case must widen the window
   and assert `clear_of_other_slots`, because moving off the named time is then
   the correct behaviour.
7. **Consistent with its siblings.** Cases of the same function carry the same
   bounds unless `notes` say why they differ. An unexplained difference between
   two cases of one function is an accident in a pass criterion.
8. **Ordering lives in `expected_tool_sequence`.** A grounded plan writes
   `[search_places, propose_plan]`; the order is not restated anywhere else,
   and no check duplicates it.

## What it scores

9. **The judge can apply every criterion from the request and the reply
   alone.** P3 keeps the judge blind to what the member did afterwards, so a
   criterion needing the trace, the database or the user's reaction is not
   scorable and belongs in `checks` instead.
10. **The criteria discriminate.** Each one can separate a good reply from a
    mediocre one. A criterion every plausible reply satisfies costs a point of
    the ten-point scale and buys nothing.
11. **Factual cases carry a sufficient reference.** For `factual_qa`, the
    stored reference actually contains what the criteria ask the reply to get
    right (D23). A criterion about a fact the reference does not cover cannot
    be scored honestly.

## As part of the suite

12. **The pair earns its place.** Two seeds per function (D21), and the second
    differs from the first in something that matters — a different region, a
    different resolution the member leaves implicit, a different failure mode —
    rather than being the same case with new nouns.

13. **The notes stand alone.** `notes` explains this case without leaning on
    another one: no "the same as the seafood case", no "the second advisory
    seed", no "same reason as above". A case is read on its own — in a diff, in
    a failure report, in the notebook a year later — and a note pointing
    sideways is a reason the reader has to go and find. Give the reason here,
    even where it repeats one given elsewhere. The notes should also still be
    true: an explanation of why something is asserted has to survive the rule
    that made it necessary changing.

## Four questions about the suite

The thirteen criteria are asked of one case at a time, and a suite can pass all
of them case by case while still being wrong as a whole. These four are asked
once, after the cases have been read.

**A. Would the pairs catch a regression in each of the four functions?** For
venue lookup, scheduling, factual question answering and advisory in turn: if
the agent got worse at that function tomorrow, would one of its two cases
notice? Name what a whole function's pair would miss. Criterion 12 asks whether
the second case differs from the first; this asks whether the two together are
enough, which is a different question and the one §3.1 means by a minimum
functionality baseline.

**B. Which scoring criteria would a mediocre reply still pass?** Criterion 10
asks this of each criterion in isolation, where it is easy to answer yes. Asked
across the suite it exposes the pattern: rubrics drift towards restating the
request, and a rubric every plausible reply satisfies makes the ten-point scale
shorter than it looks and the baseline in §3.1 easier to match than intended.

**C. Is any scoring criterion unscorable by a judge that sees only the request
and the reply?** The same sweep for criterion 9. P3 keeps the judge blind to
what the member did afterwards, and a criterion needing the trace, the database
or the user's reaction cannot be scored honestly — it has to move into `checks`
or be dropped.

**D. Is any declared constraint wrong — would it fail a correct agent, or pass
an incorrect one?** This matters more than the other three together. A case
that fails a correct agent puts a false regression in the record and costs the
suite its credibility the first time someone chases one; a case that passes an
incorrect agent is worse, because it is silent. Criteria 4 to 8 ask whether a
constraint follows from the request and is complete; this asks whether it is
*true*, which no amount of internal consistency guarantees.

## Reporting a review

Per case: adopt, adopt with a named change, or reject with the reason. Cite the
criterion number. Where a case is fine, say so briefly rather than padding;
where it is not, say what specifically to change.

Then answer A to D. Finally, state what was not checked and could not be
verified — a review that names its own limits is evidence, and one that implies
it checked everything is not.
