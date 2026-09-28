#!/usr/bin/env python3
"""Saved Engel prompt-training template runner.

This is prompt/memory training, not a claim of model-weight fine-tuning. It
drives the visible Engel Main chat, routes prompts through the Agent Meeting
Room, and saves reviewable training records to local Engel storage.
Google Drive is used only for Sub-Engel communication work orders/results.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
os.chdir(ROOT)

from engel_ui_prompt_training_support import (  # noqa: E402
    build_agent_proposals,
    build_device_selection,
    iso_now,
    prompt_bank,
    redact,
    stamp,
)


MEMORY_DIR = ROOT / "memory" / "training"
TEMPLATE_DIR = MEMORY_DIR / "templates"
TEMPLATE_PATH = TEMPLATE_DIR / "ENGEL_LOCAL_LLM_AGENT_MEETING_ROOM_PROMPT_TRAINING_TEMPLATE.json"
TEMPLATE_MD = TEMPLATE_DIR / "ENGEL_LOCAL_LLM_AGENT_MEETING_ROOM_PROMPT_TRAINING_TEMPLATE.md"
LATEST_STATUS = MEMORY_DIR / "ENGEL_PROMPT_TRAINING_TEMPLATE_LATEST_RUN.json"
MAIN_MEMORY_JSONL = MEMORY_DIR / "ENGEL_MAIN_LOCAL_LLM_PROMPT_TRAINING_MEMORY.jsonl"
REPORT_DIR = ROOT / "reports" / "codex_bridge"
RUNS_DIR = REPORT_DIR / "training_template_runs"
CHAT_RECEIPT_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
RUNPOD_CHAT_RECEIPT_DIRS = [
    ROOT / "reports" / "engel_runpod_chat" / "receipts",
    Path(os.environ.get("ENGEL_RUNPOD_CHAT_RECEIPT_DIR", str(ROOT / "runtime" / "runpod" / "chat_receipts"))),
]
FLUTTER_TRAINER = TOOLS / "run_engel_flutter_main_ui_prompt_training.py"
SUB_ROOT = Path(os.environ.get("ENGEL_WINDOWS_SUB_NODE_ROOT", "D:/EngelWindowsSubNode"))
SUB_TEMPLATE_DIR = SUB_ROOT / "workspace" / "training" / "templates"
SUB_MEMORY_DIR = SUB_ROOT / "state" / "local_llm_training"
SUB_MEMORY_JSONL = SUB_MEMORY_DIR / "ENGEL_SUB_ENGEL_LOCAL_LLM_PROMPT_TRAINING_MEMORY.jsonl"
SUB_LATEST_STATUS = SUB_MEMORY_DIR / "ENGEL_PROMPT_TRAINING_TEMPLATE_LATEST_RUN.json"
SHARED_ROOM = Path(
    os.environ.get(
        "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
        str(ROOT / "run" / "sub_engel_transport"),
    )
)
WORK_ORDER_DIR = SHARED_ROOM / "SUB_ENGEL_WORK_ORDERS"
ACTIVE_WORK_REQUEST = SHARED_ROOM / "SUB_ENGEL_ACTIVE_WORK_REQUEST.json"
SUB_AGENT = (
    ROOT
    / "workflows"
    / "sub_engel_nodes"
    / "standalone"
    / "agent"
    / "engel_windows_sub_node_agent.py"
)

SELF_GROWTH_PROMPT = (
    "Run Engel UI prompt training self-growth: Review recent local training receipts, "
    "Agent Meeting Room routing results, and Sub-Engel returned-result summaries. "
    "Create two future training prompts labeled NEW_PROMPT: that are useful, bounded, "
    "device-aware, and not duplicates of prior prompts. Keep all outputs local and review-only."
)
SUB_ENGEL_REQUIRED_PROMPTS = [
    (
        "Run Engel UI prompt training Sub-Engel local LLM step A: Agent Meeting Room must select the best "
        "Sub-Engel node by stable node_id, send a communication-only work order, and require the Sub-Engel "
        "local LLM to return reviewable output."
    ),
    (
        "Run Engel UI prompt training Sub-Engel local LLM step B: Verify the selected Sub-Engel has its "
        "local model manifest, CUDA llama.cpp runtime, and LoRA artifact visible from its local node root."
    ),
    (
        "Run Engel UI prompt training Sub-Engel local LLM step C: Save the Sub-Engel training memory locally "
        "under the node root, and verify Google Drive was used only as the communication lane."
    ),
    (
        "Run Engel UI prompt training Sub-Engel local LLM step D: Compare Main local LLM output with "
        "Sub-Engel local LLM output, then record which agent/device should handle the next similar task."
    ),
]

TRIGGER_PROMPT = (
    "Run the saved Engel four-hour local LLM prompt-training template now. "
    "Use the Engel Main chat UI, local LLM, Agent Meeting Room, device selection, "
    "and Sub-Engel communication lane. Save training records locally only, not in Google Drive."
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    if path.drive.lower() == "c:":
        raise RuntimeError(f"refusing to write Engel training artifact on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    if path.drive.lower() == "c:":
        raise RuntimeError(f"refusing to write Engel training memory on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact(payload), sort_keys=True) + "\n")


def _text_blob(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text_blob(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text_blob(item) for item in value)
    return "" if value is None else str(value)


def _prompt_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _add_prompt(prompts: list[dict[str, str]], seen: set[str], text: str, source: str) -> None:
    clean = re.sub(r"\s+", " ", text.strip())
    if len(clean) < 35 or len(clean) > 1200:
        return
    key = _prompt_key(clean)
    if key in seen:
        return
    seen.add(key)
    prompts.append({"prompt": clean, "source": source})


def _extract_new_prompt_markers(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        match = re.search(r"\bNEW_PROMPT\s*:\s*(.+)$", line.strip(), flags=re.IGNORECASE)
        if match:
            out.append(match.group(1).strip())
    return out


def harvest_prompt_pool(operator_prompt: str = "") -> list[dict[str, str]]:
    prompts: list[dict[str, str]] = []
    seen: set[str] = set()
    for text in prompt_bank("one-hour"):
        _add_prompt(prompts, seen, text, "seed_prompt_bank")
    _add_prompt(prompts, seen, SELF_GROWTH_PROMPT, "self_growth_prompt")
    for text in SUB_ENGEL_REQUIRED_PROMPTS:
        _add_prompt(prompts, seen, text, "required_sub_engel_local_llm_prompt")

    existing = _load_json(TEMPLATE_PATH)
    if isinstance(existing, dict):
        for text in existing.get("active_prompts", []) + existing.get("learned_prompts", []):
            _add_prompt(prompts, seen, str(text), "existing_template")

    for text in _extract_new_prompt_markers(operator_prompt):
        _add_prompt(prompts, seen, text, "operator_prompt_new_prompt_marker")

    session = _load_json(MEMORY_DIR / "ENGEL_UI_PROMPT_TRAINING_SESSION.json")
    if isinstance(session, dict):
        for item in session.get("prompt_results", []):
            if isinstance(item, dict):
                _add_prompt(prompts, seen, str(item.get("prompt") or ""), "previous_training_session")
                for text in _extract_new_prompt_markers(_text_blob(item)):
                    _add_prompt(prompts, seen, text, "previous_training_new_prompt_marker")

    if CHAT_RECEIPT_DIR.exists():
        receipts = sorted(
            CHAT_RECEIPT_DIR.glob("ENGEL_UI_CHAT_MEETING_ROOM_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[:80]
        for path in receipts:
            payload = _load_json(path)
            if not isinstance(payload, dict):
                continue
            order = payload.get("meeting_room_order") if isinstance(payload.get("meeting_room_order"), dict) else {}
            for key in ("order_text", "effective_order_text", "prompt"):
                _add_prompt(prompts, seen, str(order.get(key) or payload.get(key) or ""), f"chat_receipt:{path.name}")
            for text in _extract_new_prompt_markers(_text_blob(payload)):
                _add_prompt(prompts, seen, text, f"chat_receipt_new_prompt_marker:{path.name}")

    for receipt_dir in RUNPOD_CHAT_RECEIPT_DIRS:
        if not receipt_dir.exists():
            continue
        receipts = sorted(
            receipt_dir.glob("ENGEL_RUNPOD_CHAT_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[:40]
        for path in receipts:
            payload = _load_json(path)
            if not isinstance(payload, dict):
                continue
            for text in _extract_new_prompt_markers(_text_blob(payload)):
                _add_prompt(prompts, seen, text, f"runpod_chat_receipt_new_prompt_marker:{path.name}")

    return prompts


def runpod_assist_receipts() -> list[str]:
    receipts: list[str] = []
    seen: set[str] = set()
    for receipt_dir in RUNPOD_CHAT_RECEIPT_DIRS:
        if not receipt_dir.exists():
            continue
        for path in sorted(
            receipt_dir.glob("ENGEL_RUNPOD_CHAT_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[:20]:
            payload = _load_json(path)
            if not isinstance(payload, dict):
                continue
            if not _extract_new_prompt_markers(_text_blob(payload)):
                continue
            text = str(path)
            if text in seen:
                continue
            seen.add(text)
            receipts.append(text)
    return receipts


def _make_cycle_sets(active_prompts: list[str], cycles: int) -> list[dict[str, Any]]:
    seed = prompt_bank("one-hour")
    learned = [prompt for prompt in active_prompts if _prompt_key(prompt) not in {_prompt_key(item) for item in seed}]
    sets: list[dict[str, Any]] = []
    for cycle in range(1, cycles + 1):
        extra = learned[(cycle - 1) * 3 : cycle * 3]
        if not extra:
            extra = learned[:3]
        cycle_prompts: list[str] = []
        seen: set[str] = set()
        for item in seed[:9] + extra + [SELF_GROWTH_PROMPT]:
            key = _prompt_key(item)
            if key not in seen:
                seen.add(key)
                cycle_prompts.append(item)
        sets.append(
            {
                "cycle": cycle,
                "minutes": 60,
                "prompts": cycle_prompts,
                "self_growth_enabled": True,
            }
        )
    return sets


def render_template_markdown(template: dict[str, Any]) -> str:
    lines = [
        "# Engel Local LLM Agent Meeting Room Prompt Training Template",
        "",
        f"- Template ID: {template.get('template_id')}",
        f"- Updated: {template.get('updated_at_utc')}",
        f"- Minimum duration minutes: {template.get('minimum_duration_minutes')}",
        "- Training type: prompt/memory training, not model-weight fine-tuning.",
        "- Entry: Engel Main chat UI.",
        "- Route: Engel Main chat -> local LLM -> Agent Meeting Room -> selected device/agent.",
        "- Storage: local D:/F: Engel storage only. Google Drive is communication/collab only.",
        "- Self-growth: enabled via NEW_PROMPT markers and prior receipts.",
        "",
        "## Active Prompts",
    ]
    for index, prompt in enumerate(template.get("active_prompts", []), start=1):
        lines.append(f"{index}. {prompt}")
    return "\n".join(lines).rstrip() + "\n"


def prepare_template(operator_prompt: str = "", cycles: int = 4, minutes_per_cycle: float = 60.0) -> dict[str, Any]:
    pool = harvest_prompt_pool(operator_prompt)
    active_prompts = [item["prompt"] for item in pool]
    selection = build_device_selection("training_template_prepare_" + stamp())
    proposals = build_agent_proposals(selection)
    template = {
        "schema": "engel_local_llm_agent_meeting_room_prompt_training_template_v1",
        "template_id": "engel_four_hour_local_llm_agent_meeting_room_prompt_training",
        "updated_at_utc": iso_now(),
        "training_type": "prompt_memory_training_not_weight_finetune",
        "weight_finetune_performed": False,
        "minimum_duration_minutes": int(cycles * minutes_per_cycle),
        "default_cycles": cycles,
        "default_minutes_per_cycle": minutes_per_cycle,
        "entry_point": "Engel Main chat UI",
        "ui_trigger_phrases": [
            "run the saved Engel four-hour local LLM prompt-training template",
            "start Engel prompt training template",
            "run saved four hour training template",
        ],
        "route": "Engel Main chat -> local standalone LLM -> Agent Meeting Room -> selected device/agent",
        "google_drive_policy": "communication_and_collaboration_only_no_engel_item_storage",
        "main_local_training_memory": str(MAIN_MEMORY_JSONL),
        "sub_engel_local_training_memory": str(SUB_MEMORY_JSONL),
        "sub_engel_node_root": str(SUB_ROOT),
        "active_prompts": active_prompts,
        "smoke_prompts": active_prompts[:3],
        "learned_prompts": [item["prompt"] for item in pool if item["source"] != "seed_prompt_bank"],
        "prompt_sources": pool,
        "runpod_assist_receipts": runpod_assist_receipts(),
        "cycle_prompt_sets": _make_cycle_sets(active_prompts, cycles),
        "self_growth_rules": [
            "Harvest NEW_PROMPT markers from prior local receipts.",
            "Keep prompts bounded, device-aware, and routed through Agent Meeting Room.",
            "Use stable device IDs first; treat addresses as temporary metadata.",
            "Do not claim model-weight training unless a real fine-tune receipt exists.",
        ],
        "device_selection_preview": selection,
        "agent_proposals_preview": proposals,
    }
    _write_json(TEMPLATE_PATH, template)
    _write_json(SUB_TEMPLATE_DIR / TEMPLATE_PATH.name, template)
    _write_json(SUB_MEMORY_DIR / "ENGEL_LOCAL_LLM_AGENT_MEETING_ROOM_PROMPT_TRAINING_TEMPLATE.json", template)
    TEMPLATE_MD.write_text(render_template_markdown(template), encoding="utf-8")
    (SUB_TEMPLATE_DIR / TEMPLATE_MD.name).write_text(render_template_markdown(template), encoding="utf-8")
    return template


def _training_memory_event(event: str, run_id: str, payload: dict[str, Any]) -> None:
    record = {
        "schema": "engel_local_llm_prompt_training_memory_event_v1",
        "event": event,
        "run_id": run_id,
        "recorded_at_utc": iso_now(),
        "training_type": "prompt_memory_training_not_weight_finetune",
        "payload": payload,
    }
    _append_jsonl(MAIN_MEMORY_JSONL, record)
    _append_jsonl(SUB_MEMORY_JSONL, record)


def _write_status(status: dict[str, Any]) -> None:
    _write_json(LATEST_STATUS, status)
    _write_json(SUB_LATEST_STATUS, status)


def _publish_sub_engel_comm(run_id: str, phase: str) -> dict[str, Any]:
    if not (SHARED_ROOM.exists() and SUB_AGENT.exists()):
        return {"ok": False, "reason": "shared_room_or_agent_missing", "google_drive_use": "communication_only"}
    WORK_ORDER_DIR.mkdir(parents=True, exist_ok=True)
    order_id = f"engel_prompt_training_comm_{phase}_{stamp()}"
    order_path = WORK_ORDER_DIR / f"{order_id}.json"
    selected_node = _select_sub_engel_comm_node(run_id)
    order = {
        "id": order_id,
        "job_type": "local_training_coordination",
        "target": "windows_sub_engel_node",
        "target_label": "Sub-Engel local LLM",
        "proof_required": True,
        "selected_node": selected_node,
        "order_text": (
            f"Communication-only update for Engel local prompt training run {run_id}, phase {phase}. "
            f"Use local Sub-Engel LLM status and return a concise coordination result. "
            f"Training artifacts stay on local node paths, including {SUB_MEMORY_JSONL}. "
            "Do not save Engel items in Google Drive; the shared room is only the collaboration lane."
        ),
    }
    _write_json(order_path, order)
    _write_json(
        ACTIVE_WORK_REQUEST,
        {
            "order_id": order_id,
            "work_order_name": order_path.name,
            "created_at_utc": iso_now(),
            "source": "engel_prompt_training_template_communication_only",
        },
    )
    completed = subprocess.run(
        [sys.executable, str(SUB_AGENT), "process-latest-work-order"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=210,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {
        "ok": completed.returncode == 0,
        "google_drive_use": "communication_only",
        "order_path": str(order_path),
        "return_code": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def _select_sub_engel_comm_node(run_id: str) -> dict[str, Any]:
    fallback = {
        "node_root": str(SUB_ROOT),
        "stable_id": os.environ.get("COMPUTERNAME", ""),
        "source": "fallback_sub_engel_local_llm_root",
    }
    try:
        from engel_ui_prompt_training_support import build_device_selection

        selection = build_device_selection(f"{run_id}_sub_engel_comm")
        decision = next(
            (
                item
                for item in selection.get("decisions", [])
                if item.get("task_type") == "sub_engel_node_task" and item.get("selected_device_id")
            ),
            None,
        )
        if not isinstance(decision, dict):
            return fallback
        node_id = str(decision.get("selected_device_id") or decision.get("selected_stable_identity") or "")
        session_path = ROOT / "remote_nodes" / "windows_sub_engel" / "nodes" / node_id / "session.json"
        session = _load_json(session_path)
        node_root = str(session.get("node_root") or SUB_ROOT) if isinstance(session, dict) else str(SUB_ROOT)
        return {
            "node_id": node_id,
            "stable_id": str(decision.get("selected_stable_identity") or node_id),
            "label": str(decision.get("selected_label") or node_id),
            "node_root": node_root,
            "address": str(decision.get("current_discovered_address") or ""),
            "selection_source": str(decision.get("address_source") or session_path),
            "selection_method": str(decision.get("selection_method") or ""),
            "source": "engel_agent_meeting_room_device_selection",
        }
    except Exception as exc:
        fallback["selection_error"] = str(exc)
        return fallback


def run_template(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or "engel_prompt_training_template_" + stamp()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.initial_delay_seconds > 0:
        time.sleep(args.initial_delay_seconds)
    template = prepare_template(args.operator_prompt, args.cycles, args.minutes_per_cycle)
    status = {
        "schema": "engel_prompt_training_template_run_status_v1",
        "run_id": run_id,
        "status": "RUNNING",
        "started_at_utc": iso_now(),
        "template_path": str(TEMPLATE_PATH),
        "sub_template_path": str(SUB_TEMPLATE_DIR / TEMPLATE_PATH.name),
        "cycles_requested": args.cycles,
        "minutes_per_cycle": args.minutes_per_cycle,
        "google_drive_policy": "communication_only",
        "cycle_results": [],
        "blockers": [],
    }
    _write_status(status)
    _training_memory_event("template_run_started", run_id, {"template_path": str(TEMPLATE_PATH)})
    start_comm = _publish_sub_engel_comm(run_id, "started") if args.sub_engel_comm else {"ok": None, "skipped": True}
    status["sub_engel_start_communication"] = start_comm
    _write_status(status)

    for cycle in range(1, args.cycles + 1):
        prepare_template(args.operator_prompt, args.cycles, args.minutes_per_cycle)
        log_path = run_dir / f"cycle_{cycle:02d}.log"
        command = [
            sys.executable,
            str(FLUTTER_TRAINER),
            "--mode",
            "one-hour",
            "--minutes",
            str(args.minutes_per_cycle),
            "--per-prompt-timeout",
            str(args.per_prompt_timeout),
            "--template",
            str(TEMPLATE_PATH),
            "--template-cycle",
            str(cycle),
        ]
        started = time.perf_counter()
        with log_path.open("w", encoding="utf-8") as log:
            log.write(json.dumps({"event": "cycle_start", "run_id": run_id, "cycle": cycle, "command": command}) + "\n")
            completed = subprocess.run(command, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        cycle_result = {
            "cycle": cycle,
            "return_code": completed.returncode,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "log_path": str(log_path),
            "template_path": str(TEMPLATE_PATH),
            "latest_session_path": str(MEMORY_DIR / "ENGEL_UI_PROMPT_TRAINING_SESSION.json"),
        }
        status["cycle_results"].append(cycle_result)
        if completed.returncode != 0:
            status["blockers"].append(f"cycle {cycle} returned {completed.returncode}; see {log_path}")
        latest_session = _load_json(MEMORY_DIR / "ENGEL_UI_PROMPT_TRAINING_SESSION.json")
        _training_memory_event(
            "template_cycle_completed",
            run_id,
            {"cycle_result": cycle_result, "latest_session": latest_session if isinstance(latest_session, dict) else {}},
        )
        _write_status(status)

    finish_comm = _publish_sub_engel_comm(run_id, "finished") if args.sub_engel_comm else {"ok": None, "skipped": True}
    status["sub_engel_finish_communication"] = finish_comm
    status["finished_at_utc"] = iso_now()
    status["status"] = "PASS" if not status["blockers"] else "FAIL"
    status["main_training_memory"] = str(MAIN_MEMORY_JSONL)
    status["sub_engel_training_memory"] = str(SUB_MEMORY_JSONL)
    status["report_path"] = str(run_dir / "summary.json")
    _write_status(status)
    _write_json(run_dir / "summary.json", status)
    _training_memory_event("template_run_finished", run_id, status)
    return status


def start_background(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or "engel_prompt_training_template_" + stamp()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    template = prepare_template(args.operator_prompt, args.cycles, args.minutes_per_cycle)
    log_path = run_dir / "background.log"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run",
        "--run-id",
        run_id,
        "--cycles",
        str(args.cycles),
        "--minutes-per-cycle",
        str(args.minutes_per_cycle),
        "--per-prompt-timeout",
        str(args.per_prompt_timeout),
        "--initial-delay-seconds",
        str(args.initial_delay_seconds),
    ]
    if args.sub_engel_comm:
        command.append("--sub-engel-comm")
    if args.operator_prompt:
        command.extend(["--operator-prompt", args.operator_prompt])
    log = log_path.open("w", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(command, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, text=True, creationflags=flags)
    receipt = {
        "schema": "engel_prompt_training_template_background_start_v1",
        "ok": True,
        "status": "started",
        "run_id": run_id,
        "pid": process.pid,
        "started_at_utc": iso_now(),
        "template_path": str(TEMPLATE_PATH),
        "sub_template_path": str(SUB_TEMPLATE_DIR / TEMPLATE_PATH.name),
        "template_prompt_count": len(template.get("active_prompts") or []),
        "log_path": str(log_path),
        "latest_status_path": str(LATEST_STATUS),
        "main_training_memory": str(MAIN_MEMORY_JSONL),
        "sub_engel_training_memory": str(SUB_MEMORY_JSONL),
        "google_drive_policy": "communication_only",
        "assistant_reply": (
            f"Started Engel prompt-training template run {run_id}. "
            f"It will run {args.cycles} one-hour UI chat cycles through local LLM and Agent Meeting Room. "
            f"Training artifacts stay local: {TEMPLATE_PATH} and {SUB_MEMORY_JSONL}."
        ),
    }
    _write_json(run_dir / "start_receipt.json", receipt)
    _write_status({**receipt, "run_status": "STARTED_BACKGROUND"})
    return receipt


def trigger_via_ui(args: argparse.Namespace) -> dict[str, Any]:
    from run_engel_flutter_main_ui_prompt_training import _ensure_window, send_prompt_through_flutter

    hwnd, _pid, _path = _ensure_window()
    run_id = "engel_template_trigger_" + stamp()
    prompt = args.operator_prompt.strip() or TRIGGER_PROMPT
    return send_prompt_through_flutter(hwnd, prompt, args.trigger_timeout, 1, run_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "start", "run", "trigger-via-ui"):
        item = sub.add_parser(name)
        item.add_argument("--run-id", default="")
        item.add_argument("--operator-prompt", default="")
        item.add_argument("--cycles", type=int, default=4)
        item.add_argument("--minutes-per-cycle", type=float, default=60.0)
        item.add_argument("--per-prompt-timeout", type=int, default=760)
        item.add_argument("--initial-delay-seconds", type=float, default=0.0)
        item.add_argument("--sub-engel-comm", action="store_true")
        item.add_argument("--trigger-timeout", type=int, default=180)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "prepare":
        result = prepare_template(args.operator_prompt, args.cycles, args.minutes_per_cycle)
    elif args.command == "start":
        result = start_background(args)
    elif args.command == "run":
        result = run_template(args)
    elif args.command == "trigger-via-ui":
        result = trigger_via_ui(args)
    else:
        raise AssertionError(args.command)
    print(json.dumps(redact(result), indent=2, sort_keys=True))
    if isinstance(result, dict):
        if result.get("ok") is False or result.get("status") == "FAIL":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
