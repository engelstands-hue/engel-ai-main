#!/usr/bin/env python3
"""Bounded wake helper for Engel Android worker phones.

The wake lane is intentionally narrow: it may only wake the screen and launch
the visible Engel Remote Worker app over USB ADB. It never transfers job
payloads, enables WiFi ADB, starts a shell session, or grants phone control of
Engel. Actual work still moves through the existing LAN assignment queue.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from engel_project_paths import resolve_engel_app_root

ROOT = resolve_engel_app_root(__file__)
PHONE_MAP_PATH = ROOT / "memory" / "ENGEL_PHONE_DEVICE_MAP_V1.json"
LINK_STATE_PATH = ROOT / "remote_workers" / "lan_link_manager" / "session_state.json"
SESSION_PATH = ROOT / "remote_workers" / "lan_pairing" / "pairing_session.json"
REPORT_DIR = ROOT / "reports" / "phone_wake"
LOCAL_PLATFORM_TOOLS_ADB = ROOT / "tools" / "platform-tools" / "adb.exe"
APP_PACKAGE = "com.example.engel_remote_worker"
DEFAULT_STALE_AFTER_SECONDS = 10 * 60
ADB_TIMEOUT_SECONDS = 20

FALLBACK_WORKERS: dict[str, dict[str, str]] = {
    "android_worker_alpha": {
        "adb_serial": "ANDROID_WORKER_ALPHA",
        "marketing_name": "Moto G Power 2025",
    },
    "android_worker_beta": {
        "adb_serial": "ANDROID_WORKER_BETA",
        "marketing_name": "Moto G Fast",
    },
}


@dataclass
class WakeResult:
    worker_id: str
    serial: str
    label: str
    stale: bool
    age_seconds: float | None
    adb_available: bool
    usb_connected: bool
    applied: bool
    attempted: bool
    success: bool
    detail: str
    commands: list[list[str]]
    pairing_config_refreshed: bool = False
    report_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "serial": self.serial,
            "label": self.label,
            "stale": self.stale,
            "age_seconds": self.age_seconds,
            "adb_available": self.adb_available,
            "usb_connected": self.usb_connected,
            "applied": self.applied,
            "attempted": self.attempted,
            "success": self.success,
            "detail": self.detail,
            "commands": self.commands,
            "pairing_config_refreshed": self.pairing_config_refreshed,
            "report_path": self.report_path,
            "job_payload_over_usb": False,
            "pairing_config_over_usb": self.pairing_config_refreshed,
            "wifi_adb_enabled": False,
            "raw_shell_target": False,
            "phone_controls_engel": False,
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_stamp(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def phone_worker_map() -> dict[str, dict[str, str]]:
    mapping = {key: dict(value) for key, value in FALLBACK_WORKERS.items()}
    payload = load_json(PHONE_MAP_PATH)
    phones = payload.get("phones") if isinstance(payload, dict) else None
    if isinstance(phones, list):
        for phone in phones:
            if not isinstance(phone, dict):
                continue
            worker_id = str(phone.get("assigned_worker_id") or "").strip()
            serial = str(phone.get("adb_serial") or "").strip()
            if not worker_id or not serial:
                continue
            mapping[worker_id] = {
                "adb_serial": serial,
                "marketing_name": str(phone.get("marketing_name") or worker_id),
            }
    return mapping


def load_link_state() -> dict[str, Any]:
    payload = load_json(LINK_STATE_PATH)
    return payload if isinstance(payload, dict) else {}


def worker_last_seen(worker_id: str, state: dict[str, Any] | None = None) -> str | None:
    state = state if state is not None else load_link_state()
    workers = state.get("workers")
    if isinstance(workers, dict):
        record = workers.get(worker_id)
        if isinstance(record, dict) and isinstance(record.get("last_seen_utc"), str):
            return record["last_seen_utc"]
    identity = state.get("paired_phone_identity")
    if isinstance(identity, dict) and identity.get("worker_id") == worker_id:
        value = state.get("last_seen_utc")
        return value if isinstance(value, str) else None
    return None


def seconds_since_worker_seen(worker_id: str, now: datetime | None = None) -> float | None:
    seen = parse_utc(worker_last_seen(worker_id))
    if seen is None:
        return None
    return max(0.0, ((now or utc_now()) - seen).total_seconds())


def worker_is_stale(worker_id: str, stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS) -> tuple[bool, float | None]:
    age = seconds_since_worker_seen(worker_id)
    return age is None or age >= stale_after_seconds, age


def current_pairing_code() -> str | None:
    payload = load_json(SESSION_PATH)
    if not isinstance(payload, dict):
        return None
    code = str(payload.get("pairing_code") or "").strip()
    return code or None


def current_lan_host() -> str:
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.0.2.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -First 1 -ExpandProperty IPAddress)",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        host = proc.stdout.strip()
        if host:
            return host
    except Exception:
        pass
    return "192.0.2.40"


def resolve_adb(explicit: str | None = None) -> str | None:
    if explicit:
        candidate = Path(explicit).expanduser()
        return str(candidate) if candidate.is_file() else None
    if LOCAL_PLATFORM_TOOLS_ADB.is_file():
        return str(LOCAL_PLATFORM_TOOLS_ADB)
    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        base = os.environ.get(env_name)
        if base:
            candidate = Path(base) / "platform-tools" / "adb.exe"
            if candidate.is_file():
                return str(candidate)
    found = shutil.which("adb.exe") or shutil.which("adb")
    return found


def run_adb(adb: str, args: list[str], timeout: int = ADB_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [adb] + args,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def connected_usb_serials(adb: str) -> set[str]:
    proc = run_adb(adb, ["devices", "-l"], timeout=10)
    serials: set[str] = set()
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.add(parts[0])
    return serials


def _command_preview(adb: str, serial: str) -> list[list[str]]:
    exe = Path(adb).name if adb else "adb.exe"
    return [
        [exe, "-s", serial, "push", "<redacted-pairing-config>", "/sdcard/Android/data/com.example.engel_remote_worker/files/worker_connection.json"],
        [exe, "-s", serial, "shell", "run-as", APP_PACKAGE, "cp", "<redacted-pairing-config>", "files/worker_connection.json"],
        [exe, "-s", serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP"],
        [exe, "-s", serial, "shell", "am", "force-stop", APP_PACKAGE],
        [exe, "-s", serial, "shell", "monkey", "-p", APP_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"],
    ]


def refresh_pairing_config(adb: str, serial: str, worker_id: str, label: str) -> tuple[bool, str]:
    code = current_pairing_code()
    if not code:
        return False, "No current LAN pairing token is available."
    connection = {
        "host": current_lan_host(),
        "port": 8765,
        "pairing_code": code,
        "auto_pair": True,
    }
    identity = {
        "worker_id": worker_id,
        "worker_name": "Android Worker Alpha" if worker_id == "android_worker_alpha" else "Android Worker Beta",
        "phone_model": label,
    }
    tmp_paths: list[Path] = []
    try:
        config_fd, config_name = tempfile.mkstemp(prefix="engel_worker_connection_", suffix=".json")
        identity_fd, identity_name = tempfile.mkstemp(prefix="engel_worker_identity_", suffix=".json")
        os.close(config_fd)
        os.close(identity_fd)
        config_path = Path(config_name)
        identity_path = Path(identity_name)
        tmp_paths.extend([config_path, identity_path])
        config_path.write_text(json.dumps(connection, separators=(",", ":")), encoding="utf-8")
        identity_path.write_text(json.dumps(identity, separators=(",", ":")), encoding="utf-8")
        commands = [
            (["-s", serial, "push", str(config_path), f"/sdcard/Android/data/{APP_PACKAGE}/files/worker_connection.json"], 20),
            (["-s", serial, "push", str(identity_path), f"/sdcard/Android/data/{APP_PACKAGE}/files/worker_identity.json"], 20),
            (["-s", serial, "push", str(config_path), "/data/local/tmp/engel_worker_connection.json"], 20),
            (["-s", serial, "push", str(identity_path), "/data/local/tmp/engel_worker_identity.json"], 20),
            (["-s", serial, "shell", "chmod", "644", "/data/local/tmp/engel_worker_connection.json", "/data/local/tmp/engel_worker_identity.json"], 20),
            (["-s", serial, "shell", "run-as", APP_PACKAGE, "cp", "/data/local/tmp/engel_worker_connection.json", "files/worker_connection.json"], 20),
            (["-s", serial, "shell", "run-as", APP_PACKAGE, "cp", "/data/local/tmp/engel_worker_identity.json", "files/worker_identity.json"], 20),
        ]
        for args, timeout in commands:
            proc = run_adb(adb, args, timeout=timeout)
            if proc.returncode != 0:
                return False, "Pairing config refresh failed at bounded ADB step."
        return True, "Current pairing config refreshed in external and internal app storage."
    finally:
        for path in tmp_paths:
            try:
                path.unlink()
            except OSError:
                pass


def wake_worker_if_stale(
    worker_id: str,
    *,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    apply: bool = False,
    adb_path: str | None = None,
    write_report: bool = False,
) -> WakeResult:
    mapping = phone_worker_map()
    info = mapping.get(worker_id, {})
    serial = str(info.get("adb_serial") or "").strip()
    label = str(info.get("marketing_name") or worker_id)
    stale, age = worker_is_stale(worker_id, stale_after_seconds=stale_after_seconds)
    adb = resolve_adb(adb_path)
    commands = _command_preview(adb or "adb.exe", serial or "<unknown-serial>")

    if not serial:
        result = WakeResult(worker_id, "", label, stale, age, bool(adb), False, apply, False, False, "No USB serial is registered for this worker.", commands)
        return _maybe_write_report(result, write_report)
    if not stale:
        result = WakeResult(worker_id, serial, label, stale, age, bool(adb), False, apply, False, True, "Worker is fresh; wake skipped.", commands)
        return _maybe_write_report(result, write_report)
    if not adb:
        result = WakeResult(worker_id, serial, label, stale, age, False, False, apply, False, False, "ADB is not available; WiFi polling must resume from the foreground app.", commands)
        return _maybe_write_report(result, write_report)

    serials = connected_usb_serials(adb)
    usb_connected = serial in serials
    if not usb_connected:
        result = WakeResult(worker_id, serial, label, stale, age, True, False, apply, False, False, "USB device is not connected; Engel cannot force-wake this phone over WiFi.", commands)
        return _maybe_write_report(result, write_report)
    if not apply:
        result = WakeResult(worker_id, serial, label, stale, age, True, True, False, False, True, "Worker is stale and USB-connected; wake would be applied with --apply.", commands)
        return _maybe_write_report(result, write_report)

    refreshed, refresh_detail = refresh_pairing_config(adb, serial, worker_id, label)
    wake = run_adb(adb, ["-s", serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP"])
    stop = run_adb(adb, ["-s", serial, "shell", "am", "force-stop", APP_PACKAGE])
    launch = run_adb(adb, ["-s", serial, "shell", "monkey", "-p", APP_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])
    success = refreshed and wake.returncode == 0 and stop.returncode == 0 and launch.returncode == 0
    detail = f"{refresh_detail} Wake key sent, stale app process refreshed, and Engel Remote Worker launch requested." if success else (
        "Wake attempted, but ADB returned a non-zero status. "
        f"wake_rc={wake.returncode}; stop_rc={stop.returncode}; launch_rc={launch.returncode}"
    )
    result = WakeResult(worker_id, serial, label, stale, age, True, True, True, True, success, detail, commands, refreshed)
    return _maybe_write_report(result, write_report)


def wake_all_stale(
    *,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    apply: bool = False,
    adb_path: str | None = None,
    write_report: bool = False,
) -> list[WakeResult]:
    results = [
        wake_worker_if_stale(
            worker_id,
            stale_after_seconds=stale_after_seconds,
            apply=apply,
            adb_path=adb_path,
            write_report=False,
        )
        for worker_id in sorted(phone_worker_map())
    ]
    if write_report:
        path = write_receipt(results)
        for result in results:
            result.report_path = str(path)
    return results


def _maybe_write_report(result: WakeResult, enabled: bool) -> WakeResult:
    if enabled:
        result.report_path = str(write_receipt([result]))
    return result


def write_receipt(results: list[WakeResult]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    path = REPORT_DIR / f"ENGEL_PHONE_WAKE_{stamp}.json"
    payload = {
        "created_at_utc": utc_stamp(),
        "mode": "bounded_usb_wake_only",
        "app_package": APP_PACKAGE,
        "job_payload_over_usb": False,
        "pairing_config_over_usb": True,
        "wifi_adb_enabled": False,
        "raw_shell_target": False,
        "phone_controls_engel": False,
        "results": [result.to_dict() for result in results],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def status_payload() -> dict[str, Any]:
    mapping = phone_worker_map()
    return {
        "mode": "bounded_usb_wake_only",
        "stale_after_seconds": DEFAULT_STALE_AFTER_SECONDS,
        "workers": {
            worker_id: {
                "serial": info.get("adb_serial"),
                "label": info.get("marketing_name"),
                "last_seen_utc": worker_last_seen(worker_id),
                "age_seconds": seconds_since_worker_seen(worker_id),
            }
            for worker_id, info in sorted(mapping.items())
        },
        "job_payload_over_usb": False,
        "wifi_adb_enabled": False,
        "raw_shell_target": False,
        "phone_controls_engel": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded Engel phone wake helper")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="Show worker stale state; no wake.")
    wake_stale = sub.add_parser("wake-stale", help="Wake all stale USB-connected Engel phones.")
    wake_stale.add_argument("--apply", action="store_true", help="Actually send bounded wake/launch commands.")
    wake_stale.add_argument("--stale-after-seconds", type=int, default=DEFAULT_STALE_AFTER_SECONDS)
    wake_stale.add_argument("--adb-path")
    wake_stale.add_argument("--write-report", action="store_true")
    wake_one = sub.add_parser("wake-worker", help="Wake one stale USB-connected Engel phone.")
    wake_one.add_argument("worker_id")
    wake_one.add_argument("--apply", action="store_true", help="Actually send bounded wake/launch commands.")
    wake_one.add_argument("--stale-after-seconds", type=int, default=DEFAULT_STALE_AFTER_SECONDS)
    wake_one.add_argument("--adb-path")
    wake_one.add_argument("--write-report", action="store_true")
    args = parser.parse_args(argv)

    if args.command in (None, "status"):
        print(json.dumps(status_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "wake-stale":
        results = wake_all_stale(
            stale_after_seconds=args.stale_after_seconds,
            apply=args.apply,
            adb_path=args.adb_path,
            write_report=args.write_report,
        )
        print(json.dumps([result.to_dict() for result in results], indent=2, sort_keys=True))
        return 0 if all(result.success for result in results) else 1
    if args.command == "wake-worker":
        result = wake_worker_if_stale(
            args.worker_id,
            stale_after_seconds=args.stale_after_seconds,
            apply=args.apply,
            adb_path=args.adb_path,
            write_report=args.write_report,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.success else 1
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
