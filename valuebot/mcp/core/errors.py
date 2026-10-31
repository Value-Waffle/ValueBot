"""Typed error taxonomy shared by every module."""

from __future__ import annotations

__all__ = [
    "ValuebotError",
    "IdentityNotConfigured",
    "SymbolNotFound",
    "CompanyNotFound",
    "FilingNotFound",
    "SectionNotFound",
    "TableNotFound",
    "StatementUnavailable",
    "MetricNotFound",
    "MetricUnavailable",
    "ModuleUnavailable",
    "InvalidArgument",
    "EdgarUnavailable",
    "EdgarRateLimited",
    "ArtifactTooLarge",
    "ArtifactNotCached",
    "CitationUnresolvable",
    "ParserFailed",
    "CacheUnavailable",
    "ContractViolation",
    "InternalError",
]


class ValuebotError(Exception):
    code = "internal_error"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        retryable: bool | None = None,
        retry_after_s: float | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = str(message)
        self.hint = hint
        if retryable is not None:
            self.retryable = bool(retryable)
        self.retry_after_s = retry_after_s
        self.details = details or {}

    def to_dict(self) -> dict:
        payload: dict = {
            "code": self.code,
            "message": self.message,
            "retryable": bool(self.retryable),
        }
        if self.hint:
            payload["hint"] = self.hint
        if self.retry_after_s is not None:
            payload["retry_after_s"] = float(self.retry_after_s)
        if self.details:
            payload.update(self.details)
        return payload


class IdentityNotConfigured(ValuebotError):
    code = "identity_not_configured"


class SymbolNotFound(ValuebotError):
    code = "symbol_not_found"


class CompanyNotFound(ValuebotError):
    code = "company_not_found"


class FilingNotFound(ValuebotError):
    code = "filing_not_found"


class SectionNotFound(ValuebotError):
    code = "section_not_found"


class TableNotFound(ValuebotError):
    code = "table_not_found"


class StatementUnavailable(ValuebotError):
    code = "statement_unavailable"


class MetricNotFound(ValuebotError):
    code = "metric_not_found"


class MetricUnavailable(ValuebotError):
    code = "metric_unavailable"


class ModuleUnavailable(ValuebotError):
    code = "module_unavailable"
    retryable = True


class InvalidArgument(ValuebotError):
    code = "invalid_argument"


class EdgarUnavailable(ValuebotError):
    code = "edgar_unavailable"
    retryable = True


class EdgarRateLimited(ValuebotError):
    code = "edgar_rate_limited"
    retryable = True


class ArtifactTooLarge(ValuebotError):
    code = "artifact_too_large"


class ArtifactNotCached(ValuebotError):
    """Raw material for a citation artifact is not available locally.

    ``hint`` should name the build path that materialises it (for example
    ``run report_section first``), because resolution never builds artifacts.
    """

    code = "artifact_not_cached"


class CitationUnresolvable(ValuebotError):
    """The citation carries no usable artifact, or its module is unavailable."""

    code = "citation_unresolvable"


class ParserFailed(ValuebotError):
    code = "parser_failed"


class CacheUnavailable(ValuebotError):
    code = "cache_unavailable"
    retryable = True


class ContractViolation(ValuebotError):
    code = "contract_violation"


class InternalError(ValuebotError):
    code = "internal_error"
