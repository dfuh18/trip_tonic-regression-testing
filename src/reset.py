"""State reset and the precondition gate (B02; invariant 1; D03).

Every repetition begins from the fixture. ``reset`` returns a fixture trip to
that state; ``assert_clean`` refuses to let a run start on a trip that is not
in it. The refusal is recorded — one line in ``runs/harness.log`` — because
"the harness refused" must stay distinguishable from "nobody ran it", but it
is not a run field: a run that proceeded would always carry ``true`` (D03).

What ``reset`` deletes, and why ``tonic_runs`` is on the list: the agent joins
a turn to the caller's live run within thirty minutes
(``RunService.findResumable``), so without deleting runs, repetition two would
be filed inside repetition one's conversation and seeded with its history.
The study rows scoped to the trip go too, including the mutation rows the
rebuild itself produces: the reset is not part of the case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import db
from src.auth import SimUser
from src.fixture import build_children, create_trip, expected_digest, find_trip, load_fixture, observed_digest, observed_regions

HARNESS_LOG = Path(__file__).resolve().parent.parent / "runs" / "harness.log"

#: Tables that must hold no row for the trip before a repetition starts. The
#: fixture's own blocks, slots, days and regions are checked by digest instead.
MUST_BE_EMPTY = (
    "chat_messages",
    "tonic_runs",
    "ai_suggestions",
    "branches",
    "study_suggestions",
    "study_mutations",
)


@dataclass(frozen=True)
class ResetResult:
    """What one rebuild produced: the state digest the gate compares, and the
    ids it created. The ids are new every time and are recorded on the
    execution row, because nothing else can resolve a mutation's ``row_id``
    back to a stop once the next repetition has replaced it (D26)."""

    digest: str
    ids: dict = field(default_factory=dict)


class DirtyState(RuntimeError):
    """The precondition failed: named table, or a digest that does not match."""

    def __init__(self, trip_id: str, table: str, detail: str):
        super().__init__(f"trip {trip_id[:8]}: {table} — {detail}")
        self.trip_id = trip_id
        self.table = table
        self.detail = detail


def harness_log(line: str) -> None:
    HARNESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with HARNESS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now(timezone.utc).isoformat()} {line}\n")


def ensure_trip(user: SimUser, token: str, fixture: dict[str, Any] | None = None) -> str:
    """The member's fixture trip id, creating the trip row on first use."""
    fixture = fixture or load_fixture()
    return find_trip(fixture, user) or create_trip(fixture, user, token)


def _delete_children(trip_id: str) -> None:
    a = db.admin()
    a.table("chat_messages").delete().eq("trip_id", trip_id).execute()
    a.table("tonic_runs").delete().eq("trip_id", trip_id).execute()
    a.table("ai_suggestions").delete().eq("trip_id", trip_id).execute()
    a.table("branches").delete().eq("trip_id", trip_id).execute()
    days = [d["id"] for d in a.table("itinerary_days").select("id").eq("trip_id", trip_id).execute().data]
    if days:
        a.table("itinerary_slots").delete().in_("itinerary_day_id", days).execute()
    a.table("trip_blocks").delete().eq("trip_id", trip_id).execute()
    a.table("itinerary_days").delete().eq("trip_id", trip_id).execute()
    a.table("regions").delete().eq("trip_id", trip_id).execute()


def _delete_study_rows(trip_id: str) -> None:
    a = db.admin()
    # user actions and verdicts cascade with their suggestion; feedback with its message
    a.table("study_suggestions").delete().eq("trip_id", trip_id).execute()
    a.table("study_mutations").delete().eq("trip_id", trip_id).execute()


def reset(trip_id: str, token: str, fixture: dict[str, Any] | None = None) -> ResetResult:
    """Wipe the trip's children and rebuild the fixture, returning the digest
    and the ids the rebuild produced."""
    fixture = fixture or load_fixture()
    _delete_children(trip_id)
    _delete_study_rows(trip_id)
    ids = build_children(fixture, trip_id, token)
    _delete_study_rows(trip_id)  # the rebuild's own mutation rows are not data
    return ResetResult(digest=observed_digest(trip_id), ids=ids)


def assert_clean(trip_id: str, fixture: dict[str, Any] | None = None) -> None:
    """Refuse to start unless the trip is exactly the fixture (invariant 1)."""
    fixture = fixture or load_fixture()
    a = db.admin()
    for table in MUST_BE_EMPTY:
        count = a.table(table).select("id", count="exact").eq("trip_id", trip_id).limit(1).execute().count or 0
        if count:
            _refuse(trip_id, table, f"{count} row(s) present")
    expected = expected_digest(fixture)
    observed = observed_digest(trip_id)
    if observed != expected:
        _refuse(trip_id, "fixture", f"digest {observed[:12]} != expected {expected[:12]}")
    missing = {r["name"] for r in fixture["regions"]} - observed_regions(trip_id)
    if missing:
        _refuse(trip_id, "regions", f"declared region(s) absent: {sorted(missing)}")


def _refuse(trip_id: str, table: str, detail: str) -> None:
    error = DirtyState(trip_id, table, detail)
    harness_log(f"REFUSED {error}")
    raise error
