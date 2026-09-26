"""Simulated members (B01).

The simulator drives the application as a member would (§3.3), so it needs
accounts: deterministic emails under an undeliverable domain, one shared
password from the environment, and — the part that makes the runs visible to
the study at all — a ``study_sessions`` row with ``run_type = 'simulation'``
(D15) on each, because the turn logger (A02) writes nothing for an account
without a consented session.

Idempotent: an existing account is reused, an existing session kept. Nothing
here prints an email, a token or a key; ``--check`` prints pseudonymous ids.

    python -m src.auth --check
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from supabase import create_client

from src import db
from src.config import settings

CONSENT_VERSION_SIMULATION = "simulation"


@dataclass(frozen=True)
class SimUser:
    index: int
    id: str
    email: str
    session_id: str

    @property
    def label(self) -> str:
        """What logs and notebooks show: never the email."""
        return f"sim-{self.index:02d} ({self.id[:8]})"


def sim_email(index: int) -> str:
    return f"sim-{index:02d}@{settings.SIM_USER_DOMAIN}"


def _password() -> str:
    if not settings.SIM_USER_PASSWORD:
        raise RuntimeError("SIM_USER_PASSWORD is not set; the simulated accounts need one (see .env.example)")
    return settings.SIM_USER_PASSWORD


def _find_user_id(email: str) -> str | None:
    page = 1
    while True:
        users = db.admin().auth.admin.list_users(page=page, per_page=200)
        if not users:
            return None
        for user in users:
            if user.email == email:
                return user.id
        if len(users) < 200:
            return None
        page += 1


def _ensure_user(index: int) -> tuple[str, str]:
    email = sim_email(index)
    existing = _find_user_id(email)
    if existing:
        return existing, email
    created = db.admin().auth.admin.create_user(
        {
            "email": email,
            "password": _password(),
            "email_confirm": True,
            "user_metadata": {"username": f"sim_{index:02d}", "display_name": f"Sim {index:02d}", "onboarded": True},
        }
    )
    return created.user.id, email


def _ensure_session(user_id: str) -> str:
    rows = (
        db.admin()
        .table("study_sessions")
        .select("id")
        .eq("user_id", user_id)
        .eq("run_type", "simulation")
        .not_.is_("consent_at", "null")
        .is_("declined_at", "null")
        .order("consent_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if rows:
        return rows[0]["id"]
    inserted = (
        db.admin()
        .table("study_sessions")
        .insert(
            {
                "user_id": user_id,
                "run_type": "simulation",
                "consent_version": CONSENT_VERSION_SIMULATION,
                "consent_at": datetime.now(timezone.utc).isoformat(),
                "device_type": "harness",
                "client_session_id": "harness",
            }
        )
        .execute()
        .data
    )
    return inserted[0]["id"]


def ensure_sim_users(count: int | None = None) -> list[SimUser]:
    """The simulated accounts, created on first call, each with a live simulation session."""
    users: list[SimUser] = []
    for index in range(1, (count or settings.SIM_USER_COUNT) + 1):
        user_id, email = _ensure_user(index)
        users.append(SimUser(index=index, id=user_id, email=email, session_id=_ensure_session(user_id)))
    return users


def sign_in(user: SimUser) -> str:
    """A fresh JWT for one simulated member, through the same password grant a browser uses."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_PUBLISHABLE_KEY)
    response = client.auth.sign_in_with_password({"email": user.email, "password": _password()})
    if not response.session:
        raise RuntimeError(f"sign-in failed for {user.label}")
    return response.session.access_token


def _jwt_expiry(token: str) -> float | None:
    """The `exp` claim of a JWT, read without verifying it (the API verifies)."""
    import base64
    import json

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except Exception:
        return None


class Session:
    """A simulated member's JWT that renews itself before it expires.

    Supabase access tokens live an hour. The runner used to sign in once and
    reuse the token, so every run longer than an hour died with a 401 on the
    first request after it — the first overnight B10 attempt stopped at exactly
    60 minutes. `token` re-signs in (the same password grant a browser uses)
    whenever less than ``margin`` remains, so each execution starts with at
    least that much validity; one execution takes minutes.
    """

    def __init__(self, user: SimUser, margin_s: int = 15 * 60, clock=time.time) -> None:
        self.user = user
        self.margin_s = margin_s
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0
        self.renewals = 0

    def _sign_in(self) -> tuple[str, float]:
        token = sign_in(self.user)
        return token, _jwt_expiry(token) or (self._clock() + 3600)

    def invalidate(self) -> None:
        """Force the next read to sign in again — after the API said 401."""
        self._token = None

    @property
    def token(self) -> str:
        if self._token is None or self._expires_at - self._clock() < self.margin_s:
            if self._token is not None:
                self.renewals += 1
            self._token, self._expires_at = self._sign_in()
        return self._token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulated members for the regression-testing harness.")
    parser.add_argument("--check", action="store_true", help="ensure the accounts exist, sign each in, print pseudonymous ids")
    parser.add_argument("--count", type=int, default=None)
    args = parser.parse_args(argv)
    users = ensure_sim_users(args.count)
    if args.check:
        for user in users:
            token = sign_in(user)
            print(f"{user.label}: session {user.session_id[:8]}, signed in ({len(token)} chars)")
    else:
        print(f"{len(users)} simulated accounts ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
