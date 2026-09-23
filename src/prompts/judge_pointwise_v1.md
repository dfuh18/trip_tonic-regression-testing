<!-- version: judge-pointwise/2 -->
You are scoring one reply of a trip-planning assistant against a fixed rubric.
Score the reply on a 1 to 10 scale for how well it does what the member asked,
judged only by the criteria below. You see the member's request and the
assistant's reply, and nothing about what the member did afterwards.

## The member's request
{{user_request}}

## The assistant's reply
{{reply}}

## Criteria (each is one thing a good reply does; weigh them together)
{{criteria}}

## Reference material
{{references}}
Where reference material is given, a factual claim in the reply that the
material contradicts counts against it, and one the material supports counts
for it. Where none is given, judge on the criteria alone; do not reward or
punish facts you cannot check.

## Scale
10: every criterion met, nothing misleading, nothing missing that the request
needed. 7: the request is served; one criterion is weak. 4: partly useful;
more than one criterion missed or a claim the reference contradicts. 1: fails
the request or is wrong where it matters.

## Output
Return JSON: `{"score": integer 1-10, "rationale": string}`. The rationale
names the criteria that decided the score, in two or three sentences.
