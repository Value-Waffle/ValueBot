"""Inline evidence rendering shared by the HTTP viewer and the MCP tool result.

LibreChat cannot fetch MCP resources, but it *does* render a tool result block
of type ``resource`` whose URI uses the ``ui://`` scheme and whose mime type is
``text/html`` as an inline sandboxed iframe. This module renders that HTML and
the ``ui://`` address, so evidential material can be shown without any
browser-to-plugin network path: the model receives an opaque identifier, never
a URL.

Design constraints:

* stdlib only (``html``) plus :mod:`core.citations`; nothing from ``modules.*``.
* one HTML renderer for both surfaces: :func:`render_html` is the only place
  that assembles a document, and :func:`core.artifact_viewer._page` delegates
  to it.
* every resolved text fragment is HTML-escaped; only an explicit
  ``footer_html`` argument is inserted as markup, and callers pass pre-escaped
  link markup.
* resolution goes through :func:`core.citations.resolve_citation`, i.e. the
  same resolver registry the tools use.
"""

from __future__ import annotations

import html
from typing import Any

__all__ = ["MIME_TYPE", "URI_PREFIX", "build", "render_html", "ui_uri"]

#: Only ``text/html`` renders as an inline iframe in LibreChat v0.8.8.
MIME_TYPE = "text/html"
#: Prefix for the opaque evidence address the model puts in its answer.
URI_PREFIX = "ui://valuebot/evidence/"

#: Shared visual style: the HTTP viewer and the inline resource look the same.
_STYLE = (
    "body{font:14px/1.5 -apple-system,system-ui,sans-serif;margin:2rem;"
    "max-width:70rem}pre{white-space:pre-wrap;word-break:break-word;"
    "background:#f6f6f6;padding:1rem;border-radius:6px}"
)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _meta(payload: dict) -> str:
    """Render the artifact metadata header line (all values escaped)."""
    kind = _text(payload.get("kind"))
    fmt = _text(payload.get("format"))
    total = payload.get("total_chars")
    return " · ".join(
        part
        for part in (
            f"kind: <code>{html.escape(kind)}</code>" if kind else "",
            f"format: <code>{html.escape(fmt)}</code>" if fmt else "",
            f"chars: {html.escape(str(total))}" if total is not None else "",
        )
        if part
    )


def render_html(
    payload: dict,
    *,
    title: str = "",
    footer_html: str = "",
) -> str:
    """Render ``payload`` as one self-contained HTML document.

    ``payload`` carries ``kind``, ``format``, ``chunk`` and ``total_chars`` as
    returned by a resolver. The chunk is always escaped inside ``<pre>``.
    ``title`` overrides the document title; ``footer_html`` is trusted markup
    (callers pass links they have already escaped) and is emitted as a final
    paragraph only when non-empty.
    """
    if not isinstance(payload, dict):
        payload = {"format": "text", "chunk": str(payload)}

    text = _text(payload.get("chunk"))
    kind = _text(payload.get("kind"))
    heading = title or f"valuebot evidence {kind}".strip()
    footer = f"<p>{footer_html}</p>" if footer_html else ""
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(heading)}</title>"
        f"<style>{_STYLE}</style>"
        "</head><body>"
        f"<p>{_meta(payload)}</p>"
        f"<pre>{html.escape(text)}</pre>"
        f"{footer}"
        "</body></html>"
    )


def ui_uri(citation_id: str) -> str:
    """Return the ``ui://`` address LibreChat renders for ``citation_id``."""
    return f"{URI_PREFIX}{_text(citation_id).strip()}"


def build(citation: dict, *, offset: int = 0, limit: int = 8000) -> dict:
    """Resolve ``citation`` and render it as an inline evidence payload.

    Returns ``{uri, mime_type, html, kind, format, next_offset, total_chars}``.
    Resolver and citation errors propagate unchanged so the caller can turn
    them into a recoverable message.
    """
    from .citations import citation_id as _citation_id
    from .citations import resolve_citation

    payload = resolve_citation(citation, offset=offset, limit=limit)
    if not isinstance(payload, dict):  # pragma: no cover - defensive
        payload = {"format": "text", "chunk": str(payload)}

    token = citation.get("citation_id") if isinstance(citation, dict) else None
    if not token:
        artifact = citation.get("artifact") if isinstance(citation, dict) else None
        token = _citation_id(artifact) if isinstance(artifact, dict) else None
    if not token:
        from .errors import CitationUnresolvable

        raise CitationUnresolvable(
            "citation has no citation_id to address inline evidence",
            hint="pass the citation_id token a module tool returned",
        )

    kind = _text(payload.get("kind"))
    return {
        "uri": ui_uri(str(token)),
        "mime_type": MIME_TYPE,
        "html": render_html(payload, title=f"valuebot evidence {kind}"),
        "kind": kind,
        "format": _text(payload.get("format")),
        "next_offset": payload.get("next_offset"),
        "total_chars": payload.get("total_chars"),
    }
