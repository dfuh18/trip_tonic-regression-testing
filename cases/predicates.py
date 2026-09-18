"""Predicates: the constraints a schema cannot state (D19, D27).

A declarative check describes **one** execution — which tools ran, how often,
what the draft looked like, what the database recorded — and
``src/cases.py``'s ``Checks`` carries all of those. What it cannot describe is
a relation **between** executions, which is exactly what a metamorphic
follow-up asserts: the same venues as its seed, or deliberately different ones.
Those live here, as named functions a case references by name.

That is the whole of the split. It is not about where the data comes from —
checks and predicates read the same recorded execution — but about arity: one
execution can be described, two must be compared, and a comparison needs the
other execution in hand.

Each function takes the checker's execution object and returns ``None`` when
satisfied or a short finding when not. The execution carries: ``trace`` (every
turn's tool-call entries in order), ``mutations`` (the study_mutations rows),
``drafts`` (the ``resulting_state_shape`` draft objects), ``place_ids`` (the
Google ids the replies named), ``blocks`` (the ids this repetition's fixture
rebuild produced, mapped to titles — D26; a row the case itself created is not
in the map and is identified by its own projection) and ``base`` (the seed's
execution, for a metamorphic follow-up).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


def same_venues_as_base(execution: Mapping[str, Any]) -> Optional[str]:
    """INV relations: rewording the request does not change what is found."""
    base = execution.get("base")
    if not base:
        return "no base execution to compare against"
    mine, theirs = _place_ids(execution), _place_ids(base)
    if mine != theirs:
        return f"venues differ from the base case ({len(mine ^ theirs)} not shared)"
    return None


def different_venues_from_base(execution: Mapping[str, Any]) -> Optional[str]:
    """DIR relations: changing a constraint changes what is found."""
    base = execution.get("base")
    if not base:
        return "no base execution to compare against"
    if _place_ids(execution) == _place_ids(base):
        return "venues identical to the base case despite the changed constraint"
    return None


def same_tool_sequence_as_base(execution: Mapping[str, Any]) -> Optional[str]:
    """INV relations: the execution path is the same shape as the seed's."""
    base = execution.get("base")
    if not base:
        return "no base execution to compare against"
    mine, theirs = _tools(execution), _tools(base)
    if mine != theirs:
        return f"tool sequence {mine} differs from the base case's {theirs}"
    return None


def _place_ids(execution: Mapping[str, Any]) -> set[str]:
    return set(execution.get("place_ids") or [])


def _tools(execution: Mapping[str, Any]) -> list[str]:
    ordered = [e["tool"] for e in execution.get("trace", []) if e.get("kind") == "tool"]
    collapsed: list[str] = []
    for tool in ordered:
        if not collapsed or collapsed[-1] != tool:
            collapsed.append(tool)
    return collapsed
