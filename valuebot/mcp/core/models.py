"""Frozen data transfer objects shared across module boundaries.

No module imports another module's internals; cross-module calls exchange these
objects or plain primitives only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CompanyRef",
    "CompanyProfile",
    "FilingRef",
    "FilingPage",
    "FactRow",
    "FactPage",
    "FactSeries",
    "LineItemValue",
    "LineItemSeries",
    "StatementRow",
    "NormalizedStatement",
    "MetricDef",
    "MetricResult",
    "MetricPage",
    "DcfAssumption",
    "DcfForecastRow",
    "DcfResult",
    "Section",
    "SectionsPage",
    "SectionSlice",
    "TableGrid",
    "TableSlice",
    "SearchHit",
    "SearchPage",
    "VaultDocument",
]


@dataclass(frozen=True)
class CompanyRef:
    symbol: str
    cik: int
    name: str


@dataclass(frozen=True)
class CompanyProfile:
    symbol: str
    cik: int
    name: str
    tickers: tuple[str, ...] = ()
    exchange: str = ""
    sic: str = ""
    industry: str = ""
    fiscal_year_end: str = ""
    filer_category: str = ""
    is_foreign: bool = False

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "cik": self.cik,
            "name": self.name,
            "tickers": list(self.tickers),
            "exchange": self.exchange,
            "sic": self.sic,
            "industry": self.industry,
            "fiscal_year_end": self.fiscal_year_end,
            "filer_category": self.filer_category,
            "is_foreign": self.is_foreign,
        }


@dataclass(frozen=True)
class FilingRef:
    symbol: str
    cik: int
    accession: str
    form: str
    filed: str
    period_of_report: str = ""
    primary_document: str = ""
    source_url: str = ""

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "cik": self.cik,
            "accession": self.accession,
            "form": self.form,
            "filed": self.filed,
            "period_of_report": self.period_of_report,
            "primary_document": self.primary_document,
            "source_url": self.source_url,
        }


@dataclass(frozen=True)
class FilingPage:
    symbol: str
    cik: int
    rows: tuple[FilingRef, ...] = ()
    total: int = 0
    offset: int = 0
    next_offset: int | None = None


@dataclass(frozen=True)
class FactRow:
    concept: str
    taxonomy: str
    label: str
    unit: str
    value: Any
    numeric_value: float | None
    period_type: str
    period_start: str | None
    period_end: str
    duration_days: int | None
    fiscal_year: int | None
    fiscal_period: str | None
    form_type: str | None
    accession: str | None
    filing_date: str | None
    period_label: str | None = None


@dataclass(frozen=True)
class FactPage:
    symbol: str
    cik: int
    rows: tuple[FactRow, ...] = ()
    total: int = 0
    offset: int = 0
    next_offset: int | None = None
    facets: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FactSeries:
    symbol: str
    cik: int
    concept: str
    unit: str
    points: tuple[FactRow, ...] = ()


@dataclass(frozen=True)
class LineItemValue:
    line_item: str
    label: str
    unit: str
    period_end: str
    value: float | None
    concept: str
    citation: dict | None = None


@dataclass(frozen=True)
class LineItemSeries:
    symbol: str
    cik: int
    currency: str
    periods: tuple[str, ...]
    items: dict[str, tuple[LineItemValue, ...]]
    facts_version: str = ""

    def period_values(self, line_item: str) -> dict[str, LineItemValue]:
        return {value.period_end: value for value in self.items.get(line_item, ())}


@dataclass(frozen=True)
class StatementRow:
    concept: str
    label: str
    depth: int
    parent: str | None
    is_total: bool
    unit: str
    values: dict[str, float | None]


@dataclass(frozen=True)
class NormalizedStatement:
    symbol: str
    cik: int
    statement: str
    label: str
    basis: str
    unit: str
    periods: tuple[str, ...]
    period_ends: dict[str, str]
    rows: tuple[StatementRow, ...]
    citations: dict[str, dict] = field(default_factory=dict)
    currency: str = "USD"


@dataclass(frozen=True)
class MetricDef:
    metric_id: str
    label: str
    family: str
    formula: str
    line_items: tuple[str, ...]
    unit: str
    direction: str = "contextual"
    window: int = 0
    version: int = 1


@dataclass(frozen=True)
class MetricResult:
    metric_id: str
    label: str
    family: str
    period_end: str
    value: float | None
    display: str
    unit: str
    quality: str
    formula: str
    formula_version: int
    inputs: tuple[dict, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class MetricPage:
    symbol: str
    cik: int
    periods: tuple[str, ...]
    results: tuple[MetricResult, ...]
    balance_basis: str = "average"


@dataclass(frozen=True)
class DcfAssumption:
    name: str
    value: Any
    display: str
    unit: str
    source: str
    derivation: str = ""
    periods_used: tuple[str, ...] = ()
    assumption_quality: str = "company_history"
    citation: dict | None = None


@dataclass(frozen=True)
class DcfForecastRow:
    year: int
    period_end: str
    revenue: float
    ebit: float
    taxes: float
    nopat: float
    da: float
    capex: float
    delta_nwc: float
    fcff: float
    discount_factor: float
    pv: float


@dataclass(frozen=True)
class DcfResult:
    symbol: str
    cik: int
    currency: str
    base_period_end: str
    forecast_years: int
    assumptions: tuple[DcfAssumption, ...]
    assumptions_complete: bool
    forecast: tuple[DcfForecastRow, ...]
    terminal: dict
    valuation: dict
    sensitivity: dict
    warnings: tuple[str, ...] = ()
    model_version: int = 1


@dataclass(frozen=True)
class Section:
    id: str
    parent_id: str | None
    kind: str
    title: str
    start: int
    end: int
    char_count: int
    section_type: str | None = None
    level: int = 0
    table_ids: tuple[str, ...] = ()
    note_number: int | None = None


@dataclass(frozen=True)
class SectionsPage:
    symbol: str | None
    cik: int | None
    filing: FilingRef | None
    profile: str
    sections: tuple[Section, ...]
    coverage: dict
    warnings: tuple[str, ...] = ()
    table_count: int = 0


@dataclass(frozen=True)
class SectionSlice:
    section: Section
    text: str
    offset: int
    next_offset: int | None
    tables: tuple[dict, ...] = ()


@dataclass(frozen=True)
class TableGrid:
    id: str
    section_id: str | None
    index: int
    caption: str
    header_rows: int
    grid: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class TableSlice:
    table: TableGrid
    markdown: str
    columns: tuple[str, ...]
    row_offset: int
    next_offset: int | None
    total_rows: int
    truncated: bool = False


@dataclass(frozen=True)
class SearchHit:
    kind: str
    section_id: str
    title: str
    snippet: str
    table_id: str | None = None
    element_index: int | None = None


@dataclass(frozen=True)
class SearchPage:
    query: str
    hits: tuple[SearchHit, ...]
    total: int


@dataclass(frozen=True)
class VaultDocument:
    symbol: str
    front_matter: dict
    body: str
    offset: int
    next_offset: int | None
    attachments: tuple[str, ...] = ()
