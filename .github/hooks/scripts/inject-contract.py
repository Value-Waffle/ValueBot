#!/usr/bin/env python3
"""SubagentStart hook — inject the agent-handoff reporting contract.

Registered as a VS Code agent hook (``.github/hooks/agent-handoff.json`` ->
``SubagentStart``). Emits ``hookSpecificOutput.additionalContext`` carrying a
compact reminder of the reporting contract, so every subagent receives it
automatically instead of relying on 13 agent files restating the same rules
(which is how they drift).

Why this exists
---------------
The reporting contract already lives in one place, ``AGENTS.md`` → "Agent
handoff — per-delegation job cards", because ``AGENTS.md`` is loaded into every
subagent's context. This hook is the belt-and-braces layer for the two rules a
subagent is most likely to skip under load: **overwrite the pre-written stub**
and **append a checkpoint after each action**. Those are the two whose omission
destroys the orchestrator's ability to tell "still working" from "dead".

Confidence note (be honest)
---------------------------
The *documented* mechanism for context injection is
``hookSpecificOutput.additionalContext``. One source additionally described a
top-level ``additionalContext`` for ``SubagentStart`` specifically; we could not
verify which shape the harness honours. We emit the documented
``hookSpecificOutput`` form and log every invocation, so the next real subagent
delegation settles it empirically. If it turns out to be ignored, this hook is
inert — it cannot break anything, because the contract still reaches subagents
via ``AGENTS.md``.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_INVOCATION_LOG = ".hook-invocations.log"
_STDIN_LOG = ".hook-stdin.log"

# Deliberately short: this is a nudge, not a replacement for AGENTS.md. Long
# injected text would burn context on every delegation.
_CONTRACT = (
    "Agent-handoff reporting contract (authoritative detail: AGENTS.md -> "
    "\"Agent handoff — per-delegation job cards\"): "
    "(1) your report_path ALREADY EXISTS as an `in_progress` stub written by the "
    "orchestrator — OVERWRITE it atomically (temp + rename) when done, do not "
    "create it; "
    "(2) append a `checkpoint` event to events_path after each action and before "
    "any long-running command — this is the orchestrator's only heartbeat; "
    "(3) put the LITERAL command output in verification_results, never a "
    "paraphrase, and mark runtime claims VERIFIED <observed> or UNVERIFIED <why>; "
    "(4) if under 60% of actions are done and you are deep in the task, stop and "
    "write status \"partial\" with the next step; "
    "(5) never stop silently — on a blocker write status \"blocked\" or append a "
    "`question` event BEFORE returning."
)


def state_dir() -> Path:
    """Resolve the vault-root ``.agent_state`` dir from this script's location."""
    # .github/hooks/scripts/inject-contract.py -> parents[3] == vault root
    return Path(__file__).resolve().parents[3] / ".agent_state"


def read_stdin_payload() -> str:
    """Read the hook payload, never blocking and never raising."""
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


def agent_label(payload: object) -> str:
    """Best-effort agent name from the (undocumented) SubagentStart payload."""
    if isinstance(payload, dict):
        for key in ("agent_type", "agentType", "agent_name", "agentName"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return "unknown"


def main() -> int:
    raw = read_stdin_payload()
    directory = state_dir()

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except (ValueError, TypeError):
        payload = {}

    append_json_line(
        directory / _INVOCATION_LOG,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "hook": "SubagentStart",
            "agent": agent_label(payload),
        },
    )
    if raw:
        append_json_line(directory / _STDIN_LOG, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "hook": "SubagentStart",
            "payload": raw,
        })

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": _CONTRACT,
        }
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
