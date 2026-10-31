# Pull Requests

## Create a PR with `gh`

```bash
git push -u origin feat/<branch>
gh pr create --base main --title "feat(db): add project notes" --body "$(cat <<'EOF'
## What
...

## Why
...

## Testing
...

## Screenshots
...
EOF
)"
```

Shortcuts:

- `gh pr create --fill` — auto-fill title/body from commit messages.
- `gh pr create --web` — draft locally and finish in the browser.
- `gh pr create --draft` — open as draft for early feedback.

## PR Body Template

```markdown
## What
- Brief summary of the change.

## Why
- The problem this solves or the motivation.

## Testing
- Commands run and results (e.g. `make test-coverage`, `npm test`).

## Screenshots / Notes
- UI screenshots or reviewer notes, if applicable.
```

## Review & State

| Task | Command |
|------|---------|
| My PRs + review requests | `gh pr status` |
| List open PRs | `gh pr list` |
| View a PR | `gh pr view <number>` |
| View the diff | `gh pr diff <number>` |
| Add reviewers | `gh pr edit <number> --add-reviewer <user>` |
| Merge (squash) | `gh pr merge <number> --squash` |
| Close without merge | `gh pr close <number>` |

## Quality Checklist (before creating)

- [ ] Branch is based on latest `main` (`git pull --rebase` done).
- [ ] Commits are atomic with conventional messages.
- [ ] No secrets or generated files committed.
- [ ] Tests pass locally.
- [ ] PR body states what, why, and how it was tested.

## After Merge

```bash
git switch main
git pull --rebase
git branch -d feat/<branch>
git fetch --prune
```
