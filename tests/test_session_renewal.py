"""The simulated member's JWT renews itself before it expires.

The first overnight B10 attempt died with a 401 exactly one hour after it
started: the runner signed in once and reused the token past its lifetime.
"""

from __future__ import annotations

from src import auth


class FakeSession(auth.Session):
    """No network: each sign-in issues a token valid for an hour of fake time."""

    def __init__(self) -> None:
        self.now = 1_000.0
        super().__init__(user=None, margin_s=15 * 60, clock=lambda: self.now)  # type: ignore[arg-type]
        self.issued = 0

    def _sign_in(self):
        self.issued += 1
        return f"jwt-{self.issued}", self.now + 3600


def test_the_first_read_signs_in():
    s = FakeSession()
    assert s.token == "jwt-1"
    assert s.renewals == 0


def test_a_token_is_reused_while_well_inside_its_hour():
    s = FakeSession()
    s.token
    s.now += 40 * 60  # 20 minutes left: above the 15-minute margin
    assert s.token == "jwt-1"


def test_a_token_is_renewed_before_the_margin_and_long_before_expiry():
    s = FakeSession()
    s.token
    s.now += 46 * 60  # 14 minutes left
    assert s.token == "jwt-2"
    assert s.renewals == 1


def test_a_long_run_never_reads_an_expired_token():
    s = FakeSession()
    expires = {}
    for minute in range(0, 6 * 60, 2):  # six hours, one execution every two minutes
        s.now = 1_000.0 + minute * 60
        token = s.token
        expires.setdefault(token, s._expires_at)
        assert expires[token] - s.now >= 15 * 60


# --- a 401 is the harness's session, never the agent (D95) -------------------

from src.runner import failure_class  # noqa: E402


def test_a_401_on_the_agents_turn_is_auth_not_agent():
    assert failure_class("agent returned 401: Unauthorized") == "auth"
    assert failure_class("simulator: API 401 Unauthorized") == "auth"


def test_401_digits_inside_an_id_or_a_number_are_not_a_status():
    assert failure_class("agent returned 502 after 4012 ms") == "agent"
    assert failure_class("agent returned 502 (trace 1a4012bc)") == "agent"


def test_other_classes_are_unchanged():
    assert failure_class("agent returned 503") == "platform"
    assert failure_class("agent returned 429") == "ours"
    assert failure_class("agent returned 504") == "agent"
