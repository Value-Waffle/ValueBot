"""Section and note heuristics over sec-parser elements.

sec-parser classifies only eight top sections in a 10-K; Items 1A, 7, 7A, 8 and
9+ are rejected. The canonical item heuristic below is therefore mandatory for
10-K filings and a gap-filler for 10-Q filings.
"""

from __future__ import annotations

import re

from core.models import Section

from . import profiles

PART_RE = re.compile(r"^PART\s+(I|II|III|IV)\b", re.I)
ITEM_RE = re.compile(r"^Item\s+(\d{1,2}[A-C]?)\.?\s*(?:[—–:\-]\s*)?(.+)$", re.I)
NOTE_RE = re.compile(r"^Note\s+(\d{1,2})\b", re.I)
SECTION_TYPE_RE = re.compile(r"^part(\d+)(?:item(\d+[a-c]?))?$", re.I)
CROSS_REF = ("see ", "refer to", "pursuant to", "incorporated by reference")
ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4"}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _canonical_item(raw: str) -> str:
    return raw.strip().upper()


def detect_note(title: str) -> int | None:
    match = NOTE_RE.match(_clean(title))
    return int(match.group(1)) if match else None


def _accepted_part_for_note(form: str) -> set[str]:
    if profiles.profile_for(form) == "10-K":
        return {"part2-item8"}
    if profiles.profile_for(form) == "10-Q":
        return {"part1-item1"}
    return set()


def _heading_records(elements: list[dict], form: str) -> tuple[list[dict], int, list[str]]:
    expected = profiles.expected_items(form)
    parser_top = 0
    current_part: str | None = None
    current_item: str | None = None
    seen_items: set[str] = set()
    seen_notes: set[int] = set()
    note_parents = _accepted_part_for_note(form)
    records: list[dict] = []

    for index, element in enumerate(elements):
        kind = str(element.get("type") or "")
        text = _clean(element.get("text") or "")
        if not text:
            continue

        if kind == "TopSectionTitle":
            parser_top += 1
            identifier = str(element.get("section_type") or "")
            match = SECTION_TYPE_RE.match(identifier)
            if match:
                part_num, item = match.group(1), match.group(2)
                if item is None:
                    current_part = f"part{part_num}"
                    current_item = None
                    records.append(
                        {"index": index, "kind": "part", "id": current_part,
                         "parent": None, "title": text, "section_type": identifier,
                         "level": int(element.get("level") or 0), "note": None}
                    )
                    continue
                item_id = _canonical_item(item)
                section_id = f"part{part_num}-item{item_id.lower()}"
                allowed = expected.get(f"part{part_num}", [])
                if item_id not in allowed:
                    continue
                current_part = f"part{part_num}"
                current_item = section_id
                seen_items.add(section_id)
                records.append(
                    {"index": index, "kind": "item", "id": section_id,
                     "parent": current_part, "title": text,
                     "section_type": identifier, "level": int(element.get("level") or 0),
                     "note": None}
                )
                continue

        if kind not in {"TitleElement", "TextElement", "TopSectionTitle"}:
            continue
        if kind == "TextElement" and len(text) > 220:
            continue
        if any(text.lower().startswith(prefix) for prefix in CROSS_REF):
            continue

        part_match = PART_RE.match(text)
        if part_match:
            part_num = ROMAN.get(part_match.group(1).upper(), "1")
            current_part = f"part{part_num}"
            current_item = None
            records.append(
                {"index": index, "kind": "part", "id": current_part, "parent": None,
                 "title": text, "section_type": None,
                 "level": int(element.get("level") or 0), "note": None}
            )
            continue

        item_match = ITEM_RE.match(text)
        if item_match and len(text) <= 220:
            item_id = _canonical_item(item_match.group(1))
            part_key = current_part or "part1"
            if part_key not in expected and profiles.profile_for(form) in profiles.SEMANTIC_FORMS:
                continue
            allowed = expected.get(part_key, [])
            if allowed and item_id not in allowed:
                continue
            section_id = f"{part_key}-item{item_id.lower()}"
            if section_id in seen_items:
                continue
            seen_items.add(section_id)
            current_part = part_key
            current_item = section_id
            records.append(
                {"index": index, "kind": "item", "id": section_id,
                 "parent": current_part, "title": text, "section_type": None,
                 "level": int(element.get("level") or 0), "note": None}
            )
            continue

        if current_item in note_parents:
            number = detect_note(text)
            if number is not None and number not in seen_notes:
                seen_notes.add(number)
                records.append(
                    {"index": index, "kind": "note", "id": f"note-{number}",
                     "parent": current_item, "title": text, "section_type": None,
                     "level": int(element.get("level") or 0), "note": number}
                )

    return records, parser_top, [f"item-{item}" for item in sorted(seen_items)]


def _coverage(form: str, parser_top: int, accepted: set[str], notes: int) -> dict:
    expected = profiles.expected_items(form)
    expected_ids = [
        f"{part}-item{item.lower()}"
        for part, items in expected.items()
        for item in items
    ]
    missing = [item for item in expected_ids if item not in accepted]
    degraded = bool(expected_ids) and bool(missing)
    if profiles.profile_for(form) in profiles.SEMANTIC_FORMS and notes == 0:
        degraded = True
    return {
        "parser_top_sections": parser_top,
        "heuristic_items": len(accepted),
        "expected_items": len(expected_ids),
        "missing_items": missing,
        "notes_found": notes,
        "degraded": degraded,
    }


def build_sections(elements: list[dict], form: str) -> tuple[list[Section], dict]:
    records, parser_top, _ = _heading_records(elements, form)
    sections: list[Section] = []
    accepted_items = {record["id"] for record in records if record["kind"] == "item"}
    notes = sum(1 for record in records if record["kind"] == "note")

    for position, record in enumerate(records):
        end = records[position + 1]["index"] if position + 1 < len(records) else len(elements)
        start = record["index"]
        char_count = sum(
            len(str(elements[i].get("text") or ""))
            for i in range(start, min(end, len(elements)))
            if elements[i].get("type") in {"TextElement", "SupplementaryText"}
        )
        sections.append(
            Section(
                id=record["id"],
                parent_id=record["parent"],
                kind=record["kind"],
                title=record["title"][:240],
                start=start,
                end=max(start, end),
                char_count=char_count,
                section_type=record["section_type"],
                level=record["level"],
                note_number=record["note"],
            )
        )

    return sections, _coverage(form, parser_top, accepted_items, notes)


def section_text(elements: list[dict], section: Section) -> str:
    parts: list[str] = []
    for element in elements[section.start : section.end]:
        if element.get("type") in {"TextElement", "SupplementaryText"}:
            text = _clean(element.get("text") or "")
            if text:
                parts.append(text)
    return "\n\n".join(parts)
