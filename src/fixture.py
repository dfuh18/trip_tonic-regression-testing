"""The fixture trip (B02): the known state every repetition starts from.

Defined as data in ``cases/fixture.json`` and built through the same API a
member uses, so a rebuilt trip is a trip the application made, not one the
harness assembled from rows. One fixture trip per simulated member, found by
name and owner; created when missing, otherwise reused and rebuilt in place —
the trip id is what runs record, and it should not change between them.

The digest is the state the precondition gate compares against: sorted block
titles and types and the scheduled slots by day and time. It is computed the
same way from the fixture file and from the database, so the two are
comparable without the database being the reference for itself. Regions are
deliberately not in it: the application assigns a region to every block it
creates and may add one (city-aware assignment), so a rebuilt trip can carry a
region the fixture never named. The gate checks instead that every declared
region is present.

The trip carries two placeholder travellers besides the simulated member, so
that a request about "the three of us" is about a group the trip actually has.
They are placeholders in the application's own sense - a display_name and no
account - which is how a trip names a traveller who has not signed up. Nothing
in the run deletes them, so they are ensured rather than rebuilt, and the gate
checks their presence the way it checks regions.

``summary`` renders the fixture as a few lines of prose for the judge. A
criterion like "fits this trip" is unscorable by a judge that sees only the
request and the reply (P3), and the alternative - leaving the trip out and
scoring the criterion on vibes - is worse than telling it what the trip is.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from src import db
from src.auth import SimUser
from src.config import settings

FIXTURE_FILE = Path(__file__).resolve().parent.parent / "cases" / "fixture.json"


def load_fixture(path: Path = FIXTURE_FILE) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    # A stop is identified by its title everywhere — in the trip, in a case's
    # fixture_depends_on, in the id map below — so two stops sharing one would
    # make every reference to it ambiguous and silently drop a block from the
    # build. Refuse the fixture rather than build something unresolvable.
    titles = [block["title"] for block in data["blocks"]]
    duplicates = sorted({t for t in titles if titles.count(t) > 1})
    if duplicates:
        raise ValueError(f"fixture has stops sharing a title: {duplicates}; titles identify a stop")
    names = [member["display_name"] for member in data.get("members", [])]
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise ValueError(f"fixture has travellers sharing a name: {repeated}")
    slot_titles = {slot["block"] for slot in data["slots"]}
    unknown = sorted(slot_titles - set(titles))
    if unknown:
        raise ValueError(f"fixture schedules stops it does not define: {unknown}")
    return data


def trip_name(fixture: dict[str, Any], user: SimUser, label: str = "") -> str:
    """The trip's name, carrying the repetition it was built for (D38).

    One trip per repetition, so the name has to tell them apart: the id is in
    the execution row, but a person looking at a list of trips has only this.
    """
    base = f"{fixture['trip']['name_prefix']} sim-{user.index:02d}"
    return f"{base} {label}" if label else base


def expected_digest(fixture: dict[str, Any]) -> str:
    """What a freshly built fixture must hash to."""
    blocks = sorted((b["title"], b["type"]) for b in fixture["blocks"])
    slots = sorted((s["day_date"], s["start_time"], s["end_time"], s["block"]) for s in fixture["slots"])
    return _digest(blocks, slots)


def observed_digest(trip_id: str) -> str:
    """What the trip hashes to now, read with the service key."""
    a = db.admin()
    blocks = sorted(
        (row["title"], row["type"])
        for row in a.table("trip_blocks").select("title, type").eq("trip_id", trip_id).execute().data
    )
    days = a.table("itinerary_days").select("id, day_date").eq("trip_id", trip_id).execute().data
    day_date = {d["id"]: d["day_date"] for d in days}
    slots = []
    if days:
        for row in (
            a.table("itinerary_slots")
            .select("itinerary_day_id, start_time, end_time, trip_blocks(title)")
            .in_("itinerary_day_id", list(day_date))
            .execute()
            .data
        ):
            title = (row.get("trip_blocks") or {}).get("title")
            slots.append((day_date[row["itinerary_day_id"]], row["start_time"][:5], row["end_time"][:5], title))
    return _digest(blocks, sorted(slots))


def observed_regions(trip_id: str) -> set[str]:
    return {r["name"] for r in db.admin().table("regions").select("name").eq("trip_id", trip_id).execute().data}


def observed_members(trip_id: str) -> set[str]:
    """Placeholder travellers present on the trip, by name.

    Read from the database rather than the API: there is no GET for a trip's
    members - the web app subscribes to the table directly - and adding one
    for the harness would be a change to the application under study.
    """
    rows = (
        db.admin()
        .table("trip_members")
        .select("display_name")
        .eq("trip_id", trip_id)
        .eq("status", "active")
        .execute()
        .data
    )
    return {r["display_name"] for r in rows if r.get("display_name")}


def _day(iso: str) -> str:
    """A date the way a member says it, and the way a reply will.

    The summary is the judge's only view of the trip, and three criteria ask
    it to check a reply that says "Saturday" or "the Sunday" against a fixture
    that stored 2026-11-07. Making the judge do that arithmetic is a way to
    lose a point to a conversion it got wrong, so the summary does it.
    """
    return f"{date.fromisoformat(iso).strftime('%A')} {iso}"


def summary(fixture: dict[str, Any]) -> str:
    """The trip in a few lines, for the judge's reference material.

    Rendered from the fixture file and not from the database, so it says what
    every repetition starts from rather than what one of them ended with - a
    judge told the after-state could reward a reply for a change the case
    forbids.
    """
    trip = fixture["trip"]
    scheduled = {s["block"]: s for s in fixture["slots"]}
    lines = [
        f"The trip runs {_day(trip['start_date'])} to {_day(trip['end_date'])}.",
        "Regions: " + ", ".join(r["name"] for r in fixture["regions"]) + ".",
    ]
    travellers = [m["display_name"] for m in fixture.get("members", [])]
    if travellers:
        lines.append(
            f"Travelling: the member asking, plus {' and '.join(travellers)} "
            f"({len(travellers) + 1} people)."
        )
    lines.append("Stops saved to the trip:")
    for block in fixture["blocks"]:
        slot = scheduled.get(block["title"])
        when = (
            f"scheduled {_day(slot['day_date'])} {slot['start_time']}-{slot['end_time']}"
            if slot
            else "not scheduled"
        )
        lines.append(f"  - {block['title']} ({block['type']}) - {when}")
    days = sorted({s["day_date"] for s in fixture["slots"]})
    lines.append(
        "Days with anything scheduled: " + (", ".join(_day(d) for d in days) or "none") + "."
    )
    return "\n".join(lines)


def _digest(blocks: list, slots: list) -> str:
    payload = json.dumps({"blocks": blocks, "slots": slots}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _api(token: str) -> httpx.Client:
    return httpx.Client(base_url=settings.API_BASE_URL, headers=db.api_headers(token), timeout=60)


def create_trip(fixture: dict[str, Any], user: SimUser, token: str, label: str = "") -> str:
    """The trip row itself. One per repetition (D38) — there is no finding an
    existing one, because reusing a trip is exactly what this stopped doing."""
    with _api(token) as api:
        r = api.post(
            "/trips",
            json={
                "name": trip_name(fixture, user, label),
                "description": fixture["trip"]["description"],
                "start_date": fixture["trip"]["start_date"],
                "end_date": fixture["trip"]["end_date"],
            },
        )
        r.raise_for_status()
        return r.json()["data"]["id"]


def ensure_members(fixture: dict[str, Any], trip_id: str, token: str) -> None:
    """Add any declared traveller the trip does not already have.

    Ensured, not rebuilt: nothing in a repetition can remove a member - the
    agent has no tool for it and the reset deletes only the trip's content -
    so deleting and re-adding them every time would be two writes and a new
    set of ids for no gain. Adding one that exists would be a duplicate name,
    which the loader refuses on the way in.
    """
    present = observed_members(trip_id)
    missing = [m for m in fixture.get("members", []) if m["display_name"] not in present]
    if not missing:
        return
    with _api(token) as api:
        for member in missing:
            r = api.post(f"/trips/{trip_id}/members", json=member)
            r.raise_for_status()


def build_children(fixture: dict[str, Any], trip_id: str, token: str) -> dict[str, Any]:
    """Regions, blocks and slots, through the member's own API calls.

    Returns the ids this build produced. They are new every time — the rebuild
    deletes the previous rows — so an execution that does not record them
    cannot afterwards say which stop a mutation touched (D26).
    """
    ids: dict[str, Any] = {"trip": trip_id, "regions": {}, "blocks": {}, "days": {}, "slots": {}}
    ensure_members(fixture, trip_id, token)
    with _api(token) as api:
        for region in fixture["regions"]:
            r = api.post(f"/trips/{trip_id}/regions", json=region)
            r.raise_for_status()
            body = r.json().get("data") or {}
            if body.get("id"):
                ids["regions"][region["name"]] = body["id"]
        # Keyed by title: a stop is named the same way here, in the database,
        # in a study_mutations projection and in a case's fixture_depends_on.
        block_ids: dict[str, str] = {}
        for block in fixture["blocks"]:
            body = dict(block)
            body["place_link"] = "unlinked"
            r = api.post(f"/trips/{trip_id}/blocks", json=body)
            r.raise_for_status()
            block_ids[block["title"]] = r.json()["data"]["id"]
        ids["blocks"] = dict(block_ids)
        for slot in fixture["slots"]:
            r = api.post(
                f"/trips/{trip_id}/itinerary/add-block-to-day",
                json={
                    "block_id": block_ids[slot["block"]],
                    "day_date": slot["day_date"],
                    "start_time": slot["start_time"],
                    "end_time": slot["end_time"],
                    "time_precision": "exact",
                },
            )
            r.raise_for_status()
            created = r.json().get("data") or {}
            if created.get("day", {}).get("id"):
                ids["days"][slot["day_date"]] = created["day"]["id"]
            if created.get("slot", {}).get("id"):
                ids["slots"][slot["block"]] = created["slot"]["id"]
    return ids
