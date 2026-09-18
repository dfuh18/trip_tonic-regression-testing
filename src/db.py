"""Supabase clients for the harness.

Two roles, kept apart on purpose. The **admin** client (service key) reads the
study tables and writes the run and case-execution rows — the harness is the
one writer of the run level (event-model.md). A **user** client carries a
simulated member's JWT and sees exactly what that member sees, which is how
the simulator stays on the member's side of RLS when it writes the chat rows
the browser would write. Neither client is ever printed.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, ClientOptions, create_client

from src.config import settings


@lru_cache(maxsize=1)
def admin() -> Client:
    """Service-key client: bypasses RLS. For the study tables and auth admin."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)


def for_user(access_token: str) -> Client:
    """RLS-scoped client for one simulated member, exactly as the browser has it."""
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_PUBLISHABLE_KEY,
        options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"}),
    )


def api_headers(access_token: str, **extra: str) -> dict[str, str]:
    """Headers the browser sends the Fastify API, for the same request path."""
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Device-Type": "desktop",
        "X-Session-Id": "harness",
        "Content-Type": "application/json",
        **extra,
    }
