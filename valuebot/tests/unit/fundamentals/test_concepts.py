"""Line-item vocabulary invariants."""

from __future__ import annotations

import sys
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from modules.fundamentals.domain import concepts  # noqa: E402


def test_vocabulary_is_complete_and_versioned():
    assert concepts.VOCABULARY_VERSION >= 1
    assert len(concepts.LINE_ITEMS) == 36
    for name, definition in concepts.LINE_ITEMS.items():
        assert definition.name == name
        assert definition.concepts, name
        assert definition.unit in {"USD", "shares", "USD/shares"}
        assert definition.period_type in {"instant", "duration"}


def test_revenue_fallback_order():
    revenue = concepts.get("revenue")
    assert revenue.concepts[0] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert "Revenues" in revenue.concepts


def test_total_debt_can_be_derived():
    total = concepts.get("total_debt")
    assert total.derived_from == ("short_term_debt", "long_term_debt")


def test_unknown_item_raises():
    try:
        concepts.get("not_a_line_item")
    except KeyError as exc:
        assert "unknown line item" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected KeyError")
