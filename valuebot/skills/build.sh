#!/bin/sh
# Package each valuebot skill as an installable .skill archive for the Claude app.
#
# A skill install takes one skill, not a bundle of five, so this writes one
# archive per skill. The container format is a ZIP; the `.skill` extension is
# used because that is what the app ships its own bundled skills as
# (a `docx.skill` entry is part of the installed bundle).
#
# Each archive holds one top-level directory named after the skill, with
# SKILL.md inside it (`<skill>/SKILL.md`), matching the shape the app's own
# bundled skills use. Use:
#
#   sh skills/build.sh                     # writes dist/skills/<skill>.skill
#   sh skills/build.sh --out DIR           # writes DIR/<skill>.skill
#   sh skills/build.sh --dry-run           # show what would be packaged
#
# No `zip` binary is required: the archives are written with Python's zipfile.

set -eu

usage() {
    cat <<'EOF'
usage: sh skills/build.sh [--out DIR] [--dry-run]

  --out DIR    write the .skill archives to DIR (default: dist/skills)
  --dry-run    print each skill's frontmatter name and description and exit
EOF
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

OUT_DIR="$PLUGIN_ROOT/dist/skills"
DRY_RUN=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --out)
            if [ "$#" -lt 2 ]; then
                printf 'skills-build: --out needs a directory\n' >&2
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
            printf 'skills-build: unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

# Read `name` and `description` from a SKILL.md frontmatter block. Handles the
# plain (unquoted) scalars this repository uses, including indented
# continuation lines, and strips surrounding quotes when present.
read_frontmatter() {
    python3 - "$1" <<'PY'
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as stream:
    lines = stream.read().splitlines()

if not lines or lines[0].strip() != "---":
    print("skills-build: no YAML frontmatter in %s" % path, file=sys.stderr)
    sys.exit(1)

values = {}
key = None
for line in lines[1:]:
    if line.strip() == "---":
        break
    if not line.strip():
        key = None
        continue
    if line[0] in " \t":
        if key:
            values[key] = (values[key] + " " + line.strip()).strip()
        continue
    name, _, value = line.partition(":")
    if not _:
        key = None
        continue
    key = name.strip()
    values[key] = value.strip()

for field in ("name", "description"):
    value = values.get(field, "")
    if len(value) > 1 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    if not value:
        print("skills-build: missing `%s` in %s" % (field, path), file=sys.stderr)
        sys.exit(1)
    print(value)
PY
}

# Write one archive: the skill directory's contents, prefixed with the skill
# name, so the archive holds `<skill>/SKILL.md` rather than `SKILL.md` at the
# top level.
write_zip() {
    python3 - "$1" "$2" "$3" <<'PY'
import os
import sys
import zipfile

skill_dir, archive_path, arc_root = sys.argv[1], sys.argv[2], sys.argv[3]
EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_NAMES = {".DS_Store"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo")

members = []
for base, dirs, files in os.walk(skill_dir):
    dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
    for name in sorted(files):
        if name in EXCLUDED_NAMES or name.endswith(EXCLUDED_SUFFIXES):
            continue
        full = os.path.join(base, name)
        members.append((full, os.path.relpath(full, skill_dir)))

with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for full, rel in members:
        archive.write(full, os.path.join(arc_root, rel))
PY
}

SKILL_COUNT=0
BUILT_COUNT=0

for skill_path in "$SCRIPT_DIR"/*/; do
    [ -d "$skill_path" ] || continue
    skill_dir=${skill_path%/}
    skill_name=${skill_dir##*/}

    [ -f "$skill_dir/SKILL.md" ] || continue

    if [ "$DRY_RUN" -eq 1 ]; then
        fm=$(read_frontmatter "$skill_dir/SKILL.md")
        fm_name=$(printf '%s\n' "$fm" | sed -n '1p')
        fm_desc=$(printf '%s\n' "$fm" | sed -n '2p')
        SKILL_COUNT=$((SKILL_COUNT + 1))
        printf '%s\n' "$skill_name"
        printf '  name: %s\n' "$fm_name"
        printf '  description: %s\n' "$fm_desc"
        continue
    fi

    fm=$(read_frontmatter "$skill_dir/SKILL.md")
    fm_name=$(printf '%s\n' "$fm" | sed -n '1p')
    if [ "$fm_name" != "$skill_name" ]; then
        printf 'skills-build: warning: %s has frontmatter name %s\n' \
            "$skill_dir/SKILL.md" "$fm_name" >&2
    fi

    mkdir -p "$OUT_DIR"
    SKILL_COUNT=$((SKILL_COUNT + 1))
    write_zip "$skill_dir" "$OUT_DIR/$skill_name.skill" "$skill_name"
    BUILT_COUNT=$((BUILT_COUNT + 1))
    printf 'skills-build: wrote %s\n' "$OUT_DIR/$skill_name.skill"
done

if [ "$SKILL_COUNT" -eq 0 ]; then
    printf 'skills-build: no skill directories with a SKILL.md under %s\n' \
        "$SCRIPT_DIR" >&2
    exit 1
fi

if [ "$DRY_RUN" -eq 1 ]; then
    printf 'skills-build: dry run, %s skill(s) would be packaged; nothing written\n' \
        "$SKILL_COUNT"
    exit 0
fi

printf 'skills-build: packaged %s skill(s) into %s\n' \
    "$BUILT_COUNT" "$OUT_DIR"
