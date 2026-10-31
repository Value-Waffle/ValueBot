# 09 — Multi-harness setup

valuebot uses one MCP server, five shared skills, and one launcher file per
harness. The server, skills, tools, personas, and data stay the same; only the
host application's configuration and approval rules change.

## Support matrix

| Harness | Status | Install guide |
|:---|:---|:---|
| LibreChat | ✅ Shipped | [LibreChat install guide](../../harnesses/librechat/INSTALL.md) |
| Claude Code | ✅ Supported | [Claude Code install guide](../../harnesses/claude-code/INSTALL.md) |
| Claude Desktop (app) | ✅ Supported | [Claude Desktop install guide](../../harnesses/claude-desktop/INSTALL.md) |
| OpenAI Codex CLI | ✅ Supported | [Codex CLI install guide](../../harnesses/codex/INSTALL.md) |
| GitHub Copilot (VS Code) | ✅ Supported | [Copilot install guide](../../harnesses/copilot/INSTALL.md) |
| GitHub Copilot Desktop | ❌ Unverified | Use the portable Copilot CLI configuration only as a best effort; Desktop support is not documented. |
| ChatGPT Desktop | 🔌 Needs HTTPS tunnel | Connectors reach MCP only over a public HTTPS URL, so run the server's Streamable HTTP mode behind a tunnel. See [ChatGPT install guide](../../harnesses/chatgpt/INSTALL.md). |
| DeepSeek Harness (`dsh`) | 🚧 Developer preview | [DeepSeek install guide](../../harnesses/deepseek/INSTALL.md) |
| Gemini CLI | ✅ Supported | [Gemini CLI install guide](../../harnesses/gemini-cli/INSTALL.md) |
| Hermes Agent (Nous Research) | ✅ Supported | [Hermes install guide](../../harnesses/hermes/INSTALL.md) |
| OpenCode | ✅ Supported | [OpenCode install guide](../../harnesses/opencode/INSTALL.md) |
| Open WebUI | 🔌 Needs `mcpo` bridge | [Open WebUI install guide](../../harnesses/openwebui/INSTALL.md) |
| Pi (`pi.dev`) | ✅ Supported | [Pi install guide](../../harnesses/pi-agent/INSTALL.md) |

The [Getting started](01-getting-started.md) guide is harness-agnostic: it
covers the general idea, the common prerequisites, the launch contract, the
one-time SEC identity, the shared data root, and the verification checklist
that apply to every harness. Read it first, then follow your harness's install
guide above.

The canonical launch contract, including the full optional environment block, is
in the [harness overview](../../harnesses/README.md#optional-tuning). Every
variable there has a default, so no environment block is required. Do not
create a separate environment block for each harness.

## What stays the same vs what changes

| Stays the same | Changes by harness |
|:---|:---|
| The `sh <PLUGIN_ROOT>/mcp/run.sh` stdio server command | Configuration filename and schema |
| The 19 MCP tools and their namespaced equivalents | Whether `${VAR}` and `~` are expanded |
| Five skills and six valuebot personas | Skill/persona installation locations |
| SEC identity setup and shared data root | Approval prompts, permissions, and trust settings |

### The launcher

Every harness launches `sh <PLUGIN_ROOT>/mcp/run.sh`. It is the repository's
portable launcher: it uses `uv run --project` when `uv` is installed, and
otherwise builds a host-local venv and installs `requirements.txt`. LibreChat
is the exception — its image ships `uv`, so `mcp.json` calls `uv` directly.

The **transport** is normally stdio. ChatGPT is the one client that cannot
spawn a local process, so it uses the server's opt-in Streamable HTTP mode
(`VW_MCP_TRANSPORT=streamable-http`, endpoint `/mcp`). The default is
unchanged — stdio unless you ask otherwise.

Verify the server before wiring any harness:

```bash
cd <PLUGIN_ROOT>
sh mcp/run.sh
```

It starts the stdio server and waits for JSON-RPC on stdin. Press `Ctrl-C`
to stop; a `valuebot-mcp: launching via ...` line on stderr means the
launcher works.

### Path substitution

Replace `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` before saving any configuration.
Claude Code expands `${VAR}` and `${VAR:-default}`; portable Copilot expands
braced `${VAR}`; Codex CLI and Copilot's `.vscode/mcp.json` require literal
absolute paths. DeepSeek `dsh` requires absolute paths unless its documented
`!!js process.env.X` escape hatch is used. None of these configurations expand
`~`. The [harness overview](../../harnesses/README.md#path-substitution--read-this-before-copying-a-snippet)
has the detailed matrix.

## Quick installation

Start with the harness-agnostic [Getting started](01-getting-started.md), then
open your harness's install guide from the [support matrix](#support-matrix)
above. Each guide covers installation through additional info for that harness.

The common steps every harness shares are:

1. **Place the code** at `<PLUGIN_ROOT>` (your copy of valuebot).
2. **Run the one-time SEC identity setup** from the plugin root:

   ```bash
  ./setup.sh example-user@gmail.com
   ```

3. **Point the harness at the launcher** `sh <PLUGIN_ROOT>/mcp/run.sh` with the
   13 environment variables from the launch contract.
4. **Copy the five skills and six personas** from the harness folder (where the
   harness has a native skills/agents format).
5. **Verify** with `ping` and the checklist in the Getting started guide.

Harness-specific differences (config filename, `${VAR}`/`~` expansion, skill and
persona install locations, approval rules) are detailed in each install guide.

## Shared data root

Choose one writable `<PLUGIN_DATA>` directory and point every harness at it.
The SQLite caches, SEC HTTP cache, downloaded filings, and artifact store are
shared there, so switching harnesses reuses data already downloaded. Do not
copy data per harness: duplicate roots waste disk space, require repeated
downloads, and can make results differ between clients. Keep the plugin root
(code and configuration) separate from the data root (identity, caches, and
artifacts), so upgrades do not overwrite user data.

## Troubleshooting

- **`spawn uv ENOENT`:** you are launching `uv` directly and it is not
  installed. Launch `sh <PLUGIN_ROOT>/mcp/run.sh` instead, which falls back to
  a local venv. Also replace every `<PLUGIN_ROOT>` and `<PLUGIN_DATA>`
  placeholder; do not rely on `~`.
- **`sh: <PLUGIN_ROOT>/mcp/run.sh: No such file or directory`:** the
  `<PLUGIN_ROOT>` placeholder was not substituted, or `PLUGIN_ROOT` points at
  the repository root instead of the `valuebot/` plugin directory.
- **`dependency installation failed` from `run.sh`:** the venv fallback needs
  a package index. Install `uv` so the launcher takes the fast path, or
  pre-provision the venv.
- **Server is listed but no tools appear:** verify the configuration format and
  location for that harness, confirm the project is trusted where applicable,
  approve or enable the MCP server, and test the exact
  `sh <PLUGIN_ROOT>/mcp/run.sh` command from the install guide. Restart or
  reconnect after editing config.
- **A module reports `unavailable`:** call `ping` and read the per-module
  `status`, `error` and `error_code`. One failed module leaves the other three
  serving; fix the reported cause rather than reinstalling everything.
- **`identity_not_configured`:** run `./setup.sh example-user@gmail.com` from the
  plugin root with the same data root used by the harness, then reconnect the
  MCP server. Every data tool requires this SEC identity.
- **Approval prompts on `citation_view`:** citation evidence may require a
  separate tool approval. Approve the narrowly scoped valuebot MCP tools, or
  configure the harness's equivalent allowlist/auto-approval setting only in a
  trusted project. Do not broadly auto-approve unrelated tools.

For harness-specific schema details, consult the [harness overview](../../harnesses/README.md)
and its linked install guide.