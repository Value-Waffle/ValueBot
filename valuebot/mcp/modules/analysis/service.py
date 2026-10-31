"""Analysis orchestration: metric computation, cache and DCF."""

from __future__ import annotations

import json

from core import config
from core.envelope import chunk_text
from core.errors import ArtifactNotCached, InvalidArgument
from core.ttl_cache import SqliteTtlCache

from .domain import dcf, engine, metrics

CACHE_TTL = 24 * 60 * 60
DERIVED_KIND = "derived-inputs"

#: Fields of a cached metric row exposed by the derived-inputs artifact.
BUNDLE_FIELDS = (
    "metric_id", "label", "formula", "formula_version", "quality",
    "value", "display", "unit", "period_end", "inputs",
)

DCF_ITEMS = (
    "revenue", "operating_income", "pretax_income", "income_tax", "da", "capex",
    "current_assets", "current_liabilities", "total_debt", "cash", "shares_diluted",
)


class AnalysisService:
    api_version = 1

    def __init__(self, facts, cache_path=None):
        if facts is None:
            raise InvalidArgument("analysis requires a line-item provider")
        self.facts = facts
        self._cache = SqliteTtlCache(cache_path or config.ANALYSIS_CACHE)

    def close(self) -> None:
        self._cache.close()

    def _key(self, cik, metric_id, period, basis, version, facts_version) -> str:
        return (
            f"metric:{cik}:{metric_id}:{period}:{basis}:{version}:{facts_version}"
        )

    def catalog(self, symbol: str | None = None, family: str | None = None) -> dict:
        entries = metrics.catalog()
        if family:
            entries = [entry for entry in entries if entry["family"] == family]
        available = None
        currency = None
        if symbol:
            union = sorted({item for entry in entries for item in entry["line_items"]})
            series = self.facts.line_items(symbol, union, periods=1)
            currency = series.currency
            available = {}
            for entry in entries:
                present = {
                    item for item in entry["line_items"]
                    if series.items.get(item)
                }
                entry["available"] = set(entry["line_items"]).issubset(present)
                entry["missing_line_items"] = sorted(set(entry["line_items"]) - present)
        return {
            "symbol": symbol,
            "currency": currency,
            "family": family,
            "metrics": entries,
            "count": len(entries),
        }

    def compute(
        self,
        symbol: str,
        metric_ids,
        *,
        periods: int = 5,
        balance_basis: str = "average",
        include_inputs: bool = True,
    ) -> dict:
        if isinstance(metric_ids, str):
            metric_ids = [item.strip() for item in metric_ids.replace(";", ",").split(",") if item.strip()]
        metric_ids = list(metric_ids or [])
        if not metric_ids:
            raise InvalidArgument("metric_ids must not be empty")
        definitions = [metrics.get(metric_id) for metric_id in metric_ids]
        if balance_basis not in {"average", "ending"}:
            raise InvalidArgument("balance_basis must be average or ending")

        union = sorted({item for definition in definitions for item in definition.line_items})
        lookback = max([definition.window for definition in definitions] + [0])
        fetched_periods = max(1, min(int(periods) + lookback, 20))
        series = self.facts.line_items(
            symbol, union, periods=fetched_periods,
            balance_basis=balance_basis,
        )
        selected_periods = list(series.periods)[: max(1, int(periods))]
        results = []
        for definition in definitions:
            for period in selected_periods:
                key = self._key(
                    series.cik, definition.metric_id, period, balance_basis,
                    definition.version, series.facts_version,
                )
                cached = self._cache.get(key)
                if cached is not None:
                    results.append(cached)
                    continue
                result = engine.compute_one(series, definition.metric_id, period)
                payload = result.__dict__
                self._cache.set(key, payload, CACHE_TTL, bucket="metrics")
                results.append(payload)
        if not include_inputs:
            for result in results:
                result["inputs"] = []
        return {
            "symbol": series.symbol,
            "cik": series.cik,
            "currency": series.currency,
            "periods": selected_periods,
            "balance_basis": balance_basis,
            "facts_version": series.facts_version,
            "results": results,
            "count": len(results),
        }

    def dcf(self, symbol: str, *, overrides: dict | None = None,
            assumptions_only: bool = False) -> dict:
        series = self.facts.line_items(
            symbol, DCF_ITEMS, periods=6, balance_basis="ending"
        )
        return dcf.run(series, overrides=overrides, assumptions_only=assumptions_only)

    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
        """Serve a ``derived-inputs`` artifact from the metric cache.

        Never computes a metric: a cache miss raises :class:`ArtifactNotCached`
        so the caller knows to run ``ratio_compute`` first.
        """
        artifact = artifact or {}
        metric_id = str(artifact.get("metric_id") or "")
        period_end = artifact.get("period_end")
        key = self._key(
            artifact.get("cik"),
            metric_id,
            period_end,
            artifact.get("balance_basis", "average"),
            metrics.get(metric_id).version,
            artifact.get("facts_version", ""),
        )
        cached = self._cache.get(key)
        if cached is None:
            raise ArtifactNotCached(
                f"derived inputs for {metric_id} at {period_end} are not cached",
                hint="run ratio_compute for this metric first",
            )
        bundle = {field: cached.get(field) for field in BUNDLE_FIELDS}
        bundle["metric_id"] = bundle["metric_id"] or metric_id
        bundle["inputs"] = bundle["inputs"] or []
        text = json.dumps(bundle, indent=2, ensure_ascii=False, default=str)
        page = chunk_text(text, offset=offset, limit=limit)
        return {
            "kind": DERIVED_KIND,
            "format": "json",
            "chunk": page["chunk"],
            "next_offset": page["next_offset"],
            "total_chars": page["total"],
        }
