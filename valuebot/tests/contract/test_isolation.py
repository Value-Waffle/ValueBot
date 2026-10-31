"""Contract tests: module import and schema isolation."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[2] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

MODULES = MCP_DIR / "modules"
MODULE_NAMES = {
    "fundamentals", "analysis", "reports", "thesis", "calendar", "price_action"
}


def _module_files():
    return [path for path in MODULES.rglob("*.py") if "__pycache__" not in path.parts]


def _owner(path: Path) -> str | None:
    relative = path.relative_to(MODULES).parts
    return relative[0] if relative and relative[0] in MODULE_NAMES else None


def test_no_cross_module_imports():
    violations = []
    for path in _module_files():
        owner = _owner(path)
        if owner is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.startswith("modules."):
                    target = name.split(".")[1]
                    if target != owner:
                        violations.append(f"{path}: imports {name}")
    assert not violations, violations


def test_core_does_not_import_modules():
    violations = []
    for path in (MCP_DIR / "core").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.startswith("modules"):
                    violations.append(f"{path}: imports {name}")
    assert not violations, violations


def test_analysis_has_no_xbrl_concepts():
    for path in (MODULES / "analysis").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "us-gaap:" not in text, path
        assert "RevenueFromContract" not in text, path


def test_reserved_modules_are_not_imported():
    for path in _module_files():
        owner = _owner(path)
        if owner in {"calendar", "price_action"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "modules.calendar" not in text, path
        assert "modules.price_action" not in text, path


def test_module_schemas_do_not_overlap():
    fundamentals = (
        MODULES / "fundamentals" / "store" / "facts_store.py"
    ).read_text(encoding="utf-8")
    reports = (MODULES / "reports" / "store" / "db.py").read_text(encoding="utf-8")
    assert "filings_index" not in fundamentals
    assert "artifacts" not in fundamentals
    assert "companies" not in reports
    assert "fact_key" not in reports
    for path in MODULES.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "attach database" not in text, path
        assert 'execute("attach' not in text, path
