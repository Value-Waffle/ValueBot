Copy this template and save it as `.github/skills/<your-skill-name>/SKILL.md`.

```markdown
---
name: portable-skill
description: 'Cross-platform task. Use when: trigger-keyword.'
---

# Portable Skill

Works with VS Code Copilot, Claude Code, and Cline.

## When to Use
- Cross-platform automation task
- CI/CD or local development workflow

## Prerequisites
- Tool installed (`which tool`)

## Procedure
1. Run `command` from project root.
2. Verify with `check-command`.

## Scripts
- [setup script](./scripts/setup.sh) — installs prerequisites
- [main script](./scripts/run.sh) — executes the workflow
```
