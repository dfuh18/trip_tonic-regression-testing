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
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from src import db
from src.auth import SimUser
from src.config import settings

FIXTURE_FILE = Path(__file__).resolve().parent.parent / "cases" / "fixture.json"


def load_fixture(path: Path = FIXTURE_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def trip_name(fixture: dict[str, Any], user: SimUser) -> str:
    return f"{fixture['trip']['name_prefix']} sim-{user.index:02d}"


def expected_digest(fixture: dict[str, Any]) -> str:
    """What a freshly built fixture must hash to."""
    blocks = sorted((b["title"], b["type"]) for b in fixture["blocks"])
    title_of = {b["key"]: b["title"] for b in fixture["blocks"]}
    slots = sorted((s["day_date"], s["start_time"], s["end_time"], title_of[s["block"]]) for s in fixture["slots"])
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


def _digest(blocks: list, slots: list) -> str:
    payload = json.dumps({"blocks": blocks, "slots": slots}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_trip(fixture: dict[str, Any], user: SimUser) -> str | None:
    rows = (
        db.admin()
        .table("trips")
        .select("id")
        .eq("created_by", user.id)
        .eq("name", trip_name(fixture, user))
        .limit(1)
        .execute()
        .data
    )
    return rows[0]["id"] if rows else None


def _api(token: str) -> httpx.Client:
    return httpx.Client(base_url=settings.API_BASE_URL, headers=db.api_headers(token), timeout=60)


def create_trip(fixture: dict[str, Any], user: SimUser, token: str) -> str:
    """The trip row itself, once. Children are the rebuild's job."""
    with _api(token) as api:
        r = api.post(
            "/trips",
            json={
                "name": trip_name(fixture, user),
                "description": fixture["trip"]["description"],
                "start_date": fixture["trip"]["start_date"],
                "end_date": fixture["trip"]["end_date"],
            },
        )
        r.raise_for_status()
        return r.json()["data"]["id"]


def build_children(fixture: dict[str, Any], trip_id: str, token: str) -> None:
    """Regions, blocks and slots, through the member's own API calls."""
    with _api(token) as api:
        for region in fixture["regions"]:
            api.post(f"/trips/{trip_id}/regions", json=region).raise_for_status()
        block_ids: dict[str, str] = {}
        for block in fixture["blocks"]:
            body = {k: v for k, v in block.items() if k != "key"}
            body["place_link"] = "unlinked"
            r = api.post(f"/trips/{trip_id}/blocks", json=body)
            r.raise_for_status()
            block_ids[block["key"]] = r.json()["data"]["id"]
        for slot in fixture["slots"]:
            api.post(
                f"/trips/{trip_id}/itinerary/add-block-to-day",
                json={
                    "block_id": block_ids[slot["block"]],
                    "day_date": slot["day_date"],
                    "start_time": slot["start_time"],
                    "end_time": slot["end_time"],
                    "time_precision": "exact",
                },
            ).raise_for_status()
