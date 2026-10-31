"""Reports filing index reads SEC submissions JSON instead of edgartools."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from modules.reports.sources import edgar_source  # noqa: E402
from modules.reports.store import db, filings_store  # noqa: E402

SUBMISSIONS = {
    "filings": {
        "recent": {
            "accessionNumber": [
                "0000320193-25-000079",
                "0000320193-25-000020",
                "0000320193-24-000123",
                "0000320193-23-000106",
            ],
            "form": ["10-K", "10-Q", "10-K", "10-K"],
            "filingDate": ["2025-10-31", "2025-05-02", "2024-11-01", "2023-11-03"],
            "reportDate": ["2025-09-27", "2025-03-29", "2024-09-28", "2023-09-30"],
            "primaryDocument": [
                "aapl-20250927.htm",
                "aapl-20250329.htm",
                "aapl-20240928.htm",
                "aapl-20230930.htm",
            ],
        }
    }
}


def make_source():
    source = edgar_source.ReportsEdgarSource()
    source.company = lambda symbol: SimpleNamespace(cik=320193, name="Apple Inc.")
    source._submissions_json = lambda cik: SUBMISSIONS
    return source


def test_filings_filter_by_form_and_period():
    refs = make_source().filings("aapl", forms=["10-K"], start="2024-01-01")
    assert [ref.accession for ref in refs] == [
        "0000320193-25-000079",
        "0000320193-24-000123",
    ]
    assert refs[0].symbol == "AAPL"
    assert refs[0].cik == 320193
    assert refs[0].form == "10-K"
    assert refs[0].period_of_report == "2025-09-27"
    assert refs[0].source_url.endswith("/aapl-20250927.htm")
    assert "320193/000032019325000079" in refs[0].source_url


def test_get_filing_matches_accession_and_latest_form():
    source = make_source()
    by_accession = source.get_filing("AAPL", accession="0000320193-24-000123")
    assert by_accession.period_of_report == "2024-09-28"

    latest = source.get_filing("AAPL", form="10-K")
    assert latest.accession == "0000320193-25-000079"
    assert latest.filed == "2025-10-31"


def test_store_latest_returns_newest_matching_form(tmp_path):
    conn = db.connect(tmp_path / "manifest.sqlite")
    try:
        refs = make_source().filings("AAPL")
        filings_store.sync_issuer(conn, "AAPL", 320193, "Apple Inc.", refs, fetched_at=1.0)
        latest = filings_store.latest(conn, 320193, "10-K")
        assert latest is not None
        assert latest.accession == "0000320193-25-000079"
        assert latest.period_of_report == "2025-09-27"
        assert filings_store.cached_symbol(conn, "aapl") == 320193
    finally:
        conn.close()
