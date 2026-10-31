"""Artifact-bearing reports citations and the load-only citation resolver.

Everything here is offline: the semantic artifact is written straight to a
temporary manifest + gzip cache, and the EDGAR source is stubbed at the
submissions-JSON boundary.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core import artifact_viewer  # noqa: E402
from core.errors import (  # noqa: E402
    ArtifactNotCached,
    CitationUnresolvable,
    InvalidArgument,
    SectionNotFound,
    TableNotFound,
)
from modules.reports.service import ReportsService  # noqa: E402
from modules.reports.sources import edgar_source  # noqa: E402
from modules.reports.store import artifact_store  # noqa: E402
from modules.reports.tools import register as register_tools  # noqa: E402
from modules.reports.tools import _filing_citation  # noqa: E402

CIK = 320193
ACCESSION = "0000320193-25-000079"
HTML = "<html><body>Apple filing</body></html>"
SECTION_TEXT = " ".join(
    ["Apple designs and sells consumer devices worldwide."] * 6
)

FILING = {
    "symbol": "AAPL",
    "cik": CIK,
    "accession": ACCESSION,
    "form": "10-K",
    "filed": "2025-10-31",
    "period_of_report": "2025-09-27",
    "primary_document": "aapl-20250927.htm",
    "source_url": (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019325000079/aapl-20250927.htm"
    ),
}


def _artifact_dict() -> dict:
    return {
        "schema": 1,
        "accession": ACCESSION,
        "symbol": "AAPL",
        "cik": CIK,
        "form": "10-K",
        "filed": "2025-10-31",
        "period_of_report": "2025-09-27",
        "primary_document": "aapl-20250927.htm",
        "source_url": FILING["source_url"],
        "profile": "10-K",
        "parser_version": "0.58.1",
        "rules_version": "1",
        "warnings": [],
        "coverage": {"degraded": False},
        "sections": [
            {
                "id": "part1", "parent_id": None, "kind": "part",
                "title": "PART I", "start": 0, "end": 5, "char_count": 0,
                "section_type": "part1", "level": 0, "table_ids": [],
                "note_number": None,
            },
            {
                "id": "part1-item1", "parent_id": "part1", "kind": "item",
                "title": "Item 1. Business", "start": 1, "end": 3,
                "char_count": len(SECTION_TEXT), "section_type": None,
                "level": 0, "table_ids": ["t1"], "note_number": None,
            },
            {
                "id": "note-1", "parent_id": "part1-item1", "kind": "note",
                "title": "Note 1. Basis of Presentation", "start": 4, "end": 5,
                "char_count": 0, "section_type": None, "level": 0,
                "table_ids": [], "note_number": 1,
            },
        ],
        "elements": [
            {"type": "TopSectionTitle", "level": 0, "text": "PART I",
             "section_id": "part1", "table_id": None},
            {"type": "TitleElement", "level": 0, "text": "Item 1. Business",
             "section_id": "part1-item1", "table_id": None},
            {"type": "TextElement", "level": 0, "text": SECTION_TEXT,
             "section_id": "part1-item1", "table_id": None},
            {"type": "TableElement", "level": 0, "text": "",
             "section_id": "part1-item1", "table_id": "t1"},
            {"type": "TitleElement", "level": 0,
             "text": "Note 1. Basis of Presentation",
             "section_id": "note-1", "table_id": None},
        ],
        "tables": [
            {
                "id": "t1", "section_id": "part1-item1", "index": 3,
                "caption": "Revenue", "header_rows": 1,
                "grid": [["Item", "FY2025"], ["Revenue", "416,161"]],
            }
        ],
        "parse_ms": 1,
    }


def _persist(service: ReportsService) -> dict:
    """Write one semantic artifact straight into the reports cache."""
    artifact = _artifact_dict()
    ref = SimpleNamespace(
        accession=artifact["accession"],
        cik=artifact["cik"],
        form=artifact["form"],
        filed=artifact["filed"],
        period_of_report=artifact["period_of_report"],
        primary_document=artifact["primary_document"],
        source_url=artifact["source_url"],
    )
    _, digest, html_bytes = artifact_store.save_raw_html(
        service.artifacts_root, ref.cik, ref.accession, HTML
    )
    artifact_bytes = artifact_store.save_artifact(
        service.artifacts_root, ref.cik, ref.accession, artifact
    )
    artifact_store.record(
        service.conn, ref, profile=artifact["profile"],
        parser_version="0.58.1", artifact_bytes=artifact_bytes,
        html_bytes=html_bytes, html_sha256=digest,
        element_count=len(artifact["elements"]),
        section_count=len(artifact["sections"]), note_count=1,
        table_count=len(artifact["tables"]), coverage=artifact["coverage"],
        warnings=[],
    )
    return artifact


def _locator(kind: str, **extra) -> dict:
    locator = {
        "module": "reports",
        "kind": kind,
        "cik": CIK,
        "accession": ACCESSION,
        "format": "html" if kind == "raw-html" else "md",
        "status": "cached",
    }
    locator.update(extra)
    return locator


@pytest.fixture(autouse=True)
def _viewer_stopped():
    """Default citations stay link-free: no listener, so no url can go stale."""
    artifact_viewer.stop()
    yield
    artifact_viewer.stop()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def service(tmp_path):
    instance = ReportsService(
        source=SimpleNamespace(),
        db_path=tmp_path / "reports.sqlite",
        artifacts_root=tmp_path / "artifacts",
    )
    yield instance
    instance.close()


def _fail(*args, **kwargs):
    raise AssertionError("the build path must never be reached by a resolver")


def test_artifact_peek_reads_the_cache_then_the_lru(service, monkeypatch):
    _persist(service)
    monkeypatch.setattr(service, "artifact", _fail)

    assert service._cache.get(ACCESSION) is None
    first = service.artifact_peek(ACCESSION)
    assert first["accession"] == ACCESSION
    assert service._cache[ACCESSION] is first

    monkeypatch.setattr(artifact_store, "load", _fail)
    assert service.artifact_peek(ACCESSION) is first


def test_artifact_peek_misses_without_building(service, monkeypatch):
    monkeypatch.setattr(service, "artifact", _fail)
    with pytest.raises(ArtifactNotCached) as excinfo:
        service.artifact_peek("0000000000-00-000000")
    assert excinfo.value.hint == "run report_section or report_sections first"


def test_resolve_serves_semantic_section_in_pages(service):
    _persist(service)
    pages: list[str] = []
    offset = 0
    while True:
        payload = service.resolve(
            _locator("semantic-section", section_id="part1-item1"),
            offset=offset, limit=40,
        )
        assert payload["kind"] == "semantic-section"
        assert payload["format"] == "md"
        assert payload["total_chars"] == len(SECTION_TEXT)
        pages.append(payload["chunk"])
        if payload["next_offset"] is None:
            break
        assert payload["next_offset"] > offset
        offset = payload["next_offset"]
    assert len(pages) > 1
    assert "".join(pages) == SECTION_TEXT


def test_resolve_serves_semantic_table_markdown(service):
    _persist(service)
    payload = service.resolve(
        _locator("semantic-table", section_id="part1-item1", table_id="t1")
    )
    assert payload["kind"] == "semantic-table"
    assert payload["format"] == "md"
    assert payload["next_offset"] is None
    assert "| --- | --- |" in payload["chunk"]
    assert "Revenue" in payload["chunk"]
    assert "416,161" in payload["chunk"]


def test_resolve_serves_semantic_index_listing(service):
    _persist(service)
    payload = service.resolve(_locator("semantic-index"))
    assert payload["kind"] == "semantic-index"
    assert "| part1-item1 | item | Item 1. Business |" in payload["chunk"]
    assert "| note-1 | note | Note 1. Basis of Presentation |" in payload["chunk"]
    assert "| id | kind | title | chars | tables |" in payload["chunk"]


def test_resolve_serves_raw_html_window(service):
    _persist(service)
    payload = service.resolve(_locator("raw-html"), offset=0, limit=12)
    assert payload["kind"] == "raw-html"
    assert payload["format"] == "html"
    assert payload["chunk"].startswith("<html>")
    assert payload["total_chars"] == len(HTML.encode("utf-8"))
    assert payload["next_offset"] == 12


def test_resolve_rejects_bad_locators(service):
    _persist(service)
    with pytest.raises(InvalidArgument):
        service.resolve({})
    with pytest.raises(CitationUnresolvable):
        service.resolve(_locator("semantic-chunk"))
    with pytest.raises(SectionNotFound):
        service.resolve(_locator("semantic-section", section_id="part9-item99"))
    with pytest.raises(TableNotFound):
        service.resolve(
            _locator("semantic-table", section_id="part1-item1", table_id="t99")
        )


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):
        def decorator(function):
            self.tools[function.__name__] = function
            return function

        return decorator


class _FakeService:
    def filings(self, symbol, **kwargs):
        return {
            "symbol": "AAPL",
            "cik": CIK,
            "rows": [
                {**FILING, "report_available": True},
                {**FILING, "accession": "0000320193-25-000020",
                 "report_available": False},
            ],
            "total": 2,
            "paging": {"offset": 0, "limit": 50, "total": 2,
                       "next_offset": None, "truncated": False},
        }

    def sections(self, **kwargs):
        return {
            "filing": dict(FILING),
            "profile": "10-K",
            "coverage": {},
            "warnings": [],
            "sections": [
                {"id": "part1-item1", "kind": "item",
                 "title": "Item 1. Business"}
            ],
            "total": 1,
            "paging": {"offset": 0, "limit": 40, "total": 1,
                       "next_offset": None, "truncated": False},
        }

    def section(self, **kwargs):
        return {
            "filing": dict(FILING),
            "section": {"id": "part1-item1", "title": "Item 1. Business"},
            "text": SECTION_TEXT,
            "total_chars": len(SECTION_TEXT),
            "next_offset": None,
            "tables": [],
        }

    def search(self, **kwargs):
        return {
            "filing": dict(FILING),
            "query": "revenue",
            "hits": [
                {"kind": "text", "section_id": "part1-item1",
                 "title": "Item 1. Business", "snippet": "revenue"},
                {"kind": "table", "section_id": None, "title": "",
                 "snippet": "Revenue"},
            ],
            "total": 2,
        }

    def table(self, **kwargs):
        return {
            "filing": dict(FILING),
            "table": {"id": "t1", "section_id": "part1-item1",
                      "caption": "Revenue", "header_rows": 1,
                      "rows": 2, "columns": 2},
            "markdown": "| Item | FY2025 |\n| --- | --- |",
            "row_offset": 0,
            "next_offset": None,
            "total_rows": 1,
            "truncated": False,
        }


@pytest.fixture()
def tools():
    fake = _FakeMCP()
    register_tools(fake, _FakeService())
    return fake.tools


def test_filing_citation_embeds_the_artifact_locator():
    artifact = _locator("semantic-section", section_id="part1-item1")
    citation = _filing_citation(FILING, section="part1-item1", artifact=artifact)
    assert citation["artifact"] == artifact
    assert citation["source"] == "sec-report"
    # The viewer is not listening here, so there is no url (nothing can 404).
    assert "url" not in citation
    assert citation["original_url"] == FILING["source_url"]


def test_citation_is_an_identifier_with_no_url_while_the_viewer_is_stopped(tools):
    artifact_viewer.stop()

    citation = tools["report_section"]("AAPL", section_id="part1-item1")[
        "citations"
    ][0]

    assert "url" not in citation
    assert citation["citation_id"]
    assert citation["artifact"] == _locator(
        "semantic-section", section_id="part1-item1"
    )


def test_citation_stays_link_free_when_the_viewer_is_enabled(tools):
    # The viewer is a debug surface: enabling it never puts a url on a citation.
    public = "https://viewer.example.test"
    assert artifact_viewer.start(_free_port(), public_base=public) is not None

    citation = tools["report_section"]("AAPL", section_id="part1-item1")[
        "citations"
    ][0]

    assert "url" not in citation
    assert citation["citation_id"]


def test_filing_list_citations_report_cache_status(tools):
    payload = tools["filing_list"]("AAPL")
    citations = payload["citations"]
    assert [item["artifact"]["kind"] for item in citations] == [
        "semantic-index", "semantic-index",
    ]
    assert [item["artifact"]["status"] for item in citations] == [
        "cached", "not_cached",
    ]
    assert citations[0]["artifact"]["module"] == "reports"
    assert citations[0]["artifact"]["cik"] == CIK
    assert citations[0]["artifact"]["accession"] == ACCESSION
    assert citations[0]["artifact"]["format"] == "md"
    assert all("url" not in item for item in citations)
    assert all(item.get("original_url") == FILING["source_url"] for item in citations)


def test_section_tool_citations_are_semantic_sections(tools):
    listed = tools["report_sections"]("AAPL")
    assert listed["citations"][0]["artifact"] == _locator(
        "semantic-section", section_id="part1-item1"
    )
    single = tools["report_section"]("AAPL", section_id="part1-item1")
    assert single["citations"][0]["artifact"]["kind"] == "semantic-section"
    assert single["citations"][0]["artifact"]["section_id"] == "part1-item1"


def test_search_and_table_citation_kinds(tools):
    hits = tools["report_search"]("AAPL", query="revenue")
    kinds = [item["artifact"]["kind"] for item in hits["citations"]]
    assert kinds == ["semantic-section", "semantic-index"]

    table = tools["report_table"]("AAPL", table_id="t1")
    artifact = table["citations"][0]["artifact"]
    assert artifact["kind"] == "semantic-table"
    assert artifact["section_id"] == "part1-item1"
    assert artifact["table_id"] == "t1"


def test_two_search_hits_in_one_filing_never_share_identity():
    class _HitService(_FakeService):
        def search(self, **kwargs):
            return {
                "filing": dict(FILING),
                "query": "revenue",
                "hits": [
                    {"kind": "text", "section_id": "part1-item1",
                     "title": "Item 1. Business", "snippet": "revenue"},
                    {"kind": "table", "section_id": "part1-item1",
                     "title": "Item 1. Business", "table_id": "t1",
                     "snippet": "Revenue"},
                ],
                "total": 2,
            }

    fake = _FakeMCP()
    register_tools(fake, _HitService())
    found = fake.tools["report_search"]("AAPL", query="revenue")["citations"]

    # success() dedupes by key, so two surviving entries already prove the keys differ.
    assert len(found) == 2
    assert len({item["key"] for item in found}) == 2
    assert len({item["label"] for item in found}) == 2
    assert found[0]["artifact"]["kind"] == "semantic-section"
    assert found[1]["artifact"]["kind"] == "semantic-table"
    assert found[1]["artifact"]["table_id"] == "t1"


SUBMISSIONS = {
    "filings": {
        "recent": {
            "accessionNumber": [
                "0000320193-25-000079",
                "0000320193-25-000020",
            ],
            "form": ["10-K", "10-Q"],
            "filingDate": ["2025-10-31", "2025-05-02"],
            "reportDate": ["2025-09-27", "2025-03-29"],
            "primaryDocument": ["aapl-20250927.htm", ""],
        }
    }
}


def _make_source() -> edgar_source.ReportsEdgarSource:
    source = edgar_source.ReportsEdgarSource()
    source.company = lambda symbol: SimpleNamespace(cik=CIK, name="Apple Inc.")
    source._submissions_json = lambda cik: SUBMISSIONS
    return source


def test_filings_use_the_document_url_and_never_the_placeholder():
    refs = {ref.accession: ref for ref in _make_source().filings("AAPL")}
    assert refs["0000320193-25-000079"].source_url.endswith("/aapl-20250927.htm")
    assert refs["0000320193-25-000020"].source_url == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000020/"
    )
    assert all("(index)" not in ref.source_url for ref in refs.values())


def test_get_filing_by_accession_falls_back_to_the_index_page():
    filing = _make_source().get_filing("AAPL", accession="0000320193-25-000020")
    assert filing.primary_document == ""
    assert filing.source_url == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000020/"
    )


def test_edgartools_ref_falls_back_to_the_index_page():
    filing = SimpleNamespace(
        accession_no="0000320193-25-000020",
        primary_document="",
        primary_documents=(),
        period_of_report="2025-03-29",
        form="10-Q",
        filing_date="2025-05-02",
    )
    ref = edgar_source.ReportsEdgarSource._to_ref("AAPL", CIK, filing)
    assert ref is not None
    assert ref.source_url == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000020/"
    )
