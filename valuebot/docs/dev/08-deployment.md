# 08 — Deployment and packaging

How the plugin is packaged, what LibreChat requires, and how to ship a change.

## Package layout

```
valuebot/
├── plugin.json                 manifest (Agent Plugins 1.0.0)
├── mcp.json                    stdio server + env contract
├── setup.sh                    one-time SEC User-Agent setup (POSIX sh)
├── README.md
├── LICENSE                     MIT
├── THIRD-PARTY-NOTICES.md      dependency licenses and attribution
├── requirements.txt            dev/test convenience
├── mcp/pyproject.toml          runtime dependency source of truth
├── mcp/server.py               entry point
├── mcp/core/                   shared library
├── mcp/modules/                six modules
├── skills/                     five SKILL.md bundles
├── agent-builder-exports/      six agent personas + INSTALL.md
├── docs/                       this documentation
└── tests/                      unit, contract, integration
```

`deploy/` and `eval/` existed in v1 and are intentionally gone.

## `plugin.json`

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "valuebot",
  "version": "0.2.0",
  "description": "…",
  "author": { "name": "ValueWaffle", "url": "https://github.com/valuewaffle/valuebot" },
  "license": "MIT",
  "keywords": ["finance", "sec-filings", "xbrl", "citations", "dcf", "research"]
}
```

Loader constraints (verified against LibreChat 0.8.8):

| Rule | Detail |
|:---|:---|
| Closed key set | `$schema`, `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`, `extensions` |
| `$schema` exact match | any other value → `manifest_unsupported_version`, plugin rejected |
| `name` | `^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$`, 1–64 chars, no `--` or `..` |
| `author` | strict object with only `name`, `email`, `url` |
| Duplicate name | second plugin skipped (`manifest_name_conflict`) |

Unknown top-level keys are a warning, not an error — but keep the manifest clean.

## `mcp.json`

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "vw-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--project", "${PLUGIN_ROOT}/mcp", "server.py"],
      "cwd": "${PLUGIN_ROOT}/mcp",
      "env": { "…": "…" }
    }
  }
}
```

| Rule | Detail |
|:---|:---|
| `$schema` | must be the MCP 1.0.0 schema, and its version must equal `plugin.json.version` |
| `command` | a bare executable or `./`-relative path; absolute paths, `/` and whitespace are rejected |
| `${PLUGIN_ROOT}` / `${PLUGIN_DATA}` | expanded once, non-recursively, in `env` values, `args` and `cwd` — **not** in `command` |
| `cwd` | must resolve inside `${PLUGIN_ROOT}` or `${PLUGIN_DATA}` |
| `env` | may not declare `PLUGIN_ROOT` or `PLUGIN_DATA`; LibreChat injects them |
| server name | must already be normalised; `__proto__`/`constructor`/`prototype` rejected |
| conflicts | a plugin server never displaces one declared in `librechat.yaml` |

`vw-mcp` is the server name, and LibreChat exposes tools as
`<tool>_mcp_vw-mcp`.

## Environment contract

| Variable | Set by | Purpose |
|:---|:---|:---|
| `SEC_USER_AGENT` | user (optional) | per-run identity override |
| `EDGAR_LOCAL_DATA_DIR` | `mcp.json` | edgartools HTTP cache |
| `EDGAR_RATE_LIMIT_PER_SEC`, `EDGAR_HTTP_TIMEOUT` | `mcp.json` | throttle and timeout |
| `VW_THESIS_ROOT` | `mcp.json` | read-only vault mount |
| `VW_MAX_HTML_MB`, `VW_MAX_FACTS_COMPANIES`, `VW_ENABLE_PRICE` | `mcp.json` | limits |
| `UV_PROJECT_ENVIRONMENT`, `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR` | `mcp.json` | keep `uv` writable in a container with read-only `HOME` |

Never put the SEC identity in `mcp.json`; it belongs in
`${PLUGIN_DATA}/identity.json`.

## Dependencies

`mcp/pyproject.toml` is the runtime source of truth; `requirements.txt` mirrors
it for local development.

```toml
requires-python = ">=3.11,<3.14"
dependencies = [
  "mcp>=2.2.0", "edgartools>=5.58,<6", "sec-parser>=0.58.1,<0.59",
  "beautifulsoup4>=4.14,<5", "lxml>=5.2.2,<6", "requests>=2.31",
]

[tool.uv]
package = false      # the server is a script, not an installable package
```

`package = false` keeps `uv run` from trying to build a wheel for a directory
that has no importable top-level package (it is `mcp/`, which would also shadow
the SDK).

Add a dependency: edit both files, keep the ranges aligned, and re-run
`uv sync --project mcp` before testing.

## Local vs runtime environment

| Context | How Python is provided |
|:---|:---|
| Tests and probes | `./bootstrap.sh` → `valuebot/.venv` |
| LibreChat spawn | `uv run --project ${PLUGIN_ROOT}/mcp server.py`, building `${PLUGIN_DATA}/uv-env` |

Never commit `.venv/`. Never add a `uv.lock` that pins a platform-specific build
for a plugin that ships as source (the deployment machine resolves its own).

## Packaging checklist

Before shipping a version:

| Step | Check |
|:---|:---|
| Version bumped | `plugin.json.version`, `mcp/pyproject.toml.version`, `server.py` `MCPServer(version=…)` |
| Schema versions aligned | `plugin.json.$schema` and `mcp.json.$schema` both 1.0.0 |
| Tool count | `server.py` `MODULE_TOOLS` matches the docs (16 domain + 3 core) |
| Skills present | five `skills/*/SKILL.md` |
| Agents valid | six JSON files; `tests/contract/test_package.py` enforces allowlists |
| Tests | `.venv/bin/python -m pytest tests -q` → 76 passed (or passed+skipped) |
| No secrets | `git status --short` has no `identity.json`, `.env`, `*.sqlite` |
| Docs updated | `docs/users/03-tools-reference.md` for any signature change |

## Recommended CI

There is no valuebot workflow yet. Suggested job:

```yaml
name: valuebot
on:
  push: { branches: [main], paths: ["valuebot/**"] }
  pull_request: { paths: ["valuebot/**"] }

jobs:
  test:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: valuebot } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python -m pytest tests -q
```

Fixture-dependent tests skip on a clean runner, which is expected. Live tests
need a real identity and network access — keep them out of PR CI.

## Release procedure

1. Bump the version in all three places.
2. Run the suite; confirm `76 passed` locally with fixtures.
3. Copy to LibreChat:

   ```bash
   rsync -a --delete \
     --exclude '.git' --exclude '.venv' --exclude '.test-data' \
     --exclude '.probe-live' --exclude '.pytest_cache' --exclude '__pycache__' \
     valuebot/ ./plugin/valuebot/
   ```

4. Verify the plugin loads:

   ```bash
   docker restart LibreChat
   docker logs --since 3m LibreChat 2>&1 | grep -E 'agentPlugins|\[MCP\]\[vw-mcp\]'
   ```

  Expect `5 skill(s), 1 MCP server(s)` and 19 tools.

5. Smoke-test `ping`, `symbol_resolve`, `ratio_compute`, `dcf_compute`.
6. Tag and archive.

## Publishing to the Claude Code marketplace

`.claude-plugin/marketplace.json` describes this repository as a single-plugin
marketplace and points Claude Code at the existing plugin manifest. Users can
add the marketplace and install the plugin with:

```text
/plugin marketplace add valuewaffle/valuebot
/plugin install valuebot@valuebot
```

No review or approval is required for this repository marketplace install. It
has no post-install hook, so run the one-time `./setup.sh <email>` step after
installation (or use `./install.sh` for the non-plugin path). A directory
listing in a curated marketplace is a separate, reviewed submission and is not
covered here.

## Rollback

```bash
mv ./plugin/valuebot ./plugin/valuebot.bak
mv ./plugin/valuebot.previous ./plugin/valuebot
docker restart LibreChat
```

If the previous version used a different artifact schema, delete
`${PLUGIN_DATA}/modules/` so it rebuilds. `identity.json` lives outside the
plugin folder and survives both directions.

## Observability

| Signal | Where |
|:---|:---|
| Plugin load, skills, MCP servers | `[agentPlugins]` lines |
| Server init, tool list | `[MCP][vw-mcp]` lines |
| Module failure | `[valuebot.mcp] module X failed to initialise` (stderr) |
| Per-call timing | `meta.elapsed_ms` in every response |
| Artifact build cost | `parse_ms` in the artifact JSON |
| Identity | `ping.data.identity_source` and `identity_file` |

## Next

- [Roadmap](09-roadmap.md)
- [Contributing](10-contributing.md)
