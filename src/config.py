"""Configuration for the regression testing harness.

Every variable the harness reads is declared here and nowhere else, and every
one of them comes from the environment (invariant 5 in ``CLAUDE.md``): from
``.env`` in this subtree, which is gitignored, or from the process environment,
which wins where both are set.

``Settings`` deliberately refuses to print itself. A config object is the one
thing in the pipeline that holds a service key, and a notebook that renders it
in an output cell commits that key to git history. Its ``repr`` and ``str`` are
therefore ``Settings(<redacted>)``; read a field by name when a value is needed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

SUBTREE_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = SUBTREE_ROOT / ".env"

#: Variables that must be set for the harness to run at all.
REQUIRED_VARS = (
    "SUPABASE_URL",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
    "VERTEX_API_KEY",
    "VERTEX_MODEL",
    "SIMULATOR_MODEL",
    "JUDGE_MODEL",
)

#: Variables that pin one manuscript revision; ``tools/manuscript.py`` falls
#: back to the newest revision in the default folder when they are unset.
OPTIONAL_VARS = (
    "MA_MANUSCRIPT",
    "MA_MANUSCRIPT_DIR",
)

_REDACTED = "Settings(<redacted>)"


class Settings(BaseModel):
    """The harness configuration. Never printed, never logged."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    SUPABASE_URL: str
    SUPABASE_SECRET_KEY: str
    SUPABASE_PUBLISHABLE_KEY: str
    VERTEX_API_KEY: str
    VERTEX_MODEL: str
    SIMULATOR_MODEL: str
    JUDGE_MODEL: str
    MA_MANUSCRIPT: Optional[str] = None
    MA_MANUSCRIPT_DIR: Optional[str] = None

    def __repr__(self) -> str:  # noqa: D105 - see module docstring
        return _REDACTED

    def __str__(self) -> str:  # noqa: D105 - see module docstring
        return _REDACTED


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    """Build ``Settings`` from ``env``, or from ``.env`` plus ``os.environ``.

    Raises ``RuntimeError`` naming every missing required variable — all of
    them at once, so a half-filled ``.env`` is fixed in one pass rather than one
    error at a time. A variable set to whitespace counts as missing; the
    ``.env.example`` template ships every key with an empty value, so a copied
    but unfilled file must not read as configured. The message names variables
    only, never values.
    """
    if env is None:
        load_dotenv(ENV_PATH)  # does not override what is already in os.environ
        env = os.environ

    def value_of(name: str) -> Optional[str]:
        raw = env.get(name)
        if raw is None:
            return None
        raw = raw.strip()
        return raw or None

    present = {name: value_of(name) for name in REQUIRED_VARS + OPTIONAL_VARS}
    missing = [name for name in REQUIRED_VARS if present[name] is None]
    if missing:
        raise RuntimeError(
            "Missing required configuration: "
            + ", ".join(missing)
            + f". Set these in {ENV_PATH} (copy .env.example and fill it in) or "
            "in the environment. Never inline a credential in a module or a "
            "notebook."
        )

    return Settings(**{name: v for name, v in present.items() if v is not None})


_settings: Optional[Settings] = None


def __getattr__(name: str) -> Settings:
    """Build ``settings`` on first access (PEP 562).

    ``from src.config import settings`` raises the ``RuntimeError`` above when
    the environment is incomplete, which is the intended behaviour: nothing in
    the harness should run half-configured. It is bound lazily rather than at
    module import so that importing ``load_settings`` or ``REQUIRED_VARS`` — as
    the tests and any tooling do — does not itself require a filled ``.env``.
    """
    if name != "settings":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
