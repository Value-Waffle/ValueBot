"""One-time SEC User-Agent setup.

Run once per deployment (the value is persisted in ``${PLUGIN_DATA}/identity.json``):

    python -m core.setup your@email.com
    python -m core.setup --show
    python -m core.setup --reset
    python -m core.setup --doctor

Until this file exists the data tools fail with ``identity_not_configured``;
there is no built-in identity default and no interactive prompt from the server.
``--doctor`` only prints read-only diagnostics and never reads stdin.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys

from . import config, identity


_REQUIRED_PACKAGES = ("mcp", "edgar", "sec_parser")


def doctor() -> int:
    """Print one ``<status>  <name>  <detail>`` line per read-only check."""
    failed = False

    def emit(status: str, name: str, detail: str) -> None:
        nonlocal failed
        if status == "fail":
            failed = True
        print(f"{status}  {name}  {detail}")

    version = "%d.%d.%d" % sys.version_info[:3]
    if sys.version_info >= (3, 11):
        emit("ok", "python", version)
    else:
        emit("fail", "python", f"{version} (need >= 3.11)")

    uv = shutil.which("uv")
    if uv:
        emit("ok", "uv", uv)
    else:
        emit("warn", "uv", "not on PATH (mcp/run.sh falls back to the venv)")

    config.refresh()
    data = config.PLUGIN_DATA
    try:
        data.mkdir(parents=True, exist_ok=True)
        probe = data / f".doctor-probe-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        emit("fail", "plugin_data", f"{data} not writable: {exc}")
    else:
        emit("ok", "plugin_data", str(data))

    expected = config.identity_file()
    if config.identity_configured():
        emit("ok", "sec_identity", f"configured ({expected})")
    elif config.is_placeholder_identity() and config.SEC_USER_AGENT:
        emit("warn", "sec_identity", "placeholder value; run ./setup.sh you@email.com")
    else:
        emit(
            "warn",
            "sec_identity",
            f"missing; run ./setup.sh you@email.com (expected {expected})",
        )

    missing = []
    for name in _REQUIRED_PACKAGES:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        emit("fail", "packages", "missing: " + ", ".join(missing))
    else:
        emit("ok", "packages", ", ".join(_REQUIRED_PACKAGES) + " importable")

    resolved = config.describe()
    emit(
        "ok",
        "paths",
        f"PLUGIN_DATA={resolved['PLUGIN_DATA']['value']} "
        f"EDGAR_CACHE={resolved['EDGAR_CACHE']['value']}",
    )

    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.setup",
        description="Configure the single SEC User-Agent (one time per deployment).",
    )
    parser.add_argument(
        "user_agent",
        nargs="?",
        help='contact email (or "Name email"), e.g. example-user@gmail.com',
    )
    parser.add_argument("--show", action="store_true", help="print the active value")
    parser.add_argument("--reset", action="store_true", help="remove the stored value")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="run read-only diagnostics (never reads stdin)",
    )
    args = parser.parse_args(argv)

    if args.doctor:
        return doctor()

    if args.show:
        if not config.SEC_USER_AGENT:
            print(
                f"not configured: {identity.path(config.PLUGIN_DATA)} is missing",
                file=sys.stderr,
            )
            return 2
        print(config.SEC_USER_AGENT)
        return 0

    if args.reset:
        target = identity.path(config.PLUGIN_DATA)
        try:
            target.unlink()
        except FileNotFoundError:
            print(f"nothing to remove: {target}")
            return 0
        print(f"removed {target}")
        return 0

    raw = args.user_agent
    if not raw:
        if not sys.stdin.isatty():
            print(
                "error: pass your contact email, "
                "e.g. python -m core.setup example-user@gmail.com",
                file=sys.stderr,
            )
            return 2
        raw = input("SEC contact email: ").strip()

    try:
        target = identity.save(config.PLUGIN_DATA, raw)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"user agent saved to {target}")
    print(f"User-Agent: {identity.normalize_user_agent(raw)}")
    print("restart LibreChat (or the MCP server) to pick it up")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
