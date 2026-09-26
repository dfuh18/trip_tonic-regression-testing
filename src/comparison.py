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
   ``case.opening_turn`` (D34). Every verdict is written to
   ``study_comparisons`` as it is made (Q33), which is also how a lost kernel
   resumes instead of re-judging — the loss D71 fixed for point-wise scores.
3. **Pass rates (D23, amended by D88).** An execution passes when its
   structural verdict is ``none`` **and** the judge does not consistently
   prefer the baseline; a structural ``detected`` fails it regardless of the
   judge. A pair whose two orderings contradict each other is a **position
   draw**: it passes, and is counted and shown as one (D88). A seed case passes
   only when every repetition passes; an expanded case at ≥ 75 %.

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
    """The baseline file, tagged with its kind: ``adopted`` for
    ``cases/baseline.json``, ``test`` for anything else. The kind travels into
    every verdict taken against it, so a rehearsal cannot pass as stage 3.2."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["_kind"] = "test" if is_test_baseline(path) else "adopted"
    return data


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
        """The execution verdict under the rule in force (``RULE``, D88).
        Structural ``detected`` fails outright; ``None`` when nothing decided."""
        return passed_under(self, RULE)

    @property
    def position_draw(self) -> bool:
        """Passes only because a contradiction between the two orderings is
        read as a draw: D23's strict reading would have failed it (D88)."""
        return bool(self.passed) and passed_under(self, "strict") is False


def baseline_key(baseline: dict) -> str:
    """A hash of the baseline's entries: which execution stands for which case."""
    import hashlib

    return hashlib.sha256(json.dumps(baseline.get("cases", {}), sort_keys=True).encode()).hexdigest()[:12]


def _judge_identity() -> tuple[str, str]:
    from src.config import settings
    from src.llm import load_prompt

    return settings.JUDGE_MODEL, load_prompt("judge_pairwise_v2").version


def pg_text(value):
    """Text Postgres can store. A judge reply once carried a NUL (\u0000), which a
    `text` column refuses outright (22P05) — and the refusal crashed a whole
    B11 comparison pass at 149 of 176. A NUL is never content, so it is dropped."""
    return value.replace("\x00", "") if isinstance(value, str) else value


def _record(run_id: str, row: dict, c: Comparison, baseline: dict) -> dict:
    model, version = _judge_identity()
    orderings = list(c.orderings) + [None, None]
    return {
        "run_id": run_id, "execution_id": c.execution_id,
        "baseline_execution_id": c.baseline_execution_id,
        "case_id": c.case_id, "repetition": c.repetition, "attempt": row.get("attempt") or 1,
        "baseline_kind": baseline.get("_kind", "test"), "baseline_key": baseline_key(baseline),
        "judge_model": model, "judge_prompt_version": version,
        "structural_outcome": c.structural,
        "ordering_candidate_b": orderings[0], "ordering_candidate_a": orderings[1],
        "at_least_as_good": c.at_least_as_good, "rationale": pg_text(c.rationale), "error": pg_text(c.error),
    }


def _persist(run_id: str, row: dict, c: Comparison, baseline: dict) -> None:
    """Write one verdict to ``study_comparisons`` (Q33). Upsert on the
    judge-version key, so a retry that finally obtains a verdict replaces the
    refusal recorded for the same comparison, and nothing else is overwritten."""
    from src import db

    db.admin().table("study_comparisons").upsert(
        _record(run_id, row, c, baseline),
        on_conflict="execution_id,baseline_execution_id,judge_model,judge_prompt_version",
    ).execute()


def stored_comparisons(run_id: str, baseline: dict) -> dict[str, dict]:
    """Verdicts already in the database for this run, this baseline and this
    judge version, keyed by candidate execution."""
    from src import db

    model, version = _judge_identity()
    rows = (db.admin().table("study_comparisons").select("*")
            .eq("run_id", run_id).eq("baseline_key", baseline_key(baseline))
            .eq("judge_model", model).eq("judge_prompt_version", version).execute().data)
    return {r["execution_id"]: r for r in rows}


def _from_row(r: dict) -> Comparison:
    return Comparison(
        case_id=r["case_id"], repetition=r["repetition"], execution_id=r["execution_id"],
        baseline_execution_id=r["baseline_execution_id"], structural=r.get("structural_outcome"),
        at_least_as_good=r.get("at_least_as_good"),
        orderings=[o for o in (r.get("ordering_candidate_b"), r.get("ordering_candidate_a")) if o],
        rationale=r.get("rationale") or "", error=r.get("error"),
    )


def compare_run(
    candidate_run_id: str,
    baseline: dict,
    *,
    llm=None,
    log: Callable[[str], None] = print,
) -> list[Comparison]:
    """Judge every execution of a run against its case's baseline reply.

    Resumes from ``study_comparisons``: a candidate execution that already has
    a decided verdict for this baseline and judge version is read, not
    re-judged. Its structural verdict is taken from the execution as it is now,
    since the stored snapshot is only what the comparison saw.
    """
    from src.execution import latest_attempts
    from src.judge import compare_pairwise
    from src.llm import judge_llm
    from src.scoring import MAX_JUDGE_ATTEMPTS, _judge_backoff_s, _judge_worth_retrying, execution_day, first_reply
    from src.survey import _rows

    cases = {c.case_id: c for c in load_cases()}
    done = {k: v for k, v in stored_comparisons(candidate_run_id, baseline).items() if not v.get("error")}

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
            c = _from_row(done[row["id"]])
            c.structural = row.get("structural_outcome")
            out.append(c)
            continue
        case = cases.get(row["case_id"])
        entry = baseline.get("cases", {}).get(row["case_id"])
        base = dict(case_id=row["case_id"], repetition=row["repetition"], execution_id=row["id"],
                    baseline_execution_id=(entry or {}).get("execution_id", ""),
                    structural=row.get("structural_outcome"), at_least_as_good=None,
                    orderings=[], rationale="")
        if case is None or entry is None or entry["execution_id"] not in by_id:
            # Not a judge result: nothing to persist, and no baseline row to key it to.
            out.append(Comparison(**base, error="no baseline for this case"))
            continue
        _, candidate = first_reply(row)
        _, reference = first_reply(by_id[entry["execution_id"]])
        if not candidate.strip():
            # No reply is the agent's failure; recorded as the baseline winning both orderings.
            out.append(Comparison(**{**base, "at_least_as_good": False, "orderings": ["A", "B"],
                                     "rationale": "the candidate execution produced no reply"}))
        else:
            refs = [r.text() for r in case.references]
            for attempt in range(1, MAX_JUDGE_ATTEMPTS + 1):
                try:
                    result = compare_pairwise(
                        case, case.opening_turn, reference, candidate, refs, llm=llm,
                        baseline_day=execution_day(by_id[entry["execution_id"]]),
                        candidate_day=execution_day(row),
                    )
                    out.append(Comparison(**{
                        **base, "at_least_as_good": result.at_least_as_good,
                        "orderings": [o.better for o in result.orderings],
                        "rationale": " | ".join(o.rationale for o in result.orderings)[:1200],
                    }))
                    break
                except Exception as exc:
                    if attempt == MAX_JUDGE_ATTEMPTS or not _judge_worth_retrying(exc):
                        out.append(Comparison(**base, error=f"judge: {type(exc).__name__}: {exc}"))
                        break
                    time.sleep(_judge_backoff_s(attempt))
        c = out[-1]
        _persist(candidate_run_id, row, c, baseline)
        mark = "DRAW" if c.position_draw else ("pass" if c.passed else ("----" if c.passed is None else "FAIL"))
        log(f"  {mark:>4s}  "
            f"{c.case_id} rep {c.repetition}  {c.orderings or c.error or ''}")
    return out


def comparison_frame(comparisons: list[Comparison]) -> "DataFrame":
    pd = _pd()
    return pd.DataFrame([{**asdict(c), "passed": c.passed, "position draw": c.position_draw}
                         for c in comparisons])


# --- 3. pass rates ---------------------------------------------------------------


def pass_rates(comparisons: list[Comparison], reading: Optional[str] = None) -> "DataFrame":
    """Per case: repetitions, passes, rate, threshold and the verdict.

    ``reading`` is the rule in force (``RULE``) unless given. ``position
    draws`` counts the executions that pass only because their orderings
    contradicted each other, and ``pass rate (strict)`` is D23's reading beside
    it, so a pass bought by a position draw is never silent (D88)."""
    pd = _pd()
    reading = reading or RULE
    cases = {c.case_id: c for c in load_cases()}
    rows = []
    for case_id in sorted({c.case_id for c in comparisons}):
        mine = [c for c in comparisons if c.case_id == case_id]
        verdicts = [passed_under(c, reading) for c in mine]
        strict = [passed_under(c, "strict") for c in mine]
        decided = [v for v in verdicts if v is not None]
        passes = sum(1 for v in decided if v)
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
            "judge prefers baseline": sum(1 for c, v in zip(mine, verdicts)
                                          if v is False and c.structural != "detected"),
            "position draws": sum(1 for v, st in zip(verdicts, strict) if v and st is False),
            "not compared": len(mine) - len(decided),
            "pass rate": rate,
            "pass rate (strict)": sum(1 for v in strict if v) / len(mine) if mine else float("nan"),
            "threshold": threshold, "verdict": verdict,
        })
    return pd.DataFrame(rows).set_index("case")


# --- 4. position bias (Q34) ----------------------------------------------------
#
# D23 asks the judge twice with the order swapped. That does not remove
# position bias; it EXPOSES it, as answers that contradict each other. What
# a contradictory pair then counts as is a separate rule, and D23's is strict:
# the candidate passes only if both orderings hold. These functions name each
# pattern and recompute verdicts under the alternatives, without changing D23.

#: Each answer from the candidate's side: +1 it won, 0 tie, -1 the baseline won.
#: First ordering: candidate shown as B. Second: candidate shown as A.
_FIRST = {"B": 1, "tie": 0, "A": -1}
_SECOND = {"A": 1, "tie": 0, "B": -1}

PATTERNS = {
    (1, 1): "consistent: candidate better",
    (0, 0): "consistent: tie",
    (-1, -1): "consistent: baseline better",
    (1, 0): "leans candidate (one ordering)",
    (0, 1): "leans candidate (one ordering)",
    (-1, 0): "leans baseline (one ordering)",
    (0, -1): "leans baseline (one ordering)",
    (-1, 1): "same slot both times: first (A)",
    (1, -1): "same slot both times: second (B)",
}

#: Patterns that disagree with themselves: the judge could not rank the two
#: replies the same way in both orders.
INCONSISTENT = {
    "leans candidate (one ordering)", "leans baseline (one ordering)",
    "same slot both times: first (A)", "same slot both times: second (B)",
}

#: The reading in force (D88, amending D23): a fail that exists only because
#: the two orderings contradict each other is a draw, and passes. Only a
#: consistent preference for the baseline fails on the judge.
RULE = "any_draw"

#: How a pair of answers becomes an execution verdict.
#: ``strict``   D23: both orderings must hold (candidate at least as good).
#: ``slot_draw`` a same-slot pick is a draw, so it holds; leans still count.
#: ``any_draw`` every inconsistent pair is a draw; only a consistent
#:             preference for the baseline fails.
READINGS = ("strict", "slot_draw", "any_draw")


def pattern(orderings: list[str]) -> Optional[str]:
    if len(orderings) != 2 or orderings[0] not in _FIRST or orderings[1] not in _SECOND:
        return None
    return PATTERNS[(_FIRST[orderings[0]], _SECOND[orderings[1]])]


def holds(orderings: list[str], reading: str = "strict") -> Optional[bool]:
    """Whether the judge's pair of answers counts as "at least as good"."""
    p = pattern(orderings)
    if p is None:
        return None
    a, b = _FIRST[orderings[0]], _SECOND[orderings[1]]
    if reading == "strict":
        return a >= 0 and b >= 0
    if reading == "slot_draw":
        return (a >= 0 and b >= 0) or p.startswith("same slot")
    if reading == "any_draw":
        return p != "consistent: baseline better"
    raise ValueError(f"unknown reading {reading!r}")


def passed_under(c: Comparison, reading: str) -> Optional[bool]:
    """``Comparison.passed`` with the judge's pair read under ``reading``.
    Under ``strict`` it is ``passed`` exactly. A structural ``detected`` fails
    under every reading, because it does not come from the judge."""
    if c.structural == "detected":
        return False
    if c.structural != "none" or c.error:
        return None
    if not c.orderings:  # recorded without answers, e.g. no reply at all
        return c.at_least_as_good
    return holds(c.orderings, reading)


def verdicts_under(comparisons: list[Comparison], reading: str) -> "DataFrame":
    """``pass_rates`` with every execution read under ``reading``."""
    return pass_rates(comparisons, reading)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Share ``k/n`` with a 95 % Wilson interval: (p, low, high)."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)
