#!/usr/bin/env python3
"""
Engel Remote Worker Pairing Reader - D-only, safe target version

This version avoids launching the wrong/old monitor app.

Targets only:
  com.example.engel_remote_worker

Does NOT target:
  com.engel.engel_monitor

What it does:
- Reads worker_identity.json and worker_connection.json from the real worker app if debuggable.
- Pulls/redacts the values into D:\b.WorkSpace\Engel App\memory\phone_bridge.
- Merges duplicate USB/Wi-Fi ADB transports by Android ID.
- Creates a desktop-side pairing state file Engel can read.
- Does not write to C:.
- Does not uninstall/install/delete anything.
- Does not fake pairing.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

ENGEL_ROOT = Path(r"D:\b.WorkSpace\Engel App")
BRIDGE_DIR = ENGEL_ROOT / "memory" / "phone_bridge"
REPORT_DIR = ENGEL_ROOT / "reports" / "codex_bridge"

TARGET_PACKAGE = "com.example.engel_remote_worker"

STATE_FILE = BRIDGE_DIR / "ENGEL_REMOTE_WORKER_PAIRING_STATE.json"
RAW_FILE = BRIDGE_DIR / "ENGEL_REMOTE_WORKER_PAIRING_RAW.json"
REPORT_FILE = REPORT_DIR / "ENGEL_REMOTE_WORKER_PAIRING_REPORT.md"
LOG_FILE = BRIDGE_DIR / "engel_remote_worker_pairing_reader.log"

ADB_CANDIDATES = [
    ENGEL_ROOT / "tools" / "platform-tools" / "adb.exe",
    Path(r"D:\platform-tools\adb.exe"),
    ENGEL_ROOT / "platform-tools" / "adb.exe",
    Path.cwd() / "tools" / "platform-tools" / "adb.exe",
    Path.cwd() / "platform-tools" / "adb.exe",
    Path.cwd() / "adb.exe",
]


def assert_d_only(path: Path) -> None:
    if not str(path).lower().startswith("d:\\"):
        raise RuntimeError(f"Blocked non-D path: {path}")


def ensure_dirs() -> None:
    for path in [ENGEL_ROOT, BRIDGE_DIR, REPORT_DIR]:
        assert_d_only(path)
        path.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    ensure_dirs()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_adb() -> str | None:
    for candidate in ADB_CANDIDATES:
        if candidate.exists() and not str(candidate).lower().startswith("c:\\"):
            return str(candidate)

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
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        if out:
            log("STDOUT: " + out[:3000])
        if err:
            log("STDERR: " + err[:3000])
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        return 998, "", f"Timed out after {timeout}s"
    except Exception as exc:
        return 997, "", str(exc)


def adb(adb_path: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return run([adb_path, *args], timeout=timeout)


def adb_s(adb_path: str, serial: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return adb(adb_path, "-s", serial, *args, timeout=timeout)


def parse_devices(adb_path: str) -> list[dict[str, Any]]:
    code, out, _ = adb(adb_path, "devices", "-l", timeout=15)
    devices: list[dict[str, Any]] = []
    if code != 0:
        return devices

    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue

        parts = line.split()
        if len(parts) >= 2:
            serial = parts[0]
            devices.append({
                "serial": serial,
                "state": parts[1],
                "detail": " ".join(parts[2:]),
                "is_wifi": bool(re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", serial)),
            })
    return devices


def shell(adb_path: str, serial: str, *args: str, timeout: int = 20) -> str:
    code, out, _ = adb_s(adb_path, serial, "shell", *args, timeout=timeout)
    return out.strip() if code == 0 else ""


def get_wifi_ip(adb_path: str, serial: str) -> str:
    out = shell(adb_path, serial, "ip", "-f", "inet", "addr", "show", "wlan0", timeout=10)
    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
    if match:
        return match.group(1)
    return ""


def enrich_device(adb_path: str, dev: dict[str, Any]) -> dict[str, Any]:
    out = dict(dev)
    if dev["state"] != "device":
        out["usable"] = False
        return out

    serial = dev["serial"]
    out["usable"] = True
    out["model"] = shell(adb_path, serial, "getprop", "ro.product.model", timeout=10)
    out["android_version"] = shell(adb_path, serial, "getprop", "ro.build.version.release", timeout=10)
    out["android_id"] = shell(adb_path, serial, "settings", "get", "secure", "android_id", timeout=10)
    out["wifi_ip"] = get_wifi_ip(adb_path, serial)
    return out


def canonicalize(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for dev in devices:
        key = dev.get("android_id") or dev.get("serial")
        grouped.setdefault(key, []).append(dev)

    result = []
    for _, group in grouped.items():
        usable = [x for x in group if x.get("usable")]
        wifi = [x for x in usable if x.get("is_wifi")]
        chosen = wifi[0] if wifi else (usable[0] if usable else group[0])
        chosen = dict(chosen)
        chosen["duplicate_transports"] = [
            {
                "serial": x.get("serial"),
                "state": x.get("state"),
                "is_wifi": x.get("is_wifi"),
            }
            for x in group
        ]
        result.append(chosen)

    return result


def package_exists(adb_path: str, serial: str) -> bool:
    code, out, _ = adb_s(adb_path, serial, "shell", "pm", "path", TARGET_PACKAGE, timeout=15)
    return code == 0 and "package:" in out


def run_as_cat(adb_path: str, serial: str, app_path: str) -> tuple[bool, str]:
    code, out, err = adb_s(
        adb_path,
        serial,
        "shell",
        "run-as",
        TARGET_PACKAGE,
        "cat",
        app_path,
        timeout=15,
    )
    if code == 0:
        return True, out
    return False, err or out


def try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return text


def redact_jsonish(obj: Any) -> Any:
    secret_words = ("token", "secret", "password", "pass", "key", "auth", "bearer", "credential")

    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            low = str(k).lower()
            if any(word in low for word in secret_words):
                clean[k] = "[REDACTED]"
            else:
                clean[k] = redact_jsonish(v)
        return clean

    if isinstance(obj, list):
        return [redact_jsonish(x) for x in obj]

    return obj


def read_worker_files(adb_path: str, serial: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "package": TARGET_PACKAGE,
        "installed": package_exists(adb_path, serial),
        "run_as_ok": False,
        "files": {},
        "errors": [],
    }

    if not result["installed"]:
        result["errors"].append("Target worker package not installed.")
        return result

    code, out, err = adb_s(adb_path, serial, "shell", "run-as", TARGET_PACKAGE, "pwd", timeout=10)
    if code != 0:
        result["errors"].append("run-as failed; app may not be debuggable.")
        result["errors"].append(err or out)
        return result

    result["run_as_ok"] = True
    result["data_dir"] = out.strip()

    wanted = [
        "./files/worker_identity.json",
        "./files/worker_connection.json",
    ]

    for rel in wanted:
        ok, text = run_as_cat(adb_path, serial, rel)
        parsed = try_json(text) if ok else text
        result["files"][rel] = {
            "read_ok": ok,
            "redacted_content": redact_jsonish(parsed),
        }

    return result


def build_state(canonical_devices: list[dict[str, Any]], worker_reads: list[dict[str, Any]]) -> dict[str, Any]:
    paired_candidates = []

    for item in worker_reads:
        files = item.get("worker_files", {}).get("files", {})
        identity = files.get("./files/worker_identity.json", {})
        connection = files.get("./files/worker_connection.json", {})

        paired_candidates.append({
            "serial": item.get("serial"),
            "model": item.get("model"),
            "android_id": item.get("android_id"),
            "wifi_ip": item.get("wifi_ip"),
            "package": TARGET_PACKAGE,
            "identity_read_ok": identity.get("read_ok", False),
            "connection_read_ok": connection.get("read_ok", False),
            "worker_identity_redacted": identity.get("redacted_content"),
            "worker_connection_redacted": connection.get("redacted_content"),
        })

    return {
        "overall": "WORKER_FILES_READ" if any(x["identity_read_ok"] or x["connection_read_ok"] for x in paired_candidates) else "NO_WORKER_PAIRING_FILES_READ",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engel_root": str(ENGEL_ROOT),
        "target_package": TARGET_PACKAGE,
        "wrong_package_avoided": "com.engel.engel_monitor",
        "notes": [
            "This file is desktop-side state only.",
            "Secrets are redacted.",
            "If worker_connection shows an old host/port/token state, Engel desktop must match or regenerate it.",
            "This script does not launch or inspect com.engel.engel_monitor.",
        ],
        "canonical_devices": canonical_devices,
        "paired_candidates": paired_candidates,
    }


def markdown_report(state: dict[str, Any]) -> str:
    lines = [
        "# Engel Remote Worker Pairing Report",
        "",
        f"- Time: `{state.get('timestamp')}`",
        f"- Target package: `{TARGET_PACKAGE}`",
        "- Avoided wrong/old package: `com.engel.engel_monitor`",
        f"- Overall: `{state.get('overall')}`",
        "",
        "## Meaning",
        "",
        "The real worker app is `com.example.engel_remote_worker`. The older monitor app is not used by this script.",
        "The important app files are `worker_identity.json` and `worker_connection.json`.",
        "",
        "## Devices",
        "",
    ]

    for d in state.get("paired_candidates", []):
        lines += [
            f"### {d.get('model')} / {d.get('serial')}",
            "",
            f"- Android ID: `{d.get('android_id')}`",
            f"- Wi-Fi IP: `{d.get('wifi_ip')}`",
            f"- Identity read ok: `{d.get('identity_read_ok')}`",
            f"- Connection read ok: `{d.get('connection_read_ok')}`",
            "",
            "Redacted worker identity:",
            "```json",
            json.dumps(d.get("worker_identity_redacted"), indent=2),
            "```",
            "",
            "Redacted worker connection:",
            "```json",
            json.dumps(d.get("worker_connection_redacted"), indent=2),
            "```",
            "",
        ]

    lines += [
        "## Next decision",
        "",
        "If `worker_connection.json` has stale desktop host/port info, the desktop app needs to write a matching connection state or the Android app needs a refresh/re-pair action.",
        "If it has no usable pairing fields, the Android app needs a real pairing endpoint/intent added later.",
        "",
    ]

    return "\n".join(lines)


def main() -> None:
    ensure_dirs()
    log("Starting safe Engel Remote Worker pairing reader.")
    adb_path = find_adb()

    raw: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "adb_path": adb_path,
        "target_package": TARGET_PACKAGE,
    }

    if not adb_path:
        state = {
            "overall": "ADB_NOT_FOUND",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "target_package": TARGET_PACKAGE,
            "error": "ADB not found under approved D paths.",
        }
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        REPORT_FILE.write_text(markdown_report(state), encoding="utf-8")
        print("ADB not found.")
        return

    adb(adb_path, "start-server", timeout=15)

    raw_devices = parse_devices(adb_path)
    enriched = [enrich_device(adb_path, d) for d in raw_devices]
    canonical = canonicalize(enriched)

    worker_reads = []
    for dev in canonical:
        if not dev.get("usable"):
            continue
        serial = dev["serial"]
        worker_reads.append({
            "serial": serial,
            "model": dev.get("model"),
            "android_id": dev.get("android_id"),
            "wifi_ip": dev.get("wifi_ip"),
            "worker_files": read_worker_files(adb_path, serial),
        })

    raw["raw_devices"] = raw_devices
    raw["enriched_devices"] = enriched
    raw["canonical_devices"] = canonical
    raw["worker_reads"] = worker_reads

    state = build_state(canonical, worker_reads)

    RAW_FILE.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(markdown_report(state), encoding="utf-8")

    log(f"Wrote state: {STATE_FILE}")
    log(f"Wrote raw: {RAW_FILE}")
    log(f"Wrote report: {REPORT_FILE}")
    log(f"Finished. Overall: {state['overall']}")

    print("")
    print("DONE")
    print(f"Overall: {state['overall']}")
    print(f"Open report: {REPORT_FILE}")
    print(f"Open state:  {STATE_FILE}")


if __name__ == "__main__":
    main()
