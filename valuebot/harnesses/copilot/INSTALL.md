# valuebot on GitHub Copilot

This guide installs the valuebot stdio MCP server, five shared skills, and six Copilot agent personas. See the [harness overview](../README.md) for the canonical launch contract and the [multi-harness guide](../../docs/users/09-multi-harness.md) for cross-harness details.

## Prerequisites

Set `PLUGIN_ROOT` to the absolute path of this repository and choose a writable `PLUGIN_DATA` directory. The VS Code format requires absolute paths. The portable Copilot CLI format supports braced `${VAR}` expansion, but does not expand `~`.

Run the one-time SEC identity setup from the plugin root:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

## Before you configure

`run.sh` is the portable launcher: it uses `uv` when installed and otherwise builds a venv at `$PLUGIN_DATA/venv` (about 26 s on a first run). A restricted network needs `uv` installed first because the fallback installs from a package index.

## (0) Guided install in VS Code

Open the Command Palette and choose **MCP: Add Server**, then **Command
(stdio)**. Enter `sh` as the command, add `<PLUGIN_ROOT>/mcp/run.sh` as the
argument, and save it to the workspace. This writes the same `.vscode/mcp.json`
that the next section shows by hand. Run `./install.sh --harness vscode` from
the `valuebot` directory for a non-interactive install.

## (A) VS Code MCP configuration

Create `.vscode/mcp.json`. VS Code's guided flow now labels this format deprecated, but it remains the VS Code workspace format. Replace `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` with absolute paths; this format does not expand variables or `~`.

```json
{
  "servers": {
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

The `env` block is optional; every setting has a default. See the [canonical
minimal configuration](../README.md#minimal-configuration) for optional tuning.
An optional `envFile` may be used where supported by your VS Code version, but keep the server's required environment keys available.

## (B) Portable Copilot MCP configuration

For Copilot CLI, create `.mcp.json` at the workspace root or `~/.copilot/mcp-config.json`. This is the portable/CLI format: it uses `mcpServers`, has no `type` key, supports braced `${VAR}` expansion, and does not support `envFile`. Export `PLUGIN_ROOT` and `PLUGIN_DATA` first, or replace them with absolute paths.

```json
{
  "mcpServers": {
    "vw-mcp": {
      "command": "sh",
      "args": ["${PLUGIN_ROOT}/mcp/run.sh"],
      "env": {
        "EDGAR_LOCAL_DATA_DIR": "${PLUGIN_DATA}/edgar",
        "EDGAR_RATE_LIMIT_PER_SEC": "5",
        "EDGAR_HTTP_TIMEOUT": "30",
        "VW_MAX_HTML_MB": "40",
        "VW_MAX_FACTS_COMPANIES": "100",
        "VW_ENABLE_PRICE": "0",
        "VW_ARTIFACT_HTTP_PORT": "0",
        "VW_ARTIFACT_HTTP_HOST": "127.0.0.1",
        "VW_ARTIFACT_PUBLIC_BASE_URL": "",
        "UV_PROJECT_ENVIRONMENT": "${PLUGIN_DATA}/uv-env",
        "UV_CACHE_DIR": "${PLUGIN_DATA}/uv-cache",
        "UV_PYTHON_INSTALL_DIR": "${PLUGIN_DATA}/uv-python"
      }
    }
  }
}
```

The `env` block in this portable configuration is optional; every setting has a
default. Add it only when you need custom paths or limits.

## Skills and personas

Copy the five shared skills, without editing them, into `.github/skills/` (or `.agents/skills/`):

```bash
mkdir -p .github/skills
cp -R <PLUGIN_ROOT>/skills/grounded-citation .github/skills/
cp -R <PLUGIN_ROOT>/skills/hypothesis-analysis .github/skills/
cp -R <PLUGIN_ROOT>/skills/ratio-analysis .github/skills/
cp -R <PLUGIN_ROOT>/skills/dcf-valuation .github/skills/
cp -R <PLUGIN_ROOT>/skills/semantic-report-reading .github/skills/
```

Copy the six `.agent.md` persona files from this directory into `.github/agents/` (or the agent location used by your Copilot setup). The orchestrator references the other five as subagents. The citation auditor is read-only and must not add claims or rewrite drafts.

### Tool identifiers in persona frontmatter

The persona files name MCP tools as `vw-mcp_<tool>` (the `<server>_<tool>` form). VS Code has changed how it renders MCP tool identifiers between releases, so confirm the exact string before relying on the `tools:` lists:

1. Open the Tools picker in Copilot Chat.
2. Find the `vw-mcp` group and note the identifiers it shows.
3. If they differ from `vw-mcp_<tool>`, update the `tools:` list in each `.agent.md` file to match. Tools the harness cannot resolve are silently dropped, which shows up as a specialist that "answers without data".

The tool *set* per persona is authoritative; only the prefix format may vary.

## Approvals and permissions

Copilot may prompt for approval on each MCP tool call. Approve calls only when appropriate for the task. For unattended citation-view workflows, configure `chat.tools.autoApprove` narrowly for the relevant `vw-mcp_*` tools; do not broadly auto-approve all tools.

## GitHub Copilot Desktop

No documented Copilot Desktop MCP config format was found as of 2026-10-27. As a best effort, use the portable Copilot CLI configuration at `~/.copilot/mcp-config.json`; it supports stdio. Do not assume that this path or format is supported by Desktop.

## Troubleshooting

- **Server is not listed in the Tools picker**: confirm the configuration is in the correct workspace/user location, JSON parses, the MCP server is enabled, and restart or reconnect Copilot after changing it.
- **Launcher or path errors**: Replace every `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` placeholder; neither format expands `~`. Test with `sh <PLUGIN_ROOT>/mcp/run.sh`. The server exposes 19 tools: core 3, fundamentals 6, analysis 3, reports 5, and thesis 2; `symbol_resolve` takes `query`, not `symbol`.
- **`identity_not_configured`**: run `./setup.sh example-user@gmail.com` from the plugin root, then restart or reconnect the MCP server.
- **Need to validate the installation**: run `./setup.sh --doctor` from the plugin root.

The canonical launch contract is in [`../README.md`](../README.md). For cross-harness setup, see [`../../docs/users/09-multi-harness.md`](../../docs/users/09-multi-harness.md).