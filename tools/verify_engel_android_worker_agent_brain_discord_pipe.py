#!/usr/bin/env python3
"""Verify Android worker Agent+Brain map and Discord↔phone pipe (no Discord on phone)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MAP_PATH = ROOT / "memory" / "ENGEL_ANDROID_WORKER_AGENT_BRAIN_MAP_V1.json"
MAIN_DART = ROOT / "mobile" / "engel_remote_worker" / "lib" / "main.dart"
PHONE_MAP = ROOT / "memory" / "ENGEL_PHONE_DEVICE_MAP_V1.json"

REQUIRED_WORKERS = {
    "android_worker_alpha": "ANDROID_WORKER_ALPHA",
    "android_worker_beta": "ANDROID_WORKER_BETA",
    "android_worker_gamma": "ANDROID_WORKER_GAMMA",
}


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    errors: list[str] = []
    if not MAP_PATH.is_file():
        return fail(f"missing map {MAP_PATH}")
    payload = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    workers = payload.get("workers")
    if not isinstance(workers, dict):
        return fail("workers object missing")
    for worker_id, serial in REQUIRED_WORKERS.items():
        record = workers.get(worker_id)
        if not isinstance(record, dict):
            errors.append(f"missing worker {worker_id}")
            continue
        for field in (
            "agent_id",
            "agent_name",
            "brain_id",
            "brain_label",
            "brain_lane",
            "adb_serial",
        ):
            if not str(record.get(field) or "").strip():
                errors.append(f"{worker_id} missing {field}")
        if record.get("adb_serial") != serial:
            errors.append(f"{worker_id} serial expected {serial}")
        identity_path = ROOT / "remote_workers" / worker_id / "config" / "worker_identity.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        if identity.get("agent_name") != record.get("agent_name"):
            errors.append(f"{worker_id} identity agent_name mismatch")
        if identity.get("brain_id") != record.get("brain_id"):
            errors.append(f"{worker_id} identity brain_id mismatch")
        if identity.get("discord_on_phone") is not False:
            errors.append(f"{worker_id} must set discord_on_phone false")
        if identity.get("controls_engel") is not False:
            errors.append(f"{worker_id} must set controls_engel false")
        if identity.get("model_runtime") is not False:
            errors.append(f"{worker_id} must keep model_runtime false")

    safety = payload.get("safety") or {}
    if safety.get("discord_on_phone") is not False:
        errors.append("map safety.discord_on_phone must be false")
    if safety.get("on_device_model_runtime") is not False:
        errors.append("map safety.on_device_model_runtime must be false")

    from engel_android_worker_agent_brain import binding_for_serial, pair_status_fields
    from engel_adb_worker_manager import _DEVICE_WORKERS
    from engel_discord_android_worker_pipe import (
        PIPE_SCHEMA,
        SELF_TASK_MAX_STEPS,
        enqueue_from_desk,
        format_discord_reply,
        pipe_colony_snapshot,
        propose_next_phone_task,
    )

    for worker_id, serial in REQUIRED_WORKERS.items():
        if _DEVICE_WORKERS.get(serial) != [worker_id]:
            errors.append(f"ADB map missing {serial} -> {worker_id}")
        fields = pair_status_fields(worker_id)
        if fields.get("agent_assigned") is not True:
            errors.append(f"pair status not assigned for {worker_id}")
        if fields.get("discord_on_phone") is not False:
            errors.append(f"pair status discord_on_phone for {worker_id}")

    if binding_for_serial("ANDROID_WORKER_GAMMA").get("worker_id") != "android_worker_gamma":
        errors.append("gamma serial binding failed")

    dart = MAIN_DART.read_text(encoding="utf-8")
    theme = (ROOT / "mobile" / "engel_remote_worker" / "lib" / "new_tech_theme.dart").read_text(
        encoding="utf-8"
    )
    for needle in (
        "Agent ready",
        "Discord pipe",
        "brain_alpha_research_companion",
        "discord_on_phone",
        "Android Phone Alpha Agent",
        "new_tech_theme",
    ):
        if needle not in dart:
            errors.append(f"main.dart missing {needle}")
    for needle in (
        "worker_texture_alpha.png",
        "worker_texture_beta.png",
        "worker_texture_gamma.png",
    ):
        if needle not in theme and needle not in dart:
            errors.append(f"texture asset reference missing: {needle}")
        asset_path = ROOT / "mobile" / "engel_remote_worker" / "assets" / needle
        if not asset_path.is_file():
            errors.append(f"missing asset file: {needle}")
    if "STANDBY (no agent assigned yet)" in dart or "(no agent assigned yet)" in dart:
        errors.append("main.dart still shows blank standby agent copy")

    phone_map = json.loads(PHONE_MAP.read_text(encoding="utf-8"))
    serials = {p.get("adb_serial"): p.get("assigned_worker_id") for p in phone_map.get("phones", [])}
    for worker_id, serial in REQUIRED_WORKERS.items():
        if serials.get(serial) != worker_id:
            errors.append(f"phone map serial {serial} not mapped to {worker_id}")

    nxt = propose_next_phone_task(
        origin_text="search online then write code for a tiny maze",
        last_task_type="web_research_brief",
        result_summary="Candidate brief: maze generators use recursive backtracking.",
        loop_step=1,
        desk_id="product",
    )
    if not nxt or nxt.get("task_type") != "draft_code_artifact":
        errors.append("search-then-create must queue draft_code_artifact as next task")
    if propose_next_phone_task(
        origin_text="search online then write code for a tiny maze",
        last_task_type="web_research_brief",
        result_summary="ok",
        loop_step=SELF_TASK_MAX_STEPS,
        desk_id="product",
    ):
        errors.append("self-task loop must stop at SELF_TASK_MAX_STEPS")
    if propose_next_phone_task(
        origin_text="search online for RAM",
        last_task_type="web_research_brief",
        result_summary="Work is finished. No next task.",
        loop_step=1,
        desk_id="research",
    ):
        errors.append("done markers must end the self-task loop")

    from engel_device_capability_registry import infer_job_type_from_text

    if infer_job_type_from_text("search online for Engel RAM options") != "web_research_brief":
        errors.append("search online must map to web_research_brief")
    if infer_job_type_from_text("write code for a tiny maze") != "draft_code_artifact":
        errors.append("write code must map to draft_code_artifact")

    search_enq = enqueue_from_desk(
        desk_id="research",
        text="search online for Engel RAM options",
        title="Discord phone search",
        worker_id="android_worker_alpha",
        task_type="web_research_brief",
        channel_id="proof_search_channel",
        message_id="proof_search_message",
    )
    if not search_enq.get("ok"):
        errors.append(f"web_research_brief enqueue failed: {search_enq}")
    else:
        search_packet = json.loads(Path(str(search_enq["assignment_path"])).read_text(encoding="utf-8"))
        if search_packet.get("task_type") != "web_research_brief":
            errors.append("search enqueue did not keep web_research_brief")
        if (search_packet.get("origin") or {}).get("discord_on_phone") is not False:
            errors.append("search assignment must forbid discord on phone")

    enq = enqueue_from_desk(
        desk_id="research",
        text="Bounded pipe proof: summarize one short safety note for Josh review only.",
        title="Discord pipe proof summarize",
        worker_id="android_worker_alpha",
        task_type="summarize_text",
        channel_id="proof_channel",
        message_id="proof_message",
    )
    if not enq.get("ok"):
        errors.append(f"enqueue_from_desk failed: {enq}")
    else:
        assignment_path = Path(str(enq["assignment_path"]))
        packet = json.loads(assignment_path.read_text(encoding="utf-8"))
        origin = packet.get("origin") or {}
        if origin.get("source") != "discord_desk":
            errors.append("assignment missing discord_desk origin")
        if origin.get("discord_on_phone") is not False:
            errors.append("assignment must forbid discord on phone")
        if origin.get("pipe") != PIPE_SCHEMA:
            errors.append("assignment pipe schema mismatch")
        if not packet.get("agent_binding", {}).get("agent_name"):
            errors.append("assignment missing agent_binding")
        if not packet.get("brain_binding", {}).get("brain_id"):
            errors.append("assignment missing brain_binding")
        reply = format_discord_reply(
            worker_id="android_worker_alpha",
            packet=packet,
            result={"summary": "Proof draft only."},
        )
        if "Android Phone Alpha Agent" not in reply:
            errors.append("discord reply missing agent name")
        if "Review-only" not in reply:
            errors.append("discord reply missing review gate")

    snap = pipe_colony_snapshot()
    if snap.get("discord_on_phone") is not False:
        errors.append("pipe snapshot must set discord_on_phone false")
    if int(snap.get("approved_discord_assignments") or 0) < 1:
        errors.append("pipe snapshot should see at least one discord assignment")

    if errors:
        for err in errors:
            print("FAIL:", err)
        return 1
    print("PASS: android worker agent+brain + discord pipe verifier")
    print(f"proof_packet_id={enq.get('packet_id')}")
    print(f"proof_assignment={enq.get('assignment_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
