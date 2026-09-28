from __future__ import annotations

import argparse
import csv
import io
import os
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

APPROVAL_TOKEN = "APPROVE_BOUNDED_LOCAL_CHAT_SMOKE"
SOURCE_FILTER_TUNING_COMMIT = "5a2b1bc78748b12098d559a54a55849be1c66b12"
MODEL_KEY = "tiny_seed"
FIXED_PROMPT = "You are Engel local smoke test. Answer in one short sentence: I am local."
EXPECTED_PHRASE = "I am local"
N_PREDICT = 24
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

FILTER_TUNING_RECEIPT_DIR = PROJECT_ROOT / "reports" / "ai_first_response_output_filter_tuning" / "receipts"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_bounded_local_chat_smoke"
LOG_DIR = REPORT_ROOT / "logs"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_BOUNDED_LOCAL_CHAT_ENABLE_V1.md"

FINAL_DECISION_SUCCESS = "BOUNDED LOCAL CHAT SMOKE PASSED - OUTPUT UNTRUSTED - NO PERSISTENT CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_FAILURE = "BOUNDED LOCAL CHAT SMOKE FAILED - OUTPUT UNTRUSTED - NO PERSISTENT CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_BLOCKED = "BOUNDED LOCAL CHAT SMOKE BLOCKED - OUTPUT UNTRUSTED - NO PERSISTENT CHAT LOOP - NO TRUSTED MEMORY WRITE"
NEXT_SUCCESS_ACTION = "ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_V1"
NEXT_FAILURE_ACTION = "review bounded local chat smoke logs or adjust bounded command style"

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
    example = EXAMPLE_DIR / "BOUNDED_LOCAL_CHAT_SMOKE_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "bounded_local_chat_smoke_version": "1",
                    "example_only": True,
                    "model_key": MODEL_KEY,
                    "prompt": FIXED_PROMPT,
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
        "open_chat_enabled": False,
        "chat_enabled": False,
        "server_enabled": False,
        "persistent_chat_loop_enabled": False,
        "auto_load_enabled": False,
        "runtime_ready_for_inference": False,
        "inference_enabled": False,
    }


def latest_filter_tuning_receipt() -> dict[str, Any] | None:
    if not FILTER_TUNING_RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(FILTER_TUNING_RECEIPT_DIR.glob("FIRST_RESPONSE_OUTPUT_FILTER_TUNING_*.json")):
        data = read_json(path)
        if data.get("first_response_output_filter_tuning_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def latest_chat_smoke_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("BOUNDED_LOCAL_CHAT_SMOKE_*.json")):
        data = read_json(path)
        if data.get("bounded_local_chat_smoke_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def prior_first_response_passed(receipt: dict[str, Any] | None = None) -> bool:
    data = receipt or latest_filter_tuning_receipt()
    return bool(
        data
        and data.get("diagnosis_classification") == "clean_single_turn_exit_but_filter_too_strict"
        and data.get("first_response_smoke_passed_after_tuning_preview") is True
        and data.get("output_marked_untrusted") is True
        and data.get("runtime_ready_for_inference") is False
        and data.get("chat_enabled") is False
    )


def list_runtime_processes() -> list[dict[str, str]]:
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


def command_args(help_payload: dict[str, Any] | None = None) -> list[str]:
    supported_flags = list((help_payload or load_help_payload()).get("supported_flags", []))
    return [
        path_text(RUNTIME_PATH),
        "-m",
        path_text(MODEL_FILE),
        "-p",
        FIXED_PROMPT,
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
    prompt_loop_count = 0
    expected_index = combined.find(EXPECTED_PHRASE.lower())
    if expected_index >= 0:
        tail = combined[expected_index + len(EXPECTED_PHRASE) :]
        prompt_loop_count = tail.count("\n> ") + tail.count("\r\n> ")
    if prompt_loop_count >= 2:
        interactive_hits.append("repeated prompt marker")
    return {
        "fatal_server_markers": server_hits,
        "fatal_interactive_markers": sorted(set(interactive_hits)),
        "server_startup_detected": bool(server_hits),
        "persistent_chat_loop_detected": bool(interactive_hits),
        "disqualifying_interactive_markers_found": bool(interactive_hits),
    }


def preflight_payload() -> dict[str, Any]:
    filter_receipt = latest_filter_tuning_receipt()
    reasons: list[str] = []
    if not prior_first_response_passed(filter_receipt):
        reasons.append("first local response smoke is not passed after filter tuning")
    if not RUNTIME_PATH.exists() or not RUNTIME_PATH.is_file():
        reasons.append("approved runtime binary missing")
    if RUNTIME_PATH.name.lower() in FORBIDDEN_EXECUTABLE_NAMES:
        reasons.append("server executable selected")
    if not MODEL_FILE.exists() or not MODEL_FILE.is_file():
        reasons.append("selected model file missing")
    return {
        "preflight_passed": not reasons,
        "blocked_reasons": reasons,
        "source_filter_tuning_receipt": filter_receipt.get("receipt_path") if filter_receipt else None,
        "prior_first_response_smoke_passed": prior_first_response_passed(filter_receipt),
        "runtime_binary_present": RUNTIME_PATH.exists() and RUNTIME_PATH.is_file(),
        "model_file_present": MODEL_FILE.exists() and MODEL_FILE.is_file(),
    }


def preview_payload() -> dict[str, Any]:
    ensure_folders()
    preflight = preflight_payload()
    help_payload = load_help_payload()
    return {
        "bounded_local_chat_smoke_version": "1",
        "mode": "COMMAND PREVIEW ONLY - NOT EXECUTED",
        "command_executed": False,
        "fixed_prompt": FIXED_PROMPT,
        "user_content_used_as_prompt": False,
        "model_key": MODEL_KEY,
        "registered_runtime_path": path_text(RUNTIME_PATH),
        "model_file_path": path_text(MODEL_FILE),
        "n_predict": N_PREDICT,
        "command_args": command_args(help_payload),
        "stdin_mode": "devnull",
        "timeout_seconds": TIMEOUT_SECONDS,
        "suggested_flags": SUGGESTED_FLAGS,
        "supported_flags": help_payload.get("supported_flags", []),
        "unsupported_suggested_flags_removed": help_payload.get("unsupported_suggested_flags", []),
        "output_will_be_marked_untrusted": True,
        **safety_fields(),
        **preflight,
    }


def status_payload() -> dict[str, Any]:
    ensure_folders()
    latest_filter = latest_filter_tuning_receipt()
    latest_smoke = latest_chat_smoke_receipt()
    return {
        "bounded_local_chat_smoke_version": "1",
        "module_present": True,
        "latest_filter_tuning_receipt": latest_filter.get("receipt_path") if latest_filter else None,
        "prior_first_response_smoke_passed": prior_first_response_passed(latest_filter),
        "latest_bounded_local_chat_smoke_receipt": latest_smoke.get("receipt_path") if latest_smoke else None,
        "bounded_local_chat_smoke_passed": bool(latest_smoke and latest_smoke.get("bounded_local_chat_smoke_passed") is True),
        "registered_runtime_path": path_text(RUNTIME_PATH),
        "runtime_binary_present": RUNTIME_PATH.exists() and RUNTIME_PATH.is_file(),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "model_file_present": MODEL_FILE.exists() and MODEL_FILE.is_file(),
        "fixed_prompt": FIXED_PROMPT,
        "latest_final_decision": latest_smoke.get("final_decision") if latest_smoke else None,
        "latest_stdout_log_path": latest_smoke.get("stdout_log_path") if latest_smoke else None,
        "latest_stderr_log_path": latest_smoke.get("stderr_log_path") if latest_smoke else None,
        "latest_output_summary": read_text_bounded(repo_path(latest_smoke.get("stdout_log_path")), 1800) if latest_smoke else "",
        "next_safe_action": latest_smoke.get("next_safe_action") if latest_smoke else "ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1",
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
            return ExecutionResult(
                command_executed=True,
                runtime_process_started=True,
                runtime_process_exited=True,
                timeout_seconds=timeout,
                exit_code=process.returncode,
                stdout_text=stdout_text,
                stderr_text=stderr_text,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
                timed_out=False,
                interrupted=False,
                orphan_process_detected=False,
                runtime_process_id=process.pid,
                cleanup_action="none",
            )
        except subprocess.TimeoutExpired as exc:
            cleanup_action, orphan = stop_started_process(process)
            stdout_text, stdout_truncated = bounded_text(exc.stdout)
            stderr_text, stderr_truncated = bounded_text(exc.stderr)
            return ExecutionResult(
                command_executed=True,
                runtime_process_started=True,
                runtime_process_exited=False,
                timeout_seconds=timeout,
                exit_code=process.poll(),
                stdout_text=stdout_text,
                stderr_text=stderr_text,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
                timed_out=True,
                interrupted=False,
                orphan_process_detected=orphan,
                runtime_process_id=process.pid,
                cleanup_action=cleanup_action,
                error="timeout",
            )
    except KeyboardInterrupt:
        cleanup_action = None
        orphan = False
        if process is not None:
            cleanup_action, orphan = stop_started_process(process)
        return ExecutionResult(
            command_executed=True,
            runtime_process_started=process is not None,
            runtime_process_exited=False,
            timeout_seconds=timeout,
            exit_code=130,
            stdout_text="",
            stderr_text="",
            stdout_truncated=False,
            stderr_truncated=False,
            timed_out=False,
            interrupted=True,
            orphan_process_detected=orphan,
            runtime_process_id=process.pid if process is not None else None,
            cleanup_action=cleanup_action,
            error="keyboard_interrupt",
        )
    except OSError as exc:
        return ExecutionResult(
            command_executed=False,
            runtime_process_started=False,
            runtime_process_exited=False,
            timeout_seconds=timeout,
            exit_code=None,
            stdout_text="",
            stderr_text="",
            stdout_truncated=False,
            stderr_truncated=False,
            timed_out=False,
            interrupted=False,
            orphan_process_detected=False,
            error=str(exc),
        )


def write_log_pair(prefix: str, stdout_text: str, stderr_text: str) -> tuple[Path, Path]:
    stdout_path = LOG_DIR / f"{prefix}_stdout.txt"
    stderr_path = LOG_DIR / f"{prefix}_stderr.txt"
    write_lf_text(stdout_path, stdout_text)
    write_lf_text(stderr_path, stderr_text)
    return stdout_path, stderr_path


def base_receipt(created_at: str, approval_verified: bool, help_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    filter_receipt = latest_filter_tuning_receipt()
    help_data = help_payload or load_help_payload()
    return {
        "bounded_local_chat_smoke_version": "1",
        "created_at": created_at,
        "created_by": "Engel AI Bounded Local Chat Smoke",
        "source_filter_tuning_commit": SOURCE_FILTER_TUNING_COMMIT,
        "source_filter_tuning_receipt": filter_receipt.get("receipt_path") if filter_receipt else None,
        "prior_first_response_smoke_passed": prior_first_response_passed(filter_receipt),
        "prompt": FIXED_PROMPT,
        "prompt_is_fixed_test_prompt": True,
        "user_content_used_as_prompt": False,
        "model_key": MODEL_KEY,
        "registered_runtime_path": path_text(RUNTIME_PATH),
        "model_file_path": path_text(MODEL_FILE),
        "approval_token_name": APPROVAL_TOKEN,
        "approval_token_verified": approval_verified,
        "command_args": command_args(help_data),
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
    prefix = f"BOUNDED_LOCAL_CHAT_SMOKE_{stamp(created_at)}_{MODEL_KEY}"
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


def blocked_receipt(reason: str, approval_verified: bool, write_receipt: bool) -> dict[str, Any]:
    created_at = now_utc()
    help_payload = load_help_payload()
    receipt = {
        **base_receipt(created_at, approval_verified, help_payload),
        "command_executed": False,
        "runtime_process_started": False,
        "runtime_process_exited": False,
        "exit_code": None,
        "timed_out": False,
        "interrupted": False,
        "orphan_process_detected": False,
        "output_captured": False,
        "expected_phrase_seen": False,
        "stdout_truncated": False,
        "stderr_truncated": False,
        "stdout_log_path": None,
        "stderr_log_path": None,
        "bounded_local_chat_smoke_passed": False,
        "next_safe_action": NEXT_FAILURE_ACTION,
        "blocked_reason": reason,
        "final_decision": FINAL_DECISION_BLOCKED,
    }
    if write_receipt:
        return persist_receipt(receipt, created_at)
    return receipt


def run_chat_smoke(approval: str | None) -> dict[str, Any]:
    ensure_folders()
    if approval != APPROVAL_TOKEN:
        return blocked_receipt("missing or wrong approval token", approval_verified=False, write_receipt=False)

    preflight = preflight_payload()
    if not preflight["preflight_passed"]:
        return blocked_receipt("; ".join(preflight["blocked_reasons"]), approval_verified=True, write_receipt=True)

    before_processes = list_runtime_processes()
    if before_processes:
        return blocked_receipt("llama process already running before bounded smoke", approval_verified=True, write_receipt=True)

    help_payload = load_help_payload()
    if not help_payload.get("help_supported"):
        return blocked_receipt("runtime help check failed: " + str(help_payload.get("help_error")), approval_verified=True, write_receipt=True)

    created_at = now_utc()
    args = command_args(help_payload)
    result = run_bounded_process(args, TIMEOUT_SECONDS)
    after_processes = list_runtime_processes()
    orphan = bool(result.orphan_process_detected or after_processes)
    stdout_path, stderr_path = write_log_pair(f"BOUNDED_LOCAL_CHAT_SMOKE_{stamp(created_at)}_{MODEL_KEY}", result.stdout_text, result.stderr_text)
    output_captured = bool(result.stdout_text or result.stderr_text)
    expected_phrase_seen = EXPECTED_PHRASE.lower() in (result.stdout_text + "\n" + result.stderr_text).lower()
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
        **base_receipt(created_at, approval_verified=True, help_payload=help_payload),
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
        "expected_phrase_seen": expected_phrase_seen,
        "fatal_server_markers": risks["fatal_server_markers"],
        "fatal_interactive_markers": risks["fatal_interactive_markers"],
        "disqualifying_interactive_markers_found": risks["disqualifying_interactive_markers_found"],
        "bounded_local_chat_smoke_passed": passed,
        "next_safe_action": NEXT_SUCCESS_ACTION if passed else NEXT_FAILURE_ACTION,
        "final_decision": FINAL_DECISION_SUCCESS if passed else FINAL_DECISION_FAILURE,
    }
    return persist_receipt(receipt, created_at)


def render_report(receipt: dict[str, Any] | None = None) -> str:
    data = receipt or latest_chat_smoke_receipt() or status_payload()
    smoke_ran = bool(data.get("command_executed") is True)
    passed = bool(data.get("bounded_local_chat_smoke_passed") is True)
    stdout_path = str(data.get("stdout_log_path") or "")
    stderr_path = str(data.get("stderr_log_path") or "")
    receipt_path = str(data.get("receipt_path") or data.get("latest_bounded_local_chat_smoke_receipt") or "")
    final_decision = str(data.get("final_decision") or ("passed" if passed else "not run yet"))
    return (
        "# ENGEL_AI_BOUNDED_LOCAL_CHAT_ENABLE_V1\n\n"
        "## Summary\n"
        "Implemented the bounded local chat smoke module and connected the existing Companion Local AI tab to bounded-smoke status. "
        "The GUI remains a fail-closed reader; the CLI module owns the only approved one-shot tiny_seed run.\n\n"
        "## Smoke Result\n"
        f"- Smoke ran: `{smoke_ran}`\n"
        f"- Bounded local chat smoke passed: `{passed}`\n"
        f"- Final decision: `{final_decision}`\n"
        f"- Output captured: `{data.get('output_captured')}`\n"
        f"- Output marked untrusted: `{data.get('output_marked_untrusted', True)}`\n"
        f"- Model output trusted: `{data.get('model_output_trusted', False)}`\n"
        f"- Orphan process detected: `{data.get('orphan_process_detected')}`\n\n"
        "## Runtime And Model\n"
        f"- Runtime path: `{data.get('registered_runtime_path', path_text(RUNTIME_PATH))}`\n"
        f"- Model key: `{MODEL_KEY}`\n"
        f"- Model path: `{data.get('model_file_path', path_text(MODEL_FILE))}`\n"
        f"- Fixed prompt: `{FIXED_PROMPT}`\n"
        f"- Prediction bound: `{N_PREDICT}`\n\n"
        "## Evidence\n"
        f"- Receipt: `{receipt_path}`\n"
        f"- Stdout log: `{stdout_path}`\n"
        f"- Stderr log: `{stderr_path}`\n\n"
        "## Companion Panel\n"
        "- GUI host: `engel_companion.py`\n"
        "- Existing tab: `Local AI`\n"
        "- Run button: `disabled / fail-closed`\n"
        "- GUI model run on open/refresh: `False`\n"
        "- GUI approval token storage: `False`\n"
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
        "This phase enables one bounded local chat smoke only. It does not enable open chat, persistent chat, server mode, "
        "trusted-memory writes, approved-memory writes, startup auto-load, provider calls, larger models, or model output trust.\n"
    )


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists():
        write_lf_text(CODEX_REPORT, render_report(None))


def print_text(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI bounded local chat smoke gate.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("preview")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--approval", default=None)
    sub.add_parser("json")
    args = parser.parse_args(argv)

    if args.command == "status":
        write_initial_report()
        print_text(status_payload())
        return 0
    if args.command == "preview":
        write_initial_report()
        print_text(preview_payload())
        return 0
    if args.command == "run":
        payload = run_chat_smoke(args.approval)
        print_text(payload)
        return 0 if payload.get("approval_token_verified") is True else 2
    if args.command == "json":
        write_initial_report()
        print_text({"status": status_payload(), "preview": preview_payload(), "latest_receipt": latest_chat_smoke_receipt()})
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
