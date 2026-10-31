# 07 — Model endpoints

Adding OpenAI-compatible providers (DeepSeek, OpenCode Go, OpenCode Zen) to a
self-hosted LibreChat. Verified against **LibreChat 0.8.x**, `librechat.yaml`
version **1.3.17**.

Ready-to-merge block: [`../../endpoints.example.yaml`](../../endpoints.example.yaml).

valuebot itself is model-agnostic — it only needs an endpoint that supports
**tool calling**. Everything below is optional infrastructure.

---

## 1. Get an API key

| Provider | Where | Env var | Base URL |
|:---------|:------|:--------|:---------|
| **DeepSeek** — official platform API | <https://platform.deepseek.com> → API keys | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` |
| **OpenCode Go** — paid model gateway | <https://opencode.ai> → Zen / billing | `OPENCODE_GO_API_KEY` | `https://opencode.ai/zen/go/v1` |
| **OpenCode Zen** — paid model gateway | <https://opencode.ai> → Zen / billing | `OPENCODE_API_KEY` | `https://opencode.ai/inference/v1` |

All three are bearer tokens. Do not commit them and do not paste them into
`librechat.yaml` — LibreChat interpolates `${VAR}` from its process
environment.

---

## 2. Provide the API keys — two options

LibreChat reads provider keys from its **process environment**. Pick either
route; both end up as the same environment variable.

### Option A — persisted in LibreChat's `.env`

In the LibreChat deployment directory (next to `docker-compose.yml`):

```dotenv
DEEPSEEK_API_KEY=sk-...
OPENCODE_GO_API_KEY=go_...
OPENCODE_API_KEY=oc_...
```

Restart the container after editing `.env`; the values are read at boot.

### Option B — passed from your shell at `up` time (nothing on disk)

Declare the variable in `docker-compose.override.yml` so Compose interpolates
it from the **shell that runs the command**:

```yaml
services:
  api:
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-}   # `:-` = empty default, no warning
      - OPENCODE_GO_API_KEY=${OPENCODE_GO_API_KEY:-}
      - OPENCODE_API_KEY=${OPENCODE_API_KEY:-}
```

Then start with the key exported in that shell:

```bash
cd ~/Library/LibreChat
export DEEPSEEK_API_KEY=sk-...        # must be EXPORTED, not just set
export OPENCODE_GO_API_KEY=go_...
# or prefix it for one command:  DEEPSEEK_API_KEY=sk-... docker compose up -d
docker compose up -d
```

Notes:

* The key lives only in the container's process environment — it is never
  written to `.env`, `librechat.yaml`, or the image.
* A variable that is set but **not exported** is invisible to Compose.
* Because the value is supplied at `up` time, any later `docker compose up -d`
  from a shell without the key will blank it. Keep a small `up.sh` wrapper that
  checks the variable and runs `exec docker compose up -d "$@"`.
* **Reloading:** LibreChat reads keys and `librechat.yaml` at boot. After a
  yaml-only edit, `docker compose restart api` is enough; `up -d` is a no-op
  when nothing else changed.

---

## 3. Merge into `librechat.yaml`

`librechat.yaml` lives in the LibreChat root and is mounted at
`/app/librechat.yaml`. **Merge** the `version`, `cache` and `endpoints`
sections — do not replace the file, or you will lose your other settings.

```yaml
version: 1.3.17
cache: true

endpoints:
  custom:
    - name: 'DeepSeek'
      apiKey: '${DEEPSEEK_API_KEY}'
      baseURL: 'https://api.deepseek.com/v1'
      models:
        default: ['deepseek-flash', 'deepseek-v4-pro']
        fetch: true           # live discovery; set false to pin the list below
        # Flash-only, no discovery:
        #   default: ['deepseek-flash']
        #   fetch: false
      titleConvo: true
      titleModel: 'deepseek-flash'
      dropParams: ['frequency_penalty', 'presence_penalty']
      modelDisplayLabel: 'DeepSeek'

    - name: 'OpenCode Go'
      apiKey: '${OPENCODE_GO_API_KEY}'
      baseURL: 'https://opencode.ai/zen/go/v1'
      models:
        default: ['deepseek-v4.1-flash', 'glm-5.3', 'kimi-k2.7-code', 'qwen3.8-max']
        fetch: false          # `/models` advertises non-chat ids too; pin the list
      titleConvo: true
      titleModel: 'deepseek-v4.1-flash'
      dropParams: ['frequency_penalty', 'presence_penalty']
      modelDisplayLabel: 'OpenCode Go'

    - name: 'OpenCode Zen'
      apiKey: '${OPENCODE_API_KEY}'
      baseURL: 'https://opencode.ai/inference/v1'
      models:
        default: ['deepseek-v4.1-flash', 'glm-5.3', 'kimi-k2.7-code', 'minimax-m3']
        fetch: true
      titleConvo: true
      titleModel: 'deepseek-v4.1-flash'
      modelDisplayLabel: 'OpenCode Zen'
```

Validate YAML before restarting:

```bash
python -c "import yaml,sys; yaml.safe_load(open('librechat.yaml')); print('ok')"
docker compose restart api
```

A malformed or schema-invalid `librechat.yaml` makes LibreChat log a config
error and fall back to defaults — if a provider does not appear, check the api
container logs first.

---

## 4. OpenCode Go

Base URL: `https://opencode.ai/zen/go/v1`. Chat completions:
`POST /zen/go/v1/chat/completions`. Key page: <https://opencode.ai> → Go /
billing.

### Catalogue

`GET https://opencode.ai/zen/go/v1/models` currently returns **37 ids** and
nothing else — no context length, pricing, or capability flags:

```
{"id": "deepseek-v4.1-flash", "object": "model", "created": 1792331442, "owned_by": "opencode"}
```

| # | Model id | # | Model id |
|:---:|:---|:---:|:---|
| 1 | `deepseek-v4.1-flash` | 20 | `mimo-v2.5` |
| 2 | `deepseek-v4-pro` | 21 | `mimo-v2.6-flash` |
| 3 | `glm-5.1` | 22 | `mimo-v2.5-pro` |
| 4 | `glm-5.2` | 23 | `mimo-v2.6-pro` |
| 5 | `glm-5.3` | 24 | `minimax-m2.5` |
| 6 | `grok-4.6` | 25 | `minimax-m2.7` |
| 7 | `grok-4.7` | 26 | `gemini-4-argon-contributor` |
| 8 | `muse-spark-1.2-contributor` | 27 | `minimax-m3` |
| 9 | `muse-spark-1.3-contributor` | 28 | `space-bunny` |
| 10 | `glm-5.3-flash` | 29 | `longcat-2.0` |
| 11 | `omen-alpha` | 30 | `longcat-2.5-preview-free` |
| 12 | `gpt-5.6-luna` | 31 | `step-5-preview` |
| 13 | `gpt-6-luna` | 32 | `beam-free` |
| 14 | `claude-haiku-5-5` | 33 | `qwen3.6-plus` |
| 15 | `hy3` | 34 | `qwen3.7-max` |
| 16 | `hy4-preview` | 35 | `qwen3.8-max` |
| 17 | `kimi-k2.6` | 36 | `qwen3.8-flash` |
| 18 | `kimi-k2.7-code` | 37 | `qwen3.7-plus` |
| 19 | `kimi-k3` | | |

### Which ids are safe on `/chat/completions`

The gateway serves different model families on different routes — the official
client uses `/chat/completions`, `/responses`, `/messages` (Anthropic format)
and `/google/v1beta` for the same key. A LibreChat **custom** endpoint only
speaks OpenAI chat completions, so:

| Keep in the picker | Avoid (wrong route) |
|:---|:---|
| `deepseek-*`, `glm-*`, `kimi-*`, `minimax-*`, `mimo-*`, `qwen*`, `grok-*`, `hy*`, `longcat-*`, `muse-*`, `omen-alpha`, `step-5-preview`, `beam-free`, `space-bunny` | `gpt-5.6-luna`, `gpt-6-luna`, `claude-haiku-5-5`, `gemini-4-argon-contributor` |

The curated `models.default` list in
[`../../endpoints.example.yaml`](../../endpoints.example.yaml) follows that
split. If you set `fetch: true`, LibreChat merges all 37 ids into the picker —
the four excluded ones will error on the first message.

### Why `fetch: false` here

| Reason | Detail |
|:---|:---|
| `/models` is unauthenticated and unfiltered | it lists every id, including non-chat routes |
| No metadata to filter on | no `context_length`, no pricing, no capability flags |
| Stable picker | a curated list is intentional and testable |
| Cheap titling | `titleModel: deepseek-v4.1-flash` keeps titles off the expensive models |

Set `fetch: true` only if you want automatic discovery and can tolerate broken
entries.

### Verifying the key

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  https://opencode.ai/zen/go/v1/models \
  -H "Authorization: Bearer $OPENCODE_GO_API_KEY"
```

`200` means the key is accepted. `401` with
`"code": "api_key_expired"` means the key in your secret store was revoked or
expired — create a new one in the OpenCode Console; signing in again does not
renew it.

> The `/models` route answers `200` even with an expired key. Always verify a
> key against `/chat/completions`, not `/models`.

---

## 5. Verify

1. Open the model picker: **DeepSeek** and **OpenCode Zen** should be listed
   as endpoint groups.
2. With `models.fetch: true`, the list is populated from the provider's
   `/models` route — a slow first load is normal.
3. Send a one-line prompt in each group. If the reply streams, the endpoint is
   wired correctly.
4. Check the API container log for `Included custom endpoint: DeepSeek` /
   `OpenCode Zen` at boot.

Quick standalone check with curl (isolates LibreChat from the equation):

```bash
# DeepSeek
curl -s https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" | head -c 400

# OpenCode Go (no auth needed for /models)
curl -s https://opencode.ai/zen/go/v1/models | head -c 400

# OpenCode Zen
curl -s https://opencode.ai/inference/v1/models \
  -H "Authorization: Bearer $OPENCODE_API_KEY" | head -c 400
```

---

## 6. Key settings explained

| Key | Meaning |
|:----|:--------|
| `baseURL` | Must be the **OpenAI-compatible** root. DeepSeek: `/v1`. OpenCode Zen: `/inference/v1`. |
| `models.default` | Fallback list shown when `fetch` is off or fails. Keep it short. |
| `models.fetch` | Query the provider's `/models` route for live discovery. |
| `titleConvo` / `titleModel` | Auto-name conversations using a cheap model instead of the expensive one. |
| `dropParams` | Strip parameters the provider rejects or ignores before sending. |
| `modelDisplayLabel` | Text shown in the UI for the endpoint group. |
| `headers` | Extra static headers; not needed for these two. |

---

## 7. Gotchas (learned the hard way)

| Symptom | Cause | Fix |
|:--------|:------|:----|
| Models list is empty, but chat works | `fetch: true` hit an unsupported `/models` route | Use `https://opencode.ai/inference/v1` (the `/inference/openai/v1` prefix has no `/models`) |
| 404 on every request | Wrong base path for the gateway | OpenCode Zen is `/inference/v1`; DeepSeek is `/v1` |
| 400 on DeepSeek "thinking" models | `tool_choice` forced, or penalties sent | Add `frequency_penalty` / `presence_penalty` to `dropParams` |
| `deepseek-chat` / `deepseek-reasoner` 404 | Those IDs were retired (2026-07-24) | Use `deepseek-flash`, `deepseek-v4-pro` (old alias `deepseek-v4-flash` still routes) |
| OpenCode Zen: GPT/Claude/Gemini models fail | Those live on `/responses`, `/anthropic/v1/messages`, `/google/v1beta` — not `/chat/completions` | Only pick the chat-completions models (DeepSeek, GLM, Kimi, MiniMax, Qwen, Mistral there) |
| `opencode serve` won't work as an endpoint | The CLI server is **not** OpenAI-compatible (it exposes `/session`, `/event`, no `/v1/chat/completions`) | Use OpenCode Zen, or a provider that speaks the OpenAI API |
| `curl` gets `403 Illegal request` and the IP is banned for ~2 h | LibreChat's non-browser User-Agent scoring (`BAN_VIOLATIONS` / `NON_BROWSER_VIOLATION_SCORE`) | Send a browser-like `User-Agent` for scripted tests; if you banned yourself, delete only your own test ban rows — do not disable the protection |
| Edited `librechat.yaml` but the endpoint did not change | The config is read once at boot | `docker compose restart api` (`up -d` is a no-op when nothing else changed) |
| Provider shows extra/expensive models you do not want | `models.fetch: true` merges live discovery into the picker | Set `models.fetch: false` and list only the models you want — the default list becomes authoritative |
| OpenCode Go: `401 api_key_expired` | the stored Go key was revoked; signing in again does not renew it | create a new key in the OpenCode Console and replace `OPENCODE_GO_API_KEY` |
| OpenCode Go: `/models` returns 200 but chat 401s | `/models` is unauthenticated | test the key against `/chat/completions` instead |
| OpenCode Go: `gpt-*`, `claude-*`, `gemini-*` fail | those ids need `/responses`, `/messages` or `/google/v1beta` | keep the curated chat-completions list (`fetch: false`) |
| `provider: 'anthropic'` silently ignored | Supported only from LibreChat **0.8.7+**; earlier versions strip the key | Upgrade, or use a native Anthropic endpoint instead of a custom one |

---

## 8. Using these with valuebot

valuebot is model-agnostic — it only needs an agent-capable endpoint that
supports **tool calling**. All three endpoints above qualify, so the six bundled
agents can run on any of them:

- **OpenCode Go** — widest catalogue and the cheapest Flash-class subagents
  (`deepseek-v4.1-flash`, `glm-5.3-flash`, `qwen3.8-flash`); `deepseek-v4-pro`
  or `qwen3.8-max` for the Orchestrator's final synthesis.
- **OpenCode Zen** — same families on a different route; useful as a fallback
  when a Go key or quota is exhausted.
- **DeepSeek** — cheapest path for the Fundamentals/Analysis/Reports subagents;
  use `deepseek-v4-pro` for the Orchestrator if you prefer one provider.

Because the Go catalogue exposes no pricing or context metadata, benchmark cost
and tool-calling reliability per model before assigning it to an agent. Models
that fail to emit tool calls will answer from memory instead of calling
`facts_query` — the `grounded-citation` skill will then correctly drop every
number, which looks like an empty answer.

Token-credit guardrails are separate from providers: configure `balance:` in
`librechat.yaml` so a runaway loop cannot bill either account without bound.

For model-to-role guidance inside valuebot, see
[Agents and skills](04-agents-and-skills.md#choosing-a-model).
