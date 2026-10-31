# 06 — Reports and the parser

How filing HTML becomes stable sections, notes and table grids — and the
sec-parser limits that shape the code.

## Pipeline

```
symbol + form (or accession)
  → filings_index lookup (submissions JSON, 12 h)
  → artifact already built?  → load gzip
  → GET source_url        (edgartools filing.html() fallback)
  → cap at VW_MAX_HTML_MB
  → secparser_source.parse_html(html)      → elements, warnings
  → sections.build_sections(elements, form) → sections, coverage
  → tables.extract_grid(html) per TableElement
  → persist semantic JSON + manifest row
```

`sources/edgar_source.py` owns discovery and download; `sources/secparser_source.py`
owns parsing; `domain/` owns rules. No domain module performs I/O.

## Why the submissions JSON for the index

`Company.get_filings()` materialised every historical filing and took ~480 s on a
cold cache. One `GET https://data.sec.gov/submissions/CIK##########.json`
returns the full recent history in well under a second and is cached twice (12 h
in-process, 12 h in SQLite). edgartools is still used for `Company(symbol)` and
as an HTML fallback.

Both paths require the configured User-Agent:
SEC answers `403 Forbidden` to anonymous or rejected identities. See
[Configuration](../users/02-configuration.md#sec-user-agent).

## sec-parser constraints

Verified against **sec-parser 0.58.1** on real AAPL filings.

| Constraint | Consequence in code |
|:---|:---|
| A 10-K yields only 8 `TopSectionTitle` nodes; Items 1A, 7, 7A, 8 and 9+ are rejected as `InvalidTopSectionIn10Q` | mandatory canonical-item heuristic over `TitleElement`s |
| A 10-Q is fully classified | heuristic only fills gaps |
| Notes are level 0 in a 10-K and level 2 in a 10-Q | detect by heading text (`Note N`), never by level |
| `TableElement.table_to_markdown()` loses `colspan`, omits the GFM delimiter row and **mutates the parse tree** | never call it; read `html_tag.get_source_code()` first |
| The tree must not be rendered or rebuilt after tables are read | table HTML is captured before any other access |
| `loguru` writes to stdout by default | parser logging is redirected to stderr in `secparser_source` |

`parse_html()` returns:

```python
([{"type": ..., "level": ..., "text": ..., "section_type": ..., "table_html": ...}], warnings)
```

Elements with neither text nor table HTML are dropped. `PARSER_VERSION = "0.58.1"`
and a mismatch invalidates every artifact.

## Section IDs

IDs are derived from headings, lowercased, and stable for a filing:

| Source | Pattern | Example |
|:---|:---|:---|
| parser `TopSectionTitle` | `part{n}-item{id}` | `part2-item8` |
| heuristic `Item N` | `{part_key}-item{id}` | `part2-item7a` |
| notes | `note-{number}` | `note-8` |
| part header | `part{n}` | `part2` |

`part_key` is always `part1`…`part4` (never a bare `"1"`), which earlier
prevented IDs like `partpart1-item1`. Expected-item IDs are built the same way,
so coverage comparisons cannot double-prefix.

Regexes:

```python
PART_RE         = re.compile(r"^PART\s+(I|II|III|IV)\b", re.I)
ITEM_RE         = re.compile(r"^Item\s+(\d{1,2}[A-C]?)\.?\s*(?:[—–:\-]\s*)?(.+)$", re.I)
NOTE_RE         = re.compile(r"^Note\s+(\d{1,2})\b", re.I)
SECTION_TYPE_RE = re.compile(r"^part(\d+)(?:item(\d+[a-c]?))?$", re.I)
ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4"}
```

## The 10-K item heuristic

```
walk elements in document order
  PART n heading        → current_part = f"part{n}"
  "Item X — Title"      → record section, mark item seen
  "Note N" inside Item 8→ record note section
  first heading after a section → closes it
```

Then coverage compares the recorded IDs with the canonical set:

| Part | Expected items |
|:---|:---|
| Part I | 1, 1A, 1B, 2, 3, 4, 5 (7 with sub-items) |
| Part II | 5, 6, 7, 7A, 8, 9, 9A, 9B, 9C (9) |
| Part III | 10, 11, 12, 13, 14 (5) |
| Part IV | 15, 16 (2) |

Total: 23 expected IDs for a complete 10-K. The local AAPL FY2025 10-K produces
23 items, 13 notes and `degraded: false`.

## Coverage

`coverage` is the parser's self-report; the model is instructed to surface it.

| Key | Meaning |
|:---|:---|
| `parser_top_sections` | sections sec-parser classified natively |
| `heuristic_items` | items recovered by the heuristic |
| `expected_items` | canonical count for this form |
| `missing_items` | expected IDs not found (e.g. `part2-item7a`) |
| `notes_found` | note headings detected |
| `table_count` | extracted tables |
| `degraded` | `true` when expected items are missing, or a semantic form has zero notes |

```python
missing = [item for item in expected_ids if item not in accepted]
degraded = bool(expected_ids) and bool(missing)
if profile in SEMANTIC_FORMS and notes == 0:
    degraded = True
```

Generic forms (`8-K`, `20-F`, `40-F`, proxies) have no expected set, so
`degraded` stays `false` — absence of items is not a defect there.

## Tables

`domain/tables.py` builds a real grid from the captured HTML:

1. Parse with BeautifulSoup (`lxml`).
2. Read every `tr` and its direct `th`/`td` children.
3. Apply `colspan`/`rowspan` into a sparse map keyed by `(row, col)`.
4. Fill covered cells with `""` so the grid stays rectangular.
5. Collapse whitespace; escape `|` so markdown cannot break.
6. Render GFM with an explicit delimiter row:

```
| Year | Revenue | Margin |
| --- | --- | --- |
| 2025 | 416,161 | 31.5% |
```

Caps: 5 000 cells, 60 columns, 500 characters per cell. Empty grids are skipped
(that is why a live 10-K can show 45 tables where an offline copy shows 47 — the
difference is empty layout tables, not lost data).

`caption_for()` picks the nearest preceding heading or `Table N` label. Tables
are attached to the section that owns their element index.

## Profiles

| Form | Profile | Expected items | Notes |
|:---|:---|:---|:---|
| `10-K`, `10-K/A` | `10-K` | yes | full heuristic |
| `10-Q`, `10-Q/A` | `10-Q` | yes | parser types + gap fill |
| `8-K`, `8-K/A` | `8-K` | no | generic sections |
| `20-F`, `40-F` | `generic` | no | foreign private issuers |
| `DEF 14A`, `DEF14A`, `DEFA14A` | `proxy` | no | generic sections |

`is_semantic_form()` is true only for `10-K` and `10-Q`.

## Artifact lifecycle

```
artifact(symbol, accession, form)
  → in-process LRU (VW_ARTIFACT_LRU, default 2)
  → artifact_store.load(): manifest row + both files + version match
  → build_lock(cik, accession) with flock
       → re-check
       → parse and persist
```

- `save_artifact()` writes gzip atomically (temp file + rename).
- `record()` upserts the manifest; `mark_failed()` stores `status='failed'` with
  the error so the next call retries.
- `_valid()` requires `schema_version`, `rules_version`, `parser_version`, both
  files and `status='ready'`.
- Concurrent callers for the same accession either wait for the lock or receive
  `parser_failed("artifact build already in progress; retry shortly")` — never a
  half-built artifact.

## Limits and performance

| Item | Value |
|:---|:---|
| HTML cap | `VW_MAX_HTML_MB` (40) |
| Parse time | ~0.2–0.5 s for a 1.5 MB 10-K |
| Artifact size | 50–250 KB gzip |
| Section page | 8 000 chars default, max 12 000 |
| Table page | 40 rows default, max 100 |
| Search query | 2–120 chars, 50 hits max |

Search before reading. Paging a 40 k-character Item 7 to locate one paragraph
wastes the byte budget and the user's patience.

## Failure modes

| Symptom | Cause | Action |
|:---|:---|:---|
| `parser_failed` | sec-parser raised | capture the accession; try another filing |
| `artifact_too_large` | HTML above the cap | raise `VW_MAX_HTML_MB` or skip |
| `section_not_found` | stale ID | re-list sections |
| `coverage.degraded` | items or notes missing | search for the passage; never assert absence |
| Empty `table_ids` | layout-only tables were skipped | expected behaviour |
| `403 Forbidden` on download | rejected User-Agent | fix identity |

## Extending the parser

1. Add the rule in `domain/sections.py` or `domain/tables.py` — never in
   `service.py`.
2. Bump `RULES_VERSION` in `artifact_store.py` if IDs or coverage semantics
   change.
3. Add a test in `tests/unit/reports/test_sections_tables.py` asserting the ID
   and the coverage effect.
4. Re-run the offline integration test; it asserts 23 items and 13 notes on the
   real AAPL 10-K.

## Next

- [Analysis and DCF](07-analysis-and-dcf.md)
- [Data model](03-data-model.md)
