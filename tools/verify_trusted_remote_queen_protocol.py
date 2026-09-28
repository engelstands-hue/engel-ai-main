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

DESIGN_PATH = ROOT / "memory" / "TRUSTED_REMOTE_QUEEN_PROTOCOL_DESIGN_V1.md"
CONTRACT_PATH = ROOT / "memory" / "COMMUNICATION_QUEEN_REMOTE_QUEEN_CONTRACT_V1.json"
ROUTE_MATRIX_PATH = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"

SOURCE_PATHS = {
    "app": ROOT / "engel_app.py",
    "companion": ROOT / "engel_companion.py",
    "gui": ROOT / "engel_research_office.py",
    "data": ROOT / "engel_research_office_data.py",
    "protocol_verifier": Path(__file__).resolve(),
}

REQUIRED_DESIGN_PHRASES = [
    "no runtime implementation yet",
    "manual allowlist only",
    "no open discovery by default",
    "no broadcast discovery by default",
    "no automatic pairing",
    "local trusted WiFi only in future",
    "device identity required",
    "authentication required",
    "encryption required",
    "user confirmation required",
    "per-device approval required",
    "per-project scope required",
    "no remote shell",
    "no remote command execution",
    "no provider/API expansion",
    "no remote trusted-memory writes",
    "no remote queue mutation",
    "no source edits",
    "no applied learning",
    "no background autonomy",
    "no file transfer unless separately approved",
    "heartbeat/status only as a future first runtime phase",
    "future runtime must be separately approved, verifier-covered, and bounded",
]

REQUIRED_PHASES = [
    "Phase 0: current scaffold only",
    "Phase 1: read-only route/status",
    "Phase 2: bundled GUI smoke",
    "Phase 3: protocol design and verifier",
    "Phase 4: local manual allowlist registry draft",
    "Phase 5: read-only heartbeat/status prototype only",
    "Phase 6: task proposal exchange only",
    "Phase 7: no applied learning until explicit approval",
]

REQUIRED_FALSE_FLAGS = [
    "runtime_enabled",
    "runtime_wifi_enabled",
    "trusted_wifi_runtime_enabled",
    "runtime_remote_queen_network_enabled",
    "remote_queen_runtime_enabled",
    "network_discovery_enabled",
    "device_pairing_enabled",
    "remote_execution_enabled",
    "background_service_enabled",
    "background_worker_enabled",
    "autonomous_remote_work_enabled",
    "remote_file_transfer_enabled",
    "trusted_memory_write_enabled",
    "remote_memory_write_enabled",
    "source_edit_enabled",
    "remote_source_edit_enabled",
    "queue_mutation_enabled",
    "remote_queue_mutation_enabled",
    "applied_learning_enabled",
    "provider_network_enabled",
    "provider_or_api_calls_enabled",
    "internet_behavior_enabled",
]

IMPLEMENTED_READ_ONLY_ROUTES = [
    "colony hive communication queen",
    "colony hive remote queens",
    "colony hive remote queen status",
    "research office remote queens",
]

FUTURE_ROUTE_SHAPES = [
    "communication queen status",
    "communication queen contract",
    "remote queens status",
    "remote queens candidates",
    "remote queen assignment preview",
]


class CheckFailure(Exception):
    pass


def _token(*parts: str) -> str:
    return "".join(parts)


EXECUTABLE_FORBIDDEN_PATTERNS = [
    ("net_import", r"\b(import|from)\s+" + _token("soc", "ket") + r"\b"),
    ("net_call", r"\b" + _token("soc", "ket") + r"\."),
    ("req_import", r"\bimport\s+" + _token("requ", "ests") + r"\b"),
    ("req_call", r"\b" + _token("requ", "ests") + r"\."),
    ("ws_pattern", r"\b" + _token("web", "soc", "ket") + r"\b"),
    ("bt_pattern", r"\b" + _token("blue", "tooth") + r"\b"),
    ("discovery_md", r"\b" + _token("m", "dns") + r"\b"),
    ("zero_conf_pattern", r"\b" + _token("zero", "conf") + r"\b"),
    ("process_import", r"\bimport\s+" + _token("sub", "process") + r"\b"),
    ("process_call", r"\b" + _token("sub", "process") + r"\."),
    ("thread_import", r"\bimport\s+" + _token("thread", "ing") + r"\b"),
    ("thread_call", r"\b" + _token("thread", "ing") + r"\."),
    ("multi_process_import", r"\bimport\s+" + _token("multi", "processing") + r"\b"),
    ("multi_process_call", r"\b" + _token("multi", "processing") + r"\."),
    ("watch_guard", r"\b" + _token("watch", "dog") + r"\b"),
    ("schedule_call", r"\b" + _token("schedule") + r"\."),
    ("while_true", r"\bwhile\s+True\b"),
    ("start_process", r"\bStart" + r"-" + r"Process\b"),
    ("os_system", r"\bos\.system\b"),
    ("process_open", r"\bPopen\b"),
]


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


def _require_phrase(text: str, phrase: str, label: str) -> None:
    if _normalize(phrase) not in _normalize(text):
        raise CheckFailure(f"{label} missing required phrase: {phrase}")


def _section(text: str, start_marker: str, end_marker: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise CheckFailure(f"{label} missing start marker: {start_marker}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise CheckFailure(f"{label} missing end marker after {start_marker}: {end_marker}")
    return text[start:end]


def _assert_design(text: str) -> None:
    for phrase in REQUIRED_DESIGN_PHRASES:
        _require_phrase(text, phrase, "protocol design")
    for phase in REQUIRED_PHASES:
        _require_phrase(text, phase, "protocol design phases")
    _require_phrase(text, "untrusted until reviewed, scanned, verified, and human-approved", "protocol trust boundary")


def _assert_contract(contract: object) -> None:
    if not isinstance(contract, dict):
        raise CheckFailure("Communication Queen contract must be a JSON object")
    if contract.get("contract_id") != "COMMUNICATION_QUEEN_REMOTE_QUEEN_CONTRACT_V1":
        raise CheckFailure("Communication Queen contract_id mismatch")
    if contract.get("status") != "scaffold_only":
        raise CheckFailure("Communication Queen contract status must remain scaffold_only")
    for flag in REQUIRED_FALSE_FLAGS:
        if contract.get(flag) is not False:
            raise CheckFailure(f"contract flag must remain explicit false: {flag}")
    remote_queens = contract.get("remote_queens")
    if not isinstance(remote_queens, dict):
        raise CheckFailure("contract missing remote_queens object")
    _require_phrase(str(remote_queens.get("current_behavior", "")), "Placeholder candidates only", "remote_queens")
    _require_phrase(str(remote_queens.get("output_trust", "")), "untrusted until reviewed", "remote_queens")
    _require_phrase(str(remote_queens.get("output_trust", "")), "human-approved", "remote_queens")


def _assert_route_matrix(matrix: object) -> None:
    if not isinstance(matrix, dict):
        raise CheckFailure("route matrix must be a JSON object")
    entries = matrix.get("route_regression_matrix_entries")
    if not isinstance(entries, list):
        raise CheckFailure("route matrix missing route_regression_matrix_entries")
    entry_map = {str(entry.get("command")): entry for entry in entries if isinstance(entry, dict)}
    for route in FUTURE_ROUTE_SHAPES:
        entry = entry_map.get(route)
        if not entry:
            raise CheckFailure(f"route matrix missing future route: {route}")
        if entry.get("implemented_now") is not False:
            raise CheckFailure(f"future route must remain unimplemented: {route}")
        if entry.get("should_execute_in_test") is not False:
            raise CheckFailure(f"future route must remain no-execute: {route}")
    for route in IMPLEMENTED_READ_ONLY_ROUTES:
        entry = entry_map.get(route)
        if not entry:
            raise CheckFailure(f"route matrix missing implemented read-only route: {route}")
        if entry.get("implemented_now") is not True:
            raise CheckFailure(f"implemented read-only route must remain implemented: {route}")
        if entry.get("route_status") != "implemented/read-only":
            raise CheckFailure(f"implemented read-only route status drifted: {route}")
        if entry.get("safety") != "read_only_status_only_no_runtime":
            raise CheckFailure(f"implemented read-only route safety drifted: {route}")
    expectations = matrix.get("communication_queen_remote_queen_contract_expectations")
    if not isinstance(expectations, dict):
        raise CheckFailure("route matrix missing communication queen expectations")
    if expectations.get("trusted_remote_queen_protocol_verifier") != "tools\\verify_trusted_remote_queen_protocol.py":
        raise CheckFailure("route matrix missing trusted Remote Queen protocol verifier reference")


def _communication_runtime_sections(source_texts: dict[str, str]) -> dict[str, str]:
    return {
        "engel_research_office.py Communication Queen tab": _section(
            source_texts["gui"],
            "def _make_communication_queen_tab",
            "def _make_permissions_tab",
            "Communication Queen GUI section",
        ),
        "engel_research_office_data.py Communication Queen constants": _section(
            source_texts["data"],
            "COMMUNICATION_QUEEN_STATUS",
            "EMPTY_FOLDER_SUMMARY",
            "Communication Queen data constants",
        ),
        "engel_research_office_data.py Communication Queen status render": _section(
            source_texts["data"],
            "def render_communication_queen_status",
            "def render_colony_hive_permissions",
            "Communication Queen status renderer",
        ),
        "engel_app.py read-only Communication Queen handlers": _section(
            source_texts["app"],
            "def research_office_remote_queens",
            "def colony_hive_permissions",
            "Communication Queen read-only route handlers",
        ),
        "trusted Remote Queen protocol verifier": source_texts["protocol_verifier"],
    }


def _assert_no_executable_runtime_patterns(sections: dict[str, str]) -> None:
    for label, text in sections.items():
        for pattern_name, pattern in EXECUTABLE_FORBIDDEN_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                raise CheckFailure(f"{label} contains executable forbidden pattern {pattern_name}: {match.group(0)}")


def _assert_companion_not_expanded(companion_text: str) -> None:
    normalized = _normalize(companion_text)
    for phrase in [
        "communication queen status",
        "remote queen status",
        "trusted remote queen protocol",
        "remote queen pairing",
    ]:
        if phrase in normalized:
            raise CheckFailure(f"engel_companion.py gained Remote Queen runtime/route text: {phrase}")


def _assert_app_routes_are_status_only(app_text: str, data_text: str) -> None:
    normalized = _normalize(app_text)
    for route in IMPLEMENTED_READ_ONLY_ROUTES:
        if route not in normalized:
            raise CheckFailure(f"missing read-only route in engel_app.py: {route}")
    output_source = app_text + "\n" + data_text
    for phrase in [
        "Communication Queen: SCAFFOLD ONLY / READ_ONLY_STATUS",
        "Remote Queen records:",
        "- untrusted/session-local/scaffold-only",
        "Bundled GUI smoke, then trusted-device protocol design.",
    ]:
        _require_phrase(output_source, phrase, "Communication Queen route output")
    forbidden_future_runtime_routes = [
        "trusted remote queen pair",
        "remote queen pair",
        "remote queen heartbeat",
        "remote queen allowlist add",
    ]
    for route in forbidden_future_runtime_routes:
        if route in normalized:
            raise CheckFailure(f"unexpected future runtime route appears in engel_app.py: {route}")


def _run() -> list[str]:
    results: list[str] = []

    design_text = _read_text(DESIGN_PATH)
    _assert_design(design_text)
    results.append("PASS protocol_design_required_boundaries")

    contract = _load_json(CONTRACT_PATH)
    _assert_contract(contract)
    results.append("PASS communication_queen_contract_runtime_flags_disabled")

    matrix = _load_json(ROUTE_MATRIX_PATH)
    _assert_route_matrix(matrix)
    results.append("PASS route_matrix_read_only_and_future_boundaries")

    source_texts = {name: _read_text(path) for name, path in SOURCE_PATHS.items()}
    sections = _communication_runtime_sections(source_texts)
    _assert_no_executable_runtime_patterns(sections)
    _assert_companion_not_expanded(source_texts["companion"])
    _assert_app_routes_are_status_only(source_texts["app"], source_texts["data"])
    results.append("PASS active_communication_sources_no_runtime_patterns")

    return results


def main() -> int:
    try:
        for line in _run():
            print(line)
        print()
        print("TRUSTED_REMOTE_QUEEN_PROTOCOL_VERIFICATION_PASS")
        return 0
    except CheckFailure as exc:
        print("TRUSTED_REMOTE_QUEEN_PROTOCOL_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
