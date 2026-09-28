#!/usr/bin/env python3
"""Verify Windows Sub-Engel node agent safety and controller integration."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "engel_windows_sub_node_agent.py"
CLIENT = ROOT / "engel_sub_node_remote_control.py"
APP = ROOT / "engel_app.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
GITIGNORE = ROOT / "remote_nodes" / "windows_sub_engel" / ".gitignore"

REQUIRED_ALLOWED = {
    "node.status",
    "node.hardware",
    "node.safety",
    "node.controller",
    "net.status",
    "net.diagnose",
    "install.status",
    "install.preflight",
    "install.list_disks",
    "ui.dashboard",
    "ui.visible_status",
    "direct_work.execute",
    "remote.status",
}

REQUIRED_BLOCKED = {
    "shell",
    "exec",
    "ssh",
    "reboot",
    "shutdown",
    "package.install",
    "install.install",
    "disk.partition",
    "disk.format",
    "disk.erase",
    "wifi.connect",
    "provider.start",
    "model.start",
    "controller.runtime.start",
    "background.worker.start",
    "registry.write",
    "service.install",
    "firewall.modify",
    "shared_room.status",
    "shared_room.process_latest_work_order",
    "shared_room.process_pending_work_orders",
}

REQUIRED_AGENT_MARKERS = [
    "APPROVE_ENGEL_WINDOWS_SUB_NODE",
    "DEFAULT_PORT = 8776",
    "PAIRING_TTL_SECONDS",
    "SESSION_TTL_SECONDS",
    "secrets.compare_digest",
    "host_requires_lan_approval",
    "ThreadingHTTPServer",
    "/pair",
    "/node/command",
    "subprocess.run",
    "Remote disk install/format/partition: disabled",
    "Windows-preserve mode",
    "Get-Disk",
    "ENGEL DEVICE-SIDE VISIBLE PROOF",
    "Visible proof: paired controller commands print in this foreground window.",
    "direct_work.execute",
    "ct246_authenticated_direct_http",
    'ENGEL_SUB_ENGEL_LLM_TIMEOUT_SECONDS", "300"',
    "real_worker_completion",
    "local_llm_completed",
    "windows_sub_engel_direct_work_failed",
    "firewall.modify",
    "valid_proposed_session_token",
    "proposed_session_token",
    "idempotent_replay",
    "current_session_record_is_live",
    "session-preserving",
]

FORBIDDEN_AGENT_MARKERS = [
    "shell=True",
    "os.system",
    "Popen",
    "format.com",
    "diskpart",
    "New-Partition",
    "Format-Volume",
    "Remove-Partition",
    "Clear-Disk",
    "Initialize-Disk",
    "New-Service",
    "netsh advfirewall firewall add",
]

REQUIRED_CLIENT_MARKERS = [
    "python engel_windows_sub_node_agent.py token",
    "APPROVE_ENGEL_WINDOWS_SUB_NODE",
    "WINDOWS-NODE-IP:8776",
    '"direct_work.execute"',
    '"node_kind": response.get("node_kind"',
    '"proposed_session_token": proposed_token',
    '"pair_timeout_recovered": True',
]

REQUIRED_APP_MARKERS = [
    "def windows_sub_engel_node_remote_control_status():",
    "def windows_sub_engel_node_remote_control_help():",
    "def windows_sub_engel_node_remote_control_pair(url=\"\", pairing_code=\"\"):",
    "def windows_sub_engel_node_remote_control_run(action=\"\"):",
    "windows sub engel node remote control pair",
    "windows sub engel node remote control run",
]

REQUIRED_COMMAND_MARKERS = [
    "windows sub engel node remote control status",
    "windows sub engel node remote control help",
    "windows sub engel node remote control pair",
    "windows sub engel node remote control run",
    "APPROVE_ENGEL_WINDOWS_SUB_NODE",
    "WINDOWS-NODE-IP:8776",
]


def fail(message: str) -> None:
    raise SystemExit(f"WINDOWS_SUB_ENGEL_VERIFY_FAIL: {message}")


def literal_string_collection(tree: ast.AST, name: str) -> set[str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Set)):
            fail(f"{name} is not a literal list/set")
        values: set[str] = set()
        for item in node.value.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                fail(f"{name} contains a non-string literal")
            values.add(item.value)
        return values
    fail(f"{name} not found")
    return set()


def require_all(text: str, markers: list[str], label: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        fail(f"{label} missing markers: {missing}")


def require_absent(text: str, markers: list[str], label: str) -> None:
    present = [marker for marker in markers if marker in text]
    if present:
        fail(f"{label} contains forbidden markers: {present}")


def main() -> int:
    for path in [AGENT, CLIENT, APP, COMMANDS, GITIGNORE]:
        if not path.exists():
            fail(f"missing required file: {path}")

    agent_text = AGENT.read_text(encoding="utf-8-sig")
    client_text = CLIENT.read_text(encoding="utf-8")
    app_text = APP.read_text(encoding="utf-8")
    command_text = COMMANDS.read_text(encoding="utf-8")
    ignore_text = GITIGNORE.read_text(encoding="utf-8")

    tree = ast.parse(agent_text)
    allowed = literal_string_collection(tree, "ALLOWED_ACTIONS")
    blocked = literal_string_collection(tree, "BLOCKED_ACTIONS")
    if not REQUIRED_ALLOWED.issubset(allowed):
        fail(f"agent allowlist missing: {sorted(REQUIRED_ALLOWED - allowed)}")
    if not REQUIRED_BLOCKED.issubset(blocked):
        fail(f"agent blocked list missing: {sorted(REQUIRED_BLOCKED - blocked)}")
    if allowed & REQUIRED_BLOCKED:
        fail(f"blocked actions leaked into allowlist: {sorted(allowed & REQUIRED_BLOCKED)}")

    require_all(agent_text, REQUIRED_AGENT_MARKERS, "agent")
    require_absent(agent_text, FORBIDDEN_AGENT_MARKERS, "agent")
    require_all(client_text, REQUIRED_CLIENT_MARKERS, "controller client")
    require_all(app_text, REQUIRED_APP_MARKERS, "engel_app")
    require_all(command_text, REQUIRED_COMMAND_MARKERS, "memory commands")
    for marker in ["pairing-session.json", "session-token.json", "windows-sub-node-state.json"]:
        if marker not in ignore_text:
            fail(f"windows_sub_engel .gitignore missing {marker}")

    print("WINDOWS_SUB_ENGEL_VERIFY_PASS")
    print(f"allowed_actions={len(allowed)}")
    print(f"blocked_actions={len(blocked)}")
    print("default_service=none_foreground_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
