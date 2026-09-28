#!/usr/bin/env python3
"""Manual local LAN pairing/status receiver for Engel Remote Worker.

Phase 4 is pairing/status only. Phase 5 adds bounded Engel Communication
Router auto-assignment polling and untrusted result return. Request bodies are treated
as untrusted data and never become commands, routes, trusted-memory writes,
source edits, or applied changes.
"""

from __future__ import annotations

import engel_temp_policy  # noqa: F401
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import string
from typing import Any

from engel_branding import ENGEL_COMMUNICATION_ROUTER_ALIASES, ENGEL_CORE_NAME
from engel_project_paths import resolve_engel_app_root


PROJECT_ROOT = resolve_engel_app_root(__file__)
PAIRING_ROOT = PROJECT_ROOT / "remote_workers" / "lan_pairing"
SESSION_PATH = PAIRING_ROOT / "pairing_session.json"
REPORT_DIR = PROJECT_ROOT / "reports" / "remote_worker_lan_pairing"
ASSIGNMENT_ROOT = PROJECT_ROOT / "remote_workers" / "communication_queen_assignments"
APPROVED_ASSIGNMENTS_DIR = ASSIGNMENT_ROOT / "approved"
CLAIMED_ASSIGNMENTS_DIR = ASSIGNMENT_ROOT / "claimed"
RETURNED_ASSIGNMENTS_DIR = ASSIGNMENT_ROOT / "returned"
INVALID_ASSIGNMENTS_DIR = ASSIGNMENT_ROOT / "invalid"
RETIRED_ASSIGNMENTS_DIR = ASSIGNMENT_ROOT / "retired"
ASSIGNMENT_EXAMPLES_DIR = ASSIGNMENT_ROOT / "examples"
CLAIM_LOCKS_DIR = ASSIGNMENT_ROOT / "claim_locks"
DUPLICATE_RETURNS_DIR = ASSIGNMENT_ROOT / "duplicate_returns"
AUTO_REPORT_DIR = PROJECT_ROOT / "reports" / "remote_worker_auto_assignment"
DUPLICATE_GUARD_REPORT_DIR = PROJECT_ROOT / "reports" / "remote_worker_duplicate_guards"
LINK_MANAGER_ROOT = PROJECT_ROOT / "remote_workers" / "lan_link_manager"
LINK_MANAGER_STATE_PATH = LINK_MANAGER_ROOT / "session_state.json"
# Phones and the PC receiver share one pairing token for this full window.
# Do not rotate early inside the TTL — early rotation was dropping long runs.
TOKEN_TTL_SECONDS = 8 * 60 * 60
# Worker continuity without re-entering a code (DHCP / WiFi IP drift, token age).
PAIRED_WORKER_CONTINUITY_SECONDS = 6 * 60 * 60
# Advisory only: UI may warn when the session is close to expiring.
TOKEN_ROTATE_GRACE_SECONDS = 300
TOKEN_LENGTH = 8
MAX_REQUEST_BYTES = 4096
MAX_RESULT_BYTES = 64 * 1024
MAX_ASSIGNMENT_FILES = 100
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
FINAL_DECISION = "PAIRING STATUS ONLY - NO CONTROL GRANTED"
AUTO_FINAL_DECISION = "UNTRUSTED REVIEW ONLY - NOT APPLIED"
DUPLICATE_FINAL_DECISION = "DUPLICATE RETURN REJECTED - NOT APPLIED"
EXPECTED_WORKER_DEVICE = "engel_remote_worker_flutter"
EXPECTED_WORKER_ID = "android_worker_alpha"
# All worker IDs the LAN server will accept at /pair, /worker/*, and
# /worker/return-result. Keep this set in sync with the Flutter client's
# _allowedWorkerIds in mobile/engel_remote_worker/lib/lan_pairing_client.dart.
ALLOWED_WORKER_IDS = frozenset({
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
})


def is_allowed_worker_id(worker_id: Any) -> bool:
    """Return True if the supplied worker_id is one of the allowed phones."""
    return isinstance(worker_id, str) and worker_id in ALLOWED_WORKER_IDS


EXPECTED_CLIENT_MODE = "local_draft_mode"
ALLOWED_ACTIONS = ["status_ping"]
AUTO_ALLOWED_ACTIONS = ["poll_approved_assignment", "return_untrusted_result"]
BLOCKED_ACTIONS = [
    "execute_commands",
    "mutate_source",
    "mutate_routes",
    "mutate_queue",
    "write_trusted_memory",
    "auto_apply",
    "control_engel",
    "packet_transfer",
    "result_upload",
]
REQUIRED_PACKET_BLOCKED_ACTIONS = [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes",
]
ALLOWED_AUTO_TASK_TYPES = {
    "draft_notes",
    "summarize_text",
    "review_status",
    "extract_topics",
    "classify_untrusted_content",
    "prepare_library_candidate_notes",
    "prepare_memory_candidate_notes",
    "compare_summaries",
    "check_document_against_safety_rules",
    "draft_research_note",
    "draft_candidate_json",
    "format_report_draft",
    "classify_file",
    "compute_small_local_task",
    "return_status",
    "return_logs",
    "return_receipt",
    "draft_code_artifact",
    "web_research_brief",
}
BLOCKED_AUTO_TASK_TYPES = {
    "execute_command",
    "run_command",
    "shell",
    "powershell",
    "cmd",
    "bash",
    "wsl",
    "run_route",
    "edit_source",
    "apply_patch",
    "write_memory",
    "trusted_memory_write",
    "approve_memory",
    "promote_memory",
    "mutate_queue",
    "mutate_routes",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
    "start_worker",
    "start_server",
    "auto_apply",
    "control_engel",
}
LINK_MANAGER_ALLOWED_CONTROLS = [
    "status_request",
    "check_now",
    "enable_auto_worker",
    "disable_auto_worker",
    "pause_worker",
    "rotate_session_notice",
    "assignment_available",
]
LINK_MANAGER_BLOCKED_CONTROLS = [
    "execute_command",
    "run_route",
    "apply_patch",
    "write_memory",
    "mutate_source",
    "mutate_routes",
    "mutate_queue",
    "provider_call",
    "browser_task",
    "install_package",
    "download",
    "trust_result",
]

# Chat callback — registered by engel_app when starting the server.
# Receives user text string, returns response string.
_CHAT_CALLBACK = None


def register_chat_callback(fn) -> None:
    global _CHAT_CALLBACK
    _CHAT_CALLBACK = fn


def rust_lan_bridge_enabled() -> bool:
    return os.environ.get("ENGEL_REMOTE_WORKER_LAN_RUST_BRIDGE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def rust_lan_bridge_strict() -> bool:
    return os.environ.get("ENGEL_REMOTE_WORKER_LAN_RUST_STRICT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def rust_bridge_error_response(reason: str, status: int = 503) -> tuple[int, dict[str, Any]] | None:
    if not rust_lan_bridge_strict():
        return None
    return status, {
        "accepted": False,
        "status": "rust_bridge_unavailable",
        "status_code": status,
        "runtime": "engel-ai-rs",
        "bridge": "python-lan-endpoint-rust-state-machine",
        "reason": reason,
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "safe_to_auto_apply": False,
        "link_manager_controls": link_manager_state(),
    }


def rust_bridge_next_assignment_response(
    *,
    worker_id: str,
    worker_device: str,
) -> tuple[int, dict[str, Any]] | None:
    if not rust_lan_bridge_enabled():
        return None
    try:
        from engel_rust_remote_worker_lan_bridge import claim_next_assignment

        bridged = claim_next_assignment(worker_id, worker_device)
    except Exception as exc:  # pragma: no cover - strict verifier covers the happy path.
        return rust_bridge_error_response(f"Rust claim bridge failed: {exc}")
    if bridged is None:
        return None
    status, response = bridged
    response.setdefault("runtime", "engel-ai-rs")
    response.setdefault("bridge", "python-lan-endpoint-rust-state-machine")
    response.setdefault("link_manager_controls", link_manager_state())
    return status, response


def rust_bridge_return_result_response(
    payload: Any,
    remote_address: str,
) -> tuple[int, dict[str, Any]] | None:
    if not rust_lan_bridge_enabled():
        return None
    try:
        from engel_rust_remote_worker_lan_bridge import return_result

        bridged = return_result(payload, remote_address)
    except Exception as exc:  # pragma: no cover - strict verifier covers the happy path.
        return rust_bridge_error_response(f"Rust return-result bridge failed: {exc}")
    if bridged is None:
        return None
    status, response = bridged
    response.setdefault("runtime", "engel-ai-rs")
    response.setdefault("bridge", "python-lan-endpoint-rust-state-machine")
    return status, response


@dataclass(frozen=True)
class PairingSession:
    pairing_code: str
    created_at_utc: str
    expires_at_utc: str

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or utc_now()
        expires = parse_utc(self.expires_at_utc)
        return expires is None or current >= expires

    def seconds_remaining(self, now: datetime | None = None) -> float:
        current = now or utc_now()
        expires = parse_utc(self.expires_at_utc)
        if expires is None:
            return 0.0
        return max(0.0, (expires - current).total_seconds())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_stamp(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def ensure_scaffold() -> None:
    PAIRING_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for directory in [
        ASSIGNMENT_ROOT,
        APPROVED_ASSIGNMENTS_DIR,
        CLAIMED_ASSIGNMENTS_DIR,
        RETURNED_ASSIGNMENTS_DIR,
        INVALID_ASSIGNMENTS_DIR,
        RETIRED_ASSIGNMENTS_DIR,
        ASSIGNMENT_EXAMPLES_DIR,
        CLAIM_LOCKS_DIR,
        DUPLICATE_RETURNS_DIR,
        AUTO_REPORT_DIR,
        DUPLICATE_GUARD_REPORT_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def generate_pairing_code(length: int = TOKEN_LENGTH) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_pairing_session(now: datetime | None = None) -> PairingSession:
    ensure_scaffold()
    created = now or utc_now()
    session = PairingSession(
        pairing_code=generate_pairing_code(),
        created_at_utc=utc_stamp(created),
        expires_at_utc=utc_stamp(created + timedelta(seconds=TOKEN_TTL_SECONDS)),
    )
    SESSION_PATH.write_text(json.dumps(session.__dict__, indent=2), encoding="utf-8")
    return session


def get_or_create_session(now: datetime | None = None) -> PairingSession:
    """Return the on-disk pairing session while it is still valid, else issue
    a fresh one. Reuse until real expiry so paired phones stay up for multi-hour
    training without silent invalidation near the end of the TTL."""
    ensure_scaffold()
    current = now or utc_now()
    existing = load_pairing_session()
    if existing is not None and not existing.is_expired(current):
        return existing
    return create_pairing_session(current)


def load_pairing_session() -> PairingSession | None:
    try:
        payload = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    code = str(payload.get("pairing_code", ""))
    created = str(payload.get("created_at_utc", ""))
    expires = str(payload.get("expires_at_utc", ""))
    if not code or not created or not expires:
        return None
    return PairingSession(code, created, expires)


def redacted_code(code: str) -> str:
    if len(code) <= 2:
        return "**"
    return "*" * (len(code) - 2) + code[-2:]


def link_manager_state() -> dict[str, Any]:
    state: dict[str, Any] = {}
    if LINK_MANAGER_STATE_PATH.exists():
        try:
            loaded = json.loads(LINK_MANAGER_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except (OSError, json.JSONDecodeError):
            state = {}
    return {
        "link_manager": "Engel Dedicated Phone Link",
        "phone_role": "Dedicated Engel Remote Worker",
        "control_direction": "Engel controls phone",
        "phone_does_not_control_engel": True,
        "lan_only": True,
        "auto_worker_enabled": bool(state.get("auto_worker_enabled")),
        "auto_worker_paused": bool(state.get("auto_worker_paused")),
        "check_now_requested": bool(state.get("check_now_requested")),
        "claim_lock_status": "present"
        if (PROJECT_ROOT / "tools" / "verify_engel_remote_worker_claim_lock.py").exists()
        else "missing",
        "allowed_control_messages": list(LINK_MANAGER_ALLOWED_CONTROLS),
        "blocked_control_messages": list(LINK_MANAGER_BLOCKED_CONTROLS),
        "requires_review": True,
        "safe_to_auto_apply": False,
        "auto_apply": False,
        "trusted_memory_write": False,
    }


def update_link_manager_seen(payload: dict[str, Any] | None, remote_address: str) -> None:
    if not LINK_MANAGER_ROOT.exists():
        return
    state: dict[str, Any] = {}
    if LINK_MANAGER_STATE_PATH.exists():
        try:
            loaded = json.loads(LINK_MANAGER_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except (OSError, json.JSONDecodeError):
            state = {}
    identity = {
        "worker_id": EXPECTED_WORKER_ID,
        "worker_device": EXPECTED_WORKER_DEVICE,
        "remote_address": remote_address,
    }
    if isinstance(payload, dict):
        identity["worker_device"] = str(payload.get("worker_device") or EXPECTED_WORKER_DEVICE)
        if payload.get("worker_id"):
            identity["worker_id"] = str(payload.get("worker_id"))
        for optional in ["app_version", "platform", "battery_level", "current_mode"]:
            if payload.get(optional) is not None:
                identity[optional] = payload.get(optional)
    worker_id = str(identity.get("worker_id") or EXPECTED_WORKER_ID)
    workers = state.get("workers")
    if not isinstance(workers, dict):
        workers = {}
    workers[worker_id] = {
        "identity": identity,
        "last_seen_utc": utc_stamp(),
        "phone_does_not_control_engel": True,
        "auto_apply": False,
        "safe_to_auto_apply": False,
        "trusted_memory_write": False,
        "source_mutation": False,
        "route_mutation": False,
        "queue_mutation_from_phone": False,
    }
    state.update(
        {
            "paired_phone_identity": identity,
            "last_seen_utc": utc_stamp(),
            "workers": workers,
            "phone_does_not_control_engel": True,
            "auto_apply": False,
            "safe_to_auto_apply": False,
            "trusted_memory_write": False,
            "source_mutation": False,
            "route_mutation": False,
            "queue_mutation_from_phone": False,
            "receiver_pid": os.getpid(),
            "receiver_running": True,
        }
    )
    LINK_MANAGER_ROOT.mkdir(parents=True, exist_ok=True)
    LINK_MANAGER_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def status_payload() -> dict[str, Any]:
    ensure_scaffold()
    session = load_pairing_session()
    token_status = "missing"
    token_hint = None
    expires_at = None
    if session is not None:
        token_status = "expired" if session.is_expired() else "valid"
        token_hint = redacted_code(session.pairing_code)
        expires_at = session.expires_at_utc
    return {
        "receiver": "Engel Remote Worker LAN Pairing V1",
        "mode": "pairing_status_only",
        "default_host": DEFAULT_HOST,
        "default_port": DEFAULT_PORT,
        "lan_requires_allow_lan": True,
        "token_status": token_status,
        "token_hint": token_hint,
        "token_expires_at_utc": expires_at,
        "token_auto_rotation": True,
        "token_rotate_grace_seconds": TOKEN_ROTATE_GRACE_SECONDS,
        "paired_worker_continuity_seconds": PAIRED_WORKER_CONTINUITY_SECONDS,
        "min_stable_pairing_hours": PAIRED_WORKER_CONTINUITY_SECONDS // 3600,
        "pairing_root": str(PAIRING_ROOT),
        "reports": str(REPORT_DIR),
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "packet_transfer": False,
        "result_upload": False,
        "background_autostart": False,
        "auto_assignment_root": str(ASSIGNMENT_ROOT),
        "auto_assignment_mode": "manual_server_only",
        "claim_lock_dir": str(CLAIM_LOCKS_DIR),
        "duplicate_returns_dir": str(DUPLICATE_RETURNS_DIR),
        "duplicate_guard_reports": str(DUPLICATE_GUARD_REPORT_DIR),
        "link_manager": link_manager_state(),
    }


def health_response() -> dict[str, Any]:
    return {
        "status": "engel_lan_pairing_receiver_ready",
        "mode": "pairing_only",
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "packet_transfer": False,
        "result_upload": False,
    }


def probe_receiver_health(host: str, port: int) -> bool:
    """Return True when a LAN pairing receiver answers GET /health."""
    import socket as _socket

    request = (
        f"GET /health HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    try:
        with _socket.create_connection((str(host), int(port)), timeout=1.5) as sock:
            sock.settimeout(1.5)
            sock.sendall(request)
            chunks: list[bytes] = []
            total_bytes = 0
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                chunks.append(chunk)
                total_bytes += len(chunk)
                if b"engel_lan_pairing_receiver_ready" in b"".join(chunks) or total_bytes >= 8192:
                    break
    except OSError:
        return False
    body = b"".join(chunks).decode("utf-8", errors="replace")
    if " 200 " not in body.split("\r\n", 1)[0]:
        return False
    return "engel_lan_pairing_receiver_ready" in body


def base_pair_response(paired: bool) -> dict[str, Any]:
    return {
        "paired": paired,
        "mode": "status_only",
        "allowed_actions": ALLOWED_ACTIONS,
        "blocked_actions": BLOCKED_ACTIONS,
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "packet_transfer": False,
        "result_upload": False,
    }


def worker_status_response() -> dict[str, Any]:
    response = {
        "worker_protocol": "communication_queen_auto_assignment",
        "mode": "bounded_auto_worker",
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "allowed_actions": AUTO_ALLOWED_ACTIONS,
        "blocked_actions": [
            "execute_commands",
            "mutate_source",
            "mutate_routes",
            "mutate_queue",
            "write_trusted_memory",
            "auto_apply",
            "control_engel",
        ],
        "packet_transfer": "approved_assignment_poll_only",
        "result_upload": "untrusted_result_return_only",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "discord_on_phone": False,
        "link_manager_controls": link_manager_state(),
    }
    try:
        from engel_discord_android_worker_pipe import pipe_colony_snapshot

        snap = pipe_colony_snapshot()
        response["discord_pipe"] = {
            "schema": snap.get("schema"),
            "approved_waiting": snap.get("approved_discord_assignments"),
            "pending_replies": snap.get("pending_discord_replies"),
            "discord_on_phone": False,
        }
    except Exception:
        response["discord_pipe"] = {"discord_on_phone": False}
    return response


def validate_pair_payload(
    payload: Any,
    *,
    session: PairingSession | None = None,
    now: datetime | None = None,
) -> tuple[int, dict[str, Any]]:
    response = base_pair_response(False)
    if not isinstance(payload, dict):
        response["error"] = "invalid JSON object"
        return 400, response

    message_type = payload.get("message_type")
    if message_type not in (None, "pairing_status_request"):
        response["error"] = "unknown message type"
        return 400, response

    requested_blocked = [
        action for action in BLOCKED_ACTIONS if action in payload and bool(payload.get(action))
    ]
    if requested_blocked:
        response["error"] = "blocked action requested"
        response["blocked_request_fields"] = requested_blocked[:5]
        return 403, response

    pairing_code = str(payload.get("pairing_code", "")).strip()
    if not pairing_code:
        response["error"] = "missing pairing code"
        return 400, response

    worker_device = str(payload.get("worker_device", "")).strip()
    worker_id = str(payload.get("worker_id", EXPECTED_WORKER_ID)).strip() or EXPECTED_WORKER_ID
    client_mode = str(payload.get("client_mode", "")).strip()
    if worker_device != EXPECTED_WORKER_DEVICE:
        response["error"] = "unknown worker device"
        return 400, response
    if not is_allowed_worker_id(worker_id):
        response["error"] = "unknown worker id"
        response["allowed_worker_ids"] = sorted(ALLOWED_WORKER_IDS)
        return 400, response
    if client_mode != EXPECTED_CLIENT_MODE:
        response["error"] = "unknown client mode"
        return 400, response

    active_session = session or load_pairing_session()
    if active_session is None:
        response["error"] = "no valid pairing token"
        return 403, response
    if active_session.is_expired(now):
        response["error"] = "pairing token expired"
        return 403, response
    if not secrets.compare_digest(pairing_code, active_session.pairing_code):
        response["error"] = "invalid pairing code"
        return 403, response

    success = base_pair_response(True)
    success["status"] = "paired_for_status_only"
    success["worker_id"] = worker_id
    success["final_decision"] = FINAL_DECISION
    try:
        from engel_android_worker_agent_brain import pair_status_fields

        success.update(pair_status_fields(worker_id))
    except Exception:
        success["agent_assigned"] = False
        success["discord_on_phone"] = False
        success["controls_engel"] = False
    return 200, success


def validate_pairing_auth(
    pairing_code: str,
    worker_device: str,
    *,
    worker_id: str = EXPECTED_WORKER_ID,
    session: PairingSession | None = None,
    now: datetime | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = {
        "pairing_code": pairing_code,
        "worker_device": worker_device,
        "worker_id": worker_id,
        "client_mode": EXPECTED_CLIENT_MODE,
    }
    return validate_pair_payload(payload, session=session, now=now)


def validate_existing_worker_session(
    worker_device: str,
    worker_id: str,
    remote_address: str,
) -> tuple[int, dict[str, Any]]:
    """Allow an already-known LAN worker to survive pairing-token rotation.

    This is not open pairing. It only applies when the worker id, worker device,
    and remote LAN address match the last recorded paired worker state. It keeps
    long-running WiFi training loops alive without granting new authority.
    """
    response = base_pair_response(False)
    if worker_device != EXPECTED_WORKER_DEVICE:
        response["error"] = "unknown worker device"
        return 401, response
    if not is_allowed_worker_id(worker_id):
        response["error"] = "unknown worker id"
        return 401, response
    state = {}
    if LINK_MANAGER_STATE_PATH.exists():
        try:
            loaded = json.loads(LINK_MANAGER_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = loaded
        except (OSError, json.JSONDecodeError):
            state = {}
    workers = state.get("workers") if isinstance(state.get("workers"), dict) else {}
    worker_record = workers.get(worker_id) if isinstance(workers, dict) else None
    identity = worker_record.get("identity") if isinstance(worker_record, dict) else None
    if not isinstance(identity, dict):
        response["error"] = "no known paired worker session"
        return 401, response
    if identity.get("worker_device") != worker_device:
        response["error"] = "known worker device mismatch"
        return 401, response
    recorded_address = str(identity.get("remote_address") or "")
    if recorded_address and recorded_address != str(remote_address):
        last_seen = worker_record.get("last_seen_utc") if isinstance(worker_record, dict) else None
        seen_at = parse_utc(last_seen) if last_seen else None
        if seen_at is None:
            response["error"] = "known worker address mismatch"
            return 401, response
        age_seconds = (utc_now() - seen_at).total_seconds()
        if age_seconds > PAIRED_WORKER_CONTINUITY_SECONDS:
            response["error"] = "known worker address mismatch"
            return 401, response
    success = base_pair_response(True)
    success["status"] = "paired_existing_worker_session"
    success["worker_id"] = worker_id
    success["token_rotation_continuity"] = True
    success["final_decision"] = FINAL_DECISION
    return 200, success


def validate_assignment_packet(payload: Any, worker_id: str = EXPECTED_WORKER_ID) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["assignment packet must be a JSON object"]
    required_strings = [
        "packet_version",
        "packet_id",
        "created_by",
        "approved_by",
        "assignment_mode",
        "trust_level",
        "worker_target",
        "task_type",
        "title",
        "instructions",
    ]
    for field in required_strings:
        if not str(payload.get(field, "")).strip():
            errors.append(f"missing required field: {field}")
    if payload.get("created_by") not in (*ENGEL_COMMUNICATION_ROUTER_ALIASES, ENGEL_CORE_NAME):
        errors.append("created_by must be Engel Communication Router or approved Engel assignment source")
    if payload.get("approved_by") != "Engel Core":
        errors.append("approved_by must be Engel Core")
    if payload.get("assignment_mode") != "remote_worker_auto":
        errors.append("assignment_mode must be remote_worker_auto")
    if payload.get("trust_level") != "untrusted_until_reviewed":
        errors.append("trust_level must be untrusted_until_reviewed")
    if payload.get("worker_target") not in (worker_id, "remote_worker", "android_remote_worker"):
        errors.append("worker_target does not match paired worker")
    task_type = str(payload.get("task_type", ""))
    if task_type in BLOCKED_AUTO_TASK_TYPES:
        errors.append("blocked task type")
    if task_type and task_type not in ALLOWED_AUTO_TASK_TYPES:
        errors.append("task_type is not allowed for Phase 5")
    if payload.get("requires_review") is not True:
        errors.append("requires_review must be true")
    if payload.get("safe_to_auto_apply") is not False:
        errors.append("safe_to_auto_apply must be false")
    blocked_actions = payload.get("blocked_actions")
    if not isinstance(blocked_actions, list):
        errors.append("blocked_actions must be a list")
    else:
        for action in REQUIRED_PACKET_BLOCKED_ACTIONS:
            if action not in blocked_actions:
                errors.append(f"blocked_actions missing: {action}")
    allowed_outputs = payload.get("allowed_outputs")
    if allowed_outputs != ["draft_result_json"]:
        errors.append("allowed_outputs must be draft_result_json only")
    return errors


def assignment_files(directory: Path = APPROVED_ASSIGNMENTS_DIR) -> list[Path]:
    ensure_scaffold()
    if not directory.exists():
        return []
    files = [path for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()) if path.is_file()]
    return [path for path in files if path.suffix.lower() == ".json"][:MAX_ASSIGNMENT_FILES]


def load_json_file(path: Path) -> Any:
    try:
        if path.stat().st_size > MAX_RESULT_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def canonical_id(value: Any) -> str:
    return str(value or "").strip().lower()


def record_files(directory: Path, suffix: str | None = ".json") -> list[Path]:
    ensure_scaffold()
    if not directory.exists():
        return []
    files = [path for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()) if path.is_file()]
    if suffix is None:
        return files
    return [path for path in files if path.name.lower().endswith(suffix.lower())]


def records_with_packet_id(directory: Path, packet_id: Any, suffix: str | None = ".json") -> list[tuple[Path, dict[str, Any]]]:
    target = canonical_id(packet_id)
    matches: list[tuple[Path, dict[str, Any]]] = []
    if not target:
        return matches
    for path in record_files(directory, suffix):
        payload = load_json_file(path)
        if isinstance(payload, dict) and canonical_id(payload.get("packet_id")) == target:
            matches.append((path, payload))
    return matches


def has_packet_record(directory: Path, packet_id: Any, suffix: str | None = ".json") -> bool:
    return bool(records_with_packet_id(directory, packet_id, suffix))


def has_claim_lock(packet_id: Any, lock_dir: Path = CLAIM_LOCKS_DIR) -> bool:
    packet_slug = safe_id(packet_id)
    return (lock_dir / f"{packet_slug}.lock").exists()


def has_returned_result(
    packet_id: Any,
    worker_id: str = EXPECTED_WORKER_ID,
    returned_dir: Path = RETURNED_ASSIGNMENTS_DIR,
) -> bool:
    target_worker = canonical_id(worker_id)
    for _path, payload in records_with_packet_id(returned_dir, packet_id):
        if canonical_id(payload.get("worker_id")) == target_worker:
            return True
    return False


def matching_claim(
    packet_id: Any,
    worker_id: str = EXPECTED_WORKER_ID,
    worker_device: str = EXPECTED_WORKER_DEVICE,
    claimed_dir: Path = CLAIMED_ASSIGNMENTS_DIR,
) -> tuple[Path, dict[str, Any]] | None:
    target_worker = canonical_id(worker_id)
    target_device = canonical_id(worker_device)
    for path, payload in records_with_packet_id(claimed_dir, packet_id):
        if path.name.endswith("_assignment.json"):
            continue
        if canonical_id(payload.get("worker_id")) == target_worker and canonical_id(payload.get("worker_device")) == target_device:
            return path, payload
    return None


def assignment_is_ineligible(
    payload: dict[str, Any],
    *,
    claimed_dir: Path = CLAIMED_ASSIGNMENTS_DIR,
    returned_dir: Path = RETURNED_ASSIGNMENTS_DIR,
    retired_dir: Path = RETIRED_ASSIGNMENTS_DIR,
    invalid_dir: Path = INVALID_ASSIGNMENTS_DIR,
    lock_dir: Path = CLAIM_LOCKS_DIR,
) -> str | None:
    packet_id = payload.get("packet_id")
    if has_claim_lock(packet_id, lock_dir):
        return "already claim-locked"
    if has_packet_record(claimed_dir, packet_id):
        return "already claimed"
    if has_packet_record(returned_dir, packet_id):
        return "already returned"
    if has_packet_record(retired_dir, packet_id):
        return "retired"
    if has_packet_record(invalid_dir, packet_id):
        return "invalid"
    return None


def next_valid_assignment(
    worker_id: str = EXPECTED_WORKER_ID,
    directory: Path = APPROVED_ASSIGNMENTS_DIR,
    claimed_dir: Path = CLAIMED_ASSIGNMENTS_DIR,
    returned_dir: Path = RETURNED_ASSIGNMENTS_DIR,
    retired_dir: Path = RETIRED_ASSIGNMENTS_DIR,
    invalid_dir: Path = INVALID_ASSIGNMENTS_DIR,
    lock_dir: Path = CLAIM_LOCKS_DIR,
) -> tuple[dict[str, Any] | None, Path | None, list[str]]:
    last_errors: list[str] = []
    for path in assignment_files(directory):
        payload = load_json_file(path)
        errors = validate_assignment_packet(payload, worker_id)
        if not errors and isinstance(payload, dict):
            ineligible = assignment_is_ineligible(
                payload,
                claimed_dir=claimed_dir,
                returned_dir=returned_dir,
                retired_dir=retired_dir,
                invalid_dir=invalid_dir,
                lock_dir=lock_dir,
            )
            if ineligible:
                last_errors = [f"assignment ineligible: {ineligible}"]
                continue
            return payload, path, []
        last_errors = errors
    return None, None, last_errors


def write_claim_record(
    packet: dict[str, Any],
    source_path: Path,
    *,
    worker_id: str,
    worker_device: str,
    claimed_assignment_path: Path,
    lock_path: Path,
    claimed_dir: Path = CLAIMED_ASSIGNMENTS_DIR,
) -> Path:
    ensure_scaffold()
    claimed_dir.mkdir(parents=True, exist_ok=True)
    timestamp = utc_stamp()
    packet_id = safe_id(packet.get("packet_id", "unknown"))
    claim_path = claimed_dir / f"{timestamp_file(timestamp)}_{packet_id}_claim.json"
    claim = {
        "timestamp_utc": timestamp,
        "packet_id": packet.get("packet_id"),
        "worker_id": worker_id,
        "worker_device": worker_device,
        "source_path": str(source_path),
        "claimed_assignment_path": str(claimed_assignment_path),
        "claim_lock_path": str(lock_path),
        "claim_type": "append_only_protocol_record",
        "claim_mode": "untrusted_assignment_claim",
        "trust_level": "untrusted_assignment_record",
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "safe_to_auto_apply": False,
    }
    claim_path.write_text(json.dumps(claim, indent=2), encoding="utf-8")
    return claim_path


def claim_assignment(
    packet: dict[str, Any],
    source_path: Path,
    *,
    worker_id: str = EXPECTED_WORKER_ID,
    worker_device: str = EXPECTED_WORKER_DEVICE,
    claimed_dir: Path = CLAIMED_ASSIGNMENTS_DIR,
    lock_dir: Path = CLAIM_LOCKS_DIR,
) -> tuple[Path, Path, Path]:
    ensure_scaffold()
    claimed_dir.mkdir(parents=True, exist_ok=True)
    lock_dir.mkdir(parents=True, exist_ok=True)
    timestamp = utc_stamp()
    packet_id = safe_id(packet.get("packet_id", "unknown"))
    lock_path = lock_dir / f"{packet_id}.lock"
    lock_payload = {
        "timestamp_utc": timestamp,
        "packet_id": packet.get("packet_id"),
        "worker_id": worker_id,
        "worker_device": worker_device,
        "lock_type": "exclusive_assignment_claim_lock",
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
    }
    with lock_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(lock_payload, indent=2))
    claimed_assignment_path = claimed_dir / f"{timestamp_file(timestamp)}_{packet_id}_assignment.json"
    shutil.move(str(source_path), str(claimed_assignment_path))
    claim_path = write_claim_record(
        packet,
        source_path,
        worker_id=worker_id,
        worker_device=worker_device,
        claimed_assignment_path=claimed_assignment_path,
        lock_path=lock_path,
        claimed_dir=claimed_dir,
    )
    return claim_path, claimed_assignment_path, lock_path


def no_work_response(errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "no_work",
        "mode": "bounded_auto_worker",
        "reason": "no_unclaimed_approved_assignments",
        "validation_errors_seen": (errors or [])[:5],
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "requires_review": True,
        "safe_to_auto_apply": False,
        "link_manager_controls": link_manager_state(),
    }


def next_assignment_response(
    *,
    worker_id: str = EXPECTED_WORKER_ID,
    worker_device: str = EXPECTED_WORKER_DEVICE,
    approved_dir: Path = APPROVED_ASSIGNMENTS_DIR,
    claimed_dir: Path = CLAIMED_ASSIGNMENTS_DIR,
    returned_dir: Path = RETURNED_ASSIGNMENTS_DIR,
    retired_dir: Path = RETIRED_ASSIGNMENTS_DIR,
    invalid_dir: Path = INVALID_ASSIGNMENTS_DIR,
    lock_dir: Path = CLAIM_LOCKS_DIR,
) -> tuple[int, dict[str, Any]]:
    bridged = rust_bridge_next_assignment_response(
        worker_id=worker_id,
        worker_device=worker_device,
    )
    if bridged is not None:
        return bridged

    packet, source_path, errors = next_valid_assignment(
        worker_id=worker_id,
        directory=approved_dir,
        claimed_dir=claimed_dir,
        returned_dir=returned_dir,
        retired_dir=retired_dir,
        invalid_dir=invalid_dir,
        lock_dir=lock_dir,
    )
    if packet is None or source_path is None:
        return 200, no_work_response(errors)
    try:
        claim_path, claimed_assignment_path, lock_path = claim_assignment(
            packet,
            source_path,
            worker_id=worker_id,
            worker_device=worker_device,
            claimed_dir=claimed_dir,
            lock_dir=lock_dir,
        )
    except FileExistsError:
        return 200, no_work_response(["assignment already claim-locked"])
    return 200, {
        "status": "assignment_ready",
        "mode": "bounded_auto_worker",
        "assignment": packet,
        "claim_receipt_path": str(claim_path),
        "claimed_assignment_path": str(claimed_assignment_path),
        "claim_lock_path": str(lock_path),
        "source_path": str(source_path),
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "requires_review": True,
        "safe_to_auto_apply": False,
        "link_manager_controls": link_manager_state(),
    }


def validate_returned_result(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["result must be a JSON object"]
    for field in ["result_version", "packet_id", "worker_device", "worker_id", "trust_level", "result_type", "draft_text"]:
        if field not in payload:
            errors.append(f"missing required field: {field}")
    if payload.get("worker_device") != EXPECTED_WORKER_DEVICE:
        errors.append("worker_device mismatch")
    if not is_allowed_worker_id(payload.get("worker_id")):
        errors.append("worker_id must be one of: " + ", ".join(sorted(ALLOWED_WORKER_IDS)))
    if payload.get("trust_level") != "untrusted_until_engel_review":
        errors.append("trust_level must be untrusted_until_engel_review")
    if payload.get("requires_review") is not True:
        errors.append("requires_review must be true")
    if payload.get("safe_to_auto_apply") is not False:
        errors.append("safe_to_auto_apply must be false")
    for field in [
        "auto_apply",
        "trusted",
        "write_trusted_memory",
        "execute_commands",
        "mutate_source",
        "mutate_routes",
        "mutate_queue",
        "control_engel",
    ]:
        if payload.get(field) is True:
            errors.append(f"forbidden true field: {field}")
    return errors


def store_returned_result(
    payload: dict[str, Any],
    remote_address: str = "local",
    *,
    returned_dir: Path = RETURNED_ASSIGNMENTS_DIR,
    report_dir: Path = AUTO_REPORT_DIR,
) -> tuple[Path, Path]:
    ensure_scaffold()
    returned_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = utc_stamp()
    packet_id = safe_id(payload.get("packet_id", "unknown"))
    result_path = returned_dir / f"{timestamp_file(timestamp)}_{packet_id}_result.json"
    receipt_path = report_dir / f"REMOTE_WORKER_AUTO_ASSIGNMENT_{timestamp_file(timestamp)}_{packet_id}.md"
    safe_payload = dict(payload)
    safe_payload.pop("pairing_code", None)
    safe_payload.update(
        {
            "stored_at_utc": timestamp,
            "storage_decision": AUTO_FINAL_DECISION,
            "direct_control": False,
            "trusted_memory_write": False,
            "auto_apply": False,
        }
    )
    result_path.write_text(json.dumps(safe_payload, indent=2), encoding="utf-8")
    text = f"""# Remote Worker Auto Assignment Receipt

- timestamp: `{timestamp}`
- remote address: `{bounded(remote_address)}`
- packet_id: `{bounded(payload.get("packet_id"))}`
- worker_device: `{bounded(payload.get("worker_device"))}`
- worker_id: `{bounded(payload.get("worker_id"))}`
- result_type: `{bounded(payload.get("result_type"))}`
- requires_review: `{payload.get("requires_review")}`
- safe_to_auto_apply: `{payload.get("safe_to_auto_apply")}`
- returned_result_path: `{result_path}`
- final decision: `{AUTO_FINAL_DECISION}`

Returned Remote Worker output is untrusted review-only data. This receipt does not execute, apply, promote, route, queue, trust, or write trusted memory from worker output.
"""
    receipt_path.write_text(text, encoding="utf-8")
    return result_path, receipt_path


def write_duplicate_return_rejection(
    payload: dict[str, Any],
    *,
    remote_address: str,
    prior_result_path: Path | None,
    duplicate_dir: Path = DUPLICATE_RETURNS_DIR,
    report_dir: Path = DUPLICATE_GUARD_REPORT_DIR,
) -> tuple[Path, Path]:
    ensure_scaffold()
    duplicate_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = utc_stamp()
    packet_id = safe_id(payload.get("packet_id", "unknown"))
    duplicate_path = duplicate_dir / f"{timestamp_file(timestamp)}_{packet_id}_duplicate_return.json"
    receipt_path = report_dir / f"DUPLICATE_RETURN_{timestamp_file(timestamp)}_{packet_id}.md"
    duplicate_record = {
        "timestamp_utc": timestamp,
        "packet_id": payload.get("packet_id"),
        "worker_id": payload.get("worker_id"),
        "worker_device": payload.get("worker_device"),
        "remote_address": bounded(remote_address),
        "prior_result_path": str(prior_result_path) if prior_result_path else None,
        "duplicate_status": "duplicate_return_rejected",
        "final_decision": DUPLICATE_FINAL_DECISION,
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "safe_to_auto_apply": False,
    }
    duplicate_path.write_text(json.dumps(duplicate_record, indent=2), encoding="utf-8")
    text = f"""# Remote Worker Duplicate Return Guard Receipt

- timestamp: `{timestamp}`
- packet_id: `{bounded(payload.get("packet_id"), 160)}`
- worker_id: `{bounded(payload.get("worker_id"), 80)}`
- worker_device: `{bounded(payload.get("worker_device"), 80)}`
- remote address: `{bounded(remote_address)}`
- prior_result_path: `{prior_result_path}`
- duplicate_record_path: `{duplicate_path}`
- final decision: `{DUPLICATE_FINAL_DECISION}`

DUPLICATE RETURN REJECTED - NOT APPLIED.

This receipt is bounded evidence only. It does not execute, apply, promote, route, queue, trust, or write trusted memory from worker output.
"""
    receipt_path.write_text(text, encoding="utf-8")
    return duplicate_path, receipt_path


def return_result_response(
    payload: Any,
    remote_address: str = "local",
    *,
    claimed_dir: Path = CLAIMED_ASSIGNMENTS_DIR,
    returned_dir: Path = RETURNED_ASSIGNMENTS_DIR,
    report_dir: Path = AUTO_REPORT_DIR,
    duplicate_dir: Path = DUPLICATE_RETURNS_DIR,
    duplicate_report_dir: Path = DUPLICATE_GUARD_REPORT_DIR,
    require_claim: bool = True,
) -> tuple[int, dict[str, Any]]:
    bridged = rust_bridge_return_result_response(payload, remote_address)
    if bridged is not None:
        return bridged

    errors = validate_returned_result(payload)
    if errors:
        return 400, {"accepted": False, "errors": errors[:10], "final_decision": AUTO_FINAL_DECISION}
    assert isinstance(payload, dict)
    claim = matching_claim(
        payload.get("packet_id"),
        str(payload.get("worker_id", "")),
        str(payload.get("worker_device", "")),
        claimed_dir,
    )
    if require_claim and claim is None:
        return 409, {
            "accepted": False,
            "status": "return_rejected",
            "error": "no matching claim for returned result",
            "final_decision": AUTO_FINAL_DECISION,
            "direct_control": False,
            "trusted_memory_write": False,
            "auto_apply": False,
        }
    prior_result_path: Path | None = None
    for path, result in records_with_packet_id(returned_dir, payload.get("packet_id")):
        if canonical_id(result.get("worker_id")) == canonical_id(payload.get("worker_id")):
            prior_result_path = path
            break
    if prior_result_path is not None:
        duplicate_path, duplicate_receipt_path = write_duplicate_return_rejection(
            payload,
            remote_address=remote_address,
            prior_result_path=prior_result_path,
            duplicate_dir=duplicate_dir,
            report_dir=duplicate_report_dir,
        )
        return 409, {
            "accepted": False,
            "status": "duplicate_return_rejected",
            "error": "duplicate return rejected - review-only",
            "duplicate_record_path": str(duplicate_path),
            "duplicate_receipt_path": str(duplicate_receipt_path),
            "prior_result_path": str(prior_result_path),
            "final_decision": DUPLICATE_FINAL_DECISION,
            "direct_control": False,
            "trusted_memory_write": False,
            "auto_apply": False,
        }
    result_path, receipt_path = store_returned_result(
        payload,
        remote_address=remote_address,
        returned_dir=returned_dir,
        report_dir=report_dir,
    )
    return 200, {
        "accepted": True,
        "mode": "untrusted_result_return_only",
        "returned_result_path": str(result_path),
        "receipt_path": str(receipt_path),
        "final_decision": AUTO_FINAL_DECISION,
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
    }


def safe_id(value: Any) -> str:
    text = bounded(value, 64).lower()
    cleaned = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in text)
    return cleaned.strip("_") or "unknown"


def timestamp_file(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("Z", "Z")


def parse_query(path: str) -> tuple[str, dict[str, str]]:
    route, sep, query = path.partition("?")
    params: dict[str, str] = {}
    if not sep:
        return route, params
    for part in query.split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        params[key] = value
    return route, params


def validate_bind(host: str, allow_lan: bool) -> tuple[bool, str]:
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if host in local_hosts:
        return True, "localhost bind"
    if allow_lan:
        return True, "explicit LAN bind approved"
    return False, "LAN bind requires --allow-lan"


def bounded(value: Any, limit: int = 120) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ").strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def redact_sensitive_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"(pairing_code=)[^&\s\"]+", r"\1REDACTED", text)
    text = re.sub(r'("pairing_code"\s*:\s*")[^"]+(")', r"\1REDACTED\2", text)
    return text


def write_pairing_receipt(
    *,
    remote_address: str,
    payload: Any,
    response: dict[str, Any],
) -> Path:
    ensure_scaffold()
    timestamp = utc_stamp()
    paired = bool(response.get("paired"))
    suffix = "paired" if paired else "blocked"
    path = REPORT_DIR / f"REMOTE_WORKER_LAN_PAIRING_{timestamp.replace(':', '').replace('-', '')}_{suffix}.md"
    worker_device = payload.get("worker_device") if isinstance(payload, dict) else None
    client_mode = payload.get("client_mode") if isinstance(payload, dict) else None
    text = f"""# Remote Worker LAN Pairing Receipt

- timestamp: `{timestamp}`
- remote address: `{bounded(remote_address)}`
- request type: `pair`
- paired: `{str(paired).lower()}`
- worker_device: `{bounded(worker_device)}`
- client_mode: `{bounded(client_mode)}`
- safety mode: `status_only`
- final decision: `{FINAL_DECISION}`

This receipt is bounded metadata only. It does not include the full pairing token or arbitrary request payload.
It does not transfer packets, upload results, execute commands, control Engel, mutate source/routes/queues, or write trusted memory.
"""
    path.write_text(text, encoding="utf-8")
    return path


class PairingRequestHandler(BaseHTTPRequestHandler):
    server_version = "EngelLanPairing/1"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {redact_sensitive_text(format % args)}")

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route, params = parse_query(self.path)
        if route == "/health":
            self.send_json(200, health_response())
            return
        if route in ("/worker/status", "/worker/next-assignment"):
            worker_id = params.get("worker_id", EXPECTED_WORKER_ID)
            worker_device = params.get("worker_device", "")
            remote_address = str(self.client_address[0])
            status, response = validate_pairing_auth(
                params.get("pairing_code", ""),
                worker_device,
                worker_id=worker_id,
            )
            if status != 200:
                status, response = validate_existing_worker_session(worker_device, worker_id, remote_address)
                if status != 200:
                    self.send_json(401, response)
                    return
            update_link_manager_seen(
                {
                    "worker_device": worker_device,
                    "worker_id": worker_id,
                    "current_mode": "foreground_worker_request",
                },
                remote_address,
            )
            if route == "/worker/status":
                self.send_json(200, worker_status_response())
                return
            next_status, next_response = next_assignment_response(
                worker_id=worker_id,
                worker_device=worker_device or EXPECTED_WORKER_DEVICE,
            )
            self.send_json(next_status, next_response)
            return
        if route in ("/system/stats", "/media/latest"):
            auth_status, auth_resp = validate_pairing_auth(
                params.get("pairing_code", ""),
                params.get("worker_device", "engel_remote_worker_flutter"),
            )
            if auth_status != 200:
                self.send_json(401, auth_resp)
                return
            if route == "/system/stats":
                try:
                    import engel_system_monitor as _mon
                    self.send_json(200, {"ok": True, "stats": _mon.system_stats()})
                except Exception as exc:
                    self.send_json(200, {"ok": False, "error": str(exc), "stats": {}})
                return
            # /media/latest
            try:
                import engel_system_monitor as _mon
                media = _mon.latest_media()
                if media is None:
                    self.send_json(200, {"ok": True, "media": None})
                else:
                    self.send_json(200, {"ok": True, "media": media})
            except Exception as exc:
                self.send_json(200, {"ok": False, "error": str(exc), "media": None})
            return
        if route != "/health":
            self.send_json(404, {"error": "unknown endpoint"})
            return

    def do_POST(self) -> None:
        if self.path not in ("/pair", "/worker/return-result", "/chat", "/system/limp"):
            self.send_json(404, {"error": "unknown endpoint"})
            return
        length_text = self.headers.get("Content-Length", "0")
        try:
            length = int(length_text)
        except ValueError:
            self.send_json(400, {"error": "invalid content length"})
            return
        max_bytes = MAX_RESULT_BYTES if self.path == "/worker/return-result" else MAX_REQUEST_BYTES
        if length <= 0 or length > max_bytes:
            self.send_json(413, {"error": "request too large or empty"})
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "invalid JSON"})
            return
        if self.path == "/pair":
            status, response = validate_pair_payload(payload)
            if status != 200 and isinstance(payload, dict):
                status, response = validate_existing_worker_session(
                    str(payload.get("worker_device", "")),
                    str(payload.get("worker_id", EXPECTED_WORKER_ID)),
                    str(self.client_address[0]),
                )
            write_pairing_receipt(
                remote_address=str(self.client_address[0]),
                payload=payload,
                response=response,
            )
            if status == 200 and isinstance(payload, dict):
                update_link_manager_seen(payload, str(self.client_address[0]))
            self.send_json(status, response)
            return

        status, response = validate_pairing_auth(
            str(payload.get("pairing_code", "")) if isinstance(payload, dict) else "",
            str(payload.get("worker_device", "")) if isinstance(payload, dict) else "",
            worker_id=str(payload.get("worker_id", EXPECTED_WORKER_ID)) if isinstance(payload, dict) else EXPECTED_WORKER_ID,
        )
        if status != 200:
            status, response = validate_existing_worker_session(
                str(payload.get("worker_device", "")) if isinstance(payload, dict) else "",
                str(payload.get("worker_id", EXPECTED_WORKER_ID)) if isinstance(payload, dict) else EXPECTED_WORKER_ID,
                str(self.client_address[0]),
            )
            if status != 200:
                self.send_json(401, response)
                return
        update_link_manager_seen(payload if isinstance(payload, dict) else None, str(self.client_address[0]))

        if self.path == "/system/limp":
            enabled_raw = payload.get("enabled", None) if isinstance(payload, dict) else None
            if not isinstance(enabled_raw, bool):
                self.send_json(400, {"error": "enabled field (bool) required"})
                return
            try:
                import engel_system_monitor as _mon
                result = _mon.set_limp(enabled_raw)
                self.send_json(200, result)
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return

        if self.path == "/chat":
            user_text = str(payload.get("message", "")).strip() if isinstance(payload, dict) else ""
            if not user_text:
                self.send_json(400, {"error": "message field required"})
                return
            reply = ""
            cb = _CHAT_CALLBACK
            if cb is not None:
                try:
                    reply = str(cb(user_text) or "")
                except Exception as exc:
                    reply = f"[Engel chat error: {exc}]"
            if not reply:
                reply = "I'm here. (Local companion mode — no AI connected.)"
            self.send_json(200, {
                "ok": True,
                "response": reply,
                "source": "engel_local",
                "untrusted": True,
            })
            return

        result_status, result_response = return_result_response(
            payload,
            remote_address=str(self.client_address[0]),
        )
        self.send_json(result_status, result_response)


def render_status() -> str:
    return json.dumps(status_payload(), indent=2)


def render_token() -> str:
    session = create_pairing_session()
    return json.dumps(
        {
            "pairing_code": session.pairing_code,
            "created_at_utc": session.created_at_utc,
            "expires_at_utc": session.expires_at_utc,
            "ttl_seconds": TOKEN_TTL_SECONDS,
            "mode": "pairing_status_only",
            "no_control_granted": True,
        },
        indent=2,
    )


def render_lan_pairing_status() -> str:
    """Markdown view of the LAN pairing server session state."""
    sp = status_payload()
    session = load_pairing_session()
    token_status = sp.get("token_status", "missing")
    token_hint = sp.get("token_hint") or "(none)"
    expires = sp.get("token_expires_at_utc") or "N/A"

    lm = sp.get("link_manager", {})
    last_seen = lm.get("last_seen_utc") if isinstance(lm, dict) else None
    auto_enabled = lm.get("auto_worker_enabled", False) if isinstance(lm, dict) else False

    lines = [
        "# Engel LAN Pairing Server -- Status",
        "",
        f"  Host:          {sp.get('default_host', '127.0.0.1')}:{sp.get('default_port', DEFAULT_PORT)}",
        f"  Token status:  {token_status}",
        f"  Token hint:    {token_hint}",
        f"  Expires:       {expires}",
        f"  TTL:           {TOKEN_TTL_SECONDS // 60} minutes",
        "",
        "## Safety",
        "  Mode:           pairing + status only",
        "  Direct control: NO",
        "  Auto apply:     NO",
        "  Trusted writes: NO",
        "",
        "## Link Manager",
        f"  Auto worker:    {'enabled' if auto_enabled else 'disabled'}",
        f"  Last seen:      {last_seen or 'never'}",
        "",
        "## Commands",
        "  Generate new pairing token:  engel lan pairing token",
        "  Start server (localhost):    python engel_remote_worker_lan_pairing.py serve",
        "  Start server (LAN):          python engel_remote_worker_lan_pairing.py serve --lan",
    ]
    return "\n".join(lines)


def render_lan_pairing_token() -> str:
    """Generate a new pairing token and return a Markdown view."""
    session = create_pairing_session()
    ttl_min = TOKEN_TTL_SECONDS // 60
    lines = [
        "# Engel LAN Pairing -- New Token",
        "",
        f"  Pairing code:  {session.pairing_code}",
        f"  Created:       {session.created_at_utc}",
        f"  Expires:       {session.expires_at_utc}",
        f"  Valid for:     {ttl_min} minutes",
        "",
        "  Mode: pairing_status_only -- no control granted",
        "",
        "Show this code on the Engel Remote Worker app on the phone.",
        "The phone uses this code to pair with the LAN pairing server.",
        "",
        "Start server:  python engel_remote_worker_lan_pairing.py serve --lan",
    ]
    return "\n".join(lines)


UDP_DISCOVERY_PORT_OFFSET = 1  # broadcasts on tcp_port + 1 (default 8766)


def udp_discovery_targets() -> list[str]:
    targets = ["255.255.255.255"]
    try:
        import ipaddress
        import socket as _socket

        hostname = _socket.gethostname()
        private_prefixes = (24, 23, 22, 21, 20, 16)
        for _family, _type, _proto, _canon, sockaddr in _socket.getaddrinfo(hostname, None, _socket.AF_INET):
            ip = str(sockaddr[0])
            if ip.startswith("127."):
                continue
            address = ipaddress.ip_address(ip)
            prefixes = private_prefixes if address.is_private else (24,)
            for prefix in prefixes:
                network = ipaddress.ip_network(ip + f"/{prefix}", strict=False)
                broadcast = str(network.broadcast_address)
                if broadcast not in targets:
                    targets.append(broadcast)
    except Exception:
        pass
    return targets


def _udp_broadcast_loop(tcp_port: int, interval: float = 3.0) -> None:
    import socket as _socket
    import time as _time

    udp_port = tcp_port + UDP_DISCOVERY_PORT_OFFSET
    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_BROADCAST, 1)
    sock.settimeout(2)
    while True:
        try:
            session = get_or_create_session()
            if session and not session.is_expired():
                payload = json.dumps({
                    "engel": 1,
                    "port": tcp_port,
                    "pairing_code": session.pairing_code,
                }).encode("utf-8")
                for target in udp_discovery_targets():
                    sock.sendto(payload, (target, udp_port))
                    if target == "255.255.255.255":
                        sock.sendto(payload, ("255.255.255.255", udp_port))
        except Exception:
            pass
        _time.sleep(interval)


def start_udp_broadcaster(tcp_port: int) -> None:
    import threading as _threading
    t = _threading.Thread(
        target=_udp_broadcast_loop,
        args=(tcp_port,),
        daemon=True,
        name="engel-udp-discovery",
    )
    t.start()


def run_server(host: str, port: int, allow_lan: bool) -> int:
    ensure_scaffold()
    ok, reason = validate_bind(host, allow_lan)
    if not ok:
        print(reason)
        return 2
    server = ThreadingHTTPServer((host, port), PairingRequestHandler)
    start_udp_broadcaster(port)
    print(f"Engel LAN pairing receiver listening on {host}:{port}")
    print(f"UDP discovery broadcasting on port {port + UDP_DISCOVERY_PORT_OFFSET}")
    print("Mode: pairing/status only. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Engel LAN pairing receiver.")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel Remote Worker LAN pairing/status receiver.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("token")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default=DEFAULT_HOST)
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve.add_argument("--allow-lan", action="store_true")
    serve.add_argument("--lan", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "status":
        print(render_status())
        return 0
    if args.command == "token":
        print(render_token())
        return 0
    if args.command == "serve":
        host = "0.0.0.0" if args.lan else args.host
        allow_lan = bool(args.allow_lan or args.lan)
        return run_server(host, args.port, allow_lan)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
