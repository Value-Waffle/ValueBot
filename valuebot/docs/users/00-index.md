# valuebot user guide

Everything needed to install valuebot, configure it once, and use it from
LibreChat. No Python knowledge is required; commands are copy-paste.

## What valuebot does

valuebot answers financial questions from primary sources instead of prose:

| Module | Answers | Example |
|:---|:---|:---|
| `fundamentals` | What did the company report? | revenue by fiscal year, diluted shares, total debt |
| `analysis` | What do those numbers imply? | ROE, revenue CAGR, free cash flow, DCF value |
| `reports` | What did the filing say? | Item 7 MD&A text, Note 8 tables, risk factors |
| `thesis` | What did I already write? | my thesis notes and annotations for this ticker |

Every numeric claim carries a citation to the accession, form, filing date and
period it came from. Tables carry the filing URL.

## Reading order

| # | Document | Read when |
|:---|:---|:---|
| 01 | [Getting started](01-getting-started.md) | first install; `install.sh` and `setup.sh --doctor` |
| 02 | [Configuration](02-configuration.md) | setting the SEC identity, paths, limits |
| 03 | [Tools reference](03-tools-reference.md) | you need a tool's arguments or return shape |
| 04 | [Agents and skills](04-agents-and-skills.md) | setting up the six agents |
| 05 | [Research workflows](05-research-workflows.md) | you want proven prompt patterns |
| 06 | [LibreChat deployment](06-librechat-deployment.md) | Docker, volumes, upgrades |
| 07 | [Model endpoints](07-model-endpoints.md) | adding DeepSeek or OpenCode Zen |
| 08 | [Troubleshooting and FAQ](08-troubleshooting-and-faq.md) | something failed |
| — | [Roadmap](../roadmap.md) | what is being built and when |

## Requirements at a glance

| Requirement | Version | Notes |
|:---|:---|:---|
| LibreChat | 0.8.8+ | Agent Plugins schema 1.0.0 |
| A tool-calling model | any | DeepSeek, OpenCode Zen, OpenAI, Anthropic |
| Python (managed by LibreChat) | 3.11–3.13 | 3.12 recommended; `uv` builds it |
| A contact email | — | one-time SEC User-Agent setup |

The installer supports the five local harnesses listed in the getting-started
guide. Run `./install.sh --harness <name>` when applicable, then use
`./setup.sh --doctor` to check the setup before entering your SEC email.

You do **not** install Python packages yourself. LibreChat starts the server
with `uv run` and builds the environment inside `${PLUGIN_DATA}`.

## What valuebot is not

- Not a price feed. There is no share price, market cap or technical analysis;
  `price_action` is reserved and disabled.
- Not a screener. It works one issuer at a time.
- Not investment advice. DCF output is an intrinsic-value calculation from your
  assumptions, not a price target. The full disclaimer is in the
  [plugin README](../../README.md#disclaimer--not-investment-advice).
- Not a web search. Evidence comes from SEC filings and your own vault.

## Choose your harness

valuebot runs on any harness that supports stdio MCP. The
[Getting started](01-getting-started.md) guide is harness-agnostic: it covers
what valuebot does, the common prerequisites, the launch contract, the one-time
SEC identity, the shared data root, and a verification checklist that apply to
every harness.

Once you have read it, pick your harness — each install guide covers
installation through additional info for that harness:

| Harness | Status | Install guide |
|:---|:---|:---|
| LibreChat | ✅ Shipped | [LibreChat](../../harnesses/librechat/INSTALL.md) |
| Claude Code | ✅ Supported | [Claude Code](../../harnesses/claude-code/INSTALL.md) |
| Claude Desktop (app) | ✅ Supported | [Claude Desktop](../../harnesses/claude-desktop/INSTALL.md) |
| OpenAI Codex CLI | ✅ Supported | [Codex CLI](../../harnesses/codex/INSTALL.md) |
| GitHub Copilot (VS Code) | ✅ Supported | [Copilot](../../harnesses/copilot/INSTALL.md) |
| ChatGPT (Desktop & web) | 🔌 Needs public HTTPS tunnel | [ChatGPT](../../harnesses/chatgpt/INSTALL.md) |
| DeepSeek Harness (`dsh`) | 🚧 Developer preview | [DeepSeek](../../harnesses/deepseek/INSTALL.md) |
| Gemini CLI | ✅ Supported | [Gemini CLI](../../harnesses/gemini-cli/INSTALL.md) |
| Hermes Agent | ✅ Supported | [Hermes](../../harnesses/hermes/INSTALL.md) |
| OpenCode | ✅ Supported | [OpenCode](../../harnesses/opencode/INSTALL.md) |
| Open WebUI | 🔌 Needs `mcpo` bridge | [Open WebUI](../../harnesses/openwebui/INSTALL.md) |
| Pi (`pi.dev`) | ✅ Supported | [Pi](../../harnesses/pi-agent/INSTALL.md) |

The canonical launch contract and cross-harness details are in the
[harness overview](../../harnesses/README.md) and the
[multi-harness guide](09-multi-harness.md).

## Coming next

The [roadmap](../roadmap.md) lists what is being built and when — valuation
models in December 2026, deeper report parsing in March 2027, and news in
June 2027.
