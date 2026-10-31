"""Citation guard: the single choke point that enforces grounded numbers.

Every tool response is built by :func:`core.response.success`, so a check here
cannot be bypassed by a module, an agent or a future tool. The guard walks the
response payload for *fact rows* — dicts that carry an ``accession`` and a
``period_end`` plus a numeric value, i.e. one cached XBRL fact — and verifies a
citation in the same response attributes that fact.

Policy: **fail closed**. A numeric fact row that no citation attributes has its
value stripped and is marked ``quality="uncited"``. The response reports the
outcome in ``meta.citation_coverage`` so an audit can see enforcement ran.

The guard is pure: it never queries a store, never builds an artifact and never
touches the network. It only compares data already inside the response.
"""

from __future__ import annotations

from typing import Any

__all__ = ["audit", "summary"]

#: Keys that hold the numeric payload of a cached fact row.
_VALUE_KEYS = ("value", "numeric_value")
#: A row is a cached fact only when it names its filing and period.
_ACCESSION_KEYS = ("accession", "accn")
_PERIOD_KEYS = ("period_end", "end")


def _first(mapping: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _looks_like_fact(row: Any) -> bool:
    """True for one cached XBRL fact row, False for metrics, statements, text."""
    if not isinstance(row, dict):
        return False
    if _first(row, _ACCESSION_KEYS) is None:
        return False  # metrics and statement rows have no accession
    if _first(row, _PERIOD_KEYS) is None:
        return False
    return any(_is_numeric(row.get(key)) for key in _VALUE_KEYS)


def _citation_index(citations: list[dict]) -> tuple[set, set]:
    """Return (concept-exact keys, concept-less (accession, period) keys).

    A citation that pins a concept may only attribute *that* concept: putting
    it in the loose set would let one fact silently vouch for its siblings in
    the same filing. Only a citation with no concept is treated as covering
    every concept for its accession+period (statement period citations).
    """
    exact: set = set()
    loose: set = set()
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        artifact = citation.get("artifact")
        artifact = artifact if isinstance(artifact, dict) else {}
        accession = str(
            artifact.get("accession") or citation.get("accession") or ""
        ).strip()
        period = str(
            artifact.get("period_end")
            or artifact.get("period")
            or citation.get("period")
            or ""
        ).strip()
        concept = str(artifact.get("concept") or "").strip()
        if not accession and not period:
            continue
        if concept:
            exact.add((accession, period, concept))
        else:
            loose.add((accession, period))
    return exact, loose


def _attributes(row: dict, exact: set, loose: set) -> bool:
    accession = str(_first(row, _ACCESSION_KEYS) or "").strip()
    period = str(_first(row, _PERIOD_KEYS) or "").strip()
    concept = str(row.get("concept") or "").strip()
    if concept and (accession, period, concept) in exact:
        return True
    return (accession, period) in loose


def _walk(node: Any, exact: set, loose: set, counters: dict, dropped: list) -> Any:
    """Return ``node`` with uncited fact values removed, counting as we go."""
    if isinstance(node, dict):
        if _looks_like_fact(node):
            counters["values"] += 1
            if _attributes(node, exact, loose):
                counters["cited"] += 1
                return node
            counters["dropped"] += 1
            cleaned = dict(node)
            for key in _VALUE_KEYS:
                if key in cleaned:
                    cleaned[key] = None
            cleaned["quality"] = "uncited"
            cleaned["citation"] = None
            dropped.append(
                {
                    "concept": cleaned.get("concept"),
                    "accession": _first(cleaned, _ACCESSION_KEYS),
                    "period_end": _first(cleaned, _PERIOD_KEYS),
                }
            )
            return cleaned
        return {
            key: _walk(value, exact, loose, counters, dropped)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_walk(value, exact, loose, counters, dropped) for value in node]
    return node


def audit(data: Any, citations: Any) -> tuple[Any, dict]:
    """Strip uncited cached facts from ``data`` and return a coverage report.

    ``data`` is the tool payload; ``citations`` is the citation list the tool
    attached. The returned payload is safe to emit: every surviving numeric
    fact row is backed by a citation in the same response.
    """
    items = [item for item in (citations or ()) if isinstance(item, dict)]
    exact, loose = _citation_index(items)
    counters = {"values": 0, "cited": 0, "dropped": 0}
    dropped: list[dict] = []
    cleaned = _walk(data, exact, loose, counters, dropped)
    coverage = {
        "values": counters["values"],
        "cited": counters["cited"],
        "dropped": counters["dropped"],
        "ok": counters["dropped"] == 0,
    }
    if dropped:
        coverage["uncited"] = dropped[:10]
    return cleaned, coverage


def summary(coverage: dict) -> str:
    """One-line human summary for ``meta``."""
    return (
        f"{coverage.get('cited', 0)}/{coverage.get('values', 0)} cached facts cited"
        + (
            f", {coverage['dropped']} dropped as uncited"
            if coverage.get("dropped")
            else ""
        )
    )
