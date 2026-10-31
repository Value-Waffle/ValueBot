"""Unit tests for :mod:`mcp.evidence_view` — inline evidence rendering."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core import artifact_viewer, citations, evidence_view  # noqa: E402
from core.errors import ArtifactNotCached  # noqa: E402

_ARTIFACT = {
    "module": "reports",
    "kind": "semantic-section",
    "cik": 320193,
    "accession": "0000320193-25-000079",
    "section_id": "part2-item7",
    "format": "md",
    "status": "cached",
}


class _FakeResolver:
    api_version = 1

    def __init__(self, chunk: str = "revenue grew <b>12%</b>") -> None:
        self.chunk = chunk
        self.calls: list[tuple[dict, int, int]] = []

    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
        self.calls.append((artifact, offset, limit))
        return {
            "kind": artifact.get("kind"),
            "format": artifact.get("format", "md"),
            "chunk": self.chunk,
            "next_offset": 42,
            "total_chars": 100,
        }


class _NotCachedResolver:
    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
        raise ArtifactNotCached(
            "reports artifact not cached",
            hint="run report_section first to build the semantic artifact",
        )


@pytest.fixture(autouse=True)
def _clean_registry():
    citations.clear_resolvers()
    yield
    citations.clear_resolvers()


def test_render_html_escapes_the_chunk():
    rendered = evidence_view.render_html(
        {
            "kind": "semantic-section",
            "format": "md",
            "chunk": "<script>alert(1)</script> ok",
            "total_chars": 30,
        }
    )

    assert "&lt;script&gt;alert(1)&lt;/script&gt; ok" in rendered
    assert "<script>" not in rendered
    assert "<pre>" in rendered


def test_render_html_is_self_contained_and_carries_metadata():
    rendered = evidence_view.render_html(
        {"kind": "semantic-section", "format": "md", "chunk": "body", "total_chars": 4}
    )

    assert rendered.lstrip().lower().startswith("<!doctype html")
    assert "<style>" in rendered and "</style>" in rendered
    assert rendered.rstrip().endswith("</html>")
    assert "kind: <code>semantic-section</code>" in rendered
    assert "format: <code>md</code>" in rendered
    assert "chars: 4" in rendered


def test_render_html_escapes_metadata_and_title():
    rendered = evidence_view.render_html(
        {"kind": "<img src=x>", "format": "md", "chunk": "", "total_chars": 0}
    )

    assert "<img src=x>" not in rendered
    assert "&lt;img src=x&gt;" in rendered


def test_render_html_passes_footer_html_through_as_markup():
    footer = '<a href="/a?format=raw">raw</a>'

    rendered = evidence_view.render_html(
        {"kind": "k", "format": "md", "chunk": "x", "total_chars": 1},
        footer_html=footer,
    )

    assert footer in rendered
    assert rendered.index("<pre>") < rendered.index(footer)


def test_render_html_omits_an_empty_footer():
    rendered = evidence_view.render_html({"chunk": "x"})

    assert "<pre>x</pre>" in rendered
    assert rendered.count("<p>") == 1


def test_ui_uri_shape_is_opaque_and_namespaced():
    assert evidence_view.ui_uri("abc123") == "ui://valuebot/evidence/abc123"
    assert evidence_view.ui_uri("").startswith("ui://valuebot/evidence/")


def test_build_returns_html_and_mime_type_for_a_resolved_artifact():
    resolver = _FakeResolver("<script>alert(1)</script> evidence")
    citations.register_resolver("reports", resolver)
    token = citations.citation_id(_ARTIFACT)
    assert token

    view = evidence_view.build(
        {"artifact": _ARTIFACT, "citation_id": token}, offset=0, limit=4000
    )

    assert view["uri"] == f"ui://valuebot/evidence/{token}"
    assert view["mime_type"] == "text/html"
    assert view["kind"] == "semantic-section"
    assert view["format"] == "md"
    assert view["next_offset"] == 42
    assert view["total_chars"] == 100
    assert view["html"].lstrip().lower().startswith("<!doctype html")
    assert "&lt;script&gt;" in view["html"]
    assert "<script>" not in view["html"]
    assert resolver.calls == [(_ARTIFACT, 0, 4000)]


def test_build_derives_the_uri_from_the_artifact_when_no_token_is_given():
    citations.register_resolver("reports", _FakeResolver())
    token = citations.citation_id(_ARTIFACT)

    view = evidence_view.build({"artifact": _ARTIFACT})

    assert view["uri"] == f"ui://valuebot/evidence/{token}"


def test_build_propagates_artifact_not_cached():
    citations.register_resolver("reports", _NotCachedResolver())

    with pytest.raises(ArtifactNotCached):
        evidence_view.build({"artifact": _ARTIFACT})


def test_viewer_page_delegates_to_the_shared_renderer(monkeypatch):
    calls: dict = {}

    def fake_render(payload, *, title="", footer_html=""):
        calls.update(payload=payload, title=title, footer=footer_html)
        return "SENTINEL"

    monkeypatch.setattr(evidence_view, "render_html", fake_render)

    body = artifact_viewer._page(
        {"kind": "semantic-section", "format": "md", "chunk": "<b>x</b>", "total_chars": 3},
        {"t": ["token"]},
        "<b>x</b>",
    )

    assert body == "SENTINEL"
    assert calls["payload"]["chunk"] == "<b>x</b>"
    assert calls["payload"]["kind"] == "semantic-section"
    assert calls["title"] == "valuebot artifact semantic-section"
    assert "raw" in calls["footer"]
