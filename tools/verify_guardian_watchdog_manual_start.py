#!/usr/bin/env python3
"""
Verifier for ENGEL_GUARDIAN_WATCHDOG_MANUAL_START_V1.

This verifier checks the manual-start UI/source path without starting Engel.
It uses a temporary receipt root for dry-run receipt checks and does not
monitor, kill, restart, restore, build, promote, or mutate trusted memory.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType


_FILE = globals().get("__file__")
if not _FILE or not isinstance(_FILE, str) or _FILE.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_FILE).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

WATCHDOG_SOURCE = ROOT / "engel_guardian_watchdog.py"
UI_STATUS_VERIFIER = ROOT / "tools" / "verify_guardian_watchdog_ui_status.py"
STATUS_VERIFIER = ROOT / "tools" / "verify_guardian_watchdog_status.py"
CONTRACT_VERIFIER = ROOT / "tools" / "verify_guardian_watchdog_contract.py"

SUCCESS_MARKER = "GUARDIAN_WATCHDOG_MANUAL_START_VERIFICATION_PASS"
UI_STATUS_SUCCESS_MARKER = "GUARDIAN_WATCHDOG_UI_STATUS_VERIFICATION_PASS"
STATUS_SUCCESS_MARKER = "GUARDIAN_WATCHDOG_STATUS_VERIFICATION_PASS"
CONTRACT_SUCCESS_MARKER = "GUARDIAN_WATCHDOG_CONTRACT_VERIFICATION_PASS"

APPROVED_LIVE_ROOT = ROOT / "live" / "app"
APPROVED_TARGET = APPROVED_LIVE_ROOT / "Engel.exe"
UNAPPROVED_SUPER_SWARM_TARGET = APPROVED_LIVE_ROOT / "EngelSuperSwarmHive3D.exe"

REQUIRED_SOURCE_MARKERS = [
    "APPROVED_ENGEL_TARGET",
    "MANUAL_START_RECEIPT_ROOT",
    "MANUAL_START_COPY",
    "validate_approved_engel_target",
    "manual_start_engel",
    "write_manual_start_receipt",
    "launch_approved_engel_process",
    "Start Engel",
    "Manual start only. No auto-restart, no restore, no monitoring loop.",
]

FORBIDDEN_SOURCE_TOKENS = [
    "os.kill",
    "os.system",
    "os.startfile",
    "Popen",
    "Start-Process",
    "Stop-Process",
    "taskkill",
    "TerminateProcess",
    "kill_process",
    "restart_on_crash_enabled = True",
    "auto_restart_enabled = True",
    "auto_restore_enabled = True",
    "restore_allowed = True",
    "monitoring_loop_enabled = True",
    "while True",
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
    "EngelSuperSwarmHive3D",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def pass_line(label: str) -> None:
    print(f"PASS {label}")


def read_source() -> str:
    require(WATCHDOG_SOURCE.exists(), f"missing watchdog source: {WATCHDOG_SOURCE}")
    text = WATCHDOG_SOURCE.read_text(encoding="utf-8", errors="replace")
    require(text.strip(), "watchdog source is empty")
    return text


def check_source_compiles() -> None:
    py_compile.compile(str(WATCHDOG_SOURCE), doraise=True)
    ast.parse(WATCHDOG_SOURCE.read_text(encoding="utf-8", errors="replace"), filename=str(WATCHDOG_SOURCE))
    pass_line("source_compiles")


def check_source_markers(text: str) -> None:
    missing = [marker for marker in REQUIRED_SOURCE_MARKERS if marker not in text]
    require(not missing, f"missing manual-start source markers: {missing}")
    pass_line("manual_start_source_markers_exist")


def check_forbidden_tokens(text: str) -> None:
    found = [token for token in FORBIDDEN_SOURCE_TOKENS if token in text]
    require(not found, f"forbidden manual-start source tokens found: {found}")
    pass_line("no_auto_restart_restore_kill_or_super_swarm_tokens")


def check_manual_start_is_user_action_only(text: str) -> None:
    tree = ast.parse(text, filename=str(WATCHDOG_SOURCE))
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    call_scopes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "manual_start_engel":
            cursor: ast.AST | None = node
            scope = "<module>"
            while cursor in parents:
                cursor = parents[cursor]
                if isinstance(cursor, ast.FunctionDef):
                    scope = cursor.name
                    break
            call_scopes.append(scope)

    require(call_scopes == ["handle_manual_start"], f"manual_start_engel calls must stay behind the UI button: {call_scopes}")
    pass_line("manual_start_requires_user_button_action")


def load_watchdog_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("engel_guardian_watchdog_manual_start_verify", WATCHDOG_SOURCE)
    require(spec is not None and spec.loader is not None, "could not load watchdog module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check_path_validation(module: ModuleType) -> None:
    ok, target, reason = module.validate_approved_engel_target()
    require(target == APPROVED_TARGET.resolve(strict=False), f"default target mismatch: {target}")
    require(ok, f"approved Engel target must validate when present: {reason}")

    outside_ok, _, outside_reason = module.validate_approved_engel_target(ROOT / "memory" / "Engel.exe")
    require(not outside_ok, "arbitrary path outside live app root must be rejected")
    require("outside" in outside_reason or "approved" in outside_reason, f"unexpected outside rejection reason: {outside_reason}")

    super_ok, _, super_reason = module.validate_approved_engel_target(UNAPPROVED_SUPER_SWARM_TARGET)
    require(not super_ok, "Super Swarm target must not be accepted by first manual-start slice")
    require("approved" in super_reason, f"unexpected Super Swarm rejection reason: {super_reason}")

    traversal_ok, _, traversal_reason = module.validate_approved_engel_target(APPROVED_LIVE_ROOT / ".." / "app" / "Engel.exe")
    require(not traversal_ok, "parent traversal input must be rejected")
    require("traversal" in traversal_reason, f"unexpected traversal rejection reason: {traversal_reason}")

    pass_line("approved_path_validation_and_arbitrary_path_rejection")


def check_dry_run_receipt(module: ModuleType) -> None:
    with tempfile.TemporaryDirectory(prefix="engel_watchdog_manual_start_") as temp_root:
        result = module.manual_start_engel(
            receipt_root=Path(temp_root),
            launch=False,
            inspect_existing=False,
        )
        require(result.launch_attempted is False, "dry-run must not attempt launch")
        require(result.launch_succeeded is False, "dry-run must not report launch success")
        require(result.refusal_reason is None, f"dry-run should not refuse valid target: {result.refusal_reason}")
        require(result.receipt_path, "dry-run receipt path missing")
        receipt_path = Path(result.receipt_path)
        require(receipt_path.exists(), "dry-run receipt was not created in temp root")
        require(receipt_path.parent == Path(temp_root), "receipt must stay inside verifier temp root")
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
        require(data.get("action") == "manual_start", "receipt action mismatch")
        require(data.get("target_display_name") == "Engel", "receipt target display mismatch")
        require(data.get("path_validation_result") == "approved", "receipt path validation mismatch")
        require(data.get("launch_attempted") is False, "receipt dry-run launch_attempted mismatch")
        require(data.get("launch_succeeded") is False, "receipt dry-run launch_succeeded mismatch")
        safety = data.get("safety_flags")
        require(isinstance(safety, dict), "receipt safety flags missing")
        for key in (
            "auto_restart_enabled",
            "auto_restore_enabled",
            "monitoring_loop_enabled",
            "process_kill_allowed",
            "restore_allowed",
            "trusted_memory_write_allowed",
            "source_mutation_allowed",
            "route_mutation_allowed",
            "queue_mutation_allowed",
            "provider_api_allowed",
            "network_allowed",
            "local_llm_inference_allowed",
            "mobile_runtime_allowed",
            "remote_queen_runtime_allowed",
        ):
            require(safety.get(key) is False, f"receipt safety flag must be false: {key}")
        require("No auto-restart" in data.get("no_auto_restart_statement", ""), "receipt auto-restart boundary missing")
        require("No restore" in data.get("no_restore_statement", ""), "receipt restore boundary missing")
        require("No monitoring loop" in data.get("no_monitoring_loop_statement", ""), "receipt monitor boundary missing")

    pass_line("temp_receipt_behavior_without_launch")


def run_verifier(path: Path, marker: str, label: str) -> None:
    require(path.exists(), f"missing prior verifier: {path}")
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
    require(marker in result.stdout, f"{label} success marker missing")
    pass_line(f"{label}_passes")


def main() -> int:
    print("INFO Guardian Watchdog manual-start verifier")
    print("INFO Mode: dry-run/source-only; no Engel launch, no monitor, no restart, no restore")
    try:
        text = read_source()
        check_source_compiles()
        check_source_markers(text)
        check_forbidden_tokens(text)
        check_manual_start_is_user_action_only(text)
        module = load_watchdog_module()
        check_path_validation(module)
        check_dry_run_receipt(module)
        run_verifier(UI_STATUS_VERIFIER, UI_STATUS_SUCCESS_MARKER, "ui_status_verifier")
        run_verifier(STATUS_VERIFIER, STATUS_SUCCESS_MARKER, "status_verifier")
        run_verifier(CONTRACT_VERIFIER, CONTRACT_SUCCESS_MARKER, "contract_verifier")
    except (CheckFailure, py_compile.PyCompileError, SyntaxError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}")
        return 1

    print(SUCCESS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
