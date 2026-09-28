#!/usr/bin/env python3
"""Local Agent Meeting Room bridge for Engel Sub-Engel nodes.

This module makes node presence legible to the Agent Meeting Room without
starting a controller server, opening inbound ports, running shell commands, or
turning on remote-control behavior. It only reads local pairing/check-in
records and stages meeting packets under Engel App runtime state.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib import error, parse, request


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
REMOTE_NODES_DIR = ROOT / "remote_nodes"
LINUX_NODE_DIR = REMOTE_NODES_DIR / "sub_engel"
WINDOWS_NODE_DIR = REMOTE_NODES_DIR / "windows_sub_engel"
LINUX_SESSION_PATH = LINUX_NODE_DIR / "session.json"
WINDOWS_SESSION_PATH = WINDOWS_NODE_DIR / "session.json"
WINDOWS_FLEET_MANIFEST = WINDOWS_NODE_DIR / "fleet_manifest.json"
WINDOWS_CHECKINS_DIR = WINDOWS_NODE_DIR / "checkins"
MEETING_ROOM_DIR = ROOT / "runtime" / "meeting_room"
MEETING_STAGING_DIR = MEETING_ROOM_DIR / "sub_engel_prompts"
SUB_ENGEL_WORK_ORDERS = "SUB_ENGEL_WORK_ORDERS"
SUB_ENGEL_SENT_WORK = "SUB_ENGEL_SENT_WORK"
SERVER_TRANSPORT_ROOT = Path(
    os.environ.get(
        "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
        str(ROOT / "run" / "sub_engel_transport"),
    )
)

LINUX_LABEL = "Sub-Engel OS Worker"
WINDOWS_LABEL = "Windows Sub-Engel Node"

ALLOWED_MEETING_ACTIONS = [
    "read_local_pairing_state",
    "read_windows_checkin_registry",
    "stage_meeting_packet",
    "show_status_in_meeting_room",
]

BLOCKED_MEETING_ACTIONS = [
    "shell",
    "exec",
    "ssh",
    "reboot",
    "shutdown",
    "disk.partition",
    "disk.format",
    "disk.erase",
    "install.install",
    "provider.start",
    "model.start",
    "background.worker.start",
    "firewall.modify",
    "service.install",
]

SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "credential",
    "api_key",
)

DISABLED_AGENT_MEETING_STATUSES = {
    "not_selectable",
    "not_selectable_external_jobs",
    "reserved_external_jobs",
    "disabled",
    "retired",
}


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _server_transport_order_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _server_transport_paths() -> dict[str, Path]:
    room_dir = SERVER_TRANSPORT_ROOT
    room_dir.mkdir(parents=True, exist_ok=True)
    return {
        "room_dir": room_dir,
        "work_orders": room_dir / SUB_ENGEL_WORK_ORDERS,
        "sent_work": room_dir / SUB_ENGEL_SENT_WORK,
        "bus": room_dir / "engel_server_transport_bus.jsonl",
    }


def _not_expired(expires_at: Any) -> bool:
    raw = str(expires_at or "").strip()
    if not raw:
        return True
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed > datetime.now(timezone.utc)


def _live_windows_node_health(url: str, timeout: float = 2.0) -> dict[str, Any]:
    clean = str(url or "").strip().rstrip("/")
    if not clean:
        return {"ok": False, "error": "missing_url"}
    if "://" not in clean:
        clean = "http://" + clean
    try:
        req = request.Request(clean + "/health", headers={"Accept": "application/json"})
        with request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, dict) else {"ok": False, "error": "invalid_health_payload"}
    except error.HTTPError as exc:
        return {"ok": False, "error": f"http_{exc.code}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _storage_penalty(path: Any) -> int:
    text = str(path or "").replace("/", "\\").lower()
    if not text:
        return 20
    if "\\my drive\\" in text or text.startswith("g:\\my drive\\") or text.startswith("h:\\my drive\\"):
        return 180
    return 0


def _best_node_for_work_order(node_kind: str) -> dict[str, Any]:
    try:
        nodes = windows_node_summaries() if node_kind == "windows_sub_engel" else linux_node_summaries()
    except Exception:
        nodes = []
    best: dict[str, Any] = {}
    best_score = -1_000_000
    for node in nodes:
        if not isinstance(node, dict):
            continue
        candidate = dict(node)
        score = 0
        if candidate.get("paired"):
            score += 40
        if _not_expired(candidate.get("expires_at_utc")):
            score += 40
        else:
            score -= 80
        if candidate.get("url"):
            score += 10
        if candidate.get("last_seen_utc"):
            score += 5
        if node_kind == "windows_sub_engel":
            health = _live_windows_node_health(str(candidate.get("url") or ""))
            live_ok = bool(health.get("ok"))
            candidate["live_health_ok"] = live_ok
            if live_ok:
                score += 200
                candidate["hostname"] = candidate.get("hostname") or health.get("hostname") or ""
                allowed = health.get("allowed_actions") if isinstance(health.get("allowed_actions"), list) else []
                candidate["allowed_actions"] = allowed or candidate.get("allowed_actions", [])
                if "direct_work.execute" in candidate.get("allowed_actions", []):
                    score += 40
                if "local_llm.status" in candidate.get("allowed_actions", []):
                    score += 20
                candidate["node_root"] = health.get("node_root", "")
                candidate["state_dir"] = health.get("state_dir", "")
                score -= _storage_penalty(candidate.get("node_root", ""))
                if candidate.get("node_root") and _storage_penalty(candidate.get("node_root", "")) == 0:
                    score += 90
            else:
                candidate["live_health_error"] = health.get("error", "health_not_ok")
                score -= 120
        candidate["selection_score"] = score
        if score > best_score:
            best_score = score
            best = candidate
    return strip_sensitive(best)


def write_server_transport_work_order_for_node(
    station: dict[str, Any],
    job_type: str,
    prompt: str,
    meeting_packet_path: str = "",
) -> dict[str, Any]:
    """Write a CT246-owned work order for authenticated direct dispatch."""
    paths = _server_transport_paths()
    paths["work_orders"].mkdir(parents=True, exist_ok=True)
    paths["sent_work"].mkdir(parents=True, exist_ok=True)
    node_kind = node_kind_for_station(station)
    selected_node = _best_node_for_work_order(node_kind)
    # (2026-07-12) Pin the order to a specific node ONLY when that node is
    # verifiably alive right now. The old unconditional pin addressed orders to
    # the highest-scoring candidate even when its live health probe FAILED
    # (score -120 but still "best"), and the agent-side identity gate makes
    # every OTHER worker skip a pinned order — so every order written while the
    # dedicated node was offline was dead on arrival (nobody could answer it).
    # Unpinned orders keep the generic windows_sub_engel target, but CT246 still
    # requires an authenticated direct session before dispatch.
    pin_node = bool(selected_node) and (
        node_kind != "windows_sub_engel" or selected_node.get("live_health_ok") is True
    )
    stamp = _server_transport_order_stamp()
    order_id = f"MAIN-MEETING-{stamp}"
    order_path = paths["work_orders"] / f"{order_id}.json"
    order = {
        "schema": "engel_sub_engel_work_order_v1",
        "id": order_id,
        "created_at_utc": utc_stamp(),
        "created_by": "Engel AI Main / Agent Meeting Room",
        "target": node_kind,
        "target_label": WINDOWS_LABEL if node_kind == "windows_sub_engel" else LINUX_LABEL,
        "target_node": strip_sensitive({
            "station_name": station.get("name", ""),
            "agent": station.get("type_label", ""),
            "skill": station.get("skill_label", ""),
            "equipment": station.get("equipment", ""),
            "bridge": station.get("bridge", ""),
        }),
        "selected_node": selected_node if pin_node else {},
        "selected_stable_identity": (
            selected_node.get("node_id")
            or selected_node.get("hostname")
            or selected_node.get("label")
            or ""
        ) if pin_node else "",
        # Observability only — no agent identity gate reads this key.
        "best_candidate_when_written": {} if pin_node else selected_node,
        "lane": "CT246 authenticated direct HTTP",
        "status": "ready_for_direct_dispatch",
        "job_type": str(job_type or "meeting_work"),
        "order_text": str(prompt or "").strip(),
        "transport_root": str(paths["room_dir"]),
        "expected_return_folder": str(paths["sent_work"]),
        "meeting_packet_path": str(meeting_packet_path or ""),
        "proof_required": True,
        "completion_rule": "Main may mark returned only after a real SUB_ENGEL_SENT_WORK result file is present.",
    }
    write_json(order_path, order)
    active_request_path = paths["room_dir"] / "SUB_ENGEL_ACTIVE_WORK_REQUEST.json"
    write_json(active_request_path, {
        "schema": "engel_sub_engel_active_work_request_v1",
        "created_at_utc": utc_stamp(),
        "created_by": "Engel AI Main / Agent Meeting Room",
        "order_id": order_id,
        "work_order_name": order_path.name,
        "work_order_path": str(order_path),
        "expected_return_folder": str(paths["sent_work"]),
        "target": node_kind,
        "selected_node": selected_node,
        "proof_required": True,
    })
    stat = order_path.stat()
    bus_record = {
        "timestamp_utc": utc_stamp(),
        "sender": "Engel AI Main",
        "channel": "SUB_ENGEL_WORK_ORDER",
        "message": f"Main wrote Sub-Engel work order {order_id}",
        "path": str(order_path),
        "bytes": stat.st_size,
    }
    try:
        with paths["bus"].open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(bus_record, sort_keys=True) + "\n")
    except OSError:
        pass
    return {
        "ok": True,
        "id": order_id,
        "path": str(order_path),
        "bytes": stat.st_size,
        "expected_return_folder": str(paths["sent_work"]),
        "transport_root": str(paths["room_dir"]),
        "bus": str(paths["bus"]),
        "target": node_kind,
        "selected_node": selected_node,
        "active_request_path": str(active_request_path),
    }


def write_shared_room_work_order_for_node(
    station: dict[str, Any],
    job_type: str,
    prompt: str,
    meeting_packet_path: str = "",
) -> dict[str, Any]:
    """Compatibility alias; writes only to CT246 server transport."""
    return write_server_transport_work_order_for_node(
        station,
        job_type,
        prompt,
        meeting_packet_path=meeting_packet_path,
    )


def safe_name(value: str, fallback: str = "node") -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or fallback)).strip("._")
    return (safe or fallback)[:90]


def redact(value: str) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    if len(raw) <= 4:
        return "****"
    return "*" * (len(raw) - 4) + raw[-4:]


def url_host(url: str) -> str:
    candidate = str(url or "").strip()
    if candidate and "://" not in candidate:
        candidate = "http://" + candidate
    try:
        return parse.urlparse(candidate).hostname or ""
    except ValueError:
        return ""


def strip_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            low = str(key).lower()
            if any(part in low for part in SENSITIVE_KEY_PARTS):
                continue
            clean[str(key)] = strip_sensitive(item)
        return clean
    if isinstance(value, list):
        return [strip_sensitive(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _latest_json_file(path: Path) -> Path | None:
    try:
        candidates = [p for p in path.glob("*.json") if p.is_file()]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _node_record_disabled(data: dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("disabled_for_engel_main") is True or data.get("do_not_use_for_engel_ai_main") is True:
        return True
    status = str(data.get("agent_meeting_status") or "").strip().lower()
    if status in DISABLED_AGENT_MEETING_STATUSES:
        return True
    node = data.get("node") if isinstance(data.get("node"), dict) else {}
    node_status = str(node.get("agent_meeting_status") or "").strip().lower()
    return node_status in DISABLED_AGENT_MEETING_STATUSES


def _node_identity_values(data: dict[str, Any]) -> set[str]:
    if not isinstance(data, dict):
        return set()
    node = data.get("node") if isinstance(data.get("node"), dict) else {}
    values = {
        data.get("node_id", ""),
        data.get("hostname", ""),
        data.get("computer_name", ""),
        node.get("node_id", ""),
        node.get("hostname", ""),
        node.get("computer_name", ""),
    }
    return {str(value).strip().lower() for value in values if str(value or "").strip()}


def _disabled_windows_node_identities() -> set[str]:
    disabled: set[str] = set()
    for session_path in sorted((WINDOWS_NODE_DIR / "nodes").glob("*/session.json")):
        session = read_json(session_path)
        if _node_record_disabled(session):
            disabled.update(_node_identity_values(session))
    legacy = read_json(WINDOWS_SESSION_PATH)
    if _node_record_disabled(legacy):
        disabled.update(_node_identity_values(legacy))
    return disabled


def _enabled_windows_node_identities() -> set[str]:
    enabled: set[str] = set()
    for session_path in sorted((WINDOWS_NODE_DIR / "nodes").glob("*/session.json")):
        session = read_json(session_path)
        if session and not _node_record_disabled(session) and _not_expired(session.get("expires_at_utc")):
            enabled.update(_node_identity_values(session))
    legacy = read_json(WINDOWS_SESSION_PATH)
    if legacy and not _node_record_disabled(legacy) and _not_expired(legacy.get("expires_at_utc")):
        enabled.update(_node_identity_values(legacy))
    return enabled


def latest_windows_checkin() -> dict[str, Any]:
    disabled_ids = _disabled_windows_node_identities()
    enabled_ids = _enabled_windows_node_identities()
    try:
        candidates = [p for p in WINDOWS_CHECKINS_DIR.glob("*.json") if p.is_file()]
    except OSError:
        candidates = []
    for latest in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        data = read_json(latest)
        identities = _node_identity_values(data)
        if _node_record_disabled(data) or bool(disabled_ids.intersection(identities)):
            continue
        if enabled_ids and not bool(enabled_ids.intersection(identities)):
            continue
        if data:
            data.setdefault("registry_path", str(latest))
            return data
    return {}


def linux_node_summary() -> dict[str, Any]:
    session = read_json(LINUX_SESSION_PATH)
    paired = bool(session)
    return {
        "node_kind": "linux_sub_engel",
        "label": LINUX_LABEL,
        "role": session.get("node_kind") or session.get("role") or "sub_engel_cluster_node",
        "paired": paired,
        "meeting_ready": paired,
        "status": "paired session stored; diagnostics/preview only" if paired else "not paired; diagnostics/preview only",
        "url": session.get("url", ""),
        "last_seen_utc": session.get("paired_at_utc", ""),
        "allowed_actions": session.get("allowed_actions", []),
        "remote_control": "pair-gated diagnostics only; no raw shell or disk install authority",
        "session_path": str(LINUX_SESSION_PATH),
    }


def windows_node_summary() -> dict[str, Any]:
    session = read_json(WINDOWS_SESSION_PATH)
    checkin = latest_windows_checkin()
    active_ids = _node_identity_values(session)
    if checkin and active_ids and not bool(active_ids.intersection(_node_identity_values(checkin))):
        checkin = {}
    node = checkin.get("node", {}) if isinstance(checkin.get("node"), dict) else {}
    network = checkin.get("network", {}) if isinstance(checkin.get("network"), dict) else {}
    paired = bool(session) or bool(node.get("paired"))
    checkin_seen = bool(checkin)
    hostname = node.get("hostname") or node.get("computer_name") or session.get("hostname") or session.get("computer_name") or ""
    node_id = node.get("node_id") or ""
    ips = node.get("ip_addresses") or network.get("ip_addresses") or session.get("last_known_ips") or []
    if paired and checkin_seen:
        status = "paired; latest outbound check-in recorded"
    elif checkin_seen:
        status = "outbound check-in recorded; pairing review required"
    elif paired:
        status = "paired session stored; awaiting outbound check-in"
    else:
        status = "not paired; outbound check-in slot ready"
    if not ips and session.get("url"):
        host = url_host(str(session.get("url") or ""))
        if host:
            ips = [host]
    remote_control = node.get("remote_control_status")
    if not remote_control:
        remote_control = "pair-gated LAN/WiFi diagnostics session stored" if paired else "disabled_by_default"
    return {
        "node_kind": "windows_sub_engel",
        "label": WINDOWS_LABEL,
        "role": node.get("role") or session.get("node_kind") or "windows_sub_engel_node",
        "paired": paired,
        "meeting_ready": paired or checkin_seen,
        "status": status,
        "url": session.get("url", ""),
        "node_id": node_id,
        "hostname": hostname,
        "ips": ips if isinstance(ips, list) else [str(ips)],
        "last_seen_utc": checkin.get("recorded_at_utc") or checkin.get("checkin_utc") or session.get("paired_at_utc", ""),
        "remote_control": remote_control,
        "session_path": str(WINDOWS_SESSION_PATH),
        "checkin_path": str(checkin.get("registry_path", "")),
    }


def _node_id_from_session(data: dict[str, Any]) -> str:
    host = str(data.get("hostname") or data.get("computer_name") or "").strip()
    if not host:
        host = url_host(str(data.get("url") or "")) or "node"
    return safe_name(host, "node")


def _registered_sessions(node_dir: Path, legacy_path: Path) -> list[tuple[str, dict[str, Any]]]:
    """All paired sessions of a kind: per-node registry plus the active/legacy file."""
    out: dict[str, dict[str, Any]] = {}
    reg = node_dir / "nodes"
    if reg.is_dir():
        for child in sorted(reg.iterdir()):
            data = read_json(child / "session.json")
            if data and not _node_record_disabled(data) and _not_expired(data.get("expires_at_utc")):
                out[_node_id_from_session(data)] = data
    legacy = read_json(legacy_path)
    if legacy and not _node_record_disabled(legacy) and _not_expired(legacy.get("expires_at_utc")):
        out.setdefault(_node_id_from_session(legacy), legacy)
    return sorted(out.items())


def _summary_from_session(node_id: str, session: dict[str, Any], label: str, kind_key: str) -> dict[str, Any]:
    invalid = session.get("session_invalid") is True
    paired_flag = session.get("paired")
    auth_probe = session.get("last_auth_probe_ok")
    paired = bool(
        session
        and not invalid
        and paired_flag is not False
        and auth_probe is not False
    )
    ips = session.get("last_known_ips") or []
    if not ips and session.get("url"):
        host = url_host(str(session.get("url") or ""))
        if host:
            ips = [host]
    return {
        "node_kind": kind_key,
        "label": label,
        "node_id": node_id,
        "role": session.get("node_kind") or session.get("role") or kind_key,
        "paired": paired,
        "meeting_ready": paired,
        "status": "paired session stored; diagnostics/preview only" if paired else "not paired; diagnostics/preview only",
        "url": session.get("url", ""),
        "hostname": session.get("hostname") or session.get("computer_name") or "",
        "ips": ips if isinstance(ips, list) else [str(ips)],
        "last_seen_utc": session.get("last_seen_utc") or session.get("paired_at_utc", ""),
        "expires_at_utc": session.get("expires_at_utc", ""),
        "allowed_actions": session.get("allowed_actions", []),
        "live_health_ok": auth_probe if isinstance(auth_probe, bool) else None,
        "last_auth_probe_ok": auth_probe if isinstance(auth_probe, bool) else None,
        "session_invalid": invalid,
        "last_auth_error": session.get("last_auth_error", ""),
        "remote_control": "pair-gated diagnostics only; no raw shell or disk install authority",
    }


def windows_node_summaries() -> list[dict[str, Any]]:
    """Per-node summaries for every paired Windows Sub-Engel node."""
    return [
        _summary_from_session(nid, s, WINDOWS_LABEL, "windows_sub_engel")
        for nid, s in _registered_sessions(WINDOWS_NODE_DIR, WINDOWS_SESSION_PATH)
    ]


def windows_fleet_manifest() -> dict[str, Any]:
    """Operator-maintained target list for Windows Sub-Engel machines."""
    return read_json(WINDOWS_FLEET_MANIFEST)


def windows_fleet_node_summaries() -> list[dict[str, Any]]:
    manifest = windows_fleet_manifest()
    raw_nodes = manifest.get("nodes", [])
    if not isinstance(raw_nodes, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in raw_nodes:
        if not isinstance(raw, dict):
            continue
        node_id = safe_name(
            str(raw.get("node_id") or raw.get("hostname") or raw.get("display_name") or "windows_sub_engel_node"),
            "windows_sub_engel_node",
        )
        ips = raw.get("last_known_ips") or []
        out.append({
            "node_kind": "windows_sub_engel",
            "label": WINDOWS_LABEL,
            "node_id": node_id,
            "display_name": str(raw.get("display_name") or node_id),
            "hostname": str(raw.get("hostname") or ""),
            "ips": ips if isinstance(ips, list) else [str(ips)],
            "paired": str(raw.get("agent_meeting_status") or "").startswith("registered"),
            "meeting_ready": str(raw.get("agent_meeting_status") or "").startswith("registered"),
            "status": str(raw.get("setup_state") or raw.get("agent_meeting_status") or "planned"),
            "agent_meeting_status": str(raw.get("agent_meeting_status") or ""),
            "connection_plan": str(raw.get("connection_plan") or ""),
            "bootstrap_profile": str(raw.get("bootstrap_profile") or ""),
            "file_structure_profile": str(raw.get("file_structure_profile") or ""),
            "operator_confirmed": strip_sensitive(raw.get("operator_confirmed", {})),
        })
    return out


def windows_planned_node_summaries() -> list[dict[str, Any]]:
    registered_ids = {str(n.get("node_id") or "") for n in windows_node_summaries()}
    planned: list[dict[str, Any]] = []
    for node in windows_fleet_node_summaries():
        node_id = str(node.get("node_id") or "")
        if node_id not in registered_ids:
            planned.append(node)
    return planned


def linux_node_summaries() -> list[dict[str, Any]]:
    """Per-node summaries for every paired Linux Sub-Engel OS node."""
    return [
        _summary_from_session(nid, s, LINUX_LABEL, "linux_sub_engel")
        for nid, s in _registered_sessions(LINUX_NODE_DIR, LINUX_SESSION_PATH)
    ]


def meeting_node_statuses() -> dict[str, Any]:
    # Singular keys preserved for backward compatibility (active node); the
    # *_nodes lists enumerate every registered node of each kind.
    return {
        "linux_sub_engel": linux_node_summary(),
        "windows_sub_engel": windows_node_summary(),
        "linux_sub_engel_nodes": linux_node_summaries(),
        "windows_sub_engel_nodes": windows_node_summaries(),
        "windows_sub_engel_fleet_manifest": windows_fleet_manifest(),
        "windows_sub_engel_fleet_nodes": windows_fleet_node_summaries(),
        "windows_sub_engel_planned_nodes": windows_planned_node_summaries(),
        "shared_drive_room": shared_drive_room_status(),
    }


def shared_drive_room_status() -> dict[str, Any]:
    try:
        from engel_shared_drive_room import status as drive_room_status

        return drive_room_status()
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "status": "shared Drive room unavailable",
        }


def render_meeting_node_status() -> str:
    statuses = meeting_node_statuses()
    linux = statuses["linux_sub_engel"]
    windows = statuses["windows_sub_engel"]
    lines = [
        "Agent Meeting Room Sub-Engel nodes",
        f"- {linux['label']}: {linux['status']}",
        f"  url: {linux.get('url') or 'not configured'}",
        f"- {windows['label']}: {windows['status']}",
        f"  node: {windows.get('hostname') or windows.get('node_id') or 'not seen'}",
        f"  ips: {', '.join(windows.get('ips') or []) or 'not seen'}",
    ]
    all_nodes = statuses["linux_sub_engel_nodes"] + statuses["windows_sub_engel_nodes"]
    if all_nodes:
        lines.append(f"Registered nodes ({len(all_nodes)}):")
        for n in all_nodes:
            lines.append(
                f"  - [{n['node_kind']}] {n.get('node_id') or n.get('hostname') or '?'}: "
                f"{n.get('url') or 'no url'} ({'paired' if n['paired'] else 'not paired'})"
            )
    planned_windows = statuses.get("windows_sub_engel_planned_nodes", [])
    if planned_windows:
        lines.append(f"Planned Windows nodes ({len(planned_windows)}):")
        for n in planned_windows:
            lines.append(
                f"  - {n.get('display_name') or n.get('node_id') or '?'}: "
                f"{n.get('agent_meeting_status') or n.get('status') or 'planned'}"
            )
    shared_room = statuses.get("shared_drive_room", {})
    if isinstance(shared_room, dict):
        lines.append("Shared Drive room:")
        lines.append(f"  status: {'ready' if shared_room.get('ok') and shared_room.get('room_exists') else 'not ready'}")
        lines.append(f"  live file: {shared_room.get('live_doc') or 'not configured'}")
        lines.append(f"  messages: {shared_room.get('message_count', 0)}")
    lines.append(
        "Safety: local registry/status only; no listener, shell, SSH, provider/model runtime, or background worker is started here."
    )
    return "\n".join(lines)


def node_kind_for_station(station: dict[str, Any] | str) -> str:
    if isinstance(station, dict):
        text = " ".join([
            str(station.get("equipment", "")),
            str(station.get("bridge", "")),
            str(station.get("skill_label", "")),
        ]).lower()
    else:
        text = str(station or "").lower()
    if "windows" in text or "laptop" in text or "desktop" in text:
        return "windows_sub_engel"
    return "linux_sub_engel"


def stage_meeting_packet_for_node(station: dict[str, Any], job_type: str, prompt: str) -> dict[str, Any]:
    node_kind = node_kind_for_station(station)
    label = WINDOWS_LABEL if node_kind == "windows_sub_engel" else LINUX_LABEL
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    station_name = safe_name(str(station.get("name") or station.get("type_label") or label), fallback=node_kind)
    path = MEETING_STAGING_DIR / node_kind / f"{stamp}_{station_name}.json"
    payload = {
        "created_at_utc": utc_stamp(),
        "node_kind": node_kind,
        "node_label": label,
        "station": strip_sensitive(station),
        "job_type": str(job_type or "meeting_work"),
        "prompt": str(prompt or ""),
        "allowed_meeting_actions": ALLOWED_MEETING_ACTIONS,
        "blocked_meeting_actions": BLOCKED_MEETING_ACTIONS,
        "safety": {
            "remote_runtime_started": False,
            "listener_opened": False,
            "raw_shell_enabled": False,
            "ssh_enabled": False,
            "provider_model_runtime_started": False,
            "background_worker_started": False,
        },
    }
    write_json(path, payload)
    return {
        "ok": True,
        "node_kind": node_kind,
        "node_label": label,
        "path": str(path),
        "status": "meeting packet staged",
    }


def record_windows_sub_node_checkin(payload: dict[str, Any], token_hint: str = "") -> dict[str, Any]:
    safe_payload = strip_sensitive(payload if isinstance(payload, dict) else {})
    node = safe_payload.get("node", {}) if isinstance(safe_payload.get("node"), dict) else {}
    node_id = str(node.get("node_id") or node.get("hostname") or node.get("computer_name") or "windows_sub_engel_node")
    record = {
        "recorded_at_utc": utc_stamp(),
        "checkin_utc": safe_payload.get("checkin_utc", ""),
        "node": node,
        "hardware": safe_payload.get("hardware", {}),
        "network": safe_payload.get("network", {}),
        "token_hint": redact(token_hint),
        "controller_receiver": "future HTTP route should validate token before calling this helper",
    }
    path = WINDOWS_CHECKINS_DIR / f"{safe_name(node_id, 'windows_sub_engel_node')}.json"
    write_json(path, record)
    return {
        "ok": True,
        "node_id": node_id,
        "path": str(path),
        "status": "windows sub-engel check-in recorded for meeting-room registry",
    }


def main() -> int:
    print(render_meeting_node_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
