"""Declarative metric catalog owned by the analysis module."""

from __future__ import annotations

from core.models import MetricDef

FORMULA_VERSION = 1

METRICS: dict[str, MetricDef] = {
    "gross_margin": MetricDef("gross_margin", "Gross margin", "profitability",
        "gross_profit / revenue", ("gross_profit", "revenue"), "percent", "higher_is_better"),
    "operating_margin": MetricDef("operating_margin", "Operating margin", "profitability",
        "operating_income / revenue", ("operating_income", "revenue"), "percent", "higher_is_better"),
    "net_margin": MetricDef("net_margin", "Net margin", "profitability",
        "net_income / revenue", ("net_income", "revenue"), "percent", "higher_is_better"),
    "roa": MetricDef("roa", "Return on assets", "profitability",
        "net_income / total_assets", ("net_income", "total_assets"), "percent", "higher_is_better"),
    "roe": MetricDef("roe", "Return on equity", "profitability",
        "net_income / equity", ("net_income", "equity"), "percent", "higher_is_better"),
    "roic": MetricDef("roic", "Return on invested capital", "profitability",
        "nopat / invested_capital",
        ("operating_income", "pretax_income", "income_tax", "total_debt", "equity", "cash"),
        "percent", "higher_is_better"),
    "fcf_margin": MetricDef("fcf_margin", "Free-cash-flow margin", "profitability",
        "(cfo - capex) / revenue", ("cfo", "capex", "revenue"), "percent", "higher_is_better"),
    "current_ratio": MetricDef("current_ratio", "Current ratio", "liquidity",
        "current_assets / current_liabilities", ("current_assets", "current_liabilities"),
        "ratio", "higher_is_better"),
    "quick_ratio": MetricDef("quick_ratio", "Quick ratio", "liquidity",
        "(current_assets - inventory) / current_liabilities",
        ("current_assets", "inventory", "current_liabilities"), "ratio", "higher_is_better"),
    "cash_ratio": MetricDef("cash_ratio", "Cash ratio", "liquidity",
        "(cash + short_term_investments) / current_liabilities",
        ("cash", "short_term_investments", "current_liabilities"), "ratio", "higher_is_better"),
    "working_capital": MetricDef("working_capital", "Working capital", "liquidity",
        "current_assets - current_liabilities", ("current_assets", "current_liabilities"),
        "currency", "higher_is_better"),
    "debt_to_equity": MetricDef("debt_to_equity", "Debt to equity", "leverage",
        "total_debt / equity", ("total_debt", "equity"), "ratio", "lower_is_better"),
    "net_debt": MetricDef("net_debt", "Net debt", "leverage",
        "total_debt - cash", ("total_debt", "cash"), "currency", "lower_is_better"),
    "net_debt_to_ebitda": MetricDef("net_debt_to_ebitda", "Net debt to EBITDA", "leverage",
        "(total_debt - cash) / (operating_income + da)",
        ("total_debt", "cash", "operating_income", "da"), "ratio", "lower_is_better"),
    "interest_coverage": MetricDef("interest_coverage", "Interest coverage", "leverage",
        "operating_income / interest_expense", ("operating_income", "interest_expense"),
        "ratio", "higher_is_better"),
    "equity_multiplier": MetricDef("equity_multiplier", "Equity multiplier", "leverage",
        "total_assets / equity", ("total_assets", "equity"), "ratio", "contextual"),
    "asset_turnover": MetricDef("asset_turnover", "Asset turnover", "efficiency",
        "revenue / total_assets", ("revenue", "total_assets"), "turns", "higher_is_better"),
    "inventory_turnover": MetricDef("inventory_turnover", "Inventory turnover", "efficiency",
        "cost_of_revenue / inventory", ("cost_of_revenue", "inventory"), "turns", "higher_is_better"),
    "receivables_turnover": MetricDef("receivables_turnover", "Receivables turnover", "efficiency",
        "revenue / accounts_receivable", ("revenue", "accounts_receivable"), "turns", "higher_is_better"),
    "dso": MetricDef("dso", "Days sales outstanding", "efficiency",
        "365 / receivables_turnover", ("revenue", "accounts_receivable"), "days", "lower_is_better"),
    "dio": MetricDef("dio", "Days inventory outstanding", "efficiency",
        "365 / inventory_turnover", ("cost_of_revenue", "inventory"), "days", "lower_is_better"),
    "dpo": MetricDef("dpo", "Days payables outstanding", "efficiency",
        "365 / (cost_of_revenue / accounts_payable)",
        ("cost_of_revenue", "accounts_payable"), "days", "higher_is_better"),
    "cash_conversion_cycle": MetricDef("cash_conversion_cycle", "Cash conversion cycle", "efficiency",
        "dso + dio - dpo",
        ("revenue", "accounts_receivable", "cost_of_revenue", "inventory", "accounts_payable"),
        "days", "lower_is_better"),
    "capex_to_revenue": MetricDef("capex_to_revenue", "Capex intensity", "efficiency",
        "capex / revenue", ("capex", "revenue"), "percent", "contextual"),
    "fcf": MetricDef("fcf", "Free cash flow", "cash_quality",
        "cfo - capex", ("cfo", "capex"), "currency", "higher_is_better"),
    "fcf_per_share": MetricDef("fcf_per_share", "FCF per share", "cash_quality",
        "(cfo - capex) / shares_diluted", ("cfo", "capex", "shares_diluted"),
        "currency", "higher_is_better"),
    "cfo_to_net_income": MetricDef("cfo_to_net_income", "Cash conversion of earnings", "cash_quality",
        "cfo / net_income", ("cfo", "net_income"), "ratio", "higher_is_better"),
    "accrual_ratio": MetricDef("accrual_ratio", "Accrual ratio", "cash_quality",
        "(net_income - cfo) / total_assets", ("net_income", "cfo", "total_assets"),
        "percent", "lower_is_better"),
    "book_value_per_share": MetricDef("book_value_per_share", "Book value per share", "per_share",
        "equity / shares_diluted", ("equity", "shares_diluted"), "currency", "higher_is_better"),
    "revenue_per_share": MetricDef("revenue_per_share", "Revenue per share", "per_share",
        "revenue / shares_diluted", ("revenue", "shares_diluted"), "currency", "higher_is_better"),
    "revenue_cagr": MetricDef("revenue_cagr", "Revenue CAGR", "growth",
        "(revenue_t / revenue_t-n) ^ (1/n) - 1", ("revenue",), "percent",
        "higher_is_better", window=3),
    "eps_cagr": MetricDef("eps_cagr", "EPS CAGR", "growth",
        "(eps_t / eps_t-n) ^ (1/n) - 1", ("eps_diluted",), "percent",
        "higher_is_better", window=3),
    "fcf_cagr": MetricDef("fcf_cagr", "FCF CAGR", "growth",
        "(fcf_t / fcf_t-n) ^ (1/n) - 1", ("cfo", "capex"), "percent",
        "higher_is_better", window=3),
    "equity_growth": MetricDef("equity_growth", "Equity growth YoY", "growth",
        "equity_t / equity_t-1 - 1", ("equity",), "percent",
        "higher_is_better", window=1),
    "share_dilution": MetricDef("share_dilution", "Share count change YoY", "growth",
        "shares_t / shares_t-1 - 1", ("shares_diluted",), "percent",
        "lower_is_better", window=1),
    "dupont_return": MetricDef("dupont_return", "DuPont return on equity", "profitability",
        "net_margin * asset_turnover * equity_multiplier",
        ("net_income", "revenue", "total_assets", "equity"), "percent", "higher_is_better"),
}

METRIC_ORDER = tuple(METRICS)


def get(metric_id: str) -> MetricDef:
    try:
        return METRICS[metric_id]
    except KeyError as exc:
        from core.errors import MetricNotFound

        raise MetricNotFound(f"unknown metric: {metric_id}") from exc


def catalog() -> list[dict]:
    return [
        {
            "metric_id": definition.metric_id,
            "label": definition.label,
            "family": definition.family,
            "formula": definition.formula,
            "line_items": list(definition.line_items),
            "unit": definition.unit,
            "direction": definition.direction,
            "window": definition.window,
            "version": definition.version,
        }
        for definition in METRICS.values()
    ]
