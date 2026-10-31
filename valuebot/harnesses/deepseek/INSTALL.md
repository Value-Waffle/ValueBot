# valuebot on DeepSeek Harness (`dsh`) — developer preview

> **Developer preview:** this integration is not a supported production path. DeepSeek Harness configuration and MCP behavior may change.

See the [harness overview](../README.md) for the canonical launch contract and the [multi-harness guide](../../docs/users/09-multi-harness.md) for cross-harness details.

## Prerequisites

Set `DSH_HOME` and choose absolute paths for the plugin and writable data root. Run the one-time SEC identity setup from the plugin root:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

## Before you configure

`run.sh` is the portable launcher: it uses `uv` when installed and otherwise builds a venv at `$PLUGIN_DATA/venv` (about 26 s on a first run). A restricted network needs `uv` installed first because the fallback installs from a package index.

The environment block is optional because every variable has a default in `mcp/core/config.py`; see the [two-key minimum](../README.md#minimal-configuration). The default thesis root is `<PLUGIN_DATA>/theses`.

## `cordis.yml`

DeepSeek Harness reads the profile configuration from `$DSH_HOME/profiles/<profile>/cordis.yml`. The file is a YAML plugin-entry list. Add this entry and replace the absolute path placeholders before saving it:

```yaml
- id: mcp-vw
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: vw
    transport: stdio
    command: sh
    args:
      - /absolute/path/to/valuebot/mcp/run.sh
    env:
      EDGAR_LOCAL_DATA_DIR: /absolute/path/to/valuebot-data/edgar
      EDGAR_RATE_LIMIT_PER_SEC: '5'
      EDGAR_HTTP_TIMEOUT: '30'
      VW_MAX_HTML_MB: '40'
      VW_MAX_FACTS_COMPANIES: '100'
      VW_ENABLE_PRICE: '0'
      VW_ARTIFACT_HTTP_PORT: '0'
      VW_ARTIFACT_HTTP_HOST: 127.0.0.1
      VW_ARTIFACT_PUBLIC_BASE_URL: ''
      UV_PROJECT_ENVIRONMENT: /absolute/path/to/valuebot-data/uv-env
      UV_CACHE_DIR: /absolute/path/to/valuebot-data/uv-cache
      UV_PYTHON_INSTALL_DIR: /absolute/path/to/valuebot-data/uv-python
```

The canonical environment block is:

```dotenv
EDGAR_LOCAL_DATA_DIR=<PLUGIN_DATA>/edgar
EDGAR_RATE_LIMIT_PER_SEC=5
EDGAR_HTTP_TIMEOUT=30
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

`dsh` does not expand `~` or `${VAR}` in this configuration. Use absolute paths, or use `!!js process.env.X` as the escape hatch for values supplied by the process environment. Ambient environment variables matching `KEY|PASSWORD|SECRET|TOKEN` are scrubbed, so do not rely on those being inherited. The MCP tools surface as `mcp__vw__<tool>`.

## Skills and personas

Support for copying `SKILL.md` files and for persona/agent files in `dsh` is **UNVERIFIED as of 2026-10-27**. No corresponding format was found in the dsh documentation. Do not assume the Claude Code, Codex, or Copilot formats work; consult the current [dsh plugin documentation](https://github.com/deepseek-ai/deepseek-harness) before attempting to add them.

## Troubleshooting

- **Profile not loaded:** verify `DSH_HOME`, the selected profile name, and the exact path `$DSH_HOME/profiles/<profile>/cordis.yml`; restart `dsh` after editing.
- **Invalid `serverName`:** use only `[A-Za-z0-9_-]{1,32}`; `vw` is valid.
- **Server fails with `failOnStartupError`:** replace every absolute-path placeholder, and run `sh /absolute/path/to/valuebot/mcp/run.sh` directly. The server exposes 19 tools: core 3, fundamentals 6, analysis 3, reports 5, and thesis 2; `symbol_resolve` takes `query`, not `symbol`.
- **`identity_not_configured`:** run `./setup.sh example-user@gmail.com` from the plugin root, then reconnect the MCP client.