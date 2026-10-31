"""Facts mirror against the local AAPL companyfacts fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from modules.fundamentals.store import facts_store  # noqa: E402

FIXTURE_DB = Path(
    __import__("os").environ.get("VW_FIXTURE_DB", "/Users/rkarumugam/LocalFiles/Projects/db")
)
COMPANY_FACTS = FIXTURE_DB / "debug" / "jsonData" / "aapl" / "companyFacts_0000320193.json"

pytestmark = pytest.mark.skipif(
    not COMPANY_FACTS.exists(), reason="local AAPL companyfacts fixture is unavailable"
)


@pytest.fixture(scope="module")
def facts():
    edgar_parser = pytest.importorskip("edgar.entity.parser")
    payload = json.loads(COMPANY_FACTS.read_text(encoding="utf-8"))
    return edgar_parser.EntityFactsParser.parse_company_facts(payload)


@pytest.fixture()
def conn(tmp_path, facts):
    connection = facts_store.connect(tmp_path / "fundamentals.sqlite")
    profile = SimpleNamespace(
        cik=320193, symbol="AAPL", name="Apple Inc.", exchange="Nasdaq",
        sic="3571", industry="Electronic Computers", fiscal_year_end="0926",
        filer_category="Large accelerated filer", is_foreign=False,
    )
    count = facts_store.sync_company(
        connection, profile, iter(facts), fetched_at=1_700_000_000.0
    )
    assert count > 20_000
    yield connection
    connection.close()


def test_facts_query_and_timeseries(conn):
    rows, total = facts_store.query(
        conn, 320193, concepts_in=["NetIncomeLoss"], unit="USD", limit=5
    )
    assert total >= 5
    assert rows[0].numeric_value is not None
    assert rows[0].period_end

    series = facts_store.annual_series(conn, 320193, "NetIncomeLoss", unit="USD", limit=6)
    assert len(series) == 6
    assert series[0].duration_days and 350 <= series[0].duration_days <= 380
    values = [row.period_end for row in series]
    assert values == sorted(values, reverse=True)


def test_line_items_are_cited_and_aligned(conn):
    series = facts_store.line_items(
        conn, 320193, "AAPL", "USD",
        ["revenue", "net_income", "total_assets", "equity", "shares_diluted"],
        periods=4, balance_basis="ending",
    )
    assert len(series.periods) == 4
    revenue = series.period_values("revenue")
    assert revenue
    first = next(iter(revenue.values()))
    assert first.citation and first.citation["accession"]
    assets = series.period_values("total_assets")
    assert assets


def test_instant_line_items_use_fiscal_year_ends(conn):
    series = facts_store.line_items(
        conn, 320193, "AAPL", "USD", ["equity", "total_assets", "cash"],
        periods=4, balance_basis="ending",
    )
    assert len(series.periods) == 4
    periods = set(series.periods)
    for item in ("equity", "total_assets", "cash"):
        values = series.period_values(item)
        assert len(values) == 4, f"{item} returned {len(values)} periods"
        assert set(values) == periods, f"{item} periods diverge from canonical periods"


def test_provenance_resolves_accession(conn):
    series = facts_store.annual_series(conn, 320193, "NetIncomeLoss", unit="USD", limit=1)
    row = series[0]
    provenance = facts_store.provenance_for(
        conn, 320193, "NetIncomeLoss", row.period_end, row.numeric_value
    )
    assert provenance["accession"]
    assert provenance["artifact"]["kind"] == "facts-json"
    assert provenance["artifact"]["concept"] == "NetIncomeLoss"
    assert provenance["artifact"]["period_end"] == row.period_end
    # Cached facts are served by citation_resolve; there is no outbound link.
    assert "url" in provenance
    assert provenance["url"] is None
    assert "sec.gov" not in str(provenance.get("url") or "")
    assert provenance["key"]
