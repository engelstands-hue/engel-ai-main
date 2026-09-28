#!/usr/bin/env python3
"""Graph Studio must open one client window, never a console/WebEngine extra.

AI account sign-in may open a CLI or system-browser window. That is the allowed
outside-link exception. Software-download pages and embedded https navigation
are not allowed.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STUDIO = Path(r"D:\Graph_&_Loop_Studio")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    # Graph & Loop Studio is a separately installed companion application. A
    # Main-only checkout/package must remain verifiable when that companion is
    # not mounted on this desktop.
    if not STUDIO.is_dir():
        print("SKIP verify_engel_graph_studio_single_window: separate Graph Studio checkout is absent")
        return 0
    source = (STUDIO / "engel_graph_loop_studio.py").read_text(encoding="utf-8")
    launcher = (STUDIO / "launch_engel_graph_loop_studio.bat").read_text(encoding="utf-8")
    dart = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(encoding="utf-8")
    require("QWebEngineView(win)" in source, "unparented WebEngine can still spawn a Chromium window")
    require("CREATE_NO_WINDOW" in source, "spawned Studio can still attach a console")
    require("_python_executable(windowed=True)" in source, "source spawn still uses console python.exe")
    require("pythonw.exe" in launcher, "desktop shortcut still launches a visible console")
    require(r"runtime\python310\python.exe" not in launcher, "desktop shortcut still names console python.exe")
    require("pythonw.exe" in dart, "Engel Flutter Main still launches Graph Studio with python.exe")
    require("D:\\Graph_&_Loop_Studio" in dart, "Engel Flutter Main does not launch the standalone Studio home")
    setup_body = source.split("def openProviderSetup", 1)[-1].split("def startProviderTest", 1)[0]
    require("start_claude_cli_login" in setup_body and "start_grok_cli_login" in setup_body and "start_codex_cli_login" in setup_body, "AI CLI sign-in windows were removed")
    require("QDesktopServices.openUrl" in setup_body, "cloud AI account sign-in window was removed")
    require("ai_account_sign_in_url" in setup_body, "browser open is not limited to AI account sign-in")
    require("def acceptNavigationRequest" in source, "WebEngine still allows non-local navigation")
    require("QWebEngineUrlRequestInterceptor" in source, "WebEngine still allows outbound page requests")
    require("'--profile', 'standalone'" in dart, "Engel Flutter Main must launch Graph Studio as standalone")
    require("'--profile', 'engel'" not in dart, "Engel Flutter Main still auto-binds Engel App as Graph Studio flagship")
    spawn_body = source.split("def spawn_studio", 1)[-1].split("def render_graph_studio_status", 1)[0]
    require('"--profile", "engel"' not in spawn_body, "spawned Studio still auto-binds Engel App as flagship")
    print("ENGEL_GRAPH_STUDIO_SINGLE_WINDOW_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL verify_engel_graph_studio_single_window: {exc}")
        raise SystemExit(2) from exc
