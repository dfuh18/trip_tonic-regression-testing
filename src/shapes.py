"""Request shape — candidate rules, side by side (Q28).

A request shape sits between the two labels the study already has:
``request_type`` (D09: four classes, one per function of §1.4) is too coarse to
say *where* the participants' uncovered turns concentrate, and the coverage
signature (D24: exact tool sequence plus buckets) is too fine to carry a
per-class failure rate. A shape is meant to be the level in between: a class
per thing the agent *did*, read off ``tool_call_trace``.

The author chose ``shapes7`` (D99), with ``advisory`` meaning a turn that
called no acting tool (D105). The other candidates stay computable as
secondary views, the way D09 keeps the composite derivable. Each rule is a
pure function of the tool names a turn called:

* ``d09``        — D09's precedence, re-derived here so the four rules are
  computed by the same code path over the same input (the app's own label is
  ``study_suggestions.request_type``; the notebook checks the two agree).
* ``shapes7``    — seven shapes plus ``other``.
* ``shapes9``    — ``shapes7`` with the live edit split into move / place /
  remove.
* ``families``   — Q08's rejected option (b): the set of D09 families, joined.

Two rules are shared by ``shapes7`` and ``shapes9`` and are the substance of
the proposal:

1. **A turn is one shape or it is ``other``.** No precedence. A precedence
   decides silently which half of a mixed turn counts, and the mixed turn is
   exactly the kind of thing the participants may do and the suite does not.
   ``other`` is reported, not tidied away.
2. **One exception: a search that feeds a draft is the draft.** A grounded
   plan is ``search_places`` then ``propose_plan``; that is the suite's own
   ``scheduling_belem_morning`` shape, not a mix of two requests.

Reading the trip (``get_trip_details``, ``list_trip_blocks``,
``get_itinerary``) is context, not a shape, and is ignored by every rule. A
tool the rules do not know is ``other`` rather than guessed at: a new agent
tool must be a visible change to ``REQUEST_SHAPE_RULE_VERSION``, the same
reasoning ``agent.request-type.ts`` gives for writing its names out.

Pure and deterministic, no I/O, like ``src.signature``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

#: Bump when any rule below changes. Labels computed under different versions
#: are not comparable.
REQUEST_SHAPE_RULE_VERSION = "1"  # frozen 2026-10-01 (D112)

READ_TOOLS = frozenset({"get_trip_details", "list_trip_blocks", "get_itinerary"})

ADVISORY = "advisory"
OTHER = "other"

#: The finest reading: one shape per distinct thing a tool does. ``shapes7``
#: is this with the three live edits merged.
_TOOL_SHAPE_9: dict[str, str] = {
    "propose_plan": "scheduling.draft",
    "move_slot": "scheduling.move",
    "schedule_block": "scheduling.place",
    "unschedule_block": "scheduling.remove",
    "search_places": "venue.search",
    "get_weather": "factual.forecast",
    "get_climate_normals": "factual.climate",
    "get_region_climate": "factual.climate",
    "read_wikipedia": "factual.reference",
}

_EDIT_MERGE = {
    "scheduling.move": "scheduling.edit",
    "scheduling.place": "scheduling.edit",
    "scheduling.remove": "scheduling.edit",
}

#: D09's families, written out for the same reason as above.
_D09_FAMILY: dict[str, str] = {
    "propose_plan": "scheduling",
    "move_slot": "scheduling",
    "schedule_block": "scheduling",
    "unschedule_block": "scheduling",
    "search_places": "venue_lookup",
    "get_weather": "factual_qa",
    "get_climate_normals": "factual_qa",
    "get_region_climate": "factual_qa",
    "read_wikipedia": "factual_qa",
}
_D09_PRECEDENCE = ("scheduling", "venue_lookup", "factual_qa")


def tools_of(trace: Sequence[Mapping[str, Any]]) -> list[str]:
    """The tool names in a ``tool_call_trace``, in ``seq`` order.

    The trace interleaves ``kind: llm`` entries (one per model call) with
    ``kind: tool`` entries; only the latter name a tool.
    """
    ordered = sorted(trace, key=lambda entry: entry.get("seq", 0))
    return [str(e["tool"]) for e in ordered if e.get("kind", "tool") == "tool" and e.get("tool")]


def _acting(tools: Iterable[str]) -> set[str]:
    return {t for t in tools if t not in READ_TOOLS}


def _one_shape(tools: Iterable[str], table: Mapping[str, str]) -> str:
    acting = _acting(tools)
    if any(t not in table for t in acting):
        return OTHER
    shapes = {table[t] for t in acting}
    if "scheduling.draft" in shapes:
        shapes.discard("venue.search")
    if not shapes:
        return ADVISORY
    return shapes.pop() if len(shapes) == 1 else OTHER


def shapes9(tools: Iterable[str]) -> str:
    return _one_shape(tools, _TOOL_SHAPE_9)


def shapes7(tools: Iterable[str]) -> str:
    return _one_shape(tools, {t: _EDIT_MERGE.get(s, s) for t, s in _TOOL_SHAPE_9.items()})


def d09(tools: Iterable[str]) -> str:
    """D09 as ``agent.request-type.ts`` states it: a precedence, advisory as
    the fall-through (including a turn that only read the trip)."""
    present = {_D09_FAMILY[t] for t in tools if t in _D09_FAMILY}
    return next((f for f in _D09_PRECEDENCE if f in present), ADVISORY)


def families(tools: Iterable[str]) -> str:
    present = {_D09_FAMILY[t] for t in tools if t in _D09_FAMILY}
    return "+".join(sorted(present)) or ADVISORY


RULES: dict[str, Callable[[Iterable[str]], str]] = {
    "d09": d09,
    "shapes7": shapes7,
    "shapes9": shapes9,
    "families": families,
}


def interaction_label(turn_labels: Sequence[str]) -> str:
    """One label for a multi-turn interaction, from its turns' labels.

    Not the rule in force: D106 labels a request by shapes7 over the union of
    its turns' tools (``analysis.interaction_shape``). Kept because
    ``sim/07_shapes`` and ``study/05b_pilot_shapes`` use it, as the record of
    how D99 was decided.

    A closing "no thanks" turn calls nothing and would read as ``advisory``;
    it says nothing about what the interaction was, so ``advisory`` turns only
    count when every turn is one. Two different acting labels are ``other``,
    by the same rule as within a turn.
    """
    acting = {label for label in turn_labels if label != ADVISORY}
    if not acting:
        return ADVISORY
    return acting.pop() if len(acting) == 1 else OTHER


def declared_label(required: Iterable[str], any_of: Iterable[frozenset[str]], rule: str) -> str:
    """The label a case's *declarations* imply under ``rule``.

    ``required`` is ``coverage.tools_required_by(case)``; each ``any_of`` group
    contributes one member, which is only sound when every member of the group
    maps to the same label — asserted, because a group that straddles two
    shapes would make the expected label depend on which member was picked.
    """
    fn = RULES[rule]
    tools = set(required)
    for group in any_of:
        labels = {fn([t]) for t in group}
        assert len(labels) == 1, f"any_of group {sorted(group)} straddles {sorted(labels)} under {rule}"
        tools.add(min(group))
    return fn(sorted(tools))


def segment(turn_labels: Sequence[str]) -> list[list[int]]:
    """Split one run's turns into requests (Q29, option C) — candidate rule.

    ``turn_labels`` are one rule's labels for a run's turns, in ``turn_index``
    order. Returns the turn positions of each request.

    A request ends where the next acting turn has a different label. A turn
    that called nothing ("thanks", "yes do it", an answer to the agent's
    question) joins the request before it; only a run that opens with such
    turns gives them a request of their own. Two consecutive requests of the
    same label are therefore indistinguishable — the rule's known blind spot,
    measured in ``07_shapes``.
    """
    segments: list[list[int]] = []
    current: str | None = None  # the open request's acting label, if any yet
    for i, label in enumerate(turn_labels):
        if segments and (label == ADVISORY or label == current):
            segments[-1].append(i)
        else:
            segments.append([i])
            current = None if label == ADVISORY else label
    return segments


# --- request boundaries with more than the shape (Q29) ---------------------

#: Argument keys whose values name a thing on the trip or a found place. A
#: turn acting on one of these is acting on something specific.
_ID_KEYS = frozenset({"google_place_id", "place_id", "reuse_block_id", "block_id", "slot_id"})
#: The application abbreviates block ids to their first eight characters in
#: tool arguments (``block_id: 'bc224bfd'``), so ids match by prefix.
_MIN_ID_PREFIX = 8


@dataclass(frozen=True)
class TurnSignals:
    """What one turn offers the boundary rule, all read from the record.

    ``label``    this turn's shape under the chosen rule.
    ``intent``   ``study_suggestions.agent_intent`` — the slash command, or None.
    ``acted_on`` ids in the arguments of this turn's acting tools.
    ``offered``  ids this turn put in front of the member or touched: its
                 reply's place refs (``chat_messages.metadata.refs``) and the
                 ids in all of its tool arguments.
    """

    label: str
    intent: Optional[str] = None
    acted_on: frozenset = frozenset()
    offered: frozenset = frozenset()


def _ids_in(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in _ID_KEYS and isinstance(nested, str) and nested:
                found.add(nested)
            else:
                found |= _ids_in(nested)
    elif isinstance(value, (list, tuple)):
        for item in value:
            found |= _ids_in(item)
    return found


def signals_of(
    trace: Sequence[Mapping[str, Any]],
    reply_place_ids: Iterable[str],
    intent: Optional[str],
    rule: Callable[[Iterable[str]], str] = None,
) -> TurnSignals:
    """Assemble one turn's signals from its trace, its reply's place ids and
    its stored intent. Pure: the loader does the reading."""
    rule = rule or shapes7
    tools = [e for e in trace if e.get("kind", "tool") == "tool" and e.get("tool")]
    acting = [e for e in tools if e["tool"] not in READ_TOOLS]
    return TurnSignals(
        label=rule([str(e["tool"]) for e in tools]),
        intent=intent or None,
        acted_on=frozenset(i for e in acting for i in _ids_in(e.get("args") or {})),
        offered=frozenset(set(reply_place_ids) | {i for e in tools for i in _ids_in(e.get("args") or {})}),
    )


def _same_id(a: str, b: str) -> bool:
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= _MIN_ID_PREFIX and long_.startswith(short)


def _continues(acted_on: frozenset, offered: set[str]) -> bool:
    return any(_same_id(a, o) for a in acted_on for o in offered)


def segment_with(
    turns: Sequence[TurnSignals], *, use_intent: bool = True, use_reference: bool = True
) -> list[list[int]]:
    """Split one run's turns into requests, using up to three signals (Q29).

    For each turn after the first, the first rule that applies decides:

    1. **Reference** (``use_reference``) — the turn acts on an id that a turn
       of the *current* request offered or touched: it continues that
       request, whatever its shape or command. "Add the second one" drafts a
       place the search just returned.
    2. **Slash** (``use_intent``) — the turn carries a slash command: the
       member started something, so a new request begins.
    3. **Shape** — ``segment``'s rule: a new request where the acting shape
       changes, and a turn that called nothing joins the one before.

    Reference outranks the slash because a member may use a command to
    continue ("/plan put the second one on Saturday"), and acting on what the
    request just offered is direct evidence where a command is only a
    keystroke. Both signals are optional: the agent reaches every path
    without a command, so a slash is evidence when present and says nothing
    when absent. With both switched off this is ``segment`` exactly.

    Causal: a turn's request is decided from it and the turns before it,
    never later ones, so the same function labels a run turn by turn as it
    happens and in one pass afterwards, with identical results.
    """
    segments: list[list[int]] = []
    current: Optional[str] = None
    offered: set[str] = set()
    for i, turn in enumerate(turns):
        if not segments:
            new = True
        elif use_reference and _continues(turn.acted_on, offered):
            new = False
        elif use_intent and turn.intent:
            new = True
        else:
            new = not (turn.label == ADVISORY or turn.label == current)
        if new:
            segments.append([i])
            current, offered = None, set()
        else:
            segments[-1].append(i)
        # The request's shape is its latest acting turn's: after "add the
        # second one" joins a search by reference, a revised draft is still
        # the same request.
        if turn.label != ADVISORY:
            current = turn.label
        offered |= turn.offered
    return segments
