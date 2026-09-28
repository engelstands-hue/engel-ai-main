#!/usr/bin/env python3
"""Verify the active Windows Sub-Engel desktop uses the current server contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_NODE_ID = "DESKTOP-UE5A6GG"
RETIRED_NODE_ID = "DESKTOP-FIB17O7"
REMOTE_ROOT = ROOT / "remote_nodes" / "windows_sub_engel"
ACTIVE_SESSION_PATH = REMOTE_ROOT / "session.json"
ACTIVE_NODE_SESSION_PATH = REMOTE_ROOT / "nodes" / ACTIVE_NODE_ID / "session.json"
RETIRED_NODE_SESSION_PATH = REMOTE_ROOT / "nodes" / RETIRED_NODE_ID / "session.json"
FLEET_MANIFEST_PATH = REMOTE_ROOT / "fleet_manifest.json"
WORKER_CONFIG = ROOT / "remote_workers" / "windows_sub_engel" / "config"
LATEST_INBOX = ROOT / "remote_workers" / "windows_sub_engel" / "inbox" / "SERVER_CONTRACT_UPDATE_LATEST.json"
MEMORY_PATH = ROOT / "memory" / "SUB_ENGEL_DESKTOP_SERVER_UPDATE_V1.md"
REPORT_LATEST = ROOT / "reports" / "sub_engel_remote_control" / "SUB_ENGEL_DESKTOP_SERVER_UPDATE_LATEST.json"


FORBIDDEN_TEXT = [
    "/mnt/engel-vault\"",
    "engel-vault-main\"",
    "engel-vault-share\"",
]


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def fetch_health(url: str, timeout: float = 3.0) -> dict[str, Any]:
    clean = str(url or "").strip().rstrip("/")
    if not clean:
        return {"ok": False, "error": "missing_url"}
    try:
        req = request.Request(clean + "/health", headers={"Accept": "application/json"})
        with request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {"ok": False, "error": "invalid_json"}
    except error.HTTPError as exc:
        return {"ok": False, "error": f"http_{exc.code}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def has_required_storage(contract: dict[str, Any]) -> bool:
    storage = contract.get("storage") if isinstance(contract.get("storage"), dict) else {}
    return (
        storage.get("active_training") == "/opt/engel/training"
        and storage.get("archive_training") == "/mnt/engel-hdd-vault/training-outputs"
        and "/mnt/engel-vault" in storage.get("permanently_excluded_storage", [])
        and storage.get("active_inference_from_hdd") is False
    )


def main() -> int:
    failures: list[str] = []
    session = read_json(ACTIVE_SESSION_PATH, {}) or {}
    node_session = read_json(ACTIVE_NODE_SESSION_PATH, {}) or {}
    manifest = read_json(FLEET_MANIFEST_PATH, {}) or {}
    worker_caps = read_json(WORKER_CONFIG / "worker_capabilities.json", {}) or {}
    inbox = read_json(LATEST_INBOX, {}) or {}
    report = read_json(REPORT_LATEST, {}) or {}
    retired = read_json(RETIRED_NODE_SESSION_PATH, {}) or {}

    if session.get("hostname") != ACTIVE_NODE_ID:
        failures.append("active session hostname is not DESKTOP-UE5A6GG")
    if node_session.get("hostname") != ACTIVE_NODE_ID:
        failures.append("per-node session hostname is not DESKTOP-UE5A6GG")
    if session.get("disabled_for_engel_main") is True:
        failures.append("active session is disabled")
    if session.get("registered_for_server_ct") != 246:
        failures.append("active session is not registered to CT246")
    contract = session.get("server_integration") if isinstance(session.get("server_integration"), dict) else {}
    if contract.get("server", {}).get("engel_ai_main_ct") != 246:
        failures.append("server contract does not point to CT246")
    if not has_required_storage(contract):
        failures.append("server contract storage boundary is incomplete")
    if contract.get("chat_routes", {}).get("controller_expected_local_service") != "http://127.0.0.1:24680":
        failures.append("chat route is not the expected long-lived local service")

    fleet_nodes = manifest.get("nodes") if isinstance(manifest.get("nodes"), list) else []
    active_ids = [str(node.get("node_id") or node.get("hostname") or "") for node in fleet_nodes if isinstance(node, dict)]
    if RETIRED_NODE_ID in active_ids:
        failures.append("retired DESKTOP-FIB17O7 is still in the active fleet manifest")
    if ACTIVE_NODE_ID not in active_ids:
        failures.append("active DESKTOP-UE5A6GG missing from active fleet manifest")
    if retired and retired.get("disabled_for_engel_main") is not True:
        failures.append("retired DESKTOP-FIB17O7 session is not disabled")

    jobs = worker_caps.get("allowed_jobs") if isinstance(worker_caps.get("allowed_jobs"), list) else []
    for job in ("server_route_status", "meeting_room_status", "computer_control_observation", "storage_contract_verify"):
        if job not in jobs:
            failures.append(f"worker job not allowed: {job}")

    if inbox.get("target_node_id") != ACTIVE_NODE_ID:
        failures.append("latest inbox packet is not targeted at active Sub-Engel")
    if inbox.get("status") != "ready_for_sub_engel_import":
        failures.append("latest inbox packet is not ready_for_sub_engel_import")
    if report.get("ok") is not True:
        failures.append("latest update report is missing or not ok")
    if not MEMORY_PATH.exists():
        failures.append("persistent memory note missing")

    joined = "\n".join([
        json.dumps(session, sort_keys=True),
        json.dumps(manifest, sort_keys=True),
        json.dumps(worker_caps, sort_keys=True),
        json.dumps(inbox, sort_keys=True),
    ]).replace("\\\\", "/")
    for forbidden in FORBIDDEN_TEXT:
        if forbidden in joined and "permanently_excluded_storage" not in joined:
            failures.append(f"forbidden storage appears outside boundary: {forbidden}")

    health = fetch_health(str(session.get("url") or ""))
    if not health.get("ok"):
        failures.append(f"active Sub-Engel health not reachable: {health.get('error')}")
    if health.get("hostname") != ACTIVE_NODE_ID:
        failures.append("active Sub-Engel health returned unexpected hostname")

    result = {
        "ok": not failures,
        "active_node": ACTIVE_NODE_ID,
        "health_ok": bool(health.get("ok")),
        "health_hostname": health.get("hostname", ""),
        "ct246_registered": session.get("registered_for_server_ct") == 246,
        "fleet_nodes": active_ids,
        "retired_node_disabled": retired.get("disabled_for_engel_main") is True if retired else True,
        "latest_inbox": str(LATEST_INBOX),
        "latest_report": str(REPORT_LATEST),
        "failures": failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
