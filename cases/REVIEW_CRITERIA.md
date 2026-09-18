# Reviewing a test case

A case is adopted into the suite when the author has read it and recorded that
in `reviewed.json`. This is what the reading is for. §3.1 calls the seeds
LLM-generated and human-reviewed, so the review is the step that makes them the
author's rather than the model's, and a case that passes review badly is a case
that will measure the wrong thing eight times per run.

Twelve criteria, grouped. A case fails review on any one of them.

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
5. **Nothing asserted is guaranteed elsewhere.** No zero for a tool the slash
   command already forbids (`agent.tool-policy.ts` has its own tests), and no
   assertion that restates a database constraint.
6. **Nothing load-bearing is missing.** If the request implies a change to the
   trip, or implies none, `mutation_counts` says so. If it implies a specific
   stop in a specific window, `slot_moved` says so.
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

## Reporting a review

Per case: adopt, adopt with a named change, or reject with the reason. Cite the
criterion number. Where a case is fine, say so briefly rather than padding;
where it is not, say what specifically to change.
