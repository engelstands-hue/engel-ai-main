from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
import sys
import textwrap

import engel_ai_growth_dashboard as ai_growth_dashboard
import engel_global_password_gate as global_password_gate
import engel_bounded_self_learning_scheduler as self_learning_scheduler
import engel_candidate_review_dashboard as candidate_review_dashboard
import engel_low_risk_self_fix_runner as low_risk_self_fix_runner
import engel_research_to_fix_loop as research_to_fix_loop


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "daily_cycle_receipts"
RUNNER_VERSION = "ENGEL_DAILY_CYCLE_RUNNER_V1"

RUNNER_STATUS = [
    "DAILY_CYCLE_RUNNER",
    "FOREGROUND_COMMAND_ONLY",
    "BOUNDED_RUN_ONLY",
    "ONE_CYCLE_PER_INVOCATION",
    "RECEIPT_REQUIRED",
    "NO_STARTUP_AUTORUN",
    "NO_ENDLESS_LOOP",
    "NO_BACKGROUND_WORKER",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_PACKAGE_REFRESH",
    "NO_UNAPPROVED_MEMORY_WRITE",
    "NO_UNAPPROVED_SOURCE_MUTATION",
    "NO_HIGH_RISK_SELF_FIX",
]

RECEIPT_FIELDS = [
    "daily_cycle_run_id",
    "started_at",
    "completed_at",
    "mode",
    "status_checks_run",
    "verifiers_run",
    "learning_jobs_run",
    "candidates_seen",
    "self_fix_dry_runs",
    "self_fixes_applied",
    "conical_failure_issues_created",
    "conical_failure_jobs_pending",
    "receipts_created",
    "stopped",
    "stop_reason",
    "safety_boundary",
    "final_summary",
]

VERIFIER_COMMANDS = [
    ["python", "tools\\verify_engel_ai_growth_dashboard.py"],
    ["python", "tools\\verify_engel_bounded_self_learning_scheduler.py"],
    ["python", "tools\\verify_engel_candidate_review_dashboard.py"],
    ["python", "tools\\verify_engel_low_risk_self_fix_runner.py"],
    ["python", "tools\\verify_engel_research_to_fix_loop.py"],
    ["python", "tools\\verify_untrusted_content_guard.py"],
    ["python", "tools\\verify_prompt_injection_guard.py"],
    ["python", "tools\\verify_authority_hierarchy.py"],
    ["python", "tools\\verify_living_systems_documentation_drift.py"],
]

CANDIDATE_FOLDERS = [
    "reports\\self_research_notes",
    "reports\\lesson_candidates",
    "reports\\memory_candidates",
    "reports\\verifier_improvement_candidates",
    "reports\\self_fix_improvement_candidates",
]

SAFETY_BOUNDARY = (
    "DAILY_CYCLE_RUNNER / FOREGROUND_COMMAND_ONLY / BOUNDED_RUN_ONLY / "
    "ONE_CYCLE_PER_INVOCATION / RECEIPT_REQUIRED. No startup autorun, endless loop, "
    "background worker, provider call, network, browser, model runtime, package refresh, "
    "unapproved memory write, high-risk self-fix, or unapproved source mutation. "
    "Low-risk self-fix dry-run comes first; applies remain bounded to pre-approved classes."
)


class DailyCycleRunnerError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve(strict=False)
    if not is_relative_to(path, PROJECT_ROOT.resolve()):
        raise DailyCycleRunnerError("daily cycle path escaped project root")
    return path


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve())).replace("/", "\\")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_daily_cycle_run_id(mode: str, started_at: str) -> str:
    seed = f"{RUNNER_VERSION}|{mode}|{started_at}".encode("utf-8")
    return "daily_cycle_run_" + hashlib.sha256(seed).hexdigest()[:16]


def command_label(command: list[str]) -> str:
    return " ".join(command)


def bounded_file_count(relative_folder: str) -> int:
    folder = project_path(relative_folder)
    if not folder.exists() or not folder.is_dir():
        return 0
    return sum(1 for item in folder.iterdir() if item.is_file() and item.name != ".gitkeep")


def candidate_counts() -> dict[str, int]:
    return {relative_folder: bounded_file_count(relative_folder) for relative_folder in CANDIDATE_FOLDERS}


def total_candidates_seen() -> int:
    return sum(candidate_counts().values())


def run_status_checks() -> tuple[list[str], str]:
    sections = [
        ("Engel AI Growth Dashboard V1", ai_growth_dashboard.render_dashboard()),
        ("Engel Candidate Review Dashboard V1", candidate_review_dashboard.render_dashboard()),
        ("Research-to-Fix Summary", research_to_fix_loop.render_summary()),
    ]
    rendered: list[str] = ["# Daily Cycle Status Checks", ""]
    for label, text in sections:
        rendered.extend([f"## {label}", text.rstrip(), ""])
    return [label for label, _text in sections], "\n".join(rendered).rstrip() + "\n"


def run_or_list_verifiers(mode: str) -> tuple[list[str], str, bool, str]:
    labels = [command_label(command) for command in VERIFIER_COMMANDS]
    if mode == "dry-run":
        rendered = ["# Daily Cycle Verifier Stack", "", "Dry-run lists verifier commands without running them:"]
        rendered.extend(f"- {label}" for label in labels)
        return labels, "\n".join(rendered).rstrip() + "\n", False, "not_stopped_dry_run_listed_verifiers"

    rendered = ["# Daily Cycle Verifier Stack", ""]
    stopped = False
    stop_reason = "not_stopped_verifiers_passed"
    for command in VERIFIER_COMMANDS:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        status = "PASS" if completed.returncode == 0 else "FAIL"
        rendered.append(f"- {status}: {command_label(command)}")
        if completed.returncode != 0:
            stopped = True
            stop_reason = "verifier stack failed: " + command_label(command)
            tail = (completed.stdout + "\n" + completed.stderr).strip().splitlines()[-8:]
            rendered.extend("  " + line for line in tail)
            break
    return labels, "\n".join(rendered).rstrip() + "\n", stopped, stop_reason


def run_low_risk_self_fix_dry_run() -> tuple[int, int, str, bool, str]:
    receipt = low_risk_self_fix_runner.run_issue("stale_pid_cleanup", "dry-run")
    rendered = low_risk_self_fix_runner.render_receipt(receipt)
    stopped = bool(receipt.get("stopped"))
    stop_reason = str(receipt.get("stop_reason", "not_stopped"))
    return 1, 0, rendered, stopped, stop_reason


def run_optional_scheduler(mode: str, jobs_path: str | None) -> tuple[int, list[str], str, bool, str]:
    if not jobs_path:
        return 0, [], "Bounded self-learning scheduler: not requested; no jobs file provided.\n", False, "not_stopped_scheduler_not_requested"

    jobs_file, jobs = self_learning_scheduler.load_jobs(jobs_path)
    scheduler_mode = "dry-run" if mode == "dry-run" else "write-candidates"
    rendered, stopped = self_learning_scheduler.run_jobs_from_file(
        project_relative(jobs_file),
        scheduler_mode,
        write_receipt=mode != "dry-run",
    )
    receipt_paths: list[str] = []
    for line in rendered.splitlines():
        marker = "WROTE_SELF_LEARNING_SCHEDULER_RECEIPT "
        if marker in line:
            receipt_paths.append(line.split(marker, 1)[1].strip())
    stop_reason = "bounded self-learning scheduler stopped a job" if stopped else "not_stopped_scheduler_completed"
    return len(jobs), receipt_paths, rendered, stopped, stop_reason


def safe_slug(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"_", "-"} else "_" for character in value).strip("_").lower()


def render_receipt_value(value: object) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value) if value else "none"
    if isinstance(value, dict):
        return "\n".join(f"- {key}: {val}" for key, val in value.items()) if value else "none"
    return str(value)


def render_daily_cycle_receipt(receipt: dict[str, object]) -> str:
    lines = [
        "# Engel Daily Cycle Runner Receipt V1",
        "",
        "Labels:",
        "- DAILY_CYCLE_RUNNER",
        "- FOREGROUND_COMMAND_ONLY",
        "- BOUNDED_RUN_ONLY",
        "- ONE_CYCLE_PER_INVOCATION",
        "- RECEIPT_REQUIRED",
        "- NOT_TRUSTED_MEMORY",
        "- NO_BACKGROUND_WORKER",
        "- NO_STARTUP_AUTORUN",
        "",
        "Runner status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
    ]
    for field in RECEIPT_FIELDS:
        lines.extend([f"## {field}", render_receipt_value(receipt.get(field, "")), ""])
    return "\n".join(lines).rstrip() + "\n"


def write_daily_cycle_receipt(receipt: dict[str, object]) -> Path:
    output_dir = RECEIPT_DIR.resolve(strict=False)
    if not is_relative_to(output_dir, PROJECT_ROOT.resolve()):
        raise DailyCycleRunnerError("daily cycle receipt folder escaped project root")
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = safe_slug(str(receipt["daily_cycle_run_id"]))
    target = (output_dir / f"{run_id}_{receipt['mode']}_receipt.md").resolve(strict=False)
    if not is_relative_to(target, output_dir):
        raise DailyCycleRunnerError("daily cycle receipt output escaped reports\\daily_cycle_receipts")
    target.write_text(render_daily_cycle_receipt(receipt), encoding="utf-8")
    return target


def build_daily_cycle_summary(
    *,
    mode: str,
    status_output: str,
    verifier_output: str,
    scheduler_output: str,
    self_fix_output: str,
    receipt: dict[str, object],
    receipt_path: Path | None,
) -> str:
    lines = [
        "Engel Daily Cycle Runner V1",
        "",
        "Status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
        f"Mode: {mode}",
        "",
        status_output.rstrip(),
        "",
        verifier_output.rstrip(),
        "",
        "# Bounded Self-Learning Scheduler",
        scheduler_output.rstrip(),
        "",
        "# Low-Risk Self-Fix Dry-Run",
        self_fix_output.rstrip(),
        "",
        "# Daily Cycle Receipt Summary",
        f"- daily_cycle_run_id: {receipt['daily_cycle_run_id']}",
        f"- stopped: {receipt['stopped']}",
        f"- stop_reason: {receipt['stop_reason']}",
        f"- candidates_seen: {receipt['candidates_seen']}",
        f"- self_fix_dry_runs: {receipt['self_fix_dry_runs']}",
        f"- self_fixes_applied: {receipt['self_fixes_applied']}",
        f"- final_summary: {receipt['final_summary']}",
    ]
    if receipt_path is not None:
        lines.append(f"- WROTE_DAILY_CYCLE_RECEIPT: {project_relative(receipt_path)}")
    return "\n".join(lines).rstrip() + "\n"


def run_daily_cycle(mode: str, jobs_path: str | None = None, *, write_receipt: bool = True) -> tuple[str, bool]:
    if mode not in {"dry-run", "run"}:
        raise DailyCycleRunnerError("mode must be dry-run or run")

    started_at = now_utc()
    run_id = make_daily_cycle_run_id(mode, started_at)
    status_checks_run, status_output = run_status_checks()
    verifiers_run, verifier_output, verifier_stopped, verifier_stop_reason = run_or_list_verifiers(mode)
    learning_jobs_run = 0
    scheduler_receipts: list[str] = []
    scheduler_output = "Bounded self-learning scheduler skipped because verifier stack stopped the cycle.\n"
    scheduler_stopped = False
    scheduler_stop_reason = "not_stopped_scheduler_skipped_after_verifier_stop"
    if not verifier_stopped:
        learning_jobs_run, scheduler_receipts, scheduler_output, scheduler_stopped, scheduler_stop_reason = run_optional_scheduler(mode, jobs_path)
    self_fix_dry_runs, self_fixes_applied, self_fix_output, self_fix_stopped, self_fix_stop_reason = run_low_risk_self_fix_dry_run()

    # Bounded failure->issue intake: failed conical jobs become deduped
    # self-upgrade issues (intake only; downstream stays the governed cycle).
    conical_failure_issues_created = 0
    conical_failure_jobs_pending = 0
    try:
        import sys as _sys
        _tools = str(Path(__file__).resolve().parent / "tools")
        if _tools not in _sys.path:
            _sys.path.insert(0, _tools)
        import engel_conical_failure_to_issue as _failure_ingest

        if mode == "run":
            _ingest_result = _failure_ingest.ingest(limit=5)
            conical_failure_issues_created = int(_ingest_result.get("issues_created_count") or 0)
            conical_failure_jobs_pending = int(_ingest_result.get("failed_jobs_pending") or 0)
        else:
            conical_failure_jobs_pending = len(_failure_ingest.scan_failed_jobs())
    except Exception:
        pass  # intake is best-effort; the cycle itself must never stop on it

    stopped = verifier_stopped or scheduler_stopped or self_fix_stopped
    stop_reasons = [
        reason
        for reason, is_stopped in [
            (verifier_stop_reason, verifier_stopped),
            (scheduler_stop_reason, scheduler_stopped),
            (self_fix_stop_reason, self_fix_stopped),
        ]
        if is_stopped
    ]
    stop_reason = "; ".join(stop_reasons) if stop_reasons else "not_stopped_one_cycle_completed"
    receipts_created = list(scheduler_receipts)
    if write_receipt:
        receipts_created.append("daily cycle receipt pending write")
    completed_at = now_utc()
    receipt = {
        "daily_cycle_run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "mode": mode,
        "status_checks_run": status_checks_run,
        "verifiers_run": verifiers_run,
        "learning_jobs_run": learning_jobs_run,
        "candidates_seen": total_candidates_seen(),
        "self_fix_dry_runs": self_fix_dry_runs,
        "self_fixes_applied": self_fixes_applied,
        "conical_failure_issues_created": conical_failure_issues_created,
        "conical_failure_jobs_pending": conical_failure_jobs_pending,
        "receipts_created": receipts_created,
        "stopped": stopped,
        "stop_reason": stop_reason,
        "safety_boundary": SAFETY_BOUNDARY,
        "final_summary": "one foreground bounded daily cycle completed and stopped" if not stopped else "daily cycle stopped safely",
    }
    receipt_path = write_daily_cycle_receipt(receipt) if write_receipt else None
    if receipt_path is not None:
        receipt["receipts_created"] = [item for item in receipts_created if item != "daily cycle receipt pending write"]
        receipt["receipts_created"].append(project_relative(receipt_path))
        receipt_path.write_text(render_daily_cycle_receipt(receipt), encoding="utf-8")
    rendered = build_daily_cycle_summary(
        mode=mode,
        status_output=status_output,
        verifier_output=verifier_output,
        scheduler_output=scheduler_output,
        self_fix_output=self_fix_output,
        receipt=receipt,
        receipt_path=receipt_path,
    )
    return rendered, stopped


def status_only_text() -> str:
    lines = [
        "Engel Daily Cycle Runner V1",
        "",
        "Status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
        "CLI:",
        "- python engel_daily_cycle_runner.py --dry-run",
        "- python engel_daily_cycle_runner.py --run --password-prompt",
        "- python engel_daily_cycle_runner.py --status-only",
        "- python engel_daily_cycle_runner.py --run --jobs <project-local-json> --password-prompt",
        "",
        "Boundaries:",
        "- one-cycle boundary: max one daily cycle per command invocation",
        "- foreground command only",
        "- no startup autorun",
        "- no endless loop",
        "- no background worker",
        "- no provider/network/browser",
        "- no model runtime",
        "- no package refresh",
        "- no unapproved memory write",
        "- no high-risk self-fix",
        "- no unapproved source mutation",
        "- receipts are written only to reports\\daily_cycle_receipts\\",
    ]
    return "\n".join(lines).rstrip() + "\n"


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Daily Cycle Runner V1

        Usage:
          python engel_daily_cycle_runner.py --dry-run
          python engel_daily_cycle_runner.py --run --password-prompt
          python engel_daily_cycle_runner.py --status-only
          python engel_daily_cycle_runner.py --run --jobs <project-local-json> --password-prompt

        Boundary:
          Foreground only, one cycle per invocation, receipt-based, no startup autorun,
          no endless loop, no background worker, no provider/network/browser, no model
          runtime, no package refresh, no unapproved memory write, and no high-risk self-fix.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Run Engel's bounded daily local cycle.")
    parser.add_argument("--dry-run", action="store_true", help="Run one non-mutating daily cycle preview and write a dry-run receipt.")
    parser.add_argument("--run", action="store_true", help="Run one bounded foreground daily cycle and write a receipt.")
    parser.add_argument("--status-only", action="store_true", help="Show daily cycle runner status without running the cycle.")
    parser.add_argument("--jobs", metavar="PROJECT_LOCAL_JSON", help="Optional explicit bounded self-learning scheduler job list.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for the global password before protected run mode.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    args = build_parser().parse_args(argv)
    modes = [args.dry_run, args.run, args.status_only]
    if not any(modes):
        out.write(usage_text())
        return 0
    if sum(1 for enabled in modes if enabled) != 1:
        err.write("Choose exactly one of --dry-run, --run, or --status-only.\n")
        return 2
    if args.status_only:
        if args.jobs or args.password_prompt:
            err.write("--jobs and --password-prompt are only valid with --dry-run or --run.\n")
            return 2
        out.write(status_only_text())
        return 0

    mode = "run" if args.run else "dry-run"
    if args.run and not args.password_prompt:
        err.write("Protected action requires --password-prompt.\n")
        return 2
    try:
        if args.run:
            global_password_gate.prompt_and_require_action("run_daily_cycle")
        rendered, stopped = run_daily_cycle(mode, args.jobs, write_receipt=True)
        out.write(rendered)
        return 1 if stopped else 0
    except (DailyCycleRunnerError, self_learning_scheduler.BoundedSelfLearningSchedulerError) as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1
    except global_password_gate.PasswordGateError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
