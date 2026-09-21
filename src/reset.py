"""State provisioning and the precondition gate (B02; invariant 1; D03, D38).

Every repetition begins from the fixture, and it begins on a **trip of its
own**. ``provision`` builds one; ``assert_clean`` refuses to start a
repetition on a trip that is not exactly the fixture. The refusal is
recorded — one line in ``runs/harness.log`` — because "the harness refused"
must stay distinguishable from "nobody ran it", but it is not a run field: a
run that proceeded would always carry ``true`` (D03).

**Nothing is ever deleted here, and that is the point (D38).** This module
used to wipe one trip's children between repetitions, including the
``study_suggestions`` and ``study_mutations`` rows the previous repetition had
just produced. A probe run showed the consequence plainly: of eight
executions, seven had no readable record left, because each repetition's reset
destroyed the one before it. The checker, the judge and the analysis all read
those rows *after* a run, and the reply text lives only in ``chat_messages``,
which went the same way — so a baseline run would have left nothing for a
later run to be compared against.

Isolation is now by construction. A new trip cannot inherit chat, runs,
drafts, branches or edits from the previous repetition, because none of them
ever existed on it — which is a stronger guarantee than deleting the right
list of tables, and it removes the way the record was being destroyed. The
gate below still runs, and on a fresh trip it is the assertion that the trip
really is fresh: if provisioning ever handed back a reused id, ``MUST_BE_EMPTY``
is what would notice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import db
from src.auth import SimUser
from src.fixture import (
    build_children,
    create_trip,
    expected_digest,
    load_fixture,
    observed_digest,
    observed_members,
    observed_regions,
)

HARNESS_LOG = Path(__file__).resolve().parent.parent / "runs" / "harness.log"

#: Tables that must hold no row for the trip before a repetition starts. The
#: fixture's own blocks, slots, days and regions are checked by digest instead.
#:
#: ``study_mutations`` is deliberately **not** here (D38). Building the fixture
#: writes the trip's stops and slots through the member's own API calls, and
#: the trigger records every one of them, so a freshly built trip always has
#: mutation rows and asserting otherwise would refuse every repetition. They
#: are excluded from the execution instead, by id, in ``ResetResult
#: .build_mutation_ids`` — by id rather than by timestamp because the rows are
#: stamped with the database's clock and the harness reads its own.
MUST_BE_EMPTY = (
    "chat_messages",
    "tonic_runs",
    "ai_suggestions",
    "branches",
    "study_suggestions",
)


@dataclass(frozen=True)
class ResetResult:
    """What one provisioning produced: the trip it built, the state digest the
    gate compares, and the ids it created. The ids are new every time and are
    recorded on the execution row, because nothing else can resolve a
    mutation's ``row_id`` back to a stop (D26)."""

    trip_id: str
    digest: str
    ids: dict = field(default_factory=dict)
    #: The mutation rows the fixture build itself wrote. Not the case's, so
    #: the execution excludes them; kept rather than deleted, because deleting
    #: them is what also deleted the previous repetition's record (D38).
    build_mutation_ids: tuple[str, ...] = ()


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


def provision(
    user: SimUser,
    token: str,
    label: str = "",
    fixture: dict[str, Any] | None = None,
) -> ResetResult:
    """A new fixture trip for one repetition: the trip row, then its children.

    ``label`` names the repetition in the trip's title, so a person reading a
    list of trips can tell them apart; the id is on the execution row either
    way. The rebuild's own ``study_mutations`` rows are left where they are and
    filtered out by time when the execution is collected — deleting them was
    how the previous repetition's record came to be deleted too (D38).
    """
    fixture = fixture or load_fixture()
    trip_id = create_trip(fixture, user, token, label)
    ids = build_children(fixture, trip_id, token)
    built = db.admin().table("study_mutations").select("id").eq("trip_id", trip_id).execute().data
    return ResetResult(
        trip_id=trip_id,
        digest=observed_digest(trip_id),
        ids=ids,
        build_mutation_ids=tuple(row["id"] for row in built),
    )


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
    # Travellers are checked by presence for the same reason as regions: they
    # are not in the digest, because nothing in a repetition can change them.
    absent = {m["display_name"] for m in fixture.get("members", [])} - observed_members(trip_id)
    if absent:
        _refuse(trip_id, "members", f"declared traveller(s) absent: {sorted(absent)}")


def _refuse(trip_id: str, table: str, detail: str) -> None:
    error = DirtyState(trip_id, table, detail)
    harness_log(f"REFUSED {error}")
    raise error
