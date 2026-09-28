#!/usr/bin/env python3
"""Run real Sub-Engel prompt-training work orders during a main UI training run.

This companion does not replace the Engel UI trainer. It sends paced Agent
Meeting Room work orders through the shared room, wakes a paired Windows
Sub-Engel with the allowlisted shared-room action, waits for real
SUB_ENGEL_SENT_WORK returns, and records local proof receipts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engel_sub_node_meeting_bridge import (  # noqa: E402
    stage_meeting_packet_for_node,
    write_shared_room_work_order_for_node,
)
from engel_sub_node_remote_control import run_action  # noqa: E402
from tools.prove_engel_sub_engel_auto_return import (  # noqa: E402
    decode_remote_stdout,
    refresh_active_request,
    wait_for_sub_engel_return,
)


REPORT_DIR = ROOT / "reports" / "sub_engel_prompt_training"
MEMORY_PATH = ROOT / "memory" / "project_engel_sub_engel_prompt_training_20260621.md"


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def build_prompts(count: int) -> list[str]:
    allowed_devices = (
        "Allowed selected_device values are exactly: Engel AI Main, "
        "android_worker_alpha, android_worker_beta, DESKTOP-UE5A6GG, "
        "and future nodes explicitly added by Joshua. Retired desktop nodes are "
        "not selectable for Engel AI Main because they have separate jobs now. "
        "For Windows Sub-Engel local LLM work, use DESKTOP-UE5A6GG until a "
        "new node is registered. Do not invent any other device name."
    )
    answer_contract = (
        "Start the answer directly with selected_device:. Return exactly five short lines, "
        "no markdown headings, no Summary, no Result, no Concerns, no Next step, no extra "
        "text, and do not repeat the allowed-device list. Even if the task asks for a bug "
        "report, put the bug-report details inside reason and proof_needed. The first line "
        "must be selected_device: followed by exactly one allowed device ID. Required keys, "
        "in order: selected_device, agent_role, reason, proof_needed, review_required."
    )
    seeds = [
        "Choose the best Engel device for a prompt that asks for a review-only code draft, then explain why the chosen worker is safest.",
        "Act as a Windows Sub-Engel local LLM helper and summarize what proof Main should require before marking a meeting-room task done.",
        "Given Android workers and Windows Sub-Engels are both visible, pick the correct device for a local file-analysis job and return the agent role.",
        "Explain how Engel AI Main should route a prompt when one Sub-Engel is live but installed from a Drive-backed root.",
        "Draft the operator-facing answer for a successful Sub-Engel return that must stay review-required and not auto-apply code.",
        "Classify a prompt asking for a small artifact, a status check, and a device-selection explanation into the correct Engel agent lanes.",
        "Create a concise Agent Meeting Room handoff for a Windows Sub-Engel that has CUDA llama.cpp and a packaged LoRA artifact.",
        "Identify the next safe action when a Sub-Engel local LLM returns useful text but the LoRA is packaged, not loaded by the GGUF CLI.",
        "Describe how Main should prove a Sub-Engel used local LLM inference without trusting the model output as source authority.",
        "Pick between android_worker_alpha, android_worker_beta, and a Windows Sub-Engel for a long reasoning prompt, then justify the selection.",
        "Fill the five-line contract for a bug-report case where a work order appears in the shared room but no SUB_ENGEL_SENT_WORK file returns.",
        "Explain the difference between communication-only Google Drive use and storing Engel runtime state in Drive.",
    ]
    prompts: list[str] = []
    for index in range(max(1, count)):
        seed = seeds[index % len(seeds)]
        prompts.append(
            "ENGEL SUB-ENGEL PROMPT TRAINING "
            f"{index + 1:03d}: {allowed_devices} {seed} {answer_contract} "
            "Do not mutate files or run commands."
        )
    return prompts


def selected_device_contract(output: Any) -> dict[str, Any]:
    text = str(output or "")
    allowed = [
        "Engel AI Main",
        "android_worker_alpha",
        "android_worker_beta",
        "DESKTOP-UE5A6GG",
    ]
    invented = ["Engel Worker 3.0", "DESKTOP-" + "FIB17O7"]
    selected_match = re.search(r'(?im)^\s*"?selected_device"?\s*:\s*"?([^",\n]+)"?\s*,?\s*$', text)
    selected_raw = selected_match.group(1).strip() if selected_match else ""
    selected_clean = selected_raw.strip("`'\" ")
    matched = [item for item in allowed if selected_clean == item]
    bad = [item for item in invented if item.lower() in text.lower()]
    required_keys = ["selected_device", "agent_role", "reason", "proof_needed", "review_required"]
    key_presence = {
        key: bool(re.search(rf'(?im)^\s*"?{re.escape(key)}"?\s*:', text))
        for key in required_keys
    }
    forbidden_wrapper = bool(re.search(r"(?im)^\s*(summary|result|concerns|next step)\s*:", text))
    return {
        "selected_device_raw": selected_raw,
        "selected_device": selected_clean,
        "has_known_selected_device": len(matched) == 1,
        "matched_known_devices": matched,
        "invented_device_labels": bad,
        "required_key_presence": key_presence,
        "forbidden_wrapper_present": forbidden_wrapper,
        "contract_ok": len(matched) == 1 and all(key_presence.values()) and not forbidden_wrapper and not bad,
    }


def run_one_job(node_id: str, prompt: str, job_index: int, wait_seconds: float) -> dict[str, Any]:
    station = {
        "name": "Windows Sub-Engel Prompt Training",
        "type_label": "Sub-Engel Training Agent",
        "skill_label": "Local LLM Prompt Routing",
        "equipment": f"Windows Sub-Engel Node {node_id}",
        "bridge": "Windows Sub-Engel Check-in Preview",
    }
    packet = stage_meeting_packet_for_node(station, "sub_engel_prompt_training", prompt)
    work_order = write_shared_room_work_order_for_node(
        station,
        "sub_engel_prompt_training",
        prompt,
        meeting_packet_path=str(packet.get("path") or ""),
    )
    order_id = str(work_order.get("id") or "")
    sent_folder = str(work_order.get("expected_return_folder") or "")
    attempt_log: list[dict[str, Any]] = []
    returned = None

    for action in ("shared_room.process_pending_work_orders", "shared_room.process_latest_work_order"):
        refreshed = refresh_active_request(work_order)
        remote = run_action(action, node_kind="windows", node_id=node_id)
        payload = decode_remote_stdout(remote)
        returned = wait_for_sub_engel_return(order_id, sent_folder, wait_seconds, node_id)
        attempt_log.append(
            {
                "action": action,
                "active_marker_refreshed": refreshed,
                "remote_ok": bool(remote.get("ok")),
                "remote_error": remote.get("error", ""),
                "remote_return_code": remote.get("result", {}).get("return_code")
                if isinstance(remote.get("result"), dict)
                else None,
                "remote_payload_overall_ok": payload.get("overall_ok"),
                "remote_payload_exported_file": payload.get("exported_file", ""),
                "returned_file": str(returned[0]) if returned else "",
            }
        )
        if returned:
            break

    returned_payload = returned[1] if returned else {}
    executor = returned_payload.get("executor") if isinstance(returned_payload.get("executor"), dict) else {}
    runtime = executor.get("runtime") if isinstance(executor.get("runtime"), dict) else {}
    local_status = returned_payload.get("local_llm_status") if isinstance(returned_payload.get("local_llm_status"), dict) else {}
    trained_lora = returned_payload.get("trained_lora_adapter") if isinstance(returned_payload.get("trained_lora_adapter"), dict) else {}
    worker_output = returned_payload.get("worker_output", "")
    device_contract = selected_device_contract(worker_output)
    returned_ok = returned is not None
    record = {
        "schema": "engel_sub_engel_prompt_training_job_v1",
        "created_at_utc": utc_stamp(),
        "ok": returned_ok and bool(device_contract.get("contract_ok")),
        "returned_ok": returned_ok,
        "job_index": job_index,
        "node_id": node_id,
        "prompt": prompt,
        "meeting_packet": packet,
        "work_order": work_order,
        "attempts": attempt_log,
        "returned_file": str(returned[0]) if returned else "",
        "returned_payload": returned_payload,
        "proof": {
            "auto_apply": False,
            "google_drive_use": "communication_only",
            "local_llm_attempted": bool(returned_payload.get("local_llm_attempted")),
            "worker_engine": returned_payload.get("worker_engine", ""),
            "runtime_backend": local_status.get("runtime_backend", ""),
            "runtime_cli": local_status.get("runtime_cli", ""),
            "llama_return_code": runtime.get("return_code"),
            "trained_lora_present": trained_lora.get("present"),
            "model_output_trusted": returned_payload.get("model_output_trusted"),
            "requires_review_before_apply": returned_payload.get("requires_review_before_apply"),
            "selected_device_contract": device_contract,
        },
    }
    return record


def append_memory(final_report: Path, records: list[dict[str, Any]]) -> None:
    ok_count = sum(1 for item in records if item.get("ok"))
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "",
        "## Sub-Engel Prompt Training Companion",
        "",
        f"Saved: {utc_stamp()}",
        f"- Final report: `{final_report.relative_to(ROOT).as_posix()}`",
        f"- Jobs returned: {ok_count}/{len(records)}",
        "- Work orders used the Google Drive shared room only for communication.",
        "- Returned Sub-Engel model output remains review-required and is not source authority.",
    ]
    with MEMORY_PATH.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default="DESKTOP-UE5A6GG")
    parser.add_argument("--minutes", type=float, default=240.0)
    parser.add_argument("--target-jobs", type=int, default=48)
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    parser.add_argument("--wait-seconds", type=float, default=90.0)
    args = parser.parse_args(argv)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run_stamp = local_stamp()
    events_path = REPORT_DIR / f"ENGEL_SUB_ENGEL_PROMPT_TRAINING_{run_stamp}.jsonl"
    final_path = REPORT_DIR / f"ENGEL_SUB_ENGEL_PROMPT_TRAINING_{run_stamp}.json"
    latest_path = REPORT_DIR / "ENGEL_SUB_ENGEL_PROMPT_TRAINING_LATEST.json"
    prompts = build_prompts(args.target_jobs)
    deadline = time.time() + max(0.0, args.minutes * 60.0)
    records: list[dict[str, Any]] = []

    start_event = {
        "event": "sub_engel_prompt_training_started",
        "run_stamp": run_stamp,
        "node": args.node,
        "minutes": args.minutes,
        "target_jobs": args.target_jobs,
        "interval_seconds": args.interval_seconds,
        "time_utc": utc_stamp(),
    }
    print(json.dumps(start_event, sort_keys=True), flush=True)
    append_jsonl(events_path, start_event)

    for index, prompt in enumerate(prompts, start=1):
        if time.time() >= deadline:
            break
        started = time.time()
        record = run_one_job(args.node, prompt, index, args.wait_seconds)
        record["duration_seconds"] = round(time.time() - started, 3)
        records.append(record)
        event = {
            "event": "sub_engel_prompt_training_job_complete",
            "job_index": index,
            "ok": bool(record.get("ok")),
            "node": args.node,
            "returned_file": record.get("returned_file", ""),
            "duration_seconds": record["duration_seconds"],
            "proof": record.get("proof", {}),
            "time_utc": utc_stamp(),
        }
        print(json.dumps(event, sort_keys=True), flush=True)
        append_jsonl(events_path, event)
        write_json(latest_path, {
            "schema": "engel_sub_engel_prompt_training_run_v1",
            "run_stamp": run_stamp,
            "status": "running",
            "events": str(events_path),
            "records": records,
        })
        if index < len(prompts) and time.time() < deadline:
            time.sleep(max(0.0, min(args.interval_seconds, deadline - time.time())))

    ok_count = sum(1 for item in records if item.get("ok"))
    final = {
        "schema": "engel_sub_engel_prompt_training_run_v1",
        "run_stamp": run_stamp,
        "created_at_utc": utc_stamp(),
        "status": "complete",
        "node": args.node,
        "requested_minutes": args.minutes,
        "requested_jobs": args.target_jobs,
        "completed_jobs": len(records),
        "ok_jobs": ok_count,
        "all_jobs_ok": ok_count == len(records) and bool(records),
        "events": str(events_path),
        "records": records,
        "google_drive_use": "communication_only",
        "auto_apply": False,
        "requires_review_before_apply": True,
    }
    write_json(final_path, final)
    write_json(latest_path, final)
    append_memory(final_path, records)
    print(json.dumps({"event": "sub_engel_prompt_training_finished", "final_report": str(final_path), **final}, sort_keys=True), flush=True)
    return 0 if final["all_jobs_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
