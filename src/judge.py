"""The judge (B09, §3.4): scores a textual reply against a case's criteria.

Point-wise on a ten-point scale to establish the baseline; pair-wise
"at least as good" against the adopted baseline reply afterwards (§3.1). The
prompts are files under ``src/prompts/`` with a version header — invariant 6:
an explicit, inspectable, versionable judge, not a managed evaluation service.

D23: the pair-wise comparison is asked in both orderings and passes only when
both agree, which is the position-bias control; the reference material for a
weather question is the forecast the agent actually retrieved, for a Wikipedia
question the stored section. P3: the judge sees the request and the reply and
nothing about what the member did afterwards. D20 (stated, not hidden): the
judge is the agent's own model family.

Every call also carries a summary of the fixture trip, prepended to the
reference material. Criteria like "fits this trip" or "refers to the palace
already on that day" are otherwise unscorable: a judge that sees only the
request and the reply has no way to know what the trip holds, and would be
scoring them on plausibility. It is prepended here rather than passed by the
caller so that no call can forget it. P3 is untouched - the summary is the
before-state every repetition starts from, not what the member did next.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.cases import Case
from src.llm import Llm, LlmReply, load_prompt, judge_llm

POINTWISE_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer"}, "rationale": {"type": "string"}},
    "required": ["score", "rationale"],
}
PAIRWISE_SCHEMA = {
    "type": "object",
    "properties": {"better": {"type": "string", "enum": ["A", "B", "tie"]}, "rationale": {"type": "string"}},
    "required": ["better", "rationale"],
}


@dataclass(frozen=True)
class Usage:
    model: str
    prompt_version: str
    calls: int
    tokens_input: int
    tokens_output: int
    retries: int


@dataclass(frozen=True)
class PointwiseResult:
    score: int
    rationale: str
    usage: Usage


@dataclass(frozen=True)
class Ordering:
    """One of the two calls, and what it said about the candidate."""

    candidate_shown_as: str  # "B" in the first call, "A" in the swapped one
    better: str  # "A" | "B" | "tie", as the model answered
    candidate_at_least_as_good: bool
    rationale: str


@dataclass(frozen=True)
class PairwiseResult:
    at_least_as_good: bool
    orderings: tuple[Ordering, Ordering]
    usage: Usage


def _criteria(case: Case) -> str:
    return "\n".join(f"- {line.strip()}" for line in case.scoring_criteria)


def _fixture_summary() -> str:
    # Imported here: the judge's scoring logic is unit-tested without a
    # fixture file, and a module-level import would make it a hard dependency.
    from src.fixture import load_fixture, summary

    return summary(load_fixture())


def _references(references: list[str]) -> str:
    blocks = [f"--- the trip this was asked about ---\n{_fixture_summary()}"]
    blocks += [f"--- reference {i + 1} ---\n{text.strip()}" for i, text in enumerate(references)]
    return "\n\n".join(blocks)


def _usage(model: str, version: str, replies: list[LlmReply]) -> Usage:
    return Usage(
        model=model,
        prompt_version=version,
        calls=len(replies),
        tokens_input=sum(r.tokens_input for r in replies),
        tokens_output=sum(r.tokens_output for r in replies),
        retries=sum(r.retries for r in replies),
    )


def score_pointwise(
    case: Case, user_request: str, reply: str, references: Optional[list[str]] = None, llm: Optional[Llm] = None
) -> PointwiseResult:
    llm = llm or judge_llm()
    prompt = load_prompt("judge_pointwise_v1")
    rendered = prompt.render(
        user_request=user_request.strip(),
        reply=reply.strip() or "(empty reply)",
        criteria=_criteria(case),
        references=_references(references or []),
    )
    out = llm.generate(rendered, "Score the reply.", json_schema=POINTWISE_SCHEMA, temperature=0.0)
    parsed = out.parsed or {}
    score = int(parsed.get("score", 0))
    if not 1 <= score <= 10:
        raise RuntimeError(f"judge returned a score outside 1..10: {parsed}")
    return PointwiseResult(score=score, rationale=str(parsed.get("rationale", "")), usage=_usage(out.model, prompt.version, [out]))


def compare_pairwise(
    case: Case,
    user_request: str,
    baseline_reply: str,
    candidate_reply: str,
    references: Optional[list[str]] = None,
    llm: Optional[Llm] = None,
) -> PairwiseResult:
    """Is the candidate at least as good as the baseline?

    Asked twice with the replies swapped (D23's position-bias control). In the
    first call the candidate is B, so it holds when the model answers B or
    tie; in the second it is A, so it holds when the model answers A or tie.
    The candidate passes only when both calls say it holds.
    """
    llm = llm or judge_llm()
    prompt = load_prompt("judge_pairwise_v1")
    refs = _references(references or [])
    outs: list[LlmReply] = []
    orderings: list[Ordering] = []
    for candidate_as in ("B", "A"):
        a, b = (baseline_reply, candidate_reply) if candidate_as == "B" else (candidate_reply, baseline_reply)
        rendered = prompt.render(
            user_request=user_request.strip(),
            reply_a=a.strip() or "(empty reply)",
            reply_b=b.strip() or "(empty reply)",
            criteria=_criteria(case),
            references=refs,
        )
        out = llm.generate(rendered, "Compare the replies.", json_schema=PAIRWISE_SCHEMA, temperature=0.0)
        outs.append(out)
        parsed = out.parsed or {}
        better = str(parsed.get("better", "")).strip()
        if better not in ("A", "B", "tie"):
            raise RuntimeError(f"judge returned no verdict: {out.text[:120]}")
        holds = better == "tie" or better == candidate_as
        orderings.append(Ordering(candidate_shown_as=candidate_as, better=better, candidate_at_least_as_good=holds, rationale=str(parsed.get("rationale", ""))))
    return PairwiseResult(
        at_least_as_good=all(o.candidate_at_least_as_good for o in orderings),
        orderings=(orderings[0], orderings[1]),
        usage=_usage(outs[0].model, prompt.version, outs),
    )
