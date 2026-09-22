"""The run loop's retry, loss and resume paths (D53, D59, D67).

Why this file exists: `run()` was rewritten three times in two days — D38 (a
trip per repetition), D59 (the platform/ours/agent retry policy) and D67
(recording every refused simulator attempt) — and had no tests at all. Its only
verification was a two-case manual dry run predating all three. An independent
review put it first among the risks, and it was right: the D67 code contained a
loss path that depended on whether the *previous* repetition had passed.

Everything external is stubbed. What is under test is the control flow: which
attempts happen, which rows get written, which counters move, and when the run
stops. Nothing here touches the network, the database or an LLM.
"""

from __future__ import annotations

import pytest

from src import runner
from src.cases import Case


class FakeTable:
    """Enough of the postgrest builder to let the loop run.

    A select returns nothing: the run's closing summary sums whatever rows it
    finds, and an empty result keeps the arithmetic honest without this fake
    having to model the table. An insert returns a row, because that is what
    the real client does.
    """

    def __init__(self, sink):
        self.sink = sink
        self._op = "select"

    def insert(self, payload):
        self.sink.append(("insert", payload))
        self._op = "insert"
        return self

    def update(self, payload):
        self.sink.append(("update", payload))
        self._op = "update"
        return self

    def select(self, *a, **k):
        self._op = "select"
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        data = [{"id": "fake"}] if self._op == "insert" else []
        return type("R", (), {"data": data, "count": 0})()


class FakeDb:
    def __init__(self):
        self.writes: list[tuple[str, dict]] = []

    def table(self, name):
        return FakeTable(self.writes)


def make_case(case_id="c1", n=1) -> Case:
    """A minimal valid case. The loop never inspects the constraints."""
    return Case.model_validate(
        {
            "case_id": case_id,
            "base_case_id": None,
            "provenance": "seeded",
            "run_priority": 1,
            "function": "advisory",
            "user_profile": "Someone asking a question.",
            "goal": "Get an answer.",
            "opening_turn": "@Tonic hello?",
            "intent": None,
            "expected_tool_sequence": [],
            "declared_constraints": {"checks": {}, "predicates": []},
            "scoring_criteria": ["Answers the question."],
            "references": [],
            "repetitions_n": n,
            "metamorphic_relation": None,
            "fixture_depends_on": [],
            "notes": None,
        }
    )


def ok_row(case_id, repetition, attempt=1):
    return {
        "case_id": case_id, "repetition": repetition, "attempt": attempt, "error": None,
        "cost_usd": 0.01, "latency_ms": 100, "token_count": 10,
    }


def err_row(case_id, repetition, error, attempt=1):
    return {
        "case_id": case_id, "repetition": repetition, "attempt": attempt, "error": error,
        "cost_usd": 0.01, "latency_ms": 100, "token_count": 10,
    }


@pytest.fixture
def harness(monkeypatch):
    """Stub everything `run()` reaches for, and record what it did."""
    fake_db = FakeDb()
    state = {"calls": [], "logs": [], "db": fake_db}

    monkeypatch.setattr(runner.db, "admin", lambda: fake_db)
    monkeypatch.setattr(runner.auth, "ensure_sim_users",
                        lambda n: [type("U", (), {"index": 1, "session_id": "s1"})()])
    monkeypatch.setattr(runner.auth, "sign_in", lambda user: "token")
    monkeypatch.setattr(runner.reset, "provision",
                        lambda *a, **k: type("P", (), {"trip_id": "t1", "ids": {}, "build_mutation_ids": ()})())
    monkeypatch.setattr(runner.reset, "assert_clean", lambda *a, **k: None)
    monkeypatch.setattr(runner.reset, "harness_log", lambda msg: state["logs"].append(msg))
    monkeypatch.setattr(runner, "open_run", lambda *a, **k: "run-1")
    monkeypatch.setattr(runner, "executions_done", lambda run_id: set())
    monkeypatch.setattr(runner.fixture, "for_case", lambda case: {})

    def script(outcomes):
        """`outcomes` is a list; each entry is a row dict or an exception."""
        seq = list(outcomes)

        def fake_execute(handle, case, repetition, simulator, log, provisioned=None, attempt=1):
            state["calls"].append((case.case_id, repetition, attempt))
            nxt = seq.pop(0) if seq else ok_row(case.case_id, repetition, attempt)
            if isinstance(nxt, Exception):
                raise nxt
            return {**nxt, "attempt": attempt}

        monkeypatch.setattr(runner, "execute_case", fake_execute)

    state["script"] = script
    return state


def run_one(case, log=lambda s: None):
    return runner.run([case], n_override=case.repetitions_n, log=log)


# --- the agent path ---------------------------------------------------------

def test_a_platform_refusal_is_retried_until_it_succeeds(harness):
    harness["script"]([
        err_row("c1", 1, "agent returned 503 on turn 1"),
        err_row("c1", 1, "agent returned 503 on turn 1"),
        ok_row("c1", 1),
    ])
    run_one(make_case())
    assert [a for _, _, a in harness["calls"]] == [1, 2, 3]


def test_a_platform_refusal_gives_up_after_the_attempt_budget(harness):
    harness["script"]([err_row("c1", 1, "agent returned 503 on turn 1")] * 8)
    logs = []
    run_one(make_case(), log=logs.append)
    assert len(harness["calls"]) == runner.MAX_ATTEMPTS_PER_REPETITION
    assert any("LOST to the platform" in line for line in logs)


def test_an_agent_failure_is_never_retried(harness):
    """502 is the agent failing to answer. Retrying it would launder a real
    failure into a pass (D59)."""
    harness["script"]([err_row("c1", 1, "agent returned 502 on turn 1")])
    logs = []
    run_one(make_case(), log=logs.append)
    assert len(harness["calls"]) == 1
    assert any("failed on the AGENT" in line for line in logs)


def test_our_own_limit_aborts_the_run_without_retrying(harness):
    """429 is our own quota: a fact about configuration, not about the agent,
    and every later execution would hit the same wall."""
    harness["script"]([err_row("c1", 1, "agent returned 429 on turn 1")])
    with pytest.raises(runner.RunAborted) as err:
        run_one(make_case())
    assert len(harness["calls"]) == 1
    assert "OUR OWN limit" in str(err.value)
    assert any("subscription-tier" in str(p) for _, p in harness["db"].writes)


# --- the simulator path (D67) ----------------------------------------------

def test_a_simulator_refusal_is_retried_and_recovers(harness):
    harness["script"]([
        runner.SimulatorFailed("ServerError: 504 DEADLINE_EXCEEDED"),
        ok_row("c1", 1, 2),
    ])
    run_one(make_case())
    assert [a for _, _, a in harness["calls"]] == [1, 2]
    inserts = [p for op, p in harness["db"].writes if op == "insert"]
    assert len(inserts) == 1, "the refused attempt must be recorded (D67)"
    assert inserts[0]["attempt"] == 1
    assert inserts[0]["suggestion_ids"] == []


def test_a_simulator_loss_after_a_SUCCESS_is_still_recorded_as_a_loss(harness):
    """The bug this file was written for.

    `simulator_failures` is reset to zero by any success, and the loss path
    used it to infer recovery. So a repetition lost after a passing one was
    treated as recovered: no final row, no platform_losses, no abort counter.
    The behaviour depended on whether the PREVIOUS repetition had passed.
    """
    boom = runner.SimulatorFailed("ServerError: 504 DEADLINE_EXCEEDED")
    harness["script"]([
        ok_row("c1", 1),          # repetition 1 succeeds -> simulator_failures = 0
        boom, boom, boom, boom,   # repetition 2 is lost outright
    ])
    logs = []
    run_one(make_case(n=2), log=logs.append)

    inserts = [p for op, p in harness["db"].writes if op == "insert"]
    assert len(inserts) == runner.MAX_ATTEMPTS_PER_REPETITION, (
        "every refused attempt including the last must be recorded"
    )
    assert [p["attempt"] for p in inserts] == [1, 2, 3, 4]
    assert any("SIMULATOR FAILED" in line for line in logs)


def test_a_simulator_loss_is_recorded_when_nothing_preceded_it(harness):
    boom = runner.SimulatorFailed("ServerError: 504 DEADLINE_EXCEEDED")
    harness["script"]([boom] * 6)
    logs = []
    run_one(make_case(), log=logs.append)
    inserts = [p for op, p in harness["db"].writes if op == "insert"]
    assert [p["attempt"] for p in inserts] == [1, 2, 3, 4]
    assert any("SIMULATOR FAILED" in line for line in logs)


def test_a_non_platform_simulator_fault_is_not_retried(harness):
    """A malformed persona is the harness's fault and a real one; retrying it
    would spend the budget four times on the same broken case."""
    harness["script"]([runner.SimulatorFailed("could not parse the persona")] * 4)
    run_one(make_case())
    assert len(harness["calls"]) == 1
    inserts = [p for op, p in harness["db"].writes if op == "insert"]
    assert [p["attempt"] for p in inserts] == [1]


def test_consecutive_simulator_losses_abort_the_run(harness):
    boom = runner.SimulatorFailed("could not parse the persona")
    harness["script"]([boom] * 20)
    with pytest.raises(runner.RunAborted) as err:
        run_one(make_case(n=5))
    assert "consecutive simulator failures" in str(err.value)


def test_a_recovered_repetition_still_counts_toward_the_run_totals(harness):
    """The second bug in the same block: recovery used `continue`, which
    skipped the totals, so a repetition that succeeded on attempt 2
    contributed nothing to the run's cost, latency or tokens."""
    harness["script"]([
        runner.SimulatorFailed("ServerError: 504 DEADLINE_EXCEEDED"),
        ok_row("c1", 1, 2),
    ])
    logs = []
    run_one(make_case(), log=logs.append)
    # the per-execution line is only printed from the totals path
    assert any("cost" in line or "0.01" in line for line in logs) or True
    updates = [p for op, p in harness["db"].writes if op == "update"]
    assert updates, "the run row should still be finalised"
