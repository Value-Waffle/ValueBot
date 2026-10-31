# Third-party notices

valuebot itself is MIT licensed (see [`LICENSE`](LICENSE)). It does **not**
redistribute the packages below — they are installed at runtime into
`${PLUGIN_DATA}/uv-env` by `uv` from PyPI, under their own licenses. This file
records what those licenses are, so you can assess redistribution obligations
before you ship valuebot inside your own product.

Versions below are the ones resolved in the development environment
(`valuebot/.venv`). The runtime resolves the ranges declared in
[`mcp/pyproject.toml`](mcp/pyproject.toml).

## Direct dependencies

These are the packages valuebot imports or declares.

| Package | Declared range | License | Project |
|:---|:---|:---|:---|
| `mcp` | `>=2.2.0` | MIT | [modelcontextprotocol.io](https://modelcontextprotocol.io) |
| `edgartools` | `>=5.58,<6` | MIT | [github.com/dgunning/edgartools](https://github.com/dgunning/edgartools) |
| `sec-parser` | `>=0.58.1,<0.59` | MIT | [github.com/alphanome-ai/sec-parser](https://github.com/alphanome-ai/sec-parser) |
| `beautifulsoup4` | `>=4.14,<5` | MIT | [www.crummy.com/software/BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/bs4/) |
| `lxml` | `>=5.2.2,<6` | BSD-3-Clause | [github.com/lxml/lxml](https://github.com/lxml/lxml) |
| `requests` | `>=2.31` | Apache-2.0 | [github.com/psf/requests](https://github.com/psf/requests) |
| `pytest` | `>=8.0` | MIT | [github.com/pytest-dev/pytest](https://github.com/pytest-dev/pytest) |

### Optional extra: `price`

Not installed by default. Enabled only by `bootstrap.sh --with-price` and only
used when `VW_ENABLE_PRICE=1` — the `price_action` module is currently a
reserved protocol with no tools.

| Package | Declared range | License | Project |
|:---|:---|:---|:---|
| `yfinance` | `>=1.5.0` | Apache-2.0 | [github.com/ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) |
| `tzdata` | `>=2024.1` | Apache-2.0 | [github.com/python/tzdata](https://github.com/python/tzdata) |

> `yfinance` was not present in the inspected environment, so its license is
> recorded from the upstream project rather than from installed metadata.

## Transitive dependencies

Pulled in by the packages above. Listed for completeness.

| Package | Version | License |
|:---|:---|:---|
| `aiofiles` | 25.1.0 | Apache-2.0 |
| `annotated-types` | 0.8.0 | MIT |
| `anyio` | 4.15.1 | MIT |
| `attrs` | 26.1.0 | MIT |
| `certifi` | 2026.7.22 | MPL-2.0 |
| `chardet` | 7.7.0 | 0BSD |
| `charset-normalizer` | 3.5.2 | MIT |
| `cffi` | 2.1.1 | MIT-0 |
| `click` | 8.5.0 | BSD-3-Clause |
| `cryptography` | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| `cssutils` | 2.15.0 | LGPL-3.0-or-later |
| `encutils` | 1.0.0 | LGPL-3.0-or-later |
| `filelock` | 4.2.2 | MIT |
| `frozendict` | 2.4.7 | LGPL-3.0-or-later |
| `h11` | 0.16.0 | MIT |
| `httpcore` | 1.0.9 | BSD-3-Clause |
| `httpcore2` | 2.13.1 | BSD-3-Clause |
| `httpx` | 0.28.1 | BSD-3-Clause |
| `httpx2` | 2.13.1 | BSD-3-Clause |
| `httpxthrottlecache` | 0.7.0 | MIT |
| `humanize` | 4.16.0 | MIT |
| `idna` | 3.20 | BSD-3-Clause |
| `iniconfig` | 2.3.1 | MIT |
| `jinja2` | 3.1.6 | BSD-3-Clause |
| `jsonschema` | 4.26.0 | MIT |
| `jsonschema-specifications` | 2025.9.1 | MIT |
| `loguru` | 0.7.3 | MIT |
| `markdown-it-py` | 4.2.0 | MIT |
| `markupsafe` | 3.0.4 | BSD-3-Clause |
| `mcp-types` | 2.3.0 | MIT |
| `mdurl` | 0.1.2 | MIT |
| `more-itertools` | 11.2.1 | MIT |
| `nest-asyncio` | 1.6.0 | BSD-3-Clause |
| `numpy` | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| `opentelemetry-api` | 1.45.1 | Apache-2.0 |
| `orjson` | 3.13.0 | MPL-2.0 AND (Apache-2.0 OR MIT) |
| `packaging` | 26.3 | Apache-2.0 OR BSD-2-Clause |
| `pandas` | 2.3.3 | BSD-3-Clause |
| `pluggy` | 1.7.0 | MIT |
| `pyarrow` | 26.0.0 | Apache-2.0 |
| `pycparser` | 3.11 | BSD-3-Clause |
| `pydantic` | 2.14.1 | MIT |
| `pydantic-core` | 2.50.1 | MIT |
| `pygments` | 2.21.0 | BSD-2-Clause |
| `PyJWT` | 2.15.1 | MIT |
| `python-dateutil` | 2.9.0.post0 | BSD-3-Clause OR Apache-2.0 |
| `python-multipart` | 0.0.32 | Apache-2.0 |
| `pytz` | 2026.5 | MIT |
| `rank-bm25` | 0.2.2 | Apache-2.0 |
| `rapidfuzz` | 3.14.6 | MIT |
| `referencing` | 0.37.0 | MIT |
| `rich` | 15.0.0 | MIT |
| `rpds-py` | 2026.9.1 | MIT |
| `sec-downloader` | 0.11.2 | MIT |
| `sec-edgar-downloader` | 5.1.0 | MIT |
| `six` | 1.17.0 | MIT |
| `soupsieve` | 3.0.3 | MIT |
| `sse-starlette` | 3.5.0 | BSD-3-Clause |
| `stamina` | 26.1.0 | MIT |
| `starlette` | 1.8.0 | BSD-3-Clause |
| `tabulate` | 0.9.0 | MIT |
| `textdistance` | 4.6.3 | MIT |
| `truststore` | 0.10.5 | MIT |
| `typing-extensions` | 4.16.0 | PSF-2.0 |
| `typing-inspection` | 0.4.4 | MIT |
| `Unidecode` | 1.4.0 | GPL-2.0-or-later |
| `urllib3` | 2.8.0 | MIT |
| `uvicorn` | 0.54.0 | BSD-3-Clause |
| `xxhash` | 3.8.2 | BSD-2-Clause |

## Copyleft and source-available dependencies

Three of the resolved packages are copyleft, and one is source-available. All
are consumed **unmodified, as separately installed Python packages** that
valuebot imports at runtime — valuebot does not link their source into its own
code.

| Package | License | Reached through | Notes |
|:---|:---|:---|:---|
| `Unidecode` | GPL-2.0-or-later | `edgartools` → `unidecode>=1.2.0` | Used for ASCII transliteration of issuer names during company resolution. The dependency exists upstream, not by choice, and is not imported directly by valuebot code. |
| `cssutils` | LGPL-3.0-or-later | `sec-parser` | CSS parsing inside the filing HTML parser. |
| `encutils` | LGPL-3.0-or-later | `sec-parser` | Character-encoding helpers. |
| `frozendict` | LGPL-3.0-or-later | `sec-parser` | Immutable mapping used by the parser. |
| `certifi` | MPL-2.0 | `requests` | Mozilla Public License 2.0 — file-level copyleft, permissive in practice. |
| `orjson` | MPL-2.0 AND (Apache-2.0 OR MIT) | `edgartools` | Dual-licensed; the MIT/Apache option is available. |

**What this means for you.** If you run valuebot as-is, against PyPI, in a
container you own, the normal end-user obligations apply and nothing extra is
required from you. If you **redistribute** valuebot — vendored into your own
product, or shipped as a bundled wheel or frozen binary — you become the
distributor of the installed environment and should:

- keep the upstream license texts and copyright notices for every package in
  the environment, and
- satisfy the LGPL/GPL obligations for `Unidecode`, `cssutils`, `encutils` and
  `frozendict` (in practice: provide the corresponding source, or link to it,
  and allow replacement of the LGPL libraries).

This is a summary of the license metadata, not legal advice. Have counsel
review the obligations that apply to your distribution model.

## Verifying this file

The table above was generated from the `METADATA` of each installed
distribution (`License-Expression`, then `License`, then the
`Classifier: License ::` line). To re-derive it in your own environment:

```bash
cd valuebot
.venv/bin/python - <<'PY'
import importlib.metadata as md
for dist in sorted(md.distributions(), key=lambda d: (d.metadata["Name"] or "").lower()):
    m = dist.metadata
    lic = m.get("License-Expression") or m.get("License") or ""
    if not lic:
        lic = next((c for c in m.get_all("Classifier") or [] if c.startswith("License ::")), "")
    print(f'{m.get("Name")}=={m.get("Version")}\t{lic}')
PY
```

## Other third-party material

valuebot embeds no third-party source files. Two external data sources are
used at runtime and are **not** redistributed with it:

| Source | Use | Terms |
|:---|:---|:---|
| [SEC EDGAR](https://www.sec.gov/) | filings, XBRL facts, company submissions | [SEC.gov terms of use](https://www.sec.gov/os/accessing-edgar-data) — SEC requires an identifying User-Agent and a declared contact address; see [Configuration](docs/users/02-configuration.md#sec-user-agent) |
| [IANA time zone database](https://www.iana.org/time-zones) | via the optional `tzdata` package | IANA Time Zone Database License (public domain-like) |
