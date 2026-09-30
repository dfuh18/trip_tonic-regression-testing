"""The judge applied to participant replies (P3, D110; closes Q35).

The simulation's judge (``src.judge``) scores a reply against a *case's*
criteria with the fixture trip prepended. A participant has neither a case nor
the fixture trip, so this module scores against one of four rubrics, chosen by
the request type of the turn (D09), and shows the judge no trip at all
(``prompts/participant_rubrics_v1.md``: no criterion depends on the trip).

Which replies: the **opening turn of each request** (D82), with requests cut
by D100 as in ``src.analysis``. The rubric is the opening turn's own request
type, because it is that turn's reply that is scored: a request that searched
and then drafted in a second turn is scored on its search reply, against the
venue rubric.

Blind as in the simulation: the judge sees the request and the reply, never
thumbs, accept/reject or anything done afterwards. Scores are written to
``study_participant_scores``, which cascades from the suggestion and so from
the session and the account (D14), and whose rationale the eight-month
anonymisation removes (D91). Append-only per judge version, like
``study_scores``: re-scoring under the same version is idempotent, under a new
one adds rows.

Nothing here prints a participant's words.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from src import analysis, shapes
from src.judge import POINTWISE_SCHEMA
from src.llm import Llm, load_prompt, judge_llm
from src.scoring import MAX_JUDGE_ATTEMPTS, _judge_backoff_s, _judge_worth_retrying

PROMPT_NAME = "judge_participant_v1"
RUBRICS_NAME = "participant_rubrics_v1"
REQUEST_TYPES = ("scheduling", "venue_lookup", "factual_qa", "advisory")

_WHAT_IT_DID = {
    "scheduling": "It wrote or changed the group's plan (scheduling).",
    "venue_lookup": "It searched for places (venue lookup).",
    "factual_qa": "It looked up reference information such as weather, climate or an encyclopedia (factual question).",
    "advisory": "It answered from the conversation alone, without looking anything up (advisory).",
}

Row = dict[str, Any]


def load_rubrics() -> tuple[str, dict[str, list[str]]]:
    """(version, criteria per request type) from the rubric file."""
    prompt = load_prompt(RUBRICS_NAME)
    sections = re.split(r"^## (\w+)\s*$", prompt.template, flags=re.M)
    rubrics = {name: [ln[2:].strip() for ln in body.splitlines() if ln.startswith("- ")]
               for name, body in zip(sections[1::2], sections[2::2])}
    missing = [t for t in REQUEST_TYPES if not rubrics.get(t)]
    if missing:
        raise ValueError(f"{RUBRICS_NAME}: no criteria for {missing}")
    return prompt.version, rubrics


def judge_version() -> str:
    """The version stored with every score: prompt and rubrics together."""
    return f"{load_prompt(PROMPT_NAME).version}+{load_rubrics()[0]}"


def request_type_of(turn: Row) -> str:
    """The turn's stored label, or D09 re-derived from its trace if unset."""
    stored = turn.get("request_type")
    if stored in REQUEST_TYPES:
        return stored
    return shapes.d09(shapes.tools_of(turn.get("tool_call_trace") or []))


def opening_turns(turns: Iterable[Row]) -> list[Row]:
    """The first turn of every request, requests cut by D100 per Tonic run."""
    return [seg[0] for run in analysis.runs_of(turns) for seg in analysis.segments(run)]


def render(user_request: str, reply: str, request_type: str) -> str:
    _, rubrics = load_rubrics()
    return load_prompt(PROMPT_NAME).render(
        user_request=user_request.strip(),
        reply=reply.strip() or "(empty reply)",
        request_type_line=_WHAT_IT_DID[request_type],
        criteria="\n".join(f"- {c}" for c in rubrics[request_type]),
    )


@dataclass(frozen=True)
class ParticipantScore:
    suggestion_id: str
    request_type: str
    score: Optional[int]
    rationale: str
    reply_chars: int
    error: Optional[str] = None


def score_turn(turn: Row, reply: str, llm: Optional[Llm] = None) -> ParticipantScore:
    """One opening turn, retried on a transient judge failure (D70)."""
    rtype = request_type_of(turn)
    base = dict(suggestion_id=turn["id"], request_type=rtype)
    if not (reply or "").strip():
        return ParticipantScore(**base, score=None, rationale="", reply_chars=0, error="no reply to score")
    if not (turn.get("user_turn") or "").strip():
        return ParticipantScore(**base, score=None, rationale="", reply_chars=len(reply),
                                error="no request text (anonymised)")
    llm = llm or judge_llm()
    rendered = render(turn["user_turn"], reply, rtype)
    for attempt in range(1, MAX_JUDGE_ATTEMPTS + 1):
        try:
            out = llm.generate(rendered, "Score the reply.", json_schema=POINTWISE_SCHEMA, temperature=0.0)
            parsed = out.parsed or {}
            score = int(parsed.get("score", 0))
            if not 1 <= score <= 10:
                raise RuntimeError(f"judge returned a score outside 1..10: {score}")
            return ParticipantScore(**base, score=score, rationale=str(parsed.get("rationale", "")),
                                    reply_chars=len(reply))
        except Exception as exc:
            if attempt == MAX_JUDGE_ATTEMPTS or not _judge_worth_retrying(exc):
                return ParticipantScore(**base, score=None, rationale="", reply_chars=len(reply),
                                        error=f"judge: {type(exc).__name__}")
            time.sleep(_judge_backoff_s(attempt))
    raise AssertionError("unreachable")


# --- I/O ------------------------------------------------------------------------


def _replies(client: Any, turns: Sequence[Row]) -> dict[str, str]:
    ids = [t["reply_message_id"] for t in turns if t.get("reply_message_id")]
    if not ids:
        return {}
    rows = client.table("chat_messages").select("id, content").in_("id", ids).execute().data
    return {r["id"]: r.get("content") or "" for r in rows}


def _persist(client: Any, turn: Row, s: ParticipantScore, model: str, version: str) -> None:
    from src.comparison import pg_text

    client.table("study_participant_scores").upsert({
        "suggestion_id": s.suggestion_id,
        "session_id": turn["session_id"],
        "request_type": s.request_type,
        "judge_model": model,
        "judge_prompt_version": version,
        "score": s.score,
        "rationale": pg_text(s.rationale),
        "reply_chars": s.reply_chars,
        "error": pg_text(s.error),
    }, on_conflict="suggestion_id,judge_model,judge_prompt_version").execute()


def score_round(client: Any, turns: Sequence[Row], log: Callable[[str], None] = print,
                llm: Optional[Llm] = None) -> list[ParticipantScore]:
    """Score every opening turn not yet scored under the current judge, and
    persist each score as it arrives. Logs counts only, never text."""
    from src.config import settings

    version, model = judge_version(), settings.JUDGE_MODEL
    done = {r["suggestion_id"] for r in _stored(client, [t["id"] for t in turns], model, version)}
    todo = [t for t in opening_turns(turns) if t["id"] not in done]
    replies = _replies(client, todo)
    log(f"judge {model} · {version}: {len(todo)} opening turns to score, {len(done)} already scored")
    out = []
    for i, turn in enumerate(todo, start=1):
        s = score_turn(turn, replies.get(turn.get("reply_message_id"), ""), llm=llm)
        _persist(client, turn, s, model, version)
        out.append(s)
        log(f"  {i}/{len(todo)} {s.request_type}: {s.score if s.score is not None else s.error}")
    return out


def _stored(client: Any, suggestion_ids: Sequence[str], model: str, version: str) -> list[Row]:
    rows: list[Row] = []
    for start in range(0, len(suggestion_ids), 200):
        rows += (client.table("study_participant_scores")
                 .select("suggestion_id, score, request_type, error")
                 .in_("suggestion_id", list(suggestion_ids[start:start + 200]))
                 .eq("judge_model", model).eq("judge_prompt_version", version)
                 .execute().data)
    return rows


def stored_scores(client: Any, turns: Sequence[Row]) -> dict[str, float]:
    """``{suggestion_id: score}`` under the current judge, for P3."""
    from src.config import settings

    rows = _stored(client, [t["id"] for t in turns], settings.JUDGE_MODEL, judge_version())
    return {r["suggestion_id"]: float(r["score"]) for r in rows if r.get("score") is not None}


def score_summary(scores: Iterable[ParticipantScore]) -> Mapping[str, Any]:
    scores = list(scores)
    got = [s.score for s in scores if s.score is not None]
    return {"scored": len(got), "not scored": len(scores) - len(got),
            "mean": round(sum(got) / len(got), 2) if got else None}
