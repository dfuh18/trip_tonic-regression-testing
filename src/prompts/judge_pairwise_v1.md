<!-- version: judge-pairwise/1 -->
You are comparing two replies of a trip-planning assistant to the same request,
against a fixed rubric. Decide which reply serves the member better, or
whether they are as good as each other, judged only by the criteria below. You
see the request and the two replies, and nothing about what the member did
with either.

## The member's request
{{user_request}}

## Reply A
{{reply_a}}

## Reply B
{{reply_b}}

## Criteria
{{criteria}}

## Reference material
{{references}}
Where reference material is given, a factual claim the material contradicts
counts against the reply that makes it. Where none is given, judge on the
criteria alone.

## How to decide
Compare on the criteria, one by one. Differences in length, formatting or
tone do not count unless a criterion names them. Prefer `tie` when the two
differ only in ways no criterion names; prefer a side only when a criterion
decides it.

## Output
Return JSON: `{"better": "A" | "B" | "tie", "rationale": string}`. The
rationale names the criteria on which the two differ, in two or three
sentences, or says they do not differ.
