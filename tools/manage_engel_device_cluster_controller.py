#!/usr/bin/env python3
"""Start and inspect controller-side helpers for Engel device cluster links."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "runtime" / "python310" / "python.exe"
RUNTIME_DIR = ROOT / "runtime" / "device_cluster_controller"
STARTUP_SCRIPT = ROOT / "workflows" / "device_cluster" / "Start-EngelDeviceClusterController.ps1"
TASK_NAME = "EngelDeviceClusterController"
STARTUP_CMD_NAME = "EngelDeviceClusterController.cmd"


def is_os_drive_path(path: Path | str) -> bool:
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def python_exe() -> str:
    return str(PYTHON if PYTHON.is_file() else Path(sys.executable))


def run_text(command: list[str], *, timeout: int = 30) -> tuple[int, str, str]:
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return proc.returncode, proc.stdout, proc.stderr


def run_json(command: list[str], *, timeout: int = 45) -> dict[str, Any]:
    code, stdout, stderr = run_text(command, timeout=timeout)
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = {"stdout": stdout[-4000:]}
    if isinstance(payload, dict):
        payload["return_code"] = code
        if stderr.strip():
            payload["stderr"] = stderr.strip()[-4000:]
        return payload
    return {"return_code": code, "stdout": stdout[-4000:], "stderr": stderr.strip()[-4000:]}


def powershell_json(script: str) -> list[dict[str, Any]]:
    code, stdout, _stderr = run_text(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; " + script,
        ],
        timeout=30,
    )
    if code != 0 or not stdout.strip():
        return []
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    return []


def processes_matching(script_name: str) -> list[dict[str, Any]]:
    pattern = "*" + script_name.replace("'", "''") + "*"
    script = (
        f"Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -like '{pattern}' }} | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    rows = powershell_json(script)
    matches: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("ProcessId"):
            continue
        command_line = str(row.get("CommandLine", ""))
        if "Get-CimInstance Win32_Process" in command_line:
            continue
        matches.append({"pid": int(row.get("ProcessId", 0)), "command_line": command_line})
    return matches


def helper_commands(args: argparse.Namespace) -> dict[str, list[str]]:
    py = python_exe()
    return {
        "android_link_watchdog": [
            py,
            str(ROOT / "tools" / "keep_engel_android_link_alive.py"),
            "--duration-seconds",
            "0",
            "--interval-seconds",
            str(args.interval_seconds),
            "--host",
            args.controller_ip,
            "--port",
            str(args.android_port),
        ],
        "windows_sub_bootstrap_server": [
            py,
            str(ROOT / "tools" / "windows_sub_engel_wired_bootstrap_server.py"),
            "--port",
            str(args.bootstrap_port),
            "--controller-ip",
            args.controller_ip,
        ],
        "windows_sub_auto_pair_watcher": [
            py,
            str(ROOT / "tools" / "watch_windows_sub_engel_pairing.py"),
        ],
    }


def helper_script_name(role: str) -> str:
    return {
        "android_link_watchdog": "keep_engel_android_link_alive.py",
        "windows_sub_bootstrap_server": "windows_sub_engel_wired_bootstrap_server.py",
        "windows_sub_auto_pair_watcher": "watch_windows_sub_engel_pairing.py",
    }[role]


def start_process(role: str, command: list[str]) -> dict[str, Any]:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RUNTIME_DIR / f"{role}_{stamp()}.log"
    log_handle = log_path.open("a", encoding="utf-8")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    return {"started": True, "pid": proc.pid, "log": str(log_path), "command": command}


def start_helpers(args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {"time_utc": utc_now(), "root": str(ROOT), "helpers": {}}
    for role, command in helper_commands(args).items():
        existing = processes_matching(helper_script_name(role))
        if existing:
            result["helpers"][role] = {"started": False, "already_running": True, "processes": existing}
            continue
        result["helpers"][role] = start_process(role, command)
    return result


def task_status() -> dict[str, Any]:
    code, stdout, stderr = run_text(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"], timeout=30)
    return {
        "task_name": TASK_NAME,
        "exists": code == 0,
        "return_code": code,
        "stdout": stdout.strip()[-4000:],
        "stderr": stderr.strip()[-4000:],
    }


def startup_file_path() -> Path:
    return RUNTIME_DIR / STARTUP_CMD_NAME


def startup_file_status() -> dict[str, Any]:
    path = startup_file_path()
    return {"path": str(path), "exists": path.is_file(), "on_os_drive": is_os_drive_path(path)}


def install_startup_file() -> dict[str, Any]:
    folder = RUNTIME_DIR
    if is_os_drive_path(folder):
        return {"ok": False, "error": f"refusing OS-drive startup marker: {folder}"}
    folder.mkdir(parents=True, exist_ok=True)
    path = startup_file_path()
    body = (
        "@echo off\r\n"
        f'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{STARTUP_SCRIPT}"\r\n'
    )
    path.write_text(body, encoding="ascii")
    return {"ok": True, "path": str(path), "method": "approved_runtime_marker_no_os_startup_folder"}


def uninstall_startup_file() -> dict[str, Any]:
    path = startup_file_path()
    if is_os_drive_path(path):
        return {"ok": False, "error": f"refusing OS-drive startup marker removal: {path}"}
    if path.exists():
        path.unlink()
        return {"ok": True, "removed": str(path)}
    return {"ok": True, "removed": "", "already_absent": True}


def install_startup() -> dict[str, Any]:
    if not STARTUP_SCRIPT.is_file():
        return {"ok": False, "error": f"missing startup script: {STARTUP_SCRIPT}"}
    file_result = install_startup_file()
    return {
        "ok": bool(file_result.get("ok")),
        "method": "approved_runtime_marker_no_c_startup_write",
        "task_name": TASK_NAME,
        "os_startup_write_skipped": True,
        "os_startup_skip_reason": "C: is OS-only; no Windows Startup folder or scheduled-task mutation is performed here.",
        "task": task_status(),
        "startup_file": startup_file_status(),
        "startup_file_install": file_result,
    }


def uninstall_startup() -> dict[str, Any]:
    file_result = uninstall_startup_file()
    return {
        "ok": bool(file_result.get("ok")),
        "task_name": TASK_NAME,
        "os_startup_delete_skipped": True,
        "os_startup_skip_reason": "C: is OS-only; no Windows Startup folder or scheduled-task mutation is performed here.",
        "task": task_status(),
        "startup_file_uninstall": file_result,
    }


def cluster_status() -> dict[str, Any]:
    helper_processes = {
        role: processes_matching(helper_script_name(role))
        for role in [
            "android_link_watchdog",
            "windows_sub_bootstrap_server",
            "windows_sub_auto_pair_watcher",
        ]
    }
    return {
        "time_utc": utc_now(),
        "root": str(ROOT),
        "helpers": helper_processes,
        "android_lan_receiver": processes_matching("engel_remote_worker_lan_pairing.py"),
        "startup_task": task_status(),
        "startup_file": startup_file_status(),
        "android_link": run_json([python_exe(), str(ROOT / "engel_remote_worker_link_manager.py"), "status"], timeout=45),
        "windows_sub_engel": run_text(
            [python_exe(), str(ROOT / "engel_sub_node_remote_control.py"), "status", "--node-kind", "windows"],
            timeout=45,
        )[1].strip(),
        "shared_drive_room": run_json(
            [
                python_exe(),
                str(ROOT / "engel_shared_drive_room.py"),
                "status",
                "--root",
                os.environ.get(
                    "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
                    str(ROOT / "run" / "sub_engel_transport"),
                ),
            ],
            timeout=45,
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "status", "install-startup", "uninstall-startup"])
    parser.add_argument("--controller-ip", default="192.0.2.40")
    parser.add_argument("--android-port", type=int, default=8765)
    parser.add_argument("--bootstrap-port", type=int, default=8788)
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args(argv)

    if args.command == "start":
        print(json.dumps(start_helpers(args), indent=2, sort_keys=True))
        return 0
    if args.command == "status":
        print(json.dumps(cluster_status(), indent=2, sort_keys=True))
        return 0
    if args.command == "install-startup":
        print(json.dumps(install_startup(), indent=2, sort_keys=True))
        return 0
    if args.command == "uninstall-startup":
        print(json.dumps(uninstall_startup(), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
