"""Packaging contract: manifests, skills and agent allowlists."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

VALUEBOT = Path(__file__).resolve().parents[2]
MCP_DIR = VALUEBOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402

from core import citations  # noqa: E402
from core.errors import CitationUnresolvable  # noqa: E402

V1_ONLY_TOOLS = {
    "facts_statement", "filing_tables", "filing_sections", "filing_section",
    "data_availability", "proxy_persons", "leadership_read", "insider_read",
    "price_summary",
}


def test_plugin_manifest():
    manifest = json.loads((VALUEBOT / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "valuebot"
    assert manifest["version"] == "0.2.0"
    assert "xbrl" in manifest["keywords"]


def test_mcp_manifest_env():
    manifest = json.loads((VALUEBOT / "mcp.json").read_text(encoding="utf-8"))
    env = manifest["mcpServers"]["vw-mcp"]["env"]
    assert "SEC_USER_AGENT" not in env
    assert "EDGAR_IDENTITY" not in env
    assert "EDGAR_LOCAL_DATA_DIR" in env
    assert env["EDGAR_RATE_LIMIT_PER_SEC"] == "5"
    assert "VW_MCP_CACHE" not in env
    assert "VW_DB_ROOT" not in env


def test_server_instructions_route_over_web_search():
    instructions = server.INSTRUCTIONS
    assert instructions.strip()
    # The routing paragraph is what makes the model prefer these tools over
    # web search; deleting it silently would regress tool selection.
    assert "SEC" in instructions
    assert "web search" in instructions


def test_every_agent_allowlist_is_valid():
    files = sorted((VALUEBOT / "agent-builder-exports").glob("*.json"))
    assert len(files) == 6
    # An agent allowlist may name module tools and core tools. The
    # grounded-citation skill requires citation_resolve / citation_view, which
    # live in CORE_TOOLS and are deliberately absent from TOOL_NAMES, so
    # checking against TOOL_NAMES alone would forbid the citation protocol.
    allowed = set(server.TOOL_NAMES) | set(server.CORE_TOOLS)
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schemaVersion"] == "1.0.0"
        tools = set(payload["tools"])
        assert tools <= allowed, (path.name, tools - allowed)
        for skill in payload["skills"]:
            skill_path = VALUEBOT / skill / "SKILL.md"
            assert skill_path.exists(), skill_path
        assert payload["instructions"].strip()


def test_skills_exist():
    for name in (
        "grounded-citation", "hypothesis-analysis", "ratio-analysis",
        "dcf-valuation", "semantic-report-reading",
    ):
        assert (VALUEBOT / "skills" / name / "SKILL.md").is_file(), name


def test_no_v1_tool_names_in_packaging_docs():
    for path in list((VALUEBOT / "skills").rglob("*.md")) + list(
        (VALUEBOT / "agent-builder-exports").glob("*.json")
    ) + list((VALUEBOT / "docs").glob("*.md")) + [VALUEBOT / "README.md"]:
        text = path.read_text(encoding="utf-8")
        for tool in V1_ONLY_TOOLS:
            assert tool not in text, f"{path}: stale tool {tool}"


def test_core_and_module_tool_registries():
    assert "facts_export" in server.MODULE_TOOLS["fundamentals"]
    assert server.TOOL_MODULES["facts_export"] == "fundamentals"
    assert server.CORE_TOOLS == ("ping", "citation_resolve", "citation_view")
    assert "citation_resolve" not in server.TOOL_NAMES
    assert "citation_view" not in server.TOOL_NAMES


def test_resolvers_cover_exactly_the_available_modules():
    server.register_resolvers(server.STATES)
    available = {
        name for name, state in server.STATES.items() if state.instance is not None
    }
    assert set(citations.RESOLVERS) == available
    assert {"fundamentals", "reports", "analysis", "thesis"} <= available


def test_unregistered_module_citation_is_unresolvable():
    server.register_resolvers(server.STATES)
    citation = {
        "key": "demo",
        "label": "demo",
        "source": "local",
        "artifact": {"module": "calendar", "kind": "demo"},
    }
    with pytest.raises(CitationUnresolvable) as excinfo:
        citations.resolve_citation(citation)
    assert excinfo.value.code == "citation_unresolvable"


def test_citation_resolve_wraps_resolver_output_and_never_raises():
    class _DemoResolver:
        def resolve(self, artifact, *, offset=0, limit=8000):
            return {
                "kind": "demo",
                "format": "md",
                "chunk": "abc",
                "next_offset": 3,
                "total_chars": 6,
            }

    citations.register_resolver("demo", _DemoResolver())
    try:
        citation = {
            "key": "demo",
            "label": "demo",
            "source": "local",
            "artifact": {"module": "demo", "kind": "demo"},
        }
        payload = server.citation_resolve(citation, offset=0, limit_chars=100)
        assert payload["ok"] is True
        assert payload["module"] == "core"
        assert payload["tool"] == "citation_resolve"
        # Opening evidence must not mint a new citation: echoing it would give
        # the model a fresh citation_id/url on every call, i.e. a loop.
        assert payload["citations"] == []
        assert payload["references"] == []
        assert payload["paging"] == {
            "offset": 0,
            "next_offset": 3,
            "truncated": True,
        }

        missing = {"key": "x", "label": "x", "source": "local"}
        failed = server.citation_resolve(missing)
        assert failed["ok"] is False
        assert failed["error"]["code"] == "citation_unresolvable"
    finally:
        server.register_resolvers(server.STATES)
