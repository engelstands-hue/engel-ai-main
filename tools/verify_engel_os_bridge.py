#!/usr/bin/env python3
"""Verify Engel OS is hooked into Engel AI through the safe bridge."""
from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIDGE_MODULE = ROOT / "engel_os_bridge.py"
MEETING_ROOM = ROOT / "engel_agent_meeting_room.py"
PROMPT_SELECTOR = ROOT / "engel_prompt_bridge_selection.py"
MEMORY_SPEC = ROOT / "memory" / "ENGEL_OS_BRIDGE_V1.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def assert_no_secret_or_c_temp(value: object) -> None:
    text = json.dumps(value, indent=2) if not isinstance(value, str) else value
    forbidden = (
        "C:\\Users\\ziese\\AppData\\Local\\Temp",
        "AppData\\Local\\Temp",
        '"PAIRING_CODE":',
        '"pairing_code":',
        '"session_token":',
        "Authorization: Bearer",
        "Wi-Fi password",
        "wifi_password",
    )
    require(not any(item in text for item in forbidden), "forbidden secret/temp text leaked")


def verify_bridge_module() -> None:
    import engel_os_bridge as bridge

    review = bridge.review_engel_os_project()
    require(review.get("ok") is True, "Engel OS review is not healthy")
    require(review.get("bridge") == "Engel OS Bridge (read-only)", "wrong bridge label")
    docs = review.get("documents") or {}
    for name in (
        "handoff",
        "readme",
        "ready_to_flash",
        "technical_plan",
        "usb_flashing_guide",
        "sub_node_handoff",
        "packet_016_remote_control",
    ):
        require((docs.get(name) or {}).get("exists") is True, f"missing doc: {name}")
        require((docs.get(name) or {}).get("markers_found"), f"doc markers missing: {name}")
    iso = review.get("iso") or {}
    require((iso.get("iso") or {}).get("exists") is True, "current ISO missing")
    require(iso.get("sha256_verified") is True, "current ISO SHA256 did not verify")
    summary = iso.get("build_summary") or {}
    require(summary.get("usb_flashed") is False, "bridge should not mark USB flashed")
    require(summary.get("host_disk_mutation") is False, "bridge should not mutate host disk")
    safety = review.get("safety_gates") or {}
    for key in (
        "read_only_bridge",
        "remote_control_allowlist_only",
        "no_ssh",
        "no_raw_shell",
        "no_remote_install_format_partition",
        "no_provider_runtime_started",
        "no_model_runtime_started",
        "no_background_workers_started",
        "no_secrets_or_pairing_codes_recorded",
    ):
        require(safety.get(key) is True, f"safety gate missing/false: {key}")

    result = bridge.stage_engel_os_hookup_packet(
        "Check D:\\Engel OS and make sure it is hooked to Engel AI correctly.",
        source="Verifier",
    )
    report = Path(str(result.get("report_path") or ""))
    status = Path(str(result.get("status_path") or ""))
    require(report.is_file(), f"missing report: {report}")
    require(status.is_file(), f"missing status: {status}")
    report_text = read(report)
    for needle in (
        "Engel OS Bridge Hookup Report",
        "SHA256 verified: True",
        "Allowed remote actions",
        "Blocked by design",
        "No remote action was run by this bridge.",
    ):
        require(needle in report_text, f"report missing {needle!r}")
    assert_no_secret_or_c_temp(result)
    assert_no_secret_or_c_temp(report_text)


def verify_memory_spec() -> None:
    require(MEMORY_SPEC.is_file(), f"missing memory spec: {MEMORY_SPEC}")
    text = read(MEMORY_SPEC)
    for needle in (
        "Engel OS Bridge V1",
        "Engel OS Bridge Agent",
        "Engel OS Bridge Skill",
        "No SSH",
        "No raw shell",
        "No remote USB flash",
        "No secrets",
    ):
        require(needle in text, f"memory spec missing {needle!r}")
    assert_no_secret_or_c_temp(text)


def verify_prompt_selector() -> None:
    import engel_prompt_bridge_selection as selector

    decision = selector.build_prompt_route_decision(
        "Make sure D:\\Engel OS is hooked up to Engel AI correctly and report the current ISO safety status."
    )
    require(decision.task_type == "engel-os", f"wrong task type: {decision.task_type}")
    require(decision.bridge_key == "engel_os", f"wrong bridge key: {decision.bridge_key}")
    require(decision.primary_agent == "Engel OS Bridge Agent", f"wrong primary: {decision.primary_agent}")
    require("Safety Agent" in decision.support_agents, "Safety Agent support missing")
    require("Verifier Agent" in decision.support_agents, "Verifier Agent support missing")
    require("Engel OS Bridge" in decision.meeting_bridge, "meeting bridge missing")
    require(any("SSH" in limit or "raw shell" in limit for limit in decision.safety_limits), "safety limits missing")


def verify_meeting_room_route_and_dispatch() -> None:
    import engel_agent_meeting_room as room

    state = room.RoomState(participants=[])
    prompt = "Make sure this is hooked up to Engel AI correctly: D:\\Engel OS"
    rows = room._ensure_order_stations(state, prompt)
    require(rows, "no stations selected")
    routed = [state.participants[row] for row in rows]
    skills = [participant.skill_label for participant in routed]
    bridges = [participant.bridge for participant in routed]
    require(skills[0] == "Engel OS Bridge Skill", f"wrong primary skill order: {skills}")
    require("Sub-Engel Worker Skill" in skills, "Sub-Engel support missing")
    require("Safety Review Skill" in skills, "Safety Review support missing")
    require("Verification Skill" in skills, "Verification support missing")
    require(any("Engel OS Bridge" in bridge for bridge in bridges), "Engel OS bridge missing")

    tmp_dir = ROOT / "runtime" / "engel_os_bridge_verifier"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    test_state = room.RoomState(participants=[])
    old_load = room._load_state
    old_save = room._save_state
    old_order_path = room._order_path
    try:
        def fake_load():
            return test_state

        def fake_save(state):
            (tmp_dir / "room_state.json").write_text(
                json.dumps(room.asdict(state), indent=2),
                encoding="utf-8",
            )

        def fake_order_path(order_id: str):
            return tmp_dir / f"{order_id}.json"

        room._load_state = fake_load
        room._save_state = fake_save
        room._order_path = fake_order_path
        submitted = room.submit_order_from_engel_main_ui(prompt, source="Verifier")
        require(submitted.get("accepted") is True, "Meeting Room submit rejected Engel OS prompt")
        completed = room.complete_order_from_engel_main_ui(
            str(submitted.get("order_id")),
            "Engel local bridge is connected and Engel OS should report through the read-only bridge.",
            source="Verifier",
        )
    finally:
        room._load_state = old_load
        room._save_state = old_save
        room._order_path = old_order_path

    require(completed.get("accepted") is True, "Meeting Room completion rejected Engel OS prompt")
    station_results = completed.get("station_results") or []
    require(
        any("Engel OS Bridge Agent: Returned" == str(item) for item in station_results),
        f"Engel OS station did not return: {station_results}",
    )
    assert_no_secret_or_c_temp(completed)


def main() -> None:
    for module in (BRIDGE_MODULE, MEETING_ROOM, PROMPT_SELECTOR):
        py_compile.compile(str(module), doraise=True)
    verify_bridge_module()
    verify_memory_spec()
    verify_prompt_selector()
    verify_meeting_room_route_and_dispatch()
    print("OK: Engel OS bridge verified")


if __name__ == "__main__":
    main()
