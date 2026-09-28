from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from engel_android_remote_worker_protocol import (
    AUTONOMY_SCOPE,
    CONNECTION_MODE,
    REGISTRY_PATH,
    REMOTE_WORKERS_ROOT,
    ROUTING_LAYER,
    SAFETY_STATES,
    WORKER_IDS,
    protocol_contract,
    read_json,
    validate_job_packet,
    validate_result_packet,
    validate_status_packet,
    validate_worker_flags,
    worker_identity,
    worker_package_path,
    worker_registry,
)


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)

HONEST_STATES = {
    "no_workers": "No Android Remote Workers configured. Manual setup required.",
    "no_jobs": "Workers configured / no assigned jobs.",
    "awaiting_status": "Job packet prepared / awaiting manual worker status.",
    "no_result": "Result not returned yet.",
    "returned": "Returned candidate output requires human review.",
}

CURRENT_JOB_FIELDS = [
    "current job title",
    "job id",
    "assigned worker",
    "job type",
    "status",
    "progress percentage",
    "current step",
    "last update time",
    "blocked reason",
    "complete yes/no",
    "output ready yes/no",
    "receipt/log paths",
    "safety status",
    "autonomy status",
    "data source path",
]

WORKER_LIST_FIELDS = [
    "worker name",
    "worker id",
    "device label",
    "role",
    "connection mode",
    "current job id",
    "current job title",
    "job status",
    "progress percentage",
    "last update",
    "output-ready state",
    "blocked reason",
    "safety state",
    "autonomy scope",
    "data source path",
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def json_files(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    files: list[Path] = []
    for child in folder.iterdir():
        if child.is_file() and child.suffix.lower() == ".json":
            files.append(child)
    return sorted(files)


def real_job_files(package: Path) -> list[Path]:
    found: list[Path] = []
    for folder_name in ["jobs", "inbox"]:
        for path in json_files(package / folder_name):
            payload = read_json(path)
            if payload.get("job_template") is True:
                continue
            if payload.get("real_job") is True:
                found.append(path)
    return sorted(found)


def returned_status_files(package: Path) -> list[Path]:
    found: list[Path] = []
    for path in json_files(package / "status"):
        payload = read_json(path)
        if payload.get("real_status") is True and payload.get("source") == "android_worker_returned_status":
            found.append(path)
    return sorted(found)


def returned_result_files(package: Path) -> list[Path]:
    found: list[Path] = []
    for path in json_files(package / "outbox"):
        payload = read_json(path)
        if payload.get("real_result") is True and payload.get("source") == "android_worker_returned_result":
            found.append(path)
    return sorted(found)


def latest_packet(paths: list[Path]) -> tuple[Path | None, dict[str, object]]:
    if not paths:
        return None, {}
    path = paths[-1]
    return path, read_json(path)


def package_status(worker_id: str) -> dict[str, object]:
    package = worker_package_path(worker_id)
    identity = worker_identity(worker_id)
    registry = worker_registry()
    registry_entry = {}
    for entry in registry.get("workers", []):
        if isinstance(entry, dict) and entry.get("worker_id") == worker_id:
            registry_entry = entry
            break

    jobs = real_job_files(package)
    statuses = returned_status_files(package)
    results = returned_result_files(package)
    job_path, job = latest_packet(jobs)
    status_path, status = latest_packet(statuses)
    result_path, result = latest_packet(results)

    state = "Not Connected"
    state_note = HONEST_STATES["no_workers"]
    current_job_id = str(registry_entry.get("current_job_id", ""))
    current_job_title = ""
    job_status = str(registry_entry.get("current_job_status", "Manual Setup"))
    progress = 0
    current_step = ""
    blocked_reason = ""
    output_ready = False
    complete = False
    last_update = str(registry_entry.get("last_update", ""))
    data_source = rel(REGISTRY_PATH)
    receipt_path = ""
    log_path = ""
    validation_warnings: list[str] = []

    if package.exists() and package.is_dir():
        state = "Manual Setup"
        state_note = HONEST_STATES["no_jobs"]
        data_source = rel(package)
    if job:
        validation_warnings.extend(validate_job_packet(job, identity))
        state = "Assigned"
        state_note = HONEST_STATES["awaiting_status"]
        current_job_id = str(job.get("job_id", ""))
        current_job_title = str(job.get("job_title", ""))
        job_status = str(job.get("status", "prepared_for_manual_transfer"))
        data_source = rel(job_path) if job_path else data_source
    if status:
        validation_warnings.extend(validate_status_packet(status))
        state = " ".join(str(status.get("job_status", "In Progress")).split("_")).title()
        state_note = HONEST_STATES["no_result"]
        current_job_id = str(status.get("job_id", current_job_id))
        current_job_title = str(status.get("job_title", current_job_title))
        job_status = str(status.get("job_status", job_status))
        progress = int(status.get("progress_percent", 0)) if isinstance(status.get("progress_percent"), int) else 0
        current_step = str(status.get("current_step", ""))
        blocked_reason = str(status.get("blocked_reason", ""))
        output_ready = bool(status.get("output_ready", False))
        last_update = str(status.get("updated_at", ""))
        receipt_path = str(status.get("receipt_path", ""))
        log_path = str(status.get("log_path", ""))
        data_source = rel(status_path) if status_path else data_source
    if result:
        validation_warnings.extend(validate_result_packet(result))
        state = "Returned"
        state_note = HONEST_STATES["returned"]
        current_job_id = str(result.get("job_id", current_job_id))
        job_status = str(result.get("job_status", job_status))
        output_ready = True
        complete = job_status in {"completed", "returned_to_engel"}
        receipt_files = result.get("receipt_files", [])
        log_files = result.get("log_files", [])
        if isinstance(receipt_files, list) and receipt_files:
            receipt_path = str(receipt_files[0])
        if isinstance(log_files, list) and log_files:
            log_path = str(log_files[0])
        data_source = rel(result_path) if result_path else data_source

    flag_errors = validate_worker_flags(identity) if identity else ["worker identity missing"]
    if flag_errors:
        validation_warnings.extend(flag_errors)

    return {
        "worker_name": identity.get("worker_name", registry_entry.get("worker_name", worker_id)),
        "worker_id": worker_id,
        "device_label": identity.get("device_label", registry_entry.get("device_label", "")),
        "role": identity.get("role", registry_entry.get("role", "")),
        "connection_mode": CONNECTION_MODE,
        "state": state,
        "state_note": state_note,
        "current_job_id": current_job_id,
        "current_job_title": current_job_title,
        "job_status": job_status,
        "progress_percent": progress,
        "current_step": current_step,
        "last_update": last_update,
        "output_ready": output_ready,
        "complete": complete,
        "blocked_reason": blocked_reason,
        "receipt_path": receipt_path,
        "log_path": log_path,
        "safety_state": "candidate_outputs_only / no trusted memory write / no patch apply / no model runtime",
        "autonomy_scope": AUTONOMY_SCOPE,
        "data_source_path": data_source,
        "real_job_count": len(jobs),
        "returned_status_count": len(statuses),
        "returned_result_count": len(results),
        "validation_warnings": validation_warnings,
    }


def collect_status() -> dict[str, object]:
    protocol = protocol_contract()
    registry = worker_registry()
    workers = [package_status(worker_id) for worker_id in WORKER_IDS]
    package_count = sum(1 for worker_id in WORKER_IDS if worker_package_path(worker_id).exists())
    real_job_count = sum(int(worker["real_job_count"]) for worker in workers)
    returned_status_count = sum(int(worker["returned_status_count"]) for worker in workers)
    returned_result_count = sum(int(worker["returned_result_count"]) for worker in workers)
    current = next((worker for worker in workers if worker["returned_result_count"]), None)
    if current is None:
        current = next((worker for worker in workers if worker["returned_status_count"]), None)
    if current is None:
        current = next((worker for worker in workers if worker["real_job_count"]), None)

    if package_count == 0:
        overall = HONEST_STATES["no_workers"]
    elif real_job_count == 0 and returned_status_count == 0 and returned_result_count == 0:
        overall = HONEST_STATES["no_jobs"]
    elif real_job_count > 0 and returned_status_count == 0 and returned_result_count == 0:
        overall = HONEST_STATES["awaiting_status"]
    elif returned_status_count > 0 and returned_result_count == 0:
        overall = HONEST_STATES["no_result"]
    else:
        overall = HONEST_STATES["returned"]

    return {
        "protocol_name": protocol.get("protocol_name", "Engel Multi Android Remote Workers Protocol V1"),
        "routing_layer": ROUTING_LAYER,
        "connection_mode": CONNECTION_MODE,
        "real_data_only": True,
        "fake_live_data_allowed": False,
        "safety_states": SAFETY_STATES,
        "registry_path": rel(REGISTRY_PATH),
        "registry_present": REGISTRY_PATH.exists(),
        "registry_workers_configured": len(registry.get("workers", [])) if isinstance(registry.get("workers", []), list) else 0,
        "worker_package_count": package_count,
        "real_job_count": real_job_count,
        "returned_status_count": returned_status_count,
        "returned_result_count": returned_result_count,
        "overall_state": overall,
        "current_selected_job": current or {},
        "current_job_fields": CURRENT_JOB_FIELDS,
        "worker_list_fields": WORKER_LIST_FIELDS,
        "workers": workers,
        "honest_states": list(HONEST_STATES.values()),
        "boundaries": {
            "engel_communication_router_routing_required": True,
            "remote_worker_not_queen": True,
            "manual_transfer_mode_only": True,
            "no_phone_connection": True,
            "no_android_runtime_execution_from_engel": True,
            "candidate_outputs_only": True,
            "no_trusted_memory_write": True,
            "no_patch_apply": True,
            "no_provider_network": True,
            "no_model_runtime": True,
            "no_startup_autorun": True,
            "no_fake_worker_progress": True,
        },
    }


def render_worker(worker: dict[str, object]) -> str:
    return "\n".join(
        [
            f"- {worker['worker_name']} ({worker['worker_id']})",
            f"  device label: {worker['device_label']}",
            f"  role: {worker['role']}",
            f"  connection mode: {worker['connection_mode']}",
            f"  state: {worker['state']}",
            f"  current job id: {worker['current_job_id'] or '(none)'}",
            f"  current job title: {worker['current_job_title'] or '(none)'}",
            f"  job status: {worker['job_status']}",
            f"  progress percentage: {worker['progress_percent']}",
            f"  output-ready state: {worker['output_ready']}",
            f"  blocked reason: {worker['blocked_reason'] or '(none)'}",
            f"  safety state: {worker['safety_state']}",
            f"  autonomy scope: {worker['autonomy_scope']}",
            f"  data source path: {worker['data_source_path']}",
        ]
    )


def render_status() -> str:
    payload = collect_status()
    current = payload["current_selected_job"]
    lines = [
        "Engel Multi Android Remote Workers Protocol V1",
        "",
        f"Routing layer: {payload['routing_layer']}",
        f"Connection mode: {payload['connection_mode']}",
        f"Real data only: {payload['real_data_only']}",
        f"Fake live data allowed: {payload['fake_live_data_allowed']}",
        f"Overall state: {payload['overall_state']}",
        f"Worker packages configured: {payload['worker_package_count']}",
        f"Real job packets: {payload['real_job_count']}",
        f"Returned status packets: {payload['returned_status_count']}",
        f"Returned result packets: {payload['returned_result_count']}",
        "",
        "Current selected job",
    ]
    if isinstance(current, dict) and current:
        lines.extend(
            [
                f"- current job title: {current.get('current_job_title') or '(none)'}",
                f"- job id: {current.get('current_job_id') or '(none)'}",
                f"- assigned worker: {current.get('worker_name')} ({current.get('worker_id')})",
                f"- job type: {current.get('role')}",
                f"- status: {current.get('job_status')}",
                f"- progress percentage: {current.get('progress_percent')}",
                f"- current step: {current.get('current_step') or '(none)'}",
                f"- last update time: {current.get('last_update') or '(none)'}",
                f"- blocked reason: {current.get('blocked_reason') or '(none)'}",
                f"- complete yes/no: {current.get('complete')}",
                f"- output ready yes/no: {current.get('output_ready')}",
                f"- receipt/log paths: {current.get('receipt_path') or '(none)'} / {current.get('log_path') or '(none)'}",
                f"- safety status: {current.get('safety_state')}",
                f"- autonomy status: {current.get('autonomy_scope')}",
                f"- data source path: {current.get('data_source_path')}",
            ]
        )
    else:
        lines.append("- (none)")
    lines.extend(["", "Remote Workers"])
    for worker in payload["workers"]:
        lines.append(render_worker(worker))
    lines.extend(
        [
            "",
            "Safety",
            "- Engel Communication Router routing is required.",
            "- Android Remote Workers are Remote Workers / Mobile Workers, not Queens.",
            "- No phone connection, Android runtime execution from Engel, ADB, SSH, socket server, cloud sync, network/provider/browser behavior, model runtime, trusted-memory write, patch apply, source/route mutation, background worker, or startup autorun is enabled.",
            "- Returned worker outputs are candidate-only and require human review.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_check_links() -> str:
    payload = collect_status()
    lines = ["Engel Multi Android Remote Workers link check", ""]
    required = [
        REGISTRY_PATH,
        ROOT / "memory" / "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.json",
        ROOT / "memory" / "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md",
        ROOT / "tools" / "verify_engel_multi_android_remote_workers.py",
    ]
    for worker_id in WORKER_IDS:
        package = worker_package_path(worker_id)
        required.extend(
            [
                package / "config" / "worker_identity.json",
                package / "config" / "worker_capabilities.json",
                package / "config" / "worker_autonomy_policy.json",
                package / "remote_worker_runner.py",
                package / "remote_worker_status.py",
                package / "remote_worker_job_view.py",
                package / "README_ANDROID_SETUP.md",
            ]
        )
    for path in required:
        lines.append(("PASS " if path.exists() else "MISSING ") + rel(path))
    lines.extend(["", "Overall state: " + str(payload["overall_state"])])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Engel multi Android Remote Worker status.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Print multi-worker status.")
    mode.add_argument("--json", action="store_true", help="Print multi-worker status JSON.")
    mode.add_argument("--workers", action="store_true", help="Print worker list.")
    mode.add_argument("--current-job", action="store_true", help="Print selected current job.")
    mode.add_argument("--check-links", action="store_true", help="Check expected local files.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    args = build_parser().parse_args(argv)
    payload = collect_status()
    if args.json:
        out.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    elif args.workers:
        for worker in payload["workers"]:
            out.write(render_worker(worker) + "\n")
    elif args.current_job:
        out.write(json.dumps(payload["current_selected_job"], indent=2, sort_keys=True) + "\n")
    elif args.check_links:
        out.write(render_check_links())
    else:
        out.write(render_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
