# valuebot on OpenAI Codex CLI

> Codex marks `~/.codex/prompts/` deprecated in favour of skills. The persona prompts in this directory are therefore best-effort; install them as project or user skills when possible.

This guide installs the valuebot stdio MCP server, five shared skills, and six Codex persona prompts. See the [harness overview](../README.md) for the canonical launch contract and the [multi-harness guide](../../docs/users/09-multi-harness.md) for cross-harness details.

## Prerequisites

Set `PLUGIN_ROOT` and `PLUGIN_DATA` to absolute paths before copying the configuration. Codex CLI does not expand `${VAR}` or `~` in this configuration, so replace every placeholder with its literal absolute path.

Run the one-time SEC identity setup from the plugin root:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

## Before you configure

`run.sh` is the portable launcher: it uses `uv` when installed and otherwise builds a venv at `$PLUGIN_DATA/venv` (about 26 s on a first run). A restricted network needs `uv` installed first because the fallback installs from a package index.

The environment block is optional because every variable has a default in `mcp/core/config.py`; see the [two-key minimum](../README.md#minimal-configuration). The default thesis root is `<PLUGIN_DATA>/theses`.

## User configuration

Create or edit `~/.codex/config.toml`. Replace `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` with absolute paths. This is the first TOML block because it is the copy-paste configuration snippet.

```toml
[mcp_servers.vw-mcp]
command = "sh"
args = ["<PLUGIN_ROOT>/mcp/run.sh"]
env_vars = []
cwd = "<PLUGIN_ROOT>/mcp"
startup_timeout_sec = 20
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"

[mcp_servers.vw-mcp.env]
EDGAR_LOCAL_DATA_DIR = "<PLUGIN_DATA>/edgar"
EDGAR_RATE_LIMIT_PER_SEC = "5"
EDGAR_HTTP_TIMEOUT = "30"
VW_MAX_HTML_MB = "40"
VW_MAX_FACTS_COMPANIES = "100"
VW_ENABLE_PRICE = "0"
VW_ARTIFACT_HTTP_PORT = "0"
VW_ARTIFACT_HTTP_HOST = "127.0.0.1"
VW_ARTIFACT_PUBLIC_BASE_URL = ""
UV_PROJECT_ENVIRONMENT = "<PLUGIN_DATA>/uv-env"
UV_CACHE_DIR = "<PLUGIN_DATA>/uv-cache"
UV_PYTHON_INSTALL_DIR = "<PLUGIN_DATA>/uv-python"
```

Codex has no `type` key and no `env_file` key for this server configuration. Do not add either key. The `env` table is optional — every key has a default in `mcp/core/config.py` — but if you do set one, take its name from [`valuebot/mcp.json`](../../mcp.json) so it cannot drift.

## Project configuration

For a project-scoped setup, place the same `[mcp_servers.vw-mcp]` configuration in `.codex/config.toml` at the project root. Codex applies project configuration only to trusted projects; review and trust the project before relying on this server. Use absolute paths in this file as well.

## Skills and personas

Copy the five shared skills without editing them into `.agents/skills/` for the project:

```bash
mkdir -p .agents/skills
cp -R <PLUGIN_ROOT>/skills/grounded-citation .agents/skills/
cp -R <PLUGIN_ROOT>/skills/hypothesis-analysis .agents/skills/
cp -R <PLUGIN_ROOT>/skills/ratio-analysis .agents/skills/
cp -R <PLUGIN_ROOT>/skills/dcf-valuation .agents/skills/
cp -R <PLUGIN_ROOT>/skills/semantic-report-reading .agents/skills/
```

For user-wide availability, copy them into `~/.agents/skills/` instead. Codex discovers skills from `.agents/skills/` and does **not** scan `.codex/skills/`. `~/.codex/prompts/` is deprecated in favour of skills.

The six persona files are in [`personas/`](./personas/). Copy or adapt them as skills under `.agents/skills/` or `~/.agents/skills/`; load `vw-orchestrator` for coordinated research and the specialist prompt matching the task.

## Approvals

`default_tools_approval_mode = "prompt"` is the safe default, but it interrupts the citation_view evidence flow whenever a tool needs approval. Inside a trusted project, `"auto"` is recommended for a smoother evidence workflow. Keep `"prompt"` for untrusted or exploratory projects.

## Troubleshooting

- **Launcher or path errors**: Replace every `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` placeholder; Codex does not expand `~` or environment variables in this configuration. Test with `sh <PLUGIN_ROOT>/mcp/run.sh`.
- **`identity_not_configured`**: Run `./setup.sh example-user@gmail.com` from the plugin root, then restart Codex or reconnect the MCP server.
- **Skills are not discovered**: Confirm the files are under `.agents/skills/` in the project or `~/.agents/skills/` for user scope. `.codex/skills/` is not scanned, and `~/.codex/prompts/` is deprecated.
- **Tools are not listed**: Confirm the project is trusted, the MCP server configuration parses, the configured `sh <PLUGIN_ROOT>/mcp/run.sh` command can start, and the server approval prompt has been accepted. The server exposes 19 tools: core 3, fundamentals 6, analysis 3, reports 5, and thesis 2; `symbol_resolve` takes `query`, not `symbol`.

See the [canonical harness README](../README.md), [`valuebot/mcp.json`](../../mcp.json), and the [multi-harness guide](../../docs/users/09-multi-harness.md) for shared details.
