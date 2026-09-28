#!/usr/bin/env python3
"""Verify the Windows Sub-Engel two-node setup kit."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fail(message: str) -> None:
    raise AssertionError(message)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"missing or unreadable file: {path} ({exc})")


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"missing or invalid JSON: {path} ({exc})")
    if not isinstance(data, dict):
        fail(f"expected JSON object: {path}")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> int:
    checks: list[str] = []

    workflow = ROOT / "workflows" / "sub_engel_nodes"
    installer_path = workflow / "install_windows_sub_engel_node.ps1"
    structure_path = workflow / "windows_sub_engel_file_structure.json"
    bootstrap_bat = workflow / "start_windows_sub_engel_bootstrap_server.bat"
    pair_bat = workflow / "pair_latest_windows_sub_engel_node.bat"
    bootstrap_server_path = ROOT / "tools" / "windows_sub_engel_wired_bootstrap_server.py"
    pair_helper_path = ROOT / "tools" / "pair_latest_windows_sub_engel_node.py"
    manifest_path = ROOT / "remote_nodes" / "windows_sub_engel" / "fleet_manifest.json"

    for path in [
        installer_path,
        structure_path,
        bootstrap_bat,
        pair_bat,
        bootstrap_server_path,
        pair_helper_path,
        manifest_path,
    ]:
        require(path.exists(), f"required setup-kit file missing: {path}")
    checks.append("setup-kit files exist")

    structure = read_json(structure_path)
    directories = set(structure.get("directories") or [])
    for required_dir in [
        "workspace\\agent_meeting",
        "workspace\\codex",
        "workspace\\vscode",
        "workspace\\jobs\\incoming",
        "workspace\\reports",
        "runtime\\meeting_room\\staged",
    ]:
        require(required_dir in directories, f"file structure missing {required_dir}")
    require(structure.get("safety", {}).get("raw_shell") is False, "file structure must keep raw_shell disabled")
    checks.append("file structure manifest includes agent meeting, Codex, and VS Code workspace folders")

    installer = read_text(installer_path)
    for marker in [
        "Python.Python.3.12",
        "ENGEL_WINDOWS_SUB_NODE_STATE",
        "workspace\\agent_meeting",
        "workspace\\codex",
        "workspace\\vscode",
        "operator_confirmed",
        "Codex signed in",
        "APPROVE_ENGEL_WINDOWS_SUB_NODE",
        "/node-ready",
    ]:
        require(marker in installer, f"installer missing marker: {marker}")
    for forbidden in [
        "New-Service",
        "Register-ScheduledTask",
        "Start-Job",
        "Invoke-Expression",
        "ssh.exe",
        "diskpart",
        "Format-Volume",
    ]:
        require(forbidden not in installer, f"installer contains blocked primitive: {forbidden}")
    checks.append("installer creates folders, handles Python bootstrap, and remains foreground/pair-gated")

    bootstrap_server = read_text(bootstrap_server_path)
    for marker in [
        "install_windows_sub_engel_node.ps1",
        "windows_sub_engel_file_structure.json",
        "/start.ps1",
        "/node-ready",
    ]:
        require(marker in bootstrap_server, f"bootstrap server missing marker: {marker}")
    checks.append("main-side bootstrap server serves installer and file-structure manifest")

    manifest = read_json(manifest_path)
    nodes = manifest.get("nodes")
    require(isinstance(nodes, list) and len(nodes) >= 2, "fleet manifest must contain at least two Windows nodes")
    statuses = [str(n.get("agent_meeting_status") or "") for n in nodes if isinstance(n, dict)]
    registered_statuses = [s for s in statuses if s.startswith("registered")]
    require(len(registered_statuses) >= 1, "fleet manifest missing a registered Windows node")
    require(
        "planned_waiting_for_bootstrap" in statuses or len(registered_statuses) >= 2,
        "fleet manifest missing either a planned fresh node or two registered Windows nodes",
    )
    for node in nodes:
        if not isinstance(node, dict):
            fail("fleet manifest node entry must be an object")
        confirmed = node.get("operator_confirmed") or {}
        require(confirmed.get("vscode_open") is True, f"{node.get('node_id')} missing VS Code confirmation")
        require(confirmed.get("codex_signed_in") is True, f"{node.get('node_id')} missing Codex confirmation")
    checks.append("fleet manifest tracks registered/planned nodes with VS Code/Codex confirmation")

    from engel_sub_node_meeting_bridge import meeting_node_statuses

    status = meeting_node_statuses()
    require("windows_sub_engel_fleet_nodes" in status, "meeting bridge missing fleet-node summaries")
    require("windows_sub_engel_planned_nodes" in status, "meeting bridge missing planned-node summaries")
    fleet_nodes = status.get("windows_sub_engel_fleet_nodes") or []
    planned_nodes = status.get("windows_sub_engel_planned_nodes") or []
    require(len(fleet_nodes) >= 2, "meeting bridge sees fewer than two fleet nodes")
    require(
        len(planned_nodes) >= 1 or len(status.get("windows_sub_engel_nodes") or []) >= 2,
        "meeting bridge should expose either planned Windows nodes or two registered Windows nodes",
    )
    checks.append("Agent Meeting Room bridge exposes Windows Sub-Engel fleet nodes")

    print(json.dumps({"ok": True, "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
