"""Package schema: the two manifests a harness loads must stay in step.

Only local files are read. Remote schema URLs are never fetched: when no local
schema file ships with the package, that single assertion is skipped.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

VALUEBOT = Path(__file__).resolve().parents[2]
PLUGIN_JSON = VALUEBOT / "plugin.json"
MCP_JSON = VALUEBOT / "mcp.json"
HARNESS_README = VALUEBOT / "harnesses" / "README.md"

#: ``KEY=value`` lines in the harness environment block, e.g. ``VW_ENABLE_PRICE=0``.
DOCUMENTED_ENV = re.compile(r"^((?:EDGAR|VW|UV)_[A-Z0-9_]+)=", re.MULTILINE)

#: The harness guide documents exactly this many environment keys.
DOCUMENTED_ENV_COUNT = 13


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path.name} is not a JSON object"
    return payload


def _vw_server() -> dict:
    servers = _load(MCP_JSON)["mcpServers"]
    assert "vw-mcp" in servers, sorted(servers)
    return servers["vw-mcp"]


def test_plugin_manifest_shape():
    manifest = _load(PLUGIN_JSON)
    assert manifest["$schema"], "plugin.json has no $schema"
    assert manifest["name"] == "valuebot"


def test_mcp_manifest_declares_a_stdio_server():
    server = _vw_server()
    assert server["type"] == "stdio"
    assert any("${PLUGIN_ROOT}" in str(arg) for arg in server["args"]), server["args"]
    assert "${PLUGIN_ROOT}" in str(server.get("cwd", "")), server.get("cwd")


def test_mcp_env_covers_every_documented_key():
    documented = set(DOCUMENTED_ENV.findall(HARNESS_README.read_text(encoding="utf-8")))
    assert len(documented) == DOCUMENTED_ENV_COUNT, (
        f"harnesses/README.md documents {sorted(documented)}"
    )

    env = set(_vw_server()["env"])
    missing = documented - env
    assert not missing, f"mcp.json env is missing {sorted(missing)}"


def _local_schema(name: str) -> Path | None:
    """Return a schema shipped in the package, or ``None`` (never fetched)."""
    for base in (VALUEBOT, VALUEBOT.parent):
        for relative in (name, f"schemas/{name}"):
            candidate = base / relative
            if candidate.is_file():
                return candidate
    return None


@pytest.mark.parametrize(
    ("manifest", "schema_name"),
    [(PLUGIN_JSON, "plugin.schema.json"), (MCP_JSON, "mcp.schema.json")],
)
def test_manifest_matches_local_schema(manifest: Path, schema_name: str):
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = _local_schema(schema_name)
    if schema_path is None:
        pytest.skip(f"no local {schema_name}; remote schemas are never fetched")
    jsonschema.validate(
        _load(manifest), json.loads(schema_path.read_text(encoding="utf-8"))
    )
