"""Unit tests for :mod:`mcp.artifact_viewer` — opt-in loopback artifact viewer."""

from __future__ import annotations

import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core import artifact_viewer, citations  # noqa: E402
from core.errors import ArtifactNotCached  # noqa: E402

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

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

    def __init__(self) -> None:
        self.calls: list[tuple[dict, int, int]] = []

    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
        self.calls.append((artifact, offset, limit))
        return {
            "kind": artifact.get("kind"),
            "format": artifact.get("format", "md"),
            "chunk": "revenue grew <b>12%</b>",
            "next_offset": 42,
            "total_chars": 100,
            "path": None,
            "preview": None,
            "hint": None,
        }


class _NotCachedResolver:
    api_version = 1

    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
        raise ArtifactNotCached(
            "reports artifact not cached",
            hint="run report_section first to build the semantic artifact",
        )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get(url: str) -> tuple[int, str]:
    try:
        with _OPENER.open(url, timeout=5) as response:
            return int(response.status), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8")


@pytest.fixture(autouse=True)
def _isolated_viewer():
    artifact_viewer.stop()
    citations.clear_resolvers()
    yield
    artifact_viewer.stop()
    citations.clear_resolvers()


@pytest.fixture
def viewer() -> str:
    port = _free_port()
    # The public base must be reachable from this test process, so it points at
    # the actual bound loopback address; production sets a real public origin.
    base = artifact_viewer.start(port, public_base=f"http://127.0.0.1:{port}")
    assert base is not None
    return base


def test_a_negative_port_disables_the_viewer():
    assert artifact_viewer.start(-1) is None
    assert artifact_viewer.base_url() is None
    assert artifact_viewer.public_base() is None
    assert artifact_viewer.public_base_source() is None
    assert artifact_viewer.url_for(_ARTIFACT) is None


def test_viewer_infers_a_loopback_base_without_configuration():
    base = artifact_viewer.start(0)

    assert base is not None
    assert base.startswith("http://127.0.0.1:")
    port = base.rpartition(":")[2]
    assert port.isdigit() and int(port) > 0
    # The inferred base uses the actually bound (ephemeral) port.
    assert artifact_viewer.public_base() == base
    assert artifact_viewer.public_base_source() == "inferred"

    url = artifact_viewer.url_for(_ARTIFACT)
    assert url is not None and url.startswith(f"{base}/a?")


def test_explicit_public_base_overrides_inference():
    public = "https://viewer.example.test"
    assert artifact_viewer.start(0, public_base=public) is not None

    assert artifact_viewer.public_base() == public
    assert artifact_viewer.public_base_source() == "explicit"
    url = artifact_viewer.url_for(_ARTIFACT)
    assert url is not None and url.startswith(f"{public}/a?")


def test_port_zero_binds_an_ephemeral_port_with_a_public_base():
    base = artifact_viewer.start(0, public_base="https://viewer.example.test")

    assert base is not None
    assert base.startswith("http://127.0.0.1:")
    url = artifact_viewer.url_for(_ARTIFACT)
    assert url is not None and url.startswith("https://viewer.example.test/a?")


def test_url_for_uses_the_configured_public_base():
    public = "https://viewer.example.test"
    assert artifact_viewer.start(_free_port(), public_base=public + "/") is not None

    url = artifact_viewer.url_for(_ARTIFACT)
    assert url is not None
    parsed = urlsplit(url)
    assert f"{parsed.scheme}://{parsed.netloc}" == public
    assert parsed.path == "/a"

    query = parse_qs(parsed.query)
    assert query["kind"] == ["semantic-section"]
    assert query["section_id"] == ["part2-item7"]
    assert artifact_viewer.public_base() == public
    assert artifact_viewer.public_base_source() == "explicit"


def test_start_binds_the_given_host():
    base = artifact_viewer.start(_free_port(), host="localhost")

    assert base is not None
    scheme, _, authority = base.partition("://")
    host, _, port = authority.rpartition(":")
    assert scheme == "http"
    assert host == "localhost"
    assert port.isdigit()


def test_stop_clears_the_public_base():
    assert artifact_viewer.start(
        _free_port(), public_base="https://viewer.example.test"
    ) is not None
    assert artifact_viewer.url_for(_ARTIFACT) is not None

    artifact_viewer.stop()

    assert artifact_viewer.public_base() is None
    assert artifact_viewer.public_base_source() is None
    assert artifact_viewer.url_for(_ARTIFACT) is None


def test_stop_clears_an_inferred_public_base():
    assert artifact_viewer.start(0) is not None
    assert artifact_viewer.public_base_source() == "inferred"

    artifact_viewer.stop()

    assert artifact_viewer.public_base() is None
    assert artifact_viewer.public_base_source() is None
    assert artifact_viewer.url_for(_ARTIFACT) is None


def test_stop_is_idempotent():
    assert artifact_viewer.start(_free_port()) is not None
    artifact_viewer.stop()
    artifact_viewer.stop()
    assert artifact_viewer.base_url() is None
    assert artifact_viewer.url_for(_ARTIFACT) is None


# -- status(): the only honest answer about reachability -----------------


def test_status_reports_a_stopped_viewer():
    artifact_viewer.stop()

    state = artifact_viewer.status()

    assert state["enabled"] is False
    assert state["base_url"] is None
    assert state["public_base"] is None
    assert state["public_base_source"] is None
    assert state["reachable_hint"] == "unknown"
    assert state["last_error"] is None


def test_status_reports_an_inferred_loopback_base():
    base = artifact_viewer.start(0)
    assert base is not None

    state = artifact_viewer.status()

    assert state["enabled"] is True
    assert state["base_url"] == base
    assert state["public_base"] == base
    assert state["public_base_source"] == "inferred"
    assert state["reachable_hint"] == "loopback"
    assert state["last_error"] is None


def test_status_marks_an_explicit_base_as_reachable():
    assert artifact_viewer.start(0, public_base="https://viewer.example.test")

    state = artifact_viewer.status()

    assert state["enabled"] is True
    assert state["public_base"] == "https://viewer.example.test"
    assert state["public_base_source"] == "explicit"
    assert state["reachable_hint"] == "explicit"


def test_a_failed_bind_is_visible_as_last_error():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        taken = int(occupied.getsockname()[1])

        assert artifact_viewer.start(taken) is None

    state = artifact_viewer.status()

    assert state["enabled"] is False
    assert state["public_base"] is None
    assert state["last_error"]
    assert "bind failed" in state["last_error"]
    assert artifact_viewer.url_for(_ARTIFACT) is None


def test_url_for_carries_module_kind_and_token(viewer):
    url = artifact_viewer.url_for(_ARTIFACT)

    assert url is not None
    parsed = urlsplit(url)
    assert f"{parsed.scheme}://{parsed.netloc}" == viewer
    assert parsed.path == "/a"

    query = parse_qs(parsed.query)
    assert query["module"] == ["reports"]
    assert query["kind"] == ["semantic-section"]
    assert query["cik"] == ["320193"]
    assert query["accession"] == ["0000320193-25-000079"]
    # ``format`` is the artifact's content format, never an HTTP knob.
    assert "format" not in query
    assert query["t"] and len(query["t"][0]) >= 16


def test_viewer_binds_loopback_only(viewer):
    assert viewer.startswith("http://127.0.0.1:")
    assert "0.0.0.0" not in viewer


def test_missing_token_is_forbidden(viewer):
    status, body = _get(f"{viewer}/a?module=reports&kind=semantic-section")

    assert status == 403
    assert "forbidden" in body


def test_wrong_token_is_forbidden(viewer):
    status, body = _get(f"{viewer}/a?module=reports&kind=semantic-section&t=nope")

    assert status == 403
    assert "forbidden" in body


def test_serves_raw_chunk_through_the_resolver_registry(viewer, capsys):
    resolver = _FakeResolver()
    citations.register_resolver("reports", resolver)
    url = artifact_viewer.url_for(_ARTIFACT)
    assert url is not None

    status, body = _get(f"{url}&format=raw")

    assert status == 200
    assert body == "revenue grew <b>12%</b>"
    assert resolver.calls
    artifact, offset, limit = resolver.calls[0]
    assert artifact["module"] == "reports"
    assert artifact["section_id"] == "part2-item7"
    assert artifact["cik"] == 320193
    assert offset == 0
    assert limit == 8000
    assert capsys.readouterr().out == ""


def test_serves_escaped_html_with_paging_links(viewer):
    citations.register_resolver("reports", _FakeResolver())
    url = artifact_viewer.url_for(_ARTIFACT)
    assert url is not None

    status, body = _get(url)

    assert status == 200
    assert "<pre>" in body
    assert "&lt;b&gt;12%&lt;/b&gt;" in body
    assert "<b>12%</b>" not in body
    assert "next page" in body
    assert "format=raw" in body
    assert "offset=42" in body


def test_paging_offset_and_limit_reach_the_resolver(viewer):
    resolver = _FakeResolver()
    citations.register_resolver("reports", resolver)
    url = artifact_viewer.url_for(_ARTIFACT)
    assert url is not None

    status, _ = _get(f"{url}&offset=40&limit=20&format=raw")

    assert status == 200
    assert resolver.calls[-1][1:] == (40, 20)


def test_artifact_not_cached_maps_to_409(viewer):
    citations.register_resolver("reports", _NotCachedResolver())
    url = artifact_viewer.url_for(_ARTIFACT)
    assert url is not None

    status, body = _get(url)

    assert status == 409
    assert "artifact_not_cached" in body
    assert "report_section" in body


def test_unregistered_module_maps_to_404(viewer):
    url = artifact_viewer.url_for({"module": "fundamentals", "kind": "fact"})
    assert url is not None

    status, body = _get(url)

    assert status == 404
    assert "citation_unresolvable" in body


def test_unknown_path_is_404_with_a_valid_token(viewer):
    token = parse_qs(urlsplit(artifact_viewer.url_for(_ARTIFACT) or "").query)["t"][0]

    status, body = _get(f"{viewer}/nope?t={token}")

    assert status == 404
    assert "not_found" in body
