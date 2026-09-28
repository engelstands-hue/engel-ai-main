from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
PROTOCOL_PATH = ROOT / "memory" / "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.json"
REGISTRY_PATH = ROOT / "memory" / "ENGEL_ANDROID_REMOTE_WORKER_REGISTRY_V1.json"
REMOTE_WORKERS_ROOT = ROOT / "remote_workers"

PROTOCOL_NAME = "Engel Multi Android Remote Workers Protocol V1"
ROUTING_LAYER = "engel_communication_router_only"
LEGACY_ROUTING_LAYER = "communication_queen_only"
ROUTED_BY = "engel_communication_router"
LEGACY_ROUTED_BY = "communication_queen"
CONNECTION_MODE = "manual_transfer_v1"
AUTONOMY_SCOPE = "assigned_job_sandbox_only"

SAFETY_STATES = [
    "protocol_defined",
    "multi_worker_registry_defined",
    "real_data_only",
    "manual_setup_required",
    "manual_transfer_mode_only",
    "on_device_autonomy_allowed",
    "autonomy_scope_assigned_job_sandbox_only",
    "no_phone_connection",
    "no_android_runtime_execution_from_engel",
    "engel_communication_router_routing_required",
    "remote_worker_not_queen",
    "candidate_outputs_only",
    "no_trusted_memory_write",
    "no_patch_apply",
    "no_provider_network",
    "no_model_runtime",
    "no_startup_autorun",
    "no_fake_worker_progress",
]

ANDROID_WORKER_IDS = [
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
]

SUB_ENGEL_WORKER_IDS = [
    "sub_engel_os_worker",
    "windows_sub_engel",
]

# Android assignment/status surfaces must never treat desktop Sub-Engel nodes
# as phones. The desktop lanes have their own authenticated controllers.
WORKER_IDS = ANDROID_WORKER_IDS
ALL_LEGACY_WORKER_IDS = ANDROID_WORKER_IDS + SUB_ENGEL_WORKER_IDS

JOB_PACKET_REQUIRED_FIELDS = [
    "job_id",
    "job_title",
    "job_type",
    "job_template",
    "real_job",
    "created_at",
    "assigned_worker_id",
    "created_by",
    "routed_by",
    "priority",
    "status",
    "input_files",
    "instructions",
    "allowed_actions",
    "blocked_actions",
    "expected_outputs",
    "receipt_required",
    "log_required",
    "max_runtime_hint",
    "max_input_size",
    "max_output_size",
    "offline_only",
    "manual_transfer_required",
    "on_device_autonomy_allowed",
    "autonomy_scope",
    "trusted_memory_write",
    "source_mutation",
    "route_mutation",
    "patch_apply",
    "provider_network",
    "model_runtime",
    "approval_required_for_any_write",
]

JOB_STATUSES = [
    "template_only",
    "queued",
    "assigned",
    "prepared_for_manual_transfer",
    "received_by_worker",
    "validated_by_worker",
    "in_progress",
    "waiting",
    "blocked",
    "completed",
    "failed",
    "returned_to_engel",
    "rejected_by_worker",
    "cancelled",
]

STATUS_PACKET_REQUIRED_FIELDS = [
    "worker_id",
    "worker_name",
    "device_label",
    "job_id",
    "job_title",
    "job_status",
    "progress_percent",
    "status_message",
    "current_step",
    "started_at",
    "updated_at",
    "completed_at",
    "blocked_reason",
    "output_ready",
    "receipt_path",
    "log_path",
    "safety_flags",
    "manual_transfer_mode",
    "on_device_autonomy",
    "autonomy_scope",
    "real_status",
    "source",
]

RESULT_PACKET_REQUIRED_FIELDS = [
    "worker_id",
    "worker_name",
    "job_id",
    "job_status",
    "summary",
    "output_files",
    "candidate_outputs",
    "log_files",
    "receipt_files",
    "warnings",
    "safety_flags",
    "requires_human_review",
    "trusted_memory_write",
    "source_mutation",
    "route_mutation",
    "patch_apply",
    "provider_network",
    "model_runtime",
    "on_device_autonomy_used",
    "autonomy_scope",
    "real_result",
    "source",
]

FORBIDDEN_ACTION_TOKENS = [
    "execute arbitrary shell from job packet",
    "install packages",
    "download files",
    "download models",
    "start network server",
    "expose SSH",
    "run background daemon",
    "schedule boot startup",
    "mutate job packet after receipt except status/result fields",
    "access paths outside worker folder unless listed in input_files",
    "delete receipts",
    "delete logs",
    "mark output trusted",
    "mark memory promoted",
    "mark patch applied",
    "impersonate approval",
]

WORKER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "android_worker_alpha": {
        "worker_id": "android_worker_alpha",
        "worker_name": "Engel Android Worker Alpha",
        "device_label": "manual_transfer_device_alpha",
        "role": "research note worker",
        "allowed_task_types": [
            "summarize_text",
            "draft_research_note",
            "classify_file",
            "return_status",
            "return_logs",
            "return_receipt",
        ],
        "allowed_local_actions": [
            "read assigned local text file listed in the job packet",
            "split text into bounded chunks",
            "create bullet summary",
            "create research note draft",
            "flag risky instructions",
            "save candidate output",
            "save receipt",
        ],
    },
    "android_worker_beta": {
        "worker_id": "android_worker_beta",
        "worker_name": "Engel Android Worker Beta",
        "device_label": "manual_transfer_device_beta",
        "role": "candidate JSON worker",
        "allowed_task_types": [
            "draft_candidate_json",
            "format_report_draft",
            "classify_file",
            "return_status",
            "return_logs",
            "return_receipt",
        ],
        "allowed_local_actions": [
            "read assigned local note listed in the job packet",
            "extract bounded fields",
            "validate simple JSON structure",
            "reject unknown or unsafe fields",
            "save candidate JSON",
            "save validation notes",
            "save receipt",
        ],
    },
    "android_worker_gamma": {
        "worker_id": "android_worker_gamma",
        "worker_name": "Engel Android Worker Gamma",
        "device_label": "manual_transfer_device_gamma",
        "role": "small local compute / report formatting worker",
        "allowed_task_types": [
            "compute_small_local_task",
            "format_report_draft",
            "summarize_text",
            "return_status",
            "return_logs",
            "return_receipt",
        ],
        "allowed_local_actions": [
            "perform small local calculations from assigned input files",
            "format report drafts",
            "summarize assigned file",
            "create local output package",
            "save result packet",
            "save receipt",
        ],
    },
}

REQUIRED_WORKER_FLAGS: dict[str, Any] = {
    "queen_authority": False,
    "routing_layer": ROUTING_LAYER,
    "trusted_memory_write": False,
    "source_mutation": False,
    "route_mutation": False,
    "patch_apply": False,
    "provider_network": False,
    "startup_autorun": False,
    "model_runtime": False,
    "hermes_allowed": False,
    "controls_engel": False,
    "candidate_outputs_only": True,
    "on_device_autonomy": True,
    "autonomy_scope": AUTONOMY_SCOPE,
    "can_self_assign_jobs": False,
    "can_create_jobs": False,
    "can_route_jobs": False,
    "can_control_engel": False,
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def protocol_contract() -> dict[str, Any]:
    return read_json(PROTOCOL_PATH)


def worker_registry() -> dict[str, Any]:
    return read_json(REGISTRY_PATH)


def worker_package_path(worker_id: str) -> Path:
    return REMOTE_WORKERS_ROOT / worker_id


def worker_identity_path(worker_id: str) -> Path:
    return worker_package_path(worker_id) / "config" / "worker_identity.json"


def worker_identity(worker_id: str) -> dict[str, Any]:
    return read_json(worker_identity_path(worker_id))


def validate_worker_flags(identity: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, expected in REQUIRED_WORKER_FLAGS.items():
        if key == "routing_layer" and identity.get(key) == LEGACY_ROUTING_LAYER:
            continue
        if identity.get(key) != expected:
            errors.append(f"{key} expected {expected!r}")
    return errors


def validate_job_packet(job: dict[str, Any], worker: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    for field in JOB_PACKET_REQUIRED_FIELDS:
        if field not in job:
            errors.append("missing job packet field: " + field)
    if job.get("job_template") is True:
        if job.get("real_job") is not False or job.get("status") != "template_only":
            errors.append("template jobs must be real_job false and status template_only")
        return errors
    if job.get("real_job") is not True:
        errors.append("real jobs must set real_job true")
    if job.get("created_by") != "engel":
        errors.append("created_by must be engel")
    if job.get("routed_by") not in (ROUTED_BY, LEGACY_ROUTED_BY):
        errors.append("routed_by must be engel_communication_router")
    if job.get("status") not in JOB_STATUSES:
        errors.append("unknown job status")
    if job.get("offline_only") is not True:
        errors.append("offline_only must be true")
    if job.get("manual_transfer_required") is not True:
        errors.append("manual_transfer_required must be true")
    if job.get("on_device_autonomy_allowed") is not True:
        errors.append("on_device_autonomy_allowed must be true")
    if job.get("autonomy_scope") != AUTONOMY_SCOPE:
        errors.append("autonomy_scope must be assigned_job_sandbox_only")
    for blocked_flag in [
        "trusted_memory_write",
        "source_mutation",
        "route_mutation",
        "patch_apply",
        "provider_network",
        "model_runtime",
    ]:
        if job.get(blocked_flag) is not False:
            errors.append(blocked_flag + " must be false")
    if job.get("approval_required_for_any_write") is not True:
        errors.append("approval_required_for_any_write must be true")
    if worker:
        if job.get("assigned_worker_id") != worker.get("worker_id"):
            errors.append("assigned_worker_id does not match worker")
        if job.get("job_type") not in worker.get("allowed_task_types", []):
            errors.append("job_type is not allowed for worker")
    return errors


def validate_status_packet(status: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in STATUS_PACKET_REQUIRED_FIELDS:
        if field not in status:
            errors.append("missing status packet field: " + field)
    if status.get("manual_transfer_mode") is not True:
        errors.append("manual_transfer_mode must be true")
    if status.get("on_device_autonomy") is not True:
        errors.append("on_device_autonomy must be true")
    if status.get("autonomy_scope") != AUTONOMY_SCOPE:
        errors.append("autonomy_scope mismatch")
    if status.get("real_status") is not True:
        errors.append("real_status must be true")
    if status.get("source") != "android_worker_returned_status":
        errors.append("status source mismatch")
    progress = status.get("progress_percent")
    if not isinstance(progress, int) or progress < 0 or progress > 100:
        errors.append("progress_percent must be integer 0..100")
    return errors


def validate_result_packet(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in RESULT_PACKET_REQUIRED_FIELDS:
        if field not in result:
            errors.append("missing result packet field: " + field)
    for blocked_flag in [
        "trusted_memory_write",
        "source_mutation",
        "route_mutation",
        "patch_apply",
        "provider_network",
        "model_runtime",
    ]:
        if result.get(blocked_flag) is not False:
            errors.append(blocked_flag + " must be false")
    if result.get("requires_human_review") is not True:
        errors.append("requires_human_review must be true")
    if result.get("autonomy_scope") != AUTONOMY_SCOPE:
        errors.append("autonomy_scope mismatch")
    if result.get("real_result") is not True:
        errors.append("real_result must be true")
    if result.get("source") != "android_worker_returned_result":
        errors.append("result source mismatch")
    return errors
