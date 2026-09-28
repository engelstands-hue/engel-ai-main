#!/usr/bin/env python3
"""Verify the server Meeting Room shows only current, real device presence."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import py_compile
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def utc_at(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat().replace("+00:00", "Z")


def fixture_snapshot() -> dict[str, Any]:
    return {
        "ok": True,
        "room": {
            "participants": [
                {
                    "name": "Historical Alpha Station",
                    "type_label": "Historical Alpha Station",
                    "skill_label": "Android Worker Alpha Skill",
                    "status": "Assigned",
                },
                {
                    "name": "Historical Sub Station",
                    "type_label": "Historical Sub Station",
                    "skill_label": "Windows Sub-Engel Worker Skill",
                    "status": "Assigned",
                },
                {
                    "name": "Verification Agent",
                    "type_label": "Verification Agent",
                    "skill_label": "Verification Skill",
                    "status": "Ready",
                },
            ]
        },
        "latest_order": None,
        "participants": [
            {
                "participant_id": "android_worker_alpha",
                "name": "Android Worker Alpha",
                "role": "android-worker",
                "status": "working",
                "raw": {
                    "conical_job_id": "conical-live-alpha",
                    "current_task": "fresh alpha check-in",
                },
            }
        ],
        "windows_sub_engels": [],
        "real_work_proof": {
            "android_returns": {
                "workers": {
                    "android_worker_alpha": {
                        "packet_id": "stale-alpha",
                        "file_mtime_utc": utc_at(timedelta(hours=-3)),
                    },
                    "android_worker_beta": {
                        "packet_id": "current-beta",
                        "configured_phone_model": "Moto G Fast",
                        "file_mtime_utc": utc_at(timedelta(minutes=-2)),
                    },
                }
            },
        },
        "worker_live_claim_return_proof": {
            "ok": True,
            "active_worker_count": 1,
            "workers": {
                "android_worker_alpha": {
                    "active_claim": True,
                    "work_state": "claimed",
                    "work_fresh": True,
                    "claim": {"packet_id": "alpha-live"},
                    "return": {},
                },
                "android_worker_beta": {
                    "active_claim": False,
                    "work_state": "returned",
                    "work_fresh": True,
                    "claim": {},
                    "return": {"packet_id": "current-beta"},
                },
                "android_worker_gamma": {
                    "active_claim": False,
                    "work_state": "idle",
                    "work_fresh": False,
                    "claim": {},
                    "return": {},
                },
                "DESKTOP-UE5A6GG": {
                    "active_claim": False,
                    "work_state": "unreachable",
                    "work_fresh": False,
                    "claim": {},
                    "return": {},
                },
            },
        },
        "sub_engel_training_safe_executor": {"status": "session_expired_requires_pair"},
    }


PHONE_BRIDGE = {
    "ok": True,
    "workers": {
        "android_worker_alpha": {
            "label": "Android Worker Alpha",
            "live": True,
            "transport": "wifi",
            "adb_serial": "ANDROID_WORKER_ALPHA",
            "observed_ip": "192.0.2.78",
        },
        "android_worker_beta": {
            "label": "Android Worker Beta",
            "live": True,
            "transport": "wifi",
            "adb_serial": "ANDROID_WORKER_BETA",
            "observed_ip": "192.0.2.83",
        },
        "android_worker_gamma": {
            "label": "Android Worker Gamma",
            "live": True,
            "transport": "wifi",
            "adb_serial": "ANDROID_WORKER_GAMMA",
            "observed_ip": "198.51.100.236",
        },
    },
}


PHONE_MAP = {
    "android_worker_alpha": {"marketing_name": "Moto G Power (2025)"},
    "android_worker_beta": {"marketing_name": "Moto G Fast"},
    "android_worker_gamma": {"marketing_name": "Samsung Galaxy A14 5G"},
}


def render(module: Any, snapshot: dict[str, Any]) -> dict[str, Any]:
    old_room = module.build_room_snapshot
    old_bridge = module.summarize_phone_bridge_state
    old_map = module.phone_device_map
    try:
        module.build_room_snapshot = lambda _state: deepcopy(snapshot)
        module.summarize_phone_bridge_state = lambda: deepcopy(PHONE_BRIDGE)
        module.phone_device_map = lambda: deepcopy(PHONE_MAP)
        with tempfile.TemporaryDirectory(prefix="engel-live-device-overlay-") as tmp:
            state = module.MeetingRoomServerState(Path(tmp))
            return module.build_virtual_environment_snapshot(state)
    finally:
        module.build_room_snapshot = old_room
        module.summarize_phone_bridge_state = old_bridge
        module.phone_device_map = old_map


def devices_by_role(payload: dict[str, Any], role: str) -> list[dict[str, Any]]:
    return [item for item in payload.get("agents", []) if item.get("role") == role]


def verify_unavailable_sub_and_phone_truth(module: Any) -> None:
    payload = render(module, fixture_snapshot())
    phones = devices_by_role(payload, "android-worker")
    require(len(phones) == 3, f"expected exactly three phone agents, got {len(phones)}")
    by_id = {item["agentId"]: item for item in phones}

    alpha = by_id["android-worker-alpha"]
    beta = by_id["android-worker-beta"]
    gamma = by_id["android-worker-gamma"]
    require(alpha["state"] == "working", "current Alpha check-in was not shown as working")
    require("alpha-live" in alpha["current_task"], "Alpha live claim packet is missing")
    require(beta["state"] == "meeting", "current Beta return proof was not shown as returned")
    require("current-beta" in beta["current_task"], "Beta current return packet is missing")
    require(gamma["state"] == "idle", "live Gamma without current work must be idle")
    require("waiting for a current assignment" in gamma["current_task"], "Gamma idle reason is missing")

    expected_devices = {
        "android-worker-alpha": ("Moto G Power (2025)", "ANDROID_WORKER_ALPHA", "192.0.2.78"),
        "android-worker-beta": ("Moto G Fast", "ANDROID_WORKER_BETA", "192.0.2.83"),
        "android-worker-gamma": ("Samsung Galaxy A14 5G", "ANDROID_WORKER_GAMMA", "198.51.100.236"),
    }
    for agent_id, details in expected_devices.items():
        device = str(by_id[agent_id].get("device") or "")
        for detail in details:
            require(detail in device, f"{agent_id} device identity missing {detail!r}: {device!r}")

    names = {str(item.get("name") or "") for item in payload.get("agents", [])}
    require("Historical Alpha Station" not in names, "stale Android station leaked into live overlay")
    require("Historical Sub Station" not in names, "stale Sub station leaked into live overlay")
    static_verifiers = [
        item
        for item in payload.get("agents", [])
        if item.get("role") == "Verification Skill"
    ]
    require(
        static_verifiers
        and all(item.get("state") == "idle" for item in static_verifiers),
        "a current worker receipt made an unrelated static agent look busy",
    )
    subs = devices_by_role(payload, "windows-sub-engel")
    require(len(subs) == 1, f"unavailable Sub must have one truthful agent, got {len(subs)}")
    require(subs[0]["state"] == "error", "unavailable Sub was not marked error")
    require("no work is assigned" in subs[0]["current_task"], "Sub assignment guard is missing")

    encoded = json.dumps(payload, sort_keys=True).lower()
    require("powervault" not in encoded, "PowerVault appeared in the live environment payload")
    require("/mnt/engel-vault" not in encoded, "retired PowerVault path appeared in the live environment payload")


def verify_live_sub_is_single_reachable_agent(module: Any) -> None:
    snapshot = fixture_snapshot()
    snapshot["windows_sub_engels"] = [
        {
            "participant_id": "DESKTOP-UE5A6GG",
            "name": "Sub-Engel Desktop",
            "address": "http://198.51.100.227:8776",
            "last_seen_utc": utc_at(timedelta(minutes=-1)),
        }
    ]
    snapshot["worker_live_claim_return_proof"]["workers"]["DESKTOP-UE5A6GG"] = {
        "active_claim": False,
        "work_state": "idle",
        "work_fresh": False,
        "claim": {},
        "return": {},
    }
    payload = render(module, snapshot)
    subs = devices_by_role(payload, "windows-sub-engel")
    require(len(subs) == 1, f"live Sub must not be duplicated, got {len(subs)}")
    require(subs[0]["state"] == "idle", "live Sub without current work must be idle")
    require("Paired and reachable" in subs[0]["current_task"], "live Sub reachability is not visible")
    require("198.51.100.227:8776" in subs[0]["device"], "live Sub address is missing")
    require("visible_proof" not in subs[0], "stale visible proof was treated as current")


def main() -> None:
    module_path = ROOT / "tools" / "engel_meeting_room_lan_server.py"
    py_compile.compile(str(module_path), doraise=True)
    source = module_path.read_text(encoding="utf-8")
    real_work_source = source.split(
        "def summarize_real_work_proof",
        1,
    )[1].split("def resolve_worker_return_evidence", 1)[0]
    require(
        "summarize_latest_sub_engel_visible_proof" not in real_work_source
        and '"sub_engel_visible_proof"' not in real_work_source,
        "stale legacy Sub visible-proof report is still exposed as live work",
    )
    from tools import engel_meeting_room_lan_server as module

    verify_unavailable_sub_and_phone_truth(module)
    verify_live_sub_is_single_reachable_agent(module)
    print("ENGEL_MEETING_ROOM_LIVE_DEVICE_OVERLAY_VERIFY_PASS")


if __name__ == "__main__":
    main()
