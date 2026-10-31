"""SQLite fact mirror owned by the fundamentals module."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

from core import citations
from core.models import FactRow, LineItemSeries, LineItemValue

from ..domain import concepts

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    cik INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    name TEXT NOT NULL,
    exchange TEXT,
    sic TEXT,
    industry TEXT,
    fiscal_year_end TEXT,
    filer_category TEXT,
    is_foreign INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    facts_synced_at REAL,
    facts_access REAL,
    fact_count INTEGER NOT NULL DEFAULT 0,
    facts_bytes_estimate INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies(ticker);

CREATE TABLE IF NOT EXISTS facts (
    fact_key TEXT PRIMARY KEY,
    cik INTEGER NOT NULL REFERENCES companies(cik) ON DELETE CASCADE,
    concept TEXT NOT NULL,
    taxonomy TEXT NOT NULL,
    label TEXT,
    unit TEXT NOT NULL,
    value TEXT,
    numeric_value REAL,
    period_type TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT NOT NULL,
    duration_days INTEGER,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    form_type TEXT,
    accession TEXT,
    filing_date TEXT,
    is_audited INTEGER,
    is_restated INTEGER,
    data_quality TEXT,
    confidence_score REAL,
    dimensions_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_facts_concept ON facts(cik, concept, period_end);
CREATE INDEX IF NOT EXISTS idx_facts_period ON facts(cik, period_end, period_type);
CREATE INDEX IF NOT EXISTS idx_facts_form ON facts(cik, form_type, filing_date);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    return conn


def _days(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days
    except ValueError:
        return None


def _split_concept(raw: str) -> tuple[str, str]:
    text = str(raw or "")
    if ":" in text:
        taxonomy, concept = text.split(":", 1)
        return taxonomy, concept
    return "us-gaap", text


def _fact_key(cik: int, concept: str, unit: str, period_type: str,
              start: Any, end: Any, accession: Any, dimensions: Any) -> str:
    payload = json.dumps(
        [cik, concept, unit, period_type, str(start or ""), str(end or ""),
         str(accession or ""), dimensions or {}],
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:10] if text else None


def sync_company(
    conn: sqlite3.Connection,
    profile,
    facts: Iterable,
    *,
    fetched_at: float,
) -> int:
    """Replace one company's facts and update its metadata row."""
    cik = int(profile.cik)
    conn.execute(
        """
        INSERT INTO companies (cik, ticker, name, exchange, sic, industry,
                               fiscal_year_end, filer_category, is_foreign,
                               updated_at, facts_synced_at, facts_access)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cik) DO UPDATE SET
            ticker=excluded.ticker, name=excluded.name, exchange=excluded.exchange,
            sic=excluded.sic, industry=excluded.industry,
            fiscal_year_end=excluded.fiscal_year_end,
            filer_category=excluded.filer_category, is_foreign=excluded.is_foreign,
            updated_at=excluded.updated_at, facts_synced_at=excluded.facts_synced_at,
            facts_access=excluded.facts_access
        """,
        (
            cik, profile.symbol, profile.name, profile.exchange, profile.sic,
            profile.industry, profile.fiscal_year_end, profile.filer_category,
            int(bool(profile.is_foreign)), fetched_at, fetched_at, fetched_at,
        ),
    )
    conn.execute("DELETE FROM facts WHERE cik = ?", (cik,))

    rows = []
    for fact in facts:
        taxonomy, concept = _split_concept(getattr(fact, "concept", ""))
        unit = str(getattr(fact, "unit", "") or "")
        start = _date(getattr(fact, "period_start", None))
        end = _date(getattr(fact, "period_end", None))
        if not concept or not end:
            continue
        period_type = str(getattr(fact, "period_type", "duration") or "duration")
        accession = getattr(fact, "accession", None)
        dimensions = getattr(fact, "dimensions", None)
        numeric = getattr(fact, "numeric_value", None)
        if numeric is None:
            try:
                numeric = float(getattr(fact, "value"))
            except (TypeError, ValueError):
                numeric = None
        rows.append(
            (
                _fact_key(cik, concept, unit, period_type, start, end, accession, dimensions),
                cik, concept, taxonomy, str(getattr(fact, "label", "") or ""),
                unit, str(getattr(fact, "value", "") or ""), numeric,
                period_type, start, end, _days(start, end),
                getattr(fact, "fiscal_year", None),
                None if getattr(fact, "fiscal_period", None) is None else str(fact.fiscal_period),
                None if getattr(fact, "form_type", None) is None else str(fact.form_type),
                None if accession is None else str(accession),
                _date(getattr(fact, "filing_date", None)),
                None if getattr(fact, "is_audited", None) is None else int(bool(fact.is_audited)),
                None if getattr(fact, "is_restated", None) is None else int(bool(fact.is_restated)),
                None if getattr(fact, "data_quality", None) is None else str(fact.data_quality),
                None if getattr(fact, "confidence_score", None) is None else float(fact.confidence_score),
                json.dumps(dimensions, default=str) if dimensions else None,
            )
        )
    conn.executemany(
        """
        INSERT OR REPLACE INTO facts
        (fact_key, cik, concept, taxonomy, label, unit, value, numeric_value,
         period_type, period_start, period_end, duration_days, fiscal_year,
         fiscal_period, form_type, accession, filing_date, is_audited,
         is_restated, data_quality, confidence_score, dimensions_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )
    conn.execute(
        "UPDATE companies SET fact_count = ?, facts_bytes_estimate = ?, facts_synced_at = ? WHERE cik = ?",
        (len(rows), len(rows) * 200, fetched_at, cik),
    )
    conn.commit()
    return len(rows)


def touch(conn: sqlite3.Connection, cik: int, at: float) -> None:
    conn.execute("UPDATE companies SET facts_access = ? WHERE cik = ?", (at, cik))
    conn.commit()


def facts_version(conn: sqlite3.Connection, cik: int) -> str:
    row = conn.execute(
        "SELECT facts_synced_at, fact_count FROM companies WHERE cik = ?", (cik,)
    ).fetchone()
    if row is None:
        return "0:0"
    return f"{row['facts_synced_at'] or 0}:{row['fact_count']}"


def _annual_clause(period_type: str) -> str:
    if period_type == "instant":
        return "period_type = 'instant'"
    return "period_type = 'duration' AND duration_days BETWEEN 350 AND 380"


def _row_to_fact(row: sqlite3.Row) -> FactRow:
    return FactRow(
        concept=row["concept"],
        taxonomy=row["taxonomy"],
        label=row["label"] or row["concept"],
        unit=row["unit"],
        value=row["value"],
        numeric_value=row["numeric_value"],
        period_type=row["period_type"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        duration_days=row["duration_days"],
        fiscal_year=row["fiscal_year"],
        fiscal_period=row["fiscal_period"],
        form_type=row["form_type"],
        accession=row["accession"],
        filing_date=row["filing_date"],
        period_label=_period_label(row),
    )


def _period_label(row: sqlite3.Row) -> str:
    end = row["period_end"] or ""
    if row["period_type"] == "instant":
        return f"As of {end}"
    duration = row["duration_days"]
    if duration is not None and duration < 300:
        return f"Period ending {end}"
    return f"FY ending {end}"


def query(
    conn: sqlite3.Connection,
    cik: int,
    *,
    concepts_in: Sequence[str] | None = None,
    search: str | None = None,
    forms: Sequence[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    unit: str | None = None,
    annual_only: bool = False,
    dedupe: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[FactRow], int]:
    clauses = ["cik = ?"]
    params: list[Any] = [cik]
    if concepts_in:
        placeholders = ",".join("?" for _ in concepts_in)
        clauses.append(f"LOWER(concept) IN ({placeholders})")
        params.extend([item.lower() for item in concepts_in])
    if search:
        clauses.append("(LOWER(concept) LIKE ? OR LOWER(label) LIKE ?)")
        needle = f"%{search.lower()}%"
        params.extend([needle, needle])
    if forms:
        placeholders = ",".join("?" for _ in forms)
        clauses.append(f"UPPER(form_type) IN ({placeholders})")
        params.extend([item.upper() for item in forms])
    if start:
        clauses.append("period_end >= ?")
        params.append(start[:10])
    if end:
        clauses.append("period_end <= ?")
        params.append(end[:10])
    if unit:
        clauses.append("unit = ?")
        params.append(unit)
    if annual_only:
        clauses.append("period_type = 'duration' AND duration_days BETWEEN 350 AND 380")

    where = " AND ".join(clauses)
    if dedupe:
        base = f"""
            SELECT * FROM (
              SELECT f.*, ROW_NUMBER() OVER (
                PARTITION BY concept, unit, period_end
                ORDER BY filing_date DESC, (form_type = '10-K') DESC
              ) AS rn
              FROM facts f WHERE {where}
            ) WHERE rn = 1
        """
    else:
        base = f"SELECT * FROM facts WHERE {where}"

    total = conn.execute(f"SELECT COUNT(*) FROM ({base})", params).fetchone()[0]
    rows = conn.execute(
        f"{base} ORDER BY period_end DESC, concept ASC LIMIT ? OFFSET ?",
        [*params, max(1, int(limit)), max(0, int(offset))],
    ).fetchall()
    return [_row_to_fact(row) for row in rows], int(total)


def annual_series(
    conn: sqlite3.Connection,
    cik: int,
    concept: str,
    *,
    unit: str | None = None,
    limit: int = 20,
    start: str | None = None,
    end: str | None = None,
    period_type: str = "duration",
    period_ends: Sequence[str] | None = None,
    fiscal_periods: Sequence[str] | None = None,
) -> list[FactRow]:
    clauses = ["cik = ?", "LOWER(concept) = ?", _annual_clause(period_type)]
    params: list[Any] = [cik, concept.lower()]
    if unit:
        clauses.append("unit = ?")
        params.append(unit)
    if start:
        clauses.append("period_end >= ?")
        params.append(start[:10])
    if end:
        clauses.append("period_end <= ?")
        params.append(end[:10])
    if period_ends:
        placeholders = ",".join("?" for _ in period_ends)
        clauses.append(f"period_end IN ({placeholders})")
        params.extend(period_ends)
    if fiscal_periods:
        placeholders = ",".join("?" for _ in fiscal_periods)
        clauses.append(f"UPPER(fiscal_period) IN ({placeholders})")
        params.extend([item.upper() for item in fiscal_periods])
    sql = f"""
        SELECT * FROM (
          SELECT f.*, ROW_NUMBER() OVER (
            PARTITION BY period_end
            ORDER BY filing_date DESC, (form_type = '10-K') DESC
          ) AS rn
          FROM facts f WHERE {' AND '.join(clauses)}
        ) WHERE rn = 1
        ORDER BY period_end DESC LIMIT ?
    """
    rows = conn.execute(sql, [*params, max(1, int(limit))]).fetchall()
    return [_row_to_fact(row) for row in rows]


def _canonical_periods(conn: sqlite3.Connection, cik: int, limit: int) -> list[str]:
    for concept in (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "NetIncomeLoss",
        "OperatingIncomeLoss",
        "Assets",
    ):
        series = annual_series(
            conn, cik, concept,
            period_type="instant" if concept == "Assets" else "duration",
            limit=limit,
            fiscal_periods=["FY"] if concept == "Assets" else None,
        )
        if series:
            return [row.period_end for row in series]
    return []


def _fact_artifact(
    cik: int,
    *,
    accession: Any,
    concept: Any,
    taxonomy: Any = None,
    unit: Any = None,
    period_end: Any = None,
) -> dict:
    """Return the cached companyfacts locator backing one XBRL citation."""
    artifact = {
        "module": "fundamentals",
        "kind": "facts-json",
        "cik": int(cik),
        "accession": accession,
        "concept": concept,
        "format": "json",
        "status": "cached",
    }
    for key, value in (
        ("taxonomy", taxonomy),
        ("unit", unit),
        ("period_end", period_end),
    ):
        if value:
            artifact[key] = value
    return artifact


def _cite(cik: int, row: FactRow, label: str) -> dict:
    artifact = _fact_artifact(
        cik,
        accession=row.accession,
        concept=row.concept,
        taxonomy=row.taxonomy,
        unit=row.unit,
        period_end=row.period_end,
    )
    return citations.cite(
        "sec-xbrl",
        label,
        cik=cik,
        accession=row.accession,
        form=row.form_type,
        filed=row.filing_date,
        period=row.period_end,
        artifact=artifact,
    )


def _series_for_item(
    conn: sqlite3.Connection,
    cik: int,
    item: concepts.LineItemDef,
    limit: int,
    allowed_periods: set[str] | None = None,
) -> dict[str, LineItemValue]:
    for concept in item.concepts:
        rows = annual_series(
            conn, cik, concept, unit=item.unit,
            period_type=item.period_type, limit=limit,
            period_ends=sorted(allowed_periods) if allowed_periods else None,
        )
        if not rows:
            continue
        result: dict[str, LineItemValue] = {}
        for row in rows:
            numeric = row.numeric_value
            if numeric is None:
                continue
            result[row.period_end] = LineItemValue(
                line_item=item.name,
                label=item.label,
                unit=item.unit,
                period_end=row.period_end,
                value=float(numeric),
                concept=row.concept,
                citation=_cite(cik, row, f"{item.label}, {row.period_end}"),
            )
        if result:
            return result
    if item.derived_from:
        parts = [
            _series_for_item(
                conn, cik, concepts.get(name), limit, allowed_periods
            )
            for name in item.derived_from
        ]
        periods = set.intersection(*(set(part) for part in parts)) if parts else set()
        result = {}
        for period_end in periods:
            values = [part[period_end].value for part in parts if part[period_end].value is not None]
            if len(values) != len(parts):
                continue
            total = float(sum(values))
            anchor = parts[0][period_end]
            result[period_end] = LineItemValue(
                line_item=item.name,
                label=item.label,
                unit=item.unit,
                period_end=period_end,
                value=total,
                concept=item.name,
                citation=anchor.citation,
            )
        return result
    return {}


def _average(values: dict[str, LineItemValue], periods: list[str]) -> dict[str, LineItemValue]:
    """Average instant balances with the immediately preceding fiscal period."""
    ordered = sorted(values, reverse=True)
    averaged: dict[str, LineItemValue] = {}
    for index, period in enumerate(ordered):
        current = values[period]
        if index + 1 < len(ordered):
            previous = values[ordered[index + 1]]
            if previous.value is not None and current.value is not None:
                averaged[period] = LineItemValue(
                    line_item=current.line_item,
                    label=current.label,
                    unit=current.unit,
                    period_end=period,
                    value=(current.value + previous.value) / 2.0,
                    concept=current.concept,
                    citation=current.citation,
                )
                continue
        averaged[period] = current
    return averaged


def line_items(
    conn: sqlite3.Connection,
    cik: int,
    symbol: str,
    currency: str,
    items: Sequence[str],
    *,
    periods: int = 5,
    balance_basis: str = "average",
) -> LineItemSeries:
    limit = max(1, min(int(periods), 20)) + 1
    canonical = _canonical_periods(conn, cik, limit)
    if not canonical:
        canonical = []
    selected = canonical[: max(1, min(int(periods), 20))]

    series: dict[str, tuple[LineItemValue, ...]] = {}
    allowed = set(canonical)
    for name in items:
        definition = concepts.get(name)
        values = _series_for_item(conn, cik, definition, limit, allowed)
        if definition.period_type == "instant" and balance_basis == "average":
            values = _average(values, selected)
        series[name] = tuple(
            values[period] for period in selected if period in values
        )

    return LineItemSeries(
        symbol=symbol.upper(),
        cik=cik,
        currency=currency,
        periods=tuple(selected),
        items=series,
        facts_version=facts_version(conn, cik),
    )


def find_fact(
    conn: sqlite3.Connection,
    cik: int,
    concept: str,
    period_end: str,
    value: float | None,
) -> sqlite3.Row | None:
    rows = conn.execute(
        """
        SELECT * FROM facts
        WHERE cik = ? AND LOWER(concept) = ? AND period_end = ?
          AND period_type IN ('duration','instant')
        ORDER BY (form_type = '10-K') DESC, filing_date ASC
        """,
        (cik, concept.lower(), period_end),
    ).fetchall()
    if not rows:
        return None
    if value is None:
        return rows[0]
    tolerance = max(1.0, abs(float(value)) * 5e-7)
    for row in rows:
        if row["numeric_value"] is not None and abs(row["numeric_value"] - float(value)) <= tolerance:
            return row
    return rows[0]


def provenance_for(
    conn: sqlite3.Connection, cik: int, concept: str, period_end: str, value: float | None
) -> dict | None:
    row = find_fact(conn, cik, concept, period_end, value)
    if row is None:
        return None
    artifact = _fact_artifact(
        cik,
        accession=row["accession"],
        concept=row["concept"],
        taxonomy=row["taxonomy"],
        unit=row["unit"],
        period_end=row["period_end"],
    )
    # The fact is served from the cache; evidence is addressed by citation_id.
    # ``url`` stays present but None for backward compatibility with this shape.
    return {
        "accession": row["accession"],
        "form": row["form_type"],
        "filed": row["filing_date"],
        "period_end": row["period_end"],
        "url": None,
        "artifact": artifact,
        "key": citations.cite(
            "sec-xbrl", concept, cik=cik, accession=row["accession"],
            form=row["form_type"], filed=row["filing_date"], period=row["period_end"],
            artifact=artifact,
        )["key"],
    }


def dump_accession(
    conn: sqlite3.Connection,
    cik: int,
    accession: str,
    *,
    concepts: Sequence[str] | None = None,
    unit: str | None = None,
    limit: int = 500000,
) -> list[dict]:
    """Return raw fact rows for one filing accession, concept-ordered.

    Read-only: the caller decides how to render the rows (JSON, TSV, XLSX).
    """
    clauses = ["cik = ?", "accession = ?"]
    params: list[Any] = [int(cik), str(accession)]
    if concepts:
        placeholders = ",".join("?" for _ in concepts)
        clauses.append(f"LOWER(concept) IN ({placeholders})")
        params.extend([str(item).lower() for item in concepts])
    if unit:
        clauses.append("unit = ?")
        params.append(unit)
    sql = f"""
        SELECT concept, taxonomy, label, unit, value, period_start, period_end,
               fiscal_year, fiscal_period, form_type AS form, filing_date AS filed
        FROM facts
        WHERE {' AND '.join(clauses)}
        ORDER BY concept ASC, period_end ASC
        LIMIT ?
    """
    rows = conn.execute(sql, [*params, max(1, int(limit))]).fetchall()
    return [dict(row) for row in rows]


def entity_name(conn: sqlite3.Connection, cik: int) -> str:
    """Return the issuer name recorded for ``cik`` (``""`` when unknown)."""
    row = conn.execute(
        "SELECT name FROM companies WHERE cik = ?", (int(cik),)
    ).fetchone()
    return str(row["name"] or "") if row is not None else ""


def latest_fact_accession(conn: sqlite3.Connection, cik: int) -> str | None:
    """Return the newest 10-K accession with facts, else the newest accession."""
    for clause in ("AND UPPER(form_type) = '10-K'", ""):
        row = conn.execute(
            f"""
            SELECT accession FROM facts
            WHERE cik = ? AND accession IS NOT NULL AND accession <> '' {clause}
            ORDER BY COALESCE(filing_date, '') DESC, period_end DESC
            LIMIT 1
            """,
            (int(cik),),
        ).fetchone()
        if row is not None:
            return str(row["accession"])
    return None


def evict_lru(conn: sqlite3.Connection, max_companies: int, max_bytes: int) -> int:
    rows = conn.execute(
        "SELECT cik, facts_bytes_estimate FROM companies ORDER BY facts_access ASC, updated_at ASC"
    ).fetchall()
    total_bytes = sum(int(row["facts_bytes_estimate"] or 0) for row in rows)
    count = len(rows)
    deleted = 0
    for row in rows:
        if count <= max_companies and total_bytes <= max_bytes:
            break
        cik = int(row["cik"])
        conn.execute("DELETE FROM facts WHERE cik = ?", (cik,))
        conn.execute("DELETE FROM companies WHERE cik = ?", (cik,))
        total_bytes -= int(row["facts_bytes_estimate"] or 0)
        count -= 1
        deleted += 1
    conn.commit()
    return deleted
