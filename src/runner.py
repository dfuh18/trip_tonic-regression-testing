"""The runner (B07, §3.4): executes the suite, n times per case, recording
everything Table 11 asks for at run and test-case level.

Order of one execution, and the two things that make it a measurement:

  1. ``provision`` a fixture trip **of this repetition's own** (D38), then
     ``assert_clean`` — the precondition gate (invariant 1, D03). A refusal
     aborts the whole run and is logged; no execution row is written for a
     repetition that did not start clean.
  2. simulate the case (B06), then collect what the application logged for it
     (A02's suggestion rows, A04's mutation rows) and what the simulator spent.

Nothing is deleted between repetitions. Isolation is by construction — a new
trip has no chat, no run, no draft and no edit to inherit — and the record of
every execution survives the run, which is what the checker, the judge and the
analysis all read afterwards.

Concurrency is one: the Vertex spacing and the per-minute quota are per user,
and independence between repetitions is the point. Concurrency alone was not
enough — serial requests still exhausted the key's per-minute quota, so every
model call the run causes, its own and the agent's, is paced against one
budget (D39, ``src/ratelimit.py``). Resumable: every finished execution is a
row keyed by (run, case, repetition), so a run that stopped continues from the
next repetition it has not recorded.
"""

from __future__ import annotations

import json

import time
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

from src import auth, fixture, db, reset
from src.auth import SimUser
from src.cases import Case, by_priority, load_cases, suite_version
from src.config import settings
from src.pricing import PRICING_VERSION, llm_cost_usd
from src.ratelimit import limiter
from src.simulator import SimulationResult, Simulator

SIMULATOR_PROMPT = "simulator_v1"


class RunAborted(RuntimeError):
    """The precondition gate refused; the run stops here (D03)."""


class SimulatorFailed(RuntimeError):
    """The simulator's own model call failed — the harness, not the agent."""


#: How many executions a smoke run does at once. Four is chosen against the
#: provider rather than the machine: the executions are almost all waiting, and
#: the ceiling that matters is Vertex's shared capacity, not local CPU.
SMOKE_CONCURRENCY = 4

#: Consecutive simulator failures before the run gives up. One is an upstream
#: hiccup; three in a row is the simulator being down, and continuing would
#: spend the budget recording nothing.
MAX_CONSECUTIVE_SIMULATOR_FAILURES = 3

#: How many times a repetition may be attempted when the PLATFORM refused it
#: (D59). Not a general retry budget: only a failure that is nobody's fault but
#: the provider's is re-run, and every attempt stays in the record.
#:
#: Four, because a baseline needs every planned execution and one spare attempt
#: was not enough — a 27-case run lost three executions to platform refusals,
#: and D23's 8/8 seed criterion turns a 3.8% per-execution loss into roughly a
#: 27% chance of losing a seed for reasons that have nothing to do with the
#: agent.
MAX_ATTEMPTS_PER_REPETITION = 4

#: Statuses that mean the model provider could not serve the turn: it was busy
#: (503, which D45 gave its own status) or it ran past our deadline without
#: answering (504). Re-running these is sampling, not laundering.
PLATFORM_REFUSAL_STATUSES = ("503", "504")

#: Statuses that mean **we** refused the turn — our own per-minute or monthly AI
#: quota (`ai-quota.ts`, `failureKind: 'rate_limited_by_us'`). Never retried,
#: and fatal to the run: it is a statement about this harness's configuration,
#: not about the agent, and every execution after it would hit the same wall.
#: Retrying it would also make it worse — being rate limited is what being rate
#: limited is caused by.
OUR_OWN_LIMIT_STATUSES = ("429",)


def failure_class(error: Optional[str]) -> Optional[str]:
    """Who failed: ``platform``, ``ours``, ``agent`` — or None if nothing did.

    The distinction is the whole of D59's retry policy, and it is available
    only because the API gives each cause its own status (D45, and the
    empty-reply split that followed): 503 busy, 504 past the deadline, 429 our
    own quota, 502 the agent genuinely failing to answer. Before that split a
    turn killed by our 85-second deadline arrived as "the agent returned an
    empty reply", which is both wrong and un-retryable.
    """
    if not error:
        return None
    if any(s in error for s in OUR_OWN_LIMIT_STATUSES):
        return "ours"
    if any(s in error for s in PLATFORM_REFUSAL_STATUSES):
        return "platform"
    return "agent"


def is_platform_refusal(error: Optional[str]) -> bool:
    return failure_class(error) == "platform"


@dataclass
class RunHandle:
    """What every execution of one run shares. Not the trip: since D38 each
    repetition builds its own, and the id belongs to the execution row."""

    run_id: str
    user: SimUser
    token: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def app_versions(token: str) -> dict:
    """Prompt, tool and model versions from the deployed API (A10)."""
    r = httpx.get(f"{settings.API_BASE_URL}/study/versions", headers=db.api_headers(token), timeout=30)
    r.raise_for_status()
    return r.json()


def record_simulator_failure(run_id, handle, case, repetition, attempt, exc) -> None:
    """One execution row for a repetition the simulator could not run.

    Written for every attempt, not only the last, so the platform-failure rate
    counts what the platform actually refused (D53, D67). `suggestion_ids` is
    empty because nothing reached the agent — that is what distinguishes this
    from an execution the agent failed.
    """
    db.admin().table("study_case_executions").insert({
        "run_id": run_id, "case_id": case.case_id, "base_case_id": case.base_case_id,
        "provenance": case.provenance, "run_priority": case.run_priority,
        "repetition": repetition, "repetitions_n": case.repetitions_n,
        "attempt": attempt,
        "session_id": handle.user.session_id,
        "suggestion_ids": [], "error": f"simulator: {exc}",
        "started_at": _now(), "finished_at": _now(),
    }).execute()


def open_run(
    user: SimUser,
    token: str,
    cases: list[Case],
    baseline_ref: Optional[str],
    notes: str = "",
    concurrency: int = 1,
) -> str:
    versions = app_versions(token)
    serving = serving_api()
    row = {
        **serving,
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
    # Concurrency belongs in the record: a run made four-at-a-time and one made
    # serially do not have comparable latency or failure rates, and a reader
    # with only the numbers cannot tell which is which.
    if concurrency != 1:
        row["notes"] = f"{row['notes']} [concurrency {concurrency}]"
    return db.admin().table("study_runs").insert(row).execute().data[0]["id"]


def serving_api(log: Callable[[str], None] = print) -> dict[str, Optional[str]]:
    """What the API process on the other end actually is (D63).

    Asked of the RUNNING server rather than read from the repository, because
    those are different questions and once gave different answers: a full
    suite ran against a stale dev server whose code predated the fix under
    test, and every number in it described the old behaviour while the run row
    pointed at the new commit.

    A mismatch is a warning and not an abort: a deliberate run against a
    deployed build is legitimate, and only the operator knows which they meant.
    Saying it out loud is the part that was missing.
    """
    import subprocess

    import httpx

    from src.config import settings

    info: dict[str, Optional[str]] = {"api_version": None, "api_commit": None, "app_version": None}
    try:
        base = settings.API_BASE_URL.rstrip("/").removesuffix("/api")
        health = httpx.get(f"{base}/health", timeout=10).json()
        info["api_version"] = health.get("version")
        info["api_commit"] = health.get("commit")
    except Exception as exc:
        log(f"    WARNING could not read the API's /health — api_version unrecorded ({exc})")

    web_pkg = Path(__file__).resolve().parents[3] / "apps" / "web" / "package.json"
    try:
        info["app_version"] = json.loads(web_pkg.read_text(encoding="utf-8")).get("version")
    except Exception:
        pass

    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()[:12]
    except Exception:
        head = None
    served = info["api_commit"]
    if head and served and served != "unknown" and not head.startswith(served)             and not served.startswith(head):
        log(f"    WARNING the API serving this run was built from {served}, but the working tree "
            f"is {head}. This run does NOT measure the code on disk — restart the API, or accept "
            f"that the record's git_sha and its api_commit disagree.")
    return info


def _prompt_version() -> str:
    from src.llm import load_prompt

    return load_prompt(SIMULATOR_PROMPT).version


def executions_done(run_id: str) -> set[tuple[str, int]]:
    rows = db.admin().table("study_case_executions").select("case_id, repetition").eq("run_id", run_id).execute().data
    return {(r["case_id"], r["repetition"]) for r in rows}


def collect(trip_id: str, suggestion_ids: list[str], exclude_mutations: tuple[str, ...] = ()) -> dict:
    """What the application logged for this execution.

    ``exclude_mutations`` are the rows the fixture build wrote before the case
    began (D38): the trip is this repetition's alone, so every other mutation
    row on it is the case's.
    """
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
    mutations = [
        m
        for m in a.table("study_mutations")
        .select("id, table_name, op, origin_kind, origin_suggestion_id, changed_keys, projection")
        .eq("trip_id", trip_id)
        .order("occurred_at")
        .execute()
        .data
        if m["id"] not in exclude_mutations
    ]
    return {"suggestions": suggestions, "mutations": mutations}


def execute_case(
    handle: RunHandle,
    case: Case,
    repetition: int,
    simulator: Simulator,
    log: Callable[[str], None],
    provisioned: Optional[reset.ResetResult] = None,
    attempt: int = 1,
) -> dict:
    """One repetition: provision, gate, simulate, collect, record.

    A trip of its own per repetition (D38), so nothing this execution recorded
    is destroyed to make room for the next one. ``provisioned`` lets the
    caller hand over a trip it already built and gated — the run's own opening
    gate, which must pass before there is a run row at all (D03).
    """
    trip_fixture = fixture.for_case(case)
    rebuilt = provisioned or reset.provision(
        handle.user, handle.token, f"{case.case_id} r{repetition}", fixture=trip_fixture
    )
    trip_id = rebuilt.trip_id
    if provisioned is None:
        try:
            reset.assert_clean(trip_id, fixture=trip_fixture)
        except reset.DirtyState as exc:
            raise RunAborted(str(exc)) from exc

    started = time.time()
    try:
        result: SimulationResult = simulator.run(case, handle.user, handle.token, trip_id)
    except Exception as exc:  # the SIMULATOR's own model call, not the agent's
        # A harness failure, not an agent failure, and the two must not be
        # confused: D44 counts a lost execution as a failure of the case, and
        # this is not that. It is recorded as an execution that did not happen
        # — no suggestion ids, error prefixed `simulator:` — so the analysis
        # can tell the two apart, and the run carries on.
        #
        # Carrying on is the point. A 504 from the simulator's own provider
        # used to propagate out and kill the whole run; at 140 executions that
        # means one upstream hiccup ends an unattended evening. The run loop
        # aborts only if these start arriving consecutively, because a
        # simulator that is down should not burn the budget one case at a time.
        raise SimulatorFailed(f"{type(exc).__name__}: {exc}") from exc
    collected = collect(trip_id, result.suggestion_ids, rebuilt.build_mutation_ids)
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
        "attempt": attempt,
        "repetitions_n": case.repetitions_n,
        "session_id": handle.user.session_id,
        "trip_id": trip_id,
        "declared_constraints": case.declared_constraints.model_dump(),
        "expected_tool_sequence": case.expected_tool_sequence,
        "scoring_criteria": case.scoring_criteria,
        "suggestion_ids": result.suggestion_ids,
        # The ids this repetition built. New every time, and the only way to
        # read a study_mutations row_id back to the stop it touched (D26).
        "fixture_ids": rebuilt.ids,
        # Which mutation rows were the build's, so the checker can exclude
        # them when it reads the trip back after the run (D38).
        "build_mutation_ids": list(rebuilt.build_mutation_ids),
        "cost_usd": cost,
        "latency_ms": int((time.time() - started) * 1000),
        "token_count": agent_in + agent_out + result.simulator_tokens_input + result.simulator_tokens_output,
        "error": None if result.stopped != "agent_error" else result.stop_reason,
        "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "finished_at": _now(),
    }
    db.admin().table("study_case_executions").insert(row).execute()
    line = (f"{case.case_id} rep {repetition}"
            + (f" attempt {attempt}" if attempt > 1 else "")
            + f": {len(result.turns)} turn(s), stopped={result.stopped}, "
            f"mutations={len(collected['mutations'])}, cost={cost:.4f}, {row['latency_ms'] // 1000}s")
    log(line)
    # Also on disk: a run left unattended must be observable from outside its process.
    reset.harness_log(f"RUN {handle.run_id[:8]} {line}")
    return row


def smoke(log: Callable[[str], None] = print) -> str:
    """Every seed once, in parallel — fast feedback, not a measurement.

    A regression suite that takes two hours is a suite nobody runs before
    lunch, so this exists to answer one question quickly: does the agent still
    do the basic things? Seeds only (they are the minimum-functionality cases,
    §3.1 P7), one repetition each, run concurrently.

    **It is not the baseline and must never be used as one**, for two reasons
    that have nothing to do with correctness. Latency, tokens and retry counts
    measured under contention are not the same quantity as measured serially,
    and Q22 defers bounding them until a baseline says what they look like —
    comparing a parallel run with a sequential one would compare two different
    machines. And parallelism multiplies our request rate against the
    provider's *shared* capacity, which is the one limit the sim tier does not
    raise, so the 429 rate rises and D44 counts every lost execution as a
    failure of the case.

    Structurally it is safe, which it was not before D38: every repetition
    builds its own trip, so concurrent executions share no chat, no run, no
    draft and no slots. The concurrency is recorded on the run row, so a
    reader can tell at a glance which runs are comparable with which.
    """
    seeds = [c for c in load_cases() if c.provenance == "seeded"]
    return run(
        seeds,
        n_override=1,
        concurrency=SMOKE_CONCURRENCY,
        notes=f"SMOKE {len(seeds)} seeds at n=1, concurrency {SMOKE_CONCURRENCY} — NOT a baseline",
        log=log,
    )


def run(
    cases: Optional[list[Case]] = None,
    *,
    n_override: Optional[int] = None,
    concurrency: int = 1,
    priority_only: bool = False,
    baseline_ref: Optional[str] = None,
    resume_run_id: Optional[str] = None,
    simulator: Optional[Simulator] = None,
    notes: str = "",
    log: Callable[[str], None] = print,
) -> str:
    """Execute the suite. Returns the run id. Raises RunAborted on a dirty start."""
    cases = by_priority(cases or load_cases())
    if priority_only:
        cases = [c for c in cases if c.run_priority == 1]
    user = auth.ensure_sim_users(1)[0]
    token = auth.sign_in(user)
    # The gate before there is a run: a start the harness cannot vouch for
    # produces no run row at all (D03). The trip it builds is handed to the
    # first execution rather than thrown away, so the gate is a real
    # provisioning of a real repetition and not a rehearsal of one.
    opening: Optional[reset.ResetResult] = None
    if not resume_run_id:
        opening = reset.provision(user, token, "gate")
        try:
            reset.assert_clean(opening.trip_id)
        except reset.DirtyState as exc:
            reset.harness_log(f"RUN NOT OPENED: {exc}")
            raise RunAborted(str(exc)) from exc
    # A run that is not the baseline says so in its own row. `notes` is the
    # only field that can carry it, and a probe run mistaken for the reference
    # run later is not a mistake anything else would catch.
    run_id = resume_run_id or open_run(user, token, cases, baseline_ref, notes, concurrency)
    handle = RunHandle(run_id=run_id, user=user, token=token)
    simulator = simulator or Simulator()
    done = executions_done(run_id) if resume_run_id else set()
    log(f"run {run_id[:8]}: {len(cases)} case(s), {len(done)} execution(s) already recorded")
    totals = {"cost": 0.0, "latency": 0, "tokens": 0}
    simulator_failures = 0
    platform_retries = 0   # attempts spent on the provider being busy
    platform_losses = 0    # repetitions the provider refused to the last attempt
    for case in cases:
        n = n_override or case.repetitions_n
        for repetition in range(1, n + 1):
            if (case.case_id, repetition) in done:
                continue
            try:
                # The gate's trip is on the fixed calendar, so only a case that
                # wants that calendar may inherit it (D54); a near-dated case
                # builds its own and the gate's trip goes to the next taker.
                inherit = opening if case.fixture_dates == "fixture" else None
                row = execute_case(handle, case, repetition, simulator, log, provisioned=inherit)
                if inherit is not None:
                    opening = None  # the gate's trip belongs to one execution only
                simulator_failures = 0
                # The platform gets several chances to not be busy (D59); the
                # agent gets none, and our own quota gets none either. Every
                # attempt stays in the record — the refusals are evidence about
                # the platform, the completed one is evidence about the agent,
                # and merging them would lose the first.
                for attempt in range(2, MAX_ATTEMPTS_PER_REPETITION + 1):
                    kind = failure_class(row.get("error"))
                    if kind == "ours":
                        break  # handled below, as a run-level fault
                    if kind != "platform":
                        break
                    warn = (f"    WARNING platform refused {case.case_id} rep {repetition} "
                            f"({row['error']}) — retrying, attempt {attempt} of "
                            f"{MAX_ATTEMPTS_PER_REPETITION}")
                    log(warn)
                    reset.harness_log(f"RUN {run_id[:8]} {warn.strip()}")
                    platform_retries += 1
                    row = execute_case(handle, case, repetition, simulator, log, attempt=attempt)
                final = failure_class(row.get("error"))
                if final == "ours":
                    # Our own quota, which is a fact about this harness's
                    # configuration and not about the agent. Every execution
                    # after this one would hit the same wall, and retrying is
                    # what being rate limited is caused by — so stop, and say
                    # which limit and which tier to go and look at.
                    msg = (f"RUN {run_id} ABORTED: refused by OUR OWN limit — {row['error']}. "
                           f"This is not the provider. Check the sim account's subscription tier "
                           f"and the per-minute/monthly caps in apps/api/src/lib/subscription-tier.ts")
                    log(msg)
                    reset.harness_log(msg)
                    db.admin().table("study_runs").update({
                        "notes": f"aborted: refused by our own rate limit/quota — {row['error']}",
                        "finished_at": _now(),
                    }).eq("id", run_id).execute()
                    raise RunAborted(msg)
                if final == "platform":
                    lost = (f"    WARNING {case.case_id} rep {repetition} LOST to the platform after "
                            f"{MAX_ATTEMPTS_PER_REPETITION} attempts ({row['error']})")
                    log(lost)
                    reset.harness_log(f"RUN {run_id[:8]} {lost.strip()}")
                    platform_losses += 1
                elif final == "agent":
                    log(f"    {case.case_id} rep {repetition} failed on the AGENT "
                        f"({row['error']}) — not retried, this is a result")
            except SimulatorFailed as exc:
                opening = None
                # The simulator runs on the same provider as the agent, so it
                # meets the same queue. A member turn lost to a 429/503/504
                # there costs the whole repetition and says nothing about the
                # agent — so it is re-run on the same terms (D59). Everything
                # else (a malformed persona, a parse failure) is a real fault
                # and is recorded as one.
                # Each refused attempt is recorded before the next is tried
                # (D67). D53's rule is that both attempts stay in the record
                # because the refusal is evidence about the platform, and the
                # simulator path was keeping only the one that succeeded — so
                # a simulator refusal recovered on attempt 2 vanished from the
                # platform-failure rate entirely and survived only in the log.
                sim_attempt = 1
                while (failure_class(f"simulator: {exc}") == "platform"
                       and sim_attempt < MAX_ATTEMPTS_PER_REPETITION):
                    record_simulator_failure(run_id, handle, case, repetition, sim_attempt, exc)
                    sim_attempt += 1
                    warn = (f"    WARNING simulator refused by the platform on {case.case_id} rep "
                            f"{repetition} ({exc}) — retrying, attempt {sim_attempt} of "
                            f"{MAX_ATTEMPTS_PER_REPETITION}")
                    log(warn)
                    reset.harness_log(f"RUN {run_id[:8]} {warn.strip()}")
                    platform_retries += 1
                    try:
                        row = execute_case(handle, case, repetition, simulator, log,
                                           attempt=sim_attempt)
                        simulator_failures = 0
                        break
                    except SimulatorFailed as again:
                        exc = again
                else:
                    pass
                if simulator_failures == 0 and sim_attempt > 1:
                    continue  # recovered on a later attempt
                simulator_failures += 1
                if sim_attempt > 1:
                    platform_losses += 1
                record_simulator_failure(run_id, handle, case, repetition, sim_attempt, exc)
                line = f"{case.case_id} rep {repetition}: SIMULATOR FAILED — {exc}"
                log(line)
                reset.harness_log(f"RUN {run_id[:8]} {line}")
                if simulator_failures >= MAX_CONSECUTIVE_SIMULATOR_FAILURES:
                    reset.harness_log(f"RUN {run_id} ABORTED: {simulator_failures} simulator failures in a row")
                    db.admin().table("study_runs").update({
                        "notes": f"aborted: {simulator_failures} consecutive simulator failures",
                        "finished_at": _now(),
                    }).eq("id", run_id).execute()
                    raise RunAborted(f"{simulator_failures} consecutive simulator failures") from exc
                continue
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
    # What the pacing cost, stated rather than inferred from the wall clock
    # (D39). If this is most of a run's duration the key's budget is set too
    # low, and VERTEX_CALLS_PER_MINUTE is the one line to change.
    paced = limiter().waited_s
    log(f"run {run_id[:8]} finished: {len(existing)} executions, {paced / 60:.1f} min spent pacing")
    # Coverage travels with the run (D50). A suite that never called a tool
    # cannot have noticed that tool breaking, and the only honest place to say
    # so is beside the result.
    try:
        from src.coverage import for_run, report

        log("\n" + report(for_run(run_id), run_id))
    except Exception as exc:  # never let reporting break a completed run
        log(f"coverage report unavailable: {exc}")

    # What failed and whose fault it was, read from the evidence rather than
    # from the error string alone (D59). Printed every run, not on request:
    # the misclassification this exists to catch was invisible for as long as
    # someone had to think to go looking for it.
    if platform_retries or platform_losses:
        log(f"PLATFORM: {platform_retries} retry/retries spent, {platform_losses} repetition(s) "
            f"lost after {MAX_ATTEMPTS_PER_REPETITION} attempts")
    try:
        from src.failures import (
            for_run as failures_for_run,
            latency_profile,
            report as failures_report,
        )

        recorded = (
            db.admin().table("study_case_executions").select("id", count="exact")
            .eq("run_id", run_id).limit(1).execute().count or 0
        )
        log("\n" + failures_report(failures_for_run(run_id), recorded))
        log("\n" + latency_profile(run_id))
    except Exception as exc:
        log(f"failure report unavailable: {exc}")
    reset.harness_log(f"RUN {run_id[:8]} finished: {len(existing)} executions, paced {paced:.0f}s")
    return run_id
