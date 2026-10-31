"""Canonical line-item vocabulary owned by the fundamentals module.

Analysis asks for line-item names, never XBRL concepts. Each item carries an
ordered fallback chain because issuers tag the same economic line differently.
"""

from __future__ import annotations

from dataclasses import dataclass

VOCABULARY_VERSION = 1


@dataclass(frozen=True)
class LineItemDef:
    name: str
    label: str
    concepts: tuple[str, ...]
    unit: str
    period_type: str
    derived_from: tuple[str, ...] = ()


LINE_ITEMS: dict[str, LineItemDef] = {
    # -- income statement -------------------------------------------------
    "revenue": LineItemDef(
        "revenue",
        "Revenue",
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
        "USD",
        "duration",
    ),
    "cost_of_revenue": LineItemDef(
        "cost_of_revenue",
        "Cost of revenue",
        ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices"),
        "USD",
        "duration",
    ),
    "gross_profit": LineItemDef("gross_profit", "Gross profit", ("GrossProfit",), "USD", "duration"),
    "operating_expenses": LineItemDef(
        "operating_expenses",
        "Operating expenses",
        ("OperatingExpenses", "CostsAndExpenses"),
        "USD",
        "duration",
    ),
    "operating_income": LineItemDef(
        "operating_income", "Operating income", ("OperatingIncomeLoss",), "USD", "duration"
    ),
    "da": LineItemDef(
        "da",
        "Depreciation and amortization",
        (
            "DepreciationDepletionAndAmortization",
            "DepreciationAmortizationAndAccretionNet",
            "DepreciationAndAmortization",
            "Depreciation",
        ),
        "USD",
        "duration",
    ),
    "interest_expense": LineItemDef(
        "interest_expense",
        "Interest expense",
        ("InterestExpenseNonoperating", "InterestExpenseDebt", "InterestExpense"),
        "USD",
        "duration",
    ),
    "pretax_income": LineItemDef(
        "pretax_income",
        "Income before income taxes",
        (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
        ),
        "USD",
        "duration",
    ),
    "income_tax": LineItemDef(
        "income_tax", "Income tax expense", ("IncomeTaxExpenseBenefit",), "USD", "duration"
    ),
    "net_income": LineItemDef(
        "net_income", "Net income", ("NetIncomeLoss", "ProfitLoss"), "USD", "duration"
    ),
    "eps_basic": LineItemDef(
        "eps_basic", "EPS basic", ("EarningsPerShareBasic",), "USD/shares", "duration"
    ),
    "eps_diluted": LineItemDef(
        "eps_diluted", "EPS diluted", ("EarningsPerShareDiluted",), "USD/shares", "duration"
    ),
    "shares_basic": LineItemDef(
        "shares_basic",
        "Weighted-average basic shares",
        ("WeightedAverageNumberOfSharesOutstandingBasic",),
        "shares",
        "duration",
    ),
    "shares_diluted": LineItemDef(
        "shares_diluted",
        "Weighted-average diluted shares",
        ("WeightedAverageNumberOfDilutedSharesOutstanding",),
        "shares",
        "duration",
    ),
    "sbc": LineItemDef("sbc", "Share-based compensation", ("ShareBasedCompensation",), "USD", "duration"),
    # -- balance sheet ----------------------------------------------------
    "cash": LineItemDef(
        "cash",
        "Cash and cash equivalents",
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
        "USD",
        "instant",
    ),
    "short_term_investments": LineItemDef(
        "short_term_investments",
        "Short-term investments",
        ("ShortTermInvestments", "MarketableSecuritiesCurrent"),
        "USD",
        "instant",
    ),
    "accounts_receivable": LineItemDef(
        "accounts_receivable",
        "Accounts receivable",
        ("AccountsReceivableNetCurrent", "ReceivablesNetCurrent"),
        "USD",
        "instant",
    ),
    "inventory": LineItemDef("inventory", "Inventory", ("InventoryNet",), "USD", "instant"),
    "current_assets": LineItemDef(
        "current_assets", "Current assets", ("AssetsCurrent",), "USD", "instant"
    ),
    "total_assets": LineItemDef("total_assets", "Total assets", ("Assets",), "USD", "instant"),
    "ppe_net": LineItemDef(
        "ppe_net", "Property, plant and equipment", ("PropertyPlantAndEquipmentNet",), "USD", "instant"
    ),
    "goodwill": LineItemDef("goodwill", "Goodwill", ("Goodwill",), "USD", "instant"),
    "accounts_payable": LineItemDef(
        "accounts_payable",
        "Accounts payable",
        ("AccountsPayableCurrent", "AccountsPayableAndAccruedLiabilitiesCurrent", "AccountsPayable"),
        "USD",
        "instant",
    ),
    "current_liabilities": LineItemDef(
        "current_liabilities", "Current liabilities", ("LiabilitiesCurrent",), "USD", "instant"
    ),
    "total_liabilities": LineItemDef(
        "total_liabilities", "Total liabilities", ("Liabilities",), "USD", "instant"
    ),
    "short_term_debt": LineItemDef(
        "short_term_debt",
        "Short-term debt",
        ("ShortTermBorrowings", "LongTermDebtCurrent", "DebtCurrent"),
        "USD",
        "instant",
    ),
    "long_term_debt": LineItemDef(
        "long_term_debt",
        "Long-term debt",
        ("LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations", "LongTermDebt"),
        "USD",
        "instant",
    ),
    "total_debt": LineItemDef(
        "total_debt",
        "Total debt",
        ("LongTermDebt", "DebtInstrumentCarryingAmount", "DebtLongtermAndShorttermCombinedAmount"),
        "USD",
        "instant",
        derived_from=("short_term_debt", "long_term_debt"),
    ),
    "equity": LineItemDef(
        "equity",
        "Stockholders' equity",
        (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "USD",
        "instant",
    ),
    "retained_earnings": LineItemDef(
        "retained_earnings",
        "Retained earnings",
        ("RetainedEarningsAccumulatedDeficit",),
        "USD",
        "instant",
    ),
    # -- cash flow --------------------------------------------------------
    "cfo": LineItemDef(
        "cfo",
        "Operating cash flow",
        ("NetCashProvidedByUsedInOperatingActivities",),
        "USD",
        "duration",
    ),
    "capex": LineItemDef(
        "capex",
        "Capital expenditure",
        ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"),
        "USD",
        "duration",
    ),
    "cfi": LineItemDef(
        "cfi",
        "Investing cash flow",
        ("NetCashProvidedByUsedInInvestingActivities",),
        "USD",
        "duration",
    ),
    "cff": LineItemDef(
        "cff",
        "Financing cash flow",
        ("NetCashProvidedByUsedInFinancingActivities",),
        "USD",
        "duration",
    ),
    "dividends_paid": LineItemDef(
        "dividends_paid",
        "Dividends paid",
        ("PaymentsOfDividendsCommonStock", "PaymentsOfDividends"),
        "USD",
        "duration",
    ),
}

for _item in LINE_ITEMS.values():
    for _derived in _item.derived_from:
        if _derived not in LINE_ITEMS:
            raise RuntimeError(f"line item {_item.name} derives from unknown {_derived}")


def vocabulary() -> dict[str, tuple[str, ...]]:
    return {name: definition.concepts for name, definition in LINE_ITEMS.items()}


def get(name: str) -> LineItemDef:
    try:
        return LINE_ITEMS[name]
    except KeyError as exc:
        raise KeyError(f"unknown line item: {name}") from exc
