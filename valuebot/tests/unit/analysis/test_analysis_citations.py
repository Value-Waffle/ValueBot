"""Analysis citations: derived-analysis artifacts and the derived-inputs resolver."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core.errors import ArtifactNotCached  # noqa: E402
from core.models import LineItemSeries, LineItemValue  # noqa: E402
from modules.analysis.service import AnalysisService  # noqa: E402
from modules.analysis.tools import register  # noqa: E402

PERIODS = ("2025-09-30", "2024-09-30", "2023-09-30", "2022-09-30")

VALUES = {
    "gross_profit": (60, 55, 50, 45),
    "revenue": (100, 95, 90, 85),
    "current_assets": (40, 38, 36, 34),
    "current_liabilities": (25, 24, 23, 22),
    "operating_income": (20, 19, 18, 17),
    "pretax_income": (18, 17, 16, 15),
    "income_tax": (4, 4, 3, 3),
    "da": (5, 5, 5, 4),
    "capex": (6, 6, 5, 5),
    "total_debt": (30, 29, 28, 27),
    "cash": (10, 9, 8, 7),
    "shares_diluted": (10, 10, 10, 10),
}


class FakeFacts:
    """Minimal line-item provider; counts calls to prove resolve never computes."""

    def __init__(self):
        self.calls = 0

    def line_items(self, symbol, items, *, periods=5, balance_basis="average"):
        self.calls += 1
        selected = PERIODS[: max(1, int(periods))]
        payload = {}
        for item in items:
            if item not in VALUES:
                continue
            payload[item] = tuple(
                LineItemValue(
                    line_item=item,
                    label=item.replace("_", " ").title(),
                    unit="shares" if item == "shares_diluted" else "USD",
                    period_end=period,
                    value=VALUES[item][index],
                    concept=f"Concept{item.title().replace('_', '')}",
                    citation={
                        "key": f"{item}-{period}",
                        "label": f"{item} {period}",
                        "source": "sec-xbrl",
                        "accession": "0000000000-25-000001",
                        "period": period,
                    },
                )
                for index, period in enumerate(selected)
            )
        return LineItemSeries(
            symbol=symbol.upper(),
            cik=1,
            currency="USD",
            periods=selected,
            items=payload,
            facts_version="1:1",
        )


class FakeMcp:
    def __init__(self):
        self.tools: dict = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def build(tmp_path):
    facts = FakeFacts()
    service = AnalysisService(facts, cache_path=tmp_path / "analysis.sqlite")
    mcp = FakeMcp()
    register(mcp, service)
    return facts, service, mcp


def ratio_payload(mcp, periods=2):
    payload = mcp.tools["ratio_compute"]("TEST", ["gross_margin"], periods=periods)
    assert payload["ok"], payload
    return payload


def test_ratio_compute_emits_derived_analysis_citation_per_result(tmp_path):
    _facts, service, mcp = build(tmp_path)
    try:
        payload = ratio_payload(mcp)
    finally:
        service.close()

    data = payload["data"]
    results = data["results"]
    assert len(results) == 2
    derived = [c for c in payload["citations"] if c.get("source") == "derived-analysis"]
    assert len(derived) == len(results)
    # Derived citations lead the list so the openable artifact survives the cap.
    assert payload["citations"][: len(derived)] == derived

    for result, citation in zip(results, derived):
        assert citation["label"] == f"{result['label']}, {result['period_end']}"
        assert citation["artifact"] == {
            "module": "analysis",
            "kind": "derived-inputs",
            "cik": data["cik"],
            "metric_id": result["metric_id"],
            "period_end": result["period_end"],
            "balance_basis": data["balance_basis"],
            "facts_version": data["facts_version"],
            "format": "json",
            "status": "cached",
        }
        assert citation["derived_from"] == [
            item["citation"] for item in result["inputs"]
        ]
        assert citation["derived_from"]
        assert citation["key"]
        # A citation is an identifier: no url, whatever the viewer state.
        assert citation.get("url") is None
        assert "url" not in citation
        assert citation["citation_id"]

    # The underlying sec-xbrl citations still follow the derived ones.
    input_citations = [
        item["citation"] for result in results for item in result["inputs"]
    ]
    assert input_citations
    for citation in input_citations:
        assert citation in payload["citations"]


def test_derived_citation_is_link_free_when_the_viewer_is_enabled(tmp_path):
    from core import artifact_viewer

    assert artifact_viewer.start(0) is not None
    facts, service, mcp = build(tmp_path)
    try:
        payload = ratio_payload(mcp)
        derived = [
            c for c in payload["citations"] if c.get("source") == "derived-analysis"
        ]
        assert derived
        for citation in derived:
            assert citation["citation_id"]
            assert "url" not in citation
    finally:
        service.close()
        artifact_viewer.stop()


def test_resolve_serves_cached_payload_without_recomputing(tmp_path):
    facts, service, mcp = build(tmp_path)
    try:
        payload = ratio_payload(mcp)
        result = payload["data"]["results"][0]
        artifact = next(
            citation["artifact"]
            for citation in payload["citations"]
            if citation.get("source") == "derived-analysis"
            and citation["artifact"]["period_end"] == result["period_end"]
        )

        calls_before = facts.calls
        first = service.resolve(artifact, offset=0, limit=60)
        assert facts.calls == calls_before, "resolve must not compute metrics"

        assert first["kind"] == "derived-inputs"
        assert first["format"] == "json"
        assert first["total_chars"] > 0

        text = first["chunk"]
        offset = first["next_offset"]
        pages = 1
        while offset is not None:
            page = service.resolve(artifact, offset=offset, limit=60)
            text += page["chunk"]
            offset = page["next_offset"]
            pages += 1
        assert facts.calls == calls_before, "resolve must not compute metrics"
    finally:
        service.close()

    assert pages > 1, "the payload should have paged"
    assert len(text) == first["total_chars"]

    bundle = json.loads(text)
    assert bundle["metric_id"] == "gross_margin"
    assert bundle["label"] == "Gross margin"
    assert bundle["formula"] == "gross_profit / revenue"
    assert bundle["formula_version"] == 1
    assert bundle["quality"] == "ok"
    assert bundle["value"] == pytest.approx(0.6)
    assert bundle["display"] == "60.0%"
    assert bundle["unit"] == "percent"
    assert bundle["period_end"] == result["period_end"]
    assert bundle["inputs"] == [
        {
            "line_item": item["line_item"],
            "label": item["label"],
            "value": item["value"],
            "unit": item["unit"],
            "concept": item["concept"],
            "period_end": item["period_end"],
            "citation": item["citation"],
        }
        for item in result["inputs"]
    ]


def test_resolve_raises_artifact_not_cached_on_miss(tmp_path):
    facts, service, _mcp = build(tmp_path)
    try:
        artifact = {
            "module": "analysis",
            "kind": "derived-inputs",
            "cik": 1,
            "metric_id": "gross_margin",
            "period_end": PERIODS[0],
            "balance_basis": "average",
            "facts_version": "1:1",
            "format": "json",
            "status": "cached",
        }
        with pytest.raises(ArtifactNotCached) as excinfo:
            service.resolve(artifact)
        assert facts.calls == 0, "a cache miss must not compute the metric"
    finally:
        service.close()

    assert "ratio_compute" in (excinfo.value.hint or "")
    assert excinfo.value.code == "artifact_not_cached"


def test_dcf_compute_citations_carry_no_derived_artifact(tmp_path):
    _facts, service, mcp = build(tmp_path)
    try:
        payload = mcp.tools["dcf_compute"]("TEST", assumptions_only=True)
    finally:
        service.close()

    assert payload["ok"], payload
    citations = payload["citations"]
    assert citations
    for citation in citations:
        assert citation.get("source") != "derived-analysis"
        assert "derived_from" not in citation
        assert (citation.get("artifact") or {}).get("kind") != "derived-inputs"
    assert all(citation.get("artifact") is None for citation in citations)
