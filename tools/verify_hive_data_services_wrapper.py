from __future__ import annotations

import ast
import datetime as _datetime
import importlib
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = ROOT / "engel_hive_data_services.py"
WRAPPER_MODULE = "engel_hive_data_services"
WRAPPER_FUNCTION = "build_hive_snapshot"
SOURCE_MODULE = "engel_research_office_data"
SOURCE_FUNCTION = "build_colony_hive_snapshot"


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


class FixedDateTime(_datetime.datetime):
    @classmethod
    def now(cls, tz: _datetime.tzinfo | None = None) -> "FixedDateTime":
        fixed = cls(2026, 5, 21, 12, 0, 0)
        if tz is not None:
            return cls(2026, 5, 21, 12, 0, 0, tzinfo=tz)
        return fixed


def _static_check_wrapper(checks: CheckSet) -> None:
    if not WRAPPER_PATH.exists():
        checks.fail("wrapper_file_exists", "missing " + str(WRAPPER_PATH))
        return
    source = WRAPPER_PATH.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=str(WRAPPER_PATH))
    except SyntaxError as exc:
        checks.fail("wrapper_ast_parse", str(exc))
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
    allowed_imports = {
        "__future__",
        "pathlib",
        "typing",
        "engel_research_office_data",
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
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                imported_modules.add(root)
                if root in forbidden_import_roots:
                    found.append("forbidden import " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            imported_modules.add(root)
            if root in forbidden_import_roots:
                found.append("forbidden import-from " + module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in forbidden_call_names:
                found.append("forbidden call " + func.id)
            if isinstance(func, ast.Attribute) and func.attr in forbidden_call_attrs:
                found.append("forbidden call attribute " + func.attr)

    unexpected = sorted(imported_modules - allowed_imports)
    if unexpected:
        found.append("unexpected import root(s) " + ", ".join(unexpected))

    if found:
        checks.fail("wrapper_static_no_forbidden_behavior", "; ".join(sorted(set(found))))
    else:
        checks.ok("wrapper_static_no_forbidden_behavior")


def _load_functions(checks: CheckSet) -> tuple[Any | None, Any | None, Any | None]:
    sys.dont_write_bytecode = True
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        source_module = importlib.import_module(SOURCE_MODULE)
    except Exception as exc:
        checks.fail("source_module_import", type(exc).__name__ + ": " + str(exc))
        return None, None, None
    try:
        wrapper_module = importlib.import_module(WRAPPER_MODULE)
    except Exception as exc:
        checks.fail("wrapper_module_import", type(exc).__name__ + ": " + str(exc))
        return source_module, None, None

    source_builder = getattr(source_module, SOURCE_FUNCTION, None)
    wrapper_builder = getattr(wrapper_module, WRAPPER_FUNCTION, None)
    if callable(source_builder):
        checks.ok("source_builder_callable")
    else:
        checks.fail("source_builder_callable", SOURCE_MODULE + "." + SOURCE_FUNCTION + " is not callable")
    if callable(wrapper_builder):
        checks.ok("wrapper_builder_callable")
    else:
        checks.fail("wrapper_builder_callable", WRAPPER_MODULE + "." + WRAPPER_FUNCTION + " is not callable")
    return source_module, source_builder, wrapper_builder


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


def _normalize_for_comparison(value: Any) -> Any:
    return value


def _compare_outputs(
    checks: CheckSet,
    source_module: Any,
    source_builder: Any,
    wrapper_builder: Any,
) -> None:
    original_datetime = source_module.datetime.datetime
    before = _collect_file_state(ROOT)
    try:
        source_module.datetime.datetime = FixedDateTime
        source_snapshot = source_builder(Path(ROOT))
        wrapper_snapshot = wrapper_builder(Path(ROOT))
    except Exception as exc:
        checks.fail("wrapper_and_source_call", type(exc).__name__ + ": " + str(exc))
        return
    finally:
        source_module.datetime.datetime = original_datetime
    after = _collect_file_state(ROOT)

    checks.ok("wrapper_and_source_call")

    if isinstance(wrapper_snapshot, dict):
        checks.ok("wrapper_snapshot_is_dict")
    else:
        checks.fail("wrapper_snapshot_is_dict", "wrapper returned " + type(wrapper_snapshot).__name__)

    if _normalize_for_comparison(wrapper_snapshot) == _normalize_for_comparison(source_snapshot):
        checks.ok("wrapper_output_equals_original")
    else:
        checks.fail("wrapper_output_equals_original", "wrapper snapshot differs from source builder snapshot")

    if before == after:
        checks.ok("wrapper_call_no_file_mutation")
    else:
        changed = sorted(
            path for path in set(before) | set(after) if before.get(path) != after.get(path)
        )
        checks.fail("wrapper_call_no_file_mutation", "; ".join(changed[:40]))

    _validate_consumer_keys(wrapper_snapshot, checks)
    _validate_disabled_markers(wrapper_snapshot, checks)
    _validate_safe_empty_states(wrapper_snapshot, checks)


def _validate_consumer_keys(snapshot: Any, checks: CheckSet) -> None:
    if not isinstance(snapshot, dict):
        checks.fail("super_swarm_consumer_keys_preserved", "snapshot is not a dict")
        return
    required = [
        "cells",
        "grouped_cells",
        "queens",
        "workers",
        "permissions",
        "super_swarm_hive_live",
        "communication_queen",
        "guardian_layer",
        "mind_summary",
        "memory_nests",
        "guardian_cards",
        "proposal_lanes",
        "mycelium_signals",
    ]
    missing = [key for key in required if key not in snapshot]
    if missing:
        checks.fail("super_swarm_consumer_keys_preserved", "missing " + ", ".join(missing))
    else:
        checks.ok("super_swarm_consumer_keys_preserved")


def _expect_false(section: dict[str, Any], key: str, failures: list[str], prefix: str) -> None:
    if section.get(key) is not False:
        failures.append(prefix + "." + key + " expected false")


def _validate_disabled_markers(snapshot: Any, checks: CheckSet) -> None:
    failures: list[str] = []
    if not isinstance(snapshot, dict):
        checks.fail("disabled_state_markers_preserved", "snapshot is not a dict")
        return

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
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    failures.append("remote queen candidate not object")
                    continue
                if candidate.get("can_assign_tasks_now") is not False:
                    failures.append("remote queen can_assign_tasks_now changed")
                if "untrusted" not in str(candidate.get("output_trust", "")).lower():
                    failures.append("remote queen output_trust missing untrusted marker")
        else:
            failures.append("communication_queen.remote_queen_candidates not list")
    else:
        failures.append("communication_queen not object")

    permissions = snapshot.get("permissions", [])
    if isinstance(permissions, list):
        for permission in permissions:
            if not isinstance(permission, dict):
                failures.append("permission row not object")
                continue
            if permission.get("can_execute_from_hive") is not False:
                failures.append("permission can_execute_from_hive changed")
    else:
        failures.append("permissions not list")

    if failures:
        checks.fail("disabled_state_markers_preserved", "; ".join(failures[:80]))
    else:
        checks.ok("disabled_state_markers_preserved")


def _validate_safe_empty_states(snapshot: Any, checks: CheckSet) -> None:
    failures: list[str] = []
    if not isinstance(snapshot, dict):
        checks.fail("safe_empty_states_preserved", "snapshot is not a dict")
        return
    live = snapshot.get("super_swarm_hive_live", {})
    if isinstance(live, dict):
        if not isinstance(live.get("recent_local_paths", []), list):
            failures.append("recent_local_paths not list")
        if not isinstance(live.get("memory_colony_signals", []), list):
            failures.append("memory_colony_signals not list")
        if not isinstance(live.get("local_signal_counts", {}), dict):
            failures.append("local_signal_counts not dict")
    grouped = snapshot.get("grouped_cells", {})
    if isinstance(grouped, dict):
        for role, records in grouped.items():
            if not isinstance(records, list):
                failures.append("grouped_cells." + str(role) + " not list")
    else:
        failures.append("grouped_cells not object")
    if failures:
        checks.fail("safe_empty_states_preserved", "; ".join(failures))
    else:
        checks.ok("safe_empty_states_preserved")


def main() -> int:
    checks = CheckSet()
    _static_check_wrapper(checks)
    source_module, source_builder, wrapper_builder = _load_functions(checks)
    if source_module is not None and callable(source_builder) and callable(wrapper_builder):
        _compare_outputs(checks, source_module, source_builder, wrapper_builder)

    if checks.failures:
        print()
        print("HIVE_DATA_SERVICES_WRAPPER_VERIFICATION_FAIL")
        return 1
    print()
    print("HIVE_DATA_SERVICES_WRAPPER_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
