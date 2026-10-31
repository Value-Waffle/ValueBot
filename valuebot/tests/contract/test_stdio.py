"""stdio contract: JSON-RPC only on stdout and every tool registered."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

VALUEBOT = Path(__file__).resolve().parents[2]
MCP_DIR = VALUEBOT / "mcp"

sys.path.insert(0, str(VALUEBOT / "tests"))
from support_stdio import StdioClient  # noqa: E402

from core import citations  # noqa: E402


def _start(tmp_path, *, drop_identity: bool = False, bootstrap: Path | None = None):
    env = dict(os.environ)
    env.update(
        {
            "PLUGIN_DATA": str(tmp_path / "data"),
            "SEC_USER_AGENT": "example-user@gmail.com",
            "PYTHONUNBUFFERED": "1",
        }
    )
    if drop_identity:
        env.pop("SEC_USER_AGENT", None)
        env.pop("EDGAR_IDENTITY", None)
    stderr_file = open(tmp_path / "stderr.log", "w+", encoding="utf-8")
    entrypoint = bootstrap if bootstrap is not None else MCP_DIR / "server.py"
    proc = subprocess.Popen(
        [sys.executable, str(entrypoint)],
        cwd=str(MCP_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_file,
        text=True,
        bufsize=1,
        env=env,
    )
    return proc, stderr_file, StdioClient(proc, stderr_file)


def test_stdio_lists_tools_and_ping(tmp_path):
    proc, stderr_file, client = _start(tmp_path)
    try:
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "contract", "version": "0.0.1"},
                },
            }
        )
        init = client.wait_for(1)
        assert "result" in init

        client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        client.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listing = client.wait_for(2)
        names = {tool["name"] for tool in listing["result"]["tools"]}
        assert "ping" in names
        assert "citation_resolve" in names
        assert "citation_view" in names
        assert len(names) == 19
        assert {
            "facts_query", "facts_export", "ratio_compute", "dcf_compute",
            "report_section"
        } <= names

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "ping", "arguments": {}},
            }
        )
        response = client.wait_for(3)
        payload = json.loads(response["result"]["content"][0]["text"])
        assert payload["ok"] is True
        assert payload["module"] == "core"
        assert set(payload["data"]["tools"]) == names
        states = payload["data"]["modules"]
        assert all(state["status"] == "ready" for state in states.values())
        assert payload["data"]["identity_configured"] is True
        assert payload["data"]["identity_source"] == "env"
    finally:
        client.close()
        stderr_file.close()
        if proc.poll() is None:
            proc.kill()


def test_citation_resolve_returns_jsonrpc_error_envelope(tmp_path):
    proc, stderr_file, client = _start(tmp_path)
    try:
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "contract", "version": "0.0.1"},
                },
            }
        )
        assert "result" in client.wait_for(1)
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "citation_resolve",
                    "arguments": {
                        "citation": {
                            "key": "abc",
                            "label": "url-only citation",
                            "source": "local",
                        }
                    },
                },
            }
        )
        result = client.wait_for(2)["result"]
        payload = json.loads(result["content"][0]["text"])
        assert payload["ok"] is False
        assert payload["module"] == "core"
        assert payload["tool"] == "citation_resolve"
        assert payload["error"]["code"] == "citation_unresolvable"
    finally:
        client.close()
        stderr_file.close()
        if proc.poll() is None:
            proc.kill()


def test_unconfigured_identity_blocks_data_tools(tmp_path):
    proc, stderr_file, client = _start(tmp_path, drop_identity=True)
    try:
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "contract", "version": "0.0.1"},
                },
            }
        )
        assert "result" in client.wait_for(1)
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "ping", "arguments": {}},
            }
        )
        ping = json.loads(client.wait_for(2)["result"]["content"][0]["text"])
        assert ping["data"]["identity_configured"] is False
        assert ping["data"]["identity_source"] == "missing"

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "facts_query", "arguments": {"symbol": "AAPL"}},
            }
        )
        response = json.loads(client.wait_for(3)["result"]["content"][0]["text"])
        assert response["ok"] is False
        assert response["error"]["code"] == "identity_not_configured"
        assert "setup" in response["error"]["hint"].lower()
    finally:
        client.close()
        stderr_file.close()
        if proc.poll() is None:
            proc.kill()


_BOOTSTRAP = '''
import sys

sys.path.insert(0, {mcp_dir!r})

import server  # noqa: E402
from core import citations  # noqa: E402


class _DemoResolver:
    def resolve(self, artifact, *, offset=0, limit=8000):
        return {{
            "kind": artifact.get("kind", "demo"),
            "format": "md",
            "chunk": "<script>alert(1)</script> evidence",
            "next_offset": None,
            "total_chars": 30,
        }}


citations.register_resolver("demo", _DemoResolver())
server.main()
'''


def _initialize(client) -> None:
    client.send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "contract", "version": "0.0.1"},
            },
        }
    )
    assert "result" in client.wait_for(1)
    client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})


def test_citation_view_returns_an_inline_ui_resource(tmp_path):
    bootstrap = tmp_path / "bootstrap_citation_view.py"
    bootstrap.write_text(_BOOTSTRAP.format(mcp_dir=str(MCP_DIR)), encoding="utf-8")
    proc, stderr_file, client = _start(tmp_path, bootstrap=bootstrap)
    try:
        _initialize(client)

        token = citations.citation_id(
            {"module": "demo", "kind": "demo", "format": "md", "status": "cached"}
        )
        assert token

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "citation_view",
                    "arguments": {"citation_id": token},
                },
            }
        )
        result = client.wait_for(2)["result"]
        assert not result.get("isError")
        content = result["content"]
        assert isinstance(content, list) and len(content) == 2

        summary = content[0]
        assert summary["type"] == "text"
        uri = f"ui://valuebot/evidence/{token}"
        # The URI is the resource address only: the model must never see it.
        assert uri not in summary["text"]
        assert "ui://" not in summary["text"]
        assert "kind: demo" in summary["text"]
        assert "format: md" in summary["text"]
        assert "chars: 30" in summary["text"]

        block = content[1]
        assert block["type"] == "resource"
        assert block["resource"]["uri"] == uri
        assert block["resource"]["mimeType"] == "text/html"
        page = block["resource"]["text"]
        assert page.lstrip().lower().startswith("<!doctype html")
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
        assert "<script>" not in page

        # stdout is the JSON-RPC channel: nothing else may appear on it.
        assert all(line.lstrip().startswith("{") for line in client.lines)
    finally:
        client.close()
        stderr_file.close()
        if proc.poll() is None:
            proc.kill()


def test_citation_view_explains_a_miss_instead_of_raising(tmp_path):
    proc, stderr_file, client = _start(tmp_path)
    try:
        _initialize(client)

        token = citations.citation_id({"module": "calendar", "kind": "demo"})
        assert token

        client.send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "citation_view",
                    "arguments": {"citation_id": token},
                },
            }
        )
        result = client.wait_for(2)["result"]
        assert not result.get("isError")
        content = result["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert "citation_unresolvable" in content[0]["text"]
        # A miss is terminal: the text must forbid a retry rather than point the
        # model at another tool, which would start a retry loop.
        assert "Do not retry" in content[0]["text"]
    finally:
        client.close()
        stderr_file.close()
        if proc.poll() is None:
            proc.kill()
