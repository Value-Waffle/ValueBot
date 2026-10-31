# librechat-plugin

A workspace for building [LibreChat](https://librechat.ai) Agent Plugins that
give an AI assistant **grounded, citable data** instead of prose.

The plugin in this repository is **valuebot** — a financial research plugin
that answers questions about a company from SEC filings, and attaches the
filing reference to every number it returns.

> ### ⚠️ Educational use only — not investment advice
>
> valuebot is a **research and educational tool**. It is not a financial
> adviser, broker, dealer, or registered investment adviser, and it makes no
> recommendations. Nothing it produces — including any discounted cash flow
> value — is a price target or a prediction of future price.
>
> You are responsible for every decision you make. See the
> [full disclaimer](valuebot/README.md#disclaimer--not-investment-advice) and
> the [data usage restrictions](#data-usage-and-source-terms) below before you
> rely on anything it returns.

---

## Why this repository exists

Most AI assistants answer financial questions from their training data. That
data has a date, it was not written with a specific company in mind, and it
cannot be checked. When such an assistant tells you a company earned $94.9
billion last quarter, there is no way to find out whether that number is
right, which quarter it refers to, or whether it was restated.

valuebot exists to close that gap. It sits next to the model and does the
retrieval itself: it fetches the filing, parses it, computes the figure, and
hands the model a number **with its source attached**.

```
┌──────────────┐        ┌──────────────────────────────────┐
│              │  call  │  valuebot (MCP server)            │
│  LibreChat   │───────▶│  fetch filing → parse → compute  │
│  + a model   │        │  → return value + citation       │
│              │◀───────│                                  │
└──────────────┘  text  └──────────────────────────────────┘
                                  │
                                  ▼
                        SEC EDGAR (public filings)
```

The model still writes the prose. But the numbers in it now come from a
deterministic tool that can point at a filing, a form type, a date, and a
period.

## Who this is for

| You are… | Start here |
|:---|:---|
| A **developer** who wants to build a LibreChat plugin with grounded data | This page, then [the developer guide](valuebot/docs/dev/00-index.md) |
| A **user** who wants to install valuebot and ask better financial questions | [the user guide](valuebot/docs/users/00-index.md) |
| A **researcher** evaluating whether the output is trustworthy | [The citation contract](#the-citation-contract) below |
| A **contributor** who wants to add a tool or a model | [CONTRIBUTING.md](CONTRIBUTING.md) and the [roadmap](valuebot/docs/roadmap.md) |

You do not need to know Python to use valuebot. You do need a LibreChat
instance and one email address.

---

## What LibreChat is

[LibreChat](https://librechat.ai) is an open-source chat interface for LLMs.
It is a self-hosted web app — you run it on your own machine or server with
Docker — that gives a model a workspace: conversations, agents, files, tools
and integrations.

Two properties matter for this repository:

1. **You control the deployment.** Your chats, your data, your machine.
2. **It has a plugin system.** A plugin is a folder LibreChat loads at startup
   that gives the model new capabilities — which is the extension point
   valuebot uses.

LibreChat is not required to use valuebot's logic; it is the host that makes
the plugin loadable, discoverable, and usable by non-technical people.

## What a LibreChat plugin is

A plugin is **a directory on disk that LibreChat loads at startup**. Each
immediate subdirectory of the plugins folder is treated as one plugin.

Per the [Agent Plugins documentation](https://www.librechat.ai/docs/features/agent_plugins),
a plugin can bundle:

| Bundled item | What it does | In valuebot |
|:---|:---|:---|
| **Skills** | Instruction bundles the model loads when a task matches | 5 skills that teach citation discipline, ratio interpretation, DCF framing |
| **MCP servers** | Processes that expose tools the model can call | 1 server, `vw-mcp`, with 16 tools |
| **Command hooks** | Code that runs at agent lifecycle boundaries | None — deliberately not used |

valuebot is a plugin in that sense: a folder containing a `plugin.json`
manifest, an `mcp.json` that describes the server to launch, the server
itself, the skills, and the tests.

The model calls the server's tools over [MCP](https://www.librechat.ai/docs/features/mcp)
(Model Context Protocol) — a standard interface for exposing tools to a model.
The server runs as a separate process and speaks JSON-RPC over stdio. It is
launched by LibreChat, not by the model.

---

## What valuebot does

valuebot answers questions about **one company at a time**, from that
company's own SEC filings.

| Module | The question it answers | Example |
|:---|:---|:---|
| `fundamentals` | *What did the company report?* | revenue by fiscal year, diluted share count, total debt |
| `analysis` | *What do those numbers imply?* | ROE, revenue CAGR, free cash flow, discounted cash flow value |
| `reports` | *What did the filing actually say?* | Item 7 MD&A prose, Note 8 tables, risk factors |
| `thesis` | *What did I already write about it?* | your own research notes and annotations for that ticker |

Ask it a question and it returns an answer with references:

> **What was Apple's revenue, net margin and diluted share count for the last
> three fiscal years?**
>
> | Fiscal year | Revenue | Net margin | Diluted shares |
> |:---|---:|---:|---:|
> | 2025 | … | … | … |
> | 2024 | … | … | … |
> | 2023 | … | … | … |
>
> `[1]` 10-K, filed 2025-11-01, period ending 2025-09-27 — accession 0000320193-25-000079
> `[2]` 10-K, filed 2024-11-01, period ending 2024-09-28 — accession 0000320193-24-000065

### The citation contract

This is the feature that separates valuebot from an assistant that simply
knows things.

Every numeric claim leaves the server carrying a **citation**: the accession
number, the form type, the filing date, and the period it covers. Tables
carry the filing URL. A value that cannot be cited is either omitted or
returned with an explicit note saying so — it is never quietly presented as
fact.

That means you can always answer the question *"where did that number come
from?"*, and you can go read it yourself.

---

## How this differs from Claude's financial skills

Anthropic publishes financial skills for Claude, and markets a "Financial
Analysis Solution" alongside them. The two approaches are **complementary but
not equivalent** — and the difference is mostly about where the data comes
from.

| | Claude's financial skills | valuebot |
|:---|:---|:---|
| **What it is** | Instruction bundles (`SKILL.md`) plus scripts, e.g. in the public [claude-cookbooks](https://github.com/anthropics/claude-cookbooks) repository | A LibreChat plugin with its own MCP server, skills, and reference agents |
| **Where the numbers come from** | **You supply them** — via the [Financial Analysis Solution's](https://www.anthropic.com/news/claude-for-financial-services) connectors to market feeds and to internal platforms such as Databricks and Snowflake | **The plugin fetches them** from SEC EDGAR and parses the filings itself |
| **What you must already have** | A market-data subscription, or your own exports, plus a connector and credentials for each | One email address. No data licence, no warehouse, no connector |
| **Are the figures cited?** | Not intrinsically — the skill reasons over whatever you give it | Yes, by contract. Every number carries accession, form, date and period |
| **Market data, prices, consensus estimates** | Available, via the connected market feeds | **Not available.** valuebot has no price feed, no market cap, no analyst estimates, no news |
| **Where it runs** | Claude.ai, Claude Code, or the Anthropic API | Inside **your own** self-hosted LibreChat, against public filings |
| **Model** | Claude | **Any** tool-calling model — DeepSeek, OpenCode Zen, OpenAI, Anthropic, Qwen |

In short: **Claude's skills teach a model to analyse financial data you
already have; valuebot supplies the filings and proves where the numbers came
from.** If you have a licensed market data feed and want Claude's workflow
applied to it, the two are complementary. If you want SEC filing data with
verifiable provenance, and nothing else, valuebot is the thing that does it.

valuebot is also deliberately narrower. It does not claim to replace an
analyst, a data vendor, or a research platform. It is a filing-grounded
research aid.

---

## BYOK — bring your own key

**BYOK** means you use **your own** API keys for the model, instead of a
hosted plan's included credits. LibreChat calls this *"user provided"*: you
supply a provider key in the web UI at request time, and it is used for that
request.

Configure it under the **`user_provided`** key setting — see LibreChat's
[AI Endpoints configuration page](https://www.librechat.ai/docs/configuration/librechat_yaml/ai_endpoints),
which documents the `user_provided` value for both `librechat.yaml` and
`.env`:

````yaml
# librechat.yaml
endpoints:
  custom:
    - name: 'DeepSeek'
      apiKey: 'user_provided'
      baseURL: 'https://api.deepseek.com/v1'
      models:
        default: ['deepseek-v4-pro']
````

````dotenv
# .env
OPENAI_API_KEY=user_provided
````

**Why this matters for valuebot:** the plugin is model-agnostic. It needs an
endpoint that supports **tool calling**, and nothing else. BYOK is how you
point LibreChat at whichever provider you already pay for — DeepSeek, OpenAI,
Anthropic, or a gateway such as OpenCode Zen. No provider key is bundled with
valuebot, and valuebot never sees your model credentials.

For provider-specific setup — keys, base URLs, which model ids work on which
route — see [07 — Model endpoints](valuebot/docs/users/07-model-endpoints.md).

---

## Data usage and source terms

valuebot reads **public SEC filings**. It does not redistribute them, and it
does not let you request arbitrary URLs — every tool addresses SEC endpoints
by issuer. But the data has rules, and so do the libraries that fetch it.

### SEC EDGAR

The SEC publishes filings for free and asks every automated client to
identify itself and to stay within a rate limit. Per the
[SEC's "Accessing EDGAR Data" page](https://www.sec.gov/os/accessing-edgar-data):

> "Please declare your user agent in request headers" — a company name and a
> contact email address.

> "Current max request rate: 10 requests/second."

The SEC also states that it "reserves the right to limit request rates to
preserve fair access for all users", and that requests identified as part of
a botnet or as an automated tool outside the acceptable policy "will be
managed to ensure fair access for all users". The governing policy is the
[SEC Internet Security Policy](https://www.sec.gov/about/privacy-information#security).

**valuebot's compliance:**

| Requirement | How valuebot meets it |
|:---|:---|
| Declare a User-Agent with a contact address | A one-time setup writes `identity.json`; every request carries `User-Agent: valuebot <email>` |
| Stay under 10 requests/second | `EDGAR_RATE_LIMIT_PER_SEC` defaults to `5` — deliberately under the cap |
| Identify yourself, do not crawl | The plugin fetches a defined set of SEC endpoints for one issuer at a time |
| Do not redistribute the data | Filings are cached locally under `${PLUGIN_DATA}` for your own use; they are never republished |

**If you use the plugin, these obligations are yours too.** Give it a real
mailbox you can receive mail at, and do not raise the rate limit above the
SEC's cap. The [SEC's terms](https://www.sec.gov/os/accessing-edgar-data) and
the [Internet Security Policy](https://www.sec.gov/about/privacy-information#security)
apply to you as the operator.

### The libraries that fetch the data

| Library | License | What it does here | Terms that come with it |
|:---|:---|:---|:---|
| [edgartools](https://github.com/dgunning/edgartools) | MIT | Company resolution, XBRL facts, statements | Carries the SEC's identity requirement: `set_identity()` sets the `EDGAR_IDENTITY` User-Agent, and the library points at the [SEC's access policy](https://www.sec.gov/os/accessing-edgar-data). `EDGAR_RATE_LIMIT_PER_SEC` and `EDGAR_HTTP_TIMEOUT` are the controls it exposes. |
| [sec-parser](https://github.com/alphanome-ai/sec-parser) | MIT | Parses SEC filing HTML into semantic sections, notes and tables | Carries its own disclaimer, which valuebot adopts: sec-parser is "an independent, open-source initiative and has no affiliation, endorsement, or verification by the United States Securities and Exchange Commission (SEC). It utilizes public APIs and data provided by the SEC solely for research, informational, and educational objectives. This tool is not intended for financial advisement." |

Both are MIT-licensed and carry no separate commercial-use restriction. The
full dependency inventory, with every transitive package and its license, is
in [valuebot/THIRD-PARTY-NOTICES.md](valuebot/THIRD-PARTY-NOTICES.md).

### Your thesis vault

valuebot can read a folder of **your own** research notes. It never writes to
it, and it is the only data in the system that cannot be re-downloaded. If you
put confidential material there, treat it as confidential — the plugin has no
encryption and no access control of its own.

---

## Documentation

| Guide | For |
|:---|:---|
| [valuebot/docs/users/](valuebot/docs/users/00-index.md) | **User guide** — install, configure, and use the plugin |
| [valuebot/docs/dev/](valuebot/docs/dev/00-index.md) | **Developer guide** — architecture, module contracts, testing |
| [valuebot/docs/roadmap.md](valuebot/docs/roadmap.md) | **Roadmap** — what is being built and when |
| [architecture/](architecture/INDEX.md) | **Architecture** — design rationale and data mapping |
| [CONTRIBUTING.md](CONTRIBUTING.md) | **Contributing** — how to add a tool, metric, or module |

New to valuebot? Start with
[01 — Getting started](valuebot/docs/users/01-getting-started.md).

## What is in this repository

| Path | What it holds |
|:---|:---|
| [`valuebot/`](valuebot/) | The distributable plugin — manifests, MCP server, skills, agents, tests, and its own documentation |
| [`architecture/`](architecture/) | Design documents: the system map, data mapping, and the valuebot v2 design and implementation plan |
| [`wiki/`](wiki/) | Project wiki (git submodule → [ValueBot.wiki](https://github.com/Value-Waffle/ValueBot.wiki.git)): overview, install, configuration, troubleshooting, feature and module reference, platform guides, and developer docs |
| [`.github/`](.github/) | Repository automation, issue and pull request templates, and the agent and skill library used to work on this codebase |
| [`RELEASING.md`](RELEASING.md) | How to cut a release (version bump, tag, publish) |
| [`CHANGELOG.md`](CHANGELOG.md) | Notable changes per release |

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first — it
covers the setup, the invariants a change must not break, and what a reviewer
checks. The [roadmap](valuebot/docs/roadmap.md) shows what is already planned,
so you can pick something that is scoped.

- [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Security policy](SECURITY.md)
- [Issues](https://github.com/valuewaffle/valuebot/issues) · [Discussions](https://github.com/valuewaffle/valuebot/discussions)

## License

This repository and valuebot are licensed under the **MIT License** — see
[LICENSE](LICENSE) and [valuebot/LICENSE](valuebot/LICENSE).

valuebot's Python dependencies are installed at runtime and are **not**
redistributed with it. Their licenses are listed in
[valuebot/THIRD-PARTY-NOTICES.md](valuebot/THIRD-PARTY-NOTICES.md), along with
the copyleft dependencies that matter if you redistribute the environment.
