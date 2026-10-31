#!/bin/sh
# Cut a valuebot release: bump both manifests, update CHANGELOG.md, commit, tag.
#
# Usage: ./scripts/release.sh <version> [--dry-run]
#   version   SemVer string without the leading "v", e.g. 0.3.0
#   --dry-run preview the edits and exit without writing anything
#
# This script never pushes. It only writes local commits and an annotated tag.

set -eu

VERSION="${1:-}"
DRY_RUN=0
if [ "${2:-}" = "--dry-run" ]; then
    DRY_RUN=1
fi

if [ -z "$VERSION" ]; then
    printf 'usage: %s <version> [--dry-run]\n' "$0" >&2
    exit 2
fi

case "$VERSION" in
    [0-9]*.[0-9]*.[0-9]*) ;;
    *) printf 'release: version must look like MAJOR.MINOR.PATCH: %s\n' "$VERSION" >&2; exit 2 ;;
esac

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PLUGIN="$ROOT/valuebot/plugin.json"
MANIFEST="$ROOT/valuebot/mcpb/manifest.json"
CHANGELOG="$ROOT/CHANGELOG.md"

for f in "$PLUGIN" "$MANIFEST" "$CHANGELOG"; do
    [ -f "$f" ] || { printf 'release: missing %s\n' "$f" >&2; exit 1; }
done

# Refuse to cut a release from a dirty tree.
if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
    printf 'release: working tree is not clean; commit or stash first\n' >&2
    exit 1
fi

DATE=$(date +%Y-%m-%d)

printf 'release: bumping to %s (date %s)\n' "$VERSION" "$DATE"
printf '  plugin.json   %s\n' "$PLUGIN"
printf '  manifest.json %s\n' "$MANIFEST"

if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] python edits would run here; no files changed\n'
    exit 0
fi

python3 - "$PLUGIN" "$MANIFEST" "$VERSION" <<'PY'
import json, pathlib, sys
plugin_path, manifest_path, version = sys.argv[1], sys.argv[2], sys.argv[3]
for p in (plugin_path, manifest_path):
    path = pathlib.Path(p)
    data = json.loads(path.read_text())
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n")
PY

# Prepend a dated section under [Unreleased]'s heading position: insert a new
# released section right after the "## [Unreleased]" block header line.
python3 - "$CHANGELOG" "$VERSION" "$DATE" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
version, date = sys.argv[2], sys.argv[3]
text = path.read_text()
header = "## [Unreleased]\n"
if header not in text:
    raise SystemExit("CHANGELOG.md has no '## [Unreleased]' section")
new_section = (
    f"\n## [{version}] - {date}\n\n"
    "### Changed\n\n"
    "- Release " + version + ".\n"
)
# Insert the new released section immediately after the Unreleased header line.
text = text.replace(header, header + new_section, 1)
# Add the comparison link if the [Unreleased] link exists.
old_link = f"[Unreleased]: https://github.com/Value-Waffle/ValueBot/compare/v{version}...HEAD"
# best-effort: leave links as-is
path.write_text(text)
PY

git -C "$ROOT" add valuebot/plugin.json valuebot/mcpb/manifest.json CHANGELOG.md
git -C "$ROOT" commit -q -m "chore(release): v${VERSION}"
git -C "$ROOT" tag -a "v${VERSION}" -m "valuebot v${VERSION}"

printf 'release: committed and tagged v%s\n' "$VERSION"
printf 'release: push with `git push origin main && git push origin v%s`\n' "$VERSION"