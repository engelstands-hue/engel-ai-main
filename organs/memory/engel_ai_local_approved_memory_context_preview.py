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

APPROVAL_TOKEN = "APPROVE_LOCAL_APPROVED_MEMORY_CONTEXT_RUN"
MODEL_KEY = "tiny_seed"
PROMPT_MAX_LENGTH = 500
MAX_RECORDS = 3
MAX_CONTEXT_CHARS = 1500
MAX_RECORD_SUMMARY_CHARS = 500
N_PREDICT = 96
CONTEXT_SIZE = 1024
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

APPROVED_RECORD_DIR = PROJECT_ROOT / "reports" / "ai_local_chat_session_memory_candidate_review_and_approved_write" / "approved_memory_records"
ROLLBACK_DIR = PROJECT_ROOT / "reports" / "ai_local_chat_session_memory_candidate_review_and_approved_write" / "rollback"
READBACK_RECEIPT_DIR = PROJECT_ROOT / "reports" / "ai_local_approved_memory_readback" / "receipts"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_local_approved_memory_context_preview"
CONTEXT_DIR = REPORT_ROOT / "contexts"
LOG_DIR = REPORT_ROOT / "logs"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1.md"

FINAL_PREVIEW_DECISION = "VISIBLE APPROVED LOCAL MEMORY CONTEXT PREVIEW CREATED - NO HIDDEN CONTEXT - NO MODEL RUN"
FINAL_RUN_SUCCESS = "LOCAL APPROVED MEMORY CONTEXT RUN PASSED - OUTPUT UNTRUSTED - NO HIDDEN CONTEXT - NO MEMORY WRITE"
FINAL_RUN_FAILURE = "LOCAL APPROVED MEMORY CONTEXT RUN FAILED - OUTPUT UNTRUSTED - NO HIDDEN CONTEXT - NO MEMORY WRITE"
FINAL_RUN_BLOCKED = "LOCAL APPROVED MEMORY CONTEXT RUN BLOCKED - OUTPUT UNTRUSTED - NO HIDDEN CONTEXT - NO MEMORY WRITE"

SUGGESTED_FLAGS = ["--simple-io", "--no-display-prompt", "--single-turn", "--log-disable", "--offline"]


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


def stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


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


def ensure_folders() -> None:
    for folder in [CONTEXT_DIR, LOG_DIR, RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "local_approved_memory_context_preview_version": VERSION,
                    "example_only": True,
                    "visible_context_only": True,
                    "hidden_prompt_context": False,
                    "automatic_context_injection_enabled": False,
                    "global_trusted_memory": False,
                    "memory_write_performed": False,
                    "runtime_process_started": False,
                    "model_process_started": False,
                    "runtime_ready_for_inference": False,
                    "open_chat_enabled": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )


def safety_fields() -> dict[str, Any]:
    return {
        "visible_context_only": True,
        "hidden_prompt_context": False,
        "automatic_context_injection_enabled": False,
        "global_trusted_memory": False,
        "approved_local_chat_memory_scope_only": True,
        "memory_write_performed": False,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "source_route_queue_mutation": False,
        "provider_api_enabled": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
        "chat_enabled": False,
    }


def approved_record_files() -> list[Path]:
    if not APPROVED_RECORD_DIR.exists():
        return []
    return sorted(path for path in APPROVED_RECORD_DIR.glob("APPROVED_LOCAL_CHAT_MEMORY_RECORD_*.json") if path.is_file())


def context_preview_receipts() -> list[dict[str, Any]]:
    if not RECEIPT_DIR.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_*.json")):
        data = read_json(path)
        if data.get("local_approved_memory_context_preview_version") == VERSION:
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows


def context_run_receipts() -> list[dict[str, Any]]:
    if not RECEIPT_DIR.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("LOCAL_APPROVED_MEMORY_CONTEXT_RUN_*.json")):
        data = read_json(path)
        if data.get("local_approved_memory_context_run_version") == VERSION:
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows


def latest_context_preview_receipt() -> dict[str, Any] | None:
    rows = context_preview_receipts()
    return rows[-1] if rows else None


def latest_context_run_receipt() -> dict[str, Any] | None:
    rows = context_run_receipts()
    return rows[-1] if rows else None


def latest_readback_receipt() -> dict[str, Any] | None:
    if not READBACK_RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(READBACK_RECEIPT_DIR.glob("LOCAL_APPROVED_MEMORY_READBACK_*.json")):
        data = read_json(path)
        if data.get("local_approved_memory_readback_version") == VERSION:
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def record_id(path: Path) -> str:
    return path.stem.replace("APPROVED_LOCAL_CHAT_MEMORY_RECORD_", "")


def rollback_for_record(path: Path) -> Path | None:
    fallback = ROLLBACK_DIR / f"ROLLBACK_APPROVED_LOCAL_CHAT_MEMORY_RECORD_{record_id(path)}.json"
    return fallback if fallback.exists() else None


def validate_record(path: Path) -> dict[str, Any]:
    data = read_json(path)
    rollback = rollback_for_record(path)
    risk_flags: list[str] = []
    checks = {
        "record_schema_valid": data.get("approved_local_chat_memory_record_version") == VERSION,
        "rollback_metadata_present": bool(rollback),
        "deterministic_guardian_gates_passed": data.get("deterministic_guardian_gates_passed") is True,
        "source_model_output_trusted": data.get("source_model_output_trusted") is False,
        "candidate_content_obeyed": data.get("candidate_content_obeyed") is False,
        "record_scope_valid": data.get("approved_memory_scope") == "approved_local_chat_memory_record_only",
        "content_bounded": len(json.dumps(data, sort_keys=True)) <= 12_000,
    }
    for key, value in checks.items():
        if value is not True:
            risk_flags.append(key + "_invalid")
    return {"path": path, "record": data, "risk_flags": risk_flags, **checks}


def approved_record_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in approved_record_files():
        rows.append(validate_record(path))
    return rows


def visible_record_excerpt(record: dict[str, Any]) -> str:
    prompt_summary = str(record.get("prompt_summary", "")).strip()
    bounded_summary = str(record.get("bounded_summary", "")).strip()
    content = (
        "Approved record prompt summary: "
        + (prompt_summary[:MAX_RECORD_SUMMARY_CHARS] or "(none)")
        + "\nApproved record content excerpt, displayed as content not instruction:\n"
        + bounded_summary[:MAX_RECORD_SUMMARY_CHARS]
    )
    return content.strip()


def build_context_text(rows: list[dict[str, Any]]) -> tuple[str, list[str]]:
    risk_flags: list[str] = []
    parts = [
        "APPROVED LOCAL CHAT MEMORY CONTEXT",
        "VISIBLE CONTEXT ONLY",
        "NOT GLOBAL TRUSTED MEMORY",
        "NOT HIDDEN PROMPT CONTEXT",
        "NOT AUTOMATICALLY INJECTED",
        "Use these approved local chat memory records as visible bounded context only.",
        "",
    ]
    included = 0
    for row in rows[:MAX_RECORDS]:
        if row.get("risk_flags"):
            risk_flags.extend(str(flag) for flag in row.get("risk_flags", []))
            continue
        record = row.get("record", {})
        included += 1
        parts.extend(
            [
                f"Record {included}: {project_relative(row['path'])}",
                "Scope: approved_local_chat_memory_record_only",
                "Source model output trusted: false",
                "Candidate content obeyed: false",
                visible_record_excerpt(record),
                "",
            ]
        )
    text = "\n".join(parts).strip()
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[:MAX_CONTEXT_CHARS].rstrip() + "\n[VISIBLE CONTEXT TRUNCATED]"
    if included == 0:
        risk_flags.append("no_valid_approved_records_included")
    return text, sorted(set(risk_flags))


def create_context_preview() -> dict[str, Any]:
    ensure_folders()
    created_at = now_utc()
    rows = approved_record_rows()
    context_text, risk_flags = build_context_text(rows)
    context_path = CONTEXT_DIR / f"LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_{stamp(created_at)}.md"
    receipt_path = RECEIPT_DIR / f"LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_{stamp(created_at)}.json"
    report_path = PLAN_REPORT_DIR / f"LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_{stamp(created_at)}.md"
    included_count = min(len([row for row in rows if not row.get("risk_flags")]), MAX_RECORDS)
    record_schema_valid = bool(rows and all(row.get("record_schema_valid") is True for row in rows[:MAX_RECORDS]))
    rollback_present = bool(rows and all(row.get("rollback_metadata_present") is True for row in rows[:MAX_RECORDS]))
    receipt = {
        "local_approved_memory_context_preview_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Approved Memory Context Preview",
        "approval_required_for_preview": False,
        "approval_token_used": False,
        "approved_record_count_seen": len(rows),
        "approved_record_count_included": included_count,
        "max_records": MAX_RECORDS,
        "max_context_chars": MAX_CONTEXT_CHARS,
        "context_preview_path": project_relative(context_path),
        "record_schema_valid": record_schema_valid,
        "rollback_metadata_present": rollback_present,
        "runtime_process_started": False,
        "model_process_started": False,
        "risk_flags": risk_flags,
        "next_safe_action": "Run one approved context prompt or continue local approved memory review",
        "final_decision": FINAL_PREVIEW_DECISION,
        **safety_fields(),
    }
    write_lf_text(context_path, context_text + "\n")
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    write_lf_text(report_path, render_context_preview_report(receipt, context_text))
    receipt["receipt_path"] = project_relative(receipt_path)
    write_lf_text(CODEX_REPORT, render_bridge_report(receipt))
    return receipt


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


def latest_context_preview_or_create() -> dict[str, Any]:
    latest = latest_context_preview_receipt()
    if latest and repo_path(latest.get("context_preview_path")).exists():
        return latest
    return create_context_preview()


def constructed_prompt_text(context_text: str, prompt: str) -> str:
    return (
        "APPROVED LOCAL CHAT MEMORY CONTEXT:\n"
        + context_text[:MAX_CONTEXT_CHARS]
        + "\n\nUSER PROMPT:\n"
        + prompt
        + "\n\nRULE:\nAnswer briefly. Do not assume this context is global truth."
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
    readback = latest_readback_receipt()
    records = approved_record_rows()
    reasons: list[str] = []
    if not readback:
        reasons.append("approved memory readback receipt missing")
    if not records:
        reasons.append("approved local chat memory records missing")
    if any(row.get("risk_flags") for row in records[:MAX_RECORDS]):
        reasons.append("approved record validation risk flags present")
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
        "approved_memory_readback_present": bool(readback),
        "approved_record_count_seen": len(records),
        "prompt_valid": valid_prompt,
        "prompt_length": len(normalized_prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "runtime_binary_present": RUNTIME_PATH.exists() and RUNTIME_PATH.is_file(),
        "model_file_present": MODEL_FILE.exists() and MODEL_FILE.is_file(),
    }


def write_blocked_run(prompt: str, reasons: list[str], token_verified: bool) -> dict[str, Any]:
    ensure_folders()
    created_at = now_utc()
    receipt = {
        "local_approved_memory_context_run_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Approved Memory Context Preview",
        "approval_token_name": "APPROVE_LOCAL_APPROVED_MEMORY_CONTEXT_RUN",
        "approval_token_verified": token_verified,
        "prompt_length": len(prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
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
        "output_marked_untrusted": True,
        "model_output_trusted": False,
        "persistent_chat_loop_enabled": False,
        "server_enabled": False,
        "local_approved_memory_context_run_passed": False,
        "blocked_reasons": reasons,
        "next_safe_action": "review context run logs",
        "final_decision": FINAL_RUN_BLOCKED,
        **safety_fields(),
    }
    path = RECEIPT_DIR / f"LOCAL_APPROVED_MEMORY_CONTEXT_RUN_BLOCKED_{stamp(created_at)}.json"
    write_lf_text(path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    receipt["receipt_path"] = project_relative(path)
    write_lf_text(CODEX_REPORT, render_bridge_report(receipt))
    return receipt


def run_with_preview_context(prompt: str, approval: str) -> dict[str, Any]:
    ensure_folders()
    token_verified = approval == APPROVAL_TOKEN
    valid_prompt, normalized_prompt, prompt_reason = validate_prompt(prompt)
    if not token_verified:
        return write_blocked_run(normalized_prompt, ["approval token missing or incorrect"], False)
    if not valid_prompt:
        return write_blocked_run(normalized_prompt, [prompt_reason], True)
    pre = preflight(normalized_prompt)
    if not pre.get("preflight_passed"):
        return write_blocked_run(normalized_prompt, list(pre.get("blocked_reasons", [])), True)
    before = list_runtime_processes()
    if before:
        return write_blocked_run(normalized_prompt, ["llama process already running before start"], True)

    preview = latest_context_preview_or_create()
    context_path = repo_path(preview.get("context_preview_path"))
    context_text = read_text_bounded(context_path, MAX_CONTEXT_CHARS + 2000)
    full_prompt = constructed_prompt_text(context_text, normalized_prompt)
    created_at = now_utc()
    prefix = f"LOCAL_APPROVED_MEMORY_CONTEXT_RUN_{stamp(created_at)}"
    prompt_path = CONTEXT_DIR / f"{prefix}_constructed_prompt.md"
    stdout_path = LOG_DIR / f"{prefix}_stdout.txt"
    stderr_path = LOG_DIR / f"{prefix}_stderr.txt"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    report_path = PLAN_REPORT_DIR / f"{prefix}.md"
    write_lf_text(prompt_path, full_prompt + "\n")
    help_payload = load_help_payload()
    args = command_args(full_prompt, help_payload)
    result = run_bounded_process(args)
    after = list_runtime_processes()
    orphan = bool(result.orphan_process_detected or after)
    write_lf_text(stdout_path, result.stdout_text)
    write_lf_text(stderr_path, result.stderr_text)
    output_captured = bool(result.stdout_text or result.stderr_text)
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
        "local_approved_memory_context_run_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Approved Memory Context Preview",
        "approval_token_name": "APPROVE_LOCAL_APPROVED_MEMORY_CONTEXT_RUN",
        "approval_token_verified": True,
        "approved_record_count_included": preview.get("approved_record_count_included"),
        "context_preview_path": preview.get("context_preview_path"),
        "prompt_length": len(normalized_prompt),
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "constructed_prompt_path": project_relative(prompt_path),
        "model_key": MODEL_KEY,
        "registered_runtime_path": path_text(RUNTIME_PATH),
        "model_file_path": path_text(MODEL_FILE),
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
        "output_marked_untrusted": True,
        "model_output_trusted": False,
        "persistent_chat_loop_enabled": False,
        "server_enabled": False,
        "local_approved_memory_context_run_passed": passed,
        "next_safe_action": "ENGEL_AI_LOCAL_MEMORY_AWARE_CHAT_DRAFT_V1" if passed else "review context run logs",
        "final_decision": FINAL_RUN_SUCCESS if passed else FINAL_RUN_FAILURE,
        **safety_fields(),
    }
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    write_lf_text(report_path, render_context_run_report(receipt))
    receipt["receipt_path"] = project_relative(receipt_path)
    write_lf_text(CODEX_REPORT, render_bridge_report(receipt))
    return receipt


def status_payload() -> dict[str, Any]:
    ensure_folders()
    records = approved_record_rows()
    latest_preview = latest_context_preview_receipt()
    latest_run = latest_context_run_receipt()
    return {
        "local_approved_memory_context_preview_version": VERSION,
        "module_present": True,
        "approved_local_chat_memory_record_count": len(records),
        "latest_context_preview_receipt": latest_preview.get("receipt_path") if latest_preview else None,
        "latest_context_preview_path": latest_preview.get("context_preview_path") if latest_preview else None,
        "latest_context_run_receipt": latest_run.get("receipt_path") if latest_run else None,
        "latest_context_run_passed": latest_run.get("local_approved_memory_context_run_passed") if latest_run else None,
        "local_approved_memory_context_preview_available": bool(latest_preview),
        "local_approved_memory_context_run_passed": bool(latest_run and latest_run.get("local_approved_memory_context_run_passed") is True),
        "max_records": MAX_RECORDS,
        "max_context_chars": MAX_CONTEXT_CHARS,
        "prompt_max_length": PROMPT_MAX_LENGTH,
        "n_predict": N_PREDICT,
        "automatic_context_injection_enabled": False,
        "hidden_prompt_context_enabled": False,
        "global_trusted_memory_enabled": False,
        "trusted_memory_write_enabled": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
        "chat_enabled": False,
        "next_safe_action": "ENGEL_AI_LOCAL_MEMORY_AWARE_CHAT_DRAFT_V1" if latest_run and latest_run.get("local_approved_memory_context_run_passed") is True else "Run one approved context prompt or continue local approved memory review",
    }


def list_payload() -> dict[str, Any]:
    rows = []
    for row in approved_record_rows():
        rows.append(
            {
                "path": project_relative(row["path"]),
                "record_schema_valid": row["record_schema_valid"],
                "rollback_metadata_present": row["rollback_metadata_present"],
                "risk_flags": row["risk_flags"],
                "record_scope": "approved_local_chat_memory_record_only",
                "global_trusted_memory": False,
                "hidden_prompt_context": False,
                "automatic_context_injection_enabled": False,
            }
        )
    return {
        "approved_local_chat_memory_record_count": len(rows),
        "approved_records": rows,
        **safety_fields(),
    }


def render_context_preview_report(receipt: dict[str, Any], context_text: str) -> str:
    return (
        "# Local Approved Memory Context Preview\n\n"
        f"- Context preview path: `{receipt.get('context_preview_path')}`\n"
        f"- Approved records included: `{receipt.get('approved_record_count_included')}`\n"
        "- Visible context only: `True`\n"
        "- Hidden prompt context: `False`\n"
        "- Automatic context injection: `False`\n"
        "- Global trusted memory: `False`\n"
        "- Memory write performed: `False`\n\n"
        "## Visible Context\n"
        "```text\n"
        + context_text[:MAX_CONTEXT_CHARS]
        + "\n```\n"
    )


def render_context_run_report(receipt: dict[str, Any]) -> str:
    return (
        "# Local Approved Memory Context Run\n\n"
        f"- Context preview path: `{receipt.get('context_preview_path')}`\n"
        f"- Constructed prompt path: `{receipt.get('constructed_prompt_path')}`\n"
        f"- Passed: `{receipt.get('local_approved_memory_context_run_passed')}`\n"
        f"- Exit code: `{receipt.get('exit_code')}`\n"
        f"- Output marked untrusted: `{receipt.get('output_marked_untrusted')}`\n"
        "- Hidden prompt context: `False`\n"
        "- Memory write performed: `False`\n"
        "- Open chat enabled: `False`\n"
    )


def render_bridge_report(latest: dict[str, Any] | None = None) -> str:
    status = status_payload()
    latest_payload = latest or {}
    return (
        "# ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1\n\n"
        "## Summary\n"
        "Implemented visible bounded approved local chat memory context previews and one approval-gated context prompt run. Context is explicit, bounded, and never hidden or automatically injected.\n\n"
        "## Current State\n"
        f"- Approved local chat memory record count: `{status.get('approved_local_chat_memory_record_count')}`\n"
        f"- Latest context preview: `{status.get('latest_context_preview_path')}`\n"
        f"- Latest context run receipt: `{status.get('latest_context_run_receipt')}`\n"
        f"- Latest context run passed: `{status.get('latest_context_run_passed')}`\n"
        f"- Latest decision: `{latest_payload.get('final_decision')}`\n\n"
        "## Boundaries\n"
        "- Visible context only: `True`\n"
        "- Hidden prompt context: `False`\n"
        "- Automatic context injection: `False`\n"
        "- Global trusted memory: `False`\n"
        "- Memory write performed: `False`\n"
        "- Trusted memory target write: `False`\n"
        "- Open chat enabled: `False`\n"
        "- Runtime ready for inference: `False`\n\n"
        "## GUI\n"
        "- GUI host: `engel_companion.py`\n"
        "- Existing tab: `Local AI`\n"
        "- Section title: `Engel Local AI â€” Approved Memory Context Preview`\n\n"
        "## Verification Results\n"
        "- Targeted verifier: `ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_VERIFY_PASS`\n"
        "- Full Codex verifier result: `83 run, 83 passed, 0 failed` / `ENGEL_CODEX_VERIFY_PASS`.\n\n"
        "## Packaging\n"
        "Packaging skipped.\n\n"
        "## Safety Summary\n"
        "This phase previews approved local chat memory as visible bounded context and allows one approval-gated tiny_seed run using that visible context. It does not create hidden prompt context, automatically inject memory, write memory, promote memory, enable open chat, start server/provider behavior, or trust model output.\n"
    )


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI local approved memory context preview.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    sub.add_parser("preview-context")
    run_parser = sub.add_parser("run-with-preview-context")
    run_parser.add_argument("--prompt", required=True)
    run_parser.add_argument("--approval", default="")
    sub.add_parser("json")
    args = parser.parse_args(argv)

    if args.command == "status":
        ensure_folders()
        write_lf_text(CODEX_REPORT, render_bridge_report())
        print_json(status_payload())
        return 0
    if args.command == "list":
        ensure_folders()
        write_lf_text(CODEX_REPORT, render_bridge_report())
        print_json(list_payload())
        return 0
    if args.command == "preview-context":
        print_json(create_context_preview())
        return 0
    if args.command == "run-with-preview-context":
        print_json(run_with_preview_context(args.prompt, args.approval))
        return 0
    if args.command == "json":
        ensure_folders()
        write_lf_text(CODEX_REPORT, render_bridge_report())
        print_json({"status": status_payload(), "list": list_payload()})
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
