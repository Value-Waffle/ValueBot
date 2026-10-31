"""MCP tools owned by the fundamentals module."""

from __future__ import annotations

import re
import time

from core.errors import InternalError, InvalidArgument, ValuebotError
from core.response import failure, page, success

MODULE = "fundamentals"


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]
    try:
        return [str(item).strip() for item in value if str(item).strip()]
    except TypeError:
        return [str(value).strip()]


def _error(tool: str, exc: Exception, started: float) -> dict:
    if isinstance(exc, ValuebotError):
        return failure(MODULE, tool, exc, started=started)
    return failure(MODULE, tool, InternalError(str(exc)), started=started)


def register(mcp, service) -> None:
    @mcp.tool()
    def symbol_resolve(query: str, limit: int = 10) -> dict:
        """Find the ticker or company name matching a name or partial ticker,
        including SEC registrants.

        Args:
            query: Company name or ticker fragment.
            limit: Maximum matches to return (1-25).
        """
        started = time.perf_counter()
        try:
            limit = max(1, min(int(limit), 25))
            matches = service.resolve(query, limit)
            return success(
                MODULE, "symbol_resolve",
                {"query": query, "matches": matches, "count": len(matches)},
                started=started, cap=6144,
            )
        except Exception as exc:
            return _error("symbol_resolve", exc, started)

    @mcp.tool()
    def company_profile(symbol: str, refresh: bool = False) -> dict:
        """Return SEC issuer identity and cached filing and XBRL fact availability for one ticker.

        Args:
            symbol: Exact ticker, e.g. "AAPL".
            refresh: Invalidate cached profile and force a facts re-sync.
        """
        started = time.perf_counter()
        try:
            data = service.profile(symbol, refresh=bool(refresh))
            return success(
                MODULE, "company_profile", data,
                symbol=data.get("symbol"), cik=data.get("cik"),
                started=started, cap=6144,
            )
        except Exception as exc:
            return _error("company_profile", exc, started)

    @mcp.tool()
    def facts_query(
        symbol: str,
        concepts: list[str] | str | None = None,
        search: str | None = None,
        forms: list[str] | str | None = None,
        start: str | None = None,
        end: str | None = None,
        unit: str | None = None,
        annual_only: bool = False,
        dedupe: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """Query SEC-reported XBRL facts for one issuer, newest period first —
        revenue, net income, assets, cash flow and other tagged line items.

        ``start`` and ``end`` filter the fact's period end, never the filing
        date. ``forms`` filters the form that tagged the fact.

        Args:
            symbol: Exact ticker.
            concepts: Concept name(s), e.g. ["NetIncomeLoss"].
            search: Substring matched against concept names and labels.
            forms: Form filter(s), e.g. ["10-K"].
            start: Inclusive period-end lower bound (YYYY-MM-DD).
            end: Inclusive period-end upper bound (YYYY-MM-DD).
            unit: XBRL unit, e.g. "USD", "shares".
            annual_only: Keep annual duration facts only.
            dedupe: One row per concept/unit/period (latest filing).
            limit: Page size (1-100).
            offset: Zero-based row offset.
        """
        started = time.perf_counter()
        try:
            limit = max(1, min(int(limit), 100))
            data = service.facts(
                symbol,
                concepts_in=_as_list(concepts) or None,
                search=search,
                forms=_as_list(forms) or None,
                start=start,
                end=end,
                unit=unit,
                annual_only=bool(annual_only),
                dedupe=bool(dedupe),
                limit=limit,
                offset=max(0, int(offset)),
            )
            citations = data.pop("citations", [])
            return success(
                MODULE, "facts_query", data, symbol=data.get("symbol"),
                cik=data.get("cik"), citations=citations,
                paging=data.get("paging"), started=started, cap=6144,
            )
        except Exception as exc:
            return _error("facts_query", exc, started)

    @mcp.tool()
    def facts_timeseries(
        symbol: str,
        concept: str,
        annual_only: bool = True,
        start: str | None = None,
        end: str | None = None,
        unit: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return one SEC XBRL concept as a period series, newest first —
        e.g. annual revenue and net income over the last N fiscal years.

        Args:
            symbol: Exact ticker.
            concept: Concept name, e.g. "Revenues".
            annual_only: Keep annual duration facts only.
            start: Inclusive period-end lower bound.
            end: Inclusive period-end upper bound.
            unit: XBRL unit filter.
            limit: Maximum points (1-50).
        """
        started = time.perf_counter()
        try:
            data = service.timeseries(
                symbol, concept, annual_only=bool(annual_only), start=start,
                end=end, unit=unit, limit=max(1, min(int(limit), 50)),
            )
            citations = data.pop("citations", [])
            return success(
                MODULE, "facts_timeseries", data, symbol=data.get("symbol"),
                cik=data.get("cik"), citations=citations,
                started=started, cap=6144,
            )
        except Exception as exc:
            return _error("facts_timeseries", exc, started)

    @mcp.tool()
    def statement_get(
        symbol: str,
        statement: str,
        basis: str = "company",
        periods: int = 4,
        accession: str | None = None,
        offset: int = 0,
        limit: int = 40,
    ) -> dict:
        """Return a normalized annual income, balance-sheet or cash-flow
        statement from SEC filings, with period citations.

        Args:
            symbol: Exact ticker.
            statement: One of "income", "balance", "cashflow".
            basis: "company" for canonical multi-period, "filing" for as-reported.
            periods: Periods to request (2-20) for the company basis.
            accession: Filing accession for the filing basis.
            offset: Row offset.
            limit: Page size (1-80).
        """
        started = time.perf_counter()
        try:
            if statement not in {"income", "balance", "cashflow"}:
                raise InvalidArgument("statement must be income, balance or cashflow")
            if basis not in {"company", "filing"}:
                raise InvalidArgument("basis must be company or filing")
            data = service.statement(
                symbol, statement, basis=basis,
                periods=max(2, min(int(periods), 20)),
                accession=accession,
            )
            citations = data.pop("citations", [])
            rows, paging = page(data["rows"], offset, limit=max(1, min(int(limit), 80)))
            data["rows"] = rows
            return success(
                MODULE, "statement_get", data, symbol=data.get("symbol"),
                cik=data.get("cik"), citations=citations,
                paging=paging, started=started, cap=8192,
            )
        except Exception as exc:
            return _error("statement_get", exc, started)

    @mcp.tool()
    def facts_export(
        symbol: str,
        accession: str | None = None,
        concepts: list[str] | str | None = None,
        format: str = "json",
        unit: str | None = None,
    ) -> dict:
        """Export the raw SEC XBRL facts tagged in one filing as JSON, TSV or XLSX.

        Writes ``<exports>/<cik>/<accession>.concepts.<ext>`` and returns the
        path, byte size, counts and a short inline preview.

        Args:
            symbol: Exact ticker.
            accession: Filing accession; defaults to the latest 10-K with facts.
            concepts: Restrict to these concept names, e.g. ["Revenues"].
            format: "json" (companyfacts shape), "txt" (TSV) or "xlsx".
            unit: XBRL unit filter, e.g. "USD", "shares".
        """
        started = time.perf_counter()
        try:
            fmt = str(format or "json").strip().lower()
            if fmt not in {"json", "txt", "xlsx"}:
                raise InvalidArgument("format must be json, txt or xlsx")
            data = service.export(
                symbol,
                accession=accession or None,
                concepts=_as_list(concepts) or None,
                format=fmt,
                unit=unit or None,
            )
            data.pop("citations", None)
            citation = _export_citation(
                data.get("cik"), data.get("accession"), fmt
            )
            return success(
                MODULE, "facts_export", data, symbol=data.get("symbol"),
                cik=data.get("cik"), citations=[citation],
                started=started, cap=8192,
            )
        except Exception as exc:
            return _error("facts_export", exc, started)


_ARTIFACT_KINDS = {
    "json": "facts-json",
    "txt": "facts-txt",
    "xlsx": "facts-xlsx",
}


def _export_citation(cik, accession, fmt: str) -> dict:
    """Build the facts-json/facts-txt/facts-xlsx artifact citation.

    The citation carries ``citation_id`` and no link: the artifact is opened
    with ``citation_resolve`` or the ``citation_view`` inline panel. There is
    no guessed SEC page and no viewer url.
    """
    from core import citations

    artifact = {
        "module": MODULE,
        "kind": _ARTIFACT_KINDS.get(fmt, "facts-json"),
        "format": fmt,
        "cik": int(cik),
        "accession": accession,
        "status": "cached",
    }
    return citations.cite(
        "sec-xbrl",
        f"XBRL facts, {accession}",
        cik=cik,
        accession=accession,
        artifact=artifact,
    )
