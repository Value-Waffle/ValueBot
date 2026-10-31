"""Unit tests for the citation guard and ``citation_id`` addressing.

The guard is the fail-closed hook inside ``core.response.success``: a cached
fact that no citation attributes loses its value. These tests prove both
directions — cited values survive, uncited values are stripped — and that a
citation can be opened by token with no URL.
"""

from __future__ import annotations

import sys
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core import citation_guard, citations  # noqa: E402
from core.errors import CitationUnresolvable  # noqa: E402
from core.response import success  # noqa: E402

CIK = 320193
ACCESSION = "0000320193-25-000079"


def _fact_row(concept="NetIncomeLoss", period_end="2024-09-28", value=93736000000):
    return {
        "concept": concept,
        "taxonomy": "us-gaap",
        "label": "Net income",
        "unit": "USD",
        "value": value,
        "numeric_value": value,
        "period_end": period_end,
        "form_type": "10-K",
        "accession": ACCESSION,
        "filing_date": "2024-11-01",
    }


def _fact_citation(concept="NetIncomeLoss", period_end="2024-09-28"):
    artifact = {
        "module": "fundamentals",
        "kind": "facts-json",
        "cik": CIK,
        "accession": ACCESSION,
        "concept": concept,
        "period_end": period_end,
        "format": "json",
        "status": "cached",
    }
    return citations.cite(
        "sec-xbrl", "Net income, 2024-09-28", cik=CIK,
        accession=ACCESSION, period=period_end, artifact=artifact,
    )


# -- guard: cited values survive ------------------------------------------


def test_cited_fact_keeps_its_value():
    payload = success(
        "fundamentals", "facts_query", {"rows": [_fact_row()]},
        cik=CIK, citations=[_fact_citation()],
    )

    row = payload["data"]["rows"][0]
    assert row["numeric_value"] == 93736000000
    assert payload["meta"]["citation_coverage"] == {
        "values": 1, "cited": 1, "dropped": 0, "ok": True,
    }


# -- guard: uncited values are stripped -----------------------------------


def test_uncited_fact_row_is_stripped_and_flagged():
    payload = success(
        "fundamentals", "facts_query", {"rows": [_fact_row()]},
        cik=CIK, citations=[],
    )

    row = payload["data"]["rows"][0]
    assert row["numeric_value"] is None
    assert row["value"] is None
    assert row["quality"] == "uncited"
    coverage = payload["meta"]["citation_coverage"]
    assert coverage["dropped"] == 1
    assert coverage["ok"] is False
    assert coverage["uncited"][0]["concept"] == "NetIncomeLoss"


def test_citation_for_a_different_period_does_not_cover_the_row():
    payload = success(
        "fundamentals", "facts_query", {"rows": [_fact_row(period_end="2024-09-28")]},
        cik=CIK, citations=[_fact_citation(period_end="2023-09-30")],
    )

    assert payload["data"]["rows"][0]["value"] is None
    assert payload["meta"]["citation_coverage"]["dropped"] == 1


def test_metric_results_are_not_treated_as_facts():
    metric = {
        "metric_id": "debt_to_equity",
        "label": "Debt to equity",
        "value": 0.42,
        "display": "0.42",
        "period_end": "2024-12-31",
        "quality": "ok",
    }
    payload = success("analysis", "ratio_compute", {"results": [metric]})

    assert payload["data"]["results"][0]["value"] == 0.42
    assert payload["meta"]["citation_coverage"]["values"] == 0


def test_statement_rows_without_accession_are_untouched():
    statement = {
        "rows": [{"concept": "Revenues", "label": "Revenue", "values": {"FY2024": 1.0}}],
        "periods": ["FY2024"],
    }
    payload = success("fundamentals", "statement_get", statement)

    assert payload["data"]["rows"][0]["values"] == {"FY2024": 1.0}


def test_nested_fact_rows_are_checked():
    payload = success(
        "fundamentals", "facts_timeseries",
        {"points": [_fact_row(), _fact_row(concept="Assets", period_end="2024-09-28")]},
        citations=[_fact_citation()],
    )

    points = payload["data"]["points"]
    assert points[0]["value"] is not None
    assert points[1]["value"] is None
    assert payload["meta"]["citation_coverage"] == {
        "values": 2, "cited": 1, "dropped": 1, "ok": False,
        "uncited": [{"concept": "Assets", "accession": ACCESSION, "period_end": "2024-09-28"}],
    }


def test_coverage_survives_the_byte_cap():
    rows = [_fact_row(concept=f"C{index}") for index in range(60)]
    payload = success(
        "fundamentals", "facts_query", {"rows": rows},
        citations=[_fact_citation()], cap=2048,
    )

    assert "citation_coverage" in payload["meta"]


# -- citation_id addressing ------------------------------------------------


def test_citation_carries_a_citation_id_and_no_url():
    citation = _fact_citation()

    assert citation.get("citation_id")
    assert "url" not in citation
    assert citation["artifact"]["kind"] == "facts-json"


def test_citation_id_round_trips_to_the_artifact():
    citation = _fact_citation()
    artifact = citations.artifact_from_citation_id(citation["citation_id"])

    assert artifact == citation["artifact"]


def test_citation_id_is_deterministic_and_artifact_sensitive():
    first = _fact_citation()
    same = _fact_citation()
    other = _fact_citation(concept="Assets")

    assert first["citation_id"] == same["citation_id"]
    assert first["citation_id"] != other["citation_id"]


def test_malformed_citation_id_is_rejected():
    for bad in ("", "not-base64!!", "eyJhIjoxfQ"):
        try:
            citations.artifact_from_citation_id(bad)
        except CitationUnresolvable:
            continue
        raise AssertionError(f"{bad!r} should raise CitationUnresolvable")


def test_guard_is_pure_and_does_not_mutate_the_input():
    row = _fact_row()
    data = {"rows": [row]}
    citation_guard.audit(data, [])

    assert row["value"] == 93736000000  # original untouched
    assert data["rows"] is not row
