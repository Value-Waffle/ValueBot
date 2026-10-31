"""Fundamentals orchestration: identity, facts mirror, statements, line items."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Sequence

from core import config
from core.envelope import chunk_text
from core.errors import (
    ArtifactNotCached,
    ArtifactTooLarge,
    CitationUnresolvable,
    InvalidArgument,
    SymbolNotFound,
    ValuebotError,
)
from core.models import (
    FactPage,
    FactSeries,
    LineItemSeries,
    NormalizedStatement,
)
from core.response import page

from .domain import statements
from .sources import edgar_source
from .store import facts_store

PROFILE_TTL = 12 * 60 * 60
STATEMENT_TTL = 24 * 60 * 60

#: Columns shared by the TSV and XLSX raw-concept exports.
EXPORT_COLUMNS = (
    "concept",
    "taxonomy",
    "unit",
    "value",
    "period_start",
    "period_end",
    "fiscal_year",
    "fiscal_period",
    "form",
    "filed",
    "accession",
)
#: Excel's practical row budget for one raw-concept export.
MAX_EXPORT_ROWS = 500_000
#: Per-export byte cap (design 3.4) and the inline preview budget.
MAX_EXPORT_BYTES = 32 * 1024 * 1024
PREVIEW_CHARS = 2000

_ARTIFACT_KINDS = {
    "json": "facts-json",
    "txt": "facts-txt",
    "xlsx": "facts-xlsx",
}


class _FundamentalsCitationResolver:
    api_version = 1

    def __init__(self, service: "FundamentalsService") -> None:
        self.service = service

    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
        return self.service.resolve_artifact(artifact, offset=offset, limit=limit)


class FundamentalsService:
    api_version = 1

    def __init__(self, source=None, db_path=None):
        self.source = source or edgar_source.EdgarSource()
        self.db_path = db_path or config.FUND_CACHE
        self._conn = None
        self._profiles: dict[str, tuple[float, object]] = {}
        self._statements: dict[tuple, tuple[float, NormalizedStatement]] = {}
        self.resolver = _FundamentalsCitationResolver(self)

    # -- infrastructure ---------------------------------------------------
    @property
    def conn(self):
        if self._conn is None:
            self._conn = facts_store.connect(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _profile(self, symbol: str):
        symbol = (symbol or "").strip().upper()
        if not symbol:
            raise SymbolNotFound("empty symbol")
        cached = self._profiles.get(symbol)
        now = time.time()
        if cached and now - cached[0] < PROFILE_TTL:
            return cached[1]
        profile = self.source.profile(symbol)
        self._profiles[symbol] = (now, profile)
        return profile

    def _ensure_facts(self, symbol: str):
        profile = self._profile(symbol)
        row = self.conn.execute(
            "SELECT facts_synced_at FROM companies WHERE cik = ?", (profile.cik,)
        ).fetchone()
        fresh = row is not None and row["facts_synced_at"] and (
            time.time() - float(row["facts_synced_at"]) < PROFILE_TTL
        )
        if not fresh:
            facts = self.source.facts(symbol)
            count = facts_store.sync_company(
                self.conn, profile, edgar_source.iter_facts(facts), fetched_at=time.time()
            )
            del facts
            edgar_source.clear_facts_cache()
            facts_store.evict_lru(
                self.conn, config.MAX_FACTS_COMPANIES, config.MAX_FUND_MB * 1024 * 1024
            )
            if count == 0:
                raise SymbolNotFound(f"no usable XBRL facts for {symbol}")
        facts_store.touch(self.conn, profile.cik, time.time())
        return profile

    # -- public API -------------------------------------------------------
    def resolve(self, query: str, limit: int = 10) -> list[dict]:
        return self.source.resolve(query, limit)

    def resolve_artifact(
        self, artifact: dict, *, offset: int = 0, limit: int = 8000
    ) -> dict:
        if not isinstance(artifact, dict) or not artifact:
            raise InvalidArgument("artifact must be a non-empty dict")
        kind = str(artifact.get("kind") or "").strip().lower()
        if kind not in {"facts-json", "facts-txt", "facts-xlsx"}:
            raise CitationUnresolvable(f"unknown fundamentals artifact kind: {kind or '<missing>'}")
        if "cik" not in artifact or "accession" not in artifact:
            raise InvalidArgument("artifact requires cik and accession")
        try:
            cik = int(artifact["cik"])
        except (TypeError, ValueError) as exc:
            raise InvalidArgument("artifact cik must be an integer") from exc
        accession = str(artifact.get("accession") or "").strip()
        if not accession:
            raise InvalidArgument("artifact accession must not be empty")

        rows = facts_store.dump_accession(
            self.conn, cik, accession, limit=MAX_EXPORT_ROWS + 1
        )
        entity = facts_store.entity_name(self.conn, cik)
        if kind == "facts-json":
            text = json.dumps(
                _companyfacts(cik, entity, accession, rows),
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
            page_data = chunk_text(text, offset=offset, limit=limit)
            return {
                "kind": kind,
                "format": "json",
                "chunk": page_data["chunk"],
                "next_offset": page_data["next_offset"],
                "total_chars": page_data["total"],
            }
        if kind == "facts-txt":
            text = _tsv(rows)
            page_data = chunk_text(text, offset=offset, limit=limit)
            return {
                "kind": kind,
                "format": "txt",
                "chunk": page_data["chunk"],
                "next_offset": page_data["next_offset"],
                "total_chars": page_data["total"],
            }

        target = (
            Path(config.FUNDAMENTALS_EXPORTS)
            / str(cik)
            / f"{accession}.concepts.xlsx"
        )
        if not target.is_file():
            raise ArtifactNotCached(
                f"facts XLSX export for {accession} is not cached",
                hint="run facts_export with format=xlsx first",
            )
        return {
            "kind": kind,
            "format": "xlsx",
            "chunk": "",
            "next_offset": None,
            "total_chars": 0,
            "path": str(target),
            "preview": _render_preview(cik, entity, accession, rows, "xlsx"),
        }

    def profile(self, symbol: str, *, refresh: bool = False) -> dict:
        symbol = (symbol or "").strip().upper()
        if refresh:
            self._profiles.pop(symbol, None)
            profile = self._profile(symbol)
            self.conn.execute(
                "UPDATE companies SET facts_synced_at = NULL WHERE cik = ?", (profile.cik,)
            )
            self.conn.commit()
        else:
            profile = self._profile(symbol)
        row = self.conn.execute(
            "SELECT fact_count, facts_synced_at FROM companies WHERE cik = ?",
            (profile.cik,),
        ).fetchone()
        data = profile.as_dict()
        data["facts_cached"] = bool(row and row["facts_synced_at"])
        data["fact_count"] = int(row["fact_count"]) if row else 0
        data["data_available"] = {
            "facts": bool(row and row["fact_count"]),
            "reports": None,
            "analysis": bool(row and row["fact_count"]),
            "thesis": None,
        }
        return data

    def facts(self, symbol: str, **kwargs) -> dict:
        profile = self._ensure_facts(symbol)
        rows, total = facts_store.query(self.conn, profile.cik, **kwargs)
        offset = int(kwargs.get("offset", 0))
        limit = int(kwargs.get("limit", 20))
        data_rows = [row.__dict__ for row in rows]
        _, paging = page(data_rows, offset, limit)
        paging["total"] = total
        paging["next_offset"] = offset + len(data_rows) if offset + len(data_rows) < total else None
        paging["truncated"] = paging["next_offset"] is not None
        citations = [
            _fact_citation(profile.cik, row) for row in rows if row.accession
        ]
        return {
            "symbol": profile.symbol,
            "cik": profile.cik,
            "rows": data_rows,
            "count": len(data_rows),
            "total": total,
            "paging": paging,
            "citations": citations,
        }

    def timeseries(self, symbol: str, concept: str, **kwargs) -> dict:
        profile = self._ensure_facts(symbol)
        annual_only = bool(kwargs.pop("annual_only", True))
        limit = int(kwargs.pop("limit", 20))
        rows = facts_store.annual_series(
            self.conn,
            profile.cik,
            concept,
            limit=limit,
            start=kwargs.get("start"),
            end=kwargs.get("end"),
            unit=kwargs.get("unit"),
            period_type="duration",
        ) if annual_only else []
        if not annual_only:
            rows, _ = facts_store.query(
                self.conn, profile.cik, concepts_in=[concept], limit=limit,
                start=kwargs.get("start"), end=kwargs.get("end"),
                unit=kwargs.get("unit"), annual_only=False, dedupe=True,
            )
        points = [
            {
                "period_end": row.period_end,
                "period_label": row.period_label,
                "duration_days": row.duration_days,
                "value": row.numeric_value,
                "unit": row.unit,
                "form": row.form_type,
                "accession": row.accession,
                "filed": row.filing_date,
            }
            for row in rows
        ]
        summary = _series_summary([row.numeric_value for row in rows])
        citations = [_fact_citation(profile.cik, row) for row in rows if row.accession]
        return {
            "symbol": profile.symbol,
            "cik": profile.cik,
            "concept": concept,
            "unit": rows[0].unit if rows else None,
            "points": points,
            "summary": summary,
            "citations": citations,
        }

    def statement(
        self,
        symbol: str,
        statement: str,
        *,
        basis: str = "company",
        periods: int = 4,
        accession: str | None = None,
        currency: str = "USD",
    ) -> dict:
        symbol = (symbol or "").strip().upper()
        if statement not in statements.LABELS:
            from core.errors import StatementUnavailable

            raise StatementUnavailable(f"unknown statement: {statement}")
        profile = self._profile(symbol)
        cache_key = (profile.cik, statement, basis, int(periods), accession)
        cached = self._statements.get(cache_key)
        if cached and time.time() - cached[0] < STATEMENT_TTL:
            normalized = cached[1]
        elif basis == "filing":
            raw = self.source.filing_statement(symbol, accession, statement)
            normalized = statements.normalize_filing(
                raw,
                symbol=symbol,
                cik=profile.cik,
                statement=statement,
                accession=accession or "",
                form="10-K",
                filed="",
                currency=currency,
            )
            self._statements[cache_key] = (time.time(), normalized)
        else:
            raw = self.source.statement(symbol, statement, periods)
            normalized = statements.normalize_company(
                raw, symbol=symbol, cik=profile.cik, statement=statement, currency=currency
            )
            self._ensure_facts(symbol)
            normalized = statements.resolve_period_ends(
                self.conn, statement, profile.cik, normalized
            )
            self._statements[cache_key] = (time.time(), normalized)

        rows = []
        for row in normalized.rows:
            rows.append(
                {
                    "concept": row.concept,
                    "label": row.label,
                    "depth": row.depth,
                    "parent": row.parent,
                    "is_total": row.is_total,
                    "unit": row.unit,
                    "values": row.values,
                }
            )
        citations = list(normalized.citations.values())
        return {
            "symbol": normalized.symbol,
            "cik": normalized.cik,
            "statement": normalized.statement,
            "label": normalized.label,
            "basis": normalized.basis,
            "unit": normalized.unit,
            "currency": normalized.currency,
            "periods": list(normalized.periods),
            "period_ends": normalized.period_ends,
            "rows": rows,
            "citations": citations,
        }

    def line_items(
        self,
        symbol: str,
        items: Sequence[str],
        *,
        periods: int = 5,
        annual_only: bool = True,
        balance_basis: str = "average",
    ) -> LineItemSeries:
        profile = self._ensure_facts(symbol)
        return facts_store.line_items(
            self.conn,
            profile.cik,
            profile.symbol,
            "USD",
            list(items),
            periods=periods,
            balance_basis=balance_basis,
        )

    def concept_vocabulary(self) -> dict[str, tuple[str, ...]]:
        from .domain import concepts

        return concepts.vocabulary()

    def export(
        self,
        symbol: str,
        accession: str | None = None,
        concepts: Sequence[str] | None = None,
        format: str = "json",
        unit: str | None = None,
    ) -> dict:
        """Write one accession's raw concepts as companyfacts JSON, TSV or XLSX."""
        fmt = str(format or "json").strip().lower()
        if fmt not in _ARTIFACT_KINDS:
            raise InvalidArgument("format must be json, txt or xlsx")
        profile = self._ensure_facts(symbol)
        accession = str(accession or "").strip() or facts_store.latest_fact_accession(
            self.conn, profile.cik
        )
        if not accession:
            raise SymbolNotFound(f"no XBRL facts cached for {profile.symbol}")

        selected = [str(item).strip() for item in (concepts or []) if str(item).strip()]
        rows = facts_store.dump_accession(
            self.conn,
            profile.cik,
            accession,
            concepts=selected or None,
            unit=unit or None,
            limit=MAX_EXPORT_ROWS + 1,
        )
        truncated = len(rows) > MAX_EXPORT_ROWS
        if truncated:
            if fmt == "xlsx":
                raise ArtifactTooLarge(
                    f"export exceeds {MAX_EXPORT_ROWS} rows; narrow it with concepts or unit"
                )
            rows = rows[:MAX_EXPORT_ROWS]

        entity = facts_store.entity_name(self.conn, profile.cik)
        root = Path(config.FUNDAMENTALS_EXPORTS)
        target = root / str(profile.cik) / f"{accession}.concepts.{fmt}"
        target.parent.mkdir(parents=True, exist_ok=True)
        preview = _render_preview(profile.cik, entity, accession, rows, fmt)
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            if fmt == "xlsx":
                _write_xlsx(temporary, rows)
            else:
                payload = (
                    json.dumps(
                        _companyfacts(profile.cik, entity, accession, rows),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        default=str,
                    )
                    if fmt == "json"
                    else _tsv(rows)
                )
                with temporary.open("wb") as handle:
                    handle.write(payload.encode("utf-8"))
                    handle.flush()
                    os.fsync(handle.fileno())
            size = temporary.stat().st_size
            if size > MAX_EXPORT_BYTES:
                raise ArtifactTooLarge(
                    f"export is {size / (1024 * 1024):.1f} MB, above the "
                    f"{MAX_EXPORT_BYTES // (1024 * 1024)} MB cap"
                )
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

        _evict_exports(root, config.MAX_EXPORTS_MB * 1024 * 1024, target.parent)
        return {
            "symbol": profile.symbol,
            "cik": profile.cik,
            "accession": accession,
            "format": fmt,
            "path": str(target),
            "bytes": size,
            "fact_count": len(rows),
            "concept_count": len({row.get("concept") for row in rows}),
            "preview": preview[:PREVIEW_CHARS],
            "truncated": truncated,
            "citations": [_export_citation(profile.cik, accession, fmt)],
        }


def _fact_citation(cik: int, row) -> dict:
    from core import citations

    artifact = {
        "module": "fundamentals",
        "kind": "facts-json",
        "cik": int(cik),
        "accession": row.accession,
        "concept": row.concept,
        "taxonomy": row.taxonomy,
        "unit": row.unit,
        "period_end": row.period_end,
        "format": "json",
        "status": "cached",
    }
    return citations.cite(
        "sec-xbrl",
        f"{row.label}, {row.period_end}",
        cik=cik,
        accession=row.accession,
        form=row.form_type,
        filed=row.filing_date,
        period=row.period_end,
        artifact=artifact,
    )


def _series_summary(values: list[float | None]) -> dict:
    numeric = [float(value) for value in values if value is not None]
    if len(numeric) < 2:
        return {"change": None, "direction": "neutral", "latest": numeric[0] if numeric else None}
    latest, oldest = numeric[0], numeric[-1]
    change = None if oldest == 0 else (latest - oldest) / abs(oldest)
    return {
        "latest": latest,
        "oldest": oldest,
        "change": change,
        "direction": "up" if latest > oldest else "down" if latest < oldest else "flat",
    }


def _number(text) -> object:
    """Render a stored fact value as a JSON number when it parses cleanly."""
    try:
        number = float(text)
    except (TypeError, ValueError):
        return text
    return int(number) if number.is_integer() else number


def _companyfacts_row(row: dict, accession: str) -> dict:
    item = {
        "end": row.get("period_end"),
        "val": _number(row.get("value")),
        "accn": accession,
        "fy": row.get("fiscal_year"),
        "fp": row.get("fiscal_period"),
        "form": row.get("form"),
        "filed": row.get("filed"),
    }
    if row.get("period_start"):
        item["start"] = row["period_start"]
    return item


def _companyfacts(cik: int, entity: str, accession: str, rows: list[dict]) -> dict:
    """Group raw rows into the SEC companyfacts shape."""
    facts: dict[str, dict[str, dict]] = {}
    for row in rows:
        taxonomy = row.get("taxonomy") or "us-gaap"
        concept = row.get("concept") or ""
        entry = facts.setdefault(taxonomy, {}).setdefault(
            concept,
            {"label": row.get("label") or concept, "description": "", "units": {}},
        )
        entry["units"].setdefault(row.get("unit") or "", []).append(
            _companyfacts_row(row, accession)
        )
    return {"cik": int(cik), "entityName": entity, "facts": facts}


def _cell(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _tsv(rows: list[dict]) -> str:
    lines = ["\t".join(EXPORT_COLUMNS)]
    for row in rows:
        lines.append("\t".join(_cell(row.get(name)) for name in EXPORT_COLUMNS))
    return "\n".join(lines) + "\n"


def _render_preview(
    cik: int, entity: str, accession: str, rows: list[dict], fmt: str
) -> str:
    if fmt == "json":
        payload = json.dumps(
            _companyfacts(cik, entity, accession, rows),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return payload[:PREVIEW_CHARS]
    if fmt == "txt":
        return _tsv(rows)[:PREVIEW_CHARS]
    return _tsv(rows[:10])[:PREVIEW_CHARS]


def _write_xlsx(path: Path, rows: list[dict]) -> None:
    from openpyxl import Workbook

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("facts")
    sheet.append(list(EXPORT_COLUMNS))
    for row in rows:
        sheet.append([row.get(name) for name in EXPORT_COLUMNS])
    workbook.save(str(path))


def _export_citation(cik: int, accession: str, fmt: str) -> dict:
    from core import citations

    artifact = {
        "module": "fundamentals",
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


def _folder_bytes(folder: Path) -> int:
    total = 0
    for path in folder.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total


def _folder_mtime(folder: Path) -> float:
    newest = 0.0
    for path in folder.rglob("*"):
        if path.is_file():
            try:
                newest = max(newest, path.stat().st_mtime)
            except OSError:
                continue
    return newest


def _evict_exports(root: Path, max_bytes: int, keep: Path) -> None:
    """Delete the oldest export folders until the module total fits the cap."""
    if not root.exists():
        return
    folders = [path for path in root.iterdir() if path.is_dir()]
    total = sum(_folder_bytes(path) for path in folders)
    for folder in sorted(folders, key=_folder_mtime):
        if total <= max_bytes:
            break
        if folder == keep:
            continue
        size = _folder_bytes(folder)
        shutil.rmtree(folder, ignore_errors=True)
        total -= size
