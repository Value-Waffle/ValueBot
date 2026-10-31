"""Reserved calendar module. No tools are registered in v1."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CalendarAPI(Protocol):
    api_version: int

    def events(self, symbol: str, *, kinds=None, start=None, end=None) -> dict:
        ...
