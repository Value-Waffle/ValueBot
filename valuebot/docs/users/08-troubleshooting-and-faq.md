# 08 — Troubleshooting and FAQ

Start with `ping`. It reports module health, identity source and resolved paths,
which separates configuration problems from data problems.

```json
{ "data": {
    "modules": { "fundamentals": {"status":"ready"}, "…": {} },
    "identity_configured": true,
    "identity_source": "file",
    "identity_file": "/app/data/plugins/valuebot/identity.json"
} }
```

`identity_source` values: `file` (normal), `env` (override), `env
(EDGAR_IDENTITY alias)`, `missing` (not configured).

---

## Run the doctor first

When anything fails, run the read-only doctor before changing configuration:

```bash
./setup.sh --doctor
```

It never prompts and prints one line per check as `<status>  <name>  <detail>`:

```
ok  python  3.12.1
ok  uv  /usr/local/bin/uv
ok  plugin_data  /Users/you/.valuebot
warn  sec_identity  missing; run ./setup.sh you@email.com (expected ~/.valuebot/identity.json)
ok  packages  mcp, edgar, sec_parser importable
ok  paths  PLUGIN_DATA=/Users/you/.valuebot EDGAR_CACHE=/Users/you/.valuebot/edgar
```

Exit code `0` means no check failed; `1` means at least one `fail`.

---

## Installation and startup

| Symptom | Cause | Fix |
|:---|:---|:---|
| No `[agentPlugins]` line in the log | plugin dir not mounted or not scanned | check `DEPLOYMENT_PLUGINS_DIR` and the volume |
| `Loaded 0 plugin(s)` | folder missing or named wrong | the scan reads immediate subdirectories of `/app/plugin` |
| `plugin.json was not found in the plugin root` | wrong nesting (`plugin/valuebot/valuebot/`) | flatten one level |
| `Unsupported Agent Plugins manifest schema` | `$schema` mismatch | must be `…/schemas/1.0.0/plugin.schema.json` |
| Plugin listed as rejected | zod validation failed | check `name` (`^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$`, 1–64 chars) and that `author` has only `name`/`email`/`url` |
| `mcp_version_mismatch` | `plugin.json` and `mcp.json` versions differ | make `plugin.json.version` and the `mcp.json` schema version agree |
| `[MCP] Plugin server "vw-mcp" conflicts` | another server uses that name | rename one; a plugin never overrides `librechat.yaml` |
| `No module named 'mcp'` at boot | Python < 3.11 or a corrupt venv | delete `${PLUGIN_DATA}/uv-env`; let `uv` rebuild |
| First tool call times out | cold `uv` environment (60–120 s) | prime it — see [deployment](06-librechat-deployment.md#4-prime-the-python-environment) |
| `mkdir … Permission denied` during setup | container `HOME` is `/` | export the `UV_*` vars into `${PLUGIN_DATA}` (already done in `mcp.json`) |
| `env: can't execute 'bash'` | image ships no bash | use the current POSIX `setup.sh` (`sh`) |

---

## Identity and SEC access

| Symptom | Cause | Fix |
|:---|:---|:---|
| `identity_not_configured` | no `identity.json`, no override | run `setup.sh you@email.com`, restart |
| `edgar_unavailable` + `403 Forbidden` | SEC rejected the User-Agent | use a real mailbox; `@users.noreply.github.com` is blocked |
| `edgar_rate_limited` | more than ~10 req/s | wait `retry_after_s`; keep `EDGAR_RATE_LIMIT_PER_SEC=5` |
| `edgar_unavailable` + timeout | slow network | raise `EDGAR_HTTP_TIMEOUT` to `60` |
| `identity_source: env` unexpectedly | a shell/compose variable is set | unset `SEC_USER_AGENT` / `EDGAR_IDENTITY` |
| Setup writes the file but SEC still 403s | address itself is blocked | try a different domain; verify with `curl -A 'your ua' https://data.sec.gov/submissions/CIK0000320193.json` |

Quick identity check from inside the container:

```bash
docker exec LibreChat node -e "
fetch('https://data.sec.gov/submissions/CIK0000320193.json', {
  headers: { 'User-Agent': 'valuebot you@email.com' }
}).then(r => console.log(r.status))"
```

`200` means the address is accepted; `403` means it is not.

---

## Data and tool errors

| Symptom | Cause | Fix |
|:---|:---|:---|
| `symbol_not_found` | ticker fragment has no match | call `symbol_resolve` with the company name |
| `filing_not_found` | no filing of that form | call `filing_list` and use an accession |
| `section_not_found` | stale or guessed section ID | call `report_sections` and copy its IDs |
| `table_not_found` | table ID from another filing | re-list with `include_tables: true` |
| `statement_unavailable` | issuer does not tag that statement | use `facts_query` for the specific concept |
| `metric_not_found` | unknown metric ID | call `ratio_catalog` |
| `artifact_too_large` | HTML above `VW_MAX_HTML_MB` (40) | raise the cap or skip that filing |
| `parser_failed` | sec-parser could not parse the document | report the accession; try another filing |
| `coverage.degraded: true` | expected items or notes not found | search for the passage; do not assert absence |
| A ratio is `gap` | not enough annual history for the window | ask for fewer periods, or report the gap |
| A ratio is `not_meaningful` | negative equity or zero denominator | report the state, never the number |
| Values look like last year after a new 10-K | cached facts | `company_profile(symbol, refresh=true)` |

---

## Response and formatting

| Symptom | Cause | Fix |
|:---|:---|:---|
| `"truncated": true` | payload exceeded the 6/8 KB cap | page with `offset`/`next_offset`, or request fewer rows |
| Table renders as one long line | markdown not preserved by the client | read `report_table` output directly; it is GFM with a delimiter row |
| No citations in an answer | model skipped the skill | attach `grounded-citation`, or ask "cite each number" |
| Model invents a share price | no price data exists | re-prompt: "no price data; use intrinsic value only" |
| Tool list missing from the picker | server not connected | `ping`, then check the api log |

## When a harness chooses web search

Every harness with built-in web search competes with these tools. A skill is not
required to call one: the reliable ways to steer selection are to name the
tool explicitly, disable web search for the chat or project, or install a skill
such as `grounded-citation`. The request must also name or imply a specific
public issuer; a revenue question about Apple maps to a tool, while “is Apple
a good buy?” does not.

| Symptom | Likely cause | Try |
|:---|:---|:---|
| Answer cites the web instead of valuebot | web search won tool selection | name the valuebot tool, or disable web search |
| Tools are connected but not selected | the request sounds like general knowledge | name a public company and the intended tool |
| You want the behaviour to trigger automatically | no matching skill is installed | install `grounded-citation`; skills guide selection but are not required |

---

## Frequently asked questions

**Do I need a market data subscription?**
No. valuebot uses SEC filings only. There is no share price, market cap or
technicals.

**Why is there no current price in the DCF output?**
`price_action` is reserved and disabled. The DCF returns intrinsic value; any
comparison to price is your input, not the plugin's.

**How current is the data?**
Facts come from the SEC company-facts API and are re-synced per issuer on a
12-hour cache. Use `company_profile(refresh=true)` after a new filing.

**Does it cover non-US companies?**
Filings tagged in XBRL with a CIK, including `20-F`/`40-F` filers. Statement
normalisation is tuned for US GAAP; IFRS issuers may return more `unavailable`
metrics.

**Which forms get full semantic parsing?**
`10-K` and `10-Q` (including `/A` amendments) get item and note heuristics.
`8-K`, `20-F`, `40-F` and proxies are parsed generically — sections exist but
coverage is not item-complete.

**How many periods can I request?**
Up to 20 for `ratio_compute` and `statement_get`; fact series up to 50 points.
Growth metrics fetch extra history automatically, so a 3-year CAGR works even
when you ask for 2 periods.

**Can I change the metric formulas?**
Yes, in code — see [dev/07-analysis-and-dcf.md](../dev/07-analysis-and-dcf.md).
Bump the formula version so cached results invalidate.

**Can I add my own line items?**
Yes — [dev/10-contributing.md](../dev/10-contributing.md#add-a-line-item).

**Can I run it without LibreChat?**
Yes. Start `python server.py` in `mcp/` and speak MCP over stdio; tests do
exactly this. See [dev/04-development-setup.md](../dev/04-development-setup.md).

**Does it write to my thesis vault?**
Never. The `thesis` module opens files read-only and rejects path traversal.

**What happens if a module fails to start?**
Its tools are replaced with stubs returning `module_unavailable`; the other
modules keep working. `ping` shows which module failed and why.

**Is anything sent anywhere except SEC?**
Only SEC endpoints (`data.sec.gov`, `www.sec.gov`). No analytics, no third-party
API calls, no telemetry.

**Where are logs?**
Server logs go to stderr, which LibreChat captures:
`docker logs --since 10m LibreChat 2>&1 | grep -E 'valuebot|vw-mcp|MCP'`.

---

## Reporting a problem

Include:

1. `ping` output.
2. The failing tool name and arguments.
3. The error `code`, `message` and `hint`.
4. The accession if a filing is involved.
5. LibreChat version and the plugin version from `plugin.json`.

Do not paste `identity.json`, API keys or JWTs.

## Next

- [Getting started](01-getting-started.md)
- [Configuration](02-configuration.md)
- [Tools reference](03-tools-reference.md)
