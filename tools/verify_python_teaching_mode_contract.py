from __future__ import annotations

import ast
import json
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()
CONTRACT_PATH = ROOT / "memory" / "PYTHON_TEACHING_MODE_CONTRACT_V1.json"
HELPER_PATH = ROOT / "engel_python_teaching_mode.py"
APP_PATH = ROOT / "engel_app.py"
COMPANION_PATH = ROOT / "engel_companion.py"
ROUTER_PATH = ROOT / "engel_communication_router.py"
ROUTE_MATRIX_PATH = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
COMMANDS_PATH = ROOT / "memory" / "ENGEL_COMMANDS.md"
PROJECT_INDEX_PATH = ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md"


class CheckFailure(Exception):
    pass


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(_read(path))
    except Exception as exc:
        raise CheckFailure(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CheckFailure(f"{path} must contain a JSON object")
    return data


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _require_text(text: str, needle: str, label: str) -> None:
    _require(needle in text, f"missing {label}: {needle}")


def _norm_root(value: str) -> str:
    return str(value).replace("/", "\\").rstrip("\\").lower()


def check_contract(data: dict) -> None:
    true_fields = [
        "python_teaching_mode_enabled",
        "lesson_file_write_enabled",
        "practice_script_write_enabled",
        "safe_lesson_execution_enabled",
        "py_compile_enabled",
        "verifier_execution_enabled",
        "source_edit_requires_explicit_approval",
        "trusted_memory_write_requires_explicit_approval",
        "package_install_requires_approved_dependency_route",
    ]
    false_fields = [
        "arbitrary_shell_execution_enabled",
        "autonomous_execution_enabled",
        "model_command_execution_enabled",
        "provider_network_behavior_enabled",
    ]
    for field in true_fields:
        _require(data.get(field) is True, f"{field} must be true")
    for field in false_fields:
        _require(data.get(field) is False, f"{field} must be false")

    _require(data.get("python_learning_scope") == "beginner_to_advanced", "python_learning_scope must be beginner_to_advanced")
    lesson_roots = {_norm_root(item) for item in data.get("allowed_lesson_roots", [])}
    report_roots = {_norm_root(item) for item in data.get("allowed_report_roots", [])}
    _require(
        lesson_roots
        == {
            _norm_root(r"D:\b.WorkSpace\Engel App\lessons"),
            _norm_root(r"D:\b.WorkSpace\Engel App\lessons\python"),
        },
        "allowed_lesson_roots must stay bounded to lessons and lessons\\python",
    )
    _require(report_roots == {_norm_root(r"D:\b.WorkSpace\Engel App\reports\codex_bridge")}, "allowed_report_roots must be reports\\codex_bridge only")


def check_helper_source(source: str) -> None:
    required_functions = [
        "build_python_teaching_status",
        "build_python_lesson_help",
        "sanitize_lesson_topic",
        "lesson_path_for_topic",
        "create_python_lesson",
        "create_python_practice",
        "python_learning_path",
        "create_python_learning_path_report",
        "create_python_teaching_report",
        "explain_python_file",
        "compile_python_lesson",
        "run_python_lesson",
        "python_concept",
    ]
    for name in required_functions:
        _require_text(source, f"def {name}(", "helper function")
    _require_text(source, 'APPROVAL_TOKEN = "APPROVE_RUN"', "approval token constant")
    _require_text(source, "if str(approval_token or \"\").strip() != APPROVAL_TOKEN", "approval token guard")
    _require_text(source, "_validate_lesson_path", "bounded lesson path validation")
    _require_text(source, "_unsafe_matches", "unsafe pattern detector")
    _require_text(source, "shell=False", "shell disabled execution")
    for needle in [
        "os.system",
        "subprocess",
        "Popen",
        "shell=true",
        "requests",
        "socket",
        "http://",
        "https://",
        "shutil.rmtree",
        "remove(",
        "unlink(",
        "while true",
        "start-process",
        "taskkill",
    ]:
        _require_text(source.lower(), needle.lower(), "unsafe pattern blocklist")

    tree = ast.parse(source)
    forbidden_imports = {"requests", "socket", "urllib", "http", "websocket", "threading", "multiprocessing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", 1)[0]
                _require(root_name not in forbidden_imports, f"forbidden helper import: {alias.name}")
        if isinstance(node, ast.ImportFrom):
            root_name = (node.module or "").split(".", 1)[0]
            _require(root_name not in forbidden_imports, f"forbidden helper import: {node.module}")


def check_routes_and_docs() -> None:
    app = _read(APP_PATH)
    companion = _read(COMPANION_PATH)
    router = _read(ROUTER_PATH)
    commands = _read(COMMANDS_PATH)
    project_index = _read(PROJECT_INDEX_PATH)
    matrix = _load_json(ROUTE_MATRIX_PATH)

    for command in [
        "python teaching mode status",
        "python lesson help",
        "python learning path",
        "create python learning path report",
        "create python lesson <topic>",
        "create python practice <topic>",
        "create python teaching report <topic>",
        "explain python file <path>",
        "compile python lesson <lesson_file.py>",
        "run python lesson <lesson_file.py> APPROVE_RUN",
        "python concept <topic>",
    ]:
        _require_text(commands, command, "ENGEL_COMMANDS documentation")

    _require_text(project_index, "Python Teaching Mode", "project memory index")
    _require_text(app, "handle_human_command_mode_cli", "app deterministic command handler")
    _require_text(app, "python teaching mode status", "app python teaching route")
    _require_text(app, "run python lesson ", "app lesson run route")
    _require_text(app, "APPROVE_RUN", "app lesson approval token")
    _require_text(companion, "handle_human_command_mode_cli", "companion deterministic routing")
    _require_text(router, "python teaching mode status", "router known command")
    _require_text(router, "create python lesson ", "router command prefix")
    _require_text(router, "human_command_mode", "router deterministic route target")

    entries = matrix.get("route_regression_matrix_entries", [])
    commands_by_name = {entry.get("command"): entry for entry in entries if isinstance(entry, dict)}
    required_matrix = [
        "python teaching mode status",
        "python lesson help",
        "python learning path",
        "create python learning path report",
        "create python lesson <topic>",
        "create python practice <topic>",
        "create python teaching report <topic>",
        "explain python file <path>",
        "compile python lesson <lesson_file.py>",
        "run python lesson <lesson_file.py> APPROVE_RUN",
        "python concept <topic>",
    ]
    for command in required_matrix:
        entry = commands_by_name.get(command)
        _require(isinstance(entry, dict), f"route matrix missing {command}")
        _require(entry.get("content_contract_ref") == "python_teaching_mode_contract_expectations", f"route matrix entry missing python teaching contract ref: {command}")
        _require(entry.get("autonomous_route") is False, f"route matrix must mark non-autonomous: {command}")
        _require(entry.get("model_route") is False, f"route matrix must mark non-model route: {command}")

    run_entry = commands_by_name.get("run python lesson <lesson_file.py> APPROVE_RUN", {})
    _require(run_entry.get("approval_token") == "APPROVE_RUN", "run python lesson route must require APPROVE_RUN")

    expectations = matrix.get("python_teaching_mode_contract_expectations")
    _require(isinstance(expectations, dict), "route matrix missing python_teaching_mode_contract_expectations")
    _require(expectations.get("run_command_approval_token") == "APPROVE_RUN", "route matrix run token mismatch")
    _require(expectations.get("arbitrary_shell_execution_enabled") is False, "arbitrary shell must remain disabled")
    _require(expectations.get("autonomous_execution_enabled") is False, "autonomous execution must remain disabled")
    _require(expectations.get("model_command_execution_enabled") is False, "model-command execution must remain disabled")
    _require(expectations.get("provider_network_behavior_enabled") is False, "provider/network behavior must remain disabled")


def main() -> int:
    checks = [
        ("contract_json", lambda: check_contract(_load_json(CONTRACT_PATH))),
        ("helper_source_static", lambda: check_helper_source(_read(HELPER_PATH))),
        ("routes_and_docs", check_routes_and_docs),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print(f"PASS {name}")
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print(f"FAIL {name}: unexpected error: {exc}")
    if failures:
        print("\nPython Teaching Mode contract verification FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nPython Teaching Mode contract verification PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
