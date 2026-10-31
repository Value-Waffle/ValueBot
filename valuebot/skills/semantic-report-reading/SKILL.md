---
name: semantic-report-reading
description: Navigate sec-parser reports with valuebot — stable section IDs, notes, coverage degradation, table grids and section citations.
---

# Semantic report reading

## Workflow

1. `filing_list(symbol, forms=["10-K"])` to choose an accession, or let
   `report_sections` resolve the latest form.
2. `report_sections(symbol, form="10-K", kind="all")` to get stable IDs.
   - Items look like `part1-item1a`, `part2-item7`, `part2-item8`.
   - Notes look like `note-1` … `note-13`.
   - Check `coverage.degraded` and `warnings` before trusting the index.
3. `report_section(..., section_id="part2-item7")` to read text. Page with
   `offset=next_offset` and keep each call to one section.
4. `report_search(query=...)` for a phrase across text and tables.
5. `report_table(table_id="t14")` for a GFM grid. Select `columns` and page with
   `row_offset`; do not ask for the whole table when a few rows answer.

## Coverage and degradation

- sec-parser classifies only some 10-K items directly; valuebot adds a canonical
  item heuristic. `coverage.missing_items` lists anything not found.
- `coverage.degraded=true` means the index is incomplete. Say so and verify a
  specific claim with `report_search`.
- Generic forms (20-F, 40-F, 8-K, proxy) use title sections, not a guaranteed
  item order.

## Tables

- Tables are grids extracted from source HTML; the markdown has a delimiter row
  and escaped pipes.
- Table text is not returned by `report_sections`; call `report_table`.
- Large tables are capped. If `truncated` is true, page or narrow columns.

## Citations

Cite the filing and section returned in `filing` and `section`. One citation
per section read or table used. Never cite a section ID that the tool did not
return.

## Boundaries

- Do not use report text to re-derive a number that `facts_query` or
  `statement_get` already returned.
- Do not claim a filing is a 10-K if `filing.form` says otherwise.
- Do not present a snippet as a full section.
