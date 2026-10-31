# 03 — Data model

Four SQLite databases, one artifact tree and one identity file. Each module owns
its store; no module reads another module's tables.

## Layout

```
${PLUGIN_DATA}/
├── identity.json                                   core (0600)
├── modules/
│   ├── fundamentals/cache.sqlite                   facts + companies + entries
│   ├── analysis/cache.sqlite                       entries (metric results)
│   ├── reports/manifest.sqlite                     issuers, filings, artifacts, entries
│   │   └── artifacts/{cik}/{accession}.*           semantic JSON, raw HTML, lock
│   └── thesis/index.sqlite                         reserved (created on demand)
└── edgar/                                          edgartools HTTP cache (external)
```

Common connection settings (`store/db.py` in each module):

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
```

## `fundamentals/cache.sqlite`

### `companies`

| Column | Type | Notes |
|:---|:---|:---|
| `cik` | INTEGER PK | |
| `ticker` | TEXT | indexed |
| `name`, `exchange`, `sic`, `industry` | TEXT | profile mirror |
| `fiscal_year_end` | TEXT | `MMDD` |
| `filer_category`, `is_foreign` | | |
| `updated_at` | REAL | profile fetch time |
| `facts_synced_at` | REAL | last successful facts sync (also drives `facts_version`) |
| `facts_access` | REAL | LRU signal for `VW_MAX_FACTS_COMPANIES` |
| `fact_count` | INTEGER | rows for this CIK |
| `facts_bytes_estimate` | INTEGER | disk estimate |

### `facts`

| Column | Type | Notes |
|:---|:---|:---|
| `fact_key` | TEXT PK | deterministic hash of cik+concept+period+unit+dimensions |
| `cik` | INTEGER FK | `ON DELETE CASCADE` |
| `concept`, `taxonomy`, `label`, `unit` | TEXT | XBRL identity |
| `value`, `numeric_value` | TEXT, REAL | raw and parsed |
| `period_type` | TEXT | `duration` or `instant` |
| `period_start`, `period_end` | TEXT | ISO dates |
| `duration_days` | INTEGER | annual = 350–380 |
| `fiscal_year`, `fiscal_period` | INTEGER, TEXT | **filing metadata, not period identity** |
| `form_type`, `accession`, `filing_date` | TEXT | provenance |
| `is_audited`, `is_restated`, `data_quality`, `confidence_score` | | quality flags |
| `dimensions_json` | TEXT | segment axes when present |

Indexes: `(cik, concept, period_end)`, `(cik, period_end, period_type)`,
`(cik, form_type, filing_date)`.

Rules:

1. All period matching uses `period_end` + `duration_days`. Never `fiscal_year`.
2. Annual duration = `duration_days BETWEEN 350 AND 380`.
3. Annual instants are limited to the canonical fiscal year-end set computed from
   a revenue-like duration series, so balance-sheet items never return quarters.
4. One row per `(period_end)` after dedupe: latest `filing_date` wins, `10-K`
   breaks ties.

### `facts_version`

```python
def facts_version(conn, cik) -> str:
    row = conn.execute(
        "SELECT facts_synced_at, fact_count FROM companies WHERE cik = ?", (cik,)
    ).fetchone()
    return "0:0" if row is None else f"{row['facts_synced_at'] or 0}:{row['fact_count']}"
```

Included in every analysis cache key, so a re-sync invalidates metrics
automatically.

## `analysis/cache.sqlite`

### `entries`

| Column | Type | Notes |
|:---|:---|:---|
| `key` | TEXT PK | `metric:{cik}:{metric}:{period}:{basis}:{formula_version}:{facts_version}` |
| `bucket` | TEXT | `metrics` |
| `value` | TEXT | JSON payload |
| `created_at`, `expires_at`, `last_access` | REAL | TTL 24 h |
| `bytes` | INTEGER | drives the 64 MB LRU cap |

```sql
CREATE INDEX idx_entries_bucket_expires ON entries(bucket, expires_at);
```

`set()` evicts to cap after writing; `get()` deletes an expired row on read.

## `reports/manifest.sqlite`

### `issuers`

| Column | Type |
|:---|:---|
| `cik` PK, `symbol`, `name`, `synced_at` |

12 h freshness gate for the filing index.

### `filings_index`

| Column | Type | Notes |
|:---|:---|:---|
| `accession` | TEXT PK | |
| `cik` | INTEGER | |
| `form`, `filed`, `period_of_report` | TEXT | |
| `primary_document`, `source_url` | TEXT | Archives URL |
| `synced_at` | REAL | |

Indexes: `(cik, filed DESC)`, `(cik, form, filed DESC)`.

Populated from `https://data.sec.gov/submissions/CIK##########.json`
(`filings.recent`), cached 12 h in-process and 12 h in SQLite. This replaced an
edgartools filings collection that took minutes on a cold cache.

### `artifacts`

| Column | Type | Notes |
|:---|:---|:---|
| `accession` | TEXT PK | |
| `cik`, `form`, `filed`, `period_of_report`, `primary_document`, `source_url` | | filing identity |
| `profile` | TEXT | `10-K`, `10-Q`, `8-K`, `proxy`, `generic` |
| `parser_version` | TEXT | `0.58.1` |
| `rules_version` | TEXT | `"1"` |
| `schema_version` | INTEGER | `1` |
| `html_sha256`, `html_bytes`, `artifact_bytes` | | integrity and size |
| `element_count`, `section_count`, `note_count`, `table_count` | INTEGER | counts |
| `coverage_json`, `warnings_json` | TEXT | coverage dict, parser warnings |
| `status` | TEXT | `ready` or `failed` |
| `error` | TEXT | failure reason |
| `built_at`, `last_access` | REAL | LRU |

Indexes: `(cik, filed DESC)`, `(last_access)`, `(status)`.

### Artifact files

```
artifacts/{cik}/{accession}.semantic.json.gz     parsed sections, elements, tables
artifacts/{cik}/{accession}.html.gz              raw filing HTML
artifacts/{cik}/{accession}.lock                 build lock (flock)
```

Artifact JSON top-level keys:

```json
{
  "schema": 1, "accession": "…", "symbol": "AAPL", "cik": 320193,
  "form": "10-K", "filed": "…", "period_of_report": "…",
  "primary_document": "…", "source_url": "…", "profile": "10-K",
  "parser_version": "0.58.1", "rules_version": "1",
  "warnings": [], "coverage": {}, "sections": [], "elements": [],
  "tables": [], "parse_ms": 412
}
```

`_valid()` rejects an artifact unless `schema_version`, `rules_version` and
`parser_version` all match the running code **and** both files exist **and**
`status == "ready"`. That makes parser upgrades self-invalidating.

## Build lifecycle

```
request for sections/section/search/table
  → in-process LRU hit?            → return
  → manifest row valid + files?    → load gzip, remember, return
  → acquire artifacts/{cik}/{accession}.lock  (flock, 30 s)
       → re-check (another process may have built it)
       → GET source_url (edgartools fallback); enforce VW_MAX_HTML_MB
       → write {accession}.html.gz atomically
       → sec_parser.parse → sections → tables
       → write {accession}.semantic.json.gz atomically
       → UPSERT artifacts status='ready'
```

A failure records `status='failed'` with the error, so the next call retries
rather than serving a half-built artifact.

## Versioning

| Version | Location | Invalidates |
|:---|:---|:---|
| `api_version = 1` | each service | cross-module compatibility |
| `VOCABULARY_VERSION = 1` | `fundamentals/domain/concepts.py` | line-item mapping changes |
| `FORMULA_VERSION = 1` | `analysis/domain/metrics.py` | metric cache |
| `model_version = 1` | DCF output | consumers reading DCF output |
| `SCHEMA_VERSION = 1` | `reports/store/artifact_store.py` | artifact JSON |
| `RULES_VERSION = "1"` | `reports/store/artifact_store.py` | section heuristics |
| `PARSER_VERSION = "0.58.1"` | `reports/sources/secparser_source.py` | parser output |

Bump the relevant constant whenever its semantics change; caches and artifacts
invalidate themselves.

## Retention

| Store | Policy |
|:---|:---|
| `facts` | LRU over `VW_MAX_FACTS_COMPANIES` (default 100 issuers) |
| `entries` | TTL + 64 MB cap |
| `artifacts` | LRU in-process (`VW_ARTIFACT_LRU`, default 2); files persist until deleted |
| `edgar/` | external library cache, disposable |

Safe to delete at any time: `analysis/cache.sqlite`, `entries` rows,
`artifacts/` and `edgar/`. Deleting `fundamentals/cache.sqlite` forces a
re-download of company facts (a few MB per issuer).

## Migration policy

There is no migration framework, and none is needed:

- Schema changes are additive (`CREATE TABLE IF NOT EXISTS`).
- Non-additive changes bump the relevant version constant, which invalidates
  artifacts and cache entries.
- A downgrade requires deleting `modules/*` so the older code rebuilds.

Never write a cross-module foreign key. `facts.cik` references `companies` inside
the same database only.

## Next

- [Testing](05-testing.md)
- [Reports and parser](06-reports-parser.md)
