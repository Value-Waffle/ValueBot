# valuebot on Pi (`pi.dev`)

> **Correction:** an earlier version of this file called Pi unsupported. That
> was wrong — it described Inflection's consumer assistant, a different
> product. **Pi at [pi.dev](https://pi.dev)** (Earendil Inc., npm
> `@earendil-works/pi-coding-agent`, MIT) is a terminal coding agent with
> **native stdio MCP support** and the Agent Skills spec. Verified 2026-10-27.

Pi is a minimal terminal agent harness. It supports MCP over stdio and
Streamable HTTP (legacy SSE is rejected), skills via `SKILL.md`, and any
OpenAI-compatible model endpoint. It deliberately has **no sub-agents**, so
the six valuebot personas do not map — the skills and MCP tools do.

See the [harness overview](../README.md) for the canonical launch contract and
the [multi-harness guide](../../docs/users/09-multi-harness.md) for the
cross-harness overview.

## Prerequisites

Run the one-time SEC identity setup from the plugin root:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

The environment block is optional because every variable has a default in `mcp/core/config.py`; see the [two-key minimum](../README.md#minimal-configuration).

## MCP configuration

Pi reads user config from `~/.pi/agent/mcp.json` and project config from
`.pi/mcp.json` (project config is only read after you trust the project).

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

`type` is optional and its default is stdio. `command` is a single executable
and is **never** run through a shell, which is why the launcher above is
`sh` + the script path rather than one combined string.

### Expansion rules

Pi is more flexible here than most clients:

| Where | Supported |
|:---|:---|
| `command`, an argument, `cwd` | `~/` expansion |
| `env` values, `headers` | `${VAR}` expansion |
| Any value | `!command` captures command output |

So `<PLUGIN_ROOT>` may be written as `~/src/valuebot`, and `<PLUGIN_DATA>` as
`${PLUGIN_DATA}` if you export it.

### CLI alternative

```bash
pi mcp add vw-mcp -- sh <PLUGIN_ROOT>/mcp/run.sh
```

Add the env keys afterwards in `~/.pi/agent/mcp.json`, because `pi mcp add`
takes only the command.

## Skills

Pi implements the Agent Skills spec and discovers `SKILL.md` recursively in
its skill directories, including `~/.agents/skills/` and `.agents/skills/`.
Copy the five unchanged:

```bash
mkdir -p .agents/skills
cp -R <PLUGIN_ROOT>/skills/grounded-citation .agents/skills/
cp -R <PLUGIN_ROOT>/skills/hypothesis-analysis .agents/skills/
cp -R <PLUGIN_ROOT>/skills/ratio-analysis .agents/skills/
cp -R <PLUGIN_ROOT>/skills/dcf-valuation .agents/skills/
cp -R <PLUGIN_ROOT>/skills/semantic-report-reading .agents/skills/
```

Invoke one explicitly with `/skill:grounded-citation`.

## Personas

Pi has no sub-agents, so `vw-orchestrator` and the five specialists cannot be
installed as agents. The behaviour that matters is already in the skills and
the MCP server instructions. If you want the persona instructions available,
copy the relevant body text from
[`../claude-code/personas/`](../claude-code/personas/) into an `AGENTS.md` in
your project — Pi reads project context, but treats it as instructions rather
than as a role.

## Models

DeepSeek is a first-class provider (`DEEPSEEK_API_KEY`). Any OpenAI-compatible
endpoint works by adding it to `models.json` with `baseUrl` and
`"api": "openai-completions"`.

## Troubleshooting

- **Tools not listed:** check that `~/.pi/agent/mcp.json` parses and that
  `sh <PLUGIN_ROOT>/mcp/run.sh` starts on its own. For project config,
  confirm the project is trusted — Pi ignores `.pi/mcp.json` until then.
- **`identity_not_configured`:** run `./setup.sh example-user@gmail.com`. This is the
  expected envelope before setup and is not a Pi problem.
- **Legacy SSE servers are rejected:** valuebot uses stdio, so this does not
  apply; it matters only if you add other servers.