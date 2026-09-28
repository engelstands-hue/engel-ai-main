#!/usr/bin/env python3
"""
Guardian Watchdog status-only UI.

This module renders a small local status window from the template-only
Guardian Watchdog status file. It does not monitor processes, start or stop
Engel, restart anything, restore files, create services/schedulers, or mutate
source/routes/queues/trusted memory.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
STATUS_TEMPLATE_PATH = ROOT / "memory" / "ENGEL_GUARDIAN_WATCHDOG_STATUS_TEMPLATE_V1.json"
LIVE_APP_ROOT = ROOT / "live" / "app"
APPROVED_TARGET_STEM = "Engel"
APPROVED_TARGET_SUFFIX = "." + "exe"
APPROVED_ENGEL_TARGET = LIVE_APP_ROOT / (APPROVED_TARGET_STEM + APPROVED_TARGET_SUFFIX)
MANUAL_START_RECEIPT_ROOT = ROOT / "reports" / "guardian_watchdog"

WINDOW_TITLE = "Engel Guardian Watchdog"
STATUS_ONLY_NOTICE = "Status only. No monitoring, restart, restore, or process control is active."
RESTORE_REQUIRES_COPY = "Restore requires verified mode configuration"
MANUAL_START_COPY = "Start Engel"
MANUAL_START_BOUNDARY_COPY = "Manual start only. No auto-restart, no restore, no monitoring loop."
SAFETY_BOUNDARY_COPY = (
    "Source mutation OFF | Trusted memory write OFF | Provider/API OFF | "
    "Local LLM OFF | Mobile/Remote Queen OFF"
)

WATCHDOG_MODES = [
    "OFF",
    "MONITOR_ONLY",
    "RESTART_ON_CRASH",
    "UPDATE_GUARD",
    "RESTORE_LAST_GOOD",
]

STATUS_LABELS = [
    "Engel status",
    "Watchdog mode",
    "Watchdog enabled",
    "Single instance lock",
    "Last known good backup",
    "Last known good hash status",
    "Last crash time",
    "Last restore status",
    "Restart count",
    "Restart limit",
    "Last receipt path",
    "Source mutation",
    "Trusted memory write",
    "Provider/API",
    "Local LLM",
    "Mobile/Remote Queen",
]

REQUIRED_STATUS_STRINGS = [
    "Engel status: unknown",
    "Watchdog mode: OFF",
    "Watchdog enabled: no",
    "Single instance lock: not held",
    "Source mutation OFF",
    "Trusted memory write OFF",
    "Provider/API OFF",
    "Local LLM OFF",
    "Mobile/Remote Queen OFF",
    RESTORE_REQUIRES_COPY,
    "Exit Watchdog",
]


ManualStartResult = SimpleNamespace


def load_status_template(path: Path = STATUS_TEMPLATE_PATH) -> dict[str, Any]:
    """Load the template-only status shape. This is a read-only operation."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Guardian Watchdog status template must be a JSON object.")
    return data


def _bool_no(value: object) -> str:
    return "yes" if value is True else "no"


def _off(value: object) -> str:
    return "ON" if value is True else "OFF"


def _lock_status(value: object) -> str:
    if value in {None, "", "not_created", "absent"}:
        return "not held"
    return str(value)


def _empty(value: object, fallback: str = "none") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _last_known_good_backup(value: object) -> str:
    if not isinstance(value, dict):
        return "not configured"
    if value.get("configured") is not True:
        return "not configured"
    pieces = [
        _empty(value.get("baseline_id"), "no baseline id"),
        _empty(value.get("backup_path"), "no backup path"),
    ]
    return " | ".join(pieces)


def build_status_rows(status: dict[str, Any]) -> list[tuple[str, str]]:
    """Convert the status template into display rows without side effects."""
    return [
        ("Engel status", _empty(status.get("engel_status"), "unknown")),
        ("Watchdog mode", _empty(status.get("watchdog_mode"), "OFF")),
        ("Watchdog enabled", _bool_no(status.get("watchdog_enabled"))),
        ("Single instance lock", _lock_status(status.get("single_instance_lock_status"))),
        ("Last known good backup", _last_known_good_backup(status.get("last_known_good_backup"))),
        ("Last known good hash status", _empty(status.get("last_known_good_hash_status"), "not_checked")),
        ("Last crash time", _empty(status.get("last_crash_time"), "none")),
        ("Last restore status", _empty(status.get("last_restore_status"), "disabled")),
        ("Restart count", _empty(status.get("restart_count"), "0")),
        ("Restart limit", _empty(status.get("restart_limit"), "0")),
        ("Last receipt path", _empty(status.get("last_receipt_path"), "none")),
        ("Source mutation", _off(status.get("source_mutation_allowed"))),
        ("Trusted memory write", _off(status.get("trusted_memory_write_allowed"))),
        ("Provider/API", _off(status.get("provider_api_allowed"))),
        ("Local LLM", _off(status.get("local_llm_inference_allowed"))),
        (
            "Mobile/Remote Queen",
            "ON"
            if status.get("mobile_runtime_allowed") is True or status.get("remote_queen_runtime_allowed") is True
            else "OFF",
        ),
    ]


def build_summary_lines(status: dict[str, Any]) -> list[str]:
    """Return simple text lines suitable for tests or non-GUI inspection."""
    return [f"{label}: {value}" for label, value in build_status_rows(status)]


def _safe_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_approved_engel_target(candidate_path: Path | str | None = None) -> tuple[bool, Path, str]:
    """Validate the one approved manual-start target without launching it."""
    requested = APPROVED_ENGEL_TARGET if candidate_path is None else Path(candidate_path)
    if any(part == ".." for part in requested.parts):
        return False, requested, "parent traversal is not allowed"
    if ":" in requested.name:
        return False, requested, "alternate stream syntax is not allowed"

    live_root = LIVE_APP_ROOT.resolve(strict=False)
    target = requested.resolve(strict=False)
    approved = APPROVED_ENGEL_TARGET.resolve(strict=False)

    if not _is_relative_to(target, live_root):
        return False, target, "target is outside the approved live app folder"
    if target != approved:
        return False, target, "target is not the approved Engel live application"
    if target.suffix.lower() != APPROVED_TARGET_SUFFIX:
        return False, target, "target suffix is not approved"
    if not target.exists():
        return False, target, "approved Engel live application is missing"
    if not target.is_file():
        return False, target, "approved Engel live application is not a file"
    return True, target, "approved"


def validate_last_known_good_for_manual_start(status: dict[str, Any], target: Path) -> tuple[bool, str]:
    """Validate last-known-good status only if the template says one is configured."""
    backup = status.get("last_known_good_backup")
    if not isinstance(backup, dict) or backup.get("configured") is not True:
        return True, "not_configured"

    backup_path = backup.get("backup_path")
    if not backup_path:
        return False, "configured_record_missing_backup_path"

    configured_target = Path(str(backup_path)).resolve(strict=False)
    if configured_target != target.resolve(strict=False):
        return False, "configured_record_target_mismatch"

    return False, "configured_record_requires_future_hash_verifier"


def _windows_running_instances(target: Path) -> tuple[str, list[str]]:
    if sys.platform != "win32":
        return "review_required_non_windows", []

    wintypes = ctypes.wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return "review_required_snapshot_failed", []

    matches: list[str] = []
    ambiguous = False
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(ProcessEntry)
        success = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            image_name = str(entry.szExeFile)
            if image_name.lower() == APPROVED_ENGEL_TARGET.name.lower():
                handle = kernel.OpenProcess(0x1000, False, entry.th32ProcessID)
                if not handle:
                    ambiguous = True
                else:
                    try:
                        size = wintypes.DWORD(32768)
                        buffer = ctypes.create_unicode_buffer(size.value)
                        ok = kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
                        if ok:
                            running_path = Path(buffer.value).resolve(strict=False)
                            if running_path == target.resolve(strict=False):
                                matches.append(str(running_path))
                        else:
                            ambiguous = True
                    finally:
                        kernel.CloseHandle(handle)
            success = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)

    if matches:
        return "already_running", matches
    if ambiguous:
        return "review_required_ambiguous_process_evidence", []
    return "clear", []


def launch_approved_engel_process(target: Path) -> tuple[bool, int | None, str | None]:
    """Launch the approved target after validation; no restart or monitoring is created."""
    if sys.platform != "win32":
        return False, None, "manual_start_requires_windows"

    wintypes = ctypes.wintypes

    class StartupInfo(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.c_void_p),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class ProcessInformation(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    startup = StartupInfo()
    startup.cb = ctypes.sizeof(StartupInfo)
    info = ProcessInformation()
    command_line = ctypes.create_unicode_buffer(f'"{target}"')
    ok = kernel.CreateProcessW(
        str(target),
        command_line,
        None,
        None,
        False,
        0,
        None,
        str(target.parent),
        ctypes.byref(startup),
        ctypes.byref(info),
    )
    if not ok:
        return False, None, f"launch_failed_error_{ctypes.get_last_error()}"

    try:
        return True, int(info.dwProcessId), None
    finally:
        kernel.CloseHandle(info.hThread)
        kernel.CloseHandle(info.hProcess)


def write_manual_start_receipt(result: ManualStartResult, receipt_root: Path | None = None) -> Path:
    root = MANUAL_START_RECEIPT_ROOT if receipt_root is None else receipt_root
    root.mkdir(parents=True, exist_ok=True)
    receipt_path = root / f"ENGEL_GUARDIAN_WATCHDOG_MANUAL_START_{result.receipt_id}.json"
    payload = dict(vars(result))
    payload["receipt_path"] = str(receipt_path)
    with receipt_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return receipt_path


def manual_start_engel(
    *,
    target_path: Path | str | None = None,
    status: dict[str, Any] | None = None,
    receipt_root: Path | None = None,
    launch: bool = True,
    inspect_existing: bool = True,
) -> ManualStartResult:
    receipt_id = f"{_safe_timestamp()}_{uuid.uuid4().hex[:8]}"
    status_data = load_status_template() if status is None else status
    path_ok, target, path_result = validate_approved_engel_target(target_path)
    lkg_ok, lkg_result = validate_last_known_good_for_manual_start(status_data, target)
    single_instance_result = "not_checked"
    launched = False
    process_id: int | None = None
    refusal_reason: str | None = None

    if not path_ok:
        refusal_reason = path_result
    elif not lkg_ok:
        refusal_reason = lkg_result
    elif launch and inspect_existing:
        single_instance_result, matches = _windows_running_instances(target)
        if single_instance_result != "clear":
            refusal_reason = single_instance_result
            if matches:
                refusal_reason = f"{single_instance_result}: {matches[0]}"
    elif not launch:
        single_instance_result = "not_checked_dry_run"

    launch_attempted = bool(launch and refusal_reason is None)
    if launch_attempted:
        launched, process_id, launch_error = launch_approved_engel_process(target)
        if not launched:
            refusal_reason = launch_error or "launch_failed"

    result = ManualStartResult(
        receipt_id=receipt_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        action="manual_start",
        target_path=str(target),
        target_display_name=APPROVED_TARGET_STEM,
        path_validation_result=path_result,
        last_known_good_validation_result=lkg_result,
        single_instance_validation_result=single_instance_result,
        launch_attempted=launch_attempted,
        launch_succeeded=launched,
        launched_process_id=process_id,
        receipt_path=None,
        refusal_reason=refusal_reason,
        safety_flags={
            "auto_restart_enabled": False,
            "auto_restore_enabled": False,
            "monitoring_loop_enabled": False,
            "process_kill_allowed": False,
            "restore_allowed": False,
            "trusted_memory_write_allowed": False,
            "source_mutation_allowed": False,
            "route_mutation_allowed": False,
            "queue_mutation_allowed": False,
            "provider_api_allowed": False,
            "network_allowed": False,
            "local_llm_inference_allowed": False,
            "mobile_runtime_allowed": False,
            "remote_queen_runtime_allowed": False,
        },
        no_auto_restart_statement="No auto-restart is enabled by manual start.",
        no_restore_statement="No restore is enabled by manual start.",
        no_monitoring_loop_statement="No monitoring loop is enabled by manual start.",
    )
    receipt_path = write_manual_start_receipt(result, receipt_root=receipt_root)
    result.receipt_path = str(receipt_path)
    return result


def create_window(status: dict[str, Any] | None = None) -> Any:
    """Create the status-only Tkinter window. No monitoring loop is started."""
    import tkinter as tk
    from tkinter import ttk

    status_data = load_status_template() if status is None else status

    window = tk.Tk()
    window.title(WINDOW_TITLE)
    window.geometry("520x640")
    window.minsize(460, 560)

    root = ttk.Frame(window, padding=16)
    root.grid(row=0, column=0, sticky="nsew")
    window.columnconfigure(0, weight=1)
    window.rowconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)

    title = ttk.Label(root, text=WINDOW_TITLE, font=("Segoe UI", 16, "bold"))
    title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    notice = ttk.Label(root, text=STATUS_ONLY_NOTICE, wraplength=460)
    notice.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 14))

    enabled_var = tk.BooleanVar(value=False)
    toggle = ttk.Checkbutton(
        root,
        text="ON/OFF toggle visible - status only",
        variable=enabled_var,
        state="disabled",
    )
    toggle.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))

    ttk.Label(root, text="Mode selector").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=3)
    mode_var = tk.StringVar(value=str(status_data.get("watchdog_mode", "OFF")))
    mode_selector = ttk.Combobox(root, textvariable=mode_var, values=WATCHDOG_MODES, state="disabled")
    mode_selector.grid(row=3, column=1, sticky="ew", pady=3)

    for index, (label, value) in enumerate(build_status_rows(status_data), start=4):
        ttk.Label(root, text=f"{label}:").grid(row=index, column=0, sticky="w", padx=(0, 12), pady=3)
        ttk.Label(root, text=value, wraplength=280).grid(row=index, column=1, sticky="w", pady=3)

    boundary_row = 4 + len(STATUS_LABELS)
    safety_boundary = ttk.Label(root, text=SAFETY_BOUNDARY_COPY, wraplength=460)
    safety_boundary.grid(row=boundary_row, column=0, columnspan=2, sticky="w", pady=(14, 4))

    boundary = ttk.Label(root, text=RESTORE_REQUIRES_COPY, wraplength=460)
    boundary.grid(row=boundary_row + 1, column=0, columnspan=2, sticky="w", pady=(4, 8))

    manual_start_status = tk.StringVar(value=MANUAL_START_BOUNDARY_COPY)

    def handle_manual_start() -> None:
        result = manual_start_engel()
        if result.launch_succeeded:
            manual_start_status.set(f"Manual start receipt: {result.receipt_path}")
        else:
            manual_start_status.set(f"Manual start refused: {result.refusal_reason}; receipt: {result.receipt_path}")

    start_button = ttk.Button(root, text=MANUAL_START_COPY, command=handle_manual_start)
    start_button.grid(row=boundary_row + 2, column=0, sticky="w", pady=(8, 0))
    ttk.Label(root, textvariable=manual_start_status, wraplength=300).grid(
        row=boundary_row + 2,
        column=1,
        sticky="w",
        pady=(8, 0),
    )

    exit_button = ttk.Button(root, text="Exit Watchdog", command=window.destroy)
    exit_button.grid(row=boundary_row + 3, column=0, columnspan=2, sticky="e", pady=(8, 0))

    return window


def main() -> int:
    window = create_window()
    window.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
