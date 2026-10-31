# Releasing valuebot

valuebot uses a single version number that must agree in three places:

- `valuebot/plugin.json` (`$.version`)
- `valuebot/mcpb/manifest.json` (`$.version`)
- the git tag (`v<version>`, e.g. `v0.2.0`)

The CI package job in `.github/workflows/valuebot.yml` already checks that the
two manifests agree. The release workflow additionally checks that the tag
matches both.

## Cutting a release

1. Decide the next version (SemVer: `MAJOR.MINOR.PATCH`).
2. Run the helper, which bumps both manifests, prepends a dated section to
   `CHANGELOG.md`, commits, and creates the annotated tag locally (it does
   **not** push):

   ```sh
   ./scripts/release.sh 0.3.0
   ```

   Use `--dry-run` to preview the edits without writing anything:

   ```sh
   ./scripts/release.sh 0.3.0 --dry-run
   ```

3. Review the diff and the tag:

   ```sh
   git show --stat HEAD
   git show v0.3.0 --no-patch
   ```

4. Push the commit **and** the tag (this is the only step that touches the
   remote, and it is deliberately manual):

   ```sh
   git push origin main
   git push origin v0.3.0
   ```

   Pushing the tag triggers `.github/workflows/release.yml`, which:

   - re-runs the test suite,
   - verifies the tag matches both manifests,
   - builds `valuebot-<version>.mcpb` via `valuebot/mcpb/build.sh`,
   - creates a GitHub Release with the changelog section for that version as
     the body, attaching the bundle and its SHA-256.

## Wiki submodule

The wiki lives in a separate repository and is attached as a submodule at
`wiki/`. When cutting a release, make sure the wiki submodule is at the
commit you want shipped and that `.gitmodules` records `branch = master`:

```sh
git submodule status
git -C wiki log --oneline -1
```

If the wiki moved, update the submodule pointer in the main repo and commit
it as part of the release.

## Rotating the submodule

If the wiki remote ever changes, update `.gitmodules` and run:

```sh
git submodule sync
git submodule update --init --recursive
```

## "Don't push yet"

These instructions never push. All remote writes are explicit, manual commands
above. CI runs on push/PR; releases run on tag push.