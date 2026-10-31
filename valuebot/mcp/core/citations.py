"""Central citation factory for every valuebot tool result.

Every factual or numeric claim must carry a citation produced here. The
canonical citation shape is::

    {
      "key": "<stable hash>",
      "label": "Apple Inc. 10-K, FY2025, Item 7",
      "source": "edgar" | "thesis" | "local" | "insider" | ...,
      "accession": "0000320193-25-000079",   # optional
      "form": "10-K",                        # optional
      "filed": "2025-10-31",                 # optional
      "period": "FY2025",                    # optional
      "section": "Item 7",                   # optional
      "url": "https://www.sec.gov/...",      # optional, caller-supplied only
      "artifact": {                          # optional, artifact-first locator
        "module": "reports",
        "kind": "semantic-section",
        "format": "md",
        "status": "cached",
      },
    }

``key`` is a stable hash of the citation's identity (including the serialized
artifact locator) so the same source cited twice deduplicates, different
filings never collide, and distinct raw sources are never merged.

Everything in this module is pure: no file I/O, no network, no printing.
The resolver registry is in-memory process state only; it never persists
anything and never touches a store itself — resolvers do that.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from .contracts import CitationResolver

__all__ = [
    "MAX_CITATIONS",
    "RESOLVERS",
    "artifact_from_citation_id",
    "cite",
    "citation_id",
    "clear_resolvers",
    "edgar_url",
    "merge",
    "references",
    "register_resolver",
    "resolve_citation",
    "sec_companyfacts_url",
    "sec_fact_url",
    "viewer_url",
    "CitationBag",
]

#: Maximum citations carried by a single tool response.
MAX_CITATIONS = 20

_IDENTITY_FIELDS = ("accession", "form", "filed", "section", "url")

_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data/"
_COMPANY_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    "&CIK={cik}&type=10-K&dateb=&owner=include&count=40"
)
#: SEC XBRL API (the dataset XBRL facts actually come from).
_SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_SEC_COMPANYCONCEPT_URL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{concept}.json"
)
_DEFAULT_TAXONOMY = "us-gaap"
#: A ``kind="doc"`` document must look like a real filing document.
_DOC_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.(?:htm|html|xml)$")
#: Generic document names are never real EDGAR filing documents.
_PLACEHOLDER_STEMS = frozenset({"index", "report", "document", "default", "filing"})

#: In-memory ``artifact.module`` -> resolver registry, wired at composition time.
RESOLVERS: dict[str, "CitationResolver"] = {}


def _text(value: Any) -> str:
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return str(value)
    return value if isinstance(value, str) else str(value)


def _artifact_locator(artifact: Any) -> str:
    """Return a stable, sorted JSON rendering of an artifact locator."""
    if not artifact:
        return ""
    try:
        return json.dumps(
            artifact,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_text,
        )
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return _text(artifact)


def _identity(
    source: Any,
    accession: Any = None,
    form: Any = None,
    filed: Any = None,
    section: Any = None,
    url: Any = None,
    artifact: Any = None,
) -> str:
    """Return a deterministic 16-hex-character key for a citation identity.

    The sorted, JSON-serialised artifact locator participates in the hash so
    two citations pointing at different raw material never dedupe together.
    Artifact-less citations keep the pre-artifact identity (and therefore the
    same key) for backward compatibility.
    """
    payload = [
        _text(source) if source is not None else "",
        _text(accession) if accession is not None else "",
        _text(form) if form is not None else "",
        _text(filed) if filed is not None else "",
        _text(section) if section is not None else "",
        _text(url) if url is not None else "",
    ]
    locator = _artifact_locator(artifact)
    if locator:
        payload.append(locator)
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def _key_for(citation: dict) -> str:
    key = citation.get("key")
    if isinstance(key, str) and key:
        return key
    return _identity(
        citation.get("source"),
        citation.get("accession"),
        citation.get("form"),
        citation.get("filed"),
        citation.get("section"),
        citation.get("url"),
        citation.get("artifact"),
    )


def _normalise_cik(cik: Any) -> str:
    digits = re.sub(r"\D", "", str(cik or ""))
    return digits.lstrip("0") or ("0" if digits else "")


def _cik10(cik: Any) -> str | None:
    """Return the SEC 10-digit zero-padded CIK, or ``None`` when absent."""
    digits = re.sub(r"\D", "", str(cik or ""))
    if not digits:
        return None
    return f"{int(digits):010d}"


def _valid_document(document: Any) -> str | None:
    """Return the cleaned document name, or ``None`` when it is not a real doc."""
    if document is None:
        return None
    name = str(document).strip().lstrip("/")
    if not _DOC_NAME_RE.match(name):
        return None
    stem = name.rsplit(".", 1)[0].lower()
    if stem in _PLACEHOLDER_STEMS:
        return None
    return name


def edgar_url(
    cik: Any, accession: Any, document: str | None = None, *, kind: str = "index"
) -> str | None:
    """Build a validated EDGAR link; never emits a double slash or a placeholder.

    ``cik`` may be an int or a zero-padded string (``"0000320193"``); the
    canonical URL uses the unpadded form. ``accession`` may include dashes.

    ``kind`` selects the link flavour:

    * ``"index"`` (default) — the accession directory page, which exists for
      every filed accession. ``document`` is ignored, so legacy call sites
      that still pass a placeholder document name produce a live page.
    * ``"doc"`` — the filing document itself, but only when ``document`` looks
      like a real EDGAR document name; otherwise ``None`` is returned so the
      caller omits the URL rather than fabricating a dead link.
    * ``"company"`` — the browse-edgar company filing list page.
    """
    cik_part = _normalise_cik(cik)
    accession_part = re.sub(r"\D", "", str(accession or ""))
    mode = str(kind or "index").strip().lower()

    if mode == "company":
        return _COMPANY_URL.format(cik=f"{int(cik_part or 0):010d}")

    if mode == "doc":
        doc = _valid_document(document)
        if doc is None:
            return None
        segments = [part for part in (cik_part, accession_part, doc) if part]
        return _ARCHIVE_BASE + "/".join(segments)

    segments = [part for part in (cik_part, accession_part) if part]
    return _ARCHIVE_BASE + "/".join(segments) + "/"


def sec_companyfacts_url(cik: Any) -> str | None:
    """Return the SEC companyfacts dataset URL for ``cik``.

    This is the source of cached XBRL facts, not a filing directory.
    """
    cik10 = _cik10(cik)
    if cik10 is None:
        return None
    return _SEC_COMPANYFACTS_URL.format(cik=cik10)


def sec_fact_url(cik: Any, taxonomy: Any, concept: Any) -> str | None:
    """Return the SEC companyconcept (raw fact) URL for one XBRL concept.

    ``taxonomy`` defaults to ``us-gaap``. Returns ``None`` when the concept or
    the CIK is missing, so callers omit the URL instead of inventing one.
    """
    cik10 = _cik10(cik)
    name = str(concept or "").strip()
    if cik10 is None or not name:
        return None
    tax = str(taxonomy or "").strip() or _DEFAULT_TAXONOMY
    return _SEC_COMPANYCONCEPT_URL.format(cik=cik10, taxonomy=tax, concept=name)


def viewer_url(artifact: Any) -> str | None:
    """Return a loopback URL that serves ``artifact`` in the local viewer.

    Returns ``None`` when the viewer is disabled (the default) or when there
    is no artifact locator. Imported lazily: the viewer imports this module.

    This is a **debug surface only**. Citations must not carry it: it points
    at the MCP host's loopback address, which a browser running elsewhere
    cannot reach. Use :func:`citation_id` to address evidence instead.
    """
    if not artifact:
        return None
    from . import artifact_viewer  # local import: avoids an import cycle

    return artifact_viewer.url_for(artifact)


def citation_id(artifact: Any) -> str | None:
    """Return an opaque, URL-safe identifier for an artifact locator.

    The token round-trips through :func:`artifact_from_citation_id`, so an
    agent can open cached evidence with no URL at all. This is the topology-
    proof addressing scheme: it works in Docker, remote and local deployments
    because the resolver runs inside the MCP server.
    """
    if not isinstance(artifact, dict) or not artifact:
        return None
    try:
        raw = json.dumps(
            artifact, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), default=_text,
        )
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None
    token = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
    return token.rstrip("=")


def artifact_from_citation_id(token: Any) -> dict:
    """Decode a token produced by :func:`citation_id` back into a locator.

    Raises :class:`CitationUnresolvable` for a malformed token rather than
    leaking a base64 or JSON error to the caller.
    """
    from .errors import CitationUnresolvable

    text = str(token or "").strip()
    if not text:
        raise CitationUnresolvable("citation_id is empty")
    try:
        padded = text + "=" * (-len(text) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        artifact = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CitationUnresolvable(
            "citation_id is not a valid artifact locator",
            hint="pass the citation_id exactly as the tool returned it",
        ) from exc
    if not isinstance(artifact, dict) or not artifact:
        raise CitationUnresolvable("citation_id decodes to an empty locator")
    if not str(artifact.get("module") or "").strip():
        raise CitationUnresolvable(
            "citation_id locator has no module",
            hint="pass the citation_id exactly as the tool returned it",
        )
    if not str(artifact.get("kind") or "").strip():
        raise CitationUnresolvable(
            "citation_id locator has no artifact kind",
            hint="pass the citation_id exactly as the tool returned it",
        )
    return artifact


def cite(
    source: str,
    label: str,
    *,
    cik: Any = None,
    accession: Any = None,
    form: Any = None,
    filed: Any = None,
    period: Any = None,
    section: Any = None,
    url: Any = None,
    extra: dict | None = None,
    artifact: dict | None = None,
) -> dict:
    """Build one canonical citation dict.

    Optional fields are omitted when unset rather than emitted as ``None``.
    ``url`` is emitted only when the caller passes it explicitly: this factory
    never invents a source link, because a cached XBRL fact came from the SEC
    dataset, not from the filing directory. Use :func:`sec_fact_url`,
    :func:`sec_companyfacts_url` or :func:`edgar_url` to build an honest URL
    and pass it here. ``cik`` is accepted for identity/labelling convenience
    but contributes no URL. ``extra`` fields are only added when they do not
    collide with canonical keys. A non-empty ``artifact`` locator is embedded
    under ``"artifact"`` and participates in the citation identity.
    """
    citation: dict = {}
    if extra:
        for name, value in extra.items():
            if value is not None and name not in citation:
                citation[str(name)] = value

    citation["key"] = _identity(source, accession, form, filed, section, url, artifact)
    citation["label"] = _text(label)
    citation["source"] = _text(source)
    for name, value in (
        ("accession", accession),
        ("form", form),
        ("filed", filed),
        ("period", period),
        ("section", section),
        ("url", url),
    ):
        if value is not None:
            citation[name] = _text(value)
    if artifact:
        # Canonical key wins: an ``extra`` payload can never shadow the artifact.
        citation["artifact"] = artifact
        token = citation_id(artifact)
        if token:
            citation["citation_id"] = token
    return citation


def register_resolver(module: str, resolver: "CitationResolver") -> None:
    """Register ``resolver`` for ``module`` (overwrites any previous entry)."""
    name = str(module or "").strip()
    if not name:
        raise ValueError("module name is required to register a resolver")
    if resolver is None or not callable(getattr(resolver, "resolve", None)):
        raise TypeError("resolver must implement resolve(artifact, *, offset, limit)")
    RESOLVERS[name] = resolver


def clear_resolvers() -> None:
    """Drop every registered resolver (test / composition helpers)."""
    RESOLVERS.clear()


def resolve_citation(
    citation: dict, *, offset: int = 0, limit: int = 8000
) -> dict:
    """Dispatch a citation's ``artifact`` block to its module's resolver.

    Returns the resolver's payload unchanged (``kind``, ``format``, ``chunk``,
    ``next_offset``, ``total_chars`` and optional ``path``, ``preview``,
    ``hint``). Resolvers raise :class:`ArtifactNotCached` when the raw
    material is not cached; that error propagates unchanged. Anything this
    module can decide on its own (no artifact, unknown module) raises
    :class:`CitationUnresolvable` with an actionable hint. No I/O here.
    """
    from .errors import CitationUnresolvable

    if not isinstance(citation, dict):
        raise CitationUnresolvable(
            "citation must be a dict",
            hint="pass the full citation object returned by the tool, not its key",
        )
    artifact = citation.get("artifact")
    if (not isinstance(artifact, dict) or not artifact) and citation.get("citation_id"):
        # Accept a dict whose only useful key is the token: a caller may hold a
        # stored ``citation_id`` without the locator, and the token round-trips
        # back to the artifact on its own.
        artifact = artifact_from_citation_id(citation.get("citation_id"))
    if not isinstance(artifact, dict) or not artifact:
        raise CitationUnresolvable(
            "citation has no artifact block to resolve",
            hint=(
                "pass the citation_id token, or re-run the owning module tool "
                "(e.g. report_section, facts_query) to get an artifact citation"
            ),
        )
    module = artifact.get("module")
    name = str(module or "").strip()
    if not name:
        raise CitationUnresolvable(
            "citation artifact is missing its module",
            hint="artifact.module must name the owning module (reports, fundamentals, ...)",
        )
    resolver = RESOLVERS.get(name)
    if resolver is None:
        available = ", ".join(sorted(RESOLVERS)) or "none"
        raise CitationUnresolvable(
            f"no citation resolver is registered for module {name!r}",
            hint=(
                f"the {name} module is not available in this deployment; "
                f"registered modules: {available}"
            ),
        )
    return resolver.resolve(artifact, offset=offset, limit=limit)


def merge(citations: Iterable[dict], limit: int = MAX_CITATIONS) -> list[dict]:
    """Deduplicate citations by ``key`` (first wins), preserving order and cap."""
    if limit is None or int(limit) <= 0:
        return []
    cap = int(limit)
    merged: list[dict] = []
    seen: set[str] = set()
    for citation in citations or ():
        if not isinstance(citation, dict):
            continue
        key = _key_for(citation)
        if key in seen:
            continue
        seen.add(key)
        merged.append(citation)
        if len(merged) >= cap:
            break
    return merged


def references(
    citations: Iterable[dict], limit: int = MAX_CITATIONS
) -> list[dict]:
    """Build the ready-to-paste references footer for a response.

    The footer is human-readable attribution carrying no machine tokens. The
    server never invents a URL, so a reference stays URL-free unless the
    citation itself already carries a caller-supplied ``url``, which is passed
    through verbatim. Artifact status is included when present so the model
    can report whether evidence was cached.

    Machine addressing lives in ``citations[]`` (``citation_id``), never here.

    Each entry is ``{n, label, source, status?, url?}``.
    """
    entries: list[dict] = []
    for citation in merge(citations, limit=limit):
        entry: dict = {
            "n": len(entries) + 1,
            "label": str(citation.get("label") or "").strip(),
            "source": str(citation.get("source") or "").strip(),
        }
        url = citation.get("url")
        if url:
            entry["url"] = url
        artifact = citation.get("artifact")
        if isinstance(artifact, dict) and artifact.get("status"):
            entry["status"] = artifact["status"]
        entries.append(entry)
    return entries


class CitationBag:
    """Accumulate citations while deduplicating and enforcing the response cap."""

    def __init__(self, limit: int = MAX_CITATIONS) -> None:
        self.limit = int(limit)
        self._items: dict[str, dict] = {}

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items.values())

    def add(self, citation: dict) -> dict:
        """Add one citation; returns the stored (possibly existing) entry."""
        if not isinstance(citation, dict):
            raise TypeError("citation must be a dict")
        key = _key_for(citation)
        if key in self._items:
            return self._items[key]
        if len(self._items) >= self.limit:
            return citation
        item = dict(citation)
        item.setdefault("key", key)
        self._items[key] = item
        return item

    def extend(self, citations: Iterable[dict]) -> "CitationBag":
        """Add many citations, ignoring duplicates and anything past the cap."""
        for citation in citations or ():
            self.add(citation)
        return self

    def as_list(self) -> list[dict]:
        """Return the deduplicated citations in insertion order."""
        return list(self._items.values())
