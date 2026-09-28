"""Render one complete simulated execution and one pilot session as printable HTML.

    python tools/render_example.py                       # the defaults below
    python tools/render_example.py --case venue_lookup_seafood_lisbon --rep 3
    python tools/render_example.py --session S2
    python tools/render_example.py --list                # the pilot sessions and their sizes

Writes to examples/ (git-ignored), for each unit the full record and an
appendix_ version (shortened, with a reading guide): open a file in a browser
and print to PDF.
See src/examples.py for what is shown and why.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import db, examples, pilot  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "examples"
SIM_RUN_IDS = ["1a872c09-7070-4789-a806-904969f9185d", "e097f78e-3326-4aea-acaa-0b904d3b0a1c"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run", default=SIM_RUN_IDS[1], help="simulated run id (default: the B11 regression run)")
    p.add_argument("--case", default="scheduling_dinner_from_offer")
    p.add_argument("--rep", type=int, default=1)
    p.add_argument("--session", help="pilot session pseudonym, e.g. S2 (default: the one with the most turns)")
    p.add_argument("--run-type", default="pilot")
    p.add_argument("--list", action="store_true", help="list the sessions and exit")
    p.add_argument("--focus-turn", type=int, help="the turn the appendix version shows in detail "
                                                   "(default: the one that called the most tools)")
    p.add_argument("--chars", type=int, default=500, help="appendix version: longest reply shown, in characters")
    a = p.parse_args()

    def write(example, stem):
        for path, ex in ((OUT / f"{stem}.html", example),
                         (OUT / f"appendix_{stem}.html", examples.compact(example, a.focus_turn, a.chars))):
            path.write_text(examples.render(ex), encoding="utf-8")
            print(f"wrote {path}")

    client = db.admin()
    if a.list:
        for s in pilot.session_table(pilot.load(client, a.run_type)):
            print(f"{s['session']:>4}  {s['status']:<10} {s['turns']} turns")
        return

    OUT.mkdir(exist_ok=True)
    write(examples.simulated(client, a.run, a.case, a.rep), f"sim_{a.case}_rep{a.rep}")

    name = a.session
    if not name:
        rows = [s for s in pilot.session_table(pilot.load(client, a.run_type)) if s["status"] == "consented"]
        name = max(rows, key=lambda s: s["turns"])["session"]
    write(examples.pilot_session(client, name, SIM_RUN_IDS, a.run_type), f"{a.run_type}_{name}")


if __name__ == "__main__":
    main()
