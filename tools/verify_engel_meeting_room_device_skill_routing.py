#!/usr/bin/env python3
"""Verify Meeting Room assigns device -> agent -> skill by job need."""
from __future__ import annotations

import py_compile
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def primary_station_for(prompt: str):
    import engel_agent_meeting_room as room

    state = room.RoomState(participants=[])
    rows = room._ensure_order_stations(state, prompt)
    require(rows, f"no stations selected for {prompt!r}")
    primary = state.participants[rows[0]]
    return room._infer_job_type(prompt), primary, room._station_route_detail(primary)


def verify_prompt_matrix() -> None:
    cases = [
        (
            "Make me a PDF about phone workers.",
            "format_report_draft",
            "Android Phone Beta Agent",
            "Android Worker Beta Skill",
            "Moto G Fast",
        ),
        (
            "Write Python code for a worker health helper.",
            "draft_code_artifact",
            "Android Phone Alpha Agent",
            "Android Worker Alpha Skill",
            "Moto G Power",
        ),
        (
            "Write code for eighth-wave operator-ready run with simple user phrasing: a summary merger for first-run and correction-run receipts.",
            "draft_code_artifact",
            "Android Phone Alpha Agent",
            "Android Worker Alpha Skill",
            "Moto G Power",
        ),
        (
            "Help me write clearer app wording for ninth-wave future-device run that keeps Alpha and Beta behavior clear: offline phone warnings and not-paired messages.",
            "summarize_text",
            "Android Phone Alpha Agent",
            "Android Worker Alpha Skill",
            "Moto G Power",
        ),
        (
            "Help me write clearer app wording for third-wave build-on check using the first two classifier fixes: plain words for code, PDF, file, game, language, and research jobs.",
            "summarize_text",
            "Android Phone Alpha Agent",
            "Android Worker Alpha Skill",
            "Moto G Power",
        ),
        (
            "Search online for Android WiFi reliability ideas.",
            "web_research_brief",
            "Android Phone Alpha Agent",
            "Android Worker Alpha Skill",
            "Moto G Power",
        ),
        (
            "Create file with an index of today's Engel UI test outputs.",
            "summarize_text",
            "Android Phone Alpha Agent",
            "Android Worker Alpha Skill",
            "Moto G Power",
        ),
        (
            "Extract fields into JSON for these worker results.",
            "draft_candidate_json",
            "Android Phone Beta Agent",
            "Android Worker Beta Skill",
            "Moto G Fast",
        ),
        (
            "Classify these phone worker logs by status.",
            "classify_file",
            "Android Phone Beta Agent",
            "Android Worker Beta Skill",
            "Moto G Fast",
        ),
        (
            "Create a polished browser video game with high quality graphics and a boss fight.",
            "draft_code_artifact",
            "Android Phone Alpha Agent",
            "Android Worker Alpha Skill",
            "Moto G Power",
        ),
        (
            "Give me pairing code for WiFi.",
            "return_status",
            "Android Phone Alpha Agent",
            "Android Worker Alpha Skill",
            "Moto G Power",
        ),
    ]
    for prompt, expected_job, expected_agent, expected_skill, expected_device in cases:
        job_type, primary, detail = primary_station_for(prompt)
        require(job_type == expected_job, f"{prompt!r} job_type {job_type!r} != {expected_job!r}")
        require(primary.type_label == expected_agent, f"{prompt!r} agent {primary.type_label!r} != {expected_agent!r}")
        require(primary.skill_label == expected_skill, f"{prompt!r} skill {primary.skill_label!r} != {expected_skill!r}")
        require(expected_device in primary.equipment, f"{prompt!r} device missing {expected_device!r}: {primary.equipment!r}")
        require("Android Worker Job Packet" == primary.bridge, f"{prompt!r} wrong bridge: {primary.bridge!r}")
        require(detail["device"] == primary.equipment, "route detail lost device")
        require(detail["agent"] == primary.type_label, "route detail lost agent")
        require(detail["skill"] == primary.skill_label, "route detail lost skill")


def verify_existing_generic_station_normalizes() -> None:
    import engel_agent_meeting_room as room

    state = room.RoomState(participants=[
        room.Participant(
            name="Code Agent / Android Worker Skill",
            kind="agent",
            type_label="Code Agent",
            skill_label="Android Worker Skill",
            equipment="Android App Worker - WiFi / LAN pairing",
            bridge="Android Worker Job Packet",
        )
    ])
    rows = room._ensure_order_stations(state, "Check Android worker queue status.")
    generic = next(p for p in state.participants if p.skill_label == "Android Worker Skill")
    require(rows, "generic station did not route")
    require(generic.type_label == "Android Phone Agent", "generic Android station did not normalize agent label")
    require(generic.name == "Android Phone Agent / Android Worker Skill", "generic Android station did not normalize name")
    require("Android App Worker" in generic.equipment, "generic Android station lost device target")
    require("Moto G Power" in generic.equipment or "Moto G Fast" in generic.equipment, "generic Android station did not pick a real phone")


def verify_game_agents_join_after_device_worker() -> None:
    import engel_agent_meeting_room as room

    state = room.RoomState(participants=[])
    rows = room._ensure_order_stations(
        state,
        "Create a polished Phaser browser video game with high quality graphics, touch controls, and a boss fight.",
    )
    routed = [state.participants[row] for row in rows]
    skills = [participant.skill_label for participant in routed]
    agents = [participant.type_label for participant in routed]
    require("Android Worker Alpha Skill" in skills, "game prompt should still use the best phone worker first")
    require("Game Development Skill" in skills, "game prompt must route to Game Development Skill")
    require("Game Art Skill" in skills, "game prompt must route to Game Art Skill")
    require("UI Skill" in skills, "game prompt must include UI/touch/HUD skill")
    require("Verification Skill" in skills, "game prompt must include verifier")
    require("Game Developer Agent" in agents, "game prompt must select Game Developer Agent")
    require("Game Art Director Agent" in agents, "game prompt must select Game Art Director Agent")


def verify_game_factory_refinement_route() -> None:
    import engel_agent_meeting_room as room

    state = room.RoomState(participants=[])
    rows = room._ensure_order_stations(
        state,
        "Use the Game Factory to refine the latest Engel game with longer stages, better controls, dash, smoother jumping, weapon cycling, and expanded touch controls.",
    )
    routed = [state.participants[row] for row in rows]
    skills = [participant.skill_label for participant in routed]
    agents = [participant.type_label for participant in routed]
    bridges = [participant.bridge for participant in routed]
    require("Android Worker Alpha Skill" in skills, "Game Factory prompt should still use the best phone worker first")
    require("Game Factory Refinement Skill" in skills, "Game Factory prompt must route through Game Factory Refinement Skill")
    require("Game Development Skill" in skills, "Game Factory prompt must keep Game Development Skill in the room")
    require("UI Skill" in skills, "Game Factory prompt must include UI controls polish")
    require("Verification Skill" in skills, "Game Factory prompt must include verifier")
    require("Game Factory Scout Agent" in agents, "Game Factory prompt must select Game Factory Scout Agent")
    require("Game Factory Scout (Engel Meeting Room)" in bridges, "Game Factory prompt must use the Game Factory bridge")


def verify_game_factory_dispatch_from_main_ui_completion() -> None:
    import engel_agent_meeting_room as room

    tmp_dir = ROOT / "runtime" / "game_factory_meeting_room_verifier"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    test_state = room.RoomState(participants=[])
    old_load = room._load_state
    old_save = room._save_state
    old_order_path = room._order_path
    old_wait = os.environ.get("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS")
    try:
        os.environ["ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS"] = "0"

        def fake_load():
            return test_state

        def fake_save(state):
            (tmp_dir / "room_state.json").write_text(room.json.dumps(room.asdict(state), indent=2), encoding="utf-8")

        def fake_order_path(order_id: str):
            return tmp_dir / f"{order_id}.json"

        room._load_state = fake_load
        room._save_state = fake_save
        room._order_path = fake_order_path
        submitted = room.submit_order_from_engel_main_ui(
            "Use the Game Factory to refine the latest Engel game with longer stages and better controls.",
            source="Verifier",
        )
        require(submitted.get("accepted") is True, "Game Factory main UI submit was rejected")
        completed = room.complete_order_from_engel_main_ui(
            str(submitted.get("order_id")),
            "Engel local bridge is connected and will finalize the game artifact.",
            source="Verifier",
        )
    finally:
        room._load_state = old_load
        room._save_state = old_save
        room._order_path = old_order_path
        if old_wait is None:
            os.environ.pop("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS", None)
        else:
            os.environ["ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS"] = old_wait

    require(completed.get("accepted") is True, "Game Factory main UI completion was rejected")
    station_results = completed.get("station_results") or []
    require(
        any("Game Factory Scout Agent: Returned" == str(item) for item in station_results),
        f"Game Factory station did not dispatch/return: {station_results}",
    )
    previews = completed.get("returned_previews") or []
    require(any("Game Factory" in str(item) for item in previews), "Game Factory returned preview missing")


def main() -> None:
    for module in (
        ROOT / "engel_agent_meeting_room.py",
        ROOT / "engel_device_capability_registry.py",
    ):
        py_compile.compile(str(module), doraise=True)
    verify_prompt_matrix()
    verify_existing_generic_station_normalizes()
    verify_game_agents_join_after_device_worker()
    verify_game_factory_refinement_route()
    verify_game_factory_dispatch_from_main_ui_completion()
    print("OK: Meeting Room device -> agent -> skill routing verified")


if __name__ == "__main__":
    main()
