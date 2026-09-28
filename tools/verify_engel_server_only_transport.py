#!/usr/bin/env python3
"""Verify active Engel Sub-Engel transport is CT246-owned and Drive-free."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_FILES = (
    ROOT / "tools" / "engel_main_server_chat_http_service.py",
    ROOT / "tools" / "engel_meeting_room_lan_server.py",
    ROOT / "tools" / "engel_meeting_room_event_stream.py",
    ROOT / "tools" / "engel_device_broker.py",
    ROOT / "tools" / "engel_ct246_sub_engel_direct_work.py",
    ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py",
    ROOT / "tools" / "watch_windows_sub_engel_pairing.py",
    ROOT / "scripts" / "Start-EngelMainSubBridge.ps1",
    ROOT / "tools" / "engel_stack_controller.py",
    ROOT / "engel_sub_node_meeting_bridge.py",
    ROOT / "engel_agent_meeting_room.py",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    texts: dict[Path, str] = {}
    for path in ACTIVE_FILES:
        text = path.read_text(encoding="utf-8")
        texts[path] = text
        if path.suffix == ".py":
            ast.parse(text)

    active = "\n".join(texts.values())
    for forbidden in (
        "G:\\My Drive",
        "G:/My Drive",
        "Google Drive",
        "google_drive_policy",
        "ENGEL_SHARED_NODE_ROOM",
        "EngelSubEngelAutoReturn",
        "engel_sub_engel_auto_return_service.py",
    ):
        require(forbidden not in active, f"active Drive transport reference remains: {forbidden}")

    require(
        active.count("ENGEL_SUB_ENGEL_TRANSPORT_ROOT") >= 4,
        "server transport root is not wired through all active runtime readers",
    )
    require(
        active.count('ROOT / "run" / "sub_engel_transport"') >= 4,
        "CT246 runtime fallback is missing",
    )
    require('"--server-only"' in texts[ROOT / "scripts" / "Start-EngelMainSubBridge.ps1"],
            "Main pairing watcher is not server-only")
    require('CT_ID = "246"' in texts[ROOT / "tools" / "watch_windows_sub_engel_pairing.py"],
            "pairing is not delegated to the real Engel server CT246")
    require(
        "write_server_transport_work_order_for_node" in texts[ROOT / "engel_agent_meeting_room.py"],
        "Meeting Room is not using the CT246 server transport writer",
    )
    require(
        '"direct_work.execute"' in texts[ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py"],
        "visible chat is not dispatching the authenticated direct Sub action",
    )
    require(
        'DIRECT_ACTION = "direct_work.execute"' in texts[ROOT / "tools" / "engel_ct246_sub_engel_direct_work.py"],
        "CT246 direct dispatcher action is missing",
    )
    chat_service = texts[ROOT / "tools" / "engel_main_server_chat_http_service.py"]
    require("session_token_present" in chat_service, "Sub paired status does not require a stored session token")
    require("session_invalid" in chat_service, "Sub paired status does not reject an invalid session")
    require('"meeting_ready": live' in chat_service, "Sub meeting-ready status is not tied to live auth")

    print("PASS: active Engel transport is CT246 server-owned and contains no Google Drive path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
