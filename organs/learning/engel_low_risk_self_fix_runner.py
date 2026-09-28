from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import textwrap

import engel_global_password_gate as global_password_gate


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
CONTRACT_PATH = PROJECT_ROOT / "memory" / "ENGEL_LOW_RISK_SELF_FIX_RUNNER_CONTRACT_V1.json"
RECEIPT_DIR = PROJECT_ROOT / "reports" / "self_fix_receipts"
RUNNER_VERSION = "ENGEL_LOW_RISK_SELF_FIX_RUNNER_V1"

RUNNER_STATUS = [
    "LOW_RISK_SELF_FIX_RUNNER",
    "PREAPPROVED_LOW_RISK_FIXES_ONLY",
    "VERIFY_BEFORE_COMMIT",
    "RECEIPT_REQUIRED",
    "STOP_ON_HIGH_RISK",
    "STOP_ON_UNCLEAR_RISK",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PACKAGE_REFRESH",
    "NO_ROUTE_STARTUP_MUTATION",
    "NO_BACKGROUND_WORKER",
]

RECEIPT_LABELS = [
    "LOW_RISK_SELF_FIX_RUNNER",
    "PREAPPROVED_LOW_RISK_FIXES_ONLY",
    "VERIFY_BEFORE_COMMIT",
    "RECEIPT_REQUIRED",
    "NOT_TRUSTED_MEMORY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_NETWORK_BROWSER",
    "NO_BACKGROUND_WORKER",
]

IMPLEMENTED_LOW_RISK_FIX_CLASSES = [
    "stale_pid_cleanup",
    "report_hash_refresh",
    "generated_report_metadata_update",
    "generated_artifact_cleanup",
]

FUTURE_LOW_RISK_FIX_CLASSES = [
    "docs_drift_alignment",
    "core_continuity_missing_verified_node",
    "verifier_expectation_update_for_existing_committed_contract",
    "read_only_status_surface_reference_update",
    "codex_bridge_report_reference_update",
    "known_safe_path_label_or_status_correction",
]

HIGH_RISK_STOP_CLASSES = [
    "provider_api_network_browser_activation",
    "model_loading_or_inference",
    "trusted_memory_write",
    "route_startup_source_behavior_mutation",
    "background_worker_or_autonomous_loop",
    "package_refresh_or_live_exe_promotion",
    "file_import_copy_move_sync",
    "queue_runtime_or_worker_activation",
    "security_authority_hierarchy_change",
    "deletion_of_unknown_or_unclassified_files",
    "arbitrary_source_refactor",
    "external_drive_access",
    "package_manager_change",
]

RECEIPT_FIELDS = [
    "self_fix_run_id",
    "issue_detected",
    "classification",
    "allowed_low_risk_class",
    "mode",
    "files_changed",
    "patch_summary",
    "verification_commands",
    "verification_result",
    "safety_scan_result",
    "commit_hash",
    "rollback_notes",
    "stopped",
    "stop_reason",
    "human_intervention_required",
    "no_trusted_memory_write",
    "no_provider_network_browser",
    "no_background_worker",
]

KNOWN_STALE_PID_FILES = [
    PROJECT_ROOT / "memory" / "engel_research_office.pid",
    PROJECT_ROOT / "memory" / "overnight_research_loop.pid",
]

SAFE_GENERATED_ARTIFACT_PREFIXES = [
    "self_fix_runner_generated_artifact_",
    "low_risk_self_fix_runner_smoke_",
]

SAFE_GENERATED_ARTIFACT_SUFFIXES = [".tmp", ".md", ".json"]

POST_APPLY_VERIFICATION_COMMANDS = [
    ["python", "tools\\verify_untrusted_content_guard.py"],
    ["python", "tools\\verify_prompt_injection_guard.py"],
    ["python", "tools\\verify_authority_hierarchy.py"],
    ["python", "tools\\verify_living_systems_documentation_drift.py"],
    ["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts\\codex_verify.ps1"],
]


class LowRiskSelfFixRunnerError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def project_relative(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("/", "\\")


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def validate_contract_alignment() -> None:
    contract = load_contract()
    allowed = set(contract.get("allowed_low_risk_fix_classes", []))
    high_risk = set(contract.get("high_risk_stop_classes", []))
    missing_allowed = set(IMPLEMENTED_LOW_RISK_FIX_CLASSES + FUTURE_LOW_RISK_FIX_CLASSES) - allowed
    missing_high_risk = set(HIGH_RISK_STOP_CLASSES) - high_risk
    if missing_allowed:
        raise LowRiskSelfFixRunnerError("Runner class list drifted from contract: " + ", ".join(sorted(missing_allowed)))
    if missing_high_risk:
        raise LowRiskSelfFixRunnerError("Runner high-risk stop list drifted from contract: " + ", ".join(sorted(missing_high_risk)))


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_run_id(issue: str, mode: str, timestamp: str) -> str:
    seed = f"{RUNNER_VERSION}|{issue}|{mode}|{timestamp}".encode("utf-8")
    return "low_risk_self_fix_run_" + hashlib.sha256(seed).hexdigest()[:16]


def command_label(command: list[str]) -> str:
    return " ".join(command)


def verification_command_text() -> str:
    return "\n".join(f"- {command_label(command)}" for command in POST_APPLY_VERIFICATION_COMMANDS)


def build_receipt(
    issue: str,
    mode: str,
    classification: str,
    allowed_low_risk_class: str,
    files_changed: list[str],
    patch_summary: str,
    verification_result: str,
    safety_scan_result: str,
    stopped: bool,
    stop_reason: str,
    human_intervention_required: bool,
    rollback_notes: str,
) -> dict[str, object]:
    timestamp = now_utc()
    return {
        "self_fix_run_id": make_run_id(issue, mode, timestamp),
        "issue_detected": issue,
        "classification": classification,
        "allowed_low_risk_class": allowed_low_risk_class,
        "mode": mode,
        "files_changed": files_changed,
        "patch_summary": patch_summary,
        "verification_commands": verification_command_text(),
        "verification_result": verification_result,
        "safety_scan_result": safety_scan_result,
        "commit_hash": "not_committed_by_runner_v1",
        "rollback_notes": rollback_notes,
        "stopped": stopped,
        "stop_reason": stop_reason,
        "human_intervention_required": human_intervention_required,
        "no_trusted_memory_write": True,
        "no_provider_network_browser": True,
        "no_background_worker": True,
    }


def render_receipt(receipt: dict[str, object]) -> str:
    lines = [
        "# Engel Low-Risk Self-Fix Runner Receipt V1",
        "",
        "Labels:",
        *[f"- {label}" for label in RECEIPT_LABELS],
        "",
        "Runner status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
        "Boundary:",
        "- Only implemented V1 low-risk classes may run.",
        "- High-risk classes stop.",
        "- Unclear-risk classes stop.",
        "- Stale PID cleanup never kills a process.",
        "- Report/hash/metadata/artifact classes stop unless a known safe mismatch is present.",
        "- No trusted memory write.",
        "- No provider, network, or browser call.",
        "- No model runtime.",
        "- No package refresh.",
        "- No route/startup mutation.",
        "- No background worker.",
        "- Runner V1 does not commit automatically.",
        "",
    ]
    for field in RECEIPT_FIELDS:
        value = receipt.get(field, "")
        if isinstance(value, list):
            rendered_value = "\n".join(f"- {item}" for item in value) if value else "none"
        else:
            rendered_value = str(value)
        lines.extend([f"## {field}", rendered_value, ""])
    return "\n".join(lines).rstrip() + "\n"


def safe_receipt_filename(receipt: dict[str, object]) -> str:
    run_id = str(receipt["self_fix_run_id"])
    issue = str(receipt["issue_detected"]).replace("-", "_").lower()
    safe_issue = "".join(character if character.isalnum() or character == "_" else "_" for character in issue).strip("_")
    return f"{run_id}_{safe_issue}.md"


def write_receipt(receipt: dict[str, object]) -> Path:
    output_dir = RECEIPT_DIR.resolve()
    if not is_relative_to(output_dir, PROJECT_ROOT.resolve()):
        raise LowRiskSelfFixRunnerError("Receipt directory escaped the project root.")
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / safe_receipt_filename(receipt)).resolve()
    if not is_relative_to(output_path, output_dir):
        raise LowRiskSelfFixRunnerError("Receipt output escaped reports\\self_fix_receipts.")
    output_path.write_text(render_receipt(receipt), encoding="utf-8")
    return output_path


def classify_issue(issue: str) -> tuple[str, str, str]:
    if issue in HIGH_RISK_STOP_CLASSES:
        return "HIGH_RISK_STOP", "", "STOP_ON_HIGH_RISK: issue class is forbidden by contract"
    if issue in FUTURE_LOW_RISK_FIX_CLASSES:
        return "FUTURE_LOW_RISK_NOT_IMPLEMENTED", "", "STOP_ON_UNCLEAR_RISK: class is contract-listed but not implemented in V1"
    if issue not in IMPLEMENTED_LOW_RISK_FIX_CLASSES:
        return "UNKNOWN_STOP", "", "STOP_ON_UNCLEAR_RISK: issue class is not implemented or preapproved"
    return "PREAPPROVED_LOW_RISK", issue, ""


def read_pid_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text.isdecimal():
        raise LowRiskSelfFixRunnerError(f"PID file is not a plain decimal PID: {project_relative(path)}")
    return int(text)


def pid_is_active_windows(pid: int) -> bool | None:
    process_query_limited_information = 0x1000
    still_active = 259
    error_invalid_parameter = 87
    error_access_denied = 5
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == error_invalid_parameter:
            return False
        if error == error_access_denied:
            return True
        return None
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return None
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def pid_is_active(pid: int) -> bool | None:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return pid_is_active_windows(pid)
    proc_path = Path("/proc") / str(pid)
    if proc_path.exists():
        return True
    if Path("/proc").exists():
        return False
    return None


def existing_known_pid_files() -> list[Path]:
    return [path for path in KNOWN_STALE_PID_FILES if path.exists() and path.is_file()]


def handle_stale_pid_cleanup(mode: str) -> dict[str, object]:
    candidates = existing_known_pid_files()
    if not candidates:
        return build_receipt(
            issue="stale_pid_cleanup",
            mode=mode,
            classification="PREAPPROVED_LOW_RISK",
            allowed_low_risk_class="stale_pid_cleanup",
            files_changed=[],
            patch_summary="No known Engel PID file exists. Dry-run is safe; apply would stop without mutation.",
            verification_result="not_run_no_mutation",
            safety_scan_result="not_run_no_mutation",
            stopped=mode == "apply",
            stop_reason="No known stale PID file found." if mode == "apply" else "not_stopped_dry_run_only",
            human_intervention_required=mode == "apply",
            rollback_notes="No rollback needed; no file was changed.",
        )

    observations: list[str] = []
    stale_files: list[Path] = []
    for path in candidates:
        pid = read_pid_file(path)
        active = pid_is_active(pid)
        relative = project_relative(path)
        if active is True:
            observations.append(f"{relative}: PID {pid} is active; stop")
        elif active is False:
            observations.append(f"{relative}: PID {pid} is inactive; stale candidate")
            stale_files.append(path)
        else:
            observations.append(f"{relative}: PID {pid} activity unclear; stop")

    if mode == "dry-run":
        return build_receipt(
            issue="stale_pid_cleanup",
            mode=mode,
            classification="PREAPPROVED_LOW_RISK",
            allowed_low_risk_class="stale_pid_cleanup",
            files_changed=[],
            patch_summary="Dry-run only. " + " | ".join(observations),
            verification_result="not_run_dry_run",
            safety_scan_result="not_run_dry_run",
            stopped=False,
            stop_reason="not_stopped_dry_run_only",
            human_intervention_required=False,
            rollback_notes="No rollback needed; dry-run made no changes.",
        )

    if not stale_files:
        return build_receipt(
            issue="stale_pid_cleanup",
            mode=mode,
            classification="PREAPPROVED_LOW_RISK",
            allowed_low_risk_class="stale_pid_cleanup",
            files_changed=[],
            patch_summary="Apply stopped. " + " | ".join(observations),
            verification_result="not_run_no_mutation",
            safety_scan_result="not_run_no_mutation",
            stopped=True,
            stop_reason="No PID file could be proven stale.",
            human_intervention_required=True,
            rollback_notes="No rollback needed; no file was changed.",
        )

    changed: list[str] = []
    for path in stale_files:
        path.unlink()
        changed.append(project_relative(path))

    verification_result = run_post_apply_verification()
    verification_failed = "FAIL" in verification_result
    return build_receipt(
        issue="stale_pid_cleanup",
        mode=mode,
        classification="PREAPPROVED_LOW_RISK",
        allowed_low_risk_class="stale_pid_cleanup",
        files_changed=changed,
        patch_summary="Deleted known stale PID file(s) only after confirming PID was inactive. No process was killed.",
        verification_result=verification_result,
        safety_scan_result="focused_scan_manual_review_required_after_apply",
        stopped=verification_failed,
        stop_reason="Verification failed after stale PID cleanup." if verification_failed else "not_stopped_verification_passed",
        human_intervention_required=verification_failed,
        rollback_notes="Restore the deleted PID file only if it represented an active process; runner never killed a process.",
    )


def handle_report_hash_refresh(mode: str) -> dict[str, object]:
    return build_receipt(
        issue="report_hash_refresh",
        mode=mode,
        classification="PREAPPROVED_LOW_RISK",
        allowed_low_risk_class="report_hash_refresh",
        files_changed=[],
        patch_summary="No safe report hash/self-reference mismatch was provided or detected by an explicit known pattern. V1 stops instead of guessing.",
        verification_result="not_run_no_mutation",
        safety_scan_result="not_run_no_mutation",
        stopped=mode == "apply",
        stop_reason="Pattern unclear; report_hash_refresh requires a precise known safe mismatch." if mode == "apply" else "not_stopped_dry_run_only",
        human_intervention_required=mode == "apply",
        rollback_notes="No rollback needed; no file was changed.",
    )


def handle_generated_report_metadata_update(mode: str) -> dict[str, object]:
    return build_receipt(
        issue="generated_report_metadata_update",
        mode=mode,
        classification="PREAPPROVED_LOW_RISK",
        allowed_low_risk_class="generated_report_metadata_update",
        files_changed=[],
        patch_summary="No known generated report metadata mismatch in reports\\codex_bridge was explicitly identified. V1 stops instead of altering report content.",
        verification_result="not_run_no_mutation",
        safety_scan_result="not_run_no_mutation",
        stopped=mode == "apply",
        stop_reason="No known safe metadata mismatch supplied." if mode == "apply" else "not_stopped_dry_run_only",
        human_intervention_required=mode == "apply",
        rollback_notes="No rollback needed; no file was changed.",
    )


def safe_generated_artifact_candidates() -> list[Path]:
    candidates: list[Path] = []
    if not RECEIPT_DIR.exists():
        return candidates
    for path in RECEIPT_DIR.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name == ".gitkeep":
            continue
        if any(name.startswith(prefix) for prefix in SAFE_GENERATED_ARTIFACT_PREFIXES) and any(
            name.endswith(suffix) for suffix in SAFE_GENERATED_ARTIFACT_SUFFIXES
        ):
            candidates.append(path)
    return candidates


def handle_generated_artifact_cleanup(mode: str) -> dict[str, object]:
    candidates = safe_generated_artifact_candidates()
    if mode == "dry-run":
        return build_receipt(
            issue="generated_artifact_cleanup",
            mode=mode,
            classification="PREAPPROVED_LOW_RISK",
            allowed_low_risk_class="generated_artifact_cleanup",
            files_changed=[],
            patch_summary=(
                "Dry-run only. Known safe generated artifact candidates: "
                + (", ".join(project_relative(path) for path in candidates) if candidates else "none")
            ),
            verification_result="not_run_dry_run",
            safety_scan_result="not_run_dry_run",
            stopped=False,
            stop_reason="not_stopped_dry_run_only",
            human_intervention_required=False,
            rollback_notes="No rollback needed; dry-run made no changes.",
        )
    if not candidates:
        return build_receipt(
            issue="generated_artifact_cleanup",
            mode=mode,
            classification="PREAPPROVED_LOW_RISK",
            allowed_low_risk_class="generated_artifact_cleanup",
            files_changed=[],
            patch_summary="No clearly generated temporary artifact matched the V1 safe cleanup patterns.",
            verification_result="not_run_no_mutation",
            safety_scan_result="not_run_no_mutation",
            stopped=True,
            stop_reason="No known safe generated artifact found; unknown files stop.",
            human_intervention_required=True,
            rollback_notes="No rollback needed; no file was changed.",
        )

    changed: list[str] = []
    for path in candidates:
        path.unlink()
        changed.append(project_relative(path))

    verification_result = run_post_apply_verification()
    verification_failed = "FAIL" in verification_result
    return build_receipt(
        issue="generated_artifact_cleanup",
        mode=mode,
        classification="PREAPPROVED_LOW_RISK",
        allowed_low_risk_class="generated_artifact_cleanup",
        files_changed=changed,
        patch_summary="Removed only known generated temporary artifacts from the bounded self-fix receipt folder.",
        verification_result=verification_result,
        safety_scan_result="focused_scan_manual_review_required_after_apply",
        stopped=verification_failed,
        stop_reason="Verification failed after generated artifact cleanup." if verification_failed else "not_stopped_verification_passed",
        human_intervention_required=verification_failed,
        rollback_notes="Restore removed generated artifacts only if a human determines they were needed.",
    )


def run_post_apply_verification() -> str:
    results: list[str] = []
    for command in POST_APPLY_VERIFICATION_COMMANDS:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        status = "PASS" if completed.returncode == 0 else "FAIL"
        results.append(f"{status}: {command_label(command)}")
        if completed.returncode != 0:
            tail = (completed.stdout + "\n" + completed.stderr).strip().splitlines()[-8:]
            if tail:
                results.extend("  " + line for line in tail)
            break
    return "\n".join(results)


def run_issue(issue: str, mode: str) -> dict[str, object]:
    validate_contract_alignment()
    classification, allowed, stop_reason = classify_issue(issue)
    if classification != "PREAPPROVED_LOW_RISK":
        return build_receipt(
            issue=issue,
            mode=mode,
            classification=classification,
            allowed_low_risk_class=allowed,
            files_changed=[],
            patch_summary="Stopped before any file mutation.",
            verification_result="not_run_stopped_before_mutation",
            safety_scan_result="not_run_stopped_before_mutation",
            stopped=True,
            stop_reason=stop_reason,
            human_intervention_required=True,
            rollback_notes="No rollback needed; no file was changed.",
        )
    if issue == "stale_pid_cleanup":
        return handle_stale_pid_cleanup(mode)
    if issue == "report_hash_refresh":
        return handle_report_hash_refresh(mode)
    if issue == "generated_report_metadata_update":
        return handle_generated_report_metadata_update(mode)
    if issue == "generated_artifact_cleanup":
        return handle_generated_artifact_cleanup(mode)
    raise LowRiskSelfFixRunnerError("Unhandled implemented low-risk class: " + issue)


def status_text() -> str:
    lines = [
        "Engel Low-Risk Self-Fix Runner V1",
        "",
        "Status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
        "Implemented V1 fix classes:",
        *[f"- {name}" for name in IMPLEMENTED_LOW_RISK_FIX_CLASSES],
        "",
        "Future low-risk classes listed by contract but not implemented in V1:",
        *[f"- {name}" for name in FUTURE_LOW_RISK_FIX_CLASSES],
        "",
        "High-risk stop classes:",
        *[f"- {name}" for name in HIGH_RISK_STOP_CLASSES],
        "",
        "CLI:",
        "- python engel_low_risk_self_fix_runner.py --status",
        "- python engel_low_risk_self_fix_runner.py --dry-run --issue stale_pid_cleanup",
        "- python engel_low_risk_self_fix_runner.py --apply --issue stale_pid_cleanup --password-prompt",
        "- python engel_low_risk_self_fix_runner.py --dry-run --issue report_hash_refresh",
        "- python engel_low_risk_self_fix_runner.py --dry-run --issue generated_report_metadata_update",
        "- python engel_low_risk_self_fix_runner.py --dry-run --issue generated_artifact_cleanup",
        "",
        "Boundaries:",
        "- one explicit issue per run",
        "- stale_pid_cleanup may delete only known stale Engel PID files after confirming the PID is inactive",
        "- stale_pid_cleanup must not kill processes",
        "- report_hash_refresh stops when the safe hash/self-reference pattern is unclear",
        "- generated_report_metadata_update stays bounded to known report metadata mismatches in reports\\codex_bridge",
        "- generated_artifact_cleanup removes only clearly generated temporary artifacts matching known safe patterns",
        "- no provider/network/browser/model/trusted-memory/package-refresh/route-startup/background-worker behavior",
        "- runner V1 writes receipts to reports\\self_fix_receipts and does not commit automatically",
    ]
    return "\n".join(lines).rstrip() + "\n"


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Low-Risk Self-Fix Runner V1

        Usage:
          python engel_low_risk_self_fix_runner.py --status
          python engel_low_risk_self_fix_runner.py --dry-run --issue stale_pid_cleanup
          python engel_low_risk_self_fix_runner.py --apply --issue stale_pid_cleanup --password-prompt
          python engel_low_risk_self_fix_runner.py --dry-run --issue report_hash_refresh
          python engel_low_risk_self_fix_runner.py --dry-run --issue generated_report_metadata_update
          python engel_low_risk_self_fix_runner.py --dry-run --issue generated_artifact_cleanup

        Apply mode is conservative. If context is missing or risk is unclear, the runner stops and writes a receipt.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Run bounded Engel low-risk self-fix V1 tasks.")
    parser.add_argument("--status", action="store_true", help="Show runner status and boundaries.")
    parser.add_argument("--dry-run", action="store_true", help="Show the planned receipt without mutating files.")
    parser.add_argument("--apply", action="store_true", help="Apply a bounded V1 low-risk fix when safe, then write a receipt.")
    parser.add_argument("--issue", metavar="ISSUE_CLASS", help="One explicit issue class.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for the global password before protected apply mode.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not any([args.status, args.dry_run, args.apply, args.issue]):
        out.write(usage_text())
        return 0
    if args.status:
        if any([args.dry_run, args.apply, args.issue]):
            err.write("Use --status by itself.\n")
            return 2
        out.write(status_text())
        return 0
    if args.dry_run and args.apply:
        err.write("Choose either --dry-run or --apply, not both.\n")
        return 2
    if not args.dry_run and not args.apply:
        err.write("Choose --dry-run or --apply.\n")
        return 2
    if not args.issue:
        err.write("Explicit --issue is required.\n")
        return 2

    mode = "apply" if args.apply else "dry-run"
    if args.apply and not args.password_prompt:
        err.write("Protected action requires --password-prompt.\n")
        return 2
    try:
        if args.apply:
            action_id = "clear_stale_pid_file" if args.issue == "stale_pid_cleanup" else "run_low_risk_self_fix_apply"
            global_password_gate.prompt_and_require_action(action_id)
        receipt = run_issue(args.issue, mode)
        rendered = render_receipt(receipt)
        if args.apply:
            path = write_receipt(receipt)
            out.write(rendered)
            out.write(f"\nWROTE_SELF_FIX_RECEIPT: {project_relative(path)}\n")
        else:
            out.write(rendered)
        return 1 if receipt["stopped"] else 0
    except LowRiskSelfFixRunnerError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1
    except global_password_gate.PasswordGateError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
