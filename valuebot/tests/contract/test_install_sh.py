"""Contract for install.sh: create-or-merge harness MCP configs, offline."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

VALUEBOT = Path(__file__).resolve().parents[2]
INSTALL = VALUEBOT / "install.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("sh") is None, reason="POSIX sh is not available"
)


def run_install(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("sh") or "sh", str(INSTALL), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_lists_supported_harnesses(tmp_path):
    result = run_install("--help", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    for harness in (
        "claude-desktop",
        "claude-code",
        "vscode",
        "copilot-cli",
        "gemini-cli",
    ):
        assert harness in result.stdout


def test_dry_run_writes_nothing_and_prints_json(tmp_path):
    config = tmp_path / ".vscode" / "mcp.json"

    result = run_install(
        "--harness",
        "vscode",
        "--config",
        str(config),
        "--data",
        str(tmp_path / "data"),
        "--dry-run",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert not config.exists()
    assert not config.parent.exists()
    payload = json.loads(result.stdout)
    entry = payload["servers"]["vw-mcp"]
    assert entry["command"] == "sh"
    assert entry["args"] == [str(VALUEBOT / "mcp" / "run.sh")]
    assert entry["env"] == {
        "PLUGIN_DATA": str(tmp_path / "data"),
        "EDGAR_LOCAL_DATA_DIR": str(tmp_path / "data" / "edgar"),
        "EDGAR_HTTP_TIMEOUT": "30",
        "EDGAR_RATE_LIMIT_PER_SEC": "5",
        "UV_PROJECT_ENVIRONMENT": str(tmp_path / "data" / "uv-env"),
        "UV_CACHE_DIR": str(tmp_path / "data" / "uv-cache"),
        "UV_PYTHON_INSTALL_DIR": str(tmp_path / "data" / "uv-python"),
    }


def test_merge_preserves_other_servers_and_keys(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text(
        json.dumps({"servers": {"other": {"command": "x"}}, "extra": 1}),
        encoding="utf-8",
    )

    result = run_install(
        "--harness",
        "vscode",
        "--config",
        str(config),
        "--data",
        str(tmp_path / "data"),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert f"wrote {config}" in result.stdout
    assert "merged" in result.stdout
    payload = json.loads(config.read_text(encoding="utf-8"))
    assert payload["extra"] == 1
    assert payload["servers"]["other"] == {"command": "x"}
    assert payload["servers"]["vw-mcp"]["command"] == "sh"


def test_merge_creates_missing_top_level_key(tmp_path):
    """A fresh Claude Desktop config has no mcpServers key at all."""
    config = tmp_path / "claude_desktop_config.json"
    original = {"preferences": {"x": 1}, "coworkUserFilesPath": "/tmp/claude"}
    config.write_text(json.dumps(original), encoding="utf-8")
    before = config.read_bytes()

    result = run_install(
        "--harness",
        "claude-desktop",
        "--config",
        str(config),
        "--data",
        str(tmp_path / "data"),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert f"wrote {config}" in result.stdout
    assert "merged" in result.stdout
    assert "not an object" not in result.stderr

    payload = json.loads(config.read_text(encoding="utf-8"))
    # (a) the server entry was created
    assert payload["mcpServers"]["vw-mcp"]["command"] == "sh"
    assert payload["mcpServers"]["vw-mcp"]["args"] == [str(VALUEBOT / "mcp" / "run.sh")]
    env = payload["mcpServers"]["vw-mcp"]["env"]
    assert env["PLUGIN_DATA"] == str(tmp_path / "data")
    assert env["EDGAR_LOCAL_DATA_DIR"] == str(tmp_path / "data" / "edgar")
    assert "type" not in payload["mcpServers"]["vw-mcp"]
    # (b) unrelated keys survive byte-for-byte and in their original order
    assert json.dumps(payload["preferences"]) == json.dumps(original["preferences"])
    assert payload["coworkUserFilesPath"] == original["coworkUserFilesPath"]
    assert list(payload) == ["preferences", "coworkUserFilesPath", "mcpServers"]
    # (c) the file on disk is valid JSON and is not the untouched original
    assert json.loads(config.read_text(encoding="utf-8")) == payload
    assert config.read_bytes() != before


def test_rerun_replaces_existing_entry(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text(
        json.dumps({"mcpServers": {"vw-mcp": {"command": "stale", "args": []}}}),
        encoding="utf-8",
    )

    result = run_install(
        "--harness",
        "claude-code",
        "--config",
        str(config),
        "--data",
        str(tmp_path / "data"),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    raw = config.read_text(encoding="utf-8")
    assert raw.count('"vw-mcp"') == 1
    entry = json.loads(raw)["mcpServers"]["vw-mcp"]
    assert entry["command"] == "sh"
    assert entry["type"] == "stdio"
    assert entry["args"] == [str(VALUEBOT / "mcp" / "run.sh")]


def test_unsupported_harness_exits_two(tmp_path):
    config = tmp_path / "mcp.json"

    result = run_install(
        "--harness",
        "librechat",
        "--config",
        str(config),
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "librechat/INSTALL.md" in result.stderr
    assert not config.exists()


def test_corrupt_file_is_backed_up_then_replaced(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text("{this is not json", encoding="utf-8")

    result = run_install(
        "--harness",
        "gemini-cli",
        "--config",
        str(config),
        "--data",
        str(tmp_path / "data"),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "backed up" in result.stderr
    backups = list(tmp_path.glob("mcp.json.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{this is not json"
    entry = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["vw-mcp"]
    assert entry["command"] == "sh"
