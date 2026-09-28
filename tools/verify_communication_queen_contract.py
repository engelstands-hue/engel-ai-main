from __future__ import annotations

import json
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

CONTRACT_PATH = ROOT / "memory" / "COMMUNICATION_QUEEN_REMOTE_QUEEN_CONTRACT_V1.json"
SCAFFOLD_CHECKPOINT_PATH = ROOT / "memory" / "V2APP_COMMUNICATION_QUEEN_REMOTE_QUEEN_SCAFFOLD.json"
ROUTE_MATRIX_PATH = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"

DOC_PATHS = {
    "standard_checklist": ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md",
    "engel_commands": ROOT / "memory" / "ENGEL_COMMANDS.md",
    "project_memory_index": ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
}

SOURCE_PATHS = {
    "gui": ROOT / "engel_research_office.py",
    "data": ROOT / "engel_research_office_data.py",
    "app": ROOT / "engel_app.py",
    "companion": ROOT / "engel_companion.py",
}

REQUIRED_FALSE_FLAGS = [
    "runtime_wifi_enabled",
    "runtime_remote_queen_network_enabled",
    "device_pairing_enabled",
    "background_service_enabled",
    "autonomous_remote_work_enabled",
    "remote_file_transfer_enabled",
    "trusted_memory_write_enabled",
    "queue_mutation_enabled",
    "source_edit_enabled",
    "applied_learning_enabled",
    "provider_network_enabled",
]

FUTURE_ROUTES = [
    "communication queen status",
    "communication queen contract",
    "remote queens status",
    "remote queens candidates",
    "remote queen assignment preview",
]

IMPLEMENTED_READ_ONLY_ROUTES = [
    "colony hive communication queen",
    "colony hive remote queens",
    "colony hive remote queen status",
    "research office remote queens",
]

EXECUTABLE_FORBIDDEN_PATTERNS = [
    ("socket_import", r"\b(import|from)\s+socket\b"),
    ("socket_call", r"\bsocket\."),
    ("requests_call", r"\brequests\."),
    ("requests_import", r"\bimport\s+requests\b"),
    ("websocket", r"\bwebsocket\b"),
    ("bluetooth", r"\bbluetooth\b"),
    ("mdns", r"\bmdns\b"),
    ("zeroconf", r"\bzeroconf\b"),
    ("subprocess_import", r"\bimport\s+subprocess\b"),
    ("subprocess_call", r"\bsubprocess\."),
    ("threading_import", r"\bimport\s+threading\b"),
    ("threading_call", r"\bthreading\."),
    ("multiprocessing_import", r"\bimport\s+multiprocessing\b"),
    ("multiprocessing_call", r"\bmultiprocessing\."),
    ("watchdog", r"\bwatchdog\b"),
    ("schedule_call", r"\bschedule\."),
    ("while_true", r"\bwhile\s+True\b"),
    ("start_process", r"\bStart-Process\b"),
    ("os_system", r"\bos\.system\b"),
    ("popen", r"\bPopen\b"),
    ("qnetwork", r"\bQNetwork\b"),
]


class CheckFailure(Exception):
    pass


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_text(path: Path) -> str:
    if not path.exists():
        raise CheckFailure(f"missing required file: {_rel(path)}")
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> object:
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"invalid JSON in {_rel(path)}: {exc}") from exc


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("\\", "/").replace("`", "").split())


def _require_text(text: str, needle: str, label: str) -> None:
    if _normalize(needle) not in _normalize(text):
        raise CheckFailure(f"{label} missing expected text: {needle}")


def _section(text: str, start_marker: str, end_marker: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise CheckFailure(f"{label} missing start marker: {start_marker}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise CheckFailure(f"{label} missing end marker after {start_marker}: {end_marker}")
    return text[start:end]


def _assert_contract(contract: object) -> None:
    if not isinstance(contract, dict):
        raise CheckFailure("contract JSON must be an object")
    if contract.get("contract_id") != "COMMUNICATION_QUEEN_REMOTE_QUEEN_CONTRACT_V1":
        raise CheckFailure("contract_id mismatch")
    if contract.get("status") != "scaffold_only":
        raise CheckFailure("contract status must remain scaffold_only")
    if contract.get("runtime_enabled") is not False:
        raise CheckFailure("runtime_enabled must be false")
    for flag in REQUIRED_FALSE_FLAGS:
        if contract.get(flag) is not False:
            raise CheckFailure(f"contract flag must be explicit false: {flag}")
    for legacy_flag in [
        "trusted_wifi_runtime_enabled",
        "remote_queen_runtime_enabled",
        "network_discovery_enabled",
        "remote_execution_enabled",
        "background_worker_enabled",
        "remote_memory_write_enabled",
        "remote_source_edit_enabled",
        "remote_queue_mutation_enabled",
        "provider_or_api_calls_enabled",
        "internet_behavior_enabled",
    ]:
        if contract.get(legacy_flag) is not False:
            raise CheckFailure(f"contract legacy safety flag must remain false: {legacy_flag}")

    remote_queens = contract.get("remote_queens")
    if not isinstance(remote_queens, dict):
        raise CheckFailure("contract missing remote_queens object")
    _require_text(str(remote_queens.get("current_behavior", "")), "Placeholder candidates only", "remote queen contract")
    _require_text(str(remote_queens.get("output_trust", "")), "untrusted until reviewed", "remote queen contract")
    _require_text(str(remote_queens.get("output_trust", "")), "human-approved", "remote queen contract")

    forbidden_now = contract.get("forbidden_now")
    if not isinstance(forbidden_now, list):
        raise CheckFailure("contract forbidden_now must be a list")
    for phrase in [
        "WiFi scanning",
        "LAN discovery",
        "Socket communication",
        "HTTP server or client behavior",
        "WebSocket behavior",
        "Bluetooth behavior",
        "Remote code execution",
        "Remote shell execution",
        "Autonomous task dispatch",
        "Background workers",
        "Trusted memory writes",
        "Source edits",
        "Queue mutation",
        "Provider or API calls",
        "Internet behavior",
        "Digest or history writes",
        "ALIVE_STATE writes",
    ]:
        if phrase not in forbidden_now:
            raise CheckFailure(f"contract forbidden_now missing: {phrase}")

    future_shapes = contract.get("future_route_shapes")
    if not isinstance(future_shapes, list):
        raise CheckFailure("contract future_route_shapes must be a list")
    shape_map = {
        str(item.get("route")): item for item in future_shapes if isinstance(item, dict)
    }
    for route in FUTURE_ROUTES:
        shape = shape_map.get(route)
        if not shape:
            raise CheckFailure(f"contract missing future route shape: {route}")
        if shape.get("implemented_now") is not False:
            raise CheckFailure(f"contract future route must remain unimplemented: {route}")
        if shape.get("should_execute_in_test") is not False:
            raise CheckFailure(f"contract future route must not execute in tests: {route}")


def _assert_checkpoint(checkpoint: object) -> None:
    if not isinstance(checkpoint, dict):
        raise CheckFailure("scaffold checkpoint must be a JSON object")
    if checkpoint.get("checkpoint_id") != "V2APP_COMMUNICATION_QUEEN_REMOTE_QUEEN_SCAFFOLD":
        raise CheckFailure("unexpected scaffold checkpoint_id")
    safety_state = checkpoint.get("safety_state")
    if not isinstance(safety_state, dict):
        raise CheckFailure("scaffold checkpoint missing safety_state")
    for flag in ["runtime_enabled", *REQUIRED_FALSE_FLAGS]:
        if safety_state.get(flag) is not False:
            raise CheckFailure(f"checkpoint safety_state must keep {flag}=false")
    if checkpoint.get("runtime_network_behavior_added") is not False:
        raise CheckFailure("checkpoint must state runtime_network_behavior_added=false")


def _assert_route_metadata(matrix: object) -> None:
    if not isinstance(matrix, dict):
        raise CheckFailure("route matrix must be a JSON object")
    entries = matrix.get("route_regression_matrix_entries")
    if not isinstance(entries, list):
        raise CheckFailure("route matrix missing route_regression_matrix_entries")
    entry_map = {str(entry.get("command")): entry for entry in entries if isinstance(entry, dict)}
    for route in FUTURE_ROUTES:
        entry = entry_map.get(route)
        if not entry:
            raise CheckFailure(f"route matrix missing future route entry: {route}")
        if entry.get("implemented_now") is not False:
            raise CheckFailure(f"route matrix must keep implemented_now=false for {route}")
        if entry.get("should_execute_in_test") is not False:
            raise CheckFailure(f"route matrix must keep should_execute_in_test=false for {route}")
        if entry.get("route_status") != "future/not implemented/no-execute":
            raise CheckFailure(f"route matrix must keep no-execute status for {route}")
        if entry.get("category") != "future_communication_queen":
            raise CheckFailure(f"route matrix category mismatch for {route}")

    for route in IMPLEMENTED_READ_ONLY_ROUTES:
        entry = entry_map.get(route)
        if not entry:
            raise CheckFailure(f"route matrix missing implemented read-only route entry: {route}")
        if entry.get("implemented_now") is not True:
            raise CheckFailure(f"route matrix must keep implemented_now=true for {route}")
        if entry.get("should_execute_in_test") is not True:
            raise CheckFailure(f"route matrix should execute read-only smoke for {route}")
        if entry.get("route_status") != "implemented/read-only":
            raise CheckFailure(f"route matrix must keep read-only status for {route}")
        if entry.get("safety") != "read_only_status_only_no_runtime":
            raise CheckFailure(f"route matrix must keep no-runtime safety label for {route}")

    expectations = matrix.get("communication_queen_remote_queen_contract_expectations")
    if not isinstance(expectations, dict):
        raise CheckFailure("route matrix missing communication queen expectations")
    if expectations.get("implemented_now") is not False:
        raise CheckFailure("communication queen expectations must remain implemented_now=false")
    if expectations.get("should_execute_in_test") is not False:
        raise CheckFailure("communication queen expectations must remain should_execute_in_test=false")
    expected_flags = expectations.get("required_disabled_flags")
    if not isinstance(expected_flags, list):
        raise CheckFailure("communication queen expectations missing required_disabled_flags")
    for flag in REQUIRED_FALSE_FLAGS:
        if flag not in expected_flags:
            raise CheckFailure(f"route matrix expectations missing disabled flag: {flag}")
    implemented_routes = expectations.get("implemented_read_only_routes")
    if not isinstance(implemented_routes, list):
        raise CheckFailure("communication queen expectations missing implemented_read_only_routes")
    for route in IMPLEMENTED_READ_ONLY_ROUTES:
        if route not in implemented_routes:
            raise CheckFailure(f"communication queen expectations missing implemented route: {route}")


def _communication_sections(gui_text: str, data_text: str) -> dict[str, str]:
    return {
        "engel_research_office.py communication tab": _section(
            gui_text,
            "def _make_communication_queen_tab",
            "def _make_permissions_tab",
            "Communication Queen GUI section",
        ),
        "engel_research_office_data.py communication constants": _section(
            data_text,
            "COMMUNICATION_QUEEN_STATUS",
            "EMPTY_FOLDER_SUMMARY",
            "Communication Queen data constants",
        ),
        "engel_research_office_data.py communication snapshot": _section(
            data_text,
            "def build_communication_queen_snapshot",
            "def _signal_growth_level",
            "Communication Queen data snapshot",
        ),
    }


def _assert_gui_data_safety_copy(gui_text: str, data_text: str) -> None:
    combined = gui_text + "\n" + data_text
    for phrase in [
        "OFFLINE SCAFFOLD",
        "NO NETWORK ACTIVE",
        "Trusted WiFi Runtime",
        "Remote Queen Runtime",
        "Network Discovery",
        "Remote Execution",
        "Remote Memory Writes",
        "Remote Source Edits",
        "Background Workers",
        "No device discovery has run.",
        "No remote device is connected.",
        "No remote task can be assigned.",
        "untrusted until reviewed",
        "human-approved",
    ]:
        _require_text(combined, phrase, "Communication Queen GUI/data safety copy")


def _assert_no_executable_patterns(sections: dict[str, str]) -> None:
    for label, text in sections.items():
        for pattern_name, pattern in EXECUTABLE_FORBIDDEN_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                raise CheckFailure(
                    f"{label} contains executable forbidden pattern {pattern_name}: {match.group(0)}"
                )


def _assert_wifi_only_safety_copy(sections: dict[str, str]) -> None:
    allowed_context = [
        "future",
        "trusted",
        "runtime",
        "enabled",
        "scaffold",
        "does not scan",
        "not active",
        "communication",
        "coordinator",
    ]
    disallowed_runtime_context = [
        "ssid",
        "adapter",
        "pywifi",
        "wifi.scan",
        "wifi.connect",
        "scan_wifi",
        "connect_wifi",
    ]
    for label, text in sections.items():
        for line_number, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if "wifi" not in lowered:
                continue
            if any(term in lowered for term in disallowed_runtime_context):
                raise CheckFailure(f"{label} line {line_number} uses WiFi runtime context: {line.strip()}")
            if not any(term in lowered for term in allowed_context):
                raise CheckFailure(f"{label} line {line_number} has WiFi outside safety/status copy: {line.strip()}")


def _assert_no_runtime_route_implementation(app_text: str, companion_text: str) -> None:
    combined = app_text + "\n" + companion_text
    app_normalized = _normalize(app_text)
    companion_normalized = _normalize(companion_text)
    for route in IMPLEMENTED_READ_ONLY_ROUTES:
        if route not in app_normalized:
            raise CheckFailure(f"implemented read-only route missing from engel_app.py: {route}")
    if "research_office_remote_queens" not in app_text:
        raise CheckFailure("engel_app.py missing research_office_remote_queens read-only handler")
    for route in FUTURE_ROUTES:
        quoted_single = "'" + route + "'"
        quoted_double = '"' + route + '"'
        if quoted_single in app_text or quoted_double in app_text:
            raise CheckFailure(f"future Communication Queen route appears as implemented command: {route}")
    for phrase in [
        "remote queen assignment preview",
        "remote queen runtime",
    ]:
        if phrase in app_normalized or phrase in companion_normalized:
            raise CheckFailure(f"Communication Queen runtime phrase appears in app/companion source: {phrase}")
    if "communication queen" in companion_normalized or "remote queens" in companion_normalized:
        raise CheckFailure("Communication Queen / Remote Queen route text must not be added to engel_companion.py")


def _assert_docs_alignment(docs: dict[str, str]) -> None:
    for route in IMPLEMENTED_READ_ONLY_ROUTES:
        _require_text(docs["engel_commands"], route, "ENGEL_COMMANDS")
    _require_text(docs["engel_commands"], "communication queen status [future/not implemented/no-execute", "ENGEL_COMMANDS")
    _require_text(docs["standard_checklist"], "Before Communication Queen / Remote Queen Scaffold Work", "standard checklist")
    _require_text(docs["standard_checklist"], "Run `python .\\tools\\verify_communication_queen_contract.py`", "standard checklist")
    _require_text(docs["project_memory_index"], "Communication Queen / Remote Queens", "project memory index")
    _require_text(docs["project_memory_index"], "tools\\verify_communication_queen_contract.py", "project memory index")


def _assert_provider_and_mutation_disabled(contract: dict) -> None:
    for flag in [
        "provider_network_enabled",
        "provider_or_api_calls_enabled",
        "trusted_memory_write_enabled",
        "queue_mutation_enabled",
        "source_edit_enabled",
        "applied_learning_enabled",
        "remote_execution_enabled",
        "background_service_enabled",
        "background_worker_enabled",
    ]:
        if contract.get(flag) is not False:
            raise CheckFailure(f"contract must keep {flag}=false")


def _run() -> list[str]:
    results: list[str] = []
    contract = _load_json(CONTRACT_PATH)
    _assert_contract(contract)
    results.append("PASS contract_json_and_disabled_flags")

    checkpoint = _load_json(SCAFFOLD_CHECKPOINT_PATH)
    _assert_checkpoint(checkpoint)
    results.append("PASS scaffold_checkpoint_alignment")

    matrix = _load_json(ROUTE_MATRIX_PATH)
    _assert_route_metadata(matrix)
    results.append("PASS future_route_metadata_non_executing")

    gui_text = _read_text(SOURCE_PATHS["gui"])
    data_text = _read_text(SOURCE_PATHS["data"])
    app_text = _read_text(SOURCE_PATHS["app"])
    companion_text = _read_text(SOURCE_PATHS["companion"])
    sections = _communication_sections(gui_text, data_text)
    _assert_gui_data_safety_copy(gui_text, data_text)
    results.append("PASS gui_data_disabled_safety_copy")

    _assert_no_executable_patterns(sections)
    _assert_wifi_only_safety_copy(sections)
    results.append("PASS communication_slices_no_network_or_background_execution")

    _assert_no_runtime_route_implementation(app_text, companion_text)
    results.append("PASS communication_queen_routes_read_only_and_companion_unchanged")

    docs = {name: _read_text(path) for name, path in DOC_PATHS.items()}
    _assert_docs_alignment(docs)
    results.append("PASS docs_alignment_for_direct_verifier")

    if not isinstance(contract, dict):
        raise CheckFailure("contract must be a dict for provider/mutation assertions")
    _assert_provider_and_mutation_disabled(contract)
    results.append("PASS provider_mutation_autonomy_boundaries_disabled")
    return results


def main() -> int:
    try:
        for line in _run():
            print(line)
        print()
        print("COMMUNICATION_QUEEN_CONTRACT_VERIFICATION_PASS")
        return 0
    except CheckFailure as exc:
        print("COMMUNICATION_QUEEN_CONTRACT_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
