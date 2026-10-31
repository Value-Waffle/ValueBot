"""MCP tools owned by the analysis module."""

from __future__ import annotations

import time

from core import citations
from core.errors import InternalError, ValuebotError
from core.response import failure, success

MODULE = "analysis"
DERIVED_KIND = "derived-inputs"


def _error(tool: str, exc: Exception, started: float) -> dict:
    if isinstance(exc, ValuebotError):
        return failure(MODULE, tool, exc, started=started)
    return failure(MODULE, tool, InternalError(str(exc)), started=started)


def _collect_citations(results) -> list[dict]:
    found = []
    for result in results:
        for item in result.get("inputs", ()):
            citation = item.get("citation")
            if citation:
                found.append(citation)
    return found


def _input_citations(result) -> list[dict]:
    return [
        item["citation"] for item in result.get("inputs", ())
        if item.get("citation")
    ]


def _derived_citations(data) -> list[dict]:
    """One resolvable ``derived-analysis`` citation per computed metric result."""
    found = []
    for result in data.get("results", ()):
        artifact = {
            "module": MODULE,
            "kind": DERIVED_KIND,
            "cik": data.get("cik"),
            "metric_id": result.get("metric_id"),
            "period_end": result.get("period_end"),
            "balance_basis": data.get("balance_basis"),
            "facts_version": data.get("facts_version"),
            "format": "json",
            "status": "cached",
        }
        found.append(
            citations.cite(
                "derived-analysis",
                f"{result.get('label')}, {result.get('period_end')}",
                cik=data.get("cik"),
                period=result.get("period_end"),
                extra={"derived_from": _input_citations(result)},
                artifact=artifact,
            )
        )
    return found


def register(mcp, service) -> None:
    @mcp.tool()
    def ratio_catalog(symbol: str | None = None, family: str | None = None) -> dict:
        """List profitability, leverage and growth metrics from SEC filing XBRL facts, with optional issuer availability.

        Args:
            symbol: Optional ticker to check line-item availability.
            family: Optional family filter: profitability, liquidity, leverage,
                efficiency, cash_quality, per_share, growth.
        """
        started = time.perf_counter()
        try:
            data = service.catalog(symbol, family)
            return success(
                MODULE, "ratio_catalog", data, symbol=symbol,
                started=started, cap=6144,
            )
        except Exception as exc:
            return _error("ratio_catalog", exc, started)

    @mcp.tool()
    def ratio_compute(
        symbol: str,
        metric_ids: list[str] | str,
        periods: int = 5,
        balance_basis: str = "average",
        include_inputs: bool = True,
    ) -> dict:
        """Compute profitability, leverage and growth ratios from SEC filing reported XBRL facts across annual periods.

        Args:
            symbol: Exact ticker.
            metric_ids: Metric IDs from ratio_catalog.
            periods: Number of annual periods (1-20).
            balance_basis: "average" or "ending" for balance-sheet inputs.
            include_inputs: Attach input values and citations per metric.
        """
        started = time.perf_counter()
        try:
            data = service.compute(
                symbol, metric_ids,
                periods=max(1, min(int(periods), 20)),
                balance_basis=balance_basis,
                include_inputs=bool(include_inputs),
            )
            # Derived citations lead so the openable artifact survives the cap.
            citations = _derived_citations(data) + _collect_citations(data["results"])
            return success(
                MODULE, "ratio_compute", data, symbol=data.get("symbol"),
                cik=data.get("cik"), citations=citations,
                started=started, cap=8192,
            )
        except Exception as exc:
            return _error("ratio_compute", exc, started)

    @mcp.tool()
    def dcf_compute(
        symbol: str,
        assumptions_only: bool = False,
        base_period_end: str | None = None,
        forecast_years: int = 5,
        revenue_growth: float | list[float] | None = None,
        operating_margin: float | list[float] | None = None,
        tax_rate: float | None = None,
        capex_pct_revenue: float | None = None,
        da_pct_revenue: float | None = None,
        nwc_pct_revenue: float | None = None,
        wacc: float | None = None,
        terminal_growth: float | None = None,
        terminal_method: str = "gordon",
        exit_multiple: float | None = None,
        shares_diluted: float | None = None,
        net_debt: float | None = None,
    ) -> dict:
        """Estimate intrinsic value from annual SEC filing data with a simple FCFF DCF, deriving and echoing every assumption.

        Call without assumptions first: the tool derives them from annual
        history, labels each one as user/derived/default, and returns the table.
        Set ``assumptions_only=true`` to inspect assumptions without a valuation.
        All rates are decimals (0.08 means 8%).

        Args:
            symbol: Exact ticker.
            assumptions_only: Return assumptions without a valuation.
            base_period_end: Base annual period end; defaults to the latest.
            forecast_years: Forecast horizon, 3-15.
            revenue_growth: Decimal or per-year list (-0.10 to 0.25).
            operating_margin: Decimal or per-year list (0.00 to 0.60).
            tax_rate: Cash tax rate (0.00 to 0.40).
            capex_pct_revenue: Capex intensity (0.00 to 0.30).
            da_pct_revenue: D&A intensity (0.00 to 0.20).
            nwc_pct_revenue: Incremental working capital (-0.20 to 0.50).
            wacc: Discount rate (0.03 to 0.30); default 0.09 is a policy default.
            terminal_growth: Perpetuity growth (-0.02 to 0.04); default 0.025.
            terminal_method: "gordon" or "exit_multiple".
            exit_multiple: EBITDA multiple when terminal_method is exit_multiple.
            shares_diluted: Override diluted share count.
            net_debt: Override net debt.
        """
        started = time.perf_counter()
        try:
            overrides = {
                "base_period_end": base_period_end,
                "forecast_years": int(forecast_years),
                "revenue_growth": revenue_growth,
                "operating_margin": operating_margin,
                "tax_rate": tax_rate,
                "capex_pct_revenue": capex_pct_revenue,
                "da_pct_revenue": da_pct_revenue,
                "nwc_pct_revenue": nwc_pct_revenue,
                "wacc": wacc,
                "terminal_growth": terminal_growth,
                "terminal_method": terminal_method,
                "exit_multiple": exit_multiple,
                "shares_diluted": shares_diluted,
                "net_debt": net_debt,
            }
            overrides = {key: value for key, value in overrides.items() if value is not None}
            data = service.dcf(
                symbol, overrides=overrides, assumptions_only=bool(assumptions_only)
            )
            citations = [
                item["citation"] for item in data.get("assumptions", ())
                if item.get("citation")
            ]
            return success(
                MODULE, "dcf_compute", data, symbol=data.get("symbol"),
                cik=data.get("cik"), citations=citations,
                started=started, cap=8192,
                meta={"model_version": data.get("model_version", 1)},
            )
        except Exception as exc:
            return _error("dcf_compute", exc, started)
