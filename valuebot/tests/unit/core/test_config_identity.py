"""The SEC User-Agent is configured once and required for every run."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core import config, identity, setup  # noqa: E402
from core.errors import IdentityNotConfigured  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    config.refresh()
    yield tmp_path / "data"
    config.refresh()


def test_unconfigured_by_default(tmp_path):
    assert config.SEC_USER_AGENT == ""
    assert config.identity_configured() is False
    assert config.identity_source() == "missing"
    assert config.identity_file() == tmp_path / "data" / "identity.json"
    with pytest.raises(IdentityNotConfigured):
        config.require_identity()


def test_env_override_is_normalized(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "example-user@gmail.com")
    config.refresh()
    assert config.SEC_USER_AGENT == "valuebot example-user@gmail.com"
    assert config.EDGAR_IDENTITY == config.SEC_USER_AGENT
    assert config.identity_source() == "env"
    assert config.require_identity() == "valuebot example-user@gmail.com"


def test_legacy_alias_still_works(monkeypatch):
    monkeypatch.setenv("EDGAR_IDENTITY", "Value Waffle research@waffle.dev")
    config.refresh()
    assert config.SEC_USER_AGENT == "Value Waffle research@waffle.dev"
    assert config.identity_source() == "env (EDGAR_IDENTITY alias)"


def test_file_setup_persists_across_restarts(tmp_path):
    target = identity.save(tmp_path / "data", "example-user@gmail.com")
    assert stat.S_IMODE(target.stat().st_mode) == 0o600

    config.refresh()
    assert config.SEC_USER_AGENT == "valuebot example-user@gmail.com"
    assert config.identity_source() == "file"
    assert config.identity_configured() is True


def test_env_wins_over_file(tmp_path, monkeypatch):
    identity.save(tmp_path / "data", "file-user@waffle.dev")
    monkeypatch.setenv("SEC_USER_AGENT", "env-user@waffle.dev")
    config.refresh()
    assert config.SEC_USER_AGENT == "valuebot env-user@waffle.dev"
    assert config.identity_source() == "env"


def test_setup_cli_saves_shows_and_resets(tmp_path, capsys):
    assert setup.main(["example-user@gmail.com"]) == 0
    assert "User-Agent: valuebot example-user@gmail.com" in capsys.readouterr().out
    assert (tmp_path / "data" / "identity.json").is_file()

    config.refresh()
    assert setup.main(["--show"]) == 0
    assert capsys.readouterr().out.strip() == "valuebot example-user@gmail.com"

    assert setup.main(["--reset"]) == 0
    config.refresh()
    assert config.identity_configured() is False


def test_setup_cli_rejects_placeholders(tmp_path, capsys):
    assert setup.main(["research@example.com"]) == 2
    assert "real contact email" in capsys.readouterr().err
    assert not (tmp_path / "data" / "identity.json").exists()


def test_angle_brackets_are_stripped(tmp_path):
    identity.save(tmp_path / "data", "Value Waffle <research@waffle.dev>")
    config.refresh()
    assert config.SEC_USER_AGENT == "Value Waffle research@waffle.dev"
