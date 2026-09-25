"""Delete one participant's study data on request, keeping their account.

The participant information promises (participant-information-and-consent_
260925.md, "What are my rights regarding my data?"): "If you wish to have
your study data deleted without deleting your account, please contact the
researcher, who will remove it on request." This is how.

Two steps, and both are needed:

1. Delete the person's ``pilot`` / ``study`` sessions. Every study table
   hangs off the session with ON DELETE CASCADE (surveys, turns, their
   action rows and verdicts, thumbs, plan mutations), so this is the whole
   of their study data.
2. Clear ``user_metadata.study``. Without it the account is still enrolled,
   and the app's gate would send the person back to the consent page.

Their account, trips and trip chat are app data, not study data, and stay.
After the eight-month anonymisation (D91) nothing links to the account any
more, and this finds nothing — which is the form's "until the point of
complete anonymisation".

    python tools/withdraw_participant.py --email someone@example.org          # dry run
    python tools/withdraw_participant.py --email someone@example.org --apply

Prints counts only. The email is taken from the request, never stored.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import db  # noqa: E402

COHORTS = ("pilot", "study")
PAGE = 200


def find_user(client, email: str):
    target = email.strip().lower()
    for page in range(1, 10_000):
        users = client.auth.admin.list_users(page=page, per_page=PAGE)
        for user in users:
            if (user.email or "").lower() == target:
                return user
        if len(users) < PAGE:
            return None
    return None


def count_rows(client, session_ids: list[str]) -> dict[str, int]:
    if not session_ids:
        return {}
    counts = {}
    for table in ("study_survey_demographics", "study_survey_post_task", "study_suggestions",
                  "study_feedback", "study_mutations"):
        result = client.table(table).select("session_id", count="exact").in_("session_id", session_ids).limit(1).execute()
        counts[table] = result.count or 0
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--email", required=True, help="the account's email, as given in the request")
    parser.add_argument("--apply", action="store_true", help="delete; without it, only report")
    args = parser.parse_args(argv)

    client = db.admin()
    user = find_user(client, args.email)
    if user is None:
        print("No account with that email.")
        return 1

    sessions = (
        client.table("study_sessions").select("id, run_type").eq("user_id", user.id).in_("run_type", list(COHORTS)).execute().data
    )
    session_ids = [s["id"] for s in sessions]
    enrolled = bool((user.user_metadata or {}).get("study"))
    print(f"study sessions: {len(sessions)} ({', '.join(sorted({s['run_type'] for s in sessions})) or 'none'})")
    for table, n in count_rows(client, session_ids).items():
        print(f"  {table}: {n}")
    print(f"enrolment flag set: {enrolled}")

    if not session_ids and not enrolled:
        print("Nothing to delete — never enrolled, already withdrawn, or already anonymised.")
        return 0
    if not args.apply:
        print("Dry run. Re-run with --apply to delete.")
        return 0

    if session_ids:
        client.table("study_sessions").delete().in_("id", session_ids).execute()
    if enrolled:
        client.auth.admin.update_user_by_id(user.id, {"user_metadata": {"study": None}})
    left = client.table("study_sessions").select("id").eq("user_id", user.id).in_("run_type", list(COHORTS)).execute().data
    print(f"Deleted {len(session_ids)} session(s) and everything under them; enrolment cleared. Remaining: {len(left)}.")
    return 0 if not left else 1


if __name__ == "__main__":
    raise SystemExit(main())
