from __future__ import annotations

import re
import sys
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

COMPANION_PATH = ROOT / "engel_companion.py"
SUPER_SWARM_PATH = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
APP_PATH = ROOT / "engel_app.py"
ROUTER_PATH = ROOT / "engel_communication_router.py"

SURFACES = [
    {
        "name": "Companion",
        "path": COMPANION_PATH,
        "constants_start": "# ENGEL_MOBILE_CONNECTION_COMPANION_READONLY_TAB_V1_CONSTANTS_START",
        "constants_end": "# ENGEL_MOBILE_CONNECTION_COMPANION_READONLY_TAB_V1_CONSTANTS_END",
        "panel_start": "# ENGEL_MOBILE_CONNECTION_COMPANION_READONLY_TAB_V1_PANEL_START",
        "panel_end": "# ENGEL_MOBILE_CONNECTION_COMPANION_READONLY_TAB_V1_PANEL_END",
        "tab_needle": 'addTab(self.mobile_connection_panel, "Mobile")',
        "remote_badge_needle": 'MOBILE_ENGEL_REMOTE_WORKERS_LABEL + ": Blocked"',
        "remote_split_needle": '"Engel Remote Workers"',
    },
    {
        "name": "Super Swarm",
        "path": SUPER_SWARM_PATH,
        "constants_start": "# ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_CONSTANTS_START",
        "constants_end": "# ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_CONSTANTS_END",
        "panel_start": "# ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_PANEL_START",
        "panel_end": "# ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_PANEL_END",
        "tab_needle": 'addTab(self._build_mobile_connection_panel(), "Mobile")',
        "remote_badge_needle": 'MOBILE_SWARM_REMOTE_QUEENS_LABEL + ": Blocked"',
        "remote_split_needle": '"Engel Remote Workers"',
    },
]

REQUIRED_SAFETY_COPY = [
    "Engel Mobile Connection",
    "Contract installed; runtime not enabled",
    "Mobile: Planned",
    "Runtime: Disabled",
    "Networking: Not implemented",
    "Pairing: Not implemented",
    "Packets: Untrusted",
    "Commands: Blocked",
    "Human approval: Required",
]

REQUIRED_SECTIONS = [
    "Mobile Overview",
    "Safety Boundaries",
    "Planned Packet Types",
    "Empty Inbox / Requests",
    "Receipts & Reports Placeholder",
    "Local Documents / Contracts",
]

REMOTE_HANDOFF_SECTION_NAMES = [
    "Engel Remote Worker Handoff Placeholder",
    "Remote Queen Handoff Placeholder",
]

PACKET_CATEGORIES = [
    "mobile_status_snapshot",
    "mobile_note",
    "mobile_request",
    "mobile_receipt_view_request",
    "mobile_report_view_request",
    "mobile_approval_request",
    "mobile_remote_queen_task_request",
    "mobile_health_ping",
    "mobile_device_profile",
    "mobile_sync_summary",
    "mobile_error_report",
    "mobile_permission_request",
]

DISABLED_ACTIONS = [
    "Refresh Local Mobile Status",
    "View Mobile Contract",
    "View Mobile Display Design",
    "Open Mobile Inbox",
    "Open Mobile Receipts",
    "Review Pending Mobile Request",
    "Pair Device",
    "Enable Mobile Runtime",
    "Start Engel Remote Worker",
    "Export Mobile Status Report",
]

APPROVED_LOCAL_DOCS = [
    "memory\\ENGEL_MOBILE_CONNECTION_CONTRACT_V1.json",
    "memory\\ENGEL_MOBILE_CONNECTION_PLAN_V1.md",
    "memory\\MOBILE_CONNECTION_STATUS_DISPLAY_DESIGN_V1.json",
    "memory\\ENGEL_MOBILE_CONNECTION_STATUS_DISPLAY_DESIGN_V1.md",
    "memory\\MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_CONTRACT_V1.json",
    "memory\\ENGEL_MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_CONTRACT_V1.md",
    "memory\\MIXED_COLONY_ARCHITECTURE_CONTRACT_V1.json",
    "reports\\codex_bridge\\ENGEL_MOBILE_CONNECTION_CONTRACT.md",
    "reports\\codex_bridge\\MOBILE_CONNECTION_STATUS_DISPLAY_DESIGN.md",
    "reports\\codex_bridge\\MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_CONTRACT.md",
]

PLANNED_ROUTE_NAMES = [
    "mobile connection desktop status",
    "mobile connection gui status",
    "mobile connection surface contract",
    "mobile connection safety surface",
]

FORBIDDEN_EXECUTABLE_PATTERNS = [
    ("socket_import", r"\b(import|from)\s+socket\b"),
    ("socket_call", r"\bsocket\."),
    ("requests_import", r"\bimport\s+requests\b"),
    ("requests_call", r"\brequests\."),
    ("urllib_import", r"\b(import|from)\s+urllib\b"),
    ("http_server", r"\bHTTPServer\b|\bhttp\.server\b"),
    ("webbrowser", r"\bwebbrowser\b"),
    ("email_module", r"\b(import|from)\s+email\b"),
    ("subprocess", r"\bsubprocess\b|\bPopen\b"),
    ("threading", r"\bthreading\b|\bThread\b"),
    ("multiprocessing", r"\bmultiprocessing\b"),
    ("qtimer", r"\bQTimer\b"),
    ("watchdog", r"\bwatchdog\b"),
    ("schedule", r"\bschedule\."),
    ("while_true", r"\bwhile\s+True\b"),
    ("core_write_file", r"\bcore\.write_file\b"),
    ("path_write_text", r"\.write_text\s*\("),
    ("path_write_bytes", r"\.write_bytes\s*\("),
    ("open_call", r"\bopen\s*\("),
    ("queue_mutation", r"\bqueue\b.*\b(append|put|write|mutate)\b"),
    ("source_mutation", r"\b(source|route)\b.*\b(write|mutate|edit)\b"),
    ("folder_browse", r"\.iterdir\s*\(|\.glob\s*\(|\.rglob\s*\("),
]

FAKE_LIVE_PATTERNS = [
    r"\bonline\b",
    r"\blive device\b",
    r"\bconnected device\b",
    r"\bactive connection\b",
    r"\bpaired device found\b",
]


class CheckFailure(Exception):
    pass


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure(f"missing required file: {_rel(path)}")
    return path.read_text(encoding="utf-8", errors="replace")


def _normalize(text: str) -> str:
    cleaned = text.lower().replace("\\", "/").replace("`", "")
    cleaned = re.sub(r"/+", "/", cleaned)
    return " ".join(cleaned.split())


def _require(text: str, needle: str, label: str) -> None:
    if _normalize(needle) not in _normalize(text):
        raise CheckFailure(f"{label} missing expected text: {needle}")


def _section(text: str, start_marker: str, end_marker: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise CheckFailure(f"{label} missing start marker: {start_marker}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise CheckFailure(f"{label} missing end marker: {end_marker}")
    return text[start:end]


def _assert_visible_copy(surface: dict[str, Path | str], source: str, mobile_source: str) -> None:
    name = str(surface["name"])
    _require(source, str(surface["tab_needle"]), name + " Mobile tab")
    for phrase in REQUIRED_SAFETY_COPY:
        _require(source, phrase, name + " Mobile tab safety copy")
    if "Engel Remote Workers: Blocked" not in source and "Remote Queens: Blocked" not in source:
        if str(surface["remote_badge_needle"]) not in source:
            raise CheckFailure(name + " Mobile tab safety copy missing visible Engel Remote Workers: Blocked badge")
        if str(surface["remote_split_needle"]) not in source:
            raise CheckFailure(name + " Mobile tab Engel Remote Workers badge must be constructed from safe text")
    for section in REQUIRED_SECTIONS:
        _require(source, section, name + " Mobile tab section label")
    if not any(_normalize(section) in _normalize(source) for section in REMOTE_HANDOFF_SECTION_NAMES):
        raise CheckFailure(name + " Mobile tab missing Engel Remote Worker handoff section")
    for metric in [
        "paired_devices_count: 0",
        "pending_mobile_packets_count: 0",
        "pending_mobile_requests_count: 0",
        "pending_mobile_approval_requests_count: 0",
        "mobile_runtime_enabled: false",
        "mobile_networking_enabled: false",
        "mobile_pairing_enabled: false",
        "remote_queen_mobile_handoff_enabled: false",
    ]:
        _require(mobile_source, metric, name + " Mobile tab static metric")


def _assert_packet_categories(source: str) -> None:
    for packet in PACKET_CATEGORIES:
        _require(source, packet, "Mobile tab planned packet category")
    _require(source, "Untrusted / Planned / Non-actioning", "Mobile packet trust label")


def _assert_disabled_actions(source: str) -> None:
    for action in DISABLED_ACTIONS:
        if action == "Start Engel Remote Worker" and _normalize(action) not in _normalize(source):
            _require(source, "Start Remote Queen", "Mobile tab disabled action label")
        else:
            _require(source, action, "Mobile tab disabled action label")
    if "button.setEnabled(False)" not in source and ".setEnabled(False)" not in source:
        raise CheckFailure("Mobile disabled-action implementation missing disabled button call")
    _require(
        source,
        "Planned/not enabled. This read-only Mobile tab does not execute actions.",
        "Mobile disabled-action implementation",
    )


def _assert_approved_docs(source: str) -> None:
    for doc in APPROVED_LOCAL_DOCS:
        _require(source, doc, "Mobile tab approved local doc path")
    for phrase in [
        "Approved local docs/config presence only",
        "No arbitrary path expansion",
        "NoSelection",
        "NoEditTriggers",
    ]:
        _require(source, phrase, "Mobile local docs safety copy")


def _assert_planned_routes_absent_from_active_sources() -> None:
    combined = "\n".join(
        _read(path)
        for path in [APP_PATH, COMPANION_PATH, SUPER_SWARM_PATH, ROUTER_PATH]
        if path.exists()
    )
    normalized = _normalize(combined)
    for route in PLANNED_ROUTE_NAMES:
        if _normalize(route) in normalized:
            raise CheckFailure(f"planned Mobile desktop route/display name appears in active Python source: {route}")


def _assert_no_forbidden_runtime_patterns(mobile_source: str, surface_name: str) -> None:
    for label, pattern in FORBIDDEN_EXECUTABLE_PATTERNS:
        match = re.search(pattern, mobile_source, flags=re.IGNORECASE)
        if match:
            raise CheckFailure(
                f"{surface_name} Mobile tab source contains forbidden executable pattern {label}: {match.group(0)}"
            )
    for pattern in FAKE_LIVE_PATTERNS:
        match = re.search(pattern, mobile_source, flags=re.IGNORECASE)
        if match:
            raise CheckFailure(f"{surface_name} Mobile tab source suggests fake live state: {match.group(0)}")
    if "QPushButton(" not in mobile_source:
        raise CheckFailure(surface_name + " Mobile tab should show disabled/non-executing action controls")
    if ".clicked.connect" in mobile_source:
        raise CheckFailure(surface_name + " Mobile tab must not connect disabled action handlers")


def _run() -> list[str]:
    results: list[str] = []
    for surface in SURFACES:
        name = str(surface["name"])
        source = _read(Path(surface["path"]))
        constants_source = _section(
            source,
            str(surface["constants_start"]),
            str(surface["constants_end"]),
            name + " Mobile constants",
        )
        panel_source = _section(
            source,
            str(surface["panel_start"]),
            str(surface["panel_end"]),
            name + " Mobile panel",
        )
        mobile_source = constants_source + "\n" + panel_source

        _assert_visible_copy(surface, source, mobile_source)
        results.append("PASS " + name.lower().replace(" ", "_") + "_mobile_tab_label_header_and_safety_copy")

        _assert_packet_categories(mobile_source)
        results.append("PASS " + name.lower().replace(" ", "_") + "_planned_packet_categories_documented_untrusted")

        _assert_disabled_actions(mobile_source)
        results.append("PASS " + name.lower().replace(" ", "_") + "_disabled_future_action_labels_non_executing")

        _assert_approved_docs(mobile_source)
        results.append("PASS " + name.lower().replace(" ", "_") + "_approved_local_docs_config_paths_referenced")

        _assert_no_forbidden_runtime_patterns(mobile_source, name)
        results.append("PASS " + name.lower().replace(" ", "_") + "_mobile_tab_source_no_runtime_network_worker_mutation_patterns")

    _assert_planned_routes_absent_from_active_sources()
    results.append("PASS forbidden_route_names_not_implemented")

    return results


def main() -> int:
    try:
        for line in _run():
            print(line)
        print()
        print("MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_VERIFICATION_PASS")
        return 0
    except CheckFailure as exc:
        print("MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
