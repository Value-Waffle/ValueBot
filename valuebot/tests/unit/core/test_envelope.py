"""Envelope, caps and paging."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core import citations  # noqa: E402
from core.envelope import fit_data  # noqa: E402
from core.errors import SymbolNotFound  # noqa: E402
from core.response import _shrink, failure, page, success  # noqa: E402

CIK = 320193
ACCESSION = "0000320193-25-000079"


def _report_citation(url: str | None = None) -> dict:
    artifact = {
        "module": "reports",
        "kind": "semantic-section",
        "cik": CIK,
        "accession": ACCESSION,
        "section_id": "part2-item7",
        "format": "md",
        "status": "cached",
    }
    return citations.cite(
        "sec-report",
        "AAPL 10-K FY2025, Item 7",
        cik=CIK,
        accession=ACCESSION,
        section="part2-item7",
        url=url,
        artifact=artifact,
    )


def _json_bytes(payload) -> int:
    return len(json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8"))


def test_success_envelope_and_cap():
    payload = success(
        "fundamentals", "facts_query",
        {"rows": [{"i": index, "text": "x" * 100} for index in range(200)]},
        symbol="AAPL", cik=320193, cap=2048,
    )
    assert payload["ok"] is True
    assert payload["module"] == "fundamentals"
    assert payload["tool"] == "facts_query"
    assert payload["symbol"] == "AAPL"
    assert payload["meta"]["bytes"] <= 2048
    assert payload["truncated"] is True


def test_failure_envelope():
    payload = failure("fundamentals", "company_profile", SymbolNotFound("nope"))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "symbol_not_found"
    assert payload["error"]["retryable"] is False


def test_page_offsets():
    window, paging = page(list(range(10)), 4, 3)
    assert window == [4, 5, 6]
    assert paging["next_offset"] == 7
    assert paging["truncated"] is True
    window, paging = page(list(range(4)), 0, 10)
    assert paging["next_offset"] is None


# -- regression: the footer is a contract field, not payload --------------


def test_footer_survives_an_oversized_section():
    citation = _report_citation(url="https://www.sec.gov/Archives/edgar/data/320193/x/")
    payload = success(
        "reports", "report_section", {"text": "x" * 8000},
        cik=CIK, citations=[citation],
        meta={"section": {"id": "part2-item7"}}, cap=8192,
    )

    assert payload["citations"], "citations must never be emptied by byte capping"
    assert payload["references"], "the reference footer must survive byte capping"
    entry = payload["references"][0]
    assert set(entry) == {"n", "label", "source", "url", "status"}
    assert "citation_id" not in entry
    assert entry["url"] == "https://www.sec.gov/Archives/edgar/data/320193/x/"
    assert entry["status"] == "cached"
    assert payload["meta"]["data_truncated"] is True
    assert payload["truncated"] is True
    assert _json_bytes(payload) <= 8192 or payload["meta"]["footer_overflow"] is True


def test_footer_survives_without_a_url():
    payload = success(
        "reports", "report_section", {"text": "x" * 8000},
        cik=CIK, citations=[_report_citation()], cap=8192,
    )

    assert payload["references"][0] == {
        "n": 1,
        "label": "AAPL 10-K FY2025, Item 7",
        "source": "sec-report",
        "status": "cached",
    }


def test_uncited_data_is_not_truncated_and_flagged():
    payload = success("analysis", "ratio_compute", {"results": [{"value": 1.0}]}, cap=8192)

    assert payload["meta"]["data_truncated"] is False
    assert "truncated" not in payload


# -- fit_data: pure and data-only -----------------------------------------


def test_fit_data_does_not_mutate_its_input():
    data = {"text": "x" * 5000, "rows": [{"t": "y" * 100} for _ in range(20)]}
    before = copy.deepcopy(data)

    fitted, truncated = fit_data(data, 1024)

    assert data == before
    assert fitted is not data
    assert truncated is True
    assert _json_bytes(fitted) <= 1024


def test_fit_data_leaves_small_payloads_untouched():
    data = {"text": "short"}

    fitted, truncated = fit_data(data, 1024)

    assert fitted == data
    assert truncated is False
    assert fitted is not data


# -- _shrink: pure and footer-safe ----------------------------------------


def test_shrink_does_not_mutate_its_input():
    original = {"data": {"rows": [{"text": "x" * 100} for _ in range(100)]}}
    before = copy.deepcopy(original)

    shrunk = _shrink(original, 512)

    assert original == before
    assert shrunk is not original
    assert _json_bytes(shrunk) <= 512


def test_shrink_never_targets_the_footer():
    payload = {
        "data": {"rows": [{"text": "x" * 200} for _ in range(50)]},
        "citations": [{"key": "a" * 100}],
        "references": [{"n": 1, "label": "L", "source": "sec-report"}],
    }

    shrunk = _shrink(payload, 512)

    assert shrunk["citations"] == payload["citations"]
    assert shrunk["references"] == payload["references"]
