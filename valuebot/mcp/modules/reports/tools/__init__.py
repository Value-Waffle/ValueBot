"""MCP tools owned by the reports module."""

from __future__ import annotations

import time

from core import citations
from core.errors import InternalError, InvalidArgument, ValuebotError
from core.response import failure, success

MODULE = "reports"


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _error(tool: str, exc: Exception, started: float) -> dict:
    if isinstance(exc, ValuebotError):
        return failure(MODULE, tool, exc, started=started)
    return failure(MODULE, tool, InternalError(str(exc)), started=started)


def _artifact(filing: dict, kind: str, *, section_id=None, table_id=None,
              status: str = "cached") -> dict:
    """Build the citation artifact locator for one reports call site."""
    artifact = {
        "module": MODULE,
        "kind": kind,
        "cik": filing.get("cik"),
        "accession": filing.get("accession"),
        "format": "html" if kind == "raw-html" else "md",
        "status": status,
    }
    if section_id:
        artifact["section_id"] = section_id
    if table_id:
        artifact["table_id"] = table_id
    return artifact


def _filing_citation(filing: dict, section: str | None = None, label: str | None = None,
                     artifact: dict | None = None):
    return citations.cite(
        "sec-report",
        label or f"{filing.get('form')} {filing.get('accession')}",
        cik=filing.get("cik"),
        accession=filing.get("accession"),
        form=filing.get("form"),
        filed=filing.get("filed"),
        period=filing.get("period_of_report"),
        section=section,
        extra={"original_url": filing.get("source_url")},
        artifact=artifact,
    )


def _search_artifact(filing: dict, hit: dict) -> dict:
    """Locate the raw material behind one search hit.

    Each hit carries its own locator: a table hit resolves to that table, a
    text hit to its section, and only a locator-less hit falls back to the
    filing index. Two hits in one filing therefore never share an identity.
    """
    table_id = hit.get("table_id")
    section_id = hit.get("section_id")
    if table_id:
        return _artifact(
            filing, "semantic-table", section_id=section_id, table_id=table_id
        )
    if section_id:
        return _artifact(filing, "semantic-section", section_id=section_id)
    return _artifact(filing, "semantic-index")


def _search_label(filing: dict, hit: dict, query: str) -> str:
    """Name the hit, not just the query, so two matches are distinguishable."""
    table_id = hit.get("table_id")
    identity = (
        hit.get("title")
        or table_id
        or hit.get("section_id")
        or filing.get("accession")
        or "match"
    )
    identity = str(identity)
    if table_id and identity != table_id:
        # A table beside a text hit in the same section shares the title, so
        # the table id is what makes the two labels distinguishable.
        identity = f"{identity} (table {table_id})"
    return f"{identity[:80]} - match: {query[:40]}"


def register(mcp, service) -> None:
    @mcp.tool()
    def filing_list(
        symbol: str,
        forms: list[str] | str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List 10-K, 10-Q and other SEC filings for one issuer, newest first.

        Args:
            symbol: Exact ticker.
            forms: Form filter(s), e.g. ["10-K"].
            start: Inclusive period-of-report lower bound.
            end: Inclusive period-of-report upper bound.
            limit: Page size (1-100).
            offset: Zero-based row offset.
        """
        started = time.perf_counter()
        try:
            data = service.filings(
                symbol, forms=_as_list(forms) or None, start=start, end=end,
                limit=max(1, min(int(limit), 100)), offset=max(0, int(offset)),
            )
            cites = [
                _filing_citation(
                    row, label=f"{symbol.upper()} {row['form']} {row['filed']}",
                    artifact=_artifact(
                        row, "semantic-index",
                        status="cached" if row.get("report_available") else "not_cached",
                    ),
                )
                for row in data["rows"]
            ]
            return success(
                MODULE, "filing_list", data, symbol=data.get("symbol"),
                cik=data.get("cik"), citations=cites,
                paging=data.get("paging"), started=started, cap=6144,
            )
        except Exception as exc:
            return _error("filing_list", exc, started)

    @mcp.tool()
    def report_sections(
        symbol: str | None = None,
        accession: str | None = None,
        form: str = "10-K",
        kind: str = "all",
        include_tables: bool = False,
        offset: int = 0,
        limit: int = 40,
    ) -> dict:
        """List semantic 10-K/10-Q sections such as Item 7 (MD&A), Item 1A (risk factors), and notes.

        Args:
            symbol: Ticker; used when accession is omitted.
            accession: Explicit filing accession.
            form: Form used to resolve the latest filing (default "10-K").
            kind: "all", "items" or "notes".
            include_tables: Attach table summaries to each section.
            offset: Section offset.
            limit: Page size (1-80).
        """
        started = time.perf_counter()
        try:
            if kind not in {"all", "items", "notes"}:
                raise InvalidArgument("kind must be all, items or notes")
            data = service.sections(
                symbol=symbol, accession=accession, form=form, kind=kind,
                include_tables=bool(include_tables),
                offset=max(0, int(offset)), limit=max(1, min(int(limit), 80)),
            )
            citations_list = [
                _filing_citation(
                    data["filing"], section=item["id"],
                    label=f"{item['kind']} {item['title'][:80]}",
                    artifact=_artifact(
                        data["filing"], "semantic-section", section_id=item["id"]
                    ),
                )
                for item in data["sections"]
            ]
            return success(
                MODULE, "report_sections", data,
                symbol=symbol, cik=data["filing"].get("cik"),
                citations=citations_list, paging=data.get("paging"),
                started=started, cap=6144,
            )
        except Exception as exc:
            return _error("report_sections", exc, started)

    @mcp.tool()
    def report_section(
        symbol: str | None = None,
        accession: str | None = None,
        form: str = "10-K",
        section_id: str = "",
        offset: int = 0,
        limit_chars: int = 8000,
    ) -> dict:
        """Read a 10-K/10-Q section such as Item 7 (MD&A), Item 1A (risk factors), or a note, with character paging.

        Args:
            symbol: Ticker; used when accession is omitted.
            accession: Explicit filing accession.
            form: Form used to resolve the latest filing.
            section_id: Stable ID from report_sections, e.g. "part2-item7".
            offset: Character offset.
            limit_chars: Characters per page (1000-12000).
        """
        started = time.perf_counter()
        try:
            if not section_id:
                raise InvalidArgument("section_id is required")
            data = service.section(
                symbol=symbol, accession=accession, form=form,
                section_id=section_id, offset=max(0, int(offset)),
                limit_chars=max(1000, min(int(limit_chars), 12000)),
            )
            cite = _filing_citation(
                data["filing"], section=section_id,
                label=f"{data['section']['title'][:100]}",
                artifact=_artifact(
                    data["filing"], "semantic-section", section_id=section_id
                ),
            )
            data["filing"]["symbol"] = symbol or data["filing"].get("symbol")
            return success(
                MODULE, "report_section", data,
                symbol=symbol, cik=data["filing"].get("cik"),
                citations=[cite], started=started, cap=8192,
            )
        except Exception as exc:
            return _error("report_section", exc, started)

    @mcp.tool()
    def report_search(
        symbol: str | None = None,
        accession: str | None = None,
        form: str = "10-K",
        query: str = "",
        limit: int = 20,
    ) -> dict:
        """Search a 10-K/10-Q filing for text and table mentions in Item 7 (MD&A), risk factors, or notes.

        Args:
            symbol: Ticker; used when accession is omitted.
            accession: Explicit filing accession.
            form: Form used to resolve the latest filing.
            query: Search text (2-120 characters).
            limit: Maximum hits (1-50).
        """
        started = time.perf_counter()
        try:
            query = (query or "").strip()
            if not 2 <= len(query) <= 120:
                raise InvalidArgument("query must be 2-120 characters")
            data = service.search(
                symbol=symbol, accession=accession, form=form, query=query,
                limit=max(1, min(int(limit), 50)),
            )
            cites = [
                _filing_citation(
                    data["filing"], section=hit.get("section_id"),
                    label=_search_label(data["filing"], hit, query),
                    artifact=_search_artifact(data["filing"], hit),
                )
                for hit in data["hits"]
            ]
            return success(
                MODULE, "report_search", data, symbol=symbol,
                cik=data["filing"].get("cik"), citations=cites,
                started=started, cap=8192,
            )
        except Exception as exc:
            return _error("report_search", exc, started)

    @mcp.tool()
    def report_table(
        symbol: str | None = None,
        accession: str | None = None,
        form: str = "10-K",
        table_id: str = "",
        columns: list[int] | None = None,
        row_offset: int = 0,
        max_rows: int = 40,
    ) -> dict:
        """Render an extracted table from a 10-K/10-Q filing or its notes as a GFM markdown grid.

        Args:
            symbol: Ticker; used when accession is omitted.
            accession: Explicit filing accession.
            form: Form used to resolve the latest filing.
            table_id: Table ID from report_sections, e.g. "t14".
            columns: Optional zero-based column indexes to include.
            row_offset: Body row offset.
            max_rows: Rows per page (1-100).
        """
        started = time.perf_counter()
        try:
            if not table_id:
                raise InvalidArgument("table_id is required")
            data = service.table(
                symbol=symbol, accession=accession, form=form, table_id=table_id,
                columns=columns, row_offset=max(0, int(row_offset)),
                max_rows=max(1, min(int(max_rows), 100)),
            )
            cite = _filing_citation(
                data["filing"], section=data["table"].get("section_id"),
                label=data["table"].get("caption") or f"table {table_id}",
                artifact=_artifact(
                    data["filing"], "semantic-table",
                    section_id=data["table"].get("section_id"), table_id=table_id,
                ),
            )
            return success(
                MODULE, "report_table", data, symbol=symbol,
                cik=data["filing"].get("cik"), citations=[cite],
                started=started, cap=8192,
            )
        except Exception as exc:
            return _error("report_table", exc, started)
