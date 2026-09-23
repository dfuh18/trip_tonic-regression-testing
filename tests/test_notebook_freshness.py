"""Published notebooks must not describe a suite that no longer exists (D80).

`notebooks/sim/` keeps its outputs: they are the worked examples published with
the thesis. That makes a stored output a claim, and a claim goes stale when the
code under it moves.

It has gone stale three times, and a reader caught it each time — twice in
`02_expand` (an admission table computed under a superseded threshold, prose
counting sixteen follow-ups when there were eighteen) and once in `01_cases`,
which for three days told a reader the suite had **8 cases** and was
**8 of 8 reviewed** against a live 29 and 29/29. That last one is the sharper
failure: a stale test goes red, a stale stored output is silent.

`02_expand` already had two guards of this shape. They were never generalised,
so the notebook that was actually wrong had none. This parametrizes them over
every published notebook.

What is asserted is the *derived* count, never a literal: the expected numbers
come from `load_cases()`, so this file states no fact about the suite that the
suite does not state about itself. Formatting is not asserted — pandas may
widen, wrap or reorder, and none of that is a claim.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cases import CASES_DIR, load_cases

NOTEBOOKS = sorted((Path(CASES_DIR).parent / "notebooks" / "sim").glob("*.ipynb"))

#: Run-scoped notebooks describe one execution and name it, so their stored
#: numbers are a dated record rather than a claim about the current suite.
#: `run_survey` prints the run id and date it read; that is what makes it
#: exempt, not its filename.
RUN_SCOPED = {"run_survey.ipynb"}


def _outputs(nb: dict) -> str:
    return "".join(
        "".join(out.get("text") or "") or "".join(out.get("data", {}).get("text/plain") or "")
        for cell in nb["cells"]
        for out in cell.get("outputs", [])
    )


def _prose(nb: dict) -> str:
    return "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_a_published_notebook_has_stored_outputs(path):
    """`notebooks/sim/` keeps its outputs; one with none was never run."""
    nb = json.loads(path.read_text(encoding="utf-8"))
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert code_cells, f"{path.name} has no code cells"
    with_output = [c for c in code_cells if c.get("outputs")]
    assert with_output, f"{path.name} has no stored outputs — execute it before committing"


@pytest.mark.parametrize(
    "path", [p for p in NOTEBOOKS if p.name not in RUN_SCOPED], ids=lambda p: p.name
)
def test_a_suite_scoped_notebook_states_the_current_case_count(path):
    """A notebook whose outputs describe the SUITE must describe this one.

    `01_cases` said "8 cases" for three days after the suite reached 29. The
    count is derived here rather than written down, so this test cannot itself
    become the stale thing it is checking for.
    """
    nb = json.loads(path.read_text(encoding="utf-8"))
    text = _outputs(nb) + "\n" + _prose(nb)
    if not _outputs(nb).strip():
        pytest.skip(f"{path.name} has no stored outputs; the freshness test above covers that")

    import re

    # "N cases", not a bare N: the number 29 appears in a token count, a
    # latency and a date, so a bare search passes on a notebook whose visible
    # claim is "8 cases". Simulating the stale state proved exactly that.
    total = len(load_cases())
    assert re.search(rf"(?<!\d){total} cases", text), (
        f"{path.name} never states the current case count as '{total} cases' — re-run it"
    )

    # And must not still assert a count the suite has left behind. Word
    # boundaries matter: "9 cases" is a substring of "29 cases", so a plain
    # `in` reports the current count as stale — the same prefix trap that made
    # the admission-table guard report seeds as present whenever one of their
    # follow-ups was listed.
    stale = [
        n for n in (8, 9, 16, 24, 26, 27)
        if n < total and re.search(rf"(?<!\d){n} cases", text)
    ]
    assert not stale, f"{path.name} still says {stale} cases; the suite has {total} — re-run it"


def test_the_review_ledger_in_the_notebook_matches_the_ledger():
    """`01_cases` prints the review state, which moves whenever the author
    reviews anything. Its stored output claimed "8 of 8 reviewed -- all
    adopted" while three seeds were unmarked and eighteen follow-ups were
    outside the ledger entirely."""
    from src.cases import review_status

    path = next((p for p in NOTEBOOKS if p.name == "01_cases.ipynb"), None)
    if path is None:
        pytest.skip("01_cases.ipynb not present")

    nb = json.loads(path.read_text(encoding="utf-8"))
    text = _outputs(nb)
    if not text.strip():
        pytest.skip("no stored outputs; covered by the freshness test")

    status = review_status()
    reviewed = sum(1 for v in status.values() if v["state"] != "unreviewed")
    assert f"{reviewed} of {len(status)} reviewed" in text, (
        f"the notebook's review line disagrees with the ledger "
        f"({reviewed} of {len(status)}) — re-run it"
    )
