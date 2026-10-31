# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Wiki published as a git submodule at `wiki/` (https://github.com/Value-Waffle/ValueBot.wiki.git).
- Release process: tag-driven GitHub Releases workflow, `RELEASING.md`, and `scripts/release.sh`.
- Root-level `.gitignore` (Python template plus workspace-specific ignores).

### Changed
- Removed the stale `ci.yml` workflow that referenced a non-existent `board-games/` tree; `valuebot.yml` remains the CI entry point.

### Security
- Rotated the GitHub personal access token that had been embedded in `.github/.git/config` (see `SECURITY-AUDIT.md`). Treat that token as compromised and rotate it again if it is still in use anywhere.

## [0.2.0] - 2026-10-31

### Added
- valuebot v2 MCP server (core, fundamentals, analysis, reports, thesis modules; 19 tools).
- Claude Desktop MCP bundle build (`valuebot/mcpb/build.sh`).
- Multi-harness support (LibreChat, Claude Code, Codex, Copilot, ChatGPT, DeepSeek, Gemini CLI, Hermes, OpenCode, Open WebUI, Pi).

[Unreleased]: https://github.com/Value-Waffle/ValueBot/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Value-Waffle/ValueBot/releases/tag/v0.2.0