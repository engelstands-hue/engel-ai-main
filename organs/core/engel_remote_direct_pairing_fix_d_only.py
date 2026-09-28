#!/usr/bin/env python3
"""
Engel Remote Direct Pairing Fix / Probe - D-only

Run from:
  D:
  cd "D:\\b.WorkSpace\\Engel App"
  python engel_remote_direct_pairing_fix_d_only.py

Purpose:
- Do NOT use Claude/Codex.
- Do NOT write to C:.
- Confirm ADB transport, de-duplicate USB/Wi-Fi transports by Android ID.
- Inspect Engel Remote Android app packages.
- Launch the app.
- Capture logcat lines that mention pairing / token / server / websocket / not paired.
- If the app is debuggable, safely read app files/shared_prefs/databases using run-as.
- Create a D-only Engel pairing state JSON for the desktop side.
- Write a clear BLOCKED report if the Android app does not expose a pairing API we can call from ADB.

Important:
- This script will NOT fake "paired".
- It does not modify Android app data by default.
- It only writes D:\\b.WorkSpace\\Engel App\\memory\\phone_bridge and reports.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import hashlib
from pathlib import Path
from typing import Any

ENGEL_ROOT = Path(r"D:\b.WorkSpace\Engel App")
BRIDGE_DIR = ENGEL_ROOT / "memory" / "phone_bridge"
REPORT_DIR = ENGEL_ROOT / "reports" / "codex_bridge"
TOOLS_DIR = ENGEL_ROOT / "tools"

STATUS_FILE = BRIDGE_DIR / "ENGEL_REMOTE_DIRECT_PAIRING_STATE.json"
REPORT_FILE = REPORT_DIR / "ENGEL_REMOTE_DIRECT_PAIRING_PROBE_REPORT.md"
RAW_JSON_FILE = BRIDGE_DIR / "ENGEL_REMOTE_DIRECT_PAIRING_PROBE_RAW.json"
LOG_FILE = BRIDGE_DIR / "engel_remote_direct_pairing_probe.log"

ADB_CANDIDATES = [
    ENGEL_ROOT / "tools" / "platform-tools" / "adb.exe",
    Path(r"D:\platform-tools\adb.exe"),
    ENGEL_ROOT / "platform-tools" / "adb.exe",
    Path.cwd() / "tools" / "platform-tools" / "adb.exe",
    Path.cwd() / "platform-tools" / "adb.exe",
    Path.cwd() / "adb.exe",
]

TARGET_PACKAGES = [
    "com.example.engel_remote_worker",
    "com.engel.engel_monitor",
]

PAIRING_KEYWORDS = [
    "pair", "paired", "pairing", "not paired",
    "token", "secret", "shared secret", "handshake",
    "server", "host", "port", "url", "uri",
    "http", "https", "ws://", "wss://", "websocket",
    "qr", "code", "device id", "device_id",
    "engel", "remote", "bridge", "worker",
]


def assert_d_only(path: Path) -> None:
    text = str(path)
    if not text.lower().startswith("d:\\"):
        raise RuntimeError(f"Blocked non-D path: {text}")


def ensure_dirs() -> None:
    for p in [ENGEL_ROOT, BRIDGE_DIR, REPORT_DIR, TOOLS_DIR]:
        assert_d_only(p)
        p.mkdir(parents=True, exist_ok=True)


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

    # PATH fallback, but reject C:\ adb.
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
            log("STDOUT: " + out[:5000])
        if err:
            log("STDERR: " + err[:5000])
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        return 998, "", f"Timed out after {timeout}s"
    except Exception as e:
        return 997, "", str(e)


def adb_cmd(adb: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return run([adb, *args], timeout=timeout)


def adb_serial(adb: str, serial: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return adb_cmd(adb, "-s", serial, *args, timeout=timeout)


def parse_devices(adb: str) -> list[dict[str, Any]]:
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
                "is_wifi_transport": bool(re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", parts[0])),
            })
    return devices


def shell(adb: str, serial: str, *args: str, timeout: int = 30) -> str:
    code, out, err = adb_serial(adb, serial, "shell", *args, timeout=timeout)
    if code == 0:
        return out.strip()
    return ""


def get_device_identity(adb: str, dev: dict[str, Any]) -> dict[str, Any]:
    serial = dev["serial"]
    result = dict(dev)
    if dev["state"] != "device":
        result["usable"] = False
        result["error"] = f"ADB state is {dev['state']}"
        return result

    result["model"] = shell(adb, serial, "getprop", "ro.product.model", timeout=10)
    result["android_version"] = shell(adb, serial, "getprop", "ro.build.version.release", timeout=10)
    result["android_id"] = shell(adb, serial, "settings", "get", "secure", "android_id", timeout=10)
    result["wifi_ip"] = get_wifi_ip(adb, serial)
    result["usable"] = True
    return result


def get_wifi_ip(adb: str, serial: str) -> str:
    out = shell(adb, serial, "ip", "-f", "inet", "addr", "show", "wlan0", timeout=10)
    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
    if m:
        return m.group(1)

    out = shell(adb, serial, "ifconfig", "wlan0", timeout=10)
    m = re.search(r"inet(?: addr:)?\s*(\d+\.\d+\.\d+\.\d+)", out)
    if m:
        return m.group(1)

    return ""


def canonicalize_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Merge USB/Wi-Fi duplicates by android_id. Prefer Wi-Fi transport if present and usable.
    groups: dict[str, list[dict[str, Any]]] = {}
    for d in devices:
        key = d.get("android_id") or d.get("serial")
        groups.setdefault(key, []).append(d)

    canonical = []
    for android_id, group in groups.items():
        usable = [g for g in group if g.get("usable")]
        wifi = [g for g in usable if g.get("is_wifi_transport")]
        selected = wifi[0] if wifi else (usable[0] if usable else group[0])
        selected = dict(selected)
        selected["duplicate_transports"] = [
            {
                "serial": g.get("serial"),
                "state": g.get("state"),
                "is_wifi_transport": g.get("is_wifi_transport"),
            }
            for g in group
        ]
        selected["canonical_reason"] = "preferred Wi-Fi transport" if wifi else "preferred first usable transport"
        canonical.append(selected)

    return canonical


def package_exists(adb: str, serial: str, package: str) -> bool:
    code, out, err = adb_serial(adb, serial, "shell", "pm", "path", package, timeout=15)
    return code == 0 and "package:" in out


def resolve_activity(adb: str, serial: str, package: str) -> str:
    code, out, err = adb_serial(
        adb, serial, "shell", "cmd", "package", "resolve-activity", "--brief", package, timeout=15
    )
    if code == 0:
        lines = [x.strip() for x in out.splitlines() if x.strip()]
        for line in reversed(lines):
            if "/" in line:
                return line
    return ""


def launch_package(adb: str, serial: str, package: str) -> dict[str, Any]:
    activity = resolve_activity(adb, serial, package)
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
    return {
        "package": package,
        "activity": activity,
        "launch_ok": code == 0,
        "launch_stdout": out[-1500:],
        "launch_stderr": err[-1500:],
    }


def dumpsys_package(adb: str, serial: str, package: str) -> str:
    code, out, err = adb_serial(adb, serial, "shell", "dumpsys", "package", package, timeout=30)
    return out if code == 0 else ""


def extract_interesting_manifest_bits(dumpsys: str) -> dict[str, Any]:
    bits: dict[str, Any] = {
        "debuggable_hint": "DEBUGGABLE" in dumpsys or "debuggable" in dumpsys.lower(),
        "activities": [],
        "services": [],
        "receivers": [],
        "providers": [],
        "permissions": [],
        "intent_lines": [],
    }

    for line in dumpsys.splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if "/" in stripped and ("activity" in low or "service" in low or "receiver" in low or "provider" in low):
            if "activity" in low:
                bits["activities"].append(stripped[:500])
            elif "service" in low:
                bits["services"].append(stripped[:500])
            elif "receiver" in low:
                bits["receivers"].append(stripped[:500])
            elif "provider" in low:
                bits["providers"].append(stripped[:500])

        if "permission" in low and len(bits["permissions"]) < 80:
            bits["permissions"].append(stripped[:500])

        if any(k in low for k in PAIRING_KEYWORDS) and len(bits["intent_lines"]) < 120:
            bits["intent_lines"].append(stripped[:800])

    # de-dupe while preserving order
    for k in ["activities", "services", "receivers", "providers", "permissions", "intent_lines"]:
        seen = set()
        out = []
        for item in bits[k]:
            if item not in seen:
                out.append(item)
                seen.add(item)
        bits[k] = out[:80]

    return bits


def clear_logcat(adb: str, serial: str) -> None:
    adb_serial(adb, serial, "logcat", "-c", timeout=10)


def capture_logcat_pairing_lines(adb: str, serial: str, seconds: int = 8) -> list[str]:
    # Use adb logcat -d after a short wait. No background process.
    time.sleep(seconds)
    code, out, err = adb_serial(adb, serial, "logcat", "-d", "-v", "time", timeout=30)
    if code != 0:
        return []

    lines = []
    for line in out.splitlines():
        low = line.lower()
        if any(k in low for k in PAIRING_KEYWORDS):
            lines.append(line[-1000:])
    return lines[-250:]


def try_run_as_read(adb: str, serial: str, package: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "package": package,
        "run_as_ok": False,
        "files": [],
        "shared_prefs": {},
        "databases": [],
        "notes": [],
    }

    code, out, err = adb_serial(adb, serial, "shell", "run-as", package, "pwd", timeout=10)
    if code != 0:
        result["notes"].append("run-as failed. App is probably not debuggable, so app data cannot be read safely through ADB.")
        result["run_as_error"] = err or out
        return result

    result["run_as_ok"] = True
    result["app_data_dir"] = out.strip()

    code, out, err = adb_serial(adb, serial, "shell", "run-as", package, "find", ".", "-maxdepth", "3", "-type", "f", timeout=20)
    if code == 0:
        files = [x.strip() for x in out.splitlines() if x.strip()]
        result["files"] = files[:300]
        result["databases"] = [x for x in files if "database" in x.lower() or x.endswith(".db")][:80]

        pref_files = [x for x in files if "shared_prefs" in x and x.endswith(".xml")]
        for pf in pref_files[:20]:
            code2, content, err2 = adb_serial(adb, serial, "shell", "run-as", package, "cat", pf, timeout=10)
            if code2 == 0:
                # Redact obvious secrets while preserving keys and structure.
                redacted = redact_sensitive(content)
                result["shared_prefs"][pf] = redacted[:8000]

    return result


def redact_sensitive(text: str) -> str:
    patterns = [
        (r'(?i)(token|secret|password|passwd|key|auth|bearer)([^<>\n]{0,30})([=:]\s*|">)([^<\s"]+)', r'\1\2\3[REDACTED]'),
        (r'(?i)(token|secret|password|passwd|key|auth|bearer)"\s*:\s*"[^"]+"', r'\1":"[REDACTED]"'),
    ]
    out = text
    for pat, repl in patterns:
        out = re.sub(pat, repl, out)
    return out


def build_desktop_pairing_state(canonical_devices: list[dict[str, Any]], app_reports: list[dict[str, Any]]) -> dict[str, Any]:
    token_seed = f"{time.time()}::{os.getpid()}::{ENGEL_ROOT}".encode("utf-8")
    local_pairing_token_id = hashlib.sha256(token_seed).hexdigest()[:16]

    return {
        "overall": "TRANSPORT_OK_APP_PAIRING_UNKNOWN",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engel_root": str(ENGEL_ROOT),
        "bridge_dir": str(BRIDGE_DIR),
        "meaning": {
            "adb_connected": "Windows can reach Android through ADB.",
            "engel_remote_paired": "The Android app and Engel desktop share an app-level pairing state/token/protocol.",
            "current_problem": "ADB works, but app-level pairing is not proven yet.",
        },
        "local_pairing_token_id": local_pairing_token_id,
        "token_value_written": False,
        "token_note": "Only a token id is written. No secret token is exposed here.",
        "canonical_devices": canonical_devices,
        "android_app_reports": app_reports,
        "required_next_action": (
            "If logcat/manifest/run-as does not reveal a callable pairing API, update the Android "
            "Engel Remote app to accept a pairing intent/deep link or read a D/desktop-served pairing handshake."
        ),
    }


def make_markdown_report(raw: dict[str, Any], state: dict[str, Any]) -> str:
    lines = []
    lines.append("# Engel Remote Direct Pairing Probe Report")
    lines.append("")
    lines.append(f"- Time: `{raw.get('timestamp')}`")
    lines.append(f"- Engel root: `{ENGEL_ROOT}`")
    lines.append(f"- ADB path: `{raw.get('adb_path')}`")
    lines.append(f"- Status JSON: `{STATUS_FILE}`")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    lines.append("ADB transport is not the same as Engel Remote app pairing.")
    lines.append("This report checks whether the Android app exposes enough information to complete app-level pairing without Claude/Codex.")
    lines.append("")
    lines.append(f"- Overall: `{state.get('overall')}`")
    lines.append(f"- Canonical phone count: `{len(state.get('canonical_devices', []))}`")
    lines.append("")
    lines.append("## Canonical devices")
    lines.append("")
    for d in state.get("canonical_devices", []):
        lines.append(f"### {d.get('model', 'Android device')} / {d.get('serial')}")
        lines.append("")
        lines.append(f"- Android: `{d.get('android_version', '')}`")
        lines.append(f"- Android ID: `{d.get('android_id', '')}`")
        lines.append(f"- Wi-Fi IP: `{d.get('wifi_ip', '')}`")
        lines.append(f"- Selected reason: `{d.get('canonical_reason', '')}`")
        lines.append("- Duplicate transports:")
        for t in d.get("duplicate_transports", []):
            lines.append(f"  - `{t.get('serial')}` state=`{t.get('state')}` wifi=`{t.get('is_wifi_transport')}`")
        lines.append("")

    lines.append("## Android app findings")
    lines.append("")
    for ar in state.get("android_app_reports", []):
        lines.append(f"### Device `{ar.get('serial')}` package `{ar.get('package')}`")
        lines.append("")
        lines.append(f"- Installed: `{ar.get('installed')}`")
        lines.append(f"- Launch ok: `{ar.get('launch', {}).get('launch_ok')}`")
        lines.append(f"- Activity: `{ar.get('launch', {}).get('activity')}`")
        manifest = ar.get("manifest_bits", {})
        lines.append(f"- Debuggable hint: `{manifest.get('debuggable_hint')}`")
        lines.append(f"- Pairing/logcat lines found: `{len(ar.get('pairing_logcat_lines', []))}`")
        lines.append(f"- run-as ok: `{ar.get('run_as', {}).get('run_as_ok')}`")
        lines.append("")
        if manifest.get("intent_lines"):
            lines.append("Interesting manifest/package lines:")
            for item in manifest.get("intent_lines", [])[:20]:
                lines.append(f"- `{item}`")
            lines.append("")
        if ar.get("pairing_logcat_lines"):
            lines.append("Recent pairing-related logcat lines:")
            for item in ar.get("pairing_logcat_lines", [])[:30]:
                lines.append(f"- `{item}`")
            lines.append("")

    lines.append("## Decision")
    lines.append("")
    lines.append("If the app still says `not paired`, do not keep repairing ADB. ADB is only the cable/wireless transport.")
    lines.append("The desktop side must implement the same app-level pairing protocol expected by the Android package.")
    lines.append("")
    lines.append("If this report shows no pairing intent, receiver, service, port, logcat hint, or readable debug preference, then this is BLOCKED until the Android app is updated to expose one of these:")
    lines.append("")
    lines.append("1. A deep link / intent such as `engel://pair?...`.")
    lines.append("2. A broadcast receiver for pairing data.")
    lines.append("3. A local websocket/http pairing endpoint.")
    lines.append("4. A QR/token flow documented in the app.")
    lines.append("5. A debug-only ADB pairing command for local development.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ensure_dirs()
    log("Starting direct Engel Remote pairing probe/fix.")

    adb = find_adb()
    raw: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "adb_path": adb,
        "devices_raw": [],
        "devices_identity": [],
        "canonical_devices": [],
        "app_reports": [],
    }

    if not adb:
        state = {
            "overall": "ADB_NOT_FOUND",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "engel_root": str(ENGEL_ROOT),
            "fix": "Place adb.exe under D:\\b.WorkSpace\\Engel App\\tools\\platform-tools\\adb.exe or D:\\platform-tools\\adb.exe.",
        }
        STATUS_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        RAW_JSON_FILE.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        REPORT_FILE.write_text(make_markdown_report(raw, state), encoding="utf-8")
        log("ADB not found.")
        return

    adb_cmd(adb, "start-server", timeout=15)
    devices = parse_devices(adb)
    raw["devices_raw"] = devices

    identities = []
    for dev in devices:
        identities.append(get_device_identity(adb, dev))
    raw["devices_identity"] = identities

    canonical = canonicalize_devices(identities)
    raw["canonical_devices"] = canonical

    app_reports = []
    for dev in canonical:
        serial = dev.get("serial")
        if not serial or not dev.get("usable"):
            continue

        for package in TARGET_PACKAGES:
            installed = package_exists(adb, serial, package)
            app_report: dict[str, Any] = {
                "serial": serial,
                "device_model": dev.get("model"),
                "package": package,
                "installed": installed,
            }

            if installed:
                clear_logcat(adb, serial)
                app_report["launch"] = launch_package(adb, serial, package)
                dumpsys = dumpsys_package(adb, serial, package)
                app_report["manifest_bits"] = extract_interesting_manifest_bits(dumpsys)
                app_report["pairing_logcat_lines"] = capture_logcat_pairing_lines(adb, serial, seconds=8)
                app_report["run_as"] = try_run_as_read(adb, serial, package)
            else:
                app_report["note"] = "Package not installed on this canonical device."

            app_reports.append(app_report)

    raw["app_reports"] = app_reports

    state = build_desktop_pairing_state(canonical, app_reports)

    # Upgrade status if we found something actionable.
    found_actionable = False
    for ar in app_reports:
        bits = ar.get("manifest_bits", {})
        if ar.get("pairing_logcat_lines") or bits.get("intent_lines") or ar.get("run_as", {}).get("run_as_ok"):
            found_actionable = True
            break

    if found_actionable:
        state["overall"] = "ACTIONABLE_PAIRING_CLUES_FOUND"
    else:
        state["overall"] = "BLOCKED_NO_APP_PAIRING_API_FOUND"

    STATUS_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    RAW_JSON_FILE.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(make_markdown_report(raw, state), encoding="utf-8")

    log(f"Wrote state: {STATUS_FILE}")
    log(f"Wrote raw JSON: {RAW_JSON_FILE}")
    log(f"Wrote report: {REPORT_FILE}")
    log(f"Finished. Overall: {state['overall']}")

    print("")
    print("DONE")
    print(f"Open report: {REPORT_FILE}")
    print(f"Open state:  {STATUS_FILE}")
    print("")
    print("If overall is BLOCKED_NO_APP_PAIRING_API_FOUND, the Android app must expose a pairing command/API.")
    print("If overall is ACTIONABLE_PAIRING_CLUES_FOUND, paste the report back here and I will build the next direct fix.")


if __name__ == "__main__":
    main()
