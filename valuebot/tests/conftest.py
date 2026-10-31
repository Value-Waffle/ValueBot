"""Shared test setup: put the MCP source directory on sys.path.

Tests import ``core`` and ``modules`` directly, never the ``mcp`` package name,
which belongs to the MCP SDK.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

VALUEBOT = Path(__file__).resolve().parents[1]
MCP_DIR = VALUEBOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

os.environ.setdefault("PLUGIN_DATA", str(VALUEBOT / ".test-data"))
os.environ.setdefault("SEC_USER_AGENT", "example-user@gmail.com")
