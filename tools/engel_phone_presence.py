#!/usr/bin/env python3
"""Build one truthful Android worker presence snapshot for ROG and CT246."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib import request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REMOTE_URL = os.environ.get(
    "ENGEL_PHONE_PRESENCE_URL",
    "http://192.0.2.40:8765/cluster/status",
)
DEFAULT_FRESHNESS_SECONDS = 300
EXPECTED = {
    "android_worker_alpha": {
        "label": "Android Worker Alpha",
        "expected_ip": "192.0.2.78",
        "accepted_ips": ("192.0.2.78", "192.168.7.196"),
        "adb_serial": "ANDROID_WORKER_ALPHA",
    },
    "android_worker_beta": {
        "label": "Android Worker Beta",
        "expected_ip": "192.0.2.83",
        "accepted_ips": ("192.0.2.83", "192.168.7.195"),
        "adb_serial": "ANDROID_WORKER_BETA",
    },
    "android_worker_gamma": {
        "label": "Android Worker Gamma",
        "expected_ip": "198.51.100.236",
        "accepted_ips": ("198.51.100.236", "192.168.7.190"),
        "adb_serial": "ANDROID_WORKER_GAMMA",
    },
}


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    text = re.sub(
        r"\.(\d{1,9})(?=[+-]\d{2}:\d{2}$|$)",
        lambda match: "." + match.group(1)[:6].ljust(6, "0"),
        text,
    )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _worker_map(value: Any) -> dict[str, dict[str, Any]]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items() if isinstance(item, dict)}
    if isinstance(value, list):
        return {
            str(item.get("worker_id") or ""): item
            for item in value
            if isinstance(item, dict) and item.get("worker_id")
        }
    return {}


def fetch_remote_presence(url: str = DEFAULT_REMOTE_URL, timeout: float = 2.0) -> dict[str, Any]:
    clean = str(url or "").strip()
    if not clean:
        return {"ok": False, "error": "remote presence URL is empty"}
    try:
        req = request.Request(clean, headers={"Accept": "application/json"})
        with request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "remote presence response was not an object"}
    return payload


def build_presence_snapshot(
    paired_state: dict[str, Any],
    local_session: dict[str, Any],
    remote_presence: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    paired_workers = _worker_map(paired_state.get("workers"))
    local_workers = _worker_map(local_session.get("workers"))
    remote_workers = _worker_map(remote_presence.get("workers")) if remote_presence.get("ok") is True else {}
    authoritative_workers = remote_workers or local_workers
    authoritative_source = "rog_remote_presence" if remote_workers else "local_session_state"
    try:
        freshness_seconds = int(
            remote_presence.get("freshness_seconds")
            or paired_state.get("freshness_seconds")
            or DEFAULT_FRESHNESS_SECONDS
        )
    except (TypeError, ValueError):
        freshness_seconds = DEFAULT_FRESHNESS_SECONDS

    workers: dict[str, dict[str, Any]] = {}
    live_count = 0
    for worker_id in sorted(set(EXPECTED) | set(paired_workers) | set(authoritative_workers)):
        expected = EXPECTED.get(worker_id, {})
        paired = paired_workers.get(worker_id, {})
        presence = authoritative_workers.get(worker_id, {})
        identity = presence.get("identity") if isinstance(presence.get("identity"), dict) else {}
        last_seen = str(presence.get("last_seen_utc") or paired.get("last_seen") or paired.get("last_seen_utc") or "")
        seen_at = parse_utc(last_seen)
        age_seconds = None if seen_at is None else round((checked_at - seen_at).total_seconds(), 1)
        expected_ip = str(
            paired.get("expected_phone_ip")
            or paired.get("required_ip")
            or paired.get("phone_ip")
            or expected.get("expected_ip")
            or ""
        )
        observed_ip = str(
            identity.get("remote_address")
            or paired.get("observed_remote_address")
            or paired.get("observed_ip")
            or ""
        )
        accepted_ips = {expected_ip} if expected_ip else set()
        for item in expected.get("accepted_ips") or ():
            text = str(item or "").strip()
            if text:
                accepted_ips.add(text)
        for key in ("accepted_phone_ips", "alt_ips"):
            extra = paired.get(key)
            if isinstance(extra, (list, tuple, set)):
                for item in extra:
                    text = str(item or "").strip()
                    if text:
                        accepted_ips.add(text)
        lan_ok = bool(observed_ip and observed_ip in accepted_ips)
        reported_transport = str(paired.get("transport") or ("lan" if lan_ok else "unknown"))
        adb_serial = str(paired.get("adb_serial") or expected.get("adb_serial") or "")
        adb_reverse_active = paired.get("adb_reverse_active") is True
        expected_adb_serial = str(expected.get("adb_serial") or "")
        adb_reverse_ok = bool(
            observed_ip == "127.0.0.1"
            and adb_reverse_active
            and expected_adb_serial
            and adb_serial == expected_adb_serial
        )
        transport = "adb_reverse_usb" if adb_reverse_ok else reported_transport
        remote_ok = bool(lan_ok or adb_reverse_ok)
        authenticated_presence = bool(
            presence
            and presence.get("phone_does_not_control_engel") is True
            and str(identity.get("worker_id") or worker_id) == worker_id
        )
        paired_ok = bool(paired.get("paired") is True or paired.get("live_phone_connected") is True or authenticated_presence)
        fresh = bool(age_seconds is not None and 0 <= age_seconds <= freshness_seconds)
        live = bool(authenticated_presence and paired_ok and remote_ok and fresh)
        if live:
            live_count += 1
        workers[worker_id] = {
            "worker_id": worker_id,
            "label": str(paired.get("worker_name") or paired.get("label") or expected.get("label") or worker_id),
            "live": live,
            "paired": paired_ok,
            "authenticated_presence": authenticated_presence,
            "required_ip": expected_ip,
            "observed_ip": observed_ip,
            "transport": transport,
            "reported_transport": reported_transport,
            "adb_serial": adb_serial,
            "adb_reverse_active": adb_reverse_active,
            "adb_reverse_verified": adb_reverse_ok,
            "last_seen_utc": last_seen,
            "fresh_seconds": age_seconds,
            "freshness_limit_seconds": freshness_seconds,
            "phone_does_not_control_engel": presence.get("phone_does_not_control_engel") is True,
            "source": authoritative_source,
            "reason": (
                "fresh authenticated phone heartbeat over verified ADB reverse"
                if live and adb_reverse_ok
                else "fresh authenticated phone heartbeat"
                if live
                else "phone heartbeat is missing, stale, unpaired, or from the wrong address"
            ),
        }
    return {
        "schema": "engel_phone_presence_snapshot_v1",
        "ok": live_count == len(EXPECTED),
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "source": authoritative_source,
        "remote_presence_ok": remote_presence.get("ok") is True,
        "remote_presence_error": str(remote_presence.get("error") or ""),
        "freshness_seconds": freshness_seconds,
        "expected_count": len(EXPECTED),
        "live_count": live_count,
        "workers": workers,
    }


def phone_presence_snapshot(
    *,
    root: Path = ROOT,
    remote_url: str = DEFAULT_REMOTE_URL,
    timeout: float = 2.0,
) -> dict[str, Any]:
    paired = _load_json(root / "memory" / "phone_bridge" / "ENGEL_REMOTE_WORKERS_PAIRED.json")
    session = _load_json(root / "remote_workers" / "lan_link_manager" / "session_state.json")
    remote = fetch_remote_presence(remote_url, timeout=timeout)
    snapshot = build_presence_snapshot(paired, session, remote)
    snapshot["paired_state_path"] = str(root / "memory" / "phone_bridge" / "ENGEL_REMOTE_WORKERS_PAIRED.json")
    snapshot["local_session_path"] = str(root / "remote_workers" / "lan_link_manager" / "session_state.json")
    snapshot["remote_presence_url"] = remote_url
    return snapshot
