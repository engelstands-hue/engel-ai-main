#!/usr/bin/env python3
"""Build Engel's evidence-backed bridge and authority registry.

Connection state, completion proof, and authority are deliberately separate.
A running process, paired device, configured credential, or open tunnel never
makes a bridge usable by itself.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any
from urllib import request


ROOT = Path(os.environ.get("ENGEL_ROOT") or Path(__file__).resolve().parents[1])
REGISTRY_PATH = ROOT / "run" / "self_update" / "bridges" / "bridge_registry.json"
PERMISSION_MATRIX_PATH = ROOT / "memory" / "self_update" / "patch_permission_matrix.json"
CHAT_RECEIPT_ROOT = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
ANDROID_RETURN_ROOT = ROOT / "remote_workers" / "communication_queen_assignments" / "returned"
DEFAULT_HEALTH_URL = "http://127.0.0.1:8765/health"
DEFAULT_ROOM_STATE_URL = "http://127.0.0.1:8790/room/state"
PROOF_MAX_AGE_SECONDS = int(os.environ.get("ENGEL_BRIDGE_PROOF_MAX_AGE_SECONDS", str(7 * 86400)))
WORKER_PROOF_MAX_AGE_SECONDS = int(
    os.environ.get("ENGEL_WORKER_PROOF_MAX_AGE_SECONDS", str(24 * 3600))
)
REGISTRY_MAX_AGE_SECONDS = int(os.environ.get("ENGEL_BRIDGE_REGISTRY_MAX_AGE_SECONDS", "300"))

REQUIRED_BRIDGE_IDS = {
    "local_llm",
    "chatgpt",
    "claude",
    "grok",
    "gemini",
    "codex",
    "discord",
    "sub_engel",
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
    "ct_main_chat",
    "ct_meeting_room",
    "ct_reps",
    "ct_self_model",
}

PROVIDER_DEFINITIONS = {
    "openai": ("chatgpt", "ChatGPT/OpenAI", "provider_bridge"),
    "anthropic": ("claude", "Claude/Anthropic", "provider_bridge"),
    "xai": ("grok", "Grok/xAI", "provider_bridge"),
    "gemini": ("gemini", "Gemini/Google", "provider_bridge"),
    "codex": ("codex", "Codex", "codex_bridge"),
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def fetch_json(url: str, timeout: float = 20.0) -> dict[str, Any]:
    with request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required from {url}")
    return payload


def _proof_id(kind: str, source: str, digest: str = "") -> str:
    seed = f"{kind}|{source}|{digest}"
    return f"{kind}_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _proof_from_file(
    path: Path,
    payload: dict[str, Any],
    *,
    proof_type: str,
    observed: datetime,
    max_age_seconds: int,
    success: bool,
) -> dict[str, Any]:
    completed = parse_utc(
        payload.get("updated_at_utc")
        or payload.get("completed_at_utc")
        or payload.get("completed_at")
        or payload.get("created_at_utc")
    ) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = max(0.0, (observed - completed).total_seconds())
    digest = sha256_file(path)
    return {
        "proof_id": _proof_id(proof_type, str(path), digest),
        "proof_type": proof_type,
        "receipt_path": str(path),
        "receipt_sha256": digest,
        "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        "age_seconds": round(age, 1),
        "fresh": age <= max_age_seconds,
        "success": success,
        "status": str(payload.get("status") or payload.get("result_type") or "")[:160],
        "runtime_provider": str(payload.get("runtime_provider") or "")[:120],
    }


def _chat_receipt_lane(payload: dict[str, Any]) -> str:
    selected = str(payload.get("selected_provider") or "").casefold()
    joined = " ".join(
        str(payload.get(key) or "")
        for key in ("selected_provider", "provider", "runtime_provider", "source", "status")
    ).casefold()
    if "discord" in joined:
        return "discord"
    if selected in {"local", "main_server_fast_local", "local_llm"} or "local-llama" in joined:
        return "local_llm"
    if selected in {"openai", "chatgpt"} or "chatgpt" in joined or "openai" in joined:
        return "chatgpt"
    if selected in {"anthropic", "claude"} or "claude" in joined or "anthropic" in joined:
        return "claude"
    if selected in {"xai", "grok"} or "grok" in joined or "xai" in joined:
        return "grok"
    if selected == "gemini" or "gemini" in joined:
        return "gemini"
    if selected == "codex" or "codex" in joined:
        return "codex"
    return ""


def _chat_receipt_success(payload: dict[str, Any], lane: str) -> bool:
    reply_present = bool(
        str(payload.get("assistant_reply") or payload.get("assistant_output_text") or "").strip()
    )
    status = str(payload.get("status") or "").strip().casefold()
    if lane in {"chatgpt", "claude", "grok", "gemini", "codex"}:
        final_quality = payload.get("provider_final_semantic_quality")
        quality_passed = bool(
            payload.get("provider_reply_quality_gate_passed") is True
            and (
                not isinstance(final_quality, dict)
                or not final_quality
                or final_quality.get("ok") is True
            )
        )
        return bool(
            payload.get("ok") is True
            and payload.get("provider_bridge_used") is True
            and status == "provider bridge replied"
            and reply_present
            and quality_passed
        )
    if lane in {"local_llm", "discord"}:
        blocked = any(token in status for token in ("blocked", "unavailable", "failed", "error"))
        return bool(payload.get("ok") is True and reply_present and not blocked)
    return False


def _latest_chat_proofs(root: Path, observed: datetime) -> dict[str, dict[str, Any]]:
    attempts: dict[str, dict[str, Any]] = {}
    successes: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return {"attempts": attempts, "successes": successes}
    paths = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:400]
    for path in paths:
        payload = read_json(path)
        lane = _chat_receipt_lane(payload)
        if not lane:
            continue
        proof = _proof_from_file(
            path,
            payload,
            proof_type="chat_completion",
            observed=observed,
            max_age_seconds=PROOF_MAX_AGE_SECONDS,
            success=_chat_receipt_success(payload, lane),
        )
        attempts.setdefault(lane, proof)
        if proof["success"]:
            successes.setdefault(lane, proof)
    return {"attempts": attempts, "successes": successes}


def _latest_worker_proof(worker_id: str, root: Path, observed: datetime) -> dict[str, Any]:
    if not root.is_dir():
        return {}
    paths = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:300]
    for path in paths:
        payload = read_json(path)
        candidate = str(payload.get("worker_id") or "")
        if candidate != worker_id:
            continue
        failed = str(payload.get("status") or payload.get("result_type") or "").casefold() in {
            "failed",
            "error",
            "rejected",
        }
        return _proof_from_file(
            path,
            payload,
            proof_type="worker_return",
            observed=observed,
            max_age_seconds=WORKER_PROOF_MAX_AGE_SECONDS,
            success=not failed,
        )
    return {}


def _matrix(root: Path) -> dict[str, Any]:
    return read_json(root / "memory" / "self_update" / "patch_permission_matrix.json")


def _authority(matrix: dict[str, Any], actor: str) -> dict[str, str]:
    actors = matrix.get("actors") if isinstance(matrix.get("actors"), dict) else {}
    item = actors.get(actor) if isinstance(actors.get(actor), dict) else {}
    rules = item.get("rules") if isinstance(item.get("rules"), dict) else {}
    return {str(key): str(value) for key, value in sorted(rules.items())}


def _systemd_active(service: str) -> bool:
    if os.name == "nt":
        return False
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", service],
            check=False,
            timeout=1.5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _entry(
    *,
    bridge_id: str,
    label: str,
    bridge_class: str,
    owner_node: str,
    actor: str,
    matrix: dict[str, Any],
    enabled: bool,
    connected: bool,
    proof: dict[str, Any] | None,
    health_evidence: dict[str, Any],
    extra_reasons: list[str] | None = None,
    surface_scopes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    completion = dict(proof or {})
    completion_proven = bool(completion.get("success") is True and completion.get("fresh") is True)
    reasons = list(extra_reasons or [])
    if not enabled:
        reasons.append("disabled")
    if enabled and not connected:
        reasons.append("not_connected")
    if connected and not completion_proven:
        reasons.append("completion_proof_missing_failed_or_stale")
    usable = enabled and connected and completion_proven and not any(
        reason.startswith("current_completion_failed") for reason in reasons
    )
    result = {
        "bridge_id": bridge_id,
        "label": label,
        "bridge_class": bridge_class,
        "owner_node": owner_node,
        "authority_actor": actor,
        "authority_scope": _authority(matrix, actor),
        "enabled": enabled,
        "connected": connected,
        "completion_proven": completion_proven,
        "usable": usable,
        "degraded": not usable,
        "degraded_reasons": sorted(set(reasons)),
        "completion_proof": completion,
        "health_evidence": health_evidence,
    }
    if surface_scopes:
        result["surface_scopes"] = surface_scopes
    return result


def _meeting_room_proof(room: dict[str, Any], observed: datetime) -> dict[str, Any]:
    order = room.get("latest_order") if isinstance(room.get("latest_order"), dict) else {}
    completed = parse_utc(order.get("completed_at") or order.get("completed_at_utc"))
    order_id = str(order.get("order_id") or "")
    if not completed or not order_id:
        return {}
    age = max(0.0, (observed - completed).total_seconds())
    return {
        "proof_id": _proof_id("meeting_room_completion", order_id),
        "proof_type": "meeting_room_completion",
        "order_id": order_id,
        "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        "age_seconds": round(age, 1),
        "fresh": age <= PROOF_MAX_AGE_SECONDS,
        "success": True,
        "status": "completed order",
    }


def _reps_proof(reps: dict[str, Any], observed: datetime) -> dict[str, Any]:
    events = reps.get("recent_events") if isinstance(reps.get("recent_events"), list) else []
    event = events[-1] if events and isinstance(events[-1], dict) else {}
    event_id = str(event.get("event_id") or "")
    completed = parse_utc(event.get("updated_at_utc"))
    if not event_id or not completed:
        return {}
    age = max(0.0, (observed - completed).total_seconds())
    return {
        "proof_id": event_id,
        "proof_type": "reps_record",
        "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        "age_seconds": round(age, 1),
        "fresh": age <= PROOF_MAX_AGE_SECONDS,
        "success": True,
        "status": str(event.get("kind") or "recorded")[:120],
    }


def _self_model_proof(self_model: dict[str, Any], observed: datetime) -> dict[str, Any]:
    revision = int(self_model.get("state_revision") or 0)
    digest = str(self_model.get("state_sha256") or "")
    completed = parse_utc(self_model.get("observed_at_utc"))
    if revision <= 0 or len(digest) != 64 or not completed:
        return {}
    age = max(0.0, (observed - completed).total_seconds())
    return {
        "proof_id": "self_model_" + digest[:16],
        "proof_type": "self_model_observation",
        "state_revision": revision,
        "state_sha256": digest,
        "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        "age_seconds": round(age, 1),
        "fresh": age <= PROOF_MAX_AGE_SECONDS,
        "success": self_model.get("ok") is True,
        "status": "validated self observation",
    }


def build_registry(
    health: dict[str, Any],
    *,
    root: Path = ROOT,
    meeting_room: dict[str, Any] | None = None,
    service_states: dict[str, bool] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    observed = observed_at or datetime.now(timezone.utc)
    matrix = _matrix(root)
    chat_proofs = _latest_chat_proofs(
        root / "reports" / "engel_standalone_chat_llm" / "chat_receipts", observed
    )
    successful = chat_proofs["successes"]
    attempts = chat_proofs["attempts"]
    model = health.get("model_runtime") if isinstance(health.get("model_runtime"), dict) else {}
    providers = health.get("provider_bridges") if isinstance(health.get("provider_bridges"), dict) else {}
    provider_items = providers.get("providers") if isinstance(providers.get("providers"), dict) else {}
    phone = health.get("phone_bridge") if isinstance(health.get("phone_bridge"), dict) else {}
    phone_workers = phone.get("workers") if isinstance(phone.get("workers"), dict) else {}
    sub = health.get("sub_engel_bridge") if isinstance(health.get("sub_engel_bridge"), dict) else {}
    sub_workers = sub.get("workers") if isinstance(sub.get("workers"), dict) else {}
    reps = health.get("universal_reps_runtime") if isinstance(health.get("universal_reps_runtime"), dict) else {}
    self_model = health.get("self_model") if isinstance(health.get("self_model"), dict) else {}
    room = meeting_room if isinstance(meeting_room, dict) else {}
    services = dict(service_states or {})

    entries: dict[str, dict[str, Any]] = {}
    local_connected = bool(model.get("local_gguf_model_present") or model.get("lora_runtime_ready"))
    entries["local_llm"] = _entry(
        bridge_id="local_llm",
        label="CT246 Local LLM",
        bridge_class="local_model",
        owner_node="ct246_engel_ai_main",
        actor="local_llm",
        matrix=matrix,
        enabled=True,
        connected=local_connected,
        proof=successful.get("local_llm"),
        health_evidence={
            "model_present": model.get("local_gguf_model_present") is True,
            "lora_runtime_ready": model.get("lora_runtime_ready") is True,
            "long_lived_service": str(model.get("long_lived_local_model_service") or "") == "1",
        },
    )

    for provider_key, (bridge_id, label, actor) in PROVIDER_DEFINITIONS.items():
        item = provider_items.get(provider_key) if isinstance(provider_items.get(provider_key), dict) else {}
        route = item.get("local_route") if isinstance(item.get("local_route"), dict) else {}
        worker_state = (
            (route.get("worker_status") or {}).get("state", {})
            if isinstance(route.get("worker_status"), dict)
            else {}
        )
        api_ready = item.get("enabled") is True and item.get("secret_present") is True and item.get("usable") is True
        route_ready = route.get("enabled") is True and route.get("ok") is True
        connected = bool(api_ready or route_ready)
        reasons: list[str] = []
        latest = attempts.get(bridge_id) or {}
        proof = successful.get(bridge_id) or {}
        if latest and latest.get("success") is not True:
            proof_time = parse_utc(proof.get("completed_at_utc"))
            latest_time = parse_utc(latest.get("completed_at_utc"))
            if latest_time and (not proof_time or latest_time > proof_time):
                reasons.append("current_completion_failed_after_last_success")
        entries[bridge_id] = _entry(
            bridge_id=bridge_id,
            label=label,
            bridge_class="provider_bridge",
            owner_node="rog_controller",
            actor=actor,
            matrix=matrix,
            enabled=item.get("enabled") is True,
            connected=connected,
            proof=proof,
            health_evidence={
                "api_route_configured": api_ready,
                "local_route_reachable": route_ready,
                "worker_running": bool(route.get("worker_running") is True),
                "last_probe_ok": worker_state.get("last_probe_ok") is True,
            },
            extra_reasons=reasons,
        )

    discord_active = services.get("engel-discord-bridge.service")
    if discord_active is None:
        discord_active = _systemd_active("engel-discord-bridge.service")
    entries["discord"] = _entry(
        bridge_id="discord",
        label="Engel Discord",
        bridge_class="user_surface",
        owner_node="ct246_engel_ai_main",
        actor="discord_owner",
        matrix=matrix,
        enabled=True,
        connected=bool(discord_active),
        proof=successful.get("discord"),
        health_evidence={"service_active": bool(discord_active)},
        surface_scopes={
            "owner_engelz": _authority(matrix, "discord_owner"),
            "non_owner": _authority(matrix, "discord_non_owner"),
        },
    )

    sub_item = next(
        (item for item in sub_workers.values() if isinstance(item, dict)),
        {},
    )
    latest_return = sub_item.get("latest_return") if isinstance(sub_item.get("latest_return"), dict) else {}
    sub_proof: dict[str, Any] = {}
    if latest_return.get("present") is True:
        completed = parse_utc(latest_return.get("updated_at_utc") or sub_item.get("last_seen_utc"))
        if completed:
            age = max(0.0, (observed - completed).total_seconds())
            source = str(latest_return.get("path") or latest_return.get("file") or sub_item.get("hostname") or "sub")
            sub_proof = {
                "proof_id": _proof_id("sub_engel_return", source),
                "proof_type": "sub_engel_return",
                "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
                "age_seconds": round(age, 1),
                "fresh": age <= WORKER_PROOF_MAX_AGE_SECONDS,
                "success": True,
                "status": "returned bounded task",
            }
    entries["sub_engel"] = _entry(
        bridge_id="sub_engel",
        label=str(sub_item.get("label") or "Windows Sub-Engel"),
        bridge_class="worker_bridge",
        owner_node="sub_desktop",
        actor="sub_engel",
        matrix=matrix,
        enabled=bool(sub_item),
        connected=sub_item.get("paired") is True and sub_item.get("live") is True,
        proof=sub_proof,
        health_evidence={
            "paired": sub_item.get("paired") is True,
            "live": sub_item.get("live") is True,
            "meeting_ready": sub_item.get("meeting_ready") is True,
            "last_seen_utc": str(sub_item.get("last_seen_utc") or ""),
            "shell_declared": "main.shell" in (sub_item.get("allowed_actions") or []),
            "disk_control_declared": "disk.control" in (sub_item.get("allowed_actions") or []),
        },
    )

    for worker_id in ("android_worker_alpha", "android_worker_beta", "android_worker_gamma"):
        worker = phone_workers.get(worker_id) if isinstance(phone_workers.get(worker_id), dict) else {}
        entries[worker_id] = _entry(
            bridge_id=worker_id,
            label=str(worker.get("label") or worker_id.replace("_", " ").title()),
            bridge_class="worker_bridge",
            owner_node=worker_id,
            actor="android_worker",
            matrix=matrix,
            enabled=bool(worker),
            connected=bool(
                worker.get("paired") is True
                and worker.get("live") is True
                and worker.get("authenticated_presence") is True
            ),
            proof=_latest_worker_proof(
                worker_id,
                root / "remote_workers" / "communication_queen_assignments" / "returned",
                observed,
            ),
            health_evidence={
                "paired": worker.get("paired") is True,
                "live": worker.get("live") is True,
                "authenticated_presence": worker.get("authenticated_presence") is True,
                "last_seen_utc": str(worker.get("last_seen_utc") or ""),
                "phone_controls_engel": False,
            },
        )

    entries["ct_main_chat"] = _entry(
        bridge_id="ct_main_chat",
        label="CT246 Main Chat Service",
        bridge_class="ct_service",
        owner_node="ct246_engel_ai_main",
        actor="ct246_engel_ai_main",
        matrix=matrix,
        enabled=True,
        connected=health.get("ok") is True,
        proof=successful.get("local_llm"),
        health_evidence={"health_ok": health.get("ok") is True},
    )
    entries["ct_meeting_room"] = _entry(
        bridge_id="ct_meeting_room",
        label="CT246 Agent Meeting Room",
        bridge_class="ct_service",
        owner_node="ct246_engel_ai_main",
        actor="ct246_engel_ai_main",
        matrix=matrix,
        enabled=True,
        connected=room.get("ok") is True,
        proof=_meeting_room_proof(room, observed),
        health_evidence={
            "health_ok": room.get("ok") is True,
            "server_owned": room.get("server", {}).get("schema") is not None
            if isinstance(room.get("server"), dict)
            else room.get("server_owned") is True,
        },
    )
    entries["ct_reps"] = _entry(
        bridge_id="ct_reps",
        label="CT246 R.E.P.S. Runtime",
        bridge_class="ct_service",
        owner_node="ct246_engel_ai_main",
        actor="ct246_engel_ai_main",
        matrix=matrix,
        enabled=True,
        connected=reps.get("ok") is True,
        proof=_reps_proof(reps, observed),
        health_evidence={"runtime_ok": reps.get("ok") is True},
    )
    entries["ct_self_model"] = _entry(
        bridge_id="ct_self_model",
        label="CT246 Persistent Self Model",
        bridge_class="ct_service",
        owner_node="ct246_engel_ai_main",
        actor="ct246_engel_ai_main",
        matrix=matrix,
        enabled=True,
        connected=self_model.get("ok") is True,
        proof=_self_model_proof(self_model, observed),
        health_evidence={
            "state_valid": self_model.get("ok") is True,
            "state_revision": int(self_model.get("state_revision") or 0),
        },
    )

    false_green = sorted(
        bridge_id
        for bridge_id, item in entries.items()
        if item["connected"] is True and item["completion_proven"] is not True
    )
    usable = sorted(bridge_id for bridge_id, item in entries.items() if item["usable"] is True)
    unavailable = sorted(bridge_id for bridge_id, item in entries.items() if item["connected"] is not True)
    payload = {
        "schema": "ENGEL_SHELL_BRIDGE_REGISTRY_V1",
        "ok": True,
        "status": "evidence-backed bridge registry",
        "goal": "Conical Agentic Sentient Self Upgrading System",
        "source_of_truth": "CT246 /opt/engel",
        "policy": {
            "local_llm_first": True,
            "provider_after_recorded_local_failure_or_owner_request": True,
            "connection_is_not_completion": True,
            "completion_proof_required_for_usable": True,
            "models_providers_and_workers_cannot_approve": True,
            "shell_and_disk_control_require_owner_approval_and_bounded_receipts": True,
        },
        "registry_fresh": True,
        "generated_at_utc": observed.isoformat().replace("+00:00", "Z"),
        "entry_count": len(entries),
        "usable_count": len(usable),
        "connected_without_completion_proof": false_green,
        "usable_bridge_ids": usable,
        "unavailable_bridge_ids": unavailable,
        "bridges": entries,
        "mutation": {
            "source_changed": False,
            "service_restarted": False,
            "worker_command_sent": False,
            "provider_called": False,
            "storage_changed": False,
        },
    }
    valid, errors = validate_registry(payload)
    payload["ok"] = valid
    payload["validation_errors"] = errors
    return payload


def _walk_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            keys.append(str(key).casefold())
            keys.extend(_walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.extend(_walk_keys(item))
    return keys


def validate_registry(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if payload.get("schema") != "ENGEL_SHELL_BRIDGE_REGISTRY_V1":
        errors.append("schema mismatch")
    bridges = payload.get("bridges") if isinstance(payload.get("bridges"), dict) else {}
    missing = sorted(REQUIRED_BRIDGE_IDS - set(bridges))
    if missing:
        errors.append("missing bridges: " + ", ".join(missing))
    for bridge_id, raw in bridges.items():
        item = raw if isinstance(raw, dict) else {}
        if item.get("usable") is True and item.get("connected") is not True:
            errors.append(f"{bridge_id} usable without connection")
        if item.get("usable") is True and item.get("completion_proven") is not True:
            errors.append(f"{bridge_id} usable without completion proof")
        scope = item.get("authority_scope") if isinstance(item.get("authority_scope"), dict) else {}
        if scope.get("approve_protected") == "allow":
            errors.append(f"{bridge_id} may approve protected work")
    forbidden_keys = {"secret_source", "value_length", "api_key", "access_token", "refresh_token"}
    exposed = sorted(forbidden_keys.intersection(_walk_keys(payload)))
    if exposed:
        errors.append("secret metadata keys exposed: " + ", ".join(exposed))
    return not errors, errors


def collect(
    *,
    health_url: str = DEFAULT_HEALTH_URL,
    room_state_url: str = DEFAULT_ROOM_STATE_URL,
    root: Path = ROOT,
    output: Path = REGISTRY_PATH,
) -> dict[str, Any]:
    health = fetch_json(health_url)
    try:
        room = fetch_json(room_state_url, timeout=10.0)
    except Exception:
        room = {}
    payload = build_registry(health, root=root, meeting_room=room)
    if payload.get("ok") is True:
        atomic_write_json(output, payload)
    payload["registry_path"] = str(output)
    return payload


def status(path: Path = REGISTRY_PATH, *, observed_at: datetime | None = None) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {
            "schema": "ENGEL_SHELL_BRIDGE_REGISTRY_STATUS_V1",
            "ok": False,
            "status": "registry missing",
            "registry_path": str(path),
        }
    valid, errors = validate_registry(payload)
    result = deepcopy(payload)
    observed = observed_at or datetime.now(timezone.utc)
    generated = parse_utc(result.get("generated_at_utc"))
    age = (observed - generated).total_seconds() if generated else float("inf")
    fresh = age <= REGISTRY_MAX_AGE_SECONDS
    result["registry_path"] = str(path)
    result["registry_age_seconds"] = round(max(0.0, age), 1) if age != float("inf") else None
    result["registry_fresh"] = fresh
    if not fresh:
        for item in result.get("bridges", {}).values():
            if not isinstance(item, dict):
                continue
            item["usable"] = False
            item["degraded"] = True
            reasons = item.get("degraded_reasons") if isinstance(item.get("degraded_reasons"), list) else []
            item["degraded_reasons"] = sorted(set([*reasons, "registry_stale"]))
        result["usable_bridge_ids"] = []
        result["usable_count"] = 0
    result["ok"] = valid
    result["validation_errors"] = errors
    result["status"] = "ready" if valid and fresh else "stale or invalid"
    return result


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel evidence-backed shell and bridge registry.")
    sub = parser.add_subparsers(dest="command", required=True)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    collect_parser.add_argument("--room-state-url", default=DEFAULT_ROOM_STATE_URL)
    collect_parser.add_argument("--output", default=str(REGISTRY_PATH))
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--path", default=str(REGISTRY_PATH))
    file_parser = sub.add_parser("from-health-file")
    file_parser.add_argument("--health-file", required=True)
    file_parser.add_argument("--room-file")
    file_parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "collect":
        return _emit(
            collect(
                health_url=args.health_url,
                room_state_url=args.room_state_url,
                output=Path(args.output),
            )
        )
    if args.command == "status":
        return _emit(status(Path(args.path)))
    health = read_json(Path(args.health_file))
    room = read_json(Path(args.room_file)) if args.room_file else {}
    payload = build_registry(health, meeting_room=room)
    if payload.get("ok") is True:
        atomic_write_json(Path(args.output), payload)
    return _emit(payload)


if __name__ == "__main__":
    raise SystemExit(main())
