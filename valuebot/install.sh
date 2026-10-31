#!/bin/sh
# valuebot installer — create or merge the "vw-mcp" server entry for a harness.
#
#   ./install.sh --harness vscode --dry-run
#   ./install.sh --harness claude-code --email example-user@gmail.com
#   ./install.sh --help
#
# POSIX sh only (Alpine has no bash) and no jq: every bit of JSON work is done
# by python3 from an inline heredoc. Re-running is safe — only
# <topkey>["vw-mcp"] is written; every other server and top-level key survives.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

HARNESS=""
DATA="$HOME/.valuebot"
PLUGIN_ROOT="$SCRIPT_DIR"
CONFIG=""
EMAIL=""
NO_SETUP=0
DRY_RUN=0

usage() {
    cat <<'USAGE'
usage: install.sh --harness <name> [options]

Create or merge the valuebot MCP server entry ("vw-mcp") in a harness config
file. Safe to re-run: only <topkey>["vw-mcp"] is written; other servers and
unrelated top-level keys are left exactly as they were.

Harnesses with a local JSON config:
  claude-desktop   mcpServers                 ~/Library/Application Support/Claude/claude_desktop_config.json
  claude-code      mcpServers (type: stdio)   ./.mcp.json
  vscode           servers    (type: stdio)   ./.vscode/mcp.json
  copilot-cli      mcpServers                 ~/.copilot/mcp-config.json
  gemini-cli       mcpServers                 ~/.gemini/settings.json

options:
  --harness <name>    target harness (required)
  --data DIR          valuebot data root (default: $HOME/.valuebot)
  --plugin-root DIR   valuebot checkout (default: the directory containing install.sh)
  --config PATH       override the config file path (handy for testing)
  --email ADDR        SEC contact address; run setup.sh with it afterwards
  --no-setup          never run setup.sh
  --dry-run           print the resulting JSON and write nothing
  -h, --help          show this message and exit 0

Harnesses that need a non-JSON or non-local config (LibreChat, Codex, DeepSeek,
Hermes, Pi, ChatGPT, OpenCode, Open WebUI) cannot be installed this way; the
per-harness guides in harnesses/<name>/INSTALL.md stay the reference, and this
script points you at the matching guide.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --harness)
            [ "$#" -ge 2 ] || { printf 'install.sh: --harness requires a value\n' >&2; usage >&2; exit 2; }
            HARNESS=$2
            shift 2
            ;;
        --harness=*)
            HARNESS=${1#*=}
            shift
            ;;
        --data)
            [ "$#" -ge 2 ] || { printf 'install.sh: --data requires a value\n' >&2; usage >&2; exit 2; }
            DATA=$2
            shift 2
            ;;
        --data=*)
            DATA=${1#*=}
            shift
            ;;
        --plugin-root)
            [ "$#" -ge 2 ] || { printf 'install.sh: --plugin-root requires a value\n' >&2; usage >&2; exit 2; }
            PLUGIN_ROOT=$2
            shift 2
            ;;
        --plugin-root=*)
            PLUGIN_ROOT=${1#*=}
            shift
            ;;
        --config)
            [ "$#" -ge 2 ] || { printf 'install.sh: --config requires a value\n' >&2; usage >&2; exit 2; }
            CONFIG=$2
            shift 2
            ;;
        --config=*)
            CONFIG=${1#*=}
            shift
            ;;
        --email)
            [ "$#" -ge 2 ] || { printf 'install.sh: --email requires a value\n' >&2; usage >&2; exit 2; }
            EMAIL=$2
            shift 2
            ;;
        --email=*)
            EMAIL=${1#*=}
            shift
            ;;
        --no-setup)
            NO_SETUP=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'install.sh: unknown option: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ -z "$HARNESS" ]; then
    printf 'install.sh: --harness is required\n' >&2
    usage >&2
    exit 2
fi

TOPKEY=""
ENTRY_TYPE=""
RESTART=""

case "$HARNESS" in
    claude-desktop)
        TOPKEY="mcpServers"
        ENTRY_TYPE=""
        RESTART='open the app again: in Claude click "Claude" → "Quit Claude", then relaunch Claude (a running app keeps the old config).'
        [ -n "$CONFIG" ] || CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
        ;;
    claude-code)
        TOPKEY="mcpServers"
        ENTRY_TYPE="stdio"
        RESTART='restart the Claude Code session so .mcp.json is re-read (check it with /mcp).'
        [ -n "$CONFIG" ] || CONFIG="./.mcp.json"
        ;;
    vscode)
        TOPKEY="servers"
        ENTRY_TYPE="stdio"
        RESTART='restart VS Code, or run "MCP: List Servers" and restart vw-mcp, so .vscode/mcp.json is re-read.'
        [ -n "$CONFIG" ] || CONFIG="./.vscode/mcp.json"
        ;;
    copilot-cli)
        TOPKEY="mcpServers"
        ENTRY_TYPE=""
        RESTART='restart the Copilot CLI session so ~/.copilot/mcp-config.json is re-read.'
        [ -n "$CONFIG" ] || CONFIG="$HOME/.copilot/mcp-config.json"
        ;;
    gemini-cli)
        TOPKEY="mcpServers"
        ENTRY_TYPE=""
        RESTART='start Gemini CLI again so ~/.gemini/settings.json is re-read.'
        [ -n "$CONFIG" ] || CONFIG="$HOME/.gemini/settings.json"
        ;;
    *)
        GUIDE_NAME=$HARNESS
        case "$HARNESS" in
            pi) GUIDE_NAME="pi-agent" ;;
        esac
        if [ -f "$PLUGIN_ROOT/harnesses/$GUIDE_NAME/INSTALL.md" ]; then
            printf 'install.sh: %s does not use a plain local JSON MCP config, so there is nothing this\n' "$HARNESS" >&2
            printf 'script can merge safely — it needs a non-JSON format or a non-local transport instead.\n' >&2
            printf 'Follow the harness guide: %s/harnesses/%s/INSTALL.md\n' "$PLUGIN_ROOT" "$GUIDE_NAME" >&2
            exit 2
        fi
        printf 'install.sh: unknown harness: %s\n' "$HARNESS" >&2
        printf 'supported harnesses: claude-desktop claude-code vscode copilot-cli gemini-cli\n' >&2
        printf 'other harnesses are documented in %s/harnesses/README.md\n' "$PLUGIN_ROOT" >&2
        exit 2
        ;;
esac

PLUGIN_ROOT=$(CDPATH= cd -- "$PLUGIN_ROOT" 2>/dev/null && pwd) || {
    printf 'install.sh: no such plugin directory: %s\n' "$PLUGIN_ROOT" >&2
    exit 2
}

command -v python3 >/dev/null 2>&1 || {
    printf 'install.sh: python3 is required to merge JSON without jq\n' >&2
    exit 1
}

VD_CONFIG_PATH=$CONFIG \
VD_TOPKEY=$TOPKEY \
VD_ENTRY_TYPE=$ENTRY_TYPE \
VD_PLUGIN_ROOT=$PLUGIN_ROOT \
VD_DATA=$DATA \
VD_DRY_RUN=$DRY_RUN \
python3 - <<'PY'
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

config = Path(os.environ["VD_CONFIG_PATH"])
topkey = os.environ["VD_TOPKEY"]
entry_type = os.environ.get("VD_ENTRY_TYPE", "")
root = os.environ["VD_PLUGIN_ROOT"].rstrip("/") or "/"
data = os.environ["VD_DATA"].rstrip("/") or "/"
dry_run = os.environ.get("VD_DRY_RUN") == "1"

entry = {
    "command": "sh",
    "args": [root + "/mcp/run.sh"],
}
if entry_type:
    entry["type"] = entry_type
entry["env"] = {
    "PLUGIN_DATA": data,
    "EDGAR_LOCAL_DATA_DIR": data + "/edgar",
    "EDGAR_HTTP_TIMEOUT": "30",
    "EDGAR_RATE_LIMIT_PER_SEC": "5",
    "UV_PROJECT_ENVIRONMENT": data + "/uv-env",
    "UV_CACHE_DIR": data + "/uv-cache",
    "UV_PYTHON_INSTALL_DIR": data + "/uv-python",
}

existed = config.exists()
payload = {}
if existed:
    try:
        loaded = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        loaded = None
    if not isinstance(loaded, dict):
        backup = config.with_name(
            config.name + ".bak-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        )
        if dry_run:
            sys.stderr.write(
                "warn: %s is not a usable JSON object; a real run would back it up to %s\n"
                % (config, backup)
            )
        else:
            shutil.copy2(config, backup)
            sys.stderr.write(
                "warn: %s is not a usable JSON object; backed up to %s\n"
                % (config, backup)
            )
    else:
        payload = loaded

section = payload.get(topkey)
if not isinstance(section, dict):
    if section is not None:
        sys.stderr.write(
            "warn: %s in %s is not an object; replacing it with a server map\n"
            % (topkey, config)
        )
    section = {}
    payload[topkey] = section
section["vw-mcp"] = entry

rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

if dry_run:
    sys.stdout.write(rendered)
    sys.exit(0)

parent = config.parent if str(config.parent) else Path(".")
parent.mkdir(parents=True, exist_ok=True)
handle_fd, tmp_name = tempfile.mkstemp(
    prefix="." + config.name + ".", suffix=".tmp", dir=str(parent)
)
try:
    with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
        handle.write(rendered)
    os.replace(tmp_name, config)
except BaseException:
    try:
        os.unlink(tmp_name)
    except OSError:
        pass
    raise

sys.stdout.write("wrote %s (%s)\n" % (config, "merged" if existed else "created"))
PY

if [ "$DRY_RUN" -eq 1 ]; then
    exit 0
fi

printf 'restart:  %s\n' "$RESTART"
printf 'identity: PLUGIN_DATA=%s %s/setup.sh example-user@gmail.com\n' "$DATA" "$PLUGIN_ROOT"
printf 'tools:    19 tools appear in the client once the server starts.\n'

if [ "$NO_SETUP" -eq 1 ]; then
    printf 'setup:    skipped (--no-setup)\n'
elif [ -n "$EMAIL" ]; then
    printf '\nrunning setup: PLUGIN_DATA=%s %s/setup.sh %s\n' "$DATA" "$PLUGIN_ROOT" "$EMAIL"
    if PLUGIN_DATA=$DATA "$PLUGIN_ROOT/setup.sh" "$EMAIL"; then
        printf 'setup:    ok\n'
    else
        printf 'install.sh: setup.sh failed; rerun PLUGIN_DATA=%s %s/setup.sh %s\n' "$DATA" "$PLUGIN_ROOT" "$EMAIL" >&2
        exit 1
    fi
fi
