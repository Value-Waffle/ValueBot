"""Reports orchestration: index, artifact build, section and table reads."""

from __future__ import annotations

import dataclasses
import gzip
import logging
import time
from collections import OrderedDict

from core import citations, config
from core.errors import (
    ArtifactNotCached,
    ArtifactTooLarge,
    CitationUnresolvable,
    FilingNotFound,
    InvalidArgument,
    ParserFailed,
    SectionNotFound,
    TableNotFound,
)
from core.models import FilingPage, Section, SectionsPage, SectionSlice, TableGrid, TableSlice
from core.envelope import chunk_text

from .domain import profiles, sections as section_rules, tables as table_rules
from .sources import edgar_source, secparser_source
from .store import artifact_store, db, filings_store

logger = logging.getLogger("valuebot.reports")


class ReportsService:
    api_version = 1

    def __init__(self, source=None, db_path=None, artifacts_root=None):
        self.source = source or edgar_source.ReportsEdgarSource()
        self.db_path = db_path or config.REPORTS_DB
        self.artifacts_root = artifacts_root or config.REPORTS_ARTIFACTS
        self._conn = None
        self._cache: OrderedDict[str, dict] = OrderedDict()

    @property
    def conn(self):
        if self._conn is None:
            self._conn = db.connect(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- issuer and index -------------------------------------------------
    def _issuer(self, symbol: str):
        company = self.source.company(symbol)
        cik = int(company.cik)
        if not filings_store.is_fresh(self.conn, cik):
            refs = self.source.filings(symbol)
            filings_store.sync_issuer(
                self.conn, symbol, cik, str(getattr(company, "name", "") or ""),
                refs, fetched_at=time.time(),
            )
        return company

    def filings(self, symbol: str, *, forms=None, start=None, end=None,
                limit: int = 50, offset: int = 0) -> dict:
        company = self._issuer(symbol)
        refs, total = filings_store.list_filings(
            self.conn, int(company.cik), forms=forms, start=start, end=end,
            limit=limit, offset=offset,
        )
        rows = []
        for ref in refs:
            row = ref.as_dict()
            row["symbol"] = symbol.upper()
            row["report_available"] = artifact_store.manifest(
                self.conn, ref.accession
            ) is not None
            rows.append(row)
        next_offset = offset + len(rows) if offset + len(rows) < total else None
        return {
            "symbol": symbol.upper(),
            "cik": int(company.cik),
            "rows": rows,
            "total": total,
            "paging": {
                "offset": offset, "limit": limit, "total": total,
                "next_offset": next_offset, "truncated": next_offset is not None,
            },
        }

    def _filing_ref(self, symbol: str | None, accession: str | None, form: str):
        if accession:
            cached = filings_store.get(self.conn, accession)
            if cached is not None:
                return cached
            if not symbol:
                raise FilingNotFound(f"accession {accession} is not indexed; symbol is required")
            return self.source.get_filing(symbol, accession=accession, form=form)
        if not symbol:
            raise FilingNotFound("symbol or accession is required")
        symbol = symbol.upper()
        cik = filings_store.cached_symbol(self.conn, symbol)
        if cik is not None:
            cached = filings_store.latest(self.conn, cik, form)
            if cached is not None:
                return dataclasses.replace(cached, symbol=symbol)
        company = self.source.company(symbol)
        ref = self.source.get_filing(symbol, form=form)
        return dataclasses.replace(ref, symbol=symbol, cik=int(company.cik))

    # -- artifact ---------------------------------------------------------
    def _cached(self, accession: str) -> dict | None:
        artifact = self._cache.get(accession)
        if artifact is not None:
            self._cache.move_to_end(accession)
        return artifact

    def artifact(self, symbol: str | None, accession: str | None, form: str) -> dict:
        ref = self._filing_ref(symbol, accession, form)
        cached = self._cached(ref.accession)
        if cached is not None:
            return cached
        loaded = artifact_store.load(self.conn, self.artifacts_root, ref.accession)
        if loaded is not None:
            self._remember(ref.accession, loaded)
            return loaded

        with artifact_store.build_lock(
            self.artifacts_root, ref.cik, ref.accession
        ) as acquired:
            loaded = artifact_store.load(self.conn, self.artifacts_root, ref.accession)
            if loaded is not None:
                self._remember(ref.accession, loaded)
                return loaded
            if not acquired:
                raise ParserFailed("artifact build already in progress; retry shortly")
            return self._build(ref)

    # -- load-only citation resolution -------------------------------------
    def artifact_peek(self, accession: str) -> dict:
        """Return the semantic artifact from the LRU or the gzip cache.

        A ``stale`` artifact (same files, older schema/rules/parser version) is
        rebuilt transparently: the data is intact, only the code moved on, so
        reporting ``not_cached`` there would be wrong and unfixable by the
        reader. A genuinely ``missing`` artifact still raises
        :class:`ArtifactNotCached` so the caller can build it with a domain tool.
        """
        accession = str(accession or "").strip()
        if not accession:
            raise ArtifactNotCached(
                "an artifact accession is required",
                hint="run report_section or report_sections first",
            )
        cached = self._cached(accession)
        if cached is not None:
            return cached
        loaded, reason = artifact_store.load_with_reason(
            self.conn, self.artifacts_root, accession
        )
        if loaded is not None:
            self._remember(accession, loaded)
            return loaded
        if reason == "stale":
            rebuilt = self._rebuild_stale(accession)
            if rebuilt is not None:
                return rebuilt
            raise ArtifactNotCached(
                f"semantic artifact for {accession} is stale and could not be rebuilt",
                hint="run report_section to rebuild it from the filing",
            )
        raise ArtifactNotCached(
            f"semantic artifact for {accession} is not cached ({reason})",
            hint="run report_section or report_sections first",
        )

    def _rebuild_stale(self, accession: str) -> dict | None:
        """Rebuild one stale artifact; failures degrade to ``None``."""
        try:
            artifact = self.artifact(None, accession, "10-K")
        except Exception:  # network, parser or lock failure: stay a cache miss
            logger.warning("stale artifact %s could not be rebuilt", accession, exc_info=True)
            return None
        if isinstance(artifact, dict):
            self._remember(accession, artifact)
            return artifact
        return None

    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
        """Serve the raw material behind a reports citation artifact.

        Load-only: builds nothing and never touches the network. Supported
        kinds are ``semantic-section``, ``semantic-table``, ``semantic-index``
        and ``raw-html``.
        """
        if not isinstance(artifact, dict) or not artifact:
            raise InvalidArgument("an artifact locator is required to resolve a citation")
        kind = str(artifact.get("kind") or "").strip()
        if kind == "raw-html":
            return self._resolve_raw_html(artifact, offset=offset, limit=limit)
        if kind not in {"semantic-section", "semantic-table", "semantic-index"}:
            raise CitationUnresolvable(
                f"unsupported reports artifact kind {kind!r}",
                hint=(
                    "supported kinds are semantic-section, semantic-table, "
                    "semantic-index and raw-html"
                ),
            )

        semantic = self.artifact_peek(str(artifact.get("accession") or ""))
        fmt = str(artifact.get("format") or "md")
        if kind == "semantic-section":
            return _page(
                kind, fmt,
                self._section_text(semantic, artifact.get("section_id")),
                offset, limit,
            )
        if kind == "semantic-table":
            return _page(kind, fmt, self._table_markdown(semantic, artifact.get("table_id")), offset, limit)
        return _page(kind, fmt, _index_markdown(semantic), offset, limit)

    @staticmethod
    def _section_text(semantic: dict, section_id) -> str:
        wanted = str(section_id or "").strip()
        target = next(
            (item for item in semantic.get("sections", []) if item.get("id") == wanted),
            None,
        )
        if target is None:
            raise SectionNotFound(
                f"no section {wanted}",
                hint="run report_sections to list valid section IDs",
            )
        section = Section(
            id=target["id"], parent_id=target.get("parent_id"),
            kind=target["kind"], title=target["title"], start=target["start"],
            end=target["end"], char_count=target["char_count"],
            section_type=target.get("section_type"), level=target.get("level", 0),
            table_ids=tuple(target.get("table_ids", ())),
            note_number=target.get("note_number"),
        )
        return section_rules.section_text(semantic.get("elements", []), section)

    @staticmethod
    def _table_markdown(semantic: dict, table_id) -> str:
        wanted = str(table_id or "").strip()
        record = next(
            (item for item in semantic.get("tables", []) if item.get("id") == wanted),
            None,
        )
        if record is None:
            raise TableNotFound(
                f"no table {wanted}",
                hint="run report_sections with include_tables=true to list table IDs",
            )
        grid = record.get("grid") or []
        header_rows = int(record.get("header_rows") or 1)
        return table_rules.render_markdown(grid, header_rows, max_rows=max(1, len(grid)))

    def _resolve_raw_html(self, artifact: dict, *, offset: int, limit: int) -> dict:
        accession = str(artifact.get("accession") or "").strip()
        cik = artifact.get("cik")
        if not accession or cik in (None, ""):
            raise ArtifactNotCached(
                "the raw-html artifact locator is incomplete",
                hint="run report_section or report_sections first",
            )
        _, raw, _ = artifact_store.artifact_paths(self.artifacts_root, int(cik), accession)
        if not raw.exists():
            raise ArtifactNotCached(
                f"raw HTML for {accession} is not cached",
                hint="run report_section or report_sections first",
            )
        total = _gzip_uncompressed_size(raw)
        start = max(0, int(offset))
        size = max(1, int(limit))
        data = _read_gzip_window(raw, start, size)
        end = start + len(data)
        return {
            "kind": "raw-html",
            "format": str(artifact.get("format") or "html"),
            "chunk": data.decode("utf-8", "replace"),
            "next_offset": end if end < total else None,
            "total_chars": total,
        }

    def _remember(self, accession: str, artifact: dict) -> None:
        self._cache[accession] = artifact
        while len(self._cache) > max(1, config.ARTIFACT_LRU):
            self._cache.popitem(last=False)

    def _build(self, ref) -> dict:
        html, actual_ref = self.source.filing_html(ref.symbol or "", ref.accession)
        ref = dataclasses.replace(
            actual_ref,
            symbol=ref.symbol or actual_ref.symbol,
        )
        size_mb = len(html.encode("utf-8", "replace")) / (1024 * 1024)
        if size_mb > config.MAX_HTML_MB:
            raise ArtifactTooLarge(
                f"filing HTML is {size_mb:.1f} MB, above the {config.MAX_HTML_MB} MB cap"
            )
        profile = profiles.profile_for(ref.form)
        started = time.perf_counter()
        try:
            elements, warnings = secparser_source.parse_html(html)
        except Exception as exc:
            artifact_store.mark_failed(
                self.conn, ref, profile=profile,
                parser_version=secparser_source.PARSER_VERSION, error=str(exc),
            )
            raise ParserFailed(f"sec-parser failed: {exc}") from exc

        try:
            section_list, coverage = section_rules.build_sections(elements, ref.form)
        except Exception as exc:
            raise ParserFailed(f"section heuristics failed: {exc}") from exc

        # tables
        table_records: list[dict] = []
        table_ids_by_section: dict[str, list[str]] = {}
        for index, element in enumerate(elements):
            if element.get("type") != "TableElement" or not element.get("table_html"):
                continue
            grid, header_rows = table_rules.extract_grid(element["table_html"])
            if not grid:
                continue
            table_id = f"t{len(table_records) + 1}"
            section_id = _owning_section(section_list, index)
            caption = table_rules.caption_for(elements, index)
            table_records.append(
                {
                    "id": table_id, "section_id": section_id, "index": index,
                    "caption": caption, "header_rows": header_rows, "grid": grid,
                }
            )
            if section_id:
                table_ids_by_section.setdefault(section_id, []).append(table_id)

        updated_sections = [
            dataclasses.replace(section, table_ids=tuple(table_ids_by_section.get(section.id, ())))
            for section in section_list
        ]
        section_ranges = [(section.start, section.end, section.id) for section in updated_sections]
        out_elements = []
        table_id_by_index = {record["index"]: record["id"] for record in table_records}
        for index, element in enumerate(elements):
            out_elements.append(
                {
                    "type": element.get("type"),
                    "level": element.get("level", 0),
                    "text": element.get("text", ""),
                    "section_id": _owning_section(updated_sections, index, section_ranges),
                    "table_id": table_id_by_index.get(index),
                }
            )

        coverage = dict(coverage)
        coverage["table_count"] = len(table_records)
        artifact = {
            "schema": artifact_store.SCHEMA_VERSION,
            "accession": ref.accession,
            "symbol": ref.symbol or (ref.symbol),
            "cik": ref.cik,
            "form": ref.form,
            "filed": ref.filed,
            "period_of_report": ref.period_of_report,
            "primary_document": ref.primary_document,
            "source_url": ref.source_url,
            "profile": profile,
            "parser_version": secparser_source.PARSER_VERSION,
            "rules_version": artifact_store.RULES_VERSION,
            "warnings": warnings,
            "coverage": coverage,
            "sections": [dataclasses.asdict(section) for section in updated_sections],
            "elements": out_elements,
            "tables": table_records,
            "parse_ms": int((time.perf_counter() - started) * 1000),
        }

        raw_path, digest, html_bytes = artifact_store.save_raw_html(
            self.artifacts_root, ref.cik, ref.accession, html
        )
        artifact_bytes = artifact_store.save_artifact(
            self.artifacts_root, ref.cik, ref.accession, artifact
        )
        artifact_store.record(
            self.conn, ref, profile=profile,
            parser_version=secparser_source.PARSER_VERSION,
            artifact_bytes=artifact_bytes, html_bytes=html_bytes, html_sha256=digest,
            element_count=len(out_elements), section_count=len(updated_sections),
            note_count=sum(1 for section in updated_sections if section.kind == "note"),
            table_count=len(table_records), coverage=coverage, warnings=warnings,
        )
        artifact_store.evict_lru(
            self.conn, self.artifacts_root, config.MAX_REPORTS_MB * 1024 * 1024
        )
        self._remember(ref.accession, artifact)
        return artifact

    # -- reads ------------------------------------------------------------
    def sections(self, *, symbol=None, accession=None, form="10-K", kind="all",
                 include_tables=False, offset=0, limit=40) -> dict:
        artifact = self.artifact(symbol, accession, form)
        sections = artifact["sections"]
        if kind == "items":
            sections = [item for item in sections if item["kind"] in {"item", "part"}]
        elif kind == "notes":
            sections = [item for item in sections if item["kind"] == "note"]
        total = len(sections)
        window = sections[offset : offset + limit]
        if include_tables:
            table_map = {table["id"]: table for table in artifact["tables"]}
            for item in window:
                item["tables"] = [
                    {
                        "id": table_id,
                        "caption": table_map.get(table_id, {}).get("caption", ""),
                        "rows": len(table_map.get(table_id, {}).get("grid", [])),
                    }
                    for table_id in item.get("table_ids", [])
                ]
        next_offset = offset + len(window) if offset + len(window) < total else None
        return {
            "filing": _filing_dict(artifact),
            "profile": artifact["profile"],
            "coverage": artifact["coverage"],
            "warnings": artifact["warnings"],
            "sections": window,
            "total": total,
            "paging": {
                "offset": offset, "limit": limit, "total": total,
                "next_offset": next_offset, "truncated": next_offset is not None,
            },
        }

    def section(self, *, symbol=None, accession=None, form="10-K", section_id: str,
                offset: int = 0, limit_chars: int = 8000) -> dict:
        artifact = self.artifact(symbol, accession, form)
        target = next(
            (item for item in artifact["sections"] if item["id"] == section_id), None
        )
        if target is None:
            raise SectionNotFound(
                f"no section {section_id}",
                hint="Call report_sections to list valid section IDs.",
            )
        section = Section(
            id=target["id"], parent_id=target.get("parent_id"),
            kind=target["kind"], title=target["title"], start=target["start"],
            end=target["end"], char_count=target["char_count"],
            section_type=target.get("section_type"), level=target.get("level", 0),
            table_ids=tuple(target.get("table_ids", ())),
            note_number=target.get("note_number"),
        )
        text = section_rules.section_text(artifact["elements"], section)
        chunk = chunk_text(text, offset=offset, limit=limit_chars)
        tables = [
            {
                "id": table["id"], "caption": table["caption"],
                "rows": len(table["grid"]),
                "columns": len(table["grid"][0]) if table["grid"] else 0,
            }
            for table in artifact["tables"]
            if table["id"] in section.table_ids
        ]
        return {
            "filing": _filing_dict(artifact),
            "section": target,
            "text": chunk["chunk"],
            "total_chars": chunk["total"],
            "next_offset": chunk["next_offset"],
            "tables": tables,
        }

    def search(self, *, symbol=None, accession=None, form="10-K", query: str,
               limit: int = 20) -> dict:
        artifact = self.artifact(symbol, accession, form)
        needle = (query or "").strip().lower()
        if len(needle) < 2:
            from core.errors import InvalidArgument

            raise InvalidArgument("search query must be at least 2 characters")
        hits: list[dict] = []
        titles = {item["id"]: item["title"] for item in artifact["sections"]}
        for index, element in enumerate(artifact["elements"]):
            text = element.get("text") or ""
            lowered = text.lower()
            position = lowered.find(needle)
            if position < 0:
                continue
            start = max(0, position - 80)
            snippet = text[start : position + len(needle) + 120].strip()
            hits.append(
                {
                    "kind": "text",
                    "section_id": element.get("section_id"),
                    "title": titles.get(element.get("section_id"), ""),
                    "snippet": snippet,
                    "element_index": index,
                }
            )
            if len(hits) >= limit:
                break
        if len(hits) < limit:
            for table in artifact["tables"]:
                for row in table["grid"]:
                    if any(needle in str(cell).lower() for cell in row):
                        hits.append(
                            {
                                "kind": "table",
                                "section_id": table.get("section_id"),
                                "title": titles.get(table.get("section_id"), ""),
                                "snippet": table.get("caption") or " | ".join(row[:6]),
                                "table_id": table["id"],
                            }
                        )
                        break
                if len(hits) >= limit:
                    break
        return {"filing": _filing_dict(artifact), "query": query, "hits": hits[:limit],
                "total": len(hits)}

    def table(self, *, symbol=None, accession=None, form="10-K", table_id: str,
              columns=None, row_offset: int = 0, max_rows: int = 40) -> dict:
        artifact = self.artifact(symbol, accession, form)
        record = next(
            (item for item in artifact["tables"] if item["id"] == table_id), None
        )
        if record is None:
            raise TableNotFound(
                f"no table {table_id}",
                hint="Call report_sections with include_tables=true to list table IDs.",
            )
        grid = record["grid"]
        header_rows = int(record.get("header_rows") or 1)
        selectors = [int(item) for item in columns] if columns else None
        markdown = table_rules.render_markdown(
            grid, header_rows, columns=selectors,
            row_offset=row_offset, max_rows=max_rows,
        )
        body_rows = max(0, len(grid) - header_rows)
        next_offset = row_offset + max_rows
        if next_offset >= body_rows:
            next_offset = None
        return {
            "filing": _filing_dict(artifact),
            "table": {
                "id": record["id"], "section_id": record.get("section_id"),
                "caption": record.get("caption"), "header_rows": header_rows,
                "rows": len(grid), "columns": len(grid[0]) if grid else 0,
            },
            "markdown": markdown,
            "row_offset": row_offset,
            "next_offset": next_offset,
            "total_rows": body_rows,
            "truncated": next_offset is not None,
        }


def _owning_section(section_list, index: int, ranges=None) -> str | None:
    owner = None
    for section in section_list:
        if section.start <= index < section.end:
            owner = section.id
    return owner


def _page(kind: str, fmt: str, text: str, offset: int, limit: int) -> dict:
    """Package one paged chunk in the house citation-resolver return shape."""
    page = chunk_text(text, offset=offset, limit=limit)
    return {
        "kind": kind,
        "format": fmt,
        "chunk": page["chunk"],
        "next_offset": page["next_offset"],
        "total_chars": page["total"],
    }


def _index_markdown(semantic: dict) -> str:
    """Render the section/table inventory of one semantic artifact as markdown."""
    sections = semantic.get("sections", [])
    counts: dict[str, int] = {}
    for table in semantic.get("tables", []):
        owner = table.get("section_id")
        if owner:
            counts[owner] = counts.get(owner, 0) + 1
    heading = " ".join(
        str(part).strip()
        for part in (
            semantic.get("symbol"), semantic.get("form"), semantic.get("filed"),
            semantic.get("accession"),
        )
        if part
    )
    lines = [
        f"# {heading}",
        "",
        "| id | kind | title | chars | tables |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in sections:
        title = str(item.get("title") or "").replace("|", "\\|")
        lines.append(
            f"| {item.get('id')} | {item.get('kind')} | {title} | "
            f"{item.get('char_count', 0)} | {counts.get(item.get('id'), 0)} |"
        )
    return "\n".join(lines)


def _gzip_uncompressed_size(path) -> int:
    """Read the gzip ISIZE trailer without decompressing the payload."""
    try:
        with open(path, "rb") as handle:
            handle.seek(-4, 2)
            return int.from_bytes(handle.read(4), "little")
    except OSError:  # pragma: no cover - defensive
        return 0


def _read_gzip_window(path, offset: int, limit: int) -> bytes:
    """Read ``limit`` bytes at ``offset`` of a gzip payload without loading it."""
    with gzip.open(path, "rb") as handle:
        remaining = offset
        while remaining > 0:
            block = handle.read(min(65536, remaining))
            if not block:
                return b""
            remaining -= len(block)
        return handle.read(limit)


def _filing_dict(artifact: dict) -> dict:
    return {
        "symbol": artifact.get("symbol"),
        "cik": artifact.get("cik"),
        "accession": artifact.get("accession"),
        "form": artifact.get("form"),
        "filed": artifact.get("filed"),
        "period_of_report": artifact.get("period_of_report"),
        "primary_document": artifact.get("primary_document"),
        "source_url": artifact.get("source_url"),
    }
