"""Retire the fixture trips of runs nobody needs any more (B17).

Since D38 every repetition builds its own trip and **nothing is deleted during
a run**, because the trip holds evidence no other table has: the agent's reply
text lives only in ``chat_messages``, and the Google place ids the metamorphic
predicates compare live only in that reply's ``metadata.refs[]``. Deleting a
trip destroys both, permanently. That is not a reason never to delete one — it
is the reason to be explicit about which.

**The rule.** Keep the most recent run, and keep any run a kept run names as
its ``baseline_ref``. That is exactly the pair stage 3.2 compares (D23:
pair-wise, candidate against the adopted baseline), and it falls out of the
data rather than being a list someone maintains. Everything older is a
superseded run whose *verdicts* survive anyway — ``study_case_executions``
keeps its outcome, findings, costs and constraints, and
``study_suggestions.trip_id`` is ``ON DELETE SET NULL``, so the record of what
happened outlives the trip it happened on. What is lost is the ability to
re-judge or re-check that run, which is what makes this a decision and not
housekeeping.

**Safety.** Dry run unless ``--apply``. Three independent guards, each of which
alone would prevent touching a real member's trip: a trip must belong to a
simulated account, be named with the fixture prefix, and not belong to a kept
run. A trip failing any one of them is left alone and reported.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Optional

from src import db
from src.fixture import load_fixture


@dataclass
class Plan:
    keep_runs: list[str] = field(default_factory=list)
    delete_trips: list[dict] = field(default_factory=list)
    keep_trips: list[dict] = field(default_factory=list)
    skipped: list[tuple[dict, str]] = field(default_factory=list)
    losses: dict[str, int] = field(default_factory=dict)


def _fixture_prefix() -> str:
    return load_fixture()["trip"]["name_prefix"]


def _simulated_user_ids() -> set[str]:
    """Whose trips this is allowed to touch at all.

    The same two signals the analytics exclusion uses — a reserved `.invalid`
    email (RFC 2606, so never a person) or a `simulation` study session.
    Resolved here rather than trusted from the trip, because the question
    "may this row be deleted" should not be answered by the row itself.
    """
    a = db.admin()
    ids = {
        u.id
        for u in a.auth.admin.list_users()
        if getattr(u, "email", None) and str(u.email).lower().endswith(".invalid")
    }
    rows = a.table("study_sessions").select("user_id").eq("run_type", "simulation").execute().data
    ids |= {r["user_id"] for r in rows if r.get("user_id")}
    return ids


def keep_run_ids(runs: list[dict], keep_latest: int = 1) -> set[str]:
    """Which runs survive: the newest ``keep_latest``, plus the baseline each
    one names. ``runs`` comes newest first.

    Pure, because this rule is the whole safety argument and it should be
    checkable without a database.
    """
    keep = {r["id"] for r in runs[:keep_latest]}
    for run in runs:
        if run["id"] in keep and run.get("baseline_ref"):
            keep.add(run["baseline_ref"])
    return keep


def build_plan(keep_latest: int = 1) -> Plan:
    """What would be deleted, and what would be kept, and why."""
    a = db.admin()
    plan = Plan()

    runs = (
        a.table("study_runs")
        .select("id, started_at, baseline_ref, notes")
        .order("started_at", desc=True)
        .execute()
        .data
    )
    # A kept run's baseline is kept too: that pair is what stage 3.2 compares.
    keep = keep_run_ids(runs, keep_latest)
    plan.keep_runs = [r["id"] for r in runs if r["id"] in keep]

    executions = (
        a.table("study_case_executions").select("run_id, trip_id, case_id, repetition").execute().data
    )
    trip_run: dict[str, str] = {}
    for row in executions:
        if row.get("trip_id"):
            trip_run[row["trip_id"]] = row["run_id"]

    prefix = _fixture_prefix()
    simulated = _simulated_user_ids()
    trips = (
        a.table("trips")
        .select("id, name, created_by, created_at")
        .like("name", f"{prefix}%")
        .order("created_at")
        .execute()
        .data
    )

    for trip in trips:
        run_id = trip_run.get(trip["id"])
        trip = {**trip, "run_id": run_id}
        if trip["created_by"] not in simulated:
            plan.skipped.append((trip, "not owned by a simulated account"))
            continue
        if not trip["name"].startswith(prefix):
            plan.skipped.append((trip, "name is not a fixture trip"))
            continue
        if run_id in keep:
            plan.keep_trips.append(trip)
            continue
        plan.delete_trips.append(trip)

    ids = [t["id"] for t in plan.delete_trips]
    if ids:
        for table in ("chat_messages", "trip_blocks", "itinerary_days", "study_mutations", "ai_suggestions"):
            plan.losses[table] = (
                a.table(table).select("id", count="exact").in_("trip_id", ids).limit(1).execute().count or 0
            )
    return plan


def describe(plan: Plan) -> str:
    lines = [
        f"keep runs      : {len(plan.keep_runs)} ({', '.join(r[:8] for r in plan.keep_runs) or 'none'})",
        f"keep trips     : {len(plan.keep_trips)}",
        f"delete trips   : {len(plan.delete_trips)}",
    ]
    orphans = sum(1 for t in plan.delete_trips if not t["run_id"])
    if orphans:
        lines.append(f"  of which orphaned (no execution row): {orphans}")
    for table, n in sorted(plan.losses.items()):
        lines.append(f"  and with them  : {n} {table}")
    if plan.losses.get("chat_messages"):
        lines.append(
            "  NOTE: chat_messages is the only copy of the agent's reply text "
            "and of the place ids the metamorphic predicates compare. Those "
            "runs cannot be re-judged or re-checked afterwards."
        )
    for trip, why in plan.skipped:
        lines.append(f"  SKIPPED {trip['id'][:8]}… {trip['name']!r}: {why}")
    return "\n".join(lines)


def apply(plan: Plan) -> int:
    """Delete the planned trips. Children go by cascade; study rows survive
    with `trip_id` set to null."""
    a = db.admin()
    deleted = 0
    for trip in plan.delete_trips:
        a.table("trips").delete().eq("id", trip["id"]).execute()
        deleted += 1
    return deleted


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually delete (default is a dry run)")
    parser.add_argument("--keep-latest", type=int, default=1, help="how many recent runs to keep (default 1)")
    args = parser.parse_args(argv)

    plan = build_plan(keep_latest=args.keep_latest)
    print(describe(plan))
    if not args.apply:
        print("\ndry run — nothing deleted. Pass --apply to delete.")
        return 0
    if not plan.delete_trips:
        print("\nnothing to delete.")
        return 0
    deleted = apply(plan)
    print(f"\ndeleted {deleted} trip(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
