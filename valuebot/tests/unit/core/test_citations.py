"""Unit tests for :mod:`mcp.citations` — EDGAR URLs, keys, dedupe, caps."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[3] / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from core import citations  # noqa: E402
from core.errors import ArtifactNotCached, CitationUnresolvable  # noqa: E402

AAPL_CIK = 320193
AAPL_ACCN = "0000320193-25-000079"
AAPL_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/"
)


@pytest.fixture(autouse=True)
def _clean_registry():
    citations.clear_resolvers()
    yield
    citations.clear_resolvers()


def test_edgar_url_exact_shape_for_aapl():
    assert citations.edgar_url(AAPL_CIK, AAPL_ACCN) == AAPL_INDEX_URL


def test_edgar_url_with_document():
    assert citations.edgar_url(AAPL_CIK, AAPL_ACCN, "aapl-20250927.htm", kind="doc") == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019325000079/aapl-20250927.htm"
    )


def test_edgar_url_index_kind_ignores_document():
    assert citations.edgar_url(AAPL_CIK, AAPL_ACCN, "aapl-20250927.htm") == AAPL_INDEX_URL
    assert citations.edgar_url(AAPL_CIK, AAPL_ACCN, "(index)") == AAPL_INDEX_URL


def test_edgar_url_normalises_zero_padded_cik_and_never_double_slashes():
    url = citations.edgar_url("0000320193", "000032019325000079")

    assert url.startswith("https://www.sec.gov/Archives/edgar/data/320193/")
    assert "//" not in url.split("https://", 1)[1]
    assert url == AAPL_INDEX_URL


def test_edgar_url_doc_kind_accepts_valid_document():
    assert citations.edgar_url(AAPL_CIK, AAPL_ACCN, "aapl-20250927.htm", kind="doc")
    assert citations.edgar_url(AAPL_CIK, AAPL_ACCN, "aapl-20250927.xml", kind="doc")


@pytest.mark.parametrize(
    "document",
    ["(index)", "../x.htm", "report.html", "", None, "aapl-20250927.txt"],
)
def test_edgar_url_doc_kind_rejects_invalid_document(document):
    assert citations.edgar_url(AAPL_CIK, AAPL_ACCN, document, kind="doc") is None


def test_edgar_url_company_kind_shape():
    assert citations.edgar_url(AAPL_CIK, "", kind="company") == (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
        "&CIK=0000320193&type=10-K&dateb=&owner=include&count=40"
    )


def test_no_code_path_emits_the_index_placeholder():
    produced = [
        citations.edgar_url(AAPL_CIK, AAPL_ACCN),
        citations.edgar_url(AAPL_CIK, AAPL_ACCN, "(index)"),
        citations.edgar_url(AAPL_CIK, AAPL_ACCN, "(index)", kind="doc"),
        citations.edgar_url(AAPL_CIK, AAPL_ACCN, kind="company"),
        citations.cite("edgar", "10-K", cik=AAPL_CIK, accession=AAPL_ACCN).get("url"),
    ]

    assert all(item is None or "(index)" not in item for item in produced)


def test_cite_never_invents_a_url_from_cik_and_accession():
    citation = citations.cite("sec-xbrl", "Assets, 2025-09-27", cik=AAPL_CIK, accession=AAPL_ACCN)

    assert "url" not in citation
    assert citation["accession"] == AAPL_ACCN


def test_cite_keeps_a_caller_supplied_url():
    citation = citations.cite(
        "sec-xbrl",
        "Assets, 2025-09-27",
        cik=AAPL_CIK,
        accession=AAPL_ACCN,
        url=citations.sec_fact_url(AAPL_CIK, "us-gaap", "Assets"),
    )

    assert citation["url"] == (
        "https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/Assets.json"
    )


def test_sec_fact_url_shape_and_default_taxonomy():
    expected = (
        "https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/Assets.json"
    )

    assert citations.sec_fact_url(AAPL_CIK, "us-gaap", "Assets") == expected
    assert citations.sec_fact_url(AAPL_CIK, None, "Assets") == expected
    assert citations.sec_fact_url("0000320193", "", "Assets") == expected
    assert citations.sec_fact_url(AAPL_CIK, "dei", "EntityCommonStockSharesOutstanding") == (
        "https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/dei/"
        "EntityCommonStockSharesOutstanding.json"
    )


def test_sec_fact_url_requires_a_concept():
    assert citations.sec_fact_url(AAPL_CIK, "us-gaap", "") is None
    assert citations.sec_fact_url(AAPL_CIK, "us-gaap", None) is None
    assert citations.sec_fact_url(None, "us-gaap", "Assets") is None


def test_sec_companyfacts_url_zero_pads_the_cik():
    assert citations.sec_companyfacts_url(AAPL_CIK) == (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
    )
    assert citations.sec_companyfacts_url("320193") == (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
    )
    assert citations.sec_companyfacts_url("0000320193") == (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
    )
    assert citations.sec_companyfacts_url(320193) == citations.sec_companyfacts_url("320193")
    assert citations.sec_companyfacts_url("") is None


def test_viewer_url_is_none_while_the_viewer_is_disabled():
    from core import artifact_viewer

    artifact_viewer.stop()

    assert citations.viewer_url(None) is None
    assert citations.viewer_url({}) is None
    assert citations.viewer_url(_artifact()) is None


def test_references_never_invents_a_url_for_an_artifact_citation():
    from core import artifact_viewer

    artifact_viewer.stop()
    citation = citations.cite(
        "sec-report",
        "AAPL 10-K FY2025, Item 7",
        accession=AAPL_ACCN,
        section="part2-item7",
        artifact=_artifact(),
    )

    entry = citations.references([citation])[0]

    assert "url" not in entry
    assert "citation_id" not in entry
    assert set(entry) == {"n", "label", "source", "status"}
    assert entry["status"] == "cached"
    assert entry["n"] == 1


def test_references_omit_status_when_artifact_has_no_status():
    citation = citations.cite(
        "sec-report",
        "AAPL 10-K FY2025, Item 7",
        accession=AAPL_ACCN,
        section="part2-item7",
        artifact=_artifact(status=None),
    )

    entry = citations.references([citation])[0]

    assert "status" not in entry


def test_references_passes_through_only_an_explicit_url():
    citation = citations.cite(
        "sec-report",
        "AAPL 10-K FY2025, Item 7",
        accession=AAPL_ACCN,
        url="https://viewer.example.test/a?t=x",
        artifact=_artifact(),
    )

    assert citations.references([citation])[0]["url"] == (
        "https://viewer.example.test/a?t=x"
    )


def test_cite_returns_canonical_fields_and_omits_unset_ones():
    citation = citations.cite(
        "edgar",
        "Apple Inc. 10-K, FY2025",
        cik=AAPL_CIK,
        accession=AAPL_ACCN,
        form="10-K",
        filed="2025-10-31",
        period="FY2025",
        section="Item 7",
    )

    assert set(citation) == {
        "key",
        "label",
        "source",
        "accession",
        "form",
        "filed",
        "period",
        "section",
    }
    assert citation["source"] == "edgar"
    assert citation["label"] == "Apple Inc. 10-K, FY2025"
    assert citation["accession"] == AAPL_ACCN
    assert "url" not in citation
    assert len(citation["key"]) == 16

    minimal = citations.cite("thesis", "AAPL thesis", url="thesis://AAPL/thesis.md")
    assert "accession" not in minimal
    assert "form" not in minimal
    assert "section" not in minimal


def test_keys_are_stable_and_identity_sensitive():
    first = citations.cite("edgar", "10-K", accession=AAPL_ACCN, section="Item 7")
    same = citations.cite("edgar", "10-K", accession=AAPL_ACCN, section="Item 7")
    other_section = citations.cite(
        "edgar", "10-K", accession=AAPL_ACCN, section="Item 8"
    )
    other_accession = citations.cite(
        "edgar", "10-K", accession="0000320193-24-000123", section="Item 7"
    )

    assert first["key"] == same["key"]
    assert first["key"] != other_section["key"]
    assert first["key"] != other_accession["key"]


def test_merge_deduplicates_by_key_and_preserves_order():
    first = citations.cite("edgar", "10-K", accession=AAPL_ACCN, section="Item 7")
    duplicate = dict(first)
    second = citations.cite("edgar", "10-Q", accession=AAPL_ACCN, section="Item 2")

    merged = citations.merge([first, duplicate, second])

    assert [item["key"] for item in merged] == [first["key"], second["key"]]


def test_merge_caps_at_twenty():
    bag = [
        citations.cite("edgar", f"filing {index}", accession=f"0000000000-25-{index:06d}")
        for index in range(25)
    ]

    merged = citations.merge(bag)

    assert len(merged) == 20
    assert merged[0]["key"] == bag[0]["key"]
    assert merged[-1]["key"] == bag[19]["key"]
    assert citations.merge(bag, limit=5) == bag[:5]
    assert citations.merge(bag, limit=0) == []


def test_citation_bag_adds_dedupes_and_caps():
    bag = citations.CitationBag(limit=2)
    first = citations.cite("edgar", "10-K", accession=AAPL_ACCN, section="Item 7")
    second = citations.cite("edgar", "10-K", accession=AAPL_ACCN, section="Item 8")
    third = citations.cite("edgar", "10-Q", accession=AAPL_ACCN, section="Item 2")

    bag.add(first)
    bag.add(dict(first))
    bag.add(second)
    bag.add(third)

    assert len(bag) == 2
    assert bag.as_list() == [first, second]
    assert bag.add(third) is third


# ---------------------------------------------------------------------------
# artifact blocks
# ---------------------------------------------------------------------------


def _artifact(**overrides):
    artifact = {
        "module": "reports",
        "kind": "semantic-section",
        "cik": AAPL_CIK,
        "accession": AAPL_ACCN,
        "section_id": "part2-item7",
        "format": "md",
        "status": "cached",
    }
    artifact.update(overrides)
    return artifact


def test_cite_embeds_artifact_block():
    citation = citations.cite(
        "sec-report",
        "AAPL 10-K FY2025, Item 7",
        accession=AAPL_ACCN,
        section="part2-item7",
        artifact=_artifact(),
    )

    assert citation["artifact"] == _artifact()
    assert len(citation["key"]) == 16


def test_cite_omits_empty_artifact_and_extra_cannot_shadow_artifact():
    plain = citations.cite("edgar", "10-K", accession=AAPL_ACCN)
    assert "artifact" not in plain

    empty = citations.cite("edgar", "10-K", accession=AAPL_ACCN, artifact={})
    assert "artifact" not in empty
    assert empty["key"] == plain["key"]

    shadowed = citations.cite(
        "edgar",
        "10-K",
        accession=AAPL_ACCN,
        extra={"artifact": {"module": "bogus"}},
        artifact=_artifact(),
    )
    assert shadowed["artifact"] == _artifact()


def test_keys_are_artifact_sensitive_and_artifact_order_independent():
    first = citations.cite("sec-report", "Item 7", accession=AAPL_ACCN, artifact=_artifact())
    same = citations.cite("sec-report", "Item 7", accession=AAPL_ACCN, artifact=_artifact())
    reordered = citations.cite(
        "sec-report",
        "Item 7",
        accession=AAPL_ACCN,
        artifact=dict(reversed(list(_artifact().items()))),
    )
    other_section = citations.cite(
        "sec-report",
        "Item 7",
        accession=AAPL_ACCN,
        artifact=_artifact(section_id="part2-item8"),
    )
    no_artifact = citations.cite("sec-report", "Item 7", accession=AAPL_ACCN)

    assert first["key"] == same["key"] == reordered["key"]
    assert first["key"] != other_section["key"]
    assert first["key"] != no_artifact["key"]
    assert citations.merge([first, other_section]) == [first, other_section]


def test_key_for_fallback_is_artifact_sensitive():
    first = {"source": "sec-report", "accession": AAPL_ACCN, "artifact": _artifact()}
    other = {
        "source": "sec-report",
        "accession": AAPL_ACCN,
        "artifact": _artifact(section_id="part2-item8"),
    }

    bag = citations.CitationBag()
    bag.add(first)
    bag.add(other)

    assert len(bag) == 2
    assert citations.merge([first, other]) == [first, other]


# ---------------------------------------------------------------------------
# resolver registry
# ---------------------------------------------------------------------------


class _FakeResolver:
    api_version = 1

    def __init__(self) -> None:
        self.calls: list[tuple[dict, int, int]] = []

    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict:
        self.calls.append((artifact, offset, limit))
        return {
            "kind": artifact.get("kind"),
            "format": artifact.get("format", "md"),
            "chunk": "hello",
            "next_offset": 5,
            "total_chars": 5,
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


def test_register_resolver_and_dispatch():
    resolver = _FakeResolver()
    citations.register_resolver("reports", resolver)
    citation = citations.cite("sec-report", "Item 7", accession=AAPL_ACCN, artifact=_artifact())

    payload = citations.resolve_citation(citation, offset=10, limit=100)

    assert payload["chunk"] == "hello"
    assert payload["next_offset"] == 5
    assert resolver.calls == [(_artifact(), 10, 100)]


def test_resolve_citation_defaults_offset_and_limit():
    resolver = _FakeResolver()
    citations.register_resolver("reports", resolver)

    citations.resolve_citation({"artifact": _artifact()})

    assert resolver.calls == [(_artifact(), 0, 8000)]


def test_resolve_citation_requires_an_artifact():
    with pytest.raises(CitationUnresolvable) as missing:
        citations.resolve_citation({"source": "sec-report", "accession": AAPL_ACCN})
    assert missing.value.code == "citation_unresolvable"
    assert missing.value.retryable is False
    assert missing.value.hint

    with pytest.raises(CitationUnresolvable):
        citations.resolve_citation({"artifact": {}})

    with pytest.raises(CitationUnresolvable):
        citations.resolve_citation("not-a-citation")


def test_resolve_citation_rejects_unregistered_module():
    citations.register_resolver("reports", _FakeResolver())

    with pytest.raises(CitationUnresolvable) as error:
        citations.resolve_citation({"artifact": _artifact(module="fundamentals")})

    assert error.value.code == "citation_unresolvable"
    assert error.value.retryable is False
    assert "fundamentals" in error.value.hint
    assert "reports" in error.value.hint


def test_resolve_citation_lets_artifact_not_cached_propagate():
    citations.register_resolver("reports", _NotCachedResolver())

    with pytest.raises(ArtifactNotCached) as error:
        citations.resolve_citation({"artifact": _artifact()})

    assert error.value.code == "artifact_not_cached"
    assert error.value.retryable is False
    assert "report_section" in error.value.hint


def test_clear_resolvers_drops_registry():
    citations.register_resolver("reports", _FakeResolver())
    citations.clear_resolvers()

    with pytest.raises(CitationUnresolvable):
        citations.resolve_citation({"artifact": _artifact()})


def test_register_resolver_validates_inputs():
    with pytest.raises(ValueError):
        citations.register_resolver("", _FakeResolver())
    with pytest.raises(TypeError):
        citations.register_resolver("reports", object())
