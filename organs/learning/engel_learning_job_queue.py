from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

import engel_global_password_gate as global_password_gate


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
QUEUE_DIR = PROJECT_ROOT / "reports" / "learning_job_queue"
RECEIPT_DIR = PROJECT_ROOT / "reports" / "learning_job_queue_receipts"
CONTRACT_JSON = PROJECT_ROOT / "memory" / "ENGEL_LEARNING_JOB_QUEUE_CONTRACT_V1.json"
TOPIC_LIBRARY_MD = PROJECT_ROOT / "memory" / "ENGEL_SELF_RESEARCH_TOPIC_LIBRARY_V1.md"
APPROVED_LIBRARY_ROOT = PROJECT_ROOT / "engel_library" / "approved_library"

QUEUE_STATUS = [
    "LEARNING_JOB_QUEUE",
    "QUEUE_CONTRACT",
    "LOCAL_ONLY",
    "CANDIDATE_LEARNING_ONLY",
    "EXPLICIT_JOBS_ONLY",
    "APPROVED_LOCAL_SOURCES_ONLY",
    "REAL_SOURCE_REQUIRED",
    "SOURCE_FILE_MUST_EXIST",
    "NO_FAKE_QUEUE_RECORDS",
    "NO_FAKE_APPROVALS",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_TRUSTED_MEMORY",
    "PASSWORD_GATE_REQUIRED_FOR_WRITE_RUN",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "HUMAN_REVIEW_REQUIRED",
    "RECEIPTS_REQUIRED",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_AUTO_DISCOVERY",
    "NO_RECURSIVE_SCAN",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

JOB_FIELDS = [
    "job_id",
    "created_at",
    "created_by",
    "topic_id",
    "topic_title",
    "source_path",
    "source_type",
    "source_review_status",
    "source_approval_reference",
    "learning_goal",
    "allowed_outputs",
    "forbidden_outputs",
    "max_input_chars",
    "max_runtime_seconds",
    "priority",
    "status",
    "safety_boundary",
    "required_verifiers",
    "receipt_required",
    "human_review_required",
    "labels",
]

JOB_STATUS_VALUES = [
    "draft",
    "queued",
    "hold_source_not_approved",
    "hold_missing_topic",
    "hold_invalid_path",
    "hold_source_missing",
    "hold_forbidden_source_type",
    "ready_for_dry_run",
    "ready_for_candidate_learning",
    "completed_candidate_outputs",
    "stopped_unsafe",
    "rejected",
]

ALLOWED_SOURCE_TYPES = [
    "approved_python_doc",
    "approved_coding_reference",
    "approved_math_reference",
    "approved_security_reference",
    "approved_engel_manual",
    "approved_report_or_receipt",
    "approved_local_research_note",
    "approved_android_worker_reference",
    "approved_wsl_runtime_note",
    "approved_library_material",
]

FORBIDDEN_SOURCE_TYPES = [
    "raw_unreviewed_download",
    "model_file",
    "WSL_distro_filesystem",
    "WSL_tar",
    "executable_file",
    "binary_file",
    "live_package_artifact",
    "staging_package_artifact",
    "trusted_memory_file",
    "source_code_file_unless_explicitly_approved",
    "URL",
    "external_drive_unapproved",
    "phone_file",
    "android_runtime_file",
]

QUEUE_LABELS = [
    "CANDIDATE_LEARNING_ONLY",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_TRUSTED_MEMORY",
    "HUMAN_REVIEW_REQUIRED",
    "NO_AUTOMATION_TRIGGERED",
]

ALLOWED_OUTPUTS = [
    "untrusted_research_note",
    "lesson_candidate",
    "memory_candidate_proposal",
    "verifier_improvement_candidate",
    "self_fix_improvement_candidate",
    "research_receipt",
]

FORBIDDEN_OUTPUTS = [
    "trusted_memory",
    "applied_patch",
    "executed_code",
    "trained_model",
    "indexed_content",
    "runtime_loaded_content",
    "provider_request",
    "browser_session",
    "automatic_download",
    "autonomous_fix",
]

REQUIRED_VERIFIERS = [
    "tools\\verify_engel_learning_job_queue.py",
    "tools\\verify_untrusted_content_guard.py",
    "tools\\verify_prompt_injection_guard.py",
    "tools\\verify_authority_hierarchy.py",
]

SAFETY_BOUNDARY = (
    "LEARNING_JOB_QUEUE / CANDIDATE_LEARNING_ONLY / EXPLICIT_JOBS_ONLY / "
    "APPROVED_LOCAL_SOURCES_ONLY / UNTRUSTED_OUTPUTS_ONLY / NOT_TRUSTED_MEMORY / "
    "NO_AUTOMATION_TRIGGERED. No learning job is run by this queue. No trusted memory write, "
    "source mutation, patch apply, provider call, network, browser, model loading, inference, "
    "training, WSL execution, Hermes execution, background worker, startup autorun, recursive scan, "
    "wildcard discovery, Android connection, fake queue record, fake approval, fake success, or auto approval."
)


class LearningJobQueueError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_").lower() or "learning_job"


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve())).replace("/", "\\")


def load_topic_titles() -> dict[str, str]:
    if not TOPIC_LIBRARY_MD.exists():
        return {}
    titles: dict[str, str] = {}
    for line in TOPIC_LIBRARY_MD.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("| `SRT-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 6:
            topic_id = cells[0].strip("`")
            title = cells[5]
            titles[topic_id] = title
    return titles


def reject_source_text(raw_source: str) -> None:
    if not raw_source or not raw_source.strip():
        raise LearningJobQueueError("source path is required")
    lowered = raw_source.lower()
    uppered = raw_source.upper()
    if lowered.startswith(("http://", "https://")) or "://" in lowered:
        raise LearningJobQueueError("URL sources are forbidden")
    if raw_source.startswith("\\\\"):
        raise LearningJobQueueError("UNC paths are forbidden")
    if any(marker in raw_source for marker in ("*", "?", "[")):
        raise LearningJobQueueError("wildcard source discovery is forbidden")
    if uppered.startswith(("E:\\", "G:\\")):
        raise LearningJobQueueError("external drive sources are forbidden unless separately approved")


def resolve_source(raw_source: str) -> Path:
    reject_source_text(raw_source)
    candidate = Path(raw_source)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve(strict=False)
    root = PROJECT_ROOT.resolve()
    if not is_relative_to(resolved, root):
        raise LearningJobQueueError("source path must be project-local")
    if not resolved.exists():
        raise LearningJobQueueError("source path does not exist")
    if resolved.is_dir():
        raise LearningJobQueueError("source must be one explicit file, not a folder")
    parts = [part.lower() for part in resolved.relative_to(root).parts]
    if parts and parts[0] == "live":
        raise LearningJobQueueError("live package artifacts are forbidden sources")
    if parts and parts[0] == "staging":
        raise LearningJobQueueError("staging package artifacts are forbidden sources")
    if any(part in {"models", "model", "hf", "ollama", "llama", "trusted_memory"} for part in parts):
        raise LearningJobQueueError("model/trusted-memory paths are forbidden sources")
    if any(part in {"wsl", "ubuntu"} for part in parts) or resolved.suffix.lower() == ".tar":
        raise LearningJobQueueError("WSL distro folders and tar files are forbidden sources")
    if any(part in {"android_runtime", "phone", "phone_files"} for part in parts):
        raise LearningJobQueueError("Android runtime and phone files are forbidden sources")
    if resolved.suffix.lower() in {".exe", ".dll", ".pyd", ".so", ".bat", ".cmd", ".ps1", ".sh", ".gguf"}:
        raise LearningJobQueueError("executable, script, binary, and model files are forbidden sources")
    return resolved


def infer_source_type(path: Path) -> tuple[str, str, str]:
    rel = project_relative(path)
    rel_lower = rel.lower()
    if rel_lower.startswith("memory\\"):
        return "approved_engel_manual", "project_contract_or_memory_doc", rel
    if rel_lower.startswith("reports\\codex_bridge\\") or rel_lower.startswith("reports\\"):
        return "approved_report_or_receipt", "project_report_or_receipt", rel
    if rel_lower.startswith("engel_library\\approved_library\\python_docs\\"):
        return "approved_python_doc", "download_manifest_pending_human_review", "memory\\ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"
    if rel_lower.startswith("engel_library\\approved_library\\coding_language_references\\"):
        return "approved_coding_reference", "download_manifest_pending_human_review", "memory\\ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"
    if rel_lower.startswith("engel_library\\approved_library\\math_logic_reasoning_references\\") or rel_lower.startswith("engel_library\\approved_library\\algorithms_data_structures_references\\"):
        return "approved_math_reference", "download_manifest_pending_human_review", "memory\\ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"
    if rel_lower.startswith("engel_library\\approved_library\\security_prompt_injection_docs\\") or rel_lower.startswith("engel_library\\approved_library\\ai_safety_agent_safety_docs\\"):
        return "approved_security_reference", "download_manifest_pending_human_review", "memory\\ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"
    if rel_lower.startswith("engel_library\\approved_library\\android_remote_worker_references\\"):
        return "approved_android_worker_reference", "download_manifest_pending_human_review", "memory\\ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"
    if rel_lower.startswith("engel_library\\approved_library\\wsl_ubuntu_runtime_references\\"):
        return "approved_wsl_runtime_note", "download_manifest_pending_human_review", "memory\\ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"
    if rel_lower.startswith("engel_library\\approved_library\\"):
        return "approved_library_material", "download_manifest_pending_human_review", "memory\\ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"
    raise LearningJobQueueError("source is not in an approved local source area")


def make_job_id(topic_id: str, source_path: str, created_at: str) -> str:
    seed = f"ENGEL_LEARNING_JOB_QUEUE_V1|{topic_id}|{source_path}|{created_at}".encode("utf-8")
    return "learning_job_" + hashlib.sha256(seed).hexdigest()[:16]


def draft_job(topic_id: str, source: str, goal: str, *, status: str = "draft") -> dict[str, object]:
    topics = load_topic_titles()
    if topic_id not in topics:
        raise LearningJobQueueError("topic_id is missing from the Self-Research Topic Library")
    source_path = resolve_source(source)
    source_type, review_status, approval_ref = infer_source_type(source_path)
    created_at = now_utc()
    rel_source = project_relative(source_path)
    return {
        "job_id": make_job_id(topic_id, rel_source, created_at),
        "created_at": created_at,
        "created_by": "Engel Learning Job Queue V1",
        "topic_id": topic_id,
        "topic_title": topics[topic_id],
        "source_path": rel_source,
        "source_type": source_type,
        "source_review_status": review_status,
        "source_approval_reference": approval_ref,
        "learning_goal": goal.strip(),
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "forbidden_outputs": list(FORBIDDEN_OUTPUTS),
        "max_input_chars": 40000,
        "max_runtime_seconds": 180,
        "priority": "normal",
        "status": status,
        "labels": list(QUEUE_LABELS),
        "safety_boundary": SAFETY_BOUNDARY,
        "required_verifiers": list(REQUIRED_VERIFIERS),
        "receipt_required": True,
        "human_review_required": True,
    }


def validate_job_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise LearningJobQueueError("job JSON must be an object")
    missing = [field for field in JOB_FIELDS if field not in payload]
    if missing:
        raise LearningJobQueueError("job missing required fields: " + ", ".join(missing))
    if payload.get("status") not in JOB_STATUS_VALUES:
        raise LearningJobQueueError("job status is not allowed")
    if payload.get("source_type") not in ALLOWED_SOURCE_TYPES:
        raise LearningJobQueueError("job source_type is not allowed")
    labels = payload.get("labels", [])
    if not isinstance(labels, list) or any(label not in labels for label in QUEUE_LABELS):
        raise LearningJobQueueError("job is missing required candidate-only labels")
    if not payload.get("receipt_required") or not payload.get("human_review_required"):
        raise LearningJobQueueError("job must require receipt and human review")
    resolve_source(str(payload.get("source_path", "")))
    topics = load_topic_titles()
    if str(payload.get("topic_id")) not in topics:
        raise LearningJobQueueError("job topic_id is missing from topic library")
    if all(item in payload.get("forbidden_outputs", []) for item in ["trusted_memory", "applied_patch"]):
        return dict(payload)
    raise LearningJobQueueError("job forbidden_outputs must block trusted memory and patch apply")


def load_job_json(raw_path: str) -> tuple[Path, dict[str, object]]:
    path = resolve_source(raw_path)
    if path.suffix.lower() != ".json":
        raise LearningJobQueueError("job file must be JSON")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise LearningJobQueueError("job JSON could not be parsed") from exc
    return path, validate_job_payload(payload)


def queue_counts() -> dict[str, int]:
    counts = {status: 0 for status in JOB_STATUS_VALUES}
    if not QUEUE_DIR.exists():
        return counts
    for child in QUEUE_DIR.iterdir():
        if not child.is_file() or child.suffix.lower() != ".json":
            continue
        try:
            payload = json.loads(child.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        status = str(payload.get("status", ""))
        if status in counts:
            counts[status] += 1
    return counts


def render_status() -> str:
    counts = queue_counts()
    lines = [
        "Engel Learning Job Queue V1",
        "",
        "Status:",
        *[f"- {status}" for status in QUEUE_STATUS],
        "",
        f"Queue folder: {project_relative(QUEUE_DIR)}",
        f"Receipt folder: {project_relative(RECEIPT_DIR)}",
        "",
        "Counts:",
        *[f"- {status}: {count}" for status, count in counts.items()],
        "",
        "Boundary:",
        SAFETY_BOUNDARY,
        "",
        "Next step: Self-Learning Run Controller V1",
    ]
    return "\n".join(lines) + "\n"


def render_list() -> str:
    if not QUEUE_DIR.exists():
        return "No learning job queue files found.\n"
    files = [child for child in QUEUE_DIR.iterdir() if child.is_file() and child.suffix.lower() == ".json"]
    if not files:
        return "No learning job queue files found.\n"
    lines = ["Engel Learning Job Queue Files:"]
    for path in sorted(files):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            lines.append(f"- {path.name}: {payload.get('status')} / {payload.get('topic_id')} / {payload.get('source_type')}")
        except json.JSONDecodeError:
            lines.append(f"- {path.name}: invalid_json")
    return "\n".join(lines) + "\n"


def write_job_file(job: dict[str, object]) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (QUEUE_DIR / f"{safe_slug(str(job['job_id']))}.json").resolve(strict=False)
    if not is_relative_to(output_path, QUEUE_DIR.resolve()):
        raise LearningJobQueueError("queue output escaped queue folder")
    output_path.write_text(json.dumps(job, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def write_receipt(action: str, job: dict[str, object], output_path: Path, password_checked: bool, protected_action_id: str) -> Path:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = now_utc()
    receipt_id = "learning_job_queue_receipt_" + hashlib.sha256(f"{action}|{job['job_id']}|{created_at}".encode("utf-8")).hexdigest()[:16]
    receipt = {
        "receipt_id": receipt_id,
        "created_at": created_at,
        "action": action,
        "job_id": job["job_id"],
        "topic_id": job["topic_id"],
        "source_path": job["source_path"],
        "source_type": job["source_type"],
        "source_review_status": job["source_review_status"],
        "decision": "metadata_written_only_no_learning_run",
        "safety_boundary": SAFETY_BOUNDARY,
        "password_gate_checked": password_checked,
        "protected_action_id": protected_action_id,
        "output_path": project_relative(output_path),
        "no_trusted_memory_write": True,
        "no_source_mutation": True,
        "no_provider_network_browser": True,
        "no_model_runtime": True,
        "no_wsl_execution": True,
        "no_hermes_execution": True,
        "no_android_connection": True,
        "human_review_required": True,
    }
    receipt_path = RECEIPT_DIR / f"{receipt_id}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def require_password(action_id: str) -> bool:
    global_password_gate.prompt_and_require_action(action_id)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Learning Job Queue V1.")
    parser.add_argument("--status", action="store_true", help="Show queue status and safety boundary.")
    parser.add_argument("--list", action="store_true", help="List queue files non-recursively.")
    parser.add_argument("--validate-job", metavar="JOB_JSON", help="Validate one explicit job JSON file.")
    parser.add_argument("--draft-job", action="store_true", help="Print a draft job JSON to stdout only.")
    parser.add_argument("--write-draft", action="store_true", help="Write a draft job JSON to reports\\learning_job_queue.")
    parser.add_argument("--queue-job", metavar="JOB_JSON", help="Mark one explicit job JSON as queued after password gate.")
    parser.add_argument("--topic-id", help="Self-research topic id for draft job.")
    parser.add_argument("--source", help="Explicit project-local or approved-library source path.")
    parser.add_argument("--goal", help="Learning goal.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for global password for protected write/queue paths.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.status:
            out.write(render_status())
            return 0
        if args.list:
            out.write(render_list())
            return 0
        if args.validate_job:
            path, job = load_job_json(args.validate_job)
            out.write(f"VALID_LEARNING_JOB {project_relative(path)} {job['job_id']}\n")
            return 0
        if args.draft_job or args.write_draft:
            if not args.topic_id or not args.source or not args.goal:
                err.write("--topic-id, --source, and --goal are required for draft jobs.\n")
                return 2
            job = draft_job(args.topic_id, args.source, args.goal, status="draft")
            if args.draft_job:
                out.write(json.dumps(job, indent=2, sort_keys=True) + "\n")
                return 0
            if not args.password_prompt:
                err.write("Protected write requires --password-prompt.\n")
                return 2
            checked = require_password("write_learning_job_draft")
            output_path = write_job_file(job)
            receipt_path = write_receipt("write_learning_job_draft", job, output_path, checked, "write_learning_job_draft")
            out.write(f"WROTE_LEARNING_JOB_DRAFT {project_relative(output_path)}\n")
            out.write(f"WROTE_LEARNING_JOB_RECEIPT {project_relative(receipt_path)}\n")
            return 0
        if args.queue_job:
            if not args.password_prompt:
                err.write("Protected queue action requires --password-prompt.\n")
                return 2
            _, job = load_job_json(args.queue_job)
            checked = require_password("queue_learning_job")
            job["status"] = "queued"
            output_path = write_job_file(job)
            receipt_path = write_receipt("queue_learning_job", job, output_path, checked, "queue_learning_job")
            out.write(f"QUEUED_LEARNING_JOB {project_relative(output_path)}\n")
            out.write(f"WROTE_LEARNING_JOB_RECEIPT {project_relative(receipt_path)}\n")
            return 0
        out.write(render_status())
        return 0
    except (LearningJobQueueError, global_password_gate.PasswordGateError) as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
