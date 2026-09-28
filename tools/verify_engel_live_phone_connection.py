#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import urllib.request

from engel_phone_presence import phone_presence_snapshot


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "remote_workers" / "lan_link_manager" / "session_state.json"
PAIRED_PATH = ROOT / "memory" / "phone_bridge" / "ENGEL_REMOTE_WORKERS_PAIRED.json"
HEALTH_URL = "http://192.0.2.40:8765/health"
FRESH_SECONDS = 300
EXPECTED = {
    "android_worker_alpha": {
        "expected_ip": "192.0.2.78",
        "accepted_remote_addresses": {"192.0.2.78", "192.168.7.196"},
        "transport": "lan",
        "adb_serial": "ANDROID_WORKER_ALPHA",
    },
    "android_worker_beta": {
        "expected_ip": "192.0.2.83",
        "accepted_remote_addresses": {"192.0.2.83", "192.168.7.195", "127.0.0.1"},
        "transport": "lan_or_adb_reverse_usb",
        "adb_serial": "ANDROID_WORKER_BETA",
    },
    "android_worker_gamma": {
        "expected_ip": "198.51.100.236",
        "accepted_remote_addresses": {"198.51.100.236", "192.168.7.190"},
        "transport": "lan",
        "adb_serial": "ANDROID_WORKER_GAMMA",
    },
}


def fail(message: str) -> None:
    raise AssertionError(message)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"JSON root must be object: {path}")
    return value


def receiver_health() -> dict:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        fail(f"receiver health failed: {exc}")
    if not isinstance(payload, dict):
        fail("receiver health did not return a JSON object")
    if payload.get("status") != "engel_lan_pairing_receiver_ready":
        fail(f"receiver not ready: {payload}")
    return payload


def main() -> int:
    failures: list[str] = []
    details: list[dict] = []
    try:
        health = receiver_health()
    except AssertionError as exc:
        health = {}
        failures.append(str(exc))

    state = load_json(STATE_PATH)
    snapshot = phone_presence_snapshot(root=ROOT)

    if state.get("link_status") != "running":
        failures.append(f"link_status is not running: {state.get('link_status')}")
    if state.get("receiver_running") is not True:
        failures.append("receiver_running is not true in session_state.json")

    for worker_id, expected in EXPECTED.items():
        expected_ip = str(expected["expected_ip"])
        record = snapshot.get("workers", {}).get(worker_id)
        if not isinstance(record, dict):
            failures.append(f"{worker_id}: missing live worker record")
            details.append({"worker_id": worker_id, "expected_ip": expected_ip, "live": False})
            continue
        details.append(record)
        if record.get("live") is not True:
            failures.append(f"{worker_id}: {record.get('reason') or 'not live'}")

    result = {
        "schema": "engel_live_phone_connection_verifier_v1",
        "ok": not failures,
        "health": health,
        "state_path": str(STATE_PATH),
        "paired_path": str(PAIRED_PATH),
        "checked_at_utc": snapshot.get("checked_at_utc"),
        "presence_snapshot": snapshot,
        "details": details,
        "failures": failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
