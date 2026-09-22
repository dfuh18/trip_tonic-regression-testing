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
        ("agent returned 504 on turn 2", "platform"),
        ("simulator: ServerError: 504 DEADLINE_EXCEEDED", "platform"),
        ("agent returned 429 on turn 1", "ours"),
        ("agent returned 502 on turn 1", "agent"),
        ("simulator: could not parse the persona", "agent"),
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
