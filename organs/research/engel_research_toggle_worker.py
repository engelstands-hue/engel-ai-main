from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import textwrap
import time

import engel_self_learning_mini_runner as mini_runner
import engel_untrusted_research_note_generator as note_generator


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
CONTRACT_PATH = PROJECT_ROOT / "memory" / "ENGEL_RESEARCH_TOGGLE_OVERNIGHT_WORKER_CONTRACT_V1.md"
BACKGROUND_CONTRACT_PATH = PROJECT_ROOT / "memory" / "ENGEL_BACKGROUND_WORKER_STARTUP_AUTORUN_CONTRACT_V1.md"
STATE_PATH = PROJECT_ROOT / "memory" / "ENGEL_RESEARCH_TOGGLE_OVERNIGHT_WORKER_STATE_V1.json"
OVERNIGHT_RECEIPT_DIR = PROJECT_ROOT / "reports" / "overnight_research_receipts"
SUMMARY_DIR = PROJECT_ROOT / "reports" / "research_toggle_worker_receipts"
MAX_JOBS = 3
MAX_RUNTIME_MINUTES = 480
MAX_RUNTIME_SECONDS = MAX_RUNTIME_MINUTES * 60
DEFAULT_CADENCE_SECONDS = 1

ENABLE_ACTION_ID = "enable_research_toggle_overnight_worker"
DISABLE_ACTION_ID = "disable_research_toggle_overnight_worker"
RUN_ONCE_ACTION_ID = "run_research_toggle_worker_once"
OVERNIGHT_ACTION_ID = "run_research_toggle_worker_overnight"
KILL_SWITCH_ACTION_ID = "research_toggle_worker_kill_switch"

WORKER_STATUS = [
    "RESEARCH_TOGGLE_OVERNIGHT_WORKER",
    "BOUNDED_RESEARCH_WORKER",
    "NO_PASSWORD_GATE_REQUIRED",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "HUMAN_ENABLE_REQUIRED",
    "DISABLED_BY_DEFAULT",
    "CANDIDATE_OUTPUTS_ONLY",
    "LOCAL_ONLY_BY_DEFAULT",
    "APPROVED_LOCAL_SOURCES_ONLY",
    "EXPLICIT_JOB_LIST_ONLY",
    "RECEIPT_REQUIRED",
    "RESOURCE_LIMITS_REQUIRED",
    "TIME_LIMIT_REQUIRED",
    "MAX_JOB_LIMIT_REQUIRED",
    "KILL_SWITCH_REQUIRED",
    "STOP_ON_HIGH_RISK",
    "STOP_ON_UNCLEAR_RISK",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_VERIFIER_UPDATE",
    "NO_PROVIDER_CALLS_BY_DEFAULT",
    "NO_NETWORK_BY_DEFAULT",
    "NO_BROWSER_BY_DEFAULT",
    "NO_MODEL_RUNTIME_BY_DEFAULT",
    "NO_PACKAGE_REFRESH",
    "NO_STARTUP_AUTORUN_INSTALL",
    "NO_ENDLESS_LOOP",
    "NO_HIDDEN_AUTONOMY",
]

OUTPUT_LABELS = [
    "UNTRUSTED",
    "CANDIDATE_ONLY",
    "NOT_TRUSTED_MEMORY",
    "HUMAN_REVIEW_REQUIRED",
    "NO_AUTOMATION_TRIGGERED",
]

RECEIPT_FIELDS = [
    "research_worker_run_id",
    "started_at",
    "completed_at",
    "mode",
    "research_toggle_state",
    "jobs_requested",
    "jobs_run",
    "jobs_stopped",
    "output_paths",
    "max_runtime_minutes",
    "max_jobs",
    "password_gate_checked",
    "protected_action_id",
    "safety_boundary",
    "stopped",
    "stop_reason",
    "final_summary",
    "no_trusted_memory_write",
    "no_source_mutation",
    "no_provider_network_browser",
    "no_model_runtime",
    "no_background_escape",
    "no_startup_autorun_install",
]

SAFETY_BOUNDARY = (
    "RESEARCH_TOGGLE_OVERNIGHT_WORKER / BOUNDED_RESEARCH_WORKER / CANDIDATE_OUTPUTS_ONLY / "
    "APPROVED_LOCAL_SOURCES_ONLY / EXPLICIT_JOB_LIST_ONLY / RECEIPT_REQUIRED / "
    "TIME_LIMIT_REQUIRED / MAX_JOB_LIMIT_REQUIRED. No trusted memory write, source mutation, "
    "patch apply, verifier update, provider call, network, browser, model runtime, package refresh, "
    "startup autorun install, hidden autonomy, or endless loop."
)


class ResearchToggleWorkerError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve())).replace("/", "\\")


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_").lower() or "unknown"


def make_run_id(mode: str, jobs_path: str, timestamp: str) -> str:
    seed = f"research_toggle_worker|{mode}|{jobs_path}|{timestamp}".encode("utf-8")
    return "research_toggle_worker_run_" + hashlib.sha256(seed).hexdigest()[:16]


def default_state() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "enabled": False,
        "research_toggle_state": "OFF",
        "disabled_by_default": True,
        "startup_enabled": False,
        "startup_allowed": False,
        "last_updated_at": "",
        "last_action": "default_disabled",
        "last_receipt_path": "",
        "last_summary_path": "",
        "kill_switch_status": "READY",
        "status_labels": list(WORKER_STATUS),
    }


def load_state() -> dict[str, object]:
    if not STATE_PATH.exists():
        return default_state()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchToggleWorkerError("research toggle worker state is invalid") from exc
    if not isinstance(data, dict):
        raise ResearchToggleWorkerError("research toggle worker state is invalid")
    state = default_state()
    for key in state:
        if key in data:
            state[key] = data[key]
    state["startup_enabled"] = False
    state["startup_allowed"] = False
    return state


def write_state(state: dict[str, object]) -> Path:
    target = STATE_PATH.resolve(strict=False)
    if not is_relative_to(target, (PROJECT_ROOT / "memory").resolve(strict=False)):
        raise ResearchToggleWorkerError("research toggle worker state path escaped memory folder")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def set_worker_enabled(enabled: bool, password_already_checked: bool = False) -> dict[str, object]:
    state = load_state()
    state["enabled"] = bool(enabled)
    state["research_toggle_state"] = "ON" if enabled else "OFF"
    state["last_updated_at"] = now_utc()
    state["last_action"] = "enabled_by_human_no_password" if enabled else "disabled_by_human_no_password"
    state["startup_enabled"] = False
    state["startup_allowed"] = False
    state["kill_switch_status"] = "READY"
    write_state(state)
    return state


def enable_worker_with_password(password: str) -> dict[str, object]:
    return set_worker_enabled(True, password_already_checked=True)


def disable_worker_with_password(password: str) -> dict[str, object]:
    return set_worker_enabled(False, password_already_checked=True)


def activate_kill_switch(password_already_checked: bool = False) -> dict[str, object]:
    state = load_state()
    state["enabled"] = False
    state["research_toggle_state"] = "OFF"
    state["last_updated_at"] = now_utc()
    state["last_action"] = "kill_switch"
    state["kill_switch_status"] = "TRIPPED"
    state["startup_enabled"] = False
    state["startup_allowed"] = False
    write_state(state)
    return state


def reject_unsafe_jobs_path_text(raw_jobs_path: str) -> None:
    lowered = raw_jobs_path.lower()
    uppered = raw_jobs_path.upper()
    if lowered.startswith(("http://", "https://")):
        raise ResearchToggleWorkerError("reject URLs: job list must be a project-local JSON file")
    if raw_jobs_path.startswith("\\\\"):
        raise ResearchToggleWorkerError("reject UNC paths: job list must be project-local")
    if any(marker in raw_jobs_path for marker in ("*", "?", "[")):
        raise ResearchToggleWorkerError("reject wildcards: explicit job list file only")
    retired_suffix = "\\ENGEL_" + "APP_MEMORY"
    retired_roots = tuple(f"{letter}:{retired_suffix}" for letter in ("E", "F", "G"))
    if uppered.startswith(retired_roots):
        raise ResearchToggleWorkerError("reject retired external-drive roots: job list must stay inside the project")


def validate_jobs_path(raw_jobs_path: str) -> Path:
    reject_unsafe_jobs_path_text(raw_jobs_path)
    candidate = Path(raw_jobs_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve(strict=False)
    if not is_relative_to(resolved, PROJECT_ROOT.resolve()):
        raise ResearchToggleWorkerError("reject paths outside project root")
    if resolved.anchor == str(resolved):
        raise ResearchToggleWorkerError("reject drive roots: job list must be one explicit JSON file")
    relative_parts = [part.lower() for part in resolved.relative_to(PROJECT_ROOT.resolve()).parts]
    if relative_parts and relative_parts[0] in {"live", "staging"}:
        raise ResearchToggleWorkerError("reject live/staging paths")
    if any(part in {"model", "models", "model_library", "hf", "ollama", "trusted_memory"} for part in relative_parts):
        raise ResearchToggleWorkerError("reject model or trusted-memory paths")
    if not resolved.exists():
        raise ResearchToggleWorkerError("job list file does not exist")
    if resolved.is_dir():
        raise ResearchToggleWorkerError("reject folders: job list must be one explicit JSON file")
    if resolved.suffix.lower() != ".json":
        raise ResearchToggleWorkerError("job list must be a .json file")
    return resolved


def validate_job_record(raw_job: object, index: int) -> dict[str, str]:
    if not isinstance(raw_job, dict):
        raise ResearchToggleWorkerError(f"job {index} must be an object")
    required_keys = {"topic_id", "source", "mode"}
    if set(raw_job.keys()) != required_keys:
        raise ResearchToggleWorkerError(f"job {index} must contain only topic_id, source, and mode")
    topic_id = raw_job.get("topic_id")
    source = raw_job.get("source")
    mode = raw_job.get("mode")
    if not isinstance(topic_id, str) or not topic_id.strip():
        raise ResearchToggleWorkerError(f"job {index} requires one explicit topic_id string")
    if not isinstance(source, str) or not source.strip():
        raise ResearchToggleWorkerError(f"job {index} requires one explicit source string")
    if mode != "candidate_only":
        raise ResearchToggleWorkerError(f"job {index} mode must be candidate_only")
    if any(marker in topic_id for marker in ("*", "?", "[", "]", "\\", "/")):
        raise ResearchToggleWorkerError(f"job {index} topic_id must be explicit, not a wildcard/path")
    if any(marker in source for marker in ("*", "?", "[")):
        raise ResearchToggleWorkerError(f"job {index} source must be explicit, not a wildcard")
    note_generator.find_topic(topic_id.strip())
    note_generator.validate_source_path(source.strip())
    return {"topic_id": topic_id.strip(), "source": source.strip(), "mode": "candidate_only"}


def load_jobs(raw_jobs_path: str) -> tuple[Path, list[dict[str, str]]]:
    path = validate_jobs_path(raw_jobs_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ResearchToggleWorkerError("job list JSON could not be parsed") from exc
    if not isinstance(payload, list):
        raise ResearchToggleWorkerError("job list must be a JSON array")
    if not payload:
        raise ResearchToggleWorkerError("job list must contain at least one explicit job")
    if len(payload) > MAX_JOBS:
        raise ResearchToggleWorkerError("MAX_JOB_LIMIT_REQUIRED: job list contains more than three jobs")
    return path, [validate_job_record(job, index + 1) for index, job in enumerate(payload)]


def extract_output_paths(rendered_output: str) -> list[str]:
    paths: list[str] = []
    markers = [
        "research_note_path=",
        "lesson_candidate_path=",
        "memory_candidate_proposal_path=",
        "self_learning_receipt_path=",
        "WROTE_SELF_LEARNING_RECEIPT ",
    ]
    for line in rendered_output.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        for marker in markers:
            if marker in stripped:
                value = stripped.split(marker, 1)[1].strip()
                if value and value not in paths:
                    paths.append(value)
    return paths


def run_candidate_job(job: dict[str, str], mode: str, index: int) -> dict[str, object]:
    try:
        if mode == "dry-run":
            rendered = mini_runner.run_dry(job["topic_id"], job["source"])
        else:
            rendered = mini_runner.run_write_candidates(job["topic_id"], job["source"])
        return {
            "job_id": f"job_{index}",
            "topic_id": job["topic_id"],
            "source": job["source"],
            "mode": job["mode"],
            "status": "completed",
            "stopped": False,
            "stop_reason": "not_stopped",
            "output_paths": extract_output_paths(rendered),
            "summary": "candidate-only research job completed; outputs remain untrusted",
        }
    except (
        mini_runner.SelfLearningMiniRunnerError,
        mini_runner.note_generator.ResearchNoteError,
        mini_runner.lesson_extractor.LessonCandidateError,
        mini_runner.memory_proposal.MemoryCandidateProposalError,
        OSError,
    ) as exc:
        return {
            "job_id": f"job_{index}",
            "topic_id": job["topic_id"],
            "source": job["source"],
            "mode": job["mode"],
            "status": "stopped",
            "stopped": True,
            "stop_reason": str(exc),
            "output_paths": [],
            "summary": "job stopped before or during bounded candidate-only run",
        }


def check_enabled_for_run() -> dict[str, object]:
    state = load_state()
    if state.get("enabled") is not True:
        raise ResearchToggleWorkerError("research toggle worker is disabled; enable it before run-once or overnight")
    return state


def build_receipt(
    run_id: str,
    started_at: str,
    completed_at: str,
    mode: str,
    state: dict[str, object],
    jobs: list[dict[str, str]],
    job_results: list[dict[str, object]],
    max_runtime_minutes: int,
    max_jobs: int,
    protected_action_id: str,
    password_gate_checked: bool,
    stop_reason: str = "not_stopped",
) -> dict[str, object]:
    jobs_run = sum(1 for result in job_results if not result.get("stopped"))
    jobs_stopped = sum(1 for result in job_results if result.get("stopped"))
    output_paths: list[str] = []
    for result in job_results:
        for path in result.get("output_paths", []):
            if str(path) not in output_paths:
                output_paths.append(str(path))
    stopped = jobs_stopped > 0 or stop_reason != "not_stopped"
    final_summary = (
        f"{mode} finished with {jobs_run} completed job(s), {jobs_stopped} stopped job(s), "
        "candidate-only outputs, and no trusted-memory/source/provider/runtime behavior."
    )
    if stopped and stop_reason == "not_stopped":
        stop_reason = "; ".join(str(result.get("stop_reason")) for result in job_results if result.get("stopped")) or "stopped"
    return {
        "research_worker_run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "mode": mode,
        "research_toggle_state": state.get("research_toggle_state", "OFF"),
        "jobs_requested": len(jobs),
        "jobs_run": jobs_run,
        "jobs_stopped": jobs_stopped,
        "output_paths": output_paths,
        "max_runtime_minutes": max_runtime_minutes,
        "max_jobs": max_jobs,
        "password_gate_checked": password_gate_checked,
        "protected_action_id": protected_action_id,
        "safety_boundary": SAFETY_BOUNDARY,
        "stopped": stopped,
        "stop_reason": stop_reason,
        "final_summary": final_summary,
        "no_trusted_memory_write": True,
        "no_source_mutation": True,
        "no_provider_network_browser": True,
        "no_model_runtime": True,
        "no_background_escape": True,
        "no_startup_autorun_install": True,
        "job_results": job_results,
    }


def render_receipt(receipt: dict[str, object]) -> str:
    lines = [
        "# Engel Research Toggle Overnight Worker Receipt V1",
        "",
        "Labels:",
        *[f"- {label}" for label in OUTPUT_LABELS],
        "",
        "Worker status:",
        *[f"- {status}" for status in WORKER_STATUS],
        "",
    ]
    for field in RECEIPT_FIELDS:
        value = receipt.get(field, "")
        lines.append(f"## {field}")
        if isinstance(value, list):
            if value:
                lines.extend(f"- {item}" for item in value)
            else:
                lines.append("- none")
        else:
            lines.append(str(value))
        lines.append("")
    lines.append("## job_results")
    for result in receipt.get("job_results", []):
        if isinstance(result, dict):
            lines.append(
                f"- {result.get('job_id')}: {result.get('status')} / "
                f"{result.get('topic_id')} / {result.get('source')} / {result.get('stop_reason')}"
            )
    lines.extend(
        [
            "",
            "## boundary_reminder",
            "Research toggle worker receipts are not trusted memory.",
            "Candidate outputs require human review and separate trusted-memory promotion.",
            "No provider/network/browser/model/trusted-memory/source-mutation/patch-apply/verifier-update/package/startup behavior was authorized.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_summary_report(receipt: dict[str, object]) -> str:
    lines = [
        "# Engel Research Toggle Worker Summary V1",
        "",
        "Labels:",
        *[f"- {label}" for label in OUTPUT_LABELS],
        "",
        "Summary:",
        f"- research_worker_run_id: {receipt['research_worker_run_id']}",
        f"- mode: {receipt['mode']}",
        f"- jobs_requested: {receipt['jobs_requested']}",
        f"- jobs_run: {receipt['jobs_run']}",
        f"- jobs_stopped: {receipt['jobs_stopped']}",
        f"- stopped: {receipt['stopped']}",
        f"- stop_reason: {receipt['stop_reason']}",
        "",
        "Output paths:",
    ]
    output_paths = receipt.get("output_paths", [])
    if isinstance(output_paths, list) and output_paths:
        lines.extend(f"- {path}" for path in output_paths)
    else:
        lines.append("- none")
    lines.extend(["", "Safety boundary:", str(receipt["safety_boundary"])])
    return "\n".join(lines).rstrip() + "\n"


def write_receipt_and_summary(receipt: dict[str, object]) -> tuple[Path, Path]:
    OVERNIGHT_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    receipt_dir = OVERNIGHT_RECEIPT_DIR.resolve(strict=False)
    summary_dir = SUMMARY_DIR.resolve(strict=False)
    if not is_relative_to(receipt_dir, PROJECT_ROOT.resolve()) or not is_relative_to(summary_dir, PROJECT_ROOT.resolve()):
        raise ResearchToggleWorkerError("receipt folder escaped project root")
    name = safe_slug(str(receipt["research_worker_run_id"]))
    receipt_path = (receipt_dir / f"{name}_receipt.md").resolve(strict=False)
    summary_path = (summary_dir / f"{name}_summary.md").resolve(strict=False)
    if not is_relative_to(receipt_path, receipt_dir) or not is_relative_to(summary_path, summary_dir):
        raise ResearchToggleWorkerError("receipt output escaped bounded report folders")
    receipt_path.write_text(render_receipt(receipt), encoding="utf-8")
    summary_path.write_text(render_summary_report(receipt), encoding="utf-8")
    state = load_state()
    state["last_receipt_path"] = project_relative(receipt_path)
    state["last_summary_path"] = project_relative(summary_path)
    state["last_updated_at"] = now_utc()
    write_state(state)
    return receipt_path, summary_path


def newest_file_label(folder: Path) -> str:
    if not folder.exists():
        return "none"
    files = [path for path in folder.iterdir() if path.is_file() and path.name != ".gitkeep"]
    if not files:
        return "none"
    newest = max(files, key=lambda path: path.stat().st_mtime)
    return project_relative(newest)


def receipt_count(folder: Path) -> int:
    if not folder.exists():
        return 0
    return sum(1 for path in folder.iterdir() if path.is_file() and path.name != ".gitkeep")


def worker_status() -> dict[str, object]:
    state = load_state()
    return {
        "status_labels": list(WORKER_STATUS),
        "enabled": bool(state.get("enabled")),
        "research_toggle_state": "ON" if state.get("enabled") else "OFF",
        "overnight_worker_status": "enabled" if state.get("enabled") else "disabled",
        "disabled_by_default": True,
        "password_gate_required": False,
        "protected_action_registry_required": True,
        "candidate_only": True,
        "local_only_by_default": True,
        "max_jobs": MAX_JOBS,
        "max_runtime_minutes": MAX_RUNTIME_MINUTES,
        "approved_local_sources_only": True,
        "explicit_job_list_only": True,
        "kill_switch_status": str(state.get("kill_switch_status") or "READY"),
        "last_receipt_path": state.get("last_receipt_path") or newest_file_label(OVERNIGHT_RECEIPT_DIR),
        "receipt_count": receipt_count(OVERNIGHT_RECEIPT_DIR),
        "summary_count": receipt_count(SUMMARY_DIR),
        "startup_enabled": False,
        "startup_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def render_status() -> str:
    status = worker_status()
    lines = [
        "Engel Research Toggle Overnight Worker V1",
        "",
        "Status:",
        *[f"- {label}" for label in WORKER_STATUS],
        "",
        "Research Toggle status: " + str(status["research_toggle_state"]),
        "Overnight Research Worker status: " + str(status["overnight_worker_status"]),
        "Password gate required: NO",
        "Protected action registry required: YES",
        "Candidate-only boundary: YES",
        "",
        "Current limits:",
        f"- max jobs: {MAX_JOBS}",
        f"- max runtime minutes: {MAX_RUNTIME_MINUTES}",
        "- approved local sources only",
        "- explicit project-local JSON job list only",
        "- max 1 topic/source per job",
        "",
        "Last receipt path: " + str(status["last_receipt_path"] or "none"),
        "Kill switch status: " + str(status["kill_switch_status"]),
        "",
        "Research toggle enables bounded candidate-only research. It does not enable provider/network/browser/model runtime, trusted memory writes, source mutation, or patch apply.",
        "",
        "Safe next steps:",
        "- Enable or disable the Research toggle through the GUI without a password prompt.",
        "- Prepare an explicit project-local JSON job list.",
        "- Dry-run: python engel_research_toggle_worker.py --dry-run --jobs <project-local-json>",
        "- Run once after enable: python engel_research_toggle_worker.py --run-once --jobs <project-local-json>",
        "- Overnight after enable: python engel_research_toggle_worker.py --overnight --jobs <project-local-json> --max-runtime-minutes 480 --max-jobs 3",
        "- Disable: python engel_research_toggle_worker.py --disable",
        "- Kill switch: python engel_research_toggle_worker.py --kill-switch",
    ]
    if not status["enabled"]:
        lines.extend(
            [
                "",
                "OFF meaning:",
                "- no overnight research worker enabled",
                "- no background research loop",
                "- status visible only",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "ON meaning:",
                "- bounded research worker mode is enabled",
                "- only approved bounded jobs may run",
                "- worker still needs explicit CLI run/start command",
                "- startup autorun is not installed",
                "- receipts are required",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def run_batch(raw_jobs_path: str, mode: str, max_runtime_minutes: int, max_jobs: int) -> tuple[str, bool]:
    jobs_path, jobs = load_jobs(raw_jobs_path)
    if max_jobs < 1 or max_jobs > MAX_JOBS:
        raise ResearchToggleWorkerError("max jobs must be between 1 and 3")
    if max_runtime_minutes < 1 or max_runtime_minutes > MAX_RUNTIME_MINUTES:
        raise ResearchToggleWorkerError("max runtime minutes must be between 1 and 480")
    if len(jobs) > max_jobs:
        raise ResearchToggleWorkerError("requested jobs exceed the run max-jobs limit")
    if mode in {"run-once", "overnight"}:
        state = check_enabled_for_run()
        protected_action_id = RUN_ONCE_ACTION_ID if mode == "run-once" else OVERNIGHT_ACTION_ID
        password_checked = False
    else:
        state = load_state()
        protected_action_id = "run_research_toggle_worker_dry_run"
        password_checked = False
    started_at = now_utc()
    deadline = time.monotonic() + (max_runtime_minutes * 60)
    results: list[dict[str, object]] = []
    stop_reason = "not_stopped"
    for index, job in enumerate(jobs[:max_jobs], start=1):
        if time.monotonic() > deadline:
            stop_reason = "TIME_LIMIT_REQUIRED: max runtime reached before next job"
            break
        results.append(run_candidate_job(job, "dry-run" if mode == "dry-run" else mode, index))
        if mode == "overnight" and index < len(jobs[:max_jobs]):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_reason = "TIME_LIMIT_REQUIRED: max runtime reached after job"
                break
            time.sleep(min(DEFAULT_CADENCE_SECONDS, remaining))
    completed_at = now_utc()
    receipt = build_receipt(
        make_run_id(mode, project_relative(jobs_path), started_at),
        started_at,
        completed_at,
        mode,
        state,
        jobs,
        results,
        max_runtime_minutes,
        max_jobs,
        protected_action_id,
        password_checked,
        stop_reason,
    )
    receipt_path = None
    summary_path = None
    if mode != "dry-run":
        receipt_path, summary_path = write_receipt_and_summary(receipt)
    lines = [
        "Engel Research Toggle Overnight Worker V1",
        "",
        f"Mode: {mode}",
        f"research_worker_run_id: {receipt['research_worker_run_id']}",
        f"jobs_requested: {receipt['jobs_requested']}",
        f"jobs_run: {receipt['jobs_run']}",
        f"jobs_stopped: {receipt['jobs_stopped']}",
        f"stopped: {receipt['stopped']}",
        f"stop_reason: {receipt['stop_reason']}",
        "",
        "Output paths:",
    ]
    outputs = receipt.get("output_paths", [])
    if isinstance(outputs, list) and outputs:
        lines.extend(f"- {path}" for path in outputs)
    else:
        lines.append("- none")
    if receipt_path is not None and summary_path is not None:
        lines.extend(
            [
                "",
                "Receipt paths:",
                "- " + project_relative(receipt_path),
                "- " + project_relative(summary_path),
            ]
        )
    lines.extend(["", "Safety boundary:", SAFETY_BOUNDARY])
    return "\n".join(lines).rstrip() + "\n", bool(receipt["stopped"])


def explain_text() -> str:
    return textwrap.dedent(
        """\
        Engel Research Toggle Overnight Worker V1

        The GUI Research toggle controls whether bounded candidate-only research worker
        mode is enabled. It does not start provider/network/browser/model research,
        write trusted memory, mutate source, apply patches, update verifiers, install
        startup autorun, or create an endless loop.

        OFF:
        - no overnight research worker enabled
        - no background research loop
        - status visible only

        ON:
        - human enabled bounded research worker mode without a password prompt
        - only explicit project-local JSON job lists may run
        - CLI run-once or overnight command is still required
        - outputs remain untrusted and candidate-only
        - receipts are required
        - max 3 jobs and max 8 hours
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or control Engel's bounded Research toggle worker.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show bounded worker status.")
    mode.add_argument("--dry-run", action="store_true", help="Validate and preview one explicit job list without writes.")
    mode.add_argument("--run-once", action="store_true", help="Run one bounded candidate-only batch once.")
    mode.add_argument("--overnight", action="store_true", help="Run bounded overnight candidate-only batch with limits.")
    mode.add_argument("--enable", action="store_true", help="Enable worker state without a password prompt; does not start a loop.")
    mode.add_argument("--disable", action="store_true", help="Disable worker state without a password prompt.")
    mode.add_argument("--kill-switch", action="store_true", help="Trip bounded kill switch metadata without a password prompt.")
    parser.add_argument("--jobs", metavar="PROJECT_LOCAL_JSON", help="Explicit project-local JSON job list.")
    parser.add_argument("--password-prompt", action="store_true", help="Compatibility flag; ignored because Research no longer requires a password prompt.")
    parser.add_argument("--max-runtime-minutes", type=int, default=MAX_RUNTIME_MINUTES, help="Maximum runtime in minutes, capped at 480.")
    parser.add_argument("--max-jobs", type=int, default=MAX_JOBS, help="Maximum jobs, capped at 3.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        if not any([args.status, args.dry_run, args.run_once, args.overnight, args.enable, args.disable, args.kill_switch]):
            out.write(render_status())
            return 0
        if args.status:
            out.write(render_status())
            return 0
        if args.enable or args.disable or args.kill_switch:
            if args.enable:
                set_worker_enabled(True)
            elif args.disable:
                set_worker_enabled(False)
            else:
                activate_kill_switch()
            out.write(render_status())
            return 0
        if not args.jobs:
            err.write("Explicit --jobs <project-local-json> is required.\n")
            return 2
        mode = "dry-run" if args.dry_run else "run-once" if args.run_once else "overnight"
        rendered, stopped = run_batch(args.jobs, mode, args.max_runtime_minutes, args.max_jobs)
        out.write(rendered)
        return 1 if stopped else 0
    except ResearchToggleWorkerError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
