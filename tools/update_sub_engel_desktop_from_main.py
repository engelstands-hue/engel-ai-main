#!/usr/bin/env python3
"""Update the active Windows Sub-Engel desktop with current Engel Main state.

This is a Main-side registry/update-packet writer. It does not open a new
listener, install software on the remote desktop, expose secrets, or delete
retired node history. The active Sub-Engel node consumes the generated inbox
packet through the existing pair-gated/shared-room routes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = ROOT / "remote_nodes" / "windows_sub_engel"
ACTIVE_NODE_ID = "DESKTOP-UE5A6GG"
RETIRED_NODE_ID = "DESKTOP-" + "FIB17O7"
OFFLINE_CT245_MOUNT = "/mnt/" + "engel-vault"
OFFLINE_CT245_STORAGE_ID = "engel-" + "vault-main"
OFFLINE_CT245_DEVICE = "/dev/" + "sdc"
ACTIVE_SESSION_PATH = REMOTE_ROOT / "session.json"
ACTIVE_NODE_SESSION_PATH = REMOTE_ROOT / "nodes" / ACTIVE_NODE_ID / "session.json"
ACTIVE_CHECKIN_PATH = REMOTE_ROOT / "checkins" / f"{ACTIVE_NODE_ID}.json"
RETIRED_NODE_SESSION_PATH = REMOTE_ROOT / "nodes" / RETIRED_NODE_ID / "session.json"
RETIRED_CHECKIN_PATH = REMOTE_ROOT / "checkins" / f"{RETIRED_NODE_ID}.json"
FLEET_MANIFEST_PATH = REMOTE_ROOT / "fleet_manifest.json"
WORKER_ROOT = ROOT / "remote_workers" / "windows_sub_engel"
WORKER_CONFIG = WORKER_ROOT / "config"
WORKER_INBOX = WORKER_ROOT / "inbox"
MEMORY_PATH = ROOT / "memory" / "SUB_ENGEL_DESKTOP_SERVER_UPDATE_V1.md"
REPORT_DIR = ROOT / "reports" / "sub_engel_remote_control"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def redact_session(payload: dict[str, Any]) -> dict[str, Any]:
    safe = dict(payload)
    safe.pop("session_token", None)
    return safe


def list_without(items: list[Any], blocked: str) -> list[Any]:
    blocked_lower = blocked.lower()
    return [item for item in items if str(item).lower() != blocked_lower]


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


def server_contract(now: str) -> dict[str, Any]:
    return {
        "schema": "engel_sub_engel_server_contract_v1",
        "updated_at_utc": now,
        "controller": "ROG laptop / Engel AI Main UI",
        "server": {
            "proxmox_host": "engel-spine-01",
            "proxmox_lan_ip": "192.0.2.50",
            "engel_ai_main_ct": 246,
            "ct_hostname": "engel-ai-main",
            "ct_internal_ip": "10.246.0.2/24",
            "ssh_from_controller": "ssh root@192.0.2.50 -p 24622",
            "direct_proxmox_ssh": "ssh root@192.0.2.50",
        },
        "chat_routes": {
            "controller_expected_local_service": "http://127.0.0.1:24680",
            "server_chat_bridge": "long-lived Engel Main local model service; no per-message CLI launch",
            "provider_bridges": ["codex", "claude", "grok", "gemini", "local_llm"],
            "failure_rule": "Report unreachable route quickly; do not wait 300 seconds before returning a user-visible failure.",
        },
        "meeting_room": {
            "source": "engel3d_office_main",
            "launcher": "scripts/Start-EngelAgentMeetingRoomOffice.ps1",
            "lan_server": "tools/engel_meeting_room_lan_server.py",
            "visible_room": "Engel AI Main opens the server-owned 3D Agent Meeting Room from the controller UI.",
            "sub_engel_role": "Read assigned work packets, return visible proof/receipts, and never claim work happened before a returned file exists.",
        },
        "computer_control_pipeline": {
            "tool": "tools/engel_computer_control_pipeline.py",
            "launcher": "scripts/Start-EngelComputerControlPipeline.ps1",
            "capture_stack": ["dxcam", "mss", "PIL fallback"],
            "ocr_stack": ["Tesseract if installed", "EasyOCR fallback"],
            "action_layer": ["pyautogui", "Win32 clipboard assisted typing"],
            "full_access_flag": "-FullAccess",
            "default_mode": "observe/report unless explicitly launched with FullAccess",
            "receipt_root": "reports/computer_control_pipeline",
        },
        "storage": {
            "active_runtime": "/opt/engel",
            "active_training": "/opt/engel/training",
            "active_models": "/opt/engel/models-active",
            "archive_training": "/mnt/engel-hdd-vault/training-outputs",
            "archive_storage": "/mnt/engel-hdd-vault",
            "permanently_excluded_storage": [
                OFFLINE_CT245_MOUNT,
                "CT245",
                "engel-vault-share",
                OFFLINE_CT245_STORAGE_ID,
                "offline-ct245-vault",
                OFFLINE_CT245_DEVICE,
                "iSCSI",
            ],
            "active_inference_from_hdd": False,
            "offline_ct245_vault_health_checks_required_now": False,
        },
        "retired_nodes": {
            RETIRED_NODE_ID: "Do not route Engel AI Main work here. It has its own jobs now.",
        },
    }


def update_session(session: dict[str, Any], contract: dict[str, Any], now: str) -> dict[str, Any]:
    updated = dict(session)
    updated["hostname"] = ACTIVE_NODE_ID
    updated["selected_for_engel_main"] = True
    updated["disabled_for_engel_main"] = False
    updated["do_not_use_for_engel_ai_main"] = False
    updated["registered_for_server_ct"] = 246
    updated["agent_meeting_status"] = "registered_live"
    updated["last_main_registry_update_utc"] = now
    updated["controller_name"] = "Engel Main Dell R730xd"
    updated["server_integration"] = contract
    legacy_drive_actions = {
        "shared_room.status",
        "shared_room.process_latest_work_order",
        "shared_room.process_pending_work_orders",
    }
    current_actions = [
        action
        for action in updated.get("allowed_actions", [])
        if action not in legacy_drive_actions
    ]
    updated["allowed_actions"] = list(dict.fromkeys([
        *current_actions,
        "local_llm.status",
        "direct_work.execute",
        "ui.visible_status",
    ]))
    return updated


def retire_session(path: Path, now: str) -> dict[str, Any]:
    session = read_json(path, {}) or {}
    if not isinstance(session, dict):
        session = {}
    session.pop("session_token", None)
    session.update({
        "hostname": RETIRED_NODE_ID,
        "selected_for_engel_main": False,
        "disabled_for_engel_main": True,
        "do_not_use_for_engel_ai_main": True,
        "agent_meeting_status": "retired",
        "retired_at_utc": session.get("retired_at_utc") or now,
        "retired_reason": "Joshua removed this desktop from Engel AI Main worker routing; it has its own jobs now.",
    })
    write_json(path, session)
    return redact_session(session)


def update_fleet(contract: dict[str, Any], now: str) -> dict[str, Any]:
    manifest = read_json(FLEET_MANIFEST_PATH, {}) or {}
    nodes = manifest.get("nodes") if isinstance(manifest.get("nodes"), list) else []
    active_nodes: list[dict[str, Any]] = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("node_id") or raw.get("hostname") or "").strip().lower() == RETIRED_NODE_ID.lower():
            continue
        active_nodes.append(raw)
    if not any(str(node.get("node_id") or "") == ACTIVE_NODE_ID for node in active_nodes):
        active_nodes.append({
            "node_id": ACTIVE_NODE_ID,
            "display_name": "Windows Sub-Engel WiFi 02",
            "hostname": ACTIVE_NODE_ID,
            "last_known_ips": ["198.51.100.227"],
            "connection_plan": "wifi",
            "agent_meeting_status": "registered_live",
            "setup_state": "paired session refreshed from Engel Main server update",
            "bootstrap_profile": "fresh_windows_11",
            "file_structure_profile": "workflows/sub_engel_nodes/windows_sub_engel_file_structure.json",
            "url": "http://198.51.100.227:8776",
            "node_root": "D:\\EngelWindowsSubNode",
            "selected_for_engel_main": True,
            "disabled_for_engel_main": False,
        })
    for node in active_nodes:
        if str(node.get("node_id") or "") == ACTIVE_NODE_ID:
            node["selected_for_engel_main"] = True
            node["disabled_for_engel_main"] = False
            node["registered_for_server_ct"] = 246
            node["server_integration_updated_utc"] = now
            node["server_contract_summary"] = {
                "chat": contract["chat_routes"]["controller_expected_local_service"],
                "active_training": contract["storage"]["active_training"],
                "archive_training": contract["storage"]["archive_training"],
                "storage_policy": "CT246 allowlist only",
            }
    manifest.update({
        "version": "2026-07-02",
        "fleet_name": "Windows Sub-Engel nodes",
        "controller": "Main Engel AI / CT246 server-backed",
        "nodes": active_nodes,
        "last_updated_utc": now,
        "active_node_policy": "Only nodes in nodes[] without disabled_for_engel_main may receive Engel AI Main meeting-room work.",
        "retired_node_policy": "Retired desktop nodes are not listed for Engel AI Main routing and remain blocked by runtime policy.",
        "server_contract": contract,
        "safety": {
            "raw_shell": False,
            "ssh": False,
            "remote_disk_install": False,
            "provider_api_runtime": False,
            "model_runtime": False,
            "background_workers": False,
            "fake_connected_status": False,
            "offline_ct245_vault_use": False,
        },
    })
    write_json(FLEET_MANIFEST_PATH, manifest)
    return manifest


def update_worker_configs(contract: dict[str, Any], now: str) -> dict[str, Any]:
    identity = read_json(WORKER_CONFIG / "worker_identity.json", {}) or {}
    capabilities = read_json(WORKER_CONFIG / "worker_capabilities.json", {}) or {}
    policy = read_json(WORKER_CONFIG / "worker_autonomy_policy.json", {}) or {}

    identity.update({
        "server_backed_engel_main": True,
        "active_controller": "ROG laptop",
        "active_server_ct": 246,
        "active_node_id": ACTIVE_NODE_ID,
        "retired_nodes_not_usable": [RETIRED_NODE_ID],
        "server_contract": contract,
    })
    capabilities["allowed_jobs"] = list(dict.fromkeys([
        *capabilities.get("allowed_jobs", []),
        "server_route_status",
        "meeting_room_status",
        "computer_control_observation",
        "chat_bridge_regression_report",
        "storage_contract_verify",
        "training_receipt_summary",
        "return_visible_proof",
    ]))
    capabilities["server_backed_capabilities"] = {
        "can_report_ct246_status": True,
        "can_report_meeting_room_status": True,
        "can_return_chat_bridge_observations": True,
        "can_verify_storage_allowlist": True,
        "can_return_computer_control_observation_receipts": True,
        "cannot_run_models_directly_from_hdd": True,
        "cannot_use_retired_desktop": RETIRED_NODE_ID,
    }
    policy["server_contract_updated_utc"] = now
    policy["required_storage_boundary"] = contract["storage"]
    policy["blocked_local_actions"] = list(dict.fromkeys([
        *policy.get("blocked_local_actions", []),
        "use any permanently excluded storage",
        "route work to retired desktop nodes",
        "claim work completed without a returned receipt",
        "launch a fresh CLI model process per chat message",
    ]))

    write_json(WORKER_CONFIG / "worker_identity.json", identity)
    write_json(WORKER_CONFIG / "worker_capabilities.json", capabilities)
    write_json(WORKER_CONFIG / "worker_autonomy_policy.json", policy)
    return {"identity": identity, "capabilities": capabilities, "policy": policy}


def write_inbox_packet(contract: dict[str, Any], health_payload: dict[str, Any], now: str) -> Path:
    packet = {
        "schema": "engel_sub_engel_desktop_update_packet_v1",
        "created_at_utc": now,
        "created_by": "Engel AI Main / Codex",
        "target_worker": "windows_sub_engel",
        "target_node_id": ACTIVE_NODE_ID,
        "target_url": "http://198.51.100.227:8776",
        "status": "ready_for_sub_engel_import",
        "job_type": "server_contract_update",
        "user_visible_goal": "Update Sub-Engel desktop to the CT246 server-backed Engel AI Main build and remove retired desktop routing.",
        "instructions": [
            "Use CT246 server-backed Engel AI Main routes for chat/meeting-room context.",
            "Treat /opt/engel/training as active training storage and /mnt/engel-hdd-vault/training-outputs as archive storage.",
            "Use only the CT246 storage allowlist and never discover, probe, mount, or route permanently excluded storage.",
            "Return visible proof or a receipt before claiming work happened.",
            "Do not start raw shell, SSH, disk install, model runtime, provider runtime, or background worker from this packet.",
        ],
        "contract": contract,
        "observed_health": health_payload,
        "requires_return_receipt": True,
        "auto_apply": False,
    }
    WORKER_INBOX.mkdir(parents=True, exist_ok=True)
    path = WORKER_INBOX / f"SERVER_CONTRACT_UPDATE_{file_stamp()}_{ACTIVE_NODE_ID}.json"
    write_json(path, packet)
    latest = WORKER_INBOX / "SERVER_CONTRACT_UPDATE_LATEST.json"
    write_json(latest, packet)
    return path


def write_memory(contract: dict[str, Any], report_path: Path, inbox_path: Path, now: str) -> None:
    lines = [
        "# Sub-Engel Desktop Server Update V1",
        "",
        f"Updated UTC: {now}",
        "",
        "Active Sub-Engel desktop:",
        f"- Node: `{ACTIVE_NODE_ID}`",
        "- URL: `http://198.51.100.227:8776`",
        "- Root: `D:\\EngelWindowsSubNode`",
        "- Role: Windows Sub-Engel node for assigned-job receipts and visible proof.",
        "",
        "Server routes:",
        "- Engel AI Main server: CT `246` / `engel-ai-main` on `engel-spine-01`.",
        "- Controller SSH route: `ssh root@192.0.2.50 -p 24622`.",
        "- Controller local chat service expected by Engel AI Main: `http://127.0.0.1:24680`.",
        "",
        "Storage rules:",
        "- Active runtime and models stay on CT246 SSD under `/opt/engel` and `/opt/engel/models-active`.",
        "- Active training work uses `/opt/engel/training`.",
        "- Archive training output uses Dell PowerEdge HDD ZFS at `/mnt/engel-hdd-vault/training-outputs`.",
        "- Permanently excluded storage must never be discovered, probed, mounted, routed, archived, or used as fallback.",
        "",
        "Retired desktop:",
        f"- `{RETIRED_NODE_ID}` is not selectable for Engel AI Main work. It has its own jobs now.",
        "",
        "Generated artifacts:",
        f"- Update packet: `{inbox_path}`",
        f"- Verifier/report: `{report_path}`",
        "",
        "Contract summary:",
        f"- Provider bridges: `{', '.join(contract['chat_routes']['provider_bridges'])}`",
        "- Computer control pipeline: `tools/engel_computer_control_pipeline.py` via `scripts/Start-EngelComputerControlPipeline.ps1`.",
    ]
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    now = utc_stamp()
    contract = server_contract(now)
    base_session = read_json(ACTIVE_NODE_SESSION_PATH, {}) or read_json(ACTIVE_SESSION_PATH, {}) or {}
    if not isinstance(base_session, dict):
        base_session = {}
    updated_session = update_session(base_session, contract, now)
    write_json(ACTIVE_SESSION_PATH, updated_session)
    write_json(ACTIVE_NODE_SESSION_PATH, updated_session)

    retired = retire_session(RETIRED_NODE_SESSION_PATH, now) if RETIRED_NODE_SESSION_PATH.exists() else {}
    if RETIRED_CHECKIN_PATH.exists():
        retired_checkin = read_json(RETIRED_CHECKIN_PATH, {}) or {}
        if isinstance(retired_checkin, dict):
            retired_checkin["disabled_for_engel_main"] = True
            retired_checkin["agent_meeting_status"] = "retired"
            retired_checkin["retired_reason"] = "Do not use for Engel AI Main routing."
            write_json(RETIRED_CHECKIN_PATH, retired_checkin)

    fleet = update_fleet(contract, now)
    worker_config = update_worker_configs(contract, now)
    health_payload = fetch_health(str(updated_session.get("url") or "http://198.51.100.227:8776"))
    inbox_path = write_inbox_packet(contract, health_payload, now)

    report = {
        "schema": "engel_sub_engel_desktop_update_report_v1",
        "created_at_utc": now,
        "ok": True,
        "active_node_id": ACTIVE_NODE_ID,
        "active_node_url": updated_session.get("url", ""),
        "active_health": health_payload,
        "retired_node_id": RETIRED_NODE_ID,
        "retired_node_state": retired,
        "fleet_node_count": len(fleet.get("nodes", [])) if isinstance(fleet.get("nodes"), list) else 0,
        "worker_allowed_jobs": worker_config["capabilities"].get("allowed_jobs", []),
        "inbox_packet": str(inbox_path),
        "latest_inbox_packet": str(WORKER_INBOX / "SERVER_CONTRACT_UPDATE_LATEST.json"),
        "memory_path": str(MEMORY_PATH),
        "server_contract": contract,
        "session_path": str(ACTIVE_SESSION_PATH),
        "node_session_path": str(ACTIVE_NODE_SESSION_PATH),
        "fleet_manifest_path": str(FLEET_MANIFEST_PATH),
        "secrets_printed": False,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"SUB_ENGEL_DESKTOP_SERVER_UPDATE_{file_stamp()}.json"
    latest_path = REPORT_DIR / "SUB_ENGEL_DESKTOP_SERVER_UPDATE_LATEST.json"
    write_json(report_path, report)
    write_json(latest_path, report)
    write_memory(contract, report_path, inbox_path, now)
    print(json.dumps({
        "ok": True,
        "active_node": ACTIVE_NODE_ID,
        "health_ok": bool(health_payload.get("ok")),
        "inbox_packet": str(inbox_path),
        "latest_report": str(latest_path),
        "retired_node": RETIRED_NODE_ID,
        "retired_selectable": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
