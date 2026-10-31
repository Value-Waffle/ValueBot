"""edgartools boundary owned by the fundamentals module.

edgartools is imported lazily so server boot and ``ping`` do not depend on the
library. All outbound SEC requests share one User-Agent from
``config.SEC_USER_AGENT``; ``get_identity()`` is never called because it
prompts interactively and would hang stdio.
"""

from __future__ import annotations

import os
import threading
from typing import Iterable

from core import config
from core.errors import (
    CompanyNotFound,
    EdgarRateLimited,
    EdgarUnavailable,
    IdentityNotConfigured,
    StatementUnavailable,
    SymbolNotFound,
)
from core.models import CompanyProfile, CompanyRef

_lock = threading.Lock()
_edgar = None


def _load():
    global _edgar
    with _lock:
        if _edgar is not None:
            return _edgar
        identity = config.require_identity()
        os.environ["EDGAR_IDENTITY"] = identity
        os.environ["EDGAR_LOCAL_DATA_DIR"] = str(config.EDGAR_CACHE)
        os.environ["EDGAR_RATE_LIMIT_PER_SEC"] = str(config.EDGAR_RATE_LIMIT_PER_SEC)
        os.environ["EDGAR_HTTP_TIMEOUT"] = str(config.EDGAR_HTTP_TIMEOUT_S)
        try:
            import edgar  # noqa: PLC0415 - deliberate lazy import
        except Exception as exc:  # pragma: no cover - import failure
            raise EdgarUnavailable(
                f"edgartools could not be imported: {exc}",
                hint="Install the plugin dependencies with uv sync.",
            ) from exc
        try:
            edgar.set_identity(identity)
            edgar.configure_http(timeout=config.EDGAR_HTTP_TIMEOUT_S)
        except Exception:
            pass
        _edgar = edgar
        return _edgar


def reset() -> None:
    """Test hook: drop the cached edgartools module handle."""
    global _edgar
    with _lock:
        _edgar = None


def _wrap(exc: Exception) -> Exception:
    name = type(exc).__name__.lower()
    if "toomanyrequests" in name or "rate" in name:
        return EdgarRateLimited(f"SEC rate limit reached: {exc}")
    if "notfound" in name:
        return CompanyNotFound(str(exc))
    return EdgarUnavailable(f"SEC request failed: {exc}")


class EdgarSource:
    api_version = 1

    def _company(self, symbol: str):
        symbol = (symbol or "").strip().upper()
        if not symbol:
            raise SymbolNotFound("empty symbol")
        edgar = _load()
        try:
            company = edgar.Company(symbol)
            if getattr(company, "not_found", False):
                raise SymbolNotFound(f"no issuer found for {symbol}")
            return company
        except (SymbolNotFound, CompanyNotFound):
            raise
        except Exception as exc:
            raise _wrap(exc) from exc

    @staticmethod
    def _ticker_rows(tickers) -> list[dict]:
        """Normalize edgartools' ticker table (DataFrame, Arrow or dict)."""
        if tickers is None:
            return []
        if hasattr(tickers, "to_dict") and hasattr(tickers, "columns"):
            try:
                return [dict(row) for row in tickers.to_dict("records")]
            except (TypeError, ValueError):  # pragma: no cover - defensive
                return []
        if hasattr(tickers, "to_pylist"):  # pyarrow.Table
            return [dict(row) for row in tickers.to_pylist()]
        if isinstance(tickers, dict):
            rows: list[dict] = []
            for key, entry in tickers.items():
                if not isinstance(entry, dict):
                    continue
                row = dict(entry)
                if "cik" not in row and "cik_str" not in row:
                    row["cik"] = key
                rows.append(row)
            return rows
        return []

    def resolve(self, query: str, limit: int = 10) -> list[dict]:
        query = (query or "").strip()
        if not query:
            raise SymbolNotFound("empty query")
        edgar = _load()
        try:
            tickers = edgar.get_company_tickers()
        except Exception as exc:
            raise _wrap(exc) from exc
        needle = query.upper()
        matches: list[dict] = []
        for entry in self._ticker_rows(tickers):
            symbol = str(entry.get("ticker") or "").upper()
            name = str(entry.get("company") or entry.get("title") or entry.get("name") or "")
            cik = entry.get("cik") or entry.get("cik_str") or 0
            if not symbol:
                continue
            score = 0
            if symbol == needle:
                score = 3
            elif symbol.startswith(needle):
                score = 2
            elif needle in symbol or needle in name.upper():
                score = 1
            if score:
                matches.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "cik": int(str(cik).strip() or 0),
                        "score": score,
                    }
                )
        matches.sort(key=lambda item: (-item["score"], item["symbol"]))
        return matches[: max(0, int(limit))]

    def profile(self, symbol: str) -> CompanyProfile:
        company = self._company(symbol)
        tickers = getattr(company, "tickers", None) or ()
        if isinstance(tickers, str):
            tickers = (tickers,)
        return CompanyProfile(
            symbol=(symbol or "").upper(),
            cik=int(company.cik),
            name=str(getattr(company, "name", "") or ""),
            tickers=tuple(str(item) for item in tickers),
            exchange=str(getattr(company, "exchange", "") or ""),
            sic=str(getattr(company, "sic", "") or ""),
            industry=str(getattr(company, "industry", "") or ""),
            fiscal_year_end=str(getattr(company, "fiscal_year_end", "") or ""),
            filer_category=str(getattr(company, "filer_category", "") or ""),
            is_foreign=bool(getattr(company, "is_foreign", False)),
        )

    def company_ref(self, symbol: str) -> CompanyRef:
        profile = self.profile(symbol)
        return CompanyRef(profile.symbol, profile.cik, profile.name)

    def facts(self, symbol: str):
        company = self._company(symbol)
        try:
            facts = company.get_facts()
        except Exception as exc:
            raise _wrap(exc) from exc
        if facts is None:
            raise StatementUnavailable(
                f"no XBRL company facts for {(symbol or '').upper()}",
                hint="The issuer may not file XBRL with the SEC.",
            )
        return facts

    _STATEMENT_METHODS = {
        "income": "income_statement",
        "balance": "balance_sheet",
        "cashflow": "cashflow_statement",
    }

    def statement(self, symbol: str, statement: str, periods: int = 4):
        company = self._company(symbol)
        method_name = self._STATEMENT_METHODS.get(statement)
        if method_name is None:
            raise StatementUnavailable(f"unknown statement: {statement}")
        method = getattr(company, method_name, None)
        if method is None:  # pragma: no cover - version guard
            raise StatementUnavailable(f"edgartools has no {method_name}")
        try:
            result = method(periods=max(2, min(int(periods), 20)), period="annual")
        except Exception as exc:
            raise _wrap(exc) from exc
        if result is None:
            raise StatementUnavailable(
                f"no annual {statement} data for {(symbol or '').upper()}"
            )
        return result

    def filing_statement(self, symbol: str, accession: str | None, statement: str):
        edgar = _load()
        try:
            if accession:
                filing = edgar.get_by_accession_number(accession)
            else:
                company = self._company(symbol)
                filing = company.latest("10-K")
            if filing is None:
                raise StatementUnavailable("filing not found")
            obj = filing.obj()
            financials = getattr(obj, "financials", None) if obj else None
            if financials is None:
                raise StatementUnavailable("filing has no XBRL financial statements")
            method_name = self._STATEMENT_METHODS.get(statement)
            method = getattr(financials, method_name, None) if method_name else None
            if method is None:
                raise StatementUnavailable(f"unknown statement: {statement}")
            result = method()
            if result is None:
                raise StatementUnavailable("statement unavailable in this filing")
            return result
        except (StatementUnavailable, CompanyNotFound):
            raise
        except Exception as exc:
            raise _wrap(exc) from exc


def clear_facts_cache() -> None:
    """Clear edgartools' one-company cache, but never import it just for this."""
    if _edgar is None:
        return
    try:
        _edgar.clear_company_facts_cache()
    except Exception:
        pass


def iter_facts(facts) -> Iterable:
    try:
        return iter(facts)
    except TypeError:  # pragma: no cover - defensive
        return iter(())
