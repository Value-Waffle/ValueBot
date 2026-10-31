"""Form profiles and canonical item order for semantic reports."""

from __future__ import annotations

PROFILES = {
    "10-K": "10-K",
    "10-K/A": "10-K",
    "10-Q": "10-Q",
    "10-Q/A": "10-Q",
    "8-K": "8-K",
    "8-K/A": "8-K",
    "20-F": "generic",
    "40-F": "generic",
    "DEF 14A": "proxy",
    "DEF14A": "proxy",
    "DEFA14A": "proxy",
}

EXPECTED_ITEMS = {
    "10-K": {
        "part1": ["1", "1A", "1B", "1C", "2", "3", "4"],
        "part2": ["5", "6", "7", "7A", "8", "9", "9A", "9B", "9C"],
        "part3": ["10", "11", "12", "13", "14"],
        "part4": ["15", "16"],
    },
    "10-Q": {
        "part1": ["1", "2", "3", "4"],
        "part2": ["1", "1A", "2", "3", "4", "5", "6"],
    },
}

SEMANTIC_FORMS = {"10-K", "10-Q"}


def profile_for(form: str) -> str:
    text = (form or "").strip().upper().replace("_", " ")
    return PROFILES.get(text, "generic")


def expected_items(form: str) -> dict[str, list[str]]:
    return EXPECTED_ITEMS.get(profile_for(form), {})


def is_semantic_form(form: str) -> bool:
    return profile_for(form) in SEMANTIC_FORMS
