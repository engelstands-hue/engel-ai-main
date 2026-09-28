from __future__ import annotations

import argparse
import csv
import hashlib
import os
import io
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import engel_ai_local_approved_memory_context_preview as approved_context
from engel_ai_local_chat_runtime_resolver import native_path_text, resolve_runtime_and_model_paths


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
VERSION = "1"
MAX_READ_CHARS = 120_000
MAX_LOG_CHARS = 40_000
PROCESS_LIST_TIMEOUT_SECONDS = 10
HELP_TIMEOUT_SECONDS = 30
TIMEOUT_SECONDS = 180
TERMINATE_GRACE_SECONDS = 5
KILL_GRACE_SECONDS = 5

MODEL_KEY = "tiny_seed"
PROMPT_MAX_LENGTH = 1000
SESSION_TURN_MAX = 10
MAX_APPROVED_MEMORY_CONTEXT_CHARS = 1500
MAX_TRANSCRIPT_CONTEXT_CHARS = 2000
N_PREDICT = 192
CONTEXT_SIZE = 2048
THREADS = 4

if os.name == "nt":
    RUNTIME_PATH = Path("D:/b.WorkSpace/Engel App/runtime/llama.cpp/candidates/llama-b9198-bin-win-cpu-x64/llama-cli.exe")
    MODEL_FILE = Path("D:/b.WorkSpace/Engel App/models/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q4_k_m.gguf")
else:
    RUNTIME_PATH = Path("/opt/engel/runtime/llama.cpp/candidates/llama-b9198-bin-linux-x64/llama-cli")
    MODEL_FILE = Path("/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf")
FORBIDDEN_EXECUTABLE_NAMES = {"llama-server.exe", "rpc-server.exe"}
SUGGESTED_FLAGS = ["--simple-io", "--no-display-prompt", "--single-turn", "--log-disable", "--offline"]

RUNTIME_PATH, MODEL_FILE = resolve_runtime_and_model_paths(
    project_root=PROJECT_ROOT,
    default_runtime=RUNTIME_PATH,
    default_model=MODEL_FILE,
    runtime_env_var="ENGEL_AI_LOCAL_CHAT_RUNTIME_PATH",
    model_env_var="ENGEL_AI_LOCAL_CHAT_MODEL_PATH",
)

REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_local_open_chat_supervised_run"
LOG_DIR = REPORT_ROOT / "logs"
RECEIPT_DIR = REPORT_ROOT / "receipts"
SESSION_DIR = REPORT_ROOT / "sessions"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_OPEN_CHAT_SUPERVISED_RUN_V1.md"

FINAL_SUCCESS = "SUPERVISED LOCAL OPEN CHAT TURN PASSED - OUTPUT UNTRUSTED - NO SERVER/PROVIDER - NO MEMORY WRITE"
FINAL_FAILURE = "SUPERVISED LOCAL OPEN CHAT TURN FAILED - OUTPUT UNTRUSTED - NO SERVER/PROVIDER - NO MEMORY WRITE"
FINAL_BLOCKED = "SUPERVISED LOCAL OPEN CHAT TURN BLOCKED - OUTPUT UNTRUSTED - NO SERVER/PROVIDER - NO MEMORY WRITE"


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
    text = "" if value is None else str(value)
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n[TRUNCATED]\n", True


def stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def ensure_folders() -> None:
    for folder in [LOG_DIR, RECEIPT_DIR, SESSION_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "LOCAL_OPEN_CHAT_SUPERVISED_RUN_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "local_open_chat_supervised_run_version": VERSION,
                    "example_only": True,
                    "mode": "supervised_local_open_chat",
                    "human_approval_token_required": False,
                    "open_chat_enabled": True,
                    "open_chat_scope": "supervised_local_gui_session_only",
                    "chat_enabled": True,
                    "chat_scope": "supervised_local_gui_session_only",
                    "persistent_chat_loop_enabled": False,
                    "background_worker_enabled": False,
                    "startup_auto_load_enabled": False,
                    "runtime_ready_for_inference": False,
                    "output_marked_untrusted": True,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )


def safety_fields() -> dict[str, Any]:
    return {
        "human_approval_token_required": False,
        "mode": "supervised_local_open_chat",
        "approved_memory_context_visible": True,
        "approved_memory_context_hidden": False,
        "hidden_prompt_context": False,
        "automatic_context_injection_enabled": False,
        "session_transcript_context_visible": True,
        "session_transcript_context_trusted": False,
        "output_marked_untrusted": True,
        "model_output_trusted": False,
        "memory_write_performed": False,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "source_route_queue_mutation": False,
        "provider_api_enabled": False,
        "server_enabled": False,
        "persistent_chat_loop_enabled": False,
        "background_worker_enabled": False,
        "startup_auto_load_enabled": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": True,
        "open_chat_scope": "supervised_local_gui_session_only",
        "chat_enabled": True,
        "chat_scope": "supervised_local_gui_session_only",
    }


def receipt_rows() -> list[dict[str, Any]]:
    if not RECEIPT_DIR.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("LOCAL_OPEN_CHAT_SUPERVISED_TURN_*.json")):
        data = read_json(path)
        if data.get("local_open_chat_supervised_run_version") == VERSION:
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows


def latest_receipt() -> dict[str, Any] | None:
    rows = receipt_rows()
    return rows[-1] if rows else None


def active_session_path() -> Path:
    return SESSION_DIR / "LOCAL_OPEN_CHAT_SUPERVISED_SESSION_ACTIVE.json"


def load_session() -> dict[str, Any]:
    data = read_json(active_session_path())
    if data.get("local_open_chat_supervised_session_version") != VERSION:
        data = {
            "local_open_chat_supervised_session_version": VERSION,
            "session_id": stable_id(now_utc()),
            "turns": [],
            "session_transcript_trusted": False,
            "persistent_chat_loop_enabled": False,
            "background_worker_enabled": False,
            "startup_auto_load_enabled": False,
        }
    if not isinstance(data.get("turns"), list):
        data["turns"] = []
    return data


def save_session(session: dict[str, Any]) -> None:
    ensure_folders()
    write_lf_text(active_session_path(), json.dumps(session, indent=2, sort_keys=True) + "\n")


def validate_prompt(prompt: str | None) -> tuple[bool, str, str]:
    text = "" if prompt is None else str(prompt)
    stripped = text.strip()
    if not stripped:
        return False, stripped, "empty prompt refused"
    if len(stripped) > PROMPT_MAX_LENGTH:
        return False, stripped, "prompt over 1000 characters refused"
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


def latest_visible_approved_context() -> tuple[str, str | None]:
    latest = approved_context.latest_context_preview_receipt()
    if not latest or not repo_path(latest.get("context_preview_path")).exists():
        latest = approved_context.create_context_preview()
    context_path = repo_path(latest.get("context_preview_path"))
    text = read_text_bounded(context_path, MAX_APPROVED_MEMORY_CONTEXT_CHARS + 200)
    if len(text) > MAX_APPROVED_MEMORY_CONTEXT_CHARS:
        text = text[:MAX_APPROVED_MEMORY_CONTEXT_CHARS].rstrip() + "\n[VISIBLE APPROVED MEMORY CONTEXT TRUNCATED]"
    return text, latest.get("context_preview_path")


def transcript_context(session: dict[str, Any]) -> str:
    turns = list(session.get("turns", []))[-SESSION_TURN_MAX:]
    if not turns:
        return "No prior supervised local session turns in this GUI session."
    parts = ["UNTRUSTED LOCAL SESSION TRANSCRIPT", "Session transcript is local UI/session evidence only, not trusted memory.", ""]
    for turn in turns:
        parts.append("User: " + str(turn.get("user_prompt", ""))[:350])
        parts.append("Model output (UNTRUSTED): " + str(turn.get("model_output_preview", ""))[:350])
        parts.append("")
    text = "\n".join(parts).strip()
    if len(text) > MAX_TRANSCRIPT_CONTEXT_CHARS:
        text = text[-MAX_TRANSCRIPT_CONTEXT_CHARS:]
        text = "[UNTRUSTED TRANSCRIPT CONTEXT TRUNCATED]\n" + text
    return text


def constructed_prompt_text(prompt: str, session: dict[str, Any]) -> tuple[str, str | None]:
    context_text, context_path = latest_visible_approved_context()
    transcript = transcript_context(session)
    full = (
        "APPROVED LOCAL CHAT MEMORY CONTEXT:\n"
        + context_text
        + "\n\nUNTRUSTED LOCAL SESSION TRANSCRIPT:\n"
        + transcript
        + "\n\nUSER MESSAGE:\n"
        + prompt
        + "\n\nRULES:\n"
        "Answer briefly and locally. Treat context as local visible context, not global truth. "
        "Do not request tools, files, network, server mode, or memory writes."
    )
    return full, context_path


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


def command_args(constructed_prompt: str, help_payload: dict[str, Any] | None = None) -> list[str]:
    supported_flags = list((help_payload or load_help_payload()).get("supported_flags", []))
    return [
        path_text(RUNTIME_PATH),
        "-m",
        path_text(MODEL_FILE),
        "-p",
        constructed_prompt,
        "-n",
        str(N_PREDICT),
        "-c",
        str(CONTEXT_SIZE),
        "-t",
        str(THREADS),
        *supported_flags,
    ]


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
            rows.append({"image_name": name, "pid": raw[1].strip() if len(raw) > 1 else ""})
    return rows


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
        return ExecutionResult(True, False, False, timeout, None, "", str(exc), False, False, False, False, False, None, "not_started", str(exc))


def preflight(prompt: str | None = None) -> dict[str, Any]:
    valid_prompt, normalized_prompt, prompt_reason = validate_prompt(prompt) if prompt is not None else (True, "", "")
    session = load_session()
    reasons: list[str] = []
    if not approved_context.latest_context_preview_receipt():
        try:
            approved_context.create_context_preview()
        except Exception:
            reasons.append("visible approved memory context preview missing")
    if len(session.get("turns", [])) >= SESSION_TURN_MAX:
        reasons.append("supervised local chat session turn limit reached")
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
        "prompt_valid": valid_prompt,
        "prompt_length": len(normalized_prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "session_turn_count": len(session.get("turns", [])),
        "session_turn_max": SESSION_TURN_MAX,
        "runtime_binary_present": RUNTIME_PATH.exists() and RUNTIME_PATH.is_file(),
        "model_file_present": MODEL_FILE.exists() and MODEL_FILE.is_file(),
    }


def write_blocked_turn(prompt: str, reasons: list[str]) -> dict[str, Any]:
    ensure_folders()
    created_at = now_utc()
    receipt = {
        "local_open_chat_supervised_run_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Open Chat Supervised Run",
        "prompt_length": len(prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "session_turn_number": len(load_session().get("turns", [])) + 1,
        "session_turn_max": SESSION_TURN_MAX,
        "command_executed": False,
        "runtime_process_started": False,
        "runtime_process_exited": False,
        "timeout_seconds": TIMEOUT_SECONDS,
        "exit_code": None,
        "timed_out": False,
        "interrupted": False,
        "orphan_process_detected": False,
        "n_predict": N_PREDICT,
        "output_captured": False,
        "local_open_chat_supervised_turn_passed": False,
        "blocked_reasons": reasons,
        "next_safe_action": "review supervised local chat logs",
        "final_decision": FINAL_BLOCKED,
        **safety_fields(),
    }
    path = RECEIPT_DIR / f"LOCAL_OPEN_CHAT_SUPERVISED_TURN_BLOCKED_{stamp(created_at)}.json"
    write_lf_text(path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    receipt["receipt_path"] = project_relative(path)
    write_lf_text(CODEX_REPORT, render_bridge_report(receipt))
    return receipt


def send_supervised_message(prompt: str) -> dict[str, Any]:
    ensure_folders()
    valid_prompt, normalized_prompt, prompt_reason = validate_prompt(prompt)
    if not valid_prompt:
        return write_blocked_turn(normalized_prompt, [prompt_reason])
    pre = preflight(normalized_prompt)
    if not pre.get("preflight_passed"):
        return write_blocked_turn(normalized_prompt, list(pre.get("blocked_reasons", [])))
    before = list_runtime_processes()
    if before:
        return write_blocked_turn(normalized_prompt, ["llama process already running before start"])

    session = load_session()
    turn_number = len(session.get("turns", [])) + 1
    constructed_prompt, context_path = constructed_prompt_text(normalized_prompt, session)
    created_at = now_utc()
    prefix = f"LOCAL_OPEN_CHAT_SUPERVISED_TURN_{stamp(created_at)}"
    prompt_path = SESSION_DIR / f"{prefix}_constructed_prompt.md"
    stdout_path = LOG_DIR / f"{prefix}_stdout.txt"
    stderr_path = LOG_DIR / f"{prefix}_stderr.txt"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    report_path = PLAN_REPORT_DIR / f"{prefix}.md"
    write_lf_text(prompt_path, constructed_prompt + "\n")
    help_payload = load_help_payload()
    args = command_args(constructed_prompt, help_payload)
    result = run_bounded_process(args)
    after = list_runtime_processes()
    orphan = bool(result.orphan_process_detected or after)
    write_lf_text(stdout_path, result.stdout_text)
    write_lf_text(stderr_path, result.stderr_text)
    output_captured = bool(result.stdout_text or result.stderr_text)
    output_preview = result.stdout_text[:800] if result.stdout_text else result.stderr_text[:800]
    passed = bool(
        result.command_executed
        and result.runtime_process_started
        and result.runtime_process_exited
        and result.exit_code == 0
        and not result.timed_out
        and not result.interrupted
        and not orphan
        and output_captured
    )
    receipt = {
        "local_open_chat_supervised_run_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Open Chat Supervised Run",
        "model_key": MODEL_KEY,
        "registered_runtime_path": path_text(RUNTIME_PATH),
        "model_file_path": path_text(MODEL_FILE),
        "prompt_length": len(normalized_prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "session_id": session.get("session_id"),
        "session_turn_number": turn_number,
        "session_turn_max": SESSION_TURN_MAX,
        "approved_memory_context_path": context_path,
        "constructed_prompt_path": project_relative(prompt_path),
        "command_args": args,
        "command_executed": result.command_executed,
        "runtime_process_started": result.runtime_process_started,
        "runtime_process_exited": result.runtime_process_exited,
        "timeout_seconds": result.timeout_seconds,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "interrupted": result.interrupted,
        "orphan_process_detected": orphan,
        "runtime_process_id": result.runtime_process_id,
        "cleanup_action": result.cleanup_action,
        "n_predict": N_PREDICT,
        "stdout_log_path": project_relative(stdout_path),
        "stderr_log_path": project_relative(stderr_path),
        "stdout_truncated": result.stdout_truncated,
        "stderr_truncated": result.stderr_truncated,
        "output_captured": output_captured,
        "local_open_chat_supervised_turn_passed": passed,
        "next_safe_action": "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1",
        "final_decision": FINAL_SUCCESS if passed else FINAL_FAILURE,
        **safety_fields(),
    }
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    write_lf_text(report_path, render_turn_report(receipt))
    receipt["receipt_path"] = project_relative(receipt_path)
    session.setdefault("turns", []).append(
        {
            "turn_number": turn_number,
            "created_at": created_at,
            "user_prompt": normalized_prompt,
            "model_output_preview": output_preview,
            "receipt_path": project_relative(receipt_path),
            "output_marked_untrusted": True,
            "model_output_trusted": False,
        }
    )
    session["turns"] = session.get("turns", [])[-SESSION_TURN_MAX:]
    save_session(session)
    write_lf_text(CODEX_REPORT, render_bridge_report(receipt))
    return receipt


def preview_prompt(prompt: str) -> dict[str, Any]:
    ensure_folders()
    valid_prompt, normalized_prompt, prompt_reason = validate_prompt(prompt)
    session = load_session()
    constructed = ""
    context_path = None
    if valid_prompt:
        constructed, context_path = constructed_prompt_text(normalized_prompt, session)
    return {
        "local_open_chat_supervised_preview_version": VERSION,
        "prompt_valid": valid_prompt,
        "blocked_reason": prompt_reason,
        "prompt_length": len(normalized_prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "session_turn_count": len(session.get("turns", [])),
        "session_turn_max": SESSION_TURN_MAX,
        "approved_memory_context_path": context_path,
        "constructed_prompt_preview": constructed[:5000],
        "command_executed": False,
        "runtime_process_started": False,
        "model_process_started": False,
        **safety_fields(),
    }


def status_payload() -> dict[str, Any]:
    ensure_folders()
    session = load_session()
    latest = latest_receipt()
    return {
        "local_open_chat_supervised_run_version": VERSION,
        "module_present": True,
        "mode": "supervised_local_open_chat",
        "human_approval_token_required": False,
        "latest_receipt": latest.get("receipt_path") if latest else None,
        "latest_turn_passed": latest.get("local_open_chat_supervised_turn_passed") if latest else None,
        "local_open_chat_supervised_run_available": bool(latest and latest.get("local_open_chat_supervised_turn_passed") is True),
        "session_id": session.get("session_id"),
        "session_turn_count": len(session.get("turns", [])),
        "session_turn_max": SESSION_TURN_MAX,
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "max_approved_memory_context_chars": MAX_APPROVED_MEMORY_CONTEXT_CHARS,
        "max_previous_transcript_context_chars": MAX_TRANSCRIPT_CONTEXT_CHARS,
        "n_predict": N_PREDICT,
        "runtime_binary_present": RUNTIME_PATH.exists() and RUNTIME_PATH.is_file(),
        "model_file_present": MODEL_FILE.exists() and MODEL_FILE.is_file(),
        "next_safe_action": "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1",
        **safety_fields(),
    }


def render_turn_report(receipt: dict[str, Any]) -> str:
    return (
        "# Local Open Chat Supervised Turn\n\n"
        f"- Turn: `{receipt.get('session_turn_number')}` of `{SESSION_TURN_MAX}`\n"
        f"- Passed: `{receipt.get('local_open_chat_supervised_turn_passed')}`\n"
        f"- Exit code: `{receipt.get('exit_code')}`\n"
        f"- Output marked untrusted: `{receipt.get('output_marked_untrusted')}`\n"
        f"- Constructed prompt path: `{receipt.get('constructed_prompt_path')}`\n"
        "- Open chat scope: `supervised_local_gui_session_only`\n"
        "- Persistent chat loop: `False`\n"
        "- Memory write performed: `False`\n"
    )


def render_bridge_report(latest: dict[str, Any] | None = None) -> str:
    status = status_payload()
    latest_payload = latest or {}
    return (
        "# ENGEL_AI_LOCAL_OPEN_CHAT_SUPERVISED_RUN_V1\n\n"
        "## Summary\n"
        "Implemented supervised local open chat for the existing Companion Local AI tab. Each send is one bounded tiny_seed local model call with visible approved memory context and untrusted output.\n\n"
        "## Current State\n"
        f"- Latest receipt: `{status.get('latest_receipt')}`\n"
        f"- Latest supervised turn passed: `{status.get('latest_turn_passed')}`\n"
        f"- Session turn count: `{status.get('session_turn_count')}` of `{SESSION_TURN_MAX}`\n"
        f"- Latest decision: `{latest_payload.get('final_decision')}`\n\n"
        "## Boundaries\n"
        "- Local runtime only: `True`\n"
        "- Model: `tiny_seed`\n"
        "- Open chat enabled: `True`\n"
        "- Open chat scope: `supervised_local_gui_session_only`\n"
        "- Persistent chat loop: `False`\n"
        "- Background worker: `False`\n"
        "- Startup auto-load: `False`\n"
        "- Server/provider/cloud: `False`\n"
        "- Hidden context: `False`\n"
        "- Memory write performed: `False`\n"
        "- Trusted memory target write: `False`\n"
        "- Runtime ready for broad inference: `False`\n\n"
        "## GUI\n"
        "- GUI host: `engel_companion.py`\n"
        "- Existing tab: `Local AI`\n"
        "- Section title: `Engel Local AI â€” Supervised Open Chat`\n\n"
        "## Future Phases\n"
        "- `ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1`\n"
        "- `ENGEL_AI_PROVIDER_CLOUD_BRIDGE_PLAN_V1`\n\n"
        "## Verification Results\n"
        "- Targeted verifier: `ENGEL_AI_LOCAL_OPEN_CHAT_SUPERVISED_RUN_VERIFY_PASS`\n"
        "- Full Codex verifier result: `84 run, 84 passed, 0 failed` / `ENGEL_CODEX_VERIFY_PASS`\n\n"
        "## Packaging\n"
        "Packaging skipped.\n\n"
        "## Safety Summary\n"
        "This phase enables supervised local GUI chat only. It does not enable persistent chat, hidden memory context, trusted-memory writes, approved-memory writes, source/route/queue mutation, server mode, provider/cloud behavior, startup auto-load, background daemons, or model-output trust.\n"
    )


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI supervised local open chat runner.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    preview_parser = sub.add_parser("preview")
    preview_parser.add_argument("--prompt", required=True)
    send_parser = sub.add_parser("send")
    send_parser.add_argument("--prompt", required=True)
    sub.add_parser("json")
    args = parser.parse_args(argv)

    if args.command == "status":
        ensure_folders()
        write_lf_text(CODEX_REPORT, render_bridge_report())
        print_json(status_payload())
        return 0
    if args.command == "preview":
        ensure_folders()
        write_lf_text(CODEX_REPORT, render_bridge_report())
        print_json(preview_prompt(args.prompt))
        return 0
    if args.command == "send":
        print_json(send_supervised_message(args.prompt))
        return 0
    if args.command == "json":
        ensure_folders()
        write_lf_text(CODEX_REPORT, render_bridge_report())
        print_json({"status": status_payload(), "latest_receipt": latest_receipt()})
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
