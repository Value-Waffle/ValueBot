# Knowledge Fields

| Field | Role |
|---|---|
| `title` | Short label, noun phrase, ≤ 120 chars. |
| `short_description` | **One deliberate verb sentence** (≤ 300 chars), required. Shows in search snippets. |
| `body` | **Key extract** — the curated insight (≤ 5 KB). NOT the source document. |
| `metadata` | A pointer/link to the source (a path or URL), NOT a JSON blob. The real content lives there. |
| `source_ref` | Optional URI/file reference for provenance. |

## Confidence Calibration

| Range | Meaning |
|---|---|
| `1.0` | Verified — directly observed or confirmed. |
| `0.7–0.9` | Well-supported — strong evidence, not fully verified. |
| `0.5` | Plausible — reasonable but unconfirmed. |
| `0.2–0.4` | Speculation — a hypothesis or guess. |

Default new items are `1.0`; lower it deliberately when you are unsure.
Prefer recording `1.0` verified items and downgrading over time rather than over-storing speculation as fact.

## Tag Conventions

- Use **lowercase, hyphenated** tags (`[a-z0-9-]`). `normalize_tag()` enforces this (spaces become hyphens; invalid characters raise).
- **Prefer existing tags.** Call `list_tags()` before inventing new ones.
- Tag by **4 dimensions**: topic, tool, source, use-case.
