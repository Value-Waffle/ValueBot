"""Thesis-vault tools: ``thesis_read`` and ``thesis_annotations``.

The vault is plain files under ``{VW_THESIS_ROOT}/{TICKER}/``:

``thesis.md``
    YAML front matter delimited by a leading ``---`` block, followed by the
    markdown body. The front matter is parsed by a small stdlib-only parser —
    this module deliberately does not depend on PyYAML.
``attachments/``
    Arbitrary files (research notes, PDFs) listed by :func:`thesis_read`.
``.thesis/annotations/<doc>.json``
    ``{"mtime": ..., "annotations": [...]}`` documents indexed by
    :func:`thesis_annotations`.

An empty or missing vault is normal: both tools return ``ok=True`` with an
explicit note instead of an error. Path traversal outside the ticker directory
is rejected before any file is opened. Responses are capped at 8 KB; long text
is paged with ``offset``/``next_offset``.

Nothing here writes to stdout: over the MCP stdio transport stdout is the
JSON-RPC channel. Diagnostics go to stderr via :func:`mcp.util.log`.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from core import citations
from core import config as _config
from core import envelope as util
from core.errors import ArtifactNotCached, CitationUnresolvable, InvalidArgument

__all__ = [
    "thesis_read",
    "thesis_annotations",
    "parse_front_matter",
    "resolve",
    "BYTE_CAP",
]

#: Response cap from the tool contract.
BYTE_CAP = 8 * 1024

_JSON_SEPARATORS = (",", ":")
_MAX_ATTACHMENTS = 200
_MAX_ANNOTATION_DOCS = 200

_HIDDEN_NAMES = {".ds_store"}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _json_bytes(payload: Any) -> int:
    return len(
        json.dumps(
            payload, separators=_JSON_SEPARATORS, ensure_ascii=False, default=str
        ).encode("utf-8")
    )


def _find_dir_ci(base: Path, name: str) -> Path | None:
    if not base or not base.is_dir():
        return None
    wanted = str(name).casefold()
    try:
        entries = sorted(base.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return None
    for entry in entries:
        if entry.is_dir() and entry.name.casefold() == wanted:
            return entry
    return None


def _read_text(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def _read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _safe_relative(value: Any) -> PurePosixPath | None:
    """Return a normalised relative path, or ``None`` for traversal/absolute."""
    text = str(value or "").replace("\\", "/").strip()
    if not text:
        return None
    rel = PurePosixPath(text)
    if rel.is_absolute() or not rel.parts:
        return None
    if any(part in {"", ".", ".."} for part in rel.parts):
        return None
    return rel


def _within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except (ValueError, OSError):
        return False


def _ticker_dir(symbol: str) -> Path | None:
    root = Path(_config.THESIS_ROOT)
    if not root.is_dir():
        return None
    wanted = symbol.casefold()
    try:
        entries = sorted(root.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return None
    for entry in entries:
        if entry.is_dir() and entry.name.casefold() == wanted:
            return entry
    return None


def _thesis_citation(symbol: str, section: str) -> dict:
    ticker = symbol.upper()
    artifact = {
        "module": "thesis",
        "kind": "vault-doc",
        "symbol": ticker,
        "file": section,
        "format": "md",
        "status": "cached",
    }
    return citations.cite(
        "thesis",
        f"{ticker} thesis",
        section=section,
        extra={"file": section},
        artifact=artifact,
    )


def resolve(artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
    """Serve the vault markdown behind a ``thesis`` ``vault-doc`` citation.

    ``artifact`` is the block attached by :func:`_thesis_citation`. The path is
    validated with the same helpers as :func:`thesis_read` (``_safe_relative``
    plus ``_within``) so a citation can never escape its ticker directory. The
    vault is read-only: nothing is written here.

    Returns ``{kind, format, chunk, next_offset, total_chars, file, symbol}``.
    Raises :class:`InvalidArgument` for a malformed locator,
    :class:`CitationUnresolvable` for an unsupported artifact kind and
    :class:`ArtifactNotCached` when the file is not present locally.
    """
    if not isinstance(artifact, dict) or not artifact:
        raise InvalidArgument(
            "artifact must be a thesis vault-doc locator",
            hint="pass the citation's artifact block, not the citation key",
        )

    kind = str(artifact.get("kind") or "vault-doc").strip()
    if kind != "vault-doc":
        raise CitationUnresolvable(
            f"thesis cannot resolve artifact kind {kind!r}",
            hint="thesis citations only carry vault-doc artifacts",
        )

    raw = str(artifact.get("symbol") or "").strip()
    if not raw:
        raise InvalidArgument(
            "artifact.symbol is required",
            hint="re-run thesis_read to get a fresh citation",
        )
    ticker = raw.upper()

    rel = _safe_relative(artifact.get("file"))
    if rel is None:
        raise InvalidArgument(
            "artifact.file must be a relative path inside the ticker vault",
            details={"symbol": ticker, "file": str(artifact.get("file") or "")},
        )

    directory = _ticker_dir(raw)
    if directory is None:
        raise ArtifactNotCached(
            f"no thesis vault for {ticker}",
            hint="run thesis_read first",
        )

    target = directory.joinpath(*rel.parts)
    if not _within(directory, target):
        raise InvalidArgument(
            "artifact.file must stay inside the ticker vault",
            details={"symbol": ticker, "file": rel.as_posix()},
        )
    if not target.is_file():
        raise ArtifactNotCached(
            f"{rel.as_posix()!r} not found in the {ticker} thesis vault",
            hint="run thesis_read first",
            details={"symbol": ticker, "file": rel.as_posix()},
        )

    content = _read_text(target)
    if content is None:
        raise ArtifactNotCached(
            f"could not read {rel.as_posix()!r} from the {ticker} thesis vault",
            hint="run thesis_read first",
            details={"symbol": ticker, "file": rel.as_posix()},
        )

    page = util.chunk_text(content, offset, limit)
    return {
        "kind": "vault-doc",
        "format": "md",
        "chunk": page["chunk"],
        "next_offset": page["next_offset"],
        "total_chars": page["total"],
        "file": rel.as_posix(),
        "symbol": ticker,
    }


# ---------------------------------------------------------------------------
# stdlib front-matter parser
# ---------------------------------------------------------------------------
def _scalar(value: str) -> Any:
    text = value.strip()
    if text in {"", "~", "null", "Null", "NULL"}:
        return None
    if text == "{}":
        return {}
    if text == "[]":
        return []
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in inner.split(",")]
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    lowered = text.casefold()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def parse_front_matter(text: str) -> tuple[dict, str, str]:
    """Split ``text`` into ``(front_matter, body, raw_front_matter)``.

    Supports flat scalars, one level of nested mappings, inline lists
    (``[a, b]``) and block lists (``- item``). Anything it cannot understand is
    ignored rather than raising — a malformed vault must not break the tool.
    """
    text = text or ""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text, ""

    end: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return {}, text, ""

    raw = "".join(lines[1:end])
    body = "".join(lines[end + 1 :]).lstrip("\n")
    data: dict[str, Any] = {}
    current: str | None = None
    implicit_empty: set[str] = set()

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))

        if stripped.startswith("- ") and current is not None:
            if isinstance(data.get(current), dict) and not data[current]:
                data[current] = []
            if isinstance(data.get(current), list):
                data[current].append(_scalar(stripped[2:].strip()))
            implicit_empty.discard(current)
            continue

        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().strip("'\"")
        value = value.strip()
        if not key:
            continue

        if indent == 0:
            if value:
                data[key] = _scalar(value)
            else:
                data[key] = {}
                implicit_empty.add(key)
            current = key
            continue

        if current is None:
            continue
        if isinstance(data.get(current), dict):
            data[current][key] = _scalar(value) if value else None
            implicit_empty.discard(current)

    # ``ticker:`` with no children is an empty scalar, not a mapping. Explicit
    # ``key: {}`` is preserved because it was never added to ``implicit_empty``.
    for key in implicit_empty:
        if isinstance(data.get(key), dict) and not data[key]:
            data[key] = None

    return data, body, raw


# ---------------------------------------------------------------------------
# vault inventory
# ---------------------------------------------------------------------------
def _inventory(ticker_dir: Path) -> tuple[list[dict], list[dict]]:
    """Return ``(attachments, documents)`` relative to the ticker directory."""
    attachments: list[dict] = []
    documents: list[dict] = []

    attachments_dir = _find_dir_ci(ticker_dir, "attachments")
    if attachments_dir is not None:
        attachments = _list_files(attachments_dir, limit=_MAX_ATTACHMENTS)
        for item in attachments:
            item["path"] = f"attachments/{item['path']}"

    try:
        entries = sorted(ticker_dir.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        entries = []
    for entry in entries:
        name = entry.name
        if name.casefold() in _HIDDEN_NAMES or name.startswith("."):
            continue
        if entry.is_dir():
            continue
        documents.append(_file_entry(entry))

    return attachments, documents


def _file_entry(path: Path) -> dict:
    try:
        size = path.stat().st_size
    except OSError:  # pragma: no cover - unreadable path
        size = None
    return {"name": path.name, "path": path.name, "size": size}


def _list_files(base: Path, limit: int) -> list[dict]:
    items: list[dict] = []
    try:
        paths = sorted(base.rglob("*"), key=lambda item: item.as_posix().casefold())
    except OSError:
        return items
    for path in paths:
        if len(items) >= limit:
            break
        try:
            if not path.is_file():
                continue
        except OSError:  # pragma: no cover - unreadable path
            continue
        if path.name.startswith(".") or path.name.casefold() in _HIDDEN_NAMES:
            continue
        entry = _file_entry(path)
        entry["path"] = path.relative_to(base).as_posix()
        items.append(entry)
    return items


# ---------------------------------------------------------------------------
# text paging
# ---------------------------------------------------------------------------
def _page_text(
    text: str,
    offset: int,
    base_fields: dict,
    *,
    cap: int = BYTE_CAP,
    field: str = "text",
    max_chars: int = BYTE_CAP,
) -> dict:
    """Return a byte-capped page of ``text`` with a stable ``next_offset``."""
    total = len(text or "")
    offset = max(0, min(int(offset or 0), total))
    remaining = max(0, total - offset)

    def build(size: int) -> tuple[dict, int | None]:
        chunk = util.chunk_text(text, offset, size)
        payload = util.ok(
            **base_fields,
            **{field: chunk["chunk"]},
            offset=offset,
            total=chunk["total"],
            next_offset=chunk["next_offset"],
        )
        return payload, chunk["next_offset"]

    best_payload, best_next = build(0)
    low, high = 1, min(max_chars, remaining) if remaining else 0
    while low <= high:
        middle = (low + high) // 2
        candidate, next_offset = build(middle)
        if _json_bytes(candidate) <= cap:
            best_payload, best_next = candidate, next_offset
            low = middle + 1
        else:
            high = middle - 1

    best_payload["next_offset"] = best_next
    if best_next is not None:
        best_payload["truncated"] = True
    return util.cap_bytes(best_payload, cap)


# ---------------------------------------------------------------------------
# thesis_read
# ---------------------------------------------------------------------------
def thesis_read(
    symbol: str, file: str | None = None, offset: int = 0, limit: int = BYTE_CAP
) -> dict:
    """Read the thesis vault for a ticker.

    With ``file=None`` the parsed ``thesis.md`` (front matter + body) and the
    ``attachments/`` inventory are returned. With ``file`` set, that relative
    document is returned instead. Paths outside the ticker directory are
    rejected. A missing vault returns ``ok=True`` with an explicit note.
    """
    raw = "" if symbol is None else str(symbol).strip()
    if not raw:
        return util.err("no_symbol", "symbol is required")

    ticker = raw.upper()
    directory = _ticker_dir(raw)
    if directory is None:
        return util.ok(
            symbol=ticker,
            has_thesis=False,
            note=f"no thesis vault for {ticker}",
            front_matter={},
            raw_front_matter="",
            body="",
            attachments=[],
            documents=[],
        )

    attachments, documents = _inventory(directory)

    if file is not None:
        rel = _safe_relative(file)
        if rel is None:
            return util.err(
                "invalid_path",
                "file must be a relative path inside the ticker vault",
                symbol=raw,
                file=str(file),
            )
        target = directory.joinpath(*rel.parts)
        if not _within(directory, target):
            return util.err(
                "invalid_path",
                "file must stay inside the ticker vault",
                symbol=raw,
                file=str(file),
            )
        if not target.is_file():
            return util.err(
                "thesis_file_not_found",
                f"{rel.as_posix()!r} not found in the {ticker} thesis vault",
                symbol=raw,
                file=rel.as_posix(),
            )
        content = _read_text(target)
        if content is None:
            return util.err(
                "thesis_file_unreadable",
                f"could not read {rel.as_posix()!r}",
                symbol=raw,
                file=rel.as_posix(),
            )
        return _page_text(
            content,
            offset,
            {
                "symbol": ticker,
                "file": rel.as_posix(),
                "has_thesis": (directory / "thesis.md").is_file(),
                "size": len(content),
                "citations": [_thesis_citation(raw, rel.as_posix())],
            },
            cap=BYTE_CAP,
            field="text",
            max_chars=max(1, min(int(limit or BYTE_CAP), BYTE_CAP)),
        )

    thesis_path = directory / "thesis.md"
    text = _read_text(thesis_path)
    if text is None:
        return util.ok(
            symbol=ticker,
            has_thesis=False,
            note=f"no thesis.md in the {ticker} vault",
            front_matter={},
            raw_front_matter="",
            body="",
            attachments=attachments,
            documents=documents,
        )

    front_matter, body, raw_front_matter = parse_front_matter(text)
    return _page_text(
        body,
        offset,
        {
            "symbol": ticker,
            "file": "thesis.md",
            "has_thesis": True,
            "front_matter": front_matter,
            "raw_front_matter": raw_front_matter,
            "attachments": attachments,
            "documents": documents,
            "citations": [_thesis_citation(raw, "thesis.md")],
        },
        cap=BYTE_CAP,
        field="body",
        max_chars=max(1, min(int(limit or BYTE_CAP), BYTE_CAP)),
    )


# ---------------------------------------------------------------------------
# thesis_annotations
# ---------------------------------------------------------------------------
def _doc_key(value: Any) -> str:
    text = str(value or "").replace("\\", "/").strip()
    name = PurePosixPath(text).name.casefold()
    for suffix in (".json", ".pdf", ".md", ".txt", ".html", ".htm"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def _annotation_entry(path: Path) -> dict:
    payload = _read_json(path)
    items: list[dict] = []
    mtime = None
    if isinstance(payload, dict):
        mtime = payload.get("mtime")
        raw_items = payload.get("annotations")
        if isinstance(raw_items, list):
            items = [item for item in raw_items if isinstance(item, dict)]
    elif isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]

    types = Counter(
        str(item.get("type") or item.get("kind") or "unknown") for item in items
    )
    if mtime is None:
        try:
            mtime = int(path.stat().st_mtime)
        except OSError:  # pragma: no cover - unreadable path
            mtime = None

    return {
        "name": path.name[: -len(".json")] if path.name.endswith(".json") else path.name,
        "path": path.name,
        "mtime": util.iso(mtime) if isinstance(mtime, (int, float)) else mtime,
        "count": len(items),
        "types": dict(types),
        "has_annotations": bool(items),
        "items": items,
    }


def thesis_annotations(
    symbol: str, doc: str | None = None, offset: int = 0, limit: int = 50
) -> dict:
    """Index a ticker's ``.thesis/annotations/*.json`` files.

    With ``doc=None`` the response lists ``{name, count, types,
    has_annotations}`` for every annotation document. With ``doc`` set, that
    document's annotation items are returned (paged). A missing vault or
    annotation directory is a normal empty result, not an error.
    """
    raw = "" if symbol is None else str(symbol).strip()
    if not raw:
        return util.err("no_symbol", "symbol is required")

    ticker = raw.upper()
    directory = _ticker_dir(raw)
    if directory is None:
        return util.ok(
            symbol=ticker,
            note=f"no thesis vault for {ticker}",
            documents=[],
            count=0,
        )

    annotations_dir = _find_dir_ci(_find_dir_ci(directory, ".thesis") or directory, "annotations")
    if annotations_dir is None or not annotations_dir.is_dir():
        return util.ok(
            symbol=ticker,
            note=f"no annotations for {ticker}",
            documents=[],
            count=0,
        )

    try:
        paths = sorted(
            annotations_dir.glob("*.json"), key=lambda item: item.name.casefold()
        )
    except OSError:
        paths = []
    paths = paths[:_MAX_ANNOTATION_DOCS]

    if doc is not None:
        rel = _safe_relative(doc)
        if rel is None:
            return util.err(
                "invalid_path",
                "doc must be a relative name inside the annotation directory",
                symbol=raw,
                doc=str(doc),
            )
        wanted = _doc_key(rel.name)
        for path in paths:
            if _doc_key(path.name) == wanted:
                entry = _annotation_entry(path)
                items = entry["items"]
                start = max(0, min(int(offset or 0), len(items)))
                take = max(1, min(int(limit or 50), 200))
                page = items[start : start + take]
                next_offset = start + len(page)
                payload = util.ok(
                    symbol=ticker,
                    document=entry["name"],
                    path=entry["path"],
                    mtime=entry["mtime"],
                    count=entry["count"],
                    total=len(items),
                    types=entry["types"],
                    has_annotations=entry["has_annotations"],
                    items=page,
                    offset=start,
                    next_offset=next_offset if next_offset < len(items) else None,
                    citations=[
                        _thesis_citation(
                            raw, f".thesis/annotations/{entry['path']}"
                        )
                    ],
                )
                return util.cap_bytes(payload, BYTE_CAP)
        return util.err(
            "annotations_not_found",
            f"no annotations document matching {doc!r} for {ticker}",
            symbol=raw,
            doc=str(doc),
        )

    entries = [_annotation_entry(path) for path in paths]
    documents = [
        {
            "name": entry["name"],
            "path": entry["path"],
            "mtime": entry["mtime"],
            "count": entry["count"],
            "types": entry["types"],
            "has_annotations": entry["has_annotations"],
        }
        for entry in entries
    ]
    documents.sort(key=lambda item: item["name"].casefold())
    payload = util.ok(
        symbol=ticker,
        count=len(documents),
        documents=documents,
        citations=[
            _thesis_citation(raw, ".thesis/annotations") if documents else None
        ],
    )
    payload["citations"] = citations.merge(
        citation for citation in payload.get("citations") or [] if citation
    )
    return util.cap_bytes(payload, BYTE_CAP)
