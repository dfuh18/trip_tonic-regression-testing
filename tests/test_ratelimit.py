"""The shared Vertex budget (D39): one key, one window, two callers.

Deterministic — the limiter takes its clock and its sleep, so these assert the
pacing itself rather than waiting for it.
"""
import pytest

from src.ratelimit import RateLimiter, limiter, reset_limiter


class FakeClock:
    """Time moves only when something sleeps, which is what makes the
    assertions about *how long* a caller waited exact rather than approximate."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def build(per_minute: int = 10) -> tuple[RateLimiter, FakeClock]:
    clock = FakeClock()
    return RateLimiter(per_minute, clock=clock, sleep=clock.sleep), clock


def test_a_budget_is_spent_without_waiting_and_then_waits():
    rl, clock = build(per_minute=3)
    assert [rl.acquire() for _ in range(3)] == [0.0, 0.0, 0.0]
    # The fourth has to wait for the first to leave the window.
    waited = rl.acquire()
    assert waited == pytest.approx(60.0)
    assert clock.now == pytest.approx(1060.0)


def test_the_window_slides_rather_than_resetting_on_a_boundary():
    """A fixed minute boundary lets a burst straddle two windows and exhaust
    both, which is the failure this limiter is here to prevent."""
    rl, clock = build(per_minute=2)
    rl.acquire()
    clock.now += 59.0
    rl.acquire()
    # One permit is 59s old and one is fresh; the wait is until the older
    # leaves, not until some wall-clock minute ticks over.
    assert rl.acquire() == pytest.approx(1.0)


def test_one_caller_can_claim_the_calls_another_will_make():
    """The simulator claims a turn's worth before sending, because the calls
    happen inside the application and the budget is per key, not per process."""
    rl, _ = build(per_minute=10)
    assert rl.acquire(4) == 0.0
    assert rl.acquire(4) == 0.0
    # Eight of ten spent; a third turn of four does not fit.
    assert rl.acquire(4) > 0.0


def test_a_claim_larger_than_the_budget_is_clamped_rather_than_hanging():
    """A turn that wanted more calls than the whole minute allows would wait
    for ever. Better a turn that uses the entire budget than a run that stops."""
    rl, _ = build(per_minute=3)
    assert rl.acquire(99) == 0.0
    assert rl.acquire(1) > 0.0


def test_waiting_is_totalled_so_the_pacing_has_a_visible_cost():
    rl, _ = build(per_minute=1)
    rl.acquire()
    rl.acquire()
    rl.acquire()
    assert rl.waited_s == pytest.approx(120.0)


def test_a_budget_of_zero_is_refused():
    with pytest.raises(ValueError):
        RateLimiter(0)


def test_the_process_shares_one_limiter():
    """Two limiters against one key is the bug this module exists to fix, so
    the accessor must not hand out a second."""
    reset_limiter(RateLimiter(5))
    try:
        assert limiter() is limiter()
    finally:
        reset_limiter(None)
