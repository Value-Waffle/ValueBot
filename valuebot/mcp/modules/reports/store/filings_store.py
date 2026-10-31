"""Filing index owned by the reports module."""

from __future__ import annotations

import sqlite3
import time

from core.models import FilingRef

TTL = 12 * 60 * 60


def sync_issuer(conn: sqlite3.Connection, symbol: str, cik: int, name: str,
                refs: list[FilingRef], *, fetched_at: float) -> int:
    conn.execute(
        """
        INSERT INTO issuers (cik, symbol, name, synced_at) VALUES (?, ?, ?, ?)
        ON CONFLICT(cik) DO UPDATE SET symbol=excluded.symbol, name=excluded.name,
            synced_at=excluded.synced_at
        """,
        (int(cik), symbol.upper(), name, fetched_at),
    )
    conn.execute("DELETE FROM filings_index WHERE cik = ?", (int(cik),))
    conn.executemany(
        """
        INSERT OR REPLACE INTO filings_index
        (accession, cik, form, filed, period_of_report, primary_document, source_url, synced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                ref.accession, ref.cik, ref.form, ref.filed, ref.period_of_report,
                ref.primary_document, ref.source_url, fetched_at,
            )
            for ref in refs
        ],
    )
    conn.commit()
    return len(refs)


def last_sync(conn: sqlite3.Connection, cik: int) -> float:
    row = conn.execute("SELECT synced_at FROM issuers WHERE cik = ?", (cik,)).fetchone()
    return float(row["synced_at"]) if row else 0.0


def is_fresh(conn: sqlite3.Connection, cik: int) -> bool:
    synced = last_sync(conn, cik)
    return bool(synced) and (time.time() - synced) < TTL


def list_filings(
    conn: sqlite3.Connection,
    cik: int,
    *,
    forms: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FilingRef], int]:
    clauses = ["cik = ?"]
    params: list = [int(cik)]
    if forms:
        placeholders = ",".join("?" for _ in forms)
        clauses.append(f"UPPER(form) IN ({placeholders})")
        params.extend([item.upper() for item in forms])
    if start:
        clauses.append("(period_of_report = '' OR period_of_report >= ?)")
        params.append(start[:10])
    if end:
        clauses.append("(period_of_report = '' OR period_of_report <= ?)")
        params.append(end[:10])
    where = " AND ".join(clauses)
    total = conn.execute(f"SELECT COUNT(*) FROM filings_index WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM filings_index WHERE {where} ORDER BY filed DESC, accession DESC LIMIT ? OFFSET ?",
        [*params, max(1, int(limit)), max(0, int(offset))],
    ).fetchall()
    refs = [
        FilingRef(
            symbol="",
            cik=int(row["cik"]),
            accession=row["accession"],
            form=row["form"],
            filed=row["filed"] or "",
            period_of_report=row["period_of_report"] or "",
            primary_document=row["primary_document"] or "",
            source_url=row["source_url"] or "",
        )
        for row in rows
    ]
    return refs, int(total)


def get(conn: sqlite3.Connection, accession: str) -> FilingRef | None:
    row = conn.execute(
        "SELECT * FROM filings_index WHERE accession = ?", (accession,)
    ).fetchone()
    if row is None:
        return None
    return FilingRef(
        symbol="",
        cik=int(row["cik"]),
        accession=row["accession"],
        form=row["form"],
        filed=row["filed"] or "",
        period_of_report=row["period_of_report"] or "",
        primary_document=row["primary_document"] or "",
        source_url=row["source_url"] or "",
    )


def latest(conn: sqlite3.Connection, cik: int, form: str) -> FilingRef | None:
    row = conn.execute(
        "SELECT * FROM filings_index WHERE cik = ? AND UPPER(form) = ?"
        " ORDER BY filed DESC, accession DESC LIMIT 1",
        (int(cik), (form or "10-K").upper()),
    ).fetchone()
    if row is None:
        return None
    return FilingRef(
        symbol="",
        cik=int(row["cik"]),
        accession=row["accession"],
        form=row["form"],
        filed=row["filed"] or "",
        period_of_report=row["period_of_report"] or "",
        primary_document=row["primary_document"] or "",
        source_url=row["source_url"] or "",
    )


def cached_symbol(conn: sqlite3.Connection, symbol: str) -> int | None:
    row = conn.execute(
        "SELECT cik FROM issuers WHERE UPPER(symbol) = ?", (symbol.upper(),)
    ).fetchone()
    return int(row["cik"]) if row else None
