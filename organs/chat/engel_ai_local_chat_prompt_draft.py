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
HELP_TIMEOUT_SECONDS = 30
TIMEOUT_SECONDS = 180
TERMINATE_GRACE_SECONDS = 5
KILL_GRACE_SECONDS = 5

APPROVAL_TOKEN = "APPROVE_LOCAL_CHAT_PROMPT_DRAFT"
MODEL_KEY = "tiny_seed"
 
PROMPT_MAX_LENGTH = 500
N_PREDICT = 64
CONTEXT_SIZE = 512
THREADS = 4

if os.name == "nt":
    RUNTIME_PATH = Path("D:/b.WorkSpace/Engel App/runtime/llama.cpp/candidates/llama-b9198-bin-win-cpu-x64/llama-cli.exe")
    MODEL_FILE = Path("D:/b.WorkSpace/Engel App/models/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q4_k_m.gguf")
else:
    RUNTIME_PATH = Path("/opt/engel/runtime/llama.cpp/candidates/llama-b9198-bin-linux-x64/llama-cli")
    MODEL_FILE = Path("/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf")
    
FORBIDDEN_EXECUTABLE_NAMES = {"llama-server.exe", "rpc-server.exe"}

RUNTIME_PATH, MODEL_FILE = resolve_runtime_and_model_paths(
    project_root=PROJECT_ROOT,
    default_runtime=RUNTIME_PATH,
    default_model=MODEL_FILE,
    runtime_env_var="ENGEL_AI_LOCAL_CHAT_RUNTIME_PATH",
    model_env_var="ENGEL_AI_LOCAL_CHAT_MODEL_PATH",
)

BOUNDED_SMOKE_RECEIPT_DIR = PROJECT_ROOT / "reports" / "ai_bounded_local_chat_smoke" / "receipts"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_local_chat_prompt_draft"
LOG_DIR = REPORT_ROOT / "logs"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_HUMAN_PROMPT_DRAFT_V1.md"

FINAL_DECISION_SUCCESS = "LOCAL CHAT PROMPT DRAFT PASSED - OUTPUT UNTRUSTED - NO PERSISTENT CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_FAILURE = "LOCAL CHAT PROMPT DRAFT FAILED - OUTPUT UNTRUSTED - NO PERSISTENT CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_BLOCKED = "LOCAL CHAT PROMPT DRAFT BLOCKED - OUTPUT UNTRUSTED - NO PERSISTENT CHAT LOOP - NO TRUSTED MEMORY WRITE"
NEXT_SUCCESS_ACTION = "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_DRAFT_V1"
NEXT_FAILURE_ACTION = "review prompt draft logs or adjust bounded command style"

SUGGESTED_FLAGS = [
    "--simple-io",
    "--no-display-prompt",
    "--single-turn",
    "--log-disable",
    "--offline",
]

SERVER_MARKERS = [
    "server listening",
    "listening on",
    "listening at",
    "http server",
    "bind address",
    "server started",
    "llama server",
]

PERSISTENT_CHAT_MARKERS = [
    "waiting for input",
    "enter prompt",
    "input prompt",
    "stdin open",
    "readline",
    "interactive mode",
    "prompt loop",
    "persistent chat",
    "reverse prompt",
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
    for folder in [REPORT_ROOT, LOG_DIR, RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "LOCAL_CHAT_PROMPT_DRAFT_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "local_chat_prompt_draft_version": "1",
                    "example_only": True,
                    "prompt_max_length": PROMPT_MAX_LENGTH,
                    "n_predict": N_PREDICT,
                    "output_marked_untrusted": True,
                    "model_output_trusted": False,
                    "persistent_chat_loop_enabled": False,
                    "server_enabled": False,
                    "trusted_memory_write_enabled": False,
                    "runtime_ready_for_inference": False,
                    "open_chat_enabled": False,
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


def read_text_bounded(path: Path, limit: int = MAX_LOG_CHARS) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def path_text(path: Path) -> str:
    return native_path_text(path)


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\" if os.name == "nt" else "/")
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
        "approved_memory_write_enabled": False,
        "source_route_queue_mutation": False,
        "provider_api_enabled": False,
        "open_chat_enabled": False,
        "chat_enabled": False,
        "server_enabled": False,
        "persistent_chat_loop_enabled": False,
        "auto_load_enabled": False,
        "runtime_ready_for_inference": False,
        "inference_enabled": False,
    }


def latest_bounded_smoke_receipt() -> dict[str, Any] | None:
    if not BOUNDED_SMOKE_RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(BOUNDED_SMOKE_RECEIPT_DIR.glob("BOUNDED_LOCAL_CHAT_SMOKE_*.json")):
        data = read_json(path)
        if data.get("bounded_local_chat_smoke_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def latest_prompt_draft_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("LOCAL_CHAT_PROMPT_DRAFT_*.json")):
        data = read_json(path)
        if data.get("local_chat_prompt_draft_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def bounded_chat_smoke_passed(receipt: dict[str, Any] | None = None) -> bool:
    data = receipt or latest_bounded_smoke_receipt()
    return bool(
        data
        and data.get("bounded_local_chat_smoke_passed") is True
        and data.get("output_marked_untrusted") is True
        and data.get("model_output_trusted") is False
        and data.get("runtime_ready_for_inference") is False
        and data.get("open_chat_enabled") is False
    )


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
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=PROCESS_LIST_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    rows: list[dict[str, str]] = []
    reader = csv.reader(io.StringIO(result.stdout))
    for raw in reader:
        if not raw:
            continue
        name = raw[0].strip()
        lower_name = name.lower()
        if lower_name.startswith("llama") or lower_name in {"rpc-server.exe", "ollama.exe"}:
            rows.append(
                {
                    "image_name": name,
                    "pid": raw[1].strip() if len(raw) > 1 else "",
                    "session_name": raw[2].strip() if len(raw) > 2 else "",
                }
            )
    return rows


def load_help_payload(runtime_path: Path = RUNTIME_PATH) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "help_checked": False,
        "help_supported": False,
        "help_exit_code": None,
        "supported_flags": [],
        "unsupported_suggested_flags": list(SUGGESTED_FLAGS),
        "help_error": None,
    }
    if runtime_path.name.lower() in FORBIDDEN_EXECUTABLE_NAMES:
        payload["help_error"] = "server executable is not allowed"
        return payload
    if not runtime_path.exists() or not runtime_path.is_file():
        payload["help_error"] = "runtime binary missing"
        return payload
    try:
        result = subprocess.run(
            [path_text(runtime_path), "--help"],
            cwd=str(runtime_path.parent),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=HELP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        payload["help_error"] = "help timed out"
        return payload
    except OSError as exc:
        payload["help_error"] = str(exc)
        return payload
    help_text = (result.stdout or "") + "\n" + (result.stderr or "")
    supported = [flag for flag in SUGGESTED_FLAGS if flag in help_text]
    payload.update(
        {
            "help_checked": True,
            "help_supported": result.returncode == 0,
            "help_exit_code": result.returncode,
            "supported_flags": supported,
            "unsupported_suggested_flags": [flag for flag in SUGGESTED_FLAGS if flag not in supported],
        }
    )
    return payload


def validate_prompt(prompt: str | None) -> tuple[bool, str, str]:
    text = "" if prompt is None else str(prompt)
    stripped = text.strip()
    if not stripped:
        return False, stripped, "empty prompt refused"
    if len(stripped) > PROMPT_MAX_LENGTH:
        return False, stripped, "prompt over 500 characters refused"
    lowered = stripped.lower()
    path_like = (
        lowered.startswith("@")
        or lowered.startswith("file:")
        or lowered.startswith("http:")
        or lowered.startswith("https:")
        or lowered.startswith("\\\\")
        or lowered.endswith(".txt")
        or lowered.endswith(".md")
        or lowered.endswith(".json")
        or lowered.endswith(".py")
    )
    if path_like:
        return False, stripped, "file import prompt patterns are not supported"
    return True, stripped, ""


def command_args(prompt: str, help_payload: dict[str, Any] | None = None) -> list[str]:
    supported_flags = list((help_payload or load_help_payload()).get("supported_flags", []))
    return [
        path_text(RUNTIME_PATH),
        "-m",
        path_text(MODEL_FILE),
        "-p",
        prompt,
        "-n",
        str(N_PREDICT),
        "-c",
        str(CONTEXT_SIZE),
        "-t",
        str(THREADS),
        *supported_flags,
    ]


def detect_output_risks(stdout_text: str, stderr_text: str) -> dict[str, Any]:
    combined = (stdout_text + "\n" + stderr_text).lower()
    server_hits = [marker for marker in SERVER_MARKERS if marker in combined]
    interactive_hits = [marker for marker in PERSISTENT_CHAT_MARKERS if marker in combined]
    prompt_loop_count = combined.count("\n> ") + combined.count("\r\n> ")
    if prompt_loop_count >= 2:
        interactive_hits.append("repeated prompt marker")
    return {
        "fatal_server_markers": server_hits,
        "fatal_interactive_markers": sorted(set(interactive_hits)),
        "server_startup_detected": bool(server_hits),
        "persistent_chat_loop_detected": bool(interactive_hits),
        "disqualifying_interactive_markers_found": bool(interactive_hits),
    }


def preflight_payload(prompt: str | None = None) -> dict[str, Any]:
    smoke_receipt = latest_bounded_smoke_receipt()
    valid_prompt, normalized_prompt, prompt_reason = validate_prompt(prompt) if prompt is not None else (True, "", "")
    reasons: list[str] = []
    if not bounded_chat_smoke_passed(smoke_receipt):
        reasons.append("bounded local chat smoke has not passed")
    if not valid_prompt:
        reasons.append(prompt_reason)
    if not RUNTIME_PATH.exists() or not RUNTIME_PATH.is_file():
        reasons.append("approved runtime binary missing")
    if RUNTIME_PATH.name.lower() in FORBIDDEN_EXECUTABLE_NAMES:
        reasons.append("server executable selected")
    if not MODEL_FILE.exists() or not MODEL_FILE.is_file():
        reasons.append("selected model file missing")
    return {
        "preflight_passed": not reasons,
        "blocked_reasons": reasons,
        "source_bounded_local_chat_smoke_receipt": smoke_receipt.get("receipt_path") if smoke_receipt else None,
        "prior_bounded_local_chat_smoke_passed": bounded_chat_smoke_passed(smoke_receipt),
        "prompt_valid": valid_prompt,
        "prompt_length": len(normalized_prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "runtime_binary_present": RUNTIME_PATH.exists() and RUNTIME_PATH.is_file(),
        "model_file_present": MODEL_FILE.exists() and MODEL_FILE.is_file(),
    }


def preview_payload(prompt: str) -> dict[str, Any]:
    ensure_folders()
    valid_prompt, normalized_prompt, prompt_reason = validate_prompt(prompt)
    help_payload = load_help_payload()
    return {
        "local_chat_prompt_draft_version": "1",
        "mode": "COMMAND PREVIEW ONLY - NOT EXECUTED",
        "command_executed": False,
        "prompt": normalized_prompt,
        "prompt_valid": valid_prompt,
        "prompt_refusal_reason": prompt_reason,
        "prompt_length": len(normalized_prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "prompt_source": "human_typed_gui_or_cli_argument",
        "prompt_from_file": False,
        "prompt_from_memory": False,
        "prompt_from_model_output": False,
        "user_content_used_as_prompt": True,
        "hidden_context_added": False,
        "model_key": MODEL_KEY,
        "registered_runtime_path": path_text(RUNTIME_PATH),
        "model_file_path": path_text(MODEL_FILE),
        "n_predict": N_PREDICT,
        "command_args": command_args(normalized_prompt or "<refused-prompt>", help_payload),
        "stdin_mode": "devnull",
        "timeout_seconds": TIMEOUT_SECONDS,
        "supported_flags": help_payload.get("supported_flags", []),
        "unsupported_suggested_flags_removed": help_payload.get("unsupported_suggested_flags", []),
        "output_will_be_marked_untrusted": True,
        **safety_fields(),
        **preflight_payload(normalized_prompt),
    }


def status_payload() -> dict[str, Any]:
    ensure_folders()
    latest_smoke = latest_bounded_smoke_receipt()
    latest_draft = latest_prompt_draft_receipt()
    passed = bool(latest_draft and latest_draft.get("local_chat_prompt_draft_passed") is True)
    return {
        "local_chat_prompt_draft_version": "1",
        "module_present": True,
        "latest_bounded_local_chat_smoke_receipt": latest_smoke.get("receipt_path") if latest_smoke else None,
        "prior_bounded_local_chat_smoke_passed": bounded_chat_smoke_passed(latest_smoke),
        "latest_local_chat_prompt_draft_receipt": latest_draft.get("receipt_path") if latest_draft else None,
        "local_chat_prompt_draft_passed": passed,
        "bounded_human_prompt_enabled": passed,
        "registered_runtime_path": path_text(RUNTIME_PATH),
        "runtime_binary_present": RUNTIME_PATH.exists() and RUNTIME_PATH.is_file(),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "model_file_present": MODEL_FILE.exists() and MODEL_FILE.is_file(),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "n_predict": N_PREDICT,
        "latest_final_decision": latest_draft.get("final_decision") if latest_draft else None,
        "latest_stdout_log_path": latest_draft.get("stdout_log_path") if latest_draft else None,
        "latest_stderr_log_path": latest_draft.get("stderr_log_path") if latest_draft else None,
        "latest_output_summary": read_text_bounded(repo_path(latest_draft.get("stdout_log_path")), 1800) if latest_draft else "",
        "next_safe_action": latest_draft.get("next_safe_action") if latest_draft else "ENGEL_AI_LOCAL_CHAT_PANEL_HUMAN_PROMPT_DRAFT_V1",
        **safety_fields(),
    }


def stop_started_process(process: subprocess.Popen[str]) -> tuple[str, bool]:
    if process.poll() is not None:
        return "already_exited", False
    try:
        process.terminate()
        process.communicate(timeout=TERMINATE_GRACE_SECONDS)
        return "terminated_after_timeout", False
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.communicate(timeout=KILL_GRACE_SECONDS)
            return "killed_after_timeout", True
        except subprocess.TimeoutExpired:
            return "kill_attempt_timed_out", True
    except OSError:
        return "terminate_failed", True


def run_bounded_process(args: list[str], timeout: int = TIMEOUT_SECONDS) -> ExecutionResult:
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            args,
            cwd=str(RUNTIME_PATH.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            stdout_text, stdout_truncated = bounded_text(stdout)
            stderr_text, stderr_truncated = bounded_text(stderr)
            return ExecutionResult(True, True, True, timeout, process.returncode, stdout_text, stderr_text, stdout_truncated, stderr_truncated, False, False, False, process.pid, "none")
        except subprocess.TimeoutExpired as exc:
            cleanup_action, orphan = stop_started_process(process)
            stdout_text, stdout_truncated = bounded_text(exc.stdout)
            stderr_text, stderr_truncated = bounded_text(exc.stderr)
            return ExecutionResult(True, True, False, timeout, process.poll(), stdout_text, stderr_text, stdout_truncated, stderr_truncated, True, False, orphan, process.pid, cleanup_action, "timeout")
    except KeyboardInterrupt:
        cleanup_action = None
        orphan = False
        if process is not None:
            cleanup_action, orphan = stop_started_process(process)
        return ExecutionResult(True, process is not None, False, timeout, 130, "", "", False, False, False, True, orphan, process.pid if process is not None else None, cleanup_action, "keyboard_interrupt")
    except OSError as exc:
        return ExecutionResult(False, False, False, timeout, None, "", "", False, False, False, False, False, error=str(exc))


def write_log_pair(prefix: str, stdout_text: str, stderr_text: str) -> tuple[Path, Path]:
    stdout_path = LOG_DIR / f"{prefix}_stdout.txt"
    stderr_path = LOG_DIR / f"{prefix}_stderr.txt"
    write_lf_text(stdout_path, stdout_text)
    write_lf_text(stderr_path, stderr_text)
    return stdout_path, stderr_path


def base_receipt(created_at: str, approval_verified: bool, prompt: str, help_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    smoke_receipt = latest_bounded_smoke_receipt()
    help_data = help_payload or load_help_payload()
    return {
        "local_chat_prompt_draft_version": "1",
        "created_at": created_at,
        "created_by": "Engel AI Local Chat Prompt Draft",
        "source_bounded_local_chat_smoke_receipt": smoke_receipt.get("receipt_path") if smoke_receipt else None,
        "prior_bounded_local_chat_smoke_passed": bounded_chat_smoke_passed(smoke_receipt),
        "approval_token_name": APPROVAL_TOKEN,
        "approval_token_verified": approval_verified,
        "model_key": MODEL_KEY,
        "registered_runtime_path": path_text(RUNTIME_PATH),
        "model_file_path": path_text(MODEL_FILE),
        "prompt": prompt,
        "prompt_length": len(prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "prompt_source": "human_typed_gui_or_cli_argument",
        "prompt_from_file": False,
        "prompt_from_memory": False,
        "prompt_from_model_output": False,
        "user_content_used_as_prompt": True,
        "hidden_context_added": False,
        "command_args": command_args(prompt, help_data),
        "supported_flags": help_data.get("supported_flags", []),
        "unsupported_suggested_flags_removed": help_data.get("unsupported_suggested_flags", []),
        "stdin_mode": "devnull",
        "timeout_seconds": TIMEOUT_SECONDS,
        "n_predict": N_PREDICT,
        "continued_conversation": False,
        **safety_fields(),
    }


def persist_receipt(receipt: dict[str, Any], created_at: str) -> dict[str, Any]:
    ensure_folders()
    prefix = f"LOCAL_CHAT_PROMPT_DRAFT_{stamp(created_at)}_{MODEL_KEY}"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    if receipt.get("stdout_log_path") is None:
        stdout_path, stderr_path = write_log_pair(prefix, "", "")
        receipt["stdout_log_path"] = project_relative(stdout_path)
        receipt["stderr_log_path"] = project_relative(stderr_path)
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    receipt["receipt_path"] = project_relative(receipt_path)
    write_lf_text(PLAN_REPORT_DIR / f"{prefix}.md", render_report(receipt))
    write_lf_text(CODEX_REPORT, render_report(receipt))
    return receipt


def blocked_receipt(reason: str, prompt: str, approval_verified: bool, write_receipt: bool) -> dict[str, Any]:
    created_at = now_utc()
    help_payload = load_help_payload()
    receipt = {
        **base_receipt(created_at, approval_verified, prompt, help_payload),
        "command_executed": False,
        "runtime_process_started": False,
        "runtime_process_exited": False,
        "exit_code": None,
        "timed_out": False,
        "interrupted": False,
        "orphan_process_detected": False,
        "output_captured": False,
        "stdout_truncated": False,
        "stderr_truncated": False,
        "stdout_log_path": None,
        "stderr_log_path": None,
        "local_chat_prompt_draft_passed": False,
        "bounded_human_prompt_enabled": False,
        "next_safe_action": NEXT_FAILURE_ACTION,
        "blocked_reason": reason,
        "final_decision": FINAL_DECISION_BLOCKED,
    }
    if write_receipt:
        return persist_receipt(receipt, created_at)
    return receipt


def run_prompt_draft(prompt: str | None, approval: str | None) -> dict[str, Any]:
    ensure_folders()
    valid_prompt, normalized_prompt, prompt_reason = validate_prompt(prompt)
    if not valid_prompt:
        return blocked_receipt(prompt_reason, normalized_prompt, approval_verified=approval == APPROVAL_TOKEN, write_receipt=False)
    if approval != APPROVAL_TOKEN:
        return blocked_receipt("missing or wrong approval token", normalized_prompt, approval_verified=False, write_receipt=False)

    preflight = preflight_payload(normalized_prompt)
    if not preflight["preflight_passed"]:
        return blocked_receipt("; ".join(preflight["blocked_reasons"]), normalized_prompt, approval_verified=True, write_receipt=True)

    before_processes = list_runtime_processes()
    if before_processes:
        return blocked_receipt("llama process already running before prompt draft", normalized_prompt, approval_verified=True, write_receipt=True)

    help_payload = load_help_payload()
    if not help_payload.get("help_supported"):
        return blocked_receipt("runtime help check failed: " + str(help_payload.get("help_error")), normalized_prompt, approval_verified=True, write_receipt=True)

    created_at = now_utc()
    args = command_args(normalized_prompt, help_payload)
    result = run_bounded_process(args, TIMEOUT_SECONDS)
    after_processes = list_runtime_processes()
    orphan = bool(result.orphan_process_detected or after_processes)
    stdout_path, stderr_path = write_log_pair(f"LOCAL_CHAT_PROMPT_DRAFT_{stamp(created_at)}_{MODEL_KEY}", result.stdout_text, result.stderr_text)
    output_captured = bool(result.stdout_text or result.stderr_text)
    risks = detect_output_risks(result.stdout_text, result.stderr_text)
    passed = bool(
        result.command_executed
        and result.runtime_process_started
        and result.runtime_process_exited
        and result.exit_code == 0
        and result.timed_out is False
        and result.interrupted is False
        and orphan is False
        and output_captured
        and not risks["server_startup_detected"]
        and not risks["persistent_chat_loop_detected"]
    )
    receipt = {
        **base_receipt(created_at, approval_verified=True, prompt=normalized_prompt, help_payload=help_payload),
        "command_executed": result.command_executed,
        "runtime_process_started": result.runtime_process_started,
        "runtime_process_exited": result.runtime_process_exited,
        "runtime_process_id": result.runtime_process_id,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "interrupted": result.interrupted,
        "orphan_process_detected": orphan,
        "runtime_processes_before": before_processes,
        "runtime_processes_after": after_processes,
        "cleanup_action": result.cleanup_action,
        "error": result.error,
        "stdout_log_path": project_relative(stdout_path),
        "stderr_log_path": project_relative(stderr_path),
        "stdout_truncated": result.stdout_truncated,
        "stderr_truncated": result.stderr_truncated,
        "output_captured": output_captured,
        "fatal_server_markers": risks["fatal_server_markers"],
        "fatal_interactive_markers": risks["fatal_interactive_markers"],
        "disqualifying_interactive_markers_found": risks["disqualifying_interactive_markers_found"],
        "local_chat_prompt_draft_passed": passed,
        "bounded_human_prompt_enabled": passed,
        "next_safe_action": NEXT_SUCCESS_ACTION if passed else NEXT_FAILURE_ACTION,
        "final_decision": FINAL_DECISION_SUCCESS if passed else FINAL_DECISION_FAILURE,
    }
    return persist_receipt(receipt, created_at)


def render_report(receipt: dict[str, Any] | None = None) -> str:
    data = receipt or latest_prompt_draft_receipt() or status_payload()
    ran = bool(data.get("command_executed") is True)
    passed = bool(data.get("local_chat_prompt_draft_passed") is True)
    return (
        "# ENGEL_AI_LOCAL_CHAT_PANEL_HUMAN_PROMPT_DRAFT_V1\n\n"
        "## Summary\n"
        "Implemented one approval-gated bounded human prompt draft path for the existing Companion Local AI tab. "
        "The prompt is short, human-typed, reviewed in the panel, and executed only through `engel_ai_local_chat_prompt_draft.run_prompt_draft(...)`.\n\n"
        "## Prompt Draft Run\n"
        f"- Prompt draft run executed: `{ran}`\n"
        f"- Prompt length: `{data.get('prompt_length')}`\n"
        f"- Prompt max length: `{PROMPT_MAX_LENGTH}`\n"
        f"- Result passed: `{passed}`\n"
        f"- Final decision: `{data.get('final_decision', 'not run yet')}`\n"
        f"- Output captured: `{data.get('output_captured')}`\n"
        f"- Output marked untrusted: `{data.get('output_marked_untrusted', True)}`\n"
        f"- Model output trusted: `{data.get('model_output_trusted', False)}`\n"
        f"- Orphan process detected: `{data.get('orphan_process_detected')}`\n\n"
        "## Runtime And Model\n"
        f"- Runtime path: `{data.get('registered_runtime_path', path_text(RUNTIME_PATH))}`\n"
        f"- Model key: `{MODEL_KEY}`\n"
        f"- Model path: `{data.get('model_file_path', path_text(MODEL_FILE))}`\n"
        f"- Prediction bound: `{N_PREDICT}`\n\n"
        "## Evidence\n"
        f"- Receipt: `{data.get('receipt_path') or data.get('latest_local_chat_prompt_draft_receipt', '')}`\n"
        f"- Stdout log: `{data.get('stdout_log_path') or data.get('latest_stdout_log_path', '')}`\n"
        f"- Stderr log: `{data.get('stderr_log_path') or data.get('latest_stderr_log_path', '')}`\n\n"
        "## Companion Panel\n"
        "- GUI host: `engel_companion.py`\n"
        "- Existing tab: `Local AI`\n"
        "- Section title: `Engel Local AI â€” Human Prompt Draft`\n"
        "- Approval token stored: `False`\n"
        "- Token clears after use: `True`\n"
        "- Prompt source: `human_typed_gui_or_cli_argument`\n"
        "- Output preview label: `UNTRUSTED LOCAL MODEL OUTPUT`\n\n"
        "## Readiness\n"
        "- runtime_ready_for_inference: `False`\n"
        "- open_chat_enabled: `False`\n"
        "- chat_enabled: `False`\n"
        "- persistent_chat_loop_enabled: `False`\n"
        "- server_enabled: `False`\n"
        "- trusted_memory_write_enabled: `False`\n"
        f"- next_safe_action: `{data.get('next_safe_action', NEXT_FAILURE_ACTION)}`\n\n"
        "## Verification Results\n"
        "- Targeted verifier: pending until final verification run.\n"
        "- Full Codex verifier result: pending until final verification run.\n\n"
        "## Packaging\n"
        "Packaging skipped.\n\n"
        "## Safety Summary\n"
        "This phase adds one bounded human prompt draft/review path only. It does not enable open-ended chat, persistent chat, "
        "server mode, trusted-memory writes, approved-memory writes, startup auto-load, provider calls, larger models, or model output trust.\n"
    )


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists():
        write_lf_text(CODEX_REPORT, render_report(None))


def print_text(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI local chat prompt draft gate.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    preview_parser = sub.add_parser("preview")
    preview_parser.add_argument("--prompt", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--prompt", required=True)
    run_parser.add_argument("--approval", default=None)
    sub.add_parser("json")
    args = parser.parse_args(argv)

    if args.command == "status":
        write_initial_report()
        print_text(status_payload())
        return 0
    if args.command == "preview":
        write_initial_report()
        print_text(preview_payload(args.prompt))
        return 0
    if args.command == "run":
        payload = run_prompt_draft(args.prompt, args.approval)
        print_text(payload)
        return 0 if payload.get("approval_token_verified") is True else 2
    if args.command == "json":
        write_initial_report()
        print_text({"status": status_payload(), "preview": preview_payload("hello"), "latest_receipt": latest_prompt_draft_receipt()})
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
