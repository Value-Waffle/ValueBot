# valuebot on Hermes Agent (Nous Research)

Hermes Agent is a listed **Agent Plugins 1.0** consumer, so valuebot installs
as a package with **no adapter**. The server is the same stdio MCP server, the
five skills are the same `SKILL.md` folders, and the data root is the same.
Only the launcher changes.

See the [harness overview](../README.md) for the canonical launch contract and
the [multi-harness guide](../../docs/users/09-multi-harness.md) for the
cross-harness overview.

The environment block is optional because every variable has a default in `mcp/core/config.py`; see the [two-key minimum](../README.md#minimal-configuration). The default thesis root is `<PLUGIN_DATA>/theses`.

## Prerequisites

Run the one-time SEC identity setup from the plugin root. Every data tool
returns `identity_not_configured` until this is done:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

## Path A — install as an Agent Plugins package (preferred)

No config editing, no adapter:

```bash
hermes plugins install owner/repo
hermes plugins enable <name>
```

> **The plugin arrives DISABLED.** A freshly installed package is not active,
> not loaded and does not appear in the tool list until `hermes plugins enable
> <name>` has been run. **This is the single most common failure mode** — users
> install, search for the tools, find nothing, and conclude the server is
> broken. `plugins list` shows it as installed-but-disabled rather than as an
> error, so nothing looks wrong.

`<name>` is the plugin name as Hermes reports it from `plugins list`; the repo
slug (`owner/repo`) and the plugin name are not always identical.

### Expansion and transport facts

| Fact | Meaning for valuebot |
|:---|:---|
| `${VAR}` is forwarded from the shell, or from a `.env` | Export the env keys below, or put them in the `.env` Hermes reads |
| `${userHome}` is supported | `<PLUGIN_ROOT>` may be written as `${userHome}/src/valuebot` |
| `${workspaceFolder}` is supported | Use it only if the plugin lives inside the project |
| Legacy **SSE** servers are skipped | valuebot is **stdio**, so this does not affect us |

Because Path A forwards the ambient environment, the 13 canonical keys must
exist in your shell or `.env`. Copy them verbatim — do not invent keys:

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

## Path B — manual `~/.hermes/config.yaml`

Use this when you cannot install packages, or when you want an explicit env
block instead of ambient variables. Hermes reads MCP servers from a top-level
`mcp_servers` key.

```yaml
mcp_servers:
  vw-mcp:
    command: sh
    args:
      - <PLUGIN_ROOT>/mcp/run.sh
    env:
      EDGAR_LOCAL_DATA_DIR: <PLUGIN_DATA>/edgar
      EDGAR_RATE_LIMIT_PER_SEC: "5"
      EDGAR_HTTP_TIMEOUT: "30"
      VW_MAX_HTML_MB: "40"
      VW_MAX_FACTS_COMPANIES: "100"
      VW_ENABLE_PRICE: "0"
      VW_ARTIFACT_HTTP_PORT: "0"
      VW_ARTIFACT_HTTP_HOST: 127.0.0.1
      VW_ARTIFACT_PUBLIC_BASE_URL: ""
      UV_PROJECT_ENVIRONMENT: <PLUGIN_DATA>/uv-env
      UV_CACHE_DIR: <PLUGIN_DATA>/uv-cache
      UV_PYTHON_INSTALL_DIR: <PLUGIN_DATA>/uv-python
```

**UNVERIFIED detail:** the top-level key `mcp_servers` is verified from the
Hermes adapter matrix. The *nested* entry keys (`command`, `args`, `env`) are
shown in the MCP stdio convention shared by every other client and have not
been confirmed verbatim for Hermes; check `hermes plugins list` / the Hermes
docs if your build rejects them.

The launcher is `sh` + `<PLUGIN_ROOT>/mcp/run.sh`, not `uv`. `run.sh` uses
`uv run --project` when `uv` is on `PATH` and otherwise builds a host-local
venv — so it works on a desktop without `uv`. Replace every `<PLUGIN_ROOT>`
and `<PLUGIN_DATA>` before saving; an unsubstituted `<...>` is the usual cause
of a spawn failure.

## Skills

Hermes reads skills from `~/.hermes/skills/` (agentskills.io). Copy the five
unchanged — never edit them:

```bash
mkdir -p ~/.hermes/skills
cp -R <PLUGIN_ROOT>/skills/grounded-citation        ~/.hermes/skills/
cp -R <PLUGIN_ROOT>/skills/hypothesis-analysis      ~/.hermes/skills/
cp -R <PLUGIN_ROOT>/skills/ratio-analysis           ~/.hermes/skills/
cp -R <PLUGIN_ROOT>/skills/dcf-valuation            ~/.hermes/skills/
cp -R <PLUGIN_ROOT>/skills/semantic-report-reading  ~/.hermes/skills/
```

Skills are namespaced `<plugin>:<skill>` — for example
`valuebot:grounded-citation`. Use the namespace prefix when invoking one
explicitly, otherwise Hermes resolves against the wrong plugin when two
plugins ship a skill with the same name.

## Personas

**UNVERIFIED detail.** Agent Plugins packages may carry an `agents/` folder
that the client extension maps to personas. The exact mapping, file naming and
frontmatter for Hermes are not documented in our verified matrix. Until that
is confirmed, treat the six personas as *not installed*: the behaviour that
matters (citation gating, ratio/DCF discipline, evidence verdicts) is already
carried by the five skills and the MCP tool descriptions. The canonical
persona text lives in [`../../agent-builder-exports/`](../../agent-builder-exports/)
if you want to paste instructions manually.

## Verify it worked

Call the health check first. It needs no identity and returns no citation:

```json
{"ok": true, "module": "core", "tool": "ping",
 "data": {"server": "valuebot", "version": "0.2.0",
          "modules": {"fundamentals": {"status": "ready"},
                      "analysis": {"status": "ready"},
                      "reports": {"status": "ready"},
                      "thesis": {"status": "ready"}},
          "identity_configured": false}}
```

**All four modules must read `ready`.** A module showing `unavailable` carries
an `error` and `error_code` in the same payload.

Next, call any data tool (for example `company_profile`). Until `./setup.sh`
has been run it returns:

```json
{"ok": false, "error": {"code": "identity_not_configured", ...}}
```

**That error means the wiring is correct** and only the SEC identity is
missing. It is not a Hermes problem.

## Troubleshooting

| Symptom | Cause | Fix |
|:---|:---|:---|
| Installed, but the plugin is not listed and no tools appear | The plugin is still **disabled** — `install` does not enable | `hermes plugins enable <name>` |
| Tools exist but every data call fails with `identity_not_configured` | Expected before setup | `./setup.sh example-user@gmail.com` |
| Server fails to spawn, path or `ENOENT` error | An unsubstituted `<PLUGIN_ROOT>` / `<PLUGIN_DATA>`, or `<PLUGIN_ROOT>` does not contain `mcp/run.sh` | Use absolute paths |
| Env vars missing inside the server after redaction | Variables were set in a shell that Hermes does not inherit | Put them in the `.env` Hermes reads, or use Path B's explicit `env:` block |
| A module reads `unavailable` in `ping` | Its dependency failed to import or its data root is unwritable | Check the `error_code` in the same payload and the `EDGAR_LOCAL_DATA_DIR` path |
