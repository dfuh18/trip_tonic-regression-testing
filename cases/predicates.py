"""Sequence-dependent constraints (D19): the half that cannot be declared.

Each public function is a predicate a case may name under
``declared_constraints.predicates``. It receives the recorded execution and
returns ``None`` when satisfied or a short finding string when not — the
structural checker (B08) turns a finding into ``detected``.

The execution object is the checker's view of one case run: its ordered
``trace`` (the tool-call entries of every turn, in order), its ``mutations``
(study_mutations rows), its ``drafts`` (the resulting_state_shape ``draft``
objects) and, for metamorphic follow-ups, the ``base`` execution it is
compared against. Keep predicates small and named for what they assert.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence


def search_before_draft(execution: Mapping[str, Any]) -> Optional[str]:
    """A plan grounded in real venues searches before it drafts (P5)."""
    tools = [e["tool"] for e in execution["trace"] if e.get("kind") == "tool"]
    if "propose_plan" not in tools:
        return None
    first_draft = tools.index("propose_plan")
    if "search_places" not in tools[:first_draft]:
        return "propose_plan was called before any search_places"
    return None


def no_tool_errors(execution: Mapping[str, Any]) -> Optional[str]:
    """Every tool the turn relied on returned without an error (D11)."""
    failed = [e["tool"] for e in execution["trace"] if e.get("kind") == "tool" and e.get("result_error")]
    return f"tool errors: {', '.join(failed)}" if failed else None


def same_venues_as_base(execution: Mapping[str, Any]) -> Optional[str]:
    """INV relations: the follow-up surfaces the same places as its seed."""
    base = execution.get("base")
    if not base:
        return "no base execution to compare against"
    mine = _place_ids(execution["trace"])
    theirs = _place_ids(base["trace"])
    if mine != theirs:
        return f"venues differ from the base case ({len(mine ^ theirs)} not shared)"
    return None


def different_venues_from_base(execution: Mapping[str, Any]) -> Optional[str]:
    """DIR-1 / DIR-4: a changed constraint changes what is found."""
    base = execution.get("base")
    if not base:
        return "no base execution to compare against"
    if _place_ids(execution["trace"]) == _place_ids(base["trace"]):
        return "venues identical to the base case despite the changed constraint"
    return None


def _place_ids(trace: Sequence[Mapping[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for entry in trace:
        if entry.get("kind") != "tool":
            continue
        for place in (entry.get("result_places") or []):
            if place.get("googlePlaceId"):
                ids.add(place["googlePlaceId"])
    return ids
