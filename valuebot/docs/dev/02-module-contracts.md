# 02 — Module contracts

Each module exposes a small public surface. Tools call it; other modules must
not reach past it. This page is the reference for those surfaces.

## Contract rules

1. A module's public surface is its service object (or module functions for
   `thesis`) plus the `api_version` int.
2. Arguments and returns are dataclasses from `core/models.py` or plain dicts of
   primitives — never a module's internal row type.
3. A caller never receives a `sqlite3.Connection`, a file handle or a path.
4. Raising is the only error channel; the tool layer converts to the envelope.
5. Breaking a signature means bumping `api_version`.

## `core`

Not a service — a library every module may import.

| Export | Purpose |
|:---|:---|
| `config` | resolved roots, limits, `refresh()`, `describe()`, `require_identity()` |
| `identity` | `save/load/exists/path/normalize_user_agent/is_placeholder` |
| `models` | 25 frozen dataclasses shared across boundaries |
| `errors` | `ValuebotError` hierarchy with stable `code` values |
| `citations` | `cite()`, `edgar_url()`, `merge()`, `MAX_CITATIONS = 20` |
| `ttl_cache` | `SqliteTtlCache` with byte cap and TTL |
| `envelope` | `cap_bytes()`, `chunk_text()` |
| `response` | `success()`, `failure()`, `page()`, `timer()` |

## `fundamentals` — `FundamentalsService`

```python
api_version = 1

def __init__(self, source=None, db_path=None)
def resolve(self, query: str, limit: int = 10) -> list[dict]
def profile(self, symbol: str, *, refresh: bool = False) -> dict
def facts(self, symbol: str, **kwargs) -> dict
def timeseries(self, symbol: str, concept: str, **kwargs) -> dict
def statement(self, symbol: str, statement: str, *, basis: str = "company",
              periods: int = 4, accession: str | None = None,
              currency: str = "USD") -> dict
def line_items(self, symbol: str, items: Sequence[str], *, periods: int = 5,
               annual_only: bool = True,
               balance_basis: str = "average") -> LineItemSeries
def concept_vocabulary(self) -> dict[str, tuple[str, ...]]
def close(self) -> None
conn  # public property, for tests and maintenance only
```

Owns: `companies`, `facts`, the line-item vocabulary, statement normalisation,
the profile cache.

### The `LineItemSeries` contract

This is the **only** structure that crosses a module boundary.

```python
@dataclass(frozen=True)
class LineItemSeries:
    symbol: str
    cik: int
    currency: str
    periods: tuple[str, ...]                    # period_end values, newest first
    items: dict[str, tuple[LineItemValue, ...]]
    facts_version: str                          # "<facts_synced_at>:<fact_count>"
```

```python
@dataclass(frozen=True)
class LineItemValue:
    line_item: str
    label: str
    unit: str
    period_end: str
    value: float | None
    concept: str            # the XBRL concept actually used
    citation: dict | None
```

Guarantees:

| Guarantee | Detail |
|:---|:---|
| Aligned periods | every item's tuple is ordered by `periods` and contains only those period ends |
| Annual instants only | balance-sheet items are filtered to fiscal year-ends, not quarters |
| Average basis | `average` averages an instant with the prior fiscal period |
| Every value cited | `citation` is always populated for a real value |
| Stable versioning | `facts_version` changes when the issuer re-syncs |

`line_items()` returns an item as an **empty tuple** when no concept matched —
callers must treat that as `unavailable`, never as zero.

### Vocabulary

36 line items in `domain/concepts.py`, each with candidate concepts (first match
wins), `unit`, `period_type` (`duration`/`instant`) and optional
`derived_from` (used by `total_debt`). `VOCABULARY_VERSION = 1`.

| Group | Items |
|:---|:---|
| income | `revenue`, `cost_of_revenue`, `gross_profit`, `operating_expenses`, `operating_income`, `da`, `interest_expense`, `pretax_income`, `income_tax`, `net_income` |
| per share | `eps_basic`, `eps_diluted`, `shares_basic`, `shares_diluted`, `sbc` |
| current assets | `cash`, `short_term_investments`, `accounts_receivable`, `inventory`, `current_assets` |
| non-current / totals | `total_assets`, `ppe_net`, `goodwill` |
| liabilities | `accounts_payable`, `current_liabilities`, `total_liabilities`, `short_term_debt`, `long_term_debt`, `total_debt` (derived) |
| equity | `equity`, `retained_earnings` |
| cash flow | `cfo`, `capex`, `cfi`, `cff`, `dividends_paid` |

## `analysis` — `AnalysisService`

```python
api_version = 1

def __init__(self, facts, cache_path=None)          # facts = FundamentalsService
def catalog(self, symbol: str | None = None, family: str | None = None) -> dict
def compute(self, symbol: str, metric_ids, *, periods: int = 5,
            balance_basis: str = "average",
            include_inputs: bool = True) -> dict
def dcf(self, symbol: str, *, overrides: dict | None = None,
        assumptions_only: bool = False) -> dict
def close(self) -> None
```

Depends on `fundamentals` **only** through `line_items()`. Owns: the metric
catalog, the metric cache, DCF arithmetic. Stores no facts of its own.

Cache key:

```
metric:{cik}:{metric_id}:{period}:{basis}:{formula_version}:{facts_version}
```

TTL 24 h, bucket `metrics`, 64 MB LRU cap. DCF results are never cached.

## `reports` — `ReportsService`

```python
api_version = 1

def __init__(self, source=None, db_path=None, artifacts_root=None)
def filings(self, symbol: str, *, forms=None, start=None, end=None,
            limit: int = 50, offset: int = 0) -> dict
def artifact(self, symbol: str | None, accession: str | None, form: str) -> dict
def sections(self, *, symbol=None, accession=None, form="10-K", kind="all",
             include_tables=False, offset=0, limit=40) -> dict
def section(self, *, symbol=None, accession=None, form="10-K", section_id: str,
            offset=0, limit_chars=8000) -> dict
def search(self, *, symbol=None, accession=None, form="10-K", query: str,
           limit=20) -> dict
def table(self, *, symbol=None, accession=None, form="10-K", table_id: str,
          columns=None, row_offset=0, max_rows=40) -> dict
def close(self) -> None
conn  # public property, tests only
```

Owns: `filings_index`, `issuers`, `artifacts`, `entries`, the HTML/artifact
files, sec-parser integration.

Sources: `sources/edgar_source.py` (ticker resolution via edgartools, index via
SEC submissions JSON, HTML via `requests` with an edgartools fallback) and
`sources/secparser_source.py`.

`artifact()` is the internal build entry point: cache → manifest → build lock →
parse → persist. `section()`, `search()` and `table()` all go through it, so a
filing is parsed at most once per artifact version.

## `thesis` — module functions

```python
BYTE_CAP = 8 * 1024

def thesis_read(symbol: str, file: str | None = None,
                offset: int = 0, limit: int = BYTE_CAP) -> dict
def thesis_annotations(symbol: str, doc: str | None = None,
                       offset: int = 0, limit: int = 50) -> dict
def parse_front_matter(text: str) -> tuple[dict, str, str]
```

Read-only by construction: paths are normalised, resolved, and rejected if they
escape `{VW_THESIS_ROOT}/{TICKER}/`. No writes, no deletes, no network.

An empty vault returns `ok: true` with `has_thesis: false`; it is not an error.

## `calendar` and `price_action` — reserved

```python
@runtime_checkable
class CalendarAPI(Protocol):
    api_version: int
    def events(self, symbol: str, *, kinds=None,
               start=None, end=None) -> dict: ...

@runtime_checkable
class PriceAPI(Protocol):
    api_version: int
    def history(self, symbol: str, *, period: str = "1y",
                interval: str = "1d") -> dict: ...
```

No tools, no stores, no dependencies. See [Roadmap](09-roadmap.md).

## Cross-module call graph

```
server.py
 ├─ FundamentalsService() ............................. fundamentals
 ├─ AnalysisService(fundamentals) ..................... analysis
 │     └─ facts.line_items(symbol, items, periods, balance_basis)
 ├─ ReportsService() .................................. reports
 ├─ thesis service module ............................. thesis
 └─ ping .............................................. reads ModuleState only
```

`reports`, `thesis`, `calendar` and `price_action` never see another module's
objects. That is what makes a `sec-parser` upgrade safe and a fundamentals
outage non-fatal for filing reads.

## Enforcement

`tests/contract/test_isolation.py` parses the import graph:

| Assertion | Meaning |
|:---|:---|
| allowed import matrix | a module may import `core` and itself only |
| single cross-module edge | `analysis` → `fundamentals.service` |
| no store imports | no `modules.<other>.store` imports anywhere |
| no server imports in modules | modules never import `server` |
| `api_version` present | every service declares it |

Add a module or an edge and this test fails first — by design.

## Next

- [Data model](03-data-model.md)
- [Contributing](10-contributing.md)
