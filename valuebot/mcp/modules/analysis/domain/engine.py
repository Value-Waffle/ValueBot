"""Pure metric engine over a LineItemSeries."""

from __future__ import annotations

from datetime import date
from statistics import median

from core.models import LineItemSeries, MetricResult

from . import metrics


def _value(series: LineItemSeries, item: str, period: str):
    return series.period_values(item).get(period)


def _num(series: LineItemSeries, item: str, period: str) -> float | None:
    value = _value(series, item, period)
    return value.value if value is not None else None


def _display(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "percent":
        return f"{value * 100:.1f}%"
    if unit in {"ratio", "turns"}:
        return f"{value:.2f}x"
    if unit == "days":
        return f"{value:.1f}"
    return f"{value:,.0f}"


def _result(definition, period, value, quality, formula, inputs, reason=None):
    return MetricResult(
        metric_id=definition.metric_id,
        label=definition.label,
        family=definition.family,
        period_end=period,
        value=value if quality in {"ok", "partial"} else None,
        display=_display(value if quality in {"ok", "partial"} else None, definition.unit),
        unit=definition.unit,
        quality=quality,
        formula=formula,
        formula_version=definition.version,
        inputs=tuple(inputs),
        reason=reason,
    )


def _inputs(series, items, period):
    rows = []
    for item in items:
        value = _value(series, item, period)
        if value is None:
            continue
        rows.append(
            {
                "line_item": item,
                "label": value.label,
                "value": value.value,
                "unit": value.unit,
                "concept": value.concept,
                "period_end": value.period_end,
                "citation": value.citation,
            }
        )
    return rows


def _missing(series, items, period, optional=()):
    return [item for item in items if item not in optional and _num(series, item, period) is None]


def _safe_ratio(numerator, denominator):
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return "zero"
    return numerator / denominator


def _growth(series, item, period, window):
    periods = list(series.periods)
    if period not in periods:
        return "gap"
    index = periods.index(period)
    if index + window >= len(periods):
        return "gap"
    current = _num(series, item, period)
    previous = _num(series, item, periods[index + window])
    if current is None or previous is None:
        return "unavailable"
    try:
        current_date = date.fromisoformat(period)
        previous_date = date.fromisoformat(periods[index + window])
    except ValueError:
        return "gap"
    gap_days = abs((current_date - previous_date).days)
    if not 330 * window <= gap_days <= 400 * window:
        return "gap"
    if previous == 0:
        return "not_meaningful"
    if current <= 0 or previous <= 0:
        return "not_meaningful"
    return (current / previous) ** (1.0 / window) - 1.0


def _fcf(series, period):
    cfo, capex = _num(series, "cfo", period), _num(series, "capex", period)
    if cfo is None or capex is None:
        return None
    return cfo - abs(capex)


def _median(values):
    numeric = [value for value in values if value is not None]
    return median(numeric) if numeric else None


def compute_one(series: LineItemSeries, metric_id: str, period: str) -> MetricResult:
    definition = metrics.get(metric_id)
    items = definition.line_items
    missing = _missing(series, items, period)
    if missing:
        # Two ratios tolerate absent optional lines.
        if metric_id == "quick_ratio" and missing == ["inventory"]:
            pass
        elif metric_id == "cash_ratio" and missing == ["short_term_investments"]:
            pass
        else:
            return _result(definition, period, None, "unavailable",
                           definition.formula, _inputs(series, items, period),
                           reason=f"missing: {', '.join(missing)}")

    def n(item):
        value = _num(series, item, period)
        return 0.0 if value is None else value

    quality = "ok"
    reason = None
    value = None

    if metric_id == "gross_margin":
        value = _safe_ratio(n("gross_profit"), n("revenue"))
    elif metric_id == "operating_margin":
        value = _safe_ratio(n("operating_income"), n("revenue"))
    elif metric_id == "net_margin":
        value = _safe_ratio(n("net_income"), n("revenue"))
    elif metric_id == "roa":
        value = _safe_ratio(n("net_income"), n("total_assets"))
    elif metric_id == "roe":
        equity = n("equity")
        value = _safe_ratio(n("net_income"), equity) if equity > 0 else "negative_equity"
    elif metric_id == "roic":
        tax = 0.0
        pretax, tax_expense = n("pretax_income"), n("income_tax")
        if pretax > 0:
            tax = min(max(tax_expense / pretax, 0.0), 1.0)
        invested = n("total_debt") + n("equity") - n("cash")
        if invested <= 0:
            value = "negative_capital"
        else:
            value = (n("operating_income") * (1 - tax)) / invested
    elif metric_id == "fcf_margin":
        value = _safe_ratio(_fcf(series, period), n("revenue"))
    elif metric_id == "current_ratio":
        value = _safe_ratio(n("current_assets"), n("current_liabilities"))
    elif metric_id == "quick_ratio":
        if _num(series, "inventory", period) is None:
            quality = "partial"
        value = _safe_ratio(n("current_assets") - n("inventory"), n("current_liabilities"))
    elif metric_id == "cash_ratio":
        if _num(series, "short_term_investments", period) is None:
            quality = "partial"
        value = _safe_ratio(n("cash") + n("short_term_investments"), n("current_liabilities"))
    elif metric_id == "working_capital":
        value = n("current_assets") - n("current_liabilities")
    elif metric_id == "debt_to_equity":
        equity = n("equity")
        value = _safe_ratio(n("total_debt"), equity) if equity > 0 else "negative_equity"
    elif metric_id == "net_debt":
        value = n("total_debt") - n("cash")
    elif metric_id == "net_debt_to_ebitda":
        ebitda = n("operating_income") + n("da")
        value = _safe_ratio(n("total_debt") - n("cash"), ebitda) if ebitda > 0 else "negative_ebitda"
    elif metric_id == "interest_coverage":
        interest = n("interest_expense")
        value = _safe_ratio(n("operating_income"), interest) if interest != 0 else "no_interest"
    elif metric_id == "equity_multiplier":
        equity = n("equity")
        value = _safe_ratio(n("total_assets"), equity) if equity > 0 else "negative_equity"
    elif metric_id == "asset_turnover":
        value = _safe_ratio(n("revenue"), n("total_assets"))
    elif metric_id == "inventory_turnover":
        value = _safe_ratio(n("cost_of_revenue"), n("inventory"))
    elif metric_id == "receivables_turnover":
        value = _safe_ratio(n("revenue"), n("accounts_receivable"))
    elif metric_id == "dso":
        turnover = _safe_ratio(n("revenue"), n("accounts_receivable"))
        value = 365 / turnover if isinstance(turnover, float) and turnover else turnover
    elif metric_id == "dio":
        turnover = _safe_ratio(n("cost_of_revenue"), n("inventory"))
        value = 365 / turnover if isinstance(turnover, float) and turnover else turnover
    elif metric_id == "dpo":
        turnover = _safe_ratio(n("cost_of_revenue"), n("accounts_payable"))
        value = 365 / turnover if isinstance(turnover, float) and turnover else turnover
    elif metric_id == "cash_conversion_cycle":
        dso = compute_one(series, "dso", period).value
        dio = compute_one(series, "dio", period).value
        dpo = compute_one(series, "dpo", period).value
        if dso is None or dio is None or dpo is None:
            value = "component_unavailable"
            quality = "partial"
        else:
            value = dso + dio - dpo
    elif metric_id == "capex_to_revenue":
        value = _safe_ratio(abs(n("capex")), n("revenue"))
    elif metric_id == "fcf":
        value = _fcf(series, period)
    elif metric_id == "fcf_per_share":
        fcf = _fcf(series, period)
        value = _safe_ratio(fcf, n("shares_diluted"))
    elif metric_id == "cfo_to_net_income":
        value = _safe_ratio(n("cfo"), n("net_income"))
        if n("net_income") <= 0:
            value = "negative_earnings"
    elif metric_id == "accrual_ratio":
        value = _safe_ratio(n("net_income") - n("cfo"), n("total_assets"))
    elif metric_id == "book_value_per_share":
        value = _safe_ratio(n("equity"), n("shares_diluted"))
    elif metric_id == "revenue_per_share":
        value = _safe_ratio(n("revenue"), n("shares_diluted"))
    elif metric_id in {"revenue_cagr", "eps_cagr", "fcf_cagr"}:
        item = {"revenue_cagr": "revenue", "eps_cagr": "eps_diluted", "fcf_cagr": None}[metric_id]
        if item is None:
            current = _fcf(series, period)
            periods = list(series.periods)
            index = periods.index(period) if period in periods else -1
            previous = None
            if index >= 0 and index + 3 < len(periods):
                previous = _fcf(series, periods[index + 3])
            if current is None or previous is None:
                value = "gap"
            elif current <= 0 or previous <= 0:
                value = "not_meaningful"
            else:
                value = (current / previous) ** (1.0 / 3.0) - 1.0
        else:
            value = _growth(series, item, period, 3)
    elif metric_id == "equity_growth":
        value = _growth(series, "equity", period, 1)
    elif metric_id == "share_dilution":
        value = _growth(series, "shares_diluted", period, 1)
    elif metric_id == "dupont_return":
        margin = _safe_ratio(n("net_income"), n("revenue"))
        turnover = _safe_ratio(n("revenue"), n("total_assets"))
        multiplier = _safe_ratio(n("total_assets"), n("equity"))
        if None in (margin, turnover, multiplier) or not all(
            isinstance(part, float) for part in (margin, turnover, multiplier)
        ):
            value = "component_unavailable"
            quality = "partial"
        else:
            value = margin * turnover * multiplier

    if isinstance(value, str):
        reason = value
        value = None
        quality = {
            "gap": "gap",
            "unavailable": "unavailable",
            "component_unavailable": "partial",
        }.get(reason, "not_meaningful" if quality == "ok" else quality)

    return _result(definition, period, value, quality, definition.formula,
                   _inputs(series, items, period), reason=reason)


def compute(series: LineItemSeries, metric_ids, periods: int = 5) -> list[MetricResult]:
    selected_periods = list(series.periods)[: max(1, int(periods))]
    results: list[MetricResult] = []
    for metric_id in metric_ids:
        metrics.get(metric_id)  # validate
        for period in selected_periods:
            results.append(compute_one(series, metric_id, period))
    return results
