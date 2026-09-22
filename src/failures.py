"""What actually went wrong in a run, and whose fault it was (D59).

A run's execution rows carry one `error` string each, which is enough to know
that something failed and not enough to know what. The evidence that separates
"the provider was busy", "our own quota refused it" and "the agent could not
answer" lives one table down, on `study_suggestions`: the error code, how many
times the model layer retried underneath, how long the turn ran against its
deadline, and whether any tokens moved at all.

That diagnosis was being done by hand, which meant it was done only when
someone thought to. Two executions in a 27-case run were reported as
`agent returned 502` — the agent's fault — and were in fact turns killed by our
own 85-second deadline after the provider never answered: zero tokens in, zero
out, two internal retries. Reading the same evidence at the end of every run is
cheap, and it is the difference between a failure rate that means something and
one that quietly blames the agent for a queue.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TurnDiagnosis:
    turn_index: int
    error_code: Optional[str]
    retry_count: int
    latency_ms: int
    llm_calls: int
    tokens_in: int
    tokens_out: int

    @property
    def never_answered(self) -> bool:
        """No tokens moved in either direction — no model call completed."""
        return self.tokens_in == 0 and self.tokens_out == 0


@dataclass
class Failure:
    case_id: str
    repetition: int
    attempt: int
    error: str
    blame: str  # platform | ours | agent
    turns: list[TurnDiagnosis] = field(default_factory=list)

    def summary(self) -> str:
        last = self.turns[-1] if self.turns else None
        bits = [f"{self.case_id} rep {self.repetition} attempt {self.attempt}",
                f"blame={self.blame}", self.error[:70]]
        if last is not None:
            bits.append(
                f"turn {last.turn_index}: code={last.error_code} retries={last.retry_count} "
                f"{last.latency_ms}ms tokens={last.tokens_in}/{last.tokens_out}"
            )
            if last.never_answered and last.retry_count:
                bits.append("NO MODEL CALL EVER COMPLETED — the provider, not the agent")
        return " | ".join(bits)


def for_run(run_id: str) -> list[Failure]:
    from src import db
    from src.runner import failure_class

    a = db.admin()
    rows = (
        a.table("study_case_executions")
        .select("case_id, repetition, attempt, error, suggestion_ids")
        .eq("run_id", run_id)
        .execute()
        .data
    )
    out: list[Failure] = []
    for row in rows:
        if not row.get("error"):
            continue
        failure = Failure(
            case_id=row["case_id"],
            repetition=row["repetition"],
            attempt=row.get("attempt") or 1,
            error=row["error"],
            blame=failure_class(row["error"]) or "unknown",
        )
        ids = row.get("suggestion_ids") or []
        if ids:
            turns = (
                a.table("study_suggestions")
                .select("turn_index, error_code, retry_count, latency_ms, llm_calls, tokens_input, tokens_output")
                .in_("id", ids)
                .order("turn_index")
                .execute()
                .data
            )
            failure.turns = [
                TurnDiagnosis(
                    turn_index=t.get("turn_index") or 0,
                    error_code=t.get("error_code"),
                    retry_count=t.get("retry_count") or 0,
                    latency_ms=t.get("latency_ms") or 0,
                    llm_calls=t.get("llm_calls") or 0,
                    tokens_in=t.get("tokens_input") or 0,
                    tokens_out=t.get("tokens_output") or 0,
                )
                for t in turns
            ]
        out.append(failure)
    return sorted(out, key=lambda f: (f.case_id, f.repetition, f.attempt))


def report(failures: list[Failure], total: int) -> str:
    if not failures:
        return f"no failed executions in {total}."
    blame = Counter(f.blame for f in failures)
    lines = [
        f"{len(failures)} failed execution(s) of {total} — "
        + ", ".join(f"{k}: {v}" for k, v in sorted(blame.items())),
        "",
        "  platform = the provider was busy or ran past our deadline; retried (D59)",
        "  ours     = our own rate limit or monthly quota; never retried, aborts the run",
        "  agent    = the agent genuinely failed to answer; this is a result, not noise",
        "",
    ]
    lines += [f"  {f.summary()}" for f in failures]
    stale = [f for f in failures if f.blame == "agent"
             and f.turns and f.turns[-1].never_answered and f.turns[-1].retry_count]
    if stale:
        lines += [
            "",
            "SUSPECT CLASSIFICATION: the execution(s) above are blamed on the agent but no model",
            "call completed on the failing turn. If this appears, the API's failure classification",
            "has drifted from what the evidence says — see agent.service.ts, the empty-reply split.",
        ]
    return "\n".join(lines)


def latency_profile(run_id: str) -> str:
    """Latency split by whether the turn waited on the provider (D60).

    Total latency silently includes capacity backoff, and the two populations
    are far enough apart that mixing them makes the number unusable as a
    regression signal: measured across 194 turns, the median was 4.5s clean
    against 13.0s for a turn that retried internally — a 3x swing driven by
    queue depth, not by the agent.

    So the comparison is made on clean turns and the retried ones are reported
    beside them. No new logged field was needed: `retry_count` already
    distinguishes them, it just was not being read.
    """
    from statistics import median

    from src import db

    a = db.admin()
    ids = [
        i
        for row in a.table("study_case_executions").select("suggestion_ids").eq("run_id", run_id).execute().data
        for i in (row.get("suggestion_ids") or [])
    ]
    if not ids:
        return "latency: no turns recorded."
    turns = (
        a.table("study_suggestions")
        .select("retry_count, latency_ms, error_code")
        .in_("id", ids)
        .execute()
        .data
    )
    done = [t for t in turns if not t.get("error_code")]
    clean = [t["latency_ms"] for t in done if not (t.get("retry_count") or 0) and t.get("latency_ms")]
    waited = [t["latency_ms"] for t in done if (t.get("retry_count") or 0) and t.get("latency_ms")]
    lines = [
        f"latency of completed turns ({len(done)} of {len(turns)}):",
        f"  clean              n={len(clean):<4d} median {int(median(clean)) if clean else 0}ms"
        f"   <- compare runs on this",
        f"  waited on capacity n={len(waited):<4d} median {int(median(waited)) if waited else 0}ms",
    ]
    if done:
        share = 100 * len(waited) / len(done)
        lines.append(f"  {share:.1f}% of completed turns waited on the provider at least once")
        if share > 25:
            lines.append(
                "  WARNING: over a quarter of turns queued — a latency comparison against another "
                "run is measuring the provider, not the agent"
            )
    return "\n".join(lines)
