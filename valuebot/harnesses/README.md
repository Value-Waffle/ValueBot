# valuebot on other harnesses

valuebot is one MCP server plus five skills. Nothing about the tools, the
skills, or the data changes between harnesses — **only the launcher file and
the transport change**. The transport is stdio by default; one client (ChatGPT)
cannot launch a local process and uses the server's optional HTTP mode instead.
This folder holds one install guide per harness, and the canonical launch
contract every guide copies from.

## Quick install

For the harnesses that read a local JSON MCP config, [`../install.sh`](../install.sh)
creates or merges the `vw-mcp` entry — it never removes another server or an
unrelated top-level key:

```sh
cd valuebot
./install.sh --harness <name>          # claude-desktop, claude-code, vscode, copilot-cli, gemini-cli
./install.sh --harness <name> --dry-run # print the resulting JSON instead
```

The JSON guides in this folder remain the reference: for every other harness
(LibreChat, Codex, DeepSeek, Hermes, Pi, ChatGPT, OpenCode, Open WebUI) they are
the supported path, and `install.sh` points at the matching `INSTALL.md`.

## Support matrix

| Harness | Guide | Status |
|:---|:---|:---|
| LibreChat | [librechat/INSTALL.md](./librechat/INSTALL.md) · [user guide](../docs/users/01-getting-started.md) | ✅ Shipped (the original target) |
| Claude Code | [claude-code/INSTALL.md](./claude-code/INSTALL.md) | ✅ Supported |
| Claude Desktop (app) | [claude-desktop/INSTALL.md](./claude-desktop/INSTALL.md) | ✅ Supported (native stdio MCP; runs the 19 tools only — no skills/agents) |
| OpenAI Codex CLI | [codex/INSTALL.md](./codex/INSTALL.md) | ✅ Supported |
| GitHub Copilot (VS Code) | [copilot/INSTALL.md](./copilot/INSTALL.md) | ✅ Supported |
| GitHub Copilot Desktop | — | ❌ Unverified product; use the Copilot CLI section of the Copilot guide |
| ChatGPT (Desktop & web) | [chatgpt/INSTALL.md](./chatgpt/INSTALL.md) | 🔌 Needs a public HTTPS tunnel (no stdio; runs the server's HTTP transport) |
| DeepSeek Harness (`dsh`) | [deepseek/INSTALL.md](./deepseek/INSTALL.md) | 🚧 Developer preview |
| Pi (`pi.dev`) | [pi-agent/INSTALL.md](./pi-agent/INSTALL.md) | ✅ Supported (native stdio MCP + skills) |
| Hermes Agent (Nous Research) | [hermes/INSTALL.md](./hermes/INSTALL.md) | ✅ Consumes this package as-is (Agent Plugins 1.0) |
| OpenCode | [opencode/INSTALL.md](./opencode/INSTALL.md) | ✅ Supported (native stdio MCP + skills; `mcp` key, `{env:VAR}`) |
| Gemini CLI | [gemini-cli/INSTALL.md](./gemini-cli/INSTALL.md) | ✅ Supported (native stdio MCP + skills; Gemini models only — no OpenAI-compatible provider) |
| Open WebUI | [openwebui/INSTALL.md](./openwebui/INSTALL.md) | 🔌 Needs `mcpo` bridge (stdio only, no native stdio) |

## Minimal configuration

A working entry needs exactly two things: `command: "sh"` and
`args: ["<PLUGIN_ROOT>/mcp/run.sh"]`. Every environment variable is optional;
each has a default in `mcp/core/config.py`. Replace `<PLUGIN_ROOT>` with the
absolute path to your valuebot directory before saving the entry.

For clients using the `mcpServers` format without an explicit transport type:

```json
{
    "mcpServers": {
        "vw-mcp": {
            "command": "sh",
            "args": ["<PLUGIN_ROOT>/mcp/run.sh"]
        }
    }
}
```

For clients whose `mcpServers` format requires stdio:

```json
{
    "mcpServers": {
        "vw-mcp": {
            "type": "stdio",
            "command": "sh",
            "args": ["<PLUGIN_ROOT>/mcp/run.sh"]
        }
    }
}
```

For VS Code's `servers` format:

```json
{
    "servers": {
        "vw-mcp": {
            "type": "stdio",
            "command": "sh",
            "args": ["<PLUGIN_ROOT>/mcp/run.sh"]
        }
    }
}
```

## The launch contract (single source of truth)

This block is the only thing the harnesses disagree about *formatting*, never
about *content*. It is derived from [`../mcp.json`](../mcp.json).

- **Command:** `sh`
- **Args:** `<PLUGIN_ROOT>/mcp/run.sh`
- **Transport:** stdio
- **Environment:**

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

`<PLUGIN_ROOT>` is the directory containing this `harnesses/` folder.
`<PLUGIN_DATA>` defaults to `~/.valuebot`; set it only when you need a
different writable data root. LibreChat users may already have one; new users
can pick any absolute path.

## Optional tuning

The environment block is reference material, not a prerequisite. Set a value
only when you need to change the default. `VW_THESIS_ROOT` defaults to
`<PLUGIN_DATA>/theses`; only LibreChat installs that already mount `/vw-data`
should keep their container-mounted thesis path.

| Variable | Default | When to set it |
|:---|:---|:---|
| `PLUGIN_DATA` | `~/.valuebot` | Use another writable data root. |
| `EDGAR_LOCAL_DATA_DIR` | `<PLUGIN_DATA>/edgar` | Use another SEC cache location. |
| `EDGAR_RATE_LIMIT_PER_SEC` | `5` | Change the SEC request rate. |
| `EDGAR_HTTP_TIMEOUT` | `30` | Change the SEC request timeout in seconds. |
| `VW_THESIS_ROOT` | `<PLUGIN_DATA>/theses` | Use another thesis vault; keep a container-mounted path only for a LibreChat mount. |
| `VW_MAX_HTML_MB` | `40` | Change the maximum HTML document size. |
| `VW_MAX_FACTS_COMPANIES` | `100` | Change the facts query company limit. |
| `VW_ENABLE_PRICE` | `0` | Set to `1` only if price support is explicitly enabled. |
| `VW_ARTIFACT_HTTP_PORT` | `0` | Set a non-zero port to enable the local artifact viewer. |
| `VW_ARTIFACT_HTTP_HOST` | `127.0.0.1` | Change the artifact viewer bind address. |
| `VW_ARTIFACT_PUBLIC_BASE_URL` | empty | Set the browser-reachable artifact viewer base URL. |
| `UV_PROJECT_ENVIRONMENT` | unset | Set only when `uv` is on `PATH` and you need a custom environment directory. |
| `UV_CACHE_DIR` | unset | Set only when `uv` is on `PATH` and you need a custom cache directory. |
| `UV_PYTHON_INSTALL_DIR` | unset | Set only when `uv` is on `PATH` and you need a custom Python install directory. |

The `UV_*` variables are consulted only when `uv` is on `PATH`; the fallback
launcher uses `$PLUGIN_DATA/venv`.

### Why `run.sh` and not `uv`

[`../mcp/run.sh`](../mcp/run.sh) is the repository's portable launcher. It
uses `uv run --project` when `uv` is on `PATH`, and otherwise builds a
host-local venv at `$PLUGIN_DATA/venv` and installs `../requirements.txt`.

`mcp.json` declares `uv` directly because the LibreChat image ships `uv`. On a
desktop machine `uv` is often absent — it was absent on the machine these
guides were verified on — so every harness guide launches `run.sh` instead.

Verified 2026-10-27: `sh mcp/run.sh` built a venv and served all 19 tools in
26 s. A host that cannot reach a package index cannot use the fallback, so
install `uv` first if your network is restricted.

The `UV_*` variables in the block above are read only when `uv` is present;
they are harmless when the venv fallback is used.

### Optional HTTP transport (clients without stdio)

One client cannot launch a local process: **ChatGPT** reaches MCP servers only
over a public HTTPS URL. The same server therefore also speaks **Streamable
HTTP** on request — no extra files, no extra dependencies:

| Variable | Default | Meaning |
|:---|:---|:---|
| `VW_MCP_TRANSPORT` | `stdio` | set to `streamable-http` (or `http`) to serve HTTP |
| `VW_MCP_HTTP_HOST` | `127.0.0.1` | bind address |
| `VW_MCP_HTTP_PORT` | `8848` | bind port; the MCP path is always `/mcp` |

The endpoint is `http://<host>:<port>/mcp`. Anything other than `stdio`,
`streamable-http` or `http` exits non-zero with a stderr message, and stdout
stays a clean JSON-RPC channel in every mode. Verified 2026-10-31:
`initialize`, `tools/list` (19 tools) and `ping` all succeed over HTTP, while
the default stdio path is unchanged. Two caveats: the server has **no
authentication and no TLS**, and the SDK's automatic DNS-rebinding guard
returns **HTTP 421** for a tunnelled `Host` header when bound to loopback. See
[`chatgpt/INSTALL.md`](./chatgpt/INSTALL.md) for the tunnel setup and both
caveats.

## Path substitution — read this before copying a snippet

LibreChat is the only harness that expands `${PLUGIN_ROOT}` / `${PLUGIN_DATA}`
for you. Everywhere else:

| Harness | `${VAR}` expansion | `~` expansion | What to paste |
|:---|:---|:---|:---|
| Claude Code | ✅ `${VAR}` and `${VAR:-default}` | ❌ | absolute paths, or `${VAR}` if you export them |
| Claude Desktop | ❌ | ❌ | absolute paths |
| Copilot (portable `.mcp.json`) | ✅ braced `${VAR}` only | ❌ | absolute paths |
| Copilot (`.vscode/mcp.json`) | ❌ | ❌ | absolute paths |
| Codex CLI | ❌ | ❌ | absolute paths |
| DeepSeek `dsh` | ❌ (use `!!js process.env.X`) | ❌ | absolute paths |
| OpenCode | ✅ `{env:VAR}` (brace-colon form, not `${VAR}`) | ❌ | absolute paths |
| Gemini CLI | ✅ `$VAR` / `${VAR}` but **only inside `env`** | ⚠️ UNVERIFIED — don't rely on it | absolute paths, and list all 13 vars in `env` |

**Rule:** if you copy a snippet, replace every `<PLUGIN_ROOT>` and
`<PLUGIN_DATA>` before saving. A server that fails to spawn with
`spawn uv ENOENT` or a path error is almost always an unsubstituted `<...>`.

## What you get

All 19 tools, namespaced by the harness (Claude Code and `dsh` use
`mcp__<server>__<tool>`; LibreChat uses `<tool>_mcp_vw-mcp`):

| Module | Tools |
|:---|:---|
| core | `ping` · `citation_resolve` · `citation_view` |
| fundamentals | `symbol_resolve` · `company_profile` · `facts_query` · `facts_timeseries` · `facts_export` · `statement_get` |
| analysis | `ratio_catalog` · `ratio_compute` · `dcf_compute` |
| reports | `filing_list` · `report_sections` · `report_section` · `report_search` · `report_table` |
| thesis | `thesis_read` · `thesis_annotations` |

### First call, and what it proves

`ping` is the health check. It returns no citation and needs no SEC identity:

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

Data tools additionally need the one-time SEC identity. Until then they return
the expected, non-fatal envelope:

```json
{"ok": false, "error": {"code": "identity_not_configured", ...}}
```

That error means the wiring is correct and only the identity is missing — it
is not a harness problem.

## Skills and agents

The five skills live in [`../skills/`](../skills/) and are copied, never
edited:

| Skill | Use |
|:---|:---|
| `grounded-citation` | citation markers, `citation_view` / `citation_resolve`, references footer |
| `hypothesis-analysis` | claims → evidence → verdict |
| `ratio-analysis` | metric choice, quality states |
| `dcf-valuation` | assumptions, defaults vs history, sensitivity |
| `semantic-report-reading` | section / note / table navigation |

The six agent personas are canonical in
[`../agent-builder-exports/`](../agent-builder-exports/) as LibreChat JSON.
Each harness folder carries the same six personas rewritten in that harness's
native markdown format, with identical instructions, tools and skills.

| Persona | Scope |
|:---|:---|
| `vw-orchestrator` | plans evidence, dispatches specialists, runs the audit gate |
| `vw-fundamentals-analyst` | XBRL facts, identity, statements |
| `vw-analysis-analyst` | ratios, growth, DCF |
| `vw-reports-analyst` | filing sections, notes, tables |
| `vw-thesis-analyst` | tests the user's thesis against evidence |
| `vw-citation-auditor` | grounding gate; approves or rejects |

## Before you start

Run the one-time SEC identity setup from the plugin root. Every harness's data
tools return `identity_not_configured` until this is done.

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```
See [`../docs/users/01-getting-started.md`](../docs/users/01-getting-started.md)
for the full procedure.

## Shared data root

Every harness may point at the same `<PLUGIN_DATA>`. The SQLite caches, the
edgartools HTTP cache and the artifact store are shared, so switching harness
reuses everything already downloaded. Do not copy data per harness.
