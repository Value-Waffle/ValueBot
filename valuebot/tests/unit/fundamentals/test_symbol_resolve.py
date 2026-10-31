"""Ticker resolution must accept edgartools' DataFrame shape."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from modules.fundamentals.sources import edgar_source  # noqa: E402

pd = pytest.importorskip("pandas")


class FakeEdgar:
    def __init__(self, tickers):
        self._tickers = tickers

    def get_company_tickers(self):
        return self._tickers


def test_resolve_dataframe_matches_ticker_and_name(monkeypatch):
    frame = pd.DataFrame(
        [
            {"cik": 320193, "ticker": "AAPL", "exchange": "Nasdaq", "company": "Apple Inc."},
            {"cik": 789019, "ticker": "MSFT", "exchange": "Nasdaq", "company": "Microsoft Corp"},
        ]
    )
    monkeypatch.setattr(edgar_source, "_load", lambda: FakeEdgar(frame))

    exact = edgar_source.EdgarSource().resolve("aapl")
    assert exact == [{"symbol": "AAPL", "name": "Apple Inc.", "cik": 320193, "score": 3}]

    by_name = edgar_source.EdgarSource().resolve("micro")
    assert [row["symbol"] for row in by_name] == ["MSFT"]


def test_resolve_legacy_dict_shape(monkeypatch):
    legacy = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    }
    monkeypatch.setattr(edgar_source, "_load", lambda: FakeEdgar(legacy))
    rows = edgar_source.EdgarSource().resolve("AAPL")
    assert rows == [{"symbol": "AAPL", "name": "Apple Inc.", "cik": 320193, "score": 3}]


def test_ticker_rows_handles_missing():
    assert edgar_source.EdgarSource._ticker_rows(None) == []
    assert edgar_source.EdgarSource._ticker_rows([]) == []
