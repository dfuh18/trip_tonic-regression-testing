"""The participant-round analysis (C02, §4.3): the propositions, described.

Used by ``notebooks/study/06_analysis`` and ``09_study_propositions``. Like
``src.pilot``, every function past the loaders takes plain rows or plain
values, so the numbers are testable offline (``tests/test_analysis.py``) and
the notebook stays a reader.

**Descriptive only (D104).** Counts, proportions and distributions; no test,
no interval. The sample is a convenience sample with no defined population,
and turns are nested within participants. Each proposition is judged against
a criterion fixed before the data (Q37), not against a p-value.

What each proposition is computed from:

* **P1 — coverage.** A participant *interaction* is one request: a Tonic run
  split by ``shapes.segment_with`` with the slash signal and without reference
  (D100), over ``shapes7`` labels (D99). Its signature is D24's
  (``src.signature``) over the request's turns taken together. It is covered
  when a simulated execution has the same signature. Reported per request, per
  turn, and per participant.
* **P2 — failures the system recovered from (D103).** Tool calls that came back
  an error in a turn that still answered, per tool, side by side for both
  rounds; empty lookups as a secondary row. Simulated turns are read under D53
  (latest attempt only). Turns that failed without a response are counted
  separately.
* **P3 — judge vs feedback.** Judge-score distributions for positively and
  negatively received replies, thumbs and accept/reject kept apart.
* **Table 12** is reported as two axes side by side (D102).
* **UMUX-LITE** goes through the UMUX-LITE → SUS conversion of Lewis, Utesch
  & Maher (2013), an estimate of the SUS score, and is graded on the
  Sauro–Lewis curved grading scale (Sauro & Lewis, 2016).

The definitions of a P1 interaction and of P2's failure are recorded with
D101 and D103.

Nothing here prints, and nothing returns a participant's words or an id.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

from src import shapes
from src.signature import SIGNATURE_RULE_VERSION, signature

Row = dict[str, Any]

#: 2: descriptive only (D104) — intervals, τ and the Mann–Whitney test removed.
ANALYSIS_VERSION = "2"


def share(k: int, n: int) -> float:
    """``k / n``, or NaN when there is nothing to divide by."""
    return k / n if n else float("nan")

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
    return {"n": n, "covered": k, "uncovered": n - k, "share covered": share(k, n),
            "signature_rule": SIGNATURE_RULE_VERSION}


def uncovered_by(rows: Sequence[CoverageRow], key: str = "shape") -> Counter:
    """Where uncovered units concentrate (§4.3 (3))."""
    return Counter(getattr(r, key) for r in rows if not r.covered)


# --- P2: execution failures --------------------------------------------------


@dataclass(frozen=True)
class Rate:
    """``failures`` of ``n`` in one class, and their ratio. No interval (D104)."""

    group: str
    n: int
    failures: int
    rate: float


def _rates(n: Counter, k: Counter) -> list[Rate]:
    return [Rate(group, n[group], k[group], share(k[group], n[group])) for group in sorted(n)]


def failure_rates(turns: Iterable[Row], key: str = "request_type") -> list[Rate]:
    """Turns that failed without a response, per class."""
    n: Counter = Counter()
    k: Counter = Counter()
    for t in turns:
        group = (turn_shape(t) if key == "shape" else t.get(key)) or "(none)"
        n[group] += 1
        k[group] += failed(t)
    return _rates(n, k)


def overall_rate(turns: Sequence[Row]) -> Rate:
    turns = list(turns)
    k = sum(failed(t) for t in turns)
    return Rate("all", len(turns), k, share(k, len(turns)))


def failure_types(turns: Iterable[Row]) -> Counter:
    return Counter(t["error_code"] for t in turns if t.get("error_code"))


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
    """P2's failure measure (D103): tool calls that came back an error inside a
    turn that still produced a response (no ``error_code``).

    ``key="tool"`` (primary): per tool, n = that tool's calls in completed
    turns, k = those that errored. Every tool called is listed, errored or not.
    ``key="request_type"`` or ``"shape"`` (secondary): per class, n = completed
    turns, k = those with at least one errored call."""
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
            group = (turn_shape(t) if key == "shape" else t.get(key)) or "(none)"
            n[group] += 1
            k[group] += any(e.get("result_error") for e in entries)
    return _rates(n, k)


def empty_lookup_rates(turns: Iterable[Row]) -> list[Rate]:
    """P2's secondary row (D103): lookups that worked and found nothing.

    Only tools that report a ``found`` flag count (``result_found`` is not
    null); a call that errored is P2's failure, not a miss, and is left out.
    Per tool: n = its error-free calls in turns that still answered, k = those
    with ``result_found = false``."""
    n: Counter = Counter()
    k: Counter = Counter()
    for t in turns:
        if failed(t):
            continue
        for e in _tool_entries(t):
            if e.get("result_found") is None or e.get("result_error"):
                continue
            n[e["tool"]] += 1
            k[e["tool"]] += e["result_found"] is False
    return _rates(n, k)


#: What kind of error a tool returned, read off its message by pattern, first
#: match wins. The message itself is never shown: it can echo what a
#: participant typed. A message no pattern knows is ``other``, reported.
ERROR_KINDS: tuple[tuple[str, str], ...] = (
    ("beyond forecast horizon", r"forecast horizon"),
    ("timeout", r"time(d)?[ -]?out|aborted"),
    ("invalid arguments", r"invalid_type|expected .*received|Error in tool"),
    ("rejected value", r"must be|not allowed|invalid|out of range|not found"),
    ("upstream unavailable", r"unavailable|503|502|rate limit|quota"),
)


def error_kind(message: Any) -> str:
    import re

    text = str(message or "")
    return next((kind for kind, pattern in ERROR_KINDS if re.search(pattern, text, re.IGNORECASE)), "other")


def error_kinds(turns: Iterable[Row]) -> Counter:
    """(tool, kind) → errored calls, over turns that still produced a response."""
    out: Counter = Counter()
    for t in turns:
        if failed(t):
            continue
        for e in _tool_entries(t):
            if e.get("result_error"):
                out[(e["tool"], error_kind(e["result_error"]))] += 1
    return out


def error_summary(turns: Sequence[Row]) -> dict[str, Any]:
    """The P2 headline for one round: turns, turns that failed outright, turns
    that recovered from at least one tool error, and tool calls."""
    turns = list(turns)
    done = [t for t in turns if not failed(t)]
    calls = [e for t in done for e in _tool_entries(t)]
    k_turns = sum(1 for t in done if any(e.get("result_error") for e in _tool_entries(t)))
    k_calls = sum(1 for e in calls if e.get("result_error"))
    return {
        "turns": len(turns),
        "failed without a response": len(turns) - len(done),
        "turns with a recovered tool error": k_turns,
        "share of answered turns": share(k_turns, len(done)),
        "tool calls": len(calls),
        "errored tool calls": k_calls,
        "share of calls": share(k_calls, len(calls)),
    }


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


def score_summary(values: Sequence[float]) -> dict[str, Any]:
    """A judge-score distribution in five numbers: n, median, mean, min, max (D104)."""
    if not values:
        return {"n": 0, "median": None, "mean": None, "min": None, "max": None}
    return {"n": len(values), "median": statistics.median(values), "mean": round(statistics.fmean(values), 2),
            "min": min(values), "max": max(values)}


def feedback_scores(groups: Mapping[str, Mapping[str, Sequence[float]]]) -> list[dict[str, Any]]:
    """One row per signal and group, for the P3 table: the two signals side by
    side, never pooled."""
    return [{"signal": signal, "group": group, **score_summary(values)}
            for signal, by_group in groups.items() for group, values in by_group.items()]


# --- a shallow per-participant overview ----------------------------------------------


def participant_overview(
    sessions: Sequence[Row],
    names: Mapping[str, str],
    requests: Sequence[Sequence[Row]],
    covered: Sequence[bool],
    feedback: Sequence[Row],
    post_task: Sequence[Row],
) -> list[dict[str, Any]]:
    """One row per consented session, pseudonymous: how much they did, how much
    of it the suite covers, what went wrong, and how they reacted.

    ``requests`` and ``covered`` are aligned (the request list P1 uses). A
    check on whether the pooled numbers are carried by one person, not a
    result of its own (D104)."""
    by_session: dict[str, list[tuple[Sequence[Row], bool]]] = defaultdict(list)
    for req, cov in zip(requests, covered):
        by_session[req[0].get("session_id")].append((req, cov))
    thumbs: dict[str, Counter] = defaultdict(Counter)
    for f in feedback:
        thumbs[f.get("session_id")][f.get("value")] += 1
    sus = {p["session_id"]: row["sus_equivalent"] for p in post_task for row in usability([p])}
    out = []
    for s in sorted((s for s in sessions if s.get("consent_at")), key=lambda s: names.get(s["id"], "")):
        mine = by_session.get(s["id"], [])
        turns = [t for req, _ in mine for t in req]
        calls = [e for t in turns if not failed(t) for e in _tool_entries(t)]
        out.append({
            "participant": names.get(s["id"], "?"),
            "turns": len(turns),
            "requests": len(mine),
            "requests covered": sum(cov for _, cov in mine),
            "requests uncovered": sum(not cov for _, cov in mine),
            "shapes": ", ".join(sorted({interaction_shape(req) for req, _ in mine})) or "-",
            "failed turns": sum(failed(t) for t in turns),
            "tool calls": len(calls),
            "errored tool calls": sum(1 for e in calls if e.get("result_error")),
            "accepted / rejected turns": f"{sum(t.get('user_action') == 'accepted' for t in turns)} / "
                                         f"{sum(t.get('user_action') == 'rejected' for t in turns)}",
            "thumbs up / down": f"{thumbs[s['id']]['up']} / {thumbs[s['id']]['down']}",
            "SUS-equivalent": round(sus[s["id"]], 1) if s["id"] in sus else None,
        })
    return out


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
