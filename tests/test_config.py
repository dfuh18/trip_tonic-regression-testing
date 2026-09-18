"""Tests for ``src.config``.

Every case builds ``Settings`` from an explicit mapping rather than from the
process environment, so the suite does not depend on whether a ``.env`` exists
on the machine running it.
"""

from __future__ import annotations

import pytest

import src.config as config
from src.config import OPTIONAL_VARS, REQUIRED_VARS, Settings, load_settings

SECRET = "sk-must-never-be-printed"


def complete_env() -> dict[str, str]:
    return {name: f"value-for-{name}" for name in REQUIRED_VARS}


def test_complete_env_loads() -> None:
    settings = load_settings(complete_env())
    assert settings.SUPABASE_URL == "value-for-SUPABASE_URL"
    assert settings.JUDGE_MODEL == "value-for-JUDGE_MODEL"


def test_optional_variables_default_to_none() -> None:
    settings = load_settings(complete_env())
    for name in OPTIONAL_VARS:
        assert getattr(settings, name) is None


def test_optional_variables_are_read_when_set() -> None:
    env = complete_env()
    env["MA_MANUSCRIPT"] = "C:/thesis/MA_Thesis_260917.docx"
    settings = load_settings(env)
    assert settings.MA_MANUSCRIPT == "C:/thesis/MA_Thesis_260917.docx"
    assert settings.MA_MANUSCRIPT_DIR is None


@pytest.mark.parametrize("missing", REQUIRED_VARS)
def test_missing_variable_raises_naming_it(missing: str) -> None:
    env = complete_env()
    del env[missing]
    with pytest.raises(RuntimeError, match=missing):
        load_settings(env)


def test_blank_variable_counts_as_missing() -> None:
    env = complete_env()
    env["VERTEX_API_KEY"] = "   "
    with pytest.raises(RuntimeError, match="VERTEX_API_KEY"):
        load_settings(env)


def test_error_names_every_missing_variable_at_once() -> None:
    env = complete_env()
    del env["SUPABASE_URL"]
    del env["JUDGE_MODEL"]
    with pytest.raises(RuntimeError) as excinfo:
        load_settings(env)
    message = str(excinfo.value)
    assert "SUPABASE_URL" in message
    assert "JUDGE_MODEL" in message


def test_error_message_holds_no_values() -> None:
    env = complete_env()
    env["SUPABASE_SECRET_KEY"] = SECRET
    del env["VERTEX_MODEL"]
    with pytest.raises(RuntimeError) as excinfo:
        load_settings(env)
    assert SECRET not in str(excinfo.value)


def test_repr_and_str_are_redacted() -> None:
    env = complete_env()
    env["SUPABASE_SECRET_KEY"] = SECRET
    settings = load_settings(env)

    rendered = [repr(settings), str(settings), f"{settings}", "{}".format(settings)]
    for text in rendered:
        assert text == "Settings(<redacted>)"
        assert SECRET not in text
        for name in REQUIRED_VARS:
            assert env[name] not in text


def test_repr_of_a_container_does_not_leak() -> None:
    # A notebook cell that prints a list or dict falls back to repr on the
    # contained object, which is the leak path a plain __str__ override misses.
    env = complete_env()
    env["SUPABASE_SECRET_KEY"] = SECRET
    settings = load_settings(env)
    assert SECRET not in repr([settings])
    assert SECRET not in repr({"config": settings})


def test_unknown_variable_is_rejected() -> None:
    with pytest.raises(Exception):
        Settings(**complete_env(), SOMETHING_ELSE="x")


def test_settings_attribute_raises_when_the_environment_is_incomplete(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(config, "_settings", None)
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / "absent.env")
    monkeypatch.setattr(config.os, "environ", {})
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        config.settings


def test_settings_attribute_reads_the_environment_and_stays_redacted(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(config, "_settings", None)
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / "absent.env")
    monkeypatch.setattr(config.os, "environ", dict(complete_env(), SUPABASE_SECRET_KEY=SECRET))

    settings = config.settings
    assert settings.SUPABASE_SECRET_KEY == SECRET
    assert str(settings) == "Settings(<redacted>)"
    assert settings is config.settings  # built once, then cached
