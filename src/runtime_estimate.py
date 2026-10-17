"""How long a run took, judging included, and what that implies in parallel.

The run record carries the conversation's time (`study_case_executions`:
`started_at` / `finished_at`, `latency_ms`) and the run's wall clock
(`study_runs`), but judging is a separate pass after the run closes
(`tools/overnight_baseline.py`), so its time is read from the `created_at` of
the rows it writes: one `study_scores` row per point-wise call, one
`study_comparisons` row per pair-wise comparison (both orderings). Each pass is
sequential, so the time between consecutive rows is the time one execution's
judging took.

**Idle time is not work.** A gap between consecutive rows longer than
`PAUSE_S` is a pause (a run left overnight, a crash before a resume) and is
excluded from the active time; every excluded gap is reported, so nothing is
dropped silently. Within a run the time between one execution's finish and
the next one's start is the harness's own overhead, mostly building the next
repetition's fixture trip.

**The parallel figures are extrapolations, not measurements.** Every run so far
was sequential. A schedule's estimate composes measured serial durations, which
assumes a parallel run is as fast per execution as a serial one. It will not
be: the harness's rate limiter (`VERTEX_CALLS_PER_MINUTE`, shared by agent,
simulator and judge) would throttle concurrent executions, and latency under
contention is a different quantity (`runner.py`, the smoke run's docstring).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

#: A gap between consecutive rows longer than this is a pause, not work.
PAUSE_S = 300.0


def _all(table: str, run_id: str, columns: str) -> pd.DataFrame:
    from src import db

    rows, start = [], 0
    while True:
        page = (db.admin().table(table).select(columns).eq("run_id", run_id)
                .range(start, start + 999).execute().data)
        rows += page
        start += 1000
        if len(page) < 1000:
            return pd.DataFrame(rows)


def _times(frame: pd.DataFrame, *columns: str) -> pd.DataFrame:
    for c in columns:
        frame[c] = pd.to_datetime(frame[c], format="ISO8601")
    return frame


def load_run(run_id: str) -> dict[str, pd.DataFrame]:
    """The run row, its executions and both judge passes, timestamps parsed."""
    from src import db

    run = db.admin().table("study_runs").select("started_at,finished_at").eq("id", run_id).execute().data
    executions = _all("study_case_executions", run_id,
                      "id,case_id,provenance,repetition,started_at,finished_at")
    scores = _all("study_scores", run_id, "execution_id,created_at")
    comparisons = _all("study_comparisons", run_id, "execution_id,created_at")
    return {
        "run": _times(pd.DataFrame(run), "started_at", "finished_at"),
        "executions": _times(executions, "started_at", "finished_at"),
        "scores": _times(scores, "created_at") if len(scores) else scores,
        "comparisons": _times(comparisons, "created_at") if len(comparisons) else comparisons,
    }


def pauses(gaps_s: pd.Series, pause_s: float = PAUSE_S) -> pd.Series:
    """The gaps that count as idle time."""
    return gaps_s[gaps_s > pause_s]


def active_seconds(times: pd.Series, pause_s: float = PAUSE_S) -> tuple[float, float, pd.Series]:
    """(span, active, excluded pauses) of a sequence of timestamps."""
    t = times.sort_values()
    if len(t) < 2:
        return 0.0, 0.0, pd.Series(dtype=float)
    gaps = t.diff().dt.total_seconds().dropna()
    idle = pauses(gaps, pause_s)
    span = (t.iloc[-1] - t.iloc[0]).total_seconds()
    return span, span - idle.sum(), idle


def _execution_phase(ex: pd.DataFrame, pause_s: float) -> tuple[float, float, pd.Series]:
    """(span, active, pauses) of the execution phase. Only the time between one
    execution's finish and the next one's start can be a pause: an execution's
    own duration is always work, however long."""
    ex = ex.sort_values("started_at")
    span = (ex["finished_at"].max() - ex["started_at"].min()).total_seconds()
    between = (ex["started_at"].shift(-1) - ex["finished_at"]).dt.total_seconds().dropna()
    idle = pauses(between, pause_s)
    return span, span - idle.sum(), idle


def phases(run: dict[str, pd.DataFrame], pause_s: float = PAUSE_S) -> pd.DataFrame:
    """Per phase of one run: rows, span, excluded pauses and active minutes."""
    rows = []
    for name, frame in [("execution", run["executions"]),
                        ("point-wise judge", run["scores"]),
                        ("pair-wise judge", run["comparisons"])]:
        n = len(frame)
        if n == 0:
            continue
        if name == "execution":
            span, active, idle = _execution_phase(frame, pause_s)
        else:
            span, active, idle = active_seconds(frame["created_at"], pause_s)
            # n rows have n-1 gaps between them: the first row's own call is
            # not inside the span, so it is credited with the mean gap.
            active += active / max(n - 1, 1)
        rows.append({"phase": name, "rows": n, "span min": span / 60,
                     "pauses": len(idle), "paused min": idle.sum() / 60,
                     "active min": active / 60, "per execution s": active / n})
    return pd.DataFrame(rows).set_index("phase")


def per_execution(run: dict[str, pd.DataFrame], pause_s: float = PAUSE_S) -> pd.DataFrame:
    """One row per execution: its conversation, plus the run's mean overhead
    and mean judging per execution, in seconds."""
    ex = run["executions"].copy()
    ex["conversation s"] = (ex["finished_at"] - ex["started_at"]).dt.total_seconds()
    ph = phases(run, pause_s)
    active_s = ph.loc["execution", "active min"] * 60
    ex["overhead s"] = (active_s - ex["conversation s"].sum()) / len(ex)
    ex["point-wise s"] = ph["per execution s"].get("point-wise judge", 0.0)
    ex["pair-wise s"] = ph["per execution s"].get("pair-wise judge", 0.0)
    ex["total s"] = ex[["conversation s", "overhead s", "point-wise s", "pair-wise s"]].sum(axis=1)
    return ex


def per_case(execs: pd.DataFrame) -> pd.DataFrame:
    """Per test case, two ways of running its repetitions.

    `sequential`: one after another, as the runs did. `parallel`: all at once,
    so the case takes as long as its slowest repetition."""
    fixed = execs["total s"] - execs["conversation s"]
    g = execs.assign(fixed=fixed).groupby(["case_id", "provenance"])
    out = pd.DataFrame({
        "repetitions": g.size(),
        "sequential s": g["total s"].sum(),
        "parallel s": g["conversation s"].max() + g["fixed"].mean(),
    })
    return out.reset_index().set_index("case_id")


def schedules(execs: pd.DataFrame) -> pd.Series:
    """The whole suite under four schedules, in seconds."""
    cases = per_case(execs)
    return pd.Series({
        "everything in sequence (measured)": execs["total s"].sum(),
        "cases in parallel, repetitions in sequence": cases["sequential s"].max(),
        "cases in sequence, repetitions in parallel": cases["parallel s"].sum(),
        "everything in parallel": execs["total s"].max(),
    })


def say(seconds: float) -> str:
    """A duration as prose would round it: seconds under a minute and a half,
    half minutes under an hour, ten minutes beyond."""
    if seconds < 90:
        return f"about {int(5 * round(seconds / 5))} seconds"
    if seconds < 3600:
        m = round(seconds / 30) / 2
        return f"about {m:g} minute{'s' if m != 1 else ''}"
    h, rest = divmod(round(seconds / 600) * 10, 60)
    return f"about {h} h {rest} min" if rest else f"about {h} h"


def summary(execs: pd.DataFrame, by: Optional[str] = "provenance") -> pd.DataFrame:
    """Mean seconds per execution, split by `by`."""
    cols = ["conversation s", "overhead s", "point-wise s", "pair-wise s", "total s"]
    frame = execs.groupby(by)[cols].mean() if by else execs[cols].mean().to_frame("all").T
    return frame.round(1)
