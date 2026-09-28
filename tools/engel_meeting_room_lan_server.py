#!/usr/bin/env python3
"""Engel Meeting Room LAN server.

One LAN-visible room for Engel AI Main, Android workers, and Sub-Engels.
This server does not replace the existing Meeting Room order logic. It wraps
the current submit/complete APIs and adds a durable participant/event surface
owned by Engel runtime storage. Keep active server state on CT246 fast SSD;
use the Dell server HDD archive only after mount proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PureWindowsPath
import socket
import sys
import threading
import time
from typing import Any
from urllib import error, request
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from tools.engel_phone_presence import parse_utc as parse_presence_utc  # noqa: E402
from tools.engel_phone_presence import phone_presence_snapshot  # noqa: E402
from tools.engel_worker_live_claim_return_proof import (  # noqa: E402
    worker_live_claim_return_snapshot,
)


SERVER_SCHEMA = "engel_meeting_room_lan_server_v1"
DEFAULT_PORT = 8790
DEFAULT_HOST = "0.0.0.0"
DEFAULT_SERVER_ROOT = ROOT / "runtime" / "meeting_room_server"
ROOM_STATE_FILE = ROOT / "runtime" / "meeting_room" / "room_state.json"
ORDER_DIR = ROOT / "runtime" / "meeting_room" / "main_ui_orders"
ANDROID_SESSION_FILE = ROOT / "remote_workers" / "lan_link_manager" / "session_state.json"
PHONE_BRIDGE_STATE_FILE = ROOT / "memory" / "phone_bridge" / "ENGEL_REMOTE_WORKERS_PAIRED.json"
PHONE_DEVICE_MAP_FILE = ROOT / "memory" / "ENGEL_PHONE_DEVICE_MAP_V1.json"
WINDOWS_SUB_ENGEL_NODES_DIR = ROOT / "remote_nodes" / "windows_sub_engel" / "nodes"
REMOTE_ASSIGNMENT_ROOT = ROOT / "remote_workers" / "communication_queen_assignments"
REMOTE_RETURNED_DIR = REMOTE_ASSIGNMENT_ROOT / "returned"
REMOTE_CLAIMED_DIR = REMOTE_ASSIGNMENT_ROOT / "claimed"
CODEX_BRIDGE_REPORT_DIR = ROOT / "reports" / "codex_bridge"
CONICAL_REPORT_DIR = ROOT / "reports" / "conical_jobs"
SUB_ENGEL_TRAINING_SAFE_LATEST = (
    ROOT / "run" / "self_update" / "sub_engel_training_safe_executor" / "latest.json"
)
# Active Sub-Engel transport is server-owned CT246 runtime state.
SUB_ENGEL_TRANSPORT_ROOT = Path(
    os.environ.get(
        "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
        str(ROOT / "run" / "sub_engel_transport"),
    )
)
SERVER_TRANSPORT_BUS = SUB_ENGEL_TRANSPORT_ROOT / "engel_server_transport_bus.jsonl"

DISABLED_AGENT_MEETING_STATUSES = {
    "not_selectable",
    "not_selectable_external_jobs",
    "reserved_external_jobs",
    "disabled",
    "retired",
}


CHAT_SAFE_MEETING_ROOM_DEFAULTS = {
    "ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS": "0",
    "ENGEL_MEETING_ROOM_SUB_RETURN_WAIT_SECONDS": "0",
    "ENGEL_MEETING_ROOM_SUB_PASSIVE_WAIT_SECONDS": "0",
    "ENGEL_MEETING_ROOM_SUB_AUTO_RETURN_ATTEMPTS": "1",
    "ENGEL_MEETING_ROOM_NONBLOCKING_REMOTE_DISPATCH": "1",
}


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def node_record_is_disabled(record: dict[str, Any]) -> bool:
    if record.get("disabled_for_engel_main") is True or record.get("do_not_use_for_engel_ai_main") is True:
        return True
    status = str(record.get("agent_meeting_status") or "").strip().lower()
    return status in DISABLED_AGENT_MEETING_STATUSES


def windows_sub_engel_node_is_disabled(node_id: str) -> bool:
    clean = str(node_id or "").strip()
    if not clean:
        return False
    session = read_json(WINDOWS_SUB_ENGEL_NODES_DIR / clean / "session.json", {})
    return isinstance(session, dict) and node_record_is_disabled(session)


def clip(text: Any, limit: int = 500) -> str:
    value = " ".join(str(text or "").replace("\r", " ").split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def slug(value: Any, fallback: str = "agent") -> str:
    text = str(value or "").strip().lower()
    chars: list[str] = []
    last_dash = False
    for char in text:
        if char.isalnum():
            chars.append(char)
            last_dash = False
        elif not last_dash:
            chars.append("-")
            last_dash = True
    clean = "".join(chars).strip("-")
    return clean or fallback


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def seconds_since_utc(value: Any) -> float | None:
    parsed = parse_utc(value)
    if parsed is None:
        return None
    return (datetime.now(timezone.utc) - parsed).total_seconds()


def fetch_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    clean = str(url or "").strip().rstrip("/")
    if not clean:
        return {"ok": False, "error": "missing_url"}
    if "://" not in clean:
        clean = "http://" + clean
    try:
        req = request.Request(clean, headers={"Accept": "application/json"})
        with request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, dict) else {"ok": False, "error": "invalid_json"}
    except error.HTTPError as exc:
        return {"ok": False, "error": f"http_{exc.code}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def fetch_windows_sub_engel_health(url: str) -> dict[str, Any]:
    clean = str(url or "").strip().rstrip("/")
    if not clean:
        return {"ok": False, "error": "missing_url"}
    if "://" not in clean:
        clean = "http://" + clean
    return fetch_json(clean + "/health", timeout=1.0)


def runtime_windows_sub_engel_url(session: dict[str, Any]) -> str:
    if os.name != "nt" and session.get("ct_relay_url"):
        return str(session.get("ct_relay_url") or "")
    return str(session.get("url") or "")


def is_expired_utc(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed <= datetime.now(timezone.utc)


def bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def apply_chat_safe_meeting_room_defaults() -> None:
    for key, value in CHAT_SAFE_MEETING_ROOM_DEFAULTS.items():
        os.environ.setdefault(key, value)


def resolved_server_root() -> Path:
    configured = os.environ.get("ENGEL_MEETING_ROOM_SERVER_ROOT", "").strip()
    root = Path(configured) if configured else DEFAULT_SERVER_ROOT
    root = root.expanduser().resolve()
    if root.drive.upper() == "C:":
        raise RuntimeError(
            "Refusing to store Engel Meeting Room server state on C:. "
            "Set ENGEL_MEETING_ROOM_SERVER_ROOT to Engel-owned runtime storage such as "
            "/opt/engel/run or the project runtime directory."
        )
    root.mkdir(parents=True, exist_ok=True)
    return root


def path_payload(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "drive": path.drive,
        "c_drive": path.drive.upper() == "C:",
    }


def newest_json_file(directory: Path) -> Path | None:
    try:
        files = [p for p in directory.glob("*.json") if p.is_file()]
    except Exception:
        return None
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


class MeetingRoomServerState:
    def __init__(self, server_root: Path):
        self.server_root = server_root
        self.events_path = server_root / "meeting_room_events.jsonl"
        self.participants_path = server_root / "participants.json"
        self.lock = threading.RLock()
        self.sequence = self._load_last_sequence()
        self._snapshot_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._snapshot_ttl_seconds = 2.0

    def cached_snapshot(self, key: str, builder: Any) -> dict[str, Any]:
        now = time.monotonic()
        hit = self._snapshot_cache.get(key)
        if hit and (now - hit[0]) < self._snapshot_ttl_seconds:
            return hit[1]
        with self.lock:
            hit = self._snapshot_cache.get(key)
            if hit and (time.monotonic() - hit[0]) < self._snapshot_ttl_seconds:
                return hit[1]
            value = builder()
            if isinstance(value, dict):
                self._snapshot_cache[key] = (time.monotonic(), value)
                return value
            return {}

    def invalidate_snapshots(self) -> None:
        with self.lock:
            self._snapshot_cache.clear()

    def _load_last_sequence(self) -> int:
        if not self.events_path.exists():
            return 0
        last = 0
        try:
            with self.events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    try:
                        last = max(last, int(item.get("id", 0)))
                    except Exception:
                        continue
        except Exception:
            return 0
        return last

    def append_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.sequence += 1
            event = {
                "id": self.sequence,
                "schema": "engel_meeting_room_event_v1",
                "event_type": event_type,
                "created_at_utc": iso_now(),
                "payload": payload,
            }
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
            self.invalidate_snapshots()
            return event

    def read_events(self, since: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        events: list[dict[str, Any]] = []
        if not self.events_path.exists():
            return events
        try:
            with self.events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except Exception:
                        continue
                    try:
                        event_id = int(event.get("id", 0))
                    except Exception:
                        event_id = 0
                    if event_id > since:
                        events.append(event)
        except Exception as exc:
            return [
                {
                    "id": 0,
                    "schema": "engel_meeting_room_event_error_v1",
                    "event_type": "events_read_error",
                    "created_at_utc": iso_now(),
                    "payload": {"error": str(exc)},
                }
            ]
        return events[-limit:]

    def checkin(self, payload: dict[str, Any]) -> dict[str, Any]:
        participant_id = str(
            payload.get("participant_id")
            or payload.get("device_id")
            or payload.get("hostname")
            or payload.get("name")
            or ""
        ).strip()
        if not participant_id:
            participant_id = "participant_" + str(int(time.time() * 1000))
        record = {
            "participant_id": participant_id,
            "name": str(payload.get("name") or participant_id),
            "kind": str(payload.get("kind") or payload.get("role") or "participant"),
            "role": str(payload.get("role") or payload.get("kind") or "participant"),
            "status": str(payload.get("status") or "online"),
            "url": str(payload.get("url") or ""),
            "host": str(payload.get("host") or ""),
            "address": str(payload.get("address") or ""),
            "capabilities": payload.get("capabilities") if isinstance(payload.get("capabilities"), list) else [],
            "source": str(payload.get("source") or "lan_server_checkin"),
            "last_seen_utc": iso_now(),
            "raw": payload,
        }
        with self.lock:
            registry = read_json(self.participants_path, {"participants": {}})
            if not isinstance(registry, dict):
                registry = {"participants": {}}
            participants = registry.get("participants")
            if not isinstance(participants, dict):
                participants = {}
            participants[participant_id] = record
            registry.update(
                {
                    "schema": "engel_meeting_room_participant_registry_v1",
                    "updated_at_utc": iso_now(),
                    "server_root": str(self.server_root),
                    "participants": participants,
                }
            )
            write_json(self.participants_path, registry)
            event = self.append_event("participant.checkin", {"participant": record})
        return {"ok": True, "accepted": True, "participant": record, "event": event}

    def registered_participants(self) -> list[dict[str, Any]]:
        registry = read_json(self.participants_path, {"participants": {}})
        participants = registry.get("participants") if isinstance(registry, dict) else {}
        if not isinstance(participants, dict):
            return []
        active: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for item in participants.values():
            if not isinstance(item, dict):
                continue
            if node_record_is_disabled(item):
                continue
            participant_id = str(item.get("participant_id") or item.get("hostname") or item.get("name") or "").strip()
            if windows_sub_engel_node_is_disabled(participant_id):
                continue
            raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
            raw_id = str(raw.get("participant_id") or raw.get("hostname") or raw.get("name") or "").strip()
            if raw_id and windows_sub_engel_node_is_disabled(raw_id):
                continue
            seen_at = parse_presence_utc(item.get("last_seen_utc"))
            if seen_at is None or (now - seen_at).total_seconds() > 300:
                continue
            active.append(item)
        return active


def summarize_room_state() -> dict[str, Any]:
    state = read_json(ROOM_STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}
    participants = state.get("participants")
    messages = state.get("messages")
    if not isinstance(participants, list):
        participants = []
    if not isinstance(messages, list):
        messages = []
    status_counts: dict[str, int] = {}
    bridge_counts: dict[str, int] = {}
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        status = str(participant.get("status") or "unknown")
        bridge = str(participant.get("bridge") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        bridge_counts[bridge] = bridge_counts.get(bridge, 0) + 1
    latest_message = messages[-1] if messages else None
    return {
        "state_path": str(ROOM_STATE_FILE),
        "exists": ROOM_STATE_FILE.exists(),
        "room_name": state.get("room_name", ""),
        "goal": state.get("goal", ""),
        "project": state.get("project", ""),
        "open_task": state.get("open_task", ""),
        "safety_state": "CT246 approved storage roles; no raw shell or destructive remote actions.",
        "participant_count": len(participants),
        "message_count": len(messages),
        "status_counts": status_counts,
        "bridge_counts": bridge_counts,
        "latest_message": latest_message,
        "participants": participants,
    }


def summarize_latest_order() -> dict[str, Any] | None:
    path = newest_json_file(ORDER_DIR)
    if path is None:
        return None
    record = read_json(path, {})
    if not isinstance(record, dict):
        record = {}
    return {
        "path": str(path),
        "last_write_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)),
        "order_id": str(record.get("order_id") or path.stem),
        "source": str(record.get("source") or ""),
        "order_text": str(record.get("order_text") or ""),
        "job_type": str(record.get("job_type") or ""),
        "created_at": str(record.get("created_at") or ""),
        "completed_at": str(record.get("completed_at") or ""),
        "station_labels": record.get("station_labels") if isinstance(record.get("station_labels"), list) else [],
        "station_results": record.get("station_results") if isinstance(record.get("station_results"), list) else [],
        "returned_previews": record.get("returned_previews") if isinstance(record.get("returned_previews"), list) else [],
    }


def summarize_android_workers() -> list[dict[str, Any]]:
    snapshot = phone_presence_snapshot(root=ROOT)
    workers = snapshot.get("workers") if isinstance(snapshot, dict) else {}
    if not isinstance(workers, dict):
        return []
    result = []
    for worker_id, data in workers.items():
        if not isinstance(data, dict) or data.get("live") is not True:
            continue
        result.append(
            {
                "participant_id": str(worker_id),
                "name": str(data.get("label") or worker_id),
                "kind": "android_worker",
                "role": "dedicated_engel_remote_worker",
                "status": "live",
                "address": str(data.get("observed_ip") or ""),
                "worker_device": "engel_remote_worker_flutter",
                "last_seen_utc": str(data.get("last_seen_utc") or ""),
                "safe_to_auto_apply": False,
                "phone_does_not_control_engel": bool(data.get("phone_does_not_control_engel") is True),
                "source": str(data.get("source") or snapshot.get("source") or ""),
            }
        )
    return result


def summarize_windows_sub_engels() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not WINDOWS_SUB_ENGEL_NODES_DIR.exists():
        return result
    for session_path in WINDOWS_SUB_ENGEL_NODES_DIR.glob("*/session.json"):
        data = read_json(session_path, {})
        if not isinstance(data, dict):
            continue
        if node_record_is_disabled(data):
            continue
        url = runtime_windows_sub_engel_url(data)
        health = fetch_windows_sub_engel_health(url) if url else {"ok": False, "error": "missing_url"}
        expires_at = str(data.get("expires_at_utc") or "")
        if is_expired_utc(expires_at):
            continue
        hostname = str(data.get("hostname") or session_path.parent.name)
        if health.get("ok") and health.get("hostname"):
            hostname = str(health.get("hostname"))
        allowed_actions = data.get("allowed_actions") if isinstance(data.get("allowed_actions"), list) else []
        if health.get("ok") and isinstance(health.get("allowed_actions"), list):
            allowed_actions = health["allowed_actions"]
        last_known_ips = data.get("last_known_ips") if isinstance(data.get("last_known_ips"), list) else []
        if health.get("ok") and isinstance(health.get("local_ips"), list):
            last_known_ips = [str(item) for item in health["local_ips"]]
        result.append(
            {
                "participant_id": hostname,
                "name": hostname,
                "kind": str(data.get("node_kind") or "windows_sub_engel_node"),
                "role": str(data.get("role") or "windows_sub_engel_node"),
                "status": "live" if health.get("ok") else "registered",
                "url": url,
                "last_known_ips": last_known_ips,
                "last_seen_utc": iso_now() if health.get("ok") else str(data.get("last_seen_utc") or ""),
                "expires_at_utc": expires_at,
                "allowed_actions": allowed_actions,
                "node_root": str(health.get("node_root") or data.get("node_root") or ""),
                "state_dir": str(health.get("state_dir") or data.get("state_dir") or ""),
                "node_root_on_os_drive": bool(health.get("node_root_on_os_drive") is True)
                if health.get("ok") else bool(data.get("node_root_on_os_drive") is True),
                "state_dir_on_os_drive": bool(health.get("state_dir_on_os_drive") is True)
                if health.get("ok") else bool(data.get("state_dir_on_os_drive") is True),
                "live_health_ok": bool(health.get("ok")),
                "live_health_error": "" if health.get("ok") else str(health.get("error") or ""),
                "source": str(session_path),
            }
        )
    return sorted(result, key=lambda item: item.get("participant_id", ""))


def shared_room_tail(limit: int = 8) -> dict[str, Any]:
    if not SERVER_TRANSPORT_BUS.exists():
        return {
            "exists": False,
            "path": str(SERVER_TRANSPORT_BUS),
            "transport_mode": "ct246_server",
            "events": [],
        }
    lines: list[str] = []
    try:
        with SERVER_TRANSPORT_BUS.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    lines.append(line)
    except Exception as exc:
        return {
            "exists": True,
            "path": str(SERVER_TRANSPORT_BUS),
            "transport_mode": "ct246_server",
            "error": str(exc),
            "events": [],
        }
    events = []
    for raw in reversed(lines):
        try:
            event = json.loads(raw)
        except Exception:
            event = {"raw": clip(raw, 700)}
        sender = str(event.get("sender") or event.get("participant_id") or "") if isinstance(event, dict) else ""
        if sender and windows_sub_engel_node_is_disabled(sender):
            continue
        events.append(event)
        if len(events) >= limit:
            break
    events.reverse()
    return {
        "exists": True,
        "path": str(SERVER_TRANSPORT_BUS),
        "transport_mode": "ct246_server",
        "events": events,
    }


def _json_from_draft_text(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_latest_android_worker_returns(limit: int = 12) -> dict[str, Any]:
    if not REMOTE_RETURNED_DIR.is_dir():
        return {
            "ok": False,
            "returned_dir": str(REMOTE_RETURNED_DIR),
            "workers": {},
            "latest_returns": [],
            "reason": "returned assignment directory is missing",
        }
    files = sorted(
        [path for path in REMOTE_RETURNED_DIR.glob("*.json") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[: max(1, limit)]
    workers: dict[str, dict[str, Any]] = {}
    latest_returns: list[dict[str, Any]] = []
    for path in files:
        payload = read_json(path, {})
        if not isinstance(payload, dict):
            continue
        worker_id = str(payload.get("worker_id") or "")
        if not worker_id.startswith("android_worker_"):
            continue
        draft = _json_from_draft_text(payload.get("draft_text"))
        caps = draft.get("device_capabilities") if isinstance(draft.get("device_capabilities"), dict) else {}
        app = caps.get("app") if isinstance(caps.get("app"), dict) else {}
        android = caps.get("android") if isinstance(caps.get("android"), dict) else {}
        creation = caps.get("creation") if isinstance(caps.get("creation"), dict) else {}
        record = {
            "worker_id": worker_id,
            "packet_id": str(payload.get("packet_id") or ""),
            "file": str(path),
            "file_name": path.name,
            "file_mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
            "result_type": str(payload.get("result_type") or ""),
            "trust_level": str(payload.get("trust_level") or ""),
            "requires_review": payload.get("requires_review") is True,
            "safe_to_auto_apply": payload.get("safe_to_auto_apply") is True,
            "worker_device": str(payload.get("worker_device") or ""),
            "worker_name": str(caps.get("worker_name") or worker_id),
            "configured_phone_model": str(caps.get("configured_phone_model") or ""),
            "android_model": str(android.get("model") or ""),
            "android_release": str(android.get("release") or ""),
            "app_version": str(app.get("version") or ""),
            "app_build_number": str(app.get("build_number") or ""),
            "pdf_generation": creation.get("pdf_generation") is True,
            "png_generation": creation.get("png_generation") is True,
            "pdf_bytes": creation.get("pdf_bytes"),
            "png_bytes": creation.get("png_bytes"),
            "status": str(draft.get("status") or ""),
            "human_review_required": draft.get("human_review_required") is True,
        }
        latest_returns.append(record)
        workers.setdefault(worker_id, record)
    return {
        "ok": True,
        "returned_dir": str(REMOTE_RETURNED_DIR),
        "claimed_dir": str(REMOTE_CLAIMED_DIR),
        "workers": workers,
        "latest_returns": latest_returns,
        "latest_return_count": len(latest_returns),
    }


def summarize_latest_sub_engel_visible_proof() -> dict[str, Any]:
    reports = sorted(
        CODEX_BRIDGE_REPORT_DIR.glob("ENGEL_WINDOWS_SUB_ENGEL_VISIBLE_PROOF_*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not reports:
        return {
            "ok": False,
            "report_dir": str(CODEX_BRIDGE_REPORT_DIR),
            "report_path": None,
            "visible_ok_count": 0,
            "nodes_checked": 0,
            "reason": "no visible proof report found",
        }
    report = reports[0]
    text = report.read_text(encoding="utf-8", errors="replace")
    visible_count = 0
    nodes_checked = 0
    for line in text.splitlines():
        if line.startswith("- Nodes checked:"):
            try:
                nodes_checked = int(line.split("`", 2)[1])
            except Exception:
                nodes_checked = 0
        if line.startswith("- Visible proof OK:"):
            try:
                visible_count = int(line.split("`", 2)[1])
            except Exception:
                visible_count = 0
    connected_nodes = []
    for block in text.split("### ")[1:]:
        heading = block.splitlines()[0].strip()
        if "Visible action OK: `True`" in block:
            connected_nodes.append(heading)
    return {
        "ok": visible_count > 0,
        "report_dir": str(CODEX_BRIDGE_REPORT_DIR),
        "report_path": str(report),
        "file_mtime_utc": datetime.fromtimestamp(report.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        "visible_ok_count": visible_count,
        "nodes_checked": nodes_checked,
        "connected_nodes": connected_nodes,
        "preview": clip(text, 900),
    }


def summarize_real_work_proof() -> dict[str, Any]:
    android_returns = summarize_latest_android_worker_returns()
    conical = summarize_latest_conical_work_proof()
    worker_proof = worker_live_claim_return_snapshot()
    workers = (
        worker_proof.get("workers")
        if isinstance(worker_proof.get("workers"), dict)
        else {}
    )
    live_return_count = sum(
        1
        for row in workers.values()
        if isinstance(row, dict)
        and isinstance(row.get("return"), dict)
        and row["return"].get("present") is True
    )
    conical_proof_count = int(conical.get("returned_worker_count") or 0)
    proof_count = max(live_return_count, conical_proof_count)
    return {
        "ok": proof_count > 0,
        "schema": "engel_real_work_proof_v3",
        "updated_at_utc": iso_now(),
        "proof_count": proof_count,
        "preferred_source": (
            "latest_ct246_conical_job"
            if conical.get("ok") is True
            else "latest_individual_device_receipts"
        ),
        "latest_conical_job": conical,
        "android_returns": android_returns,
        "worker_live_claim_return_proof": worker_proof,
        "truth_contract": "A device counts as working only when it returns a current artifact, heartbeat, or visible proof receipt.",
    }


def resolve_worker_return_evidence(
    worker_id: str,
    return_path: Any,
) -> Path | None:
    raw = str(return_path or "").strip()
    if not raw:
        return None
    direct = Path(raw)
    if direct.is_file():
        try:
            direct.resolve().relative_to(ROOT.resolve())
        except ValueError:
            return None
        return direct.resolve()
    basename = (
        PureWindowsPath(raw).name
        if "\\" in raw or (len(raw) > 2 and raw[1:3] == ":\\")
        else Path(raw).name
    )
    if not basename:
        return None
    roots = (
        [REMOTE_RETURNED_DIR]
        if str(worker_id).startswith("android_worker_")
        else [SUB_ENGEL_TRANSPORT_ROOT / "SUB_ENGEL_SENT_WORK"]
    )
    for evidence_root in roots:
        candidate = evidence_root / basename
        if candidate.is_file():
            return candidate.resolve()
    return None


def summarize_latest_conical_work_proof() -> dict[str, Any]:
    """Prefer the newest exact worker-return job over old standalone demos."""
    candidates = sorted(
        CONICAL_REPORT_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates[:50]:
        payload = read_json(path, {})
        if not isinstance(payload, dict):
            continue
        worker_results = (
            payload.get("worker_results")
            if isinstance(payload.get("worker_results"), list)
            else []
        )
        if not worker_results:
            continue
        workers = []
        for item in worker_results:
            if not isinstance(item, dict):
                continue
            worker_id = str(item.get("worker_id") or "")
            evidence_path = resolve_worker_return_evidence(
                worker_id,
                item.get("return_path"),
            )
            workers.append(
                {
                    "worker_id": worker_id,
                    "role": str(item.get("role") or ""),
                    "task_type": str(item.get("task_type") or ""),
                    "status": str(item.get("status") or ""),
                    "returned": (
                        item.get("returned") is True
                        and evidence_path is not None
                    ),
                    "return_path": str(evidence_path or ""),
                    "return_evidence_present": evidence_path is not None,
                    "contribution_schema": str(
                        item.get("contribution_schema") or ""
                    ),
                    "analysis_engine": str(item.get("analysis_engine") or ""),
                }
            )
        returned = [item for item in workers if item["returned"]]
        if not returned:
            continue
        mtime = datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).isoformat().replace("+00:00", "Z")
        return {
            "ok": True,
            "schema": "engel_latest_conical_work_proof_v1",
            "job_id": str(payload.get("job_id") or path.stem),
            "status": str(
                payload.get("final_status") or payload.get("status") or ""
            ),
            "expected_worker_count": int(
                payload.get("expected_worker_count") or len(workers)
            ),
            "returned_worker_count": len(returned),
            "failed_worker_count": len(
                [item for item in workers if not item["returned"]]
            ),
            "workers": workers,
            "build_verified": payload.get("build_verified") is True,
            "workspace_path": str(payload.get("workspace_path") or ""),
            "package_path": str(payload.get("package_path") or ""),
            "receipt_path": str(path),
            "receipt_mtime_utc": mtime,
            "source": "CT246 conical job receipt",
        }
    return {
        "ok": False,
        "schema": "engel_latest_conical_work_proof_v1",
        "receipt_path": "",
        "returned_worker_count": 0,
        "workers": [],
        "reason": "no conical worker-return receipt found",
    }


def summarize_sub_engel_training_safe_executor() -> dict[str, Any]:
    payload = read_json(SUB_ENGEL_TRAINING_SAFE_LATEST, {})
    if not isinstance(payload, dict) or not payload:
        return {
            "ok": False,
            "schema": "engel_sub_engel_training_safe_executor_summary_v1",
            "status": "no_receipt",
            "receipt_path": str(SUB_ENGEL_TRAINING_SAFE_LATEST),
        }
    return {
        "ok": bool(payload.get("ok")),
        "schema": "engel_sub_engel_training_safe_executor_summary_v1",
        "status": str(payload.get("status") or "unknown"),
        "task_id": str(payload.get("task_id") or ""),
        "node_id": str(payload.get("node_id") or ""),
        "created_at_utc": str(payload.get("created_at_utc") or ""),
        "training_active": payload.get("training_active"),
        "training_processes_unchanged": payload.get("training_processes_unchanged"),
        "mutation_performed": bool(payload.get("mutation_performed")),
        "process_control_used": bool(payload.get("process_control_used")),
        "receipt_path": str(SUB_ENGEL_TRAINING_SAFE_LATEST),
    }


def build_room_snapshot(state: MeetingRoomServerState) -> dict[str, Any]:
    registered = state.registered_participants()
    android = summarize_android_workers()
    sub_engels = summarize_windows_sub_engels()
    room = summarize_room_state()
    real_work = summarize_real_work_proof()
    worker_proof = (
        real_work.get("worker_live_claim_return_proof")
        if isinstance(
            real_work.get("worker_live_claim_return_proof"),
            dict,
        )
        else worker_live_claim_return_snapshot()
    )
    participants = registered + android + sub_engels
    return {
        "ok": True,
        "schema": "engel_meeting_room_lan_snapshot_v1",
        "updated_at_utc": iso_now(),
        "server": {
            "schema": SERVER_SCHEMA,
            "host": socket.gethostname(),
            "server_root": str(state.server_root),
            "app_root": str(ROOT),
            "storage_policy": (
                "Active room state stays under /opt/engel on CT246 fast SSD; "
                "archive data may use /mnt/engel-hdd-vault only after mount proof."
            ),
            "sub_engel_transport": "ct246_authenticated_direct_http",
        },
        "paths": {
            "app_root": path_payload(ROOT),
            "server_root": path_payload(state.server_root),
            "room_state": path_payload(ROOM_STATE_FILE),
            "order_dir": path_payload(ORDER_DIR),
            "android_session": path_payload(ANDROID_SESSION_FILE),
            "windows_sub_engel_nodes": path_payload(WINDOWS_SUB_ENGEL_NODES_DIR),
        },
        "room": room,
        "latest_order": summarize_latest_order(),
        "participants": participants,
        "participant_counts": {
            "registered_checkins": len(registered),
            "android_workers": len(android),
            "windows_sub_engels": len(sub_engels),
            "total_visible": len(participants),
        },
        "android_workers": android,
        "windows_sub_engels": sub_engels,
        "shared_room_tail": shared_room_tail(),
        "real_work_proof": real_work,
        "worker_live_claim_return_proof": worker_proof,
        "sub_engel_training_safe_executor": summarize_sub_engel_training_safe_executor(),
    }


def summarize_phone_bridge_state() -> dict[str, Any]:
    return phone_presence_snapshot(root=ROOT)


def phone_device_map() -> dict[str, dict[str, Any]]:
    payload = read_json(PHONE_DEVICE_MAP_FILE, {})
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(payload, dict):
        return result
    for item in payload.get("phones", []):
        if not isinstance(item, dict):
            continue
        worker_id = str(item.get("assigned_worker_id") or "").strip()
        if worker_id:
            result[worker_id] = item
    return result


def resolve_virtual_state_from_room_status(status: Any, recent_work: bool) -> str:
    normalized = str(status or "").strip().lower()
    if "error" in normalized or "failed" in normalized or "unreachable" in normalized:
        return "error"
    if "review" in normalized or "meeting" in normalized or "verif" in normalized:
        return "meeting"
    if recent_work and any(term in normalized for term in ("assigned", "running", "working", "seen", "live", "online")):
        return "working"
    return "idle"


def build_virtual_environment_snapshot(state: MeetingRoomServerState) -> dict[str, Any]:
    room_snapshot = state.cached_snapshot("room", lambda: build_room_snapshot(state))
    real_work_proof = room_snapshot.get("real_work_proof") if isinstance(room_snapshot.get("real_work_proof"), dict) else summarize_real_work_proof()
    worker_live_proof = (
        room_snapshot.get("worker_live_claim_return_proof")
        if isinstance(
            room_snapshot.get("worker_live_claim_return_proof"),
            dict,
        )
        else worker_live_claim_return_snapshot()
    )
    worker_live_rows = (
        worker_live_proof.get("workers")
        if isinstance(worker_live_proof.get("workers"), dict)
        else {}
    )
    android_return_proofs = {}
    android_returns = real_work_proof.get("android_returns") if isinstance(real_work_proof.get("android_returns"), dict) else {}
    if isinstance(android_returns.get("workers"), dict):
        android_return_proofs = android_returns["workers"]
    latest_order = room_snapshot.get("latest_order") if isinstance(room_snapshot.get("latest_order"), dict) else None
    latest_order_seconds = seconds_since_utc(latest_order.get("last_write_utc")) if latest_order else None
    recent_order = bool(
        latest_order_seconds is not None
        and 0 <= latest_order_seconds <= 45 * 60
        and not str(latest_order.get("completed_at") or "").strip()
    )
    recent_events = state.read_events(since=0, limit=80)
    recent_work = bool(
        recent_order
        or int(worker_live_proof.get("active_worker_count") or 0) > 0
    )
    task_text = "Waiting for a current Engel request."
    if latest_order and recent_order:
        task_text = clip(latest_order.get("order_text") or latest_order.get("order_id") or task_text, 220)

    agents: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def add_agent(agent_id: str, name: str, state_value: str, role: str, current_task: str, **extra: Any) -> None:
        clean_id = slug(agent_id, "agent")
        if clean_id in seen_ids:
            suffix = 2
            while f"{clean_id}-{suffix}" in seen_ids:
                suffix += 1
            clean_id = f"{clean_id}-{suffix}"
        seen_ids.add(clean_id)
        updated_at = extra.pop("updated_at_utc", None) or iso_now()
        agents.append(
            {
                "agentId": clean_id,
                "id": clean_id,
                "name": name,
                "state": state_value if state_value in {"idle", "working", "meeting", "error"} else "idle",
                "status": state_value,
                "role": role,
                "current_task": current_task,
                "currentTask": current_task,
                "preferredDeskId": f"desk-{clean_id}",
                "updated_at_utc": updated_at,
                "server_owned": True,
                "runtime_host": socket.gethostname(),
                "runtime_path": str(ROOT),
                "runtime_storage": "engel-fast-ssd",
                **extra,
            }
        )

    add_agent(
        "engel-main-controller",
        "Engel Main Controller",
        "working" if recent_work else "idle",
        "orchestrator",
        task_text,
        device="CT 246 engel-ai-main",
    )
    add_agent(
        "meeting-room-router",
        "Meeting Room Router",
        "working" if recent_work else "idle",
        "server-router",
        "Routing work orders through the CT Agent Meeting Room.",
        device="engel-agent-meeting-room.service",
    )

    room = room_snapshot.get("room") if isinstance(room_snapshot.get("room"), dict) else {}
    room_participants = room.get("participants") if isinstance(room.get("participants"), list) else []
    live_device_skills = {
        "Android Worker Skill",
        "Android Worker Alpha Skill",
        "Android Worker Beta Skill",
        "Android Worker Gamma Skill",
        "Sub-Engel Worker Skill",
        "Windows Sub-Engel Worker Skill",
    }
    for index, participant in enumerate(room_participants):
        if not isinstance(participant, dict):
            continue
        name = str(participant.get("name") or participant.get("type_label") or f"Room Agent {index + 1}")
        role = str(participant.get("skill_label") or participant.get("role") or participant.get("kind") or "agent")
        if role in live_device_skills:
            continue
        status = participant.get("status")
        add_agent(
            participant.get("type_label") or name,
            name,
            resolve_virtual_state_from_room_status(status, recent_order),
            role,
            task_text if recent_order else f"Ready in {role}.",
            bridge=str(participant.get("bridge") or ""),
            equipment=str(participant.get("equipment") or ""),
            room_status=str(status or ""),
        )

    conical_checkins: dict[str, dict[str, Any]] = {}
    visible_participants = (
        room_snapshot.get("participants")
        if isinstance(room_snapshot.get("participants"), list)
        else []
    )
    for participant in visible_participants:
        if not isinstance(participant, dict):
            continue
        raw = participant.get("raw") if isinstance(participant.get("raw"), dict) else {}
        if not str(raw.get("conical_job_id") or "").strip():
            continue
        participant_id = str(participant.get("participant_id") or "").strip()
        if participant_id:
            conical_checkins[participant_id] = participant

    phone_bridge = summarize_phone_bridge_state()
    phone_workers = phone_bridge.get("workers") if isinstance(phone_bridge.get("workers"), dict) else {}
    phone_devices = phone_device_map()
    for worker_id, worker in phone_workers.items():
        if not isinstance(worker, dict):
            continue
        live = worker.get("live") is True
        live_work = (
            worker_live_rows.get(worker_id)
            if isinstance(worker_live_rows.get(worker_id), dict)
            else {}
        )
        proof = android_return_proofs.get(worker_id) if isinstance(android_return_proofs.get(worker_id), dict) else None
        checkin = conical_checkins.get(str(worker_id))
        label = str(worker.get("label") or worker_id)
        transport = str(worker.get("transport") or "unknown")
        proof_age = seconds_since_utc(proof.get("file_mtime_utc")) if proof else None
        proof_recent = bool(proof and proof_age is not None and 0 <= proof_age <= 45 * 60)
        if live_work.get("active_claim") is True:
            worker_task = (
                "Claimed current work packet "
                f"{clip(live_work.get('claim', {}).get('packet_id'), 100)}."
            )
            worker_state = "working"
        elif (
            live_work.get("work_state") == "returned"
            and live_work.get("work_fresh") is True
        ):
            worker_task = (
                "Returned current work proof "
                f"{clip(live_work.get('return', {}).get('packet_id'), 100)}."
            )
            worker_state = "meeting"
        elif checkin:
            raw = checkin.get("raw") if isinstance(checkin.get("raw"), dict) else {}
            worker_task = (
                f"Conical job {raw.get('conical_job_id')}: "
                f"{clip(raw.get('current_task') or raw.get('result_detail') or 'bounded worker task', 260)}"
            )
            worker_state = resolve_virtual_state_from_room_status(checkin.get("status"), True)
        elif proof_recent:
            worker_task = (
                "Returned real proof: "
                f"{proof.get('configured_phone_model') or proof.get('android_model') or label}; "
                f"packet {clip(proof.get('packet_id'), 90)}; "
                f"PDF={bool(proof.get('pdf_generation'))} PNG={bool(proof.get('png_generation'))}."
            )
            worker_state = "working"
        else:
            last_return = str((proof or {}).get("file_mtime_utc") or "")
            worker_task = f"Live phone bridge over {transport}; waiting for a current assignment."
            if last_return:
                worker_task += f" Last verified return: {last_return}."
            if not live:
                worker_task = "Phone worker is not live."
            worker_state = "idle" if live else "error"
        device_record = phone_devices.get(str(worker_id), {})
        device_name = str(device_record.get("marketing_name") or device_record.get("model") or "Android phone")
        device_serial = str(worker.get("adb_serial") or device_record.get("adb_serial") or "")
        device_address = str(worker.get("observed_ip") or worker.get("required_ip") or "")
        device_bits = [device_name]
        if device_serial:
            device_bits.append(device_serial)
        if device_address:
            device_bits.append(device_address)
        add_agent(
            worker_id,
            label,
            worker_state,
            "android-worker",
            worker_task,
            device=" / ".join(device_bits),
            transport=transport,
            observed_ip=str(worker.get("observed_ip") or ""),
            required_ip=str(worker.get("required_ip") or ""),
            adb_serial=worker.get("adb_serial"),
            last_seen_utc=str(worker.get("last_seen_utc") or ""),
            connection_reason=str(worker.get("reason") or ""),
            returned_proof=proof or {},
            live_claim_return=live_work,
            conical_job=(checkin.get("raw") if isinstance(checkin, dict) else {}) or {},
        )

    sub_live_work = (
        worker_live_rows.get("DESKTOP-UE5A6GG")
        if isinstance(worker_live_rows.get("DESKTOP-UE5A6GG"), dict)
        else {}
    )
    live_sub_engels = room_snapshot.get("windows_sub_engels") if isinstance(room_snapshot.get("windows_sub_engels"), list) else []
    if live_sub_engels:
        for sub in live_sub_engels:
            if not isinstance(sub, dict):
                continue
            node_id = str(sub.get("participant_id") or sub.get("name") or "windows-sub-engel")
            sub_checkin = conical_checkins.get(node_id)
            if sub_live_work.get("active_claim") is True:
                raw = {}
                sub_state = "working"
                sub_task = (
                    "Claimed current work order "
                    f"{clip(sub_live_work.get('claim', {}).get('packet_id'), 100)}."
                )
            elif (
                sub_live_work.get("work_state") == "returned"
                and sub_live_work.get("work_fresh") is True
            ):
                raw = {}
                sub_state = "meeting"
                sub_task = (
                    "Returned current work proof "
                    f"{clip(sub_live_work.get('return', {}).get('packet_id'), 100)}."
                )
            elif sub_checkin:
                raw = sub_checkin.get("raw") if isinstance(sub_checkin.get("raw"), dict) else {}
                sub_state = resolve_virtual_state_from_room_status(sub_checkin.get("status"), True)
                sub_task = (
                    f"Conical job {raw.get('conical_job_id')}: "
                    f"{clip(raw.get('current_task') or raw.get('result_detail') or 'bounded worker task', 260)}"
                )
            else:
                raw = {}
                sub_state = "idle"
                sub_task = "Paired and reachable; waiting for a current bounded assignment."
            add_agent(
                node_id,
                str(sub.get("name") or node_id),
                sub_state,
                "windows-sub-engel",
                sub_task,
                device=str(sub.get("address") or sub.get("url") or "Windows Sub-Engel"),
                last_seen_utc=str(sub.get("last_seen_utc") or ""),
                conical_job=raw,
                live_claim_return=sub_live_work,
            )
    else:
        executor_summary = room_snapshot.get("sub_engel_training_safe_executor") if isinstance(room_snapshot.get("sub_engel_training_safe_executor"), dict) else {}
        add_agent(
            "windows-sub-engel",
            "Windows Sub-Engel (DESKTOP-UE5A6GG)",
            "error",
            "windows-sub-engel",
            "Pairing expired or node update pending; no work is assigned until authenticated live proof succeeds.",
            device="DESKTOP-UE5A6GG / 198.51.100.227",
            training_safe_executor_status=str(executor_summary.get("status") or "no_receipt"),
        )

    live_sub_ids = {
        str(sub.get("participant_id") or sub.get("name") or "").strip()
        for sub in live_sub_engels
        if isinstance(sub, dict)
    }
    for participant_id, checkin in conical_checkins.items():
        if participant_id in phone_workers:
            continue
        checkin_role = str(checkin.get("role") or "").lower()
        participant_key = participant_id.lower()
        if (
            participant_id in live_sub_ids
            or "desktop-" in participant_key
            or "sub-engel" in participant_key
            or "sub_engel" in participant_key
            or "sub-engel" in checkin_role
        ):
            continue
        raw = checkin.get("raw") if isinstance(checkin.get("raw"), dict) else {}
        add_agent(
            participant_id,
            str(checkin.get("name") or participant_id),
            resolve_virtual_state_from_room_status(checkin.get("status"), True),
            str(checkin.get("role") or "conical-worker"),
            (
                f"Conical job {raw.get('conical_job_id')}: "
                f"{clip(raw.get('current_task') or raw.get('result_detail') or 'bounded worker task', 260)}"
            ),
            device="Windows Sub-Engel" if "DESKTOP-" in participant_id.upper() else "Engel worker",
            conical_job=raw,
        )

    counts = {"working": 0, "idle": 0, "meeting": 0, "error": 0}
    for agent in agents:
        counts[str(agent.get("state") or "idle")] = counts.get(str(agent.get("state") or "idle"), 0) + 1

    return {
        "ok": True,
        "schema": "engel_server_virtual_environment_state_v1",
        "environment_id": "engel3d-office",
        "workspaceId": "engel3d-office",
        "name": "Engel AI Main Server Agent Meeting Room",
        "timestamp": iso_now(),
        "updated_at_utc": iso_now(),
        "authority": "engel-ai-main CT 246",
        "server_owned": True,
        "viewer_policy": "ROG browser is a viewer/controller; CT 246 owns virtual environment state and work routing.",
        "runtime_storage": {
            "active_runtime_path": str(ROOT),
            "active_runtime_storage": "engel-fast-ssd",
            "archive_used_for_active_runtime": False,
            "archive_policy": "/mnt/engel-hdd-vault is archive-only and requires mount proof.",
        },
        "latest_order": latest_order,
        "recent_work": recent_work,
        "status_counts": counts,
        "agent_count": len(agents),
        "agents": agents,
        "phone_bridge": phone_bridge,
        "worker_live_claim_return_proof": worker_live_proof,
        "real_work_proof": real_work_proof,
        "meeting_room": room_snapshot,
        "events": recent_events[-20:],
    }


def build_virtual_office_presence_snapshot(state: MeetingRoomServerState) -> dict[str, Any]:
    virtual = build_virtual_environment_snapshot(state)
    agents = []
    for agent in virtual.get("agents", []):
        if not isinstance(agent, dict):
            continue
        agents.append(
            {
                "agentId": str(agent.get("agentId") or agent.get("id") or ""),
                "name": str(agent.get("name") or agent.get("agentId") or "Agent"),
                "state": str(agent.get("state") or "idle"),
                "preferredDeskId": str(agent.get("preferredDeskId") or ""),
            }
        )
    return {
        "workspaceId": "engel3d-office",
        "timestamp": str(virtual.get("updated_at_utc") or iso_now()),
        "agents": agents,
        "server_owned": True,
        "runtime_storage": virtual.get("runtime_storage"),
        "status_counts": virtual.get("status_counts"),
    }


def submit_order(order_text: str, source: str, state: MeetingRoomServerState) -> dict[str, Any]:
    from engel_agent_meeting_room import submit_order_from_engel_main_ui

    result = submit_order_from_engel_main_ui(order_text, source=source)
    if not result.get("accepted"):
        effective = "Run Engel UI chat work order through Agent Meeting Room: " + order_text
        result = submit_order_from_engel_main_ui(effective, source=source)
        result["effective_order_text"] = effective
    event = state.append_event(
        "order.submit",
        {
            "source": source,
            "accepted": bool(result.get("accepted") is True),
            "order_id": str(result.get("order_id") or ""),
            "order_text_preview": clip(order_text, 900),
        },
    )
    result = dict(result)
    result.update(
        {
            "ok": bool(result.get("accepted") is True),
            "meeting_room_server_used": True,
            "meeting_room_server_schema": SERVER_SCHEMA,
            "meeting_room_server_event": event,
            "server_enabled": True,
        }
    )
    return result


def complete_order(order_id: str, reply: str, source: str, state: MeetingRoomServerState) -> dict[str, Any]:
    from engel_agent_meeting_room import complete_order_from_engel_main_ui

    result = complete_order_from_engel_main_ui(order_id, reply, source=source)
    event = state.append_event(
        "order.complete",
        {
            "source": source,
            "accepted": bool(result.get("accepted") is True),
            "order_id": order_id,
            "reply_preview": clip(reply, 900),
        },
    )
    result = dict(result)
    result.update(
        {
            "ok": bool(result.get("accepted") is True),
            "meeting_room_server_used": True,
            "meeting_room_server_schema": SERVER_SCHEMA,
            "meeting_room_server_event": event,
            "server_enabled": True,
        }
    )
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "EngelMeetingRoomLAN/1.0"

    @property
    def state(self) -> MeetingRoomServerState:
        return self.server.meeting_room_state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        message = fmt % args
        self.state.append_event(
            "http.access",
            {"client": self.client_address[0], "request": self.requestline, "message": message},
        )

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(min(length, 2 * 1024 * 1024))
        if not raw:
            return {}
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json({"ok": True, "schema": SERVER_SCHEMA})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path in {"/", "/health", "/api/health"}:
                self._send_json(
                    {
                        "ok": True,
                        "schema": SERVER_SCHEMA,
                        "status": "running",
                        "updated_at_utc": iso_now(),
                        "server_root": str(self.state.server_root),
                        "app_root": str(ROOT),
                        "c_drive_used": False,
                        "archive_path": "/mnt/engel-hdd-vault",
                        "archive_mounted": Path("/mnt/engel-hdd-vault").is_mount(),
                        "storage_policy": (
                            "Use CT fast SSD /opt/engel for active runtime, "
                            "room state, training reports, and virtual environment services. "
                            "Use /mnt/engel-hdd-vault for archive data only after mount proof. "
                            "ROG workspace stays controller/viewer."
                        ),
                        "sub_engel_transport": "ct246_authenticated_direct_http",
                        "chat_safe_meeting_room_defaults": CHAT_SAFE_MEETING_ROOM_DEFAULTS,
                        "endpoints": [
                            "GET /health",
                            "GET /api/health",
                            "GET /room/state",
                            "GET /room/worker-proof",
                            "GET /room/participants",
                            "GET /room/events?since=0&limit=100",
                            "GET /room/orders/latest",
                            "GET /virtual-environments",
                            "GET /virtual-environments/engel3d-office/state",
                            "GET /virtual-environments/engel3d-office/presence",
                            "GET /virtual-environments/engel3d-office/events?since=0&limit=100",
                            "POST /room/checkin",
                            "POST /room/order",
                            "POST /room/complete",
                            "POST /room/chat",
                            "POST /virtual-environments/engel3d-office/task",
                        ],
                    }
                )
                return
            if parsed.path == "/room/state":
                self._send_json(self.state.cached_snapshot("room", lambda: build_room_snapshot(self.state)))
                return
            if parsed.path == "/room/worker-proof":
                self._send_json(worker_live_claim_return_snapshot())
                return
            if parsed.path == "/room/participants":
                snapshot = build_room_snapshot(self.state)
                self._send_json(
                    {
                        "ok": True,
                        "schema": "engel_meeting_room_participants_v1",
                        "updated_at_utc": iso_now(),
                        "participants": snapshot["participants"],
                        "participant_counts": snapshot["participant_counts"],
                    }
                )
                return
            if parsed.path == "/room/events":
                since = int((query.get("since") or ["0"])[0] or "0")
                limit = int((query.get("limit") or ["100"])[0] or "100")
                events = self.state.read_events(since=since, limit=limit)
                self._send_json(
                    {
                        "ok": True,
                        "schema": "engel_meeting_room_events_v1",
                        "updated_at_utc": iso_now(),
                        "events": events,
                        "event_count": len(events),
                        "last_event_id": int(events[-1]["id"]) if events else since,
                    }
                )
                return
            if parsed.path == "/room/orders/latest":
                self._send_json(
                    {
                        "ok": True,
                        "schema": "engel_meeting_room_latest_order_v1",
                        "updated_at_utc": iso_now(),
                        "latest_order": summarize_latest_order(),
                    }
                )
                return
            if parsed.path in {"/virtual-environments", "/virtual-environments/"}:
                self._send_json(
                    {
                        "ok": True,
                        "schema": "engel_virtual_environment_registry_v1",
                        "updated_at_utc": iso_now(),
                        "active_runtime_storage": "engel-fast-ssd",
                        "vault_used_for_active_runtime": False,
                        "environments": [
                            {
                                "id": "engel3d-office",
                                "name": "Engel AI Main Server Agent Meeting Room",
                                "state_url": "/virtual-environments/engel3d-office/state",
                                "presence_url": "/virtual-environments/engel3d-office/presence",
                                "events_url": "/virtual-environments/engel3d-office/events",
                                "server_owned": True,
                            }
                        ],
                    }
                )
                return
            if parsed.path in {"/virtual-environments/engel3d-office", "/virtual-environments/engel3d-office/state"}:
                self._send_json(
                    self.state.cached_snapshot(
                        "virtual",
                        lambda: build_virtual_environment_snapshot(self.state),
                    )
                )
                return
            if parsed.path == "/virtual-environments/engel3d-office/presence":
                self._send_json(build_virtual_office_presence_snapshot(self.state))
                return
            if parsed.path == "/virtual-environments/engel3d-office/events":
                since = int((query.get("since") or ["0"])[0] or "0")
                limit = int((query.get("limit") or ["100"])[0] or "100")
                raw_limit = max(limit * 20, 500)
                events = [
                    event
                    for event in self.state.read_events(since=since, limit=raw_limit)
                    if str(event.get("event_type") or "").startswith(("order.", "virtual_environment."))
                ][-limit:]
                self._send_json(
                    {
                        "ok": True,
                        "schema": "engel_virtual_environment_events_v1",
                        "updated_at_utc": iso_now(),
                        "environment_id": "engel3d-office",
                        "events": events,
                        "event_count": len(events),
                        "last_event_id": int(events[-1]["id"]) if events else since,
                    }
                )
                return
            self._send_json({"ok": False, "error": "not found", "path": parsed.path}, status=404)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc), "path": parsed.path}, status=500)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._read_json_body()
            if parsed.path == "/room/checkin":
                self._send_json(self.state.checkin(payload))
                return
            if parsed.path == "/room/order":
                order_text = str(payload.get("order_text") or payload.get("prompt") or "").strip()
                source = str(payload.get("source") or "Engel Meeting Room LAN Server")
                if not order_text:
                    self._send_json({"ok": False, "accepted": False, "reason": "order_text is required"}, status=400)
                    return
                self._send_json(submit_order(order_text, source, self.state))
                return
            if parsed.path == "/room/complete":
                order_id = str(payload.get("order_id") or "").strip()
                reply = str(payload.get("reply") or payload.get("main_reply") or "").strip()
                source = str(payload.get("source") or "Engel Meeting Room LAN Server")
                if not order_id or not reply:
                    self._send_json(
                        {"ok": False, "accepted": False, "reason": "order_id and reply are required"},
                        status=400,
                    )
                    return
                self._send_json(complete_order(order_id, reply, source, self.state))
                return
            if parsed.path == "/room/chat":
                prompt = str(payload.get("prompt") or payload.get("order_text") or "").strip()
                reply = str(payload.get("assistant_reply") or payload.get("reply") or "").strip()
                source = str(payload.get("source") or "Engel Main chat via Meeting Room LAN Server")
                if not prompt:
                    self._send_json({"ok": False, "accepted": False, "reason": "prompt is required"}, status=400)
                    return
                order = submit_order(prompt, source, self.state)
                completion: dict[str, Any] = {}
                if reply and order.get("accepted") and order.get("order_id"):
                    completion = complete_order(str(order["order_id"]), reply, source, self.state)
                self._send_json(
                    {
                        "ok": bool(order.get("accepted") and (not reply or completion.get("accepted"))),
                        "schema": "engel_meeting_room_server_chat_route_v1",
                        "updated_at_utc": iso_now(),
                        "meeting_room_server_used": True,
                        "order": order,
                        "completion": completion,
                    }
                )
                return
            if parsed.path == "/virtual-environments/engel3d-office/task":
                task = str(payload.get("task") or payload.get("prompt") or payload.get("order_text") or "").strip()
                source = str(payload.get("source") or "Engel Server Virtual Office")
                if not task:
                    self._send_json({"ok": False, "accepted": False, "reason": "task is required"}, status=400)
                    return
                event = self.state.append_event(
                    "virtual_environment.task",
                    {
                        "environment_id": "engel3d-office",
                        "source": source,
                        "task_preview": clip(task, 900),
                        "server_owned": True,
                        "runtime_storage": "engel-fast-ssd",
                    },
                )
                self._send_json(
                    {
                        "ok": True,
                        "accepted": True,
                        "schema": "engel_virtual_environment_task_receipt_v1",
                        "environment_id": "engel3d-office",
                        "event": event,
                        "state": build_virtual_environment_snapshot(self.state),
                    }
                )
                return
            self._send_json({"ok": False, "error": "not found", "path": parsed.path}, status=404)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc), "path": parsed.path}, status=500)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("ENGEL_MEETING_ROOM_SERVER_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ENGEL_MEETING_ROOM_SERVER_PORT", DEFAULT_PORT)))
    parser.add_argument("--startup-event", action="store_true", help="record a server.start event at launch")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    apply_chat_safe_meeting_room_defaults()
    server_root = resolved_server_root()
    state = MeetingRoomServerState(server_root)
    if args.startup_event:
        state.append_event(
            "server.start",
            {
                "host": args.host,
                "port": args.port,
                "server_root": str(server_root),
                "app_root": str(ROOT),
                "storage_policy": "CT246 /opt/engel active runtime; Dell HDD archive only after mount proof; no C: drive writes.",
            },
        )
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.meeting_room_state = state  # type: ignore[attr-defined]
    print(
        json.dumps(
            {
                "ok": True,
                "schema": SERVER_SCHEMA,
                "status": "serving",
                "url": f"http://{args.host}:{args.port}",
                "server_root": str(server_root),
                "app_root": str(ROOT),
                "updated_at_utc": iso_now(),
            },
            indent=2,
        ),
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        state.append_event("server.stop", {"reason": "KeyboardInterrupt", "updated_at_utc": iso_now()})
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
