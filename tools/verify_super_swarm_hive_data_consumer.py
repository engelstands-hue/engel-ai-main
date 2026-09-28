from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SUPER_SWARM_SOURCE = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
WRAPPER_MODULE = "engel_hive_data_services"
WRAPPER_FUNCTION = "build_hive_snapshot"

CONSUMER_CRITICAL_TYPES: dict[str, type] = {
    "cells": list,
    "grouped_cells": dict,
    "queens": list,
    "workers": list,
    "permissions": list,
    "super_swarm_hive_live": dict,
    "communication_queen": dict,
    "guardian_layer": dict,
    "mind_summary": dict,
    "memory_nests": list,
    "guardian_cards": list,
    "proposal_lanes": list,
    "mycelium_signals": list,
}

SUPER_SWARM_TEXT_TERMS: dict[str, list[str]] = {
    "cells": ['"cells"', "source_snapshot.get(\"cells\""],
    "grouped_cells": ['"grouped_cells"'],
    "queens": ['"queens"', "queen_registry"],
    "workers": ['"workers"', "worker_cell_registry"],
    "permissions": ['"permissions"', "permission_store"],
    "super_swarm_hive_live": ['"super_swarm_hive_live"', "signal_snapshot"],
    "communication_queen": ['"communication_queen"', "communication_snapshot"],
    "guardian_layer": ['"guardian_layer"', "guardian_layers"],
    "mind_summary": ['"mind_summary"'],
    "memory_nests": ['"memory_nests"', "nest_registry"],
    "guardian_cards": ['"guardian_cards"', "guardian_layers"],
    "proposal_lanes": ['"proposal_lanes"', "lane_state"],
    "mycelium_signals": ['"mycelium_signals"', "mycelium_signal"],
}


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


def _read_super_swarm_source(checks: CheckSet) -> str:
    if not SUPER_SWARM_SOURCE.exists():
        checks.fail("super_swarm_source_exists", "missing " + str(SUPER_SWARM_SOURCE))
        return ""
    try:
        source = SUPER_SWARM_SOURCE.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        checks.fail("super_swarm_source_readable", type(exc).__name__ + ": " + str(exc))
        return ""
    checks.ok("super_swarm_source_exists")
    checks.ok("super_swarm_source_readable")
    return source


def _self_static_check(checks: CheckSet) -> None:
    source = Path(__file__).read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=__file__)
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
        "openai",
        "anthropic",
        "google",
        "llama_cpp",
        "transformers",
        "torch",
    }
    forbidden_call_names = {
        "open",
        "exec",
        "eval",
        "compile",
        "__import__",
    }
    forbidden_call_attrs = {
        "write",
        "writelines",
        "write_text",
        "write_bytes",
        "touch",
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


def _check_super_swarm_source_contract(source: str, checks: CheckSet) -> None:
    if "from engel_hive_data_services import build_hive_snapshot" in source:
        checks.ok("super_swarm_wrapper_import_present")
    else:
        checks.fail("super_swarm_wrapper_import_present", "wrapper import not found")

    forbidden_direct_import_terms = [
        "from engel_research_office_data import build_colony_hive_snapshot",
        "import engel_research_office_data",
    ]
    direct_imports = [term for term in forbidden_direct_import_terms if term in source]
    if direct_imports:
        checks.fail("super_swarm_no_direct_research_office_import", "found " + "; ".join(direct_imports))
    else:
        checks.ok("super_swarm_no_direct_research_office_import")

    if "build_hive_snapshot(ROOT)" in source:
        checks.ok("super_swarm_wrapper_call_present")
    else:
        checks.fail("super_swarm_wrapper_call_present", "build_hive_snapshot(ROOT) not found")

    missing_terms: list[str] = []
    for key, terms in SUPER_SWARM_TEXT_TERMS.items():
        if not any(term in source for term in terms):
            missing_terms.append(key)
    if missing_terms:
        checks.fail("consumer_critical_keys_present_or_documented_in_source", ", ".join(missing_terms))
    else:
        checks.ok("consumer_critical_keys_present_or_documented_in_source")

    required_fallback_terms = [
        "def _empty_snapshot",
        '"source_error"',
        'snapshot.get("super_swarm_hive_live", {})',
        'snapshot.get("communication_queen", {})',
        'snapshot.get("permissions", [])',
        'self.source_snapshot = dict(snapshot)',
    ]
    missing_fallback_terms = [term for term in required_fallback_terms if term not in source]
    if missing_fallback_terms:
        checks.fail("super_swarm_fallback_and_copy_behavior_present", "; ".join(missing_fallback_terms))
    else:
        checks.ok("super_swarm_fallback_and_copy_behavior_present")

    try:
        tree = ast.parse(source, filename=str(SUPER_SWARM_SOURCE))
    except SyntaxError as exc:
        checks.fail("super_swarm_source_ast_parse", str(exc))
        return
    mutating_attrs = {"update", "clear", "pop", "popitem", "setdefault"}
    mutations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets: list[ast.AST] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                    if target.value.id == "snapshot":
                        mutations.append("assignment to snapshot subscript")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == "snapshot" and func.attr in mutating_attrs:
                    mutations.append("snapshot." + func.attr + "()")
    if mutations:
        checks.fail("super_swarm_does_not_mutate_input_snapshot_variable", "; ".join(sorted(set(mutations))))
    else:
        checks.ok("super_swarm_does_not_mutate_input_snapshot_variable")


def _collect_file_state(root: Path) -> dict[str, tuple[int, int]]:
    state: dict[str, tuple[int, int]] = {}
    guarded_paths: list[Path] = []
    for pattern in ["*.py", "*.json", "*.md", "*.spec"]:
        guarded_paths.extend(root.glob(pattern))
    for folder_name in ["tools", "memory", "reports", "configs", "routes", "queues"]:
        folder = root / folder_name
        if folder.exists():
            guarded_paths.extend(folder.rglob("*"))

    for path in guarded_paths:
        if "__pycache__" in path.parts:
            continue
        try:
            if not path.is_file():
                continue
            stat = path.stat()
            state[path.relative_to(root).as_posix()] = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            continue
    return state


def _load_wrapper(checks: CheckSet):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        module = importlib.import_module(WRAPPER_MODULE)
    except Exception as exc:
        checks.fail("wrapper_module_import", type(exc).__name__ + ": " + str(exc))
        return None
    builder = getattr(module, WRAPPER_FUNCTION, None)
    if not callable(builder):
        checks.fail("wrapper_build_hive_snapshot_callable", WRAPPER_FUNCTION + " is not callable")
        return None
    checks.ok("wrapper_module_import")
    checks.ok("wrapper_build_hive_snapshot_callable")
    return builder


def _validate_wrapper_snapshot(builder: Any, checks: CheckSet) -> None:
    before = _collect_file_state(ROOT)
    try:
        snapshot = builder(ROOT)
    except Exception as exc:
        checks.fail("wrapper_snapshot_call_workspace_root", type(exc).__name__ + ": " + str(exc))
        return
    after = _collect_file_state(ROOT)
    checks.ok("wrapper_snapshot_call_workspace_root")

    if before == after:
        checks.ok("wrapper_snapshot_call_no_file_mutation")
    else:
        changed = sorted(
            path for path in set(before) | set(after) if before.get(path) != after.get(path)
        )
        checks.fail("wrapper_snapshot_call_no_file_mutation", "; ".join(changed[:40]))

    if isinstance(snapshot, dict):
        checks.ok("wrapper_snapshot_is_dict")
    else:
        checks.fail("wrapper_snapshot_is_dict", "got " + type(snapshot).__name__)
        return

    _validate_consumer_critical_shape(snapshot, checks)
    _validate_cell_records(snapshot, checks)
    _validate_signal_records(snapshot, checks)
    _validate_disabled_status(snapshot, checks)
    _validate_guardian_and_mind_sections(snapshot, checks)
    _validate_safe_empty_states(snapshot, checks)


def _validate_consumer_critical_shape(snapshot: dict[str, Any], checks: CheckSet) -> None:
    failures: list[str] = []
    for key, expected_type in CONSUMER_CRITICAL_TYPES.items():
        if key not in snapshot:
            failures.append(key + " missing")
        elif not isinstance(snapshot[key], expected_type):
            failures.append(key + " expected " + expected_type.__name__)
    if failures:
        checks.fail("consumer_critical_snapshot_keys_and_types", "; ".join(failures))
    else:
        checks.ok("consumer_critical_snapshot_keys_and_types")


def _validate_cell_records(snapshot: dict[str, Any], checks: CheckSet) -> None:
    cells = snapshot.get("cells", [])
    required = [
        "id",
        "role",
        "colony_id",
        "nest_name",
        "cell_name",
        "actor",
        "current_task",
        "command",
        "signal_type",
        "confidence_marker",
        "safety_state",
        "proposal_only",
        "accent",
        "local_link",
        "exists",
        "kind",
        "status",
    ]
    failures: list[str] = []
    if isinstance(cells, list):
        for index, cell in enumerate(cells):
            if not isinstance(cell, dict):
                failures.append("cells[" + str(index) + "] not object")
                continue
            for key in required:
                if key not in cell:
                    failures.append("cells[" + str(index) + "]." + key + " missing")
    else:
        failures.append("cells not list")
    if failures:
        checks.fail("super_swarm_cell_record_fields_available", "; ".join(failures[:80]))
    else:
        checks.ok("super_swarm_cell_record_fields_available")


def _validate_signal_records(snapshot: dict[str, Any], checks: CheckSet) -> None:
    live = snapshot.get("super_swarm_hive_live", {})
    failures: list[str] = []
    if not isinstance(live, dict):
        checks.fail("super_swarm_signal_fields_available", "super_swarm_hive_live not object")
        return
    list_fields = ["memory_colony_signals", "recent_local_paths"]
    int_fields = [
        "total_signal_strength",
        "files_inspected",
        "report_count",
        "proposal_candidate_count",
        "verifier_signal_count",
        "guardian_warning_count",
    ]
    for key in list_fields:
        if not isinstance(live.get(key, []), list):
            failures.append(key + " not list")
    for key in int_fields:
        try:
            int(live.get(key, 0) or 0)
        except (TypeError, ValueError):
            failures.append(key + " not int-compatible")
    for index, signal in enumerate(live.get("memory_colony_signals", [])):
        if not isinstance(signal, dict):
            failures.append("memory_colony_signals[" + str(index) + "] not object")
            continue
        for key in ["colony_id", "label", "count", "signal_type", "safety_state"]:
            if key not in signal:
                failures.append("memory_colony_signals[" + str(index) + "]." + key + " missing")
    if failures:
        checks.fail("super_swarm_signal_fields_available", "; ".join(failures[:80]))
    else:
        checks.ok("super_swarm_signal_fields_available")


def _expect_false(section: dict[str, Any], key: str, failures: list[str], prefix: str) -> None:
    if section.get(key) is not False:
        failures.append(prefix + "." + key + " expected false")


def _validate_disabled_status(snapshot: dict[str, Any], checks: CheckSet) -> None:
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
            failures.append("communication_queen.mode changed")
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
            ]:
                if key in status:
                    _expect_false(status, key, failures, "communication_queen.status")
        else:
            failures.append("communication_queen.status not object")
        candidates = communication.get("remote_queen_candidates", [])
        if isinstance(candidates, list):
            for index, candidate in enumerate(candidates):
                if not isinstance(candidate, dict):
                    failures.append("remote_queen_candidates[" + str(index) + "] not object")
                    continue
                if candidate.get("can_assign_tasks_now") is not False:
                    failures.append("remote queen assignment enabled")
                if "untrusted" not in str(candidate.get("output_trust", "")).lower():
                    failures.append("remote queen output_trust missing untrusted marker")
        else:
            failures.append("remote_queen_candidates not list")
    else:
        failures.append("communication_queen not object")

    permissions = snapshot.get("permissions", [])
    if isinstance(permissions, list):
        for index, permission in enumerate(permissions):
            if not isinstance(permission, dict):
                failures.append("permissions[" + str(index) + "] not object")
            elif permission.get("can_execute_from_hive") is not False:
                failures.append("permissions[" + str(index) + "].can_execute_from_hive expected false")
    else:
        failures.append("permissions not list")

    signals = snapshot.get("mycelium_signals", [])
    if isinstance(signals, list):
        for index, signal in enumerate(signals):
            if not isinstance(signal, dict):
                failures.append("mycelium_signals[" + str(index) + "] not object")
            elif str(signal.get("runtime", "")).lower() != "read-only display":
                failures.append("mycelium_signals[" + str(index) + "].runtime changed")
    else:
        failures.append("mycelium_signals not list")

    if failures:
        checks.fail("disabled_state_markers_available_to_super_swarm", "; ".join(failures[:80]))
    else:
        checks.ok("disabled_state_markers_available_to_super_swarm")


def _validate_guardian_and_mind_sections(snapshot: dict[str, Any], checks: CheckSet) -> None:
    failures: list[str] = []
    guardian = snapshot.get("guardian_layer", {})
    if isinstance(guardian, dict):
        if guardian.get("visible") is not True:
            failures.append("guardian_layer.visible expected true")
        if not isinstance(guardian.get("monitors", []), list):
            failures.append("guardian_layer.monitors not list")
        blocks = [str(item).lower() for item in guardian.get("blocks", [])]
        for needle in ["trusted-memory writes", "source edits", "route mutations", "queue mutations"]:
            if needle not in blocks:
                failures.append("guardian_layer.blocks missing " + needle)
    else:
        failures.append("guardian_layer not object")

    mind = snapshot.get("mind_summary", {})
    if isinstance(mind, dict):
        if str(mind.get("safe_mode", "")).upper() != "ON":
            failures.append("mind_summary.safe_mode expected ON")
        if "no provider call" not in str(mind.get("brain_provider_state", "")).lower():
            failures.append("mind_summary.brain_provider_state missing no-provider marker")
    else:
        failures.append("mind_summary not object")

    if failures:
        checks.fail("guardian_and_mind_sections_available", "; ".join(failures))
    else:
        checks.ok("guardian_and_mind_sections_available")


def _validate_safe_empty_states(snapshot: dict[str, Any], checks: CheckSet) -> None:
    failures: list[str] = []
    grouped = snapshot.get("grouped_cells", {})
    if isinstance(grouped, dict):
        for role, records in grouped.items():
            if not isinstance(records, list):
                failures.append("grouped_cells." + str(role) + " not list")
    else:
        failures.append("grouped_cells not object")
    for key in ["cells", "queens", "workers", "memory_nests", "guardian_cards", "proposal_lanes"]:
        if not isinstance(snapshot.get(key, []), list):
            failures.append(key + " not list")
    if failures:
        checks.fail("safe_empty_states_available_to_super_swarm", "; ".join(failures))
    else:
        checks.ok("safe_empty_states_available_to_super_swarm")


def main() -> int:
    checks = CheckSet()
    _self_static_check(checks)
    source = _read_super_swarm_source(checks)
    if source:
        _check_super_swarm_source_contract(source, checks)
    builder = _load_wrapper(checks)
    if callable(builder):
        _validate_wrapper_snapshot(builder, checks)

    if checks.failures:
        print()
        print("SUPER_SWARM_HIVE_DATA_CONSUMER_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("- " + failure)
        return 1
    print()
    print("SUPER_SWARM_HIVE_DATA_CONSUMER_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
