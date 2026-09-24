"""What one run actually recorded, and what it did not (B10 precursor).

Two jobs, and the second is the reason this exists before the baseline rather
than after it.

**Joining.** A run's evidence is spread over six tables — the run row, an
execution per repetition, a suggestion per turn, the mutations a turn caused,
the structural verdict, and now the judge's score. Every question worth asking
("did the cases that scored badly also fail structurally?", "is latency worse
on the scheduling cases?") is a join, and a notebook that re-writes those joins
is a notebook that will disagree with the next one. `run_frame` is the join,
once.

**Gap-finding.** `completeness` reports, per table and column, how much of a
run is actually populated. `CLAUDE.md` asks for this of the pilot — "the
notebook asserts that every event model field is populated in at least one
record, and fails loudly if not" — for a reason that applies just as well here:
a field that exists but is always null looks correct in the schema and is
discovered empty during analysis, too late to fix. The study round happens
once; a 160-execution baseline built on a silently-empty column is a baseline
that has to be thrown away.

So this runs against a cheap n=1 run first, deliberately. Finding a hole now
costs twenty minutes; finding it after the baseline costs the baseline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    from pandas import DataFrame


def _pd():
    import pandas as pd

    return pd


#: Every study table, and how a run reaches it. Enumerated against the SCHEMA,
#: not against the event model — the first version of this list was written
#: from the document and named two tables that do not exist under those names
#: (`survey_demographics`, `survey_post_task`), while missing two that do.
#: A completeness report assembled from prose is a completeness report with the
#: document's blind spots built in.
RUN_TABLES: dict[str, str] = {
    "study_runs": "id",
    "study_case_executions": "run_id",
    "study_scores": "run_id",
    "study_comparisons": "run_id",
    "study_structural_verdicts": "run_id",
}

#: Reached through an execution rather than by `run_id`. These carry most of
#: the event model's fields — the turn level and the mutation level.
VIA_EXECUTION: tuple[str, ...] = ("study_suggestions", "study_mutations")

#: Empty in a simulated run by design, with the reason. Each is asserted
#: against the schema: if one of these tables ever gains rows in a simulated
#: run, the reason below is wrong.
EMPTY_IN_SIMULATION: dict[str, str] = {
    "study_verdicts": "no writer in either round after D73 — simulation verdicts are appended to "
                      "study_structural_verdicts, and the participant round is not structurally checked",
    "study_sessions": "participant round only",
    "study_survey_demographics": "participant round only (D02)",
    "study_survey_post_task": "participant round only (D02)",
    "study_user_actions": "participant round only (D12) — the simulator declines in prose and never "
                          "accepts or rejects a suggestion",
    "study_feedback": "participant round only (§4.2.2) — thumbs come from a person",
}

#: Columns allowed to be empty, keyed by **(table, column)**.
#:
#: Keyed by the pair, not the bare name, because the bare name leaked: the
#: reason written for `study_scores.judge_prompt_version` (where the column is
#: NOT NULL) silenced `study_runs.judge_prompt_version`, which genuinely has no
#: writer. The gate built to find unwritten fields hid one. A reason must name
#: the table it excuses.
EXPECTED_SPARSE: dict[tuple[str, str], str] = {
    ("study_runs", "finished_at"): "set when the run ends; null mid-run",
    ("study_runs", "baseline_ref"): "null on a baseline run by definition (D03)",
    ("study_runs", "notes"): "free text, optional",
    ("study_runs", "api_version"): "null on runs before versioning (D63)",
    ("study_runs", "api_commit"): "null on runs before versioning (D63)",
    ("study_runs", "app_version"): "null on runs before versioning (D63)",
    ("study_runs", "judge_prompt_version"): "null on runs before D76, when the field gained a writer",

    ("study_case_executions", "error"): "only a failed execution has one",
    ("study_case_executions", "structural_outcome"): "written by the checker, which runs after the run",
    ("study_case_executions", "structural_findings"): "only an execution with findings has any",
    ("study_case_executions", "base_case_id"): "seeds have none",
    ("study_case_executions", "trip_id"): "null when the repetition never started (D38)",
    ("study_case_executions", "case_version"): "null on runs before D74",
    ("study_case_executions", "attempt"): "defaults to 1",

    ("study_scores", "error"): "only an unscored execution has one",
    ("study_scores", "rationale"): "empty when the judge could not score",
    ("study_scores", "score"): "null when the execution could not be scored",

    ("study_structural_verdicts", "findings"): "empty when the verdict is 'none'",
    ("study_structural_verdicts", "case_version"): "null for a verdict recomputed over a run "
                                                   "that predates D74",

    ("study_suggestions", "error_code"): "only a FAILED turn has one; a clean run populates none "
                                         "(observed as llm_error/empty_reply in earlier runs)",
    ("study_suggestions", "user_action"): "participant round only (D12)",
    ("study_suggestions", "thumb_feedback"): "participant round only (§4.2.2)",
    ("study_suggestions", "private_to"): "the quiet-run mechanism exists and nothing sets it",
    ("study_suggestions", "run_id"): "null on a group-visible edit receipt, by invariant",
    ("study_suggestions", "agent_intent"): "only a slash-command turn carries one",
    ("study_suggestions", "structural_check_outcome"): "nothing writes it (D73): a structural verdict "
                                                       "belongs to an execution, not a turn",

    ("study_mutations", "actor_user_id"): "null for an agent edit",
    # Verified rather than assumed: across 1000 recorded mutations, changed_keys
    # is populated for exactly the 15 UPDATEs and no INSERT or DELETE, and
    # origin_suggestion_id for the 23 agent-originated rows and none of the
    # fixture build's own API calls.
    ("study_mutations", "changed_keys"): "only an UPDATE has changed keys",
    ("study_mutations", "origin_suggestion_id"): "only a mutation the AGENT caused has an origin; "
                                                 "the fixture build's rows have none",
    ("study_comparisons", "error"): "only a comparison the judge refused has one",
    ("study_comparisons", "ordering_candidate_b"): "null only when the judge refused (see error)",
    ("study_comparisons", "ordering_candidate_a"): "null only when the judge refused (see error)",
    ("study_comparisons", "at_least_as_good"): "null only when the judge refused (see error)",
    ("study_comparisons", "structural_outcome"): "null when the execution had not been checked yet",
    ("study_comparisons", "rationale"): "empty when the judge refused",
    ("study_comparisons", "(no rows)"): "this run has not been compared - a baseline run never is (Q33)",
    ("study_scores", "(no rows)"): "this run has not been judged — a fact about the run, not a "
                                   "missing writer",
}


def _rows(table: str, key: str, run_id: str) -> list[dict]:
    from src import db

    return db.admin().table(table).select("*").eq(key, run_id).execute().data


def completeness(run_id: str) -> "DataFrame":
    """Per column: how much of this run populated it.

    `always null` is the column to read. For a column not in
    `EXPECTED_SPARSE` it means nothing writes the field — the schema says it
    exists and the record does not.
    """
    from src import db

    pd = _pd()
    a = db.admin()
    executions = _rows("study_case_executions", "run_id", run_id)
    suggestion_ids = [i for r in executions for i in (r.get("suggestion_ids") or [])]
    trip_ids = [r["trip_id"] for r in executions if r.get("trip_id")]

    extra: dict[str, list[dict]] = {}
    if suggestion_ids:
        extra["study_suggestions"] = (
            a.table("study_suggestions").select("*").in_("id", suggestion_ids).execute().data
        )
    if trip_ids:
        extra["study_mutations"] = (
            a.table("study_mutations").select("*").in_("trip_id", trip_ids).execute().data
        )

    rows = []
    for table, key in list(RUN_TABLES.items()) + [(t2, None) for t2 in extra]:
        data = extra[table] if key is None else _rows(table, key, run_id)
        if not data:
            rows.append({"table": table, "column": "(no rows)", "rows": 0,
                         "populated": 0, "share": 0.0, "always null": True,
                         "expected": EXPECTED_SPARSE.get((table, "(no rows)"), "")})
            continue
        for column in sorted(data[0].keys()):
            filled = sum(1 for r in data if r.get(column) not in (None, "", [], {}))
            rows.append({
                "table": table,
                "column": column,
                "rows": len(data),
                "populated": filled,
                "share": round(filled / len(data), 2),
                "always null": filled == 0,
                "expected": EXPECTED_SPARSE.get((table, column), ""),
            })
    for table, why in EMPTY_IN_SIMULATION.items():
        rows.append({"table": table, "column": "(whole table)", "rows": 0,
                     "populated": 0, "share": 0.0, "always null": True, "expected": why})
    return pd.DataFrame(rows).set_index(["table", "column"])


def gaps(run_id: str) -> "DataFrame":
    """Only the columns nothing wrote, and which have no stated reason.

    This is the list to act on before a baseline.
    """
    frame = completeness(run_id)
    return frame[(frame["always null"]) & (frame["expected"] == "")]


def turn_frame(run_id: str) -> "DataFrame":
    """One row per agent turn, joined to the case it belongs to."""
    from src import db
    from src.execution import latest_attempts
    from src.shapes import tools_of

    pd = _pd()
    a = db.admin()
    executions, _ = latest_attempts(_rows("study_case_executions", "run_id", run_id))
    ids = [i for row in executions for i in (row.get("suggestion_ids") or [])]
    if not ids:
        return pd.DataFrame()
    owner = {i: row for row in executions for i in (row.get("suggestion_ids") or [])}
    turns = a.table("study_suggestions").select("*").in_("id", ids).execute().data
    rows = []
    for t in turns:
        ex = owner.get(t["id"], {})
        trace = t.get("tool_call_trace") or []
        rows.append({
            "case": ex.get("case_id"),
            "provenance": ex.get("provenance"),
            "turn": t.get("turn_index"),
            "latency_ms": t.get("latency_ms") or 0,
            "retry_count": t.get("retry_count") or 0,
            "queued": bool(t.get("retry_count")),
            "llm_calls": t.get("llm_calls") or 0,
            "tool_calls": len(trace),
            "tools": ", ".join(sorted({c.get("tool", "?") for c in trace})) or "-",
            "tool_names": tools_of(trace),
            "tokens_in": t.get("tokens_input") or 0,
            "tokens_out": t.get("tokens_output") or 0,
            "error_code": t.get("error_code"),
            "request_type": t.get("request_type"),
        })
    return pd.DataFrame(rows).sort_values(["case", "turn"]).reset_index(drop=True)


def run_frame(run_id: str) -> "DataFrame":
    """One row per execution, with everything a plot might need.

    The join: execution + case metadata + structural verdict + judge score.
    Highest attempt only (D53) — a superseded attempt is evidence about the
    platform, not about the agent, and nothing describing the agent counts it.
    """
    from src.cases import load_cases
    from src.execution import latest_attempts
    from src.runner import failure_class

    pd = _pd()
    cases = {c.case_id: c for c in load_cases()}
    executions, superseded = latest_attempts(_rows("study_case_executions", "run_id", run_id))
    scores = {s["execution_id"]: s for s in _rows("study_scores", "run_id", run_id)}

    rows = []
    for ex in executions:
        case = cases.get(ex["case_id"])
        score = scores.get(ex["id"], {})
        rows.append({
            "case": ex["case_id"],
            "function": case.function if case else "?",
            "provenance": ex.get("provenance"),
            "relation": (case.metamorphic_relation if case else None) or "-",
            "repetition": ex.get("repetition"),
            "attempt": ex.get("attempt") or 1,
            "error": ex.get("error"),
            "blame": failure_class(ex.get("error")) or "-",
            "structural": ex.get("structural_outcome") or "(not checked)",
            "findings": len(ex.get("structural_findings") or []),
            "score": score.get("score"),
            "not_scored": score.get("error"),
            "latency_ms": ex.get("latency_ms") or 0,
            "cost_usd": ex.get("cost_usd") or 0.0,
            "tokens": ex.get("token_count") or 0,
        })
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame.attrs["superseded_attempts"] = superseded
        frame = frame.sort_values(["function", "case"]).reset_index(drop=True)
    return frame


def headline(run_id: str) -> str:
    """The run in a paragraph, for the top of a notebook."""
    from src import db

    run = db.admin().table("study_runs").select("*").eq("id", run_id).execute().data[0]
    frame = run_frame(run_id)
    scored = frame["score"].dropna() if "score" in frame else []
    lines = [
        f"run {run_id[:8]}  started {str(run['started_at'])[:19]}",
        f"  notes         {run.get('notes') or '-'}",
        f"  agent         {run.get('model_version')} (released {run.get('model_released_on')})",
        f"  api           {run.get('api_version') or '?'} @ {run.get('api_commit') or '?'}",
        f"  suite         {str(run.get('suite_version'))[:12]}",
        f"  executions    {len(frame)}"
        + (f"  (+{frame.attrs.get('superseded_attempts', 0)} superseded)" if len(frame) else ""),
        f"  failed        {int((frame['blame'] != '-').sum()) if len(frame) else 0}",
        f"  scored        {len(scored)}"
        + (f", mean {scored.mean():.2f}" if len(scored) else " — no judge scores persisted"),
        f"  cost          ${run.get('cost_usd') or 0:.4f}",
    ]
    return "\n".join(lines)


def turn_signals(run_id: str, rule=None) -> dict:
    """``{"<case_id>#<repetition>": [TurnSignals, ...]}`` for one run, turns in
    order (Q29). Keyed by repetition as well as case, because at n > 1 a key of
    the case id alone kept only the last repetition of each case.

    Highest attempt only (D53). The reply's place ids come from
    ``chat_messages.metadata.refs``, the same field the checker reads; the
    rest from the turn's own row. Also returns, under the key ``None``, the
    case ids whose execution spanned more than one Tonic run — the bench
    assumes an execution is one request, and one that is not must be seen.
    """
    from src import db
    from src.execution import _place_ids_of, latest_attempts
    from src.shapes import shapes7, signals_of

    a = db.admin()
    executions, _ = latest_attempts(_rows("study_case_executions", "run_id", run_id))
    ids = [i for row in executions for i in (row.get("suggestion_ids") or [])]
    if not ids:
        return {None: []}
    turns = {
        t["id"]: t
        for t in a.table("study_suggestions")
        .select("id, run_id, turn_index, agent_intent, tool_call_trace, reply_message_id")
        .in_("id", ids).execute().data
    }
    replies = [t["reply_message_id"] for t in turns.values() if t.get("reply_message_id")]
    refs = {
        m["id"]: _place_ids_of(m.get("metadata"))
        for m in (a.table("chat_messages").select("id, metadata").in_("id", replies).execute().data
                  if replies else [])
    }
    out: dict = {None: []}
    for row in executions:
        own = sorted((turns[i] for i in row.get("suggestion_ids") or [] if i in turns),
                     key=lambda t: t.get("turn_index") or 0)
        key = f"{row['case_id']}#{row.get('repetition') or 1}"
        if len({t["run_id"] for t in own}) > 1:
            out[None].append(key)
        out[key] = [
            signals_of(t.get("tool_call_trace") or [], refs.get(t.get("reply_message_id"), ()),
                       t.get("agent_intent"), rule or shapes7)
            for t in own
        ]
    return out
