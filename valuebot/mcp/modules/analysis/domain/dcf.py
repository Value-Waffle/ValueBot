"""Simple FCFF DCF with explicit, echoed assumptions."""

from __future__ import annotations

from statistics import median

from core.errors import InvalidArgument, MetricUnavailable
from core.models import DcfAssumption, DcfForecastRow, DcfResult, LineItemSeries

MODEL_VERSION = 1
DEFAULT_WACC = 0.09
DEFAULT_TERMINAL_GROWTH = 0.025
DEFAULT_FORECAST_YEARS = 5

_RANGES = {
    "revenue_growth": (-0.10, 0.25),
    "operating_margin": (0.00, 0.60),
    "tax_rate": (0.00, 0.40),
    "capex_pct_revenue": (0.00, 0.30),
    "da_pct_revenue": (0.00, 0.20),
    "nwc_pct_revenue": (-0.20, 0.50),
    "wacc": (0.03, 0.30),
    "terminal_growth": (-0.02, 0.04),
}


def _values(series: LineItemSeries, item: str) -> dict[str, float]:
    return {
        period: value.value
        for period, value in (
            (entry.period_end, entry) for entry in series.items.get(item, ())
        )
        if value.value is not None
    }


def _latest(series: LineItemSeries, item: str) -> tuple[float | None, object]:
    values = series.items.get(item, ())
    for entry in values:
        if entry.value is not None:
            return entry.value, entry
    return None, None


def _citation(entry) -> dict | None:
    return getattr(entry, "citation", None) if entry is not None else None


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _validate(name: str, value: float) -> float:
    low, high = _RANGES[name]
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidArgument(f"{name} must be a decimal number") from exc
    if not low <= number <= high:
        raise InvalidArgument(
            f"{name}={number} is outside [{low}, {high}]",
            hint="Rates are decimals: use 0.08 for 8%.",
        )
    return number


def _growth_from_history(series: LineItemSeries) -> tuple[float | None, str]:
    values = _values(series, "revenue")
    periods = list(series.periods)
    for index in range(min(3, max(0, len(periods) - 1))):
        current = values.get(periods[index]) if index < len(periods) else None
        previous = values.get(periods[index + 3]) if index + 3 < len(periods) else None
        if current and previous and current > 0 and previous > 0:
            return (current / previous) ** (1 / 3) - 1, f"3-year revenue CAGR to {periods[index]}"
    return None, "insufficient revenue history"


def _median_ratio(series: LineItemSeries, numerator: str, denominator: str,
                  periods: int = 3, absolute: bool = False) -> float | None:
    values = []
    for period in list(series.periods)[:periods]:
        top = _values(series, numerator).get(period)
        bottom = _values(series, denominator).get(period)
        if top is None or bottom in (None, 0):
            continue
        values.append((abs(top) if absolute else top) / bottom)
    return median(values) if values else None


def _assumption(name, value, display, unit, source, derivation="", periods=(),
                quality="company_history", citation=None) -> DcfAssumption:
    return DcfAssumption(
        name=name, value=value, display=display, unit=unit, source=source,
        derivation=derivation, periods_used=tuple(periods),
        assumption_quality=quality, citation=citation,
    )


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _derive(series: LineItemSeries, overrides: dict | None) -> tuple[list[DcfAssumption], dict, list[str]]:
    overrides = dict(overrides or {})
    warnings: list[str] = []
    assumptions: list[DcfAssumption] = []

    periods = list(series.periods)
    if not periods:
        raise MetricUnavailable("no annual periods available for a DCF")

    base_period = overrides.pop("base_period_end", None) or periods[0]
    if base_period not in periods:
        raise InvalidArgument(f"base_period_end {base_period} is not an annual period")

    def series_value(item: str):
        values = _values(series, item)
        entry = next((e for e in series.items.get(item, ()) if e.period_end == base_period), None)
        return values.get(base_period), entry

    revenue, revenue_entry = series_value("revenue")
    if revenue is None:
        raise MetricUnavailable(
            "revenue is required for a DCF", details={"missing_line_items": ["revenue"]}
        )
    shares, shares_entry = series_value("shares_diluted")
    net_debt_value, _ = series_value("net_debt")
    total_debt, debt_entry = series_value("total_debt")
    cash, cash_entry = series_value("cash")
    if net_debt_value is None:
        if total_debt is None and cash is None:
            raise MetricUnavailable(
                "net debt is required for a DCF",
                details={"missing_line_items": ["total_debt", "cash"]},
            )
        net_debt_value = (total_debt or 0.0) - (cash or 0.0)
    if shares in (None, 0):
        raise MetricUnavailable(
            "diluted shares are required for a DCF",
            details={"missing_line_items": ["shares_diluted"]},
        )

    # -- growth -----------------------------------------------------------
    growth_override = overrides.get("revenue_growth")
    if growth_override is not None:
        raw = growth_override if isinstance(growth_override, (list, tuple)) else [growth_override]
        growth_values = [_validate("revenue_growth", item) for item in raw]
        assumptions.append(_assumption(
            "revenue_growth", growth_values[0] if len(growth_values) == 1 else growth_values,
            _pct(growth_values[0]) if len(growth_values) == 1 else ", ".join(_pct(v) for v in growth_values),
            "percent", "user",
        ))
    else:
        historical, derivation = _growth_from_history(series)
        if historical is None:
            growth_value = 0.03
            assumptions.append(_assumption(
                "revenue_growth", growth_value, _pct(growth_value), "percent", "default",
                derivation="policy fallback; " + derivation, quality="policy_default",
            ))
        else:
            growth_value = _clip(historical, *_RANGES["revenue_growth"])
            assumptions.append(_assumption(
                "revenue_growth", growth_value, _pct(growth_value), "percent", "derived",
                derivation=derivation, periods=periods[:4],
                citation=_citation(revenue_entry),
            ))
        growth_values = [growth_value]

    def derived(name: str, computed: float | None, fallback: float, derivation: str,
                entry=None, periods_used=()):
        override = overrides.get(name)
        if override is not None:
            value = _validate(name, override)
            assumptions.append(_assumption(name, value, _pct(value), "percent", "user"))
            return value
        if computed is None:
            _validate(name, fallback)
            assumptions.append(_assumption(
                name, fallback, _pct(fallback), "percent", "default",
                derivation="policy fallback; " + derivation, quality="policy_default",
            ))
            return fallback
        value = _clip(computed, *_RANGES[name])
        assumptions.append(_assumption(
            name, value, _pct(value), "percent", "derived",
            derivation=derivation, periods=periods_used, citation=_citation(entry),
        ))
        return value

    margin = derived(
        "operating_margin",
        _median_ratio(series, "operating_income", "revenue"),
        0.10, "median operating margin, last 3 years",
        series.items.get("operating_income", (None,))[0] if series.items.get("operating_income") else None,
        periods[:3],
    )
    tax_rate = derived(
        "tax_rate", _median_ratio(series, "income_tax", "pretax_income"),
        0.21, "median effective tax rate, last 3 years",
        series.items.get("income_tax", (None,))[0] if series.items.get("income_tax") else None,
        periods[:3],
    )
    capex_pct = derived(
        "capex_pct_revenue", _median_ratio(series, "capex", "revenue", absolute=True),
        0.05, "median capex intensity, last 3 years",
        series.items.get("capex", (None,))[0] if series.items.get("capex") else None,
        periods[:3],
    )
    da_pct = derived(
        "da_pct_revenue", _median_ratio(series, "da", "revenue"),
        0.04, "median D&A intensity, last 3 years",
        series.items.get("da", (None,))[0] if series.items.get("da") else None,
        periods[:3],
    )
    assets, assets_entry = series_value("current_assets")
    liabilities, liabilities_entry = series_value("current_liabilities")
    nwc_value = None if assets is None or liabilities is None else assets - liabilities
    nwc_pct = derived(
        "nwc_pct_revenue",
        None if nwc_value is None else nwc_value / revenue,
        0.05, "base working capital divided by base revenue",
        assets_entry or liabilities_entry, (base_period,),
    )

    wacc_override = overrides.get("wacc")
    if wacc_override is not None:
        wacc = _validate("wacc", wacc_override)
        assumptions.append(_assumption("wacc", wacc, _pct(wacc), "percent", "user"))
        wacc_is_default = False
    else:
        wacc = DEFAULT_WACC
        assumptions.append(_assumption(
            "wacc", wacc, _pct(wacc), "percent", "default",
            derivation="policy default, not market-derived", quality="policy_default",
        ))
        wacc_is_default = True

    growth_terminal_override = overrides.get("terminal_growth")
    if growth_terminal_override is not None:
        terminal_growth = _validate("terminal_growth", growth_terminal_override)
        assumptions.append(_assumption(
            "terminal_growth", terminal_growth, _pct(terminal_growth), "percent", "user"
        ))
        terminal_is_default = False
    else:
        terminal_growth = DEFAULT_TERMINAL_GROWTH
        assumptions.append(_assumption(
            "terminal_growth", terminal_growth, _pct(terminal_growth), "percent", "default",
            derivation="policy default", quality="policy_default",
        ))
        terminal_is_default = True

    if wacc - terminal_growth < 0.01:
        raise InvalidArgument("wacc must exceed terminal_growth by at least 1 percentage point")

    forecast_years = int(overrides.get("forecast_years", DEFAULT_FORECAST_YEARS))
    if not 3 <= forecast_years <= 15:
        raise InvalidArgument("forecast_years must be between 3 and 15")

    shares_override = overrides.get("shares_diluted")
    if shares_override is not None:
        shares = float(shares_override)
        assumptions.append(_assumption("shares_diluted", shares, f"{shares:,.0f}", "shares", "user"))
    else:
        assumptions.append(_assumption(
            "shares_diluted", shares, f"{shares:,.0f}", "shares", "derived",
            derivation=f"diluted shares at {base_period}", periods=(base_period,),
            citation=_citation(shares_entry),
        ))

    net_debt_override = overrides.get("net_debt")
    if net_debt_override is not None:
        net_debt_value = float(net_debt_override)
        assumptions.append(_assumption(
            "net_debt", net_debt_value, f"{net_debt_value:,.0f}", "currency", "user"
        ))
    else:
        assumptions.append(_assumption(
            "net_debt", net_debt_value, f"{net_debt_value:,.0f}", "currency", "derived",
            derivation="total debt minus cash", periods=(base_period,),
            citation=_citation(debt_entry or cash_entry),
        ))

    if wacc_is_default or terminal_is_default:
        warnings.append("assumptions_not_company_specific")
    if margin == 0.10 and "operating_margin" not in overrides:
        warnings.append("operating_margin_fallback")
    if revenue <= 0:
        warnings.append("non_positive_base_revenue")

    terminal_method = str(overrides.get("terminal_method", "gordon")).lower()
    if terminal_method not in {"gordon", "exit_multiple"}:
        raise InvalidArgument("terminal_method must be gordon or exit_multiple")
    exit_multiple = overrides.get("exit_multiple")
    if terminal_method == "exit_multiple":
        if exit_multiple is None:
            raise InvalidArgument("exit_multiple is required for terminal_method=exit_multiple")
        exit_multiple = float(exit_multiple)
        if not 3 <= exit_multiple <= 30:
            raise InvalidArgument("exit_multiple must be between 3 and 30")

    state = {
        "base_period": base_period,
        "revenue": revenue,
        "growth": growth_values,
        "margin": margin,
        "tax_rate": tax_rate,
        "capex_pct": capex_pct,
        "da_pct": da_pct,
        "nwc_pct": nwc_pct,
        "wacc": wacc,
        "terminal_growth": terminal_growth,
        "shares": shares,
        "net_debt": net_debt_value,
        "forecast_years": forecast_years,
        "terminal_method": terminal_method,
        "exit_multiple": exit_multiple,
        "base_ebit": _values(series, "operating_income").get(base_period),
    }
    if state["base_ebit"] is not None and state["base_ebit"] <= 0:
        warnings.append("negative_base_earnings")
    return assumptions, state, warnings


def _project(state: dict) -> tuple[list[DcfForecastRow], float, float]:
    wacc = state["wacc"]
    revenue = state["revenue"]
    previous_nwc = revenue * state["nwc_pct"]
    rows: list[DcfForecastRow] = []
    pv_total = 0.0
    last_ebit = last_da = 0.0
    for year in range(1, state["forecast_years"] + 1):
        growth = state["growth"][min(year - 1, len(state["growth"]) - 1)]
        revenue = revenue * (1 + growth)
        ebit = revenue * state["margin"]
        taxes = max(0.0, ebit) * state["tax_rate"]
        nopat = ebit - taxes
        da = revenue * state["da_pct"]
        capex = revenue * state["capex_pct"]
        nwc = revenue * state["nwc_pct"]
        delta = nwc - previous_nwc
        previous_nwc = nwc
        fcff = nopat + da - capex - delta
        discount = 1.0 / ((1 + wacc) ** year)
        pv = fcff * discount
        pv_total += pv
        rows.append(
            DcfForecastRow(
                year=year, period_end=f"Y+{year}", revenue=revenue, ebit=ebit,
                taxes=taxes, nopat=nopat, da=da, capex=capex, delta_nwc=delta,
                fcff=fcff, discount_factor=discount, pv=pv,
            )
        )
        last_ebit, last_da = ebit, da

    if state["terminal_method"] == "exit_multiple":
        terminal_value = (last_ebit + last_da) * state["exit_multiple"]
    else:
        last_fcff = rows[-1].fcff
        terminal_value = (
            last_fcff * (1 + state["terminal_growth"])
            / (state["wacc"] - state["terminal_growth"])
        )
    return rows, terminal_value, pv_total


def _per_share(state: dict, wacc: float, growth: float) -> float:
    trial = dict(state)
    trial["wacc"] = wacc
    trial["terminal_growth"] = growth
    rows, terminal_value, pv_total = _project(trial)
    pv_terminal = terminal_value / ((1 + wacc) ** len(rows))
    equity = pv_total + pv_terminal - state["net_debt"]
    return equity / state["shares"]


def run(series: LineItemSeries, overrides: dict | None = None, assumptions_only: bool = False) -> dict:
    assumptions, state, warnings = _derive(series, overrides)
    assumption_dicts = [
        {
            "name": item.name,
            "value": item.value,
            "display": item.display,
            "unit": item.unit,
            "source": item.source,
            "derivation": item.derivation,
            "periods_used": list(item.periods_used),
            "assumption_quality": item.assumption_quality,
            "citation": item.citation,
        }
        for item in assumptions
    ]
    base = {
        "symbol": series.symbol,
        "cik": series.cik,
        "currency": series.currency,
        "base_period_end": state["base_period"],
        "forecast_years": state["forecast_years"],
        "assumptions": assumption_dicts,
        "assumptions_complete": True,
        "model_version": MODEL_VERSION,
    }
    if assumptions_only:
        return {
            **base,
            "valuation": None,
            "forecast": [],
            "terminal": None,
            "sensitivity": None,
            "warnings": warnings,
        }

    rows, terminal_value, pv_total = _project(state)
    pv_terminal = terminal_value / ((1 + state["wacc"]) ** len(rows))
    enterprise_value = pv_total + pv_terminal
    equity_value = enterprise_value - state["net_debt"]
    per_share = equity_value / state["shares"]
    terminal_share = pv_terminal / enterprise_value if enterprise_value else 0.0
    if terminal_share > 0.75:
        warnings.append("terminal_value_dominates")

    wacc_values = [state["wacc"] + offset for offset in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    growth_values = [state["terminal_growth"] + offset for offset in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    growth_values = [
        value for value in growth_values if -0.02 <= value < state["wacc"] - 0.01
    ]
    grid = [
        [round(_per_share(state, wacc, growth), 2) for growth in growth_values]
        for wacc in wacc_values
        if wacc > state["terminal_growth"] + 0.01
    ]

    return {
        **base,
        "valuation": {
            "enterprise_value": enterprise_value,
            "net_debt": state["net_debt"],
            "equity_value": equity_value,
            "shares_diluted": state["shares"],
            "value_per_share": per_share,
            "currency": series.currency,
        },
        "terminal": {
            "method": state["terminal_method"],
            "value": terminal_value,
            "pv": pv_terminal,
            "share_of_ev": terminal_share,
        },
        "forecast": [row.__dict__ for row in rows],
        "sensitivity": {
            "wacc_values": wacc_values,
            "growth_values": growth_values,
            "grid": grid,
        },
        "warnings": warnings,
    }
