#!/usr/bin/env python3
"""A CT246 work-pipe reset must not be reported as Sub-Engel disconnected."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for entry in (str(ROOT), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import run_engel_ui_chat_meeting_room_llm as ui_lane


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(
        ui_lane._sub_engel_pipe_error_is_transient(
            "CT246 Sub direct endpoint failed: Remote end closed connection without response"
        ),
        "connection-closed Sub pipe is not classified as transient",
    )
    require(
        not ui_lane._sub_engel_pipe_error_is_transient("unapproved Sub-Engel node: OTHER"),
        "hard node rejection was treated as a retryable pipe blip",
    )
    honest = ui_lane._honest_sub_engel_dispatch_error(
        "Remote end closed connection without response",
        {"url": "http://198.51.100.227:8776"},
        {
            "url": "http://198.51.100.227:8776",
            "tcp_open": True,
            "health_ok": True,
            "reachable": True,
        },
    )
    require("paired and reachable" in honest, f"reachable node still sounded disconnected: {honest}")
    require("not an unpaired node" in honest, f"honest error lost the unpaired-node denial: {honest}")
    require("not connected" not in honest.casefold(), f"honest error still says not connected: {honest}")
    down = ui_lane._honest_sub_engel_dispatch_error(
        "connection refused",
        {"url": "http://198.51.100.227:8776"},
        {
            "url": "http://198.51.100.227:8776",
            "tcp_open": False,
            "health_ok": False,
            "reachable": False,
        },
    )
    require("not accepting connections" in down, f"down node error was too vague: {down}")
    source = (TOOLS / "run_engel_ui_chat_meeting_room_llm.py").read_text(encoding="utf-8")
    require("range(1, 4)" in source, "Sub-Engel dispatch has no bounded retry")
    require("recovered_from_done_file" in source, "Sub-Engel dispatch does not recover a late done.json")
    chat = (TOOLS / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    require("_probe_sub_engel_http_health(" in chat, "live snapshot does not probe Sub-Engel /health")
    require(
        "this is not an unpaired node" in chat.casefold(),
        "live snapshot still tells the UI to re-pair after a probe miss",
    )
    print("ENGEL_SUB_ENGEL_FALSE_DISCONNECT_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
