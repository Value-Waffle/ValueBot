"""Small stdout-safe helpers shared by every valuebot tool.

Over the MCP stdio transport stdout *is* the JSON-RPC channel, so nothing here
writes to stdout. All diagnostics go to stderr.

Pure stdlib, no import-time side effects.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from datetime import date, datetime, timezone
from typing import Any

__all__ = ["log", "err", "ok", "cap_bytes", "fit_data", "iso", "to_number", "chunk_text"]

_JSON_SEPARATORS = (",", ":")
_NAN_VALUES = {"", "n/a", "na", "none", "null", "-", "—", "–"}


def log(msg: str) -> None:
    """Write a diagnostic line to stderr (never stdout)."""
    sys.stderr.write(f"{msg}\n")
    try:
        sys.stderr.flush()
    except (AttributeError, OSError):  # pragma: no cover - closed stream
        pass


def err(code: str, message: str, **extra: Any) -> dict:
    """Return the canonical structured error envelope."""
    return {"error": {"code": code, "message": message, **extra}}


def ok(**fields: Any) -> dict:
    """Return the canonical success envelope."""
    payload: dict[str, Any] = {"ok": True}
    payload.update(fields)
    return payload


def _json_size(payload: Any) -> int:
    return len(
        json.dumps(payload, separators=_JSON_SEPARATORS, ensure_ascii=False, default=str).encode(
            "utf-8"
        )
    )


def _largest_fitting_count(items: list, build, limit: int) -> int:
    """Binary-search the largest prefix of ``items`` whose payload fits."""
    low, high, best = 0, len(items), 0
    while low <= high:
        mid = (low + high) // 2
        if _json_size(build(mid)) <= limit:
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    return best


def cap_bytes(payload: Any, limit: int = 8192) -> dict:
    """Truncate ``payload`` to at most ``limit`` JSON bytes.

    The longest list field is shortened first (callers page with
    ``offset``/``next_offset``); a scalar ``next_offset`` already present is
    preserved. A ``truncated: true`` marker is added whenever content is cut.
    """
    if not isinstance(payload, dict):
        payload = {"result": payload}

    if _json_size(payload) <= limit:
        return payload

    capped = dict(payload)
    list_keys = [key for key, value in capped.items() if isinstance(value, list) and value]

    if list_keys:
        target = max(list_keys, key=lambda key: len(capped[key]))

        def build(count: int, key: str = target) -> dict:
            trial = dict(capped)
            trial[key] = capped[key][:count]
            trial["truncated"] = True
            return trial

        keep = _largest_fitting_count(capped[target], build, limit)
        capped[target] = capped[target][:keep]
        capped["truncated"] = True
        return capped

    string_keys = [key for key, value in capped.items() if isinstance(value, str) and value]
    if string_keys:
        target = max(string_keys, key=lambda key: len(capped[key]))

        def build_text(count: int, key: str = target) -> dict:
            trial = dict(capped)
            trial[key] = capped[key][:count]
            trial["truncated"] = True
            return trial

        keep = _largest_fitting_count(capped[target], build_text, limit)
        capped[target] = capped[target][:keep]
        capped["truncated"] = True

    return capped


def _collect_paths(node: Any, predicate, path: tuple = ()) -> list[tuple[tuple, Any]]:
    """Return ``(path, value)`` for every node matching ``predicate``."""
    found: list[tuple[tuple, Any]] = []
    if predicate(node):
        found.append((path, node))
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_collect_paths(value, predicate, path + (key,)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_collect_paths(value, predicate, path + (index,)))
    return found


def _get_path(node: Any, path: tuple) -> Any:
    for key in path:
        node = node[key]
    return node


def _set_path(node: Any, path: tuple, value: Any) -> Any:
    """Assign ``value`` at ``path``; returns the (possibly new) root."""
    if not path:
        return value
    parent = _get_path(node, path[:-1])
    parent[path[-1]] = value
    return node


def _trim_largest_list(root: Any, limit: int) -> tuple[Any, bool] | None:
    """Trim the largest nested list in ``root`` to the longest fitting prefix."""
    candidates = _collect_paths(root, lambda value: isinstance(value, list) and bool(value))
    if not candidates:
        return None
    path, values = max(candidates, key=lambda item: len(item[1]))

    def build(count: int, path: tuple = path, values: list = values) -> Any:
        trial = copy.deepcopy(root)
        _set_path(trial, path, list(values[:count]))
        return trial

    keep = _largest_fitting_count(values, build, limit)
    return build(keep), keep < len(values)


def fit_data(data: Any, limit: int) -> tuple[Any, bool]:
    """Shrink ONLY ``data`` until its JSON size fits ``limit``.

    Never mutates the caller's object: a deep copy is trimmed. The largest
    nested list is shortened first, then the largest nested string, repeating
    until the budget fits or nothing more can be removed. Sibling keys are
    never touched, which is what lets the response footer stay a contract
    field instead of payload.

    Returns ``(fitted_data, truncated)``.
    """
    fitted = copy.deepcopy(data)
    limit = max(0, int(limit))
    if _json_size(fitted) <= limit:
        return fitted, False

    truncated = False
    while _json_size(fitted) > limit:
        changed = False

        result = _trim_largest_list(fitted, limit)
        if result is not None:
            candidate, list_changed = result
            if list_changed:
                fitted = candidate
                truncated = True
                changed = True
                if _json_size(fitted) <= limit:
                    break

        strings = _collect_paths(fitted, lambda value: isinstance(value, str) and bool(value))
        if not strings:
            if not changed:
                break
            continue
        path, value = max(strings, key=lambda item: len(item[1]))

        def build_text(count: int, path: tuple = path, value: str = value) -> Any:
            trial = copy.deepcopy(fitted)
            _set_path(trial, path, value[:count])
            return trial

        keep = _largest_fitting_count(value, build_text, limit)
        if keep >= len(value):
            if not changed:
                break
            continue
        fitted = build_text(keep)
        truncated = True

    return fitted, truncated


def iso(dt: Any) -> str | None:
    """Render datetimes/dates as ISO-8601 (naive datetimes are treated as UTC)."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    if isinstance(dt, date):
        return dt.isoformat()
    if isinstance(dt, (int, float)) and not isinstance(dt, bool):
        return datetime.fromtimestamp(dt, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return str(dt)


_INT_RE = re.compile(r"[-+]?\d+")


def to_number(value: Any) -> int | float | None:
    """Parse ``"1,234.5"`` / ``"$1,234"`` / ``"(42)"`` into a number."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if text.lower() in _NAN_VALUES:
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = (
        text.replace(",", "")
        .replace("$", "")
        .replace("%", "")
        .replace("\u00a0", "")
        .replace(" ", "")
    )
    if text.lower() in _NAN_VALUES:
        return None

    try:
        number: int | float
        if _INT_RE.fullmatch(text):
            number = int(text)
        else:
            number = float(text)
    except (TypeError, ValueError):
        return None
    return -number if negative else number


def chunk_text(text: str, offset: int = 0, limit: int = 8000) -> dict:
    """Split text into word-boundary-aware chunks for ``offset``/``limit`` paging.

    Returns ``{"chunk": str, "next_offset": int | None, "total": int}`` where
    ``total`` is the length of the full text. Offsets index the *original*
    text, so advancing ``next_offset`` never duplicates or skips characters.
    """
    text = text or ""
    total = len(text)
    offset = max(0, int(offset))
    limit = max(1, int(limit))

    if offset >= total:
        return {"chunk": "", "next_offset": None, "total": total}

    end = min(total, offset + limit)
    if end < total:
        window = text[offset:end]
        boundary = max(window.rfind("\n"), window.rfind(" "))
        # Only honour a boundary in the latter half, otherwise chunks get tiny.
        if boundary >= len(window) // 2:
            end = offset + boundary + 1

    return {
        "chunk": text[offset:end],
        "next_offset": end if end < total else None,
        "total": total,
    }
