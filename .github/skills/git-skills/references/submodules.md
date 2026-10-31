# Submodules

> **This vault has NO submodules.** Its sub-repos (`board-games/`, `hippo/`, `ai/`, `agent_evaluation/`, `.github/`, `.dev/`) are independent git repos embedded in the tree — not submodules. Do **not** run `git submodule` commands in this workspace. Use the instructions below only in projects that actually use submodules.

## What a Submodule Is

A submodule is a git repo nested inside another repo, where the parent stores only a **pointer to a specific commit** in the child. Updating the child does not update the parent until you commit the new pointer.

## Lifecycle Commands

| Task | Command |
|------|---------|
| Clone including submodules | `git clone --recurse-submodules <url>` |
| Init after a plain clone | `git submodule update --init --recursive` |
| Update to the pinned commit | `git submodule update --recursive` |
| Update to latest remote | `git submodule update --remote --recursive` |
| Add a submodule | `git submodule add <url> <path>` |
| Status | `git submodule status` |
| Remove a submodule | see steps below |

## Add a Submodule

```bash
git submodule add https://github.com/org/repo.git third_party/repo
git commit -m "chore: add third_party/repo submodule"
```

## Update a Submodule

```bash
git submodule update --remote --recursive
git add third_party/repo        # the pointer moved
git commit -m "chore: bump third_party/repo"
```

## Remove a Submodule

```bash
git submodule deinit -f <path>
git rm -f <path>
# remove the [submodule "<path>"] block from .gitmodules
# commit the .gitmodules change and the index removal
```

## Pitfalls

- **Pinned commits** — after `git submodule update --remote`, always commit the parent so the pin moves.
- **Dirty submodules** — a submodule with uncommitted changes shows as dirty in `git submodule status`; commit inside the submodule first.
- **`-` prefix** in `git submodule status` means "not initialized" — run `git submodule update --init`.
- **Deleting a directory is not removal** — deleting the folder leaves stale `.gitmodules` and index entries; follow the removal steps.
