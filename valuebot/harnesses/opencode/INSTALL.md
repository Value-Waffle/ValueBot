# valuebot on OpenCode

This guide installs the valuebot stdio MCP server, five shared skills, and six OpenCode agent personas. See the [harness overview](../README.md) for the canonical launch contract and the [multi-harness guide](../../docs/users/09-multi-harness.md) for cross-harness details.

> **Read this first.** OpenCode's config schema is different from every other harness in this repository. The key is `mcp`, not `mcpServers`. `command` is one array that combines the executable and its arguments — there is no `args` key. Environment variables live under `environment`, not `env`. And interpolation is `{env:VARIABLE_NAME}`, not `${VARIABLE_NAME}`. A snippet copied from the [Claude Code](../claude-code/INSTALL.md) or [Codex](../codex/INSTALL.md) guide parses without complaint and then silently does nothing useful — wrong key, missing `type`, or an unexpanded `${VAR}` left as a literal string.

## Prerequisites

Set `PLUGIN_ROOT` to the absolute path of this repository and choose a writable `PLUGIN_DATA` directory. OpenCode does not expand `~`, so paste absolute paths everywhere.

Run the one-time SEC identity setup from the plugin root:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

## Before you configure

`run.sh` is the portable launcher: it uses `uv` when installed and otherwise builds a venv at `$PLUGIN_DATA/venv` (about 26 s on a first run). A restricted network needs `uv` installed first because the fallback installs from a package index.

The environment block is optional because every variable has a default in `mcp/core/config.py`; see the [two-key minimum](../README.md#minimal-configuration).

## Where the config lives

OpenCode reads `opencode.json` (or `opencode.jsonc`) from the project root, and falls back to the global file at `~/.config/opencode/opencode.json`. Project settings win over global ones.

Two environment variables override discovery:

| Variable | Effect |
|:---|:---|
| `OPENCODE_CONFIG=<path>` | Use this specific config file |
| `OPENCODE_CONFIG_DIR=<dir>` | Look for the config in this directory instead of the default locations |

Precedence, highest first: `OPENCODE_CONFIG` → project `opencode.json` → `OPENCODE_CONFIG_DIR` / global `~/.config/opencode/opencode.json`. When in doubt, run with `opencode --print-logs` and confirm which file it loaded.

## Project `opencode.json`

Create `opencode.json` at the repository root. Replace `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` with absolute paths.

```json
{
  "mcp": {
    "vw-mcp": {
      "type": "local",
      "command": ["sh", "<PLUGIN_ROOT>/mcp/run.sh"],
      "environment": {
        "EDGAR_LOCAL_DATA_DIR": "<PLUGIN_DATA>/edgar",
        "EDGAR_RATE_LIMIT_PER_SEC": "5",
        "EDGAR_HTTP_TIMEOUT": "30",
        "VW_MAX_HTML_MB": "40",
        "VW_MAX_FACTS_COMPANIES": "100",
        "VW_ENABLE_PRICE": "0",
        "VW_ARTIFACT_HTTP_PORT": "0",
        "VW_ARTIFACT_HTTP_HOST": "127.0.0.1",
        "VW_ARTIFACT_PUBLIC_BASE_URL": "",
        "UV_PROJECT_ENVIRONMENT": "<PLUGIN_DATA>/uv-env",
        "UV_CACHE_DIR": "<PLUGIN_DATA>/uv-cache",
        "UV_PYTHON_INSTALL_DIR": "<PLUGIN_DATA>/uv-python"
      },
      "enabled": true
    }
  }
}
```

### The five keys, and what is required

| Key | Required | Values | Notes |
|:---|:---|:---|:---|
| `type` | **yes** | `"local"` or `"remote"` | The only two literals. Omit it and the server is dropped without an error. |
| `command` | yes for `local` | array of strings | Executable **and** arguments in one array: `["sh", "<PLUGIN_ROOT>/mcp/run.sh"]`. There is no separate `args` key. |
| `environment` | no | object of strings | Not `env`. |
| `enabled` | no | boolean | Set `false` to keep the entry but not launch it. |
| `cwd` | no | string | Working directory for the spawned process. |
| `timeout` | no | integer, ms | Default `30000`. Raise it on a cold first run, when `run.sh` builds the venv. |

A cold start can take ~26 s, so bump `timeout` to `120000` on the first run and drop it back afterwards.

## Interpolation: `{env:VAR}` and `{file:path}` — not `${VAR}`

This is the difference that breaks silently. OpenCode substitutes `{env:VARIABLE_NAME}` and `{file:path/to/file}` inside config string values. It does **not** understand `${VARIABLE_NAME}`. A value written as `"${HOME}/data"` is passed to the child process as the literal text `${HOME}/data`.

| Written as | OpenCode does |
|:---|:---|
| `{env:HOME}/data` | Substitutes the variable |
| `{file:./secrets/token}` | Inlines that file's contents |
| `${HOME}/data` | **Nothing** — literal string, silently wrong |
| `<PLUGIN_ROOT>/...` | **Nothing** — literal string, silently wrong |
| `~/valuebot-data` | Not supported; write the absolute path |

**Rule:** absolute paths are the safe default here. If you do want environment indirection, use the braced colon form:

```json
{
  "mcp": {
    "vw-mcp": {
      "type": "local",
      "command": ["sh", "{env:VW_PLUGIN_ROOT}/mcp/run.sh"],
      "environment": {
        "EDGAR_LOCAL_DATA_DIR": "{env:VW_DATA}/edgar"
      },
      "enabled": true
    }
  }
}
```

## Skills

OpenCode reads skills from `.opencode/skills/<name>/SKILL.md`. Copy all five, without editing them:

```bash
mkdir -p .opencode/skills
cp -R <PLUGIN_ROOT>/skills/grounded-citation .opencode/skills/
cp -R <PLUGIN_ROOT>/skills/hypothesis-analysis .opencode/skills/
cp -R <PLUGIN_ROOT>/skills/ratio-analysis .opencode/skills/
cp -R <PLUGIN_ROOT>/skills/dcf-valuation .opencode/skills/
cp -R <PLUGIN_ROOT>/skills/semantic-report-reading .opencode/skills/
```

OpenCode also discovers skills in `.claude/skills/` and `.agents/skills/` (and their `~` equivalents). If you already followed the [Claude Code guide](../claude-code/INSTALL.md), the skills are found as-is and there is nothing to copy.

## Agents and personas

OpenCode agents live at `.opencode/agents/<name>.md`. The frontmatter needs a `description`; `mode` selects where the agent can run.

```bash
mkdir -p .opencode/agents
cp <PLUGIN_ROOT>/harnesses/opencode/personas/vw-*.md .opencode/agents/
```

| Persona | `mode` | Scope |
|:---|:---|:---|
| `vw-orchestrator` | `primary` | plans evidence, dispatches specialists, runs the audit gate |
| `vw-fundamentals-analyst` | `subagent` | XBRL facts, identity, statements |
| `vw-analysis-analyst` | `subagent` | ratios, growth, DCF |
| `vw-reports-analyst` | `subagent` | filing sections, notes, tables |
| `vw-thesis-analyst` | `subagent` | tests the user's thesis against evidence |
| `vw-citation-auditor` | `subagent` | grounding gate; approves or rejects |

`mode` takes `primary` (selectable as the session agent), `subagent` (only invocable by another agent) or `all`. The orchestrator should reference the other five by name: `vw-fundamentals-analyst`, `vw-analysis-analyst`, `vw-reports-analyst`, `vw-thesis-analyst`, `vw-citation-auditor`. The citation auditor is a read-only grounding gate: it verifies citations and must not add claims or rewrite drafts.

`tools` as a boolean map is deprecated (v1.1.1). These personas carry no `tools:` block at all; per-tool control belongs in `permission`. If an older config of yours still has `tools: {write: false}`, migrate it.

## Permissions and approvals

`permission` decides whether a tool call is auto-allowed:

```json
{
  "permission": {
    "edit": "ask",
    "bash": {
      "sh": "ask"
    }
  }
}
```

Each entry is `allow`, `ask` or `deny`. `opencode --auto` skips the interactive prompts so a run does not block — but an explicit `deny` is still enforced, so `--auto` is not a way to override a deny. Keep `edit` and `bash` on `ask` and let the read-only valuebot tools run.

## Provider: an OpenAI-compatible endpoint

The canonical personas were authored against `deepseek-v4-pro` and `deepseek-v4.1-flash`. Point OpenCode at any OpenAI-compatible endpoint (DeepSeek included) with the `@ai-sdk/openai-compatible` adapter:

```json
{
  "provider": {
    "deepseek": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "DeepSeek",
      "options": {
        "baseURL": "https://api.deepseek.com/v1",
        "apiKey": "{env:DEEPSEEK_API_KEY}"
      },
      "models": {
        "deepseek-v4-pro": { "name": "DeepSeek V4 Pro" },
        "deepseek-v4.1-flash": { "name": "DeepSeek V4.1 Flash" }
      }
    }
  }
}
```

Set `model` in an agent's frontmatter to a `provider/model` id (for example `deepseek/deepseek-v4.1-flash`), or leave it out to inherit the session model. The `apiKey` here is exactly the `{env:VAR}` form — `${DEEPSEEK_API_KEY}` would authenticate with the literal string.

## Verify it worked

Start OpenCode in the repository and call the health check:

```
ping
```

`ping` needs no SEC identity. A correct install returns:

```json
{"ok": true, "module": "core", "tool": "ping",
 "data": {"server": "valuebot", "version": "0.2.0",
          "modules": {"fundamentals": {"status": "ready"},
                      "analysis": {"status": "ready"},
                      "reports": {"status": "ready"},
                      "thesis": {"status": "ready"}},
          "identity_configured": false}}
```

All four modules must read `ready`. A module showing `unavailable` carries `error` and `error_code` in the same payload.

`identity_configured: false` is expected before you run `./setup.sh`. Data tools then return `{"ok": false, "error": {"code": "identity_not_configured", ...}}` — that means the wiring is correct and only the identity is missing.

Then ask for one cited number, for example "AAPL revenue, last three fiscal years", and confirm every figure carries a citation key in a references footer.

## Debugging

| Switch | Use |
|:---|:---|
| `opencode --print-logs` | Stream the log to the terminal, including MCP server stdio |
| `opencode --log-level DEBUG` | Raise verbosity for config discovery and tool listing |
| `OPENCODE_PRINT_LOGS=1` | Force logging on from the environment (useful for GUI or wrapped launches) |

```bash
opencode --print-logs --log-level DEBUG
```

Look for the file path OpenCode loaded and the `vw-mcp` entry. Then run the launcher yourself to separate a config problem from a server problem:

```bash
sh <PLUGIN_ROOT>/mcp/run.sh
```

## Troubleshooting

- **Zero valuebot tools visible.** The entry was ignored, not rejected. Check that the key is `mcp` (not `mcpServers`), that `type` is present and is exactly `"local"` or `"remote"`, and that `command` is an array that already contains the arguments. Also confirm `enabled` is not `false`, and that you edited the file OpenCode actually loaded (project root vs `~/.config/opencode/opencode.json`).
- **Env vars silently ignored.** You copied `${VAR}` from another guide. OpenCode only substitutes `{env:VAR}`; anything else is passed through as a literal. Grep your config for `${` and fix every hit.
- **Literal `<PLUGIN_ROOT>` or `<PLUGIN_DATA>` reaches the server.** Placeholders are documentation, not syntax. Replace them with absolute paths.
- **Server starts, then times out.** The first `run.sh` run builds a venv (~26 s). Raise `timeout` to `120000` for the first run.
- **`identity_not_configured`.** Run `./setup.sh example-user@gmail.com` from the plugin root, then restart OpenCode.
- **Skills or agents not listed.** Skills go in `.opencode/skills/<name>/SKILL.md`; agents go in `.opencode/agents/<name>.md` and need a `description` in the frontmatter. A deprecated `tools:` map is not the cause of a missing agent, but it is ignored — move that intent into `permission`.
- **`spawn uv ENOENT`.** `uv` is not on the `PATH` OpenCode sees. Install `uv`, or rely on the venv fallback inside `run.sh`.

The server exposes 19 tools: core 3, fundamentals 6, analysis 3, reports 5, and thesis 2. `symbol_resolve` takes `query`, not `symbol`.

## See also

- [Harness overview](../README.md) — the canonical 13-key launch contract and path-substitution table
- [Multi-harness guide](../../docs/users/09-multi-harness.md) — sharing one data root across harnesses
- [Tools reference](../../docs/users/03-tools-reference.md)
- [Agents and skills](../../docs/users/04-agents-and-skills.md)
