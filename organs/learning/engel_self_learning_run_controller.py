from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import engel_global_password_gate as global_password_gate
import engel_learning_job_queue as learning_queue
import engel_lesson_candidate_extractor as lesson_extractor
import engel_research_memory_candidate_proposal as memory_proposal
import engel_untrusted_research_note_generator as note_generator


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "self_learning_run_receipts"
SUMMARY_DIR = PROJECT_ROOT / "reports" / "self_learning_run_summaries"
CONTRACT_JSON = PROJECT_ROOT / "memory" / "ENGEL_SELF_LEARNING_RUN_CONTROLLER_CONTRACT_V1.json"

CONTROLLER_STATUS = [
    "SELF_LEARNING_RUN_CONTROLLER",
    "BOUNDED_LEARNING_RUNNER",
    "REAL_QUEUE_JOBS_ONLY",
    "REAL_SOURCE_REQUIRED",
    "SOURCE_FILE_MUST_EXIST",
    "CANDIDATE_LEARNING_ONLY",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_TRUSTED_MEMORY",
    "PASSWORD_GATE_REQUIRED_FOR_RUN",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "RECEIPTS_REQUIRED",
    "HUMAN_REVIEW_REQUIRED",
    "NO_FAKE_LEARNING_OUTPUTS",
    "NO_FAKE_QUEUE_RECORDS",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

RUN_LIMITS = [
    "one job per run in V1",
    "explicit job file only",
    "job source file must exist",
    "job source must pass Learning Job Queue validation",
    "max input chars from job",
    "max runtime seconds from job",
    "no folder recursion",
    "no wildcard source discovery",
    "no URL fetch",
    "no model loading",
    "no WSL/Hermes/Android runtime",
    "no trusted memory write",
    "no source mutation",
    "no patch apply",
]

PIPELINE_STAGES = [
    "validate_learning_job_queue_job",
    "read_bounded_source_text",
    "generate_untrusted_research_note",
    "extract_lesson_candidate",
    "create_research_memory_candidate_proposal",
    "create_self_learning_run_receipt",
    "create_readable_run_summary",
    "leave_outputs_candidate_only",
]

OUTPUT_LABELS = [
    "UNTRUSTED",
    "CANDIDATE_ONLY",
    "NOT_TRUSTED_MEMORY",
    "HUMAN_REVIEW_REQUIRED",
    "NO_AUTOMATION_TRIGGERED",
]

RECEIPT_FIELDS = [
    "receipt_id",
    "run_id",
    "created_at",
    "job_id",
    "topic_id",
    "source_path",
    "source_type",
    "source_review_status",
    "source_hash_if_computed",
    "outputs_created",
    "research_note_path",
    "lesson_candidate_path",
    "memory_candidate_proposal_path",
    "run_summary_path",
    "password_gate_checked",
    "protected_action_id",
    "max_input_chars",
    "max_runtime_seconds",
    "safety_boundary",
    "no_trusted_memory_write",
    "no_source_mutation",
    "no_patch_apply",
    "no_model_loading",
    "no_inference",
    "no_training",
    "no_wsl_execution",
    "no_hermes_execution",
    "no_android_connection",
    "no_provider_network_browser",
    "human_review_required",
    "final_status",
]

SAFETY_BOUNDARY = (
    "SELF_LEARNING_RUN_CONTROLLER / BOUNDED_LEARNING_RUNNER / REAL_QUEUE_JOBS_ONLY / "
    "REAL_SOURCE_REQUIRED / CANDIDATE_LEARNING_ONLY / UNTRUSTED_OUTPUTS_ONLY / NOT_TRUSTED_MEMORY. "
    "No fake learning outputs, trusted memory write, source mutation, patch apply, model loading, "
    "inference, training, WSL execution, Hermes execution, Android connection, provider call, network, "
    "browser, background worker, startup autorun, recursive scan, or wildcard discovery."
)


class SelfLearningRunControllerError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve())).replace("/", "\\")


def safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value).strip("_").lower() or "self_learning_run"


def load_job(job_json: str) -> tuple[Path, dict[str, object]]:
    path, job = learning_queue.load_job_json(job_json)
    return path, job


def source_path_from_job(job: dict[str, object]) -> Path:
    return learning_queue.resolve_source(str(job.get("source_path", "")))


def require_runnable_job(job: dict[str, object]) -> None:
    status = str(job.get("status", ""))
    if status not in {"queued", "ready_for_candidate_learning"}:
        raise SelfLearningRunControllerError("run-once requires a queued or ready_for_candidate_learning job")


def read_bounded_source(path: Path, max_chars: int) -> tuple[dict[str, object], str]:
    if max_chars <= 0 or max_chars > 100000:
        raise SelfLearningRunControllerError("max_input_chars must be between 1 and 100000")
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        text = handle.read(max_chars + 1)
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    return {
        "path": project_relative(path),
        "characters_read": len(text),
        "truncated_for_safety": truncated,
        "preview": text,
    }, digest


def validate_runtime_limit(job: dict[str, object]) -> tuple[int, int]:
    max_input = int(job.get("max_input_chars", 0))
    max_runtime = int(job.get("max_runtime_seconds", 0))
    if max_input <= 0 or max_input > 100000:
        raise SelfLearningRunControllerError("job max_input_chars is out of bounds")
    if max_runtime <= 0 or max_runtime > 900:
        raise SelfLearningRunControllerError("job max_runtime_seconds is out of bounds")
    return max_input, max_runtime


def topic_for_job(job: dict[str, object]) -> dict[str, object]:
    topic_id = str(job.get("topic_id", ""))
    return note_generator.find_topic(topic_id)


def run_id_for_job(job: dict[str, object], created_at: str) -> str:
    seed = f"SELF_LEARNING_RUN_CONTROLLER_V1|{job.get('job_id')}|{created_at}".encode("utf-8")
    return "self_learning_run_" + hashlib.sha256(seed).hexdigest()[:16]


def check_elapsed(started: float, max_runtime_seconds: int) -> None:
    if time.monotonic() - started > max_runtime_seconds:
        raise SelfLearningRunControllerError("max_runtime_seconds exceeded")


def write_summary(receipt: dict[str, object]) -> Path:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = (SUMMARY_DIR / f"{safe_id(str(receipt['run_id']))}.md").resolve(strict=False)
    if not is_relative_to(summary_path, SUMMARY_DIR.resolve(strict=False)):
        raise SelfLearningRunControllerError("summary output escaped reports\\self_learning_run_summaries")
    lines = [
        "# Engel Self-Learning Run Summary V1",
        "",
        "Labels:",
        *[f"- {label}" for label in OUTPUT_LABELS],
        "",
        "Status:",
        *[f"- {status}" for status in CONTROLLER_STATUS],
        "",
        "Run:",
        f"- run_id: {receipt['run_id']}",
        f"- job_id: {receipt['job_id']}",
        f"- topic_id: {receipt['topic_id']}",
        f"- source_path: {receipt['source_path']}",
        f"- final_status: {receipt['final_status']}",
        "",
        "Outputs:",
        f"- research_note_path: {receipt.get('research_note_path')}",
        f"- lesson_candidate_path: {receipt.get('lesson_candidate_path')}",
        f"- memory_candidate_proposal_path: {receipt.get('memory_candidate_proposal_path')}",
        "",
        "Boundary:",
        SAFETY_BOUNDARY,
        "",
        "Human review is required before any use. No trusted memory was written.",
        "",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def write_receipt(receipt: dict[str, object]) -> Path:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    receipt_path = (RECEIPT_DIR / f"{safe_id(str(receipt['receipt_id']))}.json").resolve(strict=False)
    if not is_relative_to(receipt_path, RECEIPT_DIR.resolve(strict=False)):
        raise SelfLearningRunControllerError("receipt output escaped reports\\self_learning_run_receipts")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def build_base_receipt(job: dict[str, object], source_hash: str, password_checked: bool) -> dict[str, object]:
    created_at = now_utc()
    run_id = run_id_for_job(job, created_at)
    receipt_id = "self_learning_run_receipt_" + hashlib.sha256(f"{run_id}|{created_at}".encode("utf-8")).hexdigest()[:16]
    max_input, max_runtime = validate_runtime_limit(job)
    return {
        "receipt_id": receipt_id,
        "run_id": run_id,
        "created_at": created_at,
        "job_id": job["job_id"],
        "topic_id": job["topic_id"],
        "source_path": job["source_path"],
        "source_type": job["source_type"],
        "source_review_status": job["source_review_status"],
        "source_hash_if_computed": source_hash,
        "outputs_created": [],
        "research_note_path": "",
        "lesson_candidate_path": "",
        "memory_candidate_proposal_path": "",
        "run_summary_path": "",
        "password_gate_checked": password_checked,
        "protected_action_id": "self_learning_run_controller_run_once",
        "max_input_chars": max_input,
        "max_runtime_seconds": max_runtime,
        "safety_boundary": SAFETY_BOUNDARY,
        "no_trusted_memory_write": True,
        "no_source_mutation": True,
        "no_patch_apply": True,
        "no_model_loading": True,
        "no_inference": True,
        "no_training": True,
        "no_wsl_execution": True,
        "no_hermes_execution": True,
        "no_android_connection": True,
        "no_provider_network_browser": True,
        "human_review_required": True,
        "final_status": "candidate_outputs_created",
        "labels": list(OUTPUT_LABELS),
    }


def dry_run(job_json: str) -> str:
    path, job = load_job(job_json)
    source_path = source_path_from_job(job)
    max_input, max_runtime = validate_runtime_limit(job)
    lines = [
        "Engel Self-Learning Run Controller V1 Dry Run",
        "",
        f"Job file: {project_relative(path)}",
        f"Job id: {job['job_id']}",
        f"Topic id: {job['topic_id']}",
        f"Source: {project_relative(source_path)}",
        f"Source type: {job['source_type']}",
        f"Source review status: {job['source_review_status']}",
        f"Max input chars: {max_input}",
        f"Max runtime seconds: {max_runtime}",
        "",
        "Pipeline that would run:",
        *[f"- {stage}" for stage in PIPELINE_STAGES],
        "",
        "Boundary:",
        SAFETY_BOUNDARY,
        "",
        "DRY_RUN_ONLY / NO_OUTPUTS_CREATED / NO_LEARNING_JOB_RUN",
    ]
    return "\n".join(lines) + "\n"


def run_once(job_json: str, password_checked: bool) -> tuple[dict[str, object], Path]:
    started = time.monotonic()
    _, job = load_job(job_json)
    require_runnable_job(job)
    source_path = source_path_from_job(job)
    max_input, max_runtime = validate_runtime_limit(job)
    preview, source_hash = read_bounded_source(source_path, max_input)
    topic = topic_for_job(job)
    check_elapsed(started, max_runtime)

    note = note_generator.build_research_note(topic, [preview])
    note_path = note_generator.write_note(note)
    check_elapsed(started, max_runtime)

    lesson = lesson_extractor.build_lesson_candidate(note_path.name)
    lesson_path = lesson_extractor.write_candidate(lesson)
    check_elapsed(started, max_runtime)

    proposal = memory_proposal.build_memory_candidate_proposal(lesson_path.name)
    proposal_path = memory_proposal.write_proposal(proposal)
    check_elapsed(started, max_runtime)

    receipt = build_base_receipt(job, source_hash, password_checked)
    receipt["research_note_path"] = project_relative(note_path)
    receipt["lesson_candidate_path"] = project_relative(lesson_path)
    receipt["memory_candidate_proposal_path"] = project_relative(proposal_path)
    receipt["outputs_created"] = [
        receipt["research_note_path"],
        receipt["lesson_candidate_path"],
        receipt["memory_candidate_proposal_path"],
    ]
    summary_path = write_summary(receipt)
    receipt["run_summary_path"] = project_relative(summary_path)
    receipt["outputs_created"].append(receipt["run_summary_path"])
    receipt_path = write_receipt(receipt)
    return receipt, receipt_path


def queue_counts(path: Path, suffix: str) -> int:
    if not path.exists():
        return 0
    return len([child for child in path.iterdir() if child.is_file() and child.suffix.lower() == suffix])


def render_status() -> str:
    lines = [
        "Engel Self-Learning Run Controller V1",
        "",
        "Status:",
        *[f"- {status}" for status in CONTROLLER_STATUS],
        "",
        f"Receipt folder: {project_relative(RECEIPT_DIR)}",
        f"Summary folder: {project_relative(SUMMARY_DIR)}",
        f"Receipt count: {queue_counts(RECEIPT_DIR, '.json')}",
        f"Summary count: {queue_counts(SUMMARY_DIR, '.md')}",
        "",
        "Run limits:",
        *[f"- {limit}" for limit in RUN_LIMITS],
        "",
        "Pipeline:",
        *[f"- {stage}" for stage in PIPELINE_STAGES],
        "",
        "Boundary:",
        SAFETY_BOUNDARY,
        "",
        "Next step: Fix Candidate Queue V1",
    ]
    return "\n".join(lines) + "\n"


def list_files_nonrecursive(path: Path, suffix: str, title: str) -> str:
    if not path.exists():
        return f"No {title} found.\n"
    files = sorted(child for child in path.iterdir() if child.is_file() and child.suffix.lower() == suffix)
    if not files:
        return f"No {title} found.\n"
    return title + ":\n" + "\n".join(f"- {project_relative(path)}" for path in files) + "\n"


def require_password() -> bool:
    global_password_gate.prompt_and_require_action("self_learning_run_controller_run_once")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Self-Learning Run Controller V1.")
    parser.add_argument("--status", action="store_true", help="Show controller status and safety boundary.")
    parser.add_argument("--dry-run", action="store_true", help="Validate one explicit job and report what would happen.")
    parser.add_argument("--run-once", action="store_true", help="Run one explicit queued learning job after password gate.")
    parser.add_argument("--job", metavar="JOB_JSON", help="Explicit Learning Job Queue JSON file.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for global password for run-once.")
    parser.add_argument("--summary", action="store_true", help="List run summaries non-recursively.")
    parser.add_argument("--list-receipts", action="store_true", help="List run receipts non-recursively.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        if args.status:
            out.write(render_status())
            return 0
        if args.summary:
            out.write(list_files_nonrecursive(SUMMARY_DIR, ".md", "Self-learning run summaries"))
            return 0
        if args.list_receipts:
            out.write(list_files_nonrecursive(RECEIPT_DIR, ".json", "Self-learning run receipts"))
            return 0
        if args.dry_run:
            if not args.job:
                err.write("--job is required for --dry-run.\n")
                return 2
            out.write(dry_run(args.job))
            return 0
        if args.run_once:
            if not args.job:
                err.write("--job is required for --run-once.\n")
                return 2
            if not args.password_prompt:
                err.write("--run-once requires --password-prompt.\n")
                return 2
            checked = require_password()
            receipt, receipt_path = run_once(args.job, checked)
            out.write(f"WROTE_SELF_LEARNING_RUN_RECEIPT {project_relative(receipt_path)}\n")
            out.write(f"WROTE_SELF_LEARNING_RUN_SUMMARY {receipt['run_summary_path']}\n")
            out.write("CANDIDATE_ONLY / NOT_TRUSTED_MEMORY / HUMAN_REVIEW_REQUIRED\n")
            return 0
        out.write(render_status())
        return 0
    except (
        SelfLearningRunControllerError,
        learning_queue.LearningJobQueueError,
        note_generator.ResearchNoteError,
        lesson_extractor.LessonCandidateError,
        memory_proposal.MemoryCandidateProposalError,
        global_password_gate.PasswordGateError,
    ) as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
