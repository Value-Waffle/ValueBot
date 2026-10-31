#!/usr/bin/env bash
# repo-health.sh — read-only snapshot of the current git repository state.
# Safe to run any time. Makes NO changes to the repo or working tree.
# Run from inside the repo you care about (e.g. cd board-games && bash .github/skills/git-skills/scripts/repo-health.sh).
set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not inside a git repository." >&2
  echo "This vault is multi-repo: cd into the sub-repo first (e.g. board-games/, hippo/)." >&2
  exit 1
fi

root="$(git rev-parse --show-toplevel)"
branch="$(git branch --show-current 2>/dev/null || true)"
[ -z "$branch" ] && branch="(detached HEAD)"

echo "== repository =="
echo "cwd:    $(pwd)"
echo "root:   ${root}"
echo "branch: ${branch}"
echo
echo "== status =="
git status --short --branch
echo
echo "== last 10 commits =="
git log --oneline -10 2>/dev/null || echo "(no commits yet)"
echo
echo "== stashes =="
git stash list 2>/dev/null || echo "(none)"
echo
echo "== worktrees =="
git worktree list 2>/dev/null || echo "(worktrees not supported)"
