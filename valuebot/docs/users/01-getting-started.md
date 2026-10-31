# 01 — Getting started

Install valuebot once, configure it once, and confirm it works — on whatever
harness you use. valuebot is one stdio MCP server plus five skills; only the
launcher file and the host app's configuration change between harnesses.

**Time:** about 10 minutes for the first harness; a few minutes per extra
harness, because the data is shared.

## 1. What valuebot does (the general idea)

valuebot answers financial questions from primary sources instead of prose.

| Module | Answers | Example |
|:---|:---|:---|
| `fundamentals` | What did the company report? | revenue by fiscal year, diluted shares, total debt |
| `analysis` | What do those numbers imply? | ROE, revenue CAGR, free cash flow, DCF value |
| `reports` | What did the filing say? | Item 7 MD&A text, Note 8 tables, risk factors |
| `thesis` | What did I already write? | my thesis notes and annotations for this ticker |

Every numeric claim carries a citation to the accession, form, filing date and
period it came from. Tables carry the filing URL.

### What you get

All 19 tools, namespaced by the harness (Claude Code and `dsh` use
`mcp__<server>__<tool>`; LibreChat uses `<tool>_mcp_vw-mcp`):

| Module | Tools |
|:---|:---|
| core | `ping` · `citation_resolve` · `citation_view` |
| fundamentals | `symbol_resolve` · `company_profile` · `facts_query` · `facts_timeseries` · `facts_export` · `statement_get` |
| analysis | `ratio_catalog` · `ratio_compute` · `dcf_compute` |
| reports | `filing_list` · `report_sections` · `report_section` · `report_search` · `report_table` |
| thesis | `thesis_read` · `thesis_annotations` |

### What valuebot is not

- Not a price feed. No share price, market cap or technical analysis;
  `price_action` is reserved and disabled.
- Not a screener. It works one issuer at a time.
- Not investment advice. DCF output is an intrinsic-value calculation from your
  assumptions, not a price target. The full disclaimer is in the
  [plugin README](../../README.md#disclaimer--not-investment-advice).
- Not a web search. Evidence comes from SEC filings and your own vault.

## 2. Common prerequisites (all harnesses)

| Item | Check |
|:---|:---|
| A writable code directory | where valuebot's code lives (`<PLUGIN_ROOT>`) |
| A writable data directory | where valuebot keeps settings and downloads (`<PLUGIN_DATA>`) |
| `uv` (recommended) or Python 3.11–3.13 | `uv` builds the env; otherwise `run.sh` makes a venv |
| A real contact email | SEC requires a User-Agent that identifies you |
| A tool-calling model | any: DeepSeek, OpenCode Zen, OpenAI, Anthropic |

You do **not** install Python packages yourself. The launcher (`mcp/run.sh`)
uses `uv run` when `uv` is present and otherwise builds a host-local venv and
installs `requirements.txt`.

> **LibreChat only:** you also need LibreChat 0.8.8+ (Agent Plugins schema
> 1.0.0). Other harnesses have their own version notes in their install guide.

## 3. Fastest path

1. If your harness is one of the five supported by the installer, run
   `./install.sh --harness <name>` from the `valuebot` directory. The supported
   names are `claude-desktop`, `claude-code`, `vscode`, `copilot-cli`, and
   `gemini-cli`.
2. Otherwise, paste the two-key minimal snippet from the
   [harness guide](../../harnesses/README.md#minimal-configuration) and replace
   `<PLUGIN_ROOT>` with the absolute path to your valuebot directory.
3. Run `./setup.sh --doctor` to check the local setup.
4. Run `./setup.sh example-user@gmail.com` to configure the SEC contact identity.
5. Restart the client and expect 19 tools.

## 4. The launch contract (reference)

This is the only thing the harnesses disagree about *formatting*, never
*content*. It is derived from `mcp.json`. You do **not** need any of it to get
started — it is reference material for when a default is wrong for you.

- **Command:** `sh`
- **Args:** `<PLUGIN_ROOT>/mcp/run.sh`
- **Transport:** stdio
- **Environment:** optional tuning; every variable has a default

`<PLUGIN_ROOT>` is the directory containing the `mcp/` folder (your copy of
valuebot). `<PLUGIN_DATA>` is your writable data root and defaults to
`~/.valuebot`; override it only if you want a different directory. Every
harness may point at the same `<PLUGIN_DATA>`; the caches and downloads are
shared.

```dotenv
EDGAR_LOCAL_DATA_DIR=<PLUGIN_DATA>/edgar
EDGAR_RATE_LIMIT_PER_SEC=5
EDGAR_HTTP_TIMEOUT=30
# Default: <PLUGIN_DATA>/theses. Keep a container-mounted thesis path only for
# a LibreChat install that already mounts the data directory.
VW_THESIS_ROOT=<PLUGIN_DATA>/theses
VW_MAX_HTML_MB=40
VW_MAX_FACTS_COMPANIES=100
VW_ENABLE_PRICE=0
VW_ARTIFACT_HTTP_PORT=0
VW_ARTIFACT_HTTP_HOST=127.0.0.1
VW_ARTIFACT_PUBLIC_BASE_URL=
UV_PROJECT_ENVIRONMENT=<PLUGIN_DATA>/uv-env
UV_CACHE_DIR=<PLUGIN_DATA>/uv-cache
UV_PYTHON_INSTALL_DIR=<PLUGIN_DATA>/uv-python
```

### Why `run.sh` and not `uv`

`mcp/run.sh` is the portable launcher. It uses `uv run --project` when `uv` is
on `PATH`, and otherwise builds a host-local venv at `$PLUGIN_DATA/venv` and
installs `requirements.txt`. `mcp.json` declares `uv` directly because the
LibreChat image ships `uv`; on a desktop `uv` is often absent, so every harness
guide launches `run.sh` instead. Verified 2026-10-27: `sh mcp/run.sh` built a
venv and served all 19 tools in 26 s.

> **Path substitution — read before copying any snippet.** LibreChat is the
> only harness that expands `${PLUGIN_ROOT}` / `${PLUGIN_DATA}` for you.
> Everywhere else, replace every `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` with
> absolute paths before saving. A server that fails to spawn with
> `spawn uv ENOENT` or a path error is almost always an unsubstituted `<...>`.
> Each harness's install guide lists its exact expansion rules.

### Optional HTTP transport (for clients without stdio)

One client cannot launch a local process: **ChatGPT** reaches MCP servers only
over public HTTPS. The same server speaks **Streamable HTTP** on request — set
`VW_MCP_TRANSPORT=streamable-http` (plus `VW_MCP_HTTP_HOST` and
`VW_MCP_HTTP_PORT`, default port `8848`) and the endpoint becomes
`http://<host>:<port>/mcp`. The default stays stdio, so nothing changes for
every other harness. See the [ChatGPT guide](../../harnesses/chatgpt/INSTALL.md)
for the tunnel setup and its security caveats.

## 5. One-time SEC identity (all harnesses)

**Why:** the SEC asks every program that downloads from it to include a contact
address. valuebot has no built-in address and will not fetch data until you
give it one.

**What you need:** one real email address that can receive mail.

**How:** from the plugin root (`<PLUGIN_ROOT>`), run once:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

The address must be a real mailbox; addresses containing `example.com` are rejected by setup, so replace this illustrative address with your own.

This writes `identity.json` into your data root. To check it, re-run with
`--show`; to replace it, run with the new address; to remove it, run
`--reset`.

> **Pick an address that can receive mail.** The SEC blocks some placeholders,
> including anything ending in `@users.noreply.github.com`. If SEC answers
> `403 Forbidden`, run setup again with a different address. See
> [Configuration](02-configuration.md#sec-user-agent) for the full list of
> accepted and rejected addresses.

Until this is done, every data tool returns the expected, non-fatal envelope:

```json
{"ok": false, "error": {"code": "identity_not_configured", ...}}
```

That error means the wiring is correct and only the identity is missing — it
is not a harness problem.

## 6. Shared data root (all harnesses)

Choose one writable `<PLUGIN_DATA>` and point every harness at it. The SQLite
caches, the SEC HTTP cache and the artifact store are shared, so switching
harness reuses everything already downloaded. Do not copy data per harness:
duplicate roots waste disk, force repeated downloads, and can make results
differ between clients. Keep the code root (`<PLUGIN_ROOT>`) separate from the
data root so upgrades never overwrite your setup.

## 7. Verify it worked (all harnesses)

`ping` is the health check. It needs no SEC identity and returns no citation:

```json
{"ok": true, "module": "core", "tool": "ping",
 "data": {"server": "valuebot", "version": "0.2.0",
          "modules": {"fundamentals": {"status": "ready"},
                      "analysis": {"status": "ready"},
                      "reports": {"status": "ready"},
                      "thesis": {"status": "ready"}},
          "identity_configured": false}}
```

All four modules must read `ready`. A module showing `unavailable` carries an
`error` and `error_code` in the same payload.

### General verification checklist

| Check | Expected |
|:---|:---|
| Server spawned | 19 tools (core 3, fundamentals 6, analysis 3, reports 5, thesis 2) |
| `ping` | 4 modules `ready` |
| `symbol_resolve("AAPL")` | CIK 320193, name Apple Inc. |
| `filing_list("AAPL", forms=["10-K"])` | recent accessions, newest first |
| `ratio_compute("AAPL", ["roe"])` | numeric value plus citations |
| `dcf_compute("AAPL", assumptions_only=true)` | assumption table, WACC flagged `default` |

If any step fails, see your harness's install guide and
[Troubleshooting and FAQ](08-troubleshooting-and-faq.md).

## 8. Choose your harness

valuebot runs on any harness that supports MCP — stdio for most, HTTP where
the client cannot launch a local process. Pick yours — each guide covers
installation through additional info:

| Harness | Status | Install guide |
|:---|:---|:---|
| LibreChat | ✅ Shipped | [LibreChat](../../harnesses/librechat/INSTALL.md) |
| Claude Code | ✅ Supported | [Claude Code](../../harnesses/claude-code/INSTALL.md) |
| Claude Desktop (app) | ✅ Supported | [Claude Desktop](../../harnesses/claude-desktop/INSTALL.md) |
| OpenAI Codex CLI | ✅ Supported | [Codex CLI](../../harnesses/codex/INSTALL.md) |
| GitHub Copilot (VS Code) | ✅ Supported | [Copilot](../../harnesses/copilot/INSTALL.md) |
| ChatGPT (Desktop & web) | 🔌 Needs public HTTPS tunnel | [ChatGPT](../../harnesses/chatgpt/INSTALL.md) |
| DeepSeek Harness (`dsh`) | 🚧 Developer preview | [DeepSeek](../../harnesses/deepseek/INSTALL.md) |
| Gemini CLI | ✅ Supported | [Gemini CLI](../../harnesses/gemini-cli/INSTALL.md) |
| Hermes Agent | ✅ Supported | [Hermes](../../harnesses/hermes/INSTALL.md) |
| OpenCode | ✅ Supported | [OpenCode](../../harnesses/opencode/INSTALL.md) |
| Open WebUI | 🔌 Needs `mcpo` bridge | [Open WebUI](../../harnesses/openwebui/INSTALL.md) |
| Pi (`pi.dev`) | ✅ Supported | [Pi](../../harnesses/pi-agent/INSTALL.md) |

The canonical launch contract and cross-harness details are in the
[harness overview](../../harnesses/README.md) and the
[multi-harness guide](09-multi-harness.md).

## Next

- [Configuration](02-configuration.md) — paths, limits, thesis vault
- [Tools reference](03-tools-reference.md) — every argument and return field
- [Agents and skills](04-agents-and-skills.md) — the six agents
- [Research workflows](05-research-workflows.md) — prompts that work well
