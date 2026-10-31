---
name: git-skills
description: 'Safely use Git: commit, branch, diff, worktrees, stash, pull, pull requests, and submodules. Use when: committing changes, creating or merging branches, creating worktrees, stashing, pulling from remote, opening PRs, managing submodules, diffing code or listing commits.'
user-invocable: true
disable-model-invocation: false
---

# Git Skills

## When to Use
- Making a commit or staging changes
- Creating, switching, renaming, or deleting branches
- Creating a git worktree for parallel work
- Diffing code, viewing history, or listing commits
- Stashing changes (use only as a last resort)
- Pulling latest changes from a remote
- Opening or reviewing a pull request
- Adding or updating git submodules
- Answering any git hygiene or workflow question

## What It Does
Provides safe, step-by-step procedures for the most common git operations, plus guard rails (what to avoid) and a workspace-specific note about this multi-repo vault. Every procedure is read-only-safe first: run `bash .github/skills/git-skills/scripts/repo-health.sh` before mutating the repo.

## Workspace-Specific Context (this vault)

This is a **multi-repo vault, NOT a single codebase** (see `AGENTS.md`):

- Each major subdirectory is its **own git repo embedded in the tree — NOT a submodule**: `board-games/`, `hippo/`, `ai/`, `agent_evaluation/`, `.github/`, `.dev/`.
- The vault root repo only tracks `architecture/`, `src/`, `README.md`, `.gitignore`, `.claude/`. Everything else is git-ignored.
- Consequences:
  - `git status` at the vault root only shows vault-level changes.
  - **Run all git commands inside the sub-repo directory you are changing** (e.g. `cd board-games` first).
  - There are **no submodules** in this vault — do not run `git submodule` commands here. The submodule procedure below applies only to other projects that actually use submodules.

## Prerequisites
- `git` (run `git --version`; version ≥ 2.23 for `git switch` / `git restore`)
- `gh` GitHub CLI for the pull-request procedure (`gh --version`; `gh auth status`)

## Safety Rules (read first)
1. Run `bash .github/skills/git-skills/scripts/repo-health.sh` before any mutating command — it is read-only.
2. Scan staged changes for secrets with `bash .github/skills/git-skills/scripts/precommit-secrets-scan.sh` before committing.
3. NEVER run `git reset --hard`, `git clean -fd`, or `git push --force` without explicit user confirmation.
4. NEVER commit secrets, `.env` files, or generated build output. Verify with `git status` before `git add`.
5. NEVER run git commands at the vault root when the change is inside a sub-repo. `cd` into the sub-repo first.

## Procedure

### 1. Make a Commit
1. **Inspect** — run `bash .github/skills/git-skills/scripts/repo-health.sh` (or `git status --short --branch`) from inside the repo.
2. **Review changes** — `git diff` (unstaged) and `git diff --cached` (already staged).
3. **Stage intentionally** — `git add <file>...` only the files that belong to this change. Avoid `git add -A` unless you intend to stage everything.
4. **Scan for secrets** — run `bash .github/skills/git-skills/scripts/precommit-secrets-scan.sh`.
5. **Review staged diff** — `git diff --cached --stat`, then `git diff --cached`.
6. **Commit** — `git commit -m "type(scope): subject"`. Use a conventional message (see `./references/commit-conventions.md`).
7. **Verify** — `git log --oneline -1`.

Rules: one logical change per commit; imperative mood ("Add", "Fix" — not "Added"/"Fixed"); never amend or force-push a commit already pushed to a shared branch.

### 2. Create and Maintain Branches
1. **Start from latest main** — `git switch main && git pull --rebase`.
2. **Create + switch** — `git switch -c feat/<short-name>` (prefix: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`).
3. **List** — `git branch -vv` (local + upstream tracking) or `git branch -a` (all).
4. **Switch** — `git switch <branch>`.
5. **Rename** — `git branch -m <old> <new>`.
6. **Delete merged local branch** — `git branch -d <branch>` (safe; refuses if unmerged). Use `-D` only when certain.
7. **Prune stale remote-tracking branches** — `git fetch --prune`.

Keep branches short-lived and single-purpose; delete them after the PR merges. Details: `./references/branches-worktrees-stash.md`.

### 3. Diff Code and List Commits
1. **Unstaged changes** — `git diff`.
2. **Staged changes** — `git diff --cached`.
3. **Everything vs HEAD** — `git diff HEAD`.
4. **One file** — `git diff -- <path>`.
5. **Summary only** — `git diff --stat`.
6. **History** — `git log --oneline --graph --all -20`.
7. **One commit** — `git show <commit>`; file contents at a commit — `git show <commit>:<path>`.
8. **Branch comparison** — `git diff main...<branch>` (three dots = changes since the branch point; two dots = raw endpoint diff).

Full command cheat sheet: `./references/commands-cheatsheet.md`.

### 4. Create a Worktree
Use a worktree to work on a second branch in parallel without stashing or cloning.

1. **From the repo root** — `git worktree add ../<name>-<branch> -b <branch>` (creates a sibling directory with its own working tree).
2. **Verify** — `git worktree list`.
3. **Work** — run git commands inside that sibling directory as normal.
4. **Finish** — commit/push from the worktree, switch back, then `git worktree remove ../<name>-<branch>`.
5. **Clean up stale metadata** — `git worktree prune`.

Rules: a branch can be checked out in only one worktree at a time; do not edit the same worktree from two terminals; remove worktrees when done.

### 5. Stash (Last Resort)
Prefer committing WIP to a branch or using a worktree. Stash only when you must switch context without a commit.

1. **Save** — `git stash push -m "description of WIP"` (or `git stash push -- <file>` to stash only some files).
2. **List** — `git stash list`.
3. **Inspect** — `git stash show -p stash@{0}`.
4. **Restore and keep** — `git stash apply stash@{0}` (stash remains).
5. **Restore and drop** — `git stash pop` (drops after applying; may conflict).
6. **Discard one stash** — `git stash drop stash@{0}`.

Avoid: long-lived stashes, many unnamed stashes, stashing untracked files with `-u` unless you mean it, stashing secrets, and `git stash pop` with a dirty tree. Stashes are local only — they never leave your machine and are easily lost. Decision matrix: `./references/branches-worktrees-stash.md`.

### 6. Pull from Remote
1. **Fetch first (always)** — `git fetch --all --prune`.
2. **Ensure a clean tree** — commit or stash before pulling; `git status` must be clean.
3. **Pull with rebase (preferred)** — `git pull --rebase` to keep history linear. Use plain `git pull` only if the repo's convention forbids rebasing.
4. **On conflict** — resolve files, `git add <file>`, then `git rebase --continue` (or `git rebase --abort` to back out).
5. **Verify** — `git status --short --branch` and `git log --oneline -5`.

Never `git pull` at the vault root to update a sub-repo — `cd` into the sub-repo and pull there.

### 7. Open a Pull Request
1. **Push the branch** — `git push -u origin <branch>`.
2. **Create the PR** — `gh pr create --base main --title "..." --body "..."` (or `--fill` to auto-fill from commits; `--web` to finish in the browser).
3. **Check state** — `gh pr status` / `gh pr view`.
4. **List open PRs** — `gh pr list`.
5. **After merge** — `git switch main && git pull --rebase && git branch -d <branch>`.

PR body must state: what changed, why, how it was tested, and any screenshots for UI changes. Template and checklist: `./references/pull-requests.md`.

### 8. Work with Submodules
**This vault has NO submodules** (its sub-repos are independent embedded repos). Use this procedure only in projects that actually use submodules.

1. **Clone with submodules** — `git clone --recurse-submodules <url>`.
2. **Init after a plain clone** — `git submodule update --init --recursive`.
3. **Update to latest** — `git submodule update --remote --recursive`.
4. **Add a submodule** — `git submodule add <url> <path>` (then commit the parent repo).
5. **Status** — `git submodule status`.
6. **Remove** — `git submodule deinit -f <path>`, `git rm -f <path>`, delete the `.gitmodules` entry, commit.

A submodule is pinned to a commit; after updating it you must commit the parent repo so the pin moves. Details: `./references/submodules.md`.

## Best Practices
- Commit early and often; each commit is one logical change.
- Conventional commit messages; imperative mood; reference issue/PR IDs.
- Never commit secrets, `.env`, keys, or build artifacts — scan with the secrets script first.
- Prefer `git pull --rebase`; keep history linear.
- Never force-push a shared branch.
- Delete merged branches and remove finished worktrees.
- In this vault, run git inside the sub-repo you are changing, never at the root.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `fatal: not a git repository` at the vault root | `cd` into the sub-repo (e.g. `board-games/`) and rerun. |
| Detached HEAD | `git switch -c <new-branch>` to keep your work. |
| `error: Your local changes would be overwritten by merge` | Commit or stash first, then pull. |
| Merge conflict on pull/rebase | Resolve files, `git add`, then `git rebase --continue` / `git merge --continue`. |
| Branch checked out in another worktree | Switch to that worktree or remove it with `git worktree remove`. |
| Stash pop conflict | Resolve, then `git stash drop` manually; never assume it auto-cleaned. |
| Submodule not initialized (`-` prefix in `git submodule status`) | `git submodule update --init --recursive`. |

## Scripts
- [repo-health.sh](./scripts/repo-health.sh) — read-only snapshot: branch, status, recent commits, stashes, worktrees. Run before any mutation.
- [precommit-secrets-scan.sh](./scripts/precommit-secrets-scan.sh) — scans staged changes for likely secrets. Run before committing.

## References
- [commands-cheatsheet.md](./references/commands-cheatsheet.md) — git commands grouped by task
- [commit-conventions.md](./references/commit-conventions.md) — commit message format, staging, atomic commits
- [branches-worktrees-stash.md](./references/branches-worktrees-stash.md) — branch lifecycle, worktree workflow, stash decision matrix
- [pull-requests.md](./references/pull-requests.md) — gh CLI PR workflow and PR quality checklist
- [submodules.md](./references/submodules.md) — submodule lifecycle and this vault's embedded-repo caveat
