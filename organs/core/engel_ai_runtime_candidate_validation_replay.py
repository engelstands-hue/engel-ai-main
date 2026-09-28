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
MAX_READ_CHARS = 120_000
APPROVAL_TOKEN = "APPROVE_RUNTIME_CANDIDATE_VALIDATION_REPLAY"
SOURCE_DIAGNOSIS_COMMIT = "076b5f3f6d1ec3e9c61d4a46605b5060480e95d9"
SOURCE_DIAGNOSIS_CLASSIFICATION = "contradictory_receipt_state"

CANDIDATE_FOLDER = Path("D:/b.WorkSpace/Engel App/runtime/llama.cpp/candidates/llama-b9198-bin-win-cpu-x64")
CANDIDATE_BINARY = CANDIDATE_FOLDER / "llama-cli.exe"
APPROVED_CANDIDATE_ROOT = Path("D:/b.WorkSpace/Engel App/runtime/llama.cpp/candidates")
MODEL_KEY = "tiny_seed"
MODEL_FILE = Path("/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf")

N_PREDICT = 0
CONTEXT_SIZE = 512
THREADS = 4
TIMEOUT_SECONDS = 180
PROCESS_LIST_TIMEOUT_SECONDS = 10
TERMINATE_GRACE_SECONDS = 5
KILL_GRACE_SECONDS = 5

REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_runtime_candidate_validation_replay"
LOG_DIR = REPORT_ROOT / "logs"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_V1.md"

FINAL_DECISION_SUCCESS = (
    "RUNTIME CANDIDATE VALIDATION REPLAY PASSED \u2014 READY FOR SWAP REVIEW ONLY \u2014 "
    "REGISTERED RUNTIME NOT CHANGED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
)
FINAL_DECISION_FAILURE = (
    "RUNTIME CANDIDATE VALIDATION REPLAY FAILED \u2014 "
    "REGISTERED RUNTIME NOT CHANGED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
)
FINAL_DECISION_BLOCKED = (
    "RUNTIME CANDIDATE VALIDATION REPLAY BLOCKED \u2014 "
    "REGISTERED RUNTIME NOT CHANGED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"
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
    "\n> ",
]
DISQUALIFYING_GENERATION_MARKERS = [
    "generation:",
    "tokens predicted",
    "predicted",
    "sampling",
]
SERVER_MARKERS = [
    "llama server",
    "listening",
    "http://",
    "server is listening",
    "api server",
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
    post_process_interruption: bool
    orphan_process_detected: bool
    runtime_process_id: int | None = None
    cleanup_action: str | None = None
    error: str | None = None


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, LOG_DIR, RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)


def write_lf_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def path_text(path: Path) -> str:
    return str(path.resolve(strict=False)).replace("/", "\\")


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return path_text(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def normalize_process_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def bounded_text(value: Any, max_chars: int = MAX_LOG_CHARS) -> tuple[str, bool]:
    text = normalize_process_text(value)
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n[TRUNCATED]\n", True


def append_error(existing: str | None, extra: str | None) -> str | None:
    if not extra:
        return existing
    if not existing:
        return extra
    return existing + "; " + extra


def timeout_output(exc: subprocess.TimeoutExpired) -> tuple[str, str]:
    stdout = getattr(exc, "stdout", None)
    if stdout is None:
        stdout = getattr(exc, "output", None)
    return normalize_process_text(stdout), normalize_process_text(getattr(exc, "stderr", None))


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
        except subprocess.TimeoutExpired:
            cleanup_error = append_error(cleanup_error, "process_cleanup_timeout")
        except OSError as exc:
            cleanup_error = append_error(cleanup_error, "communicate_after_kill_failed: " + str(exc))
    except OSError as exc:
        cleanup_error = append_error(cleanup_error, "communicate_after_terminate_failed: " + str(exc))
    runtime_process_exited = process.poll() is not None
    orphan_process_detected = not runtime_process_exited
    return stdout_text, stderr_text, runtime_process_exited, orphan_process_detected, process.returncode, cleanup_action, cleanup_error


def run_bounded_command(args: list[str], timeout_seconds: int) -> ExecutionResult:
    if not args:
        return ExecutionResult(False, False, True, timeout_seconds, None, "", "", False, False, False, False, False, False, error="empty_args")
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
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            stdout_text, stdout_truncated = bounded_text(stdout)
            stderr_text, stderr_truncated = bounded_text(stderr)
            return ExecutionResult(True, True, True, timeout_seconds, process.returncode, stdout_text, stderr_text, stdout_truncated, stderr_truncated, False, False, False, False, runtime_process_id=process.pid, cleanup_action="none")
        except subprocess.TimeoutExpired as exc:
            stdout_text, stderr_text = timeout_output(exc)
            cleanup_stdout, cleanup_stderr, exited, orphan, exit_code, cleanup_action, cleanup_error = stop_started_process(process)
            stdout_text = cleanup_stdout or stdout_text
            stderr_text = cleanup_stderr or stderr_text
            stdout_text, stdout_truncated = bounded_text(stdout_text)
            stderr_text, stderr_truncated = bounded_text(stderr_text)
            return ExecutionResult(True, True, exited, timeout_seconds, exit_code, stdout_text, stderr_text, stdout_truncated, stderr_truncated, True, False, False, orphan, runtime_process_id=process.pid, cleanup_action=cleanup_action, error=cleanup_error)
    except KeyboardInterrupt:
        if process is not None:
            process_already_exited = process.poll() is not None
            stdout_text, stderr_text, exited, orphan, exit_code, cleanup_action, cleanup_error = stop_started_process(process)
            stdout_text, stdout_truncated = bounded_text(stdout_text)
            stderr_text, stderr_truncated = bounded_text(stderr_text)
            interrupted_during_child_run = not process_already_exited
            return ExecutionResult(
                True,
                True,
                exited,
                timeout_seconds,
                exit_code,
                stdout_text,
                stderr_text,
                stdout_truncated,
                stderr_truncated,
                False,
                interrupted_during_child_run,
                process_already_exited,
                orphan,
                runtime_process_id=process.pid,
                cleanup_action=cleanup_action,
                error=append_error(cleanup_error, "keyboard_interrupt" if interrupted_during_child_run else "post_process_keyboard_interrupt"),
            )
        return ExecutionResult(True, False, True, timeout_seconds, None, "", "", False, False, False, True, False, False, error="keyboard_interrupt_before_start")
    except OSError as exc:
        return ExecutionResult(True, False, True, timeout_seconds, None, "", str(exc), False, False, False, False, False, False, error="process_start_failed: " + str(exc))


def command_args() -> list[str]:
    return [
        path_text(CANDIDATE_BINARY),
        "-m",
        path_text(MODEL_FILE),
        "-p",
        "load check",
        "-n",
        str(N_PREDICT),
        "-c",
        str(CONTEXT_SIZE),
        "-t",
        str(THREADS),
        "--log-disable",
        "--offline",
    ]


def starts_with_path(path_value: str, root_value: str) -> bool:
    path_lower = path_value.casefold()
    root_lower = root_value.casefold().rstrip("\\")
    return path_lower == root_lower or path_lower.startswith(root_lower + "\\")


def candidate_preflight() -> dict[str, Any]:
    folder = path_text(CANDIDATE_FOLDER).rstrip("\\")
    approved_root = path_text(APPROVED_CANDIDATE_ROOT).rstrip("\\")
    binary = path_text(CANDIDATE_BINARY)
    model = path_text(MODEL_FILE)
    reasons: list[str] = []
    if not starts_with_path(folder, approved_root):
        reasons.append("candidate_folder_outside_approved_root")
    if not CANDIDATE_FOLDER.exists() or not CANDIDATE_FOLDER.is_dir():
        reasons.append("candidate_folder_missing")
    if not CANDIDATE_BINARY.exists() or not CANDIDATE_BINARY.is_file():
        reasons.append("candidate_binary_missing")
    if CANDIDATE_BINARY.name.lower() == "llama-server.exe" or "server" in CANDIDATE_BINARY.name.lower():
        reasons.append("server_binary_not_allowed")
    if not MODEL_FILE.exists() or not MODEL_FILE.is_file():
        reasons.append("tiny_seed_model_missing")
    return {
        "candidate_folder": folder,
        "candidate_binary": binary,
        "candidate_under_approved_root": not any(reason == "candidate_folder_outside_approved_root" for reason in reasons),
        "model_key": MODEL_KEY,
        "model_file_path": model,
        "preflight_passed": not reasons,
        "blocked_reasons": reasons,
    }


def list_llama_processes() -> list[dict[str, str]]:
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
        if image_name.lower().startswith("llama"):
            rows.append({"image_name": image_name, "pid": row[1]})
    return rows


def output_marker_analysis(stdout_text: str, stderr_text: str) -> dict[str, Any]:
    combined = (stdout_text + "\n" + stderr_text).lower()
    interactive_hits = [marker for marker in DISQUALIFYING_INTERACTIVE_MARKERS if marker in combined]
    generation_hits = [marker for marker in DISQUALIFYING_GENERATION_MARKERS if marker in combined]
    server_hits = [marker for marker in SERVER_MARKERS if marker in combined]
    generated_text_detected = detect_generated_text(stdout_text, stderr_text)
    return {
        "disqualifying_interactive_markers_found": bool(interactive_hits),
        "disqualifying_generation_markers_found": bool(generation_hits),
        "server_startup_markers_found": bool(server_hits),
        "generated_text_detected": generated_text_detected,
        "interactive_marker_hits": interactive_hits[:20],
        "generation_marker_hits": generation_hits[:20],
        "server_marker_hits": server_hits[:20],
    }


def detect_generated_text(stdout_text: str, stderr_text: str) -> bool:
    combined_lines = (stdout_text + "\n" + stderr_text).splitlines()
    saw_prompt = False
    for raw_line in combined_lines:
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if lower == "> load check":
            saw_prompt = True
            continue
        if saw_prompt:
            if lower.startswith("[") or lower.startswith("exiting") or lower.startswith(">"):
                continue
            if "generation:" in lower or "prompt:" in lower:
                continue
            if lower in {"load check"}:
                continue
            if lower.startswith("llama_") or lower.startswith("main:") or lower.startswith("build:"):
                continue
            if "available commands" in lower:
                continue
            return True
    return False


def safety_fields() -> dict[str, Any]:
    return {
        "registered_runtime_changed": False,
        "runtime_ready_for_inference": False,
        "inference_enabled": False,
        "chat_enabled": False,
        "server_enabled": False,
        "auto_load_enabled": False,
        "trusted_memory_write_enabled": False,
        "provider_api_enabled": False,
        "source_route_queue_mutation": False,
    }


def latest_replay_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("RUNTIME_CANDIDATE_VALIDATION_REPLAY_*.json")):
        data = read_json(path)
        if data.get("runtime_candidate_validation_replay_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def write_log_pair(prefix: str, stdout_text: str, stderr_text: str) -> tuple[str, str]:
    ensure_folders()
    stdout_path = LOG_DIR / f"{prefix}_stdout.txt"
    stderr_path = LOG_DIR / f"{prefix}_stderr.txt"
    write_lf_text(stdout_path, stdout_text)
    write_lf_text(stderr_path, stderr_text)
    return project_relative(stdout_path), project_relative(stderr_path)


def status() -> dict[str, Any]:
    latest = latest_replay_receipt()
    return {
        "runtime_candidate_validation_replay_version": "1",
        "candidate_folder": path_text(CANDIDATE_FOLDER),
        "candidate_binary": path_text(CANDIDATE_BINARY),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "latest_replay_receipt": latest.get("receipt_path") if latest else None,
        "latest_replay_passed": latest.get("candidate_validation_replay_passed") if latest else None,
        "latest_final_decision": latest.get("final_decision") if latest else None,
        **safety_fields(),
    }


def preview() -> dict[str, Any]:
    preflight = candidate_preflight()
    return {
        "runtime_candidate_validation_replay_version": "1",
        "command_preview_only": True,
        "command_style": "llama_cli_prompt_no_generation_offline_replay",
        "command_args": command_args(),
        "preflight": preflight,
        "timeout_seconds": TIMEOUT_SECONDS,
        "no_generation_requested": True,
        "n_predict": N_PREDICT,
        **safety_fields(),
    }


def base_receipt(created_at: str, approval_verified: bool) -> dict[str, Any]:
    return {
        "runtime_candidate_validation_replay_version": "1",
        "created_at": created_at,
        "candidate_folder": path_text(CANDIDATE_FOLDER),
        "candidate_binary": path_text(CANDIDATE_BINARY),
        "model_key": MODEL_KEY,
        "model_file_path": path_text(MODEL_FILE),
        "approval_token_name": APPROVAL_TOKEN,
        "approval_token_verified": approval_verified,
        "source_diagnosis_commit": SOURCE_DIAGNOSIS_COMMIT,
        "source_diagnosis_classification": SOURCE_DIAGNOSIS_CLASSIFICATION,
        "command_style": "llama_cli_prompt_no_generation_offline_replay",
        "command_args": command_args(),
        "timeout_seconds": TIMEOUT_SECONDS,
        "no_generation_requested": True,
        "n_predict": N_PREDICT,
        **safety_fields(),
    }


def blocked_receipt(reason: str, approval_verified: bool, write_receipt: bool) -> dict[str, Any]:
    ensure_folders()
    created_at = now_utc()
    receipt = {
        **base_receipt(created_at, approval_verified),
        "command_executed": False,
        "runtime_process_started": False,
        "runtime_process_exited": False,
        "exit_code": None,
        "timed_out": False,
        "interrupted": False,
        "post_process_interruption": False,
        "orphan_process_detected": False,
        "stdout_log_path": None,
        "stderr_log_path": None,
        "stdout_truncated": False,
        "stderr_truncated": False,
        "disqualifying_interactive_markers_found": False,
        "disqualifying_generation_markers_found": False,
        "generated_text_detected": False,
        "candidate_validation_replay_passed": False,
        "candidate_runtime_ready_for_swap_review": False,
        "blocked_reason": reason,
        "recommended_next_action": "Fix candidate path, token, or preflight issue before any replay.",
        "final_decision": FINAL_DECISION_BLOCKED,
    }
    if write_receipt:
        persist_receipt(receipt)
    return receipt


def persist_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    ensure_folders()
    created_at = str(receipt.get("created_at") or now_utc())
    prefix = f"RUNTIME_CANDIDATE_VALIDATION_REPLAY_{stamp(created_at)}_llama-b9198-bin-win-cpu-x64"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    report_path = PLAN_REPORT_DIR / f"{prefix}.md"
    receipt["receipt_path"] = project_relative(receipt_path)
    receipt["report_path"] = project_relative(report_path)
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    report = render_report(receipt)
    write_lf_text(report_path, report)
    write_lf_text(CODEX_REPORT, report)
    return receipt


def replay(approval: str | None) -> dict[str, Any]:
    approval_verified = approval == APPROVAL_TOKEN
    if not approval_verified:
        return blocked_receipt("approval_token_missing_or_invalid", False, False)
    preflight = candidate_preflight()
    if not preflight["preflight_passed"]:
        receipt = blocked_receipt("preflight_failed: " + ", ".join(preflight["blocked_reasons"]), True, True)
        receipt["preflight"] = preflight
        return receipt
    existing_llama = list_llama_processes()
    if existing_llama:
        receipt = blocked_receipt("llama_process_already_running_before_replay", True, True)
        receipt["pre_existing_llama_processes"] = existing_llama
        return receipt

    ensure_folders()
    created_at = now_utc()
    result = run_bounded_command(command_args(), TIMEOUT_SECONDS)
    prefix = f"RUNTIME_CANDIDATE_VALIDATION_REPLAY_{stamp(created_at)}_llama-b9198-bin-win-cpu-x64"
    stdout_path, stderr_path = write_log_pair(prefix, result.stdout_text, result.stderr_text)
    markers = output_marker_analysis(result.stdout_text, result.stderr_text)
    post_llama_processes = list_llama_processes()
    orphan = result.orphan_process_detected or bool(post_llama_processes)
    passed = (
        approval_verified
        and result.command_executed
        and result.runtime_process_started
        and result.runtime_process_exited
        and result.exit_code == 0
        and not result.timed_out
        and not result.interrupted
        and not result.post_process_interruption
        and not orphan
        and not markers["disqualifying_interactive_markers_found"]
        and not markers["disqualifying_generation_markers_found"]
        and not markers["server_startup_markers_found"]
        and not markers["generated_text_detected"]
    )
    final_decision = FINAL_DECISION_SUCCESS if passed else FINAL_DECISION_FAILURE
    recommended = (
        "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1"
        if passed
        else "Try alternate command style or different runtime candidate; do not swap."
    )
    receipt = {
        **base_receipt(created_at, approval_verified),
        "preflight": preflight,
        "command_executed": result.command_executed,
        "runtime_process_started": result.runtime_process_started,
        "runtime_process_exited": result.runtime_process_exited,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "interrupted": result.interrupted,
        "post_process_interruption": result.post_process_interruption,
        "orphan_process_detected": orphan,
        "post_replay_llama_processes": post_llama_processes,
        "runtime_process_id": result.runtime_process_id,
        "cleanup_action": result.cleanup_action,
        "error": result.error,
        "stdout_log_path": stdout_path,
        "stderr_log_path": stderr_path,
        "stdout_truncated": result.stdout_truncated,
        "stderr_truncated": result.stderr_truncated,
        **markers,
        "candidate_validation_replay_passed": passed,
        "candidate_runtime_ready_for_swap_review": passed,
        "recommended_next_action": recommended,
        "final_decision": final_decision,
    }
    return persist_receipt(receipt)


def render_report(receipt: dict[str, Any] | None = None) -> str:
    data = receipt or latest_replay_receipt() or {}
    ran = data.get("command_executed")
    result = "not run"
    if data.get("final_decision") == FINAL_DECISION_BLOCKED:
        result = "blocked"
    elif data.get("timed_out") is True:
        result = "timed out"
    elif data.get("interrupted") is True or data.get("post_process_interruption") is True:
        result = "interrupted"
    elif data.get("candidate_validation_replay_passed") is True:
        result = "passed"
    elif data:
        result = "failed"
    return f"""# ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_V1

## Summary
Engel replays one bounded runtime candidate validation with corrected interpretation logic.

## Why Replay Exists
The source diagnosis found a contradictory historical validation receipt: the process exited with code `0`, but the receipt also marked `interrupted: true`. The historical stdout showed interactive command-menu / prompt-loop / generation-style markers, so the candidate was not reclassified as clean.

## Source Diagnosis
- commit: `{SOURCE_DIAGNOSIS_COMMIT}`
- classification: `{SOURCE_DIAGNOSIS_CLASSIFICATION}`

## Candidate
- candidate folder: `{data.get("candidate_folder", path_text(CANDIDATE_FOLDER))}`
- candidate binary: `{data.get("candidate_binary", path_text(CANDIDATE_BINARY))}`
- model key: `{data.get("model_key", MODEL_KEY)}`
- model file: `{data.get("model_file_path", path_text(MODEL_FILE))}`

## Command
- style: `{data.get("command_style", "llama_cli_prompt_no_generation_offline_replay")}`
- timeout seconds: `{data.get("timeout_seconds", TIMEOUT_SECONDS)}`
- n_predict: `{data.get("n_predict", N_PREDICT)}`

## Replay Result
- replay ran: `{ran}`
- result: `{result}`
- exit code: `{data.get("exit_code")}`
- timed out: `{data.get("timed_out")}`
- interrupted: `{data.get("interrupted")}`
- post process interruption: `{data.get("post_process_interruption")}`
- disqualifying interactive markers found: `{data.get("disqualifying_interactive_markers_found")}`
- disqualifying generation markers found: `{data.get("disqualifying_generation_markers_found")}`
- generated text detected: `{data.get("generated_text_detected")}`
- orphan process detected: `{data.get("orphan_process_detected")}`
- candidate ready for swap review: `{data.get("candidate_runtime_ready_for_swap_review")}`

## Evidence
- receipt path: `{data.get("receipt_path")}`
- stdout log path: `{data.get("stdout_log_path")}`
- stderr log path: `{data.get("stderr_log_path")}`
- report path: `{data.get("report_path")}`

## Runtime State
- Registered runtime changed: `{data.get("registered_runtime_changed", False)}`
- runtime ready for inference: `{data.get("runtime_ready_for_inference", False)}`
- inference enabled: `{data.get("inference_enabled", False)}`
- chat enabled: `{data.get("chat_enabled", False)}`
- server enabled: `{data.get("server_enabled", False)}`
- trusted memory write enabled: `{data.get("trusted_memory_write_enabled", False)}`

## Verification
- Runtime candidate validation replay verifier: pending run.
- Full Codex verifier: pending run.
- Packaging skipped.

This phase replays one bounded candidate validation with corrected interpretation logic only. It does not change the registered runtime, enable inference, start chat/server mode, write trusted memory, mutate source/routes/queues, download/install anything, or trust model output.
"""


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists():
        write_lf_text(CODEX_REPORT, render_report(None))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel runtime candidate validation replay")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("preview")
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("--approval")
    sub.add_parser("json")
    args = parser.parse_args(argv)
    ensure_folders()
    write_initial_report()
    if args.command == "status":
        print(json.dumps(status(), indent=2, sort_keys=True))
        return 0
    if args.command == "preview":
        print(json.dumps(preview(), indent=2, sort_keys=True))
        return 0
    if args.command == "replay":
        result = replay(args.approval)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("approval_token_verified") is True else 2
    if args.command == "json":
        print(json.dumps({"status": status(), "latest_replay": latest_replay_receipt()}, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
