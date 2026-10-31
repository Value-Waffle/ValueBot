# 05 — Testing

76 tests across three layers. Offline by default; SEC is only contacted by
explicit live runs.

## Running

```bash
# whole suite
.venv/bin/python -m pytest tests -q

# one layer
.venv/bin/python -m pytest tests/unit -q
.venv/bin/python -m pytest tests/contract -q
.venv/bin/python -m pytest tests/integration -q

# one file, verbose
.venv/bin/python -m pytest tests/unit/reports/test_sections_tables.py -v

# live (needs a real SEC User-Agent; not part of the default suite)
SEC_USER_AGENT="example-user@gmail.com" .venv/bin/python -m pytest tests -q -k live
```

Expected output with fixtures present:

```text
........................................................................ [ 94%]
....                                                                     [100%]
76 passed in 9.20s
```

Without the local fixture tree, the four fixture-dependent files report skips:

```text
69 passed, 7 skipped in 8.10s
```

No custom markers are registered. The only marker is `pytest.mark.skipif`, used
to skip files whose fixtures are absent.

## Test layout

| File | Tests | Objective |
|:---|:---:|:---|
| `contract/test_isolation.py` | 5 | module boundaries hold |
| `contract/test_package.py` | 5 | manifests, skills and agent allowlists are consistent |
| `contract/test_stdio.py` | 2 | JSON-RPC only on stdout; unconfigured identity blocks tools |
| `integration/test_offline_pipeline.py` | 2 | fundamentals → analysis and reports → sections work from local fixtures |
| `unit/core/test_cache.py` | 10 | TTL cache expiry, byte cap, purge, corrupt-DB recovery |
| `unit/core/test_citations.py` | 8 | citation keys are stable, dedupe correctly, and never collide |
| `unit/core/test_config_identity.py` | 8 | one-time identity file, env override precedence, placeholder rejection |
| `unit/core/test_envelope.py` | 3 | byte caps and text chunking |
| `unit/fundamentals/test_concepts.py` | 4 | 36 line items are well-formed and candidate concepts resolve |
| `unit/fundamentals/test_facts_store.py` | 4 | ingest, query, annual series, instant FY filtering, provenance |
| `unit/fundamentals/test_statements.py` | 2 | statement normalisation and period citations |
| `unit/fundamentals/test_symbol_resolve.py` | 3 | ticker resolution accepts DataFrame, Arrow and dict shapes |
| `unit/analysis/test_metrics_dcf.py` | 7 | metric arithmetic, quality states, DCF assumptions, validation, sensitivity |
| `unit/analysis/test_service_lookback.py` | 1 | growth metrics fetch extra history |
| `unit/reports/test_filing_index.py` | 3 | submissions-JSON indexing, form/date filters, store `latest()` |
| `unit/reports/test_sections_tables.py` | 5 | 10-K item/note heuristic, coverage flags, table grids |
| `unit/thesis/test_thesis.py` | 4 | vault reads, front matter, paging, traversal rejection |

Support files: `conftest.py` (puts `mcp/` on `sys.path`, sets `PLUGIN_DATA` and
`SEC_USER_AGENT`), `support_stdio.py` (JSON-RPC client), `support_tree.py`
(synthetic SEC tree for reports tests).

`conftest.py` deliberately inserts only `mcp/`, never the plugin root, so the
`mcp` package directory cannot shadow the SDK.

---

## Contract tests

### `test_isolation.py` — 5 tests

Parses the import graph of `mcp/modules/**` and asserts:

1. A module imports `core` plus its own package and nothing else.
2. `analysis → fundamentals.service` is the only cross-module import.
3. No module imports another module's `store` or `domain` internals.
4. No module imports `server`.
5. Every service declares `api_version`.

**Run:** `.venv/bin/python -m pytest tests/contract/test_isolation.py -v`

**Expected:** 5 passed. A failure names the offending file and import — this is
the guard rail for the whole architecture.

### `test_package.py` — 5 tests

Asserts `plugin.json` (name, version `0.2.0`, keywords), `mcp.json` (env keys,
no `SEC_USER_AGENT`/`EDGAR_IDENTITY`, no v1 keys), six agent exports with valid
tool allowlists and existing skills, five skill directories, and that no v1-only
tool name survives.

**Expected:** 5 passed.

### `test_stdio.py` — 2 tests

Spawns `mcp/server.py` as a child process and speaks raw JSON-RPC.

| Test | Asserts |
|:---|:---|
| `test_stdio_lists_tools_and_ping` | 19 tools listed, `ping` reports 4 ready modules, `identity_source: env` |
| `test_unconfigured_identity_blocks_data_tools` | `ping` reports `identity_configured: false`, `identity_source: missing`; `facts_query` fails with `identity_not_configured` and a setup hint, without touching the network |

Both also prove nothing but JSON reaches stdout.

**Expected:** 2 passed in ~2 s.

---

## Integration test

### `test_offline_pipeline.py` — 2 tests

Runs the real services over local fixtures, no network.

| Test | Flow |
|:---|:---|
| fundamentals → analysis | ingest `companyFacts_0000320193.json`, compute metrics, assert cited values |
| reports | parse the local AAPL 10-K, assert 23 items, 13 notes, `degraded == false`, tables extracted |

Skipped when `VW_FIXTURE_DB` has no AAPL tree.

**Run:** `.venv/bin/python -m pytest tests/integration -q`

**Expected:** 2 passed (or 2 skipped).

---

## Unit tests — `core`

| File | Covered behaviour |
|:---|:---|
| `test_cache.py` | `set`/`get`, TTL expiry deletes on read, bucket isolation, `purge_expired`, `evict_to_cap`, `stats`, corrupt DB is recreated, `close()` is idempotent |
| `test_citations.py` | key stability for identical sources, distinct keys for different accessions/sections, dedupe, `MAX_CITATIONS = 20`, `edgar_url()` shape, no I/O |
| `test_config_identity.py` | missing `identity.json` → `identity_source: missing` and `IdentityNotConfigured`; env override normalization; legacy `EDGAR_IDENTITY` alias; file mode `0600`; env beats file; `setup --show/--reset`; placeholder rejection; angle-bracket stripping |
| `test_envelope.py` | `cap_bytes` truncation, `chunk_text` boundaries, UTF-8 safety |

**Expected:** 29 passed.

## Unit tests — `fundamentals`

| File | Covered behaviour |
|:---|:---|
| `test_concepts.py` | 36 items, unique names, valid `period_type`, `derived_from` references exist, candidate concepts are non-empty |
| `test_facts_store.py` | ingest count > 20 000, query totals, annual series ordering and `duration_days`, line-item alignment and citations, instant items return 4 fiscal year-ends, provenance URL shape |
| `test_statements.py` | normalized statement rows/periods, citations attached per period |
| `test_symbol_resolve.py` | DataFrame, Arrow-ish and legacy dict shapes; exact ticker scores 3; name substring matches; `None`/empty input |

**Expected:** 13 passed (4 skipped without fixtures).

## Unit tests — `analysis`

| File | Covered behaviour |
|:---|:---|
| `test_metrics_dcf.py` | gross margin and current ratio arithmetic; negative equity → `not_meaningful`; missing input → `unavailable`; growth uses consecutive periods and `gap` on short history; DCF assumptions-only shape; WACC/terminal-growth `default` + warning; valuation and sensitivity; percent-style rates rejected; exit-multiple and overrides |
| `test_service_lookback.py` | `revenue_cagr` with `periods=3` requests 6 periods and returns `ok` for all selected periods |

**Expected:** 8 passed.

## Unit tests — `reports`

| File | Covered behaviour |
|:---|:---|
| `test_filing_index.py` | submissions-JSON parsing, `forms` + `start` filters, newest-first sort, `get_filing` by accession and by form, store `latest()` and `cached_symbol()` |
| `test_sections_tables.py` | 10-K item IDs (`part2-item7`), note IDs (`note-8`), coverage keys, `degraded` rules, table grid colspan/rowspan and GFM delimiter row |

**Expected:** 8 passed (5 skipped without the local 10-K).

## Unit tests — `thesis`

| File | Covered behaviour |
|:---|:---|
| `test_thesis.py` | missing vault returns `ok` with `has_thesis: false`; front matter parse; body paging with `next_offset`; traversal (`../../etc/passwd`) rejected; annotations listing |

**Expected:** 4 passed.

---

## Fixtures

| Fixture | Path | Used by |
|:---|:---|:---|
| AAPL company facts | `{VW_FIXTURE_DB}/debug/jsonData/aapl/companyFacts_0000320193.json` | facts store, statements, integration |
| AAPL FY2025 10-K | `{VW_FIXTURE_DB}/filing/us/AAPL/10-K/2025-09-27_0000320193-25-000079_aapl-20250927.htm` | sections/tables, integration |
| Submissions JSON | `{VW_FIXTURE_DB}/debug/jsonData/aapl/submissions_0000320193.json` | filing index |

`VW_FIXTURE_DB` defaults to `/Users/rkarumugam/LocalFiles/Projects/db`. Point it
at your own copy:

```bash
VW_FIXTURE_DB=/path/to/db .venv/bin/python -m pytest tests -q
```

`support_tree.py` builds a synthetic SEC tree for tests that should not depend
on the fixture copy at all.

## Writing tests

| Change | Test to add |
|:---|:---|
| New metric | `test_metrics_dcf.py`: one arithmetic case + one quality-state case |
| New line item | `test_concepts.py`: candidate concepts resolve against a fixture |
| New tool | argument clamping, envelope shape, at least one failure path |
| New module | a row in the `test_isolation.py` matrix |
| Parser heuristic | a section-ID and a coverage assertion in `test_sections_tables.py` |
| Config value | a resolution/precedence case in `test_config_identity.py` |
| New error code | asserted via a tool call, not by raising directly |

Conventions:

- Import `core` and `modules` directly (never `mcp`).
- Never hit the network — inject a fake source or use fixtures.
- Assert on envelope fields (`ok`, `error.code`, `paging`), not on message text.
- Use the frozen dataclasses from `core.models` to build inputs.

## CI expectations

| Stage | Command | Gate |
|:---|:---|:---|
| Lint (optional) | `ruff check mcp tests` | no errors |
| Tests | `.venv/bin/python -m pytest tests -q` | 76 passed or passed+skipped |
| Contract | `.venv/bin/python -m pytest tests/contract -q` | 12 passed |
| Live (nightly) | `SEC_USER_AGENT=… pytest -k live` | manual |

## Next

- [Contributing](10-contributing.md)
- [Reports and parser](06-reports-parser.md)
