"""Analysis service must fetch enough history for growth windows."""

from __future__ import annotations

import sys
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core.models import LineItemSeries, LineItemValue  # noqa: E402
from modules.analysis.service import AnalysisService  # noqa: E402

PERIOD_ENDS = (
    "2025-09-30", "2024-09-30", "2023-09-30", "2022-09-30",
    "2021-09-30", "2020-09-30", "2019-09-30", "2018-09-30",
)


class FakeFacts:
    def __init__(self, periods=PERIOD_ENDS):
        self.periods = tuple(periods)
        self.requested: list[int] = []

    def line_items(self, symbol, items, *, periods=5, balance_basis="average"):
        self.requested.append(periods)
        revenue = tuple(
            LineItemValue(
                line_item="revenue",
                label="Revenue",
                unit="USD",
                period_end=period,
                value=100.0 - 5.0 * index,
                concept="Revenues",
                citation={"accession": "0000000000-25-000001"},
            )
            for index, period in enumerate(self.periods)
        )
        return LineItemSeries(
            symbol=symbol.upper(),
            cik=1,
            currency="USD",
            periods=self.periods,
            items={"revenue": revenue},
            facts_version="1:1",
        )


def test_growth_metric_fetches_beyond_requested_periods(tmp_path):
    facts = FakeFacts()
    service = AnalysisService(facts, cache_path=tmp_path / "analysis.sqlite")
    try:
        payload = service.compute("TEST", ["revenue_cagr"], periods=3)
    finally:
        service.close()

    assert facts.requested == [6]
    assert payload["periods"] == list(PERIOD_ENDS[:3])
    assert payload["results"]
    for result in payload["results"]:
        assert result["quality"] == "ok", result
        assert result["value"] is not None
