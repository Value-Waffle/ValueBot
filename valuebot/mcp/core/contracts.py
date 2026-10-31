"""Cross-module protocols. No I/O, no module imports."""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from .models import (
    CompanyRef,
    DcfResult,
    FilingRef,
    LineItemSeries,
    VaultDocument,
)

API_VERSION = 1
SUPPORTED_PROVIDERS: dict[str, set[int]] = {"fundamentals": {1}}


@runtime_checkable
class LineItemProvider(Protocol):
    api_version: int

    def line_items(
        self,
        symbol: str,
        items: Sequence[str],
        *,
        periods: int = 5,
        annual_only: bool = True,
        balance_basis: str = "average",
    ) -> LineItemSeries: ...

    def concept_vocabulary(self) -> dict[str, tuple[str, ...]]: ...


@runtime_checkable
class FundamentalsAPI(LineItemProvider, Protocol):
    def resolve(self, symbol: str) -> CompanyRef: ...
    def profile(self, symbol: str) -> dict: ...
    def facts(self, symbol: str, **kwargs) -> dict: ...
    def timeseries(self, symbol: str, concept: str, **kwargs) -> dict: ...
    def statement(self, symbol: str, statement: str, **kwargs) -> dict: ...


@runtime_checkable
class VaultReader(Protocol):
    api_version: int

    def read(self, symbol: str, *, offset: int = 0, limit: int = 8000) -> VaultDocument: ...
    def annotations(self, symbol: str, doc: str | None = None) -> list[dict]: ...


@runtime_checkable
class FilingLocator(Protocol):
    api_version: int

    def filings(self, symbol: str, **kwargs) -> dict: ...
    def get_filing(self, symbol: str, *, accession: str | None = None,
                   form: str | None = None) -> FilingRef: ...
    def filing_html(self, symbol: str, accession: str) -> tuple[str, FilingRef]: ...


@runtime_checkable
class AnalysisAPI(Protocol):
    api_version: int

    def catalog(self, symbol: str | None = None) -> dict: ...
    def compute(self, symbol: str, metric_ids: Sequence[str], **kwargs) -> dict: ...
    def dcf(self, symbol: str, **kwargs) -> DcfResult | dict: ...


@runtime_checkable
class CitationResolver(Protocol):
    """Serves the raw material behind a citation ``artifact`` block.

    Resolvers are read-only: they must not build artifacts (no cache writes,
    no export materialisation) and must not touch the network. A resolver that
    cannot serve the artifact locally raises :class:`ArtifactNotCached` with a
    hint naming the domain tool that builds it.

    ``resolve`` returns ``{kind, format, chunk, next_offset, total_chars}``
    plus the optional ``path``, ``preview`` and ``hint`` keys.
    """

    api_version: int

    def resolve(self, artifact: dict, *, offset: int = 0, limit: int = 8000) -> dict: ...


# Reserved for later modules. Declared now; never imported by v1 modules.
@runtime_checkable
class CalendarAPI(Protocol):
    api_version: int

    def events(self, symbol: str, *, kinds=None, start=None, end=None) -> dict: ...


@runtime_checkable
class PriceAPI(Protocol):
    api_version: int

    def history(self, symbol: str, *, period: str = "1y", interval: str = "1d") -> dict: ...
