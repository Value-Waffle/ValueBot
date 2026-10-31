"""Thesis vault: reads, paging and traversal rejection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

VALUEBOT = Path(__file__).resolve().parents[3]
MCP_DIR = VALUEBOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core import config  # noqa: E402
from core.errors import (  # noqa: E402
    ArtifactNotCached,
    CitationUnresolvable,
    InvalidArgument,
)
from modules.thesis import service  # noqa: E402


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    root = tmp_path / "theses"
    (root / "AAPL" / ".thesis" / "annotations").mkdir(parents=True)
    (root / "AAPL" / "thesis.md").write_text(
        "---\ntitle: Apple thesis\nticker: AAPL\n---\n\n# Thesis\n\nServices growth.\n",
        encoding="utf-8",
    )
    (root / "AAPL" / ".thesis" / "annotations" / "thesis.json").write_text(
        json.dumps({"mtime": 1, "annotations": [{"text": "watch margins"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("VW_THESIS_ROOT", str(root))
    config.refresh()
    yield root
    config.refresh()


def test_read_thesis(vault):
    result = service.thesis_read("AAPL")
    assert result["ok"] is True
    assert result["has_thesis"] is True
    assert result["front_matter"]["title"] == "Apple thesis"
    assert "Services growth" in result["body"]
    assert result["citations"]


def test_annotations(vault):
    result = service.thesis_annotations("AAPL")
    assert result["ok"] is True
    assert result["count"] == 1
    document = service.thesis_annotations("AAPL", doc="thesis")
    assert document["ok"] is True
    assert document["total"] == 1


def test_missing_vault_is_a_normal_empty_result(tmp_path, monkeypatch):
    monkeypatch.setenv("VW_THESIS_ROOT", str(tmp_path / "absent"))
    config.refresh()
    result = service.thesis_read("MSFT")
    assert result["ok"] is True
    assert result["has_thesis"] is False
    assert "note" in result


def test_traversal_is_rejected(vault):
    result = service.thesis_read("AAPL", file="../secret.md")
    assert result.get("ok") is not True
    assert result["error"]["code"] == "invalid_path"


# ---------------------------------------------------------------------------
# citation artifacts + resolve
# ---------------------------------------------------------------------------
def _artifact(**overrides):
    artifact = {
        "module": "thesis",
        "kind": "vault-doc",
        "symbol": "AAPL",
        "file": "thesis.md",
        "format": "md",
        "status": "cached",
    }
    artifact.update(overrides)
    return artifact


def test_citation_is_artifact_first_with_no_pseudo_url(vault):
    result = service.thesis_read("AAPL")
    citation = result["citations"][0]
    assert "url" not in citation
    assert "thesis://" not in json.dumps(citation)
    assert citation["artifact"] == _artifact()
    assert citation["label"] == "AAPL thesis"
    assert citation["section"] == "thesis.md"


def test_resolve_serves_vault_markdown_with_paging(vault):
    artifact = service.thesis_read("AAPL")["citations"][0]["artifact"]
    full = service.resolve(artifact)["chunk"]

    first = service.resolve(artifact, limit=10)
    assert first["kind"] == "vault-doc"
    assert first["format"] == "md"
    assert first["file"] == "thesis.md"
    assert first["symbol"] == "AAPL"
    assert first["total_chars"] == len(full)
    assert first["next_offset"] == len(first["chunk"])

    second = service.resolve(artifact, offset=first["next_offset"], limit=10)
    consumed = len(first["chunk"]) + len(second["chunk"])
    assert first["chunk"] + second["chunk"] == full[:consumed]

    tail = service.resolve(artifact, offset=first["total_chars"])
    assert tail["chunk"] == ""
    assert tail["next_offset"] is None


def test_resolve_reads_the_whole_vault_document(vault):
    first = service.resolve(_artifact(), limit=8000)
    assert first["chunk"].startswith("---")
    assert "Services growth." in first["chunk"]
    assert first["total_chars"] == len(first["chunk"])
    assert first["next_offset"] is None


def test_resolve_rejects_traversal(vault):
    (vault.parent / "secret.md").write_text("nope\n", encoding="utf-8")
    for value in ("../secret.md", "attachments/../../secret.md", "/etc/passwd"):
        with pytest.raises(InvalidArgument) as error:
            service.resolve(_artifact(file=value))
        assert error.value.code == "invalid_argument"


def test_resolve_missing_file_is_not_cached(vault):
    with pytest.raises(ArtifactNotCached) as error:
        service.resolve(_artifact(file="missing.md"))
    assert error.value.code == "artifact_not_cached"
    assert "thesis_read" in (error.value.hint or "")


def test_resolve_missing_vault_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("VW_THESIS_ROOT", str(tmp_path / "absent"))
    config.refresh()
    try:
        with pytest.raises(ArtifactNotCached) as error:
            service.resolve(_artifact())
        assert error.value.code == "artifact_not_cached"
    finally:
        config.refresh()


def test_resolve_rejects_unknown_artifact_kind(vault):
    with pytest.raises(CitationUnresolvable) as error:
        service.resolve(_artifact(kind="facts-json"))
    assert error.value.code == "citation_unresolvable"

