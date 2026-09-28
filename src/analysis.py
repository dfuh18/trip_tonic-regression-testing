"""The participant-round analysis (C02, §4.3): the propositions, tested.

Used by ``notebooks/study/06_analysis``. Like ``src.pilot``, every function
past the loaders takes plain rows or plain values, so the statistics are
testable offline (``tests/test_analysis.py``) and the notebook stays a reader.

What each proposition is computed from, and the rulings that fix it:

* **P1 — coverage.** A participant *interaction* is one request: a Tonic run
  split by ``shapes.segment_with`` with the slash signal and without reference
  (D100), over ``shapes7`` labels (D99). Its signature is D24's
  (``src.signature``) over the request's turns taken together. It is covered
  when a simulated execution has the same signature. Coverage is also reported
  per turn, side by side, and no claim rests on a request count (D100).
* **P2 — execution-failure rank agreement.** An execution failure is an agent
  turn whose ``error_code`` is set: the same definition in both rounds, read
  from the same column. Simulated turns are read under D53: the latest attempt
  of each execution only; superseded attempts are the platform's failure rate
  and are counted separately. Per-class rates carry 95 % Wilson intervals. The
  rank agreement is Kendall's τ over the request types both rounds observed,
  reported **descriptively**, with no p-value (D101): at four classes no rank
  test can reach significance.
* **P3 — judge vs feedback.** One-sided Mann–Whitney U (positive > negative)
  and the rank-biserial correlation with a percentile-bootstrap interval,
  computed separately for thumbs and for accept/reject, never pooled (D101).
* **Table 12** is reported as two axes side by side (D102, resolving Q27 as A).

* **UMUX-LITE** goes through the UMUX-LITE → SUS conversion of Lewis, Utesch
  & Maher (2013), an estimate of the SUS score, and is graded on the
  Sauro–Lewis curved grading scale (Sauro & Lewis, 2016).

The definitions of an execution failure and of a P1 interaction are recorded
with D101.

Nothing here prints, and nothing returns a participant's words or an id.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

from src import shapes
from src.comparison import wilson
from src.signature import SIGNATURE_RULE_VERSION, signature

Row = dict[str, Any]

ANALYSIS_VERSION = "1"

#: D100: the slash command starts a request; reference is not used.
SEGMENT_USE_INTENT = True
SEGMENT_USE_REFERENCE = False

#: Columns read from ``study_suggestions`` for simulated turns.
_TURN_COLUMNS = (
    "id, run_id, session_id, turn_index, error_code, retry_count, request_type, "
    "tool_call_trace, agent_intent, reply_message_id, occurred_at"
)


# --- loading -----------------------------------------------------------------


def simulated_executions(client: Any, run_ids: Sequence[str]) -> tuple[list[list[Row]], int]:
    """Each simulated execution's turns, in order, and the number of superseded
    attempts left out (D53). Only the latest attempt of an execution counts."""
    from src.execution import latest_attempts

    executions: list[Row] = []
    superseded = 0
    for run_id in run_ids:
        rows = client.table("study_case_executions").select("*").eq("run_id", run_id).execute().data
        latest, dropped = latest_attempts(rows)
        executions += latest
        superseded += dropped
    ids = [i for ex in executions for i in (ex.get("suggestion_ids") or [])]
    turns: dict[str, Row] = {}
    for start in range(0, len(ids), 100):
        chunk = ids[start : start + 100]
        for t in client.table("study_suggestions").select(_TURN_COLUMNS).in_("id", chunk).execute().data:
            turns[t["id"]] = t
    out = []
    for ex in executions:
        own = [turns[i] for i in ex.get("suggestion_ids") or [] if i in turns]
        if own:
            out.append(sorted(own, key=lambda t: t.get("turn_index") or 0))
    return out, superseded


def runs_of(turns: Iterable[Row]) -> list[list[Row]]:
    """Participant turns grouped by Tonic run, each run in turn order."""
    by_run: dict[Any, list[Row]] = defaultdict(list)
    for t in turns:
        by_run[(t.get("session_id"), t.get("run_id"))].append(t)
    return [sorted(v, key=lambda t: t.get("turn_index") or 0) for v in by_run.values()]


# --- shared helpers ----------------------------------------------------------


def _trace(turn: Row) -> list[Mapping[str, Any]]:
    return [e for e in (turn.get("tool_call_trace") or []) if isinstance(e, Mapping)]


def _tool_entries(turn: Row) -> list[Mapping[str, Any]]:
    return [e for e in _trace(turn) if e.get("kind", "tool") == "tool" and e.get("tool")]


def turn_shape(turn: Row) -> str:
    return shapes.shapes7(shapes.tools_of(_trace(turn)))


def failed(turn: Row) -> bool:
    return bool(turn.get("error_code"))


# --- P1: coverage ------------------------------------------------------------


def segments(run: Sequence[Row], reply_place_ids: Mapping[str, Iterable[str]] | None = None) -> list[list[Row]]:
    """One participant run split into requests under D100."""
    refs = reply_place_ids or {}
    signals = [
        shapes.signals_of(_trace(t), refs.get(t.get("reply_message_id"), ()), t.get("agent_intent"), shapes.shapes7)
        for t in run
    ]
    cut = shapes.segment_with(signals, use_intent=SEGMENT_USE_INTENT, use_reference=SEGMENT_USE_REFERENCE)
    return [[run[i] for i in seg] for seg in cut]


def joined_trace(turns: Sequence[Row]) -> list[dict]:
    """The tool entries of several turns as one trace, in turn order then
    ``seq`` order, renumbered so ``signature`` keeps that order."""
    out: list[dict] = []
    for turn in turns:
        for entry in sorted(_tool_entries(turn), key=lambda e: e.get("seq", 0)):
            out.append({**entry, "seq": len(out)})
    return out


def interaction_signature(turns: Sequence[Row]) -> tuple:
    """D24's signature of one interaction (a request or an execution).

    ``request_type`` is D09's precedence over every tool the interaction
    called, so a request whose search and draft fell in two turns is typed as
    the app types the same tools in one turn."""
    trace = joined_trace(turns)
    request_type = shapes.d09([str(e["tool"]) for e in trace])
    return signature(trace, len(turns), request_type)


def interaction_shape(turns: Sequence[Row]) -> str:
    """The ``shapes7`` label of an interaction, over all its turns' tools."""
    return shapes.shapes7([str(e["tool"]) for e in joined_trace(turns)])


@dataclass(frozen=True)
class CoverageRow:
    unit: str  # "request" | "turn"
    shape: str
    request_type: str
    covered: bool


def coverage(
    participant: Sequence[Sequence[Row]], simulated: Sequence[Sequence[Row]], unit: str
) -> list[CoverageRow]:
    """Match each participant unit against the simulated units of the same kind.

    ``unit="request"``: participant requests against simulated executions.
    ``unit="turn"``: every participant turn against every simulated turn,
    each as a one-turn interaction.
    """
    if unit == "turn":
        participant = [[t] for unit_turns in participant for t in unit_turns]
        simulated = [[t] for ex in simulated for t in ex]
    suite = {interaction_signature(ex) for ex in simulated}
    rows = []
    for turns in participant:
        sig = interaction_signature(turns)
        rows.append(CoverageRow(unit=unit, shape=interaction_shape(turns), request_type=sig[0], covered=sig in suite))
    return rows


#: The five parts of a D24 signature, in ``signature``'s order.
SIGNATURE_PARTS = ("request type", "tool sequence", "calls per tool", "turns", "parameters")


def nearest_miss(sig: tuple, suite: Iterable[tuple]) -> list[str]:
    """For an uncovered signature, the parts in which the closest suite
    signature differs. Closest = fewest differing parts; ties are broken by
    the suite signature's sort order, so the answer is deterministic.

    A diagnostic, not a matching rule: it explains *why* a request is
    uncovered (one bucket off vs. a shape the suite never produced) and
    changes nothing about whether it is."""
    candidates = sorted(suite, key=repr)
    if not candidates:
        return list(SIGNATURE_PARTS)
    best = min(candidates, key=lambda s: sum(a != b for a, b in zip(s, sig)))
    return [name for name, a, b in zip(SIGNATURE_PARTS, best, sig) if a != b]


def uncovered_diagnosis(
    participant: Sequence[Sequence[Row]], simulated: Sequence[Sequence[Row]]
) -> list[dict[str, Any]]:
    """One row per uncovered participant request: its shape, its bucketed
    turns, its collapsed tool sequence, and where the nearest suite signature
    differs. Tool names and labels only; no request text."""
    suite = {interaction_signature(ex) for ex in simulated}
    rows = []
    for turns in participant:
        sig = interaction_signature(turns)
        if sig in suite:
            continue
        diff = nearest_miss(sig, suite)
        rows.append({"shape": interaction_shape(turns), "turns": sig[3], "tool sequence": " > ".join(sig[1]) or "-",
                     "differs in": ", ".join(diff), "parts off": len(diff)})
    return sorted(rows, key=lambda r: (r["parts off"], r["shape"]))


def coverage_summary(rows: Sequence[CoverageRow]) -> dict[str, Any]:
    n, k = len(rows), sum(r.covered for r in rows)
    p, lo, hi = wilson(k, n) if n else (float("nan"),) * 3
    return {"n": n, "covered": k, "share": p, "ci_low": lo, "ci_high": hi,
            "signature_rule": SIGNATURE_RULE_VERSION}


def uncovered_by(rows: Sequence[CoverageRow], key: str = "shape") -> Counter:
    """Where uncovered units concentrate (§4.3 (3))."""
    return Counter(getattr(r, key) for r in rows if not r.covered)


# --- P2: execution failures --------------------------------------------------


@dataclass(frozen=True)
class Rate:
    group: str
    n: int
    failures: int
    rate: float
    ci_low: float
    ci_high: float


def failure_rates(turns: Iterable[Row], key: str = "request_type") -> list[Rate]:
    """Execution-failure rate per class, with 95 % Wilson intervals."""
    n: Counter = Counter()
    k: Counter = Counter()
    for t in turns:
        group = (turn_shape(t) if key == "shape" else t.get(key)) or "(none)"
        n[group] += 1
        k[group] += failed(t)
    out = []
    for group in sorted(n):
        p, lo, hi = wilson(k[group], n[group])
        out.append(Rate(group, n[group], k[group], p, lo, hi))
    return out


def overall_rate(turns: Sequence[Row]) -> Rate:
    turns = list(turns)
    k = sum(failed(t) for t in turns)
    p, lo, hi = wilson(k, len(turns)) if turns else (float("nan"),) * 3
    return Rate("all", len(turns), k, p, lo, hi)


def failure_types(turns: Iterable[Row]) -> Counter:
    return Counter(t["error_code"] for t in turns if t.get("error_code"))


def rank_agreement(simulated: Sequence[Rate], participant: Sequence[Rate]) -> dict[str, Any]:
    """Kendall's τ-b between the two rounds' failure rates, over the classes
    both rounds observed. Descriptive (D101): no p-value is returned.

    τ is undefined when either round's rates are all equal (a round with no
    failures at all is the common case), and says so rather than returning 0.
    """
    from scipy.stats import kendalltau

    sim = {r.group: r.rate for r in simulated if r.n}
    part = {r.group: r.rate for r in participant if r.n}
    classes = sorted(set(sim) & set(part))
    a, b = [sim[c] for c in classes], [part[c] for c in classes]
    out: dict[str, Any] = {"classes": classes, "n_classes": len(classes), "tau_b": None, "note": ""}
    if len(classes) < 2:
        out["note"] = "fewer than two classes observed in both rounds"
    elif len(set(a)) < 2 or len(set(b)) < 2:
        out["note"] = "undefined: one round has the same rate in every class"
    else:
        out["tau_b"] = float(kendalltau(a, b).statistic)
    return out


def tool_errors(turns: Iterable[Row]) -> list[dict[str, Any]]:
    """Per tool: calls, calls that came back an error, and how many turns still
    completed without an ``error_code`` after one did (C02 (7))."""
    calls: Counter = Counter()
    errs: Counter = Counter()
    recovered: Counter = Counter()
    for t in turns:
        errored_here = set()
        for e in _tool_entries(t):
            calls[e["tool"]] += 1
            if e.get("result_error"):
                errs[e["tool"]] += 1
                errored_here.add(e["tool"])
        if not failed(t):
            for tool in errored_here:
                recovered[tool] += 1
    return [{"tool": tool, "calls": calls[tool], "errored calls": errs[tool],
             "turns completed after an error": recovered[tool]} for tool in sorted(calls)]


def recovered_error_rates(turns: Iterable[Row], key: str = "tool") -> list[Rate]:
    """Recovered tool errors: tool calls that came back an error inside a turn
    that still completed (no ``error_code``). Q36 option C, a secondary
    reading beside P2, not an execution failure by §4.2.3's definition.

    ``key="tool"``: per tool, n = that tool's calls in completed turns.
    ``key="request_type"``: per request type, n = completed turns of that type,
    counted when at least one of their tool calls errored."""
    n: Counter = Counter()
    k: Counter = Counter()
    for t in turns:
        if failed(t):
            continue
        entries = _tool_entries(t)
        if key == "tool":
            for e in entries:
                n[e["tool"]] += 1
                k[e["tool"]] += bool(e.get("result_error"))
        else:
            group = t.get(key) or "(none)"
            n[group] += 1
            k[group] += any(e.get("result_error") for e in entries)
    out = []
    for group in sorted(n):
        p, lo, hi = wilson(k[group], n[group])
        out.append(Rate(group, n[group], k[group], p, lo, hi))
    return out


# --- Table 12 as two axes (D102) ----------------------------------------------


def participant_axes(turns: Iterable[Row], feedback: Iterable[Row]) -> dict[str, Counter]:
    turns = list(turns)
    return {
        "user_action": Counter(t.get("user_action") or "(not yet)" for t in turns),
        "thumbs": Counter(f.get("value") for f in feedback if f.get("value")),
    }


# --- P3: judge score vs feedback ---------------------------------------------


def feedback_groups(
    turns: Iterable[Row], feedback: Iterable[Row], scores: Mapping[str, float]
) -> dict[str, dict[str, list[float]]]:
    """Judge scores split by each feedback signal, never pooled (§4.2.3).

    ``scores`` maps a turn id to its judge score. Thumbs join through the reply
    message; accept/reject is the turn's ``user_action``. ``ignored`` and
    unset actions belong to neither group."""
    turns = list(turns)
    by_reply = {t.get("reply_message_id"): t["id"] for t in turns if t.get("reply_message_id")}
    thumbs: dict[str, list[float]] = {"positive": [], "negative": []}
    for f in feedback:
        tid = by_reply.get(f.get("chat_message_id"))
        if tid in scores and f.get("value") in ("up", "down"):
            thumbs["positive" if f["value"] == "up" else "negative"].append(float(scores[tid]))
    action: dict[str, list[float]] = {"positive": [], "negative": []}
    for t in turns:
        if t["id"] in scores and t.get("user_action") in ("accepted", "rejected"):
            action["positive" if t["user_action"] == "accepted" else "negative"].append(float(scores[t["id"]]))
    return {"thumbs": thumbs, "accept/reject": action}


def rank_biserial(pos: Sequence[float], neg: Sequence[float]) -> float:
    """r = P(pos > neg) − P(pos < neg), ties counting half: 2U/(n₁n₂) − 1."""
    greater = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return 2 * greater / (len(pos) * len(neg)) - 1


def mann_whitney(
    pos: Sequence[float], neg: Sequence[float], *, resamples: int = 5000, seed: int = 20260928
) -> dict[str, Any]:
    """One-sided Mann–Whitney U (positive > negative), with the rank-biserial r
    and its 95 % percentile-bootstrap interval. Returns ``test: None`` with a
    reason when a group has fewer than two scores."""
    from scipy.stats import mannwhitneyu

    out: dict[str, Any] = {"n_positive": len(pos), "n_negative": len(neg), "test": None,
                           "median_positive": _median(pos), "median_negative": _median(neg)}
    if len(pos) < 2 or len(neg) < 2:
        out["note"] = "too few scores in a group to test"
        return out
    res = mannwhitneyu(pos, neg, alternative="greater", method="auto")
    rng = random.Random(seed)
    boot = sorted(
        rank_biserial([rng.choice(pos) for _ in pos], [rng.choice(neg) for _ in neg]) for _ in range(resamples)
    )
    out.update(test="Mann–Whitney U, one-sided (positive > negative)", U=float(res.statistic),
               p=float(res.pvalue), r_rb=rank_biserial(pos, neg),
               r_ci_low=boot[int(0.025 * resamples)], r_ci_high=boot[int(0.975 * resamples) - 1])
    return out


def _median(values: Sequence[float]) -> Optional[float]:
    import statistics

    return statistics.median(values) if values else None


# --- UMUX-LITE ---------------------------------------------------------------

#: Sauro–Lewis curved grading scale (Sauro & Lewis, 2016): the
#: lower bound of each grade on the SUS scale, highest first.
CURVED_GRADES: tuple[tuple[float, str], ...] = (
    (84.1, "A+"), (80.8, "A"), (78.9, "A-"), (77.2, "B+"), (74.1, "B"), (72.6, "B-"),
    (71.1, "C+"), (65.0, "C"), (62.7, "C-"), (51.7, "D"), (0.0, "F"),
)


def umux_lite(capability: int, ease: int) -> float:
    """UMUX-LITE on 0–100 from its two 1..7 items (D18)."""
    return ((capability - 1) + (ease - 1)) / 12 * 100


def sus_equivalent(umux: float) -> float:
    """The UMUX-LITE → SUS conversion (Lewis, Utesch & Maher, 2013):
    SUS-equivalent ≈ 0.65 × UMUX-LITE + 22.9. An estimate, not a measured SUS."""
    return 0.65 * umux + 22.9


def curved_grade(sus: float) -> str:
    return next(grade for bound, grade in CURVED_GRADES if sus >= bound)


def usability(post_task: Iterable[Row]) -> list[dict[str, Any]]:
    """One row per submitted post-task survey: UMUX-LITE, its SUS equivalent,
    the grade, and the recommend item. No id."""
    out = []
    for p in post_task:
        if not p.get("submitted_at") or p.get("umux_lite_capability") is None or p.get("umux_lite_ease") is None:
            continue
        u = umux_lite(p["umux_lite_capability"], p["umux_lite_ease"])
        s = sus_equivalent(u)
        out.append({"umux_lite": u, "sus_equivalent": s, "grade": curved_grade(s),
                    "recommend": p.get("likelihood_to_recommend")})
    return out
