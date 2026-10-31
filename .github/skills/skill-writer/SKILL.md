---
name: skill-writer
description: 'Write SKILL.md files for agents. Covers format spec, guard rails, and adaptation across harnesses (VS Code, Claude Code, Cline) and models. Use when writing, reviewing, or converting a skill file.'
user-invocable: false
---

# Skill Writer Reference

A reference for writing `SKILL.md` files that work reliably across different agent harnesses and models.

---

## SKILL.md Format Specification

### File Structure

```
.github/skills/<skill-name>/
├── SKILL.md           # Required — name must match folder name (hyphenated)
├── scripts/           # Executable code (shell, Python, JS)
├── references/        # Reference docs loaded on demand
└── assets/            # Templates, boilerplate, examples
```

### Valid Locations (by harness)

| Harness | Path |
|---------|------|
| VS Code Copilot | `.github/skills/<name>/`, `.agents/skills/<name>/`, `~/.copilot/skills/<name>/` |
| Claude Code | `.claude/skills/<name>/`, `~/.claude/skills/<name>/` |
| Cline / Roo Code | `.claude/skills/<name>/` (Claude Code-compatible), or custom `./skills/` |

### Frontmatter (YAML between `---`)

```yaml
---
name: my-skill                    # Required. 1-64 chars, lowercase + hyphens. MUST match folder name.
description: 'Required. Max 1024 chars. What the skill does and when to use it. Use trigger keywords.'
argument-hint: 'Optional. Shown for slash invocation (e.g., "path/to/target").'
user-invocable: true              # Optional (default: true). Shows as /-command in chat.
disable-model-invocation: false   # Optional (default: false). Prevents auto-loading by agent.
---
```

### Body Conventions

- **What** the skill accomplishes
- **When to use** — explicit trigger keywords for agent discovery
- **Step-by-step procedure** — numbered steps, no ambiguity
- **References** — relative paths with `./` prefix, one level deep from SKILL.md

### Progressive Loading Budget

| Stage | Token Budget | What's Available |
|-------|-------------|-----------------|
| Discovery | ~100 tokens | `name` + `description` only |
| Instructions | <5000 tokens | Full `SKILL.md` body |
| Resources | On demand | Referenced files (scripts, references, assets) |

Keep `SKILL.md` under 500 lines. Split detailed docs into `./references/`.

---

## Guard Rails

### ✅ Do
- **Keyword-rich descriptions**: Use the "Use when..." pattern with concrete trigger words (e.g., "Use when deploying to AWS", "Use when running database migrations")
- **Step-by-step procedures**: Every skill must have actionable numbered steps
- **Relative paths**: Always `./scripts/test.sh`, never `/absolute/path` or `~/path`
- **Self-contained**: Include all procedural knowledge needed — the agent should not need external research
- **Progressive structure**: Frontmatter → What/When → Procedure → References
- **Test scripts**: If the skill runs code, include an idempotent safe-invoke check
- **Idempotency**: Skills should be safe to run multiple times

### ❌ Don't
- **Vague descriptions**: "A helpful skill" tells the agent nothing — be specific
- **Monolithic files**: Split into `./references/` when exceeding 500 lines
- **Name mismatches**: `name` field must equal folder name exactly
- **Missing procedures**: Description without steps = the agent has nothing to follow
- **Deep nesting**: References should be 1 level deep — avoid `./references/subdir/deep/file.md`
- **Shell-specific syntax**: Use `#!/usr/bin/env bash` or `#!/usr/bin/env python3` for portability
- **Stateful assumptions**: Don't assume previous steps succeeded, previous context, or specific tool availability

### Description Anti-Patterns

| ❌ Weak | ✅ Strong |
|---------|-----------|
| "Helps with testing" | "Run Playwright end-to-end tests for web apps. Use when verifying UI behavior, capturing screenshots, or debugging frontend failures." |
| "Database helper" | "Run PostgreSQL migrations and seed data. Use when setting up dev databases, rolling back migrations, or resetting test data." |
| "Deployment" | "Deploy to AWS Lambda using the SAM CLI. Use when shipping new versions, rolling back, or checking deployment status." |

---

## Adapting to Different Harnesses

Each harness loads and uses skills slightly differently.

### VS Code Copilot

- **Discovery**: Agent reads `description` to decide relevance; `name` for invocation
- **Slash commands**: `user-invocable: true` makes the skill appear when typing `/` in chat
- **Auto-loading**: `disable-model-invocation: false` (default) lets the agent auto-load the skill when it detects a matching task
- **Tool access**: Uses VS Code's built-in tools (read, edit, search, execute, terminal, web, etc.)
- **Reference loading**: `./references/file.md` paths are read on demand by the agent
- **Scripts**: Must be executable; VS Code runs them in the integrated terminal
- **Best for**: Tight VS Code integration, multi-step workflows with editor context

### Claude Code (Anthropic)

- **Location**: `.claude/skills/<name>/SKILL.md`
- **Discovery**: Claude Code automatically surfaces skills matching the task context
- **Slash commands**: Skills appear as `/` commands in Claude Code CLI
- **`name` convention**: Should match folder name; Claude Code uses this for tracking
- **Tool access**: Claude Code has its own tool set — write scripts cross-platform (bash works reliably)
- **Reference loading**: Claude Code loads references when explicitly referenced in the body
- **Best for**: CLI-first workflows, terminal-heavy tasks, headless environments

### Cline / Roo Code

- **Location**: Typically `.claude/skills/<name>/` (Claude Code-compatible), or project-specific `./skills/`
- **Discovery**: Reads `description` for relevance matching; no built-in slash command system
- **Tool access**: Supports MCP tools, read/write, browser, and terminal
- **Scripts**: Prefer simple bash/Python scripts — avoid VS Code-specific APIs
- **Best for**: Task automation, custom workflows, MCP-integrated tools

### Adaptation Checklist

| Aspect | VS Code Copilot | Claude Code | Cline |
|--------|----------------|-------------|-------|
| Primary path | `.github/skills/` | `.claude/skills/` | `.claude/skills/` |
| Slash command | `user-invocable: true` | Built-in for all skills | Not supported |
| Script runner | VS Code terminal | Shell | Shell |
| Reference loading | On-demand agent read | On-demand agent read | On-demand agent read |
| Tool access | Editor tools + terminal | Terminal + files | MCP + terminal |
| Best for | Editor-integrated workflows | CLI automation | Custom toolchains |

---

## Adapting to Different Models

Different models interpret skill instructions differently. Write for the weakest model in your target set.

### General Principles

- **Be explicit**: Spell out every step. Don't rely on a model's latent knowledge.
- **Avoid ambiguity**: "Install dependencies" → "Run `npm install` in the project root"
- **One step = one action**: Each numbered step should produce one clear outcome
- **Provide fallbacks**: If a command might fail, tell the agent what to try next
- **Constrained language**: Short sentences, active voice, imperative mood

### Model-Specific Notes

| Model Type | Strengths | Pitfalls | Adaptation |
|------------|-----------|----------|------------|
| **Claude (Sonnet/Opus)** | Follows long procedures well, respects constraints | Can over-engineer | Give clear completion criteria; use "DO NOT" constraints |
| **GPT-4 / GPT-4o** | Fast, good at code generation | May skip steps or hallucinate commands | Number every step; include verification checks |
| **Gemini** | Broad knowledge base | May add extra steps not in the skill | Use strict "ONLY" / "DO NOT" guard rails |
| **DeepSeek** | Strong reasoning, follows structure | May re-interpret steps creatively | Use literal language; avoid metaphors |
| **Small models (Phi, Llama 3.2, etc.)** | Lightweight | Limited context; may misread multi-step instructions | Keep <100 lines; short sentences; flat structure (no deep nesting) |

### Writing for Small / Weak Models (≤8B parameters)

- Keep SKILL.md under 100 lines
- Use flat numbered lists — avoid nested sub-steps
- One sentence per instruction
- Include explicit path references (e.g., `./scripts/deploy.sh`) — don't ask the model to figure out paths
- Repeat critical context (don't rely on the model remembering earlier steps)
- No YAML frontmatter beyond `name` and `description` (avoid `disable-model-invocation` etc. — they may confuse parsing)
- Use `---` section dividers sparingly

---

## Templates

Ready-to-use template files in [./templates/](./templates/):

| Template | File | Use Case |
|----------|------|----------|
| Standard Skill | [standard-skill.md](./templates/standard-skill.md) | General-purpose VS Code skill with full structure |
| Minimal Skill | [minimal-skill.md](./templates/minimal-skill.md) | Compact skill for small/weak models (≤8B params) |
| Multi-Harness Skill | [multi-harness-skill.md](./templates/multi-harness-skill.md) | Portable across VS Code, Claude Code, and Cline |
| Instructions File | [instructions-file.md](./templates/instructions-file.md) | `.instructions.md` for coding conventions |
| Prompt File | [prompt-file.md](./templates/prompt-file.md) | `.prompt.md` for parameterized single tasks |
| Custom Agent | [custom-agent.md](./templates/custom-agent.md) | `.agent.md` for focused subagent personas |

## Examples

Real-world examples in [./examples/](./examples/):

| Example | File | Demonstrates |
|---------|------|-------------|
| Docker Deploy | [deploy-docker.md](./examples/deploy-docker.md) | Multi-step deployment with rollback & troubleshooting |
| Playwright Tests | [run-playwright-tests.md](./examples/run-playwright-tests.md) | E2E testing with scripts and trace viewer |
| DB Migrations | [run-db-migrations.md](./examples/run-db-migrations.md) | Schema migration with seed & rollback procedures |
| Format & Lint | [format-lint-code.md](./examples/format-lint-code.md) | Code quality automation with sequential steps |
