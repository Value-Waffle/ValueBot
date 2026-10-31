"""Zero-config HTTP viewer for cached citation artifacts.

The MCP stdio transport is not a browser surface, so a citation whose artifact
is cached has no clickable way to open it. This module serves those artifacts
so a human can read them, and it starts by default: no operator configuration
is required for a citation to carry a clickable link.

Design constraints:

* stdlib only; no dependencies and no module imports.
* bound to ``VW_ARTIFACT_HTTP_HOST`` (default ``127.0.0.1``); the operator may
  widen the bind interface, but the default never exposes a public interface.
* the browser-reachable base is *inferred from the socket that actually bound*,
  so the emitted link always points at a live address. An explicit
  ``VW_ARTIFACT_PUBLIC_BASE_URL`` still wins when one is configured.
* the only safety rule is "a viewer URL exists if and only if the viewer is
  listening": a failed bind emits no links, so a citation can never carry a
  dead link.
* a per-process random token must accompany every request, because the thesis
  vault is private.
* resolution goes through :func:`core.citations.resolve_citation`, i.e. the
  same resolver registry the ``citation_resolve`` tool uses, so the viewer can
  never surface material the tools would not.
* nothing is ever written to stdout: stdout is the JSON-RPC channel.
"""

from __future__ import annotations

import html
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

__all__ = [
    "base_url",
    "public_base",
    "public_base_source",
    "start",
    "status",
    "stop",
    "url_for",
]

_HOST = "127.0.0.1"
_PATH = "/a"
_DEFAULT_LIMIT = 8000
_MAX_LIMIT = 12000

#: Bind hosts that only a browser on this machine can reach.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})
#: Bind hosts that accept traffic on every local interface.
_WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", "[::]", "", "*"})

#: Query keys that rebuild a citation's artifact locator. ``format`` is
#: deliberately absent: it is the artifact's own content format (``md``...),
#: while the viewer's ``format`` param selects ``raw`` vs ``html`` output.
_ARTIFACT_KEYS = (
    "module",
    "kind",
    "cik",
    "accession",
    "section_id",
    "table_id",
    "metric_id",
    "period_end",
    "balance_basis",
    "facts_version",
    "symbol",
    "file",
    "concept",
    "taxonomy",
    "unit",
    "status",
)

#: HTTP status per error code; every one of these is a client-side condition.
_ERROR_STATUS = {
    "artifact_not_cached": 409,
    "citation_unresolvable": 404,
    "invalid_argument": 409,
}

_lock = threading.RLock()
_token: str | None = None
_server: ThreadingHTTPServer | None = None
_thread: threading.Thread | None = None
_host: str = _HOST
_port: int = 0
#: Browser-reachable base URL (no trailing slash); ``None`` means no links.
_public_base: str | None = None
#: Where ``_public_base`` came from: ``"explicit"``, ``"inferred"`` or ``None``.
_public_base_source: str | None = None
#: Why the last ``start()`` failed to bind, or ``None`` after a clean start.
#: A port clash is the common case; without this the only trace is a log line.
_last_error: str | None = None


def base_url() -> str | None:
    """Return the actual bound ``http://<host>:<port>`` while running."""
    with _lock:
        if _server is None:
            return None
        return f"http://{_host}:{_port}"


def public_base() -> str | None:
    """Return the effective browser-reachable base URL, or ``None``."""
    with _lock:
        return _public_base


def public_base_source() -> str | None:
    """Return ``"explicit"``, ``"inferred"`` or ``None`` for ``public_base()``."""
    with _lock:
        return _public_base_source


def status() -> dict:
    """Return the viewer's observable state, including why it is off.

    This is the only place that knows whether a citation ``url`` exists and how
    reachable that url is, so callers (``success()``, ``ping``) must ask
    instead of inferring it from ``base_url()``.

    ``reachable_hint`` is deliberately a hint, not a proof: ``"explicit"``
    means an operator supplied the public base, ``"loopback"`` means the
    effective base is a loopback literal and therefore only reachable from a
    browser on this host, and ``"unknown"`` means the plugin cannot tell.
    ``last_error`` records why the most recent bind failed.
    """
    with _lock:
        enabled = _server is not None and bool(_token) and bool(_public_base)
        if _public_base_source == "explicit":
            reachable_hint = "explicit"
        elif _public_base:
            host = (urlsplit(_public_base).hostname or "").lower()
            reachable_hint = "loopback" if host in _LOOPBACK_HOSTS else "unknown"
        else:
            reachable_hint = "unknown"
        return {
            "enabled": enabled,
            "base_url": f"http://{_host}:{_port}" if _server is not None else None,
            "public_base": _public_base,
            "public_base_source": _public_base_source,
            "reachable_hint": reachable_hint,
            "last_error": _last_error,
        }


def _infer_public_base(host: str, port: int) -> str:
    """Infer the browser-reachable base for a bound ``host:port``.

    A loopback bind is reachable at ``127.0.0.1``; a wildcard bind is reachable
    at this machine's address. Pure and total: any socket failure degrades to
    ``http://127.0.0.1:<port>`` and this function never raises.
    """
    try:
        loopback = f"http://127.0.0.1:{int(port)}"
    except (TypeError, ValueError):  # pragma: no cover - defensive
        loopback = "http://127.0.0.1"
    try:
        name = str(host or "").strip().lower()
        bare = name[1:-1] if name.startswith("[") and name.endswith("]") else name
        if bare in {"127.0.0.1", "localhost", "::1"}:
            return loopback
        if bare in {"0.0.0.0", "::", "", "*"}:
            try:
                resolved = socket.gethostbyname(socket.gethostname())
            except OSError:
                resolved = socket.gethostname()
            resolved = (resolved or "").strip()
            if not resolved or resolved in _WILDCARD_HOSTS:
                return loopback
            return f"http://{resolved}:{int(port)}"
        if ":" in bare:  # IPv6 literal
            return f"http://[{bare}]:{int(port)}"
        return f"http://{bare}:{int(port)}"
    except Exception:  # pragma: no cover - inference must never raise
        return loopback


def url_for(artifact: Any) -> str | None:
    """Return a tokenised viewer URL for ``artifact``, or ``None`` if disabled.

    The only gate is that the viewer is actually listening (a server, a token
    and a public base all exist). ``start`` always sets a public base once the
    socket binds, so a URL exists if and only if the viewer is reachable.
    """
    if not isinstance(artifact, dict) or not artifact:
        return None

    with _lock:
        if _server is None or not _token or not _public_base:
            return None
        root = _public_base
        token = _token

    query: dict[str, str] = {"t": token}
    for key in _ARTIFACT_KEYS:
        value = artifact.get(key)
        if value is None or isinstance(value, (dict, list, tuple, set)):
            continue
        if isinstance(value, bool):
            value = int(value)
        text = str(value)
        if text:
            query[key] = text
    return f"{root}{_PATH}?{urlencode(query)}"


def start(
    port: int,
    host: str | None = None,
    public_base: str | None = None,
) -> str | None:
    """Start the viewer on ``host:port``; ``0`` means an ephemeral port.

    ``host`` defaults to ``127.0.0.1``. ``public_base`` is the
    browser-reachable root used by :func:`url_for`; when empty or ``None`` it is
    inferred from the socket that actually bound, *after* the bind, so an
    ephemeral port is honoured. A negative port or a failed bind leaves the
    viewer disabled (``None``) and therefore emits no citation links.
    Returns the actual bound address, as :func:`base_url` would.
    """
    global _public_base, _public_base_source, _last_error
    global _token, _server, _thread, _host, _port

    try:
        wanted = int(port)
    except (TypeError, ValueError):
        wanted = 0

    bind_host = (str(host).strip() if host else "") or _HOST
    explicit = (str(public_base).strip() if public_base else "").rstrip("/") or None

    # A negative port is the explicit "viewer off" signal, not a failure.
    if wanted < 0:
        with _lock:
            _last_error = None
        return None

    with _lock:
        if _server is not None:
            if wanted > 0 and wanted == _port and bind_host == _host:
                _public_base = explicit or _infer_public_base(bind_host, _port)
                _public_base_source = "explicit" if explicit else "inferred"
                _last_error = None
                return base_url()
            _stop_locked()

        token = secrets.token_urlsafe(16)
        try:
            server = ThreadingHTTPServer((bind_host, wanted), _make_handler(token))
        except OSError as exc:
            # Record the reason instead of failing silently: citations will
            # carry no url, and status() must be able to say why.
            _last_error = f"bind failed on {bind_host}:{wanted}: {exc}"
            return None
        server.daemon_threads = True

        thread = threading.Thread(
            target=server.serve_forever,
            name="valuebot-artifact-viewer",
            daemon=True,
        )
        thread.start()

        _server = server
        _thread = thread
        _token = token
        _host = bind_host
        _port = int(server.server_address[1])
        # Infer after the bind so ``port 0`` yields the real ephemeral port.
        _public_base = explicit or _infer_public_base(_host, _port)
        _public_base_source = "explicit" if explicit else "inferred"
        _last_error = None
        return base_url()


def stop() -> None:
    """Stop the viewer (idempotent); a disabled viewer stays disabled."""
    with _lock:
        _stop_locked()


def _stop_locked() -> None:
    global _public_base, _public_base_source, _last_error
    global _token, _server, _thread, _host, _port

    server, thread = _server, _thread
    _server, _thread, _token, _port = None, None, None, 0
    _host = _HOST
    _public_base = None
    _public_base_source = None
    _last_error = None
    if server is not None:
        try:
            server.shutdown()
        except Exception:  # pragma: no cover - shutdown races are harmless
            pass
        try:
            server.server_close()
        except Exception:  # pragma: no cover - defensive
            pass
    if thread is not None and thread.is_alive():
        thread.join(timeout=5)


def _make_handler(expected_token: str) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        server_version = "valuebot-artifact-viewer"
        sys_version = ""

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            """Silence access logging: stdout/stderr belong to the MCP channel."""
            return

        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            try:
                self._handle_get()
            except Exception:  # pragma: no cover - never leak a traceback
                self._send(500, "text/plain; charset=utf-8", "internal_error")

        def _handle_get(self) -> None:
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query, keep_blank_values=True)
            supplied = (params.get("t") or [""])[0]
            if not _token_ok(supplied, expected_token):
                self._send(
                    403,
                    "text/plain; charset=utf-8",
                    "forbidden: missing or invalid viewer token",
                )
                return
            if parsed.path != _PATH:
                self._send(
                    404,
                    "text/plain; charset=utf-8",
                    f"not_found: unknown path {parsed.path}",
                )
                return

            from .errors import (  # local import keeps the handler dependency-thin
                ArtifactNotCached,
                CitationUnresolvable,
                InvalidArgument,
                ValuebotError,
            )

            try:
                artifact = _artifact_from(params)
                offset = _int_param(params, "offset", 0)
                limit = _int_param(params, "limit", _DEFAULT_LIMIT)
                payload = _resolve(artifact, offset=max(0, offset), limit=_clamp(limit))
            except (ArtifactNotCached, CitationUnresolvable, InvalidArgument) as exc:
                status = _ERROR_STATUS.get(getattr(exc, "code", ""), 409)
                self._send(
                    status,
                    "text/plain; charset=utf-8",
                    _error_body(exc),
                )
                return
            except ValuebotError as exc:  # pragma: no cover - taxonomy fallback
                self._send(409, "text/plain; charset=utf-8", _error_body(exc))
                return
            except (TypeError, ValueError) as exc:
                self._send(
                    409,
                    "text/plain; charset=utf-8",
                    f"invalid_argument: {exc}",
                )
                return

            if not isinstance(payload, dict):
                payload = {"format": "text", "chunk": str(payload)}

            chunk = payload.get("chunk")
            text = "" if chunk is None else str(chunk)
            if _wants_raw(params):
                self._send(200, "text/plain; charset=utf-8", text)
            else:
                self._send(
                    200,
                    "text/html; charset=utf-8",
                    _page(payload, params, text),
                )

        def _send(self, status: int, content_type: str, body: str) -> None:
            encoded = body.encode("utf-8", "replace")
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):  # pragma: no cover
                pass

    return _Handler


def _token_ok(supplied: str, expected: str) -> bool:
    if not supplied or not expected:
        return False
    try:
        return secrets.compare_digest(str(supplied), str(expected))
    except TypeError:  # pragma: no cover - non-ASCII oddities
        return False


def _artifact_from(params: dict[str, list[str]]) -> dict:
    artifact: dict = {}
    for key in _ARTIFACT_KEYS:
        value = (params.get(key) or [""])[0]
        if value == "":
            continue
        artifact[key] = value
    cik = artifact.get("cik")
    if isinstance(cik, str) and cik.strip().isdigit():
        artifact["cik"] = int(cik.strip())
    return artifact


def _int_param(params: dict[str, list[str]], name: str, default: int) -> int:
    raw = (params.get(name) or [""])[0].strip()
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        from .errors import InvalidArgument

        raise InvalidArgument(
            f"{name} must be an integer",
            hint="pass offset/limit as whole characters, e.g. offset=0&limit=8000",
        ) from exc


def _clamp(limit: int) -> int:
    if limit <= 0:
        return _DEFAULT_LIMIT
    return min(limit, _MAX_LIMIT)


def _resolve(artifact: dict, *, offset: int, limit: int) -> dict:
    from .citations import resolve_citation  # local import: avoids a cycle

    # ``resolve_citation`` takes a citation, so wrap the rebuilt locator.
    return resolve_citation({"artifact": artifact}, offset=offset, limit=limit)


def _wants_raw(params: dict[str, list[str]]) -> bool:
    return ((params.get("format") or [""])[0] or "").strip().lower() == "raw"


def _error_body(exc: Any) -> str:
    code = str(getattr(exc, "code", "internal_error") or "internal_error")
    message = str(getattr(exc, "message", None) or exc)
    hint = getattr(exc, "hint", None)
    lines = [f"{code}: {message}"]
    if hint:
        lines.append(f"hint: {hint}")
    return "\n".join(lines)


def _link(base: str, params: dict[str, list[str]], **overrides: str) -> str:
    query = {key: values[0] for key, values in params.items() if values}
    query.update(overrides)
    return f"{base}{_PATH}?{urlencode(query)}"


def _page(payload: dict, params: dict[str, list[str]], text: str) -> str:
    """Render the viewer page through the one shared HTML renderer.

    :func:`core.evidence_view.render_html` owns the document and its style;
    this function only contributes the viewer's navigation links, which stay
    identical (next page and raw) so existing bookmarks and tests keep working.
    """
    root = base_url() or ""
    kind = str(payload.get("kind") or "")
    total = payload.get("total_chars")

    links = []
    next_offset = payload.get("next_offset")
    if isinstance(next_offset, int) and next_offset > 0:
        links.append(
            f'<a href="{html.escape(_link(root, params, offset=str(next_offset)))}">'
            "next page</a>"
        )
    links.append(
        f'<a href="{html.escape(_link(root, params, format="raw"))}">raw</a>'
    )

    from . import evidence_view  # local import: avoids an import cycle

    return evidence_view.render_html(
        {
            "kind": kind,
            "format": payload.get("format"),
            "total_chars": total,
            "chunk": text,
        },
        title=f"valuebot artifact {kind}",
        footer_html=" | ".join(links),
    )
