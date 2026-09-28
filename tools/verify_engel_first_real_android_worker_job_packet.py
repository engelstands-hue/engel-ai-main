from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALPHA_PACKAGE = ROOT / "remote_workers" / "android_worker_alpha"
BETA_PACKAGE = ROOT / "remote_workers" / "android_worker_beta"
GAMMA_PACKAGE = ROOT / "remote_workers" / "android_worker_gamma"
ALPHA_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_FIRST_REAL_ANDROID_REMOTE_WORKER_JOB_PACKET_V1.md"
BETA_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_FIRST_REAL_ANDROID_WORKER_BETA_JOB_PACKET_V1.md"
ASSIGNMENT_MODULE = ROOT / "engel_remote_worker_job_assignment.py"

# kept for backward compatibility (alpha-specific returned-artifact check)
WORKER_ID = "android_worker_alpha"

ALPHA_EXPECTED = {
    "worker_id": "android_worker_alpha",
    "worker_name": "Android Worker Alpha",
    "job_type": "summarize_text",
    "job_title": "Summarize Engel Remote Worker Protocol Report",
    "expected_outputs_required": [
        "candidate markdown summary",
        "worker status packet",
        "worker result packet",
        "worker log",
        "worker receipt",
    ],
}

BETA_EXPECTED = {
    "worker_id": "android_worker_beta",
    "worker_name": "Android Worker Beta",
    "job_type": "draft_candidate_json",
    "job_title": "Draft Candidate JSON From Worker Beta Package README",
    "expected_outputs_required": [
        "candidate JSON file with extracted beta package fields",
        "validation notes (text)",
        "worker status packet",
        "worker result packet",
        "worker log",
        "worker receipt",
    ],
}

ALLOWED_INPUT_ROOTS = [
    ROOT / "reports" / "codex_bridge",
    ROOT / "reports" / "candidate_set_approvals",
    ROOT / "memory",
    ROOT / "engel_library" / "approved_library",
    ROOT / "remote_workers",
    ROOT / "remote_workers" / "android_worker_beta",
]

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "subprocess",
    "threading",
    "multiprocessing",
    "shutil",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(read(path))
    require(isinstance(data, dict), "JSON root is not object: " + str(path.relative_to(ROOT)))
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def job_json_files() -> list[Path]:
    files: list[Path] = []
    for package in [ALPHA_PACKAGE, BETA_PACKAGE, GAMMA_PACKAGE]:
        folder = package / "jobs"
        if not folder.exists():
            continue
        for child in folder.iterdir():
            if child.is_file() and child.suffix.lower() == ".json":
                files.append(child)
    return sorted(files)


def artifact_files(package: Path, folder_name: str) -> list[Path]:
    folder = package / folder_name
    if not folder.exists():
        return []
    # Per-folder file-type filter:
    # - status/outbox/receipts: validate JSON control files (.json). Other
    #   files in outbox (e.g. *_summary.md, *_candidate.json fragments) are
    #   candidate outputs, referenced from the JSON result/receipt and
    #   validated as candidate-only content, not as control packets here.
    # - logs: validate .log files.
    allowed_suffix = {".log"} if folder_name == "logs" else {".json"}
    return sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.name != ".gitkeep" and path.suffix.lower() in allowed_suffix
    )


def path_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def check_assignment_module_static() -> None:
    tree = ast.parse(read(ASSIGNMENT_MODULE))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "assignment module imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "assignment module imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                require(func.id not in {"eval", "exec", "__import__"}, "assignment module uses forbidden dynamic call: " + func.id)


def validate_one_job_packet(job_path: Path, expected: dict[str, object]) -> dict[str, object]:
    job = load_json(job_path)
    label = str(expected["worker_id"])
    require(job.get("job_id") == job_path.stem, label + " job_id must match job packet filename")
    require(job.get("assigned_worker_id") == expected["worker_id"], "job must be assigned to " + label)
    require(job.get("worker_name") == expected["worker_name"], label + " worker name mismatch")
    require(job.get("job_type") == expected["job_type"], label + " job_type must be " + str(expected["job_type"]))
    require(job.get("job_title") == expected["job_title"], label + " job title mismatch")
    require(job.get("job_template") is False, label + " job_template must be false")
    require(job.get("real_job") is True, label + " real_job must be true")
    require(job.get("status") == "prepared_for_manual_transfer", label + " job status must be prepared_for_manual_transfer")
    require(job.get("assignment_status") == "prepared_for_manual_transfer", label + " assignment status must be prepared_for_manual_transfer")
    require(job.get("created_by") == "engel", label + " created_by must be engel")
    require(job.get("routed_by") == "communication_queen", label + " routed_by must be communication_queen")
    require(job.get("assignment_route") == "communication_queen_only", label + " assignment route must be communication_queen_only")
    require(job.get("manual_transfer_required") is True, label + " manual transfer must be required")
    require(job.get("offline_only") is True, label + " offline_only must be true")
    require(job.get("on_device_autonomy_allowed") is True, label + " on-device autonomy must be allowed only for assigned sandbox")
    require(job.get("autonomy_scope") == "assigned_job_sandbox_only", label + " autonomy scope mismatch")
    for field in ["trusted_memory_write", "source_mutation", "route_mutation", "patch_apply", "provider_network", "model_runtime"]:
        require(job.get(field) is False, label + " " + field + " must be false")
    require(job.get("requires_human_review") is True, label + " requires_human_review must be true")
    require(job.get("receipt_required") is True, label + " receipt_required must be true")
    require(job.get("log_required") is True, label + " log_required must be true")
    for forbidden in ["completed", "returned_to_engel", "trusted", "promoted", "applied"]:
        require(job.get("status") != forbidden and job.get("assignment_status") != forbidden, label + " job must not use forbidden status: " + forbidden)
    for field in ["progress_percent", "current_step", "completed_at", "output_ready"]:
        require(field not in job, label + " job packet must not fabricate worker runtime field: " + field)
    return job


def check_job_packets() -> dict[str, tuple[Path, dict[str, object]]]:
    """Per worker: at least one real job packet whose first packet (sorted by
    filename, i.e. by timestamp) matches the expected first-real-job shape.
    Additional later packets are validated structurally only (real_job=true,
    correct worker_id, prepared_for_manual_transfer, all safety flags false,
    input file present + hash matches). Gamma has no phone assigned yet."""
    results: dict[str, tuple[Path, dict[str, object]]] = {}
    for package, expected in [(ALPHA_PACKAGE, ALPHA_EXPECTED), (BETA_PACKAGE, BETA_EXPECTED)]:
        worker_id = str(expected["worker_id"])
        jobs_folder = package / "jobs"
        if not jobs_folder.exists():
            raise CheckFailure(worker_id + " jobs folder missing")
        packets = sorted(p for p in jobs_folder.iterdir() if p.is_file() and p.suffix.lower() == ".json")
        require(len(packets) >= 1, worker_id + " expected at least one real job packet, found 0")
        first_job = validate_one_job_packet(packets[0], expected)
        results[worker_id] = (packets[0], first_job)
        # Validate every additional packet structurally (no fixed title/job_type).
        for extra_path in packets[1:]:
            validate_additional_job_packet(extra_path, worker_id)
    gamma_jobs = list((GAMMA_PACKAGE / "jobs").glob("*.json"))
    require(not gamma_jobs, "Gamma must not have job packet yet")
    return results


def validate_additional_job_packet(job_path: Path, worker_id: str) -> dict[str, object]:
    """Structural-only validation for round-2+ job packets. Same safety
    invariants as the first-job packet, but the title/job_type/expected_outputs
    are not pinned to a single canonical string."""
    label = worker_id
    job = load_json(job_path)
    require(job.get("job_id") == job_path.stem, label + " additional job_id must match filename")
    require(job.get("assigned_worker_id") == worker_id, label + " additional packet assigned to wrong worker")
    require(job.get("job_template") is False, label + " additional job_template must be false")
    require(job.get("real_job") is True, label + " additional real_job must be true")
    require(job.get("status") == "prepared_for_manual_transfer" or job.get("status") == "completed",
            label + " additional job status must be prepared_for_manual_transfer or completed")
    require(job.get("created_by") == "engel", label + " additional created_by must be engel")
    require(job.get("routed_by") == "communication_queen", label + " additional routed_by must be communication_queen")
    require(job.get("assignment_route") == "communication_queen_only", label + " additional assignment_route mismatch")
    require(job.get("manual_transfer_required") is True, label + " additional manual_transfer_required must be true")
    require(job.get("offline_only") is True, label + " additional offline_only must be true")
    require(job.get("autonomy_scope") == "assigned_job_sandbox_only", label + " additional autonomy_scope mismatch")
    for field in ["trusted_memory_write", "source_mutation", "route_mutation", "patch_apply", "provider_network", "model_runtime"]:
        require(job.get(field) is False, label + " additional " + field + " must be false")
    require(job.get("requires_human_review") is True, label + " additional requires_human_review must be true")
    require(job.get("receipt_required") is True, label + " additional receipt_required must be true")
    require(job.get("log_required") is True, label + " additional log_required must be true")
    for field in ["progress_percent", "current_step", "completed_at", "output_ready"]:
        require(field not in job, label + " additional packet must not fabricate worker runtime field: " + field)
    job_type = str(job.get("job_type", ""))
    require(job_type, label + " additional job_type must be non-empty")
    # Source-input + staged-input must be real and hashes must match.
    source_input = job.get("source_input", {})
    require(isinstance(source_input, dict), label + " additional source_input must be object")
    project_path_text = str(source_input.get("project_path", ""))
    require(project_path_text and "://" not in project_path_text, label + " additional source path must be local")
    source_path = (ROOT / project_path_text).resolve(strict=False)
    require(source_path.exists() and source_path.is_file(), label + " additional source input file missing")
    input_files = job.get("input_files", [])
    require(isinstance(input_files, list) and len(input_files) == 1, label + " additional job must have exactly one staged input file")
    package = ALPHA_PACKAGE if worker_id == "android_worker_alpha" else BETA_PACKAGE
    staged_path = package / str(input_files[0])
    require(staged_path.exists() and staged_path.is_file(), label + " additional staged input file missing")
    require(path_inside(staged_path, package / "inbox"), label + " additional staged input must stay in worker inbox")
    require(source_input.get("copied_for_manual_transfer") is True, label + " additional source input must be a staged snapshot")
    require(source_input.get("sha256") == sha256_file(staged_path), label + " additional staged snapshot hash mismatch")
    return job


def check_input_file(package: Path, job: dict[str, object]) -> None:
    label = package.name
    source_input = job.get("source_input", {})
    require(isinstance(source_input, dict), label + " source_input must be object")
    project_path_text = str(source_input.get("project_path", ""))
    require(project_path_text and "://" not in project_path_text and not project_path_text.startswith("\\\\"), label + " source path must be local")
    source_path = (ROOT / project_path_text).resolve(strict=False)
    require(source_path.exists() and source_path.is_file(), label + " source input file missing")
    require(any(path_inside(source_path, root) for root in ALLOWED_INPUT_ROOTS), label + " source input is outside allowed roots")
    require(source_path.suffix.lower() in {".md", ".txt", ".json"}, label + " source input must be md/txt/json")
    input_files = job.get("input_files", [])
    require(isinstance(input_files, list) and len(input_files) == 1, label + " job must have exactly one staged input file")
    staged_path = package / str(input_files[0])
    require(staged_path.exists() and staged_path.is_file(), label + " staged worker input file missing")
    require(path_inside(staged_path, package / "inbox"), label + " staged input must stay in worker inbox")
    require(source_input.get("sha256") == sha256_file(staged_path), label + " staged snapshot hash mismatch")
    require(source_input.get("staged_worker_path") == str(staged_path.relative_to(ROOT)).replace("/", "\\"), label + " staged worker path mismatch")


def check_worker_eligibility(package: Path, job: dict[str, object], expected: dict[str, object]) -> None:
    label = package.name
    identity = load_json(package / "config" / "worker_identity.json")
    capabilities = load_json(package / "config" / "worker_capabilities.json")
    require(identity.get("queen_authority") is False, label + " must not be Queen")
    require(identity.get("routing_layer") == "communication_queen_only", label + " routing layer mismatch")
    require(identity.get("can_self_assign_jobs") is False, label + " cannot self-assign jobs")
    require(identity.get("can_create_jobs") is False, label + " cannot create jobs")
    require(identity.get("can_route_jobs") is False, label + " cannot route jobs")
    require(identity.get("can_control_engel") is False, label + " cannot control Engel")
    job_type = str(expected["job_type"])
    require(job_type in identity.get("allowed_task_types", []), label + " identity must allow " + job_type)
    require(job_type in capabilities.get("allowed_jobs", []), label + " capabilities must allow " + job_type)
    blocked_actions = "\n".join(str(item) for item in job.get("blocked_actions", []))
    for required in [
        "execute arbitrary shell from job packet",
        "install packages",
        "download files",
        "download models",
        "start network server",
        "expose SSH",
        "trusted_memory_write",
        "patch_apply",
        "source_mutation",
        "route_mutation",
        "provider_network",
        "model_runtime",
        "hermes_runtime_rejected_do_not_install",
        "ollama_runtime_blocked",
        "llama_cpp_runtime_blocked",
        "worker_job_execution_from_engel",
        "fake_returned_status",
        "fake_returned_result",
        "fake_progress",
    ]:
        require(required in blocked_actions, label + " job blocked_actions missing: " + required)
    expected_outputs = "\n".join(str(item) for item in job.get("expected_outputs", []))
    for required in expected["expected_outputs_required"]:
        require(required in expected_outputs, label + " job expected_outputs missing: " + required)


def check_no_returned_or_fake_artifacts() -> None:
    """Alpha and Beta may each have one real completed job's returned artifacts.
    Gamma has no phone assigned yet and must stay empty."""
    for package, worker_id in [
        (ALPHA_PACKAGE, "android_worker_alpha"),
        (BETA_PACKAGE, "android_worker_beta"),
    ]:
        jobs = sorted(p for p in (package / "jobs").glob("*.json"))
        job_id = jobs[0].stem if jobs else ""
        for folder in ["status", "outbox", "logs", "receipts"]:
            files = artifact_files(package, folder)
            for path in files:
                validate_real_returned_artifact(path, folder, job_id, worker_id)
    for folder in ["status", "outbox", "logs", "receipts"]:
        files = artifact_files(GAMMA_PACKAGE, folder)
        require(not files, f"android_worker_gamma/{folder} must not contain returned/fake artifacts yet")
    require(not list((GAMMA_PACKAGE / "jobs").glob("*.json")), "Gamma must not have job packet yet")


def validate_real_returned_artifact(path: Path, folder: str, job_id: str, worker_id: str) -> None:
    label = worker_id
    require(job_id, label + " cannot validate returned artifact without first job id")
    require(path.name.startswith(job_id), label + " returned artifact must match first real job id: " + str(path.relative_to(ROOT)))
    if folder == "logs":
        require(path.suffix.lower() == ".log", label + " log artifact must be .log")
        require(path.read_text(encoding="utf-8", errors="replace").strip(), label + " returned log must be non-empty")
        return
    # outbox can hold both the result.json control packet AND candidate-output
    # JSON files (e.g. *_candidate.json from draft_candidate_json jobs). The
    # candidate outputs use different keys (candidate_id/source_job_id) and are
    # bounded by their own candidate_only / human_review_required schema —
    # validated below, but not against worker_id/job_id of the control packet.
    payload = load_json(path)
    if folder == "outbox" and not path.name.endswith("_result.json"):
        # candidate output file
        require(payload.get("status") in {"candidate_only", "candidate"} or "candidate" in str(payload.get("candidate_type", "")).lower(),
                label + " outbox non-result file must be a candidate output: " + str(path.relative_to(ROOT)))
        require(payload.get("source_job_id") == job_id or payload.get("job_id") == job_id,
                label + " candidate file source_job_id mismatch: " + str(path.relative_to(ROOT)))
        require(payload.get("human_review_required") is True, label + " candidate output must require human review")
        for field in ["trusted_memory_write", "source_mutation", "patch_apply"]:
            require(payload.get(field) is False, label + " candidate output must keep blocked field false: " + field)
        return
    require(payload.get("worker_id") == worker_id, label + " returned artifact worker mismatch: " + str(path.relative_to(ROOT)))
    require(payload.get("job_id") == job_id, label + " returned artifact job mismatch: " + str(path.relative_to(ROOT)))
    if folder == "status":
        require(payload.get("real_status") is True, label + " status must be marked real_status")
        require(payload.get("source") == "android_worker_returned_status", label + " status source mismatch")
        require(payload.get("manual_transfer_mode") is True, label + " status must remain manual transfer")
        require(payload.get("output_ready") is False or isinstance(payload.get("output_ready"), bool), label + " status output_ready must be boolean")
    elif folder == "outbox":
        require(payload.get("real_result") is True, label + " result must be marked real_result")
        require(payload.get("source") == "android_worker_returned_result", label + " result source mismatch")
        require(payload.get("requires_human_review") is True, label + " result must require human review")
        for field in ["trusted_memory_write", "source_mutation", "route_mutation", "patch_apply", "provider_network", "model_runtime"]:
            require(payload.get(field) is False, label + " result must keep blocked field false: " + field)
    elif folder == "receipts":
        require(payload.get("candidate_outputs_only") is True, label + " receipt must remain candidate outputs only")
        require(payload.get("human_review_required") is True, label + " receipt must require human review")
        for field in ["trusted_memory_write", "source_mutation", "route_mutation", "patch_apply", "provider_network", "model_runtime"]:
            require(payload.get(field) is False, label + " receipt must keep blocked field false: " + field)


def check_report(report_path: Path, title_phrase: str, job_path: Path, job: dict[str, object], worker_id: str, job_type: str) -> None:
    require(report_path.exists(), worker_id + " first real job packet report missing: " + str(report_path.relative_to(ROOT)))
    text = read(report_path)
    for required in [
        title_phrase,
        str(job_path.relative_to(ROOT)).replace("/", "\\"),
        str(job.get("job_id")),
        worker_id,
        job_type,
        "prepared_for_manual_transfer",
        "real job packet",
        "no phone was connected",
        "no Android runtime was executed from Engel",
        "no worker job was run from Engel",
        "no fake status/progress/result/receipt was created",
        "awaiting manual transfer",
        "packaging skipped",
    ]:
        require(required.lower() in text.lower(), worker_id + " report missing: " + required)


def main() -> int:
    try:
        check_assignment_module_static()
        results = check_job_packets()
        alpha_path, alpha_job = results["android_worker_alpha"]
        beta_path, beta_job = results["android_worker_beta"]
        check_input_file(ALPHA_PACKAGE, alpha_job)
        check_input_file(BETA_PACKAGE, beta_job)
        check_worker_eligibility(ALPHA_PACKAGE, alpha_job, ALPHA_EXPECTED)
        check_worker_eligibility(BETA_PACKAGE, beta_job, BETA_EXPECTED)
        check_no_returned_or_fake_artifacts()
        check_report(ALPHA_REPORT, "First Real Android Remote Worker Job Packet V1", alpha_path, alpha_job, "android_worker_alpha", "summarize_text")
        check_report(BETA_REPORT, "First Real Android Worker Beta Job Packet V1", beta_path, beta_job, "android_worker_beta", "draft_candidate_json")
    except CheckFailure as exc:
        print("[FAIL] Engel first real Android worker job packet verifier failed.")
        print("- " + str(exc))
        return 1
    print("[PASS] Engel first real Android worker job packet verifier passed.")
    print("Alpha job packet: " + str(alpha_path.relative_to(ROOT)) + "  id: " + str(alpha_job.get("job_id")))
    print("Beta job packet:  " + str(beta_path.relative_to(ROOT)) + "  id: " + str(beta_job.get("job_id")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
