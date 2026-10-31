# valuebot on Gemini CLI

This guide installs the valuebot stdio MCP server, five shared skills, and six Gemini CLI custom commands that approximate the valuebot personas. See the [harness overview](../README.md) for the canonical launch contract and the [multi-harness guide](../../docs/users/09-multi-harness.md) for cross-harness details.

> **Two things to know before you start.**
> 1. **The model choice is constrained.** Gemini CLI authenticates only through Google sign-in / Code Assist, a Gemini API key, or Vertex AI. There is **NO documented OpenAI-compatible provider**, so **DeepSeek models CANNOT back Gemini CLI** — unlike every other harness in this folder. valuebot itself still works here; only the model you drive it with is constrained to Gemini.
> 2. **Environment inheritance is redacted.** Variables are expanded *only* inside the `env` block, and inherited base-environment names matching `KEY|TOKEN|SECRET|PASSWORD|AUTH|CREDENTIAL` are stripped. All 13 valuebot variables must therefore be listed **explicitly** in `env`. Never rely on inheritance — see [Environment variables](#environment-variables-list-all-13-explicitly).

## Prerequisites

Set `PLUGIN_ROOT` to the absolute path of the plugin repository and choose a writable `PLUGIN_DATA` directory. Gemini CLI does **not** reliably expand `~` in these paths — `~` expansion is **UNVERIFIED** — so paste absolute paths everywhere.

Run the one-time SEC identity setup from the plugin root:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

## Before you configure

`run.sh` is the portable launcher: it uses `uv` when installed and otherwise builds a venv at `$PLUGIN_DATA/venv` (about 26 s on a first run). A restricted network needs `uv` installed first because the fallback installs from a package index.

## Guided install

Run the Gemini CLI guided command from the plugin root (replace the paths):

```bash
gemini mcp add vw-mcp sh <PLUGIN_ROOT>/mcp/run.sh \
  --env EDGAR_LOCAL_DATA_DIR=<PLUGIN_DATA>/edgar \
  --env EDGAR_RATE_LIMIT_PER_SEC=5 --env EDGAR_HTTP_TIMEOUT=30 \
  --env VW_MAX_HTML_MB=40 --env VW_MAX_FACTS_COMPANIES=100 \
  --env VW_ENABLE_PRICE=0 --env VW_ARTIFACT_HTTP_PORT=0 \
  --env VW_ARTIFACT_HTTP_HOST=127.0.0.1 --env VW_ARTIFACT_PUBLIC_BASE_URL= \
  --env UV_PROJECT_ENVIRONMENT=<PLUGIN_DATA>/uv-env \
  --env UV_CACHE_DIR=<PLUGIN_DATA>/uv-cache \
  --env UV_PYTHON_INSTALL_DIR=<PLUGIN_DATA>/uv-python
```

This writes the same `settings.json` that the following reference section
shows. The environment flags may be omitted because every variable has a
default.

## Where the config lives

| Scope | File |
|:---|:---|
| User | `~/.gemini/settings.json` |
| Project | `.gemini/settings.json` (relative to the project root) |

Both files are plain JSON with an `mcpServers` object. Project scope takes effect when you work inside that project.

## User `settings.json`

Create or edit `~/.gemini/settings.json`. Replace `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` with absolute paths.

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
      },
      "cwd": "<PLUGIN_ROOT>/mcp",
      "timeout": 600000,
      "trust": false
    }
  }
}
```

### Schema: `command` is a string, `args` is a separate array

This is the opposite of [OpenCode](../opencode/INSTALL.md), which merges the executable and its arguments into one `command` array and uses `environment` instead of `env`. Do not mix the two shapes. Here:

| Key | Required | Values | Notes |
|:---|:---|:---|:---|
| `command` | yes | **string** | The executable only: `"sh"`. Not an array. |
| `args` | no | array of strings | The arguments, separate: `["<PLUGIN_ROOT>/mcp/run.sh"]`. |
| `env` | no | object of strings | Not `environment`. See the expansion rule below. |
| `cwd` | no | string | Working directory for the spawned process. |
| `timeout` | no | integer, **milliseconds** | Documented default `600000` (10 minutes). |
| `trust` | no | **boolean only** | Default `false`. `true` bypasses **all** tool confirmations. |
| `includeTools` | no | array of strings | Allowlist of tools to expose. |
| `excludeTools` | no | array of strings | Denylist of tools to hide. |

### `timeout` is milliseconds

`timeout` is an integer in **milliseconds**, default `600000`. Do not paste seconds (`600`) or a human string (`"10m"`) — nothing validates that for you. The 10-minute default already absorbs a ~26 s cold venv build; only raise it if your package index is slow.

### `trust` is a boolean, and `true` is a security decision

`trust` accepts `true` or `false` and nothing else — there is no `"prompt"`, `"auto"`, or per-tool map. `false` (the documented default) asks before tool calls. `true` **bypasses all tool confirmations** for that server, including the ones that write to disk.

Set `trust: false` unless you have deliberately decided otherwise. Do not copy `true` from a snippet just to stop the prompts; if the prompts are the problem, use `--approval-mode` or an `includeTools` allowlist instead.

## Environment variables: list all 13 explicitly

The rule, stated precisely:

- `$VAR` and `${VAR}` are expanded **only inside the `env` block**. They are not expanded in `command`, `args`, `cwd`, or anywhere else.
- An **undefined** variable expands to an **empty string** — silently, with no warning.
- The **inherited base environment is redacted**: names matching `KEY|TOKEN|SECRET|PASSWORD|AUTH|CREDENTIAL` are removed before the server is launched.

Because all 13 valuebot variables must actually reach the server, **list every one of them in `env` explicitly**. Never rely on the parent shell's environment, and never assume a variable you exported will be visible. Note that `VW_ARTIFACT_PUBLIC_BASE_URL` is intentionally empty — an empty string is a valid value, so an accidentally-undefined variable looks identical to this one.

## Project `settings.json`

For a project-scoped setup, put the same `mcpServers` object in `.gemini/settings.json` at the project root. Use absolute paths there too, for the same `~` reason. Keeping the server project-scoped is convenient when several people share a checkout; keeping it user-scoped is convenient when one machine serves many projects.

## Skills

Gemini CLI consumes the Agent Skills standard and discovers skills in three places:

| Scope | Path |
|:---|:---|
| User | `~/.gemini/skills/` |
| Project | `.gemini/skills/` |
| Project (shared) | `.agents/skills/` |

Copy all five, without editing them:

```bash
mkdir -p .gemini/skills
cp -R <PLUGIN_ROOT>/skills/grounded-citation .gemini/skills/
cp -R <PLUGIN_ROOT>/skills/hypothesis-analysis .gemini/skills/
cp -R <PLUGIN_ROOT>/skills/ratio-analysis .gemini/skills/
cp -R <PLUGIN_ROOT>/skills/dcf-valuation .gemini/skills/
cp -R <PLUGIN_ROOT>/skills/semantic-report-reading .gemini/skills/
```

For user-wide availability, copy them into `~/.gemini/skills/` instead. `.agents/skills/` is the right choice when you want the same files visible to Codex and other Agent Skills harnesses.

**Skills are not auto-loaded.** They are activated through an `activate_skill` tool that prompts you for consent before the skill's instructions take effect. Expect a consent prompt the first time you invoke each one, and do not be surprised when a fresh session has no skill instructions in context until you activate it.

## Personas as custom commands

Gemini CLI has **no sub-agent file format**. The six valuebot personas are therefore approximated as custom commands — one TOML file per persona — under `~/.gemini/commands/` (user) or `.gemini/commands/` (project). A subdirectory becomes a namespace: `commands/vw/audit.toml` is invoked as `/vw:audit`.

Each file requires a `prompt` key; `description` is optional. `{{args}}` is replaced with whatever follows the command.

```toml
description = "Plan evidence, dispatch specialists, run the citation audit gate"
prompt = """
You are vw-orchestrator. Plan the evidence needed for this request, dispatch
the specialist roles, and refuse to return an answer whose claims are not
grounded in valuebot tool output. Activate the grounded-citation skill first.

Request: {{args}}
"""
```

Create the remaining five the same way, using the instructions from the canonical exports in [`../../agent-builder-exports/`](../../agent-builder-exports/) or the markdown personas in a sibling harness folder:

| Command | Persona | Scope |
|:---|:---|:---|
| `/vw-orchestrator` | `vw-orchestrator` | plans evidence, dispatches specialists, runs the audit gate |
| `/vw-fundamentals-analyst` | `vw-fundamentals-analyst` | XBRL facts, identity, statements |
| `/vw-analysis-analyst` | `vw-analysis-analyst` | ratios, growth, DCF |
| `/vw-reports-analyst` | `vw-reports-analyst` | filing sections, notes, tables |
| `/vw-thesis-analyst` | `vw-thesis-analyst` | tests the user's thesis against evidence |
| `/vw-citation-auditor` | `vw-citation-auditor` | grounding gate; approves or rejects |

After adding or editing a command file, run `/commands reload` inside Gemini CLI. Command files are read at startup and on reload, not on every keystroke.

## `GEMINI.md` for persistent context

Custom commands are invoked on demand. For context that should always be present — the launch contract, the 13 variables, the "no claim without a citation" rule — add a `GEMINI.md` at the project root (or `~/.gemini/GEMINI.md` for user scope). Keep it short: it is loaded into every session.

## Approvals

| Flag | Effect |
|:---|:---|
| `--approval-mode default` | Prompt before tool calls (safest). |
| `--approval-mode auto_edit` | Auto-approve edits; still prompt for other tools. |
| `--approval-mode yolo` | Auto-approve everything. Equivalent to `--yolo`. |
| `--approval-mode plan` | Read-only planning; no mutating tools. |
| `--yolo` | Shorthand for `--approval-mode yolo`. |
| `--allowed-tools` | Restrict which tools may run at all. |

For valuebot research the evidence flow is read-only, so `--approval-mode plan` or an `--allowed-tools` allowlist covering the 19 tools gives a smooth run without the blanket risk of `yolo`. Remember that a server-level `trust: true` bypasses confirmations regardless of the approval mode you pass.

Add `--debug` when something does not work; it prints the MCP handshake, spawn errors and tool registration. `/mcp` inside a session lists the configured servers and their connection status.

## Verify it worked

Start Gemini CLI with `--debug` and run `/mcp`. `vw-mcp` should be listed as connected with 19 tools (core 3, fundamentals 6, analysis 3, reports 5, thesis 2). Then ask for the health check:

```text
Call valuebot ping.
```

```json
{"ok": true, "module": "core", "tool": "ping",
 "data": {"server": "valuebot", "version": "0.2.0",
          "modules": {"fundamentals": {"status": "ready"},
                      "analysis": {"status": "ready"},
                      "reports": {"status": "ready"},
                      "thesis": {"status": "ready"}},
          "identity_configured": false}}
```

All four modules must read `ready`. A module showing `unavailable` carries `error` and `error_code` in the same payload. If `identity_configured` is `false`, the data tools return `identity_not_configured` — that means the wiring is correct and only the SEC identity step is missing.

If `ping` is not in the tool list at all, the server never spawned: check that every `<PLUGIN_ROOT>` and `<PLUGIN_DATA>` placeholder was replaced, that `sh <PLUGIN_ROOT>/mcp/run.sh` starts on its own, and that all 13 variables are present in `env`.

## Troubleshooting

- **Server not listed under `/mcp`**: the JSON did not parse or the entry is malformed. `command` must be a string and `args` an array; a merged `command: ["sh", "..."]` array is the OpenCode shape and silently fails here.
- **`spawn sh ENOENT` or a path error**: unsubstituted `<PLUGIN_ROOT>`. `~` expansion is unverified — use absolute paths.
- **Empty-string settings inside the server**: a variable was omitted from `env` and inherited nothing. List all 13 explicitly; redaction of `KEY|TOKEN|SECRET|PASSWORD|AUTH|CREDENTIAL` names and empty-string expansion both fail silently.
- **Every tool call prompts for confirmation**: `trust` is `false`. That is the safe default. Prefer `--approval-mode plan` / `--allowed-tools`, and only set `trust: true` as a deliberate decision.
- **Timeouts on a first run**: `timeout` is in milliseconds; the default `600000` is usually enough. Confirm it was not written as seconds.
- **Skills never take effect**: they require `activate_skill` consent and are not auto-loaded. Activate the skill at the start of the session.
- **A command file is ignored**: it needs a `prompt` key, must live in `.gemini/commands/` or `~/.gemini/commands/`, and needs `/commands reload` after edits.
- **`symbol_resolve` fails**: it takes `query`, not `symbol`.
- **Need to validate the installation**: run `./setup.sh --doctor` from the plugin root.

See the [canonical harness README](../README.md), [`valuebot/mcp.json`](../../mcp.json), and the [multi-harness guide](../../docs/users/09-multi-harness.md) for shared details.
