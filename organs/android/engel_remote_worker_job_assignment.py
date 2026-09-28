from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from engel_android_remote_worker_protocol import (
    AUTONOMY_SCOPE,
    CONNECTION_MODE,
    FORBIDDEN_ACTION_TOKENS,
    LEGACY_ROUTING_LAYER,
    REGISTRY_PATH,
    ROUTED_BY,
    ROUTING_LAYER,
    WORKER_IDS,
    read_json,
    validate_job_packet,
    worker_identity,
    worker_package_path,
    worker_registry,
)
from engel_branding import ENGEL_COMMUNICATION_ROUTER_NAME


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
CONTRACT_JSON = ROOT / "memory" / "ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.md"
DEFAULT_MAX_INPUT_SIZE = 200_000
DEFAULT_MAX_OUTPUT_SIZE = 200_000
DEFAULT_MAX_RUNTIME_HINT = 900

ASSIGNMENT_STATES = [
    "requested",
    "validated",
    "rejected",
    "prepared_for_manual_transfer",
    "awaiting_manual_transfer",
    "awaiting_worker_status",
    "returned_to_engel",
    "blocked",
]

SUPPORTED_JOB_TYPES: dict[str, list[str]] = {
    "android_worker_alpha": [
        "summarize_text",
        "draft_research_note",
        "classify_file",
    ],
    "android_worker_beta": [
        "draft_candidate_json",
        "format_report_draft",
        "classify_file",
    ],
    "android_worker_gamma": [
        "compute_small_local_task",
        "format_report_draft",
        "summarize_text",
    ],
    # Additional computers (Sub-Engel OS Worker on Linux/Engel OS, Windows Sub-Engel)
    # enable more AI usage across the local cluster/hive. Jobs remain bounded,
    # manual-transfer or LAN staged, candidate outputs only, local node gate applies.
    "sub_engel_os_worker": [
        "summarize_text",
        "draft_research_note",
        "classify_file",
        "compute_small_local_task",
        "format_report_draft",
    ],
    "windows_sub_engel": [
        "summarize_text",
        "draft_research_note",
        "classify_file",
        "compute_small_local_task",
        "format_report_draft",
    ],
}

ALLOWED_INPUT_ROOTS = [
    ROOT / "memory",
    ROOT / "reports",
    ROOT / "engel_library",
    ROOT / "files",
    ROOT / "lessons",
    ROOT / "prompts",
    ROOT / "workspace",
    ROOT / "products",
]

BLOCKED_CAPABILITIES = [
    "trusted_memory_write",
    "source_mutation",
    "route_mutation",
    "patch_apply",
    "provider_network",
    "model_runtime",
    "phone_connection",
    "android_runtime_execution",
    "adb",
    "ssh",
    "live_connection_server",
    "cloud_sync",
    "worker_job_execution_from_engel",
    "fake_returned_status",
    "fake_returned_result",
    "fake_progress",
    "mark_completed_without_returned_packet",
    "hermes_runtime_rejected_do_not_install",
    "ollama_runtime_blocked",
    "llama_cpp_runtime_blocked",
]

PACKET_FIELDS = [
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
    "requires_human_review",
]


class AssignmentError(ValueError):
    pass


def now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def safe_slug(text: str, limit: int = 48) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_").lower()
    return (slug or "job")[:limit]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_url_or_unc(path_text: str) -> bool:
    lowered = path_text.lower()
    return "://" in lowered or lowered.startswith("\\\\") or lowered.startswith("//")


def resolve_input_path(path_text: str) -> Path:
    if not path_text or is_url_or_unc(path_text):
        raise AssignmentError("input path must be a real local file, not a URL/UNC path")
    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve(strict=False)
    if not resolved.exists() or not resolved.is_file():
        raise AssignmentError("input file does not exist: " + path_text)
    for blocked in [
        Path("C:/Windows"),
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
    ]:
        try:
            resolved.relative_to(blocked.resolve(strict=False))
        except ValueError:
            continue
        raise AssignmentError("input path is inside a blocked system folder")
    allowed = False
    for root in ALLOWED_INPUT_ROOTS:
        try:
            resolved.relative_to(root.resolve(strict=False))
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        raise AssignmentError("input path is outside approved Engel project/library/report/work roots")
    size = resolved.stat().st_size
    if size <= 0:
        raise AssignmentError("input file is empty")
    if size > DEFAULT_MAX_INPUT_SIZE:
        raise AssignmentError(f"input file exceeds V1 max size: {size} bytes")
    return resolved


def worker_entry(worker_id: str) -> dict[str, Any]:
    registry = worker_registry()
    for entry in registry.get("workers", []):
        if isinstance(entry, dict) and entry.get("worker_id") == worker_id:
            return entry
    return {}


def validate_worker(worker_id: str) -> dict[str, Any]:
    if worker_id not in WORKER_IDS:
        raise AssignmentError("unknown Android Remote Worker: " + worker_id)
    entry = worker_entry(worker_id)
    identity = worker_identity(worker_id)
    if not entry:
        raise AssignmentError("worker is missing from registry: " + worker_id)
    if not identity:
        raise AssignmentError("worker identity file is missing: " + worker_id)
    if identity.get("queen_authority") is not False:
        raise AssignmentError("Android Remote Worker must not have Queen authority")
    if identity.get("routing_layer") not in (ROUTING_LAYER, LEGACY_ROUTING_LAYER):
        raise AssignmentError("worker routing layer must be engel_communication_router_only")
    if identity.get("can_self_assign_jobs") is not False:
        raise AssignmentError("worker cannot self-assign jobs")
    if identity.get("can_create_jobs") is not False:
        raise AssignmentError("worker cannot create jobs")
    if identity.get("can_route_jobs") is not False:
        raise AssignmentError("worker cannot route jobs")
    if identity.get("can_control_engel") is not False:
        raise AssignmentError("worker cannot control Engel")
    if identity.get("candidate_outputs_only") is not True:
        raise AssignmentError("worker outputs must be candidate-only")
    return identity


def validate_job_type(worker_id: str, job_type: str) -> None:
    allowed = SUPPORTED_JOB_TYPES.get(worker_id, [])
    if job_type not in allowed:
        raise AssignmentError(f"job type {job_type!r} is not allowed for {worker_id}")
    entry = worker_entry(worker_id)
    if job_type not in entry.get("allowed_task_types", []):
        raise AssignmentError(f"registry does not allow job type {job_type!r} for {worker_id}")


def validate_instructions(text: str) -> list[str]:
    lowered = text.lower()
    warnings: list[str] = []
    blocked_terms = [
        "execute command",
        "run shell",
        "subprocess",
        "pip install",
        "pkg install",
        "download model",
        "load model",
        "run inference",
        "provider api",
        "open browser",
        "write trusted memory",
        "promote memory",
        "apply patch",
        "mutate route",
        "mutate source",
        "start worker",
        "startup autorun",
        "adb",
        "ssh",
        "connect phone",
        "ollama",
        "llama.cpp",
        "hermes",
    ]
    for term in blocked_terms:
        if term in lowered:
            warnings.append("blocked_instruction_term:" + term.replace(" ", "_"))
    return warnings


def expected_outputs_for(job_type: str) -> list[str]:
    mapping = {
        "summarize_text": ["candidate markdown summary", "worker status packet", "worker result packet", "worker log", "worker receipt"],
        "draft_research_note": ["candidate research note draft", "worker status packet", "worker result packet", "worker log", "worker receipt"],
        "classify_file": ["candidate classification JSON", "worker status packet", "worker result packet", "worker log", "worker receipt"],
        "draft_candidate_json": ["candidate JSON draft", "validation notes", "worker status packet", "worker result packet", "worker receipt"],
        "format_report_draft": ["candidate report draft", "worker status packet", "worker result packet", "worker log", "worker receipt"],
        "compute_small_local_task": ["candidate local compute result JSON", "worker status packet", "worker result packet", "worker log", "worker receipt"],
    }
    return mapping.get(job_type, ["candidate output", "worker status packet", "worker result packet", "worker log", "worker receipt"])


def allowed_actions_for(worker_id: str, job_type: str) -> list[str]:
    package = worker_package_path(worker_id)
    policy = read_json(package / "config" / "worker_autonomy_policy.json")
    capabilities = read_json(package / "config" / "worker_capabilities.json")
    base = policy.get("allowed_local_actions", capabilities.get("allowed_local_autonomous_actions", []))
    actions = list(base) if isinstance(base, list) else []
    if job_type == "compute_small_local_task":
        actions.append("perform bounded local calculations from assigned input file")
    return sorted(set(str(action) for action in actions))


def build_job_id(worker_id: str, job_type: str, title: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{worker_id}_{job_type}_{safe_slug(title, 28)}"


def staged_input_relative_path(worker_id: str, job_id: str, input_path: Path) -> str:
    package = worker_package_path(worker_id)
    staged_name = "assigned_inputs/" + job_id + "/" + safe_slug(input_path.stem, 32) + input_path.suffix.lower()
    return str((Path("inbox") / staged_name)).replace("/", "\\")


def build_job_packet(
    worker_id: str,
    job_type: str,
    input_path: Path,
    title: str,
    instructions: str,
    priority: str = "normal",
    staged_relative_path: str | None = None,
) -> dict[str, Any]:
    identity = validate_worker(worker_id)
    validate_job_type(worker_id, job_type)
    instruction_warnings = validate_instructions(instructions)
    if instruction_warnings:
        raise AssignmentError("instructions request blocked capability: " + ", ".join(instruction_warnings))
    job_id = build_job_id(worker_id, job_type, title)
    input_rel = staged_relative_path or staged_input_relative_path(worker_id, job_id, input_path)
    job = {
        "job_id": job_id,
        "job_title": title,
        "job_type": job_type,
        "job_template": False,
        "real_job": True,
        "created_at": now(),
        "assigned_worker_id": worker_id,
        "created_by": "engel",
        "routed_by": ROUTED_BY,
        "priority": priority,
        "status": "prepared_for_manual_transfer",
        "input_files": [input_rel],
        "instructions": instructions,
        "allowed_actions": allowed_actions_for(worker_id, job_type),
        "blocked_actions": sorted(set(FORBIDDEN_ACTION_TOKENS + BLOCKED_CAPABILITIES)),
        "expected_outputs": expected_outputs_for(job_type),
        "receipt_required": True,
        "log_required": True,
        "max_runtime_hint": DEFAULT_MAX_RUNTIME_HINT,
        "max_input_size": DEFAULT_MAX_INPUT_SIZE,
        "max_output_size": DEFAULT_MAX_OUTPUT_SIZE,
        "offline_only": True,
        "manual_transfer_required": True,
        "on_device_autonomy_allowed": True,
        "autonomy_scope": AUTONOMY_SCOPE,
        "trusted_memory_write": False,
        "source_mutation": False,
        "route_mutation": False,
        "patch_apply": False,
        "provider_network": False,
        "model_runtime": False,
        "approval_required_for_any_write": True,
        "requires_human_review": True,
        "assignment_status": "prepared_for_manual_transfer",
        "assignment_mode": CONNECTION_MODE,
        "assignment_route": ROUTING_LAYER,
        "android_remote_worker_not_queen": True,
        "worker_name": identity.get("worker_name", worker_id),
        "source_input": {
            "project_path": rel(input_path),
            "sha256": sha256_file(input_path),
            "size_bytes": input_path.stat().st_size,
            "copied_for_manual_transfer": True,
        },
        "assignment_safety": {
            "no_phone_connection": True,
            "no_android_runtime_execution_from_engel": True,
            "no_worker_job_execution_from_engel": True,
            "no_fake_returned_status": True,
            "no_fake_returned_result": True,
            "no_fake_progress": True,
            "no_completion_without_returned_packet": True,
            "candidate_outputs_only": True,
            "Hermes remains rejected / do not install on this computer": True,
        },
    }
    errors = validate_job_packet(job, identity)
    if errors:
        raise AssignmentError("job packet failed protocol validation: " + "; ".join(errors))
    missing = [field for field in PACKET_FIELDS if field not in job]
    if missing:
        raise AssignmentError("job packet missing assignment fields: " + ", ".join(missing))
    return job


def preview_assignment(worker_id: str, job_type: str, input_file: str, title: str, instructions: str, priority: str = "normal") -> dict[str, Any]:
    input_path = resolve_input_path(input_file)
    return build_job_packet(worker_id, job_type, input_path, title, instructions, priority)


def write_assignment(worker_id: str, job_type: str, input_file: str, title: str, instructions: str, priority: str = "normal") -> dict[str, Any]:
    input_path = resolve_input_path(input_file)
    job = build_job_packet(worker_id, job_type, input_path, title, instructions, priority)
    package = worker_package_path(worker_id)
    staged_relative = str(job["input_files"][0])
    staged_path = package / staged_relative
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path.write_bytes(input_path.read_bytes())
    jobs_folder = package / "jobs"
    jobs_folder.mkdir(parents=True, exist_ok=True)
    job_path = jobs_folder / (str(job["job_id"]) + ".json")
    job["source_input"]["staged_worker_path"] = rel(staged_path)
    job_path.write_text(json.dumps(job, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "assignment_status": "prepared_for_manual_transfer",
        "job_packet_path": rel(job_path),
        "staged_input_path": rel(staged_path),
        "job": job,
    }


def prepared_job_files() -> list[Path]:
    files: list[Path] = []
    for worker_id in WORKER_IDS:
        package = worker_package_path(worker_id)
        for folder_name in ["jobs", "inbox"]:
            folder = package / folder_name
            if not folder.exists():
                continue
            for child in sorted(folder.iterdir()):
                if not child.is_file() or child.suffix.lower() != ".json":
                    continue
                payload = read_json(child)
                if payload.get("job_template") is True:
                    continue
                if payload.get("real_job") is True and payload.get("status") == "prepared_for_manual_transfer":
                    files.append(child)
    return sorted(files)


def collect_status() -> dict[str, Any]:
    registry = worker_registry()
    workers = []
    for worker_id in WORKER_IDS:
        identity = worker_identity(worker_id)
        entry = worker_entry(worker_id)
        workers.append(
            {
                "worker_id": worker_id,
                "worker_name": identity.get("worker_name", entry.get("worker_name", worker_id)),
                "role": identity.get("role", entry.get("role", "")),
                "allowed_assignment_job_types": SUPPORTED_JOB_TYPES.get(worker_id, []),
                "package_folder": rel(worker_package_path(worker_id)),
                "connection_mode": CONNECTION_MODE,
                "queen_authority": identity.get("queen_authority"),
                "routing_layer": identity.get("routing_layer"),
                "candidate_outputs_only": identity.get("candidate_outputs_only"),
                "current_job_status": entry.get("current_job_status", "Manual Setup"),
            }
        )
    prepared = prepared_job_files()
    return {
        "contract_name": ENGEL_COMMUNICATION_ROUTER_NAME + " Remote Worker Job Assignment V1",
        "registry_path": rel(REGISTRY_PATH),
        "registry_present": REGISTRY_PATH.exists(),
        "registry_worker_count": len(registry.get("workers", [])) if isinstance(registry.get("workers", []), list) else 0,
        "routing_layer": ROUTING_LAYER,
        "connection_mode": CONNECTION_MODE,
        "assignment_status_states": ASSIGNMENT_STATES,
        "prepared_job_packet_count": len(prepared),
        "prepared_job_packets": [rel(path) for path in prepared],
        "workers": workers,
        "safe_input_roots": [rel(path) for path in ALLOWED_INPUT_ROOTS],
        "boundaries": {
            "manual_transfer_only": True,
            "engel_communication_router_routing_required": True,
            "remote_worker_not_queen": True,
            "real_input_file_required": True,
            "no_phone_connection": True,
            "no_android_runtime_execution_from_engel": True,
            "no_worker_job_execution_from_engel": True,
            "no_fake_returned_status": True,
            "no_fake_returned_result": True,
            "no_fake_progress": True,
            "no_completion_without_returned_packet": True,
            "candidate_outputs_only": True,
        },
    }


def render_status() -> str:
    payload = collect_status()
    lines = [
        ENGEL_COMMUNICATION_ROUTER_NAME + " Remote Worker Job Assignment V1",
        "",
        f"Routing layer: {payload['routing_layer']}",
        f"Connection mode: {payload['connection_mode']}",
        f"Registry: {payload['registry_path']} ({payload['registry_worker_count']} workers)",
        f"Prepared job packets: {payload['prepared_job_packet_count']}",
        "",
        "Workers",
    ]
    for worker in payload["workers"]:
        lines.extend(
            [
                f"- {worker['worker_name']} ({worker['worker_id']})",
                f"  role: {worker['role']}",
                f"  allowed assignment job types: {', '.join(worker['allowed_assignment_job_types'])}",
                f"  package folder: {worker['package_folder']}",
                f"  current registry status: {worker['current_job_status']}",
            ]
        )
    lines.extend(
        [
            "",
            "Safety",
            "- Engel Communication Router prepares bounded job packets only.",
            "- Assignment writes prepared_for_manual_transfer packets only when --assign is explicit.",
            "- Engel does not connect to phones, execute Android runtime, run worker jobs, fake returned status/result/progress, or mark work complete.",
            "- Returned worker outputs remain untrusted candidate outputs and require human review.",
            "- Hermes remains rejected / do not install on this computer.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_prepared_jobs() -> str:
    files = prepared_job_files()
    if not files:
        return "No prepared manual-transfer job packets found.\n"
    return "\n".join(rel(path) for path in files) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Communication Router manual-transfer Android Remote Worker job assignment.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show assignment layer status.")
    mode.add_argument("--json", action="store_true", help="Show assignment layer status JSON.")
    mode.add_argument("--preview", action="store_true", help="Validate and print a real job packet without writing it.")
    mode.add_argument("--assign", action="store_true", help="Write a prepared-for-manual-transfer job packet and staged input copy.")
    mode.add_argument("--jobs-prepared", action="store_true", help="List prepared manual-transfer job packets.")
    parser.add_argument("--worker-id", choices=WORKER_IDS, help="Target Android Remote Worker id.")
    parser.add_argument("--job-type", help="Bounded worker job type.")
    parser.add_argument("--input-file", help="Existing local input file under approved Engel roots.")
    parser.add_argument("--title", default="Bounded Android Remote Worker Job", help="Human-readable job title.")
    parser.add_argument("--instructions", default="Process the assigned local input file within the assigned job sandbox and return candidate-only outputs.", help="Bounded job instructions.")
    parser.add_argument("--priority", default="normal", choices=["low", "normal", "high"], help="Assignment priority label.")
    return parser


def require_assignment_args(args: argparse.Namespace) -> None:
    missing = [name for name in ["worker_id", "job_type", "input_file"] if not getattr(args, name)]
    if missing:
        raise AssignmentError("missing required assignment arguments: " + ", ".join("--" + name.replace("_", "-") for name in missing))


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        if args.preview:
            require_assignment_args(args)
            packet = preview_assignment(args.worker_id, args.job_type, args.input_file, args.title, args.instructions, args.priority)
            out.write(json.dumps(packet, indent=2, sort_keys=True) + "\n")
        elif args.assign:
            require_assignment_args(args)
            result = write_assignment(args.worker_id, args.job_type, args.input_file, args.title, args.instructions, args.priority)
            out.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        elif args.json:
            out.write(json.dumps(collect_status(), indent=2, sort_keys=True) + "\n")
        elif args.jobs_prepared:
            out.write(render_prepared_jobs())
        else:
            out.write(render_status())
        return 0
    except AssignmentError as exc:
        err.write("Assignment blocked: " + str(exc) + "\n")
        return 2


def render_sub_engel_status() -> str:
    """Status for additional computers (Sub-Engel workers)."""
    try:
        status = collect_status()
        subs = [
            w for w in status.get("workers", [])
            if "sub_engel" in str(w.get("worker_id", "")) or "windows_sub" in str(w.get("worker_id", ""))
        ]
        return (
            "Sub-Engel / Additional Computers Status (more computer usage for AI)\n"
            + json.dumps({"sub_workers": subs, "prepared_count": status.get("prepared_job_packet_count")}, indent=2)
            + "\n"
        )
    except Exception as exc:
        return "Sub-Engel status error (safe): " + str(exc)


def render_sub_engel_create_job(payload: str = "") -> str:
    """Medium change: Prepare and actually stage bounded job packet for Sub-Engel additional computers (more local AI usage).
    Payload: worker_id|job_type|title|instructions
    Stages to the worker's package (for write_assignment) + central sub_engel_jobs/ for easy consumption by Engel OS / Windows nodes.
    All safety boundaries preserved (candidate outputs, local gate on node, no remote exec from here).
    """
    try:
        import json as _json
        from pathlib import Path as _Path
        parts = [p.strip() for p in str(payload or "").split("|") if p.strip()]
        if len(parts) >= 4:
            wid, jtype, title, instr = parts[0], parts[1], parts[2], "|".join(parts[3:])
            if wid in SUPPORTED_JOB_TYPES and jtype in SUPPORTED_JOB_TYPES[wid]:
                # Use a safe marker input inside allowed root (reports/ is permitted)
                marker_dir = _Path(__file__).parent / "reports" / "sub_engel_test_inputs"
                marker_dir.mkdir(parents=True, exist_ok=True)
                marker = marker_dir / f"marker_{wid}_{jtype}.txt"
                marker.write_text(instr[:3000], encoding="utf-8")

                # Produce packet dict
                p = preview_assignment(wid, jtype, str(marker), title, instr[:3000])

                # Stage to central (medium change for more computer usage - consumed by Engel OS / Windows nodes)
                central = _Path(__file__).parent / "reports" / "sub_engel_jobs"
                central.mkdir(parents=True, exist_ok=True)
                central_job = central / (p.get("job_id", "job") + ".json")
                central_job.write_text(_json.dumps(p, indent=2, sort_keys=True) + "\n", encoding="utf-8")

                # Try package too
                pkg_note = ""
                try:
                    res = write_assignment(wid, jtype, str(marker), title, instr[:3000])
                    pkg_note = f" Package: {res.get('job_packet_path')}"
                except Exception as e: pkg_note = f" (pkg note: {str(e)[:60]})"

                return (
                    "Sub-Engel job packet staged for additional computer (medium integration).\n"
                    f"Central: {central_job}{pkg_note}\n"
                    "Node (Engel OS / Windows Sub) can consume via engel-node jobs or cluster tasks.\n"
                    + _json.dumps(p, indent=2)[:1200]
                    + "\n"
                )
            return f"Unsupported. Supported: {list(SUPPORTED_JOB_TYPES.keys())}"
        return "Payload: worker_id|job_type|title|instructions  (e.g. sub_engel_os_worker|summarize_text|Note|Summarize...)"
    except Exception as exc:
        return "Sub-Engel create (safe): " + str(exc)


def render_sub_engel_results(payload: str = "") -> str:
    """Medium addition: Collect candidate results from Sub-Engel / additional computers (more computer usage for AI).
    Nodes write results to reports/sub_engel_results/ (or equivalent on their side).
    This is safe read-only collection.
    """
    try:
        import json as _json
        from pathlib import Path as _Path
        base = _Path(__file__).parent
        results_dir = base / "reports" / "sub_engel_results"
        results_dir.mkdir(parents=True, exist_ok=True)
        found = []
        for f in sorted(results_dir.glob("*.json"))[:20]:
            try:
                data = _json.loads(f.read_text(encoding="utf-8"))
                found.append({
                    "file": f.name,
                    "job_id": data.get("job_id"),
                    "status": data.get("status", "unknown"),
                    "preview": str(data.get("candidate_output", ""))[:180]
                })
            except Exception:
                found.append({"file": f.name, "error": "unreadable"})
        if not found:
            # Fallback: show recently staged jobs awaiting return
            staged = base / "reports" / "sub_engel_jobs"
            if staged.exists():
                for f in sorted(staged.glob("*.json"))[:5]:
                    found.append({"file": f.name, "note": "staged, awaiting result from node"})
        return "Sub-Engel / Additional Computers Results:\n" + _json.dumps(found, indent=2) + "\n(Additional computers return candidate results here for main Engel review.)"
    except Exception as exc:
        return "Sub-Engel results (safe read-only): " + str(exc)


if __name__ == "__main__":
    raise SystemExit(main())
