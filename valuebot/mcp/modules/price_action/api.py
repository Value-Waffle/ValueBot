"""Reserved price-action module. No tools are registered in v1."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PriceAPI(Protocol):
    api_version: int

    def history(self, symbol: str, *, period: str = "1y", interval: str = "1d") -> dict:
        ...
