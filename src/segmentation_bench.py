"""Scoring a request-boundary rule against known boundaries (Q29).

In the simulation one execution is one request, so a run's executions carry
their own ground truth. Two errors are measured, and they need different
material:

* **Split** — one request cut in two. Measured *within* executions: every
  execution is one request, so any boundary a rule draws inside one is wrong.
  Only multi-step cases can produce it (D81), because a case with one acting
  turn has nowhere to cut.
* **Merge** — two requests read as one. Measured by *fusing* executions into
  synthetic runs, where each seam is a true boundary a rule may miss.

Every variant of ``shapes.segment_with`` is scored, so each signal's
contribution is its own column. Slashes are also scored **stripped**: the
agent reaches every path without a command, so a participant typing free text
gives the rule no slash at all, and a rule that only works when members type
commands would be measured here, not discovered in the study.

Pure: executions come in as ``{case_id: [TurnSignals, ...]}``, already loaded
(``survey.turn_signals``). No I/O, seeded randomness only.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import replace
from typing import Mapping, Sequence

from src.shapes import TurnSignals, segment_with

Executions = Mapping[str, Sequence[TurnSignals]]

#: The signal combinations scored, as (use_intent, use_reference).
VARIANTS: dict[str, tuple[bool, bool]] = {
    "shape only": (False, False),
    "+ slash": (True, False),
    "+ reference": (False, True),
    "+ slash + reference": (True, True),
}


def strip_slashes(executions: Executions) -> dict[str, list[TurnSignals]]:
    """The same turns as a member who never types a command would give them.

    An approximation, stated: the agent under a slash has a restricted toolset
    and might have acted differently without one. It removes the signal, not
    the command's effect on what the agent did.
    """
    return {c: [replace(t, intent=None) for t in turns] for c, turns in executions.items()}


def _boundaries(split: Sequence[Sequence[int]]) -> set[int]:
    return {s[0] for s in split} - {0}


def within(executions: Executions, variant: str) -> dict[str, int]:
    """Requests each execution was cut into. Truth is 1 for every one."""
    use_intent, use_reference = VARIANTS[variant]
    return {
        c: len(segment_with(turns, use_intent=use_intent, use_reference=use_reference))
        for c, turns in executions.items()
    }


def fuse(executions: Executions, sequence: Sequence[str]) -> tuple[list[TurnSignals], set[int]]:
    """One synthetic run from recorded executions, and its true boundaries."""
    turns: list[TurnSignals] = []
    truth: set[int] = set()
    for case in sequence:
        if turns:
            truth.add(len(turns))
        turns.extend(executions[case])
    return turns, truth


def score(executions: Executions, variant: str, sequences: Sequence[Sequence[str]]) -> dict[str, float]:
    """Merge and split errors over fused runs.

    ``boundaries found`` is recall over the true seams (1 − merge rate);
    ``false boundaries`` counts cuts inside an execution per run (split);
    ``runs exact`` is both at once.
    """
    use_intent, use_reference = VARIANTS[variant]
    exact = found = true_total = false_total = 0
    for sequence in sequences:
        turns, truth = fuse(executions, sequence)
        drawn = _boundaries(segment_with(turns, use_intent=use_intent, use_reference=use_reference))
        exact += drawn == truth
        found += len(drawn & truth)
        true_total += len(truth)
        false_total += len(drawn - truth)
    n = len(sequences)
    return {
        "runs": n,
        "runs exact": exact / n if n else float("nan"),
        "boundaries found": found / true_total if true_total else float("nan"),
        "false boundaries per run": false_total / n if n else float("nan"),
    }


def all_pairs(executions: Executions) -> list[tuple[str, str]]:
    return list(itertools.permutations(sorted(executions), 2))


def random_runs(executions: Executions, length: int, n: int, seed: int = 28) -> list[list[str]]:
    rng = random.Random(seed)
    names = sorted(executions)
    return [[rng.choice(names) for _ in range(length)] for _ in range(n)]
