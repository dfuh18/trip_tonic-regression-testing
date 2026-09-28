"""One complete record, printable: a simulated execution or a pilot session.

Used by ``tools/render_example.py``. Everything the study records about one
unit is gathered level by level, as ``docs/event-model.md`` orders it, and
rendered as a self-contained HTML page with print styles. Two uses:

* **Completeness.** Every column is shown, nulls included, and each is marked
  when it is an event-model field. A descriptive table that leaves out a
  recorded field, or a field that is always empty, shows up here.
* **Showcase.** The conversation, the trace, the state changes, the feedback
  and the verdicts of one unit, in the order they happened.

Ids are replaced by stable tokens (``‹id 3›``) throughout, so a printout
carries no database identifier. Text the member wrote is shown verbatim: a
pilot session holds a real person's words and is printed only with their
consent. The output goes to ``examples/``, which is git-ignored.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from src import analysis, pilot, shapes
from src.config import SUBTREE_ROOT

Row = dict[str, Any]

EVENT_MODEL = SUBTREE_ROOT / "docs" / "event-model.md"
CASES_DIR = SUBTREE_ROOT / "cases"
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")


def event_model_names(path: Path = EVENT_MODEL) -> set[str]:
    """Every field name any event-model table lists (all levels), plus the
    columns ``pilot.FIELD_COLUMNS`` stores them under."""
    names = set(re.findall(r"^\|\s*`([a-z_]+)`", path.read_text(encoding="utf-8"), re.MULTILINE))
    names |= {column for _, column in pilot.FIELD_COLUMNS.values()}
    return names


class Pseudonyms:
    """uuid → ``‹id n›``, stable within one document, applied recursively."""

    def __init__(self) -> None:
        self.seen: dict[str, str] = {}

    def token(self, uid: str) -> str:
        return self.seen.setdefault(uid, f"‹id {len(self.seen) + 1}›")

    def __call__(self, value: Any) -> Any:
        if isinstance(value, str):
            return _UUID.sub(lambda m: self.token(m.group(0)), value)
        if isinstance(value, dict):
            return {k: self(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self(v) for v in value]
        return value


@dataclass
class Section:
    """One block of the page. ``kind``: ``record`` (field/value rows),
    ``table`` (rows × columns), ``chat`` (who said what), ``text`` (pre)."""

    title: str
    kind: str
    body: Any
    note: str = ""
    level: str = ""
    #: What the section holds, for ``compact`` (e.g. ``turn_row``, ``trace``).
    role: str = ""
    #: The turn a per-turn section belongs to.
    turn: Optional[int] = None


@dataclass
class Example:
    title: str
    subtitle: str
    warning: str = ""
    sections: list[Section] = field(default_factory=list)
    #: A simulated execution a structural check failed: its appendix version
    #: keeps the case's checks, since the check that fired is the point.
    failed: bool = False


# --- gathering -------------------------------------------------------------------


def _one(client: Any, table: str, column: str, value: Any) -> Optional[Row]:
    rows = client.table(table).select("*").eq(column, value).execute().data
    return rows[0] if rows else None


def _many(client: Any, table: str, column: str, values: Sequence[Any]) -> list[Row]:
    return client.table(table).select("*").in_(column, list(values)).execute().data if values else []


def _messages(client: Any, turns: Sequence[Row]) -> dict[str, Row]:
    ids = [t[k] for t in turns for k in ("reply_message_id", "user_message_id") if t.get(k)]
    return {m["id"]: m for m in _many(client, "chat_messages", "id", ids)}


def _turn_sections(client: Any, turns: Sequence[Row], feedback: Sequence[Row], actions: Sequence[Row]) -> list[Section]:
    msgs = _messages(client, turns)
    chat = []
    thumbs = {f["chat_message_id"]: f["value"] for f in feedback}
    for t in turns:
        reply = msgs.get(t.get("reply_message_id"), {})
        chat.append({"who": "member", "turn": t.get("turn_index"), "text": t.get("user_turn") or ""})
        chat.append({"who": "Tonic", "turn": t.get("turn_index"), "text": reply.get("content") or "(no reply)",
                     "meta": f"{analysis.turn_shape(t)} · {t.get('request_type')}"
                             + (f" · thumbs {thumbs[reply['id']]}" if reply.get("id") in thumbs else "")
                             + (f" · {t['user_action']}" if t.get("user_action") else "")})
    out = [Section("The conversation", "chat", chat, level="Suggestion level", role="chat",
                   note="What the member typed (`user_turn`, verbatim) and Tonic's reply (`chat_messages.content` "
                        "via `reply_message_id`). Under each reply: its shape, request type, thumbs and user action.")]
    for t in turns:
        record = {k: v for k, v in t.items() if k not in ("tool_call_trace", "user_turn")}
        out.append(Section(f"Turn {t.get('turn_index')} — the suggestion row", "record", record,
                           level="Suggestion level", role="turn_row", turn=t.get("turn_index"),
                           note="`study_suggestions`, every column except the trace "
                                "and the member's text (shown above)."))
        trace = [{
            "seq": e.get("seq"), "kind": e.get("kind", "tool"), "tool / model": e.get("tool") or e.get("model"),
            "args": e.get("args"), "ms": e.get("duration_ms"),
            "tokens in/out": (f"{e.get('tokens_input')}/{e.get('tokens_output')}" if e.get("kind") == "llm" else None),
            "result chars": e.get("result_chars"), "found": e.get("result_found"),
            "error": (f"[{analysis.error_kind(e['result_error'])}] {e['result_error']}" if e.get("result_error")
                      else e.get("error")),
        } for e in sorted(t.get("tool_call_trace") or [], key=lambda e: e.get("seq", 0))]
        out.append(Section(f"Turn {t.get('turn_index')} — tool and model calls", "table", trace,
                           level="Suggestion level", role="trace", turn=t.get("turn_index"),
                           note="`tool_call_trace`, one row per model or tool call, "
                                "in order. An error is prefixed with its kind (D103)."))
    mine = [a for a in actions if a.get("suggestion_id") in {t["id"] for t in turns}]
    out.append(Section("What the member did with the suggestions", "table", mine, level="Suggestion level",
                       role="actions", note="`study_user_actions`, one row per target (slot, place, edits), "
                                            "from which `user_action` is derived (D12)."))
    out.append(Section("Thumbs", "table", list(feedback), level="Suggestion level", role="thumbs",
                       note="`study_feedback`, keyed by the reply message."))
    return out


def _derived(turns: Sequence[Row], suite: Optional[Sequence[Sequence[Row]]], refs: dict, unit: str) -> list[Section]:
    per_turn = [{"turn": t.get("turn_index"), "tools": " > ".join(shapes.tools_of(t.get("tool_call_trace") or [])),
                 "request_type (app)": t.get("request_type"), "shape (shapes7)": analysis.turn_shape(t),
                 "tool errors": sum(1 for e in t.get("tool_call_trace") or [] if e.get("result_error")),
                 "empty lookups": sum(1 for e in t.get("tool_call_trace") or []
                                      if e.get("result_found") is False and not e.get("result_error"))}
                for t in turns]
    segs = analysis.segments(turns, refs) if unit == "session" else [list(turns)]
    suite_sigs = {analysis.interaction_signature(ex) for ex in suite} if suite else set()
    per_request = []
    for i, seg in enumerate(segs, 1):
        sig = analysis.interaction_signature(seg)
        row = {"request": i, "turns": ", ".join(str(t.get("turn_index")) for t in seg),
               "shape": analysis.interaction_shape(seg), "signature (D24)": sig}
        if suite:
            row["covered by the simulated runs"] = sig in suite_sigs
            if sig not in suite_sigs:
                row["closest suite signature differs in"] = ", ".join(analysis.nearest_miss(sig, suite_sigs))
        per_request.append(row)
    return [
        Section("Per turn", "table", per_turn, level="Derived in analysis", role="derived_turn",
                note="Computed from the trace, not stored: shape (D99), tool errors and empty lookups (D103)."),
        Section("Per request", "table", per_request, level="Derived in analysis", role="derived_request",
                note=("A Tonic run split into requests by shape change and slash command (D100), each with its "
                      "coverage signature (D24) and whether a simulated execution matched it (P1).")
                if unit == "session" else "The execution as one interaction, with its coverage signature (D24)."),
    ]


def simulated(client: Any, run_id: str, case_id: str, repetition: int) -> Example:
    from src.execution import latest_attempts

    rows = client.table("study_case_executions").select("*").eq("run_id", run_id).eq("case_id", case_id) \
        .eq("repetition", repetition).execute().data
    ex = latest_attempts(rows)[0][0]
    run = _one(client, "study_runs", "id", run_id)
    ids = ex.get("suggestion_ids") or []
    turns = sorted(_many(client, "study_suggestions", "id", ids), key=lambda t: t.get("turn_index") or 0)
    replies = [t["reply_message_id"] for t in turns if t.get("reply_message_id")]
    feedback = _many(client, "study_feedback", "chat_message_id", replies)
    actions = _many(client, "study_user_actions", "suggestion_id", ids)
    mutations = _many(client, "study_mutations", "origin_suggestion_id", ids)
    case_file = CASES_DIR / f"{case_id}.yaml"
    fixture_text = _fixture_text(case_id, ex)

    judge = [
        Section("What the checker found", "table",
                [{"finding": f, "check that raised it": finding_check(f)} for f in ex.get("structural_findings") or []],
                level="Judge and checker", role="findings",
                note="`structural_findings`, one row per failed check, with the case's check it comes from."),
        Section("Point-wise score", "table", _many(client, "study_scores", "execution_id", [ex["id"]]),
                level="Judge and checker", role="score",
                note="`study_scores`: the first reply scored 1–10 against the case's criteria (D34)."),
        Section("Pair-wise comparison against the baseline", "table",
                _many(client, "study_comparisons", "execution_id", [ex["id"]]), level="Judge and checker",
                role="comparison", note="`study_comparisons`: both orderings (D23), read under D88."),
        Section("Structural verdicts", "table",
                _many(client, "study_structural_verdicts", "execution_id", [ex["id"]]), level="Judge and checker",
                role="verdicts", note="`study_structural_verdicts`, appended per checker version (D76)."),
    ]
    baseline_reply = _baseline_reply(client, judge[1].body)
    if baseline_reply:
        judge.append(Section("The baseline reply it was compared with", "chat",
                             [{"who": "Tonic (baseline)", "turn": 1, "text": baseline_reply}],
                             level="Judge and checker", role="baseline_reply"))

    return Example(
        title=f"A simulated execution: {case_id}, repetition {repetition}",
        subtitle=f"Run {run_id[:8]} · started {_day(ex.get('started_at'))}",
        failed=ex.get("structural_outcome") == "detected",
        sections=[
            Section("The run", "record", run, level="Run level", role="run",
                    note="`study_runs`: one row per suite run."),
            Section("The fixture trip", "text", fixture_text, level="Test case level", role="fixture",
                    note="The trip every repetition starts from, rebuilt fresh for each one (D38): the same "
                         "summary the judge is given (`src/fixture.py`)."),
            Section("The test case as defined", "text",
                    case_file.read_text(encoding="utf-8") if case_file.exists() else "(case file not found)",
                    level="Test case level", role="case",
                    note=f"`cases/{case_id}.yaml`, the file the execution ran from."),
            Section("The execution", "record", ex, level="Test case level", role="execution",
                    note="`study_case_executions`: one row per repetition."),
            Section("The simulated member's session", "record", _one(client, "study_sessions", "id", ex["session_id"]),
                    level="Session level", role="session", note="`study_sessions` with `run_type = simulation`."),
            *_turn_sections(client, turns, feedback, actions),
            Section("State changes", "table", mutations, level="State mutation level", role="mutations",
                    note="`study_mutations` linked to this execution's turns; the fixture build's own writes "
                         "(`build_mutation_ids`) are not among them."),
            *judge,
            *_derived(turns, None, {}, "execution"),
        ])


#: Which declared check a checker finding comes from, by the sentence it writes
#: (``src/checker.py``). Display only: a finding no pattern knows shows "—"
#: rather than a guess. First match wins, so the specific patterns come first.
FINDING_CHECKS: tuple[tuple[str, str], ...] = (
    (r"before the draft on .* ends", "slot_moved.after_latest_draft"),
    (r"no draft slot on .* to place", "slot_moved.after_latest_draft"),
    (r"overlaps|clear of", "slot_moved.clear_of_other_slots"),
    (r"was never moved|ended up on|' starts at .*, outside", "slot_moved"),
    (r"^draft slots outside", "draft_slot_starts_between"),
    (r"^draft slots: expected", "slot_count"),
    (r"^draft is on", "slot_days"),
    (r"offered to pick from|earlier reply|earlier turn", "draft_uses_earlier_place"),
    (r"no plan was proposed", "a draft (propose_plan)"),
    (r"km from .*, outside|places_near", "places_near"),
    (r"returned an error|failed and nothing recovered it", "tool_errors"),
    (r"which this case does not permit", "permitted tools (deny by default, D28)"),
    (r"did not complete", "turn_errors"),
    (r"was never scheduled|was scheduled on", "slot_scheduled"),
    (r"nothing was unscheduled", "slot_unscheduled"),
    (r"trip_after|post-turn trip state", "trip_after"),
    (r"^(itinerary_slots|trip_blocks|ai_suggestions|itinerary_days)\.", "mutation_counts"),
    (r"^edits\.|^(move|schedule|unschedule) edits", "edits"),
    (r"^[a-z_]+ calls: expected|^tool ", "tool_counts"),
)


def finding_check(finding: str) -> str:
    return next((key for pattern, key in FINDING_CHECKS if re.search(pattern, finding)), "—")


def _fixture_text(case_id: str, ex: Row) -> str:
    """The fixture as the execution's case saw it, dated as on the day it ran (D54)."""
    from src import fixture
    from src.cases import load_cases
    from src.scoring import execution_day

    case = {c.case_id: c for c in load_cases()}.get(case_id)
    return fixture.summary(fixture.for_case(case, execution_day(ex))) if case else "(case not in the suite)"


def _baseline_reply(client: Any, comparisons: Sequence[Row]) -> str:
    if not comparisons or not comparisons[0].get("baseline_execution_id"):
        return ""
    from src.scoring import first_reply

    base = _one(client, "study_case_executions", "id", comparisons[0]["baseline_execution_id"])
    return first_reply(base)[1] if base else ""


def pilot_session(client: Any, name: str, sim_run_ids: Sequence[str], run_type: str = "pilot") -> Example:
    from src.execution import _place_ids_of

    data = pilot.load(client, run_type)
    by_name = {v: k for k, v in data.pseudonyms().items()}
    if name not in by_name:
        raise ValueError(f"no {run_type} session {name}; have {sorted(by_name)}")
    sid = by_name[name]
    session = next(s for s in data.sessions if s["id"] == sid)
    turns = sorted((t for t in data.suggestions if t["session_id"] == sid),
                   key=lambda t: (t.get("occurred_at") or "", t.get("turn_index") or 0))
    feedback = [f for f in data.feedback if f.get("session_id") == sid]
    replies = [t["reply_message_id"] for t in turns if t.get("reply_message_id")]
    refs = {m["id"]: _place_ids_of(m.get("metadata")) for m in _many(client, "chat_messages", "id", replies)}
    suite, _ = analysis.simulated_executions(client, sim_run_ids)

    return Example(
        title=f"A {run_type} session: {name}",
        subtitle=f"{len(turns)} agent turns · consented {_day(session.get('consent_at'))}",
        warning=("This page holds a real person's words and survey answers. Print it only with their "
                 "consent, and only if the session is not excluded from what the thesis may show."),
        sections=[
            Section("The session", "record", session, level="Session level", role="session",
                    note="`study_sessions`."),
            Section("Demographic questionnaire", "record",
                    next((d for d in data.demographics if d["session_id"] == sid), None),
                    level="Survey level", role="demographics", note="`study_survey_demographics` (D18)."),
            *_turn_sections(client, turns, feedback, data.user_actions),
            Section("State changes", "table", [m for m in data.mutations if m.get("session_id") == sid],
                    level="State mutation level", role="mutations",
                    note="`study_mutations` in this session: Tonic's and the "
                         "member's own edits, told apart by `origin_kind` (D13)."),
            Section("Post-task survey", "record", next((p for p in data.post_task if p["session_id"] == sid), None),
                    level="Survey level", role="post_task",
                    note="`study_survey_post_task`; UMUX-LITE → SUS conversion in 06."),
            *_derived(turns, suite, refs, "session"),
        ])


# --- the appendix version -------------------------------------------------------------

#: How to read each part, shown in a box above it in the appendix version.
GUIDE: dict[str, str] = {
    "fixture": "The trip the simulated member is planning, before anything happens. Every repetition gets a "
               "fresh copy built from the same fixture file, so each one starts from exactly this state (D38). "
               "It is what the agent can read and change, and what the case's expectations are written "
               "against.",
    "run": "One row per suite run. The version fields pin what was tested: the agent model as a dated release "
           "(never an alias), the agent's prompt and tools, the suite, and the simulator and judge. Two runs are "
           "comparable only when these match; `baseline_ref` names the run this one is compared against.",
    "case": "The test case the execution ran from: who the simulated member is, what they want, their first "
            "message, and the criteria the judge scores the first reply against. A simulator plays the member "
            "from the profile and goal; only the opening message is fixed.",
    "case_checks": "The test case the execution ran from: who the simulated member is, what they want, their "
                   "first message, the structural checks, and the criteria the judge scores the first reply "
                   "against. A simulator plays the member from the profile and goal; only the opening message is "
                   "fixed. Each check is a claim about the outcome over the whole execution (D27): tool counts, "
                   "which days and times a draft may use, what may be written to the trip. A check left null is "
                   "not asserted.",
    "execution": "The checker's verdict over the whole execution. `structural_outcome` is `none` when every check "
                 "held and `detected` when one failed; the findings below say which, in plain words, each beside "
                 "the check in the test case that raised it. A detected finding fails the execution whatever "
                 "the judge says (D23).",
    "session": "One row per session. `run_type` separates pilot, study and simulated sessions, which share the "
               "same tables; `consent_version` records which consent text was agreed to. Every row below joins "
               "to this session.",
    "demographics": "Asked once, after consent and before the first turn (D18). Reported only in aggregate.",
    "chat": "The conversation as the member saw it. Each Tonic reply is one suggestion (D08), the unit that "
            "carries feedback and failure. The grey line under a reply gives its shape (D99), the request type "
            "the app assigned (D09), the member's thumbs, and what they did with it. Long replies are shortened "
            "here; the full text is stored.",
    "turn_row": "The record of one agent turn, shown for one turn only. `request_type` is assigned from the tools "
                "the turn called; `error_code` is set only when the turn produced no response at all. "
                "`user_action` is the indirect feedback (§4.2.2): accepted, rejected, or ignored after 24 hours. "
                "The state after the turn summarises `resulting_state_shape`.",
    "trace": "The tools the agent called in that turn, in order. P1's coverage signature is built from this "
             "sequence and its arguments. P2 counts the calls whose result carries an error while the agent "
             "still answered, and empty lookups (`found` = false) as a secondary row.",
    "actions": "What the member did with Tonic's suggestions, per target: a draft slot accepted or rejected, a "
               "place added. It is the indirect feedback signal of P3.",
    "thumbs": "The member's thumbs on Tonic's replies: the direct feedback signal of P3, never pooled with the "
              "indirect one.",
    "mutations": "Every write to the trip's plan tables, recorded by database triggers. `origin_kind` tells "
                 "Tonic's writes from the member's own (D13); this is how a suggestion is traced to the change "
                 "it caused on the trip.",
    "post_task": "Shown once, after the third turn. UMUX-LITE (two items, 1–7) is converted to an estimated SUS "
                 "score in the analysis. A dismissed survey has only `dismissed_at` set.",
    "score": "The judge's point-wise score of the first reply against the case's criteria (1–10), with its "
             "reason. The judge sees the request and the reply only (P3).",
    "comparison": "The pair-wise verdict against the baseline, asked twice with the order swapped (D23). The "
                  "execution passes unless both orderings prefer the baseline (D88).",
    "verdicts": "The structural checker's verdict, appended per checker version (D76).",
    "derived_turn": "Not stored: computed by the analysis from the trace.",
    "derived_request": "A Tonic run is split into requests (D100). Each request's coverage signature (D24) is "
                       "matched against the simulated executions: a match means the suite exercises this shape "
                       "of request (P1). The signature reads: request type · tools in call order · calls per "
                       "tool (bucketed 1, 2, 3+) · member turns (same buckets) · which kinds of parameter the "
                       "calls carried.",
}

#: The fields the appendix keeps per record; everything else is counted, not shown.
KEEP: dict[str, tuple[str, ...]] = {
    "run": ("model_version", "model_released_on", "prompt_version", "tool_version", "suite_version",
            "baseline_ref", "simulator_model", "judge_model", "judge_prompt_version"),
    "execution": ("case_id", "provenance", "repetition", "repetitions_n", "structural_outcome",
                  "latency_ms", "cost_usd", "error"),
    "session": ("run_type", "consent_version", "consent_at", "device_type"),
    "demographics": ("age", "gender", "education_level", "llm_familiarity"),
    "turn_row": ("turn_index", "agent_intent", "request_type", "latency_ms", "llm_calls", "tool_calls",
                 "tokens_input", "tokens_output", "retry_count", "error_code", "user_action", "model_version",
                 "model_released_on"),
    "post_task": ("umux_lite_capability", "umux_lite_ease", "likelihood_to_recommend", "real_trip",
                  "submitted_at", "dismissed_at"),
    "score": ("score", "rationale", "judge_model", "judge_prompt_version"),
    "comparison": ("ordering_candidate_b", "ordering_candidate_a", "at_least_as_good", "rationale", "baseline_kind"),
    "verdicts": ("checker_version", "outcome", "findings"),
}


def _clip(text: str, chars: int) -> str:
    text = text or ""
    return text if len(text) <= chars else text[:chars].rsplit(" ", 1)[0] + " […]"


def _state_line(shape: Any) -> str:
    """``resulting_state_shape`` as one sentence."""
    if not isinstance(shape, dict):
        return "not recorded"
    parts = []
    draft = shape.get("draft")
    parts.append(f"a draft with {draft.get('slots')} slot(s) over {draft.get('days')} day(s)" if draft else "no draft")
    edits = {k: v for k, v in (shape.get("edits") or {}).items() if v}
    parts.append("live edits: " + ", ".join(f"{v} {k}" for k, v in edits.items()) if edits else "no live edit")
    parts.append(f"{shape.get('places_surfaced', 0)} place(s) found")
    reply = shape.get("reply") or {}
    parts.append(f"reply of {reply.get('chars', 0)} characters citing {reply.get('place_refs', 0)} place(s)")
    after = shape.get("trip_after") or {}
    if after:
        parts.append(f"trip afterwards: {after.get('blocks')} saved stops, {after.get('slots')} scheduled")
    return "; ".join(parts)


def _short_args(args: Any, width: int = 40) -> str:
    if not isinstance(args, dict):
        return ""
    return ", ".join(f"{k}={_clip(json.dumps(v, ensure_ascii=False), width)}" for k, v in args.items())


def _counts(rows: Sequence[Row], key, name: str) -> list[Row]:
    from collections import Counter

    return [{**dict(zip(name.split("|"), k if isinstance(k, tuple) else (k,))), "rows": n}
            for k, n in sorted(Counter(key(r) for r in rows).items(), key=lambda kv: -kv[1])]


#: The appendix order for a simulated execution: the setup, then what happened,
#: then the verdict, then where it came from. Roles not listed keep their place
#: at the end; ``verdicts`` repeats the execution's findings and is dropped.
STORY: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("1 · The setup", ("fixture", "case")),
    ("2 · What happened", ("chat", "turn_row", "trace", "actions", "thumbs", "mutations")),
    ("3 · The verdict", ("execution", "findings", "score", "comparison", "baseline_reply")),
    ("4 · What the analysis derives", ("derived_turn", "derived_request")),
    ("5 · Provenance", ("run", "session")),
)


def _story_order(sections: Sequence[Section]) -> list[Section]:
    placed = []
    for level, roles in STORY:
        for role in roles:
            for s in sections:
                if s.role == role:
                    placed.append(Section(s.title, s.kind, s.body, s.note, level, s.role, s.turn))
    rest = [s for s in sections if s.role not in {r for _, roles in STORY for r in roles} | {"verdicts"}]
    return placed + rest


def compact(example: Example, focus_turn: Optional[int] = None, chars: int = 500) -> Example:
    """The appendix version: the same record, shortened, with a reading guide.

    All turns stay in the conversation (replies clipped to ``chars``); only
    ``focus_turn`` keeps its suggestion row and trace (default: the turn that
    called the most tools). Mutations and member actions become counts. Every
    shortened record says how many columns it left out. A simulated execution
    is reordered as a story (``STORY``); a failing one keeps its case's checks."""
    turns_with_trace = [s for s in example.sections if s.role == "trace"]
    if focus_turn is None and turns_with_trace:
        acting = [s for s in turns_with_trace if any(r["kind"] == "tool" for r in s.body)] or turns_with_trace
        # A failing execution shows the last turn that acted: that is where the
        # outcome the checks judge was made. Otherwise the turn that called most.
        focus_turn = (max(acting, key=lambda s: s.turn or 0) if example.failed
                      else max(acting, key=lambda s: sum(1 for r in s.body if r["kind"] == "tool"))).turn
    sections = _story_order(example.sections) if any(s.role == "fixture" for s in example.sections) \
        else example.sections
    out, guided = [], set()
    for s in sections:
        role = s.role
        if role in ("turn_row", "trace") and s.turn != focus_turn:
            continue
        body, note = s.body, s.note
        if role in KEEP and isinstance(body, dict):
            kept = {k: body.get(k) for k in KEEP[role] if k in body}
            if role == "turn_row":
                kept["state after the turn"] = _state_line(body.get("resulting_state_shape"))
            note = f"{note} Shown: {len(kept)} fields; {len(body) - len(kept)} further columns in the full record."
            body = kept
        elif role in KEEP and isinstance(body, list):
            body = [{k: r.get(k) for k in KEEP[role] if k in r} for r in body]
        elif role == "chat":
            body = [{**m, "text": _clip(m["text"], chars)} for m in body]
        elif role == "baseline_reply":
            body = [{**m, "text": _clip(m["text"], chars)} for m in body]
        elif role == "trace":
            llm = sum(1 for r in body if r["kind"] == "llm")
            body = [{"seq": r["seq"], "tool": r["tool / model"], "arguments": _short_args(r["args"]), "ms": r["ms"],
                     "found": r["found"], "error": _clip(r["error"], 90) if r["error"] else None}
                    for r in body if r["kind"] == "tool"]
            note = f"Tool calls only; the turn also made {llm} model call(s), recorded with their tokens and time."
        elif role == "actions":
            body = _counts(body, lambda r: ((r.get("target") or "").split(":")[0], r.get("action")), "target|action")
            note = "Counted per kind of target and action; one row per target in the full record."
        elif role == "thumbs":
            body = _counts(body, lambda r: r.get("value"), "value")
        elif role == "mutations":
            body = _counts(body, lambda r: (r.get("origin_kind"), r.get("table_name"), r.get("op")),
                           "origin_kind|table|operation")
            note = "Counted per origin, table and operation; one row per write in the full record."
        elif role == "case":
            checks = case_checks(body) if example.failed else []
            body = _case_summary(body)
        elif role == "derived_request":
            body = [{**r, "signature (D24)": _signature_text(r["signature (D24)"])} for r in body]
        guide = "case_checks" if role == "case" and example.failed else role
        if guide in GUIDE and role not in guided:
            out.append(Section("How to read this", "guide", GUIDE[guide], level=s.level, role="guide"))
            guided.add(role)
        out.append(Section(s.title.replace(f"Turn {focus_turn} — ", f"Turn {focus_turn} (in detail) — "),
                           s.kind, body, note, s.level, role, s.turn))
        if role == "case" and example.failed and checks:
            out.append(Section("The checks the case declares", "table", checks, level=s.level, role="checks",
                               note="`declared_constraints.checks`, asserted checks only; each is judged over "
                                    "the whole execution (D27). Bounds are inclusive."))
    return Example(example.title + " — appendix version",
                   example.subtitle + (f" · turn {focus_turn} shown in detail" if focus_turn else ""),
                   example.warning, out)


_PARAM_NAMES = ("location", "date", "price term", "dietary term")


def _signature_text(sig: Any) -> str:
    """A D24 signature in words: type · sequence · calls per tool · turns · parameters."""
    try:
        request_type, sequence, counts, turns, params = sig
    except (TypeError, ValueError):
        return str(sig)
    calls = ", ".join(f"{tool} ×{n}" for tool, n in counts) or "none"
    flags = ", ".join(name for name, on in zip(_PARAM_NAMES, params) if on) or "none"
    return (f"{request_type} · {' → '.join(sequence) or 'no tool'} · calls: {calls} · "
            f"turns: {turns} · parameters: {flags}")


def _case_summary(text: str) -> str:
    """The case file cut to what a reader needs; the checks go in a table of their own."""
    import yaml

    try:
        case = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return text
    keep = ["case_id", "provenance", "function", "user_profile", "goal", "opening_turn", "scoring_criteria"]
    return yaml.safe_dump({k: case[k] for k in keep if k in case}, sort_keys=False, allow_unicode=True, width=100)


def _bound(value: Any) -> str:
    """A count bound as a reader writes it: ``1–4``, ``≥ 1``, ``≤ 2``, ``0``."""
    if isinstance(value, dict) and set(value) <= {"min", "max"}:
        lo, hi = value.get("min"), value.get("max")
        if lo is not None and hi is not None:
            return str(lo) if lo == hi else f"{lo}–{hi}"
        return f"≥ {lo}" if lo is not None else f"≤ {hi}"
    return _expect(value)


def _expect(value: Any) -> str:
    """Any check value in one line."""
    if isinstance(value, dict):
        if set(value) <= {"min", "max"}:
            return _bound(value)
        # A plain key reads as words; a table.OP key keeps its spelling.
        word = lambda k: k if "." in k else k.replace("_", " ")
        return "; ".join(f"{word(k)} {_expect(v)}" if not isinstance(v, bool)
                         else (word(k) if v else f"not {word(k)}")
                         for k, v in value.items() if v is not None)
    if isinstance(value, list):
        return "–".join(map(str, value)) if len(value) == 2 and all(":" in str(v) for v in value) \
            else ", ".join(map(str, value))
    if value is True:
        return "yes"
    return str(value)


def case_checks(text: str) -> list[Row]:
    """The case's asserted checks as rows: check | what it expects. Null checks
    are not asserted and are left out; count checks list one bound per key."""
    import yaml

    try:
        case = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return []
    checks = ((case.get("declared_constraints") or {}).get("checks") or {})
    rows = []
    for key, value in checks.items():
        if value is None:
            continue
        if key in ("tool_counts", "mutation_counts", "edits") and isinstance(value, dict):
            text_ = ", ".join(f"{k} {_bound(v)}" for k, v in value.items())
        else:
            text_ = _expect(value)
        rows.append({"check": key, "what it expects": text_})
    return rows


def _day(ts: Any) -> str:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return "–"


# --- rendering -------------------------------------------------------------------

CSS = """
:root { --ink:#0b0b0b; --muted:#6b6a66; --line:#e2e1dc; --band:#f4f3f0; --accent:#2a78d6; --warn:#8a5a00; }
* { box-sizing: border-box; }
body { font: 10pt/1.45 "Segoe UI", system-ui, sans-serif; color: var(--ink); background: #fff; margin: 0; padding: 24px 16px; }
main { max-width: 900px; margin: 0 auto; }
h1 { font-size: 16pt; margin: 0 0 2px; } .sub { color: var(--muted); margin: 0 0 12px; }
.warn { border-left: 3px solid var(--warn); padding: 6px 10px; background: #fbf6ec; color: var(--warn); margin: 10px 0; }
.legend { color: var(--muted); font-size: 8.5pt; margin-bottom: 16px; }
h2.level { font-size: 9pt; text-transform: uppercase; letter-spacing: .06em; color: var(--accent); margin: 26px 0 4px;
           border-bottom: 1px solid var(--line); padding-bottom: 3px; }
section { margin: 10px 0 16px; break-inside: avoid; page-break-inside: avoid; }
h3 { font-size: 11pt; margin: 0 0 2px; } .note { color: var(--muted); font-size: 8.5pt; margin: 0 0 6px; }
table { border-collapse: collapse; width: 100%; font-size: 8.5pt; }
th, td { border-bottom: 1px solid var(--line); padding: 3px 6px; text-align: left; vertical-align: top; }
th { background: var(--band); font-weight: 600; }
td.k { width: 30%; font-family: Consolas, monospace; white-space: nowrap; }
td.k.em::after { content: " ●"; color: var(--accent); }
td.null { color: var(--muted); font-style: italic; }
pre, code { font-family: Consolas, monospace; font-size: 8pt; white-space: pre-wrap; word-break: break-word; margin: 0; }
pre.block { background: var(--band); padding: 8px; }
.msg { border-left: 3px solid var(--line); padding: 4px 10px; margin: 6px 0; white-space: pre-wrap; }
.msg.tonic { border-color: var(--accent); background: #f6f9fe; }
.who { font-weight: 600; font-size: 8.5pt; } .meta { color: var(--muted); font-size: 8pt; }
.empty { color: var(--muted); font-style: italic; }
.guide { display: block; border: 1px solid var(--line); border-left: 3px solid var(--accent); background: #f6f9fe;
         padding: 6px 10px; margin: 8px 0 6px; font-size: 9pt; break-inside: avoid; page-break-inside: avoid; }
@media print { body { padding: 0; } @page { size: A4; margin: 16mm 14mm; } h2.level { break-after: avoid; } }
"""


def _cell(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return f"<pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=1))}</pre>"
    return html.escape(str(value))


def _render_section(s: Section, names: set[str]) -> str:
    if s.kind == "guide":
        return f"<aside class=guide><b>How to read this.</b> {_md(s.body)}</aside>"
    head = f"<section><h3>{html.escape(s.title)}</h3>" + (f"<p class=note>{_md(s.note)}</p>" if s.note else "")
    if s.body is None or (isinstance(s.body, (list, dict, str)) and not s.body):
        return head + "<p class=empty>nothing recorded</p></section>"
    if s.kind == "record":
        rows = "".join(
            f"<tr><td class='k{' em' if k in names else ''}'>{html.escape(k)}</td>"
            f"<td class='{'null' if v is None else ''}'>{_cell(v)}</td></tr>" for k, v in s.body.items())
        return head + f"<table>{rows}</table></section>"
    if s.kind == "table":
        cols = list(dict.fromkeys(k for r in s.body for k in r))
        header = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
        body = "".join("<tr>" + "".join(f"<td class='{'null' if r.get(c) is None else ''}'>{_cell(r.get(c))}</td>"
                                        for c in cols) + "</tr>" for r in s.body)
        return head + f"<table><tr>{header}</tr>{body}</table></section>"
    if s.kind == "chat":
        msgs = "".join(
            f"<div class='msg{' tonic' if m['who'].startswith('Tonic') else ''}'><span class=who>{html.escape(m['who'])}"
            f" · turn {m['turn']}</span>{('  <span class=meta>' + html.escape(m['meta']) + '</span>') if m.get('meta') else ''}"
            f"\n{html.escape(m['text'])}</div>" for m in s.body)
        return head + msgs + "</section>"
    return head + f"<pre class=block>{html.escape(str(s.body))}</pre></section>"


def _md(text: str) -> str:
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(text))


def render(example: Example, pseudonyms: Optional[Pseudonyms] = None) -> str:
    ps = pseudonyms or Pseudonyms()
    names = event_model_names()
    parts, level = [], None
    for s in example.sections:
        s = Section(s.title, s.kind, ps(s.body), s.note, s.level, s.role, s.turn)
        if s.level != level:
            parts.append(f"<h2 class=level>{html.escape(s.level)}</h2>")
            level = s.level
        parts.append(_render_section(s, names))
    warning = f"<p class=warn>{html.escape(example.warning)}</p>" if example.warning else ""
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{html.escape(example.title)}</title>"
            f"<meta name=viewport content='width=device-width, initial-scale=1'><style>{CSS}</style></head><body><main>"
            f"<h1>{html.escape(example.title)}</h1><p class=sub>{html.escape(example.subtitle)}</p>{warning}"
            f"<p class=legend>● = a field of <code>docs/event-model.md</code>; unmarked = instrumentation column. "
            f"Ids are replaced by stable tokens. <i>null</i> = not recorded for this unit.</p>"
            + "".join(parts) + "</main></body></html>")
