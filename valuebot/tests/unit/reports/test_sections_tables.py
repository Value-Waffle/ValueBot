"""Semantic sections and notes on a real AAPL 10-K and 10-Q."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from modules.reports.domain import profiles, sections, tables  # noqa: E402
from modules.reports.sources import secparser_source  # noqa: E402

FIXTURE_DB = Path(os.environ.get("VW_FIXTURE_DB", "/Users/rkarumugam/LocalFiles/Projects/db"))
TEN_K = FIXTURE_DB / "filing" / "us" / "AAPL" / "10-K" / "2025-09-27_0000320193-25-000079_aapl-20250927.htm"
TEN_Q_DIR = FIXTURE_DB / "filing" / "us" / "AAPL" / "10-Q"

pytestmark = pytest.mark.skipif(not TEN_K.exists(), reason="local AAPL filings are unavailable")


@pytest.fixture(scope="module")
def ten_k():
    elements, warnings = secparser_source.parse_html(TEN_K.read_text(encoding="utf-8", errors="replace"))
    return elements, warnings


def test_element_stream(ten_k):
    elements, warnings = ten_k
    assert len(elements) >= 300
    top = [item for item in elements if item["type"] == "TopSectionTitle"]
    assert 6 <= len(top) <= 10
    assert any(item["section_type"] == "part1" for item in top)


def test_10k_item_and_note_coverage(ten_k):
    elements, _ = ten_k
    section_list, coverage = sections.build_sections(elements, "10-K")
    ids = {item.id for item in section_list}
    assert {"part1-item1", "part1-item1a", "part2-item7", "part2-item7a", "part2-item8"} <= ids
    assert coverage["notes_found"] >= 10
    assert coverage["expected_items"] == 23
    assert coverage["degraded"] is False
    note = next(item for item in section_list if item.kind == "note")
    assert note.id.startswith("note-")
    text = sections.section_text(elements, note)
    assert len(text) > 100


def test_10k_tables_render_with_delimiter(ten_k):
    elements, _ = ten_k
    records = []
    for element in elements:
        if element["type"] != "TableElement" or not element.get("table_html"):
            continue
        grid, header_rows = tables.extract_grid(element["table_html"])
        if grid:
            records.append((grid, header_rows))
    assert len(records) >= 40
    grid, header_rows = max(records, key=lambda item: len(item[0]))
    markdown = tables.render_markdown(grid, header_rows, max_rows=10)
    assert "| --- |" in markdown
    assert markdown.count("|") > 10


def test_10q_top_sections_are_parser_classified():
    files = sorted(TEN_Q_DIR.glob("*.htm")) if TEN_Q_DIR.exists() else []
    if not files:
        pytest.skip("no local 10-Q")
    elements, _ = secparser_source.parse_html(files[-1].read_text(encoding="utf-8", errors="replace"))
    section_list, coverage = sections.build_sections(elements, "10-Q")
    ids = {item.id for item in section_list}
    assert "part1-item1" in ids
    assert "part2-item1a" in ids
    assert coverage["notes_found"] >= 5


def test_profile_mapping():
    assert profiles.profile_for("10-K") == "10-K"
    assert profiles.profile_for("10-Q/A") == "10-Q"
    assert profiles.profile_for("20-F") == "generic"
    assert profiles.profile_for("DEF 14A") == "proxy"
