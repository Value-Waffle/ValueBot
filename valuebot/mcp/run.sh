#!/bin/sh
# valuebot MCP — portable launcher (POSIX sh; Alpine has no bash).
#
# Preferred: `uv run`, so the environment is built for the host/container that
# actually runs the server (a venv copied from another OS is unusable).
# Fallback: build a local venv with python3 and run the server from it.
#
# stdout is the JSON-RPC channel: every diagnostic below goes to stderr.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

log() {
    printf 'valuebot-mcp: %s\n' "$*" >&2
}

# 1. Preferred path: uv is shipped in the official LibreChat image.
if command -v uv >/dev/null 2>&1; then
    log "launching via uv (project=$SCRIPT_DIR)"
    exec uv run --project "$SCRIPT_DIR" "$SCRIPT_DIR/server.py"
fi

# 2. Fallback: build/reuse a venv in a writable location.
if [ -n "${PLUGIN_DATA:-}" ]; then
    ENV_DIR="$PLUGIN_DATA/venv"
else
    ENV_DIR="$SCRIPT_DIR/.dev-venv"
fi

if [ ! -x "$ENV_DIR/bin/python" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        log "neither uv nor python3 is available; cannot launch the server"
        exit 1
    fi
    log "uv not found; building a local venv at $ENV_DIR"
    if ! python3 -m venv "$ENV_DIR" >&2; then
        log "failed to create a virtualenv at $ENV_DIR"
        exit 1
    fi
    if [ -f "$PLUGIN_ROOT/requirements.txt" ]; then
        log "installing $PLUGIN_ROOT/requirements.txt"
        if ! "$ENV_DIR/bin/python" -m pip install --quiet --upgrade pip >&2 \
            || ! "$ENV_DIR/bin/python" -m pip install --quiet -r "$PLUGIN_ROOT/requirements.txt" >&2; then
            log "dependency installation failed"
            exit 1
        fi
    fi
fi

log "launching via $ENV_DIR/bin/python"
exec "$ENV_DIR/bin/python" "$SCRIPT_DIR/server.py"
