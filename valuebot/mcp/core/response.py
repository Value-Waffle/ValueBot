"""Uniform response envelope, paging and byte caps."""

from __future__ import annotations

import copy
import time
from typing import Any, Iterable

from .envelope import _json_size, cap_bytes, fit_data
from .errors import ValuebotError

from . import citation_guard, citations as _citations

__all__ = ["success", "failure", "page", "timer"]

DEFAULT_CAP = 8192

#: Hard cap on citations carried by one envelope.
MAX_ENVELOPE_CITATIONS = 20


def _nested_lists(payload, path=()):
    found = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            found.extend(_nested_lists(value, path + (key,)))
    elif isinstance(payload, list):
        found.append((path, payload))
        for index, value in enumerate(payload[:3]):
            found.extend(_nested_lists(value, path + (index,)))
    return found


def _resolve(payload, path):
    node = payload
    for key in path:
        node = node[key]
    return node


def _shrink(payload: dict, limit: int) -> dict:
    """Trim the largest nested list until the JSON payload fits ``limit``.

    Works on a deep copy: trimming a nested list used to mutate the caller's
    list object in place, silently emptying the citation footer. ``citations``
    and ``references`` are contract fields, not payload, so they are never
    chosen as a trim target.
    """
    trimmed = copy.deepcopy(payload)

    def size() -> int:
        return _json_size(trimmed)

    if size() <= limit:
        return trimmed

    protected = {"citations", "references"}
    while size() > limit:
        candidates = [
            (path, value)
            for path, value in _nested_lists(trimmed)
            if value
            and path
            and isinstance(path[-1], str)
            and path[-1] not in protected
        ]
        if not candidates:
            break
        before = size()
        path, values = max(candidates, key=lambda item: len(item[1]))
        container = _resolve(trimmed, path)
        keep = len(values)
        while keep > 0 and size() > limit:
            keep = max(0, int(keep * 0.7))
            container[:] = values[:keep]
        trimmed["truncated"] = True
        if keep == 0 and size() > limit:
            parent_path, key = path[:-1], path[-1]
            parent = _resolve(trimmed, parent_path) if parent_path else trimmed
            if isinstance(parent, dict):
                parent.pop(key, None)
        if size() >= before:
            break
    return trimmed


def success(
    module: str,
    tool: str,
    data: dict,
    *,
    symbol: str | None = None,
    cik: int | None = None,
    citations: Iterable[dict] | None = None,
    paging: dict | None = None,
    meta: dict | None = None,
    cap: int = DEFAULT_CAP,
    started: float | None = None,
    echo_references: bool = True,
) -> dict:
    """Build a successful envelope.

    ``echo_references=False`` is for tools whose job is to OPEN evidence
    (``citation_resolve``, ``citation_view``): echoing the citation back would
    mint a fresh ``citation_id``/url on every call, which is a self-referential
    loop - each resolution creates the next thing to resolve.
    """
    # The footer is a contract field: human-readable attribution carrying no
    # URL or machine token. Neither ``citations`` nor ``references`` may ever
    # be passed through ``cap_bytes`` or ``_shrink``. Order of operations is
    # REFERENCE FIRST, DATA SECOND: build the footer, reserve its bytes, then
    # shrink only ``data`` into what is left.
    header: dict = {"ok": True, "module": module, "tool": tool}
    if symbol:
        header["symbol"] = symbol
    if cik is not None:
        header["cik"] = int(cik)
    if paging is not None:
        header["paging"] = paging

    # (1) settle the citation list: dedupe by key, then enforce the hard cap.
    citation_list: list[dict] = []
    if citations:
        seen: set[str] = set()
        for citation in citations:
            key = str(citation.get("key") or "")
            if key and key in seen:
                continue
            seen.add(key)
            citation_list.append(citation)
        citation_list = citation_list[:MAX_ENVELOPE_CITATIONS]

    # (2) fail-closed grounding: a cached fact with no citation loses its value.
    data, coverage = citation_guard.audit(data, citation_list)

    # (3) the footer is resolved from the ORIGINAL settled citations, before
    # any byte capping can touch anything.
    references = _citations.references(citation_list)
    if not echo_references:
        # Opening evidence is not evidence: do not hand back a new citation.
        citation_list = []
        references = []

    info = dict(meta or {})
    if started is not None:
        info.setdefault("elapsed_ms", int((time.perf_counter() - started) * 1000))
    info["citation_coverage"] = coverage
    info["data_truncated"] = False
    info["footer_overflow"] = False
    info.setdefault("bytes", 0)

    # Viewer provenance travels with every successful envelope as DATA, never as
    # an instruction. An imperative note here would be repeated on every tool
    # result (including citation_resolve results) and would drive the model into
    # a citation_view fan-out loop. Guidance lives in the skill, not the payload.
    # Imported lazily: the viewer imports this package, so a module-level import
    # would be a cycle.
    from . import artifact_viewer  # local import: avoids an import cycle

    viewer = artifact_viewer.status()
    info["viewer"] = viewer

    # (4) reserve the bytes the header, footer and meta skeleton will occupy.
    skeleton = dict(header)
    skeleton["citations"] = citation_list
    skeleton["references"] = references
    skeleton["data"] = {}
    skeleton["truncated"] = True
    skeleton["meta"] = info
    reserved = _json_size(skeleton)

    # (5)/(6) shrink ONLY data into the remaining budget.
    budget = max(cap - reserved, 512)
    fitted, data_truncated = fit_data(data, budget)

    # (7) assemble the final payload.
    payload = dict(header)
    payload["citations"] = citation_list
    payload["references"] = references
    payload["data"] = fitted
    if data_truncated:
        payload["truncated"] = True
    info["data_truncated"] = data_truncated
    payload["meta"] = info

    def _stamp_size() -> int:
        payload["meta"]["bytes"] = 0
        measured = _json_size(payload)
        while True:
            payload["meta"]["bytes"] = measured
            remeasured = _json_size(payload)
            if remeasured == measured:
                return measured
            measured = remeasured

    # Hard postcondition: the cap binds, but the footer is never sacrificed.
    # Only the footer itself can make this impossible; report that honestly.
    if _stamp_size() > cap:
        payload["meta"]["footer_overflow"] = True
        payload["data"] = {}
        payload["truncated"] = True
        payload["meta"]["data_truncated"] = True
        _stamp_size()
    return payload


def failure(
    module: str,
    tool: str,
    exc: ValuebotError,
    *,
    cap: int = 4096,
    started: float | None = None,
) -> dict:
    payload: dict = {
        "ok": False,
        "module": module,
        "tool": tool,
        "error": exc.to_dict(),
        "meta": {},
    }
    if started is not None:
        payload["meta"]["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return cap_bytes(payload, limit=cap)


def page(rows: list, offset: int, limit: int) -> tuple[list, dict]:
    offset = max(0, int(offset))
    limit = max(1, int(limit))
    total = len(rows)
    window = rows[offset : offset + limit]
    next_offset = offset + len(window)
    if next_offset >= total:
        next_offset = None
    return window, {
        "offset": offset,
        "limit": limit,
        "total": total,
        "next_offset": next_offset,
        "truncated": next_offset is not None,
    }


def timer() -> float:
    return time.perf_counter()
