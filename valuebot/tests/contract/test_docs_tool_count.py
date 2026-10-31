"""Documentation contract for the MCP tool count."""

from __future__ import annotations

import sys
from pathlib import Path

VALUEBOT = Path(__file__).resolve().parents[2]
MCP_DIR = VALUEBOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from server import CORE_TOOLS, MODULE_TOOLS, TOOL_MODULES  # noqa: E402


def test_server_registry_has_nineteen_tools() -> None:
    assert len(TOOL_MODULES) + len(CORE_TOOLS) == 19
    assert sum(len(tools) for tools in MODULE_TOOLS.values()) == 16


def test_docs_contain_no_stale_tool_counts() -> None:
    roots = [VALUEBOT / "README.md", VALUEBOT / "docs", VALUEBOT / "harnesses"]
    patterns = ("16 tools", "all 16", "15 domain")
    stale: list[str] = []
    for root in roots:
        paths = [root] if root.is_file() else root.rglob("*.md")
        for path in paths:
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                for pattern in patterns:
                    if pattern in line.lower():
                        stale.append(f"{path.relative_to(VALUEBOT)}:{line_number}: {line}")
    assert not stale, "stale tool counts:\n" + "\n".join(stale)
