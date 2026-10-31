# 02 — Configuration

valuebot is configured through three things: one identity file, the `env:`
block in `mcp.json`, and optional environment overrides. Nothing is hardcoded
to a host path.

## Resolution order

```
mcp.json  env:            (LibreChat injects these into the server process)
      ↓
process environment       (shell, compose, CI)
      ↓
core/config.py defaults
```

`${PLUGIN_ROOT}` and `${PLUGIN_DATA}` are expanded by LibreChat before the
server starts:

| Placeholder | Value |
|:---|:---|
| `${PLUGIN_ROOT}` | absolute path of the plugin folder |
| `${PLUGIN_DATA}` | per-plugin writable data dir (`<DEPLOYMENT_PLUGIN_DATA_DIR>/valuebot`) |

`${PLUGIN_DATA}` is the only writable location. Nothing else needs to persist.

## SEC User-Agent

SEC requires every scripted client to identify itself. valuebot has exactly one
User-Agent, shared by edgartools and every direct HTTP call.

### One-time setup

```bash
PLUGIN_DATA=/app/data/plugins/valuebot /app/plugin/valuebot/setup.sh you@email.com
```

Writes `${PLUGIN_DATA}/identity.json`:

```json
{
  "user_agent": "valuebot you@email.com",
  "created_at": "2026-10-18T13:13:05+00:00"
}
```

The file is `0600` and survives restarts, container rebuilds of the plugin
folder, and upgrades.

### Accepted values

| Input | User-Agent sent to SEC |
|:---|:---|
| `you@email.com` | `valuebot you@email.com` |
| `Your Name you@email.com` | `Your Name you@email.com` |
| `Your Name <you@email.com>` | `Your Name you@email.com` |
| `research@example.com` | rejected (placeholder domain) |
| *(empty)* | rejected |

### Which addresses SEC accepts

SEC blocks some addresses at the edge with `403 Forbidden`. Verified on this
deployment:

| Address | Result |
|:---|:---|
| `you@gmail.com` | `200 OK` |
| `you@yourdomain.dev` | `200 OK` |
| `Name AdminContact@company.com` | `200 OK` |
| `name@users.noreply.github.com` | `403 Forbidden` |

Use a mailbox on a domain that receives mail. If you see
`edgar_unavailable … 403 Forbidden`, change the address with `setup.sh` and
restart.

### Managing the value

```bash
./setup.sh --show      # print the active User-Agent
./setup.sh --reset     # delete identity.json
```

### Environment override (CI and probes only)

`SEC_USER_AGENT` — or the legacy `EDGAR_IDENTITY` — takes precedence over the
file and is meant for one-off runs:

```bash
SEC_USER_AGENT="example-user@gmail.com" .venv/bin/python -m pytest tests -q -k live
```

> Do not put the identity in `mcp.json`. The stored file is the supported
> path; `mcp.json` stays free of personal data.

## Environment variables

| Variable | `mcp.json` value | Default | Owner |
|:---|:---|:---|:---|
| `SEC_USER_AGENT` | *(unset)* | `""` | `core` — override only; the real value lives in `identity.json` |
| `EDGAR_LOCAL_DATA_DIR` | `${PLUGIN_DATA}/edgar` | `${PLUGIN_DATA}/edgar` | `core` — edgartools HTTP cache |
| `EDGAR_RATE_LIMIT_PER_SEC` | `5` | `5` | `core` — SEC request throttle |
| `EDGAR_HTTP_TIMEOUT` | `30` | `30` | `core` — seconds |
| `PLUGIN_DATA` | *(injected by LibreChat)* | `~/.valuebot` | `core` — writable root |
| `VW_FUND_CACHE` | *(default)* | `${PLUGIN_DATA}/modules/fundamentals/cache.sqlite` | `fundamentals` |
| `VW_ANALYSIS_CACHE` | *(default)* | `${PLUGIN_DATA}/modules/analysis/cache.sqlite` | `analysis` |
| `VW_REPORTS_DB` | *(default)* | `${PLUGIN_DATA}/modules/reports/manifest.sqlite` | `reports` |
| `VW_REPORTS_ARTIFACTS` | *(default)* | `${PLUGIN_DATA}/modules/reports/artifacts` | `reports` |
| `VW_THESIS_ROOT` | `/vw-data/theses` | `${PLUGIN_DATA}/theses` | `thesis` — read-only vault |
| `VW_THESIS_INDEX` | *(default)* | `${PLUGIN_DATA}/modules/thesis/index.sqlite` | `thesis` |
| `VW_MAX_HTML_MB` | `40` | `40` | `reports` — filing HTML cap |
| `VW_MAX_FACTS_COMPANIES` | `100` | `100` | `fundamentals` — facts mirror LRU |
| `VW_ENABLE_PRICE` | `0` | `0` | reserved for `price_action` |
| `UV_PROJECT_ENVIRONMENT` | `${PLUGIN_DATA}/uv-env` | — | Python environment |
| `UV_CACHE_DIR` | `${PLUGIN_DATA}/uv-cache` | — | uv package cache |
| `UV_PYTHON_INSTALL_DIR` | `${PLUGIN_DATA}/uv-python` | — | Python builds (container `HOME` is not writable) |
| `VW_MCP_TRANSPORT` | *(unset)* | `stdio` | `mcp` — set `streamable-http` to serve HTTP instead |
| `VW_MCP_HTTP_HOST` | *(unset)* | `127.0.0.1` | `mcp` — HTTP bind address |
| `VW_MCP_HTTP_PORT` | *(unset)* | `8848` | `mcp` — HTTP bind port (path is always `/mcp`) |

The `/vw-data/theses` value in the `mcp.json` column applies to LibreChat deployments only. Every other harness should leave `VW_THESIS_ROOT` unset to use `<PLUGIN_DATA>/theses`; the `Default` column applies whenever a variable is absent. For the minimal required configuration, see [harnesses/README.md#minimal-configuration](../../harnesses/README.md#minimal-configuration).

The three `UV_*` values are set because the LibreChat container runs as a
non-root user with `HOME=/`. Pointing them at `${PLUGIN_DATA}` keeps `uv`
writable.

The `VW_MCP_*` values are **not** in `mcp.json` and need no entry there: the
server defaults to stdio, which is what every stdio harness wants. Only set
them when a client cannot launch a local process — currently just
[ChatGPT](../../harnesses/chatgpt/INSTALL.md), which needs
`streamable-http` behind a public HTTPS tunnel. Bind to `127.0.0.1` and prefer
the stdio path where it is available.

## Data directories

| Path | Contents | Rebuildable | Back up |
|:---|:---|:---|:---|
| `${PLUGIN_DATA}/identity.json` | SEC User-Agent | no (re-run setup) | optional |
| `${PLUGIN_DATA}/modules/fundamentals/cache.sqlite` | companies, ~25k facts per issuer, TTL cache | yes | no |
| `${PLUGIN_DATA}/modules/analysis/cache.sqlite` | 24 h metric results | yes | no |
| `${PLUGIN_DATA}/modules/reports/manifest.sqlite` | filing index, artifact manifest | yes | no |
| `${PLUGIN_DATA}/modules/reports/artifacts/{cik}/` | parsed semantics + raw HTML (gzip) | yes | no |
| `${PLUGIN_DATA}/modules/thesis/index.sqlite` | vault lookup index | yes | no |
| `${PLUGIN_DATA}/edgar/` | edgartools HTTP cache | yes | no |
| `${VW_THESIS_ROOT}/{TICKER}/` | your thesis documents | **no** | **yes** |

The vault is the only irreplaceable data. Everything else re-downloads from
SEC on demand.

## Thesis vault layout

The `thesis` module reads plain files from `{VW_THESIS_ROOT}/{TICKER}/`:

```
{vault}/AAPL/
├── thesis.md                      YAML front matter + markdown body
├── attachments/                   research notes, PDFs (listed, not parsed)
└── .thesis/annotations/*.json     {"mtime": …, "annotations": [...]}
```

- Front matter is parsed by a small stdlib parser; PyYAML is not required.
- An empty or missing vault is normal: both tools return `ok: true` with an
  explicit note instead of an error.
- Path traversal outside the ticker directory is rejected before any file is
  opened.
- The module never writes to the vault.

Example `thesis.md`:

```markdown
---
ticker: AAPL
conviction: medium
last_reviewed: 2026-09-30
tags: [services, hardware, buyback]
---
Services mix keeps expanding; hardware cycle is the swing factor.
Watch: gross margin guidance, China share, buyback pace.
```

## Tuning

| Goal | Setting |
|:---|:---|
| Stay well inside SEC's 10 req/s fair-access limit | keep `EDGAR_RATE_LIMIT_PER_SEC=5` |
| Slow networks | raise `EDGAR_HTTP_TIMEOUT` to `60` |
| Very large filings rejected as `artifact_too_large` | raise `VW_MAX_HTML_MB` (watch memory) |
| Many issuers cached at once | raise `VW_MAX_FACTS_COMPANIES` (each issuer is ~25k rows) |
| Disk pressure from parsed filings | lower the artifact LRU or delete `modules/reports/artifacts` |

Response sizes are capped per tool (6 KB or 8 KB) and are not configurable;
paging keeps large results readable instead of truncating them silently.

## What not to commit

`valuebot/.gitignore` already excludes:

```
.venv/  .pytest_cache/  __pycache__/  *.py[cod]
.probe-live/  .test-data/  identity.json
.env  .env.*  (!.env.example)
*.sqlite
```

Never commit `identity.json` — it contains your email address.

## Next

- [Tools reference](03-tools-reference.md)
- [LibreChat deployment](06-librechat-deployment.md)
- [Troubleshooting and FAQ](08-troubleshooting-and-faq.md)
