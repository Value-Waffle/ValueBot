"""MCP tools owned by the thesis module."""

from __future__ import annotations

import time

from core.errors import InternalError, InvalidArgument
from core.response import failure, success

from .. import service

MODULE = "thesis"


def _wrap(tool: str, result: dict, started: float, symbol: str | None) -> dict:
    if result.get("ok"):
        data = {key: value for key, value in result.items() if key != "ok"}
        citations = data.pop("citations", [])
        return success(
            MODULE, tool, data, symbol=symbol, citations=citations,
            started=started, cap=8192,
        )
    error = result.get("error") or {}
    exc = InvalidArgument(
        str(error.get("message") or "thesis request failed"),
        details={k: v for k, v in error.items() if k not in {"code", "message"}},
    )
    exc.code = str(error.get("code") or "invalid_argument")
    return failure(MODULE, tool, exc, started=started)


def register(mcp, _service=None) -> None:
    @mcp.tool()
    def thesis_read(symbol: str, file: str | None = None, offset: int = 0,
                    limit: int = 8000) -> dict:
        """Read the user's own investment notes in the thesis vault for a ticker.

        Args:
            symbol: Ticker.
            file: Optional relative file inside the ticker vault.
            offset: Character offset for the returned body.
            limit: Characters per page (up to 8000).
        """
        started = time.perf_counter()
        try:
            result = service.thesis_read(symbol, file=file, offset=offset, limit=limit)
            return _wrap("thesis_read", result, started, symbol)
        except Exception as exc:
            return failure(MODULE, "thesis_read", InternalError(str(exc)), started=started)

    @mcp.tool()
    def thesis_annotations(symbol: str, doc: str | None = None) -> dict:
        """List the user's own investment-note annotation documents in the thesis vault for a ticker.

        Args:
            symbol: Ticker.
            doc: Optional annotation document key.
        """
        started = time.perf_counter()
        try:
            result = service.thesis_annotations(symbol, doc=doc)
            return _wrap("thesis_annotations", result, started, symbol)
        except Exception as exc:
            return failure(
                MODULE, "thesis_annotations", InternalError(str(exc)), started=started
            )
