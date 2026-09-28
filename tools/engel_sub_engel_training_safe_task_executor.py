#!/usr/bin/env python3
"""CT246-owned, training-safe task lane for the Windows Sub-Engel node."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_sub_node_remote_control as remote  # noqa: E402
from engel_windows_sub_node_agent import (  # noqa: E402
    TRAINING_SAFE_JOB_TYPES,
    find_training_mutation_terms,
)


REPORT_DIR = ROOT / "run" / "self_update" / "sub_engel_training_safe_executor"
LATEST_REPORT = REPORT_DIR / "latest.json"
DEFAULT_NODE_ID = "DESKTOP-UE5A6GG"
DEFAULT_MEETING_ROOM_URL = "http://127.0.0.1:8790"
READ_ONLY_HINTS = (
    "check status",
    "read-only",
    "read only",
    "report status",
    "status snapshot",
    "training status",
    "inventory summary",
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _decode_stdout(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    raw = result.get("stdout") if isinstance(result, dict) else ""
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def classify_task(task: str, job_type: str = "") -> dict[str, Any]:
    text = str(task or "").strip()
    low = text.lower()
    normalized_job_type = str(job_type or "").strip().lower()
    if normalized_job_type not in TRAINING_SAFE_JOB_TYPES and any(hint in low for hint in READ_ONLY_HINTS):
        normalized_job_type = "status_snapshot"
    mutation_terms = find_training_mutation_terms(low)
    safe = bool(text) and normalized_job_type in TRAINING_SAFE_JOB_TYPES and not mutation_terms
    return {
        "ok": safe,
        "training_safe": safe,
        "non_invasive": safe,
        "job_type": normalized_job_type,
        "mutation_terms": mutation_terms,
        "reason": "read_only_status_task" if safe else "task_is_not_allowlisted_for_active_training",
    }


def probe_training_guard(node_id: str = DEFAULT_NODE_ID) -> dict[str, Any]:
    session = remote.load_session("windows", node_id)
    node_url = remote.runtime_node_url(session) or str(session.get("url") or "")
    health = remote.health(node_url) if node_url else {"ok": False, "error": "missing_node_url"}
    public_guard = health.get("training_guard") if isinstance(health.get("training_guard"), dict) else {}
    status_response: dict[str, Any] = {}
    authenticated_guard: dict[str, Any] = {}
    allowed = health.get("allowed_actions") if isinstance(health.get("allowed_actions"), list) else []
    if "training.status" in allowed and session.get("session_token"):
        status_response = remote.run_action("training.status", node_kind="windows", node_id=node_id)
        authenticated_guard = _decode_stdout(status_response)
    guard = authenticated_guard or public_guard
    observed = str(guard.get("schema") or "") == "engel_sub_engel_training_guard_v1"
    return {
        "ok": bool(health.get("ok")) and observed,
        "schema": "engel_sub_engel_training_guard_probe_v1",
        "observed_at_utc": utc_stamp(),
        "node_id": node_id,
        "node_url": node_url,
        "node_health_ok": bool(health.get("ok")),
        "training_guard_observed": observed,
        "training_active": bool(guard.get("training_active")) if observed else None,
        "training_process_ids": list(guard.get("training_process_ids") or []),
        "authenticated_training_status": bool(authenticated_guard),
        "training_safe_execute_available": "training_safe.execute" in allowed,
        "session_action_ok": bool(status_response.get("ok")) if status_response else False,
        "session_error": str(status_response.get("error") or "") if status_response else "",
        "health_error": str(health.get("error") or "") if not health.get("ok") else "",
        "mutation_performed": False,
        "process_control_used": False,
    }


def _post_meeting_room_proof(report: dict[str, Any], base_url: str = DEFAULT_MEETING_ROOM_URL) -> dict[str, Any]:
    task = (
        f"Sub-Engel training-safe task {report.get('task_id')} "
        f"status={report.get('status')} training_active={report.get('training_active')} "
        f"unchanged={report.get('training_processes_unchanged')}"
    )
    body = json.dumps({
        "task": task,
        "source": "CT246 Sub-Engel Training-Safe Executor",
    }).encode("utf-8")
    req = request.Request(
        base_url.rstrip("/") + "/virtual-environments/engel3d-office/task",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=4) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {"ok": False, "error": "invalid_payload"}
    except (OSError, error.URLError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}


def execute_training_safe_task(
    task: str,
    job_type: str = "",
    node_id: str = DEFAULT_NODE_ID,
    meeting_room_url: str = DEFAULT_MEETING_ROOM_URL,
) -> dict[str, Any]:
    classification = classify_task(task, job_type)
    guard = probe_training_guard(node_id)
    task_id = "SUB-SAFE-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report: dict[str, Any] = {
        "ok": False,
        "schema": "engel_sub_engel_training_safe_executor_receipt_v1",
        "created_at_utc": utc_stamp(),
        "task_id": task_id,
        "node_id": node_id,
        "task": task,
        "classification": classification,
        "training_guard": guard,
        "training_active": guard.get("training_active"),
        "status": "blocked",
        "mutation_performed": False,
        "process_control_used": False,
        "local_llm_attempted": False,
        "storage_policy": {
            "active_runtime": "/opt/engel",
            "archive_after_mount_proof": "/mnt/engel-hdd-vault",
        },
    }
    if not classification.get("training_safe"):
        report["status"] = "blocked_not_training_safe"
    elif not guard.get("training_guard_observed"):
        report["status"] = "blocked_training_guard_unknown"
    elif not guard.get("authenticated_training_status"):
        report["status"] = "blocked_authenticated_guard_unavailable"
    elif not guard.get("training_safe_execute_available"):
        report["status"] = "blocked_node_upgrade_required"
    else:
        response = remote.run_action(
            "training_safe.execute",
            node_kind="windows",
            node_id=node_id,
            payload={
                "task_id": task_id,
                "task": task,
                "order_text": task,
                "job_type": classification["job_type"],
                "training_safe": True,
                "non_invasive": True,
                "client_timeout_seconds": 30,
            },
        )
        remote_result = _decode_stdout(response)
        report["remote_response_ok"] = bool(response.get("ok"))
        report["remote_result"] = remote_result
        report["training_processes_unchanged"] = bool(remote_result.get("training_processes_unchanged"))
        report["ok"] = bool(
            response.get("ok")
            and remote_result.get("overall_ok")
            and remote_result.get("training_guard_observed")
            and remote_result.get("training_processes_unchanged")
            and remote_result.get("mutation_performed") is False
            and remote_result.get("process_control_used") is False
            and remote_result.get("local_llm_attempted") is False
        )
        report["status"] = "returned" if report["ok"] else "failed_remote_proof"
    report["meeting_room_proof"] = _post_meeting_room_proof(report, meeting_room_url)
    write_json(REPORT_DIR / f"{task_id}.json", report)
    write_json(LATEST_REPORT, report)
    return report


def meeting_room_training_gate(task: str, job_type: str = "") -> dict[str, Any]:
    guard = probe_training_guard()
    if not guard.get("training_guard_observed"):
        return {
            "handled": True,
            "status": "Needs Review",
            "reply": "Sub-Engel training state could not be verified, so Engel did not assign or run work on that node.",
            "guard": guard,
        }
    if guard.get("training_active") is not True:
        return {"handled": False, "guard": guard}
    classification = classify_task(task, job_type)
    if not classification.get("training_safe"):
        return {
            "handled": True,
            "status": "Waiting",
            "reply": "Sub-Engel training is active. Engel deferred this task because it is not an approved read-only status job.",
            "guard": guard,
            "classification": classification,
        }
    report = execute_training_safe_task(task, classification["job_type"])
    return {
        "handled": True,
        "status": "Returned" if report.get("ok") else "Needs Review",
        "reply": (
            f"Sub-Engel returned training-safe proof for {report.get('task_id')}; "
            f"training processes unchanged={report.get('training_processes_unchanged')}."
            if report.get("ok")
            else f"Sub-Engel training-safe task was not completed: {report.get('status')}."
        ),
        "guard": guard,
        "report": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CT246-owned training-safe Sub-Engel tasks")
    sub = parser.add_subparsers(dest="command", required=True)
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--node", default=DEFAULT_NODE_ID)
    classify_parser = sub.add_parser("classify")
    classify_parser.add_argument("--task", required=True)
    classify_parser.add_argument("--job-type", default="")
    execute_parser = sub.add_parser("execute")
    execute_parser.add_argument("--task", required=True)
    execute_parser.add_argument("--job-type", default="")
    execute_parser.add_argument("--node", default=DEFAULT_NODE_ID)
    args = parser.parse_args(argv)
    if args.command == "status":
        result = probe_training_guard(args.node)
    elif args.command == "classify":
        result = classify_task(args.task, args.job_type)
    else:
        result = execute_training_safe_task(args.task, args.job_type, args.node)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
