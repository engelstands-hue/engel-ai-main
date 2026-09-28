#!/usr/bin/env python3
"""Verifier for the Engel Agent Meeting Room V1 build.

Checks the contract requirements without running the GUI:
  - source file exists, parses, defines required surfaces;
  - equipment targets present (Local, Sub-Engel OS Worker, Android App Worker);
  - per-participant bridge selection present;
  - Meeting Room has no job input surface;
  - Engel AI Main UI handoff helpers are present;
  - export path under reports/meeting_rooms;
  - no forbidden runtime/provider/network startup calls;
  - no C:\\Users or AppData\\Local\\Temp Engel-owned bridge paths;
  - never claims fake connected workers;
  - contract file exists; runtime folders exist;
  - Desktop V2 launcher hook present.

Success: prints ENGEL_AGENT_MEETING_ROOM_VERIFY_PASS and exits 0.
Failure: prints ENGEL_AGENT_MEETING_ROOM_VERIFY_FAIL and exits 1.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_agent_meeting_room.py"
DESKTOP_V2 = ROOT / "engel_desktop_v2.py"
BRIDGE = ROOT / "engel_agent_bridge.py"
SUB_NODE_MEETING_BRIDGE = ROOT / "engel_sub_node_meeting_bridge.py"
CONTRACT = ROOT / "memory" / "ENGEL_AGENT_MEETING_ROOM_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_MEETING_ROOM_BUILD.md"
RUNTIME_MR = ROOT / "runtime" / "meeting_room"
RUNTIME_BRIDGE = ROOT / "runtime" / "agent_bridge"
REPORTS_MR = ROOT / "reports" / "meeting_rooms"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# Forbidden function call names — checked via AST so docstrings / help text
# that mention the same words do NOT trigger a false positive.
FORBIDDEN_CALLS = {
    # subprocess family
    ("subprocess", "Popen"),
    ("subprocess", "run"),
    ("subprocess", "call"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
    # OS shell-out
    ("os", "system"),
    ("os", "popen"),
    # Browser / network
    ("webbrowser", "open"),
    ("requests", "get"),
    ("requests", "post"),
    ("requests", "put"),
    ("requests", "delete"),
    ("httpx", "get"),
    ("httpx", "post"),
    ("httpx", "put"),
    ("httpx", "delete"),
    # Provider SDK constructors
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
    # Browser automation
    ("playwright", "sync_api"),
    ("selenium", "webdriver"),
    # Model downloads
    ("huggingface_hub", "snapshot_download"),
}

# Forbidden bare function names (no module prefix).
FORBIDDEN_BARE_CALLS = {
    "snapshot_download",
}

# These phrases would indicate the module is *claiming* a fake connection.
FORBIDDEN_FAKE_CONNECTED = (
    "Sub-Engel OS Worker — connected",
    "Sub-Engel OS Worker connected",
    "Android App Worker — connected",
    "Android App Worker connected",
)

# Forbidden imports — modules that themselves perform forbidden behavior.
WINDOWS_FAKE_CONNECTED = (
    "Windows Sub-Engel Node - connected",
    "Windows Sub-Engel Node connected",
)

FORBIDDEN_IMPORT_ROOTS = {
    "paramiko",
    "fabric",
    "ssh",
    "selenium",
    "adb_shell",
    "ppadb",
}


def _attr_chain(node: ast.AST) -> tuple[str, ...]:
    """Return the dotted attribute chain for an AST node, e.g. requests.post."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.insert(0, cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.insert(0, cur.id)
    return tuple(parts)


def _str_constants_excluding_docstrings(tree: ast.AST) -> list[str]:
    """Collect string literal values that are NOT module/class/function docstrings.

    This way mentions of forbidden paths in module-level documentation do not
    register as real usage.
    """
    docstring_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                docstring_ids.add(id(body[0].value))
    strings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_ids:
                continue
            strings.append(node.value)
    return strings


def _file_exists(path: Path, label: str) -> None:
    require(path.exists() and path.is_file(), f"missing required file: {label} ({path})")


def _dir_exists(path: Path, label: str) -> None:
    require(path.exists() and path.is_dir(), f"missing required directory: {label} ({path})")


def check_files_and_dirs() -> None:
    _file_exists(MODULE, "engel_agent_meeting_room.py")
    _file_exists(DESKTOP_V2, "engel_desktop_v2.py")
    _file_exists(BRIDGE, "engel_agent_bridge.py")
    _file_exists(SUB_NODE_MEETING_BRIDGE, "engel_sub_node_meeting_bridge.py")
    _file_exists(CONTRACT, "Meeting Room contract V1")
    _dir_exists(RUNTIME_MR, "runtime/meeting_room/")
    _dir_exists(RUNTIME_BRIDGE, "runtime/agent_bridge/")
    _dir_exists(REPORTS_MR, "reports/meeting_rooms/")


def check_module_surface() -> None:
    source = read(MODULE)
    # AST parse to confirm syntactic validity
    tree = ast.parse(source)
    require("SHIP_TEAM_COLLAB_CHARTER" in source,
            "Meeting Room must define the ship-team collaboration charter")
    require("No public posts from this room" in source,
            "charter must forbid public posts from the Meeting Room")
    require("No fix until Josh" in source,
            "charter must hold fixes until Josh")
    require("No receipt = it did not happen" in source,
            "charter must require receipts")
    require("class AgentMeetingRoomWindow" in source,
            "engel_agent_meeting_room.py must define AgentMeetingRoomWindow class")
    require("def launch_meeting_room" in source,
            "engel_agent_meeting_room.py must define launch_meeting_room()")
    require("AGENT_TYPES" in source and "SKILL_TYPES" in source,
            "module must define AGENT_TYPES and SKILL_TYPES")
    for needle in ("Local Engel AI", "Sub-Engel OS Worker", "Windows Sub-Engel Node", "Android App Worker"):
        require(needle in source, f"equipment target missing: {needle}")
    require("EQUIPMENT_TARGETS" in source, "EQUIPMENT_TARGETS tuple missing")
    require("BRIDGE_OPTIONS" in source, "BRIDGE_OPTIONS tuple missing (per-agent bridges)")
    for needle in (
        "ChatGPT Bridge (Engel no-API handoff)",
        "Code Factory Scout (Engel Meeting Room)",
        "Codex API / Codex Bridge",
        "Claude API / Claude Bridge",
        "Local LLM",
        "Windows Sub-Engel Check-in Preview",
        "Engel Chat Auto Route",
    ):
        require(needle in source, f"bridge option missing: {needle}")
    # Per-agent bridge field on Participant
    require(re.search(r"class Participant\b", source) is not None,
            "Participant dataclass missing")
    require("bridge:" in source or "bridge =" in source,
            "Participant must include a 'bridge' field")
    require("skill_label:" in source or "skill_label =" in source,
            "Participant must include a 'skill_label' field")
    require("Agent Station" in source and "Save Agent Station" in source,
            "left panel must expose unified device -> agent -> skill station selection")
    require("Agent Cards" in source and "Main UI Order Intake" in source and "Order Flow" in source,
            "center panel must expose agent cards and main-UI order flow")
    require("SELF_UPGRADE_WORK_ORDER_DIR" in source and "SELF_UPGRADE_RUNTIME_WORK_ORDER_DIR" in source,
            "Meeting Room must define self-upgrade work-order directories")
    require("def _load_self_upgrade_work_orders" in source,
            "Meeting Room must load self-upgrade work orders")
    require("def _latest_self_upgrade_work_order_ui_text" in source,
            "Meeting Room must render self-upgrade work-order UI text")
    require("Self-Upgrade Work Orders" in source,
            "Meeting Room must expose self-upgrade work orders in the center panel/export")
    require("ENGEL_MEETING_ROOM_SELF_UPGRADE_WORK_ORDER_V1" in source,
            "Meeting Room must read the self-upgrade work-order schema")
    for forbidden_ui in (
        "Prompt / Job Launcher",
        "Send Selected",
        "Send Team",
        "self.prompt_input",
    ):
        require(forbidden_ui not in source,
                f"Meeting Room must not expose job input UI: {forbidden_ui}")
    require("self.right_panel" not in source and "RightPanel(self)" not in source,
            "main window must not instantiate a right-side panel")
    # Main UI order handoff surface
    require("class CenterChatPanel" in source, "missing CenterChatPanel")
    require("def submit_order_from_engel_main_ui" in source,
            "missing main UI order intake helper")
    require("def complete_order_from_engel_main_ui" in source,
            "missing main UI order completion helper")
    require("def _infer_skills_for_order" in source,
            "missing skill/talent auto-selection helper")
    require("def dispatch_station_work" in source, "module must define dispatch_station_work")
    require("route_companion_text_or_command" in source,
            "provider/API bridge work must route through Engel's existing chat/router spine")
    require("run_offline_seed_llm_for_companion_chat" in source,
            "local LLM bridge must use existing offline seed runner")
    require("export_room_summary" in source, "missing export_room_summary helper")
    require("reports" in source and "meeting_rooms" in source,
            "module must write summaries under reports/meeting_rooms")
    # Send-Job dispatcher
    require("sub_engel_prompts" in source,
            "Sub-Engel work must stage prompts locally for diagnostics/preview")
    require("engel_sub_node_meeting_bridge" in source,
            "Sub-Engel Meeting Room work must route through the local node meeting bridge")
    require("_probe_sub_engel_status" in source and "_probe_windows_sub_engel_status" in source,
            "Meeting Room must probe Linux and Windows Sub-Engel registry state")
    require("approved worker packet" in source,
            "Sub-Engel dispatcher must state runtime work remains blocked")
    # Approved Android dispatch must use the LAN assignment producer. The
    # phones poll /worker/next-assignment over WiFi/LAN; Meeting Room must not
    # spawn ADB directly or write unvalidated packets into worker dirs.
    require("from engel_communication_queen_assignment_producer import" in source
            and "create_assignment" in source,
            "Android dispatch must call engel_communication_queen_assignment_producer.create_assignment")
    require("_wait_for_android_worker_return" in source and "Returned results:" in source,
            "Android dispatch must surface returned phone results back to the Engel UI summary")
    require("WiFi / LAN pairing" in source and "USB / hardwire ADB" in source,
            "device targets must include WiFi/LAN and hardwire/USB connection modes")
    # Sub-Engel must remain preview-only.
    # Architect Agent station + bridge wiring.
    require('"Architect Agent"' in source,
            "AGENT_TYPES must include 'Architect Agent'")
    require('"Architect Workflow Skill"' in source,
            "SKILL_TYPES must include 'Architect Workflow Skill'")
    require("Engel Architect Agent (engel_architect_agent)" in source,
            "BRIDGE_OPTIONS must include 'Engel Architect Agent (engel_architect_agent)'")
    require('"Grok Bot"' in source,
            "AGENT_TYPES must include 'Grok Bot'")
    require('"Grok Bot Teammate Skill"' in source,
            "SKILL_TYPES must include 'Grok Bot Teammate Skill'")
    require("Grok Bot (cluster teammate)" in source,
            "BRIDGE_OPTIONS must include 'Grok Bot (cluster teammate)'")
    require("render_grok_bot_message" in source and "render_grok_bot_status" in source,
            "Grok Bot dispatch must use render_grok_bot_message + render_grok_bot_status")
    require("render_grok_bot_handoff" not in source,
            "Meeting Room must not call render_grok_bot_handoff")
    require("render_architect_overview" in source and "render_architect_status" in source,
            "Architect dispatch must use read-only render_architect_overview + render_architect_status")
    # Architect dispatch must NEVER call any architect *action* route — those
    # stay user-explicit so the Meeting Room cannot autonomously start/advance
    # or approve an Architect run.
    for forbidden in (
        "render_architect_start_new",
        "render_architect_run_section",
        "render_architect_approve_gate",
        "render_architect_complete_section",
        "render_architect_skip_section",
        "render_architect_retry_section",
        "render_architect_redirect_gate",
        "render_architect_close",
    ):
        require(forbidden not in source,
                f"Architect dispatcher must not invoke action helper: {forbidden}")


def check_no_forbidden_calls() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            chain = _attr_chain(node.func)
            if len(chain) >= 2 and (chain[0], chain[-1]) in FORBIDDEN_CALLS:
                bad.append(".".join(chain))
            if len(chain) == 1 and chain[0] in FORBIDDEN_BARE_CALLS:
                bad.append(chain[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    bad.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                bad.append(f"from {node.module}")
    require(not bad,
            f"forbidden behavior detected: {bad}")


def check_no_temp_or_appdata_path() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    # Engel-owned files in C:\Users\<user>\AppData\Local\Temp are banned, but
    # docstring mentions (used to *forbid* the path in policy text) are fine.
    forbidden_patterns = (
        "C:\\Users",
        "C:/Users",
        "AppData\\Local\\Temp",
        "AppData/Local/Temp",
    )
    bad: list[str] = []
    for value in _str_constants_excluding_docstrings(tree):
        for pat in forbidden_patterns:
            if pat in value:
                bad.append(f"{pat!r} found in non-docstring constant")
                break
    require(not bad,
            f"module must not depend on C:\\Users / AppData\\Local\\Temp for Engel-owned files: {bad}")


def check_no_fake_connected_workers() -> None:
    source = read(MODULE)
    for needle in FORBIDDEN_FAKE_CONNECTED:
        require(needle not in source,
                f"module must not claim a fake connection: {needle!r}")
    for needle in WINDOWS_FAKE_CONNECTED:
        require(needle not in source,
                f"module must not claim a fake Windows Sub-Engel connection: {needle!r}")
    # The module must honestly state that Sub-Engel is not yet under
    # remote control (preview-only). Android is allowed to surface as
    # connected when ADB actually reports devices — that's a real local
    # state, not a fake claim.
    require(
        "Sub-Engel OS Worker — preview-only" in source
        or "Sub-Engel OS Worker — not connected" in source
        or "Sub-Engel OS Worker - diagnostics/preview only" in source,
        "module must surface Sub-Engel OS Worker as preview-only or not connected",
    )
    # The Android line is dynamic; we just require the source not to claim
    # a hard-coded 'connected' state that isn't probed.
    require(
        "Android App Worker — not connected" in source
        or "_probe_android_status" in source,
        "module must either hard-state 'not connected' or probe ADB for live status",
    )


def check_desktop_v2_hook() -> None:
    source = read(DESKTOP_V2)
    require("_launch_meeting_room" in source,
            "Desktop V2 must expose _launch_meeting_room method")
    require("Meeting Room" in source,
            "Desktop V2 must show a 'Meeting Room' label on the launcher")
    require("engel_agent_meeting_room" in source,
            "Desktop V2 must import engel_agent_meeting_room")
    require("submit_order_from_engel_main_ui" in source,
            "Desktop V2 must stage orders into the Meeting Room from the main UI")
    require("complete_order_from_engel_main_ui" in source,
            "Desktop V2 must return main UI results back to the Meeting Room")
    # Chat intercept for the user's question phrases
    require("where is the meeting room" in source.lower()
            or "open meeting room" in source.lower(),
            "Desktop V2 chat panel must intercept 'meeting room' phrases")


def check_bridge_softened() -> None:
    source = read(BRIDGE)
    require("bridge_available" in source,
            "engel_agent_bridge.py must expose bridge_available()")
    require("bridge_missing_reason" in source,
            "engel_agent_bridge.py must expose bridge_missing_reason()")
    require("_resolve_agent_root" in source,
            "engel_agent_bridge.py must search multiple roots")
    # Ensure the import-time RuntimeError is gone.
    require("raise RuntimeError(\n        f\"engel_agent_main subtree missing" not in source,
            "engel_agent_bridge.py must not raise RuntimeError at module-import time")


def check_sub_node_meeting_bridge() -> None:
    source = read(SUB_NODE_MEETING_BRIDGE)
    tree = ast.parse(source)
    for needle in (
        "meeting_node_statuses",
        "stage_meeting_packet_for_node",
        "record_windows_sub_node_checkin",
        "remote_nodes",
        "windows_sub_engel",
        "sub_engel_prompts",
        "BLOCKED_MEETING_ACTIONS",
        "Windows Sub-Engel Node",
        "Sub-Engel OS Worker",
    ):
        require(needle in source, f"node meeting bridge missing marker: {needle}")
    for forbidden in (
        "subprocess.",
        "os.system",
        "socketserver",
        "HTTPServer",
        "requests.",
        "paramiko",
        "sshtunnel",
        "diskpart",
        "format.com",
    ):
        require(forbidden not in source,
                f"node meeting bridge must remain local registry/status only: {forbidden}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            chain = _attr_chain(node.func)
            if len(chain) >= 2 and (chain[0], chain[-1]) in FORBIDDEN_CALLS:
                raise CheckFailure(f"node meeting bridge forbidden call: {'.'.join(chain)}")


def check_contract() -> None:
    source = read(CONTRACT)
    for needle in (
        "Meeting Room is human-directed",
        "Sub-Engel OS Worker",
        "Android App Worker",
        "Per-Participant Bridge Selection",
        "BRIDGE_OPTIONS",
        "no job input",
        "Engel AI Main UI",
        "WiFi/LAN",
    ):
        # Soft-match keywords; accept either case
        require(needle in source or needle.replace("No PROVIDER", "NO PROVIDER") in source,
                f"contract missing required text: {needle!r}")


def main() -> int:
    checks = (
        check_files_and_dirs,
        check_module_surface,
        check_no_forbidden_calls,
        check_no_temp_or_appdata_path,
        check_no_fake_connected_workers,
        check_desktop_v2_hook,
        check_bridge_softened,
        check_sub_node_meeting_bridge,
        check_contract,
    )
    failures: list[str] = []
    for fn in checks:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except CheckFailure as exc:
            print(f"FAIL  {fn.__name__}: {exc}")
            failures.append(f"{fn.__name__}: {exc}")
        except Exception as exc:
            print(f"FAIL  {fn.__name__}: unexpected {type(exc).__name__}: {exc}")
            failures.append(f"{fn.__name__}: {type(exc).__name__}: {exc}")

    if failures:
        print()
        print("ENGEL_AGENT_MEETING_ROOM_VERIFY_FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1

    print()
    print("ENGEL_AGENT_MEETING_ROOM_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
