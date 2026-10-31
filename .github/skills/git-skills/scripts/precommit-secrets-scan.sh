#!/usr/bin/env bash
# precommit-secrets-scan.sh — scan staged changes for likely secrets. Read-only.
# Run before `git commit`. Exits 1 (with a warning) if a likely secret is found.
# Heuristic only: review every match yourself before committing.
set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not inside a git repository." >&2
  exit 1
fi

patterns='(-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xox[bap]-[A-Za-z0-9-]{10,}|password[[:space:]]*[:=][[:space:]]*[^[:space:]]+|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+|secret[[:space:]]*[:=][[:space:]]*[^[:space:]]+|token[[:space:]]*[:=][[:space:]]*[^[:space:]]+)'

echo "Scanning staged changes for likely secrets..."
if git diff --cached -U0 | grep -Ein "${patterns}"; then
  echo "WARNING: possible secrets found above. Review before committing." >&2
  exit 1
fi

echo "OK: no obvious secrets found in staged changes."
