"""MCP conformance: the wire contract every harness and persona assumes.

The server is spawned as a real stdio subprocess because stdout *is* the
JSON-RPC channel: only a live transport proves that ``tools/list``, ``ping``
and the ``symbol_resolve`` error envelopes still look the way the guides say.
Nothing here needs the network: the identity-missing paths return before any
request is issued, so no test is skipped for connectivity.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

VALUEBOT = Path(__file__).resolve().parents[2]
MCP_DIR = VALUEBOT / "mcp"

if str(VALUEBOT / "tests") not in sys.path:
    sys.path.insert(0, str(VALUEBOT / "tests"))
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from support_stdio import StdioClient  # noqa: E402

import server  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
REQUEST_TIMEOUT = 15.0

#: The expected tool set is read from the server registry, never copied here.
EXPECTED_TOOLS = frozenset(server.TOOL_NAMES) | frozenset(server.CORE_TOOLS)
EXPECTED_MODULES = frozenset(server.MODULE_TOOLS)


class Session:
    """One initialized child server, with per-request ids and timeouts."""

    def __init__(self, proc: subprocess.Popen[str], stderr_file, client) -> None:
        self.proc = proc
        self.stderr_file = stderr_file
        self.client: StdioClient = client
        self._next_id = 0

    def request(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        self.client.send(payload)
        return self.client.wait_for(self._next_id, timeout=REQUEST_TIMEOUT)

    def notify(self, method: str, params: dict | None = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self.client.send(payload)

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self.request(
            "tools/call", {"name": name, "arguments": arguments}
        )

    def close(self) -> None:
        self.client.close()
        self.stderr_file.close()
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=REQUEST_TIMEOUT)


def _tool_payload(reply: dict) -> dict:
    """Decode the JSON envelope a tool returned in its first text block."""
    return json.loads(reply["result"]["content"][0]["text"])


@pytest.fixture(scope="module")
def session(tmp_path_factory) -> Session:
    """Spawn one server with no SEC identity and complete the handshake."""
    data_dir = tmp_path_factory.mktemp("mcp-conformance")
    env = dict(os.environ)
    env.update(
        {
            "PLUGIN_DATA": str(data_dir / "data"),
            "PYTHONUNBUFFERED": "1",
        }
    )
    # The unconfigured-identity envelope is only reachable without these.
    env.pop("SEC_USER_AGENT", None)
    env.pop("EDGAR_IDENTITY", None)

    stderr_file = open(data_dir / "stderr.log", "w+", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(MCP_DIR / "server.py")],
        cwd=str(MCP_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_file,
        text=True,
        bufsize=1,
        env=env,
    )
    client = StdioClient(proc, stderr_file)
    live = Session(proc, stderr_file, client)
    try:
        init = live.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "contract-conformance", "version": "0.0.1"},
            },
        )
        assert "result" in init, live.client.stderr_text()
        assert init["result"]["serverInfo"] == {
            "name": "valuebot",
            "version": "0.2.0",
        }
        live.notify("notifications/initialized")
        yield live
    finally:
        live.close()


def test_tools_list_matches_the_server_registry(session: Session):
    reply = session.request("tools/list")
    tools = reply["result"]["tools"]
    names = [tool["name"] for tool in tools]

    assert len(names) == len(set(names)), f"duplicate tool names: {names}"
    assert set(names) == set(EXPECTED_TOOLS), (
        f"missing: {sorted(EXPECTED_TOOLS - set(names))}; "
        f"unexpected: {sorted(set(names) - EXPECTED_TOOLS)}"
    )
    assert len(names) == 19
    assert all(tool.get("description") for tool in tools), "tool without description"


def test_ping_reports_every_module_ready(session: Session):
    payload = _tool_payload(session.call_tool("ping", {}))

    assert payload["ok"] is True
    assert payload["module"] == "core"
    assert payload["tool"] == "ping"
    states = payload["data"]["modules"]
    assert set(states) == set(EXPECTED_MODULES)
    assert {name: state["status"] for name, state in states.items()} == {
        name: "ready" for name in EXPECTED_MODULES
    }
    assert set(payload["data"]["tools"]) == set(EXPECTED_TOOLS)


def test_symbol_resolve_without_arguments_is_a_validation_error(session: Session):
    reply = session.call_tool("symbol_resolve", {})
    result = reply["result"]

    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert "validation error" in text.lower()
    assert "query" in text


def test_symbol_resolve_without_identity_is_a_typed_error(session: Session):
    payload = _tool_payload(session.call_tool("symbol_resolve", {"query": "AAPL"}))

    assert payload["ok"] is False
    assert payload["module"] == "fundamentals"
    assert payload["tool"] == "symbol_resolve"
    assert payload["error"]["code"] == "identity_not_configured"
    assert payload["error"]["message"]
