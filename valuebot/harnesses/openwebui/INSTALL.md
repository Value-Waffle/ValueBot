# valuebot on Open WebUI

**Read this constraint first.** Open WebUI's native MCP support is
**Streamable HTTP only** — it has had no native stdio MCP transport since
v0.6.31 added MCP. valuebot is a **stdio-only** MCP server. There is therefore
**no way to point Open WebUI at `mcp/run.sh` directly**: an `mcpo` bridge is
**mandatory**, not an optional convenience. Open WebUI has no native stdio
config file at all, so every step below is the supported path.

See the [harness overview](../README.md) for the canonical launch contract and
the [multi-harness guide](../../docs/users/09-multi-harness.md) for the
cross-harness overview.

## Prerequisites

Run the one-time SEC identity setup from the plugin root:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

Open WebUI must be **v0.6.31 or newer**, and MCP support needs **both** of:

- **`WEBUI_SECRET_KEY` set** to a stable value. Without it, stored integration
  settings (including external tool servers) cannot be persisted/signed
  reliably, and the integration silently does not survive a restart.
- **`ENABLE_TOOL_SERVERS` not set to `false`.** If it is present and false,
  the External Tool Servers page does nothing.

The environment block is optional because every variable has a default in `mcp/core/config.py`; see the [two-key minimum](../README.md#minimal-configuration).

## Step 1 — write the bridge config (Claude format)

`mcpo` takes a **Claude-format** stdio MCP config: a top-level `mcpServers`
object. Save it somewhere stable, e.g. `~/valuebot-mcpo.json`, and replace
every `<PLUGIN_ROOT>` / `<PLUGIN_DATA>` with absolute paths:

```json
{
  "mcpServers": {
    "vw-mcp": {
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

The `env` block is optional reference: every key shown has a default in
`mcp/core/config.py`. Keep it when you need absolute paths — `mcpo` does not
expand `${VAR}` or `~` here, so any path you do set must be absolute. The
server name in this file (`vw-mcp`) becomes the **URL path segment** in step 3
— keep it.

## Step 2 — start the bridge

```bash
uvx mcpo --config ~/valuebot-mcpo.json --port 8000
```

`mcpo` exposes each server in the config at `http://<host>:<port>/<server-name>`,
which for the file above is `http://localhost:8000/vw-mcp`. Leave this process
running: it owns the stdio child (`mcp/run.sh`), so stopping it removes every
tool from Open WebUI.

### Security note — bind to localhost only

`mcpo` serves the MCP server over plain HTTP with **no authentication of its
own**. Anyone who can reach the port can call the tools and read filings,
theses and cached facts. Therefore:

- run it on `localhost` and **do not expose or port-forward `:8000`**;
- do not add it to a reverse proxy that is reachable from other machines;
- on a shared host, restrict it with a firewall rule for the loopback only.

## Step 3 — register the server in Open WebUI

1. **Admin** → **Integrations** → **External Tool Servers** → **Add**
2. **Type:** `MCP (Streamable HTTP)`
3. **URL:** `http://localhost:8000/vw-mcp` — **the path must include the
   server name**. `http://localhost:8000` alone yields a bridge that answers
   but exposes **zero tools**.
4. Save, then refresh the chat's tool list.

## Skills

Then **Workspace** → **Skills** → upload the five `SKILL.md` folders from
[`../../skills/`](../../skills/). Copy them unchanged:

```bash
ls <PLUGIN_ROOT>/skills/
# dcf-valuation  grounded-citation  hypothesis-analysis
# ratio-analysis  semantic-report-reading
```

Open WebUI stores skills as markdown with `SKILL.md` frontmatter; the content
is not edited.

## Personas

Open WebUI has **no sub-agent concept**, so `vw-orchestrator` and the five
specialists cannot be installed as agents. Approximate a persona with
**Workspace → Models**: create a model preset per persona, paste the
instructions from the matching file in
[`../../agent-builder-exports/`](../../agent-builder-exports/), and attach the
relevant tool subset and skills to that preset. Behaviour is approximated, not
enforced — there is no dispatch and no audit gate.

## Verify it worked

Call `ping` from a chat with the tool server enabled. It needs no identity and
returns no citation:

```json
{"ok": true, "module": "core", "tool": "ping",
 "data": {"server": "valuebot", "version": "0.2.0",
          "modules": {"fundamentals": {"status": "ready"},
                      "analysis": {"status": "ready"},
                      "reports": {"status": "ready"},
                      "thesis": {"status": "ready"}},
          "identity_configured": false}}
```

**All four modules must read `ready`.**

Then call any data tool (for example `company_profile`). Until `./setup.sh`
has been run it returns:

```json
{"ok": false, "error": {"code": "identity_not_configured", ...}}
```

**That error means the wiring is correct** — the bridge, the URL and the env
block are all working, and only the SEC identity is missing. It is not an
Open WebUI problem.

## Troubleshooting

| Symptom | Cause | Fix |
|:---|:---|:---|
| Bridge responds, but the tool server shows **zero tools** | Wrong URL path — the server name segment is missing | Use `http://localhost:8000/vw-mcp`, not `http://localhost:8000` |
| External Tool Servers page is inert / settings do not persist | `ENABLE_TOOL_SERVERS=false`, or `WEBUI_SECRET_KEY` unset | Set a stable `WEBUI_SECRET_KEY`, remove the `false` |
| Connection refused | `mcpo` is not running, or stopped | Restart `uvx mcpo --config ~/valuebot-mcpo.json --port 8000` |
| Every data call returns `identity_not_configured` | Expected before setup | `./setup.sh example-user@gmail.com` |
| `mcpo` exits immediately | Unsubstituted `<PLUGIN_ROOT>` in the config, or `mcp/run.sh` missing | Fix the path; test `sh <PLUGIN_ROOT>/mcp/run.sh` on its own |
| Env vars appear missing inside the server | They are not in the bridge config's `env` block; `mcpo` does not inherit arbitrary shell state on every launcher | Set the few keys you actually need in the JSON — all of them have defaults |
