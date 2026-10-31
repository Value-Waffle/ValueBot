"""Minimal newline-delimited JSON-RPC client for the MCP stdio tests.

The client keeps stdin open while requests are in flight (closing it early
cancels non-inline handlers in the MCP SDK) and drains stdout on a background
thread so a slow tool call cannot block the child process.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time
from typing import IO


def write_diagnostic(lines: list[str]) -> None:
    """Write test diagnostics to stderr, bypassing pytest's fd capture."""
    text = "\n".join(lines) + "\n"
    try:  # /dev/tty keeps the table visible during a normal ``-q`` run
        with open("/dev/tty", "w", encoding="utf-8") as tty:
            tty.write(text)
            tty.flush()
    except OSError:
        sys.__stderr__.write(text)
        sys.__stderr__.flush()


class StdioClient:
    """Drive one child process over newline-delimited JSON-RPC on stdio."""

    def __init__(self, proc: subprocess.Popen[str], stderr_file: IO[str]) -> None:
        self.proc = proc
        self.stderr_file = stderr_file
        self.lines: list[str] = []
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self.lines.append(line)
            self._queue.put(line)
        self._queue.put(None)

    def send(self, payload: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def wait_for(self, request_id: int, timeout: float = 30.0) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"timed out waiting for response id={request_id}")
            raw = self._queue.get(timeout=remaining)
            if raw is None:
                raise AssertionError(
                    "server closed stdout before replying\n"
                    f"stderr:\n{self.stderr_text()}"
                )
            try:
                message = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise AssertionError(f"non-JSON bytes on stdout: {raw!r}") from exc
            assert isinstance(message, dict), f"stdout line is not an object: {raw!r}"
            if message.get("id") == request_id:
                return message

    def stderr_text(self) -> str:
        self.stderr_file.flush()
        self.stderr_file.seek(0)
        return self.stderr_file.read()

    def close(self, timeout: float = 10.0) -> int:
        """Close stdin (EOF) and wait for a graceful exit; return the code."""
        if self.proc.stdin is not None:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
        try:
            code = self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            code = self.proc.wait(timeout=timeout)
        self._reader.join(timeout=5)
        if self.proc.stdout is not None:
            self.proc.stdout.close()
        return code
