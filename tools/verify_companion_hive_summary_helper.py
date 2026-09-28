from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "engel_hive_data_services.py"
SERVICE_MODULE = "engel_hive_data_services"
HELPER_NAME = "build_companion_hive_summary"

PROTECTED_PATHS = [
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
    ROOT / "memory" / "LIVING_SYSTEMS_INDEX_V1.md",
    ROOT / "memory" / "NEXT_WORK_BATON_V1.md",
    ROOT / "engel_hive_data_services.py",
]

REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "hive_available": bool,
    "colony_count": int,
    "queen_count": int,
    "worker_count": int,
    "communication_queen_status": str,
    "guardian_status": str,
    "mind_summary_safe_mode": bool,
    "mobile_status": str,
    "receipts_available": bool,
    "disabled_runtime_flags": list,
    "summary_generated_from": str,
    "no_fake_live_data": bool,
    "source_trust": str,
}

OPTIONAL_FIELDS: dict[str, type | tuple[type, ...]] = {
    "remote_queen_status": str,
    "provider_api_enabled": bool,
    "internet_enabled": bool,
    "background_workers_enabled": bool,
    "last_error": (str, type(None)),
    "empty_state_reason": (str, type(None)),
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


def _collect_file_state(paths: list[Path]) -> dict[str, tuple[int, int] | None]:
    state: dict[str, tuple[int, int] | None] = {}
    for path in paths:
        try:
            if path.is_file():
                stat = path.stat()
                state[str(path)] = (stat.st_mtime_ns, stat.st_size)
            else:
                state[str(path)] = None
        except OSError:
            state[str(path)] = None
    return state


def _static_check_service(checks: CheckSet) -> None:
    if not SERVICE_PATH.exists():
        checks.fail("service_file_exists", "missing " + str(SERVICE_PATH))
        return
    source = SERVICE_PATH.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=str(SERVICE_PATH))
    except SyntaxError as exc:
        checks.fail("service_ast_parse", str(exc))
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
    helper_calls_snapshot = False
    snapshot_mutation: list[str] = []

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
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets: list[ast.AST] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            else:
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                    if target.value.id == "snapshot":
                        snapshot_mutation.append("subscript assignment to snapshot")

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == HELPER_NAME:
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    if child.func.id == "build_hive_snapshot":
                        helper_calls_snapshot = True

    unexpected = sorted(imported_modules - allowed_imports)
    if unexpected:
        found.append("unexpected import root(s) " + ", ".join(unexpected))
    if snapshot_mutation:
        found.extend(snapshot_mutation)

    if found:
        checks.fail("service_static_no_forbidden_behavior", "; ".join(sorted(set(found))))
    else:
        checks.ok("service_static_no_forbidden_behavior")

    if helper_calls_snapshot:
        checks.ok("helper_calls_build_hive_snapshot")
    else:
        checks.fail("helper_calls_build_hive_snapshot", HELPER_NAME + " must call build_hive_snapshot")


def _load_helper(checks: CheckSet) -> Any | None:
    sys.dont_write_bytecode = True
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        module = importlib.import_module(SERVICE_MODULE)
    except Exception as exc:
        checks.fail("service_module_import", type(exc).__name__ + ": " + str(exc))
        return None
    helper = getattr(module, HELPER_NAME, None)
    if callable(helper):
        checks.ok("helper_callable")
        return helper
    checks.fail("helper_callable", SERVICE_MODULE + "." + HELPER_NAME + " is not callable")
    return None


def _validate_summary(summary: Any, checks: CheckSet) -> None:
    if not isinstance(summary, dict):
        checks.fail("summary_is_dict", "got " + type(summary).__name__)
        return
    checks.ok("summary_is_dict")

    missing = [field for field in REQUIRED_FIELDS if field not in summary]
    if missing:
        checks.fail("summary_required_fields_exist", "missing " + ", ".join(missing))
    else:
        checks.ok("summary_required_fields_exist")

    bad_types: list[str] = []
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in summary:
            continue
        value = summary[field]
        if expected_type is int:
            if not isinstance(value, int) or isinstance(value, bool):
                bad_types.append(field + " expected int")
        elif not isinstance(value, expected_type):
            bad_types.append(field + " expected " + str(expected_type))
    for field, expected_type in OPTIONAL_FIELDS.items():
        if field in summary and not isinstance(summary[field], expected_type):
            bad_types.append(field + " expected " + str(expected_type))
    if bad_types:
        checks.fail("summary_field_types", "; ".join(bad_types))
    else:
        checks.ok("summary_field_types")

    flag_types = [flag for flag in summary.get("disabled_runtime_flags", []) if not isinstance(flag, str)]
    if flag_types:
        checks.fail("disabled_runtime_flags_are_strings", "non-string flags found")
    else:
        checks.ok("disabled_runtime_flags_are_strings")

    if summary.get("summary_generated_from") == "build_hive_snapshot":
        checks.ok("summary_generated_from_literal")
    else:
        checks.fail("summary_generated_from_literal", "expected build_hive_snapshot")

    if summary.get("no_fake_live_data") is True:
        checks.ok("no_fake_live_data_true")
    else:
        checks.fail("no_fake_live_data_true", "expected true")

    if summary.get("source_trust") == "local_readonly_snapshot":
        checks.ok("source_trust_literal")
    else:
        checks.fail("source_trust_literal", "expected local_readonly_snapshot")


def _call_helper_no_mutation(helper: Any, checks: CheckSet) -> None:
    before = _collect_file_state(PROTECTED_PATHS)
    try:
        summary = helper(ROOT)
    except Exception as exc:
        checks.fail("helper_call_workspace_root", type(exc).__name__ + ": " + str(exc))
        return
    after = _collect_file_state(PROTECTED_PATHS)
    checks.ok("helper_call_workspace_root")
    if before == after:
        checks.ok("helper_call_no_protected_file_mutation")
    else:
        changed = [path for path in before if before.get(path) != after.get(path)]
        checks.fail("helper_call_no_protected_file_mutation", "; ".join(changed))
    _validate_summary(summary, checks)


def _run_verifier_module(module_name: str, path: Path, checks: CheckSet) -> None:
    if not path.exists():
        checks.fail(module_name, "missing " + str(path))
        return
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            checks.fail(module_name, "could not load module spec")
            return
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.main()
    except Exception as exc:
        checks.fail(module_name, type(exc).__name__ + ": " + str(exc))
        return
    if result == 0:
        checks.ok(module_name)
    else:
        checks.fail(module_name, "returned " + str(result))


def _run_compatible_verifiers(checks: CheckSet) -> None:
    verifiers = [
        ("verify_hive_data_services_wrapper", ROOT / "tools" / "verify_hive_data_services_wrapper.py"),
        ("verify_hive_snapshot_schema", ROOT / "tools" / "verify_hive_snapshot_schema.py"),
        ("verify_super_swarm_hive_data_consumer", ROOT / "tools" / "verify_super_swarm_hive_data_consumer.py"),
    ]
    for module_name, path in verifiers:
        _run_verifier_module(module_name, path, checks)


def main() -> int:
    checks = CheckSet()
    _static_check_service(checks)
    helper = _load_helper(checks)
    if helper is not None:
        _call_helper_no_mutation(helper, checks)
    _run_compatible_verifiers(checks)

    if checks.failures:
        print()
        print("COMPANION_HIVE_SUMMARY_HELPER_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("- " + failure)
        return 1
    print()
    print("COMPANION_HIVE_SUMMARY_HELPER_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
