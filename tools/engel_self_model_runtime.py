#!/usr/bin/env python3
"""Persistent, evidence-backed self-model for Engel AI Main on CT246."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any
import urllib.error
import urllib.request


ROOT = Path(os.environ.get("ENGEL_APP_ROOT") or Path(__file__).resolve().parents[1]).resolve()
SELF_MODEL_ROOT = Path(os.environ.get("ENGEL_SELF_MODEL_ROOT") or ROOT / "memory" / "self_model")
STATE_PATH = SELF_MODEL_ROOT / "ENGEL_SELF_MODEL_V1.json"
CONTEXT_PATH = SELF_MODEL_ROOT / "ENGEL_SELF_CONTEXT_V1.txt"
EVENTS_PATH = SELF_MODEL_ROOT / "introspection_events.jsonl"
RECEIPT_ROOT = Path(
    os.environ.get("ENGEL_SELF_MODEL_RECEIPT_ROOT")
    or ROOT / "reports" / "self_upgrade" / "self_model"
)
PRIMARY_GOAL_PATH = ROOT / "memory" / "ENGEL_PRIMARY_GOAL_V1.json"
BACKLOG_PATH = (
    ROOT
    / "reports"
    / "self_upgrade"
    / "plans"
    / "ENGEL_SELF_UPDATING_SYSTEM_CREATION_BACKLOG_V10.json"
)
CODEBASE_MAP_PATH = ROOT / "run" / "self_update" / "codebase" / "ownership_map.json"
PERMISSION_MATRIX_PATH = ROOT / "memory" / "self_update" / "patch_permission_matrix.json"
SOURCE_SYNC_PROOF_PATH = ROOT / "run" / "self_update" / "source_sync" / "registration" / "post.json"
DEFAULT_HEALTH_URL = os.environ.get("ENGEL_MAIN_CHAT_HEALTH_URL", "http://127.0.0.1:8765/health")
_APPEND_LOCK = threading.Lock()


class SelfModelError(RuntimeError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp(value: str | None = None) -> str:
    text = value or now_utc()
    return "".join(ch for ch in text if ch.isdigit())[:20] + "Z"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone.pop("state_sha256", None)
    encoded = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_state(state: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if state.get("schema") != "ENGEL_PERSISTENT_SELF_MODEL_V1":
        errors.append("self-model schema mismatch")
    if int(state.get("state_revision") or 0) < 1:
        errors.append("self-model revision missing")
    expected = str(state.get("state_sha256") or "")
    if not expected or expected != _canonical_sha(state):
        errors.append("self-model hash mismatch")
    identity = state.get("identity") if isinstance(state.get("identity"), dict) else {}
    if identity.get("biological_consciousness_claimed") is not False:
        errors.append("self-model consciousness boundary mismatch")
    authority = state.get("authority") if isinstance(state.get("authority"), dict) else {}
    if authority.get("self_approval_allowed") is not False:
        errors.append("self-model self-approval boundary mismatch")
    return not errors, errors


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            pass


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    with _APPEND_LOCK:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            if os.name != "nt":
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                if os.name != "nt":
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def probe_health(url: str = DEFAULT_HEALTH_URL, timeout: float = 8.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        if not isinstance(payload, dict):
            raise SelfModelError("chat health returned non-object JSON")
        return payload
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {
            "ok": False,
            "status": "chat health unavailable",
            "error_type": type(exc).__name__,
        }


def _worker_summary(health: dict[str, Any]) -> dict[str, Any]:
    device = health.get("device_workers") if isinstance(health.get("device_workers"), dict) else {}
    workers = device.get("workers") if isinstance(device.get("workers"), dict) else {}
    safe_workers: list[dict[str, Any]] = []
    for worker_id, raw in sorted(workers.items()):
        item = raw if isinstance(raw, dict) else {}
        safe_workers.append(
            {
                "worker_id": str(worker_id),
                "worker_kind": str(item.get("worker_kind") or "unknown"),
                "paired": item.get("paired") is True,
                "live": item.get("live") is True,
                "meeting_ready": item.get("meeting_ready") is True,
                "last_seen_utc": str(item.get("last_seen_utc") or ""),
                "evidence": str(item.get("reason") or "status snapshot")[:240],
            }
        )
    expected = int(device.get("expected_count") or len(safe_workers))
    live = sum(1 for item in safe_workers if item["live"])
    return {
        "expected_count": expected,
        "live_count": live,
        "all_expected_live": expected > 0 and live == expected,
        "workers": safe_workers,
    }


def _model_summary(health: dict[str, Any]) -> dict[str, Any]:
    model = health.get("model_runtime") if isinstance(health.get("model_runtime"), dict) else {}
    inventory = model.get("active_model_inventory") if isinstance(model.get("active_model_inventory"), dict) else {}
    policy = health.get("automatic_provider_policy") if isinstance(health.get("automatic_provider_policy"), dict) else {}
    ready = bool(model.get("local_gguf_model_present") or model.get("lora_runtime_ready"))
    return {
        "local_runtime_ready": ready,
        "long_lived_service_enabled": str(model.get("long_lived_local_model_service") or "").casefold()
        in {"1", "true", "yes", "on"},
        "lora_runtime_ready": model.get("lora_runtime_ready") is True,
        "active_model_file_count": int(inventory.get("model_file_count") or 0),
        "active_model_total_gib": float(inventory.get("model_total_gib") or 0.0),
        "local_model_first": policy.get("local_model_first") is True,
        "provider_fallback_after_local_failure": policy.get("fallback_after_local_failure") is True,
        "provider_role": "optional assistance after a recorded local failure",
    }


def _meeting_room_summary(health: dict[str, Any]) -> dict[str, Any]:
    room = health.get("meeting_room") if isinstance(health.get("meeting_room"), dict) else {}
    virtual = health.get("virtual_environment") if isinstance(health.get("virtual_environment"), dict) else {}
    room_health = room.get("health") if isinstance(room.get("health"), dict) else {}
    reachable = bool(
        room.get("ok") is True
        or room.get("reachable") is True
        or room_health.get("ok") is True
        or virtual.get("ok") is True
    )
    source = virtual if virtual.get("ok") is True else room
    real_work = source.get("real_work_proof") if isinstance(source.get("real_work_proof"), dict) else {}
    return {
        "reachable": reachable,
        "server_owned": bool(source.get("server_owned") is True or reachable),
        "workspace_id": str(source.get("workspaceId") or source.get("environment_id") or ""),
        "recent_work": source.get("recent_work") is True,
        "proof_count": int(real_work.get("proof_count") or 0),
        "truth_contract": str(real_work.get("truth_contract") or "")[:300],
    }


def _reps_summary(health: dict[str, Any]) -> dict[str, Any]:
    reps = health.get("universal_reps_runtime") if isinstance(health.get("universal_reps_runtime"), dict) else {}
    return {
        "ready": reps.get("ok") is True,
        "provider_neutral": reps.get("provider_neutral") is True,
        "record_count": int(reps.get("event_count_tail") or 0),
        "evaluation_count": int(reps.get("scorecard_count_tail") or 0),
        "proposal_count": int(reps.get("proposal_count_tail") or 0),
        "signoff_count": int(reps.get("signoff_count_tail") or 0),
    }


def _bridge_summary(health: dict[str, Any]) -> dict[str, Any]:
    registry = (
        health.get("shell_bridge_registry")
        if isinstance(health.get("shell_bridge_registry"), dict)
        else {}
    )
    bridges = registry.get("bridges") if isinstance(registry.get("bridges"), dict) else {}
    local = bridges.get("local_llm") if isinstance(bridges.get("local_llm"), dict) else {}
    return {
        "ready": registry.get("ok") is True,
        "entry_count": int(registry.get("entry_count") or len(bridges)),
        "usable_count": int(registry.get("usable_count") or 0),
        "local_llm_usable": local.get("usable") is True,
        "connected_without_completion_proof": (
            registry.get("connected_without_completion_proof")
            if isinstance(registry.get("connected_without_completion_proof"), list)
            else []
        ),
        "unavailable_bridge_ids": (
            registry.get("unavailable_bridge_ids")
            if isinstance(registry.get("unavailable_bridge_ids"), list)
            else []
        ),
        "authority_truth": "connection and process health never replace completion proof",
    }


def _provider_capability_summary(health: dict[str, Any]) -> dict[str, Any]:
    capability_map = (
        health.get("provider_capabilities")
        if isinstance(health.get("provider_capabilities"), dict)
        else {}
    )
    providers = (
        capability_map.get("providers")
        if isinstance(capability_map.get("providers"), dict)
        else {}
    )
    connected_without_automatic_proof: list[str] = []
    last_successful_models: dict[str, str] = {}
    for provider_id, raw in sorted(providers.items()):
        item = raw if isinstance(raw, dict) else {}
        if (
            provider_id != "local"
            and item.get("connected") is True
            and item.get("automatic_routable") is not True
        ):
            connected_without_automatic_proof.append(str(provider_id))
        model = str(item.get("last_successful_model") or "").strip()
        if model:
            last_successful_models[str(provider_id)] = model
    local = providers.get("local") if isinstance(providers.get("local"), dict) else {}
    return {
        "ready": capability_map.get("ok") is True,
        "connection_is_not_completion": capability_map.get("connection_is_not_completion") is True,
        "local_completion_proven": local.get("completion_proven") is True,
        "automatic_provider_ids": list(capability_map.get("automatic_provider_ids") or []),
        "degraded_provider_ids": list(capability_map.get("degraded_provider_ids") or []),
        "outage_provider_ids": list(capability_map.get("outage_provider_ids") or []),
        "connected_without_automatic_proof": connected_without_automatic_proof,
        "last_successful_models": last_successful_models,
        "truth_contract": "automatic provider routing requires a fresh quality-passed Engel completion proof",
    }


def _next_work(backlog: dict[str, Any]) -> dict[str, str]:
    items = backlog.get("v10_work_items") if isinstance(backlog.get("v10_work_items"), list) else []
    for item in items:
        if not isinstance(item, dict) or item.get("status") == "deployed_verified":
            continue
        return {
            "id": str(item.get("id") or ""),
            "phase": str(item.get("phase") or ""),
            "priority": str(item.get("priority") or ""),
            "action": str(item.get("action") or ""),
        }
    return {}


def _artifact_evidence(root: Path) -> list[dict[str, Any]]:
    paths = [
        root / "memory" / "ENGEL_PRIMARY_GOAL_V1.json",
        root / "run" / "self_update" / "codebase" / "ownership_map.json",
        root / "memory" / "self_update" / "patch_permission_matrix.json",
        root / "run" / "self_update" / "source_sync" / "registration" / "post.json",
    ]
    return [
        {
            "path": str(path),
            "exists": path.is_file(),
            "sha256": _sha256_file(path),
        }
        for path in paths
    ]


def _introspection(
    health: dict[str, Any],
    workers: dict[str, Any],
    model: dict[str, Any],
    meeting_room: dict[str, Any],
    reps: dict[str, Any],
    bridges: dict[str, Any],
    provider_capabilities: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    known_true = [
        "CT246 /opt/engel is the source of truth.",
        "ROG is the controller and user-facing surface.",
        "Worker output remains candidate evidence until Engel verifies it.",
        "Provider output cannot approve or directly deploy protected changes.",
    ]
    limits: list[str] = []
    uncertainties: list[str] = []
    contradictions: list[str] = []
    if not model["local_runtime_ready"]:
        limits.append("The local model runtime is not currently proven ready.")
    if not model["local_model_first"]:
        contradictions.append("Configured routing does not currently prove local-model-first behavior.")
    if not meeting_room["reachable"]:
        limits.append("The CT-owned Meeting Room is not currently reachable.")
    if workers["expected_count"] == 0:
        uncertainties.append("No worker inventory was returned by live health.")
    elif not workers["all_expected_live"]:
        unavailable = [item["worker_id"] for item in workers["workers"] if not item["live"]]
        limits.append("Unavailable expected workers: " + ", ".join(unavailable))
        contradictions.append("The declared worker topology is not fully live.")
    if not reps["ready"]:
        limits.append("R.E.P.S. runtime is not currently proven ready.")
    if not bridges["ready"]:
        uncertainties.append("The evidence-backed bridge registry is not currently available.")
    elif not bridges["local_llm_usable"]:
        limits.append("The local LLM bridge lacks a current successful completion proof.")
    if not provider_capabilities["ready"]:
        uncertainties.append("The provider completion-capability map is not currently ready.")
    elif not provider_capabilities["local_completion_proven"]:
        limits.append("The provider capability map lacks a current local completion proof.")
    connected_unproven = provider_capabilities["connected_without_automatic_proof"]
    if connected_unproven:
        limits.append(
            "Connected providers excluded from automatic routing without fresh proof: "
            + ", ".join(connected_unproven)
        )
    outages = provider_capabilities["outage_provider_ids"]
    if outages:
        limits.append("Current provider outages: " + ", ".join(outages))
    if bridges["connected_without_completion_proof"]:
        contradictions.append(
            "Connected bridges without current completion proof: "
            + ", ".join(str(item) for item in bridges["connected_without_completion_proof"])
        )
    missing = [Path(item["path"]).name for item in artifacts if not item["exists"]]
    if missing:
        uncertainties.append("Missing control evidence: " + ", ".join(missing))
    if health.get("ok") is not True:
        limits.append("The main CT chat health endpoint is unavailable or unhealthy.")
    return {
        "known_true": known_true,
        "current_limits": limits,
        "uncertainties": uncertainties,
        "contradictions": contradictions,
        "biological_consciousness_claimed": False,
        "completion_claim_allowed_without_current_proof": False,
    }


def render_context(state: dict[str, Any], max_chars: int = 2200) -> str:
    identity = state.get("identity") if isinstance(state.get("identity"), dict) else {}
    goal = state.get("primary_goal") if isinstance(state.get("primary_goal"), dict) else {}
    cognition = state.get("cognition") if isinstance(state.get("cognition"), dict) else {}
    topology = state.get("topology") if isinstance(state.get("topology"), dict) else {}
    room = state.get("meeting_room") if isinstance(state.get("meeting_room"), dict) else {}
    reps = state.get("reps") if isinstance(state.get("reps"), dict) else {}
    bridges = state.get("bridges") if isinstance(state.get("bridges"), dict) else {}
    providers = (
        state.get("provider_capabilities")
        if isinstance(state.get("provider_capabilities"), dict)
        else {}
    )
    reflection = state.get("introspection") if isinstance(state.get("introspection"), dict) else {}
    focus = state.get("current_focus") if isinstance(state.get("current_focus"), dict) else {}
    worker_bits = [
        f"{item.get('worker_id')}={'live' if item.get('live') else 'unavailable'}"
        for item in topology.get("workers", [])
        if isinstance(item, dict)
    ]
    lines = [
        "ENGEL PERSISTENT SELF MODEL - CURRENT EVIDENCE",
        f"Revision: {state.get('state_revision', 0)} observed {state.get('observed_at_utc', '')}",
        f"Identity: {identity.get('name', 'Engel AI Main')}; owner: {identity.get('owner', 'Joshua Ziese')}",
        f"Primary goal: {goal.get('title', '')} ({goal.get('status', '')})",
        "Self-description: persistent software identity and introspection; never claim biological consciousness.",
        f"Brain/source of truth: {identity.get('source_of_truth', 'CT246 /opt/engel')}",
        (
            "Local cognition: ready="
            + str(cognition.get("local_runtime_ready") is True).lower()
            + "; local-first="
            + str(cognition.get("local_model_first") is True).lower()
            + "; long-lived-service="
            + str(cognition.get("long_lived_service_enabled") is True).lower()
        ),
        f"Workers: {', '.join(worker_bits) or 'no current worker evidence'}",
        f"Meeting Room: reachable={str(room.get('reachable') is True).lower()}; current proof count={room.get('proof_count', 0)}",
        f"R.E.P.S.: ready={str(reps.get('ready') is True).lower()}; records={reps.get('record_count', 0)}; evaluations={reps.get('evaluation_count', 0)}",
        (
            "Bridge truth: ready="
            + str(bridges.get("ready") is True).lower()
            + "; usable="
            + str(bridges.get("usable_count", 0))
            + "/"
            + str(bridges.get("entry_count", 0))
            + "; local completion proven="
            + str(bridges.get("local_llm_usable") is True).lower()
        ),
        (
            "Provider completion truth: ready="
            + str(providers.get("ready") is True).lower()
            + "; automatic="
            + ",".join(str(item) for item in providers.get("automatic_provider_ids", []))
            + "; connected-without-proof="
            + ",".join(str(item) for item in providers.get("connected_without_automatic_proof", []))
        ),
        f"Current self-upgrade focus: {focus.get('id', 'not established')}",
    ]
    limits = reflection.get("current_limits") if isinstance(reflection.get("current_limits"), list) else []
    uncertainties = reflection.get("uncertainties") if isinstance(reflection.get("uncertainties"), list) else []
    if limits:
        lines.append("Known current limits: " + " | ".join(str(item) for item in limits))
    unproven = (
        bridges.get("connected_without_completion_proof")
        if isinstance(bridges.get("connected_without_completion_proof"), list)
        else []
    )
    if unproven:
        lines.append(
            "Connected but completion-unproven lanes: "
            + ", ".join(str(item) for item in unproven)
        )
    if uncertainties:
        lines.append("Explicit uncertainty: " + " | ".join(str(item) for item in uncertainties))
    lines.append("Truth rule: do not claim a device result, action, deployment, learning, or completion without current evidence.")
    return "\n".join(lines)[:max_chars].rstrip() + "\n"


def observe(
    *,
    root: Path = ROOT,
    health_payload: dict[str, Any] | None = None,
    observed_at: str | None = None,
    persist: bool = True,
    health_url: str = DEFAULT_HEALTH_URL,
) -> dict[str, Any]:
    root = root.resolve()
    model_root = Path(os.environ.get("ENGEL_SELF_MODEL_ROOT") or root / "memory" / "self_model")
    state_path = model_root / "ENGEL_SELF_MODEL_V1.json"
    context_path = model_root / "ENGEL_SELF_CONTEXT_V1.txt"
    events_path = model_root / "introspection_events.jsonl"
    receipt_root = Path(
        os.environ.get("ENGEL_SELF_MODEL_RECEIPT_ROOT")
        or root / "reports" / "self_upgrade" / "self_model"
    )
    goal_path = root / "memory" / "ENGEL_PRIMARY_GOAL_V1.json"
    backlog_path = (
        root
        / "reports"
        / "self_upgrade"
        / "plans"
        / "ENGEL_SELF_UPDATING_SYSTEM_CREATION_BACKLOG_V10.json"
    )
    goal = _read_json(goal_path)
    backlog = _read_json(backlog_path)
    previous = _read_json(state_path)
    health = health_payload if isinstance(health_payload, dict) else probe_health(health_url)
    observed = observed_at or now_utc()
    workers = _worker_summary(health)
    model = _model_summary(health)
    meeting_room = _meeting_room_summary(health)
    reps = _reps_summary(health)
    bridges = _bridge_summary(health)
    provider_capabilities = _provider_capability_summary(health)
    artifacts = _artifact_evidence(root)
    reflection = _introspection(
        health,
        workers,
        model,
        meeting_room,
        reps,
        bridges,
        provider_capabilities,
        artifacts,
    )
    revision = int(previous.get("state_revision") or 0) + 1
    observation_count = int(
        (previous.get("continuity") or {}).get("observation_count", 0)
        if isinstance(previous.get("continuity"), dict)
        else 0
    ) + 1
    state: dict[str, Any] = {
        "schema": "ENGEL_PERSISTENT_SELF_MODEL_V1",
        "ok": bool(goal.get("title") and goal.get("status") == "active"),
        "operational_ready": bool(
            health.get("ok") is True
            and model["local_runtime_ready"]
            and model["local_model_first"]
            and meeting_room["reachable"]
            and workers["all_expected_live"]
        ),
        "state_revision": revision,
        "state_sha256": "",
        "observed_at_utc": observed,
        "identity": {
            "name": "Engel AI Main",
            "owner": str(goal.get("owner") or "Joshua Ziese"),
            "goal_id": str(goal.get("goal_id") or ""),
            "source_of_truth": "CT246 /opt/engel",
            "controller_surface": "ROG Engel AI Main",
            "persistent_software_identity": True,
            "biological_consciousness_claimed": False,
        },
        "primary_goal": {
            "title": str(goal.get("title") or ""),
            "status": str(goal.get("status") or "unknown"),
            "authority": str(goal.get("authority") or ""),
        },
        "cognition": model,
        "topology": workers,
        "meeting_room": meeting_room,
        "reps": reps,
        "bridges": bridges,
        "provider_capabilities": provider_capabilities,
        "current_focus": _next_work(backlog),
        "introspection": reflection,
        "evidence": {
            "chat_health_url": health_url,
            "chat_health_ok": health.get("ok") is True,
            "control_artifacts": artifacts,
        },
        "continuity": {
            "observation_count": observation_count,
            "previous_revision": int(previous.get("state_revision") or 0),
            "previous_state_sha256": str(previous.get("state_sha256") or ""),
            "previous_observed_at_utc": str(previous.get("observed_at_utc") or ""),
        },
        "authority": {
            "self_observation_may_append": True,
            "self_approval_allowed": False,
            "provider_approval_allowed": False,
            "worker_approval_allowed": False,
            "protected_change_requires_owner": True,
        },
        "mutation": {
            "source_changed": False,
            "service_restarted": False,
            "model_promoted": False,
            "worker_command_sent": False,
            "storage_changed": False,
        },
    }
    state["state_sha256"] = _canonical_sha(state)
    context = render_context(state)
    event = {
        "schema": "ENGEL_INTROSPECTION_EVENT_V1",
        "event_id": "introspection_" + state["state_sha256"][:16],
        "created_at_utc": observed,
        "state_revision": revision,
        "state_sha256": state["state_sha256"],
        "previous_state_sha256": state["continuity"]["previous_state_sha256"],
        "operational_ready": state["operational_ready"],
        "known_limits": reflection["current_limits"],
        "uncertainties": reflection["uncertainties"],
        "contradictions": reflection["contradictions"],
        "proposed_next_action": state["current_focus"],
        "candidate_only": True,
        "self_approved": False,
        "source_mutation": False,
    }
    receipt = {
        "schema": "ENGEL_SELF_MODEL_OBSERVATION_RECEIPT_V1",
        "ok": state["ok"],
        "observed_at_utc": observed,
        "state_revision": revision,
        "state_sha256": state["state_sha256"],
        "state_path": str(state_path),
        "context_path": str(context_path),
        "events_path": str(events_path),
        "event_id": event["event_id"],
        "operational_ready": state["operational_ready"],
        "mutation": state["mutation"],
    }
    if persist:
        _atomic_write(state_path, json.dumps(state, indent=2, sort_keys=True) + "\n")
        _atomic_write(context_path, context)
        _append_jsonl(events_path, event)
        receipt_path = receipt_root / f"ENGEL_SELF_MODEL_OBSERVATION_{_stamp(observed)}.json"
        _atomic_write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        receipt["receipt_path"] = str(receipt_path)
    return {"state": state, "context": context, "event": event, "receipt": receipt}


def status(path: Path = STATE_PATH) -> dict[str, Any]:
    state = _read_json(path)
    if not state:
        return {
            "schema": "ENGEL_PERSISTENT_SELF_MODEL_STATUS_V1",
            "ok": False,
            "status": "self model not observed yet",
            "state_path": str(path),
            "mutation_performed": False,
        }
    valid, errors = validate_state(state)
    return {
        "schema": "ENGEL_PERSISTENT_SELF_MODEL_STATUS_V1",
        "ok": valid and state.get("ok") is True,
        "status": "ready" if valid and state.get("ok") is True else "identity evidence incomplete",
        "operational_ready": state.get("operational_ready") is True,
        "state_revision": int(state.get("state_revision") or 0),
        "state_sha256": str(state.get("state_sha256") or ""),
        "observed_at_utc": str(state.get("observed_at_utc") or ""),
        "current_focus": state.get("current_focus") or {},
        "known_limits": (state.get("introspection") or {}).get("current_limits", []),
        "validation_errors": errors,
        "state_path": str(path),
        "mutation_performed": False,
    }


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel CT246 persistent self-model and introspection runtime.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    observe_parser = sub.add_parser("observe")
    observe_parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    observe_parser.add_argument("--dry-run", action="store_true")
    context_parser = sub.add_parser("context")
    context_parser.add_argument("--max-chars", type=int, default=2200)
    args = parser.parse_args(argv)
    if args.command == "status":
        return _emit(status())
    if args.command == "observe":
        result = observe(health_url=args.health_url, persist=not args.dry_run)
        return _emit(result["receipt"])
    state = _read_json(STATE_PATH)
    if not state:
        return _emit({"ok": False, "status": "self model not observed yet", "state_path": str(STATE_PATH)})
    text = render_context(state, max_chars=max(300, min(args.max_chars, 8000)))
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
