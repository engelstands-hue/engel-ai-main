from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import textwrap

import engel_global_password_gate as global_password_gate
import engel_self_learning_mini_runner as mini_runner


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "self_learning_scheduler_receipts"
SCHEDULER_VERSION = "ENGEL_BOUNDED_SELF_LEARNING_SCHEDULER_V1"
MAX_JOBS_PER_RUN = 3

SCHEDULER_STATUS = [
    "BOUNDED_SELF_LEARNING_SCHEDULER",
    "FOREGROUND_COMMAND_ONLY",
    "EXPLICIT_JOB_LIST_ONLY",
    "MAX_THREE_JOBS_PER_RUN",
    "ONE_TOPIC_ONE_SOURCE_PER_JOB",
    "CANDIDATE_OUTPUTS_ONLY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_AUTO_DOWNLOADS",
    "NO_AUTO_INDEXING",
    "NO_MODEL_TRAINING",
    "NO_RUNTIME_TRIGGER",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

RECEIPT_FIELDS = [
    "scheduler_run_id",
    "jobs_requested",
    "jobs_run",
    "jobs_stopped",
    "output_paths",
    "safety_boundary",
    "verification_summary",
    "stopped",
    "stop_reason",
]

JOB_REQUIRED_KEYS = {"topic_id", "source"}

SAFETY_BOUNDARY = (
    "BOUNDED_SELF_LEARNING_SCHEDULER / FOREGROUND_COMMAND_ONLY / "
    "EXPLICIT_JOB_LIST_ONLY / MAX_THREE_JOBS_PER_RUN / ONE_TOPIC_ONE_SOURCE_PER_JOB / "
    "CANDIDATE_OUTPUTS_ONLY / NOT_TRUSTED_MEMORY. No trusted memory write, source mutation, "
    "verifier update, self-fix policy update, provider call, network, browser, automatic download, "
    "automatic indexing, model training, runtime trigger, background worker, startup autorun, "
    "folder scan, wildcard source, external drive access, live/staging read, or model folder read."
)


class BoundedSelfLearningSchedulerError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve())).replace("/", "\\")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_scheduler_run_id(jobs_path: str, mode: str, timestamp: str) -> str:
    seed = f"{SCHEDULER_VERSION}|{jobs_path}|{mode}|{timestamp}".encode("utf-8")
    return "self_learning_scheduler_run_" + hashlib.sha256(seed).hexdigest()[:16]


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_").lower() or "unknown"


def reject_unsafe_jobs_path_text(raw_jobs_path: str) -> None:
    lowered = raw_jobs_path.lower()
    uppered = raw_jobs_path.upper()
    if lowered.startswith(("http://", "https://")):
        raise BoundedSelfLearningSchedulerError("reject URLs: job list must be a project-local JSON file")
    if raw_jobs_path.startswith("\\\\"):
        raise BoundedSelfLearningSchedulerError("reject UNC paths: job list must be project-local")
    if any(marker in raw_jobs_path for marker in ("*", "?", "[")):
        raise BoundedSelfLearningSchedulerError("reject wildcards: explicit job list file only")
    retired_suffix = "\\ENGEL_" + "APP_MEMORY"
    retired_roots = tuple(f"{letter}:{retired_suffix}" for letter in ("E", "F", "G"))
    if uppered.startswith(retired_roots):
        raise BoundedSelfLearningSchedulerError("reject retired external-drive roots: scheduler job lists must stay inside the project")


def validate_jobs_path(raw_jobs_path: str) -> Path:
    reject_unsafe_jobs_path_text(raw_jobs_path)
    candidate = Path(raw_jobs_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve(strict=False)
    if not is_relative_to(resolved, PROJECT_ROOT.resolve()):
        raise BoundedSelfLearningSchedulerError("reject paths outside project root")
    if resolved.anchor == str(resolved):
        raise BoundedSelfLearningSchedulerError("reject drive roots: job list must be one explicit JSON file")
    relative_parts = [part.lower() for part in resolved.relative_to(PROJECT_ROOT.resolve()).parts]
    if len(relative_parts) >= 2 and relative_parts[0] == "live" and relative_parts[1] == "app":
        raise BoundedSelfLearningSchedulerError("reject live\\app paths")
    if relative_parts and relative_parts[0] == "staging":
        raise BoundedSelfLearningSchedulerError("reject staging paths")
    if any(part in {"model", "models", "model_library", "hf", "ollama", "trusted_memory"} for part in relative_parts):
        raise BoundedSelfLearningSchedulerError("reject model or trusted-memory paths")
    if not resolved.exists():
        raise BoundedSelfLearningSchedulerError("job list file does not exist")
    if resolved.is_dir():
        raise BoundedSelfLearningSchedulerError("reject folders: job list must be one explicit JSON file")
    if resolved.suffix.lower() != ".json":
        raise BoundedSelfLearningSchedulerError("job list must be a .json file")
    return resolved


def validate_job_record(raw_job: object, index: int) -> dict[str, str]:
    if not isinstance(raw_job, dict):
        raise BoundedSelfLearningSchedulerError(f"job {index} must be an object with topic_id and source")
    if set(raw_job.keys()) != JOB_REQUIRED_KEYS:
        raise BoundedSelfLearningSchedulerError(f"job {index} must contain only topic_id and source")
    topic_id = raw_job.get("topic_id")
    source = raw_job.get("source")
    if not isinstance(topic_id, str) or not topic_id.strip():
        raise BoundedSelfLearningSchedulerError(f"job {index} requires one explicit topic_id string")
    if not isinstance(source, str) or not source.strip():
        raise BoundedSelfLearningSchedulerError(f"job {index} requires one explicit source string")
    if any(marker in topic_id for marker in ("*", "?", "[", "]", "\\", "/")):
        raise BoundedSelfLearningSchedulerError(f"job {index} topic_id must be explicit, not a wildcard/path")
    if any(marker in source for marker in ("*", "?", "[")):
        raise BoundedSelfLearningSchedulerError(f"job {index} source must be explicit, not a wildcard")
    return {"topic_id": topic_id.strip(), "source": source.strip()}


def load_jobs(raw_jobs_path: str) -> tuple[Path, list[dict[str, str]]]:
    path = validate_jobs_path(raw_jobs_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BoundedSelfLearningSchedulerError("job list JSON could not be parsed") from exc
    if not isinstance(payload, list):
        raise BoundedSelfLearningSchedulerError("job list must be a JSON array")
    if not payload:
        raise BoundedSelfLearningSchedulerError("job list must contain at least one explicit job")
    if len(payload) > MAX_JOBS_PER_RUN:
        raise BoundedSelfLearningSchedulerError("MAX_THREE_JOBS_PER_RUN: job list contains more than three jobs")
    return path, [validate_job_record(job, index + 1) for index, job in enumerate(payload)]


def extract_output_paths(rendered_output: str) -> list[str]:
    output_paths: list[str] = []
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
                if value and value not in output_paths:
                    output_paths.append(value)
    return output_paths


def run_scheduler_job(job: dict[str, str], mode: str, index: int) -> dict[str, object]:
    topic_id = job["topic_id"]
    source = job["source"]
    try:
        if mode == "dry-run":
            rendered = mini_runner.run_dry(topic_id, source)
        else:
            rendered = mini_runner.run_write_candidates(topic_id, source)
        return {
            "job_id": f"job_{index}",
            "topic_id": topic_id,
            "source": source,
            "status": "completed",
            "stopped": False,
            "stop_reason": "not_stopped",
            "output_paths": extract_output_paths(rendered),
            "summary": "candidate learning job completed; outputs remain untrusted/candidate-only",
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
            "topic_id": topic_id,
            "source": source,
            "status": "stopped",
            "stopped": True,
            "stop_reason": str(exc),
            "output_paths": [],
            "summary": "job stopped before or during bounded candidate-learning run",
        }


def build_scheduler_receipt(run_id: str, jobs: list[dict[str, str]], job_results: list[dict[str, object]], mode: str) -> dict[str, object]:
    jobs_run = sum(1 for result in job_results if not result["stopped"])
    jobs_stopped = sum(1 for result in job_results if result["stopped"])
    output_paths: list[str] = []
    for result in job_results:
        for path in result.get("output_paths", []):
            if str(path) not in output_paths:
                output_paths.append(str(path))
    stopped = jobs_stopped > 0
    stop_reasons = [str(result["stop_reason"]) for result in job_results if result["stopped"]]
    return {
        "scheduler_run_id": run_id,
        "jobs_requested": len(jobs),
        "jobs_run": jobs_run,
        "jobs_stopped": jobs_stopped,
        "output_paths": output_paths,
        "safety_boundary": SAFETY_BOUNDARY,
        "verification_summary": f"{mode}: bounded scheduler enforced explicit job list, max three jobs, one topic/source per job, and mini-runner source validation.",
        "stopped": stopped,
        "stop_reason": "; ".join(stop_reasons) if stop_reasons else "not_stopped",
        "job_results": job_results,
    }


def render_receipt(receipt: dict[str, object]) -> str:
    lines = [
        "# Engel Bounded Self-Learning Scheduler Receipt V1",
        "",
        "Labels:",
        "- UNTRUSTED",
        "- CANDIDATE_OUTPUTS_ONLY",
        "- NOT_TRUSTED_MEMORY",
        "- NO_AUTOMATION_TRIGGERED",
        "- HUMAN_REVIEW_REQUIRED",
        "",
        "Scheduler status:",
        *[f"- {status}" for status in SCHEDULER_STATUS],
        "",
    ]
    for field in RECEIPT_FIELDS:
        value = receipt.get(field, "")
        lines.append(f"## {field}")
        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value)
        else:
            lines.append(str(value))
        lines.append("")
    lines.append("## job_results")
    for result in receipt.get("job_results", []):
        if isinstance(result, dict):
            lines.append(f"- {result.get('job_id')}: {result.get('status')} / {result.get('topic_id')} / {result.get('source')} / {result.get('stop_reason')}")
    lines.append("")
    lines.append("## boundary_reminder")
    lines.append("Scheduler receipts are not trusted memory. Candidate outputs require later human review.")
    lines.append("No background worker, startup autorun, provider call, network, browser, automatic download, automatic indexing, model training, runtime trigger, source mutation, verifier update, self-fix policy update, or trusted-memory write was authorized by this scheduler run.")
    return "\n".join(lines).rstrip() + "\n"


def write_scheduler_receipt(receipt: dict[str, object]) -> Path:
    output_dir = RECEIPT_DIR.resolve(strict=False)
    if not is_relative_to(output_dir, PROJECT_ROOT.resolve()):
        raise BoundedSelfLearningSchedulerError("scheduler receipt folder escaped project root")
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    target = (output_dir / f"{safe_slug(str(receipt['scheduler_run_id']))}_receipt.md").resolve(strict=False)
    if not is_relative_to(target, output_dir):
        raise BoundedSelfLearningSchedulerError("scheduler receipt output escaped reports\\self_learning_scheduler_receipts")
    target.write_text(render_receipt(receipt), encoding="utf-8")
    return target


def render_scheduler_summary(receipt: dict[str, object], *, mode: str, receipt_path: Path | None = None) -> str:
    lines = [
        "Engel Bounded Self-Learning Scheduler V1",
        "",
        f"Mode: {mode}",
        "",
        "Status:",
        *[f"- {status}" for status in SCHEDULER_STATUS],
        "",
        "Summary:",
        f"- scheduler_run_id: {receipt['scheduler_run_id']}",
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
    if receipt_path is not None:
        lines.extend(["", f"WROTE_SELF_LEARNING_SCHEDULER_RECEIPT {project_relative(receipt_path)}"])
    lines.extend(["", "Safety boundary:", str(receipt["safety_boundary"])])
    return "\n".join(lines).rstrip() + "\n"


def run_jobs_from_file(raw_jobs_path: str, mode: str, *, write_receipt: bool) -> tuple[str, bool]:
    jobs_path, jobs = load_jobs(raw_jobs_path)
    timestamp = now_utc()
    run_id = make_scheduler_run_id(project_relative(jobs_path), mode, timestamp)
    job_results = [run_scheduler_job(job, mode, index + 1) for index, job in enumerate(jobs)]
    receipt = build_scheduler_receipt(run_id, jobs, job_results, mode)
    receipt_path = write_scheduler_receipt(receipt) if write_receipt else None
    return render_scheduler_summary(receipt, mode=mode, receipt_path=receipt_path), bool(receipt["stopped"])


def demo_text() -> str:
    demo_receipt = {
        "scheduler_run_id": make_scheduler_run_id("DEMO_ONLY", "demo", now_utc()),
        "jobs_requested": 1,
        "jobs_run": 0,
        "jobs_stopped": 0,
        "output_paths": [],
        "safety_boundary": SAFETY_BOUNDARY,
        "verification_summary": "demo only; no job list read, no candidate outputs written, no scheduler receipt written",
        "stopped": False,
        "stop_reason": "not_stopped_demo_only",
        "job_results": [
            {
                "job_id": "job_1",
                "topic_id": "SRT-01-01-python_error_handling_patterns_for_local_tools",
                "source": "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md",
                "status": "demo_only_not_run",
                "stopped": False,
                "stop_reason": "demo_only",
                "output_paths": [],
            }
        ],
    }
    return render_scheduler_summary(demo_receipt, mode="DEMO_ONLY")


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Bounded Self-Learning Scheduler V1

        Status:
        BOUNDED_SELF_LEARNING_SCHEDULER / FOREGROUND_COMMAND_ONLY / EXPLICIT_JOB_LIST_ONLY / MAX_THREE_JOBS_PER_RUN / ONE_TOPIC_ONE_SOURCE_PER_JOB / CANDIDATE_OUTPUTS_ONLY

        Usage:
          python engel_bounded_self_learning_scheduler.py --demo
          python engel_bounded_self_learning_scheduler.py --jobs <project-local-json> --dry-run
          python engel_bounded_self_learning_scheduler.py --jobs <project-local-json> --write-candidates --password-prompt

        Job list format:
          [
            {
              "topic_id": "...",
              "source": "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md"
            }
          ]

        Boundaries:
          Foreground command only. Explicit job list only. Max three jobs per run. One topic and
          one source per job. No implicit topic selection, folder scan, wildcard source, external
          drive read, URL, background loop, no startup integration, trusted-memory write, source
          mutation, verifier update, self-fix policy update, provider call, network, browser,
          automatic download, automatic indexing, model training, or runtime trigger.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Run bounded Engel self-learning mini-runner jobs from one explicit JSON job list.")
    parser.add_argument("--demo", action="store_true", help="Print scheduler boundaries and a demo job shape without running jobs.")
    parser.add_argument("--jobs", metavar="PROJECT_LOCAL_JSON", help="Explicit project-local JSON job list.")
    parser.add_argument("--dry-run", action="store_true", help="Run mini-runner jobs in dry-run mode only; do not write scheduler receipt.")
    parser.add_argument("--write-candidates", action="store_true", help="Run mini-runner write-candidates mode and write a scheduler receipt.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for the global password before protected write-candidates mode.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not any([args.demo, args.jobs, args.dry_run, args.write_candidates]):
        out.write(usage_text())
        return 0
    if args.demo:
        if any([args.jobs, args.dry_run, args.write_candidates, args.password_prompt]):
            err.write("Use --demo by itself.\n")
            return 2
        out.write(demo_text())
        return 0
    if not args.jobs:
        err.write("Explicit --jobs <project-local-json> is required outside demo.\n")
        return 2
    if args.dry_run and args.write_candidates:
        err.write("Choose either --dry-run or --write-candidates, not both.\n")
        return 2
    if not args.dry_run and not args.write_candidates:
        err.write("Choose --dry-run or --write-candidates.\n")
        return 2
    if args.write_candidates and not args.password_prompt:
        err.write("Protected action requires --password-prompt.\n")
        return 2
    try:
        mode = "dry-run" if args.dry_run else "write-candidates"
        if args.write_candidates:
            global_password_gate.prompt_and_require_action("run_bounded_self_learning_scheduler")
        rendered, stopped = run_jobs_from_file(args.jobs, mode, write_receipt=args.write_candidates)
        out.write(rendered)
        return 1 if stopped else 0
    except BoundedSelfLearningSchedulerError as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1
    except global_password_gate.PasswordGateError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
