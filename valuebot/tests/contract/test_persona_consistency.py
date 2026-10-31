"""Persona consistency: exports and harness frontmatter must match the server.

The authoritative tool set is the server registry itself (``server.TOOL_NAMES``
plus ``server.CORE_TOOLS``), never a second hard-coded copy, so a tool added to
or removed from the server immediately invalidates every stale persona.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

VALUEBOT = Path(__file__).resolve().parents[2]
MCP_DIR = VALUEBOT / "mcp"

if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402

#: One authoritative source: the registry the server itself registers.
AUTHORITATIVE_TOOLS = frozenset(server.TOOL_NAMES) | frozenset(server.CORE_TOOLS)

EXPORTS = sorted((VALUEBOT / "agent-builder-exports").glob("vw-*.json"))
HARNESS_PERSONAS = sorted((VALUEBOT / "harnesses").glob("*/personas/*.md"))
SKILLS_DIR = VALUEBOT / "skills"

GROUNDED_CITATION = "grounded-citation"
CITATION_TOOLS = ("citation_resolve", "citation_view")

#: ``mcp__vw-mcp__citation_view`` and ``vw-mcp_citation_view`` both mean
#: ``citation_view``; a bare name is already normalised.
_SERVER_PREFIX = re.compile(r"^(?:mcp__)?vw-mcp_{1,2}")


def normalise_tool_name(name: str) -> str:
    """Strip any harness-specific server prefix from one tool name."""
    return _SERVER_PREFIX.sub("", name.strip())


def tool_names(value: object) -> list[str]:
    """Accept a YAML list, a comma-separated scalar, or nothing at all."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    else:
        parts = [str(item) for item in value]  # type: ignore[union-attr]
    return [normalise_tool_name(part) for part in parts if part.strip()]


def skill_names(value: object) -> list[str]:
    """Accept ``grounded-citation`` or the export form ``skills/grounded-citation``."""
    if value is None:
        return []
    entries = value.split(",") if isinstance(value, str) else list(value)  # type: ignore[arg-type]
    return [Path(str(entry).strip()).name for entry in entries if str(entry).strip()]


def frontmatter(path: Path) -> dict:
    """Parse one markdown file's YAML frontmatter into a mapping."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        pytest.fail(f"{path}: no YAML frontmatter")
    _, block, _ = text.split("---", 2)
    data = yaml.safe_load(block)
    if not isinstance(data, dict):
        pytest.fail(f"{path}: frontmatter is {type(data).__name__}, not a mapping")
    return data


def _export_payloads() -> list[tuple[Path, dict]]:
    assert EXPORTS, "no agent-builder exports found"
    return [
        (path, json.loads(path.read_text(encoding="utf-8"))) for path in EXPORTS
    ]


def _persona_documents() -> list[tuple[Path, dict, list[str], list[str]]]:
    """(path, frontmatter or export payload, skills, normalised tools)."""
    documents = []
    for path, payload in _export_payloads():
        documents.append(
            (
                path,
                payload,
                skill_names(payload.get("skills")),
                tool_names(payload.get("tools")),
            )
        )
    for path in HARNESS_PERSONAS:
        data = frontmatter(path)
        documents.append(
            (path, data, skill_names(data.get("skills")), tool_names(data.get("tools")))
        )
    return documents


def test_exports_reference_registered_tools_and_existing_skills():
    for path, payload in _export_payloads():
        tools = set(tool_names(payload.get("tools")))
        unknown = tools - AUTHORITATIVE_TOOLS
        assert not unknown, f"{path.name}: unregistered tools {sorted(unknown)}"

        skills = skill_names(payload.get("skills"))
        assert skills, f"{path.name}: no skills declared"
        for skill in skills:
            assert (SKILLS_DIR / skill).is_dir(), f"{path.name}: missing skill {skill}"


def test_every_persona_declares_name_and_description():
    documents = _persona_documents()
    assert documents, "no personas found"
    for path, data, _skills, _tools in documents:
        assert isinstance(data.get("name"), str), f"{path}: name"
        assert data["name"].strip(), f"{path}: empty name"
        assert isinstance(data.get("description"), str), f"{path}: description"
        assert data["description"].strip(), f"{path}: empty description"


def test_grounded_citation_personas_declare_the_citation_tools():
    offenders = []
    for path, _data, skills, tools in _persona_documents():
        if GROUNDED_CITATION not in skills:
            continue
        missing = [tool for tool in CITATION_TOOLS if tool not in tools]
        if missing:
            offenders.append(f"{path.relative_to(VALUEBOT)}: {missing}")
    assert not offenders, (
        "personas declare the grounded-citation skill but cannot open a "
        "citation:\n" + "\n".join(offenders)
    )


def test_harness_persona_tools_normalise_to_the_registry():
    for path in HARNESS_PERSONAS:
        tools = tool_names(frontmatter(path).get("tools"))
        unknown = set(tools) - AUTHORITATIVE_TOOLS
        assert not unknown, f"{path.relative_to(VALUEBOT)}: {sorted(unknown)}"


@pytest.mark.parametrize(
    "raw",
    [
        "mcp__vw-mcp__citation_view",
        "vw-mcp_citation_view",
        "citation_view",
        "  mcp__vw-mcp__report_section  ",
    ],
)
def test_tool_name_normalisation(raw: str):
    assert normalise_tool_name(raw) in AUTHORITATIVE_TOOLS
