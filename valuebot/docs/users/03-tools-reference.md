# 03 — Tools reference

Every valuebot capability is an MCP tool. This page documents all 18: what each
answers, its arguments, and its return shape.

## How tools appear in LibreChat

The MCP server is named `vw-mcp`, so LibreChat exposes each tool as
`<tool>_mcp_vw-mcp`:

```
facts_query  →  facts_query_mcp_vw-mcp
```

You never type these names. The model calls them; this page exists so you can
read responses and write precise prompts.

| Module | Tools |
|:---|:---|
| `fundamentals` | `symbol_resolve`, `company_profile`, `facts_query`, `facts_timeseries`, `statement_get`, `facts_export` |
| `analysis` | `ratio_catalog`, `ratio_compute`, `dcf_compute` |
| `reports` | `filing_list`, `report_sections`, `report_section`, `report_search`, `report_table` |
| `thesis` | `thesis_read`, `thesis_annotations` |
| `core` | `ping`, `citation_resolve` |

## Response envelope

Every successful call returns:

```json
{
  "ok": true,
  "module": "fundamentals",
  "tool": "facts_query",
  "symbol": "AAPL",
  "cik": 320193,
  "data": { "rows": [ ... ], "total": 19 },
  "citations": [ { "key": "…", "label": "…", "accession": "…", "form": "10-K" } ],
  "paging": { "offset": 0, "limit": 20, "total": 19, "next_offset": null, "truncated": false },
  "meta": { "elapsed_ms": 41, "bytes": 3120 }
}
```

A failure returns:

```json
{
  "ok": false,
  "module": "fundamentals",
  "tool": "facts_query",
  "error": {
    "code": "identity_not_configured",
    "message": "SEC User-Agent is not configured",
    "retryable": false,
    "hint": "Run the one-time setup: ./setup.sh your@email.com …"
  },
  "meta": { "elapsed_ms": 0 }
}
```

### Caps and paging

| Cap | Tools |
|:---|:---|
| 6 KB | `ping` (4 KB), `symbol_resolve`, `company_profile`, `facts_query`, `facts_timeseries`, `ratio_catalog`, `filing_list`, `report_sections` |
| 8 KB | `statement_get`, `facts_export`, `ratio_compute`, `dcf_compute`, `report_section`, `report_search`, `report_table`, `thesis_read`, `thesis_annotations` |
| 12 KB | `citation_resolve` |

When a payload would exceed its cap, the largest nested list is trimmed and
`"truncated": true` is added — the response is never cut mid-JSON. Prefer
`offset`/`next_offset` paging over relying on truncation.

### Citations

Citations are minted by the server, never by the model:

| Field | Meaning |
|:---|:---|
| `key` | stable 16-char hash; identical sources deduplicate |
| `label` | human-readable description |
| `source` | `sec-xbrl`, `sec-report`, `thesis`, … |
| `accession`, `form`, `filed`, `period` | filing provenance |
| `section` | section ID for report citations |
| `citation_id` | opaque URL-safe token that opens the artifact; the field to pass to `citation_view` / `citation_resolve` |
| `artifact` | resolvable raw-material locator; open it with `citation_resolve` |

A response carries at most 20 citations. Table-only slices still get one
filing citation.

### Citations are identifiers — no URLs

A citation is an identifier, not a link. `cite()` never invents a URL and no
module attaches one, so every citation carries `citation_id` and **no `url`**.
The `references` footer is therefore plain text.

| Source | Raw material | How to open it |
|:---|:---|:---|
| `sec-xbrl`, `sec-statement` | Cached XBRL companyfacts rows | `citation_view(citation_id=…)` inline panel, or `citation_resolve` for text |
| `sec-report` | cached filing HTML / semantic cache (`original_url` holds the SEC HTML) | `citation_view(citation_id=…)` inline panel, or `citation_resolve` for text |
| `derived-analysis` | cached metric inputs | `citation_view(citation_id=…)` inline panel, or `citation_resolve` for text |
| `thesis` | local vault markdown | `citation_view(citation_id=…)` inline panel, or `citation_resolve` for text |

`original_url` is provenance only: it is the SEC HTML the report artifact was
parsed from, and it is never the citation link.

Every successful response still reports the viewer's state under `meta.viewer`
(`enabled`, `base_url`, `public_base`, `public_base_source`,
`reachable_hint`, `last_error`). With the viewer disabled by default that
block reports `enabled: false`; it is diagnostic information only and no
citation depends on it.

#### `citation_id`

Every citation carrying an `artifact` also carries a `citation_id`: an opaque,
URL-safe token that encodes the artifact locator.

The token is machine data in `citations[]`; a reader never sees it. It is not
part of the `references` footer.

```
citation_resolve(citation_id="eyJhY2Nlc3Npb24iOi…", offset=0, limit_chars=8000)
```

- It needs **no URL and no browser**, so it works identically for local,
  Docker and remote LibreChat deployments.
- It is deterministic: the same artifact always yields the same token, and
  different concepts, sections or periods never collide.
- A malformed or incomplete token returns `citation_unresolvable`.

#### `references` — the server-rendered footer

Every successful response carries a ready-to-use footer. The server numbers it
for human-readable attribution to the reader:

```json
"references": [
  {"n": 1, "label": "MSFT 10-K FY2026, Item 7", "source": "sec-report",
  "status": "cached"}
]
```

The footer is human-readable attribution, not machine data: it carries no
`url`, no `citation_id` token, and no URI. The model must never reproduce the
raw array. `status` is `cached` or `not_cached` when the citation's artifact
provides it. Entries are deduplicated and capped at 20, and the block survives
response truncation.

#### `citation_view` — inline evidence panel

```
citation_view(citation_id="eyJhY2Nlc3Npb24iOi…", offset=0, limit_chars=8000)
citation_view(citation={"citation_id": "eyJhY2Nlc3Npb24iOi…"}, offset=0, limit_chars=8000)
```

Returns the evidence as a rendered panel instead of a link:

- a short text summary (`kind: … · format: … · chars: …`, with optional
  `next_offset`), and
- an embedded `ui://valuebot/evidence/<token>` resource with `text/html`.

LibreChat renders that resource **inline** as a sandboxed panel and hands the
model a marker to place in its answer. This is the primary evidence channel:
the browser talks only to LibreChat, so it needs **no browser-to-plugin network
path** and works in every deployment. The text summary contains no URI; the
`ui://` address lives solely inside the embedded resource block. Use it whenever
the user should read the filing section itself. Citations never carry the
viewer's url.

A citation whose artifact is not cached returns a plain text explanation naming
the tool to run first — never an error.

#### Citation coverage guard

Every response reports `meta.citation_coverage`:

```json
{"values": 12, "cited": 12, "dropped": 0, "ok": true}
```

A cached fact row (an object with `accession` and `period_end`) that no
citation in the same response attributes has its value **stripped** and is
marked `quality: "uncited"`. The guard fails closed, so a number computed from
the local cache can never be emitted without the citation that proves it. When
`dropped > 0`, the `uncited` list names up to ten affected rows.

#### The artifact viewer — opt-in debug surface (off by default)

The viewer is **off by default** (`VW_ARTIFACT_HTTP_PORT=0`). It is a debugging
convenience for an operator sitting on the MCP host, not an evidence channel:
it binds loopback inside the MCP/LibreChat container, so a browser elsewhere in
the network cannot reach it. Citations never carry its url.

The evidence channel is the `ui://` inline panel from `citation_view` (§ above),
which renders in LibreChat's own origin and needs no network path back to the
plugin.

| Setting | Default | Meaning |
|:---|:---|:---|
| `VW_ARTIFACT_HTTP_PORT` | `0` (off) | set a port, e.g. `8765`, to enable the viewer |
| `VW_ARTIFACT_HTTP_HOST` | `127.0.0.1` | interface to bind; `0.0.0.0` only for container debugging |
| `VW_ARTIFACT_PUBLIC_BASE_URL` | `""` (auto) | override the inferred browser address |

When enabled, the viewer serves resolved artifacts at `/a`, rendering each as
an HTML page. For a cached report section, `kind=semantic-section` plus
`section_id` opens exactly that section, parsed by sec-parser:

```
http://127.0.0.1:8765/a?t=<token>&module=reports&kind=semantic-section&cik=320193&accession=0000320193-25-000079&section_id=part2-item7
```

**How the address is chosen** (only relevant when the viewer is enabled)

1. `VW_ARTIFACT_PUBLIC_BASE_URL`, when set, always wins.
2. Otherwise it is inferred from the socket that actually bound: a loopback
   bind gives `http://127.0.0.1:<port>`; a wildcard bind gives this machine's
   address.
3. If the port is already taken, the viewer stays off. The failed bind is
   reported as `artifact_viewer.last_error` in `ping` and logged at warning
   level — it is not silent. Citations are unaffected either way: they never
   carry a link.

`ping` reports the same block under `artifact_viewer` (`enabled`, `base_url`,
`public_base`, `public_base_source`, `reachable_hint`, `last_error`).

**Debugging from a different machine.** Bind host and public base differ only
when the browser is not on the MCP host.

- Docker: `-p 8765:8765`, `VW_ARTIFACT_HTTP_HOST=0.0.0.0`,
  `VW_ARTIFACT_PUBLIC_BASE_URL=http://localhost:8765`.
- Remote host: set the public base to the address you type in the browser, e.g.
  `https://research.internal/valuebot`.

Other behaviour:

- Every request must carry the `t` token generated at process start; without
  it the viewer answers `403` — the thesis vault is private.
- The viewer resolves through the same registry as `citation_resolve`, so it
  can only surface material the tools would surface. It never builds artifacts
  and never touches the network.
- `format=raw` returns plain text instead of the HTML page; `offset` / `limit`
  page long artifacts.

---

## Error codes

| Code | Retryable | Meaning | Fix |
|:---|:---:|:---|:---|
| `identity_not_configured` | no | no `identity.json` and no override | run `./setup.sh` |
| `symbol_not_found` | no | ticker or query has no match | call `symbol_resolve` first |
| `company_not_found` | no | CIK resolves but no company record | check the ticker |
| `filing_not_found` | no | accession or form is missing | call `filing_list` |
| `section_not_found` | no | bad section ID for this form | call `report_sections` |
| `table_not_found` | no | bad table ID | call `report_sections` with `include_tables=true` |
| `statement_unavailable` | no | statement type not tagged by this issuer | try another statement |
| `metric_not_found` | no | unknown metric ID | call `ratio_catalog` |
| `metric_unavailable` | no | metric cannot be computed | read the quality state |
| `invalid_argument` | no | argument outside the documented range | fix the call |
| `edgar_unavailable` | yes | SEC request failed (network, 403) | check identity and connectivity |
| `edgar_rate_limited` | yes | throttled | wait `retry_after_s` |
| `artifact_too_large` | no | filing HTML above `VW_MAX_HTML_MB` | raise the cap or skip the filing |
| `artifact_not_cached` | no | the citation's raw material is not cached locally | run the tool named in the `hint` |
| `citation_unresolvable` | no | no `artifact` block, or its module is unavailable | pass a citation returned by a module tool |
| `parser_failed` | no | sec-parser could not process the document | report the accession |
| `module_unavailable` | yes | one module failed to start | check the server log |
| `internal_error` | no | unexpected failure | report with the accession |

---

## `ping`

Health and configuration snapshot. Start here when something looks wrong.

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| — | — | — | none |

Returns `modules` (`status`, `api_version`, optional `error`), `tools`,
`identity_configured`, `identity_source` (`file`, `env`, `env (EDGAR_IDENTITY
alias)` or `missing`), `identity_file`, `version` and `paths`.

```json
{
  "data": {
    "server": "valuebot",
    "version": "0.2.0",
    "modules": { "fundamentals": {"status": "ready", "api_version": 1}, "…": {} },
    "tools": ["ping", "symbol_resolve", "…"],
    "identity_configured": true,
    "identity_source": "file",
    "identity_file": "/app/data/plugins/valuebot/identity.json",
    "paths": { "plugin_data": "…", "fundamentals": "…", "reports": "…", "thesis": "…" }
  }
}
```

A module that fails to start reports `status: "unavailable"` with its error; the
other modules keep working and their tools stay registered.

---

## `citation_resolve`

Open the raw material behind any citation that carries an `artifact` block: the
filing text, the XBRL rows, the derived metric inputs or the vault markdown it
points at. Read-only and offline — resolution never builds artifacts and never
touches the network.

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `citation` | object | — | the full citation returned by a module tool, not just its `key` |
| `offset` | int ≥ 0 | 0 | character offset into the artifact text |
| `limit_chars` | int 1000–12000 | 8000 | characters to return |

Returns the resolver payload: `kind`, `format`, `chunk`, `next_offset`,
`total_chars` and per-kind extras (`path` and `preview` for `facts-xlsx`), plus
the resolved `citation` and a `paging` block (`offset`, `next_offset`,
`truncated`).

| `artifact.kind` | Module | Resolves to |
|:---|:---|:---|
| `semantic-section` | `reports` | one section as markdown |
| `semantic-table` | `reports` | one table as a GFM grid |
| `semantic-index` | `reports` | section/table index listing |
| `raw-html` | `reports` | the filing HTML |
| `facts-json` | `fundamentals` | companyfacts-shaped JSON with the concept rows |
| `facts-txt` | `fundamentals` | TSV concept rows |
| `facts-xlsx` | `fundamentals` | export `path` + `preview` (binary, never inlined) |
| `derived-inputs` | `analysis` | one metric's cached inputs as JSON |
| `vault-doc` | `thesis` | vault markdown |

Page with `offset`/`next_offset` until `next_offset` is `null`. Offsets index
the full artifact text, so paging never duplicates or skips characters.

| Error | When | Fix |
|:---|:---|:---|
| `citation_unresolvable` | no `artifact` block, or its `module` is not available | pass a citation returned by a module tool |
| `artifact_not_cached` | the raw material is not cached locally | run the tool named in the `hint`, e.g. `report_section` |

---

## Fundamentals

### `symbol_resolve`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `query` | string | — | company name or ticker fragment |
| `limit` | int 1–25 | 10 | maximum matches |

Returns `query`, `matches[]` (`symbol`, `name`, `cik`, `score`) and `count`.
Score: 3 exact ticker, 2 ticker prefix, 1 substring match on ticker or name.

> Call this before any other tool when you are unsure of the exact ticker.

### `company_profile`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | — | exact ticker |
| `refresh` | bool | `false` | drop the cached profile and force a facts re-sync |

Returns the issuer identity (`symbol`, `cik`, `name`, `tickers`, `exchange`,
`sic`, `industry`, `fiscal_year_end`, `filer_category`, `is_foreign`) plus
`facts_cached`, `fact_count` and `data_available` for
`facts`/`reports`/`analysis`/`thesis`.

Use `refresh: true` after a new filing if a metric still reflects the old
period.

### `facts_query`

Raw XBRL facts, newest period first.

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | — | exact ticker |
| `concepts` | string or list | none | exact concept names, e.g. `["Revenues"]` |
| `search` | string | none | substring match on concept or label |
| `forms` | string or list | none | form that tagged the fact, e.g. `["10-K"]` |
| `start` | `YYYY-MM-DD` | none | inclusive **period-end** lower bound |
| `end` | `YYYY-MM-DD` | none | inclusive **period-end** upper bound |
| `unit` | string | none | XBRL unit, usually `USD` |
| `annual_only` | bool | `false` | keep annual duration facts (350–380 days) |
| `dedupe` | bool | `true` | one row per concept/period |
| `limit` | int 1–100 | 20 | rows per page |
| `offset` | int | 0 | row offset |

Returns `rows[]` (`concept`, `label`, `unit`, `value`, `numeric_value`,
`period_type`, `period_start`, `period_end`, `duration_days`, `fiscal_year`,
`fiscal_period`, `form_type`, `accession`, `filing_date`, `period_label`),
`total`, `facets` and `paging`.

> `start`/`end` filter the **period end**, never the filing date. `fiscal_year`
> is filing metadata and is not the period year — always reason from
> `period_end`.

### `facts_timeseries`

One concept over time.

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | — | exact ticker |
| `concept` | string | — | concept name |
| `annual_only` | bool | `true` | annual duration facts only |
| `start`, `end` | date | none | period-end bounds |
| `unit` | string | none | unit filter |
| `limit` | int 1–50 | 20 | points |

Returns `symbol`, `cik`, `concept`, `unit`, `points[]`.

### `statement_get`

A normalized annual statement with period citations.

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | — | exact ticker |
| `statement` | string | — | `income`, `balance` or `cashflow` |
| `basis` | string | `company` | `company` = canonical multi-period; `filing` = as reported in one filing |
| `periods` | int 2–20 | 4 | periods for the company basis |
| `accession` | string | none | filing for the `filing` basis |
| `offset` | int | 0 | row offset |
| `limit` | int 1–80 | 40 | rows per page |

Returns `statement`, `label`, `basis`, `unit`, `periods[]`, `period_ends{}`,
`rows[]` (`concept`, `label`, `depth`, `parent`, `is_total`, `unit`,
`values{}`), `citations{}` and `paging`.

Use `basis: "filing"` when you need the exact presentation a company filed;
use `company` for comparable multi-year series.

### `facts_export`

Export the raw XBRL concepts of one filing as a file, with a citation you can
open via `citation_resolve`.

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | — | exact ticker |
| `accession` | string | latest with facts | filing to export |
| `concepts` | string or list | none | restrict to these concept names |
| `format` | string | `json` | `json` (companyfacts shape), `txt` (TSV) or `xlsx` |
| `unit` | string | none | XBRL unit filter, e.g. `USD`, `shares` |

Writes `<exports>/<cik>/<accession>.concepts.<ext>` under
`VW_FUNDAMENTALS_EXPORTS` and returns `symbol`, `cik`, `accession`, `format`,
`path`, `bytes`, `fact_count`, `concept_count`, `preview` (the first 2000
characters of the export), `truncated` and one `facts-json` / `facts-txt` /
`facts-xlsx` citation.

Caps: 500 000 rows per export, 32 MB per export file (`artifact_too_large`
above either), and 64 MB of exports kept per module — older exports are evicted
as new ones land (`VW_MAX_EXPORTS_MB`).

---

## Analysis

### `ratio_catalog`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | none | report availability per metric for this issuer |
| `family` | string | none | one family: `profitability`, `liquidity`, `leverage`, `efficiency`, `cash_quality`, `per_share`, `growth` |

Returns `metrics[]` with `metric_id`, `label`, `family`, `formula`,
`line_items`, `unit`, `direction`, `window`, `version` and — when `symbol` is
given — `available` and `missing_line_items`.

### `ratio_compute`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | — | exact ticker |
| `metric_ids` | list or string | — | IDs, comma/semicolon separated if a string |
| `periods` | int 1–20 | 5 | periods to return (growth metrics fetch extra history automatically) |
| `balance_basis` | string | `average` | `average` or `ending` for instant line items |
| `include_inputs` | bool | `true` | attach the line-item inputs with citations |

Returns `periods[]`, `balance_basis`, `facts_version` and `results[]` where each
result is `metric_id`, `label`, `family`, `period_end`, `value`, `display`,
`unit`, `quality`, `formula`, `formula_version`, `inputs[]`, `reason`.

#### Quality states

| Quality | Meaning | Model behaviour |
|:---|:---|:---|
| `ok` | computed from complete inputs | may be quoted |
| `partial` | some components unavailable | quote only with the caveat |
| `gap` | not enough history for the window | do not estimate |
| `unavailable` | an input is missing for this issuer | say so |
| `not_meaningful` | inputs present but the ratio is meaningless (negative equity, zero denominator) | never present as a number |

#### Metric catalog

| Family | Metrics |
|:---|:---|
| profitability | `gross_margin`, `operating_margin`, `net_margin`, `roa`, `roe`, `roic`, `fcf_margin`, `dupont_return` |
| liquidity | `current_ratio`, `quick_ratio`, `cash_ratio`, `working_capital` |
| leverage | `debt_to_equity`, `net_debt`, `net_debt_to_ebitda`, `interest_coverage`, `equity_multiplier` |
| efficiency | `asset_turnover`, `inventory_turnover`, `receivables_turnover`, `dso`, `dio`, `dpo`, `cash_conversion_cycle`, `capex_to_revenue` |
| cash_quality | `fcf`, `fcf_per_share`, `cfo_to_net_income`, `accrual_ratio` |
| per_share | `book_value_per_share`, `revenue_per_share` |
| growth | `revenue_cagr` (3-year), `eps_cagr` (3-year), `fcf_cagr` (3-year), `equity_growth` (YoY), `share_dilution` (YoY) |

### `dcf_compute`

| Argument | Type | Default | Range | Meaning |
|:---|:---|:---|:---|:---|
| `symbol` | string | — | — | exact ticker |
| `assumptions_only` | bool | `false` | — | return the assumption table without valuation |
| `base_period_end` | date | latest | — | base year |
| `forecast_years` | int | 5 | 3–15 | explicit forecast horizon |
| `revenue_growth` | float or list | derived | −0.10 … 0.25 | one rate or one per year |
| `operating_margin` | float or list | derived | 0.00 … 0.60 | EBIT margin |
| `tax_rate` | float | derived | 0.00 … 0.40 | cash tax rate |
| `capex_pct_revenue` | float | derived | 0.00 … 0.30 | capex intensity |
| `da_pct_revenue` | float | derived | 0.00 … 0.20 | D&A intensity |
| `nwc_pct_revenue` | float | derived | −0.20 … 0.50 | change in net working capital |
| `wacc` | float | 0.09 | 0.03 … 0.30 | discount rate |
| `terminal_growth` | float | 0.025 | −0.02 … 0.04 | perpetuity growth |
| `terminal_method` | string | `gordon` | `gordon`, `exit_multiple` | terminal value method |
| `exit_multiple` | float | none | 3–30 | required for `exit_multiple` |
| `shares_diluted` | float | derived | — | share count |
| `net_debt` | float | derived | — | total debt minus cash |

All rates are decimals: `0.08` means 8%. Validation also requires
`wacc − terminal_growth ≥ 0.01`.

Returns `assumptions[]` (`name`, `value`, `display`, `unit`, `source`,
`derivation`, `periods_used`, `assumption_quality`, `citation`),
`assumptions_complete`, `valuation` (`enterprise_value`, `net_debt`,
`equity_value`, `shares_diluted`, `value_per_share`, `currency`), `terminal`
(`method`, `value`, `pv`, `share_of_ev`), `forecast[]`, `sensitivity`
(`wacc_values`, `growth_values`, `grid`), `warnings[]` and `model_version`.

Assumption order: `revenue_growth`, `operating_margin`, `tax_rate`,
`capex_pct_revenue`, `da_pct_revenue`, `nwc_pct_revenue`, `wacc`,
`terminal_growth`, `shares_diluted`, `net_debt`.

`source` is `user` (you supplied it), `derived` (from annual history) or
`default` (policy). `wacc` and `terminal_growth` are always `default` unless you
pass them, and the result then carries `assumptions_not_company_specific` in
`warnings`.

Model: `FCFF = EBIT × (1 − tax) + D&A − capex − ΔNWC`, discounted at `wacc`,
plus a Gordon or exit-multiple terminal value. Nothing is persisted; the same
inputs always give the same output.

> The output is intrinsic value under your assumptions, not a price target, and
> not investment advice.

---

## Reports

All report tools resolve a filing either by `accession` or by `symbol` +
`form` (default `10-K`, newest match).

Supported profiles: `10-K`/`10-K/A`, `10-Q`/`10-Q/A` (full item and note
heuristics), `8-K`/`8-K/A`, `20-F`, `40-F`, `DEF 14A` and `DEFA14A` (generic).

### `filing_list`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | — | exact ticker |
| `forms` | string or list | none | e.g. `["10-K"]` |
| `start`, `end` | date | none | period-of-report bounds |
| `limit` | int 1–100 | 50 | rows per page |
| `offset` | int | 0 | row offset |

Returns `symbol`, `cik`, `rows[]` (`accession`, `cik`, `form`, `filed`,
`period_of_report`, `primary_document`, `source_url`, `report_available`) and
`paging`. `report_available` is `true` when a parsed artifact already exists.

### `report_sections`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | none | ticker used when `accession` is omitted |
| `accession` | string | none | explicit filing |
| `form` | string | `10-K` | form used to resolve the newest filing |
| `kind` | string | `all` | `all`, `items` or `notes` |
| `include_tables` | bool | `false` | attach table summaries per section |
| `offset` | int | 0 | section offset |
| `limit` | int 1–80 | 40 | sections per page |

Returns `filing`, `profile`, `coverage`, `warnings`, `sections[]`, `total` and
`paging`. Each section: `id`, `parent_id`, `kind` (`item` or `note`), `title`,
`start`, `end`, `char_count`, `section_type`, `level`, `table_ids`,
`note_number`.

`coverage` explains parser confidence:

| Key | Meaning |
|:---|:---|
| `parser_top_sections` | top sections sec-parser recognised |
| `heuristic_items` | canonical items recovered by the item heuristic |
| `expected_items` | items expected for this form and part |
| `missing_items` | expected IDs not found |
| `notes_found` | note headings detected |
| `table_count` | extracted tables |
| `degraded` | `true` when expected items are missing or a semantic form has no notes |

Section IDs are stable and readable: `part2-item7`, `part2-item8`,
`note-8`, `part1-item1a`. Always take IDs from this tool.

### `report_section`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` / `accession` / `form` | | | filing resolution as above |
| `section_id` | string | — | ID from `report_sections` |
| `offset` | int | 0 | character offset |
| `limit_chars` | int 1000–12000 | 8000 | characters per page |

Returns `filing`, `section`, `text`, `total_chars`, `next_offset` and `tables[]`
(`id`, `caption`, `rows`, `columns`). Long sections page with `offset`.

### `report_search`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` / `accession` / `form` | | | filing resolution |
| `query` | string 2–120 chars | — | literal text |
| `limit` | int 1–50 | 20 | hits |

Returns `filing`, `query`, `hits[]` and `total`. Text hits carry `kind: "text"`,
`section_id`, `title`, `snippet`, `element_index`; table hits carry `kind:
"table"` and `table_id`.

Search first, then read the section — it is cheaper than paging whole Items.

### `report_table`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` / `accession` / `form` | | | filing resolution |
| `table_id` | string | — | ID from `report_sections`, e.g. `t14` |
| `columns` | list[int] | all | zero-based column indexes |
| `row_offset` | int | 0 | body row offset |
| `max_rows` | int 1–100 | 40 | rows per page |

Returns `filing`, `table` (`id`, `section_id`, `caption`, `header_rows`, `rows`,
`columns`), `markdown` (GFM grid), `row_offset`, `next_offset`, `total_rows` and
`truncated`.

Cell structure survives `colspan`/`rowspan`. Very wide tables are best read with
an explicit `columns` list.

---

## Thesis

The vault is read-only. Both tools return `ok: true` with a note when the
ticker has no vault yet — an absent vault is not an error.

### `thesis_read`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | — | ticker directory |
| `file` | string | none | relative path inside the ticker vault (default `thesis.md`) |
| `offset` | int | 0 | character offset |
| `limit` | int ≤ 8000 | 8000 | characters per page |

Returns `symbol`, `file`, `has_thesis`, `front_matter`, `raw_front_matter`,
`attachments[]`, `documents[]`, `body`, `offset`, `next_offset`, `truncated` and
`citations`.

### `thesis_annotations`

| Argument | Type | Default | Meaning |
|:---|:---|:---|:---|
| `symbol` | string | — | ticker directory |
| `doc` | string | none | annotation document key |
| `offset` | int | 0 | document offset |
| `limit` | int | 50 | documents per page |

Returns `symbol`, `documents[]` (`name`, `mtime`, `count`, `types`,
`has_annotations`, `items`) and `count`.

---

## Prompt patterns that work

| Goal | Ask |
|:---|:---|
| Discover values | "Using valuebot, show Apple's revenue and net income for the last three fiscal years with citations." |
| Ratios | "Compute roe, net_margin and net_debt_to_ebitda for AAPL over four periods and explain any non-`ok` quality." |
| DCF first pass | "Run dcf_compute for AAPL with assumptions only. Show the table and tell me which assumptions are policy defaults." |
| Filing reading | "List Apple's newest 10-K sections, then read Item 7 and quote the China revenue commentary." |
| Table extraction | "In Apple's newest 10-K, find the segment table and render it as markdown." |
| Thesis test | "Read my AAPL thesis, then test each claim against ratios, filings and a DCF." |

See [Research workflows](05-research-workflows.md) for full sequences.

## Next

- [Agents and skills](04-agents-and-skills.md)
- [Research workflows](05-research-workflows.md)
- [dev/07-analysis-and-dcf.md](../dev/07-analysis-and-dcf.md) — model details
