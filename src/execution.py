"""One execution, assembled from what the application recorded (B08).

The object the structural checker evaluates and the predicates compare. It is
built from the study tables rather than from anything the harness held in
memory, so a verdict can be recomputed from the record months later — which is
the whole reason D38 stopped the reset deleting it.

Where each part comes from, stated because two of them are not where a reader
would first look:

``trace``       every turn's tool entries, in order, each tagged with its turn.
                ``study_suggestions.tool_call_trace``, filtered to
                ``kind == 'tool'`` — the trace interleaves the agent's LLM
                steps with its tool calls and both matter, but only the tool
                entries are a check's business.
``place_ids``   the Google ids the replies named, read from
                ``chat_messages.metadata.refs[].googlePlaceId``. **Not** from
                the trace, which records a tool result's size and not its
                content, and not from ``resulting_state_shape.reply
                .place_refs``, which is a count. The ids exist nowhere else in
                the record, so the metamorphic predicates that compare venue
                sets depend on the reply row surviving the run.
``mutations``   ``study_mutations`` for the trip, minus the fixture build's own
                rows (``build_mutation_ids``), because since D38 the build's
                writes sit on the trip beside the case's.
``drafts``      the ``propose_plan`` calls' **arguments**, not the state
                shape's draft, which carries counts and no dates or times.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src import db


@dataclass
class Execution:
    """What one repetition did, as the record has it."""

    case_id: str
    repetition: int
    #: Ordered ``study_suggestions`` rows — one per agent turn.
    turns: list[dict] = field(default_factory=list)
    #: Every tool call across the turns, in order, each carrying ``turn_index``.
    trace: list[dict] = field(default_factory=list)
    #: The case's own mutation rows, build excluded.
    mutations: list[dict] = field(default_factory=list)
    #: Arguments of every ``propose_plan`` call, in order. The last is the plan
    #: the member was left with, which is what the draft checks read.
    drafts: list[dict] = field(default_factory=list)
    #: Google place ids the replies referenced, across the turns.
    place_ids: set[str] = field(default_factory=set)
    #: Title → id, as this repetition's fixture build created them (D26).
    blocks: dict[str, str] = field(default_factory=dict)
    #: The whole ``fixture_ids`` map: trip, regions, blocks, days, slots.
    fixture_ids: dict = field(default_factory=dict)
    #: The seed's execution, for a metamorphic follow-up (D27). None otherwise.
    base: Optional["Execution"] = None
    #: Recorded, never asserted (D37, Q22): a case may not bound these.
    telemetry: dict = field(default_factory=dict)

    @property
    def latest_draft(self) -> Optional[dict]:
        return self.drafts[-1] if self.drafts else None

    def tool_calls(self, name: Optional[str] = None) -> list[dict]:
        return [c for c in self.trace if name is None or c.get("tool") == name]

    def tool_sequence(self) -> list[str]:
        return [c["tool"] for c in self.trace]

    def error_codes(self) -> list[str]:
        return [t["error_code"] for t in self.turns if t.get("error_code")]

    def state_shapes(self) -> list[dict]:
        return [t.get("resulting_state_shape") or {} for t in self.turns]


def _place_ids_of(metadata: Optional[dict]) -> set[str]:
    refs = (metadata or {}).get("refs") or []
    return {
        r["googlePlaceId"]
        for r in refs
        if isinstance(r, dict) and r.get("type") == "place" and r.get("googlePlaceId")
    }


def _telemetry_of(turns: list[dict]) -> dict:
    """The five signals D37 records and forbids a case to bound (Q22).

    Summed where summing is meaningful and taken at the maximum for the reply
    length, since a closing sign-off is short and says nothing about whether
    the answer was.
    """
    shapes = [t.get("resulting_state_shape") or {} for t in turns]
    return {
        "turns": len(turns),
        "llm_calls": sum(t.get("llm_calls") or 0 for t in turns),
        "tool_calls": sum(t.get("tool_calls") or 0 for t in turns),
        "latency_ms": sum(t.get("latency_ms") or 0 for t in turns),
        "tokens_input": sum(t.get("tokens_input") or 0 for t in turns),
        "tokens_output": sum(t.get("tokens_output") or 0 for t in turns),
        "retry_count": sum(t.get("retry_count") or 0 for t in turns),
        "reply_chars_max": max((s.get("reply", {}).get("chars") or 0 for s in shapes), default=0),
    }


def load(execution_row: dict, base: Optional[Execution] = None) -> Execution:
    """Assemble one execution from its ``study_case_executions`` row."""
    a = db.admin()
    ids = execution_row.get("suggestion_ids") or []
    turns = (
        a.table("study_suggestions")
        .select(
            "id, turn_index, request_type, agent_intent, error_code, latency_ms, llm_calls, "
            "tool_calls, retry_count, tokens_input, tokens_output, model_version, "
            "tool_call_trace, resulting_state_shape, reply_message_id, user_turn"
        )
        .in_("id", ids)
        .order("turn_index")
        .execute()
        .data
        if ids
        else []
    )

    trace: list[dict] = []
    drafts: list[dict] = []
    for turn in turns:
        for entry in turn.get("tool_call_trace") or []:
            if entry.get("kind") != "tool":
                continue
            call = {**entry, "turn_index": turn.get("turn_index")}
            trace.append(call)
            if call.get("tool") == "propose_plan" and not call.get("result_error"):
                drafts.append(call.get("args") or {})

    reply_ids = [t["reply_message_id"] for t in turns if t.get("reply_message_id")]
    place_ids: set[str] = set()
    if reply_ids:
        for row in a.table("chat_messages").select("id, metadata").in_("id", reply_ids).execute().data:
            place_ids |= _place_ids_of(row.get("metadata"))

    build = set(execution_row.get("build_mutation_ids") or [])
    mutations = [
        m
        for m in a.table("study_mutations")
        .select("id, table_name, op, origin_kind, origin_suggestion_id, changed_keys, projection, row_id")
        .eq("trip_id", execution_row.get("trip_id"))
        .order("occurred_at")
        .execute()
        .data
        if m["id"] not in build
    ]

    fixture_ids = execution_row.get("fixture_ids") or {}
    return Execution(
        case_id=execution_row["case_id"],
        repetition=execution_row["repetition"],
        turns=turns,
        trace=trace,
        mutations=mutations,
        drafts=drafts,
        place_ids=place_ids,
        blocks=dict(fixture_ids.get("blocks") or {}),
        fixture_ids=fixture_ids,
        base=base,
        telemetry=_telemetry_of(turns),
    )


def as_mapping(execution: Execution) -> dict[str, Any]:
    """The shape ``cases/predicates.py`` documents as its contract."""
    return {
        "trace": [{**c, "kind": "tool"} for c in execution.trace],
        "mutations": execution.mutations,
        "drafts": execution.drafts,
        "place_ids": sorted(execution.place_ids),
        "blocks": execution.blocks,
        "base": as_mapping(execution.base) if execution.base else None,
    }
