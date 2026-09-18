"""The coverage signature (P1).

A signature is the shape of one interaction, coarse enough that two members
asking for the same thing in different words land on the same value, fine
enough that "uncovered" names a real shape rather than a rewording (D24). It is
what the coverage proportion in section 4.3 is computed over: the simulated
suite's signatures against the participants'.

The rule is versioned. ``SIGNATURE_RULE_VERSION`` is recorded beside every
result that was computed with it, because changing the rule changes the
coverage number and the two are only comparable within one version.

Pure and deterministic: no I/O, no clock, no configuration. Nothing here reads
``src.config``, so a signature can be computed over stored traces without the
environment the harness needs.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence, Tuple

#: Bump when any rule below changes. Results computed under different versions
#: are not comparable.
SIGNATURE_RULE_VERSION = "1"

Bucket = str
Signature = Tuple[str, Tuple[str, ...], Tuple[Tuple[str, Bucket], ...], Bucket, Tuple[bool, bool, bool, bool]]

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PRICE_RE = re.compile(r"cheap|budget|expensive|€|\$|price|affordable|luxury")
_DIETARY_RE = re.compile(r"vegan|vegetarian|gluten|halal|kosher|dairy|allerg")


def _bucket(n: int) -> Bucket:
    """``{1, 2, 3+}`` — the only cardinalities D24 distinguishes."""
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    return "3+"


def _ordered(trace: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The trace in ``seq`` order. A trace is written ordered; sorting makes
    the signature independent of how it was read back."""
    return sorted(trace, key=lambda entry: entry.get("seq", 0))


def _arg_keys(value: Any) -> set[str]:
    """Every mapping key in an ``args`` value, at any depth.

    Tool arguments nest: ``propose_plan`` carries ``day_date`` and a block's
    ``address`` several levels down, and reading only the top level would make
    the ``day_date``-free clause below unreachable for the one tool that can
    trigger it.
    """
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            keys.add(str(key))
            keys |= _arg_keys(nested)
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys |= _arg_keys(item)
    return keys


def _arg_values(value: Any) -> Iterable[str]:
    """Every scalar inside an ``args`` value, as text."""
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _arg_values(nested)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _arg_values(item)
    elif value is not None:
        yield str(value)


def _has_location(entries: Sequence[Mapping[str, Any]]) -> bool:
    """A call that names a place: coordinates, or an address outside a plan.

    ``day_date`` marks the call as a proposed itinerary rather than a lookup,
    and the addresses inside one are the agent's own output, not a location the
    member asked about.
    """
    for entry in entries:
        keys = _arg_keys(entry.get("args") or {})
        if "lat" in keys and "lng" in keys:
            return True
        if "address" in keys and "day_date" not in keys:
            return True
    return False


def _args_text(entries: Sequence[Mapping[str, Any]]) -> str:
    """All argument values of the whole trace as one lower-case haystack.

    Joined by a newline so two adjacent values cannot form a match that is in
    neither of them.
    """
    parts: list[str] = []
    for entry in entries:
        parts.extend(_arg_values(entry.get("args") or {}))
    return "\n".join(parts).lower()


def signature(
    trace: Sequence[Mapping[str, Any]],
    turns: int,
    request_type: str,
) -> Signature:
    """The coverage signature of one interaction (D24).

    ``trace`` is the ``tool_call_trace`` array of a ``study_suggestions`` row —
    entries carrying at least ``seq``, ``tool`` and ``args``. ``turns`` is the
    number of member turns in the interaction, ``request_type`` the label the
    A03 classifier gave it.

    Returns ``(request_type, sequence, counts, turn_bucket, params)``:

    * ``sequence`` — the tools in ``seq`` order, consecutive repeats collapsed
      (``a a b a`` → ``a b a``), matched exactly;
    * ``counts`` — ``(tool, bucket)`` per distinct tool, sorted, bucket from
      that tool's number of calls;
    * ``turn_bucket`` — the same bucketing over ``turns``;
    * ``params`` — ``(has_location, has_date, has_price_term,
      has_dietary_term)`` over the trace's arguments.
    """
    entries = _ordered(trace)
    tools = [str(entry["tool"]) for entry in entries]

    sequence: list[str] = []
    for tool in tools:
        if not sequence or sequence[-1] != tool:
            sequence.append(tool)

    counts = tuple(
        sorted((tool, _bucket(tools.count(tool))) for tool in set(tools))
    )

    text = _args_text(entries)
    params = (
        _has_location(entries),
        bool(_DATE_RE.search(text)),
        bool(_PRICE_RE.search(text)),
        bool(_DIETARY_RE.search(text)),
    )

    return (request_type, tuple(sequence), counts, _bucket(turns), params)
