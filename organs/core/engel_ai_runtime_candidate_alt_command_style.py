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
MAX_LOG_CHARS = 20_000
MAX_HELP_CHARS = 20_000
MAX_READ_CHARS = 120_000
APPROVAL_TOKEN = "APPROVE_RUNTIME_CANDIDATE_ALT_STYLE_VALIDATION"
APPROVAL_TOKEN_NAME = "runtime_candidate_alt_style_validation_token"

CANDIDATE_FOLDER = Path("D:/b.WorkSpace/Engel App/runtime/llama.cpp/candidates/llama-b9198-bin-win-cpu-x64")
APPROVED_CANDIDATE_ROOT = Path("D:/b.WorkSpace/Engel App/runtime/llama.cpp/candidates")
MODEL_KEY = "tiny_seed"
MODEL_FILE = Path("/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf")
FIXED_PROMPT = "load check"

TIMEOUT_SECONDS = 180
HELP_TIMEOUT_SECONDS = 20
PROCESS_LIST_TIMEOUT_SECONDS = 10
TERMINATE_GRACE_SECONDS = 5
KILL_GRACE_SECONDS = 5
CONTEXT_SIZE = 512
THREADS = 4

REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_runtime_candidate_alt_command_style"
DIAGNOSTIC_DIR = REPORT_ROOT / "diagnostics"
LOG_DIR = REPORT_ROOT / "logs"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_V1.md"

FINAL_DECISION_SUCCESS = (
    "RUNTIME CANDIDATE ALT COMMAND STYLE PASSED - READY FOR SWAP REVIEW ONLY - "
    "REGISTERED RUNTIME NOT CHANGED - NO CHAT - NO TRUSTED MEMORY WRITE"
)
FINAL_DECISION_FAILURE = (
    "RUNTIME CANDIDATE ALT COMMAND STYLE FAILED - "
    "REGISTERED RUNTIME NOT CHANGED - NO CHAT - NO TRUSTED MEMORY WRITE"
)
FINAL_DECISION_BLOCKED = (
    "RUNTIME CANDIDATE ALT COMMAND STYLE BLOCKED - "
    "REGISTERED RUNTIME NOT CHANGED - NO CHAT - NO TRUSTED MEMORY WRITE"
)

DISQUALIFYING_INTERACTIVE_MARKERS = [
    "available commands:",
    "ctrl+c",
    "/help",
    "/?",
    "/exit",
    "system_info",
    "interactive mode",
    "reverse prompt",
    "conversation mode",
    "chat template",
    "waiting for input",
    "press enter",
    "\n> ",
]
DISQUALIFYING_GENERATION_MARKERS = [
    "generation:",
    "tokens predicted",
    "predicted",
    "sampling",
    "assistant:",
]
SERVER_MARKERS = [
    "llama server",
    "server is listening",
    "api server",
    "listening on",
    "bind",
    "http://",
    "https://",
    "port ",
]
FORBIDDEN_EXECUTABLES = {"llama-server.exe", "rpc-server.exe"}


@dataclass(frozen=True)
class CommandStyle:
    style_id: str
    label: str
    executable_name: str
    rank: int
    command_args: list[str]
    stdin_devnull: bool
    touches_model: bool
    uses_prompt: bool
    non_chat: bool
    non_server: bool
    generation_requested: bool
    validation_eligible: bool
    reason: str


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


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, DIAGNOSTIC_DIR, LOG_DIR, RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "ALT_COMMAND_STYLE_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "runtime_candidate_alt_command_style_version": "1",
                    "example_only": True,
                    "selected_command_style": "llama_tokenize_ids_count",
                    "runtime_ready_for_inference": False,
                    "chat_enabled": False,
                    "trusted_memory_write_enabled": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )


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


def path_text(path: Path) -> str:
    return str(path.resolve(strict=False)).replace("/", "\\")


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return path_text(path)


def executable_path(name: str) -> Path:
    return CANDIDATE_FOLDER / name


def starts_with_path(path_value: str, root_value: str) -> bool:
    path_lower = path_value.casefold()
    root_lower = root_value.casefold().rstrip("\\")
    return path_lower == root_lower or path_lower.startswith(root_lower + "\\")


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


def safety_fields() -> dict[str, Any]:
    return {
        "registered_runtime_changed": False,
        "runtime_ready_for_inference": False,
        "runtime_no_generation_check_ready": False,
        "inference_enabled": False,
        "chat_enabled": False,
        "server_enabled": False,
        "auto_load_enabled": False,
        "trusted_memory_write_enabled": False,
        "provider_api_enabled": False,
        "source_route_queue_mutation": False,
    }


def base_style_definitions() -> list[CommandStyle]:
    model = path_text(MODEL_FILE)
    prompt = FIXED_PROMPT
    return [
        CommandStyle(
            "llama_tokenize_ids_count",
            "llama-tokenize model tokenizer touch, token IDs only",
            "llama-tokenize.exe",
            1,
            [path_text(executable_path("llama-tokenize.exe")), "-m", model, "-p", prompt, "--ids", "--show-count", "--log-disable"],
            True,
            True,
            True,
            True,
            True,
            False,
            True,
            "Preferred: tokenizes a fixed prompt with the tiny model/tokenizer and exits without decode/chat/server mode.",
        ),
        CommandStyle(
            "llama_cli_devnull_n0",
            "llama-cli fixed prompt, stdin DEVNULL, n_predict zero",
            "llama-cli.exe",
            2,
            [path_text(executable_path("llama-cli.exe")), "-m", model, "-p", prompt, "-n", "0", "-c", str(CONTEXT_SIZE), "-t", str(THREADS), "--log-disable", "--offline"],
            True,
            True,
            True,
            True,
            True,
            False,
            True,
            "Fallback only: previous replay saw interactive/generation markers, so this is lower confidence.",
        ),
        CommandStyle(
            "llama_completion_no_select",
            "llama-completion inventory only",
            "llama-completion.exe",
            3,
            [path_text(executable_path("llama-completion.exe")), "--help"],
            True,
            False,
            False,
            True,
            True,
            False,
            False,
            "Not selected: completion mode is not the lowest-risk tokenizer/model-touch validation.",
        ),
        CommandStyle(
            "llama_perplexity_no_select",
            "llama-perplexity inventory only",
            "llama-perplexity.exe",
            4,
            [path_text(executable_path("llama-perplexity.exe")), "--help"],
            True,
            False,
            False,
            True,
            True,
            False,
            False,
            "Not selected: perplexity is evaluation-oriented and not needed for a tokenizer-only gate.",
        ),
        CommandStyle(
            "llama_server_forbidden",
            "llama-server forbidden inventory only",
            "llama-server.exe",
            99,
            [path_text(executable_path("llama-server.exe"))],
            False,
            False,
            False,
            False,
            False,
            True,
            False,
            "Forbidden: server executable is inventory-only and must never be selected or executed.",
        ),
        CommandStyle(
            "rpc_server_forbidden",
            "rpc-server forbidden inventory only",
            "rpc-server.exe",
            100,
            [path_text(executable_path("rpc-server.exe"))],
            False,
            False,
            False,
            False,
            False,
            True,
            False,
            "Forbidden: RPC server executable is inventory-only and must never be selected or executed.",
        ),
    ]


def command_style_to_row(style: CommandStyle, help_result: dict[str, Any] | None = None) -> dict[str, Any]:
    binary = executable_path(style.executable_name)
    help_text = str((help_result or {}).get("combined_output", ""))
    required_flags = ["--model", "--prompt", "--ids", "--show-count"] if style.style_id == "llama_tokenize_ids_count" else []
    help_supports_required_flags = all(flag in help_text for flag in required_flags) if required_flags else None
    selection_eligible = (
        style.validation_eligible
        and binary.exists()
        and binary.is_file()
        and MODEL_FILE.exists()
        and MODEL_FILE.is_file()
        and style.non_chat
        and style.non_server
        and not style.generation_requested
        and style.executable_name.lower() not in FORBIDDEN_EXECUTABLES
        and (help_supports_required_flags is not False)
    )
    return {
        "style_id": style.style_id,
        "label": style.label,
        "rank": style.rank,
        "executable_name": style.executable_name,
        "executable_path": path_text(binary),
        "executable_present": binary.exists() and binary.is_file(),
        "executable_role": "forbidden_inventory_only" if style.executable_name.lower() in FORBIDDEN_EXECUTABLES else "candidate_tool",
        "selection_eligible": selection_eligible,
        "selected": False,
        "touches_model": style.touches_model,
        "uses_prompt": style.uses_prompt,
        "stdin_devnull": style.stdin_devnull,
        "non_chat": style.non_chat,
        "non_server": style.non_server,
        "generation_requested": style.generation_requested,
        "n_predict": 0 if style.style_id == "llama_cli_devnull_n0" else None,
        "help_checked": bool(help_result),
        "help_exit_code": (help_result or {}).get("exit_code"),
        "help_supports_required_flags": help_supports_required_flags,
        "command_args": style.command_args if selection_eligible else [],
        "reason": style.reason,
    }


def candidate_preflight(selected_style: dict[str, Any] | None = None) -> dict[str, Any]:
    folder = path_text(CANDIDATE_FOLDER).rstrip("\\")
    approved_root = path_text(APPROVED_CANDIDATE_ROOT).rstrip("\\")
    reasons: list[str] = []
    if not starts_with_path(folder, approved_root):
        reasons.append("candidate_folder_outside_approved_root")
    if not CANDIDATE_FOLDER.exists() or not CANDIDATE_FOLDER.is_dir():
        reasons.append("candidate_folder_missing")
    if not MODEL_FILE.exists() or not MODEL_FILE.is_file():
        reasons.append("tiny_seed_model_missing")
    if selected_style is not None:
        exe_name = str(selected_style.get("executable_name", "")).lower()
        exe_path = Path(str(selected_style.get("executable_path", "")))
        if exe_name in FORBIDDEN_EXECUTABLES:
            reasons.append("server_executable_not_allowed")
        if not selected_style.get("selection_eligible"):
            reasons.append("selected_style_not_eligible")
        if not exe_path.exists() or not exe_path.is_file():
            reasons.append("selected_executable_missing")
    return {
        "candidate_folder": folder,
        "candidate_under_approved_root": not any(reason == "candidate_folder_outside_approved_root" for reason in reasons),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "preflight_passed": not reasons,
        "blocked_reasons": reasons,
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


def run_bounded_process(args: list[str], timeout_seconds: int, *, stdin_devnull: bool = True) -> ExecutionResult:
    if not args:
        return ExecutionResult(False, False, True, timeout_seconds, None, "", "", False, False, False, False, False, error="empty_args")
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL if stdin_devnull else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            cwd=str(CANDIDATE_FOLDER) if CANDIDATE_FOLDER.exists() else None,
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


def run_help_probe(executable_name: str) -> dict[str, Any]:
    if executable_name.lower() in FORBIDDEN_EXECUTABLES:
        return {
            "executable_name": executable_name,
            "executable_path": path_text(executable_path(executable_name)),
            "ran": False,
            "exit_code": None,
            "combined_output": "",
            "blocked_reason": "server_executable_inventory_only",
        }
    binary = executable_path(executable_name)
    if not binary.exists() or not binary.is_file():
        return {
            "executable_name": executable_name,
            "executable_path": path_text(binary),
            "ran": False,
            "exit_code": None,
            "combined_output": "",
            "blocked_reason": "executable_missing",
        }
    result = run_bounded_process([path_text(binary), "--help"], HELP_TIMEOUT_SECONDS, stdin_devnull=True)
    combined, truncated = bounded_text((result.stdout_text or "") + ("\n[stderr]\n" + result.stderr_text if result.stderr_text else ""), MAX_HELP_CHARS)
    return {
        "executable_name": executable_name,
        "executable_path": path_text(binary),
        "ran": result.command_executed,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "interrupted": result.interrupted,
        "truncated": truncated or result.stdout_truncated or result.stderr_truncated,
        "combined_output": combined,
        "shell": False,
        "stdin_devnull": True,
    }


def inspect_help_payload(*, write_diagnostics: bool = True) -> dict[str, Any]:
    ensure_folders()
    allowed = ["llama-tokenize.exe", "llama-cli.exe", "llama-completion.exe", "llama-perplexity.exe"]
    forbidden = ["llama-server.exe", "rpc-server.exe"]
    probes = [run_help_probe(name) for name in allowed + forbidden]
    payload = {
        "runtime_candidate_alt_command_style_version": "1",
        "candidate_folder": path_text(CANDIDATE_FOLDER),
        "help_probe_mode": "safe_no_model_help_only",
        "forbidden_server_executables_inventory_only": forbidden,
        "probes": probes,
        **safety_fields(),
    }
    if write_diagnostics:
        write_lf_text(DIAGNOSTIC_DIR / "ALT_COMMAND_STYLE_HELP_INSPECTION.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def build_matrix(*, help_payload: dict[str, Any] | None = None, write_diagnostics: bool = True) -> dict[str, Any]:
    ensure_folders()
    help_data = help_payload or inspect_help_payload(write_diagnostics=write_diagnostics)
    help_by_name = {probe.get("executable_name"): probe for probe in help_data.get("probes", []) if isinstance(probe, dict)}
    rows = [command_style_to_row(style, help_by_name.get(style.executable_name)) for style in base_style_definitions()]
    eligible = [row for row in rows if row["selection_eligible"]]
    selected = sorted(eligible, key=lambda row: int(row["rank"]))[0] if eligible else None
    if selected:
        for row in rows:
            row["selected"] = row["style_id"] == selected["style_id"]
    payload = {
        "runtime_candidate_alt_command_style_version": "1",
        "candidate_folder": path_text(CANDIDATE_FOLDER),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "selected_command_style": selected["style_id"] if selected else None,
        "selected_alternate_command_style": selected,
        "matrix": rows,
        "selection_policy": "lowest_rank_non_chat_non_server_no_generation_model_touch",
        **safety_fields(),
    }
    if write_diagnostics:
        write_lf_text(DIAGNOSTIC_DIR / "ALT_COMMAND_STYLE_MATRIX.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def selected_style_from_matrix(matrix_payload: dict[str, Any]) -> dict[str, Any] | None:
    selected = matrix_payload.get("selected_alternate_command_style")
    return selected if isinstance(selected, dict) else None


def preview_payload() -> dict[str, Any]:
    matrix_payload = build_matrix(write_diagnostics=True)
    selected = selected_style_from_matrix(matrix_payload)
    return {
        "runtime_candidate_alt_command_style_version": "1",
        "command_preview_only": True,
        "candidate_folder": path_text(CANDIDATE_FOLDER),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "selected_command_style": selected.get("style_id") if selected else None,
        "selected_alternate_command_style": selected,
        "preflight": candidate_preflight(selected),
        "timeout_seconds": TIMEOUT_SECONDS,
        "normal_inference_requested": False,
        "chat_requested": False,
        "server_requested": False,
        **safety_fields(),
    }


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


def tokenize_output_classified_non_generation(stdout_text: str, stderr_text: str) -> bool:
    combined = (stdout_text + "\n" + stderr_text).strip()
    if not combined:
        return True
    allowed_prefixes = (
        "llama_",
        "ggml_",
        "build:",
        "main:",
        "load ",
        "load_",
        "token",
        "tokenize",
        "model ",
    )
    for raw in combined.splitlines():
        line = raw.strip()
        lower = line.lower()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            inner = line.strip("[] ").replace(",", "").replace(" ", "")
            if inner.isdigit() or inner == "":
                continue
        if line.isdigit():
            continue
        if any(lower.startswith(prefix) for prefix in allowed_prefixes):
            continue
        if "tokens" in lower and "predicted" not in lower and "generation" not in lower:
            continue
        return False
    return True


def generated_text_detected(stdout_text: str, stderr_text: str, command_style: str) -> bool:
    if command_style == "llama_tokenize_ids_count":
        return not tokenize_output_classified_non_generation(stdout_text, stderr_text)
    combined_lines = (stdout_text + "\n" + stderr_text).splitlines()
    saw_prompt = False
    for raw_line in combined_lines:
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if lower == FIXED_PROMPT:
            saw_prompt = True
            continue
        if saw_prompt:
            if lower.startswith("[") or lower.startswith("exiting") or lower.startswith(">"):
                continue
            if "generation:" in lower or "prompt:" in lower:
                continue
            if lower.startswith("llama_") or lower.startswith("main:") or lower.startswith("build:"):
                continue
            return True
    return False


def output_marker_analysis(stdout_text: str, stderr_text: str, command_style: str) -> dict[str, Any]:
    combined = (stdout_text + "\n" + stderr_text).lower()
    interactive_hits = [marker for marker in DISQUALIFYING_INTERACTIVE_MARKERS if marker in combined]
    generation_hits = [marker for marker in DISQUALIFYING_GENERATION_MARKERS if marker in combined]
    server_hits = [marker for marker in SERVER_MARKERS if marker in combined]
    tokenization_non_generation = tokenize_output_classified_non_generation(stdout_text, stderr_text) if command_style == "llama_tokenize_ids_count" else False
    generated = generated_text_detected(stdout_text, stderr_text, command_style)
    return {
        "disqualifying_interactive_markers_found": bool(interactive_hits),
        "disqualifying_generation_markers_found": bool(generation_hits),
        "server_startup_markers_found": bool(server_hits),
        "generated_text_detected": generated,
        "tokenization_output_classified_non_generation": tokenization_non_generation,
        "interactive_marker_hits": interactive_hits[:20],
        "generation_marker_hits": generation_hits[:20],
        "server_marker_hits": server_hits[:20],
    }


def latest_alt_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_*.json")):
        data = read_json(path)
        if data.get("runtime_candidate_alt_command_style_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def status_payload() -> dict[str, Any]:
    latest = latest_alt_receipt()
    return {
        "runtime_candidate_alt_command_style_version": "1",
        "candidate_folder": path_text(CANDIDATE_FOLDER),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "latest_alt_receipt": latest.get("receipt_path") if latest else None,
        "latest_selected_command_style": latest.get("selected_command_style") if latest else None,
        "latest_alt_validation_passed": latest.get("alt_command_style_validation_passed") if latest else None,
        "latest_candidate_runtime_ready_for_swap_review": latest.get("candidate_runtime_ready_for_swap_review") if latest else None,
        "latest_final_decision": latest.get("final_decision") if latest else None,
        **safety_fields(),
    }


def base_receipt(created_at: str, approval_verified: bool, selected: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "runtime_candidate_alt_command_style_version": "1",
        "created_at": created_at,
        "candidate_folder": path_text(CANDIDATE_FOLDER),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "approval_token_name": APPROVAL_TOKEN_NAME,
        "approval_token_verified": approval_verified,
        "selected_command_style": selected.get("style_id") if selected else None,
        "selected_executable_name": selected.get("executable_name") if selected else None,
        "command_args": selected.get("command_args") if selected else [],
        "timeout_seconds": TIMEOUT_SECONDS,
        "stdin_devnull": selected.get("stdin_devnull") if selected else None,
        "normal_inference_requested": False,
        "chat_requested": False,
        "server_requested": False,
        **safety_fields(),
    }


def blocked_receipt(reason: str, approval_verified: bool, selected: dict[str, Any] | None, write_receipt: bool) -> dict[str, Any]:
    ensure_folders()
    created_at = now_utc()
    receipt = {
        **base_receipt(created_at, approval_verified, selected),
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
        "disqualifying_interactive_markers_found": False,
        "disqualifying_generation_markers_found": False,
        "server_startup_markers_found": False,
        "generated_text_detected": False,
        "tokenization_output_classified_non_generation": False,
        "alt_command_style_validation_passed": False,
        "candidate_runtime_ready_for_swap_review": False,
        "blocked_reason": reason,
        "recommended_next_action": "Build matrix or choose another non-chat, non-server command style before validation.",
        "final_decision": FINAL_DECISION_BLOCKED,
    }
    if write_receipt:
        persist_receipt(receipt)
    return receipt


def write_log_pair(prefix: str, stdout_text: str, stderr_text: str) -> tuple[str, str]:
    ensure_folders()
    stdout_path = LOG_DIR / f"{prefix}_stdout.txt"
    stderr_path = LOG_DIR / f"{prefix}_stderr.txt"
    write_lf_text(stdout_path, stdout_text)
    write_lf_text(stderr_path, stderr_text)
    return project_relative(stdout_path), project_relative(stderr_path)


def persist_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    ensure_folders()
    created_at = str(receipt.get("created_at") or now_utc())
    prefix = f"RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_{stamp(created_at)}_llama-b9198-bin-win-cpu-x64"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    report_path = PLAN_REPORT_DIR / f"{prefix}.md"
    receipt["receipt_path"] = project_relative(receipt_path)
    receipt["report_path"] = project_relative(report_path)
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    report = render_report(receipt)
    write_lf_text(report_path, report)
    write_lf_text(CODEX_REPORT, report)
    return receipt


def validate_alt(approval: str | None) -> dict[str, Any]:
    approval_verified = approval == APPROVAL_TOKEN
    matrix_payload = build_matrix(write_diagnostics=True)
    selected = selected_style_from_matrix(matrix_payload)
    if not approval_verified:
        return blocked_receipt("approval_token_missing_or_invalid", False, selected, False)
    if selected is None:
        return blocked_receipt("no_safe_alternate_command_style_selected", True, selected, True)
    preflight = candidate_preflight(selected)
    if not preflight["preflight_passed"]:
        receipt = blocked_receipt("preflight_failed: " + ", ".join(preflight["blocked_reasons"]), True, selected, True)
        receipt["preflight"] = preflight
        return receipt
    existing_processes = list_runtime_processes()
    if existing_processes:
        receipt = blocked_receipt("runtime_process_already_running_before_validation", True, selected, True)
        receipt["pre_existing_runtime_processes"] = existing_processes
        return receipt

    created_at = now_utc()
    result = run_bounded_process(list(selected["command_args"]), TIMEOUT_SECONDS, stdin_devnull=bool(selected.get("stdin_devnull") is True))
    prefix = f"RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_{stamp(created_at)}_llama-b9198-bin-win-cpu-x64"
    stdout_path, stderr_path = write_log_pair(prefix, result.stdout_text, result.stderr_text)
    markers = output_marker_analysis(result.stdout_text, result.stderr_text, str(selected["style_id"]))
    post_processes = list_runtime_processes()
    orphan = result.orphan_process_detected or bool(post_processes)
    passed = (
        approval_verified
        and result.command_executed
        and result.runtime_process_started
        and result.runtime_process_exited
        and result.exit_code == 0
        and not result.timed_out
        and not result.interrupted
        and not orphan
        and bool(selected.get("non_chat") is True)
        and bool(selected.get("non_server") is True)
        and bool(selected.get("generation_requested") is False)
        and not markers["disqualifying_interactive_markers_found"]
        and not markers["disqualifying_generation_markers_found"]
        and not markers["server_startup_markers_found"]
        and not markers["generated_text_detected"]
    )
    receipt = {
        **base_receipt(created_at, approval_verified, selected),
        "preflight": preflight,
        "matrix_path": project_relative(DIAGNOSTIC_DIR / "ALT_COMMAND_STYLE_MATRIX.json"),
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
        "post_validation_runtime_processes": post_processes,
        "stdout_log_path": stdout_path,
        "stderr_log_path": stderr_path,
        "stdout_truncated": result.stdout_truncated,
        "stderr_truncated": result.stderr_truncated,
        **markers,
        "alt_command_style_validation_passed": passed,
        "candidate_runtime_ready_for_swap_review": passed,
        "recommended_next_action": "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1" if passed else "Try a different runtime candidate or choose a non-llama.cpp local backend.",
        "final_decision": FINAL_DECISION_SUCCESS if passed else FINAL_DECISION_FAILURE,
    }
    return persist_receipt(receipt)


def render_report(receipt: dict[str, Any] | None = None) -> str:
    data = receipt or latest_alt_receipt() or {}
    selected_style = data.get("selected_command_style")
    result = "not run"
    if data.get("final_decision") == FINAL_DECISION_BLOCKED:
        result = "blocked"
    elif data.get("timed_out") is True:
        result = "timed out"
    elif data.get("interrupted") is True:
        result = "interrupted"
    elif data.get("alt_command_style_validation_passed") is True:
        result = "passed"
    elif data:
        result = "failed"
    return f"""# ENGEL_AI_RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_V1

## Summary
This phase builds an alternate command-style matrix for the known llama.cpp candidate and validates at most one bounded no-generation style.

## Why This Exists
Interactive and generation behavior is bad at this stage because this is a no-generation validation gate. Chat remains a future Engel goal, but chat must stay separate from this load/tokenizer-style proof until later approved chat phases.

## Candidate
- candidate folder: `{data.get("candidate_folder", path_text(CANDIDATE_FOLDER))}`
- model key: `{data.get("model_key", MODEL_KEY)}`
- model file: `{data.get("model_file_path", path_text(MODEL_FILE))}`

## Selected Alternate Command Style
- selected command style: `{selected_style}`
- selected executable: `{data.get("selected_executable_name")}`
- stdin DEVNULL: `{data.get("stdin_devnull")}`
- timeout seconds: `{data.get("timeout_seconds", TIMEOUT_SECONDS)}`

## Validation Result
- result: `{result}`
- command executed: `{data.get("command_executed")}`
- runtime process started: `{data.get("runtime_process_started")}`
- runtime process exited: `{data.get("runtime_process_exited")}`
- exit code: `{data.get("exit_code")}`
- timed out: `{data.get("timed_out")}`
- interrupted: `{data.get("interrupted")}`
- orphan process detected: `{data.get("orphan_process_detected")}`
- disqualifying interactive markers found: `{data.get("disqualifying_interactive_markers_found")}`
- disqualifying generation markers found: `{data.get("disqualifying_generation_markers_found")}`
- generated text detected: `{data.get("generated_text_detected")}`
- tokenization output classified non-generation: `{data.get("tokenization_output_classified_non_generation")}`
- candidate ready for swap review: `{data.get("candidate_runtime_ready_for_swap_review")}`

## Evidence
- receipt path: `{data.get("receipt_path")}`
- stdout log path: `{data.get("stdout_log_path")}`
- stderr log path: `{data.get("stderr_log_path")}`
- report path: `{data.get("report_path")}`

## Runtime State
- registered runtime changed: `{data.get("registered_runtime_changed", False)}`
- runtime ready for inference: `{data.get("runtime_ready_for_inference", False)}`
- runtime no-generation check ready: `{data.get("runtime_no_generation_check_ready", False)}`
- inference enabled: `{data.get("inference_enabled", False)}`
- chat enabled: `{data.get("chat_enabled", False)}`
- server enabled: `{data.get("server_enabled", False)}`
- trusted memory write enabled: `{data.get("trusted_memory_write_enabled", False)}`

## Verification
- Alt command-style verifier: pending run.
- Full Codex verifier: pending run.
- Packaging skipped.

This phase protects future chat by keeping no-generation validation separate. It does not change the registered runtime, enable inference, start chat/server mode, run server binaries, write trusted memory, mutate source/routes/queues beyond intended phase files, download/install anything, or trust model output.
"""


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists():
        write_lf_text(CODEX_REPORT, render_report(None))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI runtime candidate alternate command-style validation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("inspect-help")
    sub.add_parser("matrix")
    sub.add_parser("preview")
    validate_parser = sub.add_parser("validate-alt")
    validate_parser.add_argument("--approval")
    sub.add_parser("json")
    args = parser.parse_args(argv)

    ensure_folders()
    write_initial_report()
    if args.command == "status":
        print(json.dumps(status_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "inspect-help":
        print(json.dumps(inspect_help_payload(write_diagnostics=True), indent=2, sort_keys=True))
        return 0
    if args.command == "matrix":
        print(json.dumps(build_matrix(write_diagnostics=True), indent=2, sort_keys=True))
        return 0
    if args.command == "preview":
        print(json.dumps(preview_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "validate-alt":
        result = validate_alt(args.approval)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("approval_token_verified") is True else 2
    if args.command == "json":
        payload = {
            "status": status_payload(),
            "matrix": build_matrix(write_diagnostics=True),
            "preview": preview_payload(),
            "latest_alt_validation": latest_alt_receipt(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
