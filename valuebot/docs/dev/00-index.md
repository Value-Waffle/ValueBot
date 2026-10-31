# Developer guide

Internals of valuebot v2: architecture, module contracts, storage, testing and
extension points. Read the [user guide](../users/00-index.md) first for what the
plugin does.

## Reading order

| # | Document | Covers |
|:---|:---|:---|
| 01 | [Architecture](01-architecture.md) | module boundaries, dependency rules, request lifecycle, composition root |
| 02 | [Module contracts](02-module-contracts.md) | public surfaces, the single cross-module edge, reserved protocols |
| 03 | [Data model](03-data-model.md) | SQLite schemas, keys, TTLs, versioning, artifact layout |
| 04 | [Development setup](04-development-setup.md) | Python 3.12, venv, bootstrap, running the server by hand |
| 05 | [Testing](05-testing.md) | every test file, fixtures, markers, how to add tests |
| 06 | [Reports and parser](06-reports-parser.md) | sec-parser constraints, item heuristic, tables, artifact lifecycle |
| 07 | [Analysis and DCF](07-analysis-and-dcf.md) | metric engine, quality states, DCF model and validation |
| 08 | [Deployment](08-deployment.md) | manifests, loader behaviour, packaging, CI |
| 09 | [Roadmap](09-roadmap.md) | `calendar` and `price_action` protocols |
| 10 | [Contributing](10-contributing.md) | adding tools, metrics, modules; review checklist |

The [product roadmap](../roadmap.md) covers the whole feature pipeline, with
release windows and exit criteria.

## Quick orientation

```
valuebot/
├── plugin.json                 Agent Plugins 1.0.0 manifest
├── mcp.json                    stdio server launch + env contract
├── setup.sh                    one-time SEC User-Agent setup
├── skills/                     5 SKILL.md bundles
├── agent-builder-exports/      6 reference agent personas
├── mcp/
│   ├── server.py               composition root: build modules, register tools, ping
│   ├── core/                   config, identity, models, errors, citations, cache, envelope, response
│   └── modules/
│       ├── fundamentals/       edgartools XBRL facts and statements
│       ├── analysis/           36 metrics + FCFF DCF
│       ├── reports/            filing index + sec-parser semantics
│       ├── thesis/             read-only vault reader
│       ├── calendar/           reserved protocol, no tools
│       └── price_action/       reserved protocol, no tools
└── tests/                      unit, contract, integration
```

## Invariants

1. A module owns its data: schema, files and caches are private.
2. Cross-module access only through a documented protocol — never SQL, never a
   file path.
3. `analysis → fundamentals` is the only module-to-module edge.
4. Every numeric claim leaves the server with a citation.
5. Failures are typed; no stack trace reaches the model.
6. Responses are byte-capped and pageable; stdout is reserved for JSON-RPC.

## Where to change what

| Change | File |
|:---|:---|
| Add or change a line item | `mcp/modules/fundamentals/domain/concepts.py` |
| Add or change a metric | `mcp/modules/analysis/domain/metrics.py` + `engine.py` |
| Change DCF behaviour | `mcp/modules/analysis/domain/dcf.py` |
| Change section/note detection | `mcp/modules/reports/domain/sections.py` |
| Change table rendering | `mcp/modules/reports/domain/tables.py` |
| Change filing discovery | `mcp/modules/reports/sources/edgar_source.py` |
| Add a tool | `mcp/modules/<module>/tools/__init__.py` |
| Add configuration | `mcp/core/config.py` (+ `mcp.json`, `.env.example`, docs) |
| Add an error type | `mcp/core/errors.py` |
| Change response caps | `mcp/core/response.py` call sites |

## Other sources

| Document | Purpose |
|:---|:---|
| [`../../../architecture/design-docs/valuebot-v2/design.md`](../../../architecture/design-docs/valuebot-v2/design.md) | full design rationale |
| [`../../../architecture/design-docs/valuebot-v2/db-mapping.md`](../../../architecture/design-docs/valuebot-v2/db-mapping.md) | data element → storage mapping |
| [`../../../architecture/design-docs/valuebot-v2/implementation-plan.md`](../../../architecture/design-docs/valuebot-v2/implementation-plan.md) | task breakdown and reuse matrix |
| [`../../README.md`](../../README.md) | repository overview |
