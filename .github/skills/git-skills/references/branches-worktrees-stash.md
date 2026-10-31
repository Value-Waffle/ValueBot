# Branches, Worktrees & Stash

## Branch Lifecycle

1. **Start fresh** — `git switch main && git pull --rebase`
2. **Create + switch** — `git switch -c feat/<short-name>`
3. **Work & commit** — atomic commits, conventional messages
4. **Push** — `git push -u origin feat/<short-name>`
5. **Open a PR** — see `./pull-requests.md`
6. **After merge** — `git switch main && git pull --rebase && git branch -d feat/<short-name>`

### Naming Conventions

| Prefix | Purpose |
|--------|---------|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `chore/` | Tooling, CI, maintenance |
| `docs/` | Documentation |
| `refactor/` | Code restructuring |
| `test/` | Test-only changes |

Use short, hyphenated names: `feat/add-project-notes`, not `feat/add_project_notes_v2_final`.

## Worktree Workflow

Worktrees let you check out a second branch in a **sibling directory** without stashing or cloning.

### Why use a worktree

- You need to switch context but have uncommitted work.
- You want to review or test another branch while your branch is checked out.
- You want to run long tests on one branch and keep coding on another.

### Steps

```bash
cd <repo-root>                                  # e.g. cd board-games
git worktree add ../board-games-hotfix -b fix/hotfix
git worktree list                               # verify
cd ../board-games-hotfix                        # separate working tree
# ... work, commit, push ...
cd <repo-root>
git worktree remove ../board-games-hotfix
git worktree prune
```

### Rules

- A branch can be checked out in **only one worktree** at a time.
- Do not edit the same worktree directory from two terminals.
- Remove worktrees when done; `git worktree prune` clears stale metadata.

## Stash Decision Matrix

Stash is a **last resort**. Prefer other options first.

| Situation | Preferred | Why not stash |
|-----------|-----------|---------------|
| Need to switch branch with WIP | Commit WIP, or use a worktree | Stash is easy to forget and lose |
| WIP is meaningful progress | Commit it (you can amend/rebase later) | A commit is recoverable; a stash is not |
| Quick 5-minute context switch | Worktree | Keeps work visible and on-disk |
| Must switch NOW, no time | `git stash push -m "..."` | Acceptable fallback |

### Stash Pitfalls

- **Stashes are local only** — they never leave your machine and survive no clone/push.
- **Unnamed stashes pile up** — always `push -m "<message>"`.
- **`git stash pop` can conflict** — prefer `apply` then `drop` when you have verified.
- **Untracked files are not stashed by default** — `-u` includes them but can surprise you.
- **Secrets in a stash are still on disk** — never stash secrets.
- **Long-lived stashes go stale** — resolve them within the same session.
