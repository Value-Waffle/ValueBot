"""Portable configuration for valuebot v2.

Every root resolves with ``env -> default`` precedence and supports
``${VAR}`` / ``${VAR:-default}`` templates. Modules read their own values from
here or from ``modules/<name>/config.py``; no module reads another module's
environment variable.

Nothing in this module writes to stdout: over the MCP stdio transport stdout
is the JSON-RPC channel.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import identity

__all__ = [
    "PLUGIN_ROOT",
    "PLUGIN_DATA",
    "MODULES_ROOT",
    "THESIS_ROOT",
    "CACHE_PATH",
    "FUND_CACHE",
    "ANALYSIS_CACHE",
    "REPORTS_DB",
    "REPORTS_ARTIFACTS",
    "FUNDAMENTALS_EXPORTS",
    "THESIS_INDEX",
    "EDGAR_CACHE",
    "SEC_USER_AGENT",
    "EDGAR_IDENTITY",
    "EDGAR_RATE_LIMIT_PER_SEC",
    "EDGAR_HTTP_TIMEOUT_S",
    "ENABLE_PRICE",
    "MAX_HTML_MB",
    "MAX_FACTS_COMPANIES",
    "MAX_FUND_MB",
    "MAX_ANALYSIS_MB",
    "MAX_REPORTS_MB",
    "MAX_EXPORTS_MB",
    "MAX_CACHE_MB",
    "ARTIFACT_LRU",
    "ARTIFACT_HTTP_PORT",
    "ARTIFACT_HTTP_HOST",
    "ARTIFACT_PUBLIC_BASE_URL",
    "module_data_dir",
    "refresh",
    "describe",
    "normalize_user_agent",
    "require_identity",
    "identity_configured",
    "identity_source",
    "identity_file",
    "is_placeholder_identity",
]

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
_TRUTHY = {"1", "true", "yes", "on"}

# Populated by refresh().
PLUGIN_ROOT: Path = Path(".")
PLUGIN_DATA: Path = Path(".")
MODULES_ROOT: Path = Path(".")
THESIS_ROOT: Path = Path(".")
CACHE_PATH: Path = Path(".")
FUND_CACHE: Path = Path(".")
ANALYSIS_CACHE: Path = Path(".")
REPORTS_DB: Path = Path(".")
REPORTS_ARTIFACTS: Path = Path(".")
FUNDAMENTALS_EXPORTS: Path = Path(".")
THESIS_INDEX: Path = Path(".")
EDGAR_CACHE: Path = Path(".")
SEC_USER_AGENT: str = ""
EDGAR_IDENTITY: str = ""  # deprecated alias, mirrors SEC_USER_AGENT
EDGAR_RATE_LIMIT_PER_SEC: int = 5
EDGAR_HTTP_TIMEOUT_S: float = 30.0
ENABLE_PRICE: bool = False
MAX_HTML_MB: int = 40
MAX_FACTS_COMPANIES: int = 100
MAX_FUND_MB: int = 500
MAX_ANALYSIS_MB: int = 32
MAX_REPORTS_MB: int = 512
MAX_EXPORTS_MB: int = 64
MAX_CACHE_MB: int = 64
ARTIFACT_LRU: int = 2
#: Loopback port for the opt-in debug artifact viewer. ``0`` (the default)
#: keeps it off; citations never carry its url, so nothing depends on it.
#: Set a non-zero port to enable it explicitly.
ARTIFACT_HTTP_PORT: int = 0
#: Bind host for the artifact viewer (used only when it is enabled).
ARTIFACT_HTTP_HOST: str = "127.0.0.1"
#: Browser-reachable base URL for viewer links; empty (default) means
#: ``auto-infer`` from the bound socket, so no manual configuration is needed.
ARTIFACT_PUBLIC_BASE_URL: str = ""

_SOURCES: dict[str, str] = {}
_UNRESOLVED: set[str] = set()


def _expand(raw: str, namespace: dict[str, str], unresolved: set[str]) -> str:
    value = str(raw)
    for _ in range(10):
        def _replace(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            if name in namespace and namespace[name]:
                return namespace[name]
            if default is not None:
                return default
            unresolved.add(name)
            return match.group(0)

        expanded = _VAR_RE.sub(_replace, value)
        if expanded == value:
            break
        value = expanded
    return value


def _path(raw: str) -> Path:
    return Path(os.path.expanduser(raw))


def _int(name: str, default: int, namespace: dict[str, str], sources: dict[str, str]) -> int:
    raw = os.environ.get(name)
    sources[name] = "env" if raw is not None else "default"
    try:
        return int(_expand(raw if raw is not None else str(default), namespace, _UNRESOLVED))
    except (TypeError, ValueError):
        return default


def _str(
    name: str, default: str, namespace: dict[str, str], sources: dict[str, str]
) -> str:
    """Read a string setting; an empty value falls back to ``default``."""
    raw = os.environ.get(name)
    sources[name] = "env" if raw is not None else "default"
    value = _expand(raw if raw is not None else default, namespace, _UNRESOLVED).strip()
    return value or default


def refresh() -> dict[str, object]:
    """Re-read the environment and rebuild every module-level value."""
    global PLUGIN_ROOT, PLUGIN_DATA, MODULES_ROOT, THESIS_ROOT, CACHE_PATH
    global FUND_CACHE, ANALYSIS_CACHE, REPORTS_DB, REPORTS_ARTIFACTS, THESIS_INDEX
    global FUNDAMENTALS_EXPORTS
    global EDGAR_CACHE, SEC_USER_AGENT, EDGAR_IDENTITY, EDGAR_RATE_LIMIT_PER_SEC
    global EDGAR_HTTP_TIMEOUT_S
    global ENABLE_PRICE, MAX_HTML_MB, MAX_FACTS_COMPANIES, MAX_FUND_MB
    global MAX_ANALYSIS_MB, MAX_REPORTS_MB, MAX_EXPORTS_MB, MAX_CACHE_MB
    global ARTIFACT_LRU, ARTIFACT_HTTP_PORT
    global ARTIFACT_HTTP_HOST, ARTIFACT_PUBLIC_BASE_URL
    global _SOURCES, _UNRESOLVED

    _SOURCES = {}
    _UNRESOLVED = set()

    root_raw = os.environ.get("PLUGIN_ROOT")
    if root_raw:
        _SOURCES["PLUGIN_ROOT"] = "env"
        root = _path(_expand(root_raw, dict(os.environ), _UNRESOLVED))
    else:
        _SOURCES["PLUGIN_ROOT"] = "default"
        root = Path(__file__).resolve().parents[2]  # .../valuebot

    namespace: dict[str, str] = {k: v for k, v in os.environ.items() if v}
    namespace["PLUGIN_ROOT"] = str(root)

    def resolve_path(name: str, template: str) -> Path:
        raw = os.environ.get(name)
        _SOURCES[name] = "env" if raw is not None else "default"
        expanded = _expand(raw if raw is not None else template, namespace, _UNRESOLVED)
        namespace[name] = expanded
        return _path(expanded)

    plugin_data = resolve_path("PLUGIN_DATA", "~/.valuebot")
    namespace["PLUGIN_DATA"] = str(plugin_data)

    modules = plugin_data / "modules"
    fund_cache = resolve_path("VW_FUND_CACHE", str(modules / "fundamentals" / "cache.sqlite"))
    analysis_cache = resolve_path(
        "VW_ANALYSIS_CACHE", str(modules / "analysis" / "cache.sqlite")
    )
    reports_db = resolve_path("VW_REPORTS_DB", str(modules / "reports" / "manifest.sqlite"))
    reports_artifacts = resolve_path(
        "VW_REPORTS_ARTIFACTS", str(modules / "reports" / "artifacts")
    )
    fundamentals_exports = resolve_path(
        "VW_FUNDAMENTALS_EXPORTS", str(modules / "fundamentals" / "exports")
    )
    thesis_index = resolve_path(
        "VW_THESIS_INDEX", str(modules / "thesis" / "index.sqlite")
    )
    thesis_root = resolve_path("VW_THESIS_ROOT", str(plugin_data / "theses"))
    edgar_cache = resolve_path("EDGAR_LOCAL_DATA_DIR", str(plugin_data / "edgar"))

    identity_env = (
        os.environ.get("SEC_USER_AGENT") or os.environ.get("EDGAR_IDENTITY", "")
    ).strip()
    if identity_env:
        identity_raw = _expand(identity_env, namespace, _UNRESOLVED)
        _SOURCES["SEC_USER_AGENT"] = (
            "env" if os.environ.get("SEC_USER_AGENT") else "env (EDGAR_IDENTITY alias)"
        )
    else:
        identity_raw = identity.load(plugin_data)
        _SOURCES["SEC_USER_AGENT"] = "file" if identity_raw else "missing"

    PLUGIN_ROOT = root
    PLUGIN_DATA = plugin_data
    MODULES_ROOT = modules
    THESIS_ROOT = thesis_root
    FUND_CACHE = fund_cache
    ANALYSIS_CACHE = analysis_cache
    REPORTS_DB = reports_db
    REPORTS_ARTIFACTS = reports_artifacts
    FUNDAMENTALS_EXPORTS = fundamentals_exports
    THESIS_INDEX = thesis_index
    EDGAR_CACHE = edgar_cache
    CACHE_PATH = fund_cache  # default singleton cache lives with fundamentals
    SEC_USER_AGENT = identity.normalize_user_agent(identity_raw)
    EDGAR_IDENTITY = SEC_USER_AGENT
    EDGAR_RATE_LIMIT_PER_SEC = _int(
        "EDGAR_RATE_LIMIT_PER_SEC", 5, namespace, _SOURCES
    )
    try:
        EDGAR_HTTP_TIMEOUT_S = float(
            os.environ.get("EDGAR_HTTP_TIMEOUT", "30") or 30
        )
    except ValueError:
        EDGAR_HTTP_TIMEOUT_S = 30.0
    ENABLE_PRICE = (
        os.environ.get("VW_ENABLE_PRICE", "0").strip().lower() in _TRUTHY
    )
    MAX_HTML_MB = _int("VW_MAX_HTML_MB", 40, namespace, _SOURCES)
    MAX_FACTS_COMPANIES = _int("VW_MAX_FACTS_COMPANIES", 100, namespace, _SOURCES)
    MAX_FUND_MB = _int("VW_FUND_MAX_MB", 500, namespace, _SOURCES)
    MAX_ANALYSIS_MB = _int("VW_ANALYSIS_MAX_MB", 32, namespace, _SOURCES)
    MAX_REPORTS_MB = _int("VW_REPORTS_MAX_MB", 512, namespace, _SOURCES)
    MAX_EXPORTS_MB = _int("VW_MAX_EXPORTS_MB", 64, namespace, _SOURCES)
    MAX_CACHE_MB = _int("VW_CACHE_MB", 64, namespace, _SOURCES)
    ARTIFACT_LRU = _int("VW_ARTIFACT_LRU", 2, namespace, _SOURCES)
    ARTIFACT_HTTP_PORT = _int("VW_ARTIFACT_HTTP_PORT", 0, namespace, _SOURCES)
    ARTIFACT_HTTP_HOST = _str("VW_ARTIFACT_HTTP_HOST", "127.0.0.1", namespace, _SOURCES)
    ARTIFACT_PUBLIC_BASE_URL = _str(
        "VW_ARTIFACT_PUBLIC_BASE_URL", "", namespace, _SOURCES
    ).rstrip("/")

    return describe()


def module_data_dir(name: str) -> Path:
    """Return (and create) the writable data directory for ``name``."""
    path = MODULES_ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    return path


normalize_user_agent = identity.normalize_user_agent


def is_placeholder_identity(value: str | None = None) -> bool:
    return identity.is_placeholder(SEC_USER_AGENT if value is None else value)


def identity_configured() -> bool:
    return not is_placeholder_identity(SEC_USER_AGENT)


def identity_source() -> str:
    """Where the active User-Agent came from: env, env alias, file or missing."""
    return _SOURCES.get("SEC_USER_AGENT", "missing")


def identity_file() -> Path:
    return identity.path(PLUGIN_DATA)


def require_identity() -> str:
    if is_placeholder_identity(SEC_USER_AGENT):
        from .errors import IdentityNotConfigured  # local import: no cycle

        raise IdentityNotConfigured(
            "SEC User-Agent is not configured",
            hint=(
                "Run the one-time setup: ./setup.sh your@email.com "
                f"(writes {identity.path(PLUGIN_DATA)})."
            ),
        )
    return SEC_USER_AGENT


def describe() -> dict[str, object]:
    """Return resolved configuration with each value's source."""
    return {
        "PLUGIN_ROOT": {"value": str(PLUGIN_ROOT), "source": _SOURCES.get("PLUGIN_ROOT", "default")},
        "PLUGIN_DATA": {"value": str(PLUGIN_DATA), "source": _SOURCES.get("PLUGIN_DATA", "default")},
        "MODULES_ROOT": {"value": str(MODULES_ROOT), "source": "derived"},
        "THESIS_ROOT": {"value": str(THESIS_ROOT), "source": _SOURCES.get("VW_THESIS_ROOT", "default")},
        "FUND_CACHE": {"value": str(FUND_CACHE), "source": _SOURCES.get("VW_FUND_CACHE", "default")},
        "ANALYSIS_CACHE": {"value": str(ANALYSIS_CACHE), "source": _SOURCES.get("VW_ANALYSIS_CACHE", "default")},
        "REPORTS_DB": {"value": str(REPORTS_DB), "source": _SOURCES.get("VW_REPORTS_DB", "default")},
        "REPORTS_ARTIFACTS": {"value": str(REPORTS_ARTIFACTS), "source": _SOURCES.get("VW_REPORTS_ARTIFACTS", "default")},
        "FUNDAMENTALS_EXPORTS": {"value": str(FUNDAMENTALS_EXPORTS), "source": _SOURCES.get("VW_FUNDAMENTALS_EXPORTS", "default")},
        "THESIS_INDEX": {"value": str(THESIS_INDEX), "source": _SOURCES.get("VW_THESIS_INDEX", "default")},
        "EDGAR_CACHE": {"value": str(EDGAR_CACHE), "source": _SOURCES.get("EDGAR_LOCAL_DATA_DIR", "default")},
        "SEC_USER_AGENT": {
            "value": SEC_USER_AGENT,
            "source": _SOURCES.get("SEC_USER_AGENT", "missing"),
        },
        "SEC_USER_AGENT_FILE": str(identity.path(PLUGIN_DATA)),
        "EDGAR_IDENTITY": {"value": EDGAR_IDENTITY, "source": "alias of SEC_USER_AGENT"},
        "EDGAR_RATE_LIMIT_PER_SEC": EDGAR_RATE_LIMIT_PER_SEC,
        "EDGAR_HTTP_TIMEOUT_S": EDGAR_HTTP_TIMEOUT_S,
        "ENABLE_PRICE": ENABLE_PRICE,
        "MAX_HTML_MB": MAX_HTML_MB,
        "MAX_FACTS_COMPANIES": MAX_FACTS_COMPANIES,
        "MAX_FUND_MB": MAX_FUND_MB,
        "MAX_ANALYSIS_MB": MAX_ANALYSIS_MB,
        "MAX_REPORTS_MB": MAX_REPORTS_MB,
        "MAX_EXPORTS_MB": MAX_EXPORTS_MB,
        "MAX_CACHE_MB": MAX_CACHE_MB,
        "ARTIFACT_LRU": ARTIFACT_LRU,
        "ARTIFACT_HTTP_PORT": ARTIFACT_HTTP_PORT,
        "ARTIFACT_HTTP_HOST": {
            "value": ARTIFACT_HTTP_HOST,
            "source": _SOURCES.get("VW_ARTIFACT_HTTP_HOST", "default"),
        },
        "ARTIFACT_PUBLIC_BASE_URL": {
            "value": ARTIFACT_PUBLIC_BASE_URL,
            "source": _SOURCES.get("VW_ARTIFACT_PUBLIC_BASE_URL", "default"),
        },
        "unresolved": sorted(_UNRESOLVED),
        "identity_configured": identity_configured(),
    }


refresh()
