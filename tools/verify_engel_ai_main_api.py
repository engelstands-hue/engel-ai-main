#!/usr/bin/env python3
"""Verify Engel AI Main reusable local API: stdio only, no HTTP server."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = ROOT / "engel_ai_main_api.py"
PYTHON = ROOT / "runtime" / "python310" / "python.exe"


def main() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, bool(ok)))
        print(("PASS " if ok else "FAIL ") + name)

    check("api_module_exists", API.is_file())
    source = API.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
    blocked = {"socket", "http", "urllib", "requests", "aiohttp"}
    check("api_does_not_import_http_or_sockets", not (set(imports) & blocked))
    check("api_does_not_mention_http_listener", "HTTPServer" not in source and "BaseHTTPRequestHandler" not in source)
    check("api_declares_no_http", "http\": False" in source.replace(" ", "") or '"http": False' in source)
    check(
        "api_has_utf8_console_fallback",
        "def _write_json" in source
        and "sys.stdin.reconfigure" in source
        and "lstrip(\"\\ufeff\")" in source
        and "reconfigure" in source
        and "ensure_ascii=True" in source,
    )
    check(
        "api_exposes_structured_route_failures",
        "_FAILURE_MARKERS" in source
        and "provider_not_configured" in source
        and "provider_bridge_error" in source
        and "bridge raised" in source,
    )

    import engel_ai_main_api as api

    ping = api.ping()
    check("ping_is_connected", ping.get("ok") is True and ping.get("text") == "connected")
    check("ping_has_no_http", ping.get("http") is False)
    status = api.status()
    check("status_ok", status.get("ok") is True and status.get("http") is False)
    original_exe = api._engel_main_executable
    api._engel_main_executable = lambda: Path("__engel_missing_main__.exe")
    try:
        missing_status = api.status()
    finally:
        api._engel_main_executable = original_exe
    check("status_fails_when_app_missing", missing_status.get("ok") is False and missing_status.get("error_code"))
    chat = api.chat("ping", system="Return a connection result.")
    check("chat_ping_is_connected", chat.get("text") == "connected" and chat.get("request_id") == "local-engel-cli")

    import engel_ai
    original_ask = engel_ai.ask_engel_ai
    engel_ai.ask_engel_ai = lambda _prompt: "No inference provider configured for this route."
    try:
        failed_chat = api.chat("run a local task")
    finally:
        engel_ai.ask_engel_ai = original_ask
    check("chat_failure_is_not_success", failed_chat.get("ok") is False and failed_chat.get("error_code") == "provider_not_configured")

    engel_ai.ask_engel_ai = lambda _prompt: "(Engel tried to route your message to the connected provider but the hermes-agent bridge raised FileNotFoundError.)"
    try:
        bridge_failed_chat = api.chat("continue the unfinished task")
    finally:
        engel_ai.ask_engel_ai = original_ask
    check(
        "chat_provider_bridge_failure_is_not_success",
        bridge_failed_chat.get("ok") is False
        and bridge_failed_chat.get("error_code") == "provider_bridge_error"
        and "FileNotFoundError" in str(bridge_failed_chat.get("error_detail") or ""),
    )

    engel_ai.ask_engel_ai = lambda _prompt: "A bounded local route reply."
    try:
        successful_chat = api.chat("summarize the local route")
    finally:
        engel_ai.ask_engel_ai = original_ask
    check(
        "chat_success_does_not_emit_failure_fields",
        successful_chat.get("ok") is True
        and "error_code" not in successful_chat
        and "error_detail" not in successful_chat,
    )

    class LegacyConsole:
        encoding = "cp1252"

        def __init__(self) -> None:
            self.values: list[str] = []
            self.first = True

        def reconfigure(self, **_kwargs: object) -> None:
            raise OSError("legacy console")

        def write(self, value: str) -> int:
            if self.first and "⚕" in value:
                self.first = False
                raise UnicodeEncodeError("cp1252", value, value.index("⚕"), value.index("⚕") + 1, "not encodable")
            self.values.append(value)
            return len(value)

        def flush(self) -> None:
            return None

    legacy = LegacyConsole()
    original_stdout = api.sys.stdout
    api.sys.stdout = legacy
    try:
        api._write_json({"ok": True, "text": "⚕"})
    finally:
        api.sys.stdout = original_stdout
    check("unicode_console_fallback_is_valid", legacy.values and "\\u2695" in legacy.values[-1])

    python = str(PYTHON if PYTHON.is_file() else sys.executable)
    completed = subprocess.run(
        [python, str(API), "ping"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        check=False,
        timeout=30,
    )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception:
        payload = {}
    check(
        "stdio_cli_ping",
        completed.returncode == 0 and payload.get("text") == "connected" and payload.get("http") is False,
    )

    # Windows PowerShell can prepend a UTF-8 BOM when piping JSON to a native
    # process.  The public stdio API must still recognize the envelope rather
    # than treating the whole JSON document as the user's prompt.
    bom_completed = subprocess.run(
        [python, str(API), "chat"],
        input="\ufeff{\"prompt\":\"ping\"}",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        check=False,
        timeout=30,
    )
    try:
        bom_payload = json.loads(bom_completed.stdout.strip().splitlines()[-1])
    except Exception:
        bom_payload = {}
    check(
        "stdio_cli_accepts_utf8_bom",
        bom_completed.returncode == 0
        and bom_payload.get("text") == "connected"
        and bom_payload.get("http") is False,
    )

    failed = [name for name, ok in checks if not ok]
    if failed:
        print("ENGEL_AI_MAIN_API_VERIFY_FAIL")
        return 1
    print(f"ENGEL_AI_MAIN_API_VERIFY_PASS {len(checks)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
