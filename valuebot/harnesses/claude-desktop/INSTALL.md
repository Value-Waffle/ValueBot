# valuebot on Claude Desktop

This guide installs the valuebot stdio MCP server into the **Claude Desktop
app** (Anthropic). See the [harness overview](../README.md) for the canonical
launch contract and the
[multi-harness guide](../../docs/users/09-multi-harness.md) for cross-harness
details.

> **Not the same product as [Claude Code](../claude-code/INSTALL.md).** Claude
> Code is a terminal agent with plugins, skills and sub-agents. Claude Desktop
> is the chat app: it is an **MCP client only**. It runs the 19 MCP tools, but
> it does **not** load this repository's `skills/` folder or the six personas.
> See [What does not carry over](#what-does-not-carry-over).

> **Verification status.** Verified on macOS on 2026-10-31 against the real
> Claude Desktop config file: `./install.sh --harness claude-desktop` merged
> `mcpServers.vw-mcp` into an existing config without disturbing its other
> keys, and the installed `sh <PLUGIN_ROOT>/mcp/run.sh` command completed a
> full JSON-RPC handshake — 19 tools listed, `ping` reporting four `ready`
> modules, and the first spawn (no `uv` on `PATH`) building its venv in 22 s.
> The remaining step is client-side: Claude Desktop only reads this file at
> launch, so quit and relaunch the app, then confirm in
> `~/Library/Logs/Claude/mcp.log`.

## Option A — install the bundle (no JSON)

Valuebot ships an MCP Bundle (`.mcpb`, formerly DXT): a ZIP archive with the
server, its skills and a manifest that Claude Desktop can install by opening
the file. This route edits no JSON and asks for the SEC email on first launch.

> **Verification status.** The bundle manifest and build script are authored
> against the documented MCP Bundle schema, but the double-click install was
> **not** exercised against a running Claude Desktop. Treat Option A as
> unverified and fall back to [Option B](#option-b--manual-configuration),
> which is the verified path, if installation fails.

1. **Get the bundle.** Download `valuebot-<version>.mcpb` if one is published,
   or build it from this repository (requires `python3`, no `zip` binary):

   ```bash
   cd <PLUGIN_ROOT>/
   sh mcpb/build.sh            # writes dist/valuebot-<version>.mcpb
   # sh mcpb/build.sh --out DIR       # write somewhere else
   # sh mcpb/build.sh --dry-run       # list what would be packaged
   ```

2. **Open it with Claude Desktop.** Double-click the `.mcpb` file, or use
   **Claude → Settings → Extensions → Install extension** and pick the file.
   Review the requested configuration and confirm the install.

3. **Supply the SEC email.** The installer prompts for a single setting,
   *SEC contact email*. The SEC requires a real, reachable mailbox in the
   User-Agent for automated EDGAR access, so enter an address you actually
   read — placeholders are rejected at runtime. The value is passed to the
   server as `SEC_USER_AGENT`.

4. **Approve the tools.** Open a new chat and approve the valuebot tools (see
   [Approvals](#5-approvals)). Approving once is enough if you choose
   **Always allow**.

If the extension does not appear, or the tools never start, use Option B
below — it gives you the log file and the exact `env` block to inspect.

## Option B — manual configuration

### Prerequisites

Set `PLUGIN_ROOT` to the absolute path of this repository's `valuebot` folder
and choose a writable `PLUGIN_DATA` directory.

Claude Desktop does **not** expand `${VAR}` or `~`, so paste **absolute paths**
everywhere. It also does **not** run `command` through a shell — which is why
the launcher is written as `sh` plus the script path, exactly as in the launch
contract.

Run the one-time SEC identity setup from the plugin root:

```bash
cd <PLUGIN_ROOT>/
./setup.sh example-user@gmail.com
```

### Before you configure: the `uv` / PATH trap

Claude Desktop launched from Finder or the Start menu inherits a **minimal
`PATH`** — not your shell's. It may therefore not find `uv` in `~/.local/bin`
or `/opt/homebrew/bin`.

- `mcp/run.sh` falls back to a host-local venv when `uv` is missing, but that
  fallback still needs a Python 3.11+ interpreter it can reach. macOS's
  `/usr/bin/python3` stub is **3.9**, which is below the supported floor.
- So either install `uv` somewhere on the app's `PATH` (for example a symlink
  in `/usr/local/bin`), or point the config at an absolute interpreter path.

If the connector appears but the server never starts, check the log before
anything else — see [Troubleshooting](#troubleshooting).

## 1. Where the config lives

Claude Desktop keeps **one user-global** config file. Unlike Codex or Gemini
CLI there is no project-scoped variant: every chat in the app sees the same
servers.

| Platform | Path |
|:---|:---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Open it from inside the app: **Settings → Developer → Edit config** — that is
the exact label in the installed build (checked against the app bundle on
2026-10-31). It reveals the containing folder; create or edit
`claude_desktop_config.json` there.

## 2. Add the server

### Case 1: the file does not exist

Create `claude_desktop_config.json` with this minimal two-key configuration.
Replace `<PLUGIN_ROOT>` with the absolute path to the `valuebot` folder.

```json
{
  "mcpServers": {
    "vw-mcp": {
      "command": "sh",
      "args": ["<PLUGIN_ROOT>/mcp/run.sh"]
    }
  }
}
```

### Case 2: the file exists and already has `mcpServers`

The automated alternative is `./install.sh --harness claude-desktop` from the
`valuebot` directory. Otherwise, add `vw-mcp` as a sibling inside the existing
`mcpServers` object and touch nothing else. For example, change this:

```json
{"mcpServers": {"other-server": {"command": "other-command", "args": []}}}
```

to this (replace `<PLUGIN_ROOT>` with the absolute path to `valuebot`):

```json
{
  "mcpServers": {
    "other-server": {"command": "other-command", "args": []},
    "vw-mcp": {"command": "sh", "args": ["<PLUGIN_ROOT>/mcp/run.sh"]}
  }
}
```

### Case 2b: the file exists but has no `mcpServers`

**This is the normal state.** A freshly installed Claude Desktop that has never
had an MCP server writes a `claude_desktop_config.json` containing only
preferences — typically `preferences` and `coworkUserFilesPath` — and **no
`mcpServers` key at all**. Opening the file and finding nothing to add to is
expected, not a broken install, and `~/Library/Logs/Claude/mcp.log` will be
empty because no server has ever started.

`install.sh` handles this: when the top-level key is missing it creates an
empty object for it before inserting `vw-mcp`. Running
`./install.sh --harness claude-desktop` from the `valuebot` directory is the
safest route. To do it by hand, add a new `mcpServers` object **alongside** the
existing keys and change nothing else. For example, change this:

```json
{
  "preferences": {
    "menuBarEnabled": true
  },
  "coworkUserFilesPath": "/Users/you/Claude"
}
```

to this (replace `<PLUGIN_ROOT>` with the absolute path to `valuebot`):

```json
{
  "preferences": {
    "menuBarEnabled": true
  },
  "coworkUserFilesPath": "/Users/you/Claude",
  "mcpServers": {
    "vw-mcp": {"command": "sh", "args": ["<PLUGIN_ROOT>/mcp/run.sh"]}
  }
}
```

Your key names and values will differ — copy whatever is already in your file
verbatim and add only the `mcpServers` key and the trailing comma before it.
Nothing is deleted or reordered.

The `env` block is optional; every setting has a default. For custom paths or
limits, use the [canonical optional configuration](../../harnesses/README.md#minimal-configuration).

### The keys Claude Desktop accepts

| Key | Required | Notes |
|:---|:---|:---|
| `command` | **yes** | one executable, **not** run through a shell — use `"sh"` with the script in `args` |
| `args` | no | array of strings |
| `env` | no | object of strings; **no** `${VAR}` expansion, and no `~` |
| `type` | — | **do not add**; stdio is the only local transport |
| `cwd` | — | **not supported**; `run.sh` must find its own paths |

> ⚠️ **Merge, do not replace.** `claude_desktop_config.json` usually already
> holds unrelated keys (for example `preferences` and `coworkUserFilesPath`)
> and may already hold other MCP servers. Preserve every existing key: add
> `vw-mcp` inside an existing `mcpServers` object, or add the `mcpServers`
> object itself if it is absent — see the three cases above. Overwriting the
> whole file silently deletes the app's own settings and your other servers.

## 3. Restart the app properly

Current builds watch the file and start a newly added server within a few
seconds — observed on 2026-10-31, where the server began initializing 9 s after
the config was written, with no relaunch. If the tools do not appear, force a
full restart: closing the window is not enough on macOS or Windows, because the
app stays resident.

1. Quit completely: **Claude → Quit Claude** (macOS: `⌘Q`).
2. Relaunch the app.
3. Open a new chat and look for the **tools / connector** icon in the message
   composer. The `vw-mcp` server should be listed with 19 tools.

## 4. First call

Ask Claude, in a new chat:

> Use ping and tell me the module statuses.

Expect the standard health payload — four modules `ready`:

```json
{"ok": true, "module": "core", "tool": "ping",
 "data": {"server": "valuebot", "version": "0.2.0",
          "modules": {"fundamentals": {"status": "ready"},
                      "analysis": {"status": "ready"},
                      "reports": {"status": "ready"},
                      "thesis": {"status": "ready"}},
          "identity_configured": false}}
```

`identity_configured: false` means the SEC identity step has not been run yet.
Until it is, data tools return the expected
`{"ok": false, "error": {"code": "identity_not_configured", ...}}` envelope —
**that error means the wiring is correct**.

Then ask a real question:

> What was Apple's revenue, net margin and diluted share count for the last
> three fiscal years? Cite each number.

## 5. Approvals

Claude Desktop prompts before tool calls. In the installed build the prompt's
buttons are labelled **Allow once**, **Allow for this chat** and **Always
allow** (checked against the app bundle on 2026-10-31; a later release may
reword them, so read the labels the app shows rather than assuming these). The
valuebot evidence flow is read-only but calls several tools in sequence, so
approving each call one at a time interrupts the chain: pick **Allow for this
chat** where it is offered, or **Always allow** to stop being prompted.

If you trust the server, scope the broadest option to the `vw-mcp` tools only.
Do not broaden approval to unrelated tools.

## Optional: install a skill so Claude reaches for these tools

**A skill is not required to call a tool.** The 19 valuebot tools appear as
soon as the server starts, and asking a question is enough to invoke them —
nothing in the MCP protocol depends on a skill being installed.

What a skill changes is *selection*. Without one, the model decides on its own
which capability to use, and many desktop builds enable **web search** by
default — so "what was Apple's revenue in FY2024?" can be answered from a
search result instead of from `statement_get` or `report_section`. A skill is a
short description that tells the app *when* a set of instructions applies; the
app matches it against your request and loads those instructions, which name
the tools to use and how. Installing the citation and report-reading skills
therefore makes the model reach for the valuebot tools, and use their output
correctly, far more reliably.

### Build the `.skill` archives

A skill install takes a single skill, so `skills/build.sh` writes **one archive
per skill** (needs `python3`; no `zip` binary):

```bash
cd <PLUGIN_ROOT>/
sh skills/build.sh                 # writes dist/skills/<skill>.skill
sh skills/build.sh --out DIR       # write somewhere else
sh skills/build.sh --dry-run       # show each skill's name and description
```

Use the **`.skill`** extension, not `.zip`. The container is a ZIP, but
`.skill` is the extension the app ships its own bundled skills under — the
installed bundle lists `docx.skill` among its bundled skills — so building to
`.skill` matches the format the app expects.

Each archive contains one top-level directory named after the skill, with
`SKILL.md` inside it (`grounded-citation/SKILL.md`). That is the same shape as
the app's own bundled skills, which resolve to `skills/docx/SKILL.md` in the
installed bundle.

> An MCP bundle (`.mcpb`) cannot install skills. Option A above delivers the
tools only; skills are installed separately, as described here.

### Install the skills in the app

**Settings → Skills → Add skill → Upload skill**, then pick the `.skill` file.
The same menu offers **Create a skill** if you would rather paste the text in by
hand. Skills live in the app's own storage, so do not point the app at this
repository's `skills/` folder — it never reads it, and edits there do not
propagate into an installed skill.

A skill whose frontmatter `name` is already installed is rejected rather than
overwritten, so edit the installed copy or remove it first.

Install two skills first, not five:

| Skill | Why start with it |
|:---|:---|
| `grounded-citation` | It is the protocol for turning tool-issued citations into `[n]` markers and dropping claims with no citation. It is what makes a web-search answer distinguishable from a grounded one. |
| `semantic-report-reading` | It covers how to navigate a parsed 10-K/10-Q — stable section IDs, notes, tables, coverage degradation — so the model uses `filing_list` / `report_sections` / `report_section` / `report_table` instead of guessing at filing structure. |

Together they cover the two behaviours that most often go wrong in a fresh
install: citing sources, and reading a filing through the tools. Add
`ratio-analysis`, `dcf-valuation` and `hypothesis-analysis` later if you use
those workflows; without them quality degrades gracefully rather than
collapsing, because the tool descriptions carry the essentials.

## If Claude answers from the web instead of the tools

This is a tool-selection problem, not a broken install. If `ping` ever returned
four `ready` modules, the wiring is correct. In increasing order of effort:

1. Ask explicitly: “use the vw-mcp tools, not web search” or “call
  `symbol_resolve` then `facts_timeseries`.” Naming the tools makes the intended
  route clearer, but no single prompt is guaranteed to win every time.
2. Turn web search off for that chat or project, where the client allows it.
  The setting persists in the app's preferences.
3. Install the [`grounded-citation` skill](#optional-install-a-skill-so-claude-reaches-for-these-tools)
  so the trigger is automatic; a skill is not required to call a tool.

Finally, name a public company. “What is Apple's revenue?” maps to an issuer
tool; “Is Apple a good buy?” does not map to any valuebot tool.

## What does not carry over

Claude Desktop is an MCP client, not an agent harness. Several parts of this
repository are therefore **not** installed by this guide:

| Part | Status in Claude Desktop |
|:---|:---|
| The 19 MCP tools | ✅ Native — the whole point of this guide |
| The five `skills/` folders | ⚠️ Not read from disk: the app never reads this repository's `skills/` folder, and an MCP bundle cannot install skills. Skills *are* supported — install them under **Settings → Skills → Add skill → Upload skill**, one `.skill` archive each, built with `skills/build.sh`. See [Optional: install a skill](#optional-install-a-skill-so-claude-reaches-for-these-tools). |
| The six personas | ❌ No sub-agents. `vw-orchestrator` cannot dispatch specialists, and there is no citation audit gate. |
| The Agent Plugins 1.0 package | ⚠️ Not consumed from a folder; Claude Desktop has no "install from directory" flow. |

**Approximating a persona.** Create a **Project** in Claude Desktop, put the
persona body from [`../../agent-builder-exports/`](../../agent-builder-exports/)
into the project's **custom instructions**, and run every chat for that ticker
inside the project. This is a prompt, not an enforced role: nothing prevents
the model from skipping the audit gate.

The behaviour that genuinely matters — citation markers, ratio discipline, DCF
assumptions, evidence verdicts — is also carried by the MCP tool descriptions,
so quality degrades gracefully rather than collapsing.

## Additional info

- **Data root.** Point `PLUGIN_DATA` at the same directory your other harnesses
  use. Caches and downloaded filings are shared, so switching harness reuses
  work already done. See [Shared data root](../README.md#shared-data-root).
- **Tool identifiers.** Claude Desktop groups tools under the server name in
  its UI; the exact rendered prefix is a client detail and may vary by release.
  The tool *set* (19 tools) is what matters.
- **Packaging for others.** Anthropic's desktop extension bundle (`.mcpb`,
  formerly DXT) is the friendlier distribution route for a desktop-only
  audience. This repository builds one with `mcpb/build.sh` — see
  [Option A](#option-a--install-the-bundle-no-json). Its install flow is
  **UNVERIFIED** against a running Claude Desktop.
- **Paths, limits, thesis vault.** See
  [Configuration](../../docs/users/02-configuration.md).
- **Docker is not involved.** Unlike LibreChat, Claude Desktop runs on your
  machine, so `PLUGIN_DATA` is just a local folder — no volume mounts.

## Troubleshooting

| Symptom | Cause | Fix |
|:---|:---|:---|
| Claude answers from the web, not the tools | web search is enabled and the question reads as general knowledge | name the tool explicitly, or disable web search for the chat — see [the section above](#if-claude-answers-from-the-web-instead-of-the-tools) |
| Tool descriptions look outdated after I changed the code | Claude Desktop cached the older tool list from the running server | quit and relaunch the app so the server respawns and re-lists its tools |
| No `vw-mcp` tools in a chat | config not read: app not fully quit, or JSON invalid | `⌘Q` and relaunch; validate the JSON (a trailing comma breaks the whole file) |
| Other MCP servers disappeared | the config file was replaced instead of merged | restore from backup and add `vw-mcp` inside the existing `mcpServers` |
| Server listed but never starts | `uv`/`python3` not on the app's minimal `PATH` | see [the PATH trap](#before-you-configure-the-uv--path-trap) |
| `spawn` or path error | an unsubstituted `<PLUGIN_ROOT>` / `<PLUGIN_DATA>`, or a `~` path | paste absolute paths only |
| `identity_not_configured` | expected before setup | `./setup.sh example-user@gmail.com`, then quit and relaunch |
| Need to validate the installation | setup or runtime paths may be wrong | `./setup.sh --doctor` from the plugin root |
| A module reads `unavailable` | its dependency failed to import, or `EDGAR_LOCAL_DATA_DIR` is unwritable | read `error_code` in the same `ping` payload |
| Need the actual error text | MCP logs | macOS: `~/Library/Logs/Claude/mcp-server-vw-mcp.log` and `mcp.log`; Windows: `%APPDATA%\Claude\logs\` |

The canonical launch contract is in [`../README.md`](../README.md). For
cross-harness setup, see
[`../../docs/users/09-multi-harness.md`](../../docs/users/09-multi-harness.md).
