#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_engel_ui_chat_meeting_room_llm as route
from engel_main_local_model_worker import (
    _prompt_mentions_multiple_fleet_targets,
    _requested_fleet_dispatch,
)


def main() -> int:
    all_prompt = (
        "Have all three phone workers and Sub-Engel check in on one bounded "
        "status job, then tell me only what actually returned."
    )
    gamma_prompt = (
        "Ask Gamma to classify a short drafting note as commercial, residential, "
        "sustainability, or needs clarification."
    )
    workers = {
        "android_worker_alpha": {"live": True},
        "android_worker_beta": {"live": True},
        "android_worker_gamma": {"live": True},
    }
    assert route._prompt_requests_phone_work(all_prompt)
    assert route._prompt_requests_sub_engel_work(all_prompt)
    assert route._prompt_requests_phone_work(gamma_prompt)
    assert route._requested_phone_workers(all_prompt, workers) == list(workers)
    assert route._requested_phone_workers(gamma_prompt, workers) == [
        "android_worker_gamma"
    ]
    assert _prompt_mentions_multiple_fleet_targets(all_prompt)
    phone_fleet_prompt = (
        "Have all three phone workers check in on one bounded drawing-review "
        "status job, then tell me only what actually returned."
    )
    assert (_requested_fleet_dispatch(phone_fleet_prompt) or {}).get("target") == "fleet"
    assert (_requested_fleet_dispatch(gamma_prompt) or {}).get("target") == "gamma"
    assert (
        _requested_fleet_dispatch(
            "Give Sub-Engel a small review task: list the information needed."
        )
        or {}
    ).get("target") == "sub-engel"
    # Exact shape that stopped the 2026-08-03 five-hour Training run at prompts
    # 31/32: "every device" is a subject, "unassigned" is not an assign verb,
    # and the answer contract's "route" is not operator fleet intent.
    training_review = (
        "For fingerprinting every device on the home LAN so nothing stays an "
        "unassigned device, separate what a named Engel verifier confirms from "
        "what nothing yet confirms. Confirmed: <component, file, or route>."
    )
    assert _requested_fleet_dispatch(training_review) is None

    original_phone = route._attach_phone_work_dispatch
    original_sub = route._attach_sub_engel_work_dispatch
    try:
        route._attach_phone_work_dispatch = lambda prompt, receipt, started: {
            **receipt,
            "phone_work_assigned": True,
        }
        route._attach_sub_engel_work_dispatch = lambda prompt, receipt, started: {
            **receipt,
            "sub_engel_work_assigned": True,
            "sub_engel_work_dispatch": {"work_order": {"id": "ROOM-TEST"}},
        }
        receipt = route._attach_device_work_dispatch(all_prompt, {}, 0.0)
    finally:
        route._attach_phone_work_dispatch = original_phone
        route._attach_sub_engel_work_dispatch = original_sub

    assert receipt["agent_meeting_room_used"] is True
    assert receipt["meeting_room_server_used"] is True
    assert receipt["meeting_room_order_id"] == "ROOM-TEST"
    print("VERIFY_ENGEL_UI_DEVICE_ROUTING_INTENT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
