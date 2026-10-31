# 01 — Architecture

valuebot is a stdio MCP server split into modules **isolated by the data they
use**. Each module owns one data lifecycle end to end: its own source adapter,
domain rules, SQLite store, tools and tests.

## Why isolation by data, not by layer

A layered split (sources / services / tools) puts every data concern in every
layer: one schema change touches all of them, and a parser regression can affect
numeric correctness. Splitting by data ownership means:

| Property | Consequence |
|:---|:---|
| One writer per store | no cross-module migrations, no lock contention |
| One failure domain | `sec-parser` upgrade cannot break XBRL ratios |
| Independent tests | reports tests never need facts fixtures |
| Clear removal path | a reserved module can ship as a protocol only |
| Explicit edges | the one cross-module dependency is visible in imports |

## Modules

| Module | Owns | Tools | Depends on |
|:---|:---|:---|:---|
| `core` | config, identity, models, errors, citations, cache, envelope | — | nothing |
| `fundamentals` | SEC XBRL facts, company identity, statements, line-item vocabulary | 5 | `core` |
| `analysis` | ratio/growth metrics, DCF | 3 | `core`, `fundamentals` (line items only) |
| `reports` | filing index, filing HTML, sec-parser semantics, tables | 5 | `core` |
| `thesis` | read-only vault reader | 2 | `core` |
| `calendar` | reserved protocol | 0 | `core` |
| `price_action` | reserved protocol | 0 | `core` |

`reports` deliberately does **not** depend on `fundamentals`: listing,
downloading and parsing a filing is one data lifecycle, and facts already carry
`accession`, `form_type` and `filing_date`, so fundamentals needs nothing from
reports.

## Dependency direction

```
                     ┌──────────────┐
                     │     core     │
                     └──────┬───────┘
        ┌──────────────┬────┴─────┬──────────────┬─────────────┐
        ▼              ▼          ▼              ▼             ▼
  fundamentals      reports    thesis       calendar     price_action
        ▲
        │  LineItemSeries only
        │
    analysis
```

Rules enforced by `tests/contract/test_isolation.py`:

1. A module imports only `core` plus its own package.
2. The sole exception is `analysis` importing the fundamentals **service**, and
   only for `line_items()`.
3. No module imports another module's `store/` or `domain/` internals.
4. `server.py` is the only place that constructs module services.

## Composition root — `mcp/server.py`

```python
mcp = MCPServer(name="valuebot", version="0.2.0", instructions=INSTRUCTIONS)

STATES = build_modules()      # guarded construction, one ModuleState per module
register_tools(STATES)        # real tools, or stubs for a failed module
mcp.run()
```

`build_modules()` wraps each constructor in `_build()`. If a module raises —
missing dependency, unreadable store — it becomes:

```python
ModuleState(name="reports", status="unavailable",
            error="…", error_code="module_unavailable")
```

and `register_tools()` installs stubs that return a typed
`module_unavailable` failure, so the remaining modules stay usable. A missing
`edgartools` install therefore never takes down `thesis`.

`ping` reads the same `STATES` mapping, so health and behaviour cannot drift.

### Path-shadow guard

The plugin's server directory is named `mcp`, which would shadow the installed
`mcp` SDK as a namespace package. `server.py` removes `""` and the plugin root
from `sys.path` before importing the SDK, then prepends its own directory.
Tests avoid the problem by importing `core` / `modules` directly.

## Request lifecycle

```
LibreChat → MCP tools/call
   → tool function in modules/<name>/tools/__init__.py
      → validate arguments (range clamps, enum checks)
      → service method
          → source adapter (SEC / sec-parser / filesystem) with lazy import
          → store (SQLite) or in-process LRU
          → domain rules (concepts, metrics, dcf, sections, tables)
      → core.response.success(...) / failure(...)
   → byte cap → nested-list shrink → JSON-RPC response
```

Every tool follows the same four beats: clamp, call, cite, cap.

### Response envelope

`core/response.py` builds one shape for every call:

| Field | Notes |
|:---|:---|
| `ok`, `module`, `tool` | always present |
| `symbol`, `cik` | when known |
| `data` | module payload |
| `citations` | deduplicated by `key`, max 20 |
| `paging` | `offset`, `limit`, `total`, `next_offset`, `truncated` |
| `meta` | `elapsed_ms`, `bytes` |
| `error` | on failure: `code`, `message`, `retryable`, `hint` |

`cap_bytes()` truncates oversized strings; `_shrink()` then trims the largest
nested list until the JSON fits, setting `"truncated": true`. After shrinking it
restores `ok`/`module`/`tool`/`symbol` so the envelope can never be mangled.

### Errors

`core/errors.py` defines `ValuebotError` with `code`, `retryable`, `hint`,
`retry_after_s` and `details`. Each tool wraps unexpected exceptions in
`InternalError`:

```python
except Exception as exc:
    return _error("ratio_compute", exc, started)
```

No traceback, no file path and no SQL text ever reaches the model.

### Citations

`core/citations.py` mints the citation dict and a stable 16-hex `key` from
`(source, accession, form, filed, section, url)`. Identical sources dedupe;
different filings never collide. The model may not invent citations — it only
references keys the server issued.

## Configuration and identity

`core/config.py` resolves every path and limit as **env → default**, with
`${VAR}` templating. `core/identity.py` owns the one-time User-Agent file:

```
env override (SEC_USER_AGENT / EDGAR_IDENTITY)
   ↓
${PLUGIN_DATA}/identity.json
   ↓
missing → identity_not_configured
```

There is no built-in default, so the plugin cannot accidentally call SEC with an
anonymous User-Agent. See
[02-configuration.md](../users/02-configuration.md#sec-user-agent).

## Isolation boundaries at runtime

| Boundary | Implementation |
|:---|:---|
| Process | one server process per LibreChat spawn |
| Storage | one SQLite file per module |
| Artifacts | `modules/reports/artifacts/{cik}/{accession}.*` |
| Concurrency | one build lock per accession; WAL on every DB |
| Cache scope | per module, keyed with `facts_version` / `formula_version` |
| Secrets | one file, `0600`, outside the plugin folder |

## What is deliberately absent

| Absent | Reason |
|:---|:---|
| Shared ORM | a schema change would cross four modules |
| Global mutable state | servers are spawned per user/session |
| Cross-module SQL joins | forces co-deployment and breaks isolation |
| Background schedulers | no long-running jobs; SEC calls are request-scoped |
| Price data | `price_action` is reserved |
| A vector store | filing text is already structured by section |

## Next

- [Module contracts](02-module-contracts.md)
- [Data model](03-data-model.md)
