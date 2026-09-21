"""One budget for every Vertex call the harness causes (D39).

The harness makes model calls two ways, and until this module they were
unaware of each other. ``src/llm.py`` calls Vertex directly for the simulator
and the judge. ``src/simulator.py`` calls the application, which then makes two
to four model calls of its own inside one agent turn. Both go to the same
express key, and a key's quota is per minute across all of it.

The B15 probe run hit that: ``429 RESOURCE_EXHAUSTED`` in the middle of a turn,
retried three times inside the same exhausted minute by ``adk-llm.ts`` and then
returned to the harness as a 502, costing one of eight executions. Roughly
thirty to forty model calls went out in about a hundred and fifty seconds.
``VERTEX_MIN_INTERVAL_MS`` had not failed — it spaces calls on an instance
field of a ``Gemini`` the API builds per request, so it paces **within** a turn
and has nothing to say about the next one.

So the budget is counted in **model calls**, not in harness actions, and a
caller that is about to cause calls it does not itself make declares how many
(``AGENT_CALLS_PER_TURN``). Counting agent turns would be counting the wrong
thing: a turn that searches twice and drafts costs four calls and a turn that
answers from the prompt costs one.

What this does not fix, and cannot from here: once a 429 does get through, the
application retries it three times a second or two apart and gives up, and
changing that would change how the application handles every member's request
(root ``CLAUDE.md``, rule 4). Pacing makes the 429 rare; what to do with the
execution it still costs is Q24's second half, and the author's.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Optional

from src.config import settings


class RateLimiter:
    """A sliding-window limiter: at most ``per_minute`` permits in any 60s.

    Sliding rather than a fixed minute boundary, because a quota that resets
    on the hour's minute lets a burst straddle two windows and exhaust both.

    ``clock`` and ``sleep`` are injectable so the tests are deterministic and
    take no wall-clock time; nothing else passes them.
    """

    WINDOW_S = 60.0

    def __init__(
        self,
        per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if per_minute < 1:
            raise ValueError("per_minute must be at least 1")
        self.per_minute = per_minute
        self._clock = clock
        self._sleep = sleep
        self._issued: deque[float] = deque()
        self._lock = threading.Lock()
        #: Total seconds spent waiting, reported with a run so the pacing's
        #: cost in wall clock is visible rather than inferred from the total.
        self.waited_s = 0.0

    def acquire(self, permits: int = 1) -> float:
        """Block until ``permits`` fit in the window. Returns seconds waited.

        A request larger than the whole budget would never fit and would wait
        for ever, so it is clamped to the budget: better a turn that uses the
        entire minute than a run that stops.
        """
        permits = max(1, min(permits, self.per_minute))
        waited = 0.0
        while True:
            with self._lock:
                now = self._clock()
                self._forget_expired(now)
                if len(self._issued) + permits <= self.per_minute:
                    self._issued.extend([now] * permits)
                    self.waited_s += waited
                    return waited
                # The oldest permit in the window is the first to leave it.
                wait = self._issued[0] + self.WINDOW_S - now
            wait = max(wait, 0.01)
            self._sleep(wait)
            waited += wait

    def _forget_expired(self, now: float) -> None:
        cutoff = now - self.WINDOW_S
        while self._issued and self._issued[0] <= cutoff:
            self._issued.popleft()


_limiter: Optional[RateLimiter] = None
_limiter_lock = threading.Lock()


def limiter() -> RateLimiter:
    """The process-wide budget. One, deliberately: two limiters sharing one
    key is the bug this module exists to fix."""
    global _limiter
    with _limiter_lock:
        if _limiter is None:
            _limiter = RateLimiter(settings.VERTEX_CALLS_PER_MINUTE)
        return _limiter


def reset_limiter(instance: Optional[RateLimiter] = None) -> None:
    """Replace the process-wide limiter. For tests, and for a notebook that
    wants to state its own budget."""
    global _limiter
    with _limiter_lock:
        _limiter = instance
