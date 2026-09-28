from __future__ import annotations

import argparse
import csv
import os
import io
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engel_ai_local_chat_runtime_resolver import native_path_text, resolve_runtime_and_model_paths


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_READ_CHARS = 120_000
MAX_LOG_CHARS = 40_000
PROCESS_LIST_TIMEOUT_SECONDS = 10
TERMINATE_GRACE_SECONDS = 5
KILL_GRACE_SECONDS = 5

APPROVAL_TOKEN = "APPROVE_FIRST_LOCAL_RESPONSE_SMOKE"
SOURCE_RUNTIME_SWAP_APPROVAL_COMMIT = "9d55cdef196964de3ce8e73a9d77f42d421ec900"
MODEL_KEY = "tiny_seed"
FIXED_PROMPT = "Reply with exactly: Engel"
N_PREDICT = 8
CONTEXT_SIZE = 512
THREADS = 4
TIMEOUT_SECONDS = 180

EXPECTED_RUNTIME_PATH = PROJECT_ROOT / "runtime" / "llama.cpp" / "candidates" / "llama-b9198-bin-win-cpu-x64" / "llama-cli.exe"
MODEL_FILE = Path("/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf")
RUNTIME_PATH, MODEL_FILE = resolve_runtime_and_model_paths(
    project_root=PROJECT_ROOT,
    default_runtime=EXPECTED_RUNTIME_PATH,
    default_model=MODEL_FILE,
    runtime_env_var="ENGEL_AI_LOCAL_CHAT_RUNTIME_PATH",
    model_env_var="ENGEL_AI_LOCAL_CHAT_MODEL_PATH",
)
EXPECTED_RUNTIME_PATH = RUNTIME_PATH
FORBIDDEN_SERVER_NAMES = {"llama-server.exe", "rpc-server.exe"}

SWAP_APPROVAL_RECEIPT_DIR = PROJECT_ROOT / "reports" / "ai_llama_cpp_runtime_swap_approval" / "receipts"
RUNTIME_PATH_CONFIG_MANIFEST = PROJECT_ROOT / "reports" / "ai_runtime_path_config" / "manifests" / "engel_ai_local_runtime_path_config_manifest.json"

REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_first_local_response_smoke"
LOG_DIR = REPORT_ROOT / "logs"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_V1.md"

FINAL_DECISION_SUCCESS = "FIRST LOCAL RESPONSE SMOKE PASSED - OUTPUT UNTRUSTED - NO CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_FAILURE = "FIRST LOCAL RESPONSE SMOKE FAILED - OUTPUT UNTRUSTED - NO CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_BLOCKED = "FIRST LOCAL RESPONSE SMOKE BLOCKED - OUTPUT UNTRUSTED - NO CHAT LOOP - NO TRUSTED MEMORY WRITE"
NEXT_SUCCESS_ACTION = "ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1"
NEXT_FAILURE_ACTION = "Review first local response smoke logs or adjust bounded command style."


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
    for folder in [REPORT_ROOT, LOG_DIR, RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "FIRST_LOCAL_RESPONSE_SMOKE_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "first_local_response_smoke_version": "1",
                    "example_only": True,
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


def path_text(path: Path) -> str:
    return native_path_text(path)


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\" if os.name == "nt" else "/")
    except ValueError:
        return path_text(path)


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


def latest_smoke_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("FIRST_LOCAL_RESPONSE_SMOKE_*.json")):
        data = read_json(path)
        if data.get("first_local_response_smoke_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def approved_runtime_path_from_swap() -> str | None:
    latest = latest_swap_approval_receipt()
    if latest and isinstance(latest.get("candidate_runtime_binary_path"), str):
        candidate = Path(str(latest["candidate_runtime_binary_path"]))
        if candidate.exists() and candidate.is_file():
            return path_text(candidate)
    config = read_json(RUNTIME_PATH_CONFIG_MANIFEST)
    value = config.get("runtime_binary_path")
    if isinstance(value, str) and value.strip():
        candidate = Path(value)
        if candidate.exists() and candidate.is_file():
            return path_text(candidate)
    return None


def command_args(runtime_path: str | None = None, model_path: str | None = None) -> list[str]:
    runtime = runtime_path or path_text(EXPECTED_RUNTIME_PATH)
    model = model_path or path_text(MODEL_FILE)
    return [
        runtime,
        "-m",
        model,
        "-p",
        FIXED_PROMPT,
        "-n",
        str(N_PREDICT),
        "-c",
        str(CONTEXT_SIZE),
        "-t",
        str(THREADS),
        "--log-disable",
        "--offline",
    ]


def command_preview_text(args: list[str]) -> str:
    return "COMMAND PREVIEW ONLY — NOT EXECUTED\n" + " ".join(json.dumps(arg) if " " in arg else arg for arg in args)


def list_runtime_processes() -> list[dict[str, str]]:
    if os.name != "nt":
        try:
            result = subprocess.run(
                ["ps", "-eo", "pid=,comm="],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                timeout=PROCESS_LIST_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                return []
            rows: list[dict[str, str]] = []
            for raw in result.stdout.splitlines():
                parts = raw.strip().split(maxsplit=1)
                if len(parts) != 2:
                    continue
                pid_text, name = parts
                lowered = name.lower()
                if lowered.startswith("llama") or lowered in {"rpc-server", "ollama"}:
                    rows.append({"image_name": name, "pid": pid_text})
            return rows
        except (OSError, subprocess.TimeoutExpired):
            return []
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


def preflight_payload() -> dict[str, Any]:
    latest_swap = latest_swap_approval_receipt()
    approved_runtime = approved_runtime_path_from_swap()
    reasons: list[str] = []
    if not latest_swap:
        reasons.append("missing_runtime_swap_approval_receipt")
    else:
        if latest_swap.get("runtime_swap_approval_recorded") is not True:
            reasons.append("runtime_swap_approval_not_recorded")
        if latest_swap.get("first_local_response_smoke_allowed_next") is not True:
            reasons.append("first_local_response_smoke_not_allowed_next")
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
    return {
        "preflight_passed": not reasons,
        "blocked_reasons": reasons,
        "source_runtime_swap_approval_receipt": latest_swap.get("receipt_path") if latest_swap else None,
        "swap_approval_recorded": latest_swap.get("runtime_swap_approval_recorded") if latest_swap else None,
        "first_local_response_smoke_allowed_next": latest_swap.get("first_local_response_smoke_allowed_next") if latest_swap else None,
        "registered_runtime_path": approved_runtime,
        "expected_runtime_path": path_text(EXPECTED_RUNTIME_PATH),
        "runtime_binary_present": runtime_path.exists() and runtime_path.is_file(),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "model_file_present": MODEL_FILE.exists() and MODEL_FILE.is_file(),
        "server_executable_selected": runtime_path.name.lower() in FORBIDDEN_SERVER_NAMES,
    }


def status_payload() -> dict[str, Any]:
    latest_swap = latest_swap_approval_receipt()
    latest_smoke = latest_smoke_receipt()
    approved_runtime = approved_runtime_path_from_swap() or path_text(EXPECTED_RUNTIME_PATH)
    runtime_binary_present = Path(approved_runtime).exists() and Path(approved_runtime).is_file()
    return {
        "first_local_response_smoke_version": "1",
        "source_runtime_swap_approval_commit": SOURCE_RUNTIME_SWAP_APPROVAL_COMMIT,
        "latest_swap_approval_receipt": latest_swap.get("receipt_path") if latest_swap else None,
        "approved_runtime_path": approved_runtime,
        "runtime_binary_present": runtime_binary_present,
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "first_local_response_smoke_allowed_next": latest_swap.get("first_local_response_smoke_allowed_next") if latest_swap else False,
        "prior_first_response_smoke_exists": latest_smoke is not None,
        "latest_first_response_smoke_receipt": latest_smoke.get("receipt_path") if latest_smoke else None,
        "latest_first_response_smoke_passed": latest_smoke.get("first_response_smoke_passed") if latest_smoke else None,
        **safety_fields(),
    }


def preview_payload() -> dict[str, Any]:
    approved_runtime = approved_runtime_path_from_swap() or path_text(EXPECTED_RUNTIME_PATH)
    args = command_args(approved_runtime, path_text(MODEL_FILE))
    return {
        "first_local_response_smoke_version": "1",
        "command_preview_only": True,
        "command_preview": command_preview_text(args),
        "prompt": FIXED_PROMPT,
        "prompt_is_fixed_inert": True,
        "user_content_used_as_prompt": False,
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "registered_runtime_path": approved_runtime,
        "command_args": args,
        "timeout_seconds": TIMEOUT_SECONDS,
        "n_predict": N_PREDICT,
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
    latest_swap = latest_swap_approval_receipt()
    runtime_path = approved_runtime_path_from_swap() or path_text(EXPECTED_RUNTIME_PATH)
    return {
        "first_local_response_smoke_version": "1",
        "created_at": created_at,
        "created_by": "Engel AI First Local Response Smoke",
        "source_runtime_swap_approval_commit": SOURCE_RUNTIME_SWAP_APPROVAL_COMMIT,
        "source_runtime_swap_approval_receipt": latest_swap.get("receipt_path") if latest_swap else None,
        "model_key": MODEL_KEY,
        "registered_runtime_path": runtime_path,
        "model_file_path": path_text(MODEL_FILE),
        "approval_token_name": APPROVAL_TOKEN,
        "approval_token_verified": approval_verified,
        "prompt": FIXED_PROMPT,
        "prompt_is_fixed_inert": True,
        "user_content_used_as_prompt": False,
        "command_args": command_args(runtime_path, path_text(MODEL_FILE)),
        "timeout_seconds": TIMEOUT_SECONDS,
        "n_predict": N_PREDICT,
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
    prefix = f"FIRST_LOCAL_RESPONSE_SMOKE_{stamp(created_at)}_tiny_seed"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    report_path = PLAN_REPORT_DIR / f"{prefix}.md"
    receipt["receipt_path"] = project_relative(receipt_path)
    receipt["report_path"] = project_relative(report_path)
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    report = render_report(receipt)
    write_lf_text(report_path, report)
    write_lf_text(CODEX_REPORT, report)
    return receipt


def run_first_response_smoke(approval: str | None) -> dict[str, Any]:
    approval_verified = approval == APPROVAL_TOKEN
    if not approval_verified:
        return blocked_receipt("approval_token_missing_or_invalid", False, False)
    existing = latest_smoke_receipt()
    if existing and existing.get("first_response_smoke_passed") is True:
        return blocked_receipt("first_local_response_smoke_already_passed", True, False)

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
    prefix = f"FIRST_LOCAL_RESPONSE_SMOKE_{stamp(created_at)}_tiny_seed"
    stdout_path, stderr_path = write_log_pair(prefix, result.stdout_text, result.stderr_text)
    post_processes = list_runtime_processes()
    orphan = result.orphan_process_detected or bool(post_processes)
    combined_output = (result.stdout_text or "") + "\n" + (result.stderr_text or "")
    output_captured = bool(combined_output.strip())
    expected_token_seen = "Engel" in combined_output
    passed = (
        approval_verified
        and result.command_executed
        and result.runtime_process_started
        and result.runtime_process_exited
        and result.exit_code == 0
        and not result.timed_out
        and not result.interrupted
        and not orphan
        and output_captured
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
            "expected_token_seen_scope": "bounded_stdout_stderr_untrusted_may_include_prompt_echo",
            "first_response_smoke_passed": passed,
            "first_local_response_smoke_ready": passed,
            "next_safe_action": NEXT_SUCCESS_ACTION if passed else NEXT_FAILURE_ACTION,
            "final_decision": FINAL_DECISION_SUCCESS if passed else FINAL_DECISION_FAILURE,
        }
    )
    return persist_receipt(receipt)


def render_report(receipt: dict[str, Any] | None = None) -> str:
    data = receipt or latest_smoke_receipt() or {}
    result = "not run"
    if data.get("final_decision") == FINAL_DECISION_BLOCKED:
        result = "blocked"
    elif data.get("timed_out") is True:
        result = "timed out"
    elif data.get("interrupted") is True:
        result = "interrupted"
    elif data.get("first_response_smoke_passed") is True:
        result = "passed"
    elif data:
        result = "failed"
    return f"""# ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_V1

## Summary
This phase runs one bounded first local response smoke with the approved llama.cpp runtime and the `tiny_seed` GGUF.

## Why This Phase Exists
The runtime swap approval gate allowed the validated candidate path to be used for a controlled future smoke. This phase captures one tiny local response as untrusted evidence while keeping broader inference, chat, server, and memory gates disabled.

## Runtime Swap Approval Dependency
- source commit: `{data.get("source_runtime_swap_approval_commit", SOURCE_RUNTIME_SWAP_APPROVAL_COMMIT)}`
- source receipt: `{data.get("source_runtime_swap_approval_receipt")}`

## Smoke Inputs
- runtime path used: `{data.get("registered_runtime_path", path_text(EXPECTED_RUNTIME_PATH))}`
- model used: `{data.get("model_key", MODEL_KEY)}`
- model file: `{data.get("model_file_path", path_text(MODEL_FILE))}`
- fixed prompt used: `{data.get("prompt", FIXED_PROMPT)}`
- user content used as prompt: `{data.get("user_content_used_as_prompt", False)}`
- n_predict: `{data.get("n_predict", N_PREDICT)}`

## Smoke Result
- smoke ran: `{data.get("command_executed")}`
- result: `{result}`
- runtime process started: `{data.get("runtime_process_started")}`
- runtime process exited: `{data.get("runtime_process_exited")}`
- exit code: `{data.get("exit_code")}`
- timed out: `{data.get("timed_out")}`
- interrupted: `{data.get("interrupted")}`
- orphan process detected: `{data.get("orphan_process_detected")}`
- output captured: `{data.get("output_captured")}`
- expected token appeared: `{data.get("expected_token_seen")}`
- output marked untrusted: `{data.get("output_marked_untrusted", True)}`

## Evidence
- receipt path: `{data.get("receipt_path")}`
- stdout log path: `{data.get("stdout_log_path")}`
- stderr log path: `{data.get("stderr_log_path")}`
- report path: `{data.get("report_path")}`

## Readiness Result
- first local response smoke passed: `{data.get("first_response_smoke_passed")}`
- runtime ready for inference: `{data.get("runtime_ready_for_inference", False)}`
- chat enabled: `{data.get("chat_enabled", False)}`
- server enabled: `{data.get("server_enabled", False)}`
- trusted memory write enabled: `{data.get("trusted_memory_write_enabled", False)}`
- next safe action: `{data.get("next_safe_action", "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_V1")}`

## Safety Boundaries
- persistent chat loop enabled: `{data.get("persistent_chat_loop_enabled", False)}`
- model output trusted: `{data.get("model_output_trusted", False)}`
- provider API enabled: `{data.get("provider_api_enabled", False)}`
- source/route/queue mutation: `{data.get("source_route_queue_mutation", False)}`
- auto-load enabled: `{data.get("auto_load_enabled", False)}`

## Verification Results
- First local response smoke verifier: pending run.
- Runtime swap approval verifier: pending run.
- Runtime readiness verifier: pending run.
- Full Codex verifier result: pending run.
- Packaging skipped.

This phase runs one bounded first local response smoke only. It does not enable persistent chat, server mode, trusted-memory writes, startup auto-load, provider calls, larger models, or model output trust.
"""


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists():
        write_lf_text(CODEX_REPORT, render_report(None))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI first local response smoke")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
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
    if args.command == "preview":
        print(json.dumps(preview_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "run":
        result = run_first_response_smoke(args.approval)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("approval_token_verified") is True else 2
    if args.command == "json":
        payload = {
            "status": status_payload(),
            "preview": preview_payload(),
            "latest_first_response_smoke": latest_smoke_receipt(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
