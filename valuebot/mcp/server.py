"""valuebot v2 MCP server: module registry, guarded wiring and health.

stdout is the JSON-RPC channel. All logging goes to stderr.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# The plugin directory is named ``mcp`` for packaging, which would shadow the
# installed ``mcp`` SDK as a namespace package when the plugin root is on
# sys.path. Drop the parent entry before importing the SDK.
_PARENT = SCRIPT_DIR.parent
sys.path[:] = [
    entry
    for entry in sys.path
    if entry not in {"", str(_PARENT), str(_PARENT) + os.sep}
]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from mcp.server import MCPServer  # noqa: E402 - SDK package, resolved after sys.path setup

from core import artifact_viewer, citations, config, evidence_view  # noqa: E402
from core.errors import (  # noqa: E402
    InternalError,
    InvalidArgument,
    ModuleUnavailable,
    ValuebotError,
)
from core.response import failure, success  # noqa: E402

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("valuebot.mcp")

try:  # pragma: no cover - the SDK ships these types with mcp >= 2.3
    from mcp_types import EmbeddedResource, TextContent, TextResourceContents
except ImportError as _exc:  # pragma: no cover - defensive text-only fallback
    _SDK_CONTENT_TYPES = False
    TextContent = None  # type: ignore[assignment,misc]
    EmbeddedResource = None  # type: ignore[assignment,misc]
    TextResourceContents = None  # type: ignore[assignment,misc]
    logger.error("mcp_types content blocks unavailable: %s", _exc)
else:
    _SDK_CONTENT_TYPES = True

#: Return annotation that makes ``citation_view`` an unstructured tool:
#: the SDK treats content blocks, bare or in a list, as unstructured output.
CitationViewContent = (
    list[TextContent | EmbeddedResource] if _SDK_CONTENT_TYPES else list
)

INSTRUCTIONS = """\
valuebot serves read-only financial research data through isolated modules.

- fundamentals: XBRL facts, company profile, annual statements.
- analysis: key ratios, growth metrics and a simple DCF with echoed assumptions.
- reports: filing index and sec-parser sections, notes and table grids.
- thesis: the user's investment vault.

Prefer these tools over web search for anything the SEC files: revenue,
margins, share counts, balance-sheet and cash-flow items, ratio and DCF
inputs, and filing text. Web search returns summaries; these tools return
the reported figure with a citation. For a financial question about a public
company, resolve the ticker and call a tool before answering.

Every numeric claim must carry a citation issued by a tool. Use start and end
for period_end filters, never filing dates. Call dcf_compute without
assumptions first and present the returned assumption table. Never invent a
filing, accession, URL or number. Keep responses within the byte caps and page
with offset/next_offset.

When a citation has artifact.status == "cached", open it with citation_resolve
instead of following its url.
"""

mcp = MCPServer(name="valuebot", version="0.2.0", instructions=INSTRUCTIONS)

MODULE_TOOLS: dict[str, tuple[str, ...]] = {
    "fundamentals": (
        "symbol_resolve", "company_profile", "facts_query", "facts_export",
        "facts_timeseries", "statement_get",
    ),
    "analysis": ("ratio_catalog", "ratio_compute", "dcf_compute"),
    "reports": (
        "filing_list", "report_sections", "report_section",
        "report_search", "report_table",
    ),
    "thesis": ("thesis_read", "thesis_annotations"),
}

TOOL_MODULES = {
    tool: module for module, tools in MODULE_TOOLS.items() for tool in tools
}
TOOL_NAMES = tuple(TOOL_MODULES)

#: Tools served by the server itself rather than by a module.
CORE_TOOLS = ("ping", "citation_resolve", "citation_view")


@dataclass
class ModuleState:
    name: str
    status: str = "ready"
    error: str | None = None
    error_code: str | None = None
    api_version: int = 1
    instance: object | None = None
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        payload = {
            "status": self.status,
            "api_version": self.api_version,
        }
        if self.error:
            payload["error"] = self.error
        if self.error_code:
            payload["error_code"] = self.error_code
        payload.update(self.extra)
        return payload


def _build(name: str, factory) -> ModuleState:
    try:
        instance = factory()
        return ModuleState(name=name, instance=instance)
    except Exception as exc:  # a failed module must not take the server down
        logger.exception("module %s failed to initialise", name)
        return ModuleState(
            name=name,
            status="unavailable",
            error=str(exc),
            error_code="module_unavailable",
        )


def _register_stubs(module: str) -> None:
    for tool_name in MODULE_TOOLS[module]:
        def stub(**kwargs):  # noqa: ANN003 - MCP schema accepts keyword args
            exc = ModuleUnavailable(
                f"{module} module is unavailable",
                hint="Check the server log and retry.",
            )
            return failure(module, tool_name, exc)

        stub.__name__ = tool_name
        stub.__doc__ = f"{module} module is unavailable."
        mcp.tool()(stub)


def build_modules() -> dict[str, ModuleState]:
    from modules.fundamentals.service import FundamentalsService
    from modules.reports.service import ReportsService
    from modules.thesis import service as thesis_service
    from modules.analysis.service import AnalysisService

    states: dict[str, ModuleState] = {}
    states["fundamentals"] = _build("fundamentals", FundamentalsService)
    fundamentals = states["fundamentals"].instance

    states["analysis"] = _build(
        "analysis",
        lambda: AnalysisService(fundamentals) if fundamentals is not None else None,
    )
    states["reports"] = _build("reports", ReportsService)
    states["thesis"] = _build("thesis", lambda: thesis_service)
    return states


def register_tools(states: dict[str, ModuleState]) -> None:
    if states["fundamentals"].instance is not None:
        from modules.fundamentals import tools as fundamentals_tools

        fundamentals_tools.register(mcp, states["fundamentals"].instance)
    else:
        _register_stubs("fundamentals")

    if states["analysis"].instance is not None:
        from modules.analysis import tools as analysis_tools

        analysis_tools.register(mcp, states["analysis"].instance)
    else:
        _register_stubs("analysis")

    if states["reports"].instance is not None:
        from modules.reports import tools as reports_tools

        reports_tools.register(mcp, states["reports"].instance)
    else:
        _register_stubs("reports")

    if states["thesis"].instance is not None:
        from modules.thesis import tools as thesis_tools

        thesis_tools.register(mcp, states["thesis"].instance)
    else:
        _register_stubs("thesis")


def register_resolvers(states: dict[str, ModuleState]) -> None:
    """Expose each available module's citation resolver to ``core.citations``.

    Unavailable modules are skipped, so a citation pointing at one resolves to
    a ``citation_unresolvable`` error instead of an unrelated crash. The
    registry is rebuilt from scratch, which makes repeated wiring idempotent.
    """
    citations.clear_resolvers()

    fundamentals = states.get("fundamentals")
    if fundamentals is not None and fundamentals.instance is not None:
        resolver = getattr(fundamentals.instance, "resolver", None)
        if resolver is not None:
            citations.register_resolver("fundamentals", resolver)

    for name in ("reports", "analysis"):
        state = states.get(name)
        if state is not None and state.instance is not None:
            citations.register_resolver(name, state.instance)

    thesis = states.get("thesis")
    if thesis is not None and thesis.instance is not None:
        # ``modules.thesis.service`` exposes a module-level ``resolve()``.
        citations.register_resolver("thesis", thesis.instance)


@mcp.tool()
def ping() -> dict:
    """Return module health, versions, paths and SEC EDGAR identity status."""
    try:
        modules = {name: state.as_dict() for name, state in STATES.items()}
        data = {
            "server": "valuebot",
            "version": "0.2.0",
            "modules": modules,
            "tools": [*CORE_TOOLS, *TOOL_NAMES],
            "identity_configured": config.identity_configured(),
            "identity_source": config.identity_source(),
            "identity_file": str(config.identity_file()),
            "artifact_viewer": artifact_viewer.status(),
            "paths": {
                "plugin_root": str(config.PLUGIN_ROOT),
                "plugin_data": str(config.PLUGIN_DATA),
                "fundamentals": str(config.FUND_CACHE),
                "analysis": str(config.ANALYSIS_CACHE),
                "reports": str(config.REPORTS_DB),
                "artifacts": str(config.REPORTS_ARTIFACTS),
                "thesis": str(config.THESIS_ROOT),
            },
        }
        return success("core", "ping", data, cap=4096)
    except Exception as exc:  # pragma: no cover - defensive
        return failure("core", "ping", InternalError(str(exc)))


@mcp.tool()
def citation_resolve(
    citation: dict | None = None,
    citation_id: str | None = None,
    offset: int = 0,
    limit_chars: int = 8000,
) -> dict:
    """Open the SEC filing, statement or other cited artifact behind a citation from any module.

    Pass either the full ``citation`` object a tool returned or its
    ``citation_id`` token. Addressing by ``citation_id`` needs no URL at all,
    so cached evidence opens the same way locally, in Docker and remotely.

    A miss never builds material: it returns ``artifact_not_cached`` with the
    domain tool to run first.

    Args:
        citation: The full citation object returned by a module tool.
        citation_id: The citation's ``citation_id`` token (alternative).
        offset: Character offset into the artifact text.
        limit_chars: Characters to return (clamped to 1000-12000).
    """
    try:
        window = max(1000, min(int(limit_chars), 12000))
        start = max(0, int(offset))
        if citation is None and citation_id:
            citation = {"artifact": citations.artifact_from_citation_id(citation_id)}
        if citation is None:
            raise InvalidArgument(
                "citation or citation_id is required",
                hint="pass the citation dict or its citation_id token",
            )
        data = citations.resolve_citation(citation, offset=start, limit=window)
    except (ValueError, TypeError) as exc:
        return failure(
            "core", "citation_resolve", InvalidArgument(str(exc))
        )
    except ValuebotError as exc:
        return failure("core", "citation_resolve", exc)
    except Exception as exc:  # a resolver bug must not break the JSON-RPC channel
        logger.exception("citation_resolve failed")
        return failure("core", "citation_resolve", InternalError(str(exc)))

    next_offset = data.get("next_offset") if isinstance(data, dict) else None
    return success(
        "core", "citation_resolve", data,
        citations=[citation] if isinstance(citation, dict) else None,
        echo_references=False,
        paging={
            "offset": start,
            "next_offset": next_offset,
            "truncated": next_offset is not None,
        },
        cap=12288,
    )


def _text_block(text: str):
    """Return one text content block (or a bare string if the SDK lacks blocks)."""
    if not _SDK_CONTENT_TYPES:
        return text
    return [TextContent(type="text", text=text)]


def _explain_view_error(exc: BaseException) -> str:
    """Explain a resolution miss so the model can recover without a retry loop."""
    code = str(getattr(exc, "code", "internal_error") or "internal_error")
    message = str(getattr(exc, "message", None) or exc)
    hint = getattr(exc, "hint", None)
    lines = [f"{code}: {message}"]
    if hint:
        lines.append(f"hint: {hint}")
    lines.append(
        "No inline evidence was embedded. Do not retry citation_view for this "
        "citation: cite it as plain text and state that the source is not cached."
    )
    return "\n".join(lines)


@mcp.tool()
def citation_view(
    citation: dict | None = None,
    citation_id: str | None = None,
    offset: int = 0,
    limit_chars: int = 8000,
) -> CitationViewContent:
    """Render cached SEC filing or other cited evidence as an inline HTML resource.

    Pass either the full ``citation`` object a tool returned or its
    ``citation_id`` token. The result is a short text summary plus an embedded
    ``text/html`` resource addressed by a ``ui://`` URI, which the client
    renders inline. That URI stays inside the embedded resource block and must
    never be echoed to the user: the model never receives a URL and the
    browser never has to reach this server.

    A miss never raises: it returns a text block naming the code and the tool
    to run first.

    Args:
        citation: The full citation object returned by a module tool.
        citation_id: The citation's ``citation_id`` token (alternative).
        offset: Character offset into the artifact text.
        limit_chars: Characters to embed (clamped to 1000-12000).
    """
    try:
        window = max(1000, min(int(limit_chars), 12000))
        start = max(0, int(offset))
        if citation is None and citation_id:
            citation = {
                "artifact": citations.artifact_from_citation_id(citation_id),
            }
        if citation is None:
            return _text_block("invalid_argument: citation or citation_id is required")
        view = evidence_view.build(citation, offset=start, limit=window)
    except (ValueError, TypeError) as exc:
        return _text_block(f"invalid_argument: {exc}")
    except ValuebotError as exc:
        return _text_block(_explain_view_error(exc))
    except Exception as exc:  # a resolver bug must not break the JSON-RPC channel
        logger.exception("citation_view failed")
        return _text_block(_explain_view_error(InternalError(str(exc))))

    total = view.get("total_chars")
    summary = (
        f"kind: {view.get('kind') or 'artifact'} · "
        f"format: {view.get('format') or 'text'} · "
        f"chars: {total if total is not None else 'unknown'}"
    )
    next_offset = view.get("next_offset")
    if isinstance(next_offset, int) and next_offset > 0:
        summary += f" · next_offset: {next_offset}"

    if not _SDK_CONTENT_TYPES:  # pragma: no cover - defensive fallback
        return summary
    return [
        TextContent(type="text", text=summary),
        EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                uri=view["uri"],
                mime_type=view.get("mime_type") or evidence_view.MIME_TYPE,
                text=view["html"],
            ),
        ),
    ]


STATES = build_modules()
register_tools(STATES)
register_resolvers(STATES)

# The local artifact viewer is an opt-in debug surface, off by default
# (VW_ARTIFACT_HTTP_PORT, default 0); citations never carry its url. When a
# port is set it infers its browser-reachable base from the socket it binds.
# Port 0 means "disabled" here; a port clash simply leaves it disabled. It
# must never take the server down.
try:
    if config.ARTIFACT_HTTP_PORT <= 0:
        logger.info("artifact viewer disabled")
    else:
        artifact_viewer.start(
            config.ARTIFACT_HTTP_PORT,
            host=config.ARTIFACT_HTTP_HOST,
            public_base=config.ARTIFACT_PUBLIC_BASE_URL,
        )
        if artifact_viewer.base_url() is None:
            logger.warning(
                "artifact viewer disabled: %s",
                artifact_viewer.status().get("last_error") or "not started",
            )
        else:
            logger.info(
                "artifact viewer ready at %s (%s)",
                artifact_viewer.public_base(),
                artifact_viewer.public_base_source(),
            )
except Exception:  # pragma: no cover - defensive, viewer is non-essential
    logger.exception("artifact viewer failed to start")


def main() -> None:
    transport = os.environ.get("VW_MCP_TRANSPORT", "stdio").strip().lower()
    if transport in {"", "stdio"}:
        logger.info("transport: stdio (stdin/stdout JSON-RPC)")
        mcp.run()
        return
    if transport in {"streamable-http", "http"}:
        host = (
            os.environ.get("VW_MCP_HTTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
        )
        raw_port = os.environ.get("VW_MCP_HTTP_PORT", "8848").strip() or "8848"
        try:
            port = int(raw_port)
        except ValueError:
            logger.error(
                "invalid VW_MCP_HTTP_PORT=%r: expected an integer", raw_port
            )
            raise SystemExit(2) from None
        if not 0 < port < 65536:
            logger.error("invalid VW_MCP_HTTP_PORT=%s: out of range 1-65535", port)
            raise SystemExit(2)
        logger.info(
            "transport: streamable-http on http://%s:%d/mcp", host, port
        )
        mcp.run("streamable-http", host=host, port=port)
        return
    logger.error(
        "unsupported VW_MCP_TRANSPORT=%r: expected 'stdio' or 'streamable-http'",
        transport,
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
