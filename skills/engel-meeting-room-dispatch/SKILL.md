---
name: "engel-meeting-room-dispatch"
description: "Route orders through the Engel Agent Meeting Room: API-only intake, per-equipment dispatch to Local Engel AI, Android workers, or Sub-Engel. Use whenever a request mentions the meeting room, submitting or completing orders, equipment dispatch, or meeting room windows and routes."
version: "1.0.0"
source: "claude-skill-creator"
created_at_utc: "2026-08-04T14:56:01Z"
updated_at_utc: "2026-08-04T14:56:01Z"
---

# Engel Meeting Room Dispatch

## Purpose

Move orders into and out of the Meeting Room correctly. The Qt Meeting Room window has **no prompt input on purpose** — intake is API-only from the main UI, and each equipment type dispatches differently.

## Two modules, one missing underscore

- `engel_agent_meeting_room.py` — the standalone **Qt window** (launch: `python engel_agent_meeting_room.py` or `launch_engel_meeting_room.bat`).
- `engel_agent_meetingroom.py` — the **text-only** `engel.meeting_room.*` routes for the chat router. Separate module; do not conflate them.

Also note: `engel_desktop_v2.py`'s chat panel intercepts phrases like `meeting room` locally before routing, so the provider bridge never sees them.

## Trigger Conditions

- The user wants to send an order to the meeting room or read replies back.
- A request involves per-equipment dispatch, meeting room agents, or the Qt window.
- Meeting room behavior must change (read the contract first — see Save Contract).

## The API contract

- Orders arrive via `submit_order_from_engel_main_ui(order_text, source="Engel AI Main UI")` called from the main UI.
- Replies return via `complete_order_from_engel_main_ui(order_id, reply)`.
- Never add a prompt input to the Meeting Room window; intake stays API-only.

## Per-equipment dispatch

| Equipment | What actually happens |
|---|---|
| Local Engel AI | Chat record only |
| Android worker | Real job packet via `engel_adb_worker_manager.render_adb_create_job` |
| Sub-Engel | Preview-only staged file — **no remote control yet** |

Do not "upgrade" Sub-Engel dispatch to live remote control; that is a deliberate boundary.

## Operating Instructions

- Use the D: interpreter for all launches: `D:\b.WorkSpace\Engel App\runtime\python310\python.exe`.
- For Android-equipment orders, the fleet rules apply (see the `engel-android-worker-fleet` skill): independent queues per phone, D: adb only.
- Text-route side: drive `engel.meeting_room.*` routes via `python engel_ai.py ask "<phrase>"`.

## Save Contract

- Before changing the dispatcher, read `memory/ENGEL_AGENT_MEETING_ROOM_CONTRACT_V1.md` and `memory/project_engel_meeting_room.md`.
- Order IDs are the receipt — include them when reporting dispatches.
- No autonomous loops: orders are submitted and completed on explicit calls only.
