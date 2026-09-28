#!/usr/bin/env python3
"""Run a live all-device Engel cluster probe.

This creates real review-only Android worker assignments, waits for phone
returns, checks Windows Sub-Engel command reachability, and writes a proof
report. Returned Android content remains untrusted review-only data.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "runtime" / "python310" / "python.exe"
ADB = ROOT / "tools" / "platform-tools" / "adb.exe"
ASSIGNMENT_ROOT = ROOT / "remote_workers" / "communication_queen_assignments"
APPROVED_DIR = ASSIGNMENT_ROOT / "approved"
RETURNED_DIR = ASSIGNMENT_ROOT / "returned"
REPORT_DIR = ROOT / "reports" / "codex_bridge"
WINDOWS_NODES = ["DESKTOP-UE5A6GG"]
ANDROID_WORKERS = ["android_worker_alpha", "android_worker_beta", "android_worker_gamma"]
BLOCKED_ACTIONS = [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
]


def py() -> str:
    return str(PYTHON if PYTHON.is_file() else Path(sys.executable))


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_stamp(value: dt.datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def file_stamp(value: dt.datetime | None = None) -> str:
    return utc_stamp(value).replace("-", "").replace(":", "").replace("Z", "Z")


def safe_id(value: str, limit: int = 96) -> str:
    text = value.lower()[:limit]
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return cleaned.strip("_") or "unknown"


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


def run_json(command: list[str], timeout: int = 45) -> dict[str, Any]:
    proc = run(command, timeout=timeout)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": proc.stdout[-4000:]}
    if not isinstance(payload, dict):
        payload = {"payload": payload}
    payload["return_code"] = proc.returncode
    if proc.stderr.strip():
        payload["stderr"] = proc.stderr.strip()[-4000:]
    return payload


def create_android_assignment(worker_id: str, run_id: str) -> dict[str, Any]:
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    created = utc_now()
    packet_id = f"{file_stamp(created)}_{worker_id}_return_status_device_cluster_live_probe_{run_id}"
    packet = {
        "packet_version": "1",
        "packet_id": packet_id,
        "created_at": utc_stamp(created),
        "created_by": "Engel Communication Router",
        "approved_by": "Engel Core",
        "approval_scope": "remote_worker_assignment_only",
        "assignment_mode": "remote_worker_auto",
        "trust_level": "untrusted_until_reviewed",
        "worker_target": worker_id,
        "task_type": "return_status",
        "title": f"Device cluster live probe for {worker_id}",
        "instructions": (
            "Return a current Android Remote Worker capability/status receipt for the Engel "
            "device cluster live probe. Include device identity and keep the result untrusted, "
            "review-only, and safe_to_auto_apply=false."
        ),
        "source_summary": "Engel controller is proving live Android poll/claim/return behavior.",
        "source_refs": [],
        "risk_flags": [],
        "requires_review": True,
        "safe_to_auto_apply": False,
        "no_direct_control": True,
        "not_trusted_memory": True,
        "blocked_actions": BLOCKED_ACTIONS,
        "allowed_outputs": ["draft_result_json"],
    }
    path = APPROVED_DIR / f"{safe_id(packet_id)}.json"
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"worker_id": worker_id, "packet_id": packet_id, "assignment_path": str(path)}


def returned_results_for(packet_id: str, worker_id: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not RETURNED_DIR.exists():
        return results
    for path in RETURNED_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("packet_id") == packet_id and payload.get("worker_id") == worker_id:
            results.append({"path": str(path), "payload": payload})
    return results


def wait_for_android_returns(assignments: list[dict[str, Any]], timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    pending = {(item["packet_id"], item["worker_id"]) for item in assignments}
    found: dict[str, Any] = {}
    while time.time() < deadline and pending:
        for packet_id, worker_id in list(pending):
            results = returned_results_for(packet_id, worker_id)
            if results:
                found[worker_id] = results[-1]
                pending.remove((packet_id, worker_id))
        if pending:
            time.sleep(2)
    return {
        "ok": not pending,
        "found": found,
        "pending": [{"packet_id": packet_id, "worker_id": worker_id} for packet_id, worker_id in sorted(pending)],
    }


def adb_status() -> dict[str, Any]:
    proc = run([str(ADB), "devices", "-l"], timeout=30)
    lines = [line for line in proc.stdout.splitlines() if "\tdevice" in line or " device " in line]
    return {"return_code": proc.returncode, "device_count": len(lines), "devices": lines, "stderr": proc.stderr.strip()}


def windows_node_status() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for node in WINDOWS_NODES:
        results[node] = run_json(
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
            timeout=45,
        )
    return results


def write_report(summary: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"ENGEL_DEVICE_CLUSTER_LIVE_PROBE_{file_stamp()}.md"
    android_returns = summary["android_returns"]["found"]
    lines = [
        "# Engel Device Cluster Live Probe",
        "",
        f"- timestamp_utc: `{summary['timestamp_utc']}`",
        f"- result: `{'PASS' if summary['ok'] else 'FAIL'}`",
        f"- android_assignments_created: `{len(summary['android_assignments'])}`",
        f"- android_returns_received: `{len(android_returns)}`",
        f"- adb_device_count: `{summary['adb']['device_count']}`",
        f"- link_receiver_running: `{summary['android_link'].get('receiver_running')}`",
        f"- link_receiver_health_ok: `{summary['android_link'].get('receiver_health_ok')}`",
        f"- shared_drive_room_ok: `{summary['shared_drive'].get('ok')}`",
        "",
        "## Android Return Evidence",
    ]
    for worker_id, result in android_returns.items():
        payload = result.get("payload", {})
        lines.extend(
            [
                f"- worker_id: `{worker_id}`",
                f"  packet_id: `{payload.get('packet_id')}`",
                f"  result_type: `{payload.get('result_type')}`",
                f"  returned_path: `{result.get('path')}`",
                f"  safe_to_auto_apply: `{payload.get('safe_to_auto_apply')}`",
            ]
        )
    lines.extend(["", "## Summary JSON", "```json", json.dumps(summary, indent=2, sort_keys=True), "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    run_id = safe_id(file_stamp(), 32)
    assignments = [create_android_assignment(worker_id, run_id) for worker_id in ANDROID_WORKERS]
    android_returns = wait_for_android_returns(assignments, timeout_seconds=180)
    android_link = run_json([py(), str(ROOT / "engel_remote_worker_link_manager.py"), "status"], timeout=45)
    _sr_root = os.environ.get(
        "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
        str(ROOT / "run" / "sub_engel_transport"),
    )
    shared_drive = run_json(
        [py(), str(ROOT / "engel_shared_drive_room.py"), "status", "--root", _sr_root],
        timeout=45,
    )
    summary: dict[str, Any] = {
        "timestamp_utc": utc_stamp(),
        "android_assignments": assignments,
        "android_returns": android_returns,
        "android_link": android_link,
        "adb": adb_status(),
        "windows_nodes": windows_node_status(),
        "shared_drive": shared_drive,
    }
    windows_ok = all(
        bool(item.get("ok")) and isinstance(item.get("result"), dict) and item["result"].get("return_code") == 0
        for item in summary["windows_nodes"].values()
    )
    summary["ok"] = (
        bool(android_returns.get("ok"))
        and bool(android_link.get("receiver_running"))
        and bool(android_link.get("receiver_health_ok"))
        and summary["adb"]["device_count"] >= len(ANDROID_WORKERS)
        and windows_ok
        and bool(shared_drive.get("ok"))
    )
    report = write_report(summary)
    summary["report_path"] = str(report)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
