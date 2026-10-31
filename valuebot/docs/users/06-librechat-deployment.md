# 06 — LibreChat deployment

Deploying valuebot in a self-hosted, Dockerised LibreChat.

**Verified against:** LibreChat **0.8.8** (`librechat-ai/librechat-dev:latest`),
Agent Plugins schema **1.0.0**, Python 3.13 built by `uv` inside the container.

## How LibreChat loads plugins

| Step | Behaviour |
|:---|:---|
| Scan | immediate subdirectories of `DEPLOYMENT_PLUGINS_DIR` (default `/app/plugin`) |
| Manifest | `plugin.json` must match the 1.0.0 schema exactly, or the plugin is rejected |
| MCP | `mcp.json` must be valid and its `$schema` version must match `plugin.json` |
| Substitution | `${PLUGIN_ROOT}` and `${PLUGIN_DATA}` expand in `env` values, `args` and `cwd` — not in `command` |
| Spawn | `command` must be a bare executable (`uv`), with `cwd` inside the plugin or data root |
| Data dir | `${DEPLOYMENT_PLUGIN_DATA_DIR}/<plugin name>` is created on boot |
| Tools | exposed as `<tool>_mcp_vw-mcp`; nothing is auto-attached to a chat |

Logs to confirm success:

```text
[agentPlugins] Loaded 1 plugin(s) from /app/plugin: 5 skill(s), 1 MCP server(s)
[MCP][vw-mcp] Initialized in: 1086ms
[MCP] Initialized with 1 configured server and 19 tools.
```

A plugin that fails validation logs `[agentPlugins] <diagnostic> (<location>)`
and is skipped — the rest of LibreChat keeps running.

## 1. Environment

Set these in `docker-compose.override.yml` (or `.env`), not in the plugin:

```yaml
services:
  api:
    environment:
      - DEPLOYMENT_PLUGINS_DIR=/app/plugin
      - DEPLOYMENT_PLUGIN_DATA_DIR=/app/data/plugins
      - DEPLOYMENT_PLUGIN_HOOKS=false      # valuebot ships no hooks
    volumes:
      - ./plugin:/app/plugin
      - ./librechat.yaml:/app/librechat.yaml:ro
```

Use the same `${PLUGIN_DATA}` volume across restarts, or every restart re-syncs
facts and re-parses filings.

Optional but recommended for a thesis vault:

```yaml
    volumes:
      - "/path/to/theses:/vw-data/theses:ro"
```

`mcp.json` points `VW_THESIS_ROOT` at `/vw-data/theses`; override it if your
mount differs.

## 2. Place the plugin

```bash
git clone <valuebot-repo> ./plugin/valuebot
chmod +x ./plugin/valuebot/setup.sh
```

The directory name becomes the plugin name. Keep it `valuebot` so the paths in
this documentation and in `agent-builder-exports/` match.

## 3. One-time SEC User-Agent

The plugin has no built-in User-Agent and will not call SEC until one is set.

```bash
docker exec LibreChat sh -lc \
  'PLUGIN_DATA=/app/data/plugins/valuebot /app/plugin/valuebot/setup.sh you@email.com'
```

Verify:

```bash
docker exec LibreChat sh -lc \
  'PLUGIN_DATA=/app/data/plugins/valuebot /app/plugin/valuebot/setup.sh --show'
```

Notes specific to LibreChat containers:

- The image has **no `bash`**; `setup.sh` is POSIX `sh` for this reason.
- `HOME` is `/` and not writable, so `UV_CACHE_DIR`,
  `UV_PROJECT_ENVIRONMENT` and `UV_PYTHON_INSTALL_DIR` must point inside
  `${PLUGIN_DATA}` — `mcp.json` already does this.
- `identity.json` is written with mode `0600` and survives plugin updates
  because it lives in the data dir, not the plugin dir.

## 4. Prime the Python environment

`uv` builds `${PLUGIN_DATA}/uv-env` on first spawn. That takes 60–120 s;
priming it during deployment avoids a first-call timeout:

```bash
docker exec LibreChat sh -lc '
  PLUGIN_DATA=/app/data/plugins/valuebot \
  UV_PROJECT_ENVIRONMENT=/app/data/plugins/valuebot/uv-env \
  UV_CACHE_DIR=/app/data/plugins/valuebot/uv-cache \
  UV_PYTHON_INSTALL_DIR=/app/data/plugins/valuebot/uv-python \
  uv sync --project /app/plugin/valuebot/mcp'
```

## 5. Restart and verify

```bash
docker restart LibreChat
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3080/)
  [ "$code" != "000" ] && break; sleep 2
done
echo "HTTP=$code"
docker logs --since 5m LibreChat 2>&1 | grep -E 'agentPlugins|\[MCP\]'
```

Functional checks:

1. In a chat, ask **"Use ping and list module statuses."** → four modules
   `ready`, `identity_configured: true`, `identity_source: file`.
2. `symbol_resolve("AAPL")` → CIK 320193.
3. `company_profile("AAPL")` → issuer metadata, fiscal year end.
4. `filing_list("AAPL", forms=["10-K"])` → recent accessions, newest first.
5. `ratio_compute("AAPL", ["gross_margin", "roe"])` → values plus citations.
6. `dcf_compute("AAPL", assumptions_only=true)` → assumption table with WACC and
   terminal growth marked `default`.

Optional API-level check (per-user MCP catalogue):

```bash
# after logging in and exporting a JWT
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:3080/api/mcp/tools | jq '.servers["vw-mcp"].tools[].name'
```

Expect 16 names. `GET /api/mcp/servers` and
`GET /api/mcp/connection/status` confirm `connectionState: "connected"`.

## 6. Volumes and backups

| Path | Content | Size | Backup |
|:---|:---|:---|:---|
| `${PLUGIN_DATA}/identity.json` | SEC User-Agent | < 1 KB | optional |
| `${PLUGIN_DATA}/modules/fundamentals/cache.sqlite` | companies + facts mirror | tens of MB | no |
| `${PLUGIN_DATA}/modules/analysis/cache.sqlite` | metric cache (24 h) | small | no |
| `${PLUGIN_DATA}/modules/reports/manifest.sqlite` | filing index + artifact manifest | small | no |
| `${PLUGIN_DATA}/modules/reports/artifacts/` | parsed sections + raw HTML | hundreds of MB | no |
| `${PLUGIN_DATA}/modules/thesis/index.sqlite` | vault index | tiny | no |
| `${PLUGIN_DATA}/edgar/` | edgartools HTTP cache | tens of MB | no |
| `${PLUGIN_DATA}/uv-env/`, `uv-cache/`, `uv-python/` | Python environment | hundreds of MB | no |
| `${VW_THESIS_ROOT}` | your thesis vault | yours | **yes** |

Every cache is rebuildable from SEC. The vault is the only irreplaceable data.

To reclaim space without losing configuration:

```bash
docker exec LibreChat rm -rf /app/data/plugins/valuebot/modules/reports/artifacts/* 
docker exec LibreChat rm -rf /app/data/plugins/valuebot/edgar
```

## 7. Upgrades

```bash
rsync -a --delete \
  --exclude '.git' --exclude '.venv' --exclude '.test-data' \
  --exclude '.probe-live' --exclude '.pytest_cache' --exclude '__pycache__' \
  <repo>/valuebot/ ./plugin/valuebot/
docker restart LibreChat
```

Notes:

- Never `--delete` the data dir; `identity.json` and caches live there.
- A new dependency triggers a `uv` re-sync on the next spawn; expect a slow
  first call unless you re-run `uv sync` first.
- Check `plugin.json` → `mcp.json` schema versions stay in step. A mismatch
  disables the MCP server with `mcp_version_mismatch`.

### Rollback

Keep the previous plugin folder:

```bash
mv ./plugin/valuebot ./plugin/valuebot.bak
mv ./plugin/valuebot.previous ./plugin/valuebot
docker restart LibreChat
```

The data dir is version-agnostic only within a major schema change; on a
downgrade, delete `${PLUGIN_DATA}/modules/*` so the older code rebuilds its
tables.

## 8. Multiple plugins

Several plugin directories can coexist; each gets its own subdirectory under
`DEPLOYMENT_PLUGIN_DATA_DIR`. Server names must be unique — `vw-mcp` is
valuebot's. A duplicate name is skipped with a warning, and a plugin server
never overrides a server declared in `librechat.yaml`.

## 9. Hooks

`DEPLOYMENT_PLUGIN_HOOKS` is `false` in the reference override. valuebot ships
no `ai.librechat/hooks/hooks.json`, so enabling hooks is unnecessary. Leave it
off unless another plugin needs it.

## 10. Reference configuration

[`../../librechat.example.yaml`](../../librechat.example.yaml) is a
ready-to-merge snippet for the LibreChat side; the compose override above is the
container side.

## Next

- [Model endpoints](07-model-endpoints.md)
- [Troubleshooting and FAQ](08-troubleshooting-and-faq.md)
- [dev/08-deployment.md](../dev/08-deployment.md) — manifest internals and CI
