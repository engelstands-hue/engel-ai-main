from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "memory" / "ENGEL_HIVE_DATA_SERVICES_CONTRACT_V1.json"
BUILDER_MODULE = "engel_research_office_data"
BUILDER_NAME = "build_colony_hive_snapshot"
SELF_PATH = Path(__file__).resolve()


class CheckSet:
    def __init__(self) -> None:
        self.passes: list[str] = []
        self.failures: list[str] = []

    def ok(self, name: str) -> None:
        self.passes.append(name)
        print("PASS " + name)

    def fail(self, name: str, detail: str) -> None:
        message = name + ": " + detail
        self.failures.append(message)
        print("FAIL " + message)


def _type_matches(value: Any, expected: str) -> bool:
    normalized = expected.strip().lower()
    if normalized in {"string", "string timestamp", "string path"}:
        return isinstance(value, str)
    if normalized == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if normalized == "boolean":
        return isinstance(value, bool)
    if normalized == "object":
        return isinstance(value, dict)
    if normalized.startswith("list"):
        return isinstance(value, list)
    return True


def _load_contract(checks: CheckSet) -> dict[str, Any]:
    if not CONTRACT_PATH.exists():
        checks.fail("contract_file_exists", "missing " + str(CONTRACT_PATH))
        return {}
    try:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        checks.fail("contract_json_loads", type(exc).__name__ + ": " + str(exc))
        return {}
    if contract.get("contract_id") != "ENGEL_HIVE_DATA_SERVICES_CONTRACT_V1":
        checks.fail("contract_id", "unexpected contract_id " + str(contract.get("contract_id")))
    else:
        checks.ok("contract_id")
    if contract.get("current_snapshot_builder") != BUILDER_NAME:
        checks.fail("contract_current_builder", "expected " + BUILDER_NAME)
    else:
        checks.ok("contract_current_builder")
    return contract


def _load_builder(checks: CheckSet):
    sys.dont_write_bytecode = True
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        module = importlib.import_module(BUILDER_MODULE)
    except Exception as exc:
        checks.fail("builder_module_import", type(exc).__name__ + ": " + str(exc))
        return None
    builder = getattr(module, BUILDER_NAME, None)
    if not callable(builder):
        checks.fail("builder_callable", BUILDER_MODULE + "." + BUILDER_NAME + " is not callable")
        return None
    checks.ok("builder_callable")
    return builder


def _self_static_check(checks: CheckSet) -> None:
    source = SELF_PATH.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=str(SELF_PATH))
    except SyntaxError as exc:
        checks.fail("verifier_ast_parse", str(exc))
        return

    forbidden_import_roots = {
        "PySide6",
        "PyQt6",
        "tkinter",
        "requests",
        "httpx",
        "socket",
        "urllib",
        "subprocess",
        "multiprocessing",
        "threading",
        "webbrowser",
    }
    forbidden_call_names = {
        "open",
        "exec",
        "eval",
        "compile",
    }
    forbidden_call_attrs = {
        "write_text",
        "write_bytes",
        "unlink",
        "remove",
        "rmdir",
        "mkdir",
        "rename",
        "replace",
        "Popen",
        "run",
        "check_call",
        "check_output",
        "startfile",
    }

    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in forbidden_import_roots:
                    found.append("forbidden import " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root in forbidden_import_roots:
                found.append("forbidden import-from " + module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in forbidden_call_names:
                found.append("forbidden call " + func.id)
            if isinstance(func, ast.Attribute) and func.attr in forbidden_call_attrs:
                found.append("forbidden call attribute " + func.attr)

    if found:
        checks.fail("verifier_static_no_forbidden_behavior", "; ".join(sorted(set(found))))
    else:
        checks.ok("verifier_static_no_forbidden_behavior")


def _validate_top_level(snapshot: dict[str, Any], contract: dict[str, Any], checks: CheckSet) -> None:
    schema = contract.get("snapshot_schema", {})
    entries = schema.get("top_level_keys", [])
    missing: list[str] = []
    bad_types: list[str] = []
    for entry in entries:
        key = str(entry.get("key", ""))
        if not key:
            continue
        if entry.get("required") and key not in snapshot:
            missing.append(key)
            continue
        if key in snapshot and not _type_matches(snapshot[key], str(entry.get("type", ""))):
            bad_types.append(key + " expected " + str(entry.get("type", "")))
    if missing:
        checks.fail("snapshot_required_top_level_keys", "missing " + ", ".join(missing))
    else:
        checks.ok("snapshot_required_top_level_keys")
    if bad_types:
        checks.fail("snapshot_required_top_level_types", "; ".join(bad_types))
    else:
        checks.ok("snapshot_required_top_level_types")


def _validate_nested(snapshot: dict[str, Any], contract: dict[str, Any], checks: CheckSet) -> None:
    entries = contract.get("snapshot_schema", {}).get("top_level_keys", [])
    missing: list[str] = []
    for entry in entries:
        key = str(entry.get("key", ""))
        nested = list(entry.get("required_nested_keys", []))
        if not key or not nested or key not in snapshot:
            continue
        value = snapshot[key]
        if isinstance(value, dict):
            for nested_key in nested:
                if nested_key not in value:
                    missing.append(key + "." + str(nested_key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if not isinstance(item, dict):
                    missing.append(key + "[" + str(index) + "] not object")
                    continue
                for nested_key in nested:
                    if nested_key not in item:
                        missing.append(key + "[" + str(index) + "]." + str(nested_key))
        else:
            missing.append(key + " not object/list for nested validation")

    grouped_roles: list[str] = []
    for entry in entries:
        if entry.get("key") == "grouped_cells":
            grouped_roles = list(entry.get("required_roles", []))
            break
    grouped = snapshot.get("grouped_cells", {})
    if isinstance(grouped, dict):
        for role in grouped_roles:
            if role not in grouped:
                missing.append("grouped_cells." + str(role))

    if missing:
        checks.fail("snapshot_required_nested_keys", "; ".join(missing[:80]))
    else:
        checks.ok("snapshot_required_nested_keys")


def _validate_cells(snapshot: dict[str, Any], contract: dict[str, Any], checks: CheckSet) -> None:
    schema = contract.get("snapshot_schema", {}).get("cell_object_schema", {})
    required = list(schema.get("required_base_keys", [])) + list(schema.get("required_enriched_keys", []))
    cells = snapshot.get("cells", [])
    if not isinstance(cells, list):
        checks.fail("snapshot_cells_schema", "cells is not a list")
        return
    missing: list[str] = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            missing.append("cells[" + str(index) + "] not object")
            continue
        for key in required:
            if key not in cell:
                missing.append("cells[" + str(index) + "]." + str(key))
    if missing:
        checks.fail("snapshot_cells_schema", "; ".join(missing[:80]))
    else:
        checks.ok("snapshot_cells_schema")

    if isinstance(snapshot.get("desks"), list) and len(snapshot["desks"]) == len(cells):
        checks.ok("snapshot_desks_cell_count_compatibility")
    else:
        checks.fail("snapshot_desks_cell_count_compatibility", "desks must remain a cells-compatible list")

    if snapshot.get("cell_count") == len(cells):
        checks.ok("snapshot_cell_count_matches_cells")
    else:
        checks.fail("snapshot_cell_count_matches_cells", "cell_count does not match len(cells)")


def _validate_super_swarm_keys(snapshot: dict[str, Any], checks: CheckSet) -> None:
    critical = [
        "cells",
        "grouped_cells",
        "queens",
        "workers",
        "memory_nests",
        "guardian_cards",
        "proposal_lanes",
        "permissions",
        "super_swarm_hive_live",
        "communication_queen",
        "guardian_layer",
        "mind_summary",
        "mycelium_signals",
    ]
    missing = [key for key in critical if key not in snapshot]
    if missing:
        checks.fail("super_swarm_consumer_critical_keys", "missing " + ", ".join(missing))
    else:
        checks.ok("super_swarm_consumer_critical_keys")


def _expect_false(section: dict[str, Any], key: str, failures: list[str], prefix: str) -> None:
    if section.get(key) is not False:
        failures.append(prefix + "." + key + " expected false")


def _validate_disabled_markers(snapshot: dict[str, Any], checks: CheckSet) -> None:
    failures: list[str] = []
    live = snapshot.get("super_swarm_hive_live", {})
    if isinstance(live, dict):
        _expect_false(live, "live_enabled", failures, "super_swarm_hive_live")
        _expect_false(live, "can_execute_from_hive", failures, "super_swarm_hive_live")
        if live.get("safety_state") != "VISUAL_ANIMATION_AND_BOUNDED_READ_ONLY_REFRESH_ONLY":
            failures.append("super_swarm_hive_live.safety_state changed")
    else:
        failures.append("super_swarm_hive_live not object")

    communication = snapshot.get("communication_queen", {})
    if isinstance(communication, dict):
        if communication.get("mode") != "READ_ONLY_ARCHITECTURE_SCAFFOLD":
            failures.append("communication_queen.mode expected READ_ONLY_ARCHITECTURE_SCAFFOLD")
        status = communication.get("status", {})
        if isinstance(status, dict):
            for key in [
                "runtime_remote_queen_network_enabled",
                "remote_queen_runtime_enabled",
                "provider_or_api_calls_enabled",
                "internet_behavior_enabled",
                "background_worker_enabled",
                "queue_mutation_enabled",
                "trusted_memory_write_enabled",
                "network_discovery_enabled",
                "device_pairing_enabled",
                "autonomous_remote_work_enabled",
                "remote_file_transfer_enabled",
                "source_edit_enabled",
                "applied_learning_enabled",
                "provider_network_enabled",
            ]:
                if key in status:
                    _expect_false(status, key, failures, "communication_queen.status")
        else:
            failures.append("communication_queen.status not object")
        candidates = communication.get("remote_queen_candidates", [])
        if isinstance(candidates, list):
            for index, candidate in enumerate(candidates):
                if not isinstance(candidate, dict):
                    failures.append("communication_queen.remote_queen_candidates[" + str(index) + "] not object")
                    continue
                if candidate.get("can_assign_tasks_now") is not False:
                    failures.append("remote queen candidate can_assign_tasks_now expected false")
                if "untrusted" not in str(candidate.get("output_trust", "")).lower():
                    failures.append("remote queen candidate output_trust missing untrusted marker")
        else:
            failures.append("communication_queen.remote_queen_candidates not list")
    else:
        failures.append("communication_queen not object")

    permissions = snapshot.get("permissions", [])
    if isinstance(permissions, list) and permissions:
        for index, permission in enumerate(permissions):
            if not isinstance(permission, dict):
                failures.append("permissions[" + str(index) + "] not object")
                continue
            if permission.get("can_execute_from_hive") is not False:
                failures.append("permissions[" + str(index) + "].can_execute_from_hive expected false")
    elif isinstance(permissions, list):
        if "source_error" not in snapshot:
            failures.append("permissions empty without source_error")
    else:
        failures.append("permissions not list")

    signals = snapshot.get("mycelium_signals", [])
    if isinstance(signals, list):
        for index, signal in enumerate(signals):
            if not isinstance(signal, dict):
                failures.append("mycelium_signals[" + str(index) + "] not object")
                continue
            if str(signal.get("runtime", "")).lower() != "read-only display":
                failures.append("mycelium_signals[" + str(index) + "].runtime expected read-only display")
    else:
        failures.append("mycelium_signals not list")

    guardian = snapshot.get("guardian_layer", {})
    if isinstance(guardian, dict):
        blocks = [str(item).lower() for item in guardian.get("blocks", [])]
        for needle in ["trusted-memory writes", "source edits", "route mutations", "queue mutations"]:
            if needle not in blocks:
                failures.append("guardian_layer.blocks missing " + needle)
    else:
        failures.append("guardian_layer not object")

    mind = snapshot.get("mind_summary", {})
    if isinstance(mind, dict):
        if "no provider call" not in str(mind.get("brain_provider_state", "")).lower():
            failures.append("mind_summary.brain_provider_state missing no-provider marker")
        if str(mind.get("safe_mode", "")).upper() != "ON":
            failures.append("mind_summary.safe_mode expected ON")
    else:
        failures.append("mind_summary not object")

    if failures:
        checks.fail("snapshot_disabled_state_markers", "; ".join(failures[:80]))
    else:
        checks.ok("snapshot_disabled_state_markers")


def _validate_safe_empty_states(snapshot: dict[str, Any], checks: CheckSet) -> None:
    failures: list[str] = []
    live = snapshot.get("super_swarm_hive_live", {})
    if isinstance(live, dict):
        if not isinstance(live.get("recent_local_paths", []), list):
            failures.append("recent_local_paths must be a list, including when empty")
        if not isinstance(live.get("memory_colony_signals", []), list):
            failures.append("memory_colony_signals must be a list, including when empty")
        if not isinstance(live.get("local_signal_counts", {}), dict):
            failures.append("local_signal_counts must be a dict, including when empty")
    grouped = snapshot.get("grouped_cells", {})
    if isinstance(grouped, dict):
        for role, value in grouped.items():
            if not isinstance(value, list):
                failures.append("grouped_cells." + str(role) + " must be a list, including when empty")
    if failures:
        checks.fail("snapshot_safe_empty_states", "; ".join(failures))
    else:
        checks.ok("snapshot_safe_empty_states")


def main() -> int:
    checks = CheckSet()
    _self_static_check(checks)
    contract = _load_contract(checks)
    builder = _load_builder(checks)
    snapshot: Any = None
    if builder is not None:
        try:
            snapshot = builder(ROOT)
        except Exception as exc:
            checks.fail("builder_call_workspace_root", type(exc).__name__ + ": " + str(exc))
        else:
            checks.ok("builder_call_workspace_root")
    if isinstance(snapshot, dict):
        checks.ok("snapshot_is_dict")
        if contract:
            _validate_top_level(snapshot, contract, checks)
            _validate_nested(snapshot, contract, checks)
            _validate_cells(snapshot, contract, checks)
            _validate_super_swarm_keys(snapshot, checks)
            _validate_disabled_markers(snapshot, checks)
            _validate_safe_empty_states(snapshot, checks)
    else:
        checks.fail("snapshot_is_dict", "builder returned " + type(snapshot).__name__)

    if checks.failures:
        print("")
        print("HIVE_SNAPSHOT_SCHEMA_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("- " + failure)
        return 1
    print("")
    print("HIVE_SNAPSHOT_SCHEMA_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
