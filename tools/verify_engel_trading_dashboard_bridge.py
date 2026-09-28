#!/usr/bin/env python3
"""Verify Engel Dashboard docs are merged into Engel AI routing safely."""
from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIDGE_MODULE = ROOT / "engel_trading_dashboard_bridge.py"
MEETING_ROOM = ROOT / "engel_agent_meeting_room.py"
PROMPT_SELECTOR = ROOT / "engel_prompt_bridge_selection.py"
MEMORY_SPEC = ROOT / "memory" / "ENGEL_TRADING_DASHBOARD_BRIDGE_V1.md"


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
        "SNAPTRADE_CONSUMER_KEY=",
        "SNAPTRADE_CLIENT_ID=",
        "Authorization: Bearer",
        "session token:",
    )
    require(not any(item in text for item in forbidden), "forbidden secret/temp text leaked")


def verify_bridge_module() -> None:
    import engel_trading_dashboard_bridge as bridge

    review = bridge.review_dashboard_docs()
    require(review.get("ok") is True, f"dashboard doc review failed: {review.get('marker_failures')}")
    require(review.get("bridge") == "Trading Dashboard Bridge (Engel Dashboard)", "wrong bridge label")
    require(len(review.get("documents") or {}) >= 5, "not all dashboard docs were reviewed")
    safety = review.get("safety_gates") or {}
    for key in (
        "paper_only_default",
        "live_trading_requires_manual_approval",
        "risk_agent_is_hard_gate",
        "snaptrade_helper_localhost_only",
        "no_secret_ingest_by_engel_ai",
        "no_raw_broker_order_from_meeting_room",
    ):
        require(safety.get(key) is True, f"safety gate missing/false: {key}")

    result = bridge.stage_dashboard_merge_packet(
        "Review Engel dashboard docs and merge them into Engel AI safely.",
        source="Verifier",
    )
    require(result.get("ok") is True, "dashboard merge packet not ok")
    report = Path(str(result.get("report_path") or ""))
    status = Path(str(result.get("status_path") or ""))
    require(report.is_file(), f"missing report: {report}")
    require(status.is_file(), f"missing status: {status}")
    report_text = read(report)
    for needle in (
        "Agent Mapping",
        "Safety Gates",
        "paper_only_default",
        "live_trading_requires_manual_approval",
        "No key, token, password",
    ):
        require(needle in report_text, f"report missing {needle!r}")
    assert_no_secret_or_c_temp(result)
    assert_no_secret_or_c_temp(report_text)


def verify_memory_spec() -> None:
    require(MEMORY_SPEC.is_file(), f"missing memory spec: {MEMORY_SPEC}")
    text = read(MEMORY_SPEC)
    for needle in (
        "Trading Dashboard Bridge",
        "Risk Agent -> Safety Agent",
        "Live trading requires explicit manual approval",
        "does not read `.env`",
        "Meeting Room does not submit raw broker orders",
    ):
        require(needle in text, f"memory spec missing {needle!r}")
    assert_no_secret_or_c_temp(text)


def verify_prompt_selector() -> None:
    import engel_prompt_bridge_selection as selector

    decision = selector.build_prompt_route_decision(
        "Review the Engel dashboard SnapTrade setup and paper trading safety rules."
    )
    require(decision.task_type == "trading-dashboard", f"wrong task type: {decision.task_type}")
    require(decision.bridge_key == "trading_dashboard", f"wrong bridge key: {decision.bridge_key}")
    require(decision.primary_agent == "Trading Dashboard Bridge Agent", f"wrong primary: {decision.primary_agent}")
    require("Safety Agent" in decision.support_agents, "Safety Agent support missing")
    require("Portfolio Strategist Agent" in decision.support_agents, "Portfolio support missing")
    require("Quant Modeler Agent" in decision.support_agents, "Quant support missing")
    require("Trading Dashboard Bridge" in decision.meeting_bridge, "meeting bridge missing")


def verify_meeting_room_route_and_dispatch() -> None:
    import engel_agent_meeting_room as room

    state = room.RoomState(participants=[])
    rows = room._ensure_order_stations(
        state,
        "Review engel-dashboard docs, SnapTrade setup, paper trader safety, and circuit breaker rules.",
    )
    require(rows, "no stations selected")
    routed = [state.participants[row] for row in rows]
    skills = [participant.skill_label for participant in routed]
    bridges = [participant.bridge for participant in routed]
    require(skills[0] == "Trading Dashboard Bridge Skill", f"wrong primary skill order: {skills}")
    require("Safety Review Skill" in skills, "Safety Review Skill missing")
    require("Portfolio Strategy Skill" in skills, "Portfolio Strategy Skill missing")
    require("Quant Modeling Skill" in skills, "Quant Modeling Skill missing")
    require(any("Trading Dashboard Bridge" in bridge for bridge in bridges), "Trading bridge missing")

    tmp_dir = ROOT / "runtime" / "trading_dashboard_verifier"
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
        submitted = room.submit_order_from_engel_main_ui(
            "Review the Engel dashboard SnapTrade setup and paper trader safety rules.",
            source="Verifier",
        )
        require(submitted.get("accepted") is True, "Meeting Room submit rejected dashboard prompt")
        completed = room.complete_order_from_engel_main_ui(
            str(submitted.get("order_id")),
            "Engel local bridge is connected and dashboard docs are ready for a read-only merge.",
            source="Verifier",
        )
    finally:
        room._load_state = old_load
        room._save_state = old_save
        room._order_path = old_order_path

    require(completed.get("accepted") is True, "Meeting Room completion rejected dashboard prompt")
    station_results = completed.get("station_results") or []
    require(
        any("Trading Dashboard Bridge Agent: Returned" == str(item) for item in station_results),
        f"Trading Dashboard station did not return: {station_results}",
    )
    assert_no_secret_or_c_temp(completed)


def main() -> None:
    for module in (BRIDGE_MODULE, MEETING_ROOM, PROMPT_SELECTOR):
        py_compile.compile(str(module), doraise=True)
    verify_bridge_module()
    verify_memory_spec()
    verify_prompt_selector()
    verify_meeting_room_route_and_dispatch()
    print("OK: Engel Trading Dashboard bridge verified")


if __name__ == "__main__":
    main()
