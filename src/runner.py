"""The runner (B07, §3.4): executes the suite, n times per case, recording
everything Table 11 asks for at run and test-case level.

Order of one execution, and the two things that make it a measurement:

  1. ``reset`` the fixture trip, then ``assert_clean`` — the precondition gate
     (invariant 1, D03). A refusal aborts the whole run and is logged; no
     execution row is written for a repetition that did not start clean.
  2. simulate the case (B06), then collect what the application logged for it
     (A02's suggestion rows, A04's mutation rows) and what the simulator spent.

Concurrency is one: the Vertex spacing and the per-minute quota are per user,
and independence between repetitions is the point. Resumable: every finished
execution is a row keyed by (run, case, repetition), so a run that stopped
continues from the next repetition it has not recorded.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

from src import auth, db, reset
from src.auth import SimUser
from src.cases import Case, by_priority, load_cases, suite_version
from src.config import settings
from src.pricing import PRICING_VERSION, llm_cost_usd
from src.simulator import SimulationResult, Simulator

SIMULATOR_PROMPT = "simulator_v1"


class RunAborted(RuntimeError):
    """The precondition gate refused; the run stops here (D03)."""


@dataclass
class RunHandle:
    run_id: str
    trip_id: str
    user: SimUser
    token: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def app_versions(token: str) -> dict:
    """Prompt, tool and model versions from the deployed API (A10)."""
    r = httpx.get(f"{settings.API_BASE_URL}/study/versions", headers=db.api_headers(token), timeout=30)
    r.raise_for_status()
    return r.json()


def open_run(user: SimUser, token: str, cases: list[Case], baseline_ref: Optional[str], notes: str = "") -> str:
    versions = app_versions(token)
    row = {
        "model_version": versions["model_version"],
        "model_released_on": versions.get("model_released_on"),
        "prompt_version": versions.get("prompt_version"),
        "tool_version": versions.get("tool_version"),
        "git_sha": versions.get("git_sha"),
        "suite_version": suite_version(),
        "baseline_ref": baseline_ref,
        "simulator_model": settings.SIMULATOR_MODEL,
        "simulator_prompt_version": _prompt_version(),
        "judge_model": settings.JUDGE_MODEL,
        "notes": notes or f"{len(cases)} cases, pricing {PRICING_VERSION}",
    }
    return db.admin().table("study_runs").insert(row).execute().data[0]["id"]


def _prompt_version() -> str:
    from src.llm import load_prompt

    return load_prompt(SIMULATOR_PROMPT).version


def executions_done(run_id: str) -> set[tuple[str, int]]:
    rows = db.admin().table("study_case_executions").select("case_id, repetition").eq("run_id", run_id).execute().data
    return {(r["case_id"], r["repetition"]) for r in rows}


def collect(trip_id: str, suggestion_ids: list[str]) -> dict:
    """What the application logged for this execution."""
    a = db.admin()
    suggestions = (
        a.table("study_suggestions")
        .select("id, turn_index, request_type, error_code, latency_ms, tokens_input, tokens_output, model_version, retry_count, tool_call_trace, resulting_state_shape")
        .in_("id", suggestion_ids)
        .order("turn_index")
        .execute()
        .data
        if suggestion_ids
        else []
    )
    mutations = a.table("study_mutations").select("table_name, op, origin_kind, origin_suggestion_id, projection").eq("trip_id", trip_id).order("occurred_at").execute().data
    return {"suggestions": suggestions, "mutations": mutations}


def execute_case(handle: RunHandle, case: Case, repetition: int, simulator: Simulator, log: Callable[[str], None]) -> dict:
    """One repetition: gate, simulate, collect, record. Returns the row written."""
    rebuilt = reset.reset(handle.trip_id, handle.token)
    try:
        reset.assert_clean(handle.trip_id)
    except reset.DirtyState as exc:
        raise RunAborted(str(exc)) from exc

    started = time.time()
    result: SimulationResult = simulator.run(case, handle.user, handle.token, handle.trip_id)
    collected = collect(handle.trip_id, result.suggestion_ids)
    agent_in = sum(s["tokens_input"] or 0 for s in collected["suggestions"])
    agent_out = sum(s["tokens_output"] or 0 for s in collected["suggestions"])
    agent_model = next((s["model_version"] for s in collected["suggestions"] if s.get("model_version")), None)
    cost = llm_cost_usd(agent_model, agent_in, agent_out) + llm_cost_usd(result.simulator_model, result.simulator_tokens_input, result.simulator_tokens_output)
    row = {
        "run_id": handle.run_id,
        "case_id": case.case_id,
        "base_case_id": case.base_case_id,
        "provenance": case.provenance,
        "run_priority": case.run_priority,
        "repetition": repetition,
        "repetitions_n": case.repetitions_n,
        "session_id": handle.user.session_id,
        "trip_id": handle.trip_id,
        "declared_constraints": case.declared_constraints.model_dump(),
        "expected_tool_sequence": case.expected_tool_sequence,
        "scoring_criteria": case.scoring_criteria,
        "suggestion_ids": result.suggestion_ids,
        # The ids this repetition built. New every time, and the only way to
        # read a study_mutations row_id back to the stop it touched (D26).
        "fixture_ids": rebuilt.ids,
        "cost_usd": cost,
        "latency_ms": int((time.time() - started) * 1000),
        "token_count": agent_in + agent_out + result.simulator_tokens_input + result.simulator_tokens_output,
        "error": None if result.stopped != "agent_error" else result.stop_reason,
        "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "finished_at": _now(),
    }
    db.admin().table("study_case_executions").insert(row).execute()
    line = (f"{case.case_id} rep {repetition}: {len(result.turns)} turn(s), stopped={result.stopped}, "
            f"mutations={len(collected['mutations'])}, cost={cost:.4f}, {row['latency_ms'] // 1000}s")
    log(line)
    # Also on disk: a run left unattended must be observable from outside its process.
    reset.harness_log(f"RUN {handle.run_id[:8]} {line}")
    return row


def run(
    cases: Optional[list[Case]] = None,
    *,
    n_override: Optional[int] = None,
    priority_only: bool = False,
    baseline_ref: Optional[str] = None,
    resume_run_id: Optional[str] = None,
    simulator: Optional[Simulator] = None,
    log: Callable[[str], None] = print,
) -> str:
    """Execute the suite. Returns the run id. Raises RunAborted on a dirty start."""
    cases = by_priority(cases or load_cases())
    if priority_only:
        cases = [c for c in cases if c.run_priority == 1]
    user = auth.ensure_sim_users(1)[0]
    token = auth.sign_in(user)
    trip_id = reset.ensure_trip(user, token)
    # The gate before there is a run: a dirty start produces no run row at all
    # (D03). The per-repetition gate below then guards every later start.
    if not resume_run_id:
        reset.reset(trip_id, token)
        try:
            reset.assert_clean(trip_id)
        except reset.DirtyState as exc:
            reset.harness_log(f"RUN NOT OPENED: {exc}")
            raise RunAborted(str(exc)) from exc
    run_id = resume_run_id or open_run(user, token, cases, baseline_ref)
    handle = RunHandle(run_id=run_id, trip_id=trip_id, user=user, token=token)
    simulator = simulator or Simulator()
    done = executions_done(run_id) if resume_run_id else set()
    log(f"run {run_id[:8]}: {len(cases)} case(s), {len(done)} execution(s) already recorded")
    totals = {"cost": 0.0, "latency": 0, "tokens": 0}
    for case in cases:
        n = n_override or case.repetitions_n
        for repetition in range(1, n + 1):
            if (case.case_id, repetition) in done:
                continue
            try:
                row = execute_case(handle, case, repetition, simulator, log)
            except RunAborted as exc:
                reset.harness_log(f"RUN {run_id} ABORTED at {case.case_id} rep {repetition}: {exc}")
                db.admin().table("study_runs").update({"notes": f"aborted: {exc}", "finished_at": _now()}).eq("id", run_id).execute()
                raise
            totals["cost"] += row["cost_usd"]
            totals["latency"] += row["latency_ms"]
            totals["tokens"] += row["token_count"]
    existing = db.admin().table("study_case_executions").select("cost_usd, latency_ms, token_count").eq("run_id", run_id).execute().data
    db.admin().table("study_runs").update({
        "finished_at": _now(),
        "cost_usd": round(sum(r["cost_usd"] or 0 for r in existing), 6),
        "latency_ms": sum(r["latency_ms"] or 0 for r in existing),
        "token_count": sum(r["token_count"] or 0 for r in existing),
    }).eq("id", run_id).execute()
    log(f"run {run_id[:8]} finished: {len(existing)} executions")
    return run_id
