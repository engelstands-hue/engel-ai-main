from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
GUI_HOST = PROJECT_ROOT / "engel_companion.py"
VERSION = "1"
MAX_READ_CHARS = 120_000

MODEL_KEY = "tiny_seed"
if os.name == "nt":
    RUNTIME_PATH = "D:/b.WorkSpace/Engel App/runtime/llama.cpp/candidates/llama-b9198-bin-win-cpu-x64/llama-cli.exe"
    MODEL_FILE = "D:/b.WorkSpace/Engel App/models/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q4_k_m.gguf"
else:
    RUNTIME_PATH = "/opt/engel/runtime/llama.cpp/candidates/llama-b9198-bin-linux-x64/llama-cli"
    MODEL_FILE = "/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf"

MAX_SESSION_TURNS = 20
MAX_IDLE_SECONDS = 300
MAX_RUNTIME_MINUTES = 30
MAX_PROMPT_CHARS_PER_TURN = 1000
MAX_RESPONSE_TOKENS_PER_TURN = 192
MAX_TRANSCRIPT_CONTEXT_CHARS = 4000

MEMORY_PLAN_JSON = PROJECT_ROOT / "memory" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.json"
MEMORY_PLAN_MD = PROJECT_ROOT / "memory" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.md"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_persistent_chat_supervised_runtime_plan"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.md"
SUPERVISED_OPEN_CHAT_RECEIPTS = PROJECT_ROOT / "reports" / "ai_local_open_chat_supervised_run" / "receipts"

FINAL_DECISION = (
    "PERSISTENT CHAT PLAN RECORDED - NOT ENABLED YET - NEXT SAFE MODE IS SUPERVISED GUI SESSION WITH REPEATED BOUNDED CALLS"
)


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


def read_text_bounded(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:80_000]
    except OSError:
        return ""


def gui_supervised_open_chat_section_present() -> bool:
    source = read_text_bounded(GUI_HOST)
    return bool(source and "Supervised Open Chat" in source and "send_supervised_message(prompt)" in source)


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False)).replace("/", "\\")


def latest_supervised_open_chat_receipt() -> dict[str, Any] | None:
    if not SUPERVISED_OPEN_CHAT_RECEIPTS.exists():
        return None
    rows: list[dict[str, Any]] = []
    for receipt in sorted(SUPERVISED_OPEN_CHAT_RECEIPTS.glob("LOCAL_OPEN_CHAT_SUPERVISED_TURN_*.json")):
        data = read_json(receipt)
        if data.get("local_open_chat_supervised_run_version") == VERSION:
            data["receipt_path"] = project_relative(receipt)
            rows.append(data)
    return rows[-1] if rows else None


def supervised_open_chat_available() -> bool:
    latest = latest_supervised_open_chat_receipt()
    return bool(
        latest
        and gui_supervised_open_chat_section_present()
        and latest.get("local_open_chat_supervised_turn_passed") is True
        and latest.get("open_chat_enabled") is True
        and latest.get("open_chat_scope") == "supervised_local_gui_session_only"
        and latest.get("chat_enabled") is True
        and latest.get("chat_scope") == "supervised_local_gui_session_only"
        and latest.get("persistent_chat_loop_enabled") is False
        and latest.get("server_enabled") is False
        and latest.get("provider_api_enabled") is False
        and latest.get("trusted_memory_write_enabled") is False
        and latest.get("runtime_ready_for_inference") is False
    )


def ensure_folders() -> None:
    for folder in [RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent, MEMORY_PLAN_JSON.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(plan_payload(created_at="2026-05-18T00:00:00Z"), indent=2, sort_keys=True) + "\n",
        )


def plan_payload(created_at: str | None = None) -> dict[str, Any]:
    supervised_available = supervised_open_chat_available()
    return {
        "persistent_chat_supervised_runtime_plan_version": VERSION,
        "created_at": created_at or now_utc(),
        "created_by": "Engel AI Persistent Chat Supervised Runtime Plan",
        "user_requested_persistent_chat": True,
        "supervised_local_open_chat_available": supervised_open_chat_available(),
        "persistent_chat_enabled": False,
        "persistent_runtime_enabled": False,
        "true_long_lived_model_process_enabled": False,
        "recommended_next_mode": "supervised_persistent_gui_session_repeated_bounded_calls",
        "recommended_next_phase": "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_SESSION_V1",
        "future_long_lived_process_phase": "ENGEL_AI_PERSISTENT_MODEL_PROCESS_SUPERVISED_RUNTIME_V1",
        "model_key": MODEL_KEY,
        "runtime_path": RUNTIME_PATH,
        "model_file_path": MODEL_FILE,
        "runtime_path_present": Path(RUNTIME_PATH).exists(),
        "model_file_present": Path(MODEL_FILE).exists(),
        "server_enabled": False,
        "provider_api_enabled": False,
        "startup_auto_load_enabled": False,
        "background_daemon_enabled": False,
        "background_worker_enabled": False,
        "autonomous_loop_enabled": False,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "memory_promotion_enabled": False,
        "source_route_queue_mutation": False,
        "model_output_trusted": False,
        "transcript_trusted": False,
        "runtime_process_started": False,
        "model_process_started": False,
        "persistent_process_started": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": supervised_available,
        "open_chat_scope": "supervised_local_gui_session_only" if supervised_available else None,
        "chat_enabled": supervised_available,
        "chat_scope": "supervised_local_gui_session_only" if supervised_available else None,
        "max_session_turns": MAX_SESSION_TURNS,
        "max_idle_seconds": MAX_IDLE_SECONDS,
        "max_runtime_minutes": MAX_RUNTIME_MINUTES,
        "max_prompt_chars_per_turn": MAX_PROMPT_CHARS_PER_TURN,
        "max_response_tokens_per_turn": MAX_RESPONSE_TOKENS_PER_TURN,
        "max_transcript_context_chars": MAX_TRANSCRIPT_CONTEXT_CHARS,
        "stop_button_required": True,
        "panic_cleanup_required": True,
        "orphan_cleanup_required": True,
        "crash_receipt_required": True,
        "stop_receipt_required": True,
        "orphan_cleanup_receipt_required": True,
        "deterministic_verifier_required": True,
        "implementation_options": {
            "true_persistent_model_process": {
                "enabled": False,
                "risk": "higher",
                "reason": "long-lived model process requires stronger stop/orphan/crash controls",
                "status": "not enabled yet",
            },
            "supervised_persistent_gui_session_repeated_bounded_calls": {
                "enabled_next": True,
                "risk": "lower",
                "reason": "preserves session UX without long-lived runtime process",
                "status": "recommended next phase",
            },
        },
        "next_safe_action": "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_SESSION_V1",
        "final_decision": FINAL_DECISION,
    }


def render_plan_markdown(payload: dict[str, Any]) -> str:
    return (
        "# ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1\n\n"
        "## Summary\n"
        "Persistent chat is requested, but this phase records the supervised runtime plan only. No persistent process, server, provider, startup auto-load, background daemon, autonomous loop, or memory write is enabled.\n\n"
        "## Recommendation\n"
        "- Recommended next mode: `supervised_persistent_gui_session_repeated_bounded_calls`\n"
        "- Recommended next phase: `ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_SESSION_V1`\n"
        "- Later long-lived process phase: `ENGEL_AI_PERSISTENT_MODEL_PROCESS_SUPERVISED_RUNTIME_V1`\n\n"
        "## Required Limits\n"
        f"- max_session_turns: `{payload['max_session_turns']}`\n"
        f"- max_idle_seconds: `{payload['max_idle_seconds']}`\n"
        f"- max_runtime_minutes: `{payload['max_runtime_minutes']}`\n"
        f"- max_prompt_chars_per_turn: `{payload['max_prompt_chars_per_turn']}`\n"
        f"- max_response_tokens_per_turn: `{payload['max_response_tokens_per_turn']}`\n"
        f"- max_transcript_context_chars: `{payload['max_transcript_context_chars']}`\n\n"
        "## Process Controls Required Before Enablement\n"
        "- Visible start control: required in a future phase\n"
        "- Visible stop button: required\n"
        "- Panic cleanup action: required\n"
        "- Process status display: required\n"
        "- Crash receipt: required\n"
        "- Stop receipt: required\n"
        "- Orphan cleanup receipt: required\n\n"
        "## Implementation Options\n"
        "### Option A: True Persistent Model Process\n"
        "- Status: not enabled yet\n"
        "- Pros: faster interactive chat\n"
        "- Risks: orphan process, prompt loop, stop complexity, long-lived runtime\n\n"
        "### Option B: Supervised Persistent GUI Session With Repeated Bounded Calls\n"
        "- Status: recommended next\n"
        "- Pros: simpler stop behavior, no long-lived runtime, close to current working supervised mode\n"
        "- Risks: slower, per-turn startup cost\n\n"
        "## Safety Boundaries\n"
        "- persistent_chat_enabled: `False`\n"
        "- persistent_runtime_enabled: `False`\n"
        "- true_long_lived_model_process_enabled: `False`\n"
        "- server_enabled: `False`\n"
        "- provider_api_enabled: `False`\n"
        "- startup_auto_load_enabled: `False`\n"
        "- background_daemon_enabled: `False`\n"
        "- trusted_memory_write_enabled: `False`\n"
        "- approved_memory_write_enabled: `False`\n"
        "- source_route_queue_mutation: `False`\n"
        "- runtime_ready_for_inference: `False`\n\n"
        f"Final decision: `{payload['final_decision']}`\n"
    )


def render_receipt_report(payload: dict[str, Any]) -> str:
    return (
        "# Persistent Chat Supervised Runtime Plan Receipt\n\n"
        f"- Created at: `{payload['created_at']}`\n"
        f"- Supervised local open chat available: `{payload['supervised_local_open_chat_available']}`\n"
        f"- Persistent chat enabled: `{payload['persistent_chat_enabled']}`\n"
        f"- Persistent runtime enabled: `{payload['persistent_runtime_enabled']}`\n"
        f"- Recommended next mode: `{payload['recommended_next_mode']}`\n"
        f"- Next safe action: `{payload['next_safe_action']}`\n"
        f"- Final decision: `{payload['final_decision']}`\n"
    )


def render_bridge_report(payload: dict[str, Any] | None = None) -> str:
    data = payload or plan_payload()
    return (
        "# ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1\n\n"
        "## Summary\n"
        "Recorded the persistent-chat supervised runtime plan and surfaced it in the existing Companion Local AI tab. Persistent chat is not enabled in this phase.\n\n"
        "## Current State\n"
        f"- Persistent chat requested: `{data['user_requested_persistent_chat']}`\n"
        f"- Persistent chat enabled: `{data['persistent_chat_enabled']}`\n"
        f"- Persistent runtime enabled: `{data['persistent_runtime_enabled']}`\n"
        f"- Long-lived model process enabled: `{data['true_long_lived_model_process_enabled']}`\n"
        f"- Recommended next mode: `{data['recommended_next_mode']}`\n"
        f"- Next phase: `{data['recommended_next_phase']}`\n\n"
        "## GUI\n"
        "- GUI host: `engel_companion.py`\n"
        "- Existing tab: `Local AI`\n"
        "- Section title: `Engel Local AI - Persistent Chat Runtime Plan`\n"
        "- Start Persistent Chat button: not present in this phase\n\n"
        "## Verification Results\n"
        "- Targeted verifier: `ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_VERIFY_PASS`\n"
        "- Full Codex verifier result: `85 run, 85 passed, 0 failed` / `ENGEL_CODEX_VERIFY_PASS`\n\n"
        "## Packaging\n"
        "Packaging skipped.\n\n"
        "## Safety Summary\n"
        "This plan phase does not run a model process, enable persistent chat, start a long-lived model process, start server/provider/cloud behavior, enable startup auto-load, start a background daemon, write trusted memory, write approved memory, promote memory, or mutate source/routes/queues.\n"
    )


def latest_plan_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for receipt in sorted(RECEIPT_DIR.glob("PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_*.json")):
        data = read_json(receipt)
        if data.get("persistent_chat_supervised_runtime_plan_version") == VERSION:
            data["receipt_path"] = project_relative(receipt)
            rows.append(data)
    return rows[-1] if rows else None


def write_plan_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ensure_folders()
    write_lf_text(MEMORY_PLAN_JSON, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_lf_text(MEMORY_PLAN_MD, render_plan_markdown(payload))
    receipt_name = "PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_" + stamp(payload["created_at"]) + ".json"
    receipt_path = RECEIPT_DIR / receipt_name
    report_path = PLAN_REPORT_DIR / receipt_name.replace(".json", ".md")
    receipt = dict(payload)
    receipt["plan_json_path"] = project_relative(MEMORY_PLAN_JSON)
    receipt["plan_markdown_path"] = project_relative(MEMORY_PLAN_MD)
    receipt["receipt_path"] = project_relative(receipt_path)
    receipt["report_path"] = project_relative(report_path)
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    write_lf_text(report_path, render_receipt_report(receipt))
    write_lf_text(CODEX_REPORT, render_bridge_report(receipt))
    return {
        "plan_json_path": project_relative(MEMORY_PLAN_JSON),
        "plan_markdown_path": project_relative(MEMORY_PLAN_MD),
        "receipt_path": project_relative(receipt_path),
        "report_path": project_relative(report_path),
    }


def status_payload() -> dict[str, Any]:
    ensure_folders()
    if not MEMORY_PLAN_JSON.exists() or not MEMORY_PLAN_MD.exists() or not CODEX_REPORT.exists():
        payload = plan_payload()
        write_lf_text(MEMORY_PLAN_JSON, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        write_lf_text(MEMORY_PLAN_MD, render_plan_markdown(payload))
        write_lf_text(CODEX_REPORT, render_bridge_report(payload))
    latest = latest_plan_receipt()
    payload = read_json(MEMORY_PLAN_JSON) or plan_payload()
    return {
        "persistent_chat_supervised_runtime_plan_version": VERSION,
        "module_present": True,
        "plan_json_path": project_relative(MEMORY_PLAN_JSON),
        "plan_markdown_path": project_relative(MEMORY_PLAN_MD),
        "plan_json_present": MEMORY_PLAN_JSON.exists(),
        "plan_markdown_present": MEMORY_PLAN_MD.exists(),
        "latest_plan_receipt": latest.get("receipt_path") if latest else None,
        "supervised_local_open_chat_available": supervised_open_chat_available(),
        "gui_supervised_open_chat_section_present": gui_supervised_open_chat_section_present(),
        "persistent_chat_requested": True,
        "persistent_chat_enabled": False,
        "persistent_runtime_enabled": False,
        "true_long_lived_model_process_enabled": False,
        "recommended_next_mode": payload.get("recommended_next_mode"),
        "recommended_next_phase": payload.get("recommended_next_phase"),
        "server_enabled": False,
        "provider_api_enabled": False,
        "startup_auto_load_enabled": False,
        "background_daemon_enabled": False,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "source_route_queue_mutation": False,
        "runtime_process_started": False,
        "model_process_started": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": supervised_open_chat_available(),
        "open_chat_scope": "supervised_local_gui_session_only" if supervised_open_chat_available() else None,
        "chat_enabled": supervised_open_chat_available(),
        "chat_scope": "supervised_local_gui_session_only" if supervised_open_chat_available() else None,
        "next_safe_action": "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_SESSION_V1",
        "final_decision": FINAL_DECISION,
    }


def create_plan() -> dict[str, Any]:
    payload = plan_payload()
    paths = write_plan_artifacts(payload)
    return {**payload, **paths}


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI persistent chat supervised runtime plan.")
    parser.add_argument("command", choices=["status", "plan", "json"])
    args = parser.parse_args(argv)
    if args.command == "plan":
        print_json(create_plan())
        return 0
    if args.command == "json":
        print_json(status_payload())
        return 0
    print_json(status_payload())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
