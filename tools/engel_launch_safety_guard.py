"""Read-only Engel launch safety preflight guard.

This tool is intentionally lightweight and bounded. It reads local machine
status when available and never writes reports, changes OS settings, kills
processes, starts builds, calls providers, or uses the network.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import io
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


ACTIVE_ENGEL_ROOTS = [
    r"D:\b.WorkSpace\Engel App",
    r"D:\EngelBible",
    r"D:\Engel App Bible",
    r"D:\EngelStandalone",
]

HEAVY_PROCESS_GROUPS = {
    "Android Studio": ["studio64.exe", "studio.exe"],
    "Visual Studio": ["devenv.exe", "visualstudio.exe"],
    "Gradle": ["gradle.exe", "gradlew.bat"],
    "Java": ["java.exe", "javaw.exe"],
    "adb": ["adb.exe"],
    "Node": ["node.exe"],
    "Python": ["python.exe", "pythonw.exe", "py.exe"],
    "PowerShell": ["powershell.exe", "pwsh.exe"],
    "Codex": ["codex.exe"],
}

BLOCKED_MEMORY_BYTES = 1.5 * 1024 * 1024 * 1024
CAUTION_MEMORY_BYTES = 4 * 1024 * 1024 * 1024
BLOCKED_DISK_BYTES = 2 * 1024 * 1024 * 1024
CAUTION_DISK_BYTES = 10 * 1024 * 1024 * 1024
BLOCKED_CPU_PERCENT = 75.0
CAUTION_CPU_PERCENT = 60.0
CPU_SAMPLE_SECONDS = 1.0


STATUS_GUIDANCE = {
    "SAFE": {
        "meaning": "SAFE means the lightweight checks found no blockers or cautions.",
        "next_action": "Low-usage Engel work may continue; heavy work still needs explicit human approval.",
    },
    "CAUTION": {
        "meaning": "CAUTION means one or more checks are limited, unknown, or already under load.",
        "next_action": "Keep Engel in low-usage mode; wait, close heavy tools, plug in power, or get approval before heavier work.",
    },
    "BLOCKED": {
        "meaning": "BLOCKED means a checked condition is too constrained for heavier Engel work.",
        "next_action": "Do not start heavy Engel work until the blocker is resolved and the guard is rerun.",
    },
}


def _bytes_to_gb(value: float | int | None) -> str:
    if value is None:
        return "unknown"
    try:
        return f"{float(value) / (1024 * 1024 * 1024):.1f} GB"
    except Exception:
        return "unknown"


def _safe_status_from_findings(blockers: list[str], cautions: list[str]) -> str:
    if blockers:
        return "BLOCKED"
    if cautions:
        return "CAUTION"
    return "SAFE"


def _status_guidance(status: str) -> dict[str, str]:
    return STATUS_GUIDANCE.get(status, STATUS_GUIDANCE["CAUTION"])


def _check_power() -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "ac_line_status": "unknown",
        "battery_percent": None,
        "severity": "UNKNOWN",
        "notes": [],
    }
    if os.name != "nt":
        result["notes"].append("Power status API is only implemented for Windows.")
        return result

    try:
        class SystemPowerStatus(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_ubyte),
                ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte),
                ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        status = SystemPowerStatus()
        ok = ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
        if not ok:
            result["notes"].append("GetSystemPowerStatus returned no data.")
            return result

        result["available"] = True
        ac_map = {0: "offline", 1: "online", 255: "unknown"}
        ac = ac_map.get(int(status.ACLineStatus), "unknown")
        battery_percent = None
        if int(status.BatteryLifePercent) != 255:
            battery_percent = int(status.BatteryLifePercent)

        result["ac_line_status"] = ac
        result["battery_percent"] = battery_percent

        if ac == "offline" and battery_percent is not None and battery_percent <= 10:
            result["severity"] = "BLOCKED"
            result["notes"].append("Battery is at or below 10 percent and AC power is offline.")
        elif ac == "offline":
            result["severity"] = "CAUTION"
            result["notes"].append("AC power is offline.")
        elif ac == "unknown":
            result["severity"] = "CAUTION"
            result["notes"].append("AC power state is unknown.")
        else:
            result["severity"] = "SAFE"
    except Exception as exc:
        result["notes"].append("Power status unavailable: " + str(exc))

    return result


def _check_memory() -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "total_bytes": None,
        "available_bytes": None,
        "load_percent": None,
        "severity": "UNKNOWN",
        "notes": [],
    }
    try:
        if os.name == "nt":
            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(MemoryStatusEx)
            ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            if not ok:
                result["notes"].append("GlobalMemoryStatusEx returned no data.")
                return result
            total = int(status.ullTotalPhys)
            available = int(status.ullAvailPhys)
            load = int(status.dwMemoryLoad)
        else:
            page_size = os.sysconf("SC_PAGE_SIZE")
            pages = os.sysconf("SC_PHYS_PAGES")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            total = int(page_size * pages)
            available = int(page_size * available_pages)
            load = int(100 - ((available / total) * 100)) if total else None

        result.update(
            {
                "available": True,
                "total_bytes": total,
                "available_bytes": available,
                "load_percent": load,
            }
        )
        if available < BLOCKED_MEMORY_BYTES:
            result["severity"] = "BLOCKED"
            result["notes"].append("Available memory is below 1.5 GB.")
        elif available < CAUTION_MEMORY_BYTES:
            result["severity"] = "CAUTION"
            result["notes"].append("Available memory is below 4 GB.")
        else:
            result["severity"] = "SAFE"
    except Exception as exc:
        result["notes"].append("Memory status unavailable: " + str(exc))

    return result


def _filetime_to_int(value: Any) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _check_cpu() -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "load_percent": None,
        "blocked_at_percent": BLOCKED_CPU_PERCENT,
        "caution_at_percent": CAUTION_CPU_PERCENT,
        "sample_seconds": CPU_SAMPLE_SECONDS,
        "severity": "UNKNOWN",
        "notes": [],
    }
    if os.name != "nt":
        result["notes"].append("CPU status API is only implemented for Windows.")
        return result

    try:
        class FileTime(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong),
            ]

        kernel32 = ctypes.windll.kernel32

        def sample() -> tuple[int, int]:
            idle = FileTime()
            kernel = FileTime()
            user = FileTime()
            ok = kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
            if not ok:
                raise RuntimeError("GetSystemTimes returned no data.")
            idle_time = _filetime_to_int(idle)
            total_time = _filetime_to_int(kernel) + _filetime_to_int(user)
            return idle_time, total_time

        idle_1, total_1 = sample()
        time.sleep(CPU_SAMPLE_SECONDS)
        idle_2, total_2 = sample()
        total_delta = total_2 - total_1
        idle_delta = idle_2 - idle_1
        if total_delta <= 0:
            result["notes"].append("CPU sample did not advance.")
            return result

        load = max(0.0, min(100.0, (1.0 - (idle_delta / total_delta)) * 100.0))
        load = round(load, 1)
        result["available"] = True
        result["load_percent"] = load

        if load >= BLOCKED_CPU_PERCENT:
            result["severity"] = "BLOCKED"
            result["notes"].append("CPU usage is at or above 75 percent; Guardian blocks heavy Engel work.")
        elif load >= CAUTION_CPU_PERCENT:
            result["severity"] = "CAUTION"
            result["notes"].append("CPU usage is at or above 60 percent; keep Engel in low-usage mode.")
        else:
            result["severity"] = "SAFE"
    except Exception as exc:
        result["notes"].append("CPU status unavailable: " + str(exc))

    return result


def _disk_check_path(root: str) -> tuple[Path, bool]:
    path = Path(root)
    if path.exists():
        return path, True
    anchor = path.anchor
    if anchor:
        drive = Path(anchor)
        if drive.exists():
            return drive, False
    return path, False


def _check_disk_roots() -> list[dict[str, Any]]:
    checks = []
    for root in ACTIVE_ENGEL_ROOTS:
        check_path, root_exists = _disk_check_path(root)
        row: dict[str, Any] = {
            "root": root,
            "checked_path": str(check_path),
            "root_exists": root_exists,
            "available": False,
            "free_bytes": None,
            "total_bytes": None,
            "severity": "UNKNOWN",
            "notes": [],
        }
        try:
            usage = shutil.disk_usage(str(check_path))
            free = int(usage.free)
            total = int(usage.total)
            row.update({"available": True, "free_bytes": free, "total_bytes": total})
            if not root_exists:
                row["severity"] = "CAUTION"
                row["notes"].append("Configured root was not found; checked containing drive instead.")
            elif free < BLOCKED_DISK_BYTES:
                row["severity"] = "BLOCKED"
                row["notes"].append("Free disk space is below 2 GB.")
            elif free < CAUTION_DISK_BYTES:
                row["severity"] = "CAUTION"
                row["notes"].append("Free disk space is below 10 GB.")
            else:
                row["severity"] = "SAFE"
        except Exception as exc:
            row["notes"].append("Disk status unavailable: " + str(exc))
        checks.append(row)
    return checks


def _process_names_from_toolhelp() -> tuple[list[str], str]:
    if os.name != "nt":
        return [], "Toolhelp process check is only implemented for Windows."
    try:
        class ProcessEntry32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_ulong),
                ("cntUsage", ctypes.c_ulong),
                ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            return [], "CreateToolhelp32Snapshot returned no data."

        names: list[str] = []
        entry = ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(ProcessEntry32W)
        try:
            ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                name = str(entry.szExeFile or "").strip().lower()
                if name:
                    names.append(name)
                ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)
        return names, ""
    except Exception as exc:
        return [], "Toolhelp process status unavailable: " + str(exc)


def _process_names_from_tasklist() -> tuple[list[str], str]:
    if os.name != "nt":
        return [], "tasklist process check is only implemented for Windows."
    try:
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW
        completed = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=5,
            creationflags=creationflags,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            return [], "tasklist returned " + str(completed.returncode) + (": " + detail if detail else "")
        names: list[str] = []
        reader = csv.reader(io.StringIO(completed.stdout))
        for row in reader:
            if row:
                names.append(str(row[0]).strip().lower())
        return names, ""
    except Exception as exc:
        return [], "Process status unavailable: " + str(exc)


def _check_heavy_processes() -> dict[str, Any]:
    names, warning = _process_names_from_toolhelp()
    if warning:
        names, warning = _process_names_from_tasklist()
    active: dict[str, list[str]] = {}
    name_set = set(names)
    for group, patterns in HEAVY_PROCESS_GROUPS.items():
        matches = sorted(pattern for pattern in patterns if pattern.lower() in name_set)
        if not matches and group == "Codex":
            matches = sorted(name for name in name_set if "codex" in name)
        if matches:
            active[group] = matches

    result: dict[str, Any] = {
        "available": not bool(warning),
        "active_groups": active,
        "active_group_count": len(active),
        "severity": "SAFE",
        "notes": [],
    }
    if warning:
        result["severity"] = "UNKNOWN"
        result["notes"].append(warning)
    elif active:
        result["severity"] = "CAUTION"
        result["notes"].append("Heavy dev processes are already active.")
    return result


def collect_launch_safety_status() -> dict[str, Any]:
    power = _check_power()
    cpu = _check_cpu()
    memory = _check_memory()
    disks = _check_disk_roots()
    processes = _check_heavy_processes()

    blockers: list[str] = []
    cautions: list[str] = []

    for label, check in [("power", power), ("cpu", cpu), ("memory", memory), ("processes", processes)]:
        severity = check.get("severity")
        if severity == "BLOCKED":
            blockers.append(label)
        elif severity in {"CAUTION", "UNKNOWN"}:
            cautions.append(label)

    for disk in disks:
        severity = disk.get("severity")
        label = "disk:" + str(disk.get("root", "unknown"))
        if severity == "BLOCKED":
            blockers.append(label)
        elif severity in {"CAUTION", "UNKNOWN"}:
            cautions.append(label)

    active_groups = int(processes.get("active_group_count") or 0)
    available_memory = memory.get("available_bytes")
    if (
        isinstance(available_memory, int)
        and available_memory < CAUTION_MEMORY_BYTES
        and active_groups >= 3
    ):
        blockers.append("combined:low-memory-heavy-processes")

    status = _safe_status_from_findings(blockers, cautions)
    guidance = _status_guidance(status)
    return {
        "engel_launch_safety": "READ_ONLY / PREFLIGHT",
        "immune_system_role": "Engel Immune System / computer stability protection",
        "startup_mode": "lightweight",
        "background_workers": "disabled",
        "autonomous_loops": "disabled",
        "heavy_scans": "disabled until approved",
        "provider_network_calls": "disabled",
        "swarm_colony_mycelium_runtime": "disabled",
        "build_tasks": "manual only",
        "cpu_guard": {
            "enabled": True,
            "caution_at_percent": CAUTION_CPU_PERCENT,
            "blocked_at_percent": BLOCKED_CPU_PERCENT,
            "policy": "Guardian blocks heavy Engel work when CPU usage is at or above 75 percent.",
        },
        "status": status,
        "status_meaning": guidance["meaning"],
        "recommended_action": guidance["next_action"],
        "unavailable_check_policy": "Unavailable checks degrade to CAUTION with an explanatory note.",
        "reporting": {
            "default_tool_writes_reports": False,
            "default_status_route_writes_reports": False,
            "approved_report_flag_exists": False,
            "approved_report_route_exists": False,
            "report_writing_requires_future_explicit_approval": True,
        },
        "checks": {
            "power": power,
            "cpu": cpu,
            "memory": memory,
            "disk_roots": disks,
            "heavy_processes": processes,
        },
        "blockers": blockers,
        "cautions": cautions,
        "safety": {
            "read_only": True,
            "writes_reports": False,
            "writes_trusted_memory": False,
            "mutates_queues": False,
            "writes_alive_state": False,
            "writes_digest_history": False,
            "starts_background_workers": False,
            "starts_autonomous_loops": False,
            "runs_startup_scans": False,
            "runs_heavy_scans": False,
            "runs_recursive_indexing": False,
            "runs_builds": False,
            "launches_engel_tasks": False,
            "starts_swarm_colony_mycelium_runtime": False,
            "calls_providers_or_network": False,
            "kills_processes": False,
            "changes_os_settings": False,
            "automatic_remediation": False,
        },
    }


def format_launch_safety_text(status: dict[str, Any] | None = None) -> str:
    data = status or collect_launch_safety_status()
    checks = data.get("checks", {})
    power = checks.get("power", {})
    cpu = checks.get("cpu", {})
    memory = checks.get("memory", {})
    disks = checks.get("disk_roots", [])
    processes = checks.get("heavy_processes", {})

    lines = [
        "# Engel Launch Safety Status",
        "",
        "Engel Launch Safety: READ_ONLY / PREFLIGHT",
        "Immune System role: computer stability protection",
        "Startup mode: lightweight",
        "Background workers: disabled",
        "Autonomous loops: disabled",
        "Heavy scans: disabled until approved",
        "Provider/network calls: disabled",
        "Swarm/colony/mycelium runtime: disabled",
        "Build tasks: manual only",
        "CPU guard: BLOCKED at >= 75%; CAUTION at >= 60%",
        "Status: " + str(data.get("status", "CAUTION")),
        "",
        "Status meaning:",
        "- SAFE: low-usage Engel work may continue; heavy work still needs explicit human approval.",
        "- CAUTION: remain low-usage; wait, close heavy tools, plug in power, or get approval before heavier work.",
        "- BLOCKED: do not start heavy Engel work until the blocker is resolved.",
        "- Current: " + str(data.get("status_meaning", "Unavailable checks degrade to CAUTION.")),
        "- Recommended action: " + str(data.get("recommended_action", "Keep Engel in low-usage mode.")),
        "- Unavailable check policy: " + str(data.get("unavailable_check_policy", "Unavailable checks degrade to CAUTION.")),
        "",
        "Power:",
        "- available: " + str(power.get("available", False)),
        "- AC power: " + str(power.get("ac_line_status", "unknown")),
        "- battery percent: " + (str(power.get("battery_percent")) if power.get("battery_percent") is not None else "unknown"),
        "- severity: " + str(power.get("severity", "UNKNOWN")),
        "",
        "CPU:",
        "- available: " + str(cpu.get("available", False)),
        "- load percent: " + (str(cpu.get("load_percent")) if cpu.get("load_percent") is not None else "unknown"),
        "- caution threshold: " + str(cpu.get("caution_at_percent", CAUTION_CPU_PERCENT)),
        "- blocked threshold: " + str(cpu.get("blocked_at_percent", BLOCKED_CPU_PERCENT)),
        "- severity: " + str(cpu.get("severity", "UNKNOWN")),
        "",
        "Memory:",
        "- available: " + str(memory.get("available", False)),
        "- total: " + _bytes_to_gb(memory.get("total_bytes")),
        "- available memory: " + _bytes_to_gb(memory.get("available_bytes")),
        "- load percent: " + (str(memory.get("load_percent")) if memory.get("load_percent") is not None else "unknown"),
        "- severity: " + str(memory.get("severity", "UNKNOWN")),
        "",
        "Disk roots:",
    ]

    for disk in disks:
        lines.extend(
            [
                "- root: " + str(disk.get("root", "")),
                "  checked path: " + str(disk.get("checked_path", "")),
                "  root exists: " + str(disk.get("root_exists", False)),
                "  free: " + _bytes_to_gb(disk.get("free_bytes")),
                "  total: " + _bytes_to_gb(disk.get("total_bytes")),
                "  severity: " + str(disk.get("severity", "UNKNOWN")),
            ]
        )

    active_groups = processes.get("active_groups", {})
    lines.extend(
        [
            "",
            "Heavy dev processes:",
            "- available: " + str(processes.get("available", False)),
            "- active groups: " + str(processes.get("active_group_count", 0)),
        ]
    )
    if active_groups:
        for group in sorted(active_groups):
            lines.append("- " + str(group) + ": " + ", ".join(active_groups[group]))
    else:
        lines.append("- none detected")
    lines.append("- severity: " + str(processes.get("severity", "UNKNOWN")))

    notes: list[str] = []
    for check in [power, cpu, memory, processes]:
        notes.extend(str(note) for note in check.get("notes", []) if note)
    for disk in disks:
        notes.extend(str(note) for note in disk.get("notes", []) if note)
    if notes:
        lines.extend(["", "Notes:"])
        lines.extend("- " + note for note in notes)

    lines.extend(
        [
            "",
            "Report behavior:",
            "- Default tool/status checks write no reports.",
            "- No approved report flag or approved report route is implemented in this launch safety tool.",
            "- Any future report-writing path must be explicit, approved, documented, and verifier-covered.",
            "",
            "Safety:",
            "- Read-only preflight status only.",
            "- No report files are written during normal status checks.",
            "- No trusted-memory writes, queue mutations, digest/history writes, or ALIVE_STATE writes.",
            "- No provider/API/network calls.",
            "- No background workers or autonomous loops.",
            "- No startup scans, heavy scans, recursive indexing, builds, remediation, process killing, or OS setting changes.",
            "- No Engel task launch and no swarm/colony/mycelium runtime.",
            "- Human approval remains required before any heavy work.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Engel launch safety preflight guard.")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    status = collect_launch_safety_status()
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(format_launch_safety_text(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
