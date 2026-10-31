"""Metric engine and DCF behavior."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core.errors import InvalidArgument  # noqa: E402
from core.models import LineItemSeries, LineItemValue  # noqa: E402
from modules.analysis.domain import dcf, engine  # noqa: E402

PERIODS = ("2025-09-30", "2024-09-30", "2023-09-30", "2022-09-30")


def series(items: dict[str, list[float]], periods=PERIODS) -> LineItemSeries:
    payload = {}
    for name, values in items.items():
        payload[name] = tuple(
            LineItemValue(
                line_item=name,
                label=name.replace("_", " ").title(),
                unit="shares" if name == "shares_diluted" else "USD",
                period_end=period,
                value=value,
                concept=f"Concept{name.title().replace('_', '')}",
                citation={"key": f"{name}-{period}", "accession": "0000000000-25-000001"},
            )
            for period, value in zip(periods, values)
            if value is not None
        )
    return LineItemSeries(
        symbol="TEST", cik=1, currency="USD", periods=tuple(periods),
        items=payload, facts_version="1:1",
    )


def test_gross_margin_and_current_ratio():
    data = series({
        "gross_profit": [60, 55, 50, 45],
        "revenue": [100, 95, 90, 85],
        "current_assets": [40, 38, 36, 34],
        "current_liabilities": [25, 24, 23, 22],
        "inventory": [5, 5, 4, 4],
    })
    margin = engine.compute_one(data, "gross_margin", PERIODS[0])
    assert margin.quality == "ok"
    assert margin.value == pytest.approx(0.6)
    assert margin.inputs and margin.inputs[0]["citation"]

    current = engine.compute_one(data, "current_ratio", PERIODS[0])
    assert current.value == pytest.approx(1.6)


def test_negative_equity_and_missing_inputs():
    data = series({
        "net_income": [-5, 1, 2, 3],
        "equity": [-10, 20, 21, 22],
        "revenue": [100, 95, 90, 85],
        "gross_profit": [60, 55, 50, 45],
        "operating_income": [20, 19, 18, 17],
        "total_assets": [200, 190, 180, 170],
    })
    roe = engine.compute_one(data, "roe", PERIODS[0])
    assert roe.quality == "not_meaningful"
    assert roe.value is None

    coverage = engine.compute_one(data, "interest_coverage", PERIODS[0])
    assert coverage.quality == "unavailable"
    assert "interest_expense" in (coverage.reason or "")


def test_growth_uses_consecutive_periods():
    data = series({"revenue": [100, 90, 80, 70]})
    cagr = engine.compute_one(data, "revenue_cagr", PERIODS[0])
    assert cagr.quality == "ok"
    assert cagr.value == pytest.approx((100 / 70) ** (1 / 3) - 1, rel=1e-6)

    short = series({"revenue": [100, 90, 80, 70]}, periods=PERIODS[:2])
    gap = engine.compute_one(short, "revenue_cagr", PERIODS[0])
    assert gap.quality == "gap"


def dcf_series() -> LineItemSeries:
    return series({
        "revenue": [100, 95, 90, 85],
        "operating_income": [20, 19, 18, 17],
        "pretax_income": [18, 17, 16, 15],
        "income_tax": [4, 4, 3, 3],
        "da": [5, 5, 5, 4],
        "capex": [6, 6, 5, 5],
        "current_assets": [40, 38, 36, 34],
        "current_liabilities": [25, 24, 23, 22],
        "total_debt": [30, 29, 28, 27],
        "cash": [10, 9, 8, 7],
        "shares_diluted": [10, 10, 10, 10],
    })


def test_dcf_assumptions_only():
    result = dcf.run(dcf_series(), assumptions_only=True)
    assert result["valuation"] is None
    names = {item["name"] for item in result["assumptions"]}
    assert {"revenue_growth", "operating_margin", "wacc", "terminal_growth"} <= names
    wacc = next(item for item in result["assumptions"] if item["name"] == "wacc")
    assert wacc["source"] == "default"
    assert wacc["assumption_quality"] == "policy_default"
    assert "assumptions_not_company_specific" in result["warnings"]


def test_dcf_computes_value_and_sensitivity():
    result = dcf.run(dcf_series())
    valuation = result["valuation"]
    assert valuation["enterprise_value"] > 0
    assert valuation["value_per_share"] > 0
    assert len(result["forecast"]) == 5
    assert result["sensitivity"]["grid"]
    assert result["terminal"]["method"] == "gordon"


def test_dcf_validation_rejects_percent_style_rates():
    with pytest.raises(InvalidArgument):
        dcf.run(dcf_series(), overrides={"wacc": 0.02})
    with pytest.raises(InvalidArgument):
        dcf.run(dcf_series(), overrides={"wacc": 8})


def test_dcf_exit_multiple_and_overrides():
    result = dcf.run(
        dcf_series(),
        overrides={
            "terminal_method": "exit_multiple",
            "exit_multiple": 12,
            "revenue_growth": [0.05, 0.04, 0.03, 0.03, 0.02],
            "wacc": 0.10,
        },
    )
    assert result["terminal"]["method"] == "exit_multiple"
    growth = next(item for item in result["assumptions"] if item["name"] == "revenue_growth")
    assert growth["source"] == "user"
