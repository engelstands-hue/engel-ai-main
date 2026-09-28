#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_core_v1_dashboard_status.py"
AI_BODY = ROOT / "engel_ai_body_status.py"
COMPANION = ROOT / "engel_companion.py"
SUPER_SWARM = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"

AUTHORITY = "Josh > Guardian > Engel/runtime"


class CheckFailure(Exception):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _compile(path: Path) -> None:
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker))
    _require(start >= 0, "missing start marker: " + start_marker)
    _require(end >= 0, "missing end marker: " + end_marker)
    return text[start:end]


def check_helper_static() -> None:
    _compile(HELPER)
    source = _read(HELPER)
    for needle in [
        "get_core_v1_dashboard_status",
        "render_core_v1_dashboard_status",
        "ENGEL_CORE_CONTINUITY_MAP_V1.json",
        "ENGEL_BROWSER_QUEEN_CONTRACT_V1.json",
        "ENGEL_MEMORY_CANDIDATE_WORKFLOW_CONTRACT_V1.json",
        "ENGEL_RESEARCH_INTAKE_QUEUE_CONTRACT_V1.json",
        "ENGEL_CORE_STABILIZATION_CHECKPOINT_V1.md",
        "ENGEL CORE V1 COMMAND CENTER",
        "LIVE BASELINE",
        "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
        "NO TRUSTED MEMORY WRITE",
        "BROWSER QUEEN DISABLED",
        "Untrusted Content Guard",
        "Prompt Injection Guard",
        "MISSING",
        "MALFORMED",
    ]:
        _require(needle in source, "dashboard helper missing required text: " + needle)
    for forbidden in [
        "build_engel_core_continuity_map",
        "verify_engel_core_continuity_map",
        "subprocess",
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "playwright",
        "selenium",
        "puppeteer",
        "pyautogui",
        "chromedriver",
        ".glob(",
        ".rglob(",
        "os.walk",
    ]:
        _require(forbidden.lower() not in source.lower(), "dashboard helper contains forbidden behavior text: " + forbidden)

    tree = ast.parse(source)
    blocked_import_roots = {
        "http",
        "os",
        "requests",
        "socket",
        "subprocess",
        "threading",
        "urllib",
        "webbrowser",
    }
    blocked_methods = {
        "glob",
        "mkdir",
        "open",
        "remove",
        "rename",
        "replace",
        "rglob",
        "rmdir",
        "touch",
        "unlink",
        "write",
        "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, "blocked import in dashboard helper: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            _require(root not in blocked_import_roots, "blocked import in dashboard helper: " + str(node.module))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            _require(node.func.attr not in blocked_methods, "blocked file/process method in dashboard helper: " + node.func.attr)


def check_helper_behavior() -> None:
    _require(CORE_JSON.exists(), "Core Continuity Map JSON missing")
    sys.path.insert(0, str(ROOT))
    helper = importlib.import_module("engel_core_v1_dashboard_status")
    status = helper.get_core_v1_dashboard_status()
    rendered = helper.render_core_v1_dashboard_status()

    _require(status["title"] == "ENGEL CORE V1 COMMAND CENTER", "dashboard title mismatch")
    _require(status["core_status"] == "LIVE BASELINE", "dashboard must report live baseline")
    _require(status["authority"] == AUTHORITY, "dashboard authority mismatch")
    _require(status["browser_queen_status"] == "DISABLED", "Browser Queen must remain disabled")
    _require(status["browser_queen_path"] == "Research Intake \u2192 Overnight Research", "Browser Queen research path mismatch")
    _require(status["trusted_memory_status"] == "BLOCKED / NOT_PERFORMED", "trusted memory status mismatch")
    _require(status["untrusted_content_guard"] == "ACTIVE", "Untrusted Content Guard status mismatch")
    _require(status["prompt_injection_guard"] == "ACTIVE", "Prompt Injection Guard status mismatch")
    _require(status["dashboard_mode"] == "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED", "dashboard mode mismatch")
    _require("NO TRUSTED MEMORY WRITE" in status["badges"], "dashboard badges missing trusted-memory boundary")
    for needle in [
        "ENGEL CORE V1 COMMAND CENTER",
        "Core: LIVE BASELINE",
        "Browser Queen: DISABLED",
        "Trusted Memory: BLOCKED / NOT_PERFORMED",
        "Untrusted Content Guard ACTIVE",
        "Prompt Injection Guard ACTIVE",
        "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
    ]:
        _require(needle in rendered, "rendered dashboard missing text: " + needle)

    original_root = helper.APP_ROOT
    try:
        helper.APP_ROOT = ROOT / "__missing_core_v1_dashboard_fixture__"
        fallback = helper.get_core_v1_dashboard_status()
    finally:
        helper.APP_ROOT = original_root
    _require(fallback["core_status"] == "INDEX UNAVAILABLE", "missing JSON fallback must be safe")
    _require(fallback["trusted_memory_status"] == "BLOCKED / NOT_PERFORMED", "fallback trusted memory must remain blocked")
    _require(fallback["dashboard_mode"] == "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED", "fallback dashboard mode mismatch")


def check_ai_body_integration() -> None:
    _compile(AI_BODY)
    source = _read(AI_BODY)
    for needle in [
        "from engel_core_v1_dashboard_status import get_core_v1_dashboard_status",
        "core_v1_dashboard",
        "ENGEL CORE V1 COMMAND CENTER",
        "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
        "NO TRUSTED MEMORY WRITE",
        "Browser Queen:",
        "Untrusted Content Guard",
        "Prompt Injection Guard",
    ]:
        _require(needle in source, "AI Body helper missing dashboard integration text: " + needle)
    for forbidden in [
        "build_engel_core_continuity_map",
        "verify_engel_core_continuity_map",
        "write_core_v1_dashboard",
    ]:
        _require(forbidden not in source, "AI Body helper must not run builders/writers: " + forbidden)


def check_gui_sources() -> None:
    for path, label, start_marker, end_marker in [
        (COMPANION, "Companion", "ENGEL_AI_BODY_COMPANION_PANEL_START", "ENGEL_AI_BODY_COMPANION_PANEL_END"),
        (SUPER_SWARM, "Super Swarm", "ENGEL_AI_BODY_SUPER_SWARM_PANEL_START", "ENGEL_AI_BODY_SUPER_SWARM_PANEL_END"),
    ]:
        _compile(path)
        source = _read(path)
        panel = _between(source, start_marker, end_marker)
        for needle in [
            "ENGEL CORE V1 COMMAND CENTER",
            "CORE V1",
            "READ ONLY",
            "JOSH FIRST",
            "GUARDIAN ACTIVE",
            "NO TRUSTED MEMORY WRITE",
            "BROWSER QUEEN DISABLED",
            "Trusted Memory:",
            "Browser Queen:",
            "Research Intake",
            "Untrusted Content Guard",
            "Prompt Injection Guard",
            "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
        ]:
            _require(needle in panel, label + " panel missing dashboard text: " + needle)
        for forbidden in [
            "build_engel_core_continuity_map",
            "verify_engel_core_continuity_map",
            "Start-Process",
            "subprocess",
            "Popen",
            "os.system",
            "write_text",
            "APPROVE_MEMORY",
            "APPROVE_PRODUCT_PATCH",
            "launch_browser",
            "navigate",
        ]:
            _require(forbidden not in panel, label + " dashboard panel contains forbidden operation: " + forbidden)


def main() -> int:
    checks = [
        ("helper_static", check_helper_static),
        ("helper_behavior", check_helper_behavior),
        ("ai_body_integration", check_ai_body_integration),
        ("gui_sources", check_gui_sources),
    ]
    try:
        for name, check in checks:
            check()
            print("PASS " + name)
    except CheckFailure as exc:
        print("FAIL: " + str(exc))
        return 1
    print("\nENGEL_CORE_V1_DASHBOARD_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
