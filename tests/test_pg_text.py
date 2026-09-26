"""Judge text is made storable before it reaches Postgres.

A pair-wise rationale once carried a NUL character; a `text` column refuses it
(22P05) and the refusal crashed the B11 comparison pass at 149 of 176.
"""

from __future__ import annotations

from pathlib import Path

from src.comparison import pg_text


def test_a_nul_is_dropped_and_nothing_else_changes():
    assert pg_text("a" + chr(0) + "b") == "ab"
    assert pg_text("fine as it is") == "fine as it is"
    assert pg_text(None) is None


def test_the_harness_sources_carry_no_nul_bytes():
    # The fix itself once put a literal NUL into comparison.py via a shell
    # escape; Python refuses to import such a file.
    for path in (Path(__file__).resolve().parents[1] / "src").glob("*.py"):
        assert b"\x00" not in path.read_bytes(), path.name
