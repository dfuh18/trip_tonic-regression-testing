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

    def __init__(self, sink, rows=None):
        self.sink = sink
        self.rows = rows or []
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
        data = [{"id": "fake"}] if self._op == "insert" else list(self.rows)
        return type("R", (), {"data": data, "count": len(data)})()


class FakeDb:
    """`rows` is what a select returns — the rows a previous run left behind."""

    def __init__(self, rows=None):
        self.writes: list[tuple[str, dict]] = []
        self.rows = rows or []

    def table(self, name):
        return FakeTable(self.writes, self.rows)


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
    # NOT stubbed by default any more: `executions_done` and `attempts_used`
    # are the resume logic, and stubbing them is exactly why the attempt
    # collision survived the last review.
    state["seed_rows"] = lambda rows: setattr(fake_db, "rows", rows)
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


def test_a_recovered_repetition_still_goes_through_the_failure_policy(harness):
    """N3, and the real content of a fix that had landed on dead code.

    Recovery fell through to a `totals` dict that nothing ever reads — the run
    row is summed from a database re-read — so the "fix" was a no-op and its
    test was a tautology. What recovery actually skipped was the failure
    policy: a repetition that recovered from a simulator refusal and then came
    back 429 sailed past the rule that says our own quota stops the run.
    """
    harness["script"]([
        runner.SimulatorFailed("ServerError: 504 DEADLINE_EXCEEDED"),
        err_row("c1", 1, "agent returned 429 on turn 1", attempt=2),
    ])
    with pytest.raises(runner.RunAborted) as err:
        run_one(make_case())
    assert "OUR OWN limit" in str(err.value)


def test_a_recovered_repetition_that_then_fails_on_the_platform_is_counted(harness):
    """Same path, the other outcome: it must be logged as a platform loss
    rather than passing silently."""
    harness["script"]([
        runner.SimulatorFailed("ServerError: 504 DEADLINE_EXCEEDED"),
        err_row("c1", 1, "agent returned 503 on turn 1", attempt=2),
        err_row("c1", 1, "agent returned 503 on turn 1", attempt=3),
        err_row("c1", 1, "agent returned 503 on turn 1", attempt=4),
    ])
    logs = []
    run_one(make_case(), log=logs.append)
    assert any("LOST to the platform" in line for line in logs)


# --- resume (N1) ------------------------------------------------------------

def test_resume_continues_the_attempt_numbering(harness):
    """N1. Every attempt is a row and (run, case, repetition, attempt) is
    unique, so re-executing a withheld repetition at attempt 1 collides with
    the row already there — and a postgrest violation RAISES, escaping
    `execute_case` as neither SimulatorFailed nor RunAborted, killing the
    resumed run with its row left unfinalised.

    Strictly worse than the lossy resume it replaced: a two-hour baseline that
    died at ninety minutes could not be continued at all.
    """
    harness["seed_rows"]([
        {"case_id": "c1", "repetition": 1, "attempt": 1,
         "error": "simulator: ServerError: 504 DEADLINE_EXCEEDED",
         "cost_usd": 0, "latency_ms": 0, "token_count": 0},
    ])
    harness["script"]([ok_row("c1", 1, 2)])
    runner.run([make_case()], n_override=1, resume_run_id="run-1", log=lambda s: None)
    assert [a for _, _, a in harness["calls"]] == [2], "must continue at attempt 2, not restart at 1"


def test_resume_skips_a_repetition_that_produced_a_result(harness):
    """A completed execution, or one the agent itself failed, is a result and
    is not re-run."""
    harness["seed_rows"]([
        {"case_id": "c1", "repetition": 1, "attempt": 1, "error": None,
         "cost_usd": 0, "latency_ms": 0, "token_count": 0},
    ])
    harness["script"]([ok_row("c1", 1)])
    runner.run([make_case()], n_override=1, resume_run_id="run-1", log=lambda s: None)
    assert harness["calls"] == [], "a completed repetition must not be re-executed"


def test_resume_does_not_re_run_an_exhausted_repetition(harness):
    """Attempts spent is a result too — it was recorded as lost."""
    harness["seed_rows"]([
        {"case_id": "c1", "repetition": 1, "attempt": runner.MAX_ATTEMPTS_PER_REPETITION,
         "error": "agent returned 503 on turn 1",
         "cost_usd": 0, "latency_ms": 0, "token_count": 0},
    ])
    harness["script"]([ok_row("c1", 1)])
    runner.run([make_case()], n_override=1, resume_run_id="run-1", log=lambda s: None)
    assert harness["calls"] == []


def test_a_simulator_retry_does_not_reuse_an_attempt_number(harness):
    """N2, the same collision from the other direction: the handler used to
    restart its counter at 1, writing a row for an attempt `execute_case` had
    already written."""
    boom = runner.SimulatorFailed("ServerError: 504 DEADLINE_EXCEEDED")
    harness["script"]([boom] * 6)
    run_one(make_case())
    inserts = [p for op, p in harness["db"].writes if op == "insert"]
    attempts = [p["attempt"] for p in inserts]
    assert attempts == sorted(set(attempts)), f"attempt numbers must not repeat: {attempts}"
