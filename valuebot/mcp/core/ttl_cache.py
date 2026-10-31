"""Small SQLite-backed TTL cache shared by valuebot tools.

The cache is the plugin's only writable artifact and lives at
``${PLUGIN_DATA}/cache.sqlite`` by default (see :mod:`mcp.config`). Two logical
buckets are conventional: ``facts`` (long TTL — historical XBRL facts) and
``price`` (short TTL).

Design notes:

* WAL journaling keeps readers from blocking the writer.
* ``get`` treats an expired row as a miss and deletes it.
* ``evict_to_cap`` removes least-recently-accessed rows first, bounding the
  file near ~64 MB by default.
* A corrupt database file is discarded and recreated — a cache must never take
  a tool down.

Nothing here writes to stdout: over the MCP stdio transport stdout is the
JSON-RPC channel.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

try:  # normal import path: ``mcp.cache``
    from . import config as _config
except ImportError:  # pragma: no cover - direct module loading
    import config as _config  # type: ignore[no-redef]

__all__ = [
    "DEFAULT_MAX_BYTES",
    "SqliteTtlCache",
    "default_cache",
    "reset_default_cache",
]

#: Total cache size cap (~64 MB) before LRU eviction kicks in.
DEFAULT_MAX_BYTES = 64 * 1024 * 1024

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    key         TEXT PRIMARY KEY,
    bucket      TEXT NOT NULL DEFAULT 'default',
    value       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    expires_at  REAL NOT NULL,
    last_access REAL NOT NULL,
    bytes       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_bucket_expires
    ON entries (bucket, expires_at);
"""

_CORRUPT_MARKERS = ("not a database", "malformed", "file is encrypted")


def _now() -> float:
    return time.time()


class SqliteTtlCache:
    """A tiny JSON TTL cache on top of SQLite.

    ``max_bytes`` bounds the sum of stored payload sizes; ``set`` triggers an
    LRU eviction pass once that bound is exceeded.
    """

    def __init__(self, path: str | Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.path = Path(path).expanduser()
        self.max_bytes = int(max_bytes)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._open()

    # -- lifecycle ---------------------------------------------------------
    def _open(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Fall back to an in-memory cache rather than failing the server.
            self._connect_memory()
            return

        for _attempt in range(2):
            conn: sqlite3.Connection | None = None
            try:
                conn = sqlite3.connect(
                    str(self.path), timeout=5.0, check_same_thread=False
                )
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.executescript(_SCHEMA)
                conn.execute("SELECT COUNT(*) FROM entries").fetchone()
            except sqlite3.DatabaseError as exc:
                if conn is not None:
                    conn.close()
                if self._is_corrupt(exc):
                    self._discard_files()
                    continue
                # Locked/unavailable file: keep the tool alive in memory.
                break
            except OSError:
                if conn is not None:
                    conn.close()
                break
            else:
                self._conn = conn
                return

        self._connect_memory()

    @staticmethod
    def _is_corrupt(exc: BaseException) -> bool:
        message = str(exc).lower()
        return any(marker in message for marker in _CORRUPT_MARKERS)

    def _discard_files(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            try:
                Path(f"{self.path}{suffix}").unlink()
            except FileNotFoundError:
                continue
            except OSError:
                continue

    def _connect_memory(self) -> None:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.executescript(_SCHEMA)
        self._conn = conn

    def close(self) -> None:
        """Close the underlying connection (idempotent)."""
        with self._lock:
            conn, self._conn = self._conn, None
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error:  # pragma: no cover - already closed
                    pass

    def __enter__(self) -> "SqliteTtlCache":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- data --------------------------------------------------------------
    def get(self, key: str) -> Any:
        """Return the cached value, or ``None`` on a miss/expiry."""
        cache_key = str(key)
        with self._lock:
            conn = self._conn
            if conn is None:
                return None
            try:
                row = conn.execute(
                    "SELECT value, expires_at FROM entries WHERE key = ?",
                    (cache_key,),
                ).fetchone()
                if row is None:
                    return None
                payload, expires_at = row
                now = _now()
                if float(expires_at) <= now:
                    conn.execute("DELETE FROM entries WHERE key = ?", (cache_key,))
                    conn.commit()
                    return None
                conn.execute(
                    "UPDATE entries SET last_access = ? WHERE key = ?",
                    (now, cache_key),
                )
                conn.commit()
            except sqlite3.Error:
                return None
            try:
                return json.loads(payload)
            except (TypeError, ValueError):
                return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: float,
        bucket: str = "default",
    ) -> bool:
        """Store ``value`` under ``key`` for ``ttl_seconds``.

        Returns ``True`` when the row was written.
        """
        cache_key = str(key)
        try:
            payload = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return False

        now = _now()
        size = len(payload.encode("utf-8"))
        with self._lock:
            conn = self._conn
            if conn is None:
                return False
            try:
                conn.execute(
                    """
                    INSERT INTO entries
                        (key, bucket, value, created_at, expires_at, last_access, bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        bucket = excluded.bucket,
                        value = excluded.value,
                        created_at = excluded.created_at,
                        expires_at = excluded.expires_at,
                        last_access = excluded.last_access,
                        bytes = excluded.bytes
                    """,
                    (
                        cache_key,
                        str(bucket),
                        payload,
                        now,
                        now + float(ttl_seconds),
                        now,
                        size,
                    ),
                )
                conn.commit()
            except (sqlite3.Error, ValueError, TypeError):
                return False

        self.evict_to_cap(self.max_bytes)
        return True

    def delete(self, key: str) -> bool:
        """Delete ``key``; returns ``True`` when a row was removed."""
        with self._lock:
            conn = self._conn
            if conn is None:
                return False
            try:
                cursor = conn.execute("DELETE FROM entries WHERE key = ?", (str(key),))
                conn.commit()
            except sqlite3.Error:
                return False
            return cursor.rowcount > 0

    def purge_expired(self) -> int:
        """Delete every expired row; returns how many were removed."""
        with self._lock:
            conn = self._conn
            if conn is None:
                return 0
            try:
                cursor = conn.execute(
                    "DELETE FROM entries WHERE expires_at <= ?", (_now(),)
                )
                conn.commit()
            except sqlite3.Error:
                return 0
            return max(cursor.rowcount, 0)

    def evict_to_cap(self, max_bytes: int | None = None) -> int:
        """Evict least-recently-accessed rows until total bytes fit the cap."""
        cap = self.max_bytes if max_bytes is None else int(max_bytes)
        with self._lock:
            conn = self._conn
            if conn is None:
                return 0
            try:
                total = int(
                    conn.execute(
                        "SELECT COALESCE(SUM(bytes), 0) FROM entries"
                    ).fetchone()[0]
                )
                if total <= cap:
                    return 0
                rows = conn.execute(
                    "SELECT key, bytes FROM entries "
                    "ORDER BY last_access ASC, created_at ASC"
                ).fetchall()
                deleted = 0
                for key, size in rows:
                    if total <= cap:
                        break
                    conn.execute("DELETE FROM entries WHERE key = ?", (key,))
                    total -= int(size or 0)
                    deleted += 1
                conn.commit()
            except sqlite3.Error:
                return 0
            return deleted

    def stats(self) -> dict:
        """Return entry/byte counts overall and per bucket."""
        with self._lock:
            conn = self._conn
            if conn is None:
                return {
                    "path": str(self.path),
                    "entries": 0,
                    "bytes": 0,
                    "max_bytes": self.max_bytes,
                    "buckets": {},
                }
            try:
                entries, total = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(bytes), 0) FROM entries"
                ).fetchone()
                per_bucket = {
                    str(bucket): {"entries": int(count), "bytes": int(size)}
                    for bucket, count, size in conn.execute(
                        "SELECT bucket, COUNT(*), COALESCE(SUM(bytes), 0) "
                        "FROM entries GROUP BY bucket"
                    ).fetchall()
                }
            except sqlite3.Error:
                return {
                    "path": str(self.path),
                    "entries": 0,
                    "bytes": 0,
                    "max_bytes": self.max_bytes,
                    "buckets": {},
                }
        return {
            "path": str(self.path),
            "entries": int(entries),
            "bytes": int(total),
            "max_bytes": self.max_bytes,
            "buckets": per_bucket,
        }


_DEFAULT: SqliteTtlCache | None = None
_DEFAULT_LOCK = threading.Lock()


def default_cache() -> SqliteTtlCache:
    """Return the process-wide cache at ``config.CACHE_PATH`` (lazily created)."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = SqliteTtlCache(_config.CACHE_PATH)
        return _DEFAULT


def reset_default_cache() -> None:
    """Drop the singleton (tests and config reloads)."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is not None:
            _DEFAULT.close()
        _DEFAULT = None
