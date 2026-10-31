"""Semantic artifact store: manifest, gzip payloads, locks and LRU eviction."""

from __future__ import annotations

import fcntl
import gzip
import hashlib
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from ..sources.secparser_source import PARSER_VERSION

SCHEMA_VERSION = 1
RULES_VERSION = "1"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def artifact_paths(root: Path, cik: int, accession: str) -> tuple[Path, Path, Path]:
    folder = Path(root) / str(cik)
    return (
        folder / f"{accession}.semantic.json.gz",
        folder / f"{accession}.html.gz",
        folder / f"{accession}.lock",
    )


def save_raw_html(root: Path, cik: int, accession: str, html: str) -> tuple[Path, str, int]:
    semantic, raw, _ = artifact_paths(root, cik, accession)
    payload = gzip.compress(html.encode("utf-8", "replace"))
    _atomic_write(raw, payload)
    digest = hashlib.sha256(html.encode("utf-8", "replace")).hexdigest()
    return raw, digest, len(html.encode("utf-8", "replace"))


def save_artifact(root: Path, cik: int, accession: str, artifact: dict) -> int:
    semantic, _, _ = artifact_paths(root, cik, accession)
    payload = gzip.compress(
        json.dumps(artifact, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    _atomic_write(semantic, payload)
    return len(payload)


@contextmanager
def build_lock(root: Path, cik: int, accession: str, timeout: float = 30.0):
    _, _, lock_path = artifact_paths(root, cik, accession)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("w")
    deadline = time.time() + timeout
    acquired = False
    try:
        while time.time() < deadline:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                time.sleep(0.1)
        yield acquired
    finally:
        if acquired:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def record(conn: sqlite3.Connection, ref, *, profile: str, parser_version: str,
           artifact_bytes: int, html_bytes: int, html_sha256: str,
           element_count: int, section_count: int, note_count: int,
           table_count: int, coverage: dict, warnings: list[str],
           status: str = "ready", error: str | None = None) -> None:
    now = time.time()
    conn.execute(
        """
        INSERT INTO artifacts
        (accession, cik, form, filed, period_of_report, primary_document,
         source_url, profile, parser_version, rules_version, schema_version,
         html_sha256, html_bytes, artifact_bytes, element_count, section_count,
         note_count, table_count, coverage_json, warnings_json, status, error,
         built_at, last_access)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(accession) DO UPDATE SET
            cik=excluded.cik, form=excluded.form, filed=excluded.filed,
            period_of_report=excluded.period_of_report,
            primary_document=excluded.primary_document, source_url=excluded.source_url,
            profile=excluded.profile, parser_version=excluded.parser_version,
            rules_version=excluded.rules_version, schema_version=excluded.schema_version,
            html_sha256=excluded.html_sha256, html_bytes=excluded.html_bytes,
            artifact_bytes=excluded.artifact_bytes, element_count=excluded.element_count,
            section_count=excluded.section_count, note_count=excluded.note_count,
            table_count=excluded.table_count, coverage_json=excluded.coverage_json,
            warnings_json=excluded.warnings_json, status=excluded.status,
            error=excluded.error, built_at=excluded.built_at,
            last_access=excluded.last_access
        """,
        (
            ref.accession, ref.cik, ref.form, ref.filed, ref.period_of_report,
            ref.primary_document, ref.source_url, profile, parser_version,
            RULES_VERSION, SCHEMA_VERSION, html_sha256, html_bytes, artifact_bytes,
            element_count, section_count, note_count, table_count,
            json.dumps(coverage, default=str), json.dumps(warnings, default=str),
            status, error, now, now,
        ),
    )
    conn.commit()


def _reason(row, root: Path) -> str:
    """Classify a manifest row for the running code.

    Returns one of ``ok``, ``missing`` (no row / files gone / not ready),
    ``failed`` (a previous build failed) or ``stale`` (the row is intact and
    the files exist, but they were produced by a different schema, rules or
    parser version). ``stale`` is rebuildable; ``missing`` is not.
    """
    if row is None:
        return "missing"
    if row["status"] == "failed":
        return "failed"
    if row["status"] != "ready":
        return "missing"
    semantic, raw, _ = artifact_paths(root, int(row["cik"]), row["accession"])
    if not (semantic.exists() and raw.exists()):
        return "missing"
    if (
        int(row["schema_version"]) != SCHEMA_VERSION
        or row["rules_version"] != RULES_VERSION
        or row["parser_version"] != PARSER_VERSION
    ):
        return "stale"
    return "ok"


def _valid(row, root: Path) -> bool:
    return _reason(row, root) == "ok"


def manifest(conn: sqlite3.Connection, accession: str):
    return conn.execute("SELECT * FROM artifacts WHERE accession = ?", (accession,)).fetchone()


def _touch(conn: sqlite3.Connection, accession: str) -> None:
    """Best-effort LRU timestamp. A read must never fail because of it."""
    try:
        conn.execute(
            "UPDATE artifacts SET last_access = ? WHERE accession = ?",
            (time.time(), accession),
        )
        conn.commit()
    except sqlite3.Error:  # read-only database, locked file, ...
        try:
            conn.rollback()
        except sqlite3.Error:  # pragma: no cover - defensive
            pass


def load_with_reason(
    conn: sqlite3.Connection, root: Path, accession: str
) -> tuple[dict | None, str]:
    """Load an artifact and say why it was unusable when it is ``None``."""
    row = manifest(conn, accession)
    reason = _reason(row, root)
    if reason != "ok":
        return None, reason
    semantic, _, _ = artifact_paths(root, int(row["cik"]), accession)
    try:
        with gzip.open(semantic, "rt", encoding="utf-8") as handle:
            artifact = json.load(handle)
    except (OSError, ValueError):
        return None, "corrupt"
    _touch(conn, accession)
    return artifact, "ok"


def load(conn: sqlite3.Connection, root: Path, accession: str) -> dict | None:
    artifact, _ = load_with_reason(conn, root, accession)
    return artifact


def mark_failed(conn: sqlite3.Connection, ref, *, profile: str, parser_version: str,
                error: str) -> None:
    record(
        conn, ref, profile=profile, parser_version=parser_version, artifact_bytes=0,
        html_bytes=0, html_sha256="", element_count=0, section_count=0,
        note_count=0, table_count=0, coverage={}, warnings=[], status="failed",
        error=error[:500],
    )


def invalidate(conn: sqlite3.Connection, accession: str) -> None:
    conn.execute("DELETE FROM artifacts WHERE accession = ?", (accession,))
    conn.commit()


def evict_lru(conn: sqlite3.Connection, root: Path, max_bytes: int) -> int:
    rows = conn.execute(
        "SELECT accession, cik, artifact_bytes, html_bytes FROM artifacts "
        "WHERE status = 'ready' OR status = 'failed' "
        "ORDER BY last_access ASC, built_at ASC"
    ).fetchall()
    total = sum(int(row["artifact_bytes"] or 0) + int(row["html_bytes"] or 0) for row in rows)
    deleted = 0
    for row in rows:
        if total <= max_bytes:
            break
        semantic, raw, lock = artifact_paths(root, int(row["cik"]), row["accession"])
        for path in (semantic, raw, lock):
            try:
                path.unlink()
            except OSError:
                pass
        conn.execute("DELETE FROM artifacts WHERE accession = ?", (row["accession"],))
        total -= int(row["artifact_bytes"] or 0) + int(row["html_bytes"] or 0)
        deleted += 1
    conn.commit()
    return deleted
