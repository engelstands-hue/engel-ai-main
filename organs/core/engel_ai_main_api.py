"""Reusable Engel AI Main local API.

This is the public API other programs should use: Python functions and a
stdio CLI. It does not start an HTTP server and it does not speak HTTP.
Graph Studio, Flutter helpers, scripts, and other local tools can call it
the same way Codex/Claude/Grok local sign-in is called: one local process,
one reply, no network listener.

Transport: in-process function or stdio JSON.
Authority: Josh > Guardian > Engel/runtime.

Response contract:
- ``ok`` is true only when the requested operation completed.
- ``status`` also reports ``api_ready`` and ``app_ready`` separately, so a
  missing desktop executable cannot be mistaken for a ready Main instance.
- route/provider failures keep their human-readable text and add ``error_code``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from engel_project_paths import resolve_engel_app_root
except ImportError:  # pragma: no cover - allows a portable ping/status probe
    # The shareable CLI package can be copied without the full Engel source tree.
    # Keep ping/status useful in that case; chat will return a structured
    # dependency error instead of failing during module import.
    def resolve_engel_app_root(caller_file: str | os.PathLike[str] | None = None) -> Path:
        configured = str(os.environ.get("ENGEL_APP_ROOT") or "").strip()
        if configured:
            return Path(configured).expanduser().resolve(strict=False)
        return Path(caller_file or __file__).resolve(strict=False).parent


ROOT = resolve_engel_app_root(__file__)
SCHEMA = "engel_ai_main_local_api_v1"
REQUEST_ID = "local-engel-cli"
DEFAULT_MODEL = "Engel AI Main"

# These are deliberately conservative.  The deterministic router returns text
# for both successful routes and renderer/provider failures; exposing all of
# those replies as ``ok: true`` makes callers continue as if work completed.
# A marker only changes the machine-readable status; the original reply is
# retained in ``text``/``error_detail`` so the operator can see what happened.
_FAILURE_MARKERS: tuple[tuple[str, str], ...] = (
    ("no inference provider configured", "provider_not_configured"),
    ("i don't have a live ai connected right now", "provider_not_configured"),
    ("for full intelligent answers, connect me to an ai", "provider_not_configured"),
    ("bridge raised", "provider_bridge_error"),
    ("status renderer unavailable", "route_renderer_failed"),
    ("unknown engel ai update route", "unknown_route"),
    ("engel ai did not produce a local response", "no_route_reply"),
    ("could not be started: filenotfounderror", "process_not_found"),
    ("filenotfounderror", "process_not_found"),
)


def _response(*, ok: bool, text: str = "", error_code: str = "", error: str = "", **extra: Any) -> dict[str, Any]:
    """Build one stable, JSON-serializable local API response envelope."""
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "ok": bool(ok),
        "text": str(text or ""),
        "request_id": REQUEST_ID,
        "model": DEFAULT_MODEL,
        "transport": "stdio",
        "http": False,
        "updated_at_utc": utc_now(),
    }
    if error_code:
        payload["error_code"] = str(error_code)
    if error:
        payload["error"] = str(error)
    payload.update(extra)
    # The transport contract is non-negotiable even if a future caller passes
    # an accidental value in ``extra``.
    payload["http"] = False
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ping() -> dict[str, Any]:
    """Connection test used by Graph Studio Test and any other local client."""
    return _response(ok=True, text="connected")


def _engel_main_executable() -> Path:
    return (
        ROOT
        / "engel_flutter_main"
        / "build"
        / "windows"
        / "x64"
        / "runner"
        / "Release"
        / "EngelAIMain.exe"
    )


def _dependency_status() -> dict[str, bool]:
    """Check source dependencies without importing provider/runtime modules."""
    return {
        name: (ROOT / name).is_file()
        for name in (
            "engel_ai.py",
            "engel_communication_router.py",
            "engel_ai_update_routes.py",
        )
    }


def status() -> dict[str, Any]:
    """File-only status. No HTTP, SSH, or provider calls.

    ``ok`` means the local API *and* the canonical Engel AI Main executable are
    ready.  ``api_ready`` and ``app_ready`` are exposed independently for
    hosts that need to explain which piece is missing.
    """
    exe = _engel_main_executable()
    dependencies = _dependency_status()
    dependencies_ok = all(dependencies.values())
    exe_present = exe.is_file()
    ready = bool(dependencies_ok and exe_present)
    if ready:
        text = "Engel AI Main local API ready"
        error_code = ""
    elif not dependencies_ok:
        missing = ", ".join(name for name, present in dependencies.items() if not present)
        text = "Engel AI Main local API dependencies are missing: " + missing
        error_code = "api_dependencies_missing"
    else:
        text = "Engel AI Main executable is missing; the local API is not ready"
        error_code = "engel_main_exe_missing"
    return _response(
        ok=ready,
        text=text,
        error_code=error_code,
        workspace=str(ROOT),
        api_file=str(Path(__file__).resolve(strict=False)),
        api_ready=dependencies_ok,
        app_ready=exe_present,
        dependencies_ok=dependencies_ok,
        dependencies=dependencies,
        engel_main_exe=str(exe),
        engel_main_exe_present=exe_present,
    )


def _is_ping(prompt: str, system: str = "") -> bool:
    blob = " ".join(f"{system} {prompt}".casefold().split())
    if not blob:
        return True
    ping_words = {"ping", "test", "connection", "return a connection result."}
    if blob.strip() in ping_words:
        return True
    return blob in {"return a connection result. ping", "ping ping"}


def _reply_error_code(reply: str) -> str:
    folded = str(reply or "").casefold()
    for marker, code in _FAILURE_MARKERS:
        if marker in folded:
            return code
    return ""


def _route_details(prompt: str) -> dict[str, Any]:
    """Expose deterministic route metadata without changing route behavior."""
    try:
        from engel_communication_router import classify_user_input

        intent = classify_user_input(prompt)
        return {
            "intent_category": str(getattr(intent, "category", "") or ""),
            "route_target": str(getattr(intent, "route_target", "") or ""),
            "handled_by_router": True,
        }
    except Exception:
        return {"handled_by_router": False}


def chat(prompt: str, *, system: str = "") -> dict[str, Any]:
    """One local Engel turn. Routes commands on this computer. No HTTP."""
    user = str(prompt or "").strip()
    system_text = str(system or "").strip()
    if not user:
        return _response(
            ok=False,
            text="A non-empty prompt is required.",
            error_code="empty_prompt",
            error="empty_prompt",
        )
    if _is_ping(user, system_text):
        return ping()
    body = user
    if system_text:
        body = system_text + "\n\n" + user
    try:
        from engel_ai import ask_engel_ai

        reply = str(ask_engel_ai(body) or "").strip()
    except Exception as exc:
        return _response(
            ok=False,
            text="Engel AI Main could not process the local request.",
            error_code="route_exception",
            error=type(exc).__name__,
            error_detail=str(exc),
            **_route_details(user),
        )
    if not reply:
        reply = "Engel AI Main local API had no route reply for that turn."
    error_code = _reply_error_code(reply)
    route_details = _route_details(user)
    if error_code:
        return _response(
            ok=False,
            text=reply,
            error_code=error_code,
            error=error_code,
            error_detail=reply,
            **route_details,
        )
    return _response(ok=True, text=reply, **route_details)


def _write_json(payload: dict[str, Any]) -> None:
    """Write UTF-8 JSON even when a Windows console defaults to cp1252."""
    stream = sys.stdout
    try:
        # Text pipes and modern Windows consoles accept UTF-8.  ``reconfigure``
        # is unavailable on a few test doubles, so the fallback below remains.
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError, ValueError):
        pass
    try:
        encoded = json.dumps(payload, ensure_ascii=False)
        stream.write(encoded + "\n")
    except UnicodeEncodeError:
        # A legacy cp1252 stream must still receive a valid JSON document.  The
        # escaped representation is ASCII and preserves every code point.
        stream.write(json.dumps(payload, ensure_ascii=True) + "\n")
    stream.flush()


def run_stdio_chat() -> int:
    # The wire format is UTF-8 JSON even when a Windows parent process has a
    # legacy cp1252 console.  Reconfigure the input side as well as stdout so
    # non-ASCII prompts survive a stdio hop unchanged.
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass
    # Windows PowerShell's native pipeline may prefix UTF-8 text with a BOM.
    # Accept that transport marker before decoding the JSON envelope; without
    # this, a perfectly valid `{"prompt":"ping"}` arrives as an invalid
    # document and is mistakenly treated as literal chat text.
    raw = sys.stdin.read().lstrip("\ufeff")
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {"prompt": raw}
    if not isinstance(payload, dict):
        payload = {"prompt": str(payload)}
    result = chat(
        str(payload.get("prompt") or payload.get("user") or ""),
        system=str(payload.get("system") or ""),
    )
    _write_json(result)
    return 0 if result.get("ok") is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Engel AI Main local API (stdio, no HTTP)."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="ping",
        choices=("ping", "status", "chat"),
        help="ping | status | chat (JSON on stdin)",
    )
    args = parser.parse_args(argv)
    if args.command == "chat":
        return run_stdio_chat()
    payload = ping() if args.command == "ping" else status()
    _write_json(payload)
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
