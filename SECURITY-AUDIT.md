# Security Audit — librechat-plugin (valuebot)

**Scope:** repository root, `valuebot/`, `wiki/`, `architecture/`, `.github/`.
**Date:** 2026-10-31
**Method:** manual review of Python source, shell scripts, configuration, workflows, and documentation; regex secret scan of the working tree (excluding `.venv`, `.dev-venv`, `.agent_state`, `.git`).
**Tools available:** none of gitleaks/trufflehog/semgrep/bandit/pip-audit were installed; all checks were performed with `grep`/`read` plus the project's own `precommit-secrets-scan.sh`.

**Remotes (canonical):** https://github.com/Value-Waffle/ValueBot.git · https://github.com/Value-Waffle/ValueBot.wiki.git
**Plugin version:** 0.2.0 (`valuebot/plugin.json`, `valuebot/mcpb/manifest.json`)

## Summary

| Severity | Count |
|:---|---:|
| Critical | 1 |
| High | 4 |
| Medium | 4 |
| Low / Info | 7 |

One real secret was found and removed from the tree (see C-1). **You must rotate that token** even though it has been moved out of the working tree, because it may already be in any clone, backup, or CI log.

## Critical

### C-1 — GitHub personal access token embedded in a nested `.git/config`

- **File:** `.github/.git/config` (now moved to `/private/var/folders/…/opencode/git-backups-20261031/github-dot-git/config` for preservation; the working tree no longer contains it)
- **Evidence:** `origin https://ramK458:<REDACTED_PAT>@github.com/ramK458/the-gremlins.git`
- **Why it matters:** the token (`ghp_…`, classic PAT) grants access to `ramK458/the-gremlins` and is readable by anything with filesystem access to this checkout. It was stored in plaintext inside a nested clone of an unrelated repository that lived under `.github/`. Because `.github/` is part of this repository's tree, any `git add` of that directory would have published the credential.
- **Status:** the nested `.git` directory has been moved out of the tree so `.github/` can be committed as ordinary files. **Action required from the owner:** revoke/rotate the token at https://github.com/settings/tokens, then update any automation that referenced it. Do not reuse it.

## High

### H-1 — Nested git repositories blocked a clean single-repo layout

- **Files:** `valuebot/.git/` (empty `git init`, no commits) and `.github/.git/` (clone of `ramK458/the-gremlins`).
- **Why it matters:** both prevented `git add` of `valuebot/` and `.github/` ("does not have a commit checked out" / "embedded git repository"), so the workspace could not be versioned as one repository until they were removed.
- **Status:** both `.git` directories moved to the backup folder above; their file contents are preserved. Re-create them only if you need the nested history.

### H-2 — Broken CI workflow referenced a non-existent `board-games/` tree

- **File:** `.github/workflows/ci.yml`
- **Evidence:** `working-directory: board-games`, `pip install -r backend/requirements.txt`, `working-directory: board-games/frontend`.
- **Why it matters:** every push and PR would have triggered a job that fails immediately because those paths do not exist in this repository. The real pipeline is `.github/workflows/valuebot.yml`.
- **Status:** `ci.yml` deleted. The valuebot workflow remains the CI entry point.

### H-3 — Broken relative links in harness install guides

- **Files:** 10 files under `valuebot/harnesses/*/INSTALL.md` (and `codex/AGENTS.md`), 16 occurrences.
- **Evidence:** `../../../docs/users/09-multi-harness.md` (one `../` too many from `valuebot/harnesses/<name>/`).
- **Why it matters:** the valuebot.yml package job runs a link checker that fails the build on any broken relative link, so CI would have been red.
- **Status:** corrected to `../../docs/users/09-multi-harness.md`.

### H-4 — Branding / remote inconsistency across documentation

- **Scope:** 117 occurrences of `github.com/valuewaffle/valuebot` across the tree vs. the canonical `github.com/Value-Waffle/ValueBot`.
- **Why it matters:** GitHub URLs are case-insensitive so links resolve, but the mixed casing is confusing and any tooling that compares strings (release notes, docs generators) will see two different projects. Also `valuebot/plugin.json` and `valuebot/mcpb/manifest.json` still carry `https://github.com/valuewaffle/valuebot` as the author URL.
- **Status:** documented only. Recommend a single normalization pass (lowercase `valuewaffle` → `Value-Waffle`, `valuebot` → `ValueBot`) in a follow-up PR, plus updating the two manifest author URLs.

## Medium

### M-1 — Artifact viewer echoes exception text to HTTP clients

- **File:** `valuebot/mcp/core/artifact_viewer.py:108-118` (the `except (TypeError, ValueError)` branch returns `f"invalid_argument: {exc}"`).
- **Evidence:** `self._send(409, "text/plain; charset=utf-8", f"invalid_argument: {exc}")`
- **Why it matters:** a malformed request could surface an exception message (and potentially a filesystem path) to anyone holding the viewer token. The viewer is token-gated and defaults to `127.0.0.1`, so exposure is limited, but the message should be a fixed string.
- **Fix:** replace `{exc}` with a generic `"invalid argument"` message.

### M-2 — `install.sh` interpolates an email into a `printf` format string

- **File:** `valuebot/install.sh:301`
- **Evidence:** `printf '\nrunning setup: PLUGIN_DATA=%s %s/setup.sh %s\n' "$DATA" "$PLUGIN_ROOT" "$EMAIL"`
- **Why it matters:** if `--email` contains `%` sequences the output is mis-formatted. The value is passed quoted to `setup.sh` (safe), so this is cosmetic, but the printf should use `%s` for the email (it already does for the others; the email is the third `%s`, which is fine — the real issue is only if a future edit drops the format specifier). Re-check before release.
- **Fix:** keep the email strictly inside a `%s` placeholder; never interpolate it into the format string.

### M-3 — No `permissions:` block on the main CI workflow (fixed)

- **File:** `.github/workflows/valuebot.yml`
- **Why it matters:** without an explicit `permissions:` block the default `GITHUB_TOKEN` granted to the workflow has broad (write) scope, increasing blast radius if a step is compromised.
- **Status:** added `permissions: contents: read` (least privilege). The release workflow keeps `contents: write` because it must create releases.

### M-4 — Link checker has two regex false positives

- **Files:** `valuebot/docs/dev/08-deployment.md:48`, `valuebot/docs/users/08-troubleshooting-and-faq.md:51`
- **Evidence:** inline regex `` `^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$` `` is parsed as a markdown link `[a-z0-9](?:…)`.
- **Why it matters:** CI noise; the package job's link check reports 2 broken links that are not actually broken.
- **Fix options:** escape the bracket, or adjust the checker's regex to ignore code spans. Recommend the latter in `valuebot.yml`.

## Low / Info

### L-1 — `precommit-secrets-scan.sh` has a high false-positive rate

- **File:** `.github/skills/git-skills/scripts/precommit-secrets-scan.sh`
- **Evidence:** it matches generic `token =`, `password =`, `api_key =` lines, so it flags variable names and placeholder keys (e.g. `apiKey: 'user_provided'`, `_token = _token`).
- **Why it matters:** alert fatigue; real leaks become easy to ignore. Consider tightening to require a value of sufficient length/entropy, or scoping to staged diff hunks only.

### L-2 — Documentation says "5 modules" but the server ships 6

- **Files:** `README.md`, `wiki/Home.md`, `wiki/20-Features-Overview.md` (and others) state "5 modules: core, fundamentals, analysis, reports, thesis".
- **Evidence:** `valuebot/mcp/modules/` contains `analysis`, `calendar`, `fundamentals`, `price_action`, `reports`, `thesis` (calendar and price_action are additional).
- **Why it matters:** minor documentation drift; a reader looking for the calendar/price-action tools will not find them in the overview.
- **Fix:** either document the two extra modules or state explicitly that they are optional/experimental.

### L-3 — GitHub Actions are pinned to major tags, not commit SHAs

- **Files:** `.github/workflows/valuebot.yml`, `.github/workflows/release.yml`
- **Evidence:** `actions/checkout@v4`, `actions/setup-python@v5`, `softprops/action-gh-release@v2`.
- **Why it matters:** a compromised or re-tagged action could run in CI. Acceptable for this project's threat model, but SHA pinning is the stronger posture. Recommend pinning once a release cadence is established.

### L-4 — Dependencies are loosely bounded

- **File:** `valuebot/requirements.txt`
- **Evidence:** `mcp>=2.2.0`, `requests>=2.31`, `beautifulsoup4>=4.14,<5` (no upper bound on mcp/requests).
- **Why it matters:** a future breaking release of an unbounded dependency could break installs. Some (edgartools, sec-parser) are correctly bounded.
- **Fix:** add upper bounds consistent with tested versions; run `pip-audit` in CI once a network-enabled job is available (pip-audit was not installed locally, so no CVE check was performed).

### L-5 — `.agent_state/` holds 193 orchestration files (now gitignored)

- **Path:** `.agent_state/`
- **Why it matters:** per-delegation job cards and reports may contain task context, paths, and (in principle) secrets pasted into prompts. They are now ignored by the root `.gitignore`; verify they never enter a commit (`git status` should not list them).

### L-6 — Large local environments live inside the tree (gitignored)

- **Paths:** `valuebot/.venv/` (~394 MB), `valuebot/mcp/.dev-venv/`.
- **Why it matters:** not a vulnerability, but they must stay ignored. Confirm with `git check-ignore` before any commit.

### L-7 — No other secrets found

- **Method:** regex scan for `ghp_`, `gho_`, `github_pat_`, `sk-`, `AKIA…`, `-----BEGIN … PRIVATE KEY-----`, `xox…`, `AIza…`, and high-entropy JWT-like tokens across the working tree (excluding `.venv`, `.dev-venv`, `.agent_state`, `.git`).
- **Result:** no matches. The only real secret was C-1.
- **Caveat:** regex scanning cannot catch all secret formats (e.g. short API keys, database passwords). Manual review of shell scripts and config found no additional credentials.

## Items checked and found clean

- No `shell=True` / `os.system` / `eval` / `exec` in first-party Python (`valuebot/mcp`, `valuebot/tests`).
- No `pickle` or unsafe `yaml.load` usage.
- SQL is parameterized; the two f-string SQL fragments build only fixed clause strings (`where`, `base`), not user input.
- Artifact viewer defaults to `127.0.0.1`; token comparison uses `secrets.compare_digest`; HTML is escaped via `html.escape`.
- `identity.json` is written with mode `0600` via an atomic temp-file + `os.replace`.
- SEC User-Agent is required (no silent default); placeholder domains are rejected.
- HTTP fetches go only to SEC endpoints (`data.sec.gov`, `sec.gov`) with a timeout; no user-controlled URLs.
- No path traversal found in artifact resolution (resolution goes through `core.citations.resolve_citation`).

## Recommended follow-up actions

1. Rotate the token from C-1 immediately.
2. Normalize branding (H-4) and update manifest author URLs.
3. Add `permissions: contents: read` is done (M-3); consider SHA-pinning actions (L-3).
4. Run `pip-audit` in CI and add upper bounds (L-4).
5. Tighten the link checker for code spans (M-4) and the precommit secret scan (L-1).
6. Document the extra `calendar` / `price_action` modules (L-2).