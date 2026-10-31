#!/usr/bin/env python3
"""PreToolUse guard — deterministically block a small set of destructive commands.

Registered as a VS Code agent hook (``.github/hooks/agent-handoff.json`` ->
``PreToolUse``). Emits a ``permissionDecision: "deny"`` for commands that are
known-destructive in THIS workspace, and stays silent (implicit allow)
otherwise.

Why this exists
---------------
Instructions can only *discourage* a dangerous command. This hook makes a
curated few *impossible*. The motivating incident: an agent nearly ran
``pkill -f "electron ."``, which would have killed the user's own running
dev-engine app. Narrow kills of agent-owned test instances use distinctive
tokens (e.g. ``de-verify-p34``) and are deliberately still allowed.

Design rules (deliberate, see the tests)
----------------------------------------
1. **Fail-open.** Any error, unparseable payload, or missing field results in
   NO output — i.e. the tool call proceeds. A guard that blocks everything
   because it broke would be worse than no guard. Only an explicit positive
   match denies.
2. **Scan the executable command, not agent prose.** The real ``PreToolUse`` payload
   (captured 2026-09-13) is ``{tool_name: "run_in_terminal", tool_input:
   {command, explanation, goal, mode}}``. Only ``command`` executes;
   ``explanation``/``goal`` are prose an agent writes *about* it. Scanning prose
   caused two live false positives: an agent was blocked for mentioning a
   deny-listed token in a case label, and blocked again when writing a **report
   that quoted this guard's own denial message** — i.e. the guard made its own
   blocks unreportable. So: scan ``tool_input.command`` when present, and fall
   back to scanning non-prose values only for an unrecognised tool shape.
3. **Match at command position.** The kill pattern requires ``pkill``/``killall``
   to start a command (after ``^``, ``;``, ``&&``, ``|``, or ``sudo``), so text
   that merely *mentions* the pattern is not denied.
3. **A tight list, not a shell-safety engine.** A broad rule would produce
   false positives and block legitimate work. Add patterns only for hazards we
   have actually hit or can name precisely.
4. **Auditable.** Every invocation is appended to ``.hook-invocations.log`` and
   every raw payload dumped to ``.hook-stdin.log``, so the undocumented
   ``PreToolUse`` schema becomes learnable from real traffic.

Scope honesty — what this is NOT
--------------------------------
This is an **accident brake, not a security boundary**. Anchoring every pattern
at command position means a plainly-written reflexive command (the real threat:
an agent reaching for a broad ``pkill``) is caught, while a deliberately
obfuscated one (``bash -c "rm -rf /"``) is not. That trade is deliberate: the
false positive it prevents is worse in practice, because an over-broad guard
blocks the agent from *reporting* what it was blocked from doing.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_INVOCATION_LOG = ".hook-invocations.log"
_STDIN_LOG = ".hook-stdin.log"

# Keys that could hold an executable command, for tool shapes we have not seen.
_COMMAND_KEYS = frozenset({"command", "cmd", "command_line", "commandLine", "script", "run"})

# A command "position": start of the string, or just after a shell separator or
# `sudo`. Every deny-list pattern is anchored with this. Without it, text that
# merely MENTIONS a pattern — a banner, a case label, or a report quoting a
# denial — is itself denied, which made a block unreportable (defect FP-3).
_CMD_POS = r"(?:^|[;&|]\s*|\bsudo\s+)"


def command_texts(payload: object) -> list[str]:
    """Return the strings that can actually EXECUTE, not prose or file content.

    See design rule 2. Three tiers, each narrower than the last:

    1. The known terminal-tool shape (captured 2026-09-13) -> ``tool_input.command``.
    2. An unseen tool shape -> only keys that could hold a command
       (``_COMMAND_KEYS``), so a write/edit tool's ``content`` is NEVER scanned.
    3. Anything else -> ``[]`` (fail open).

    Tier 3 matters: scanning unknown payloads wholesale means an agent cannot even
    *write* a file that mentions a deny-listed pattern — the guard would make its
    own blocks unreportable, which is the specific defect (FP-3) this replaced.
    A guard that blocks real work gets removed, and then it protects nothing.
    """
    if not isinstance(payload, dict):
        return []
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    command = tool_input.get("command")
    if isinstance(command, str):
        return [command]
    return [
        text
        for key, value in tool_input.items()
        if key in _COMMAND_KEYS
        for text in iter_strings(value)
    ]


# Curated deny-list: (compiled regex, human reason). Keep small and precise.
# Each entry targets a hazard that is catastrophic and cannot be undone.
_DANGEROUS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(_CMD_POS + r"(?:pkill|killall)\b[^\n;|&]*\belectron\b", re.IGNORECASE),
        "would kill the user's own Electron instances (this agent runs inside one). "
        "Use a narrow match on a unique token instead, e.g. pkill -f \"de-verify-<id>\".",
    ),
    (
        # `/*` precedes `/` so the wildcard case is not shadowed, and the
        # trailing slash is handled by a lookahead — without it `rm -rf $HOME/`
        # slipped through the boundary check.
        re.compile(
            _CMD_POS
            + r"rm\s+(?:-[a-zA-Z]*[rR][a-zA-Z]*\s+)+"
            + r"(?:/\*|/|~|\$HOME|\*)/?(?=\s|$|;|&|\|)"
        ),
        "recursive delete of a root/home/wildcard path.",
    ),
    (
        re.compile(_CMD_POS + r":\s*\(\s*\)\s*\{.*\|.*&.*\}\s*;?\s*:"),
        "shell fork bomb.",
    ),
    (
        re.compile(_CMD_POS + r"dd\b[^\n;|&]*\bof=/dev/(?:disk|rdisk|sd|nvme)"),
        "raw write to a block device.",
    ),
    (
        re.compile(_CMD_POS + r"mkfs(?:\.\w+)?\b"),
        "would format a filesystem.",
    ),
]


def state_dir() -> Path:
    """Resolve the vault-root ``.agent_state`` dir from this script's location."""
    # .github/hooks/scripts/guard-commands.py -> parents[3] == vault root
    return Path(__file__).resolve().parents[3] / ".agent_state"


def read_stdin_payload() -> str:
    """Read the hook payload, never blocking and never raising.

    Guarded by ``isatty()``: an unconditional ``read()`` blocks forever when the
    script is run interactively (no stdin looks identical to empty stdin).
    """
    stream = sys.stdin
    if stream is None:
        return ""
    try:
        if stream.isatty():
            return ""
    except (OSError, ValueError):
        return ""
    try:
        return stream.read()
    except (OSError, ValueError):
        return ""


def append_json_line(path: Path, payload: object) -> None:
    """Append one JSON line to *path*, swallowing any failure (never crash)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def iter_strings(value: object):
    """Yield every string contained in *value*, recursing into dicts/lists.

    Used instead of assuming a field name, so the guard works whatever the real
    ``PreToolUse`` payload looks like.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_strings(item)


def find_violation(payload: object) -> tuple[str, str] | None:
    """Return ``(matched_text, reason)`` for the first deny-list hit, else None.

    Only executable command text is inspected (see ``command_texts``); the first
    match in deny-list order wins (the list is ordered most-specific first).
    """
    candidates = command_texts(payload)
    for pattern, reason in _DANGEROUS:
        for text in candidates:
            match = pattern.search(text)
            if match:
                return match.group(0), reason
    return None


def main() -> int:
    raw = read_stdin_payload()
    directory = state_dir()

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except (ValueError, TypeError):
        payload = {}

    violation = find_violation(payload) if payload else None

    append_json_line(
        directory / _INVOCATION_LOG,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "hook": "PreToolUse",
            "decision": "deny" if violation else "allow",
        },
    )
    if raw:
        append_json_line(directory / _STDIN_LOG, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "hook": "PreToolUse",
            "payload": raw,
        })

    if violation:
        matched, reason = violation
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Blocked by .github/hooks/scripts/guard-commands.py: "
                    f"'{matched}' is deny-listed — {reason}"
                ),
            }
        }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
