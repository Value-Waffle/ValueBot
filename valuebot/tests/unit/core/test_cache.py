"""Unit tests for :mod:`mcp.cache` — TTL, eviction, and corruption recovery.

All databases live under ``tmp_path``; the real plugin cache is never touched.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "mcp"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core import config  # noqa: E402
from core import ttl_cache as cache  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_singleton():
    cache.reset_default_cache()
    yield
    cache.reset_default_cache()


def test_set_get_roundtrip_and_stats(tmp_path):
    with cache.SqliteTtlCache(tmp_path / "cache.sqlite") as store:
        assert store.set("facts:AAPL", {"rows": [1, 2, 3]}, 60, bucket="facts") is True

        assert store.get("facts:AAPL") == {"rows": [1, 2, 3]}
        assert store.get("facts:MISSING") is None

        stats = store.stats()
        assert stats["entries"] == 1
        assert stats["bytes"] > 0
        assert stats["buckets"]["facts"]["entries"] == 1
        assert store.path == tmp_path / "cache.sqlite"


def test_set_replaces_existing_value(tmp_path):
    with cache.SqliteTtlCache(tmp_path / "cache.sqlite") as store:
        store.set("k", "old", 60)
        store.set("k", "new", 60)
        assert store.get("k") == "new"
        assert store.stats()["entries"] == 1


def test_expired_entry_is_a_miss_and_is_removed(tmp_path):
    with cache.SqliteTtlCache(tmp_path / "cache.sqlite") as store:
        store.set("short", "value", ttl_seconds=-1)

        assert store.get("short") is None
        assert store.stats()["entries"] == 0


def test_purge_expired_only_removes_dead_rows(tmp_path):
    with cache.SqliteTtlCache(tmp_path / "cache.sqlite") as store:
        store.set("live", "a", 60)
        store.set("dead-1", "b", -1)
        store.set("dead-2", "c", -1)

        assert store.purge_expired() == 2
        assert store.get("live") == "a"
        assert store.stats()["entries"] == 1


def test_evict_to_cap_removes_least_recently_accessed_first(tmp_path):
    with cache.SqliteTtlCache(tmp_path / "cache.sqlite", max_bytes=1_000_000) as store:
        values = {"a": "a" * 100, "b": "b" * 100, "c": "c" * 100}
        for key, value in values.items():
            store.set(key, value, 60)
            time.sleep(0.01)  # distinct last_access ordering

        total = store.stats()["bytes"]
        assert store.evict_to_cap(total) == 0  # already within cap

        deleted = store.evict_to_cap(total - 1)
        assert deleted == 1
        assert store.get("a") is None
        assert store.get("b") == values["b"]
        assert store.get("c") == values["c"]


def test_set_evicts_automatically_over_max_bytes(tmp_path):
    one_value = "x" * 200
    one_size = len(json.dumps(one_value).encode("utf-8"))

    with cache.SqliteTtlCache(
        tmp_path / "cache.sqlite", max_bytes=one_size * 2
    ) as store:
        store.set("old", one_value, 60)
        time.sleep(0.01)
        store.set("new-1", one_value, 60)
        time.sleep(0.01)
        store.set("new-2", one_value, 60)

        stats = store.stats()
        assert stats["bytes"] <= one_size * 2
        assert store.get("old") is None
        assert store.get("new-2") == one_value


def test_delete(tmp_path):
    with cache.SqliteTtlCache(tmp_path / "cache.sqlite") as store:
        store.set("k", "v", 60)
        assert store.delete("k") is True
        assert store.delete("k") is False
        assert store.get("k") is None


def test_corrupt_database_is_recreated(tmp_path):
    path = tmp_path / "cache.sqlite"
    path.write_bytes(b"this is definitely not a sqlite database\n" * 20)

    with cache.SqliteTtlCache(path) as store:
        assert store.set("k", {"v": 1}, 60) is True
        assert store.get("k") == {"v": 1}

    # And the recreated file is a real SQLite database.
    assert path.read_bytes().startswith(b"SQLite format 3")


def test_default_cache_uses_config_path_and_creates_parents(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "state" / "cache.sqlite"
    monkeypatch.setattr(config, "CACHE_PATH", target)

    first = cache.default_cache()
    second = cache.default_cache()

    assert first is second
    assert first.set("k", "v", 60) is True
    assert first.get("k") == "v"
    assert target.exists()


def test_get_on_closed_cache_is_safe(tmp_path):
    store = cache.SqliteTtlCache(tmp_path / "cache.sqlite")
    store.close()

    assert store.get("k") is None
    assert store.set("k", "v", 60) is False
    assert store.stats()["entries"] == 0
