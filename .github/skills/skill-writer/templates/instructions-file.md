Copy this template and save it as `.github/instructions/<your-file>.instructions.md`.

```markdown
---
applyTo: "**/*.py"
description: 'Coding conventions for Python files. Use when writing, reviewing, or editing Python code.'
---

# Python Coding Conventions

## Style
- Use 4-space indentation.
- Maximum line length: 88 characters (Black default).
- Use type hints for all function signatures.

## Imports
- Group: standard library → third-party → local.
- Alphabetical within each group.
- Use `import X` for stdlib, `from Y import Z` for project modules.

## Naming
- `snake_case` for functions and variables.
- `PascalCase` for classes.
- `UPPER_CASE` for constants.

## Error Handling
- Prefer specific exception types over bare `except:`.
- Use context managers (`with` statement) for resource handling.
```
