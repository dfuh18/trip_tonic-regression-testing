"""Sequence-dependent constraints (D19): the half that cannot be declared.

Each public function is a predicate a case may name under
``declared_constraints.predicates``. It receives the recorded execution and
returns ``None`` when satisfied or a short finding string when not — the
structural checker (B08) turns a finding into ``detected``.

The execution object is the checker's view of one case run: its ordered
``trace`` (the tool-call entries of every turn, in order), its ``mutations``
(study_mutations rows), its ``drafts`` (the resulting_state_shape ``draft``
objects), its ``place_ids`` (the Google ids of every place the replies named,
from the reply messages' refs), its ``blocks`` (the trip's block ids mapped to
titles, so a mutation can be read back to the stop it touched) and, for
metamorphic follow-ups, the ``base`` execution it is compared against. Keep predicates small and named for what they assert.
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
    mine = _place_ids(execution)
    theirs = _place_ids(base)
    if mine != theirs:
        return f"venues differ from the base case ({len(mine ^ theirs)} not shared)"
    return None


def different_venues_from_base(execution: Mapping[str, Any]) -> Optional[str]:
    """DIR-1 / DIR-4: a changed constraint changes what is found."""
    base = execution.get("base")
    if not base:
        return "no base execution to compare against"
    if _place_ids(execution) == _place_ids(base):
        return "venues identical to the base case despite the changed constraint"
    return None


def surfaced_real_places(execution: Mapping[str, Any]) -> Optional[str]:
    """A venue lookup returned at least one Google place (P4: grounded, not recalled)."""
    return None if _place_ids(execution) else "no search_places result carried a Google place id"


def used_a_reference_tool(execution: Mapping[str, Any]) -> Optional[str]:
    """A factual answer came from a reference tool, not from the model's memory."""
    tools = {e["tool"] for e in execution["trace"] if e.get("kind") == "tool"}
    if tools & {"read_wikipedia", "get_region_climate", "get_climate_normals", "get_weather"}:
        return None
    return "no reference tool was called"


def tram_landed_on_saturday_afternoon(execution: Mapping[str, Any]) -> Optional[str]:
    """scheduling_move_tram: the tram's own slot sits on 2026-11-07 at 16:00.

    The stop is checked, not only the window: an update that moved *something*
    to Saturday afternoon is not this case passing. ``blocks`` maps the trip's
    block ids to titles and is assembled by the checker (B08); without it this
    predicate says so rather than passing on the weaker test.
    """
    blocks = execution.get("blocks")
    if not blocks:
        return "cannot tell which stop moved: the execution carries no block titles"
    for m in execution.get("mutations", []):
        proj = m.get("projection") or {}
        if m.get("table_name") != "itinerary_slots" or m.get("op") != "UPDATE":
            continue
        title = blocks.get(proj.get("trip_block_id"))
        if (title == "Tram 28 ride through Alfama"
                and proj.get("day_date") == "2026-11-07"
                and str(proj.get("start_time", "")).startswith("16:00")):
            return None
    return "the Tram 28 ride did not land on 2026-11-07 at 16:00"


def _place_ids(execution: Mapping[str, Any]) -> set[str]:
    """Google place ids the replies named, from the place refs on the reply
    messages (the trace keeps tool results as size and error only)."""
    return set(execution.get("place_ids") or [])
