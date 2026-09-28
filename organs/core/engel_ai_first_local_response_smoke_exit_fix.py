from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_READ_CHARS = 120_000
MAX_LOG_CHARS = 40_000
PROCESS_LIST_TIMEOUT_SECONDS = 10
HELP_TIMEOUT_SECONDS = 30
TERMINATE_GRACE_SECONDS = 5
KILL_GRACE_SECONDS = 5

APPROVAL_TOKEN = "APPROVE_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX"
SOURCE_FIRST_LOCAL_RESPONSE_SMOKE_COMMIT = "8be9dbf"
SOURCE_RUNTIME_SWAP_APPROVAL_COMMIT = "9d55cdef196964de3ce8e73a9d77f42d421ec900"
MODEL_KEY = "tiny_seed"
FIXED_PROMPT = "Reply with exactly: Engel"
N_PREDICT = 8
FALLBACK_N_PREDICT = 4
CONTEXT_SIZE = 512
THREADS = 4
TIMEOUT_SECONDS = 180

EXPECTED_RUNTIME_PATH = PROJECT_ROOT / "runtime" / "llama.cpp" / "candidates" / "llama-b9198-bin-win-cpu-x64" / "llama-cli.exe"
MODEL_FILE = Path("/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf")
FORBIDDEN_SERVER_NAMES = {"llama-server.exe", "rpc-server.exe"}

SWAP_APPROVAL_RECEIPT_DIR = PROJECT_ROOT / "reports" / "ai_llama_cpp_runtime_swap_approval" / "receipts"
V1_SMOKE_RECEIPT_DIR = PROJECT_ROOT / "reports" / "ai_first_local_response_smoke" / "receipts"
RUNTIME_PATH_CONFIG_MANIFEST = PROJECT_ROOT / "reports" / "ai_runtime_path_config" / "manifests" / "engel_ai_local_runtime_path_config_manifest.json"

REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_first_local_response_smoke_exit_fix"
DIAGNOSTIC_DIR = REPORT_ROOT / "diagnostics"
LOG_DIR = REPORT_ROOT / "logs"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1.md"

FINAL_DECISION_SUCCESS = "FIRST LOCAL RESPONSE SMOKE EXIT FIX PASSED - OUTPUT UNTRUSTED - NO CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_FAILURE = "FIRST LOCAL RESPONSE SMOKE EXIT FIX FAILED - OUTPUT UNTRUSTED - NO CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_BLOCKED = "FIRST LOCAL RESPONSE SMOKE EXIT FIX BLOCKED - OUTPUT UNTRUSTED - NO CHAT LOOP - NO TRUSTED MEMORY WRITE"
NEXT_SUCCESS_ACTION = "ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1"
NEXT_FAILURE_ACTION = "review first local response smoke exit-fix logs or adjust bounded command style"

INTERACTIVE_MARKERS = [
    "available commands:",
    "/exit or ctrl+c",
    "/regen",
    "/clear",
    "/read <file>",
    "/glob <pattern>",
    "waiting for input",
    "interactive mode",
    "reverse prompt",
    "prompt loop",
    "slash command",
    "\n> ",
    "\r\n> ",
]

SERVER_MARKERS = [
    "server listening",
    "listening on",
    "bind",
    "port",
    "llama server",
]


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
    timed_out: bool
    interrupted: bool
    orphan_process_detected: bool
    runtime_process_id: int | None = None
    cleanup_action: str | None = None
    error: str | None = None


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def write_lf_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, DIAGNOSTIC_DIR, LOG_DIR, RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "first_local_response_smoke_exit_fix_version": "1",
                    "example_only": True,
                    "selected_command_style": "simple_io_no_display",
                    "exit_control_flags": ["--single-turn"],
                    "model_key": MODEL_KEY,
                    "prompt": FIXED_PROMPT,
                    "output_marked_untrusted": True,
                    "model_output_trusted": False,
                    "runtime_ready_for_inference": False,
                    "chat_enabled": False,
                    "server_enabled": False,
                    "persistent_chat_loop_enabled": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_text_bounded(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_LOG_CHARS]
    except OSError:
        return ""


def path_text(path: Path) -> str:
    return str(path.resolve(strict=False)).replace("/", "\\")


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return path_text(path)


def repo_path(path_value: Any) -> Path:
    text = str(path_value or "")
    path = Path(text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def bounded_text(value: Any, max_chars: int = MAX_LOG_CHARS) -> tuple[str, bool]:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n[TRUNCATED]\n", True


def safety_fields() -> dict[str, bool]:
    return {
        "output_marked_untrusted": True,
        "model_output_trusted": False,
        "trusted_memory_write_enabled": False,
        "source_route_queue_mutation": False,
        "provider_api_enabled": False,
        "chat_enabled": False,
        "server_enabled": False,
        "persistent_chat_loop_enabled": False,
        "auto_load_enabled": False,
        "runtime_ready_for_inference": False,
        "inference_enabled": False,
    }


def latest_swap_approval_receipt() -> dict[str, Any] | None:
    if not SWAP_APPROVAL_RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(SWAP_APPROVAL_RECEIPT_DIR.glob("RUNTIME_SWAP_APPROVAL_*.json")):
        data = read_json(path)
        if data.get("runtime_swap_approval_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def latest_v1_smoke_receipt() -> dict[str, Any] | None:
    if not V1_SMOKE_RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(V1_SMOKE_RECEIPT_DIR.glob("FIRST_LOCAL_RESPONSE_SMOKE_*.json")):
        data = read_json(path)
        if data.get("first_local_response_smoke_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def latest_exit_fix_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_*.json")):
        data = read_json(path)
        if data.get("first_local_response_smoke_exit_fix_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def approved_runtime_path_from_swap() -> str | None:
    latest = latest_swap_approval_receipt()
    if latest and isinstance(latest.get("candidate_runtime_binary_path"), str):
        return path_text(Path(str(latest["candidate_runtime_binary_path"])))
    config = read_json(RUNTIME_PATH_CONFIG_MANIFEST)
    value = config.get("runtime_binary_path")
    if isinstance(value, str) and value.strip():
        return path_text(Path(value))
    return None


def list_runtime_processes() -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROCESS_LIST_TIMEOUT_SECONDS,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows: list[dict[str, str]] = []
    reader = csv.reader(io.StringIO(result.stdout))
    for row in reader:
        if len(row) < 2:
            continue
        image_name = row[0]
        lower = image_name.lower()
        if lower.startswith("llama") or lower.startswith("rpc-server") or lower.startswith("ollama"):
            rows.append({"image_name": image_name, "pid": row[1]})
    return rows


def load_help_payload(runtime_path: str | None = None) -> dict[str, Any]:
    runtime = runtime_path or approved_runtime_path_from_swap() or path_text(EXPECTED_RUNTIME_PATH)
    if Path(runtime).name.lower() in FORBIDDEN_SERVER_NAMES:
        return {"help_checked": False, "help_supported": False, "error": "server_executable_not_allowed", "supported_flags": []}
    try:
        result = subprocess.run(
            [runtime, "--help"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=HELP_TIMEOUT_SECONDS,
            shell=False,
        )
        text = (result.stdout or "") + "\n" + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"help_checked": True, "help_supported": False, "error": str(exc), "supported_flags": []}
    supported = sorted(
        flag
        for flag in ["--simple-io", "--no-display-prompt", "--no-conversation", "--single-turn"]
        if flag in text
    )
    return {
        "help_checked": True,
        "help_supported": result.returncode == 0,
        "help_exit_code": result.returncode,
        "supported_flags": supported,
        "simple_io_supported": "--simple-io" in supported,
        "no_display_prompt_supported": "--no-display-prompt" in supported,
        "no_conversation_supported": "--no-conversation" in supported,
        "single_turn_supported": "--single-turn" in supported,
        "help_output_truncated": len(text) > MAX_LOG_CHARS,
    }


def command_style_matrix(runtime_path: str | None = None) -> list[dict[str, Any]]:
    runtime = runtime_path or approved_runtime_path_from_swap() or path_text(EXPECTED_RUNTIME_PATH)
    help_payload = load_help_payload(runtime)
    supported = set(help_payload.get("supported_flags") or [])
    styles = [
        {
            "style_id": "simple_io_no_display",
            "description": "Use basic subprocess IO, suppress prompt echo, and add help-confirmed single-turn exit control.",
            "required_flags": ["--simple-io", "--no-display-prompt", "--single-turn"],
            "exit_control_flags": ["--single-turn"],
            "n_predict": N_PREDICT,
            "priority": 1,
        },
        {
            "style_id": "no_conversation_no_display",
            "description": "Disable conversation mode and suppress prompt echo.",
            "required_flags": ["--no-conversation", "--no-display-prompt"],
            "exit_control_flags": ["--no-conversation"],
            "n_predict": N_PREDICT,
            "priority": 2,
        },
        {
            "style_id": "prompt_cache_disabled_short_predict",
            "description": "Fallback bounded short prediction with stdin closed when stronger flags are unavailable.",
            "required_flags": [],
            "exit_control_flags": [],
            "n_predict": FALLBACK_N_PREDICT,
            "priority": 3,
        },
    ]
    rows: list[dict[str, Any]] = []
    for style in styles:
        missing = [flag for flag in style["required_flags"] if flag not in supported]
        eligible = bool(help_payload.get("help_supported") is True and not missing)
        args = command_args_for_style(style["style_id"], runtime, path_text(MODEL_FILE), int(style["n_predict"]), selected_without_help=True)
        rows.append({**style, "help_payload": help_payload, "missing_required_flags": missing, "selection_eligible": eligible, "command_args": args})
    return rows


def selected_command_style(runtime_path: str | None = None) -> dict[str, Any]:
    rows = command_style_matrix(runtime_path)
    eligible = [row for row in rows if row["selection_eligible"] is True]
    if eligible:
        selected = sorted(eligible, key=lambda row: int(row["priority"]))[0]
    else:
        selected = rows[-1]
    selected = dict(selected)
    selected["selected"] = True
    selected["command_args"] = command_args_for_style(
        str(selected["style_id"]),
        runtime_path or approved_runtime_path_from_swap() or path_text(EXPECTED_RUNTIME_PATH),
        path_text(MODEL_FILE),
        int(selected["n_predict"]),
        selected_without_help=True,
    )
    return selected


def command_args_for_style(style_id: str, runtime_path: str, model_path: str, n_predict: int, *, selected_without_help: bool = False) -> list[str]:
    del selected_without_help
    base = [
        runtime_path,
        "-m",
        model_path,
        "-p",
        FIXED_PROMPT,
        "-n",
        str(n_predict),
        "-c",
        str(CONTEXT_SIZE),
        "-t",
        str(THREADS),
    ]
    if style_id == "simple_io_no_display":
        return base + ["--simple-io", "--no-display-prompt", "--single-turn", "--log-disable", "--offline"]
    if style_id == "no_conversation_no_display":
        return base + ["--no-conversation", "--no-display-prompt", "--log-disable", "--offline"]
    return base + ["--log-disable", "--offline"]


def command_preview_text(args: list[str]) -> str:
    return "COMMAND PREVIEW ONLY — NOT EXECUTED\n" + " ".join(json.dumps(arg) if " " in arg else arg for arg in args)


def marker_analysis(stdout_text: str, stderr_text: str) -> dict[str, Any]:
    combined = (stdout_text or "") + "\n" + (stderr_text or "")
    lower = combined.lower()
    matched_interactive = [marker for marker in INTERACTIVE_MARKERS if marker in lower]
    matched_server = [marker for marker in SERVER_MARKERS if marker in lower]
    prompt_loop_count = lower.count("\n> ") + lower.count("\r\n> ")
    if prompt_loop_count >= 2 and "\n> " not in matched_interactive:
        matched_interactive.append("repeated prompt marker")
    return {
        "disqualifying_interactive_markers_found": bool(matched_interactive),
        "disqualifying_server_markers_found": bool(matched_server),
        "matched_interactive_markers": matched_interactive,
        "matched_server_markers": matched_server,
        "prompt_loop_marker_count": prompt_loop_count,
    }


def read_v1_logs(receipt: dict[str, Any] | None) -> tuple[str, str]:
    if not receipt:
        return "", ""
    return (
        read_text_bounded(repo_path(receipt.get("stdout_log_path"))),
        read_text_bounded(repo_path(receipt.get("stderr_log_path"))),
    )


def diagnose_latest_payload(write_diagnostic: bool = False) -> dict[str, Any]:
    latest = latest_v1_smoke_receipt()
    stdout_text, stderr_text = read_v1_logs(latest)
    markers = marker_analysis(stdout_text, stderr_text)
    classifications: list[str] = []
    if markers["disqualifying_interactive_markers_found"]:
        classifications.append("interactive_wait_after_output")
        classifications.append("command_style_needs_non_interactive_flags")
    if latest and latest.get("interrupted") is True and latest.get("exit_code") == 130:
        classifications.append("manual_keyboard_interrupt")
    if latest and latest.get("timed_out") is True:
        classifications.append("timeout_needed")
    if not classifications:
        classifications.append("ambiguous")
    snippet, truncated = bounded_text((stdout_text + "\n" + stderr_text).strip(), 4000)
    payload = {
        "diagnosis_version": "1",
        "created_at": now_utc(),
        "source_first_local_response_smoke_commit": SOURCE_FIRST_LOCAL_RESPONSE_SMOKE_COMMIT,
        "source_first_local_response_smoke_receipt": latest.get("receipt_path") if latest else None,
        "source_failure_reason": latest.get("error") if latest else None,
        "source_exit_code": latest.get("exit_code") if latest else None,
        "source_interrupted": latest.get("interrupted") if latest else None,
        "source_expected_token_seen": latest.get("expected_token_seen") if latest else None,
        "classification": classifications[0],
        "classifications": classifications,
        "stdout_stderr_treated_as_untrusted": True,
        "bounded_output_summary": snippet,
        "bounded_output_truncated": truncated,
        **markers,
        **safety_fields(),
    }
    if write_diagnostic:
        ensure_folders()
        created_at = str(payload["created_at"])
        path = DIAGNOSTIC_DIR / f"FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_DIAGNOSIS_{stamp(created_at)}.json"
        payload["diagnostic_path"] = project_relative(path)
        write_lf_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def preflight_payload() -> dict[str, Any]:
    latest_swap = latest_swap_approval_receipt()
    latest_v1 = latest_v1_smoke_receipt()
    approved_runtime = approved_runtime_path_from_swap()
    reasons: list[str] = []
    if not latest_v1:
        reasons.append("missing_first_local_response_smoke_v1_receipt")
    else:
        if latest_v1.get("command_executed") is not True:
            reasons.append("source_v1_smoke_not_executed")
        if latest_v1.get("output_marked_untrusted") is not True:
            reasons.append("source_v1_output_not_marked_untrusted")
        if latest_v1.get("runtime_ready_for_inference") is not False:
            reasons.append("source_v1_runtime_ready_not_false")
    if not latest_swap:
        reasons.append("missing_runtime_swap_approval_receipt")
    else:
        if latest_swap.get("runtime_swap_approval_recorded") is not True:
            reasons.append("runtime_swap_approval_not_recorded")
        if latest_swap.get("runtime_ready_for_inference") is not False:
            reasons.append("swap_receipt_runtime_ready_for_inference_not_false")
        if latest_swap.get("chat_enabled") is not False:
            reasons.append("swap_receipt_chat_enabled_not_false")
    if approved_runtime is None:
        reasons.append("missing_approved_runtime_path")
    elif approved_runtime.casefold() != path_text(EXPECTED_RUNTIME_PATH).casefold():
        reasons.append("approved_runtime_path_mismatch")
    runtime_path = Path(approved_runtime) if approved_runtime else EXPECTED_RUNTIME_PATH
    if runtime_path.name.lower() in FORBIDDEN_SERVER_NAMES:
        reasons.append("server_executable_not_allowed")
    if not runtime_path.exists() or not runtime_path.is_file():
        reasons.append("approved_runtime_missing")
    if not MODEL_FILE.exists() or not MODEL_FILE.is_file():
        reasons.append("tiny_seed_model_missing")
    selected = selected_command_style(approved_runtime)
    if selected.get("selection_eligible") is not True:
        reasons.append("selected_command_style_not_help_supported")
    return {
        "preflight_passed": not reasons,
        "blocked_reasons": reasons,
        "source_first_local_response_smoke_receipt": latest_v1.get("receipt_path") if latest_v1 else None,
        "source_failure_reason": latest_v1.get("error") if latest_v1 else None,
        "source_exit_code": latest_v1.get("exit_code") if latest_v1 else None,
        "source_expected_token_seen": latest_v1.get("expected_token_seen") if latest_v1 else None,
        "source_runtime_swap_approval_receipt": latest_swap.get("receipt_path") if latest_swap else None,
        "swap_approval_recorded": latest_swap.get("runtime_swap_approval_recorded") if latest_swap else None,
        "registered_runtime_path": approved_runtime,
        "expected_runtime_path": path_text(EXPECTED_RUNTIME_PATH),
        "runtime_binary_present": runtime_path.exists() and runtime_path.is_file(),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "model_file_present": MODEL_FILE.exists() and MODEL_FILE.is_file(),
        "selected_command_style": selected.get("style_id"),
        "selected_command_style_supported": selected.get("selection_eligible"),
        "supported_flags": selected.get("help_payload", {}).get("supported_flags"),
        "server_executable_selected": runtime_path.name.lower() in FORBIDDEN_SERVER_NAMES,
    }


def status_payload() -> dict[str, Any]:
    latest_v1 = latest_v1_smoke_receipt()
    latest_exit_fix = latest_exit_fix_receipt()
    return {
        "first_local_response_smoke_exit_fix_version": "1",
        "latest_first_local_response_smoke_receipt": latest_v1.get("receipt_path") if latest_v1 else None,
        "previous_result": "failed_safely" if latest_v1 and latest_v1.get("first_response_smoke_passed") is False else latest_v1.get("final_decision") if latest_v1 else None,
        "previous_failure_reason": latest_v1.get("error") if latest_v1 else None,
        "previous_exit_code": latest_v1.get("exit_code") if latest_v1 else None,
        "previous_interrupted": latest_v1.get("interrupted") if latest_v1 else None,
        "previous_expected_token_seen": latest_v1.get("expected_token_seen") if latest_v1 else None,
        "latest_exit_fix_receipt": latest_exit_fix.get("receipt_path") if latest_exit_fix else None,
        "latest_exit_fix_passed": latest_exit_fix.get("first_response_smoke_exit_fix_passed") if latest_exit_fix else None,
        "approved_runtime_path": approved_runtime_path_from_swap(),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        **safety_fields(),
    }


def preview_payload() -> dict[str, Any]:
    runtime = approved_runtime_path_from_swap() or path_text(EXPECTED_RUNTIME_PATH)
    selected = selected_command_style(runtime)
    return {
        "first_local_response_smoke_exit_fix_version": "1",
        "command_preview_only": True,
        "command_preview": command_preview_text(list(selected["command_args"])),
        "selected_command_style": selected["style_id"],
        "selected_command_style_supported": selected["selection_eligible"],
        "required_flags": selected["required_flags"],
        "exit_control_flags": selected["exit_control_flags"],
        "help_supported_flags": selected.get("help_payload", {}).get("supported_flags"),
        "prompt": FIXED_PROMPT,
        "prompt_is_fixed_inert": True,
        "user_content_used_as_prompt": False,
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "registered_runtime_path": runtime,
        "command_args": selected["command_args"],
        "stdin_mode": "devnull",
        "timeout_seconds": TIMEOUT_SECONDS,
        "n_predict": selected["n_predict"],
        "output_will_be_marked_untrusted": True,
        "preflight": preflight_payload(),
        **safety_fields(),
    }


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
            cleanup_error = "terminate_failed: " + str(exc)
    try:
        stdout, stderr = process.communicate(timeout=TERMINATE_GRACE_SECONDS)
        stdout_text = stdout or ""
        stderr_text = stderr or ""
    except subprocess.TimeoutExpired as exc:
        stdout_text = str(getattr(exc, "stdout", "") or "")
        stderr_text = str(getattr(exc, "stderr", "") or "")
        if process.poll() is None:
            cleanup_action = "kill"
            try:
                process.kill()
            except OSError as kill_exc:
                cleanup_error = (cleanup_error + "; " if cleanup_error else "") + "kill_failed: " + str(kill_exc)
        try:
            stdout, stderr = process.communicate(timeout=KILL_GRACE_SECONDS)
            stdout_text = stdout or stdout_text
            stderr_text = stderr or stderr_text
        except subprocess.TimeoutExpired:
            cleanup_error = (cleanup_error + "; " if cleanup_error else "") + "process_cleanup_timeout"
    runtime_process_exited = process.poll() is not None
    orphan_process_detected = not runtime_process_exited
    return stdout_text, stderr_text, runtime_process_exited, orphan_process_detected, process.returncode, cleanup_action, cleanup_error


def run_bounded_process(args: list[str], timeout_seconds: int) -> ExecutionResult:
    if not args:
        return ExecutionResult(False, False, True, timeout_seconds, None, "", "", False, False, False, False, False, error="empty_args")
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            cwd=str(Path(args[0]).resolve(strict=False).parent),
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            stdout_text, stdout_truncated = bounded_text(stdout)
            stderr_text, stderr_truncated = bounded_text(stderr)
            return ExecutionResult(True, True, True, timeout_seconds, process.returncode, stdout_text, stderr_text, stdout_truncated, stderr_truncated, False, False, False, runtime_process_id=process.pid, cleanup_action="none")
        except subprocess.TimeoutExpired as exc:
            stdout_text = str(getattr(exc, "stdout", "") or "")
            stderr_text = str(getattr(exc, "stderr", "") or "")
            cleanup_stdout, cleanup_stderr, exited, orphan, exit_code, cleanup_action, cleanup_error = stop_started_process(process)
            stdout_text = cleanup_stdout or stdout_text
            stderr_text = cleanup_stderr or stderr_text
            stdout_text, stdout_truncated = bounded_text(stdout_text)
            stderr_text, stderr_truncated = bounded_text(stderr_text)
            return ExecutionResult(True, True, exited, timeout_seconds, exit_code, stdout_text, stderr_text, stdout_truncated, stderr_truncated, True, False, orphan, runtime_process_id=process.pid, cleanup_action=cleanup_action, error=cleanup_error)
    except KeyboardInterrupt:
        if process is not None:
            stdout_text, stderr_text, exited, orphan, exit_code, cleanup_action, cleanup_error = stop_started_process(process)
            stdout_text, stdout_truncated = bounded_text(stdout_text)
            stderr_text, stderr_truncated = bounded_text(stderr_text)
            return ExecutionResult(True, True, exited, timeout_seconds, exit_code, stdout_text, stderr_text, stdout_truncated, stderr_truncated, False, True, orphan, runtime_process_id=process.pid, cleanup_action=cleanup_action, error=(cleanup_error or "keyboard_interrupt"))
        return ExecutionResult(True, False, True, timeout_seconds, None, "", "", False, False, False, True, False, error="keyboard_interrupt_before_start")
    except OSError as exc:
        return ExecutionResult(True, False, True, timeout_seconds, None, "", str(exc), False, False, False, False, False, error="process_start_failed: " + str(exc))


def write_log_pair(prefix: str, stdout_text: str, stderr_text: str) -> tuple[str, str]:
    stdout_path = LOG_DIR / f"{prefix}_stdout.txt"
    stderr_path = LOG_DIR / f"{prefix}_stderr.txt"
    write_lf_text(stdout_path, stdout_text)
    write_lf_text(stderr_path, stderr_text)
    return project_relative(stdout_path), project_relative(stderr_path)


def base_receipt(created_at: str, approval_verified: bool) -> dict[str, Any]:
    latest_v1 = latest_v1_smoke_receipt()
    runtime_path = approved_runtime_path_from_swap() or path_text(EXPECTED_RUNTIME_PATH)
    selected = selected_command_style(runtime_path)
    return {
        "first_local_response_smoke_exit_fix_version": "1",
        "created_at": created_at,
        "created_by": "Engel AI First Local Response Smoke Exit Fix",
        "source_first_local_response_smoke_commit": SOURCE_FIRST_LOCAL_RESPONSE_SMOKE_COMMIT,
        "source_first_local_response_smoke_receipt": latest_v1.get("receipt_path") if latest_v1 else None,
        "source_failure_reason": latest_v1.get("error") if latest_v1 else None,
        "source_exit_code": latest_v1.get("exit_code") if latest_v1 else None,
        "source_runtime_swap_approval_commit": SOURCE_RUNTIME_SWAP_APPROVAL_COMMIT,
        "model_key": MODEL_KEY,
        "registered_runtime_path": runtime_path,
        "model_file_path": path_text(MODEL_FILE),
        "approval_token_name": APPROVAL_TOKEN,
        "approval_token_verified": approval_verified,
        "selected_command_style": selected["style_id"],
        "selected_command_style_supported": selected["selection_eligible"],
        "exit_control_flags": selected["exit_control_flags"],
        "prompt": FIXED_PROMPT,
        "prompt_is_fixed_inert": True,
        "user_content_used_as_prompt": False,
        "command_args": selected["command_args"],
        "stdin_mode": "devnull",
        "timeout_seconds": TIMEOUT_SECONDS,
        "n_predict": selected["n_predict"],
        **safety_fields(),
    }


def blocked_receipt(reason: str, approval_verified: bool, write_receipt: bool = False) -> dict[str, Any]:
    receipt = {
        **base_receipt(now_utc(), approval_verified),
        "command_executed": False,
        "runtime_process_started": False,
        "runtime_process_exited": False,
        "exit_code": None,
        "timed_out": False,
        "interrupted": False,
        "orphan_process_detected": False,
        "stdout_log_path": None,
        "stderr_log_path": None,
        "stdout_truncated": False,
        "stderr_truncated": False,
        "output_captured": False,
        "expected_token_seen": False,
        "disqualifying_interactive_markers_found": False,
        "first_response_smoke_exit_fix_passed": False,
        "first_response_smoke_passed": False,
        "blocked_reason": reason,
        "next_safe_action": NEXT_FAILURE_ACTION,
        "final_decision": FINAL_DECISION_BLOCKED,
    }
    if write_receipt:
        return persist_receipt(receipt)
    return receipt


def persist_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    ensure_folders()
    created_at = str(receipt.get("created_at") or now_utc())
    prefix = f"FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_{stamp(created_at)}_tiny_seed"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    report_path = PLAN_REPORT_DIR / f"{prefix}.md"
    receipt["receipt_path"] = project_relative(receipt_path)
    receipt["report_path"] = project_relative(report_path)
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    report = render_report(receipt)
    write_lf_text(report_path, report)
    write_lf_text(CODEX_REPORT, report)
    return receipt


def run_exit_fix_smoke(approval: str | None) -> dict[str, Any]:
    approval_verified = approval == APPROVAL_TOKEN
    if not approval_verified:
        return blocked_receipt("approval_token_missing_or_invalid", False, False)
    existing = latest_exit_fix_receipt()
    if existing and existing.get("first_response_smoke_exit_fix_passed") is True:
        return blocked_receipt("first_local_response_smoke_exit_fix_already_passed", True, False)

    ensure_folders()
    preflight = preflight_payload()
    existing_processes = list_runtime_processes()
    if existing_processes:
        preflight["blocked_reasons"].append("runtime_process_already_running")
        preflight["pre_existing_runtime_processes"] = existing_processes
    if not preflight["preflight_passed"] or existing_processes:
        receipt = blocked_receipt("; ".join(preflight["blocked_reasons"]) or "preflight_failed", True, True)
        receipt["preflight"] = preflight
        return receipt

    created_at = now_utc()
    receipt = base_receipt(created_at, True)
    args = list(receipt["command_args"])
    result = run_bounded_process(args, TIMEOUT_SECONDS)
    prefix = f"FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_{stamp(created_at)}_tiny_seed"
    stdout_path, stderr_path = write_log_pair(prefix, result.stdout_text, result.stderr_text)
    post_processes = list_runtime_processes()
    orphan = result.orphan_process_detected or bool(post_processes)
    markers = marker_analysis(result.stdout_text, result.stderr_text)
    combined_output = (result.stdout_text or "") + "\n" + (result.stderr_text or "")
    output_captured = bool(combined_output.strip())
    expected_token_seen = "Engel" in combined_output
    disqualifying_interactive = bool(markers["disqualifying_interactive_markers_found"] or markers["disqualifying_server_markers_found"])
    passed = (
        approval_verified
        and receipt["selected_command_style_supported"] is True
        and result.command_executed
        and result.runtime_process_started
        and result.runtime_process_exited
        and result.exit_code == 0
        and not result.timed_out
        and not result.interrupted
        and not orphan
        and output_captured
        and expected_token_seen
        and not disqualifying_interactive
        and receipt["output_marked_untrusted"] is True
        and receipt["trusted_memory_write_enabled"] is False
        and receipt["source_route_queue_mutation"] is False
        and receipt["provider_api_enabled"] is False
        and receipt["server_enabled"] is False
        and receipt["persistent_chat_loop_enabled"] is False
        and receipt["auto_load_enabled"] is False
        and receipt["chat_enabled"] is False
        and receipt["runtime_ready_for_inference"] is False
    )
    receipt.update(
        {
            "preflight": preflight,
            "command_executed": result.command_executed,
            "runtime_process_started": result.runtime_process_started,
            "runtime_process_exited": result.runtime_process_exited,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "interrupted": result.interrupted,
            "orphan_process_detected": orphan,
            "runtime_process_id": result.runtime_process_id,
            "cleanup_action": result.cleanup_action,
            "error": result.error,
            "post_smoke_runtime_processes": post_processes,
            "stdout_log_path": stdout_path,
            "stderr_log_path": stderr_path,
            "stdout_truncated": result.stdout_truncated,
            "stderr_truncated": result.stderr_truncated,
            "output_captured": output_captured,
            "expected_token_seen": expected_token_seen,
            "expected_token_seen_scope": "bounded_stdout_stderr_untrusted",
            **markers,
            "disqualifying_interactive_markers_found": disqualifying_interactive,
            "first_response_smoke_exit_fix_passed": passed,
            "first_response_smoke_passed": passed,
            "first_local_response_smoke_ready": passed,
            "next_safe_action": NEXT_SUCCESS_ACTION if passed else NEXT_FAILURE_ACTION,
            "final_decision": FINAL_DECISION_SUCCESS if passed else FINAL_DECISION_FAILURE,
        }
    )
    return persist_receipt(receipt)


def render_report(receipt: dict[str, Any] | None = None) -> str:
    data = receipt or latest_exit_fix_receipt() or {}
    latest_v1 = latest_v1_smoke_receipt() or {}
    result = "not run"
    if data.get("final_decision") == FINAL_DECISION_BLOCKED:
        result = "blocked"
    elif data.get("timed_out") is True:
        result = "timed out"
    elif data.get("interrupted") is True:
        result = "interrupted"
    elif data.get("first_response_smoke_exit_fix_passed") is True:
        result = "passed"
    elif data:
        result = "failed"
    return f"""# ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1

## Summary
This phase fixes the first local response smoke exit behavior by selecting a help-confirmed non-interactive llama.cpp command style.

## Why This Phase Exists
V1 proved the approved runtime and tiny_seed could produce the expected token, but it failed safely because the process required interruption instead of exiting cleanly. This phase focuses on subprocess exit discipline, not broad chat enablement.

## V1 Smoke Failure Context
- source V1 commit: `{data.get("source_first_local_response_smoke_commit", SOURCE_FIRST_LOCAL_RESPONSE_SMOKE_COMMIT)}`
- source V1 receipt: `{data.get("source_first_local_response_smoke_receipt", latest_v1.get("receipt_path"))}`
- source failure reason: `{data.get("source_failure_reason", latest_v1.get("error"))}`
- source exit code: `{data.get("source_exit_code", latest_v1.get("exit_code"))}`
- source expected token appeared: `{latest_v1.get("expected_token_seen")}`

## Smoke Inputs
- runtime path used: `{data.get("registered_runtime_path", path_text(EXPECTED_RUNTIME_PATH))}`
- model used: `{data.get("model_key", MODEL_KEY)}`
- model file: `{data.get("model_file_path", path_text(MODEL_FILE))}`
- fixed prompt used: `{data.get("prompt", FIXED_PROMPT)}`
- selected command style: `{data.get("selected_command_style", "simple_io_no_display")}`
- exit control flags: `{data.get("exit_control_flags", ["--single-turn"])}`
- user content used as prompt: `{data.get("user_content_used_as_prompt", False)}`
- n_predict: `{data.get("n_predict", N_PREDICT)}`

## Selected Command Style
Selected command style: `{data.get("selected_command_style", "simple_io_no_display")}`
The selected command style is `{data.get("selected_command_style", "simple_io_no_display")}` with output kept as untrusted evidence only.

## Exit-Fix Smoke Result
- exit-fix smoke ran: `{data.get("command_executed")}`
- result: `{result}`
- runtime process started: `{data.get("runtime_process_started")}`
- runtime process exited: `{data.get("runtime_process_exited")}`
- exit code: `{data.get("exit_code")}`
- timed out: `{data.get("timed_out")}`
- interrupted: `{data.get("interrupted")}`
- orphan process detected: `{data.get("orphan_process_detected")}`
- output captured: `{data.get("output_captured")}`
- expected token appeared: `{data.get("expected_token_seen")}`
- interactive markers found: `{data.get("disqualifying_interactive_markers_found")}`
- output marked untrusted: `{data.get("output_marked_untrusted", True)}`
- Output marked untrusted: `{data.get("output_marked_untrusted", True)}`

## Evidence
- receipt path: `{data.get("receipt_path")}`
- stdout log path: `{data.get("stdout_log_path")}`
- stderr log path: `{data.get("stderr_log_path")}`
- report path: `{data.get("report_path")}`

## Readiness Result
- first local response smoke passed: `{data.get("first_response_smoke_passed")}`
- first local response smoke exit fix passed: `{data.get("first_response_smoke_exit_fix_passed")}`
- runtime ready for inference: `{data.get("runtime_ready_for_inference", False)}`
- chat enabled: `{data.get("chat_enabled", False)}`
- server enabled: `{data.get("server_enabled", False)}`
- trusted memory write enabled: `{data.get("trusted_memory_write_enabled", False)}`
- next safe action: `{data.get("next_safe_action", "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1")}`

## Safety Boundaries
- persistent chat loop enabled: `{data.get("persistent_chat_loop_enabled", False)}`
- model output trusted: `{data.get("model_output_trusted", False)}`
- provider API enabled: `{data.get("provider_api_enabled", False)}`
- source/route/queue mutation: `{data.get("source_route_queue_mutation", False)}`
- auto-load enabled: `{data.get("auto_load_enabled", False)}`

## Verification Results
- First local response smoke exit-fix verifier: pending run.
- First local response smoke verifier: pending run.
- Runtime readiness verifier: pending run.
- Full Codex verifier result: pending run.
- Packaging skipped.

This phase fixes the bounded first local response smoke exit behavior only. It does not enable persistent chat, server mode, trusted-memory writes, startup auto-load, provider calls, larger models, or model output trust.
"""


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists() or "Selected command style" not in read_text_bounded(CODEX_REPORT):
        write_lf_text(CODEX_REPORT, render_report(None))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI first local response smoke exit fix")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("diagnose-latest")
    sub.add_parser("preview")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--approval")
    sub.add_parser("json")
    args = parser.parse_args(argv)

    ensure_folders()
    write_initial_report()
    if args.command == "status":
        print(json.dumps(status_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "diagnose-latest":
        print(json.dumps(diagnose_latest_payload(write_diagnostic=False), indent=2, sort_keys=True))
        return 0
    if args.command == "preview":
        print(json.dumps(preview_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "run":
        result = run_exit_fix_smoke(args.approval)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("approval_token_verified") is True else 2
    if args.command == "json":
        payload = {
            "status": status_payload(),
            "diagnosis": diagnose_latest_payload(write_diagnostic=False),
            "preview": preview_payload(),
            "latest_exit_fix_smoke": latest_exit_fix_receipt(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
