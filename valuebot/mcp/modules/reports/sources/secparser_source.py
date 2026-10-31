"""sec-parser boundary owned by the reports module."""

from __future__ import annotations

import re
import warnings

_WS = re.compile(r"\s+")
PARSER_VERSION = "0.58.1"


def _clean(text: str) -> str:
    return _WS.sub(" ", str(text or "")).strip()


def parse_html(html: str) -> tuple[list[dict], list[str]]:
    """Parse filing HTML into a flat element stream.

    Returns ``(elements, warnings)``. Table HTML is read here, before any other
    table call, because sec-parser's markdown renderer mutates the parse tree.
    """
    import sec_parser as sp  # noqa: PLC0415 - deliberate lazy import

    captured: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        parsed = sp.Edgar10QParser().parse(html)
    for warning in caught:
        message = _clean(str(warning.message))
        if message and message not in captured:
            captured.append(message)

    elements: list[dict] = []
    for element in parsed:
        type_name = type(element).__name__
        level = int(getattr(element, "level", 0) or 0)
        section_type = None
        raw_type = getattr(element, "section_type", None)
        if raw_type is not None:
            section_type = getattr(raw_type, "identifier", None) or str(raw_type)
        text = "" if type_name in {"TableElement", "TableOfContentsElement"} else _clean(
            getattr(element, "text", "") or ""
        )
        table_html = None
        if type_name in {"TableElement", "TableOfContentsElement"}:
            try:
                table_html = element.html_tag.get_source_code(pretty=False)
            except Exception:
                table_html = None
        if not text and table_html is None:
            continue
        elements.append(
            {
                "type": type_name,
                "level": level,
                "text": text,
                "section_type": section_type,
                "table_html": table_html,
            }
        )
    return elements, captured
