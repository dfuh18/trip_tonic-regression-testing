"""Stage 3.1 → 3.2: adopt a baseline, compare a run against it, pass rates.

Three steps, each the input of the next:

1. **Adoption (B10).** One execution per case is the case's baseline: the
   reply later runs are compared against. ``propose_baseline`` suggests one per
   case — the highest judge score among structurally clean executions — and
   the author adopts by writing the file. The adopted baseline is
   ``cases/baseline.json`` (``case_id → execution_id, suggestion_id``, B10).
   Anything else is a **test baseline**: same shape, written under ``runs/``,
   which git ignores, so a rehearsal can never be mistaken for the adopted one.
2. **Comparison (B11, D23).** Every execution of the candidate run is judged
   pair-wise against its case's baseline reply, in both orderings, and holds
   only when both say "at least as good". The first reply of each, against
   ``case.opening_turn`` (D34). Verdicts are cached to ``runs/comparisons/``
   so a lost kernel resumes instead of re-judging — the loss D71 fixed for
   point-wise scores. Persisting them to the database is Q33.
3. **Pass rates (D23).** An execution passes when its structural verdict is
   ``none`` **and** the pair-wise verdict holds; a structural ``detected``
   fails it regardless of the judge. A seed case passes only when every
   repetition passes; an expanded case at ≥ 75 %.

A comparison that could not be made (the judge failed after its retries) is a
missing measurement, not a failure of the agent, and a case with one is
``incomplete`` rather than passed or failed — the same line D70 draws for
point-wise scores.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

from src.cases import CASES_DIR, load_cases

ADOPTED_BASELINE = CASES_DIR / "baseline.json"
RUNS_DIR = CASES_DIR.parent / "runs"
COMPARISON_CACHE = RUNS_DIR / "comparisons"

#: D23. A seed is minimum functionality, so one failure in eight is a failure.
SEED_PASS_RATE = 1.0
EXPANDED_PASS_RATE = 0.75


def _pd():
    import pandas as pd

    return pd


# --- 1. adoption -------------------------------------------------------------


def _executions(run_ids: list[str]) -> list[dict]:
    from src.execution import latest_attempts
    from src.survey import _rows

    rows: list[dict] = []
    for run_id in run_ids:
        latest, _ = latest_attempts(_rows("study_case_executions", "run_id", run_id))
        rows += latest
    return rows


def propose_baseline(run_ids: list[str]) -> "DataFrame":
    """Per case, the execution the author would most likely adopt.

    Ranked by structural verdict (``none`` first — a baseline that failed its
    own checks is not a reference anyone should be compared against), then by
    the latest judge score, then by repetition. A proposal, not an adoption.
    """
    from src.scoring import scores_for

    pd = _pd()
    scores = {}
    for run_id in run_ids:
        for s in scores_for(run_id):
            scores.setdefault(s["execution_id"], s)  # newest judge version first
    rows = []
    for ex in _executions(run_ids):
        s = scores.get(ex["id"], {})
        rows.append({
            "case": ex["case_id"], "run_id": ex["run_id"], "execution_id": ex["id"],
            "suggestion_id": (ex.get("suggestion_ids") or [None])[0],
            "repetition": ex.get("repetition"), "structural": ex.get("structural_outcome"),
            "score": s.get("score"), "failed": bool(ex.get("error")),
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["_clean"] = (frame["structural"] == "none") & ~frame["failed"]
    frame = frame.sort_values(["case", "_clean", "score", "repetition"],
                              ascending=[True, False, False, True], na_position="last")
    best = frame.groupby("case", sort=True).head(1).drop(columns="_clean")
    return best.set_index("case")


def write_baseline(proposal: "DataFrame", path: Path, *, by: str, note: str) -> dict:
    """Write a baseline file from a proposal (or an edited one).

    ``cases/baseline.json`` is the author's adoption and is written only on
    their instruction; a test baseline goes under ``runs/``. The file names
    the runs it was drawn from, so a reader can tell a one-run baseline from
    a rehearsal assembled across runs.
    """
    import datetime

    data = {
        "_note": note,
        "adopted_by": by,
        "on": datetime.date.today().isoformat(),
        "runs": sorted(set(proposal["run_id"])),
        "cases": {
            case: {"execution_id": row["execution_id"], "suggestion_id": row["suggestion_id"],
                   "run_id": row["run_id"]}
            for case, row in proposal.iterrows()
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def load_baseline(path: Path = ADOPTED_BASELINE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_test_baseline(path: Path) -> bool:
    return Path(path).resolve() != ADOPTED_BASELINE.resolve()


def baseline_gaps(baseline: dict) -> list[str]:
    """Cases in the suite with no baseline entry. A case without one cannot be
    compared, and would silently drop out of the pass rates."""
    return sorted({c.case_id for c in load_cases()} - set(baseline.get("cases", {})))


# --- 2. comparison -----------------------------------------------------------


@dataclass
class Comparison:
    case_id: str
    repetition: int
    execution_id: str
    baseline_execution_id: str
    structural: Optional[str]
    at_least_as_good: Optional[bool]
    #: The judge's two answers: "A", "B" or "tie", candidate shown as B then A.
    orderings: list[str]
    rationale: str
    error: Optional[str] = None

    @property
    def passed(self) -> Optional[bool]:
        """D23: structural ``detected`` fails outright; otherwise the judge
        decides. ``None`` when nothing could decide."""
        if self.structural == "detected":
            return False
        if self.structural != "none" or self.error or self.at_least_as_good is None:
            return None  # not yet checked, or not judged: nothing decided
        return self.structural == "none" and self.at_least_as_good


def _cache_path(candidate_run_id: str, baseline: dict) -> Path:
    import hashlib

    key = hashlib.sha256(json.dumps(baseline.get("cases", {}), sort_keys=True).encode()).hexdigest()[:10]
    return COMPARISON_CACHE / f"{candidate_run_id}__{key}.json"


def compare_run(
    candidate_run_id: str,
    baseline: dict,
    *,
    llm=None,
    log: Callable[[str], None] = print,
) -> list[Comparison]:
    """Judge every execution of a run against its case's baseline reply."""
    from src.execution import latest_attempts
    from src.judge import compare_pairwise
    from src.llm import judge_llm
    from src.scoring import MAX_JUDGE_ATTEMPTS, _judge_backoff_s, _judge_worth_retrying, first_reply
    from src.survey import _rows

    cases = {c.case_id: c for c in load_cases()}
    cache = _cache_path(candidate_run_id, baseline)
    done: dict[str, dict] = {}
    if cache.exists():
        done = {r["execution_id"]: r for r in json.loads(cache.read_text(encoding="utf-8"))}

    by_id = {}
    base_ids = [e["execution_id"] for e in baseline.get("cases", {}).values()]
    for run_id in baseline.get("runs", []):
        for row in _rows("study_case_executions", "run_id", run_id):
            if row["id"] in base_ids:
                by_id[row["id"]] = row

    rows, _ = latest_attempts(_rows("study_case_executions", "run_id", candidate_run_id))
    rows.sort(key=lambda r: (r["case_id"], r["repetition"]))
    out: list[Comparison] = []
    llm = llm or judge_llm()
    for row in rows:
        if row["id"] in done:
            out.append(Comparison(**done[row["id"]]))
            continue
        case = cases.get(row["case_id"])
        entry = baseline.get("cases", {}).get(row["case_id"])
        base = dict(case_id=row["case_id"], repetition=row["repetition"], execution_id=row["id"],
                    baseline_execution_id=(entry or {}).get("execution_id", ""),
                    structural=row.get("structural_outcome"), at_least_as_good=None,
                    orderings=[], rationale="")
        if case is None or entry is None or entry["execution_id"] not in by_id:
            out.append(Comparison(**base, error="no baseline for this case"))
            continue
        _, candidate = first_reply(row)
        _, reference = first_reply(by_id[entry["execution_id"]])
        if not candidate.strip():
            # No reply is the agent's failure, not a missing measurement.
            out.append(Comparison(**{**base, "at_least_as_good": False,
                                     "rationale": "the candidate execution produced no reply"}))
        else:
            refs = [r.text() for r in case.references]
            for attempt in range(1, MAX_JUDGE_ATTEMPTS + 1):
                try:
                    result = compare_pairwise(case, case.opening_turn, reference, candidate, refs, llm=llm)
                    out.append(Comparison(**{
                        **base, "at_least_as_good": result.at_least_as_good,
                        "orderings": [o.better for o in result.orderings],
                        "rationale": " | ".join(o.rationale for o in result.orderings)[:600],
                    }))
                    break
                except Exception as exc:
                    if attempt == MAX_JUDGE_ATTEMPTS or not _judge_worth_retrying(exc):
                        out.append(Comparison(**base, error=f"judge: {type(exc).__name__}: {exc}"))
                        break
                    time.sleep(_judge_backoff_s(attempt))
        c = out[-1]
        log(f"  {'pass' if c.passed else ('----' if c.passed is None else 'FAIL'):>4s}  "
            f"{c.case_id} rep {c.repetition}  {c.orderings or c.error or ''}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps([asdict(x) for x in out if not x.error], indent=1), encoding="utf-8")
    return out


def comparison_frame(comparisons: list[Comparison]) -> "DataFrame":
    pd = _pd()
    return pd.DataFrame([{**asdict(c), "passed": c.passed} for c in comparisons])


# --- 3. pass rates ---------------------------------------------------------------


def pass_rates(comparisons: list[Comparison]) -> "DataFrame":
    """Per case: repetitions, passes, rate, threshold and the D23 verdict."""
    pd = _pd()
    cases = {c.case_id: c for c in load_cases()}
    rows = []
    for case_id in sorted({c.case_id for c in comparisons}):
        mine = [c for c in comparisons if c.case_id == case_id]
        decided = [c for c in mine if c.passed is not None]
        passes = sum(1 for c in decided if c.passed)
        seed = cases[case_id].provenance == "seeded" if case_id in cases else False
        threshold = SEED_PASS_RATE if seed else EXPANDED_PASS_RATE
        rate = passes / len(mine) if mine else float("nan")
        if len(decided) < len(mine):
            verdict = "incomplete"
        else:
            verdict = "pass" if rate >= threshold else "fail"
        rows.append({
            "case": case_id, "provenance": "seeded" if seed else "metamorphic",
            "executions": len(mine), "passed": passes,
            "structural fails": sum(1 for c in mine if c.structural == "detected"),
            "judge says worse": sum(1 for c in mine if c.structural != "detected" and c.at_least_as_good is False),
            "not compared": len(mine) - len(decided),
            "pass rate": rate, "threshold": threshold, "verdict": verdict,
        })
    return pd.DataFrame(rows).set_index("case")
