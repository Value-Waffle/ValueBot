# valuebot on Claude Code

This guide installs the valuebot stdio MCP server, five shared skills, and six Claude Code agent personas. See the [harness overview](../README.md) for the canonical launch contract and the [multi-harness guide](../../docs/users/09-multi-harness.md) for cross-harness details.

## Prerequisites

Set `PLUGIN_ROOT` to the absolute path of this repository and choose a writable `PLUGIN_DATA` directory. Claude Code expands `${VAR}` and `${VAR:-default}` in command, args, and env values. You may therefore use `${CLAUDECODE_PROJECT_DIR}`-style variables instead of absolute paths. It does not expand `~`.

Run the one-time SEC identity setup from the plugin root:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

## Before you configure

`run.sh` is the portable launcher: it uses `uv` when installed and otherwise builds a venv at `$PLUGIN_DATA/venv` (about 26 s on a first run). A restricted network needs `uv` installed first because the fallback installs from a package index.

The environment block is optional because every variable has a default in `mcp/core/config.py`; see the [two-key minimum](../README.md#minimal-configuration).

## Option A: install as a plugin (recommended)

Claude Code has its own plugin format, and this repository already ships one for it:

| File | Purpose |
|:---|:---|
| `.claude-plugin/plugin.json` | Claude plugin manifest (`name` is the only required key) |
| `.mcp.json` | MCP declaration at the plugin root, separate from the Agent Plugins `mcp.json` |
| `agents/` | The six personas below |
| `skills/` | The five shared skills, loaded automatically |

Install it from the repository marketplace:

```text
/plugin marketplace add valuewaffle/valuebot
/plugin install valuebot@valuebot
```

For local development, validate and load it directly:

```bash
claude plugin validate ./valuebot
claude --plugin-dir ./valuebot
```

After editing any plugin file, run `/reload-plugins` inside the session. For MCP logs use `claude --debug=mcp` and read stderr in `~/.claude/debug/<session-id>.txt`.

Two differences from the manual path below:

- **Namespace.** Tools installed by a plugin are named `mcp__plugin_valuebot_vw-mcp__<tool>`, with an extra `plugin_valuebot` segment. A project-scoped install (Option B) uses `mcp__vw-mcp__<tool>`. Put the plugin form in `permissions.allow` when using Option A.
- **Paths.** Inside a plugin, `${CLAUDE_PLUGIN_ROOT}` is the installed plugin directory. The plugin uses `~/.valuebot` as its data root by default; set `PLUGIN_DATA` in the plugin's environment only if you want a different root.

The one-time SEC identity setup still applies; point it at the plugin root (or the directory you pass to `--plugin-dir`):

```bash
cd ./valuebot && ./setup.sh example-user@gmail.com
```

## Option B: manual install

The steps below wire the server, skills and personas into a single project. They remain correct for project-scoped use and are the fallback when plugins are disabled.

## Project `.mcp.json`

Create `.mcp.json` at the repository root. Replace `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` with absolute paths, or use exported variables as described above.

```json
{
  "mcpServers": {
    "vw-mcp": {
      "type": "stdio",
      "command": "sh",
      "args": ["<PLUGIN_ROOT>/mcp/run.sh"],
      "env": {
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
      }
    }
  }
}
```

Claude Code also supports adding the server from the command line:

```bash
claude mcp add --transport stdio vw-mcp --env EDGAR_LOCAL_DATA_DIR=<PLUGIN_DATA>/edgar --env EDGAR_RATE_LIMIT_PER_SEC=5 --env EDGAR_HTTP_TIMEOUT=30 --env VW_MAX_HTML_MB=40 --env VW_MAX_FACTS_COMPANIES=100 --env VW_ENABLE_PRICE=0 --env VW_ARTIFACT_HTTP_PORT=0 --env VW_ARTIFACT_HTTP_HOST=127.0.0.1 --env VW_ARTIFACT_PUBLIC_BASE_URL= --env UV_PROJECT_ENVIRONMENT=<PLUGIN_DATA>/uv-env --env UV_CACHE_DIR=<PLUGIN_DATA>/uv-cache --env UV_PYTHON_INSTALL_DIR=<PLUGIN_DATA>/uv-python -- sh <PLUGIN_ROOT>/mcp/run.sh
```

## Skills and personas

Copy all five skills, without editing them, into `.claude/skills/`:

```bash
mkdir -p .claude/skills
cp -R <PLUGIN_ROOT>/skills/grounded-citation .claude/skills/
cp -R <PLUGIN_ROOT>/skills/hypothesis-analysis .claude/skills/
cp -R <PLUGIN_ROOT>/skills/ratio-analysis .claude/skills/
cp -R <PLUGIN_ROOT>/skills/dcf-valuation .claude/skills/
cp -R <PLUGIN_ROOT>/skills/semantic-report-reading .claude/skills/
```

Copy the six persona files from this directory into `.claude/agents/`. `vw-orchestrator` should reference the other five as subagents: `vw-fundamentals-analyst`, `vw-analysis-analyst`, `vw-reports-analyst`, `vw-thesis-analyst`, and `vw-citation-auditor`. The citation auditor is a read-only grounding gate: it verifies citations and must not add claims or rewrite drafts.

## Approvals and permissions

The first time Claude Code starts the server, it will be pending approval. Approve the server once. Then add the MCP tools to your project or user permissions allowlist, for example under `permissions.allow`:

```json
[
  "mcp__vw-mcp__ping",
  "mcp__vw-mcp__symbol_resolve",
  "mcp__vw-mcp__company_profile",
  "mcp__vw-mcp__facts_query",
  "mcp__vw-mcp__facts_timeseries",
  "mcp__vw-mcp__facts_export",
  "mcp__vw-mcp__statement_get",
  "mcp__vw-mcp__ratio_catalog",
  "mcp__vw-mcp__ratio_compute",
  "mcp__vw-mcp__dcf_compute",
  "mcp__vw-mcp__filing_list",
  "mcp__vw-mcp__report_sections",
  "mcp__vw-mcp__report_section",
  "mcp__vw-mcp__report_search",
  "mcp__vw-mcp__report_table",
  "mcp__vw-mcp__thesis_read",
  "mcp__vw-mcp__thesis_annotations"
]
```

## Troubleshooting

- **`spawn uv ENOENT`**: Claude Code cannot find `uv`. Install `uv` and ensure its directory is on the environment `PATH` visible to Claude Code. Also replace every `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` placeholder; Claude Code does not expand `~`.
- **`spawn` or path errors**: Replace every `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` placeholder; Claude Code does not expand `~`. The portable launcher is `sh <PLUGIN_ROOT>/mcp/run.sh`.
- **`identity_not_configured`**: Run `./setup.sh example-user@gmail.com` from the plugin root, then restart or reconnect the MCP server.
- **Tools are not listed**: Confirm the server was approved, the `.mcp.json` is at the repository root, `sh <PLUGIN_ROOT>/mcp/run.sh` starts successfully, and the `mcp__vw-mcp__<tool>` names are in `permissions.allow`. The server exposes 19 tools: core 3, fundamentals 6, analysis 3, reports 5, and thesis 2; `symbol_resolve` takes `query`, not `symbol`.
