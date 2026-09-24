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

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from src.cases import Case, load_cases
from src.config import settings
from src.judge import PointwiseResult, score_pointwise
from src.llm import judge_llm


#: How many times a judge call may be retried. The judge is an instrument, not
#: the system under test: a refusal from it costs a measurement and says
#: nothing about the agent, so it is retried where an agent failure never is.
MAX_JUDGE_ATTEMPTS = 3

#: Transient judge failures — the provider refusing or timing out. A malformed
#: rubric or a score outside 1..10 is a real fault and is not retried.
_JUDGE_TRANSIENT = ("429", "503", "504", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED", "UNAVAILABLE")


def _judge_worth_retrying(exc: Exception) -> bool:
    return any(marker in f"{type(exc).__name__}: {exc}" for marker in _JUDGE_TRANSIENT)


def _judge_backoff_s(attempt: int) -> float:
    """Seconds before the next judge attempt: 2, 4, capped."""
    return min(2.0 * attempt, 8.0)


@dataclass
class Scored:
    case_id: str
    repetition: int
    score: Optional[int]
    rationale: str
    reply_chars: int
    error: Optional[str] = None
    #: Agent turns in the execution, and how many after the first called a
    #: tool. The judge scores turn 1 and only turn 1 (D34; D82 for the
    #: multi-step seeds). A later turn that only said "thanks" loses nothing by
    #: that; a later turn that ACTED — drafted, moved — is work no score here
    #: describes, so reports mark exactly those executions.
    turns: int = 1
    later_acting_turns: int = 0

    @property
    def unjudged_work(self) -> bool:
        return self.later_acting_turns > 0

    @property
    def judged(self) -> str:
        return f"turn 1 of {self.turns}; turns 2-{self.turns} not judged"


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


def _turn_counts(execution_row: dict) -> dict:
    """``turns`` and ``later_acting_turns`` for the D34 mark."""
    from src import db

    ids = execution_row.get("suggestion_ids") or []
    if not ids:
        return {"turns": 1, "later_acting_turns": 0}
    rows = (db.admin().table("study_suggestions").select("turn_index, tool_calls")
            .in_("id", ids).order("turn_index").execute().data)
    return {"turns": max(1, len(rows)),
            "later_acting_turns": sum(1 for r in rows[1:] if (r.get("tool_calls") or 0) > 0)}


def score_execution(case: Case, execution_row: dict, llm=None) -> Scored:
    request, reply = first_reply(execution_row)
    base = dict(case_id=execution_row["case_id"], repetition=execution_row["repetition"],
                **_turn_counts(execution_row))
    if not reply.strip():
        return Scored(**base, score=None, rationale="", reply_chars=0,
                      error="no reply to score (the execution produced none)")
    references = [r.text() for r in case.references]
    # The judge gets retried where the agent does not (D70). The agent is the
    # system under test and a failure of it is a result; the judge is an
    # instrument, and a 429 from it is a missing measurement, not a finding.
    # Two runs lost five scores this way — including the two lowest — and an
    # unscored execution is worse than a slow one.
    for attempt in range(1, MAX_JUDGE_ATTEMPTS + 1):
        try:
            result: PointwiseResult = score_pointwise(case, request, reply, references, llm=llm)
            break
        except Exception as exc:
            if attempt == MAX_JUDGE_ATTEMPTS or not _judge_worth_retrying(exc):
                return Scored(**base, score=None, rationale="", reply_chars=len(reply),
                              error=f"judge: {type(exc).__name__}: {exc}")
            time.sleep(_judge_backoff_s(attempt))
    return Scored(**base, score=result.score, rationale=result.rationale, reply_chars=len(reply))


def latest_attempts(rows: list[dict]) -> tuple[list[dict], int]:
    """D53's reading rule. Delegates to the canonical implementation in
    `src.execution`, which four readers now share — keeping a second copy here
    is how they came to disagree in the first place."""
    from src.execution import latest_attempts as canonical

    return canonical(rows)


def persist(run_id: str, row: dict, scored: "Scored", judge_model: str, prompt_version: str) -> None:
    """Write one judge score to `study_scores` (D71).

    Append-only and keyed by (execution, judge model, prompt version), so
    re-scoring under a new judge adds a row rather than overwriting one — a
    disagreement between two judge versions is data. `on_conflict` makes a
    re-score under the SAME judge idempotent, which is what lets a lost judge
    pass be resumed without duplicating what it already wrote.

    Never fatal: a scoring pass that cannot persist should still report its
    numbers rather than lose them, which is the failure this table exists to
    prevent in the first place.
    """
    from src import db

    try:
        db.admin().table("study_scores").upsert({
            "execution_id": row["id"],
            "run_id": run_id,
            "case_id": row["case_id"],
            "repetition": row["repetition"],
            "attempt": row.get("attempt") or 1,
            "judge_model": judge_model,
            "judge_prompt_version": prompt_version,
            "score": scored.score,
            "rationale": scored.rationale or "",
            "reply_chars": scored.reply_chars,
            "error": scored.error,
        }, on_conflict="execution_id,judge_model,judge_prompt_version").execute()
    except Exception as exc:  # pragma: no cover - reporting must survive it
        print(f"    WARNING could not persist score for {row['case_id']}: {exc}")


def scores_for(run_id: str) -> list[dict]:
    """Every persisted score for a run, newest judge version first."""
    from src import db

    return (
        db.admin()
        .table("study_scores")
        .select("*")
        .eq("run_id", run_id)
        .order("case_id")
        .execute()
        .data
    )


def _judge_prompt_version() -> str:
    from src.llm import load_prompt

    return load_prompt("judge_pointwise_v1").version


def score_run(run_id: str, log: Callable[[str], None] = print, persist_scores: bool = True) -> ScoreRun:
    """Score every execution of a run once, in case order.

    Scores are persisted by default (D71). They used to live only in the
    returned object, so a lost notebook kernel cost a whole judge pass and
    nothing could join a score to the structural verdict for the same
    execution without re-judging.
    """
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
        if persist_scores:
            persist(run_id, row, scored, settings.JUDGE_MODEL, _judge_prompt_version())
        mark = f"{scored.score}/10" if scored.score is not None else "—"
        log(f"  {mark:>5s}  {scored.case_id}"
            + (f"   [judged {scored.judged}]" if scored.unjudged_work else "")
            + (f"   [{scored.error}]" if scored.error else ""))
    return out


def report(run: ScoreRun) -> str:
    lines = [f"scored {len(run.scored)}/{len(run.results)} executions, mean {run.mean}"]
    multi = sorted({r.case_id for r in run.results if r.unjudged_work})
    if multi:
        lines.append(
            f"judged turn 1 only (D34): {len(multi)} case(s) acted again on a later turn that the "
            f"judge did NOT score; their scores describe the opening reply alone - {', '.join(multi)}"
        )
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
            lines.append(f"  {r.score}/10  {r.case_id}" + (f"  [judged {r.judged}]" if r.unjudged_work else ""))
            lines.append(f"         {r.rationale[:200]}")
    return "\n".join(lines)
