#!/usr/bin/env python3
"""Run Engel code-creation prompt training through the visible Main UI.

This is prompt/memory training and regression testing for Engel's code
creation behavior. It does not claim model-weight fine-tuning. The actual
training turns are sent through the same visible Flutter UI runner a user
would use, which then calls Engel Main chat -> local CUDA LLM -> Agent
Meeting Room.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from engel_ui_prompt_training_support import iso_now, redact, stamp  # noqa: E402


TEMPLATE_DIR = ROOT / "memory" / "training" / "templates"
TEMPLATE_PATH = TEMPLATE_DIR / "ENGEL_CODE_CREATION_UI_TRAINING_TEMPLATE.json"
TEMPLATE_MD = TEMPLATE_DIR / "ENGEL_CODE_CREATION_UI_TRAINING_TEMPLATE.md"
RUNS_DIR = ROOT / "reports" / "codex_bridge" / "code_creation_ui_training_runs"
CODE_MEMORY_JSONL = ROOT / "memory" / "training" / "ENGEL_CODE_CREATION_UI_TRAINING_MEMORY.jsonl"
LATEST_STATUS = ROOT / "memory" / "training" / "ENGEL_CODE_CREATION_UI_TRAINING_LATEST_RUN.json"
PERSISTENT_CHAT_MEMORY_JSONL = ROOT / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
FLUTTER_TRAINER = TOOLS / "run_engel_flutter_main_ui_prompt_training.py"
RUNPOD_CHAT = TOOLS / "run_engel_runpod_chat.py"
VERIFIER = TOOLS / "verify_engel_standalone_chat_llm.py"
CHAT_RECEIPT_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"


BASE_PROMPTS = [
    (
        "plain_request_python_tool",
        "Engel, make me a tiny Python CLI tool that reads a file path argument and prints the number of non-empty lines.",
    ),
    (
        "python_function_tests",
        "Engel AI Main, create code: write a Python function named normalize_phone_number plus two pytest tests.",
    ),
    (
        "debug_patch_plain_user",
        "Engel, this loop skips items after deletion; create the corrected Python code and explain the one-line bug fix.",
    ),
    (
        "javascript_plain_app_request",
        "Can you build a small JavaScript function named debounce for my UI search box?",
    ),
    (
        "typescript_api_client",
        "Engel AI Main, create code: write a TypeScript fetch helper named getJson with typed success and error results.",
    ),
    (
        "html_css_ui",
        "Engel, build a compact HTML/CSS card with a green Engel action button and keyboard-focus styling.",
    ),
    (
        "flutter_dart_widget",
        "Engel AI Main, create code: write a Flutter Dart widget named EngelStatusChip that shows online, training, or blocked states.",
    ),
    (
        "rust_cli_parser",
        "Engel, write a Rust function that parses --name and --count arguments into a small struct without panicking.",
    ),
    (
        "rust_no_std_kernel",
        "Engel AI Main, create code: write a Rust no_std kernel-style function named clamp_irq_priority that clamps a u8 to 0..15.",
    ),
    (
        "c_header_api",
        "Engel AI Main, create code: write a C header file for a tiny ring buffer API named engel_ring_buffer.",
    ),
    (
        "linux_kernel_module",
        "Engel AI Main, create code: write a safe minimal Linux kernel module in C named engel_hello that logs when it loads and unloads.",
    ),
    (
        "windows_kmdf_skeleton",
        "Engel AI Main, create code: write a safe Windows KMDF driver skeleton in C with DriverEntry and EvtDeviceAdd stubs only.",
    ),
    (
        "powershell_function",
        "Engel, create a PowerShell function named Test-EngelPath that returns true if a path exists and false otherwise.",
    ),
    (
        "sql_schema_query",
        "Engel AI Main, create code: write a SQL table for agent_training_events and a query that counts failures by category.",
    ),
    (
        "meeting_room_code_review",
        "Engel, use the Agent Meeting Room for this code task: create a small patch-review checklist for generated code and include a verifier step.",
    ),
]


COMPLEX_PROMPTS = [
    (
        "python_async_job_queue",
        "Engel AI Main, create complex code: write a single-file Python async job queue with a Job dataclass, retry/backoff, an in-memory status map, cancellation support, and two pytest-style tests.",
    ),
    (
        "typescript_typed_event_bus",
        "Engel AI Main, create complex code: write a TypeScript typed event bus with on, once, off, emit, unsubscribe cleanup, isolated handler errors, and a usage example.",
    ),
    (
        "rust_task_scheduler",
        "Engel AI Main, create complex code: write a Rust module for a bounded task scheduler with TaskState enum, typed SchedulerError, add/start/finish/fail methods, and unit tests.",
    ),
    (
        "flutter_agent_dashboard",
        "Engel AI Main, create complex code: write a Flutter ChangeNotifier controller plus an AgentStatusPanel widget for online, training, blocked, and retry states.",
    ),
    (
        "c_ring_buffer_impl",
        "Engel AI Main, create complex code: write a C header and source implementation for engel_ring_buffer with init, capacity, push, pop, peek, reset, and bounds checks.",
    ),
    (
        "python_fastapi_work_order",
        "Engel AI Main, create complex code: write a FastAPI work-order endpoint with Pydantic request/response models, validation, an in-memory store, and one unit test.",
    ),
    (
        "tauri_rust_command",
        "Engel AI Main, create complex code: write a Tauri Rust command handler that validates a workspace-relative path, calls an async service, and returns a serializable result struct.",
    ),
    (
        "node_hash_cli",
        "Engel AI Main, create complex code: write a Node.js CLI that scans a directory, hashes files, handles permission errors, and writes a JSON report.",
    ),
    (
        "sql_agent_jobs_migration",
        "Engel AI Main, create complex code: write a SQL migration for agent_jobs, agent_job_events, retry tracking, indexes, and two queries for failure categories and queue age.",
    ),
    (
        "linux_kernel_device_skeleton",
        "Engel AI Main, create complex code: write a safe minimal Linux kernel char-device skeleton in C with module init/exit, open/release stubs, and clear TODO boundaries.",
    ),
    (
        "powershell_service_health",
        "Engel AI Main, create complex code: write a PowerShell health-check module with Test-EngelService, Get-EngelProcessSummary, structured output, and error handling.",
    ),
    (
        "debug_state_machine_refactor",
        "Engel AI Main, create complex code: refactor a crashing app flow into a typed state machine with idle, loading, success, retrying, and failed states plus tests.",
    ),
]


ADVANCED_PROMPTS = [
    (
        "python_dag_orchestrator",
        "Engel AI Main, create advanced code: implement a Python async DAG workflow orchestrator with typed task definitions, dependency validation, cancellation, exponential retry/backoff, structured event logs, and pytest tests.",
    ),
    (
        "rust_actor_supervisor",
        "Engel AI Main, create advanced code: implement a Rust actor supervisor module with typed messages, bounded mailboxes, restart policy, backpressure errors, health snapshots, and unit tests.",
    ),
    (
        "typescript_plugin_sandbox",
        "Engel AI Main, create advanced code: implement a TypeScript plugin runtime with a permission manifest, isolated command dispatch, timeout handling, audit logs, typed result envelopes, and example plugins.",
    ),
    (
        "flutter_streaming_console",
        "Engel AI Main, create advanced code: implement a Flutter streaming log console with ChangeNotifier state, severity filters, search highlighting, pause/resume, virtualized rows, and widget tests.",
    ),
    (
        "go_circuit_breaker_client",
        "Engel AI Main, create advanced code: implement a Go HTTP client with circuit breaker states, retry budget, request context cancellation, structured errors, metrics counters, and table-driven tests.",
    ),
    (
        "sql_outbox_migration",
        "Engel AI Main, create advanced code: implement a PostgreSQL transactional outbox migration for agent work orders with idempotency keys, leases, retry attempts, dead-letter status, indexes, and worker polling queries.",
    ),
    (
        "cpp_lockfree_queue",
        "Engel AI Main, create advanced code: implement a modern C++ bounded multi-producer single-consumer queue with atomics, false-sharing padding, try_push, try_pop, shutdown semantics, and minimal tests.",
    ),
    (
        "python_incremental_parser",
        "Engel AI Main, create advanced code: implement a Python incremental JSONL stream parser with backpressure hooks, malformed-line quarantine, metrics, file checkpointing, and pytest tests.",
    ),
    (
        "rust_tauri_model_router",
        "Engel AI Main, create advanced code: implement a Tauri Rust local-model router command with serde request/response structs, workspace path validation, provider selection, timeout errors, and tests.",
    ),
    (
        "node_worker_pool",
        "Engel AI Main, create advanced code: implement a Node.js worker-thread pool with typed job envelopes, concurrency limits, cancellation tokens, structured error propagation, and a usage example.",
    ),
    (
        "powershell_install_auditor",
        "Engel AI Main, create advanced code: implement a PowerShell install-audit module with Test-EngelInstallBoundary, Get-EngelGpuStatus, signed-result objects, transcript logging, and Pester-style tests.",
    ),
    (
        "linux_kernel_ioctl_skeleton",
        "Engel AI Main, create advanced code: implement a safe minimal Linux kernel miscdevice skeleton in C with ioctl command definitions, input validation, locking, module init/exit, and TODO boundaries.",
    ),
]


RUNPOD_ASSIST_PROMPT = """Engel code-creation UI training assist.
Return 3 lines beginning with NEW_PROMPT: for future Engel Main chat training.
Prompts must train code creation from plain user language and explicit requests.
Cover systems/kernel-safe code, app/UI code, and debugging. Do not include unsafe exploit, malware, credential theft, or auto-apply instructions."""


RUNPOD_COMPLEX_ASSIST_PROMPT = """Engel complex code-creation UI training assist.
Return 3 lines beginning with NEW_PROMPT: for future Engel Main chat training.
Prompts must require complex but safe code: multi-function modules, typed state, tests, validation, error handling, or app/system integration.
Keep each prompt suitable for one visible Engel Main chat reply. Do not include unsafe exploit, malware, credential theft, or auto-apply instructions."""


RUNPOD_ADVANCED_ASSIST_PROMPT = """Engel advanced code-creation UI training assist.
Return 3 lines beginning with NEW_PROMPT: for future Engel Main chat training.
Each NEW_PROMPT must be phrased as an explicit code request starting with: Engel AI Main, create advanced code: implement ...
Prompts must require advanced but safe source code: concurrency, typed orchestration, durable queues, local-model routing, verifier harnesses, kernel-safe skeletons, or cross-platform systems integration.
Keep each prompt suitable for one visible Engel Main chat reply. Do not include unsafe exploit, malware, credential theft, kernel exploit, persistence, or auto-apply instructions."""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.drive.lower() == "c:":
        raise RuntimeError(f"refusing to write Engel training artifact on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    if path.drive.lower() == "c:":
        raise RuntimeError(f"refusing to write Engel training memory on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact(payload), sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def text_blob(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(text_blob(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(text_blob(item) for item in value)
    return "" if value is None else str(value)


def extract_new_prompts(text: str) -> list[str]:
    prompts: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        match = re.search(r"\bNEW_PROMPT\s*:\s*(.+)$", clean, flags=re.IGNORECASE)
        if match:
            prompt = re.sub(r"\s+", " ", match.group(1).strip())
        else:
            prompt = re.sub(r"^\s*(?:\d+[\).]\s*|[-*]\s*)", "", clean)
            prompt = re.sub(r"\s+", " ", prompt.strip())
            if not prompt.lower().startswith("engel ai main, create"):
                continue
        if 40 <= len(prompt) <= 500:
            prompts.append(prompt)
            if len(prompts) >= 3:
                break
    return prompts


def runpod_assist(timeout: int, prompt_profile: str) -> dict[str, Any]:
    if prompt_profile == "advanced":
        assist_prompt = RUNPOD_ADVANCED_ASSIST_PROMPT
    elif prompt_profile == "complex":
        assist_prompt = RUNPOD_COMPLEX_ASSIST_PROMPT
    else:
        assist_prompt = RUNPOD_ASSIST_PROMPT
    command = [
        sys.executable,
        str(RUNPOD_CHAT),
        "--prompt",
        assist_prompt,
        "--timeout",
        str(timeout),
        "--max-tokens",
        "420",
        "--temperature",
        "0.2",
    ]
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout + 20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    result: dict[str, Any] = {
        "ok": completed.returncode == 0,
        "return_code": completed.returncode,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-2000:],
        "new_prompts": [],
        "receipt_path": "",
    }
    try:
        payload = json.loads(completed.stdout)
        if isinstance(payload, dict):
            result["receipt_path"] = str(payload.get("workspace_receipt_path") or "")
            result["new_prompts"] = extract_new_prompts(str(payload.get("assistant_reply") or ""))
    except Exception:
        result["new_prompts"] = extract_new_prompts(completed.stdout)
    return result


def profile_prompts(prompt_profile: str) -> list[tuple[str, str]]:
    if prompt_profile == "advanced":
        return ADVANCED_PROMPTS
    return COMPLEX_PROMPTS if prompt_profile == "complex" else BASE_PROMPTS


def normalize_assisted_prompt(prompt: str, prompt_profile: str) -> str:
    prompt = re.sub(r"\s+", " ", prompt.strip()).rstrip(".")
    if not prompt or prompt_profile not in {"complex", "advanced"}:
        return prompt
    level = "advanced" if prompt_profile == "advanced" else "complex"
    prefixed = re.match(rf"(?i)^engel ai main,\s*create\s+{level}\s+code:\s*(.+)$", prompt)
    if prefixed:
        body = prefixed.group(1).strip()
    else:
        match = re.match(r"(?i)^(create|design|develop|implement|build|write)\s+(.+)$", prompt)
        body = match.group(2).strip() if match else prompt
    body = re.sub(r"(?i)^(create|design|develop|implement|build|write)\s+", "", body).strip()
    suffix = "with concrete source code, validation/error handling, and tests or a runnable usage example"
    if suffix in body.lower():
        return f"Engel AI Main, create {level} code: implement {body}."
    return (
        f"Engel AI Main, create {level} code: implement {body} "
        f"{suffix}."
    )


def unique_prompts(extra: list[str], prompt_profile: str) -> list[str]:
    prompts: list[str] = []
    seen: set[str] = set()
    for _name, prompt in profile_prompts(prompt_profile):
        key = re.sub(r"\s+", " ", prompt.strip().lower())
        if key not in seen:
            seen.add(key)
            prompts.append(prompt)
    for prompt in extra:
        prompt = normalize_assisted_prompt(prompt, prompt_profile)
        key = re.sub(r"\s+", " ", prompt.strip().lower())
        if key not in seen:
            seen.add(key)
            prompts.append(prompt)
    return prompts


def render_template_md(template: dict[str, Any]) -> str:
    lines = [
        "# Engel Code Creation UI Training Template",
        "",
        f"- Template ID: {template['template_id']}",
        f"- Prompt profile: {template.get('prompt_profile', 'base')}",
        f"- Updated: {template['updated_at_utc']}",
        f"- Minimum duration minutes: {template['minimum_duration_minutes']}",
        "- Entry: visible Engel AI Main chat UI.",
        "- Route: Engel Main chat -> local CUDA LLM -> Agent Meeting Room -> selected code/verifier/device agents.",
        "- Training type: prompt/memory training and regression testing, not model-weight fine-tuning.",
        "- Google Drive policy: communication/collaboration only; no Engel item storage.",
        "",
        "## Prompts",
    ]
    for index, prompt in enumerate(template["active_prompts"], start=1):
        lines.append(f"{index}. {prompt}")
    return "\n".join(lines).rstrip() + "\n"


def prepare_template(
    run_id: str,
    runpod_result: dict[str, Any] | None = None,
    prompt_profile: str = "base",
    prompt_cycles: int = 1,
) -> dict[str, Any]:
    runpod_result = runpod_result or {}
    base_prompts = unique_prompts(
        [str(item) for item in runpod_result.get("new_prompts", [])],
        prompt_profile,
    )
    prompt_cycles = max(1, int(prompt_cycles))
    prompts: list[str] = []
    cycle_focus = [
        "full implementation quality",
        "validation and typed input boundaries",
        "error handling and recovery behavior",
        "tests and runnable examples",
        "agent meeting room routing assumptions",
        "local model and GPU resource awareness",
        "Sub-Engel handoff clarity",
        "verifier and audit receipt coverage",
    ]
    for cycle in range(1, prompt_cycles + 1):
        focus = cycle_focus[(cycle - 1) % len(cycle_focus)]
        for prompt in base_prompts:
            if prompt_cycles == 1:
                prompts.append(prompt)
            else:
                prompts.append(f"{prompt} Cycle {cycle} focus: {focus}.")
    template = {
        "schema": "engel_code_creation_ui_training_template_v1",
        "template_id": (
            "engel_advanced_code_creation_ui_training_one_hour"
            if prompt_profile == "advanced"
            else (
                "engel_complex_code_creation_ui_training_one_hour"
                if prompt_profile == "complex"
                else "engel_code_creation_ui_training_one_hour"
            )
        ),
        "updated_at_utc": iso_now(),
        "run_id_prepared_for": run_id,
        "prompt_profile": prompt_profile,
        "training_type": "prompt_memory_training_not_weight_finetune",
        "weight_finetune_performed": False,
        "minimum_duration_minutes": 60,
        "entry_point": "visible Engel AI Main chat UI",
        "route": "Engel Main chat -> local standalone CUDA LLM -> Agent Meeting Room -> selected code/verifier/device agents",
        "google_drive_policy": "communication_and_collaboration_only_no_engel_item_storage",
        "ui_trigger_phrases": [
            "run Engel code creation UI training",
            "run the saved Engel code creation one-hour training template",
            "start Engel code creation prompt training",
        ],
        "active_prompts": prompts,
        "smoke_prompts": prompts[:3],
        "base_prompt_count": len(base_prompts),
        "prompt_cycles": prompt_cycles,
        "cycle_prompt_sets": [{"cycle": 1, "minutes": 60, "prompts": prompts}],
        "coverage": [
            "plain user requests that imply code creation",
            "explicit create-code prompts",
            "debugging and patch-style prompts",
            "Python, JavaScript, TypeScript, HTML/CSS, Flutter/Dart, Rust, Rust no_std, C, Linux kernel module, Windows KMDF skeleton, PowerShell, SQL",
            "Agent Meeting Room routing and verifier behavior",
        ]
        + (
            [
                "complex multi-function and multi-structure modules",
                "typed state, validation, error handling, retry/cancellation, tests, or integration boundaries",
            ]
            if prompt_profile in {"complex", "advanced"}
            else []
        ),
        "regression_rules": [
            "Do not say Engel cannot write code.",
            "Return concrete source code when the user asks for code.",
            "Use safe minimal skeletons for legitimate kernel, driver, and firmware requests.",
            "Do not claim code was compiled, applied, or installed unless a receipt proves it.",
            "Record each turn with local receipt proof.",
        ],
        "runpod_assist": runpod_result,
        "main_code_training_memory": str(CODE_MEMORY_JSONL),
    }
    write_json(TEMPLATE_PATH, template)
    TEMPLATE_MD.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATE_MD.write_text(render_template_md(template), encoding="utf-8")
    return template


def receipt_has_code_artifact(receipt: dict[str, Any]) -> bool:
    reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
    lowered = reply.lower()
    if "```" in reply:
        return True
    patterns = [
        r"(?m)^\s*def\s+[a-zA-Z_][a-zA-Z0-9_]*",
        r"(?m)^\s*function\s+[A-Za-z][A-Za-z0-9_-]*\s*\{",
        r"(?m)^\s*(pub\s+)?fn\s+[A-Za-z_][A-Za-z0-9_]*\s*\(",
        r"(?m)^\s*#include\s+[<\"].+[>\"]",
        r"(?is)<(?:html|style|button)\b",
    ]
    return any(re.search(pattern, reply) for pattern in patterns) or "module_init(" in lowered or "driverentry" in lowered


def receipt_has_complex_markers(receipt: dict[str, Any], prompt: str) -> bool:
    reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
    lowered = reply.lower()
    prompt_lowered = prompt.lower()
    if not receipt_has_code_artifact(receipt):
        return False
    marker_groups = [
        ["class ", "dataclass", "enum ", "struct ", "interface ", "type "],
        ["error", "exception", "result<", "try ", "catch", "raise", "throws"],
        ["test", "pytest", "#[test]", "assert", "expect("],
        ["async", "await", "future", "promise"],
        ["state", "status", "retry", "cancel", "validation", "validate"],
        ["impl ", "module_init", "driverentry", "create table", "index", "function "],
    ]
    hits = sum(1 for group in marker_groups if any(term in lowered for term in group))
    if "complex code" in prompt_lowered or "advanced code" in prompt_lowered:
        return hits >= 2
    return hits >= 1


def summarize_training(session: dict[str, Any], prompt_profile: str = "base") -> dict[str, Any]:
    prompt_results = session.get("prompt_results") if isinstance(session.get("prompt_results"), list) else []
    turn_summaries: list[dict[str, Any]] = []
    code_artifact_count = 0
    complex_artifact_count = 0
    failed_code_artifacts: list[str] = []
    failed_complex_artifacts: list[str] = []
    for item in prompt_results:
        if not isinstance(item, dict):
            continue
        wrapper_path = Path(str(item.get("wrapper_receipt_path") or ""))
        wrapper = read_json(wrapper_path) if wrapper_path.exists() else {}
        has_code = receipt_has_code_artifact(wrapper)
        has_complex = receipt_has_complex_markers(wrapper, str(item.get("prompt") or ""))
        if has_code:
            code_artifact_count += 1
        else:
            failed_code_artifacts.append(str(item.get("prompt_index")))
        if has_complex:
            complex_artifact_count += 1
        elif prompt_profile in {"complex", "advanced"}:
            failed_complex_artifacts.append(str(item.get("prompt_index")))
        turn_summaries.append(
            {
                "prompt_index": item.get("prompt_index"),
                "status": item.get("status"),
                "prompt": item.get("prompt"),
                "wrapper_receipt_path": str(wrapper_path),
                "meeting_room_order_id": wrapper.get("meeting_room_order_id"),
                "provider": wrapper.get("provider"),
                "gpu_backend": wrapper.get("gpu_backend"),
                "agent_meeting_room_used": wrapper.get("agent_meeting_room_used"),
                "station_results": wrapper.get("meeting_room_station_results"),
                "code_artifact_present": has_code,
                "complex_artifact_markers_present": has_complex,
            }
        )
    return {
        "turn_count": len(turn_summaries),
        "done_count": sum(1 for item in turn_summaries if item.get("status") == "DONE"),
        "code_artifact_count": code_artifact_count,
        "complex_artifact_count": complex_artifact_count,
        "failed_code_artifact_prompt_indexes": failed_code_artifacts,
        "failed_complex_artifact_prompt_indexes": failed_complex_artifacts,
        "turns": turn_summaries,
    }


def failed_training_turns(code_summary: dict[str, Any], prompt_profile: str) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for item in code_summary.get("turns", []):
        if not isinstance(item, dict):
            continue
        reasons: list[str] = []
        if item.get("status") != "DONE":
            reasons.append("ui_or_meeting_room_status_not_done")
        if item.get("code_artifact_present") is not True:
            reasons.append("missing_code_artifact")
        if prompt_profile in {"complex", "advanced"} and item.get("complex_artifact_markers_present") is not True:
            reasons.append("missing_complex_or_advanced_code_markers")
        if reasons:
            failed.append(
                {
                    "prompt_index": item.get("prompt_index"),
                    "prompt": item.get("prompt"),
                    "reasons": reasons,
                    "wrapper_receipt_path": item.get("wrapper_receipt_path"),
                    "meeting_room_order_id": item.get("meeting_room_order_id"),
                }
            )
    return failed


def repair_prompt(turn: dict[str, Any], prompt_profile: str) -> str:
    prompt = re.sub(r"\s+", " ", str(turn.get("prompt") or "").strip())
    reasons = ", ".join(str(item) for item in turn.get("reasons", []))
    level = "advanced" if prompt_profile == "advanced" else "complex" if prompt_profile == "complex" else "concrete"
    return (
        "Engel AI Main, repair this code-creation training failure through the Agent Meeting Room. "
        f"Return {level} source code in fenced code blocks, plus validation/error handling and tests or a runnable usage example. "
        f"Failure reasons: {reasons}. Original prompt: {prompt}"
    )


def write_repair_template(run_dir: Path, run_id: str, failed_turns: list[dict[str, Any]], prompt_profile: str) -> Path:
    repair_prompts = [repair_prompt(turn, prompt_profile) for turn in failed_turns]
    path = run_dir / "repair_template.json"
    payload = {
        "schema": "engel_code_creation_ui_training_repair_template_v1",
        "template_id": "engel_code_creation_ui_training_repair",
        "updated_at_utc": iso_now(),
        "run_id_prepared_for": run_id,
        "prompt_profile": prompt_profile,
        "training_type": "prompt_memory_training_repair_not_weight_finetune",
        "entry_point": "visible Engel AI Main chat UI",
        "route": "Engel Main chat -> local standalone CUDA LLM -> Agent Meeting Room -> selected code/verifier/device agents",
        "failed_turns": failed_turns,
        "smoke_prompts": repair_prompts,
        "active_prompts": repair_prompts,
        "cycle_prompt_sets": [{"cycle": 1, "minutes": 0, "prompts": repair_prompts}],
    }
    write_json(path, payload)
    return path


def run_repair_pass(
    *,
    run_dir: Path,
    run_id: str,
    failed_turns: list[dict[str, Any]],
    prompt_profile: str,
    per_prompt_timeout: int,
) -> dict[str, Any]:
    if not failed_turns:
        return {"status": "SKIPPED", "reason": "no failed training turns"}
    repair_template = write_repair_template(run_dir, run_id, failed_turns, prompt_profile)
    repair_log = run_dir / "repair_ui_prompts.log"
    repair_cmd = [
        sys.executable,
        str(FLUTTER_TRAINER),
        "--mode",
        "smoke",
        "--minutes",
        "1",
        "--per-prompt-timeout",
        str(per_prompt_timeout),
        "--template",
        str(repair_template),
    ]
    repair_rc = run_command_to_log(repair_cmd, repair_log, timeout=max(900, per_prompt_timeout * (len(failed_turns) + 2)))
    repair_session = read_json(ROOT / "memory" / "training" / "ENGEL_UI_PROMPT_TRAINING_SESSION.json")
    repair_summary = summarize_training(repair_session, prompt_profile)
    expected = len(failed_turns)
    repair_blockers: list[str] = []
    if repair_rc != 0:
        repair_blockers.append(f"repair UI prompt runner returned {repair_rc}; see {repair_log}")
    if repair_summary.get("turn_count") != expected:
        repair_blockers.append(f"repair turn count {repair_summary.get('turn_count')} did not match expected {expected}")
    if repair_summary.get("done_count") != expected:
        repair_blockers.append("one or more repair prompts did not finish DONE")
    if repair_summary.get("code_artifact_count") != expected:
        repair_blockers.append("one or more repair prompts lacked a code artifact")
    if prompt_profile in {"complex", "advanced"} and repair_summary.get("complex_artifact_count") != expected:
        repair_blockers.append("one or more repair prompts lacked complex/advanced artifact markers")
    return {
        "status": "PASS" if not repair_blockers else "FAIL",
        "repair_return_code": repair_rc,
        "repair_template_path": str(repair_template),
        "repair_log": str(repair_log),
        "failed_turns_repaired": failed_turns,
        "repair_summary": repair_summary,
        "blockers": repair_blockers,
    }


def run_command_to_log(command: list[str], log_path: Path, timeout: int | None = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": "command_start", "command": command, "started_at_utc": iso_now()}) + "\n")
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        handle.write(json.dumps({"event": "command_end", "return_code": completed.returncode, "finished_at_utc": iso_now()}) + "\n")
        return completed.returncode


def run_training(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or "engel_code_creation_ui_training_" + stamp()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    status: dict[str, Any] = {
        "schema": "engel_code_creation_ui_training_run_v1",
        "run_id": run_id,
        "status": "RUNNING",
        "started_at_utc": iso_now(),
        "requested_minutes": args.minutes,
        "prompt_profile": args.prompt_profile,
        "template_path": str(TEMPLATE_PATH),
        "template_markdown_path": str(TEMPLATE_MD),
        "run_dir": str(run_dir),
        "blockers": [],
    }
    write_json(LATEST_STATUS, status)

    runpod_result: dict[str, Any] = {"ok": None, "skipped": True}
    if args.runpod_assist:
        try:
            runpod_result = runpod_assist(args.runpod_timeout, args.prompt_profile)
        except Exception as exc:
            runpod_result = {"ok": False, "error": str(exc), "skipped": False}
    template = prepare_template(run_id, runpod_result, args.prompt_profile, args.prompt_cycles)
    status["runpod_assist"] = runpod_result
    status["prompt_count"] = len(template["active_prompts"])
    status["base_prompt_count"] = template.get("base_prompt_count")
    status["prompt_cycles"] = template.get("prompt_cycles")
    write_json(LATEST_STATUS, status)

    if not args.skip_smoke:
        smoke_log = run_dir / "smoke.log"
        smoke_cmd = [
            sys.executable,
            str(FLUTTER_TRAINER),
            "--mode",
            "smoke",
            "--minutes",
            str(args.smoke_minutes),
            "--per-prompt-timeout",
            str(args.per_prompt_timeout),
            "--template",
            str(TEMPLATE_PATH),
        ]
        status["smoke_log"] = str(smoke_log)
        smoke_rc = run_command_to_log(smoke_cmd, smoke_log, timeout=max(900, args.per_prompt_timeout * 4))
        status["smoke_return_code"] = smoke_rc
        if smoke_rc != 0:
            status["blockers"].append(f"smoke run failed; see {smoke_log}")
            status["status"] = "FAIL"
            write_json(LATEST_STATUS, status)
            write_json(run_dir / "summary.json", status)
            return status

    hour_log = run_dir / ("training_8_hour.log" if args.minutes >= 480 else "one_hour.log")
    hour_cmd = [
        sys.executable,
        str(FLUTTER_TRAINER),
        "--mode",
        "one-hour",
        "--minutes",
        str(args.minutes),
        "--per-prompt-timeout",
        str(args.per_prompt_timeout),
        "--template",
        str(TEMPLATE_PATH),
        "--template-cycle",
        "1",
    ]
    status["one_hour_log"] = str(hour_log)
    write_json(LATEST_STATUS, status)
    hour_rc = run_command_to_log(hour_cmd, hour_log, timeout=max(int(args.minutes * 60) + 1800, args.per_prompt_timeout * (len(template["active_prompts"]) + 2)))
    status["one_hour_return_code"] = hour_rc
    if hour_rc != 0:
        status["scheduled_training_status"] = "FAIL"
        status["scheduled_training_blocker"] = f"UI training returned {hour_rc}; see {hour_log}"
    else:
        status["scheduled_training_status"] = "PASS"

    session = read_json(ROOT / "memory" / "training" / "ENGEL_UI_PROMPT_TRAINING_SESSION.json")
    code_summary = summarize_training(session, args.prompt_profile)
    status["session_path"] = str(ROOT / "memory" / "training" / "ENGEL_UI_PROMPT_TRAINING_SESSION.json")
    status["code_summary"] = code_summary
    failed_turns = failed_training_turns(code_summary, args.prompt_profile)
    status["failed_training_turns"] = failed_turns

    repair_result: dict[str, Any] = {"status": "SKIPPED", "reason": "auto repair disabled or no failed turns"}
    if args.auto_repair and failed_turns:
        repair_result = run_repair_pass(
            run_dir=run_dir,
            run_id=run_id,
            failed_turns=failed_turns,
            prompt_profile=args.prompt_profile,
            per_prompt_timeout=args.per_prompt_timeout,
        )
        status["post_repair_status"] = "REPAIRED_WITH_UI_PROOF" if repair_result.get("status") == "PASS" else "REPAIR_FAILED"
    status["repair_result"] = repair_result
    training_failures_repaired = bool(failed_turns) and repair_result.get("status") == "PASS"

    if code_summary["turn_count"] == 0:
        status["blockers"].append("no UI training turns found in latest session")
    if failed_turns and not training_failures_repaired:
        if code_summary["done_count"] != code_summary["turn_count"]:
            status["blockers"].append("one or more UI training turns did not finish DONE")
        if code_summary["code_artifact_count"] != code_summary["turn_count"]:
            status["blockers"].append("one or more code training turns lacked a code artifact")
        if args.prompt_profile in {"complex", "advanced"} and code_summary["complex_artifact_count"] != code_summary["turn_count"]:
            status["blockers"].append("one or more complex-code training turns lacked complex artifact markers")
    if hour_rc != 0 and not training_failures_repaired:
        status["blockers"].append(status.get("scheduled_training_blocker", f"UI training returned {hour_rc}; see {hour_log}"))

    verifier_log = run_dir / "verifier.log"
    verifier_rc = run_command_to_log([sys.executable, str(VERIFIER)], verifier_log, timeout=1200)
    status["verifier_log"] = str(verifier_log)
    status["verifier_return_code"] = verifier_rc
    status["verifier_latest_path"] = str(ROOT / "runtime" / "engel_standalone_chat_llm_verifier_latest.json")
    if verifier_rc != 0:
        status["blockers"].append(f"post-training verifier failed; see {verifier_log}")

    status["finished_at_utc"] = iso_now()
    status["actual_duration_seconds"] = round(time.perf_counter() - started, 3)
    status["status"] = "PASS" if not status["blockers"] else "FAIL"
    status["code_training_memory_path"] = str(CODE_MEMORY_JSONL)
    status["persistent_chat_memory_path"] = str(PERSISTENT_CHAT_MEMORY_JSONL)
    write_json(LATEST_STATUS, status)
    write_json(run_dir / "summary.json", status)
    append_jsonl(CODE_MEMORY_JSONL, status)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--smoke-minutes", type=float, default=3.0)
    parser.add_argument("--per-prompt-timeout", type=int, default=760)
    parser.add_argument("--runpod-assist", action="store_true")
    parser.add_argument("--runpod-timeout", type=int, default=180)
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--prompt-profile", choices=["base", "complex", "advanced"], default="base")
    parser.add_argument("--no-auto-repair", dest="auto_repair", action="store_false")
    parser.set_defaults(auto_repair=True)
    parser.add_argument(
        "--prompt-cycles",
        type=int,
        default=1,
        help="repeat the local prompt bank this many times with cycle-specific focus text",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_training(args)
    print(json.dumps(redact(result), indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
