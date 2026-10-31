"""Regression: ``citation_view`` shows evidence without leaking an address.

The model copies what the tool hands it. A ``ui://`` URI (or the base64 token
it embeds) in the text summary therefore ends up in user-facing prose, where
nobody can use it. The URI belongs to the embedded resource block only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402

from core import artifact_viewer, citations  # noqa: E402

_ARTIFACT = {
    "module": "reports",
    "kind": "semantic-section",
    "cik": 320193,
    "accession": "0000320193-25-000079",
    "section_id": "part2-item7",
    "format": "md",
    "status": "cached",
}
#: Any opaque token: a long unbroken base64url run.
_BASE64_RUN = re.compile(r"[A-Za-z0-9_-]{20,}={0,2}")


class _Resolver:
    api_version = 1

    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
        return {
            "kind": artifact.get("kind"),
            "format": artifact.get("format", "md"),
            "chunk": "revenue grew 12%",
            "next_offset": 42,
            "total_chars": 100,
        }


@pytest.fixture(autouse=True)
def _registry():
    citations.clear_resolvers()
    artifact_viewer.stop()
    citations.register_resolver("reports", _Resolver())
    yield
    citations.clear_resolvers()


def _citation() -> dict:
    return citations.cite(
        "sec-report",
        "AAPL 10-K FY2025, Item 7",
        cik=320193,
        accession="0000320193-25-000079",
        section="part2-item7",
        artifact=dict(_ARTIFACT),
    )


def _summary(content) -> str:
    assert content[0].type == "text"
    return content[0].text


def test_text_summary_leaks_neither_a_uri_nor_a_base64_token():
    citation = _citation()

    content = server.citation_view(citation=citation)

    summary = _summary(content)
    assert "ui://" not in summary
    assert citation["citation_id"] not in summary
    assert _BASE64_RUN.search(summary) is None
    assert "kind: semantic-section" in summary
    assert "format: md" in summary
    assert "chars: 100" in summary


def test_resource_block_still_carries_the_ui_address():
    citation = _citation()

    content = server.citation_view(citation=citation)

    assert len(content) == 2
    block = content[1]
    assert block.type == "resource"
    assert block.resource.uri == f"ui://valuebot/evidence/{citation['citation_id']}"
    assert block.resource.mime_type == "text/html"


def test_a_citation_dict_and_its_token_resolve_identically():
    citation = _citation()

    by_dict = server.citation_view(citation=citation)
    by_token = server.citation_view(citation_id=citation["citation_id"])

    assert _summary(by_dict) == _summary(by_token)
    assert by_dict[1].resource.uri == by_token[1].resource.uri
    assert by_dict[1].resource.text == by_token[1].resource.text


def test_neither_argument_is_an_invalid_argument_not_a_crash():
    content = server.citation_view()

    assert "invalid_argument" in _summary(content)
