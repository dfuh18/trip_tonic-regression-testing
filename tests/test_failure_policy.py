"""Who a failure is blamed on, and what that licenses (D59)."""

import pytest

from src.failures import Failure, TurnDiagnosis, report
from src.runner import (
    MAX_ATTEMPTS_PER_REPETITION,
    OUR_OWN_LIMIT_STATUSES,
    PLATFORM_REFUSAL_STATUSES,
    failure_class,
)


@pytest.mark.parametrize(
    "error,expected",
    [
        (None, None),
        ("", None),
        ("agent returned 503 on turn 1", "platform"),
        ("agent returned 504 on turn 2", "agent"),   # OUR deadline — a product failure (D70)
        ("simulator: ServerError: 504 DEADLINE_EXCEEDED", "platform"),
        ("agent returned 429 on turn 1", "ours"),
        ("agent returned 502 on turn 1", "agent"),
        ("simulator: could not parse the persona", "harness"),
    ],
)
def test_blame(error, expected):
    assert failure_class(error) == expected


def test_our_own_limit_is_never_a_platform_refusal():
    """The two sets must not overlap: 429 is ours and is fatal, and a policy
    that retried it would make the thing it is retrying worse."""
    assert not set(OUR_OWN_LIMIT_STATUSES) & set(PLATFORM_REFUSAL_STATUSES)


def test_a_baseline_gets_more_than_one_extra_attempt():
    """D59 raised this from D53's single retry because a baseline needs every
    planned execution; one spare was not enough at the observed loss rate."""
    assert MAX_ATTEMPTS_PER_REPETITION >= 3


def _turn(**kw):
    base = dict(turn_index=1, error_code=None, retry_count=0, latency_ms=0,
                llm_calls=1, tokens_in=10, tokens_out=10)
    base.update(kw)
    return TurnDiagnosis(**base)


def test_a_turn_where_no_tokens_moved_is_flagged_as_never_answered():
    assert _turn(tokens_in=0, tokens_out=0).never_answered
    assert not _turn(tokens_in=0, tokens_out=5).never_answered


def test_the_report_flags_an_agent_blame_that_the_evidence_contradicts():
    """The regression this file exists for.

    Two executions were recorded as `agent returned 502` while the evidence
    said no model call had completed — they were turns killed by our own
    deadline. The report must say so rather than let the agent carry it.
    """
    f = Failure(
        case_id="x", repetition=1, attempt=1,
        error="agent returned 502 on turn 1", blame="agent",
        turns=[_turn(error_code="empty_reply", retry_count=2, latency_ms=85_015,
                     tokens_in=0, tokens_out=0)],
    )
    out = report([f], total=10)
    assert "NO MODEL CALL EVER COMPLETED" in out
    assert "SUSPECT CLASSIFICATION" in out


def test_a_genuine_agent_failure_is_not_flagged():
    f = Failure(
        case_id="x", repetition=1, attempt=1,
        error="agent returned 502 on turn 1", blame="agent",
        turns=[_turn(error_code="empty_reply", retry_count=0, latency_ms=4_000)],
    )
    out = report([f], total=10)
    assert "SUSPECT CLASSIFICATION" not in out


def test_a_clean_run_says_so():
    assert "no failed executions" in report([], total=28)


def test_a_harness_fault_is_not_blamed_on_the_agent():
    """A malformed persona or an unparseable simulator reply is the harness's
    fault; the agent never saw the turn. It was being printed under "the agent
    genuinely failed to answer", which is the one thing it is not."""
    assert failure_class("simulator: could not parse the persona") == "harness"
    assert failure_class("simulator: ServerError: 504 DEADLINE_EXCEEDED") == "platform"


def test_an_agent_deadline_is_a_failure_not_a_platform_refusal():
    """D70. The 85 seconds is OUR budget, and from the product's side a member
    who waited that long has been failed. Retrying it would score only the
    surviving attempt and leave the pass rate flat through exactly the
    regression §3.1 claims the pipeline catches."""
    assert failure_class("agent returned 504 on turn 1") == "agent"
    f = Failure(case_id="x", repetition=1, attempt=1,
                error="agent returned 504 on turn 1", blame="agent")
    out = report([f], total=10)
    assert "DEADLINE FAILURES" in out
    assert "IS the latency regression" in out.replace("\n", " ")


def test_the_simulators_504_is_the_providers_and_is_still_retried():
    """Same number, different origin. Vertex's deadline on the HARNESS's own
    call — the simulator is not the system under test, and we want the
    execution rather than a measurement of the simulator."""
    assert failure_class("simulator: ServerError: 504 DEADLINE_EXCEEDED") == "platform"
    f = Failure(case_id="x", repetition=1, attempt=1,
                error="simulator: ServerError: 504 DEADLINE_EXCEEDED", blame="platform")
    assert "DEADLINE FAILURES" not in report([f], total=10)


def test_the_judge_is_retried_where_the_agent_is_not():
    """The agent is the system under test and its failure is a result; the
    judge is an instrument and its refusal is a missing measurement. Two runs
    lost five scores to judge 429s, including the two lowest."""
    from src.scoring import MAX_JUDGE_ATTEMPTS, _judge_worth_retrying

    assert MAX_JUDGE_ATTEMPTS > 1
    assert _judge_worth_retrying(RuntimeError("ClientError: 429 RESOURCE_EXHAUSTED"))
    assert _judge_worth_retrying(RuntimeError("ServerError: 504 DEADLINE_EXCEEDED"))
    # a real fault in the rubric or the reply is not transient
    assert not _judge_worth_retrying(RuntimeError("judge returned a score outside 1..10"))
