"""The single SEC User-Agent, configured once on first run.

The value is stored at ``${PLUGIN_DATA}/identity.json`` with mode ``0600`` by
``python -m core.setup`` (or ``./setup.sh``). Environment variables
``SEC_USER_AGENT`` and the legacy ``EDGAR_IDENTITY`` are per-run overrides for
CI and probes; they take precedence over the stored file.

A bare email is normalized to ``valuebot <email>``; a full ``"Name email"``
identity is used unchanged. Placeholder domains are rejected everywhere, so
the plugin never runs against SEC without a real contact address.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FILENAME = "identity.json"
KEY = "user_agent"
PLACEHOLDERS = ("example.com", "user@example.com", "default@domain.com")

__all__ = [
    "FILENAME",
    "KEY",
    "PLACEHOLDERS",
    "exists",
    "is_placeholder",
    "load",
    "normalize_user_agent",
    "path",
    "save",
]


def normalize_user_agent(raw: str | None) -> str:
    """Return one SEC-compliant User-Agent from the configured value."""
    text = " ".join(str(raw or "").replace("<", " ").replace(">", " ").split())
    if not text:
        return ""
    if " " not in text:
        return f"valuebot {text}"
    return text


def is_placeholder(value: str | None) -> bool:
    text = (value or "").lower()
    if not text.strip():
        return True
    if any(marker in text for marker in PLACEHOLDERS):
        return True
    parts = text.split()
    return len(parts) < 2 or "@" not in parts[-1] or "." not in parts[-1].split("@")[-1]


def path(plugin_data: Path) -> Path:
    return Path(plugin_data) / FILENAME


def load(plugin_data: Path) -> str:
    """Return the stored User-Agent, or ``""`` when missing or unreadable."""
    file = path(plugin_data)
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return normalize_user_agent(payload.get(KEY))


def exists(plugin_data: Path) -> bool:
    return bool(load(plugin_data))


def save(plugin_data: Path, raw: str | None) -> Path:
    """Validate and atomically write the one-time User-Agent file."""
    value = normalize_user_agent(raw)
    if is_placeholder(value):
        raise ValueError(
            "a real contact email is required, e.g. example-user@gmail.com"
        )
    directory = Path(plugin_data)
    directory.mkdir(parents=True, exist_ok=True)
    target = path(directory)
    handle, temporary = tempfile.mkstemp(
        dir=directory, prefix=".identity-", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    KEY: value,
                    "created_at": datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    ),
                },
                stream,
                indent=2,
            )
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return target
