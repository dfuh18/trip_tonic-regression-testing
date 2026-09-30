"""Score participant replies with the P3 judge (D110) and store the scores.

Scores the opening turn of every request (D100) in the ``pilot`` or ``study``
sessions against the rubric for its request type, and writes each score to
``study_participant_scores`` as it arrives. Resumable: a turn already scored
under the current judge model and prompt version is skipped, so an interrupted
pass is re-run as is.

    python tools/score_participants.py --run-type pilot            # dry run: counts only
    python tools/score_participants.py --run-type pilot --apply

Prints counts, request types and scores only, never a participant's words.
The judge runs on the EU Vertex endpoint, as the consent form states.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import db, participant_judge as pj, pilot  # noqa: E402
from src.config import settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-type", choices=("pilot", "study"), required=True)
    parser.add_argument("--apply", action="store_true", help="call the judge and write the scores")
    args = parser.parse_args()

    client = db.admin()
    turns = pilot.load(client, args.run_type).suggestions
    openings = pj.opening_turns(turns)
    print(f"{args.run_type}: {len(turns)} turns, {len(openings)} requests (opening turns)")
    print("request types:", dict(Counter(pj.request_type_of(t) for t in openings)))
    print(f"judge: {settings.JUDGE_MODEL} · {pj.judge_version()}")
    if not args.apply:
        print("dry run: nothing scored (add --apply)")
        return 0

    results = pj.score_round(client, turns)
    print("done:", dict(pj.score_summary(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
