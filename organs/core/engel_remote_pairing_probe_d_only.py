#!/usr/bin/env python3
"""
Engel Remote Pairing Probe - D-only

This does NOT claim to pair the Engel Remote app by itself.
It checks whether ADB is connected, finds likely Engel/Remote Android packages,
tries to launch the selected package, and writes a D-only diagnostic report.

Why this exists:
- ADB "paired/connected" is not the same as the Engel Remote app saying "paired".
- The app may need its own token, QR code, server URL, local websocket, or shared secret.
- This script helps identify the exact Android package/activity so the real pairing bridge can target it.

Writes only under:
D:\\b.WorkSpace\\Engel App\\memory\\phone_bridge\\
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

ENGEL_ROOT = Path(r"D:\b.WorkSpace\Engel App")
BRIDGE_DIR = ENGEL_ROOT / "memory" / "phone_bridge"
REPORT_FILE = BRIDGE_DIR / "ENGEL_REMOTE_PAIRING_PROBE.json"
LOG_FILE = BRIDGE_DIR / "engel_remote_pairing_probe.log"

ADB_CANDIDATES = [
    Path(r"D:\platform-tools\adb.exe"),
    ENGEL_ROOT / "tools" / "platform-tools" / "adb.exe",
    ENGEL_ROOT / "platform-tools" / "adb.exe",
    Path.cwd() / "adb.exe",
    Path.cwd() / "platform-tools" / "adb.exe",
]

KEYWORDS = [
    "engel",
    "remote",
    "bridge",
    "phone",
    "companion",
    "worker",
    "agent",
]


def assert_d_only(path: Path) -> None:
    if not str(path).lower().startswith("d:\\"):
        raise RuntimeError(f"Blocked non-D path: {path}")


def ensure_dirs() -> None:
    assert_d_only(ENGEL_ROOT)
    assert_d_only(BRIDGE_DIR)
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    ensure_dirs()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_adb() -> str | None:
    for p in ADB_CANDIDATES:
        if p.exists() and not str(p).lower().startswith("c:\\"):
            return str(p)

    # PATH fallback, reject C:\ adb.
    try:
        result = subprocess.run(["where", "adb"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and not line.lower().startswith("c:\\"):
                    return line
    except Exception:
        pass

    return None


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    log("RUN: " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = p.stdout.strip()
        err = p.stderr.strip()
        if out:
            log("STDOUT: " + out[:4000])
        if err:
            log("STDERR: " + err[:4000])
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        return 998, "", f"Timed out after {timeout}s"
    except Exception as e:
        return 997, "", str(e)


def adb_cmd(adb: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return run([adb, *args], timeout=timeout)


def adb_serial(adb: str, serial: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return adb_cmd(adb, "-s", serial, *args, timeout=timeout)


def parse_devices(adb: str) -> list[dict]:
    code, out, err = adb_cmd(adb, "devices", "-l", timeout=15)
    devices = []
    if code != 0:
        return devices

    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append({
                "serial": parts[0],
                "state": parts[1],
                "detail": " ".join(parts[2:]),
            })
    return devices


def get_packages(adb: str, serial: str) -> list[str]:
    code, out, err = adb_serial(adb, serial, "shell", "pm", "list", "packages", timeout=30)
    if code != 0:
        return []
    packages = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            packages.append(line.replace("package:", "", 1).strip())
    return packages


def get_launch_activity(adb: str, serial: str, package: str) -> str:
    # cmd package resolve-activity works on many modern Android versions.
    code, out, err = adb_serial(
        adb,
        serial,
        "shell",
        "cmd",
        "package",
        "resolve-activity",
        "--brief",
        package,
        timeout=15,
    )
    if code == 0 and out:
        # Output often contains package/activity on final line.
        lines = [x.strip() for x in out.splitlines() if x.strip()]
        for line in reversed(lines):
            if "/" in line:
                return line

    return ""


def launch_package(adb: str, serial: str, package: str) -> dict:
    result = {
        "package": package,
        "launch_activity": "",
        "launch_attempted": True,
        "launch_ok": False,
        "error": "",
    }

    activity = get_launch_activity(adb, serial, package)
    result["launch_activity"] = activity

    code, out, err = adb_serial(
        adb,
        serial,
        "shell",
        "monkey",
        "-p",
        package,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
        timeout=20,
    )
    result["launch_ok"] = code == 0
    result["error"] = "" if code == 0 else (err or out)
    return result


def main() -> None:
    ensure_dirs()
    log("Starting Engel Remote Pairing Probe.")

    adb = find_adb()
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engel_root": str(ENGEL_ROOT),
        "bridge_dir": str(BRIDGE_DIR),
        "adb_path": adb,
        "important": [
            "ADB connected does not equal Engel Remote app paired.",
            "If Engel Remote still says not paired, the app likely needs its own app-level token/server pairing.",
            "Use this report to identify the exact package/activity before building the real app-pairing bridge.",
        ],
        "devices": [],
    }

    if not adb:
        report["overall"] = "ADB_NOT_FOUND"
        REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
        log(f"ADB not found. Report written: {REPORT_FILE}")
        return

    devices = parse_devices(adb)
    for dev in devices:
        device_report = dict(dev)
        serial = dev["serial"]
        state = dev["state"]

        if state != "device":
            device_report["error"] = f"ADB transport is {state}. Phone must be authorized and online."
            report["devices"].append(device_report)
            continue

        code, model, _ = adb_serial(adb, serial, "shell", "getprop", "ro.product.model", timeout=10)
        code2, version, _ = adb_serial(adb, serial, "shell", "getprop", "ro.build.version.release", timeout=10)
        device_report["model"] = model.strip() if code == 0 else ""
        device_report["android_version"] = version.strip() if code2 == 0 else ""

        packages = get_packages(adb, serial)
        likely = []
        for pkg in packages:
            low = pkg.lower()
            score = sum(1 for k in KEYWORDS if k in low)
            if score:
                likely.append({"package": pkg, "score": score})

        likely.sort(key=lambda x: (-x["score"], x["package"]))
        device_report["likely_remote_packages"] = likely[:30]

        # Launch the best package only if it looks Engel-specific.
        launched = None
        if likely and ("engel" in likely[0]["package"].lower()):
            launched = launch_package(adb, serial, likely[0]["package"])
        device_report["launch_result"] = launched

        report["devices"].append(device_report)

    report["overall"] = "OK" if report["devices"] else "NO_DEVICES"
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"Probe finished. Report written: {REPORT_FILE}")

    print("\nNEXT STEP:")
    print("Open the JSON report and look at likely_remote_packages.")
    print("If the Engel Remote package is listed but still says not paired, ADB is not the missing part.")
    print("The desktop Engel app needs to generate/accept the same pairing token/protocol that the Android app expects.")


if __name__ == "__main__":
    main()
