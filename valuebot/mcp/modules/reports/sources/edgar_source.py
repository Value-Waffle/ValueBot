"""Reports-local SEC adapter: ticker resolution, filing index and filing HTML.

The reports module owns filing data end to end and therefore does not depend on
the fundamentals module.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Iterable

from core import citations, config
from core.errors import (
    CompanyNotFound,
    EdgarRateLimited,
    EdgarUnavailable,
    FilingNotFound,
    SymbolNotFound,
)
from core.models import FilingRef

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
        except Exception as exc:  # pragma: no cover
            raise EdgarUnavailable(f"edgartools could not be imported: {exc}") from exc
        try:
            edgar.set_identity(identity)
            edgar.configure_http(timeout=config.EDGAR_HTTP_TIMEOUT_S)
        except Exception:
            pass
        _edgar = edgar
        return _edgar


def reset() -> None:
    global _edgar
    with _lock:
        _edgar = None


def _wrap(exc: Exception) -> Exception:
    name = type(exc).__name__.lower()
    if "toomanyrequests" in name or "rate" in name:
        return EdgarRateLimited(f"SEC rate limit reached: {exc}")
    if "notfound" in name:
        return FilingNotFound(str(exc))
    return EdgarUnavailable(f"SEC request failed: {exc}")


def _source_url(cik, accession, document) -> str | None:
    """Return the filing document URL, or the accession index page as fallback.

    Never emits the legacy placeholder document name: an empty or invalid
    primary document resolves to the accession directory page.
    """
    return citations.edgar_url(
        cik, accession, document, kind="doc"
    ) or citations.edgar_url(cik, accession, kind="index")


class ReportsEdgarSource:
    api_version = 1

    def __init__(self):
        self._submissions: dict[int, tuple[float, dict]] = {}
        self._companies: dict[str, tuple[float, object]] = {}

    @staticmethod
    def _headers() -> dict:
        identity = config.require_identity()
        return {"User-Agent": identity, "Accept-Encoding": "gzip, deflate"}

    def _submissions_json(self, cik: int) -> dict:
        cached = self._submissions.get(cik)
        now = time.time()
        if cached and now - cached[0] < 12 * 60 * 60:
            return cached[1]
        import requests  # noqa: PLC0415 - lazy import

        url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
        try:
            response = requests.get(url, headers=self._headers(), timeout=config.EDGAR_HTTP_TIMEOUT_S)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise _wrap(exc) from exc
        self._submissions[cik] = (now, payload)
        return payload

    def company(self, symbol: str):
        symbol = (symbol or "").strip().upper()
        if not symbol:
            raise SymbolNotFound("empty symbol")
        cached = self._companies.get(symbol)
        if cached and time.time() - cached[0] < 12 * 60 * 60:
            return cached[1]
        edgar = _load()
        try:
            company = edgar.Company(symbol)
            if getattr(company, "not_found", False):
                raise SymbolNotFound(f"no issuer found for {symbol}")
        except (SymbolNotFound, CompanyNotFound):
            raise
        except Exception as exc:
            raise _wrap(exc) from exc
        self._companies[symbol] = (time.time(), company)
        return company

    def filings(self, symbol: str, *, forms=None, start=None, end=None) -> list[FilingRef]:
        company = self.company(symbol)
        payload = self._submissions_json(int(company.cik))
        recent = payload.get("filings", {}).get("recent", {})
        forms_list = [item.upper() for item in (forms or [])]
        refs: list[FilingRef] = []
        accessions = recent.get("accessionNumber") or []
        for index, accession in enumerate(accessions):
            form = str((recent.get("form") or [""] * len(accessions))[index] or "")
            if forms_list and form.upper() not in forms_list:
                continue
            filed = str((recent.get("filingDate") or [""] * len(accessions))[index] or "")[:10]
            period = str((recent.get("reportDate") or [""] * len(accessions))[index] or "")[:10]
            if start and period and period < start:
                continue
            if end and period and period > end:
                continue
            document = str(
                (recent.get("primaryDocument") or [""] * len(accessions))[index] or ""
            )
            refs.append(
                FilingRef(
                    symbol=symbol.upper(),
                    cik=int(company.cik),
                    accession=str(accession),
                    form=form,
                    filed=filed,
                    period_of_report=period,
                    primary_document=document,
                    source_url=_source_url(company.cik, accession, document),
                )
            )
        refs.sort(key=lambda item: (item.filed, item.accession), reverse=True)
        return refs

    @staticmethod
    def _to_ref(symbol: str, cik: int, filing) -> FilingRef | None:
        accession = (
            getattr(filing, "accession_no", None)
            or getattr(filing, "accession_number", None)
        )
        if not accession:
            return None
        primary = getattr(filing, "primary_document", None)
        if not primary:
            documents = getattr(filing, "primary_documents", None) or ()
            for document in documents:
                name = getattr(document, "document", None) or getattr(document, "filename", None)
                if name:
                    primary = name
                    break
        period = (
            getattr(filing, "period_of_report", None)
            or getattr(filing, "report_date", None)
            or ""
        )
        return FilingRef(
            symbol=symbol.upper(),
            cik=int(cik),
            accession=str(accession),
            form=str(getattr(filing, "form", "") or ""),
            filed=str(getattr(filing, "filing_date", "") or "")[:10],
            period_of_report=str(period)[:10],
            primary_document=str(primary or ""),
            source_url=_source_url(cik, accession, primary),
        )

    def _ref_from_recent(
        self, symbol: str, cik: int, *, accession: str | None = None,
        form: str | None = None,
    ) -> FilingRef | None:
        recent = self._submissions_json(int(cik)).get("filings", {}).get("recent", {})
        accessions = recent.get("accessionNumber") or []
        for index, item in enumerate(accessions):
            if accession and str(item) != accession:
                continue
            item_form = str((recent.get("form") or [""] * len(accessions))[index] or "")
            if not accession and form and item_form.upper() != form.upper():
                continue
            document = str(
                (recent.get("primaryDocument") or [""] * len(accessions))[index] or ""
            )
            return FilingRef(
                symbol=symbol.upper(),
                cik=int(cik),
                accession=str(item),
                form=item_form,
                filed=str((recent.get("filingDate") or [""] * len(accessions))[index] or "")[:10],
                period_of_report=str(
                    (recent.get("reportDate") or [""] * len(accessions))[index] or ""
                )[:10],
                primary_document=document,
                source_url=_source_url(cik, item, document),
            )
        return None

    def get_filing(self, symbol: str, *, accession: str | None = None,
                   form: str | None = None) -> FilingRef:
        company = self.company(symbol)
        ref = self._ref_from_recent(
            symbol, company.cik, accession=accession, form=form or (None if accession else "10-K")
        )
        if ref is not None:
            return ref
        edgar = _load()
        try:
            if accession:
                filing = edgar.get_by_accession_number(accession)
            else:
                filing = company.latest(form or "10-K")
        except Exception as exc:
            raise _wrap(exc) from exc
        if filing is None:
            raise FilingNotFound(
                f"no {form or '10-K'} filing for {(symbol or '').upper()}"
            )
        fallback = self._to_ref(symbol, company.cik, filing)
        if fallback is None:  # pragma: no cover - defensive
            raise FilingNotFound("filing has no accession")
        return fallback

    def filing_html(self, symbol: str, accession: str) -> tuple[str, FilingRef]:
        company = self.company(symbol)
        ref = self._ref_from_recent(symbol, company.cik, accession=accession)
        if ref is not None and ref.primary_document:
            import requests  # noqa: PLC0415 - lazy import

            try:
                response = requests.get(
                    ref.source_url, headers=self._headers(),
                    timeout=config.EDGAR_HTTP_TIMEOUT_S,
                )
                response.raise_for_status()
                html = response.text
            except Exception as exc:
                raise _wrap(exc) from exc
            if html and ("<html" in html[:4000].lower() or "<div" in html[:4000].lower()):
                return html, ref
        edgar = _load()
        try:
            filing = edgar.get_by_accession_number(accession)
            if filing is None:
                raise FilingNotFound(f"accession {accession} not found")
            html = filing.html()
        except FilingNotFound:
            raise
        except Exception as exc:
            raise _wrap(exc) from exc
        if not html:
            raise FilingNotFound(f"filing {accession} has no HTML document")
        if ref is None:
            ref = self._to_ref(symbol, company.cik, filing)
        if ref is None:  # pragma: no cover
            raise FilingNotFound(f"filing {accession} has no accession metadata")
        return html, ref
