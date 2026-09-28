#!/usr/bin/env python3
"""Verify Agent Meeting Room integration for Linux and Windows Sub-Engel nodes."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEETING_ROOM = ROOT / "engel_agent_meeting_room.py"
MEETING_BRIDGE = ROOT / "engel_sub_node_meeting_bridge.py"
REMOTE_CLIENT = ROOT / "engel_sub_node_remote_control.py"
APP = ROOT / "engel_app.py"
WINDOWS_GITIGNORE = ROOT / "remote_nodes" / "windows_sub_engel" / ".gitignore"


def fail(message: str) -> None:
    raise SystemExit(f"SUB_ENGEL_MEETING_BRIDGE_VERIFY_FAIL: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read(path: Path) -> str:
    require(path.exists(), f"missing required file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def literal_collection(tree: ast.AST, name: str) -> set[str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
            fail(f"{name} is not a literal collection")
        values: set[str] = set()
        for item in node.value.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                fail(f"{name} contains a non-string literal")
            values.add(item.value)
        return values
    fail(f"{name} not found")
    return set()


def require_all(text: str, markers: tuple[str, ...], label: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        fail(f"{label} missing markers: {missing}")


def require_absent(text: str, markers: tuple[str, ...], label: str) -> None:
    present = [marker for marker in markers if marker in text]
    if present:
        fail(f"{label} contains forbidden markers: {present}")


def main() -> int:
    meeting_text = read(MEETING_ROOM)
    bridge_text = read(MEETING_BRIDGE)
    client_text = read(REMOTE_CLIENT)
    app_text = read(APP)
    ignore_text = read(WINDOWS_GITIGNORE)

    ast.parse(meeting_text)
    bridge_tree = ast.parse(bridge_text)
    ast.parse(client_text)

    require_all(meeting_text, (
        "Windows Sub-Engel Node - LAN check-in",
        "Windows Sub-Engel Node - service / outbound",
        "Windows Sub-Engel Check-in Preview",
        "engel_sub_node_meeting_bridge",
        "_probe_sub_engel_status",
        "_probe_windows_sub_engel_status",
        "stage_meeting_packet_for_node",
        "approved worker packet",
    ), "meeting room")

    require_all(bridge_text, (
        "meeting_node_statuses",
        "linux_node_summary",
        "windows_node_summary",
        "latest_windows_checkin",
        "record_windows_sub_node_checkin",
        "stage_meeting_packet_for_node",
        "remote_nodes",
        "windows_sub_engel",
        "sub_engel_prompts",
        "disabled_by_default",
    ), "meeting bridge")

    blocked = literal_collection(bridge_tree, "BLOCKED_MEETING_ACTIONS")
    for required in {
        "shell",
        "exec",
        "ssh",
        "disk.partition",
        "disk.format",
        "disk.erase",
        "provider.start",
        "model.start",
        "background.worker.start",
        "firewall.modify",
        "service.install",
    }:
        require(required in blocked, f"blocked meeting action missing: {required}")

    require_all(client_text, (
        "WINDOWS_STATE_DIR",
        "WINDOWS_SESSION_PATH",
        "node_kind_key",
        "session_path_for_node_kind",
        "connection_family",
        "paired_windows_sub_engel_node",
    ), "remote client")

    require_all(app_text, (
        '_node.render_status("windows")',
        'node_kind="windows"',
        "Windows Sub-Engel Node Remote Control Pair",
        "Windows Sub-Engel Node Remote Control Run",
    ), "engel_app wrappers")

    require("session.json" in ignore_text, "windows_sub_engel .gitignore must ignore session.json")
    require("checkins/*.json" in ignore_text, "windows_sub_engel .gitignore must ignore check-in registry JSON")

    forbidden = (
        "subprocess.",
        "os.system",
        "socketserver",
        "HTTPServer",
        "requests.",
        "paramiko",
        "sshtunnel",
        "diskpart",
        "format.com",
        "New-Partition",
        "Format-Volume",
        "Clear-Disk",
        "Windows Sub-Engel Node - connected",
        "Windows Sub-Engel Node connected",
    )
    require_absent(bridge_text, forbidden, "meeting bridge")

    print("SUB_ENGEL_MEETING_BRIDGE_VERIFY_PASS")
    print("linux_sub_engel=meeting_registry_ready")
    print("windows_sub_engel=meeting_registry_ready")
    print("runtime_started=no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
