# valuebot on LibreChat

This guide installs the valuebot Agent Plugin (one stdio MCP server, five
skills, six agents) into LibreChat. See the [harness overview](../README.md)
for the canonical launch contract and the
[multi-harness guide](../../docs/users/09-multi-harness.md) for cross-harness
details.

> **This is the original target harness.** The general idea, the 19 tools, the
> launch contract, the one-time SEC identity, and the shared data root are all
> covered in the [user guide getting started](../../docs/users/01-getting-started.md).
> Read that first — this file only covers the LibreChat-specific steps.

> **No GUI installer or marketplace exists for LibreChat.** A plugin is
> discovered by placing a folder named `valuebot` inside the plugins directory,
> which is why this guide is a directory-and-volume procedure rather than a
> settings screen. `./install.sh` intentionally does not support LibreChat;
> use this directory procedure instead. If the folder is in place but tools do
> not appear, run `setup.sh --doctor` inside the plugin directory.

## Prerequisites

| Item | Check |
|:---|:---|
| LibreChat 0.8.8 or newer, running | `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3080/` → `200` |
| A writable plugins directory | LibreChat creates `${PLUGIN_DATA}` on boot |
| `uv` inside the LibreChat container | `docker exec LibreChat which uv` → `/usr/bin/uv` |
| A real contact email | SEC requires a User-Agent that identifies you |

LibreChat reads two environment variables for plugin support. The defaults are
usually correct:

| Variable | Default | Meaning |
|:---|:---|:---|
| `DEPLOYMENT_PLUGINS_DIR` | `plugin` (relative to `/app`) | where plugin folders live |
| `DEPLOYMENT_PLUGIN_DATA_DIR` | `data/plugins` | per-plugin writable data |

> **Most people can skip this table.** Both settings are read *inside* the
> LibreChat container, and the values shown are the ones LibreChat uses out of
> the box. You only need them if you deliberately want to keep plugins
> somewhere else. The rest of this guide uses the default paths — `/app/plugin`
> for plugins and `/app/data/plugins` for data. If your compose file changes
> them, use your values instead of the ones printed here.

`VW_THESIS_ROOT` defaults to `<PLUGIN_DATA>/theses`. The path
`/vw-data/theses` is correct only when your compose file actually mounts that
container path; otherwise use the default or an explicit path under your
mounted plugin data directory.

## 1. Put the plugin where LibreChat can find it

LibreChat looks for plugins in **one specific folder**. To install valuebot you
need a copy of the valuebot project inside that folder, and the copy's folder
name must be exactly `valuebot`.

> **Which of these is you?**
>
> | Your setup | Do this |
> |:---|:---|
> | LibreChat runs in Docker (the common case) | [1.1](#11-find-the-plugins-folder), [1.2](#12-get-the-files) and [1.3](#13-if-you-use-docker-share-the-folder-with-the-container) |
> | LibreChat runs directly on your computer | [1.1](#11-find-the-plugins-folder) and [1.2](#12-get-the-files) only |
>
> **Not sure?** Open a terminal and run `docker ps`. If the list shows a
> container named `LibreChat`, you are on Docker.

### 1.1 Find the plugins folder

Two folders are involved, and they are **not the same place**:

| | On your computer | Inside the container |
|:---|:---|:---|
| **Plugin folder** — valuebot's code lives here | `./plugin` | `/app/plugin` |
| **Data folder** — valuebot's saved settings and downloads live here | `./data/plugins` | `/app/data/plugins` |

Read the left-hand column like this: a folder called `plugin`, sitting next to
your `docker-compose.yml`, and a folder called `data` next to it. The
right-hand column is the same two folders, seen from inside the container.

**On your computer**, create the `plugin` folder if it is not already there.
Open a terminal in your LibreChat folder — the one that contains
`docker-compose.yml` — and run:

```bash
mkdir -p plugin
```

**Inside the container**, LibreChat reads the plugins folder from the setting
`DEPLOYMENT_PLUGINS_DIR` and the data folder from `DEPLOYMENT_PLUGIN_DATA_DIR`
(see [Prerequisites](#prerequisites)). The defaults are `/app/plugin` and
`/app/data/plugins`. You do not need to change them.

After this step your computer looks like this:

```
<your LibreChat folder>/
├── docker-compose.yml
├── docker-compose.override.yml
├── data/                       ← saved settings and downloaded filings
└── plugin/                     ← valuebot goes in here
    └── valuebot/
        ├── plugin.json
        ├── mcp.json
        ├── setup.sh
        └── ...
```

> **Why two folders?** The plugin folder holds *code* — you can replace it at
> any time, and you will replace it every time you upgrade valuebot. The data
> folder holds *your stuff* — the address you gave the SEC, and the filings
> already downloaded. Keeping them apart means an upgrade can never delete
> your setup.

### 1.2 Get the files

**Where to run this:** open a terminal in the `plugin` folder you just made.
The commands below assume you are standing in the folder that will *contain*
the new `valuebot` folder.

The project is published on GitHub at
<https://github.com/valuewaffle/valuebot>. You need it on the computer that
runs LibreChat.

**If you already have the files** — somebody sent you a ZIP, or you already
have the project folder — skip the download and just copy the whole `valuebot`
folder into the `plugin` folder.

**If you have Git installed**, run:

```bash
git clone https://github.com/valuewaffle/valuebot valuebot
```

Read that as: *"copy the project from GitHub into a new folder named
`valuebot`"*. The last word is the name of the new folder — keep it exactly
`valuebot`, otherwise LibreChat will not recognise the plugin.

**If you do not have Git**, download the project as a ZIP from
<https://github.com/valuewaffle/valuebot> (the **Code → Download ZIP** button),
unzip it, and rename the unzipped folder to `valuebot`.

Now make the setup script runnable:

```bash
chmod +x valuebot/setup.sh
```

`chmod +x` means *"give this file permission to be run"*. Without it, step 2
fails with "Permission denied".

When you are done, the `plugin` folder should look like this:

```
plugin/
└── valuebot/
    ├── plugin.json
    ├── mcp.json
    ├── setup.sh
    └── ...
```

### 1.3 If you use Docker: share the folder with the container

A Docker container cannot see the folders on your computer unless you explicitly
share them. A **volume** (also called a *mount*) is the Docker term for "this
folder on my computer is also a folder inside the container".

Open the file `docker-compose.override.yml` that sits next to your
`docker-compose.yml`, find the `api:` service, and add a `volumes:` section
under it containing this line:

```yaml
services:
  api:
    volumes:
      - ./plugin:/app/plugin
```

Read it as: *"the `plugin` folder next to this file is the same as the
`/app/plugin` folder inside the container"*.

> **Also keep the data folder mounted.** valuebot's saved settings live in
> `/app/data/plugins` inside the container. If your compose file already has a
> line like `- ./data:/app/data`, leave it alone — you are done. If it has
> none, add `- ./data:/app/data` under the same `volumes:` heading. Never
> mount the same container folder twice; Docker refuses to start.

> **Formatting:** if your file already has a `volumes:` section, add the line
> *inside* it rather than writing a second `volumes:` key. If it has none,
> add the `volumes:` heading and the entry below it, indented the same way as
> `environment:`.

Restart LibreChat for the change to take effect — see
[section 3](#3-restart-and-confirm-the-plugin-loaded).

## 2. Tell the SEC who you are (one time only)

**Why this is needed:** the SEC — the US regulator whose website hosts every
company filing — asks every program that downloads from it to include a
contact address, so they know who to email if something goes wrong. valuebot
has no built-in address and will not fetch any data until you give it one.

**What you need:** one real email address that you can receive mail at. It
does not have to be a work address.

**How long:** about 30 seconds, once per installation.

### 2.1 Run the setup

**If LibreChat runs in Docker** — copy the line below into a terminal, replace
`you@email.com` with your own address, and press Enter:

```bash
docker exec LibreChat sh -lc \
  'PLUGIN_DATA=/app/data/plugins/valuebot /app/plugin/valuebot/setup.sh you@email.com'
```

What each piece means:

| Piece | In plain words |
|:---|:---|
| `docker exec LibreChat` | run a command inside the LibreChat container that is already running |
| `sh -lc '…'` | run everything between the quotes as a single command |
| `PLUGIN_DATA=/app/data/plugins/valuebot` | "save the setup files in the *data* folder, not the *plugin* folder" — this is what makes your address survive plugin updates |
| `setup.sh you@email.com` | the setup script, with your address as its only input |

> If your setup uses different paths, replace `/app/plugin/valuebot` and
> `/app/data/plugins/valuebot` in the command with yours — see
> [Prerequisites](#prerequisites). If your container is not named `LibreChat`,
> replace that name too; `docker ps` shows the real one.

**If LibreChat runs directly on your computer** (no Docker), open a terminal
inside the `valuebot` folder and run this instead:

```bash
cd valuebot
PLUGIN_DATA=~/.valuebot ./setup.sh you@email.com
```

`~/.valuebot` means "a folder called `valuebot` in your home folder". It is
the data folder for a non-Docker install — the same job `/app/data/plugins`
does inside a container.

### 2.2 What you should see

```text
user agent saved to /app/data/plugins/valuebot/identity.json
User-Agent: valuebot you@email.com
restart LibreChat (or the MCP server) to pick it up
```

Line 1 means *your address was saved.* Line 2 shows the exact text that will
be sent to the SEC. Line 3 is only a reminder — the restart is the next
section.

### 2.3 Check it any time

If you use Docker:

```bash
docker exec LibreChat sh -lc \
  'PLUGIN_DATA=/app/data/plugins/valuebot /app/plugin/valuebot/setup.sh --show'
```

If you do not use Docker:

```bash
cd valuebot
PLUGIN_DATA=~/.valuebot ./setup.sh --show
```

It prints the address currently in use. If your address is printed, this
section is done.

### 2.4 If you want to change or remove the address later

Re-run the command from [2.1](#21-run-the-setup) with the new address — it
replaces the old one. To remove the address completely, run `setup.sh --reset`
with the same `PLUGIN_DATA=…` prefix.

> **Pick an address that can receive mail.** The SEC blocks some placeholder
> addresses, including anything ending in `@users.noreply.github.com`. If SEC
> answers with "403 Forbidden", run the setup again with a different address.
> See [Configuration](../../docs/users/02-configuration.md#sec-user-agent) for
> the full list of accepted and rejected addresses.

## 3. Restart and confirm the plugin loaded

If you use Docker:

```bash
docker restart LibreChat
docker logs --since 5m LibreChat 2>&1 | grep -E 'agentPlugins|\[MCP\]\[vw-mcp\]'
```

If you do not use Docker, restart LibreChat the way you normally start it
(`npm run backend` or `npm run frontend` from the LibreChat folder) and look
for the same lines in the LibreChat console window.

Expected:

```text
[agentPlugins] Loaded 1 plugin(s) from /app/plugin: 5 skill(s), 1 MCP server(s)
[MCP][vw-mcp] Tools: ping, symbol_resolve, company_profile, facts_query, ...
[MCP][vw-mcp] Initialized in: 1086ms
[MCP] Initialized with 1 configured server and 19 tools.
```

The first spawn also builds the Python environment at `${PLUGIN_DATA}/uv-env`;
that is the slow part (60–120 s). Later spawns reuse it.

## 4. First conversation

1. Open a new chat, choose a model that supports tool calling, and pick the
   `vw-mcp` server in the MCP picker (or use an agent from
   [Agents and skills](../../docs/users/04-agents-and-skills.md)).
2. Ask:

   > Use ping and tell me the module statuses.

   Expect four modules — `fundamentals`, `analysis`, `reports`, `thesis` — all
   `ready`, with `identity_configured: true` and `identity_source: file`.

3. Ask a real question:

   > What was Apple's revenue, net margin and diluted share count for the last
   > three fiscal years? Cite each number.

   Expect a table of values, each with an accession, form and period, plus a
   references list.

4. Sanity check the filing layer:

   > List Apple's last three 10-K filings and summarise Item 7 from the newest
   > one.

## 5. Install the agents (recommended)

The plugin ships five skills and six reference agents. Skills are part of the
plugin and load automatically; the agents are created once in Agent Builder.

See [Agents and skills](../../docs/users/04-agents-and-skills.md) and
[`agent-builder-exports/INSTALL.md`](../../agent-builder-exports/INSTALL.md).

## 6. Verification checklist

| Check | Expected |
|:---|:---|
| Plugin loaded | `5 skill(s), 1 MCP server(s)` in the log |
| Tool count | 19 tools including `ping` |
| `ping` | 4 modules `ready`, `identity_configured: true` |
| `symbol_resolve("AAPL")` | CIK 320193, name Apple Inc. |
| `filing_list("AAPL", forms=["10-K"])` | recent accessions, newest first |
| `ratio_compute("AAPL", ["roe"])` | numeric value plus citations |
| `dcf_compute("AAPL", assumptions_only=true)` | assumption table, WACC flagged `default` |

If any step fails, see
[Troubleshooting and FAQ](../../docs/users/08-troubleshooting-and-faq.md).

## Additional info

- **Deployment, volumes, upgrades:** see
  [LibreChat deployment](../../docs/users/06-librechat-deployment.md).
- **Paths, limits, thesis vault:** see
  [Configuration](../../docs/users/02-configuration.md).
- **Adding DeepSeek or OpenCode Zen models:** see
  [Model endpoints](../../docs/users/07-model-endpoints.md).
- **The six agents and five skills:** see
  [Agents and skills](../../docs/users/04-agents-and-skills.md).

## Troubleshooting

| Symptom | Cause | Fix |
|:---|:---|:---|
| Plugin not loaded | `plugin/` folder name is not exactly `valuebot`, or not mounted | rename to `valuebot`; check the `volumes:` mount in `docker-compose.override.yml` |
| `Permission denied` on `setup.sh` | script not executable | `chmod +x valuebot/setup.sh` |
| `identity_not_configured` | setup not run, or wrong `PLUGIN_DATA` | re-run `setup.sh you@email.com` with the same `PLUGIN_DATA` the server uses |
| `403 Forbidden` from SEC | blocked contact address | use a different real email; see [Configuration](../../docs/users/02-configuration.md#sec-user-agent) |
| Slow first spawn | env build at `${PLUGIN_DATA}/uv-env` | wait 60–120 s; later spawns reuse it |
| Tools do not appear after the folder is mounted | plugin path, data path, or runtime prerequisite is wrong | run `setup.sh --doctor` inside the `valuebot` plugin directory |
