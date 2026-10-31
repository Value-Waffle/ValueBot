# 04 — Development setup

Local environment for running the server, the tests and probes. Installation
for production is different: LibreChat builds the environment itself with `uv`.

## 1. Python

| Requirement | Why |
|:---|:---|
| Python **3.11–3.13**, 3.12 recommended | Python 3.14 cannot import `edgartools` or `sec-parser` |
| `uv` (preferred) or `venv` + `pip` | environment and dependency management |

```bash
python3.12 --version     # must print 3.12.x
```

`.python-version` pins `3.12` for tools that honour it.

## 2. Create the environment

Preferred:

```bash
./bootstrap.sh
```

Fallback:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`bootstrap.sh` never leaves artifacts in `mcp/`; the venv lives at
`UV_PROJECT_ENVIRONMENT` (default `valuebot/.venv`).

| Flag | Effect |
|:---|:---|
| `--with-price` | also install the optional `price` extras (`yfinance`, `tzdata`) |
| `--dry-run` | print the commands, change nothing |

Dependencies (`requirements.txt`, mirrored in `mcp/pyproject.toml`):

```
mcp>=2.2.0              MCP SDK, stdio transport
edgartools>=5.58,<6     SEC identity, company resolution, XBRL facts, statements
sec-parser>=0.58.1,<0.59 semantic filing HTML
beautifulsoup4>=4.14,<5 table grid extraction
lxml>=5.2.2,<6          BeautifulSoup backend
requests>=2.31          submissions JSON + Archives HTML
pytest>=8.0             tests
```

Optional extras: `price = ["yfinance>=1.5.0", "tzdata>=2024.1"]` (reserved for
`price_action`).

## 3. Configure the SEC identity

Two options; both end at the same normalized User-Agent.

**Stored file (matches production):**

```bash
PLUGIN_DATA=~/.valuebot ./setup.sh you@email.com
PLUGIN_DATA=~/.valuebot ./setup.sh --show
```

**Per-run override (CI, probes):**

```bash
export SEC_USER_AGENT="example-user@gmail.com"
```

`EDGAR_IDENTITY` is accepted as a deprecated alias. Placeholder domains
(`example.com`) are rejected.

Check what the process resolved:

```bash
cd mcp
../.venv/bin/python -c "from core import config; print(config.describe()['SEC_USER_AGENT'])"
```

## 4. Run the server by hand

The server speaks newline-delimited JSON-RPC on stdio, so a plain terminal looks
hung — that is correct.

```bash
cd mcp
PLUGIN_DATA=/tmp/vb-dev ../.venv/bin/python server.py
```

Drive it with the test helper instead:

```python
# scripts/manual_stdio.py
import json, os, subprocess, sys

env = {**os.environ, "PLUGIN_DATA": "/tmp/vb-dev",
       "SEC_USER_AGENT": "example-user@gmail.com"}
proc = subprocess.Popen([sys.executable, "server.py"], cwd="mcp",
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True)

def call(payload):
    proc.stdin.write(json.dumps(payload) + "\n"); proc.stdin.flush()
    return json.loads(proc.stdout.readline())

call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                 "clientInfo": {"name": "dev", "version": "0"}}})
proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

print(call({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "ping", "arguments": {}}}))
proc.stdin.close()
```

Notes:

- Keep stdout clean. `print()` anywhere in `mcp/` corrupts the protocol; log to
  stderr.
- `tests/support_stdio.py` implements the same client with a background reader,
  which is what the contract tests use.

## 5. Offline vs live development

| Mode | Requires | Uses |
|:---|:---|:---|
| Offline | local fixtures at `VW_FIXTURE_DB` | `tests/unit`, `tests/integration` |
| Live | a valid SEC User-Agent and network | `tests -k live`, manual probes |

Fixtures default to `/Users/rkarumugam/LocalFiles/Projects/db`:

```
debug/jsonData/aapl/companyFacts_0000320193.json     24,852 facts
filing/us/AAPL/10-K/2025-09-27_0000320193-25-000079_aapl-20250927.htm
```

Override with `VW_FIXTURE_DB=/path/to/db`. Tests skip cleanly when the tree is
missing.

Offline probe of the full fundamentals → analysis path:

```bash
.venv/bin/python -m pytest tests/integration -q
```

## 6. Live probe

```bash
PLUGIN_DATA=/tmp/vb-live \
SEC_USER_AGENT="example-user@gmail.com" \
.venv/bin/python - <<'PY'
import sys
sys.path.insert(0, "mcp")
from modules.fundamentals.service import FundamentalsService
from modules.analysis.service import AnalysisService
from modules.reports.service import ReportsService

f, a, r = FundamentalsService(), None, ReportsService()
a = AnalysisService(f)
try:
    print(f.profile("AAPL")["cik"])
    print(len(r.filings("AAPL", forms=["10-K"], limit=3)["rows"]))
    print(a.dcf("AAPL", assumptions_only=True)["assumptions"][0])
finally:
    for s in (a, r, f):
        s.close()
PY
```

Expected: `320193`, `3`, and a `revenue_growth` assumption with
`source: derived`.

Clean up probe data afterwards — never commit a `.probe-live/` directory.

## 7. Debugging

| Problem | Approach |
|:---|:---|
| Server exits immediately | run `python server.py` in the foreground; stderr shows the import error |
| `No module named 'mcp'` | you are on the wrong interpreter, or `mcp/` shadowed the SDK — run from `mcp/` with the venv python |
| Tool returns `identity_not_configured` | set `SEC_USER_AGENT` or run `setup.sh` |
| Odd numbers | check `facts_version`, then `company_profile(refresh=true)` |
| Parser output looks wrong | inspect the artifact JSON in `modules/reports/artifacts/{cik}/` |
| Need raw JSON-RPC | `PYTHONUNBUFFERED=1` and read stdout line by line |

Logging is configured in `server.py`:

```python
logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="%(levelname)s %(name)s: %(message)s")
```

## 8. Repository hygiene

Ignored already: `.venv/`, `.uv-*/`, `.pytest_cache/`, `__pycache__/`,
`*.py[cod]`, `.probe-live/`, `.test-data/`, `identity.json`, `.env*` (except
`.env.example`), `*.sqlite`.

Before opening a PR:

```bash
.venv/bin/python -m pytest tests -q
git status --short            # no identity.json, no .sqlite, no probe data
```

## Next

- [Testing](05-testing.md)
- [Contributing](10-contributing.md)
