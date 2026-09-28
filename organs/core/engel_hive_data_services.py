from __future__ import annotations

from pathlib import Path
from typing import Any

from engel_research_office_data import build_colony_hive_snapshot


_DISABLED_RUNTIME_FLAG_KEYS = [
    "provider_or_api_calls_enabled",
    "internet_behavior_enabled",
    "background_worker_enabled",
    "remote_queen_runtime_enabled",
    "runtime_remote_queen_network_enabled",
    "queue_mutation_enabled",
    "trusted_memory_write_enabled",
    "source_edit_enabled",
    "network_discovery_enabled",
    "device_pairing_enabled",
    "autonomous_remote_work_enabled",
    "remote_file_transfer_enabled",
    "applied_learning_enabled",
    "provider_network_enabled",
]


def build_hive_snapshot(root: str | Path) -> dict[str, Any]:
    """Return the current Engel Hive snapshot through the existing data builder.

    This wrapper is intentionally behavior-preserving. It must not mutate files,
    start GUI code, call providers, or change the snapshot shape.
    """
    return build_colony_hive_snapshot(Path(root))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _safe_positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_error_text(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return type(exc).__name__
    return (type(exc).__name__ + ": " + message)[:160]


def _communication_status(snapshot: dict[str, Any]) -> str:
    communication = _as_dict(snapshot.get("communication_queen"))
    status = _as_dict(communication.get("status"))
    status_label = status.get("status_label")
    if isinstance(status_label, str) and status_label.strip():
        return status_label.strip()
    mode = communication.get("mode")
    if isinstance(mode, str) and mode.strip():
        return mode.strip()
    return "unknown"


def _guardian_status(snapshot: dict[str, Any]) -> str:
    guardian = _as_dict(snapshot.get("guardian_layer"))
    if guardian.get("visible") is True:
        blocks = [str(item) for item in _as_list(guardian.get("blocks")) if str(item).strip()]
        if blocks:
            return "visible_blocks: " + ", ".join(blocks[:6])
        return "visible_no_blocks_listed"
    return "review_required"


def _mind_safe_mode(snapshot: dict[str, Any]) -> bool:
    mind = _as_dict(snapshot.get("mind_summary"))
    return str(mind.get("safe_mode", "")).strip().upper() == "ON"


def _receipts_available(snapshot: dict[str, Any]) -> bool:
    live = _as_dict(snapshot.get("super_swarm_hive_live"))
    return _safe_positive_int(live.get("report_count")) > 0


def _remote_queen_status(snapshot: dict[str, Any]) -> str:
    communication = _as_dict(snapshot.get("communication_queen"))
    candidates = _as_list(communication.get("remote_queen_candidates"))
    if not candidates:
        return "runtime_disabled_no_candidates"
    all_disabled = True
    for candidate in candidates:
        if _as_dict(candidate).get("can_assign_tasks_now") is not False:
            all_disabled = False
    if all_disabled:
        return "runtime_disabled_candidates_present"
    return "review_required"


def _disabled_runtime_flags(snapshot: dict[str, Any]) -> list[str]:
    communication = _as_dict(snapshot.get("communication_queen"))
    status = _as_dict(communication.get("status"))
    live = _as_dict(snapshot.get("super_swarm_hive_live"))
    flags: list[str] = []
    for key in _DISABLED_RUNTIME_FLAG_KEYS:
        if status.get(key) is not True:
            flags.append(key)
    if live.get("live_enabled") is not True:
        flags.append("super_swarm_live_runtime_enabled")
    if live.get("can_execute_from_hive") is not True:
        flags.append("hive_execution_enabled")
    flags.append("mobile_runtime_enabled")
    flags.append("route_mutation_enabled")
    return flags


def _empty_state_reason(snapshot: dict[str, Any]) -> str | None:
    required = [
        "cells",
        "queens",
        "workers",
        "communication_queen",
        "guardian_layer",
        "mind_summary",
        "super_swarm_hive_live",
    ]
    missing = [key for key in required if key not in snapshot]
    if missing:
        return "missing_snapshot_sections: " + ", ".join(missing)
    if not _as_list(snapshot.get("cells")):
        return "no_hive_cells_found"
    return None


def _unavailable_companion_hive_summary(last_error: str) -> dict[str, Any]:
    return {
        "hive_available": False,
        "colony_count": 0,
        "queen_count": 0,
        "worker_count": 0,
        "communication_queen_status": "unavailable",
        "guardian_status": "unavailable",
        "mind_summary_safe_mode": False,
        "mobile_status": "planned_disabled",
        "receipts_available": False,
        "disabled_runtime_flags": [
            "provider_or_api_calls_enabled",
            "internet_behavior_enabled",
            "background_worker_enabled",
            "remote_queen_runtime_enabled",
            "mobile_runtime_enabled",
            "queue_mutation_enabled",
            "trusted_memory_write_enabled",
            "route_mutation_enabled",
        ],
        "summary_generated_from": "build_hive_snapshot",
        "no_fake_live_data": True,
        "source_trust": "local_readonly_snapshot",
        "remote_queen_status": "runtime_disabled_no_candidates",
        "provider_api_enabled": False,
        "internet_enabled": False,
        "background_workers_enabled": False,
        "last_error": last_error,
        "empty_state_reason": "snapshot_unavailable",
    }


def build_companion_hive_summary(root: str | Path) -> dict[str, Any]:
    """Return a compact read-only Hive summary for future Companion status cards."""
    try:
        snapshot = build_hive_snapshot(root)
    except Exception as exc:
        return _unavailable_companion_hive_summary(_safe_error_text(exc))

    if not isinstance(snapshot, dict):
        return _unavailable_companion_hive_summary("TypeError: snapshot is not a dict")

    communication = _as_dict(snapshot.get("communication_queen"))
    communication_status = _as_dict(communication.get("status"))
    empty_reason = _empty_state_reason(snapshot)
    return {
        "hive_available": empty_reason is None,
        "colony_count": _list_count(snapshot.get("cells")),
        "queen_count": _list_count(snapshot.get("queens")),
        "worker_count": _list_count(snapshot.get("workers")),
        "communication_queen_status": _communication_status(snapshot),
        "guardian_status": _guardian_status(snapshot),
        "mind_summary_safe_mode": _mind_safe_mode(snapshot),
        "mobile_status": "planned_disabled",
        "receipts_available": _receipts_available(snapshot),
        "disabled_runtime_flags": _disabled_runtime_flags(snapshot),
        "summary_generated_from": "build_hive_snapshot",
        "no_fake_live_data": True,
        "source_trust": "local_readonly_snapshot",
        "remote_queen_status": _remote_queen_status(snapshot),
        "provider_api_enabled": bool(communication_status.get("provider_or_api_calls_enabled", False)),
        "internet_enabled": bool(communication_status.get("internet_behavior_enabled", False)),
        "background_workers_enabled": bool(communication_status.get("background_worker_enabled", False)),
        "last_error": None,
        "empty_state_reason": empty_reason,
    }
