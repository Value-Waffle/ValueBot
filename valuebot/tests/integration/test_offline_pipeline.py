"""Offline end-to-end: fundamentals → analysis and reports from local HTML."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

MCP_DIR = Path(__file__).resolve().parents[2] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core import citations, config  # noqa: E402
from core.errors import ArtifactNotCached  # noqa: E402
from core.models import (  # noqa: E402
    CompanyProfile,
    FilingRef,
    LineItemSeries,
    LineItemValue,
)
from modules.analysis.service import AnalysisService  # noqa: E402
from modules.analysis.tools import register as register_analysis_tools  # noqa: E402
from modules.fundamentals.service import FundamentalsService  # noqa: E402
from modules.fundamentals.store import facts_store  # noqa: E402
from modules.fundamentals.tools import register as register_fundamentals_tools  # noqa: E402
from modules.reports.service import ReportsService  # noqa: E402
from modules.reports.tools import register as register_reports_tools  # noqa: E402
from modules.thesis import service as thesis_service  # noqa: E402

FIXTURE_DB = Path(os.environ.get("VW_FIXTURE_DB", "/Users/rkarumugam/LocalFiles/Projects/db"))
TEN_K = FIXTURE_DB / "filing" / "us" / "AAPL" / "10-K" / "2025-09-27_0000320193-25-000079_aapl-20250927.htm"

PERIODS = ("2025-09-30", "2024-09-30", "2023-09-30", "2022-09-30")

CONCEPTS = {
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": ("revenue", [100, 95, 90, 85], "duration", "USD"),
    "us-gaap:OperatingIncomeLoss": ("operating_income", [20, 19, 18, 17], "duration", "USD"),
    "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": ("pretax_income", [18, 17, 16, 15], "duration", "USD"),
    "us-gaap:IncomeTaxExpenseBenefit": ("income_tax", [4, 4, 3, 3], "duration", "USD"),
    "us-gaap:NetIncomeLoss": ("net_income", [14, 13, 12, 11], "duration", "USD"),
    "us-gaap:GrossProfit": ("gross_profit", [60, 55, 50, 45], "duration", "USD"),
    "us-gaap:CostOfRevenue": ("cost_of_revenue", [40, 40, 40, 40], "duration", "USD"),
    "us-gaap:DepreciationDepletionAndAmortization": ("da", [5, 5, 5, 4], "duration", "USD"),
    "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment": ("capex", [6, 6, 5, 5], "duration", "USD"),
    "us-gaap:NetCashProvidedByUsedInOperatingActivities": ("cfo", [22, 21, 20, 19], "duration", "USD"),
    "us-gaap:InterestExpenseNonoperating": ("interest_expense", [1, 1, 1, 1], "duration", "USD"),
    "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding": ("shares_diluted", [10, 10, 10, 10], "duration", "shares"),
    "us-gaap:CashAndCashEquivalentsAtCarryingValue": ("cash", [10, 9, 8, 7], "instant", "USD"),
    "us-gaap:AssetsCurrent": ("current_assets", [40, 38, 36, 34], "instant", "USD"),
    "us-gaap:LiabilitiesCurrent": ("current_liabilities", [25, 24, 23, 22], "instant", "USD"),
    "us-gaap:Assets": ("total_assets", [200, 190, 180, 170], "instant", "USD"),
    "us-gaap:LongTermDebt": ("total_debt", [30, 29, 28, 27], "instant", "USD"),
    "us-gaap:StockholdersEquity": ("equity", [120, 115, 110, 105], "instant", "USD"),
    "us-gaap:InventoryNet": ("inventory", [5, 5, 4, 4], "instant", "USD"),
    "us-gaap:AccountsReceivableNetCurrent": ("accounts_receivable", [12, 11, 10, 9], "instant", "USD"),
    "us-gaap:AccountsPayableCurrent": ("accounts_payable", [8, 8, 7, 7], "instant", "USD"),
    "us-gaap:ShortTermInvestments": ("short_term_investments", [2, 2, 2, 2], "instant", "USD"),
}


def make_facts():
    facts = []
    for concept, (name, values, period_type, unit) in CONCEPTS.items():
        for index, (period, value) in enumerate(zip(PERIODS, values)):
            year = int(period[:4])
            start = (date(year, 9, 30) - timedelta(days=365)).isoformat() if period_type == "duration" else None
            facts.append(
                SimpleNamespace(
                    concept=concept, taxonomy="us-gaap", label=name, value=value,
                    numeric_value=float(value), unit=unit, period_start=start,
                    period_end=period, period_type=period_type, fiscal_year=year,
                    fiscal_period="FY", form_type="10-K",
                    accession=f"0000000000-{str(year)[2:]}-000001",
                    filing_date=f"{year + 1}-01-15", is_audited=True,
                    is_restated=False, data_quality="high", confidence_score=0.99,
                    dimensions=None,
                )
            )
    return facts


class FakeFundamentalsSource:
    def profile(self, symbol):
        return CompanyProfile(
            symbol="TEST", cik=1, name="Test Co", tickers=("TEST",),
            exchange="NYSE", sic="1234", industry="Testing",
            fiscal_year_end="0930", filer_category="Large accelerated filer",
        )

    def facts(self, symbol):
        return make_facts()

    def resolve(self, query, limit=10):
        return [{"symbol": "TEST", "name": "Test Co", "cik": 1}]


def test_fundamentals_to_analysis(tmp_path):
    fundamentals = FundamentalsService(
        source=FakeFundamentalsSource(), db_path=tmp_path / "fundamentals.sqlite"
    )
    analysis = AnalysisService(fundamentals, cache_path=tmp_path / "analysis.sqlite")

    page = fundamentals.facts("TEST", concepts_in=["NetIncomeLoss"], limit=5)
    assert page["rows"][0]["numeric_value"] == 14.0
    assert page["citations"]

    metrics = analysis.compute(
        "TEST", ["gross_margin", "current_ratio", "revenue_cagr"], periods=4,
        balance_basis="ending",
    )
    values = {(item["metric_id"], item["period_end"]): item for item in metrics["results"]}
    assert values[("gross_margin", PERIODS[0])]["value"] == pytest.approx(0.6)
    assert values[("current_ratio", PERIODS[0])]["value"] == pytest.approx(1.6)
    assert values[("revenue_cagr", PERIODS[0])]["value"] == pytest.approx(
        (100 / 85) ** (1 / 3) - 1, rel=1e-6
    )

    assumptions = analysis.dcf("TEST", assumptions_only=True)
    assert assumptions["valuation"] is None
    assert len(assumptions["assumptions"]) >= 10

    valuation = analysis.dcf("TEST")
    assert valuation["valuation"]["value_per_share"] > 0


class FakeReportsSource:
    def __init__(self, ref: FilingRef, html: str):
        self.ref = ref
        self.html = html

    def company(self, symbol):
        return SimpleNamespace(cik=self.ref.cik, name="Apple Inc.")

    def filings(self, symbol, **kwargs):
        return [self.ref]

    def get_filing(self, symbol, accession=None, form=None, **kwargs):
        return self.ref

    def filing_html(self, symbol, accession):
        return self.html, self.ref


@pytest.mark.skipif(not TEN_K.exists(), reason="local AAPL 10-K is unavailable")
def test_reports_offline_build(tmp_path):
    ref = FilingRef(
        symbol="AAPL", cik=320193, accession="0000320193-25-000079", form="10-K",
        filed="2025-10-31", period_of_report="2025-09-27",
        primary_document="aapl-20250927.htm",
        source_url="https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
    )
    source = FakeReportsSource(ref, TEN_K.read_text(encoding="utf-8", errors="replace"))
    reports = ReportsService(
        source=source, db_path=tmp_path / "manifest.sqlite",
        artifacts_root=tmp_path / "artifacts",
    )
    listing = reports.filings("AAPL")
    assert listing["total"] == 1

    result = reports.sections(symbol="AAPL", form="10-K")
    ids = {item["id"] for item in result["sections"]}
    assert "part1-item1a" in ids
    assert "part2-item7" in ids
    assert result["coverage"]["notes_found"] >= 10
    assert (tmp_path / "artifacts" / "320193" / "0000320193-25-000079.semantic.json.gz").exists()

    section = reports.section(symbol="AAPL", form="10-K", section_id="part2-item7")
    assert len(section["text"]) > 200

    tables = reports.search(symbol="AAPL", form="10-K", query="Revenue")
    assert tables["hits"]


# ---------------------------------------------------------------------------
# Offline tool -> citation -> resolve_citation round trips (one per module).
#
# Each test drives the path a client takes: a domain tool mints an
# artifact-bearing citation, the resolver is registered the way
# ``server.register_resolvers`` wires it, and ``core.citations.resolve_citation``
# serves the raw material. No network, no EDGAR identity, and resolvers never
# build artifacts.
# ---------------------------------------------------------------------------


class FakeMcp:
    """Capture tool functions the way the MCP runtime registers them."""

    def __init__(self):
        self.tools: dict = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


@pytest.fixture()
def resolver_registry():
    """Empty the process-global resolver registry around each test."""
    citations.clear_resolvers()
    yield citations
    citations.clear_resolvers()


def _reports_offline(tmp_path) -> tuple[ReportsService, FakeMcp]:
    """Reports service over the local AAPL 10-K with its tools registered."""
    ref = FilingRef(
        symbol="AAPL", cik=320193, accession="0000320193-25-000079", form="10-K",
        filed="2025-10-31", period_of_report="2025-09-27",
        primary_document="aapl-20250927.htm",
        source_url="https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
    )
    source = FakeReportsSource(ref, TEN_K.read_text(encoding="utf-8", errors="replace"))
    reports = ReportsService(
        source=source, db_path=tmp_path / "manifest.sqlite",
        artifacts_root=tmp_path / "artifacts",
    )
    mcp = FakeMcp()
    register_reports_tools(mcp, reports)
    return reports, mcp


@pytest.mark.skipif(not TEN_K.exists(), reason="local AAPL 10-K is unavailable")
def test_reports_tool_citation_resolves_semantic_section_offline(tmp_path, resolver_registry):
    reports, mcp = _reports_offline(tmp_path)

    payload = mcp.tools["report_section"](
        symbol="AAPL", form="10-K", section_id="part2-item7", limit_chars=1000
    )
    assert payload["ok"], payload
    citation = payload["citations"][0]
    assert citation["artifact"]["kind"] == "semantic-section"
    assert citation["artifact"]["section_id"] == "part2-item7"

    resolver_registry.register_resolver("reports", reports)

    pages = []
    offset = 0
    while True:
        window = citations.resolve_citation(citation, offset=offset, limit=200)
        assert window["kind"] == "semantic-section"
        assert window["format"] == "md"
        assert window["chunk"]
        pages.append(window["chunk"])
        if window["next_offset"] is None:
            break
        assert window["next_offset"] > offset
        offset = window["next_offset"]
    assert len(pages) > 1, "the section should have paged"

    whole = citations.resolve_citation(citation, offset=0, limit=10 ** 6)
    assert whole["next_offset"] is None
    assert whole["chunk"] == "".join(pages)
    assert whole["total_chars"] == len(whole["chunk"])


@pytest.mark.skipif(not TEN_K.exists(), reason="local AAPL 10-K is unavailable")
def test_reports_uncached_accession_resolves_to_artifact_not_cached(tmp_path, resolver_registry):
    reports, mcp = _reports_offline(tmp_path)

    payload = mcp.tools["filing_list"]("AAPL", forms=["10-K"])
    assert payload["ok"], payload
    citation = payload["citations"][0]
    assert citation["artifact"]["status"] == "not_cached"

    resolver_registry.register_resolver("reports", reports)

    with pytest.raises(ArtifactNotCached) as excinfo:
        citations.resolve_citation(citation)
    assert excinfo.value.code == "artifact_not_cached"
    assert excinfo.value.hint


EXPORT_CIK = 1234567
EXPORT_ACCESSION = "0001234567-25-000001"
EXPORT_CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"


class FakeExportSource:
    """Profile-only source: the facts mirror is pre-populated by the test."""

    def profile(self, symbol):
        return SimpleNamespace(
            cik=EXPORT_CIK, symbol=symbol.upper(), name="Fixture Corp",
            exchange="Nasdaq", sic="3571", industry="Electronic Computers",
            fiscal_year_end="1231", filer_category="Large accelerated filer",
            is_foreign=False,
        )

    def facts(self, symbol):  # pragma: no cover - must never be called
        raise AssertionError("facts should already be cached")


def _insert_export_fact(conn, key, concept, value, accession, period_end, filing_date):
    conn.execute(
        """
        INSERT INTO facts (fact_key, cik, concept, taxonomy, label, unit, value,
                           numeric_value, period_type, period_start, period_end,
                           duration_days, fiscal_year, fiscal_period, form_type,
                           accession, filing_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            key, EXPORT_CIK, concept, "us-gaap", concept, "USD", str(value),
            float(value), "duration", None, period_end, 365,
            int(period_end[:4]), "FY", "10-K", accession, filing_date,
        ),
    )


@pytest.fixture()
def facts_exported(tmp_path, monkeypatch):
    db_path = tmp_path / "fundamentals.sqlite"
    conn = facts_store.connect(db_path)
    now = time.time()
    conn.execute(
        """
        INSERT INTO companies (cik, ticker, name, updated_at, facts_synced_at,
                               fact_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (EXPORT_CIK, "FIX", "Fixture Corp", now, now, 2),
    )
    _insert_export_fact(
        conn, "k1", EXPORT_CONCEPT, 1000.0, EXPORT_ACCESSION, "2024-12-31", "2025-02-01"
    )
    _insert_export_fact(
        conn, "k2", "NetIncomeLoss", 200.0, EXPORT_ACCESSION, "2024-12-31", "2025-02-01"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "FUNDAMENTALS_EXPORTS", tmp_path / "exports")
    monkeypatch.setattr(config, "MAX_EXPORTS_MB", 64)

    service = FundamentalsService(source=FakeExportSource(), db_path=db_path)
    mcp = FakeMcp()
    register_fundamentals_tools(mcp, service)
    yield SimpleNamespace(service=service, mcp=mcp)
    service.close()


def test_fundamentals_tool_citation_resolves_facts_json_offline(facts_exported, resolver_registry):
    payload = facts_exported.mcp.tools["facts_export"]("FIX", format="json")
    assert payload["ok"], payload
    citation = payload["citations"][0]
    assert citation["artifact"]["kind"] == "facts-json"

    resolver_registry.register_resolver("fundamentals", facts_exported.service.resolver)

    window = citations.resolve_citation(citation, offset=0, limit=8000)
    assert window["kind"] == "facts-json"
    assert window["format"] == "json"
    assert window["next_offset"] is None

    document = json.loads(window["chunk"])
    assert document["cik"] == EXPORT_CIK
    rows = document["facts"]["us-gaap"][EXPORT_CONCEPT]["units"]["USD"]
    assert rows == [
        {
            "end": "2024-12-31",
            "val": 1000,
            "accn": EXPORT_ACCESSION,
            "fy": 2024,
            "fp": "FY",
            "form": "10-K",
            "filed": "2025-02-01",
        }
    ]
    assert document["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]


ANALYSIS_VALUES = {
    "gross_profit": (60, 55, 50, 45),
    "revenue": (100, 95, 90, 85),
    "current_assets": (40, 38, 36, 34),
    "current_liabilities": (25, 24, 23, 22),
    "operating_income": (20, 19, 18, 17),
    "pretax_income": (18, 17, 16, 15),
    "income_tax": (4, 4, 3, 3),
    "da": (5, 5, 5, 4),
    "capex": (6, 6, 5, 5),
    "total_debt": (30, 29, 28, 27),
    "cash": (10, 9, 8, 7),
    "shares_diluted": (10, 10, 10, 10),
}


class FakeFacts:
    """Minimal line-item provider; counts calls to prove resolve never computes."""

    def __init__(self):
        self.calls = 0

    def line_items(self, symbol, items, *, periods=5, balance_basis="average"):
        self.calls += 1
        selected = PERIODS[: max(1, int(periods))]
        payload = {}
        for item in items:
            if item not in ANALYSIS_VALUES:
                continue
            payload[item] = tuple(
                LineItemValue(
                    line_item=item,
                    label=item.replace("_", " ").title(),
                    unit="shares" if item == "shares_diluted" else "USD",
                    period_end=period,
                    value=ANALYSIS_VALUES[item][index],
                    concept=f"Concept{item.title().replace('_', '')}",
                    citation={
                        "key": f"{item}-{period}",
                        "label": f"{item} {period}",
                        "source": "sec-xbrl",
                        "accession": "0000000000-25-000001",
                        "period": period,
                    },
                )
                for index, period in enumerate(selected)
            )
        return LineItemSeries(
            symbol=symbol.upper(), cik=1, currency="USD", periods=selected,
            items=payload, facts_version="1:1",
        )


def test_analysis_tool_citation_resolves_derived_inputs_offline(tmp_path, resolver_registry):
    facts = FakeFacts()
    analysis = AnalysisService(facts, cache_path=tmp_path / "analysis.sqlite")
    mcp = FakeMcp()
    register_analysis_tools(mcp, analysis)

    payload = mcp.tools["ratio_compute"]("TEST", ["gross_margin"], periods=2)
    assert payload["ok"], payload
    result = payload["data"]["results"][0]
    citation = next(
        item for item in payload["citations"]
        if item.get("source") == "derived-analysis"
        and item["artifact"]["period_end"] == result["period_end"]
    )
    assert citation["artifact"]["kind"] == "derived-inputs"

    resolver_registry.register_resolver("analysis", analysis)

    calls_before = facts.calls
    pages = []
    offset = 0
    while True:
        window = citations.resolve_citation(citation, offset=offset, limit=60)
        assert window["kind"] == "derived-inputs"
        assert window["format"] == "json"
        pages.append(window["chunk"])
        if window["next_offset"] is None:
            break
        assert window["next_offset"] > offset
        offset = window["next_offset"]
    assert len(pages) > 1, "the bundle should have paged"
    assert facts.calls == calls_before, "resolve must serve the cached inputs"

    bundle = json.loads("".join(pages))
    assert bundle["metric_id"] == "gross_margin"
    assert bundle["value"] == pytest.approx(0.6)
    assert bundle["inputs"] == [
        {
            "line_item": item["line_item"],
            "label": item["label"],
            "value": item["value"],
            "unit": item["unit"],
            "concept": item["concept"],
            "period_end": item["period_end"],
            "citation": item["citation"],
        }
        for item in result["inputs"]
    ]


def test_thesis_tool_citation_resolves_vault_markdown_offline(tmp_path, monkeypatch, resolver_registry):
    root = tmp_path / "theses"
    (root / "AAPL" / ".thesis" / "annotations").mkdir(parents=True)
    (root / "AAPL" / "thesis.md").write_text(
        "---\ntitle: Apple thesis\nticker: AAPL\n---\n\n# Thesis\n\nServices growth.\n",
        encoding="utf-8",
    )
    (root / "AAPL" / ".thesis" / "annotations" / "thesis.json").write_text(
        json.dumps({"mtime": 1, "annotations": [{"text": "watch margins"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "THESIS_ROOT", root)

    payload = thesis_service.thesis_read("AAPL")
    assert payload["ok"] is True
    citation = payload["citations"][0]
    assert citation["artifact"]["kind"] == "vault-doc"

    resolver_registry.register_resolver("thesis", thesis_service)

    pages = []
    offset = 0
    while True:
        window = citations.resolve_citation(citation, offset=offset, limit=12)
        assert window["kind"] == "vault-doc"
        assert window["format"] == "md"
        assert window["file"] == "thesis.md"
        pages.append(window["chunk"])
        if window["next_offset"] is None:
            break
        assert window["next_offset"] > offset
        offset = window["next_offset"]
    assert len(pages) > 1, "the document should have paged"

    markdown = "".join(pages)
    assert markdown.startswith("---")
    assert "Services growth." in markdown
    assert markdown == citations.resolve_citation(citation)["chunk"]
