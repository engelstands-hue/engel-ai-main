---
name: "3d-cluster-agent-meeting-room"
description: "Launch, operate, and collaborate in the live 3D Agent Meeting Room workspace across the Engel cluster: engel-ai-main server (CT 246), Sub-Engel desktop, ROG laptop controller, and USB-connected Android worker phones. Provides collaborative chat, agent dispatch, and 3D virtual office view."
version: "1.0.0"
source: "engel-ai-main"
created_at_utc: "2026-07-01T06:30:00Z"
updated_at_utc: "2026-07-01T06:30:00Z"
---

# 3D Cluster Agent Meeting Room Operator

## Purpose

Enable all devices in the Engel cluster to collaborate in a live 3D agent workspace with shared chat, orders, and dispatch. Engel-ai-main (server) acts as central controller. Laptop provides the primary UI and USB android workers. Sub-Engel nodes participate via shared rooms and LAN.

## Trigger Conditions

- User asks to open / launch / use the 3D meeting room, cluster meeting room, or agent workspace for server + devices.
- Phrases like "open meeting room", "3d agent room", "cluster collab room", "start agent meeting office".
- When dispatching work that should use the multi-device collaborative surfaces.

## Key Components (Existing)

- Qt Meeting Room: `python engel_agent_meeting_room.py` or `launch_engel_meeting_room.bat`
  - Device -> Agent -> Skill -> Bridge station selector.
  - Agent Cards, Order Flow, collaboration dialogue.
  - Dispatch to: Local, Android App Worker (real), Sub-Engel (shared/preview), Windows Sub-Engel.
- LAN Server: tools/engel_meeting_room_lan_server.py (default port 8790) for cross-device events.
- 3D Virtual Office + Tunnels: `powershell -ExecutionPolicy Bypass -File scripts\Start-EngelAgentMeetingRoomOffice.ps1`
  - Brings up engel3d_office_main (port 3000) + validates CT chat (24680) and meeting room (8790) tunnels.
- Desktop V2: `python engel_desktop_v2.py` — ⌬ Meeting Room button or chat phrases ("meeting room", "open meeting room", "where is the meeting room").
- Android: USB ADB on laptop or LAN pairing. Use existing `engel.android_workers.*` routes or Meeting Room send.
- Sub-Engel: Shared room work orders under runtime/ + node check-ins.
- Server access: Persistent tunnels from laptop to engel-ai-main CT (key-based SSH after one-time setup via Install-EngelMainPersistent... scripts).

## Launch from Laptop (Controller)

1. Basic room: `launch_engel_meeting_room.bat` or `python engel_agent_meeting_room.py`
2. Full 3D server view:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\Start-EngelAgentMeetingRoomOffice.ps1
   ```
3. Verify tunnels: http://127.0.0.1:24680/health , http://127.0.0.1:8790/health , http://127.0.0.1:3000/api/health
4. From main chat in Desktop V2: type "meeting room" (intercepted locally).

## Collaboration Flow

- Orders originate in Engel AI Main UI (laptop or tunneled).
- Meeting Room auto-selects agents/skills by equipment.
- Dispatch records collaboration dialogue.
- Android workers receive real packets; results return.
- Sub-Engel stages to shared runtime locations for processing.
- 3D office provides visual agent team workspace layer.
- All via approved paths; no new provider calls or autonomy from the room.

## Safety & Authority

- Human-directed (Josh > Guardian > Engel/runtime).
- No job input inside Meeting Room window itself — intake via main UI.
- Training, model growth, background loops, source edits, provider actions = Bucket 3 (needs explicit Josh call + matching bounded exception, e.g. RunPod with budget).
- Record lessons via /reps/* (universal, all lanes).
- Always use D: paths only.

## Related Reports & Files

- `reports/codex_bridge/ENGEL_3D_AGENT_MEETING_ROOM_CLUSTER_SERVER_20260630.md`
- `memory/ENGEL_AGENT_MEETING_ROOM_CONTRACT_V1.md`
- `ENGEL_CLUSTER_TOPOLOGY.md`
- `runtime/meeting_room/`, `runtime/meeting_room_server/`
- `scripts/Start-EngelAgentMeetingRoomOffice.ps1`, `Start-EngelMainOneSystem.ps1`
- `tools/verify_engel_agent_meeting_room.py` (must pass)

## Usage Example

User: "open the 3d cluster meeting room for the server and phones"

Action: Run the office ps1 from laptop, stage orders from main chat into the room, monitor agent cards and 3D view, dispatch to appropriate equipment targets.

## Sign-off Note

This skill is documentation + launcher guidance (Bucket 1/2). Any runtime mutation or training remains Bucket 3. Use REPS to record usage lessons.
