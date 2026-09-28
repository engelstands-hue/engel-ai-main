#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_core_v1_daily_check.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CORE_V1_DAILY_CHECK_STATUS_SNAPSHOT.md"
SNAPSHOT_ROOT = ROOT / "reports" / "core_status_snapshots"
AUTHORITY = "Josh > Guardian > Engel/runtime"
TRUSTED_MEMORY_SENTINELS = [
    ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "prompts" / "ENGEL_SYSTEM.md",
]
SOURCE_SENTINELS = [
    ROOT / "engel_core_v1_daily_check.py",
    ROOT / "engel_core_v1_dashboard_status.py",
    ROOT / "engel_browser_queen_status.py",
]


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def _compile(path: Path) -> None:
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def _hash_existing(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.exists() and path.is_file()}


def _snapshot_files() -> set[Path]:
    if not SNAPSHOT_ROOT.exists():
        return set()
    return {path for path in SNAPSHOT_ROOT.glob("*.md") if path.is_file()}


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _load_helper():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_core_v1_daily_check", HELPER)
    _require(spec is not None and spec.loader is not None, "could not load daily check helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_core_v1_daily_check"] = module
    spec.loader.exec_module(module)
    return module


def check_static_source() -> None:
    _compile(HELPER)
    source = _read(HELPER)
    tree = ast.parse(source)
    for needle in [
        "class CoreStatusSnapshot",
        "build_core_v1_status_snapshot",
        "render_core_v1_status_snapshot",
        "write_core_v1_status_snapshot",
        "MANUAL_SNAPSHOT / READ_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "This is not a scheduler.",
        "This is not background work.",
        "This is not autonomy.",
        "DISABLED",
        "BLOCKED / NOT_PERFORMED",
        "Next safe step:",
        AUTHORITY,
    ]:
        _require(needle in source, "daily check helper missing text: " + needle)

    blocked_import_roots = {
        "asyncio",
        "httpx",
        "openai",
        "anthropic",
        "requests",
        "socket",
        "urllib",
        "webbrowser",
        "threading",
        "multiprocessing",
        "schedule",
        "apscheduler",
        "selenium",
        "playwright",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, "daily check imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "daily check imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in {"eval", "exec", "__import__", "open"}, "daily check calls blocked builtin: " + func.id)
            elif isinstance(func, ast.Attribute):
                if func.attr == "run":
                    continue
                _require(func.attr not in {"Popen", "call", "check_call", "check_output", "start", "Timer"}, "daily check calls blocked method: " + func.attr)
    _require("shell=False" in source, "git status subprocess must use shell=False")
    _require("[\"git\", \"status\", \"--short\"]" in source, "git status command must stay bounded")
    for forbidden in [
        "while True",
        "BackgroundScheduler",
        "cron",
        "setInterval",
        "browser.launch",
        "page.goto",
        "webbrowser.open",
        "pip install",
        "npm install",
    ]:
        _require(forbidden not in source, "daily check contains forbidden behavior text: " + forbidden)


def check_behavior() -> None:
    helper = _load_helper()
    before_trusted = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    before_source = _hash_existing(SOURCE_SENTINELS)
    before_snapshots = _snapshot_files()

    snapshot = helper.build_core_v1_status_snapshot()
    rendered = helper.render_core_v1_status_snapshot(snapshot)
    _require(snapshot.status == "MANUAL_SNAPSHOT / READ_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED", "snapshot status mismatch")
    _require(snapshot.authority == AUTHORITY, "snapshot authority mismatch")
    for needle in [
        "# Engel Core V1 Status Snapshot",
        "MANUAL_SNAPSHOT / READ_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "READ_ONLY",
        "NOT_TRUSTED_MEMORY",
        "NOT_APPLIED",
        AUTHORITY,
        "Git status:",
        "Verifier status:",
        "Products:",
        "Research intake:",
        "Lessons:",
        "Memory candidates:",
        "Browser Queen:",
        "DISABLED",
        "Trusted memory:",
        "BLOCKED",
        "Untrusted Content Guard: ACTIVE",
        "Prompt Injection Guard: ACTIVE",
        "Next safe step:",
        "This is not a scheduler.",
        "This is not background work.",
        "This is not autonomy.",
        "No trusted memory write.",
        "No API/network/browser behavior.",
    ]:
        _require(needle in rendered, "snapshot render missing text: " + needle)

    after_render_trusted = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    after_render_source = _hash_existing(SOURCE_SENTINELS)
    _require(before_trusted == after_render_trusted, "build/render changed trusted memory files")
    _require(before_source == after_render_source, "build/render changed source files")
    _require(before_snapshots == _snapshot_files(), "build/render unexpectedly wrote a snapshot")

    written = helper.write_core_v1_status_snapshot(snapshot)
    _require(written.exists(), "explicit snapshot write did not create file")
    _require(_is_relative_to(written, SNAPSHOT_ROOT), "snapshot write escaped reports/core_status_snapshots")
    text = written.read_text(encoding="utf-8", errors="replace")
    _require("MANUAL_SNAPSHOT / READ_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED" in text, "written snapshot missing status")

    after_write_trusted = _hash_existing(TRUSTED_MEMORY_SENTINELS)
    after_write_source = _hash_existing(SOURCE_SENTINELS)
    _require(before_trusted == after_write_trusted, "snapshot write changed trusted memory files")
    _require(before_source == after_write_source, "snapshot write changed source files")


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "ENGEL_CORE_V1_DAILY_CHECK_STATUS_SNAPSHOT",
        "Status COMPLETE",
        "Files changed",
        "Snapshot behavior",
        "Manual/read-only boundary",
        "Verification results",
        "Packaging skipped",
        "Safety statement",
        "MANUAL_SNAPSHOT / READ_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "This is not a scheduler",
        "does not write trusted memory",
        "does not write ALIVE_STATE",
        AUTHORITY,
    ]:
        _require(needle in text, "daily check report missing text: " + needle)


def main() -> int:
    checks = [
        ("static_source", check_static_source),
        ("behavior", check_behavior),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(name + ": " + str(exc))
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(name + ": unexpected error: " + str(exc))
            print("FAIL " + name + ": unexpected error: " + str(exc))

    if failures:
        print()
        print("ENGEL_CORE_V1_DAILY_CHECK_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_CORE_V1_DAILY_CHECK_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
