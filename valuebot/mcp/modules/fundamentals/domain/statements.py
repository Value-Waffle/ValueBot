"""Statement normalization and period-level provenance."""

from __future__ import annotations

import re
from typing import Any, Iterable

from core import citations
from core.models import NormalizedStatement, StatementRow

from . import concepts

LABELS = {
    "income": "Income Statement",
    "balance": "Balance Sheet",
    "cashflow": "Cash Flow Statement",
}

ANCHORS = {
    "income": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "NetIncomeLoss",
        "OperatingIncomeLoss",
    ),
    "balance": ("Assets", "LiabilitiesAndStockholdersEquity", "StockholdersEquity"),
    "cashflow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "CashAndCashEquivalentsPeriodIncreaseDecrease",
    ),
}

_UNIT_RULES = (
    (re.compile(r"^EarningsPerShare", re.I), "USD/shares"),
    (re.compile(r"SharesOutstanding|NumberOfShares", re.I), "shares"),
)


def infer_unit(concept: str) -> str:
    for pattern, unit in _UNIT_RULES:
        if pattern.search(concept or ""):
            return unit
    return "USD"


def _label_regex() -> re.Pattern[str]:
    return re.compile(r"^FY\s*(\d{4})$", re.I)


def normalize_company(
    stmt: Any,
    *,
    symbol: str,
    cik: int,
    statement: str,
    currency: str = "USD",
) -> NormalizedStatement:
    periods = tuple(str(item) for item in (getattr(stmt, "periods", None) or ()))
    raw_rows = list(stmt.to_flat_list())
    rows: list[StatementRow] = []
    for item in raw_rows:
        concept = str(item.get("concept") or "")
        values = {period: item.get(period) for period in periods}
        numeric = {}
        for period, value in values.items():
            try:
                numeric[period] = None if value is None else float(value)
            except (TypeError, ValueError):
                numeric[period] = None
        rows.append(
            StatementRow(
                concept=concept,
                label=str(item.get("label") or concept),
                depth=int(item.get("depth") or 0),
                parent=item.get("parent"),
                is_total=bool(item.get("is_total")),
                unit=infer_unit(concept),
                values=numeric,
            )
        )
    return NormalizedStatement(
        symbol=symbol.upper(),
        cik=cik,
        statement=statement,
        label=LABELS.get(statement, statement),
        basis="company",
        unit="USD",
        periods=periods,
        period_ends={},
        rows=tuple(rows),
        citations={},
        currency=currency,
    )


def resolve_period_ends(conn, statement: str, cik: int, normalized: NormalizedStatement):
    """Resolve each FY label to an actual period end using anchor facts."""
    anchors = ANCHORS.get(statement, ())
    found: dict[str, str] = {}
    anchor_rows: dict[str, dict] = {}

    row_index = {row.concept: row for row in normalized.rows}
    for label in normalized.periods:
        votes: dict[str, int] = {}
        for concept in anchors:
            row = row_index.get(concept)
            if row is None or row.values.get(label) is None:
                continue
            target = row.values[label]
            candidates = conn.execute(
                """
                SELECT concept, period_end, numeric_value, accession, form_type, filing_date
                FROM facts
                WHERE cik = ? AND LOWER(concept) = ?
                  AND period_type IN ('duration','instant')
                  AND (duration_days IS NULL OR duration_days BETWEEN 350 AND 380)
                ORDER BY filing_date DESC
                """,
                (cik, concept.lower()),
            ).fetchall()
            tolerance = max(1.0, abs(float(target)) * 5e-7)
            for candidate in candidates:
                if candidate["numeric_value"] is None:
                    continue
                if abs(float(candidate["numeric_value"]) - float(target)) <= tolerance:
                    period_end = candidate["period_end"]
                    votes[period_end] = votes.get(period_end, 0) + 1
                    anchor_rows.setdefault(period_end, dict(candidate))
                    break
        if votes:
            found[label] = max(votes, key=lambda key: votes[key])

    citations_map: dict[str, dict] = {}
    for label, period_end in found.items():
        anchor = anchor_rows.get(period_end, {})
        artifact = {
            "module": "fundamentals",
            "kind": "facts-json",
            "cik": int(cik),
            "accession": anchor.get("accession"),
            "format": "json",
            "period_end": period_end,
            "status": "cached",
        }
        if anchor.get("concept"):
            artifact["concept"] = anchor["concept"]
        citations_map[label] = citations.cite(
            "sec-statement",
            f"{normalized.symbol} {normalized.statement}, {label}",
            cik=cik,
            accession=anchor.get("accession"),
            form=anchor.get("form_type"),
            filed=anchor.get("filing_date"),
            period=period_end,
            artifact=artifact,
        )

    return NormalizedStatement(
        symbol=normalized.symbol,
        cik=normalized.cik,
        statement=normalized.statement,
        label=normalized.label,
        basis=normalized.basis,
        unit=normalized.unit,
        periods=normalized.periods,
        period_ends=found,
        rows=normalized.rows,
        citations=citations_map,
        currency=normalized.currency,
    )


_PERIOD_COLUMN = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def normalize_filing(
    stmt: Any,
    *,
    symbol: str,
    cik: int,
    statement: str,
    accession: str,
    form: str,
    filed: str,
    currency: str = "USD",
) -> NormalizedStatement:
    frame = stmt.to_dataframe(standard=True)
    columns = [str(column) for column in frame.columns]
    period_columns = [column for column in columns if _PERIOD_COLUMN.match(column)]
    period_columns.sort(reverse=True)
    labels = {column: _PERIOD_COLUMN.match(column).group(1) for column in period_columns}

    rows: list[StatementRow] = []
    for concept, record in frame.iterrows():
        concept_text = str(concept)
        values: dict[str, float | None] = {}
        for column in period_columns:
            raw = record.get(column)
            try:
                values[labels[column]] = None if raw is None or str(raw) == "nan" else float(raw)
            except (TypeError, ValueError):
                values[labels[column]] = None
        rows.append(
            StatementRow(
                concept=concept_text,
                label=str(record.get("label") or concept_text),
                depth=int(record.get("level") or 0),
                parent=record.get("parent_concept"),
                is_total=bool(record.get("abstract") is False),
                unit=infer_unit(concept_text),
                values=values,
            )
        )

    periods = tuple(labels[column] for column in period_columns)
    period_end = periods[0] if periods else None
    artifact = {
        "module": "fundamentals",
        "kind": "facts-json",
        "cik": int(cik),
        "accession": accession,
        "format": "json",
        "period_end": period_end,
        "status": "cached",
    }
    citation = citations.cite(
        "sec-statement",
        f"{symbol.upper()} {form} {statement}",
        cik=cik,
        accession=accession,
        form=form,
        filed=filed,
        period=period_end,
        artifact=artifact,
    )
    return NormalizedStatement(
        symbol=symbol.upper(),
        cik=cik,
        statement=statement,
        label=LABELS.get(statement, statement),
        basis="filing",
        unit="USD",
        periods=periods,
        period_ends={label: label for label in periods},
        rows=tuple(rows),
        citations={label: citation for label in periods},
        currency=currency,
    )
