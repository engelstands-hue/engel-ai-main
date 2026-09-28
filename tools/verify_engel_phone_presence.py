#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json

from engel_phone_presence import build_presence_snapshot, parse_utc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parsed = parse_utc("2026-07-11T08:08:32.4432515Z")
    require(parsed is not None, "seven-digit .NET timestamp did not parse")
    now = datetime(2026, 7, 11, 8, 9, 0, tzinfo=timezone.utc)
    paired = {
        "workers": [
            {
                "worker_id": "android_worker_alpha",
                "paired": True,
                "expected_phone_ip": "192.0.2.78",
                "observed_remote_address": "192.0.2.78",
                "transport": "lan",
            },
            {
                "worker_id": "android_worker_beta",
                "paired": True,
                "expected_phone_ip": "192.0.2.83",
                "observed_remote_address": "127.0.0.1",
                "adb_serial": "ANDROID_WORKER_BETA",
                "adb_reverse_active": True,
                # The prior LAN label may remain in durable pairing state after
                # the phone moves to a verified USB ADB-reverse transport.
                "transport": "lan",
            },
            {
                "worker_id": "android_worker_gamma",
                "paired": True,
                "expected_phone_ip": "198.51.100.236",
                "observed_remote_address": "198.51.100.236",
                "transport": "lan",
            },
        ]
    }
    remote_workers = {}
    for worker_id, address in (
        ("android_worker_alpha", "192.0.2.78"),
        ("android_worker_beta", "127.0.0.1"),
        ("android_worker_gamma", "198.51.100.236"),
    ):
        remote_workers[worker_id] = {
            "identity": {
                "worker_id": worker_id,
                "worker_device": "engel_remote_worker_flutter",
                "remote_address": address,
            },
            "last_seen_utc": "2026-07-11T08:08:32.4432515Z",
            "phone_does_not_control_engel": True,
        }
    snapshot = build_presence_snapshot(
        paired,
        {"workers": {}},
        {"ok": True, "workers": remote_workers, "freshness_seconds": 300},
        now=now,
    )
    require(snapshot.get("live_count") == 3, f"expected 3 live workers: {snapshot}")
    require(snapshot.get("ok") is True, "three-worker snapshot should pass")
    require("android_worker_gamma" in snapshot.get("workers", {}), "Gamma missing from snapshot")
    beta = snapshot.get("workers", {}).get("android_worker_beta", {})
    require(beta.get("live") is True, f"Beta ADB-reverse heartbeat was rejected: {beta}")
    require(beta.get("transport") == "adb_reverse_usb", f"Beta transport was not normalized: {beta}")
    require(beta.get("reported_transport") == "lan", f"Beta reported transport evidence was lost: {beta}")
    require(beta.get("adb_reverse_verified") is True, f"Beta ADB serial was not verified: {beta}")

    wrong_serial = json.loads(json.dumps(paired))
    wrong_serial["workers"][1]["adb_serial"] = "WRONG"
    rejected = build_presence_snapshot(
        wrong_serial,
        {"workers": {}},
        {"ok": True, "workers": remote_workers, "freshness_seconds": 300},
        now=now,
    )
    rejected_beta = rejected.get("workers", {}).get("android_worker_beta", {})
    require(rejected_beta.get("live") is False, "unmatched ADB serial must not authorize Beta")
    require(rejected_beta.get("adb_reverse_verified") is False, "unmatched ADB serial was marked verified")

    alt_remote = {
        "android_worker_alpha": "192.168.7.196",
        "android_worker_beta": "192.168.7.195",
        "android_worker_gamma": "192.168.7.190",
    }
    alt_workers = {
        worker_id: {
            "identity": {
                "worker_id": worker_id,
                "worker_device": "engel_remote_worker_flutter",
                "remote_address": address,
            },
            "last_seen_utc": "2026-07-11T08:08:32.4432515Z",
            "phone_does_not_control_engel": True,
        }
        for worker_id, address in alt_remote.items()
    }
    alt_snapshot = build_presence_snapshot(
        paired,
        {"workers": {}},
        {"ok": True, "workers": alt_workers, "freshness_seconds": 300},
        now=now,
    )
    require(alt_snapshot.get("live_count") == 3, f"WiFi alt IPs should count as live: {alt_snapshot}")
    require(alt_snapshot.get("ok") is True, "WiFi alt-IP snapshot should pass")

    print(json.dumps({"ok": True, "schema": "verify_engel_phone_presence_v1", "live_count": 3}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
