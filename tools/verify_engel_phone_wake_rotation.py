#!/usr/bin/env python3
"""Verify long-idle phone wake and token-rotation safeguards."""
from __future__ import annotations

import datetime
import py_compile
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVER = ROOT / "engel_remote_worker_lan_pairing.py"
WAKE_MANAGER = ROOT / "engel_phone_wake_manager.py"
MEETING_ROOM = ROOT / "engel_agent_meeting_room.py"
APP_MAIN = ROOT / "mobile" / "engel_remote_worker" / "lib" / "main.dart"
PUBSPEC = ROOT / "mobile" / "engel_remote_worker" / "pubspec.yaml"
CONTRACT = ROOT / "mobile" / "engel_remote_worker" / "ENGEL_REMOTE_WORKER_ANDROID_CONTRACT_V1.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> None:
    py_compile.compile(str(SERVER), doraise=True)
    py_compile.compile(str(WAKE_MANAGER), doraise=True)
    server = read(SERVER)
    wake_manager = read(WAKE_MANAGER)
    meeting_room = read(MEETING_ROOM)
    app = read(APP_MAIN)
    pubspec = read(PUBSPEC)
    contract = read(CONTRACT)

    for needle in (
        "TOKEN_ROTATE_GRACE_SECONDS",
        "PAIRED_WORKER_CONTINUITY_SECONDS",
        "seconds_remaining",
        "token_auto_rotation",
        "8 * 60 * 60",
        "get_or_create_session()",
        "create_pairing_session()",
        "sock.sendto",
        '"workers": workers',
    ):
        require(needle in server, f"LAN receiver missing wake/rotation marker: {needle}")

    for needle in (
        "with WidgetsBindingObserver",
        "didChangeAppLifecycleState",
        "WakelockPlus.enable()",
        "Wake Guard",
        "unawaited(_pair())",
        "unawaited(_pollOnce())",
    ):
        require(needle in app, f"Android worker missing resume/wake marker: {needle}")

    version_match = re.search(r"^version:\s+(\d+)\.(\d+)\.(\d+)\+(\d+)", pubspec, re.MULTILINE)
    require(version_match is not None, "Android worker version line missing")
    version = tuple(int(part) for part in version_match.groups())
    require(version >= (1, 0, 9, 10), "Android worker build number was not bumped")

    for needle in (
        "wake_worker_if_stale",
        "refresh_pairing_config",
        "KEYCODE_WAKEUP",
        "force-stop",
        "monkey",
        "job_payload_over_usb",
        "pairing_config_over_usb",
        "wifi_adb_enabled",
        "raw_shell_target",
        "ENGEL_PHONE_DEVICE_MAP_V1.json",
    ):
        require(needle in wake_manager, f"wake manager missing bounded wake marker: {needle}")

    require("wake_worker_if_stale(worker_id, apply=True)" in meeting_room, "Meeting Room must wake stale phones before Android dispatch")

    for needle in (
        "Phase 6 Long-Idle Wake Guard",
        "visible foreground screen wakelock",
        "USB wake does not transfer job payloads",
        "reports must redact the token",
        "WiFi ADB remains disabled",
    ):
        require(needle in contract, f"Android contract missing wake guard marker: {needle}")

    from engel_remote_worker_lan_pairing import PairingSession, utc_stamp

    now = datetime.datetime(2026, 5, 26, 20, 0, 0, tzinfo=datetime.timezone.utc)
    future = now + datetime.timedelta(seconds=90)
    session = PairingSession("REDACTED", utc_stamp(now), utc_stamp(future))
    require(80 <= session.seconds_remaining(now) <= 90, "seconds_remaining did not compute future token time")
    expired = PairingSession("REDACTED", utc_stamp(now), utc_stamp(now - datetime.timedelta(seconds=1)))
    require(expired.is_expired(now), "expired token should be expired")
    require(expired.seconds_remaining(now) == 0.0, "expired token should have zero seconds remaining")

    from engel_phone_wake_manager import worker_is_stale, status_payload

    stale, age = worker_is_stale("android_worker_missing_for_verifier", stale_after_seconds=1)
    require(stale and age is None, "missing worker should be treated as stale")
    payload = status_payload()
    require(payload.get("job_payload_over_usb") is False, "wake manager must not move job payloads over USB")
    require(payload.get("wifi_adb_enabled") is False, "wake manager must not enable WiFi ADB")
    print("OK: Engel phone wake and LAN token rotation verified")


if __name__ == "__main__":
    main()
