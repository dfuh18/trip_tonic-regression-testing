"""Start the B10 baseline run later, then judge it if it came out whole.

    python tools/overnight_baseline.py                 # preflight now, start in 60 min
    python tools/overnight_baseline.py --in 5          # start in 5 minutes
    python tools/overnight_baseline.py --dry-run       # preflight and plan only

Leave it running in a terminal (the machine must not sleep, and the local API
must stay up — `pnpm dev`). Everything is written to
`runs/overnight-<UTC date>.log` (git-ignored) as well as the console.

Order, and what stops it:

1. **Preflight, now.** The local API answers, and the commit it runs is the one
   checked out here (a run records `api_commit` beside `git_sha`, and a
   mismatch makes the baseline describe code that is not the code on disk);
   the pinned model and its release date; the Vertex EU endpoint (D89); a
   simulated member can sign in. A failure here stops before the wait, so it
   is seen before the operator leaves.
2. **Wait**, then the same preflight again.
3. **The run.** `runner.run()` over the whole suite at each case's own n
   (8 per seed, 4 per expansion, D21), notes marking it as B10.
4. **Sanity check.** Completeness only, never quality — a failing case is a
   result, not a reason to skip the judge: the run row is closed and carries
   every version field; every (case, repetition) has an execution; every
   execution was structurally checked.
5. **The judge** (`scoring.score_run`) only if 4 held. Each execution is
   judged against the day it ran on, in UTC (D94).

Dates: the agent's "TODAY IS" line, the near-dated trip the harness builds, and
the day the judge is told are all the execution's UTC day, so an overnight run
crossing midnight (local or UTC) and a judge pass the next morning agree.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from src import db  # noqa: E402
from src.config import settings  # noqa: E402

LOG_DIR = ROOT / "runs"
RUN_VERSION_FIELDS = (
    "model_version", "model_released_on", "prompt_version", "tool_version", "git_sha",
    "suite_version", "api_version", "api_commit", "app_version",
    "simulator_model", "simulator_prompt_version",
)
EU_ENDPOINT = "https://aiplatform.eu.rep.googleapis.com"


class Log:
    def __init__(self) -> None:
        LOG_DIR.mkdir(exist_ok=True)
        self.path = LOG_DIR / f"overnight-{datetime.now(timezone.utc):%Y-%m-%d}.log"

    def __call__(self, message: str) -> None:
        line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z  {message}"
        print(line, flush=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _health_url() -> str:
    base = settings.API_BASE_URL.rstrip("/")
    return (base[: -len("/api")] if base.endswith("/api") else base) + "/health"


def preflight(log: Log) -> list[str]:
    """Problems that make an unattended run pointless. Empty means go."""
    from src import auth, pilot

    problems: list[str] = []
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    try:
        health = httpx.get(_health_url(), timeout=15).json()
        commit = str(health.get("commit") or "")
        log(f"API {_health_url()} answers: version {health.get('version')}, commit {commit}")
        if commit in ("", "unknown") or not head.startswith(commit):
            problems.append(
                f"the API runs commit {commit or '?'} but HEAD is {head[:12]} — restart `pnpm dev` "
                "so the run records the code on disk"
            )
    except Exception as exc:
        problems.append(f"the local API does not answer at {_health_url()}: {exc}")

    model, released = pilot.pinned_model()
    log(f"agent model pinned: {model} (released {released}); harness VERTEX_MODEL {settings.VERTEX_MODEL}")
    if settings.VERTEX_MODEL != model:
        problems.append(f"harness VERTEX_MODEL {settings.VERTEX_MODEL} differs from the pinned {model}")
    if settings.VERTEX_BASE_URL.rstrip("/") != EU_ENDPOINT:
        problems.append(f"harness Vertex endpoint is {settings.VERTEX_BASE_URL}, not the EU one (D89)")
    api_env = (ROOT.parents[1] / "apps" / "api" / ".env").read_text(encoding="utf-8")
    if "VERTEX_BASE_URL" in api_env:
        problems.append("apps/api/.env overrides VERTEX_BASE_URL — the run must use the EU default (D89)")

    try:
        user = auth.ensure_sim_users(1)[0]
        auth.sign_in(user)
        log("simulated member signs in")
    except Exception as exc:
        problems.append(f"a simulated member cannot sign in: {exc}")

    today = datetime.now(timezone.utc).date()
    log(f"UTC today {today}; local now {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}")
    return problems


def sanity(run_id: str, log: Log) -> list[str]:
    """Completeness of the run. Empty means judge it."""
    from src.cases import load_cases
    from src.execution import latest_attempts

    problems: list[str] = []
    run = db.admin().table("study_runs").select("*").eq("id", run_id).execute().data
    if not run:
        return [f"run {run_id} has no row"]
    run = run[0]
    if not run.get("finished_at"):
        problems.append("the run row was never closed (finished_at is null)")
    if str(run.get("notes") or "").startswith("aborted"):
        problems.append(f"the run aborted: {run['notes']}")
    unset = [f for f in RUN_VERSION_FIELDS if run.get(f) in (None, "")]
    if unset:
        problems.append(f"version fields unset on the run row: {', '.join(unset)}")

    rows = db.admin().table("study_case_executions").select("*").eq("run_id", run_id).execute().data
    latest, superseded = latest_attempts(rows)
    have = {(r["case_id"], r["repetition"]) for r in latest}
    expected = {(c.case_id, n) for c in load_cases() for n in range(1, c.repetitions_n + 1)}
    missing = sorted(expected - have)
    if missing:
        problems.append(f"{len(missing)} of {len(expected)} repetitions have no execution, e.g. {missing[:3]}")
    unchecked = [r for r in latest if r.get("structural_outcome") not in ("none", "detected")]
    if unchecked:
        problems.append(f"{len(unchecked)} execution(s) were not structurally checked")

    detected = sum(1 for r in latest if r.get("structural_outcome") == "detected")
    log(f"run {run_id[:8]}: {len(latest)} executions ({superseded} superseded attempts), "
        f"{len(latest) - detected} structurally clean, {detected} detected")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--in", dest="minutes", type=float, default=60.0, help="minutes until the run starts")
    parser.add_argument("--dry-run", action="store_true", help="preflight and plan only")
    args = parser.parse_args(argv)
    log = Log()

    from src.cases import load_cases

    cases = load_cases()
    executions = sum(c.repetitions_n for c in cases)
    start = datetime.now(timezone.utc) + timedelta(minutes=args.minutes)
    log(f"overnight baseline: {len(cases)} cases, {executions} executions; log {log.path}")

    problems = preflight(log)
    if problems:
        for p in problems:
            log(f"PREFLIGHT FAILED: {p}")
        return 2
    log(f"preflight passed; the run starts at {start:%H:%M} UTC "
        f"({start.astimezone():%H:%M %Z} local)")
    if args.dry_run:
        return 0

    time.sleep(max(0.0, (start - datetime.now(timezone.utc)).total_seconds()))
    problems = preflight(log)
    if problems:
        for p in problems:
            log(f"PREFLIGHT FAILED AT START: {p}")
        return 2

    from src import runner

    try:
        run_id = runner.run(
            notes="B10 baseline — overnight, started by tools/overnight_baseline.py",
            log=log,
        )
    except Exception as exc:
        log(f"RUN FAILED: {type(exc).__name__}: {exc}")
        return 3
    log(f"run {run_id} finished")

    problems = sanity(run_id, log)
    if problems:
        for p in problems:
            log(f"SANITY FAILED: {p}")
        log(f"judge NOT started. Resume the run with runner.run(resume_run_id='{run_id}') and re-run the check.")
        return 4

    from src import scoring

    log("sanity passed; judging")
    result = scoring.score_run(run_id, log=log)
    log(scoring.report(result))
    log(f"DONE. Run {run_id}. Next: open notebooks/sim/03_baseline.ipynb with this run id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
