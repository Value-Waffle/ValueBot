Copy this template and save it as `.github/skills/<your-skill-name>/SKILL.md`.

```markdown
---
name: skill-name
description: 'Do X using Y. Use when: keyword1, keyword2, keyword3.'
user-invocable: true
---

# Skill Name

## When to Use
- Trigger phrase 1 — e.g., "set up a new X", "configure Y"
- Trigger phrase 2 — e.g., "run Z", "debug W"

## What It Does
One-paragraph summary of what this skill accomplishes and why it's useful.

## Prerequisites
- Tool or dependency 1 (e.g., Node.js >= 18)
- Tool or dependency 2 (e.g., `which docker`)

## Procedure
1. **Prepare** — Run `command` from project root to set up.
2. **Execute** — Run `main-command --flag` to perform the task.
3. **Verify** — Check for expected output or run `verify-command`.
4. **Clean up** — Run `cleanup-command` if needed.

## Troubleshooting
- **Error X**: Cause → solution
- **Error Y**: Cause → solution

## Scripts
- [setup script](./scripts/setup.sh) — installs prerequisites
- [main script](./scripts/run.sh) — executes the workflow
```
