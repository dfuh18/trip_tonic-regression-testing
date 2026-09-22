"""Point-wise scoring of a run's executions (B09's judge, applied).

The judge scores the **first** agent reply of an execution against the case's
rubric (D34): the criteria were written for the answer to the opening turn,
and since the personas decline an offer to schedule, a typical execution's
last reply is a sign-off. The checks go the other way — they describe the
whole execution — and that asymmetry is deliberate: the judge scores an
answer, the checks score an outcome.

P3 keeps the judge blind. It sees the request, the reply, the rubric and any
stored reference, and nothing about what the member did next, what tools ran
or what the database recorded. A criterion that needs the trace cannot be
scored honestly and belongs in `checks`.

The reply text is read from `chat_messages`, which is the only place it
exists — `study_suggestions` keeps a `reply_message_id` and not the words.
That is why D38 stopped the reset deleting them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from src.cases import Case, load_cases
from src.judge import PointwiseResult, score_pointwise
from src.llm import judge_llm


@dataclass
class Scored:
    case_id: str
    repetition: int
    score: Optional[int]
    rationale: str
    reply_chars: int
    error: Optional[str] = None


@dataclass
class ScoreRun:
    run_id: str
    results: list[Scored] = field(default_factory=list)
    #: Attempts the provider refused, superseded by a later one (D53). Not
    #: scored and not counted against the agent — they are the platform
    #: failure rate, which is a different measurement kept in the same table.
    superseded: int = 0

    @property
    def scored(self) -> list[Scored]:
        return [r for r in self.results if r.score is not None]

    @property
    def mean(self) -> Optional[float]:
        got = [r.score for r in self.scored]
        return round(sum(got) / len(got), 2) if got else None


def first_reply(execution_row: dict) -> tuple[str, str]:
    """(user request, reply text) for the execution's first turn.

    Returns empty strings where the turn produced nothing — a failed execution
    has no reply, and scoring one would be scoring the provider rather than
    the agent.
    """
    from src import db

    ids = execution_row.get("suggestion_ids") or []
    if not ids:
        return "", ""
    a = db.admin()
    turns = (
        a.table("study_suggestions")
        .select("turn_index, user_turn, reply_message_id")
        .in_("id", ids)
        .order("turn_index")
        .execute()
        .data
    )
    if not turns:
        return "", ""
    first = turns[0]
    reply = ""
    if first.get("reply_message_id"):
        rows = (
            a.table("chat_messages")
            .select("content")
            .eq("id", first["reply_message_id"])
            .execute()
            .data
        )
        if rows:
            reply = rows[0].get("content") or ""
    return first.get("user_turn") or "", reply


def score_execution(case: Case, execution_row: dict, llm=None) -> Scored:
    request, reply = first_reply(execution_row)
    base = dict(case_id=execution_row["case_id"], repetition=execution_row["repetition"])
    if not reply.strip():
        return Scored(**base, score=None, rationale="", reply_chars=0,
                      error="no reply to score (the execution produced none)")
    references = [r.text() for r in case.references]
    try:
        result: PointwiseResult = score_pointwise(case, request, reply, references, llm=llm)
    except Exception as exc:  # a judge failure is not a low score
        return Scored(**base, score=None, rationale="", reply_chars=len(reply),
                      error=f"judge: {type(exc).__name__}: {exc}")
    return Scored(**base, score=result.score, rationale=result.rationale, reply_chars=len(reply))


def latest_attempts(rows: list[dict]) -> tuple[list[dict], int]:
    """D53's reading rule. Delegates to the canonical implementation in
    `src.execution`, which four readers now share — keeping a second copy here
    is how they came to disagree in the first place."""
    from src.execution import latest_attempts as canonical

    return canonical(rows)


def score_run(run_id: str, log: Callable[[str], None] = print) -> ScoreRun:
    """Score every execution of a run once, in case order."""
    from src import db

    cases = {c.case_id: c for c in load_cases()}
    rows = (
        db.admin()
        .table("study_case_executions")
        .select("*")
        .eq("run_id", run_id)
        .order("case_id")
        .execute()
        .data
    )
    rows, superseded = latest_attempts(rows)
    rows.sort(key=lambda r: (r["case_id"], r["repetition"]))
    llm = judge_llm()
    out = ScoreRun(run_id=run_id, superseded=superseded)
    for row in rows:
        case = cases.get(row["case_id"])
        if case is None:
            continue
        scored = score_execution(case, row, llm=llm)
        out.results.append(scored)
        mark = f"{scored.score}/10" if scored.score is not None else "—"
        log(f"  {mark:>5s}  {scored.case_id}"
            + (f"   [{scored.error}]" if scored.error else ""))
    return out


def report(run: ScoreRun) -> str:
    lines = [f"scored {len(run.scored)}/{len(run.results)} executions, mean {run.mean}"]
    if run.superseded:
        lines.append(
            f"({run.superseded} attempt(s) the provider refused, superseded by a re-run and not "
            f"scored — D53)"
        )
    unscored = [r for r in run.results if r.score is None]
    if unscored:
        lines.append("")
        lines.append("not scored:")
        for r in unscored:
            lines.append(f"  {r.case_id}: {r.error}")
    low = sorted((r for r in run.scored), key=lambda r: r.score)[:5]
    if low:
        lines.append("")
        lines.append("lowest scores:")
        for r in low:
            lines.append(f"  {r.score}/10  {r.case_id}")
            lines.append(f"         {r.rationale[:200]}")
    return "\n".join(lines)
