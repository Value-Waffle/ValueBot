#!/usr/bin/env bash
# valuebot — dev-time environment primer (NOT required for installation).
#
# The LibreChat loader launches the server with `uv run` (see mcp.json), so the
# runtime environment is built at install/first-run time on the machine or
# container that actually executes it. This script only warms a LOCAL dev
# environment for running the repo's tests and manual probes.
#
#   uv sync --project mcp   (preferred; honours UV_PROJECT_ENVIRONMENT)
#   python3 -m venv .venv   (fallback when uv is unavailable)
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$SCRIPT_DIR"
MCP_DIR="$PLUGIN_ROOT/mcp"
PYTHON_BIN="${PYTHON:-python3}"

# Keep the dev environment outside mcp/ so it is never mistaken for the
# runtime launcher (which no longer exists in the package).
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$PLUGIN_ROOT/.venv}"
VENV_DIR="$UV_PROJECT_ENVIRONMENT"
VENV_PY="$VENV_DIR/bin/python"

WITH_PRICE=0
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: ./bootstrap.sh [--with-price] [--dry-run]

  --with-price  also install the optional price extras (yfinance)
  --dry-run     print the commands that would run; change nothing

NOTE: installation does not need this script. mcp.json starts the server with
`uv run`, so LibreChat builds the environment itself inside the container.
Run this only to warm a local development environment (tests, probes).
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --with-price) WITH_PRICE=1 ;;
    --dry-run)    DRY_RUN=1 ;;
    -h|--help)    usage; exit 0 ;;
    *)
      printf 'bootstrap: unknown option: %s\n' "$arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

USE_UV=0
if command -v uv >/dev/null 2>&1; then
  USE_UV=1
elif [ "$DRY_RUN" -eq 0 ]; then
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
    printf 'bootstrap: neither uv nor %s found; install uv or python3\n' "$PYTHON_BIN" >&2
    exit 1
  }
fi

if [ "$USE_UV" -eq 1 ]; then
  if [ "$WITH_PRICE" -eq 1 ]; then
    run uv sync --project "$MCP_DIR" --extra price
  else
    run uv sync --project "$MCP_DIR"
  fi
else
  run "$PYTHON_BIN" -m venv "$VENV_DIR"
  run "$VENV_PY" -m pip install --quiet --upgrade pip
  run "$VENV_PY" -m pip install --quiet -r "$PLUGIN_ROOT/requirements.txt"
  if [ "$WITH_PRICE" -eq 1 ]; then
    run "$VENV_PY" -m pip install --quiet -r "$PLUGIN_ROOT/requirements-price.txt"
  fi
fi

printf '\nvaluebot bootstrap summary (dev environment)\n'
printf '  plugin root : %s\n' "$PLUGIN_ROOT"
if [ "$USE_UV" -eq 1 ]; then
  printf '  toolchain   : uv\n'
  printf '  project     : %s\n' "$MCP_DIR"
else
  printf '  toolchain   : %s -m venv + pip\n' "$PYTHON_BIN"
fi
printf '  environment : %s\n' "$VENV_DIR"
printf '  interpreter : %s\n' "$VENV_PY"
if [ "$WITH_PRICE" -eq 1 ]; then
  printf '  price extras: enabled\n'
else
  printf '  price extras: disabled (pass --with-price to install)\n'
fi
if [ "$DRY_RUN" -eq 1 ]; then
  printf '  status      : dry-run — nothing changed\n'
else
  printf '  status      : ready — run tests with %s -m pytest tests -q\n' "$VENV_PY"
fi
