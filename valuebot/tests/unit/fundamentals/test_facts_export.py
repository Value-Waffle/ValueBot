"""Raw concept exports: JSON shape, TSV/XLSX headers, caps and empty filings."""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import config
from core.contracts import CitationResolver
from core.errors import ArtifactNotCached, CitationUnresolvable
from core.models import NormalizedStatement, StatementRow
from modules.fundamentals import service as service_module
from modules.fundamentals.domain import statements
from modules.fundamentals.service import FundamentalsService
from modules.fundamentals.store import facts_store
from modules.fundamentals.tools import register

CIK = 1234567
ACCESSION = "0001234567-25-000001"
OLD_ACCESSION = "0001234567-24-000001"
CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"


class FakeSource:
    """Profile-only source: the facts mirror is pre-populated by the fixture."""

    def profile(self, symbol):
        return SimpleNamespace(
            cik=CIK,
            symbol=symbol.upper(),
            name="Fixture Corp",
            exchange="Nasdaq",
            sic="3571",
            industry="Electronic Computers",
            fiscal_year_end="1231",
            filer_category="Large accelerated filer",
            is_foreign=False,
        )

    def facts(self, symbol):  # pragma: no cover - must never be called
        raise AssertionError("facts should already be cached")


class FakeMcp:
    def __init__(self):
        self.tools: dict = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def _insert_fact(
    conn,
    key: str,
    concept: str,
    value: float,
    accession: str,
    period_end: str,
    *,
    filing_date: str,
    label: str | None = None,
    unit: str = "USD",
) -> None:
    conn.execute(
        """
        INSERT INTO facts (fact_key, cik, concept, taxonomy, label, unit, value,
                           numeric_value, period_type, period_start, period_end,
                           duration_days, fiscal_year, fiscal_period, form_type,
                           accession, filing_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            key, CIK, concept, "us-gaap", label or concept, unit, str(value),
            float(value), "duration", None, period_end, 365,
            int(period_end[:4]), "FY", "10-K", accession, filing_date,
        ),
    )


@pytest.fixture()
def exported(tmp_path, monkeypatch):
    db_path = tmp_path / "fundamentals.sqlite"
    conn = facts_store.connect(db_path)
    now = time.time()
    conn.execute(
        """
        INSERT INTO companies (cik, ticker, name, updated_at, facts_synced_at,
                               fact_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (CIK, "FIX", "Fixture Corp", now, now, 3),
    )
    _insert_fact(
        conn, "k1", CONCEPT, 1000.0, ACCESSION, "2024-12-31",
        filing_date="2025-02-01",
    )
    _insert_fact(
        conn, "k2", "NetIncomeLoss", 200.0, ACCESSION, "2024-12-31",
        filing_date="2025-02-01",
    )
    _insert_fact(
        conn, "k3", CONCEPT, 900.0, OLD_ACCESSION, "2023-12-31",
        filing_date="2024-02-01",
    )
    conn.commit()
    conn.close()

    exports_root = tmp_path / "exports"
    monkeypatch.setattr(config, "FUNDAMENTALS_EXPORTS", exports_root)
    monkeypatch.setattr(config, "MAX_EXPORTS_MB", 64)

    service = FundamentalsService(source=FakeSource(), db_path=db_path)
    mcp = FakeMcp()
    register(mcp, service)
    try:
        yield SimpleNamespace(
            service=service, mcp=mcp, root=exports_root, tmp_path=tmp_path
        )
    finally:
        service.close()


def _export(exported, **kwargs) -> dict:
    return exported.mcp.tools["facts_export"]("FIX", **kwargs)


def test_export_citation_is_identifier_only_whatever_the_viewer_state(exported):
    from core import artifact_viewer

    payload = _export(exported, format="json")
    citation = payload["citations"][0]
    assert citation["artifact"]["kind"] == "facts-json"
    assert "url" not in citation
    assert citation["citation_id"]

    assert artifact_viewer.start(0) is not None
    try:
        enabled = _export(exported, format="json")["citations"][0]
        assert "url" not in enabled
        assert enabled["citation_id"] == citation["citation_id"]
    finally:
        artifact_viewer.stop()


def test_json_export_round_trips_companyfacts_shape(exported):
    payload = _export(exported, format="json")
    assert payload["ok"], payload

    data = payload["data"]
    assert data["accession"] == ACCESSION
    assert data["fact_count"] == 2
    assert data["concept_count"] == 2

    document = json.loads(Path(data["path"]).read_text(encoding="utf-8"))
    assert document["cik"] == CIK
    assert document["entityName"] == "Fixture Corp"
    rows = document["facts"]["us-gaap"][CONCEPT]["units"]["USD"]
    assert rows == [
        {
            "end": "2024-12-31",
            "val": 1000,
            "accn": ACCESSION,
            "fy": 2024,
            "fp": "FY",
            "form": "10-K",
            "filed": "2025-02-01",
        }
    ]
    assert payload["citations"][0]["artifact"]["kind"] == "facts-json"


def test_txt_export_has_eleven_column_header(exported):
    payload = _export(exported, format="txt")
    assert payload["ok"], payload

    data = payload["data"]
    lines = Path(data["path"]).read_text(encoding="utf-8").splitlines()
    assert lines[0].split("\t") == list(service_module.EXPORT_COLUMNS)
    assert len(service_module.EXPORT_COLUMNS) == 11
    assert len(lines) == 3
    assert data["preview"].startswith("concept\ttaxonomy")


def test_xlsx_export_reopens_with_same_header(exported):
    openpyxl = pytest.importorskip("openpyxl")
    assert openpyxl.__version__

    payload = _export(exported, format="xlsx")
    assert payload["ok"], payload

    data = payload["data"]
    from openpyxl import load_workbook

    workbook = load_workbook(data["path"])
    try:
        sheet = workbook["facts"]
        header = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
    finally:
        workbook.close()
    assert header == list(service_module.EXPORT_COLUMNS)
    assert payload["citations"][0]["artifact"]["kind"] == "facts-xlsx"


def test_xlsx_rejects_more_rows_than_the_cap(exported, monkeypatch):
    monkeypatch.setattr(service_module, "MAX_EXPORT_ROWS", 1)

    payload = _export(exported, format="xlsx")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "artifact_too_large"
    assert not list(exported.root.rglob("*.xlsx"))


def test_size_cap_rejects_oversized_export(exported, monkeypatch):
    monkeypatch.setattr(service_module, "MAX_EXPORT_BYTES", 16)

    payload = _export(exported, format="json")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "artifact_too_large"
    assert not list(exported.root.rglob("*.json"))


def test_empty_accession_still_returns_ok(exported):
    payload = _export(exported, accession="0000000000-99-000001", format="txt")
    assert payload["ok"], payload

    data = payload["data"]
    assert data["fact_count"] == 0
    assert data["concept_count"] == 0
    assert data["truncated"] is False
    lines = Path(data["path"]).read_text(encoding="utf-8").splitlines()
    assert lines == ["\t".join(service_module.EXPORT_COLUMNS)]


def test_config_exposes_exports_root_and_cap(monkeypatch, tmp_path):
    monkeypatch.setenv("VW_FUNDAMENTALS_EXPORTS", str(tmp_path / "exports"))
    monkeypatch.setenv("VW_MAX_EXPORTS_MB", "12")
    try:
        described = config.refresh()
        assert config.FUNDAMENTALS_EXPORTS == tmp_path / "exports"
        assert config.MAX_EXPORTS_MB == 12
        assert described["FUNDAMENTALS_EXPORTS"]["source"] == "env"
        assert described["FUNDAMENTALS_EXPORTS"]["value"] == str(tmp_path / "exports")
        assert described["MAX_EXPORTS_MB"] == 12
    finally:
        monkeypatch.undo()
        config.refresh()


def _artifact(kind: str) -> dict:
    return {"kind": kind, "cik": CIK, "accession": ACCESSION}


def test_json_resolver_returns_paged_companyfacts(exported):
    result = exported.service.resolve_artifact(_artifact("facts-json"), limit=40)
    assert result["kind"] == "facts-json"
    assert result["format"] == "json"
    assert result["next_offset"] is not None
    remainder = exported.service.resolve_artifact(
        _artifact("facts-json"), offset=result["next_offset"], limit=8000
    )
    document = result["chunk"] + remainder["chunk"]
    assert '"RevenueFromContractWithCustomerExcludingAssessedTax"' in document
    assert '"NetIncomeLoss"' in document
    assert remainder["total_chars"] == result["total_chars"]


def test_txt_resolver_returns_tsv_rows(exported):
    result = exported.service.resolve_artifact(_artifact("facts-txt"))
    assert result["format"] == "txt"
    assert result["chunk"].startswith("\t".join(service_module.EXPORT_COLUMNS))
    assert CONCEPT in result["chunk"]


def test_xlsx_resolver_returns_path_and_preview(exported):
    payload = _export(exported, format="xlsx")
    result = exported.service.resolve_artifact(_artifact("facts-xlsx"))
    assert result["path"] == payload["data"]["path"]
    assert result["chunk"] == ""
    assert result["preview"].startswith("concept\ttaxonomy")


def test_xlsx_resolver_requires_cached_export(exported):
    with pytest.raises(ArtifactNotCached, match="not cached") as exc_info:
        exported.service.resolve_artifact(_artifact("facts-xlsx"))
    assert exc_info.value.hint == "run facts_export with format=xlsx first"


def test_resolver_rejects_unknown_kind_and_adapter_matches_protocol(exported):
    with pytest.raises(CitationUnresolvable):
        exported.service.resolve_artifact(_artifact("facts-pdf"))
    assert isinstance(exported.service.resolver, CitationResolver)


def _assert_dataset_citation(citation: dict, *, concept: str | None) -> None:
    """Every fact citation points at a cached facts-json artifact, not a filing."""
    artifact = citation["artifact"]
    assert artifact["module"] == "fundamentals"
    assert artifact["kind"] == "facts-json"
    assert artifact["cik"] == CIK
    assert artifact["accession"] in {ACCESSION, OLD_ACCESSION}
    if concept is not None:
        assert artifact["concept"] == concept
    assert artifact["period_end"]
    # No outbound fallback and no viewer link: the citation is an identifier.
    assert "url" not in citation
    assert citation.get("url") is None
    assert citation["citation_id"]
    assert "sec.gov" not in str(citation.get("url") or "")


def test_facts_query_citation_cites_the_dataset(exported):
    payload = exported.mcp.tools["facts_query"]("FIX", concepts=[CONCEPT])
    assert payload["ok"], payload

    citations = payload["citations"]
    assert citations
    for citation in citations:
        _assert_dataset_citation(citation, concept=CONCEPT)
        assert "url" not in citation
        assert citation["citation_id"]


def test_facts_timeseries_citation_cites_the_dataset(exported):
    payload = exported.mcp.tools["facts_timeseries"]("FIX", CONCEPT)
    assert payload["ok"], payload

    citations = payload["citations"]
    assert citations
    for citation in citations:
        _assert_dataset_citation(citation, concept=CONCEPT)


def test_line_item_citation_cites_the_dataset(exported):
    series = exported.service.line_items("FIX", ["revenue"], periods=2)
    values = series.period_values("revenue")
    assert values

    for value in values.values():
        citation = value.citation
        assert citation is not None
        _assert_dataset_citation(citation, concept=CONCEPT)


def test_statement_period_citation_cites_the_dataset(exported):
    normalized = NormalizedStatement(
        symbol="FIX",
        cik=CIK,
        statement="income",
        label="Income Statement",
        basis="company",
        unit="USD",
        periods=("FY 2024",),
        period_ends={},
        rows=(
            StatementRow(
                concept=CONCEPT,
                label="Revenue",
                depth=0,
                parent=None,
                is_total=True,
                unit="USD",
                values={"FY 2024": 1000.0},
            ),
        ),
    )

    resolved = statements.resolve_period_ends(
        exported.service.conn, "income", CIK, normalized
    )
    citation = resolved.citations["FY 2024"]
    assert citation["source"] == "sec-statement"
    artifact = citation["artifact"]
    assert artifact["kind"] == "facts-json"
    assert artifact["concept"] == CONCEPT
    assert artifact["period_end"] == "2024-12-31"
    assert "url" not in citation
    assert citation["citation_id"]
    assert "sec.gov" not in str(citation.get("url") or "")
