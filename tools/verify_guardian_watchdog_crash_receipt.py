#!/usr/bin/env python3
"""
Verifier for ENGEL_GUARDIAN_WATCHDOG_CRASH_RECEIPT_V1.

This verifier exercises crash/update receipt logic in a temporary folder only.
It does not create a real crash event, monitor processes, restart Engel,
restore files, kill processes, modify live artifacts, build, promote, stage,
or commit.
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
RECEIPT_HELPER = ROOT / "engel_guardian_watchdog_receipts.py"
REAL_CRASH_RECEIPT_ROOT = ROOT / "reports" / "guardian_watchdog" / "crashes"
MANUAL_START_VERIFIER = ROOT / "tools" / "verify_guardian_watchdog_manual_start.py"
CONTRACT_VERIFIER = ROOT / "tools" / "verify_guardian_watchdog_contract.py"

SUCCESS_MARKER = "GUARDIAN_WATCHDOG_CRASH_RECEIPT_VERIFICATION_PASS"
MANUAL_START_SUCCESS_MARKER = "GUARDIAN_WATCHDOG_MANUAL_START_VERIFICATION_PASS"
CONTRACT_SUCCESS_MARKER = "GUARDIAN_WATCHDOG_CONTRACT_VERIFICATION_PASS"

REQUIRED_HELPER_MARKERS = [
    "CRASH_RECEIPT_ROOT",
    "REQUIRED_CRASH_RECEIPT_FIELDS",
    "build_crash_receipt_payload",
    "validate_crash_receipt_payload",
    "write_crash_receipt",
    "record_crash_receipt",
    "restart_attempted",
    "restore_attempted",
    "human_review_required",
    "recent_update_build_report",
    "last_known_good_backup",
]

REQUIRED_RECEIPT_FIELDS = [
    "receipt_id",
    "timestamp",
    "watched_process",
    "expected_path",
    "observed_status",
    "exit_code",
    "recent_update_build_report",
    "last_known_good_backup",
    "restart_attempted",
    "restore_attempted",
    "restart_count",
    "restart_limit",
    "crash_loop_detected",
    "result",
    "human_review_required",
]

FORBIDDEN_HELPER_TOKENS = [
    "subprocess",
    "Popen",
    "os.kill",
    "os.system",
    "os.startfile",
    "TerminateProcess",
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
    "restart_attempted\": True",
    "restore_attempted\": True",
    "restart_enabled\": True",
    "restore_enabled\": True",
    "monitor_loop_enabled\": True",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def pass_line(label: str) -> None:
    print(f"PASS {label}")


def read_text(path: Path) -> str:
    require(path.exists(), f"missing required file: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    require(text.strip(), f"file is empty: {path}")
    return text


def check_source_compiles() -> None:
    py_compile.compile(str(WATCHDOG_SOURCE), doraise=True)
    py_compile.compile(str(RECEIPT_HELPER), doraise=True)
    ast.parse(read_text(RECEIPT_HELPER), filename=str(RECEIPT_HELPER))
    pass_line("source_and_receipt_helper_compile")


def check_helper_markers(text: str) -> None:
    missing = [marker for marker in REQUIRED_HELPER_MARKERS if marker not in text]
    require(not missing, f"missing crash receipt helper markers: {missing}")
    pass_line("crash_receipt_helper_markers_exist")


def check_forbidden_tokens(text: str) -> None:
    found = [token for token in FORBIDDEN_HELPER_TOKENS if token in text]
    require(not found, f"forbidden crash receipt helper tokens found: {found}")
    pass_line("no_monitor_restart_restore_kill_or_live_mutation_tokens")


def load_receipt_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("engel_guardian_watchdog_receipts_verify", RECEIPT_HELPER)
    require(spec is not None and spec.loader is not None, "could not load receipt helper module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def real_crash_receipt_snapshot() -> set[str]:
    if not REAL_CRASH_RECEIPT_ROOT.exists():
        return set()
    return {str(path.relative_to(REAL_CRASH_RECEIPT_ROOT)) for path in REAL_CRASH_RECEIPT_ROOT.rglob("*") if path.is_file()}


def check_payload_shape(module: ModuleType) -> None:
    payload = module.build_crash_receipt_payload(
        observed_status="exited",
        exit_code=17,
        recent_update_build_report="not_known",
        restart_count=0,
        restart_limit=3,
    )
    missing = [field for field in REQUIRED_RECEIPT_FIELDS if field not in payload]
    require(not missing, f"crash receipt payload missing fields: {missing}")
    require(payload["watched_process"] == "Engel", "watched_process must be Engel")
    require(payload["observed_status"] == "exited", "observed_status mismatch")
    require(payload["exit_code"] == 17, "exit_code mismatch")
    require(payload["recent_update_build_report"] == "not_known", "recent update/build report mismatch")
    require(isinstance(payload["last_known_good_backup"], dict), "last_known_good_backup must be an object")
    require(payload["restart_attempted"] is False, "restart_attempted must be false")
    require(payload["restore_attempted"] is False, "restore_attempted must be false")
    require(payload["restart_count"] == 0, "restart_count mismatch")
    require(payload["restart_limit"] == 3, "restart_limit mismatch")
    require(payload["crash_loop_detected"] is False, "crash_loop_detected must be false below limit")
    require(payload["result"] == "recorded_report_only", "result mismatch")
    require(payload["human_review_required"] is True, "human_review_required must be true")
    safety = payload.get("safety_flags")
    require(isinstance(safety, dict), "safety_flags missing")
    unsafe = [key for key, value in safety.items() if value is not False]
    require(not unsafe, f"safety flags must all be false: {unsafe}")
    module.validate_crash_receipt_payload(payload)
    pass_line("crash_receipt_payload_shape_valid")


def check_crash_loop_detection(module: ModuleType) -> None:
    payload = module.build_crash_receipt_payload(
        observed_status="exited",
        restart_count=3,
        restart_limit=3,
    )
    require(payload["crash_loop_detected"] is True, "crash loop must be detected at limit")
    pass_line("crash_loop_detection_report_only")


def check_rejections(module: ModuleType) -> None:
    try:
        module.build_crash_receipt_payload(observed_status="")
    except module.CrashReceiptError:
        pass
    else:
        raise CheckFailure("empty observed_status must be rejected")

    try:
        module.build_crash_receipt_payload(observed_status="exited", restart_count=-1)
    except module.CrashReceiptError:
        pass
    else:
        raise CheckFailure("negative restart_count must be rejected")

    try:
        module.build_crash_receipt_payload(observed_status="exited", expected_path=ROOT / "memory" / "Engel.exe")
    except module.CrashReceiptError:
        pass
    else:
        raise CheckFailure("unapproved expected_path must be rejected")

    payload = module.build_crash_receipt_payload(observed_status="exited")
    payload["restart_attempted"] = True
    try:
        module.validate_crash_receipt_payload(payload)
    except module.CrashReceiptError:
        pass
    else:
        raise CheckFailure("restart_attempted true must be rejected")

    pass_line("invalid_crash_receipt_inputs_rejected")


def check_temp_receipt_write(module: ModuleType) -> None:
    before = real_crash_receipt_snapshot()
    with tempfile.TemporaryDirectory(prefix="engel_watchdog_crash_receipt_") as temp_root:
        temp_root_path = Path(temp_root)
        receipt_path = module.record_crash_receipt(
            observed_status="exited_after_update",
            exit_code=1,
            recent_update_build_report="not_known",
            restart_count=0,
            restart_limit=2,
            receipt_root=temp_root_path,
        )
        require(receipt_path.exists(), "temp crash receipt was not created")
        require(receipt_path.parent == temp_root_path, "temp crash receipt escaped temp root")
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
        for field in REQUIRED_RECEIPT_FIELDS:
            require(field in data, f"written receipt missing field: {field}")
        require(data["restart_attempted"] is False, "written receipt restart_attempted must be false")
        require(data["restore_attempted"] is False, "written receipt restore_attempted must be false")
        require(data["human_review_required"] is True, "written receipt human_review_required must be true")
        require(data["result"] == "recorded_report_only", "written receipt result mismatch")
    after = real_crash_receipt_snapshot()
    require(before == after, "verifier must not create or modify real crash receipts")
    pass_line("temp_receipt_write_only_no_real_crash_event")


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
    print("INFO Guardian Watchdog crash/update receipt verifier")
    print("INFO Mode: temp-receipt-only; no monitoring, restart, restore, process kill, or real crash event")
    try:
        helper_text = read_text(RECEIPT_HELPER)
        check_source_compiles()
        check_helper_markers(helper_text)
        check_forbidden_tokens(helper_text)
        module = load_receipt_module()
        check_payload_shape(module)
        check_crash_loop_detection(module)
        check_rejections(module)
        check_temp_receipt_write(module)
        run_verifier(MANUAL_START_VERIFIER, MANUAL_START_SUCCESS_MARKER, "manual_start_verifier")
        run_verifier(CONTRACT_VERIFIER, CONTRACT_SUCCESS_MARKER, "contract_verifier")
    except (CheckFailure, py_compile.PyCompileError, SyntaxError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}")
        return 1

    print(SUCCESS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
