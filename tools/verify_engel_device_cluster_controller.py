#!/usr/bin/env python3
"""Verify Engel controller-side device cluster connectivity and startup guard."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "runtime" / "python310" / "python.exe"
MANAGER = ROOT / "tools" / "manage_engel_device_cluster_controller.py"
ADB = ROOT / "tools" / "platform-tools" / "adb.exe"
NODES = ["DESKTOP-UE5A6GG"]


def py() -> str:
    return str(PYTHON if PYTHON.is_file() else Path(sys.executable))


def run(command: list[str], timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def load_status() -> dict[str, Any]:
    proc = run([py(), str(MANAGER), "status"], timeout=90)
    require(proc.returncode == 0, f"manager status failed: {proc.stderr[-1000:]}")
    try:
        status = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FAIL: manager status returned non-JSON: {exc}") from exc
    require(isinstance(status, dict), "manager status was not an object")
    return status


def verify_adb() -> None:
    proc = run([str(ADB), "devices", "-l"], timeout=30)
    require(proc.returncode == 0, f"adb devices failed: {proc.stderr[-1000:]}")
    device_lines = [
        line
        for line in proc.stdout.splitlines()
        if "\tdevice" in line or " device " in line
    ]
    require(len(device_lines) >= 2, f"expected at least 2 connected Android devices, got {len(device_lines)}")


def verify_windows_nodes() -> None:
    for node in NODES:
        proc = run(
            [
                py(),
                str(ROOT / "engel_sub_node_remote_control.py"),
                "command",
                "--node-kind",
                "windows",
                "--node",
                node,
                "--action",
                "node.status",
            ],
            timeout=30,
        )
        require(proc.returncode == 0, f"{node} node.status command failed: {proc.stderr[-1000:]}")
        payload = json.loads(proc.stdout)
        require(bool(payload.get("ok")), f"{node} node.status returned ok=false")
        result = payload.get("result", {})
        require(result.get("return_code") == 0, f"{node} node.status return_code was not 0")


def main() -> int:
    status = load_status()
    startup_file = status.get("startup_file", {})
    startup_task = status.get("startup_task", {})
    require(
        bool(startup_file.get("exists")) or bool(startup_task.get("exists")),
        "no startup guard installed",
    )

    helpers = status.get("helpers", {})
    require(helpers.get("android_link_watchdog"), "android link watchdog process is not running")
    require(status.get("android_lan_receiver"), "Android LAN receiver process is not running")
    require(helpers.get("windows_sub_auto_pair_watcher"), "Windows Sub-Engel auto-pair watcher is not running")
    require(helpers.get("windows_sub_bootstrap_server"), "Windows Sub-Engel bootstrap server is not running")

    android = status.get("android_link", {})
    require(bool(android.get("receiver_running")), "Android link receiver_running is false")
    require(bool(android.get("receiver_health_ok")), "Android link receiver_health_ok is false")
    require(bool(android.get("auto_worker_enabled")), "Android auto worker is not enabled")
    require(str(android.get("control_direction")) == "Engel controls phone", "Android control direction is not Engel controls phone")

    drive = status.get("shared_drive_room", {})
    require(bool(drive.get("ok")), "shared Drive room status is not ok")
    require(bool(drive.get("room_exists")), "shared Drive room directory is missing")
    require(bool(drive.get("live_doc_exists")), "shared Drive live doc is missing")

    verify_adb()
    verify_windows_nodes()

    print("OK: Engel device cluster controller verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
