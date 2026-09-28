#!/usr/bin/env python3
"""
Report-only Guardian Watchdog receipt helpers.

This module writes structured crash/update receipts when explicitly called.
It does not monitor processes, restart Engel, restore files, kill processes,
modify live artifacts, call providers, use network access, or run local model
inference.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
STATUS_TEMPLATE_PATH = ROOT / "memory" / "ENGEL_GUARDIAN_WATCHDOG_STATUS_TEMPLATE_V1.json"
WATCHDOG_RECEIPT_ROOT = ROOT / "reports" / "guardian_watchdog"
CRASH_RECEIPT_ROOT = WATCHDOG_RECEIPT_ROOT / "crashes"
LIVE_APP_ROOT = ROOT / "live" / "app"
APPROVED_ENGEL_TARGET = LIVE_APP_ROOT / "Engel.exe"
WATCHED_PROCESS_NAME = "Engel"

CRASH_RECEIPT_ACTION = "crash_update_receipt"
CRASH_RECEIPT_RESULT_RECORDED = "recorded_report_only"
NO_RESTART_STATEMENT = "No restart was attempted by this receipt writer."
NO_RESTORE_STATEMENT = "No restore was attempted by this receipt writer."
HUMAN_REVIEW_REQUIRED_STATEMENT = "Human review is required before restart, restore, or promotion."

REQUIRED_CRASH_RECEIPT_FIELDS = [
    "receipt_id",
    "timestamp",
    "watched_process",
    "expected_path",
    "observed_status",
    "exit_code",
    "recent_update_build_report",
    "last_known_good_backup",
    "restart_attempted",
    "restore_attempted",
    "restart_count",
    "restart_limit",
    "crash_loop_detected",
    "result",
    "human_review_required",
]


class CrashReceiptError(ValueError):
    """Raised when a crash receipt payload is malformed."""


def _utc_timestamp_for_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_status_template(path: Path = STATUS_TEMPLATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {}
    return data


def default_last_known_good_backup(status: dict[str, Any] | None = None) -> dict[str, Any]:
    status_data = _read_status_template() if status is None else status
    backup = status_data.get("last_known_good_backup")
    if isinstance(backup, dict):
        return dict(backup)
    return {
        "configured": False,
        "baseline_id": None,
        "backup_path": None,
        "hash": None,
        "hash_status": "not_checked",
    }


def crash_loop_detected(restart_count: int, restart_limit: int) -> bool:
    if restart_limit <= 0:
        return False
    return restart_count >= restart_limit


def build_crash_receipt_payload(
    *,
    watched_process: str = WATCHED_PROCESS_NAME,
    expected_path: Path | str = APPROVED_ENGEL_TARGET,
    observed_status: str,
    exit_code: int | None = None,
    recent_update_build_report: str | None = None,
    last_known_good_backup: dict[str, Any] | None = None,
    restart_count: int = 0,
    restart_limit: int = 0,
    result: str = CRASH_RECEIPT_RESULT_RECORDED,
) -> dict[str, Any]:
    if not observed_status or not str(observed_status).strip():
        raise CrashReceiptError("observed_status is required")
    if watched_process != WATCHED_PROCESS_NAME:
        raise CrashReceiptError("only the approved Engel watched process may be recorded")
    if restart_count < 0:
        raise CrashReceiptError("restart_count must not be negative")
    if restart_limit < 0:
        raise CrashReceiptError("restart_limit must not be negative")
    if exit_code is not None and not isinstance(exit_code, int):
        raise CrashReceiptError("exit_code must be an integer or null")

    expected = Path(expected_path).resolve(strict=False)
    if expected != APPROVED_ENGEL_TARGET.resolve(strict=False):
        raise CrashReceiptError("expected_path must be the approved Engel live application")

    backup = default_last_known_good_backup() if last_known_good_backup is None else dict(last_known_good_backup)
    payload = {
        "receipt_id": f"{_utc_timestamp_for_id()}_{uuid.uuid4().hex[:8]}",
        "timestamp": _utc_timestamp(),
        "action": CRASH_RECEIPT_ACTION,
        "watched_process": watched_process,
        "expected_path": str(expected),
        "observed_status": str(observed_status),
        "exit_code": exit_code,
        "recent_update_build_report": recent_update_build_report,
        "last_known_good_backup": backup,
        "restart_attempted": False,
        "restore_attempted": False,
        "restart_count": restart_count,
        "restart_limit": restart_limit,
        "crash_loop_detected": crash_loop_detected(restart_count, restart_limit),
        "result": result,
        "human_review_required": True,
        "safety_flags": {
            "monitor_loop_enabled": False,
            "restart_enabled": False,
            "restore_enabled": False,
            "process_kill_allowed": False,
            "live_artifact_mutation_allowed": False,
            "trusted_memory_write_allowed": False,
            "source_mutation_allowed": False,
            "route_mutation_allowed": False,
            "queue_mutation_allowed": False,
            "provider_api_allowed": False,
            "network_allowed": False,
            "local_llm_inference_allowed": False,
            "mobile_runtime_allowed": False,
            "remote_queen_runtime_allowed": False,
        },
        "no_restart_statement": NO_RESTART_STATEMENT,
        "no_restore_statement": NO_RESTORE_STATEMENT,
        "human_review_required_statement": HUMAN_REVIEW_REQUIRED_STATEMENT,
    }
    validate_crash_receipt_payload(payload)
    return payload


def validate_crash_receipt_payload(payload: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_CRASH_RECEIPT_FIELDS if field not in payload]
    if missing:
        raise CrashReceiptError(f"missing crash receipt fields: {missing}")
    if payload.get("watched_process") != WATCHED_PROCESS_NAME:
        raise CrashReceiptError("watched_process must be Engel")
    if payload.get("restart_attempted") is not False:
        raise CrashReceiptError("restart_attempted must be false")
    if payload.get("restore_attempted") is not False:
        raise CrashReceiptError("restore_attempted must be false")
    if payload.get("human_review_required") is not True:
        raise CrashReceiptError("human_review_required must be true")
    safety = payload.get("safety_flags")
    if not isinstance(safety, dict):
        raise CrashReceiptError("safety_flags must be an object")
    unsafe = [key for key, value in safety.items() if value is not False]
    if unsafe:
        raise CrashReceiptError(f"safety flags must be false: {unsafe}")


def write_crash_receipt(payload: dict[str, Any], receipt_root: Path | str | None = None) -> Path:
    validate_crash_receipt_payload(payload)
    root = CRASH_RECEIPT_ROOT if receipt_root is None else Path(receipt_root)
    root.mkdir(parents=True, exist_ok=True)
    receipt_path = root / f"ENGEL_GUARDIAN_WATCHDOG_CRASH_{payload['receipt_id']}.json"
    with receipt_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return receipt_path


def record_crash_receipt(
    *,
    observed_status: str,
    exit_code: int | None = None,
    recent_update_build_report: str | None = None,
    last_known_good_backup: dict[str, Any] | None = None,
    restart_count: int = 0,
    restart_limit: int = 0,
    receipt_root: Path | str | None = None,
) -> Path:
    payload = build_crash_receipt_payload(
        observed_status=observed_status,
        exit_code=exit_code,
        recent_update_build_report=recent_update_build_report,
        last_known_good_backup=last_known_good_backup,
        restart_count=restart_count,
        restart_limit=restart_limit,
    )
    return write_crash_receipt(payload, receipt_root=receipt_root)
