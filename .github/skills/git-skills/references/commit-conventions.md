# Commit Conventions

## Commit Message Format

Use Conventional Commits:

```
<type>(<scope>): <subject>
```

- **subject** — imperative mood, lowercase, no trailing period, ≤ 50 chars
- **scope** (optional) — the area changed, e.g. `backend`, `db`, `mcp`

### Types

| Type | Use for |
|------|---------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or fixing tests |
| `chore` | Build, tooling, CI, deps — no production code |
| `perf` | Performance improvement |
| `style` | Formatting only (whitespace, lint) |

### Examples

```
feat(db): add project_notes table
fix(mcp): handle missing BG_API_KEY
docs(rules): update database migration rules
refactor(backend): extract auth resolver
test(backend): cover user deletion flow
chore(ci): pin Python 3.12
```

## Staging Rules

1. **Stage intentionally** — `git add <file>...`, not `git add -A`, unless you truly want everything.
2. **One logical change per commit** — do not mix a bug fix with an unrelated refactor.
3. **Review before committing** — `git diff --cached` must match what you think you are committing.
4. **Scan for secrets** — `bash .github/skills/git-skills/scripts/precommit-secrets-scan.sh` before `git commit`.

## Atomic Commits

An atomic commit is the smallest change that still leaves the repo in a working state:

- It compiles / tests pass.
- It does exactly one thing.
- It can be reverted in isolation without breaking others.

If you can't summarize the change in one line, split it into multiple commits.

## Never Commit

- Secrets: API keys, tokens, passwords, private keys, `.env`
- Generated output: build artifacts, caches, `node_modules/`, `__pycache__/`, `.pyc`
- Local config that differs per machine (unless intentionally tracked)
- Large binaries or datasets

## Amend & Rewrite Rules

- `git commit --amend` is safe **only before the commit is pushed** to a shared branch.
- Never `git rebase` or `git push --force` a commit others may have based work on.
