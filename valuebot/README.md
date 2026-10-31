# valuebot v2 — LibreChat Agent Plugin

> ### ⚠️ Educational use only — not investment advice
>
> valuebot is a **research and educational tool**. It is not a financial
> adviser, broker, dealer, or registered investment adviser, and it makes no
> recommendations. Nothing it produces — including any discounted cash flow
> value — is a price target or a prediction of future price.
>
> You are responsible for every decision you make. See the
> [full disclaimer](#disclaimer--not-investment-advice) and the
> [data usage terms](#data-usage-and-source-terms) below.

valuebot is a distributable **Agent Plugin for LibreChat** with five skills and a
stdio MCP server split into modules that are isolated by the data they use:

Verified end-to-end against **LibreChat 0.8.8** (`librechat-dev:latest`): the
plugin loads as 5 skills + 1 MCP server, with 19 tools — 3 core (`ping`,
`citation_resolve`, `citation_view`) plus 16 domain (fundamentals 6, analysis
3, reports 5, thesis 2) — exposed to the model
as `<tool>_mcp_vw-mcp`, and tool calls return live SEC data.

| Module | Owns | Tools |
|:---|:---|:---|
| `fundamentals` | SEC XBRL facts, company identity, annual statements, line-item vocabulary | `symbol_resolve`, `company_profile`, `facts_query`, `facts_export`, `facts_timeseries`, `statement_get` |
| `analysis` | 36 ratio/growth metrics and a simple FCFF DCF | `ratio_catalog`, `ratio_compute`, `dcf_compute` |
| `reports` | filing index, sec-parser sections, notes and table grids | `filing_list`, `report_sections`, `report_section`, `report_search`, `report_table` |
| `thesis` | read-only investment vault and annotations | `thesis_read`, `thesis_annotations` |
| `calendar`, `price_action` | reserved protocols, no tools | — |

16 domain tools plus 3 core tools. Each module has its own SQLite file, artifacts,
migrations, configuration and tests. No module imports another module's
internals or reads another module's tables. `analysis → fundamentals` is the
only cross-module edge.

Supported: **LibreChat 0.8.8+** · Agent Plugins schema **1.0.0** ·
MCP SDK **2.2.0+** · Python **3.11–3.13** (3.12 recommended).

## Quick install

If your harness reads a local JSON MCP config, the installer writes the entry
for you — and merges it, so an existing config keeps every other server:

```sh
cd valuebot
./install.sh --harness claude-code --email example-user@gmail.com
```

It supports `claude-desktop`, `claude-code`, `vscode`, `copilot-cli` and
`gemini-cli`. Add `--dry-run` to print the resulting JSON without writing it,
and `--help` for every option. Harnesses without a local JSON config
(LibreChat, Codex, DeepSeek, Hermes, Pi, ChatGPT, OpenCode, Open WebUI) are
installed by hand: the per-harness guides in
[`harnesses/`](harnesses/README.md) remain the reference for those.

## Install

The full procedure — including the one-time SEC identity setup, the Docker
volume, and the agent import — is in
**[01 — Getting started](docs/users/01-getting-started.md)**. It takes about
ten minutes.

In short: copy this folder into LibreChat's plugins directory as `valuebot`,
run `setup.sh` once with your email address, restart LibreChat, and import the
six agents from [`agent-builder-exports/INSTALL.md`](agent-builder-exports/INSTALL.md).

There is **no default User-Agent**; the data tools return
`identity_not_configured` until the setup has been run.

Dockerised LibreChat: see
[06 — LibreChat deployment](docs/users/06-librechat-deployment.md).
Model endpoints: see
[`docs/users/07-model-endpoints.md`](docs/users/07-model-endpoints.md).

## Data usage and source terms

valuebot reads **public SEC filings**. It does not redistribute them, and it
does not let you request arbitrary URLs — every tool addresses SEC endpoints by
issuer. The data has rules, and so do the libraries that fetch it.

### SEC EDGAR

The SEC publishes filings for free and asks every automated client to identify
itself and to stay within a rate limit. Per the
[SEC's "Accessing EDGAR Data" page](https://www.sec.gov/os/accessing-edgar-data):

> "Please declare your user agent in request headers" — a company name and a
> contact email address.

> "Current max request rate: 10 requests/second."

The SEC also states that it "reserves the right to limit request rates to
preserve fair access for all users", and that requests identified as part of a
botnet or as an automated tool outside the acceptable policy "will be managed
to ensure fair access for all users". The governing policy is the
[SEC Internet Security Policy](https://www.sec.gov/about/privacy-information#security).

| Requirement | How valuebot meets it |
|:---|:---|
| Declare a User-Agent with a contact address | The one-time setup writes `identity.json`; every request carries `User-Agent: valuebot <email>` |
| Stay under 10 requests/second | `EDGAR_RATE_LIMIT_PER_SEC` defaults to `5` — deliberately under the cap |
| Identify yourself, do not crawl | The plugin fetches a defined set of SEC endpoints for one issuer at a time |
| Do not redistribute the data | Filings are cached locally under `${PLUGIN_DATA}` for your own use; they are never republished |

**These obligations are yours too, as the operator.** Give the plugin a real
mailbox you can receive mail at, and do not raise the rate limit above the
SEC's cap.

### The libraries that fetch the data

| Library | License | What it does here | Terms that come with it |
|:---|:---|:---|:---|
| [edgartools](https://github.com/dgunning/edgartools) | MIT | Company resolution, XBRL facts, statements | Carries the SEC's identity requirement: `set_identity()` sets the `EDGAR_IDENTITY` User-Agent, and the library points at the [SEC's access policy](https://www.sec.gov/os/accessing-edgar-data). `EDGAR_RATE_LIMIT_PER_SEC` and `EDGAR_HTTP_TIMEOUT` are the controls it exposes. |
| [sec-parser](https://github.com/alphanome-ai/sec-parser) | MIT | Parses SEC filing HTML into semantic sections, notes and tables | Carries its own disclaimer, which valuebot adopts: sec-parser is "an independent, open-source initiative and has no affiliation, endorsement, or verification by the United States Securities and Exchange Commission (SEC). It utilizes public APIs and data provided by the SEC solely for research, informational, and educational objectives. This tool is not intended for financial advisement." |

Both are MIT-licensed and carry no separate commercial-use restriction. The
full dependency inventory, with every transitive package and its license, is
in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

### Your thesis vault

valuebot can read a folder of **your own** research notes. It never writes to
it, and it is the only data in the system that cannot be re-downloaded. If you
put confidential material there, treat it as confidential — the plugin has no
encryption and no access control of its own.

### Configuration

The plugin never hardcodes host paths. Every root resolves as **`mcp.json`
`env:` → `core/config.py` default**, and only `${PLUGIN_DATA}` is writable.
SEC data is fetched live and cached; no local pipeline is required.

The full environment-variable table, the data directory layout and the
resolution order are in
**[02 — Configuration](docs/users/02-configuration.md)**.

## Tools

`symbol_resolve` · `company_profile` · `facts_query` · `facts_timeseries` ·
`statement_get` · `ratio_catalog` · `ratio_compute` · `dcf_compute` ·
`filing_list` · `report_sections` · `report_section` · `report_search` ·
`report_table` · `thesis_read` · `thesis_annotations` · `ping`

Every response is byte-capped (2–8 KB), pages with `offset`/`next_offset`, and
carries `citations[]` or an explicit no-citation note for table-only slices.

### DCF

`dcf_compute` is a simple FCFF DCF:
`FCFF = EBIT × (1 − tax) + D&A − capex − ΔNWC`.
Call it without assumptions and it derives them from annual history, labels each
`user`, `derived` or `default`, and returns the assumption table with the
valuation. `assumptions_only=true` returns the table alone. Rates are decimals
(`0.08` = 8%). WACC (9%) and terminal growth (2.5%) are policy defaults, not
market observations. The output is an intrinsic value, not a price target.

## Verify

```bash
./bootstrap.sh                       # creates .venv, installs dependencies
.venv/bin/python -m pytest tests -q  # 76 passed
```

Offline tests use real AAPL fixtures from `VW_FIXTURE_DB` (default
`/Users/rkarumugam/LocalFiles/Projects/db`); they skip when the fixture tree is
absent.

Live check (requires a real identity):

```bash
SEC_USER_AGENT="example-user@gmail.com" .venv/bin/python -m pytest tests -q -k live
```

The live tests use the environment override; normal deployments use the
stored `identity.json` written by `./setup.sh`.

The full test guide — every test file, its objective, and how to run it — is in
[05 — Testing](docs/dev/05-testing.md).

## Layout

```
plugin.json                        Agent Plugins 1.0.0 manifest
mcp.json                           stdio server and env contract
skills/                            five skills
agent-builder-exports/             six agent personas (reference format)
mcp/server.py                      composition root, registry, ping
mcp/core/                          contracts, models, errors, envelope, citations, config, cache
mcp/modules/fundamentals/          edgartools facts and statements
mcp/modules/analysis/              metrics and DCF
mcp/modules/reports/               filing index and sec-parser semantics
mcp/modules/thesis/                vault reader and index
mcp/modules/calendar/              reserved protocol
mcp/modules/price_action/          reserved protocol
docs/                              numbered user and developer guides
tests/                             unit, contract, integration
```

## License

valuebot is released under the **MIT License** — see [`LICENSE`](LICENSE).

```
MIT License

Copyright (c) 2026 Ram Kishore Arumugam
```

The Python packages valuebot depends on are **not** redistributed with it:
they are installed at runtime by `uv` from PyPI under their own licenses.
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) lists every direct and
transitive dependency with its license, and flags the copyleft ones
(`Unidecode` — GPL-2.0-or-later; `cssutils`, `encutils`, `frozendict` —
LGPL-3.0-or-later) that matter if you redistribute the environment.

| Package | License | Role |
|:---|:---|:---|
| [`mcp`](https://modelcontextprotocol.io) | MIT | Model Context Protocol SDK |
| [`edgartools`](https://github.com/dgunning/edgartools) | MIT | SEC identity, XBRL facts, statements |
| [`sec-parser`](https://github.com/alphanome-ai/sec-parser) | MIT | semantic filing HTML |
| [`beautifulsoup4`](https://www.crummy.com/software/BeautifulSoup/bs4/) | MIT | table grid extraction |
| [`lxml`](https://github.com/lxml/lxml) | BSD-3-Clause | HTML/XML backend |
| [`requests`](https://github.com/psf/requests) | Apache-2.0 | submissions JSON, filing HTML |
| [`pytest`](https://github.com/pytest-dev/pytest) | MIT | test suite (development only) |

## Disclaimer — not investment advice

**valuebot is a research and educational tool, not a financial adviser, broker,
dealer or registered investment adviser.** It is not a substitute for
professional financial, legal, accounting or tax advice, and it does not make
recommendations.

The data it returns is public filing data. The library that parses it
([sec-parser](https://github.com/alphanome-ai/sec-parser)) describes itself
the same way — it "utilizes public APIs and data provided by the SEC solely
for research, informational, and educational objectives. This tool is not
intended for financial advisement."

By using valuebot you acknowledge and accept the following.

**1. No advice, no recommendation, no solicitation.** valuebot produces
retrospective data and arithmetic. It does not advise you to buy, sell, hold
or refrain from any security, and it is not an offer or solicitation to do so.
Nothing it outputs — including any DCF value — is a price target or a
prediction of future price.

**2. The DCF is a model, not a valuation opinion.** `dcf_compute` returns the
arithmetic result of a simple FCFF discounted-cash-flow model under a stated
set of assumptions. WACC and terminal growth are **policy defaults chosen by
the project, not market observations** — they are labelled `default` in the
output precisely so that they are never mistaken for data. The result is
sensitive to those assumptions and to the quality of the filing-derived inputs;
it is an intrinsic value under one set of inputs, and nothing more. It is
never a target price and is never mixed with market prices by default.

**3. Data may be wrong, incomplete or out of date.** Figures are read from SEC
filings and are only as reliable as the issuer's own reporting, the
XBRL tagging of that filing, and the parsing of the document. Restatements,
amendments, XBRL tagging errors, and filings that have not yet been processed
all produce results that are wrong or stale. Every number valuebot returns
carries a citation so you can check it — **please check it.** A citation is a
pointer to the source, not a guarantee that the source says what the tool
claims it says.

**4. Past performance and historical facts are not predictive.** A ratio
computed from five years of filings says nothing about the next five.

**5. You are responsible for your own decisions.** Any decision you make in
reliance on valuebot's output is yours alone. valuebot is not liable for any
loss arising from such a decision, and you should consult a licensed
professional before acting.

**6. Not a complete picture.** valuebot deliberately omits price, market
capitalisation, technical analysis, analyst estimates, macro context, and
comparables across issuers. An analysis that ignores those dimensions is
incomplete by construction.

**7. No warranty.** valuebot is provided "AS IS", without warranty of any
kind, as stated in the MIT [license](LICENSE).

**8. Professional advice.** If you are unsure whether a figure means what you
think it means, or how it should inform a decision, consult a licensed
financial adviser.

## Contributing

Contributions are welcome. See
[CONTRIBUTING.md](https://github.com/valuewaffle/librechat-plugin/blob/main/CONTRIBUTING.md)
for the workflow, the development setup, and the invariants a change must not
break.

- [Roadmap](docs/roadmap.md) — what is planned and when
- [Contributing guide](docs/dev/10-contributing.md) — how to add a tool, metric
  or module without breaking the architecture
- [Code of Conduct](https://github.com/valuewaffle/librechat-plugin/blob/main/CODE_OF_CONDUCT.md)
- [Security policy](https://github.com/valuewaffle/librechat-plugin/blob/main/SECURITY.md)
- [Issue tracker](https://github.com/valuewaffle/valuebot/issues) ·
  [Discussions](https://github.com/valuewaffle/valuebot/discussions)
