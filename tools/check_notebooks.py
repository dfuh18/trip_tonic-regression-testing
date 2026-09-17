#!/usr/bin/env python3
"""Fail if a notebook under notebooks/study/ carries stored output.

Study notebooks query participant data from Supabase. The code looks clean while
participant rows sit in the stored output cells of the .ipynb, and git history is
permanent. nbstripout is configured as a git filter for that directory, but a
filter is per-clone: a fresh clone, a second machine, or a colleague who did not
run the setup has no filter at all and nothing warns them.

This is that warning. Run it in CI and before any commit that touches notebooks.

  python tools/check_notebooks.py          # check notebooks/study
  python tools/check_notebooks.py --all    # also report sim notebooks (never fails)

Exit status 0 clean, 1 if any study notebook carries output, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STUDY = ROOT / "notebooks" / "study"
SIM = ROOT / "notebooks" / "sim"


def offences(path):
    """(cell index, reason) for every cell of a notebook holding output."""
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [(-1, "could not be read as a notebook: " + str(exc))]
    found = []
    for i, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("outputs"):
            found.append((i, str(len(cell["outputs"])) + " stored output(s)"))
        if cell.get("execution_count") is not None:
            found.append((i, "execution_count is set"))
    return found


def report(directory, failing):
    notebooks = sorted(directory.rglob("*.ipynb"))
    notebooks = [n for n in notebooks if ".ipynb_checkpoints" not in n.parts]
    if not notebooks:
        print("  (no notebooks yet)")
        return 0
    dirty = 0
    for nb in notebooks:
        bad = offences(nb)
        rel = nb.relative_to(ROOT).as_posix()
        if not bad:
            print("  ok    " + rel)
            continue
        dirty += 1
        print(("  DIRTY " if failing else "  note  ") + rel)
        for idx, why in bad[:5]:
            where = "cell " + str(idx) if idx >= 0 else "file"
            print("          " + where + ": " + why)
        if len(bad) > 5:
            print("          ... and " + str(len(bad) - 5) + " more")
    return dirty


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true",
                    help="also list notebooks/sim (informational, never fails)")
    args = ap.parse_args()

    if not STUDY.exists():
        sys.exit("Expected " + STUDY.as_posix() + " to exist. Run from the subtree.")

    print("notebooks/study (outputs must be stripped):")
    dirty = report(STUDY, failing=True)

    if args.all and SIM.exists():
        print("\nnotebooks/sim (outputs are kept on purpose):")
        report(SIM, failing=False)

    if dirty:
        print(
            "\n" + str(dirty) + " study notebook(s) carry stored output.\n"
            "This is how participant data reaches git history. Fix with:\n"
            "  pip install nbstripout\n"
            "  nbstripout notebooks/study/*.ipynb\n"
            "and install the filter so it does not recur:\n"
            "  nbstripout --install --attributes notebooks/study/.gitattributes"
        )
        return 1
    print("\nClean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
