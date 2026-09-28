"""End-to-end Meeting Room test.

Five different stations, each:
  - different agent type
  - different skill
  - different device
  - different bridge

One order arrives from the Main UI, auto-routes by skill, each station
dispatches through its bridge, results return to Engel AI.
"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

from dataclasses import asdict
from engel_agent_meeting_room import (
    Participant, RoomState, _save_state,
    submit_order_from_engel_main_ui,
    complete_order_from_engel_main_ui,
)

# 1. RESET to 5 distinct stations
fresh = RoomState(
    room_name="E2E Test Room",
    created_at="2026-05-25T20:00:00",
    goal="End-to-end split-and-rejoin demo across 5 stations.",
    project="VantaMoth",
    open_task="Plan + build + test + document a new Meeting Room bridge",
    safety_state="LOCAL ONLY — no remote control",
    last_export="",
    participants=[
        Participant(
            name="Architect Agent / Architect Workflow Skill",
            kind="agent", type_label="Architect Agent",
            skill_label="Architect Workflow Skill",
            equipment="Local Engel AI (main PC)",
            status="Assigned",
            bridge="Engel Architect Agent (engel_architect_agent)",
        ),
        Participant(
            name="Code Agent / Coding Skill",
            kind="agent", type_label="Code Agent",
            skill_label="Coding Skill",
            equipment="Android App Worker — USB / hardwire ADB",
            status="Waiting",
            bridge="Android Worker Job Packet",
        ),
        Participant(
            name="Research Agent / Research Skill",
            kind="agent", type_label="Research Agent",
            skill_label="Research Skill",
            equipment="Android App Worker — WiFi / LAN pairing",
            status="Waiting",
            bridge="ChatGPT Bridge (Engel no-API handoff)",
        ),
        Participant(
            name="Verifier Agent / Verification Skill",
            kind="agent", type_label="Verifier Agent",
            skill_label="Verification Skill",
            equipment="Sub-Engel OS Worker — WiFi / LAN diagnostics",
            status="Waiting",
            bridge="Sub-Engel Diagnostics Preview",
        ),
        Participant(
            name="UI Agent / UI Skill",
            kind="agent", type_label="UI Agent",
            skill_label="UI Skill",
            equipment="Windows Sub-Engel Node — LAN check-in",
            status="Waiting",
            bridge="Windows Sub-Engel Check-in Preview",
        ),
    ],
    messages=[],
)
_save_state(fresh)
print("=" * 70)
print("STATIONS CONFIGURED (each unique on all four axes):")
print("=" * 70)
for i, p in enumerate(fresh.participants, 1):
    print(f"  {i}. {p.type_label:<18} | {p.skill_label:<25} |")
    print(f"     device : {p.equipment}")
    print(f"     bridge : {p.bridge}")
    print()

# 2. SUBMIT one composite order from the Main UI
order_text = (
    "Plan, build, test, and document a new Meeting Room bridge that "
    "connects an Android phone over WiFi/LAN to a Sub-Engel Linux node, "
    "verify the wiring, and update the UI panel that lists active bridges."
)
print("=" * 70)
print("INCOMING MAIN-UI ORDER:")
print("=" * 70)
print(f"  {order_text}\n")

res = submit_order_from_engel_main_ui(order_text, source="E2E_TEST")
print(f"  accepted     : {res.get('accepted')}")
print(f"  order_id     : {res.get('order_id')}")
print(f"  inferred job : {res.get('job_type')}")
print(f"  station auto-selection:")
for label in res.get('station_labels', []):
    print(f"     → {label}")

# 3. MAIN UI REPLY — fans out to each selected station via dispatch_station_work
print()
print("=" * 70)
print("MAIN UI REPLY → FANS OUT TO STATIONS")
print("=" * 70)
main_reply = (
    "Engel AI Main UI answer: proceed in this order — "
    "(1) Architect drafts the 13-section plan, "
    "(2) Code Agent (Android USB) implements the dart side, "
    "(3) Research Agent (Android WiFi) drafts the GTM/positioning note, "
    "(4) Verifier Agent (Sub-Engel) runs the safety scan, "
    "(5) UI Agent (Windows Sub-Engel) ships the panel mock."
)
follow = complete_order_from_engel_main_ui(res['order_id'], main_reply, source="E2E_TEST")
print(f"  accepted : {follow.get('accepted')}")
print(f"  summary  : {follow.get('summary')}")

# 4. SHOW the per-station replies that went back into the room
import json as _json
from pathlib import Path
state = _json.loads(Path("runtime/meeting_room/room_state.json").read_text(encoding="utf-8"))
print()
print("=" * 70)
print("PER-STATION REPLIES RETURNED TO ENGEL AI:")
print("=" * 70)
shown = 0
for m in state["messages"][-30:]:
    if m["role"] == "agent":
        text = m["text"]
        if len(text) > 220:
            text = text[:220] + "..."
        print(f"\n[{m['time']}] {m['name']}:\n  {text}")
        shown += 1
print(f"\n{shown} agent replies surfaced back to Engel AI.")
