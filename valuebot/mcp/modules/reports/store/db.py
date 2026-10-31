"""Reports storage schema: filing index, artifact manifest and TTL entries."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS filings_index (
    accession TEXT PRIMARY KEY,
    cik INTEGER NOT NULL,
    form TEXT NOT NULL,
    filed TEXT,
    period_of_report TEXT,
    primary_document TEXT,
    source_url TEXT,
    synced_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_filings_cik ON filings_index(cik, filed DESC);
CREATE INDEX IF NOT EXISTS idx_filings_form ON filings_index(cik, form, filed DESC);

CREATE TABLE IF NOT EXISTS issuers (
    cik INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT,
    synced_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    accession TEXT PRIMARY KEY,
    cik INTEGER NOT NULL,
    form TEXT NOT NULL,
    filed TEXT,
    period_of_report TEXT,
    primary_document TEXT,
    source_url TEXT,
    profile TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    rules_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    html_sha256 TEXT,
    html_bytes INTEGER,
    artifact_bytes INTEGER,
    element_count INTEGER,
    section_count INTEGER,
    note_count INTEGER,
    table_count INTEGER,
    coverage_json TEXT,
    warnings_json TEXT,
    status TEXT NOT NULL,
    error TEXT,
    built_at REAL NOT NULL,
    last_access REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_cik ON artifacts(cik, filed DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_lru ON artifacts(last_access);
CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(status);

CREATE TABLE IF NOT EXISTS entries (
    key         TEXT PRIMARY KEY,
    bucket      TEXT NOT NULL DEFAULT 'default',
    value       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    expires_at  REAL NOT NULL,
    last_access REAL NOT NULL,
    bytes       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_bucket_expires ON entries(bucket, expires_at);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    return conn
