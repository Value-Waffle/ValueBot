#!/usr/bin/env python3
"""Warn when a delegation's report is still ``in_progress``.

Runs as a VS Code agent hook (``.github/hooks/agent-handoff.json`` -> ``SubagentStop``
/ ``Stop``) and is also useful standalone::

    python3 .github/hooks/scripts/check-reports.py

Reads the hook JSON on stdin (deliberately schema-independent — the hook input
contract documents only "JSON on stdin", not its fields), appends one audit line
per run to ``.agent_state/.hook-invocations.log`` and dumps the raw stdin to
``.agent_state/.hook-stdin.log`` (both best-effort and never-crash), writes a
``systemMessage`` JSON object to stdout, and always exits ``0`` so it can never
block a session.

Observed stdin schema (captured 2026-09-13 from a real firing, not inferred)::

    # Stop
    {timestamp, hook_event_name, session_id, transcript_path,
     stop_hook_active, cwd}
    # SubagentStop additionally carries
    {agent_id, agent_type}

There is **no** ``report_path`` in the payload, which is why this script scans
``.agent_state/`` for pending stubs instead of reading a path from stdin.
Verified firing: VS Code's ``GitHub Copilot Chat Hooks.log`` shows
``[SubagentStop] ... agent_type: "Python Debugger" ... Completed (Success)``
with this script's ``systemMessage`` consumed by the harness.

Why this exists
---------------
A sub-agent cut off mid-loop returns **no chat output and no files** while the
harness still reports the call as successful. The orchestrator pre-creates the
report stub, so a report left at ``status: "in_progress"`` is the only reliable
evidence that a delegation started and did not finish. See ``AGENTS.md`` ->
"Agent handoff — per-delegation job cards".
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Report statuses that mean "the sub-agent has not finished".
_PENDING_STATUS = "in_progress"
_MAX_NAMES = 5

# How long a delegation may go WITHOUT a heartbeat before it is worth flagging.
# Liveness is measured from ``events.jsonl`` mtime, NOT from the stub's age: a
# long but healthy delegation keeps appending checkpoints, so it is never
# flagged no matter how long it runs. Only a delegation that has gone quiet is
# suspicious. (An age-only rule false-alarms on slow-but-fine delegations —
# the same class of mistake as the false alarm this replaced.)
_HEARTBEAT_TIMEOUT_SECONDS_DEFAULT = 300
_HEARTBEAT_TIMEOUT_ENV = "HOOK_HEARTBEAT_TIMEOUT_SECONDS"

# Permanent audit trails written into ``.agent_state/``. The names are
# deliberately dot-prefixed and must NOT match ``*.report.json`` so
# ``pending_reports()`` never mistakes them for delegation reports.
_INVOCATION_LOG = ".hook-invocations.log"
_STDIN_LOG = ".hook-stdin.log"


def state_dir() -> Path:
    """Resolve the vault-root ``.agent_state`` dir from this script's location."""
    # .github/hooks/scripts/check-reports.py -> parents[3] == vault root
    return Path(__file__).resolve().parents[3] / ".agent_state"


def pending_reports(directory: Path) -> list[str]:
    """Names of report files still marked in-progress (or unparseable)."""
    if not directory.is_dir():
        return []

    pending: list[str] = []
    for report in sorted(directory.glob("*.report.json")):
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A half-written report is itself a truncation symptom.
            pending.append(f"{report.name} (unparseable)")
            continue
        if isinstance(payload, dict) and payload.get("status") == _PENDING_STATUS:
            pending.append(report.name)
    return pending


def read_stdin_payload() -> str:
    """Read and return the hook's raw stdin payload, never blocking or raising.

    Guarded by ``isatty()``: an unconditional ``read()`` would block forever
    when the script is run interactively from a terminal (no stdin looks the
    same as empty stdin to ``read()``). Any read error is swallowed — a hook
    must never crash the session.
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


def drain_stdin() -> None:
    """Consume the hook payload so the writer never blocks on a full pipe."""
    read_stdin_payload()


def audit_log_path(directory: Path) -> Path:
    """Path of the permanent invocation audit log inside ``.agent_state/``."""
    return directory / _INVOCATION_LOG


def stdin_log_path(directory: Path) -> Path:
    """Path of the raw-stdin dump inside ``.agent_state/``."""
    return directory / _STDIN_LOG


def append_json_line(path: Path, payload: object) -> None:
    """Append one JSON line to *path*, swallowing any failure.

    A failing audit-log write must never crash the session, so every exception
    is deliberately ignored.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def event_hint(raw_stdin: str) -> str:
    """Best-effort name of the firing event from an undocumented payload."""
    try:
        data = json.loads(raw_stdin)
    except (ValueError, TypeError):
        return "unknown"
    if isinstance(data, dict):
        for key in ("hook_event_name", "hookEventName", "event", "eventName"):
            value = data.get(key)
            if value:
                return str(value)
    return "unknown"


def heartbeat_timeout_seconds() -> int:
    """Seconds without a heartbeat before a delegation is worth flagging.

    Overridable via ``HOOK_HEARTBEAT_TIMEOUT_SECONDS`` (tests and tuning use it);
    malformed or negative values fall back to the default rather than raising.
    """
    raw = os.environ.get(_HEARTBEAT_TIMEOUT_ENV)
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _HEARTBEAT_TIMEOUT_SECONDS_DEFAULT
    return value if value >= 0 else _HEARTBEAT_TIMEOUT_SECONDS_DEFAULT


def _age_seconds(path: Path, now_ts: float | None = None) -> float | None:
    """Seconds since *path* was last modified, or None if it does not exist."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return max(0.0, (now_ts if now_ts is not None else time.time()) - mtime)


def delegation_status(
    directory: Path, now_ts: float | None = None
) -> list[dict[str, object]]:
    """In-progress reports, each judged ALIVE or QUIET by its heartbeat.

    ``alive`` is derived from ``<id>.events.jsonl`` mtime — the subagent appends a
    ``checkpoint`` after every action, so a live delegation keeps touching that
    file. This is what separates "in flight" from "died", which a bare
    "is the report written?" test cannot do (both look identical: a stub exists).

    An unparseable report is always treated as not-alive: atomic writes mean a
    complete-looking-but-invalid file is a failure, not a delegation in progress.
    """
    if not directory.is_dir():
        return []

    timeout = heartbeat_timeout_seconds()
    out: list[dict[str, object]] = []
    for report in sorted(directory.glob("*.report.json")):
        name = report.name
        delegation_id = name[: -len(".report.json")]
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
            parseable = isinstance(payload, dict)
        except (OSError, ValueError):
            payload, parseable = None, False

        if not parseable:
            out.append({
                "name": name,
                "delegation_id": delegation_id,
                "alive": False,
                "reason": "unparseable",
                "quiet_seconds": None,
            })
            continue

        if not isinstance(payload, dict) or payload.get("status") != _PENDING_STATUS:
            continue  # finished (or a non-report shape) — nothing to flag

        quiet = _age_seconds(directory / f"{delegation_id}.events.jsonl", now_ts)
        alive = quiet is not None and quiet <= timeout
        out.append({
            "name": name,
            "delegation_id": delegation_id,
            "alive": alive,
            "reason": "heartbeat" if quiet is not None else "no heartbeats",
            "quiet_seconds": quiet,
        })
    return out


def _describe(entry: dict[str, object]) -> str:
    """Human phrasing for one non-alive delegation, including how long it has been quiet."""
    name = str(entry["name"])
    if entry["reason"] == "unparseable":
        return f"{name} (unparseable)"
    quiet = entry["quiet_seconds"]
    if quiet is None:
        return f"{name} (no checkpoint events written)"
    minutes = int(quiet // 60)
    return f"{name} (no checkpoint for {minutes}m)"


def main() -> int:
    directory = state_dir()
    raw_stdin = read_stdin_payload()
    entries = delegation_status(directory)
    # Only delegations that have gone QUIET are worth surfacing. An alive one is
    # mid-flight, and reporting it was the false alarm this replaced.
    quiet = [e for e in entries if not e["alive"]]

    # Permanent invocation audit log — this is what makes firing observable.
    # It records BOTH counts so the full picture is debuggable without ever
    # spamming the session with in-flight delegations.
    append_json_line(
        audit_log_path(directory),
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_hint": event_hint(raw_stdin),
            "pending_count": len(entries),
            "quiet_count": len(quiet),
        },
    )
    # Best-effort dump of the raw stdin payload to learn its undocumented schema.
    if raw_stdin:
        append_json_line(
            stdin_log_path(directory),
            {"ts": datetime.now(timezone.utc).isoformat(), "payload": raw_stdin},
        )

    if quiet:
        shown = ", ".join(_describe(e) for e in quiet[:_MAX_NAMES])
        extra = "" if len(quiet) <= _MAX_NAMES else f" (+{len(quiet) - _MAX_NAMES} more)"
        print(
            json.dumps(
                {
                    "systemMessage": (
                        f"{len(quiet)} delegation(s) may be truncated — report still "
                        f"{_PENDING_STATUS} and no recent heartbeat: {shown}{extra}. "
                        "Check the filesystem for their edits and re-delegate only the "
                        "remainder. (Delegations that are still heartbeating are not "
                        "reported.)"
                    )
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
