#!/usr/bin/env python3
"""Run Engel AI Main app-creation training through the visible chat UI.

This is prompt/memory training and regression testing, not model-weight
fine-tuning. It reuses the existing Flutter UI prompt runner so the work enters
through the same visible Engel AI Main chat surface a user would use.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "memory" / "training" / "templates"
TEMPLATE_PATH = TEMPLATE_DIR / "ENGEL_APP_CREATION_MULTI_AGENT_UI_TEMPLATE.json"
TEMPLATE_MD = TEMPLATE_DIR / "ENGEL_APP_CREATION_MULTI_AGENT_UI_TEMPLATE.md"
LATEST_RUN = ROOT / "memory" / "training" / "ENGEL_APP_CREATION_UI_TRAINING_LATEST_RUN.json"
MEMORY_JSONL = ROOT / "memory" / "training" / "ENGEL_APP_CREATION_UI_TRAINING_MEMORY.jsonl"
REPORT_PATH = ROOT / "reports" / "codex_bridge" / "ENGEL_APP_CREATION_MULTI_AGENT_UI_TRAINING_LATEST.md"
RUN_ROOT = ROOT / "reports" / "app_creation_training"
UI_RUNNER = ROOT / "tools" / "run_engel_flutter_main_ui_prompt_training.py"
SESSION_PATH = ROOT / "memory" / "training" / "ENGEL_UI_PROMPT_TRAINING_SESSION.json"


APP_CREATION_PROMPTS = [
    (
        "Engel AI Main, create a complete Flutter desktop app named SignalForge Studio. "
        "Use the Agent Meeting Room and split the job across UI, state, local-storage, "
        "graphics, verifier, and build agents. Return a multi-file scaffold with file tree, "
        "pubspec.yaml, lib/main.dart, themed Mac-style navigation, CustomPaint or canvas-style "
        "visual graphics, responsive screens, app state model, persistence boundary, and widget "
        "tests. Do not claim it was compiled unless the receipt proves it."
    ),
    (
        "Engel AI Main, create a Tauri + React + TypeScript app named DeviceSwarm Atlas. "
        "Use the Agent Meeting Room for multi-agent collaboration: frontend agent, Rust command "
        "agent, 3D graphics agent, model-routing agent, and verifier agent. Return concrete code "
        "for package.json, src/App.tsx, src/styles.css, src-tauri command skeleton, a Three.js or "
        "canvas device swarm scene, typed device data, add-device dialog, and tests or verification "
        "steps."
    ),
    (
        "Engel AI Main, create a Python + Qt desktop program named MemoryMap Builder. "
        "Use the Agent Meeting Room and assign agents for UI graphics, model selection, file IO, "
        "persistent memory, and test verification. Return file tree, pyproject.toml, main window "
        "code, graphics-rich timeline/tree view, settings panel, JSONL memory writer, unit tests, "
        "and a run/build guide."
    ),
    (
        "Engel AI Main, create a web app named PromptFoundry Pro with Vite, React, and detailed UI "
        "graphics. Use Agent Meeting Room collaboration among design, component, data, verifier, "
        "and accessibility agents. Return multi-file code for package.json, src/main.tsx, "
        "components, state store, polished dark Mac-style interface, animated visual preview, "
        "keyboard-safe controls, and Vitest tests."
    ),
    (
        "Engel AI Main, create a Rust backend plus Flutter front end app named LocalModel Console. "
        "Use Agent Meeting Room and select the correct agents for Rust routes, Flutter UI, local "
        "LLM runtime, GPU status, verifier, and installer. Return concrete Rust structs/functions, "
        "Flutter screens, model selector, graphical runtime meters, persistent settings, tests, "
        "and build verification."
    ),
    (
        "Engel AI Main, create a full small game/app named SwarmGrid Mission Control. Use Agent "
        "Meeting Room multi-agent collaboration with gameplay/UI, graphics, storage, device "
        "simulation, and verifier roles. Return multi-file code, rendering loop or canvas graphics, "
        "device nodes with status interactions, settings, tests, and packaging notes."
    ),
]


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def render_template_md(template: dict[str, Any]) -> str:
    lines = [
        "# Engel App Creation Multi-Agent UI Training Template",
        "",
        f"- Template ID: {template['template_id']}",
        f"- Updated: {template['updated_at_utc']}",
        f"- Minimum duration minutes: {template['minimum_duration_minutes']}",
        "- Entry: visible Engel AI Main chat UI.",
        "- Route: Engel Main chat -> local CUDA LLM -> Agent Meeting Room -> selected UI/code/verifier/device agents.",
        "- Training type: prompt/memory training and regression testing, not model-weight fine-tuning.",
        "- Purpose: teach and test complete app/program creation with detailed UI graphics and multi-agent collaboration.",
        "- Google Drive policy: communication/collaboration only; no Engel item storage.",
        "",
        "## Prompts",
    ]
    for index, prompt in enumerate(template["active_prompts"], start=1):
        lines.append(f"{index}. {prompt}")
    return "\n".join(lines).rstrip() + "\n"


def prepare_template(prompt_cycles: int) -> dict[str, Any]:
    prompt_cycles = max(1, int(prompt_cycles))
    prompts: list[str] = []
    cycle_focus = [
        "multi-file app scaffold and runnable entry points",
        "detailed UI graphics, layout polish, and interaction states",
        "multi-agent Meeting Room role split and selected device/system routes",
        "tests, verifier receipts, and build/run boundaries",
    ]
    for cycle in range(1, prompt_cycles + 1):
        focus = cycle_focus[(cycle - 1) % len(cycle_focus)]
        for prompt in APP_CREATION_PROMPTS:
            if prompt_cycles == 1:
                prompts.append(prompt)
            else:
                prompts.append(f"{prompt} Cycle {cycle} focus: {focus}.")
    template = {
        "schema": "engel_app_creation_multi_agent_ui_training_template_v1",
        "template_id": "engel_app_creation_multi_agent_ui_training",
        "updated_at_utc": iso_now(),
        "training_type": "prompt_memory_training_not_weight_finetune",
        "weight_finetune_performed": False,
        "minimum_duration_minutes": 60,
        "entry_point": "visible Engel AI Main chat UI",
        "route": "Engel Main chat -> local standalone CUDA LLM -> Agent Meeting Room -> selected UI/code/verifier/device agents",
        "google_drive_policy": "communication_and_collaboration_only_no_engel_item_storage",
        "active_prompts": prompts,
        "smoke_prompts": prompts[:3],
        "base_prompt_count": len(APP_CREATION_PROMPTS),
        "prompt_cycles": prompt_cycles,
        "cycle_prompt_sets": [{"cycle": 1, "minutes": 60, "prompts": prompts}],
        "coverage": [
            "complete app/program creation",
            "multi-file scaffolds and file trees",
            "Flutter, React/Tauri, Python Qt, Rust backend plus UI",
            "detailed UI graphics, canvas/CustomPaint/Three.js style scenes, animation, responsive layout",
            "multi-agent collaboration and Agent Meeting Room routing",
            "tests, verifier receipts, build/run boundaries, and persistent memory writes",
        ],
        "regression_rules": [
            "Do not answer with a static description only.",
            "Return concrete file names and code blocks for app/program requests.",
            "Split substantial app requests across UI, backend/runtime, graphics, verifier, and build agents.",
            "Use Android workers and Sub-Engels only when the creation job requires them.",
            "Do not claim an app was built, compiled, installed, or run without receipt evidence.",
            "Record each visible UI turn into persistent Engel memory.",
        ],
        "main_app_creation_memory": str(MEMORY_JSONL),
    }
    write_json(TEMPLATE_PATH, template)
    TEMPLATE_MD.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATE_MD.write_text(render_template_md(template), encoding="utf-8")
    return template


def run_command_to_log(command: list[str], log_path: Path, timeout: int) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(command) + "\n\n")
        handle.flush()
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert process.stdout is not None
        started = time.time()
        for line in process.stdout:
            handle.write(line)
            handle.flush()
            print(line, end="", flush=True)
            if time.time() - started > timeout:
                process.kill()
                handle.write("\nTIMEOUT\n")
                return 124
        return process.wait()


def receipt_text(receipt: dict[str, Any]) -> str:
    fields = [
        receipt.get("assistant_reply"),
        receipt.get("assistant_output_text"),
        receipt.get("local_llm_reply"),
        receipt.get("meeting_room_reply"),
        receipt.get("meeting_room_returned_previews"),
        receipt.get("meeting_room_station_results"),
    ]
    return "\n".join(json.dumps(item, ensure_ascii=True) if isinstance(item, (list, dict)) else str(item or "") for item in fields)


def app_artifact_markers(text: str) -> dict[str, bool]:
    lowered = text.lower()
    return {
        "code_blocks": "```" in text,
        "file_tree_or_files": any(
            term in lowered
            for term in [
                "file tree",
                "pubspec.yaml",
                "package.json",
                "pyproject.toml",
                "src/",
                "lib/",
                "main.dart",
                "app.tsx",
                "src-tauri",
            ]
        ),
        "ui_framework": any(
            term in lowered
            for term in [
                "flutter",
                "react",
                "tauri",
                "typescript",
                "qt",
                "custompaint",
                "three.js",
                "canvas",
            ]
        ),
        "graphics": any(
            term in lowered
            for term in [
                "graphics",
                "custompaint",
                "canvas",
                "three.js",
                "animation",
                "shader",
                "asset",
                "responsive",
                "visual",
            ]
        ),
        "multi_agent": any(
            term in lowered
            for term in [
                "agent meeting room",
                "ui agent",
                "frontend agent",
                "graphics agent",
                "verifier agent",
                "build agent",
                "agent",
            ]
        ),
        "tests_or_verifier": any(
            term in lowered
            for term in [
                "test",
                "widget test",
                "vitest",
                "pytest",
                "unit test",
                "verification",
                "verifier",
                "flutter test",
            ]
        ),
        "build_or_run_boundary": any(
            term in lowered
            for term in [
                "build",
                "run",
                "install",
                "compile",
                "receipt",
                "do not claim",
                "verification step",
            ]
        ),
    }


def summarize_session(session: dict[str, Any]) -> dict[str, Any]:
    prompt_results = session.get("prompt_results") if isinstance(session.get("prompt_results"), list) else []
    turns: list[dict[str, Any]] = []
    app_artifact_count = 0
    missing: list[str] = []
    for item in prompt_results:
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("wrapper_receipt_path") or ""))
        wrapper = read_json(path) if path.exists() else {}
        markers = app_artifact_markers(receipt_text(wrapper))
        score = sum(1 for value in markers.values() if value)
        has_app_artifact = bool(score >= 6 and markers.get("code_blocks") and markers.get("multi_agent"))
        if has_app_artifact:
            app_artifact_count += 1
        else:
            missing.append(str(item.get("prompt_index")))
        turns.append(
            {
                "prompt_index": item.get("prompt_index"),
                "status": item.get("status"),
                "creation_job": item.get("creation_job"),
                "agent_meeting_room_used": item.get("agent_meeting_room_used"),
                "meeting_room_order_id": item.get("order_id"),
                "wrapper_receipt_path": str(path),
                "markers": markers,
                "marker_score": score,
                "app_artifact_present": has_app_artifact,
            }
        )
    ui_summary = session.get("summary") if isinstance(session.get("summary"), dict) else {}
    return {
        "turn_count": len(turns),
        "done_count": sum(1 for item in turns if item.get("status") == "DONE"),
        "app_artifact_count": app_artifact_count,
        "missing_app_artifact_prompt_indexes": missing,
        "meeting_room_order_count": ui_summary.get("meeting_room_order_count"),
        "meeting_room_required_order_count": ui_summary.get("meeting_room_required_order_count"),
        "persistent_chat_memory_appended_count": ui_summary.get("persistent_chat_memory_appended_count"),
        "local_llm_only": ui_summary.get("local_llm_only"),
        "selected_providers": ui_summary.get("selected_providers"),
        "no_c_drive_output_paths": ui_summary.get("no_c_drive_output_paths"),
        "turns": turns,
    }


def write_report(result: dict[str, Any]) -> None:
    summary = result.get("app_summary", {})
    lines = [
        "# Engel App Creation Multi-Agent UI Training",
        "",
        f"- Updated: {result.get('finished_at_utc')}",
        f"- Status: {result.get('status')}",
        f"- Mode: {result.get('mode')}",
        f"- Template: {result.get('template_path')}",
        f"- UI session: {result.get('ui_session_path')}",
        f"- UI runner return code: {result.get('ui_runner_return_code')}",
        f"- Prompts done: {summary.get('done_count')} / {summary.get('turn_count')}",
        f"- App artifacts present: {summary.get('app_artifact_count')} / {summary.get('turn_count')}",
        f"- Meeting Room orders: {summary.get('meeting_room_order_count')} / {summary.get('meeting_room_required_order_count')}",
        f"- Persistent memory appends: {summary.get('persistent_chat_memory_appended_count')}",
        f"- Local LLM only: {summary.get('local_llm_only')}",
        f"- No C drive output paths: {summary.get('no_c_drive_output_paths')}",
        "",
        "## Turn Receipts",
    ]
    for turn in summary.get("turns", []):
        lines.append(
            f"- Prompt {turn.get('prompt_index')}: status={turn.get('status')} "
            f"app_artifact={turn.get('app_artifact_present')} "
            f"order={turn.get('meeting_room_order_id')} receipt={turn.get('wrapper_receipt_path')}"
        )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_memory(result: dict[str, Any]) -> None:
    MEMORY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["smoke", "one-hour"], default="smoke")
    parser.add_argument("--minutes", type=float, default=30.0)
    parser.add_argument("--smoke-minutes", type=float, default=9.0)
    parser.add_argument("--per-prompt-timeout", type=int, default=900)
    parser.add_argument("--prompt-cycles", type=int, default=1)
    args = parser.parse_args(argv)

    template = prepare_template(args.prompt_cycles)
    run_id = "engel_app_creation_ui_training_" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = RUN_ROOT / run_id
    mode_minutes = args.smoke_minutes if args.mode == "smoke" else args.minutes
    command = [
        sys.executable,
        str(UI_RUNNER),
        "--mode",
        args.mode,
        "--minutes",
        str(mode_minutes),
        "--per-prompt-timeout",
        str(args.per_prompt_timeout),
        "--template",
        str(TEMPLATE_PATH),
    ]
    if args.mode == "one-hour":
        command.extend(["--template-cycle", "1"])
    timeout = max(int(mode_minutes * 60) + 1800, args.per_prompt_timeout * (len(template["active_prompts"]) + 1))
    rc = run_command_to_log(command, run_dir / f"{args.mode}.log", timeout=timeout)
    session = read_json(SESSION_PATH)
    app_summary = summarize_session(session)
    blockers: list[str] = []
    if rc != 0:
        blockers.append(f"ui_runner_return_code={rc}")
    if app_summary.get("done_count") != app_summary.get("turn_count") or not app_summary.get("turn_count"):
        blockers.append("not every app-creation prompt completed through visible Engel Main chat")
    if app_summary.get("app_artifact_count") != app_summary.get("turn_count"):
        blockers.append("one or more prompts did not return app-specific multi-file/code/graphics/agent evidence")
    if app_summary.get("meeting_room_order_count") != app_summary.get("meeting_room_required_order_count"):
        blockers.append("one or more app-creation prompts did not produce a Meeting Room order")
    if not app_summary.get("persistent_chat_memory_appended_count"):
        blockers.append("persistent chat memory append count missing or zero")
    result = {
        "schema": "engel_app_creation_ui_training_run_v1",
        "run_id": run_id,
        "status": "PASS" if not blockers else "FAIL",
        "started_template_at_utc": template["updated_at_utc"],
        "finished_at_utc": iso_now(),
        "mode": args.mode,
        "requested_minutes": mode_minutes,
        "template_path": str(TEMPLATE_PATH),
        "template_markdown_path": str(TEMPLATE_MD),
        "ui_session_path": str(SESSION_PATH),
        "ui_runner_return_code": rc,
        "app_summary": app_summary,
        "blockers": blockers,
        "report_path": str(REPORT_PATH),
        "memory_jsonl": str(MEMORY_JSONL),
    }
    write_json(LATEST_RUN, result)
    append_memory(result)
    write_report(result)
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
