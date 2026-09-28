#!/usr/bin/env python3
"""
Static verifier for ENGEL_GUARDIAN_WATCHDOG_UI_STATUS_V1.

This verifier checks the status-only Guardian Watchdog UI source without
opening a GUI or starting any process monitoring. It does not import Engel
runtime modules, start or stop Engel, restore files, build, promote, or mutate
routes/queues/source beyond reading the target files.
"""

from __future__ import annotations

import ast
import importlib.util
import py_compile
import subprocess
import sys
from pathlib import Path


_FILE = globals().get("__file__")
if not _FILE or not isinstance(_FILE, str) or _FILE.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_FILE).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

UI_SOURCE = ROOT / "engel_guardian_watchdog.py"
CONTRACT_VERIFIER = ROOT / "tools" / "verify_guardian_watchdog_contract.py"
STATUS_VERIFIER = ROOT / "tools" / "verify_guardian_watchdog_status.py"
SUCCESS_MARKER = "GUARDIAN_WATCHDOG_UI_STATUS_VERIFICATION_PASS"
CONTRACT_SUCCESS_MARKER = "GUARDIAN_WATCHDOG_CONTRACT_VERIFICATION_PASS"
STATUS_SUCCESS_MARKER = "GUARDIAN_WATCHDOG_STATUS_VERIFICATION_PASS"

REQUIRED_UI_TEXT = [
    "Engel Guardian Watchdog",
    "Engel status",
    "unknown",
    "Watchdog mode",
    "OFF",
    "Watchdog enabled",
    "no",
    "Single instance lock",
    "not held",
    "Last known good backup",
    "Last known good hash status",
    "Last crash time",
    "Last restore status",
    "Restart count",
    "Restart limit",
    "Last receipt path",
    "Source mutation OFF",
    "Trusted memory write OFF",
    "Provider/API OFF",
    "Local LLM OFF",
    "Mobile/Remote Queen OFF",
    "Restore requires verified mode configuration",
    "ON/OFF toggle visible",
    "Mode selector",
    "status only",
    "Exit Watchdog",
]

REQUIRED_SUMMARY_LINES = [
    "Engel status: unknown",
    "Watchdog mode: OFF",
    "Watchdog enabled: no",
    "Single instance lock: not held",
    "Last known good backup: not configured",
    "Last known good hash status: not_checked",
    "Last crash time: none",
    "Last restore status: disabled",
    "Restart count: 0",
    "Restart limit: 0",
    "Last receipt path: none",
    "Source mutation: OFF",
    "Trusted memory write: OFF",
    "Provider/API: OFF",
    "Local LLM: OFF",
    "Mobile/Remote Queen: OFF",
]

FORBIDDEN_IMPORT_ROOTS = {
    "asyncio",
    "ftplib",
    "http",
    "llama_cpp",
    "multiprocessing",
    "openai",
    "psutil",
    "requests",
    "schedule",
    "sched",
    "shutil",
    "smtplib",
    "socket",
    "subprocess",
    "threading",
    "torch",
    "transformers",
    "urllib",
    "win32service",
}

FORBIDDEN_SOURCE_TOKENS = [
    "os.kill",
    "os.system",
    "os.startfile",
    "subprocess",
    "Popen",
    "Start-Process",
    "Stop-Process",
    "taskkill",
    "tasklist",
    "Get-Process",
    "wmic",
    "psutil",
    "CreateService",
    "win32service",
    "schtasks",
    "Task Scheduler",
    "shutil.copy",
    "shutil.move",
    "copyfile",
    "copytree",
    "rmtree",
    ".unlink(",
    ".rename(",
    ".replace(",
    ".write_text(",
    ".write_bytes(",
    "live\\app",
    "live/app",
    ".exe",
    "backups\\",
    "backups/",
    "provider_api_call",
    "run_local_llm",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def pass_line(label: str) -> None:
    print(f"PASS {label}")


def read_source() -> str:
    require(UI_SOURCE.exists(), f"missing UI source: {UI_SOURCE}")
    text = UI_SOURCE.read_text(encoding="utf-8", errors="replace")
    require(text.strip(), "UI source must not be empty")
    return text


def check_source_compiles() -> None:
    py_compile.compile(str(UI_SOURCE), doraise=True)
    ast.parse(UI_SOURCE.read_text(encoding="utf-8", errors="replace"), filename=str(UI_SOURCE))
    pass_line("source_compiles")


def check_required_ui_strings(text: str) -> None:
    missing = [item for item in REQUIRED_UI_TEXT if item not in text]
    require(not missing, f"UI source missing required strings: {missing}")
    pass_line("ui_strings_exist")


def check_forbidden_imports(text: str) -> None:
    tree = ast.parse(text, filename=str(UI_SOURCE))
    forbidden: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    forbidden.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                forbidden.append(module)
    require(not forbidden, f"forbidden imports found in UI source: {forbidden}")
    pass_line("no_network_provider_llm_process_service_imports")


def check_forbidden_tokens(text: str) -> None:
    found = [token for token in FORBIDDEN_SOURCE_TOKENS if token in text]
    require(not found, f"forbidden process/restore/live-artifact tokens found: {found}")
    pass_line("no_process_kill_start_restart_restore_calls")
    pass_line("no_service_scheduler_creation")
    pass_line("no_live_exe_or_backup_modification_code")


def run_verifier(path: Path, success_marker: str, label: str) -> None:
    require(path.exists(), f"missing verifier: {path}")
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"INFO {label} {line}")
    if result.stderr:
        for line in result.stderr.splitlines():
            print(f"INFO {label}_stderr {line}")
    require(result.returncode == 0, f"{label} failed")
    require(success_marker in result.stdout, f"{label} success marker missing")
    pass_line(f"{label}_passes")


def load_ui_module() -> object:
    spec = importlib.util.spec_from_file_location("engel_guardian_watchdog_ui_status_verify", UI_SOURCE)
    require(spec is not None and spec.loader is not None, "could not load UI module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_summary_semantics() -> None:
    module = load_ui_module()
    status = module.load_status_template()
    lines = module.build_summary_lines(status)
    missing = [line for line in REQUIRED_SUMMARY_LINES if line not in lines]
    require(not missing, f"UI summary missing required safe values: {missing}")
    require(getattr(module, "RESTORE_REQUIRES_COPY") == "Restore requires verified mode configuration", "restore boundary copy mismatch")
    require("Source mutation OFF" in getattr(module, "SAFETY_BOUNDARY_COPY"), "source mutation OFF boundary missing")
    require("Trusted memory write OFF" in getattr(module, "SAFETY_BOUNDARY_COPY"), "trusted memory OFF boundary missing")
    require("Provider/API OFF" in getattr(module, "SAFETY_BOUNDARY_COPY"), "provider/API OFF boundary missing")
    require("Local LLM OFF" in getattr(module, "SAFETY_BOUNDARY_COPY"), "Local LLM OFF boundary missing")
    require("Mobile/Remote Queen OFF" in getattr(module, "SAFETY_BOUNDARY_COPY"), "Mobile/Remote Queen OFF boundary missing")
    pass_line("status_summary_semantics_safe")


def main() -> int:
    print("INFO Guardian Watchdog UI status verifier")
    print("INFO Mode: static/source-only; no GUI launch, no monitor, no process action")
    try:
        text = read_source()
        check_source_compiles()
        check_required_ui_strings(text)
        check_forbidden_imports(text)
        check_forbidden_tokens(text)
        check_summary_semantics()
        run_verifier(CONTRACT_VERIFIER, CONTRACT_SUCCESS_MARKER, "contract_verifier")
        run_verifier(STATUS_VERIFIER, STATUS_SUCCESS_MARKER, "status_verifier")
    except (CheckFailure, py_compile.PyCompileError, SyntaxError) as exc:
        print(f"FAIL {exc}")
        return 1

    print(SUCCESS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
