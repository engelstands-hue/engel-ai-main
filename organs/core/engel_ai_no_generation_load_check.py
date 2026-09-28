from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MODEL_APPROVAL_MANIFEST = PROJECT_ROOT / "reports" / "ai_model_review_approvals" / "manifests" / "engel_ai_model_review_approval_manifest.json"
RUNTIME_PATH_CONFIG = PROJECT_ROOT / "reports" / "ai_runtime_path_config" / "manifests" / "engel_ai_local_runtime_path_config_manifest.json"
RUNTIME_DRY_RUN_MANIFEST = PROJECT_ROOT / "reports" / "ai_runtime_dry_runs" / "configs" / "engel_ai_runtime_dry_run_manifest.json"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_no_generation_load_checks"
RECEIPT_DIR = REPORT_ROOT / "receipts"
LOG_DIR = REPORT_ROOT / "logs"
EXAMPLES_DIR = REPORT_ROOT / "examples"
DIAGNOSTIC_DIR = REPORT_ROOT / "diagnostics"

APPROVAL_TOKEN = "APPROVE_NO_GENERATION_LOAD_CHECK"
DEFAULT_MODEL_KEY = "tiny_seed"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_V2_TIMEOUT_SECONDS = 180
DEFAULT_V3_TIMEOUT_SECONDS = 180
DEFAULT_V4_TIMEOUT_SECONDS = 180
HELP_TIMEOUT_SECONDS = 20
MINIMAL_PROBE_TIMEOUT_SECONDS = 15
TERMINATE_GRACE_SECONDS = 5
KILL_GRACE_SECONDS = 5
DEFAULT_CONTEXT_SIZE = 512
DEFAULT_THREADS = 4
N_PREDICT = 0
MAX_READ_CHARS = 200_000
MAX_LOG_CHARS = 20_000
MAX_HELP_CHARS = 80_000

FINAL_DECISION_PASS = "NO-GENERATION LOAD CHECK RECORDED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_FAIL = "NO-GENERATION LOAD CHECK FAILED OR INTERRUPTED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V2_PASS = "NO-GENERATION LOAD CHECK V2 RECORDED \u2014 PROCESS EXITED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V2_FAIL = "NO-GENERATION LOAD CHECK V2 FAILED OR BLOCKED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V2_INTERRUPTED = "NO-GENERATION LOAD CHECK V2 FAILED OR INTERRUPTED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V3_PASS = "NO-GENERATION LOAD CHECK V3 RECORDED \u2014 PROCESS EXITED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V3_FAIL = "NO-GENERATION LOAD CHECK V3 FAILED OR BLOCKED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V3_INTERRUPTED = "NO-GENERATION LOAD CHECK V3 FAILED OR INTERRUPTED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V4_PASS = "NO-GENERATION LOAD CHECK V4 RECORDED \u2014 PROCESS EXITED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V4_BLOCKED = "NO-GENERATION LOAD CHECK V4 BLOCKED \u2014 NO CLEAN EXIT MODE IDENTIFIED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V4_FAIL = "NO-GENERATION LOAD CHECK V4 FAILED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
FINAL_DECISION_V4_INTERRUPTED = "NO-GENERATION LOAD CHECK V4 FAILED OR INTERRUPTED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"

V4_RUNTIME_BINARY_NAMES = [
    "llama-cli.exe",
    "llama-completion.exe",
    "llama-bench.exe",
    "llama-server.exe",
]

MODEL_KEY_TO_TIER = {
    "tiny_seed": "Tiny Seed Mode",
    "daily_local": "Daily Local Mode",
    "research_worker": "Research Worker Mode",
    "alternative_research_worker": "Alternative Research Worker",
}

MODEL_KEY_TO_NAME = {
    "tiny_seed": "Qwen2.5-0.5B-Instruct GGUF",
    "daily_local": "Qwen2.5-3B-Instruct GGUF",
    "research_worker": "Qwen2.5-7B-Instruct GGUF",
    "alternative_research_worker": "Mistral-7B-Instruct v0.3 GGUF",
}


class LoadCheckError(ValueError):
    pass


@dataclass
class ExecutionResult:
    command_executed: bool
    runtime_process_started: bool
    runtime_process_exited: bool
    timeout_seconds: int
    exit_code: int | None
    stdout_text: str
    stderr_text: str
    stdout_truncated: bool
    stderr_truncated: bool
    orphan_process_detected: bool
    timed_out: bool
    interrupted: bool = False
    runtime_process_id: int | None = None
    cleanup_action: str | None = None
    error: str | None = None


@dataclass
class HelpCheckResult:
    help_checked: bool
    help_check_command_executed: bool
    help_check_process_started: bool
    help_check_exit_code: int | None
    help_check_timed_out: bool
    help_check_interrupted: bool
    help_text: str
    help_text_truncated: bool
    error: str | None = None


@dataclass
class CommandPlan:
    args: list[str]
    command_style: str
    selected_prompt_flag: str | None
    selected_n_predict_flag: str
    non_interactive_mode: bool
    stdin_mode: str
    stdin_text: str | None
    help_checked: bool
    help_check_exit_code: int | None
    help_check_timed_out: bool
    help_check_interrupted: bool
    help_check_error: str | None
    supported_non_interactive_flags: list[str]
    execution_binary_path: str | None = None
    registered_runtime_binary_path: str | None = None


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_slug(value: str, max_length: int = 96) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isascii() and char.isalnum():
            chars.append(char)
        elif char in {"-", "_", "."}:
            chars.append(char)
        else:
            chars.append("_")
    slug = "_".join(part for part in "".join(chars).strip("._-").split("_") if part)
    return (slug or "no_generation_load_check")[:max_length]


def safe_stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, RECEIPT_DIR, LOG_DIR, EXAMPLES_DIR, DIAGNOSTIC_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def write_lf_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def approval_entries() -> list[dict[str, Any]]:
    entries = read_json(MODEL_APPROVAL_MANIFEST).get("entries")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def approval_entry_for_key(model_key: str) -> dict[str, Any] | None:
    tier = MODEL_KEY_TO_TIER.get(model_key)
    if not tier:
        return None
    for entry in approval_entries():
        if entry.get("model_tier") == tier:
            return entry
    return None


def runtime_path_config() -> dict[str, Any]:
    return read_json(RUNTIME_PATH_CONFIG)


def runtime_dry_run_entries() -> dict[str, dict[str, Any]]:
    entries = read_json(RUNTIME_DRY_RUN_MANIFEST).get("entries")
    if not isinstance(entries, list):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("model_key"), str):
            rows[entry["model_key"]] = entry
    return rows


def runtime_status() -> dict[str, Any]:
    config = runtime_path_config()
    runtime_path = config.get("runtime_binary_path")
    binary_path = Path(runtime_path) if isinstance(runtime_path, str) and runtime_path.strip() else None
    present = bool(binary_path and binary_path.exists() and binary_path.is_file())
    return {
        "runtime_backend": config.get("runtime_backend", "not_configured") if config else "not_configured",
        "runtime_binary_path": str(binary_path.resolve(strict=False)) if binary_path else None,
        "runtime_binary_present": present,
        "runtime_path_approved": bool(config.get("runtime_path_approved") is True),
        "runtime_execution_enabled": False,
        "model_load_enabled": False,
        "inference_enabled": False,
        "auto_start_enabled": False,
        "provider_api_enabled": False,
    }


def validate_model(model_key: str) -> dict[str, Any]:
    if model_key not in MODEL_KEY_TO_TIER:
        return {"valid": False, "reason": "unknown_model_key", "model_key": model_key}
    entry = approval_entry_for_key(model_key)
    if not entry:
        return {"valid": False, "reason": "model_approval_missing", "model_key": model_key}
    if entry.get("approved_for_runtime_dry_run") is not True:
        return {"valid": False, "reason": "not_approved_for_runtime_dry_run", "model_key": model_key}
    if entry.get("runtime_dry_run_eligible") is not True:
        return {"valid": False, "reason": "not_runtime_dry_run_eligible", "model_key": model_key}
    if entry.get("inference_enabled") is True or entry.get("auto_load_enabled") is True:
        return {"valid": False, "reason": "unsafe_model_approval_flags", "model_key": model_key}
    model_path = Path(str(entry.get("model_file_path", "")))
    if not model_path.exists() or not model_path.is_file():
        return {"valid": False, "reason": "model_file_missing", "model_key": model_key, "model_file_path": str(model_path)}
    if model_path.suffix.lower() != ".gguf":
        return {"valid": False, "reason": "non_gguf_model_rejected", "model_key": model_key, "model_file_path": str(model_path)}
    runtime = runtime_status()
    if runtime["runtime_path_approved"] is not True:
        return {"valid": False, "reason": "runtime_path_not_approved", "model_key": model_key}
    if runtime["runtime_binary_present"] is not True:
        return {"valid": False, "reason": "runtime_binary_missing", "model_key": model_key, "runtime_binary_path": runtime["runtime_binary_path"]}
    dry_run = runtime_dry_run_entries().get(model_key)
    if not dry_run or dry_run.get("runtime_dry_run_ready") is not True:
        return {"valid": False, "reason": "runtime_dry_run_not_ready", "model_key": model_key}
    return {
        "valid": True,
        "reason": "valid_no_generation_load_check_target",
        "model_key": model_key,
        "model_tier": str(entry.get("model_tier") or MODEL_KEY_TO_TIER[model_key]),
        "model_name": str(entry.get("model_name") or MODEL_KEY_TO_NAME[model_key]),
        "model_file_path": str(model_path.resolve(strict=False)),
        "approval_entry": entry,
        "runtime": runtime,
        "runtime_dry_run": dry_run,
    }


def build_no_generation_command(runtime_binary_path: str, model_file_path: str) -> list[str]:
    return build_no_generation_command_plan(runtime_binary_path, model_file_path, None).args


def bounded_help_text(value: str) -> tuple[str, bool]:
    if len(value) <= MAX_HELP_CHARS:
        return value, False
    return value[:MAX_HELP_CHARS] + "\n[TRUNCATED]\n", True


def help_supports(help_text: str, flag: str) -> bool:
    return flag in help_text


def run_cli_help_check(runtime_binary_path: str, *, timeout_seconds: int = HELP_TIMEOUT_SECONDS) -> HelpCheckResult:
    return run_help_check_for_binary(runtime_binary_path, timeout_seconds=timeout_seconds)


def run_help_check_for_binary(binary_path: str, *, timeout_seconds: int = HELP_TIMEOUT_SECONDS) -> HelpCheckResult:
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [binary_path, "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            cwd=str(PROJECT_ROOT),
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            timed_out = False
            interrupted = False
            error = None
        except subprocess.TimeoutExpired:
            timed_out = True
            interrupted = False
            stdout, stderr, _exited, _orphan, _exit_code, _cleanup, cleanup_error = stop_started_process(process)
            error = append_error("help_timeout_expired", cleanup_error)
        except KeyboardInterrupt:
            timed_out = False
            interrupted = True
            stdout, stderr, _exited, _orphan, _exit_code, _cleanup, cleanup_error = stop_started_process(process)
            error = append_error("help_keyboard_interrupt", cleanup_error)
        text, truncated = bounded_help_text(normalize_process_text(stdout) + "\n" + normalize_process_text(stderr))
        return HelpCheckResult(
            help_checked=True,
            help_check_command_executed=True,
            help_check_process_started=True,
            help_check_exit_code=process.returncode,
            help_check_timed_out=timed_out,
            help_check_interrupted=interrupted,
            help_text=text,
            help_text_truncated=truncated,
            error=error,
        )
    except OSError as exc:
        return HelpCheckResult(
            help_checked=True,
            help_check_command_executed=process is not None,
            help_check_process_started=process is not None,
            help_check_exit_code=None,
            help_check_timed_out=False,
            help_check_interrupted=False,
            help_text="",
            help_text_truncated=False,
            error=str(exc),
        )


def run_diagnostic_command(args: list[str], *, timeout_seconds: int = HELP_TIMEOUT_SECONDS) -> ExecutionResult:
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            cwd=str(PROJECT_ROOT),
        )
        process_id = process.pid
        timed_out = False
        interrupted = False
        cleanup_action: str | None = None
        error: str | None = None
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            stdout, stderr, runtime_process_exited, orphan_process_detected, exit_code, cleanup_action, cleanup_error = stop_started_process(process)
            error = append_error("diagnostic_timeout_expired", cleanup_error)
        except KeyboardInterrupt:
            interrupted = True
            stdout, stderr, runtime_process_exited, orphan_process_detected, exit_code, cleanup_action, cleanup_error = stop_started_process(process)
            error = append_error("diagnostic_keyboard_interrupt", cleanup_error)
        else:
            stdout = normalize_process_text(stdout)
            stderr = normalize_process_text(stderr)
            runtime_process_exited = process.poll() is not None
            orphan_process_detected = not runtime_process_exited
            exit_code = process.returncode
        stdout_bounded, stdout_truncated = bounded_text(stdout)
        stderr_bounded, stderr_truncated = bounded_text(stderr)
        return ExecutionResult(
            command_executed=True,
            runtime_process_started=True,
            runtime_process_exited=runtime_process_exited,
            timeout_seconds=timeout_seconds,
            exit_code=exit_code,
            stdout_text=stdout_bounded,
            stderr_text=stderr_bounded,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            orphan_process_detected=orphan_process_detected,
            timed_out=timed_out,
            interrupted=interrupted,
            runtime_process_id=process_id,
            cleanup_action=cleanup_action,
            error=error,
        )
    except OSError as exc:
        return ExecutionResult(
            command_executed=False,
            runtime_process_started=False,
            runtime_process_exited=False,
            timeout_seconds=timeout_seconds,
            exit_code=None,
            stdout_text="",
            stderr_text=str(exc),
            stdout_truncated=False,
            stderr_truncated=False,
            orphan_process_detected=False,
            timed_out=False,
            interrupted=False,
            error=str(exc),
        )


def build_no_generation_command_plan(
    runtime_binary_path: str,
    model_file_path: str,
    help_result: HelpCheckResult | None,
) -> CommandPlan:
    help_text = help_result.help_text if help_result and help_result.help_checked and help_result.help_check_exit_code == 0 else ""
    selected_prompt_flag: str | None = "--prompt" if not help_text or help_supports(help_text, "--prompt") else None
    if selected_prompt_flag is None and help_supports(help_text, "-p,"):
        selected_prompt_flag = "-p"
    selected_n_predict_flag = "--n-predict" if not help_text or help_supports(help_text, "--n-predict") else "-n"
    stdin_mode = "devnull" if selected_prompt_flag else "bounded_prompt_input"
    stdin_text = None if selected_prompt_flag else "load check\n"

    args = [
        runtime_binary_path,
        "--model",
        model_file_path,
    ]
    if selected_prompt_flag:
        args.extend([selected_prompt_flag, "load check"])
    args.extend(
        [
            selected_n_predict_flag,
            str(N_PREDICT),
            "--ctx-size",
            str(DEFAULT_CONTEXT_SIZE),
            "--threads",
            str(DEFAULT_THREADS),
        ]
    )

    supported_non_interactive_flags: list[str] = []
    for flag in ["--no-conversation", "--no-display-prompt", "--log-disable", "--offline", "--simple-io"]:
        if (not help_text and flag != "--simple-io") or (help_text and help_supports(help_text, flag)):
            args.append(flag)
            supported_non_interactive_flags.append(flag)

    command_style = "prompt_argument_no_generation" if selected_prompt_flag else "bounded_stdin_no_generation"
    return CommandPlan(
        args=args,
        command_style=command_style,
        selected_prompt_flag=selected_prompt_flag,
        selected_n_predict_flag=selected_n_predict_flag,
        non_interactive_mode=True,
        stdin_mode=stdin_mode,
        stdin_text=stdin_text,
        help_checked=bool(help_result and help_result.help_checked),
        help_check_exit_code=help_result.help_check_exit_code if help_result else None,
        help_check_timed_out=bool(help_result and help_result.help_check_timed_out),
        help_check_interrupted=bool(help_result and help_result.help_check_interrupted),
        help_check_error=help_result.error if help_result else None,
        supported_non_interactive_flags=supported_non_interactive_flags,
        execution_binary_path=runtime_binary_path,
        registered_runtime_binary_path=runtime_binary_path,
    )


def completion_binary_for_runtime(runtime_binary_path: str) -> Path:
    return Path(runtime_binary_path).resolve(strict=False).parent / "llama-completion.exe"


def runtime_folder_for_runtime(runtime_binary_path: str) -> Path:
    return Path(runtime_binary_path).resolve(strict=False).parent


def direct_runtime_binary_inventory(runtime_binary_path: str) -> tuple[str, list[dict[str, Any]]]:
    runtime_folder = runtime_folder_for_runtime(runtime_binary_path)
    rows: list[dict[str, Any]] = []
    for binary_name in V4_RUNTIME_BINARY_NAMES:
        binary_path = runtime_folder / binary_name
        rows.append(
            {
                "binary": binary_name,
                "path": str(binary_path.resolve(strict=False)),
                "present": binary_path.exists() and binary_path.is_file(),
                "minimal_probe_enabled": binary_name in {"llama-cli.exe", "llama-completion.exe"},
                "server_mode_forbidden": binary_name == "llama-server.exe",
            }
        )
    return str(runtime_folder.resolve(strict=False)), rows


def execution_to_probe_payload(
    binary_path: str,
    args: list[str],
    execution: ExecutionResult,
    *,
    probe_kind: str,
    stdout_log_path: str,
    stderr_log_path: str,
) -> dict[str, Any]:
    return {
        "binary": Path(binary_path).name,
        "binary_path": str(Path(binary_path).resolve(strict=False)),
        "args": args,
        "command_args": [binary_path, *args],
        "probe_kind": probe_kind,
        "timeout_seconds": execution.timeout_seconds,
        "exit_code": execution.exit_code,
        "process_exited": execution.runtime_process_exited,
        "command_executed": execution.command_executed,
        "runtime_process_started": execution.runtime_process_started,
        "timed_out": execution.timed_out,
        "interrupted": execution.interrupted,
        "orphan_process_detected": execution.orphan_process_detected,
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "stdout_truncated": execution.stdout_truncated,
        "stderr_truncated": execution.stderr_truncated,
        "error": execution.error,
    }


def probe_exited_cleanly(probe: dict[str, Any]) -> bool:
    return (
        probe.get("command_executed") is True
        and probe.get("runtime_process_started") is True
        and probe.get("process_exited") is True
        and probe.get("exit_code") == 0
        and probe.get("timed_out") is False
        and probe.get("interrupted") is False
        and probe.get("orphan_process_detected") is False
        and not probe.get("error")
    )


def run_minimal_exit_probes(*, created_at: str | None = None) -> dict[str, Any]:
    ensure_folders()
    created = created_at or now_utc()
    stem = f"NO_GENERATION_LOAD_CHECK_V4_{safe_stamp(created)}_minimal_probe"
    runtime = runtime_status()
    runtime_path = runtime["runtime_binary_path"]
    if not runtime_path:
        payload: dict[str, Any] = {
            "no_generation_load_check_version": "4",
            "created_at": created,
            "created_by": "Engel AI No-Generation Load Check V4",
            "runtime_folder": None,
            "runtime_binary_path": None,
            "binaries_checked": [],
            "minimal_probe_results": [],
            "no_model_probe_results": [],
            "safe_candidate_identified": False,
            "selected_binary": None,
            "selected_command_style": None,
            "selected_flags": [],
            "blocked_reason": "runtime_binary_not_configured",
            "runtime_ready_for_inference": False,
            "chat_enabled": False,
            "server_enabled": False,
        }
        payload["diagnostic_json_path"] = write_diagnostic_json(stem, "summary", payload)
        return payload

    runtime_folder, binaries_checked = direct_runtime_binary_inventory(runtime_path)
    probe_results: list[dict[str, Any]] = []
    help_text_by_binary: dict[str, str] = {}

    for binary in binaries_checked:
        if not binary["minimal_probe_enabled"] or not binary["present"]:
            continue
        binary_path = str(binary["path"])
        for flag, probe_kind in [("--help", "help"), ("--version", "version")]:
            execution = run_diagnostic_command([binary_path, flag], timeout_seconds=MINIMAL_PROBE_TIMEOUT_SECONDS)
            log_name = f"{Path(binary_path).name}_{flag.strip('-')}"
            stdout_log_path = write_diagnostic_text(stem, f"{log_name}_stdout", execution.stdout_text)
            stderr_log_path = write_diagnostic_text(stem, f"{log_name}_stderr", execution.stderr_text)
            probe = execution_to_probe_payload(
                binary_path,
                [flag],
                execution,
                probe_kind=probe_kind,
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
            )
            probe_results.append(probe)
            if flag == "--help":
                help_text_by_binary[Path(binary_path).name] = execution.stdout_text + "\n" + execution.stderr_text

    no_model_probe_results: list[dict[str, Any]] = []
    for binary in binaries_checked:
        if not binary["minimal_probe_enabled"] or not binary["present"]:
            continue
        binary_name = str(binary["binary"])
        help_text = help_text_by_binary.get(binary_name, "")
        if "--list-devices" not in help_text:
            continue
        binary_path = str(binary["path"])
        execution = run_diagnostic_command([binary_path, "--list-devices"], timeout_seconds=MINIMAL_PROBE_TIMEOUT_SECONDS)
        log_name = f"{Path(binary_path).name}_list_devices"
        stdout_log_path = write_diagnostic_text(stem, f"{log_name}_stdout", execution.stdout_text)
        stderr_log_path = write_diagnostic_text(stem, f"{log_name}_stderr", execution.stderr_text)
        probe = execution_to_probe_payload(
            binary_path,
            ["--list-devices"],
            execution,
            probe_kind="no_model_list_devices",
            stdout_log_path=stdout_log_path,
            stderr_log_path=stderr_log_path,
        )
        probe_results.append(probe)
        no_model_probe_results.append(probe)

    help_version_probes = [probe for probe in probe_results if probe.get("probe_kind") in {"help", "version"}]
    expected_help_version_count = sum(2 for binary in binaries_checked if binary["minimal_probe_enabled"] and binary["present"])
    help_version_clean = (
        len(help_version_probes) == expected_help_version_count
        and expected_help_version_count >= 4
        and all(probe_exited_cleanly(probe) for probe in help_version_probes)
    )
    latest_v3 = latest_receipt_for_version("3")
    latest_v3_failed = bool(latest_v3 and latest_v3.get("no_generation_load_check_passed") is not True)
    if not help_version_clean:
        blocked_reason = "minimal help/version probes did not all exit cleanly"
    elif latest_v3_failed:
        blocked_reason = "latest V3 tiny_seed model-load candidate failed or was interrupted; V4 no-model probes do not identify a new model-load exit mode"
    else:
        blocked_reason = "minimal no-model probes exited, but no distinct no-generation model-load clean-exit mode was identified"

    payload = {
        "no_generation_load_check_version": "4",
        "created_at": created,
        "created_by": "Engel AI No-Generation Load Check V4",
        "runtime_folder": runtime_folder,
        "runtime_binary_path": runtime_path,
        "binaries_checked": binaries_checked,
        "minimal_probe_results": probe_results,
        "no_model_probe_results": no_model_probe_results,
        "minimal_help_version_probes_clean": help_version_clean,
        "latest_v3_receipt_path": latest_v3.get("receipt_path") if latest_v3 else None,
        "latest_v3_failed_or_interrupted": latest_v3_failed,
        "safe_candidate_identified": False,
        "selected_binary": None,
        "selected_command_style": None,
        "selected_flags": [],
        "blocked_reason": blocked_reason,
        "runtime_ready_for_inference": False,
        "chat_enabled": False,
        "server_enabled": False,
    }
    payload["diagnostic_json_path"] = write_diagnostic_json(stem, "summary", payload)
    return payload


def build_no_generation_command_plan_v4(
    validation: dict[str, Any],
    minimal_probe_payload: dict[str, Any],
) -> tuple[CommandPlan | None, str | None]:
    if minimal_probe_payload.get("safe_candidate_identified") is not True:
        return None, str(minimal_probe_payload.get("blocked_reason") or "no_clean_exit_mode_identified")
    return None, "no_clean_exit_mode_identified"


def build_no_generation_command_plan_v3(
    registered_runtime_binary_path: str,
    model_file_path: str,
    cli_help_result: HelpCheckResult | None,
    completion_help_result: HelpCheckResult | None,
) -> CommandPlan:
    completion_binary = completion_binary_for_runtime(registered_runtime_binary_path)
    completion_help_text = (
        completion_help_result.help_text
        if completion_help_result and completion_help_result.help_checked and completion_help_result.help_check_exit_code == 0
        else ""
    )
    selected_binary = str(completion_binary) if completion_binary.exists() and completion_help_text else registered_runtime_binary_path
    selected_help_text = completion_help_text or (cli_help_result.help_text if cli_help_result else "")
    selected_prompt_flag: str | None = "--prompt" if not selected_help_text or help_supports(selected_help_text, "--prompt") else None
    if selected_prompt_flag is None and help_supports(selected_help_text, "-p,"):
        selected_prompt_flag = "-p"
    selected_n_predict_flag = "--n-predict" if not selected_help_text or help_supports(selected_help_text, "--n-predict") else "-n"
    stdin_mode = "devnull" if selected_prompt_flag else "bounded_prompt_input"
    stdin_text = None if selected_prompt_flag else "load check\n"

    args = [
        selected_binary,
        "--model",
        model_file_path,
    ]
    if selected_prompt_flag:
        args.extend([selected_prompt_flag, "load check"])
    args.extend(
        [
            selected_n_predict_flag,
            str(N_PREDICT),
            "--ctx-size",
            str(DEFAULT_CONTEXT_SIZE),
            "--threads",
            str(DEFAULT_THREADS),
        ]
    )

    supported_non_interactive_flags: list[str] = []
    for flag in ["--no-display-prompt", "--simple-io", "--log-disable", "--offline", "--no-warmup"]:
        if not selected_help_text or help_supports(selected_help_text, flag):
            args.append(flag)
            supported_non_interactive_flags.append(flag)

    command_style = "llama_completion_prompt_no_generation" if Path(selected_binary).name.lower() == "llama-completion.exe" else "llama_cli_v3_prompt_no_generation"
    return CommandPlan(
        args=args,
        command_style=command_style,
        selected_prompt_flag=selected_prompt_flag,
        selected_n_predict_flag=selected_n_predict_flag,
        non_interactive_mode=True,
        stdin_mode=stdin_mode,
        stdin_text=stdin_text,
        help_checked=bool(cli_help_result and cli_help_result.help_checked and completion_help_result and completion_help_result.help_checked),
        help_check_exit_code=completion_help_result.help_check_exit_code if completion_help_result else None,
        help_check_timed_out=bool((cli_help_result and cli_help_result.help_check_timed_out) or (completion_help_result and completion_help_result.help_check_timed_out)),
        help_check_interrupted=bool((cli_help_result and cli_help_result.help_check_interrupted) or (completion_help_result and completion_help_result.help_check_interrupted)),
        help_check_error=append_error(cli_help_result.error if cli_help_result else None, completion_help_result.error if completion_help_result else None),
        supported_non_interactive_flags=supported_non_interactive_flags,
        execution_binary_path=selected_binary,
        registered_runtime_binary_path=registered_runtime_binary_path,
    )


def validate_command_args(args: list[str], *, stdin_mode: str = "devnull") -> None:
    if not args or not all(isinstance(item, str) and item for item in args):
        raise LoadCheckError("invalid_runtime_argument_list")
    executable_name = Path(args[0]).name.lower() if args else ""
    if executable_name in {"llama-server", "llama-server.exe"}:
        raise LoadCheckError("forbidden_runtime_argument")
    forbidden_tokens = {
        "--server",
        "--host",
        "--port",
        "--interactive",
        "--interactive-first",
        "-i",
        "--conversation",
        "-cnv",
        "--chat",
        "--infinite-prompt",
        "--multiline-input",
        "--model-url",
        "-mu",
        "--hf-repo",
        "-hf",
        "-hfr",
        "--docker-repo",
        "-dr",
    }
    for item in args[1:]:
        if item.lower() in forbidden_tokens:
            raise LoadCheckError("forbidden_runtime_argument")
    if ("--n-predict" not in args and "-n" not in args) or str(N_PREDICT) not in args:
        raise LoadCheckError("missing_no_generation_argument")
    if "--prompt" not in args and "-p" not in args and stdin_mode != "bounded_prompt_input":
        raise LoadCheckError("missing_inert_prompt_argument")
    prompt_index = args.index("--prompt") if "--prompt" in args else args.index("-p") if "-p" in args else -1
    if prompt_index != -1 and (prompt_index + 1 >= len(args) or args[prompt_index + 1] != "load check"):
        raise LoadCheckError("invalid_inert_prompt_argument")
    if stdin_mode == "bounded_prompt_input" and ("--prompt" in args or "-p" in args):
        raise LoadCheckError("conflicting_prompt_input_modes")


def bounded_text(value: str) -> tuple[str, bool]:
    if len(value) <= MAX_LOG_CHARS:
        return value, False
    return value[:MAX_LOG_CHARS] + "\n[TRUNCATED]\n", True


def normalize_process_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def timeout_output(exc: subprocess.TimeoutExpired) -> tuple[str, str]:
    stdout = getattr(exc, "stdout", None)
    if stdout is None:
        stdout = getattr(exc, "output", None)
    return normalize_process_text(stdout), normalize_process_text(getattr(exc, "stderr", None))


def append_error(existing: str | None, extra: str | None) -> str | None:
    if not extra:
        return existing
    if not existing:
        return extra
    return existing + "; " + extra


def stop_started_process(process: subprocess.Popen[str]) -> tuple[str, str, bool, bool, int | None, str, str | None]:
    stdout_text = ""
    stderr_text = ""
    cleanup_action = "none"
    cleanup_error: str | None = None

    if process.poll() is None:
        cleanup_action = "terminate"
        try:
            process.terminate()
        except OSError as exc:
            cleanup_error = append_error(cleanup_error, "terminate_failed: " + str(exc))

    try:
        stdout, stderr = process.communicate(timeout=TERMINATE_GRACE_SECONDS)
        stdout_text = normalize_process_text(stdout)
        stderr_text = normalize_process_text(stderr)
    except subprocess.TimeoutExpired as exc:
        stdout_text, stderr_text = timeout_output(exc)
        if process.poll() is None:
            cleanup_action = "kill"
            try:
                process.kill()
            except OSError as kill_exc:
                cleanup_error = append_error(cleanup_error, "kill_failed: " + str(kill_exc))
        try:
            stdout, stderr = process.communicate(timeout=KILL_GRACE_SECONDS)
            stdout_text = normalize_process_text(stdout) or stdout_text
            stderr_text = normalize_process_text(stderr) or stderr_text
        except subprocess.TimeoutExpired as kill_wait_exc:
            final_stdout, final_stderr = timeout_output(kill_wait_exc)
            stdout_text = final_stdout or stdout_text
            stderr_text = final_stderr or stderr_text
            cleanup_error = append_error(cleanup_error, "process_cleanup_timeout")
        except OSError as exc:
            cleanup_error = append_error(cleanup_error, "communicate_after_kill_failed: " + str(exc))
    except OSError as exc:
        cleanup_error = append_error(cleanup_error, "communicate_after_terminate_failed: " + str(exc))

    runtime_process_exited = process.poll() is not None
    orphan_process_detected = not runtime_process_exited
    return (
        stdout_text,
        stderr_text,
        runtime_process_exited,
        orphan_process_detected,
        process.returncode,
        cleanup_action,
        cleanup_error,
    )


def execute_no_generation_command(
    args: list[str],
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    stdin_mode: str = "devnull",
    stdin_text: str | None = None,
) -> ExecutionResult:
    validate_command_args(args, stdin_mode=stdin_mode)
    process: subprocess.Popen[str] | None = None
    try:
        stdin_target = subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=stdin_target,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            cwd=str(PROJECT_ROOT),
        )
        process_id = process.pid
        timed_out = False
        interrupted = False
        cleanup_action: str | None = None
        error: str | None = None
        try:
            stdout, stderr = process.communicate(input=stdin_text, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            (
                stdout,
                stderr,
                runtime_process_exited,
                orphan_process_detected,
                exit_code,
                cleanup_action,
                cleanup_error,
            ) = stop_started_process(process)
            error = append_error("timeout_expired", cleanup_error)
        except KeyboardInterrupt:
            interrupted = True
            (
                stdout,
                stderr,
                runtime_process_exited,
                orphan_process_detected,
                exit_code,
                cleanup_action,
                cleanup_error,
            ) = stop_started_process(process)
            error = append_error("keyboard_interrupt", cleanup_error)
        else:
            stdout = normalize_process_text(stdout)
            stderr = normalize_process_text(stderr)
            runtime_process_exited = process.poll() is not None
            orphan_process_detected = not runtime_process_exited
            exit_code = process.returncode
        stdout_bounded, stdout_truncated = bounded_text(stdout)
        stderr_bounded, stderr_truncated = bounded_text(stderr)
        return ExecutionResult(
            command_executed=True,
            runtime_process_started=True,
            runtime_process_exited=runtime_process_exited,
            timeout_seconds=timeout_seconds,
            exit_code=exit_code,
            stdout_text=stdout_bounded,
            stderr_text=stderr_bounded,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            orphan_process_detected=orphan_process_detected,
            timed_out=timed_out,
            interrupted=interrupted,
            runtime_process_id=process_id,
            cleanup_action=cleanup_action,
            error=error,
        )
    except OSError as exc:
        process_started = process is not None
        return ExecutionResult(
            command_executed=process_started,
            runtime_process_started=process_started,
            runtime_process_exited=True if process is None else process.poll() is not None,
            timeout_seconds=timeout_seconds,
            exit_code=None,
            stdout_text="",
            stderr_text=str(exc),
            stdout_truncated=False,
            stderr_truncated=False,
            orphan_process_detected=False if process is None else process.poll() is None,
            timed_out=False,
            interrupted=False,
            runtime_process_id=None if process is None else process.pid,
            cleanup_action=None,
            error=str(exc),
        )


def latest_receipts() -> list[Path]:
    if not RECEIPT_DIR.exists():
        return []
    return sorted(path for path in RECEIPT_DIR.glob("*.json") if path.is_file())


def latest_receipt_by_id_or_path(reference: str) -> Path | None:
    path = Path(reference)
    if path.exists() and path.is_file():
        try:
            path.resolve(strict=False).relative_to(REPORT_ROOT.resolve(strict=False))
        except ValueError:
            return None
        return path
    for receipt in latest_receipts():
        if receipt.stem == reference or receipt.name == reference:
            return receipt
    return None


def build_receipt_payload(
    validation: dict[str, Any],
    command_args: list[str],
    execution: ExecutionResult,
    *,
    version: str = "2",
    command_plan: CommandPlan | None = None,
    created_at: str | None = None,
    stdout_log_path: str | None = None,
    stderr_log_path: str | None = None,
) -> dict[str, Any]:
    passed = (
        execution.command_executed
        and execution.runtime_process_started
        and execution.runtime_process_exited
        and not execution.timed_out
        and not execution.interrupted
        and execution.exit_code == 0
        and execution.error is None
        and not execution.orphan_process_detected
    )
    runtime = validation["runtime"]
    if version == "2":
        final_decision = FINAL_DECISION_V2_PASS if passed else FINAL_DECISION_V2_INTERRUPTED if execution.interrupted else FINAL_DECISION_V2_FAIL
    elif version == "3":
        final_decision = FINAL_DECISION_V3_PASS if passed else FINAL_DECISION_V3_INTERRUPTED if execution.interrupted or execution.timed_out else FINAL_DECISION_V3_FAIL
    elif version == "4":
        if passed:
            final_decision = FINAL_DECISION_V4_PASS
        elif execution.interrupted or execution.timed_out:
            final_decision = FINAL_DECISION_V4_INTERRUPTED
        elif not execution.command_executed or not execution.runtime_process_started:
            final_decision = FINAL_DECISION_V4_BLOCKED
        else:
            final_decision = FINAL_DECISION_V4_FAIL
    else:
        final_decision = FINAL_DECISION_PASS if passed else FINAL_DECISION_FAIL
    created_by = "Engel AI No-Generation Load Check"
    if version == "3":
        created_by = "Engel AI No-Generation Load Check V3"
    elif version == "4":
        created_by = "Engel AI No-Generation Load Check V4"
    return {
        "no_generation_load_check_version": version,
        "created_at": created_at or now_utc(),
        "created_by": created_by,
        "model_key": validation["model_key"],
        "model_tier": validation["model_tier"],
        "model_name": validation["model_name"],
        "model_file_path": validation["model_file_path"],
        "runtime_binary_path": runtime["runtime_binary_path"],
        "execution_binary_path": command_plan.execution_binary_path if command_plan else command_args[0] if command_args else None,
        "approval_token_name": APPROVAL_TOKEN,
        "approval_token_verified": True,
        "diagnosis_mode": version in {"3", "4"},
        "command_args": command_args,
        "command_style": command_plan.command_style if command_plan else "prompt_argument_no_generation",
        "selected_command_style": command_plan.command_style if command_plan else "prompt_argument_no_generation",
        "selected_flags": command_plan.supported_non_interactive_flags if command_plan else [],
        "selected_prompt_flag": command_plan.selected_prompt_flag if command_plan else "--prompt",
        "selected_n_predict_flag": command_plan.selected_n_predict_flag if command_plan else "--n-predict",
        "supported_non_interactive_flags": command_plan.supported_non_interactive_flags if command_plan else [],
        "non_interactive_mode": command_plan.non_interactive_mode if command_plan else True,
        "stdin_mode": command_plan.stdin_mode if command_plan else "devnull",
        "help_checked": command_plan.help_checked if command_plan else False,
        "help_check_exit_code": command_plan.help_check_exit_code if command_plan else None,
        "help_check_timed_out": command_plan.help_check_timed_out if command_plan else False,
        "help_check_interrupted": command_plan.help_check_interrupted if command_plan else False,
        "help_check_error": command_plan.help_check_error if command_plan else None,
        "command_executed": execution.command_executed,
        "runtime_process_started": execution.runtime_process_started,
        "runtime_process_id": execution.runtime_process_id,
        "runtime_process_exited": execution.runtime_process_exited,
        "timeout_seconds": execution.timeout_seconds,
        "timed_out": execution.timed_out,
        "interrupted": execution.interrupted,
        "exit_code": execution.exit_code,
        "model_load_check_attempted": execution.runtime_process_started,
        "no_generation_requested": True,
        "n_predict": N_PREDICT,
        "normal_inference_enabled": False,
        "chat_enabled": False,
        "server_enabled": False,
        "auto_load_enabled": False,
        "trusted_memory_write_enabled": False,
        "provider_api_enabled": False,
        "source_route_queue_mutation": False,
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "stdout_truncated": execution.stdout_truncated,
        "stderr_truncated": execution.stderr_truncated,
        "bounded_log_max_chars": MAX_LOG_CHARS,
        "cleanup_action": execution.cleanup_action,
        "orphan_process_detected": execution.orphan_process_detected,
        "no_generation_load_check_passed": passed,
        "runtime_no_generation_check_ready": passed,
        "runtime_ready_for_inference": False,
        "error": execution.error,
        "final_decision": final_decision,
    }


def render_receipt_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        "# Engel AI No-Generation Load Check Receipt",
        "",
        f"- version: `{receipt['no_generation_load_check_version']}`",
        f"- timestamp: `{receipt['created_at']}`",
        f"- model_key: `{receipt['model_key']}`",
        f"- model_tier: `{receipt['model_tier']}`",
        f"- model_name: `{receipt['model_name']}`",
        f"- model_file_path: `{receipt['model_file_path']}`",
        f"- runtime_binary_path: `{receipt['runtime_binary_path']}`",
        f"- execution_binary_path: `{receipt['execution_binary_path']}`",
        f"- command_style: `{receipt['command_style']}`",
        f"- selected_prompt_flag: `{receipt['selected_prompt_flag']}`",
        f"- selected_n_predict_flag: `{receipt['selected_n_predict_flag']}`",
        f"- non_interactive_mode: `{receipt['non_interactive_mode']}`",
        f"- stdin_mode: `{receipt['stdin_mode']}`",
        f"- help_checked: `{receipt['help_checked']}`",
        f"- help_check_exit_code: `{receipt['help_check_exit_code']}`",
        f"- command_executed: `{receipt['command_executed']}`",
        f"- runtime_process_started: `{receipt['runtime_process_started']}`",
        f"- runtime_process_id: `{receipt['runtime_process_id']}`",
        f"- runtime_process_exited: `{receipt['runtime_process_exited']}`",
        f"- timeout_seconds: `{receipt['timeout_seconds']}`",
        f"- timed_out: `{receipt['timed_out']}`",
        f"- interrupted: `{receipt['interrupted']}`",
        f"- exit_code: `{receipt['exit_code']}`",
        f"- no_generation_requested: `{receipt['no_generation_requested']}`",
        f"- n_predict: `{receipt['n_predict']}`",
        f"- normal_inference_enabled: `{receipt['normal_inference_enabled']}`",
        f"- chat_enabled: `{receipt['chat_enabled']}`",
        f"- server_enabled: `{receipt['server_enabled']}`",
        f"- auto_load_enabled: `{receipt['auto_load_enabled']}`",
        f"- trusted_memory_write_enabled: `{receipt['trusted_memory_write_enabled']}`",
        f"- cleanup_action: `{receipt['cleanup_action']}`",
        f"- orphan_process_detected: `{receipt['orphan_process_detected']}`",
        f"- no_generation_load_check_passed: `{receipt['no_generation_load_check_passed']}`",
        f"- runtime_ready_for_inference: `{receipt['runtime_ready_for_inference']}`",
        f"- stdout_log_path: `{receipt['stdout_log_path']}`",
        f"- stderr_log_path: `{receipt['stderr_log_path']}`",
        f"- final_decision: `{receipt['final_decision']}`",
        "",
        "Command arguments used:",
        "",
        "```text",
        " ".join(str(part) for part in receipt["command_args"]),
        "```",
        "",
        "No chat loop was started. No server was started. No trusted memory was written.",
    ]
    return "\n".join(lines) + "\n"


def write_receipt_and_logs(receipt: dict[str, Any], execution: ExecutionResult) -> dict[str, str]:
    ensure_folders()
    stamp = safe_stamp(str(receipt["created_at"]))
    version = str(receipt.get("no_generation_load_check_version"))
    prefix = (
        "NO_GENERATION_LOAD_CHECK_V4"
        if version == "4"
        else "NO_GENERATION_LOAD_CHECK_V3"
        if version == "3"
        else "NO_GENERATION_LOAD_CHECK_V2"
        if version == "2"
        else "NO_GENERATION_LOAD_CHECK"
    )
    stem = f"{prefix}_{stamp}_{safe_slug(str(receipt['model_key']))}"
    stdout_log = LOG_DIR / f"{stem}_stdout.txt"
    stderr_log = LOG_DIR / f"{stem}_stderr.txt"
    write_lf_text(stdout_log, execution.stdout_text)
    write_lf_text(stderr_log, execution.stderr_text)
    receipt["stdout_log_path"] = project_relative(stdout_log)
    receipt["stderr_log_path"] = project_relative(stderr_log)
    receipt_json = RECEIPT_DIR / f"{stem}.json"
    receipt_md = RECEIPT_DIR / f"{stem}.md"
    write_lf_text(receipt_json, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    write_lf_text(receipt_md, render_receipt_markdown(receipt))
    return {
        "receipt_json": project_relative(receipt_json),
        "receipt_markdown": project_relative(receipt_md),
        "stdout_log_path": project_relative(stdout_log),
        "stderr_log_path": project_relative(stderr_log),
    }


def write_diagnostic_text(stem: str, name: str, text: str) -> str:
    ensure_folders()
    path = DIAGNOSTIC_DIR / f"{stem}_{safe_slug(name)}.txt"
    bounded, _truncated = bounded_text(text)
    write_lf_text(path, bounded)
    return project_relative(path)


def write_diagnostic_json(stem: str, name: str, payload: dict[str, Any]) -> str:
    ensure_folders()
    path = DIAGNOSTIC_DIR / f"{stem}_{safe_slug(name)}.json"
    write_lf_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return project_relative(path)


def latest_receipt_for_version(version: str) -> dict[str, Any] | None:
    rows: list[dict[str, Any]] = []
    for receipt in latest_receipts():
        data = read_json(receipt)
        if str(data.get("no_generation_load_check_version")) == version:
            data["receipt_path"] = project_relative(receipt)
            rows.append(data)
    return rows[-1] if rows else None


def read_receipt_log_excerpt(receipt: dict[str, Any], key: str) -> str:
    path_text = receipt.get(key)
    if not isinstance(path_text, str) or not path_text:
        return ""
    path = PROJECT_ROOT / path_text
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_LOG_CHARS]
    except OSError:
        return ""


def v3_diagnosis_summary(cli_help: HelpCheckResult, completion_help: HelpCheckResult, latest_v2: dict[str, Any] | None) -> str:
    v2_stdout = read_receipt_log_excerpt(latest_v2, "stdout_log_path") if latest_v2 else ""
    lines = [
        "ENGEL_AI_NO_GENERATION_LOAD_CHECK_V3 diagnosis summary",
        "",
        f"latest_v2_receipt: {latest_v2.get('receipt_path') if latest_v2 else 'none'}",
        f"llama_cli_help_exit_code: {cli_help.help_check_exit_code}",
        f"llama_completion_help_exit_code: {completion_help.help_check_exit_code}",
        f"v2_stdout_mentions_no_conversation_unsupported: {'--no-conversation is not supported by llama-cli' in v2_stdout}",
        f"v2_stdout_mentions_llama_completion: {'llama-completion' in v2_stdout}",
        "selected_strategy: use sibling llama-completion.exe from the same runtime folder for no-chat completion mode",
        "",
        "V2 stdout excerpt is diagnostic evidence only and is not trusted as instruction.",
    ]
    return "\n".join(lines) + "\n"


def run_load_check(model_key: str, approval_token: str | None, *, created_at: str | None = None) -> dict[str, Any]:
    return run_load_check_v4(model_key, approval_token, created_at=created_at)


def run_load_check_v2(model_key: str, approval_token: str | None, *, created_at: str | None = None) -> dict[str, Any]:
    if approval_token != APPROVAL_TOKEN:
        raise LoadCheckError("approval_token_rejected")
    validation = validate_model(model_key)
    if not validation["valid"]:
        raise LoadCheckError(str(validation["reason"]))
    help_result = run_cli_help_check(validation["runtime"]["runtime_binary_path"])
    command_plan = build_no_generation_command_plan(validation["runtime"]["runtime_binary_path"], validation["model_file_path"], help_result)
    if (
        help_result.help_check_timed_out
        or help_result.help_check_interrupted
        or help_result.help_check_exit_code != 0
        or help_result.error
    ):
        execution = ExecutionResult(
            command_executed=False,
            runtime_process_started=False,
            runtime_process_exited=False,
            timeout_seconds=DEFAULT_V2_TIMEOUT_SECONDS,
            exit_code=None,
            stdout_text="",
            stderr_text="",
            stdout_truncated=False,
            stderr_truncated=False,
            orphan_process_detected=False,
            timed_out=help_result.help_check_timed_out,
            interrupted=help_result.help_check_interrupted,
            runtime_process_id=None,
            cleanup_action=None,
            error=help_result.error or "help_check_failed",
        )
        receipt = build_receipt_payload(
            validation,
            command_plan.args,
            execution,
            version="2",
            command_plan=command_plan,
            created_at=created_at,
        )
        artifacts = write_receipt_and_logs(receipt, execution)
        return {"load_check_status": "failed_or_interrupted", "receipt": receipt, **artifacts}
    execution = execute_no_generation_command(
        command_plan.args,
        timeout_seconds=DEFAULT_V2_TIMEOUT_SECONDS,
        stdin_mode=command_plan.stdin_mode,
        stdin_text=command_plan.stdin_text,
    )
    receipt = build_receipt_payload(
        validation,
        command_plan.args,
        execution,
        version="2",
        command_plan=command_plan,
        created_at=created_at,
    )
    artifacts = write_receipt_and_logs(receipt, execution)
    status = "passed" if receipt["no_generation_load_check_passed"] is True else "failed_or_interrupted"
    return {"load_check_status": status, "receipt": receipt, **artifacts}


def run_load_check_v3(model_key: str, approval_token: str | None, *, created_at: str | None = None) -> dict[str, Any]:
    if approval_token != APPROVAL_TOKEN:
        raise LoadCheckError("approval_token_rejected")
    validation = validate_model(model_key)
    if not validation["valid"]:
        raise LoadCheckError(str(validation["reason"]))

    created = created_at or now_utc()
    stamp = safe_stamp(created)
    stem = f"NO_GENERATION_LOAD_CHECK_V3_{stamp}_{safe_slug(model_key)}"
    registered_binary = validation["runtime"]["runtime_binary_path"]
    completion_binary = str(completion_binary_for_runtime(registered_binary))

    cli_help = run_help_check_for_binary(registered_binary)
    cli_version = run_diagnostic_command([registered_binary, "--version"])
    completion_help = run_help_check_for_binary(completion_binary)
    completion_version = run_diagnostic_command([completion_binary, "--version"])
    latest_v2 = latest_receipt_for_version("2")
    v2_stdout_excerpt = read_receipt_log_excerpt(latest_v2, "stdout_log_path") if latest_v2 else ""

    diagnostic_paths = {
        "llama_cli_help_log_path": write_diagnostic_text(stem, "llama_cli_help", cli_help.help_text),
        "llama_cli_version_log_path": write_diagnostic_text(stem, "llama_cli_version", cli_version.stdout_text + cli_version.stderr_text),
        "llama_completion_help_log_path": write_diagnostic_text(stem, "llama_completion_help", completion_help.help_text),
        "llama_completion_version_log_path": write_diagnostic_text(stem, "llama_completion_version", completion_version.stdout_text + completion_version.stderr_text),
        "v2_stdout_excerpt_log_path": write_diagnostic_text(stem, "v2_stdout_excerpt", v2_stdout_excerpt),
        "diagnosis_summary_log_path": write_diagnostic_text(stem, "diagnosis_summary", v3_diagnosis_summary(cli_help, completion_help, latest_v2)),
    }

    command_plan = build_no_generation_command_plan_v3(registered_binary, validation["model_file_path"], cli_help, completion_help)
    diagnostic_failed = (
        cli_help.help_check_exit_code != 0
        or cli_help.help_check_timed_out
        or cli_help.help_check_interrupted
        or completion_help.help_check_exit_code != 0
        or completion_help.help_check_timed_out
        or completion_help.help_check_interrupted
        or not Path(str(command_plan.execution_binary_path or "")).exists()
    )
    if diagnostic_failed:
        execution = ExecutionResult(
            command_executed=False,
            runtime_process_started=False,
            runtime_process_exited=False,
            timeout_seconds=DEFAULT_V3_TIMEOUT_SECONDS,
            exit_code=None,
            stdout_text="",
            stderr_text="",
            stdout_truncated=False,
            stderr_truncated=False,
            orphan_process_detected=False,
            timed_out=bool(cli_help.help_check_timed_out or completion_help.help_check_timed_out),
            interrupted=bool(cli_help.help_check_interrupted or completion_help.help_check_interrupted),
            error="v3_diagnosis_failed",
        )
    else:
        execution = execute_no_generation_command(
            command_plan.args,
            timeout_seconds=DEFAULT_V3_TIMEOUT_SECONDS,
            stdin_mode=command_plan.stdin_mode,
            stdin_text=command_plan.stdin_text,
        )

    receipt = build_receipt_payload(
        validation,
        command_plan.args,
        execution,
        version="3",
        command_plan=command_plan,
        created_at=created,
    )
    receipt.update(
        {
            "help_log_path": diagnostic_paths["llama_completion_help_log_path"],
            "version_log_path": diagnostic_paths["llama_completion_version_log_path"],
            "diagnostic_log_paths": diagnostic_paths,
            "latest_v2_receipt_path": latest_v2.get("receipt_path") if latest_v2 else None,
            "v2_stdout_mentions_no_conversation_unsupported": "--no-conversation is not supported by llama-cli" in v2_stdout_excerpt,
            "v2_stdout_mentions_llama_completion": "llama-completion" in v2_stdout_excerpt,
        }
    )
    artifacts = write_receipt_and_logs(receipt, execution)
    status = "passed" if receipt["no_generation_load_check_passed"] is True else "failed_or_interrupted"
    return {"load_check_status": status, "receipt": receipt, **artifacts}


def run_load_check_v4(model_key: str, approval_token: str | None, *, created_at: str | None = None) -> dict[str, Any]:
    if approval_token != APPROVAL_TOKEN:
        raise LoadCheckError("approval_token_rejected")
    if model_key != DEFAULT_MODEL_KEY:
        raise LoadCheckError("v4_requires_tiny_seed")
    validation = validate_model(model_key)
    if not validation["valid"]:
        raise LoadCheckError(str(validation["reason"]))

    created = created_at or now_utc()
    minimal_probe_payload = run_minimal_exit_probes(created_at=created)
    command_plan, blocked_reason = build_no_generation_command_plan_v4(validation, minimal_probe_payload)
    if command_plan is None:
        execution = ExecutionResult(
            command_executed=False,
            runtime_process_started=False,
            runtime_process_exited=False,
            timeout_seconds=DEFAULT_V4_TIMEOUT_SECONDS,
            exit_code=None,
            stdout_text="",
            stderr_text=str(blocked_reason or "no_clean_exit_mode_identified"),
            stdout_truncated=False,
            stderr_truncated=False,
            orphan_process_detected=False,
            timed_out=False,
            interrupted=False,
            runtime_process_id=None,
            cleanup_action=None,
            error="v4_blocked: " + str(blocked_reason or "no_clean_exit_mode_identified"),
        )
        receipt = build_receipt_payload(
            validation,
            [],
            execution,
            version="4",
            command_plan=None,
            created_at=created,
        )
        receipt.update(
            {
                "runtime_folder": minimal_probe_payload.get("runtime_folder"),
                "binaries_checked": minimal_probe_payload.get("binaries_checked", []),
                "minimal_probe_results": minimal_probe_payload.get("minimal_probe_results", []),
                "no_model_probe_results": minimal_probe_payload.get("no_model_probe_results", []),
                "minimal_help_version_probes_clean": minimal_probe_payload.get("minimal_help_version_probes_clean"),
                "diagnostic_json_path": minimal_probe_payload.get("diagnostic_json_path"),
                "latest_v3_receipt_path": minimal_probe_payload.get("latest_v3_receipt_path"),
                "latest_v3_failed_or_interrupted": minimal_probe_payload.get("latest_v3_failed_or_interrupted"),
                "selected_binary": None,
                "selected_command_style": None,
                "command_style": None,
                "selected_flags": [],
                "selected_prompt_flag": None,
                "selected_n_predict_flag": "--n-predict",
                "stdin_mode": "not_applicable",
                "help_checked": True,
                "safe_candidate_identified": False,
                "blocked_reason": blocked_reason,
                "model_load_check_attempted": False,
                "final_decision": FINAL_DECISION_V4_BLOCKED,
            }
        )
        artifacts = write_receipt_and_logs(receipt, execution)
        return {"load_check_status": "blocked", "receipt": receipt, "minimal_probe": minimal_probe_payload, **artifacts}

    execution = execute_no_generation_command(
        command_plan.args,
        timeout_seconds=DEFAULT_V4_TIMEOUT_SECONDS,
        stdin_mode=command_plan.stdin_mode,
        stdin_text=command_plan.stdin_text,
    )
    receipt = build_receipt_payload(
        validation,
        command_plan.args,
        execution,
        version="4",
        command_plan=command_plan,
        created_at=created,
    )
    receipt.update(
        {
            "runtime_folder": minimal_probe_payload.get("runtime_folder"),
            "binaries_checked": minimal_probe_payload.get("binaries_checked", []),
            "minimal_probe_results": minimal_probe_payload.get("minimal_probe_results", []),
            "no_model_probe_results": minimal_probe_payload.get("no_model_probe_results", []),
            "minimal_help_version_probes_clean": minimal_probe_payload.get("minimal_help_version_probes_clean"),
            "diagnostic_json_path": minimal_probe_payload.get("diagnostic_json_path"),
            "latest_v3_receipt_path": minimal_probe_payload.get("latest_v3_receipt_path"),
            "latest_v3_failed_or_interrupted": minimal_probe_payload.get("latest_v3_failed_or_interrupted"),
            "selected_binary": Path(str(command_plan.execution_binary_path)).name if command_plan.execution_binary_path else None,
            "safe_candidate_identified": True,
            "model_load_check_attempted": execution.runtime_process_started,
        }
    )
    artifacts = write_receipt_and_logs(receipt, execution)
    status = "passed" if receipt["no_generation_load_check_passed"] is True else "failed_or_interrupted"
    return {"load_check_status": status, "receipt": receipt, "minimal_probe": minimal_probe_payload, **artifacts}


def command_preview_payload(model_key: str) -> dict[str, Any]:
    validation = validate_model(model_key)
    if not validation["valid"]:
        return {"ok": False, "reason": validation["reason"], "model_key": model_key}
    help_result = run_cli_help_check(validation["runtime"]["runtime_binary_path"])
    command_plan = build_no_generation_command_plan(validation["runtime"]["runtime_binary_path"], validation["model_file_path"], help_result)
    ok = help_result.help_check_exit_code == 0 and not help_result.help_check_timed_out and not help_result.help_check_interrupted and not help_result.error
    return {
        "ok": ok,
        "no_generation_load_check_version": "2",
        "model_key": validation["model_key"],
        "model_name": validation["model_name"],
        "runtime_binary_path": validation["runtime"]["runtime_binary_path"],
        "command_args": command_plan.args,
        "command_style": command_plan.command_style,
        "selected_prompt_flag": command_plan.selected_prompt_flag,
        "selected_n_predict_flag": command_plan.selected_n_predict_flag,
        "supported_non_interactive_flags": command_plan.supported_non_interactive_flags,
        "non_interactive_mode": command_plan.non_interactive_mode,
        "stdin_mode": command_plan.stdin_mode,
        "help_checked": command_plan.help_checked,
        "help_check_exit_code": command_plan.help_check_exit_code,
        "help_check_timed_out": command_plan.help_check_timed_out,
        "help_check_interrupted": command_plan.help_check_interrupted,
        "help_check_error": command_plan.help_check_error,
        "runtime_ready_for_inference": False,
        "chat_enabled": False,
        "server_enabled": False,
        "trusted_memory_write_enabled": False,
    }


def command_preview_v3_payload(model_key: str) -> dict[str, Any]:
    validation = validate_model(model_key)
    if not validation["valid"]:
        return {"ok": False, "reason": validation["reason"], "model_key": model_key}
    registered_binary = validation["runtime"]["runtime_binary_path"]
    completion_binary = str(completion_binary_for_runtime(registered_binary))
    cli_help = run_help_check_for_binary(registered_binary)
    completion_help = run_help_check_for_binary(completion_binary)
    command_plan = build_no_generation_command_plan_v3(registered_binary, validation["model_file_path"], cli_help, completion_help)
    ok = (
        cli_help.help_check_exit_code == 0
        and completion_help.help_check_exit_code == 0
        and not cli_help.help_check_timed_out
        and not completion_help.help_check_timed_out
        and not cli_help.help_check_interrupted
        and not completion_help.help_check_interrupted
    )
    return {
        "ok": ok,
        "no_generation_load_check_version": "3",
        "model_key": validation["model_key"],
        "model_name": validation["model_name"],
        "runtime_binary_path": registered_binary,
        "execution_binary_path": command_plan.execution_binary_path,
        "command_args": command_plan.args,
        "selected_command_style": command_plan.command_style,
        "selected_flags": command_plan.supported_non_interactive_flags,
        "selected_prompt_flag": command_plan.selected_prompt_flag,
        "selected_n_predict_flag": command_plan.selected_n_predict_flag,
        "non_interactive_mode": command_plan.non_interactive_mode,
        "stdin_mode": command_plan.stdin_mode,
        "help_checked": command_plan.help_checked,
        "cli_help_exit_code": cli_help.help_check_exit_code,
        "completion_help_exit_code": completion_help.help_check_exit_code,
        "runtime_ready_for_inference": False,
        "chat_enabled": False,
        "server_enabled": False,
        "trusted_memory_write_enabled": False,
    }


def probe_minimal_payload() -> dict[str, Any]:
    payload = run_minimal_exit_probes()
    payload["ok"] = payload.get("minimal_help_version_probes_clean") is True
    return payload


def command_preview_v4_payload(model_key: str = DEFAULT_MODEL_KEY) -> dict[str, Any]:
    if model_key != DEFAULT_MODEL_KEY:
        return {"ok": False, "reason": "v4_requires_tiny_seed", "model_key": model_key}
    validation = validate_model(model_key)
    if not validation["valid"]:
        return {"ok": False, "reason": validation["reason"], "model_key": model_key}
    minimal_probe_payload = run_minimal_exit_probes()
    command_plan, blocked_reason = build_no_generation_command_plan_v4(validation, minimal_probe_payload)
    return {
        "ok": True,
        "no_generation_load_check_version": "4",
        "model_key": validation["model_key"],
        "model_name": validation["model_name"],
        "runtime_binary_path": validation["runtime"]["runtime_binary_path"],
        "runtime_folder": minimal_probe_payload.get("runtime_folder"),
        "binaries_checked": minimal_probe_payload.get("binaries_checked", []),
        "minimal_help_version_probes_clean": minimal_probe_payload.get("minimal_help_version_probes_clean"),
        "diagnostic_json_path": minimal_probe_payload.get("diagnostic_json_path"),
        "safe_candidate_identified": command_plan is not None,
        "blocked_reason": blocked_reason,
        "command_args": command_plan.args if command_plan else [],
        "selected_binary": Path(str(command_plan.execution_binary_path)).name if command_plan and command_plan.execution_binary_path else None,
        "selected_command_style": command_plan.command_style if command_plan else None,
        "selected_flags": command_plan.supported_non_interactive_flags if command_plan else [],
        "selected_prompt_flag": command_plan.selected_prompt_flag if command_plan else None,
        "selected_n_predict_flag": command_plan.selected_n_predict_flag if command_plan else "--n-predict",
        "non_interactive_mode": True,
        "stdin_mode": command_plan.stdin_mode if command_plan else "not_applicable",
        "model_load_check_attempted": False,
        "runtime_ready_for_inference": False,
        "chat_enabled": False,
        "server_enabled": False,
        "trusted_memory_write_enabled": False,
    }


def diagnose_cli_payload() -> dict[str, Any]:
    runtime = runtime_status()
    runtime_path = runtime["runtime_binary_path"]
    if not runtime_path:
        return {"ok": False, "reason": "runtime_binary_not_configured", "runtime": runtime}
    completion_path = str(completion_binary_for_runtime(runtime_path))
    help_result = run_cli_help_check(runtime_path)
    version_result = run_diagnostic_command([runtime_path, "--version"])
    completion_help = run_help_check_for_binary(completion_path)
    completion_version = run_diagnostic_command([completion_path, "--version"])
    command_plan = build_no_generation_command_plan_v3(runtime_path, "<approved-gguf-path>", help_result, completion_help)
    return {
        "ok": (
            help_result.help_check_exit_code == 0
            and completion_help.help_check_exit_code == 0
            and version_result.exit_code == 0
            and completion_version.exit_code == 0
            and not help_result.help_check_timed_out
            and not completion_help.help_check_timed_out
        ),
        "runtime_binary_path": runtime_path,
        "completion_binary_path": completion_path,
        "help_checked": help_result.help_checked,
        "help_check_exit_code": help_result.help_check_exit_code,
        "help_check_timed_out": help_result.help_check_timed_out,
        "help_check_interrupted": help_result.help_check_interrupted,
        "help_check_error": help_result.error,
        "version_exit_code": version_result.exit_code,
        "completion_help_exit_code": completion_help.help_check_exit_code,
        "completion_version_exit_code": completion_version.exit_code,
        "help_text_truncated": help_result.help_text_truncated,
        "selected_prompt_flag": command_plan.selected_prompt_flag,
        "selected_n_predict_flag": command_plan.selected_n_predict_flag,
        "supported_non_interactive_flags": command_plan.supported_non_interactive_flags,
        "selected_command_style": command_plan.command_style,
        "execution_binary_path": command_plan.execution_binary_path,
        "non_interactive_mode": command_plan.non_interactive_mode,
        "stdin_mode": command_plan.stdin_mode,
        "runtime_ready_for_inference": False,
        "chat_enabled": False,
        "server_enabled": False,
    }


def list_payload() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for receipt in latest_receipts():
        data = read_json(receipt)
        rows.append(
            {
                "receipt_id": receipt.stem,
                "receipt_path": project_relative(receipt),
                "no_generation_load_check_version": data.get("no_generation_load_check_version"),
                "model_key": data.get("model_key"),
                "command_style": data.get("command_style"),
                "exit_code": data.get("exit_code"),
                "timed_out": bool(data.get("timed_out") is True),
                "interrupted": bool(data.get("interrupted") is True),
                "orphan_process_detected": bool(data.get("orphan_process_detected") is True),
                "no_generation_load_check_passed": bool(data.get("no_generation_load_check_passed") is True),
                "runtime_ready_for_inference": False,
                "final_decision": data.get("final_decision"),
            }
        )
    return rows


def status_payload() -> dict[str, Any]:
    ensure_folders()
    runtime = runtime_status()
    rows = list_payload()
    latest = rows[-1] if rows else None
    return {
        "no_generation_load_check_status_version": "4",
        "mode": "bounded_no_generation_load_check",
        "folders": {
            "root": project_relative(REPORT_ROOT),
            "receipts": project_relative(RECEIPT_DIR),
            "logs": project_relative(LOG_DIR),
            "examples": project_relative(EXAMPLES_DIR),
        },
        "runtime_path_config_present": RUNTIME_PATH_CONFIG.exists(),
        "runtime_binary_path": runtime["runtime_binary_path"],
        "runtime_binary_present": runtime["runtime_binary_present"],
        "runtime_path_approved": runtime["runtime_path_approved"],
        "approved_models_count": len(approval_entries()),
        "receipt_count": len(rows),
        "latest_receipt": latest,
        "runtime_no_generation_check_ready": bool(latest and latest.get("no_generation_load_check_passed") is True),
        "runtime_ready_for_inference": False,
        "safety_flags": {
            "normal_inference_enabled": False,
            "chat_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
            "auto_load_enabled": False,
            "provider_api_enabled": False,
            "source_route_queue_mutation": False,
        },
    }


def render_status() -> str:
    data = status_payload()
    lines = [
        "Engel AI No-Generation Load Check V4",
        "Mode: bounded local runtime load check only; no chat and no normal inference",
        "",
        f"runtime_path_config_present: {data['runtime_path_config_present']}",
        f"runtime_binary_path: {data['runtime_binary_path']}",
        f"runtime_binary_present: {data['runtime_binary_present']}",
        f"approved_models_count: {data['approved_models_count']}",
        f"receipt_count: {data['receipt_count']}",
        f"runtime_no_generation_check_ready: {data['runtime_no_generation_check_ready']}",
        f"runtime_ready_for_inference: {data['runtime_ready_for_inference']}",
        "",
        "Safety:",
    ]
    lines.extend(f"- {key}: {value}" for key, value in data["safety_flags"].items())
    return "\n".join(lines) + "\n"


def show_receipt(reference: str) -> dict[str, Any]:
    path = latest_receipt_by_id_or_path(reference)
    if not path:
        raise LoadCheckError("receipt_not_found")
    data = read_json(path)
    return {
        "receipt_path": project_relative(path),
        "no_generation_load_check_version": data.get("no_generation_load_check_version"),
        "model_key": data.get("model_key"),
        "command_style": data.get("command_style"),
        "exit_code": data.get("exit_code"),
        "timed_out": data.get("timed_out"),
        "interrupted": data.get("interrupted"),
        "orphan_process_detected": data.get("orphan_process_detected"),
        "no_generation_requested": data.get("no_generation_requested"),
        "no_generation_load_check_passed": data.get("no_generation_load_check_passed"),
        "runtime_ready_for_inference": False,
        "final_decision": data.get("final_decision"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI No-Generation Load Check V4")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("model_key")
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("model_key", nargs="?", default=DEFAULT_MODEL_KEY)
    check_parser.add_argument("--approval", required=True)
    check_v2_parser = subparsers.add_parser("check-v2")
    check_v2_parser.add_argument("model_key", nargs="?", default=DEFAULT_MODEL_KEY)
    check_v2_parser.add_argument("--approval", required=True)
    check_v3_parser = subparsers.add_parser("check-v3")
    check_v3_parser.add_argument("model_key", nargs="?", default=DEFAULT_MODEL_KEY)
    check_v3_parser.add_argument("--approval", required=True)
    check_v4_parser = subparsers.add_parser("check-v4")
    check_v4_parser.add_argument("model_key", nargs="?", default=DEFAULT_MODEL_KEY)
    check_v4_parser.add_argument("--approval", required=True)
    preview_parser = subparsers.add_parser("command-preview")
    preview_parser.add_argument("model_key", nargs="?", default=DEFAULT_MODEL_KEY)
    preview_v3_parser = subparsers.add_parser("command-preview-v3")
    preview_v3_parser.add_argument("model_key", nargs="?", default=DEFAULT_MODEL_KEY)
    preview_v4_parser = subparsers.add_parser("command-preview-v4")
    preview_v4_parser.add_argument("model_key", nargs="?", default=DEFAULT_MODEL_KEY)
    subparsers.add_parser("diagnose-cli")
    subparsers.add_parser("probe-minimal")
    subparsers.add_parser("list")
    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("receipt_reference")
    subparsers.add_parser("json")
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            print(render_status(), end="")
        elif args.command == "validate":
            print(json.dumps(validate_model(args.model_key), indent=2, sort_keys=True))
        elif args.command == "check-v2":
            payload = run_load_check_v2(args.model_key, args.approval)
            print(json.dumps(payload, indent=2, sort_keys=True))
            receipt = payload["receipt"]
            if receipt.get("interrupted") is True:
                return 130
            if receipt.get("no_generation_load_check_passed") is not True:
                return 1
        elif args.command == "check-v3":
            payload = run_load_check_v3(args.model_key, args.approval)
            print(json.dumps(payload, indent=2, sort_keys=True))
            receipt = payload["receipt"]
            if receipt.get("interrupted") is True:
                return 130
            if receipt.get("no_generation_load_check_passed") is not True:
                return 1
        elif args.command in {"check", "check-v4"}:
            payload = run_load_check_v4(args.model_key, args.approval)
            print(json.dumps(payload, indent=2, sort_keys=True))
            receipt = payload["receipt"]
            if receipt.get("interrupted") is True:
                return 130
            if receipt.get("no_generation_load_check_passed") is not True:
                return 1
        elif args.command == "command-preview":
            payload = command_preview_payload(args.model_key)
            print(json.dumps(payload, indent=2, sort_keys=True))
            if payload.get("ok") is not True:
                return 2
        elif args.command == "command-preview-v3":
            payload = command_preview_v3_payload(args.model_key)
            print(json.dumps(payload, indent=2, sort_keys=True))
            if payload.get("ok") is not True:
                return 2
        elif args.command == "command-preview-v4":
            payload = command_preview_v4_payload(args.model_key)
            print(json.dumps(payload, indent=2, sort_keys=True))
            if payload.get("ok") is not True:
                return 2
        elif args.command == "diagnose-cli":
            payload = diagnose_cli_payload()
            print(json.dumps(payload, indent=2, sort_keys=True))
            if payload.get("ok") is not True:
                return 1
        elif args.command == "probe-minimal":
            payload = probe_minimal_payload()
            print(json.dumps(payload, indent=2, sort_keys=True))
            if payload.get("ok") is not True:
                return 1
        elif args.command == "list":
            print(json.dumps(list_payload(), indent=2, sort_keys=True))
        elif args.command == "show":
            print(json.dumps(show_receipt(args.receipt_reference), indent=2, sort_keys=True))
        elif args.command == "json":
            payload = status_payload()
            payload["receipts"] = list_payload()
            print(json.dumps(payload, indent=2, sort_keys=True))
    except LoadCheckError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, indent=2, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
