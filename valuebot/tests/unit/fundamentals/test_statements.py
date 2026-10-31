"""Statement normalization and period provenance from local facts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from modules.fundamentals.domain import statements  # noqa: E402
from modules.fundamentals.store import facts_store  # noqa: E402

FIXTURE_DB = Path(os.environ.get("VW_FIXTURE_DB", "/Users/rkarumugam/LocalFiles/Projects/db"))
COMPANY_FACTS = FIXTURE_DB / "debug" / "jsonData" / "aapl" / "companyFacts_0000320193.json"

pytestmark = pytest.mark.skipif(
    not COMPANY_FACTS.exists(), reason="local AAPL companyfacts fixture is unavailable"
)


@pytest.fixture(scope="module")
def entity_facts():
    parser = pytest.importorskip("edgar.entity.parser")
    payload = json.loads(COMPANY_FACTS.read_text(encoding="utf-8"))
    return parser.EntityFactsParser.parse_company_facts(payload)


@pytest.fixture()
def conn(tmp_path, entity_facts):
    connection = facts_store.connect(tmp_path / "fundamentals.sqlite")
    profile = SimpleNamespace(
        cik=320193, symbol="AAPL", name="Apple Inc.", exchange="Nasdaq",
        sic="3571", industry="Electronic Computers", fiscal_year_end="0926",
        filer_category="Large accelerated filer", is_foreign=False,
    )
    facts_store.sync_company(connection, profile, iter(entity_facts), fetched_at=1.0)
    yield connection
    connection.close()


def test_income_statement_matches_known_values(conn, entity_facts):
    raw = entity_facts.income_statement(periods=4, period="annual")
    normalized = statements.normalize_company(
        raw, symbol="AAPL", cik=320193, statement="income"
    )
    normalized = statements.resolve_period_ends(conn, "income", 320193, normalized)

    assert "FY 2025" in normalized.periods
    revenue = next(row for row in normalized.rows if row.concept.startswith("Revenue"))
    assert revenue.values["FY 2025"] == pytest.approx(416_161_000_000.0)
    net_income = next(row for row in normalized.rows if row.concept == "NetIncomeLoss")
    assert net_income.values["FY 2025"] == pytest.approx(112_010_000_000.0)
    assert normalized.period_ends["FY 2025"] == "2025-09-27"
    assert normalized.citations["FY 2025"]["accession"].startswith("0000320193-25-")


def test_depth_and_parent_are_preserved(conn, entity_facts):
    raw = entity_facts.balance_sheet(periods=4, period="annual")
    normalized = statements.normalize_company(
        raw, symbol="AAPL", cik=320193, statement="balance"
    )
    assert any(row.depth > 0 for row in normalized.rows)
    assert any(row.parent for row in normalized.rows)
