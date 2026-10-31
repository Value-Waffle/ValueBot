#!/bin/sh
# One-time SEC User-Agent setup for valuebot.
#
#   ./setup.sh example-user@gmail.com
#   ./setup.sh --show
#   ./setup.sh --reset
#   ./setup.sh --doctor
#
# PLUGIN_DATA defaults to ~/.valuebot, matching the PLUGIN_DATA resolution in
# mcp/core/config.py; the User-Agent is written to ${PLUGIN_DATA}/identity.json.
# Until that file exists the plugin's data tools return
# identity_not_configured. `--doctor` runs read-only diagnostics, prints one
# line per check and never reads stdin.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
MCP_DIR="$SCRIPT_DIR/mcp"

# Inside the LibreChat container HOME is not writable; keep uv state in the
# plugin data dir, matching mcp.json.
PLUGIN_DATA="${PLUGIN_DATA:-$HOME/.valuebot}"
export PLUGIN_DATA
mkdir -p "$PLUGIN_DATA"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PLUGIN_DATA/uv-cache}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$PLUGIN_DATA/uv-env}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$PLUGIN_DATA/uv-python}"

if command -v uv >/dev/null 2>&1; then
  cd "$MCP_DIR"
  exec uv run --project "$MCP_DIR" python -m core.setup "$@"
fi

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  cd "$MCP_DIR"
  exec "$SCRIPT_DIR/.venv/bin/python" -m core.setup "$@"
fi

cd "$MCP_DIR"
exec python3 -m core.setup "$@"
