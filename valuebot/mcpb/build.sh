#!/bin/sh
# Build a Claude Desktop MCP Bundle (.mcpb) for valuebot.
#
# The bundle is a plain ZIP archive with the .mcpb extension and manifest.json
# at the archive root. Use:
#
#   sh mcpb/build.sh                 # writes dist/valuebot-<version>.mcpb
#   sh mcpb/build.sh --out DIR       # writes DIR/valuebot-<version>.mcpb
#   sh mcpb/build.sh --dry-run       # list the files that would be included
#
# No `zip` binary is required: the archive is written with Python's zipfile.

set -eu

usage() {
    cat <<'EOF'
usage: sh mcpb/build.sh [--out DIR] [--dry-run]

  --out DIR    write the bundle to DIR (default: dist)
  --dry-run    list the files that would be included and exit
EOF
}

OUT_DIR="dist"
DRY_RUN=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --out)
            if [ "$#" -lt 2 ]; then
                printf 'mcpb-build: --out needs a directory\n' >&2
                exit 2
            fi
            OUT_DIR=$2
            shift 2
            ;;
        --out=*)
            OUT_DIR=${1#--out=}
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
            printf 'mcpb-build: unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
MANIFEST="$SCRIPT_DIR/manifest.json"

if [ ! -f "$MANIFEST" ]; then
    printf 'mcpb-build: missing manifest: %s\n' "$MANIFEST" >&2
    exit 1
fi

# The version lives only in the manifest, so bumping it can never drift from
# the produced filename.
VERSION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$MANIFEST")
if [ -z "$VERSION" ]; then
    printf 'mcpb-build: could not read version from %s\n' "$MANIFEST" >&2
    exit 1
fi

BUNDLE_NAME="valuebot-$VERSION.mcpb"

# Collect the files to include: manifest.json (renamed) plus the payload
# directories, filtered against the exclusion list. Paths are emitted
# relative to the plugin root, one per line.
list_files() {
    python3 - "$PLUGIN_ROOT" "$MANIFEST" <<'PY'
import os
import sys

root = os.path.abspath(sys.argv[1])
manifest = os.path.abspath(sys.argv[2])

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".dev-venv",
    ".pytest_cache",
    ".test-data",
    "__pycache__",
    "tests",
    "docs",
    "harnesses",
    "agent-builder-exports",
    "node_modules",
}
EXCLUDED_SUFFIXES = (".sqlite", ".mcpb", ".pyc", ".pyo")
EXCLUDED_NAMES = {".DS_Store"}

PAYLOAD = ["mcp", "skills"]
PAYLOAD_FILES = ["requirements.txt", "LICENSE", "README.md"]


def excluded(name):
    if name in EXCLUDED_NAMES or name in EXCLUDED_DIRS:
        return True
    if name.startswith(".uv-"):
        return True
    if name.endswith(EXCLUDED_SUFFIXES):
        return True
    return False


def walk(path):
    for entry in sorted(os.listdir(path)):
        if excluded(entry):
            continue
        full = os.path.join(path, entry)
        if os.path.isdir(full):
            for child in walk(full):
                yield child
        else:
            yield os.path.relpath(full, root)


print(os.path.relpath(manifest, root))
for name in PAYLOAD_FILES:
    full = os.path.join(root, name)
    if os.path.exists(full):
        print(name)
for name in PAYLOAD:
    full = os.path.join(root, name)
    if os.path.isdir(full):
        for rel in walk(full):
            print(rel)
PY
}

FILES=$(list_files)

if [ "$DRY_RUN" -eq 1 ]; then
    printf 'mcpb-build: would build %s from %s files:\n' \
        "$BUNDLE_NAME" "$(printf '%s\n' "$FILES" | wc -l | tr -d ' ')"
    printf '%s\n' "$FILES" | while IFS= read -r name; do
        if [ "$name" = "mcpb/manifest.json" ]; then
            printf '%s -> manifest.json\n' "$name"
        else
            printf '%s\n' "$name"
        fi
    done
    exit 0
fi

mkdir -p "$OUT_DIR"
OUT_DIR=$(CDPATH= cd -- "$OUT_DIR" && pwd)
BUNDLE_PATH="$OUT_DIR/$BUNDLE_NAME"

STAGE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/valuebot-mcpb.XXXXXX")
trap 'rm -rf "$STAGE_DIR"' EXIT INT TERM

# Stage: manifest.json at the archive root, payload preserved as-is.
cp "$MANIFEST" "$STAGE_DIR/manifest.json"
printf '%s\n' "$FILES" | while IFS= read -r name; do
    [ -n "$name" ] || continue
    [ "$name" = "mcpb/manifest.json" ] && continue
    mkdir -p "$STAGE_DIR/$(dirname -- "$name")"
    cp "$PLUGIN_ROOT/$name" "$STAGE_DIR/$name"
done

python3 - "$STAGE_DIR" "$BUNDLE_PATH" <<'PY'
import os
import sys
import zipfile

stage, bundle = sys.argv[1], sys.argv[2]
if os.path.exists(bundle):
    os.remove(bundle)
with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
    for base, dirs, files in os.walk(stage):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(base, name)
            archive.write(full, os.path.relpath(full, stage))
PY

SIZE=$(wc -c < "$BUNDLE_PATH" | tr -d ' ')
printf 'mcpb-build: wrote %s (%s bytes)\n' "$BUNDLE_PATH" "$SIZE"
