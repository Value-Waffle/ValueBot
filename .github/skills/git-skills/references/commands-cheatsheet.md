# Git Command Cheatsheet

Quick lookup of the commands used across the git-skills procedures. Run all commands from inside the repo you are changing.

## State & Inspection

| Task | Command |
|------|---------|
| Full snapshot (read-only) | `bash .github/skills/git-skills/scripts/repo-health.sh` |
| Short status with branch + tracking | `git status --short --branch` |
| Current branch | `git branch --show-current` |
| Repo root | `git rev-parse --show-toplevel` |
| List worktrees | `git worktree list` |
| List stashes | `git stash list` |

## Diff & History

| Task | Command |
|------|---------|
| Unstaged changes | `git diff` |
| Staged changes | `git diff --cached` |
| Everything vs HEAD | `git diff HEAD` |
| One file | `git diff -- <path>` |
| Summary only | `git diff --stat` |
| Graph history | `git log --oneline --graph --all -20` |
| One commit | `git show <commit>` |
| File at a commit | `git show <commit>:<path>` |
| Branch changes since fork | `git diff main...<branch>` |
| Who changed a file | `git blame <path>` |
| Search commit messages | `git log --oneline --grep=<term>` |

## Commit

| Task | Command |
|------|---------|
| Stage specific files | `git add <file>...` |
| Stage all (careful) | `git add -A` |
| Unstage a file | `git restore --staged <file>` |
| Commit | `git commit -m "type(scope): subject"` |
| Amend last commit (local only) | `git commit --amend` |
| Secrets scan before commit | `bash .github/skills/git-skills/scripts/precommit-secrets-scan.sh` |

## Branch

| Task | Command |
|------|---------|
| List local + upstream | `git branch -vv` |
| List all (incl. remote) | `git branch -a` |
| Create + switch | `git switch -c feat/<name>` |
| Switch | `git switch <branch>` |
| Rename | `git branch -m <old> <new>` |
| Delete merged | `git branch -d <branch>` |
| Force delete unmerged | `git branch -D <branch>` |
| Prune stale remotes | `git fetch --prune` |

## Worktree

| Task | Command |
|------|---------|
| Add (new branch) | `git worktree add ../<dir> -b <branch>` |
| Add (existing branch) | `git worktree add ../<dir> <branch>` |
| List | `git worktree list` |
| Remove | `git worktree remove ../<dir>` |
| Force remove | `git worktree remove --force ../<dir>` |
| Prune stale entries | `git worktree prune` |

## Stash (last resort)

| Task | Command |
|------|---------|
| Save with message | `git stash push -m "<message>"` |
| Save only some files | `git stash push -- <file>...` |
| List | `git stash list` |
| Inspect | `git stash show -p stash@{0}` |
| Apply + keep | `git stash apply stash@{0}` |
| Apply + drop | `git stash pop` |
| Drop one | `git stash drop stash@{0}` |
| Drop all | `git stash clear` |

## Remote / Pull

| Task | Command |
|------|---------|
| Fetch all + prune | `git fetch --all --prune` |
| Pull with rebase | `git pull --rebase` |
| Pull (merge) | `git pull` |
| Push new branch | `git push -u origin <branch>` |
| Abort a rebase | `git rebase --abort` |
| Continue a rebase | `git rebase --continue` |

## Pull Requests (gh CLI)

| Task | Command |
|------|---------|
| Create PR | `gh pr create --base main --title "..." --body "..."` |
| Create + open browser | `gh pr create --web` |
| Auto-fill from commits | `gh pr create --fill` |
| Status of my PRs | `gh pr status` |
| List open PRs | `gh pr list` |
| View a PR | `gh pr view <number>` |
| Merge | `gh pr merge <number> --squash` |

## Submodules (other projects only — this vault has none)

| Task | Command |
|------|---------|
| Clone with submodules | `git clone --recurse-submodules <url>` |
| Init after plain clone | `git submodule update --init --recursive` |
| Update to latest | `git submodule update --remote --recursive` |
| Add | `git submodule add <url> <path>` |
| Status | `git submodule status` |
| Deinit | `git submodule deinit -f <path>` |
