"""No assert in the suite may be unreachable (D80).

An assert that never runs is never right. The suite already shipped two of
them: `assert ... or True`, which certified a bug through a full review cycle,
and `assert entry["state"] == "unverifiable"` sitting under a guard that had
just asserted no such state exists — so the test could not fail for the reason
it was named after.

Both belong to the same family as the snapshot pins D80 is about. A pin records
a reading instead of a rule; a dead assert records nothing at all. The
difference is that a pin announces itself by failing, and a dead assert is
silent forever.

This is the one part of the family that is exactly mechanisable. A line either
executed or it did not, so there are no false positives by construction.

**Two attempts preceded this one, and both failed in ways worth recording.**
The first hand-rolled a `sys.settrace` tracer that matched frame filenames by
string prefix against an absolute path; pytest reports paths as given, so it
matched nothing and recorded zero lines — and a `continue` written for "this
file was skipped" turned that into a green test. It passed with a dead assert
planted in front of it. The second fixed the matching and then took over
fifteen minutes, because a Python-level trace callback on every line of a
253-test suite is exactly the workload C-accelerated coverage tooling exists
for. `coverage.py` does this job properly; hand-rolling it was the mistake.

The limit, stated because the audit that prompted this made the same point:
this finds asserts that never run, and says nothing about asserts that run and
assert the wrong thing. The brittle half of the family needs judgement, not a
tracer.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SUBTREE = TESTS_DIR.parent

#: Excluded from its own sweep: this file shells out, so its asserts run in the
#: parent process and never appear in the child's coverage data.
SELF = Path(__file__).name


def _assert_lines(path: Path) -> set[int]:
    """Line numbers of every `assert` statement in a test file.

    The line an `ast.Assert` reports is the `assert` keyword's own, which is
    what coverage records as executed — a multi-line assert counts once.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)}


@pytest.mark.slow
def test_every_assert_in_the_suite_executes(tmp_path):
    data_file = tmp_path / ".coverage"
    report = tmp_path / "coverage.json"

    run = subprocess.run(
        [
            sys.executable, "-m", "coverage", "run",
            f"--data-file={data_file}",
            "--source", str(TESTS_DIR),
            "-m", "pytest", str(TESTS_DIR),
            "-q", "-p", "no:cacheprovider", "-m", "not slow",
        ],
        cwd=str(SUBTREE), capture_output=True, text=True, timeout=600,
    )
    assert data_file.exists(), (
        f"coverage produced no data:\n{run.stdout[-2000:]}\n{run.stderr[-2000:]}"
    )

    subprocess.run(
        [sys.executable, "-m", "coverage", "json",
         f"--data-file={data_file}", "-o", str(report)],
        cwd=str(SUBTREE), capture_output=True, text=True, timeout=120, check=True,
    )
    files = json.loads(report.read_text(encoding="utf-8"))["files"]
    executed = {
        Path(name).resolve(): set(entry["executed_lines"])
        for name, entry in files.items()
    }

    # A sweep that measured nothing must fail, not pass. The first version of
    # this check skipped any file it had no data for, which is how a wholly
    # broken tracer read as green.
    assert executed, "coverage reported no files — this check is not working"

    dead: list[str] = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        if path.name == SELF:
            continue
        ran = executed.get(path.resolve())
        assert ran, f"no coverage data for {path.name}; the check cannot speak for it"
        dead += [f"{path.name}:{line}" for line in sorted(_assert_lines(path) - ran)]

    assert not dead, (
        "these asserts never executed, so they cannot be protecting anything:\n  "
        + "\n  ".join(dead)
    )
