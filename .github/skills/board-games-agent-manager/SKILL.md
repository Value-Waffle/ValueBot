---
name: board-games-agent-manager
description: 'Manage Board Games agent users and API keys programmatically via MCP tools. Use when: creating new agents, generating API keys, rotating credentials, revoking access, bootstrapping agent infrastructure.'
argument-hint: '[create|rotate|revoke|list] [agent-name]'
user-invocable: true
disable-model-invocation: false
---

# Board Games Agent Manager

## When to Use
- **Creating a new agent** — onboarding an AI agent (analyst, coder, reviewer) that needs Board Games access
- **Rotating keys** — an agent's API key may have been compromised or needs regular rotation
- **Revoking access** — decommissioning an agent or terminating its access
- **Listing agents** — checking which agents exist and whether they have active keys
- **Bootstrapping a team** — setting up multiple agents for a new project

## What It Does
Programmatic user and API key lifecycle management for the Board Games project management tool. Enables AI orchestrators to bootstrap, rotate, and decommission agent identities without human copy-paste. All operations require a `system` or `admin` role API key.

## Prerequisites
- MCP server running with `BG_API_KEY` set to a key belonging to a `system` or `admin` user
- `bg_mcp/tools/user_tools.py` implemented and imported by the MCP server
- `board-games/config/agents.config.json` must be git-ignored and writable

## Procedure

### Bootstrap a New Agent
1. **Create the user** — call `create_user(name="AgentName", email="agent@example.com", role="user")`. Save the returned `user_id`.
2. **Generate the API key** — call `generate_api_key(user_id=N)`. Returns the raw key once. Do NOT log it.
3. **Persist the key** — call `save_agent_key(user_id=N, api_key="bga_...")`. Saves to `config/agents.config.json`.
4. **Configure the agent** — set `BG_API_KEY=bga_...` in the agent's environment and restart its MCP server.

### Rotate an API Key
1. **Generate a new key** — call `generate_api_key(user_id=N)`. This overwrites the old hash in the database immediately.
2. **Persist the new key** — call `save_agent_key(user_id=N, api_key="bga_new...")`.
3. **Update the agent** — set the new `BG_API_KEY` in the agent's environment and restart its MCP server.

### Decommission an Agent
1. **Revoke the key** — call `revoke_api_key(user_id=N)`. The old key stops working on the next MCP call.
2. **Remove from config** — delete the entry from `config/agents.config.json`.
3. **Disable the user (optional)** — set `is_active=0` via the admin console.

### Audit Existing Agents
1. **List all users** — call `list_users()`. Returns `[{id, name, email, role, api_key_prefix}, ...]`. A null `api_key_prefix` means no active key.
2. **Cross-reference config** — read `config/agents.config.json` and verify each user with a key prefix has a matching entry.

## Security Rules
1. **Never log raw API keys.** Pass the `generate_api_key` return value directly to `save_agent_key`. Do not echo it or include it in output.
2. **Keys are shown once.** If you forget `save_agent_key`, you must generate a new key (invalidating the lost one).
3. **`agents.config.json` is plaintext secrets.** Git-ignore it and `chmod 600`. It is the authoritative key registry on disk.
4. **Rotation invalidates immediately.** Generating a new key overwrites `api_key_hash` in the database — no grace period.
5. **Revocation is permanent.** `revoke_api_key` sets the hash to NULL. To restore access, generate a new key.
6. **Role validation is server-side.** The MCP server's `resolve_user()` rejects calls if your role is not `system` or `admin`.

## Troubleshooting
- **`PermissionError` on `create_user`**: Your `BG_API_KEY` belongs to a `user` or `super_user`. Use a `system` or `admin` key.
- **`PermissionError` on agent's first call**: The key wasn't persisted to `agents.config.json`. Regenerate and save.
- **Agent key works then stops**: Another process rotated or revoked the key. Run `list_users()` — a null prefix means revoked.
- **`FileNotFoundError` on `save_agent_key`**: The `board-games/config/` directory doesn't exist. Create it.
