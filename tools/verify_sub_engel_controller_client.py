#!/usr/bin/env python3
"""Verify Engel App's bounded Sub-Engel node controller lane."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "engel_sub_node_remote_control.py"
APP = ROOT / "engel_app.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
SESSION_GITIGNORE = ROOT / "remote_nodes" / "sub_engel" / ".gitignore"

REQUIRED_ALLOWED = {
    "node.status",
    "node.hardware",
    "node.safety",
    "node.controller",
    "net.status",
    "net.diagnose",
    "net.firmware",
    "install.status",
    "install.preflight",
    "install.list_disks",
    "ui.dashboard",
    "ui.visible_status",
    "shared_room.status",
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
}

REQUIRED_CLIENT_MARKERS = [
    'SESSION_PATH = STATE_DIR / "session.json"',
    'if action not in ALLOWED_ACTIONS:',
    'normalized_url(node_url, "/node/command")',
    '"Authorization"',
    'append_receipt({',
    'safe_response.pop("session_token", None)',
]

# (2026-07-28) "subprocess." left this list: the 20260727 CT-authoritative
# relay rework routes ROG Sub actions through ONE bounded authenticated
# `ssh` call to CT246 (no Sub bearer ever on the laptop), which requires
# subprocess.run. That exact relay shape is now REQUIRED below instead, and
# every other process/tunnel primitive stays forbidden.
FORBIDDEN_CLIENT_MARKERS = [
    "os.system",
    "subprocess.Popen",
    "shell=True",
    "socketserver",
    "HTTPServer",
    "paramiko",
    "sshtunnel",
    "diskpart",
    "format.com",
]

REQUIRED_RELAY_MARKERS = [
    "subprocess.run(",
    '"ssh"',
    "str(CT246_SSH_KEY)",
    "ct246_relay_reached",
]

REQUIRED_APP_MARKERS = [
    "def sub_engel_node_remote_control_status():",
    "def sub_engel_node_remote_control_help():",
    "def sub_engel_node_remote_control_pair(url=\"\", pairing_code=\"\"):",
    "def sub_engel_node_remote_control_run(action=\"\"):",
    "sub engel node remote control pair",
    "sub engel node remote control run",
]

REQUIRED_COMMAND_MARKERS = [
    "sub engel node remote control status",
    "sub engel node remote control help",
    "sub engel node remote control pair",
    "sub engel node remote control run",
    "node.status",
    "net.firmware",
    "install.preflight",
]


def fail(message: str) -> None:
    raise SystemExit(f"SUB_ENGEL_CONTROLLER_VERIFY_FAIL: {message}")


def literal_string_list(tree: ast.AST, name: str) -> set[str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if not isinstance(node.value, ast.List):
            fail(f"{name} is not a list literal")
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
    client_text = CLIENT.read_text(encoding="utf-8")
    app_text = APP.read_text(encoding="utf-8")
    command_text = COMMANDS.read_text(encoding="utf-8")
    ignore_text = SESSION_GITIGNORE.read_text(encoding="utf-8")

    tree = ast.parse(client_text)
    allowed = literal_string_list(tree, "ALLOWED_ACTIONS")
    blocked = literal_string_list(tree, "BLOCKED_ACTIONS")

    if not REQUIRED_ALLOWED.issubset(allowed):
        fail(f"client allowlist missing: {sorted(REQUIRED_ALLOWED - allowed)}")
    if not REQUIRED_BLOCKED.issubset(blocked):
        fail(f"client blocked list missing: {sorted(REQUIRED_BLOCKED - blocked)}")
    if allowed & REQUIRED_BLOCKED:
        fail(f"blocked actions leaked into allowlist: {sorted(allowed & REQUIRED_BLOCKED)}")

    require_all(client_text, REQUIRED_CLIENT_MARKERS, "client")
    require_absent(client_text, FORBIDDEN_CLIENT_MARKERS, "client")
    require_all(client_text, REQUIRED_RELAY_MARKERS, "client relay")
    if client_text.count("subprocess.run(") != 1:
        fail("client must contain exactly ONE bounded subprocess.run (the "
             "authenticated CT246 ssh relay)")
    require_all(app_text, REQUIRED_APP_MARKERS, "engel_app")
    require_all(command_text, REQUIRED_COMMAND_MARKERS, "memory commands")

    if "session.json" not in ignore_text:
        fail("remote_nodes/sub_engel/.gitignore does not ignore session.json")

    print("SUB_ENGEL_CONTROLLER_VERIFY_PASS")
    print(f"allowed_actions={len(allowed)}")
    print(f"blocked_actions={len(blocked)}")
    print("pairing_state=ignored_runtime_session")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
