> **Example only** — a real SKILL.md for code formatting. Copy to `.github/skills/format-lint-code/SKILL.md` to use.

```markdown
---
name: format-lint-code
description: 'Format and lint all project files. Use when: cleaning up code, fixing lint errors, running formatter, enforcing code style.'
user-invocable: true
---

# Format & Lint

Run formatters and linters across the project.

## When to Use
- Before committing code
- Fixing CI lint failures
- Enforcing consistent code style

## Prerequisites
- Dependencies installed (`npm install` or `pip install -e ".[dev]"`)

## Procedure
1. **Format** — Run `npx prettier --write .` (JS/TS/MD) or `black .` (Python).
2. **Lint** — Run `npx eslint . --fix` or `ruff check . --fix`.
3. **Type check** — Run `npx tsc --noEmit` or `mypy .`.
4. **Verify** — Confirm no errors in output.

## Scripts
- [lint-all.sh](./scripts/lint-all.sh) — runs format + lint + type check in sequence

## Troubleshooting
- **Prettier config missing**: Create `.prettierrc` in project root.
- **ESlint plugin errors**: Run `npx eslint --debug` to find plugin load failures.
```
