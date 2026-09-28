from __future__ import annotations

import ast
import json
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
CONTRACT_PATH = ROOT / "memory" / "HUMAN_COMMAND_MODE_CONTRACT_V1.json"
HELPER_PATH = ROOT / "engel_human_command_mode.py"
SHARED_HELPER_PATH = ROOT / "engel_human_command_shared.py"
APP_PATH = ROOT / "engel_app.py"
COMPANION_PATH = ROOT / "engel_companion.py"
ROUTER_PATH = ROOT / "engel_communication_router.py"
ROUTE_MATRIX_PATH = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
COMMANDS_PATH = ROOT / "memory" / "ENGEL_COMMANDS.md"
CHECKLIST_PATH = ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md"
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
    return value.replace("/", "\\").rstrip("\\").lower()


def _root_child(*parts: str) -> str:
    return str(ROOT.joinpath(*parts))


def check_contract(data: dict) -> None:
    true_fields = [
        "human_command_mode_enabled",
        "direct_human_file_read_enabled",
        "direct_human_folder_research_enabled",
        "direct_human_file_write_enabled",
        "direct_human_report_write_enabled",
        "direct_human_local_install_copy_enabled",
        "direct_human_model_file_install_enabled",
        "human_approved_dependency_install_enabled",
        "dependency_install_requires_approval_token",
        "dependency_install_target_environment_required",
        "dependency_install_report_required",
        "dependency_install_verifier_run_required",
        "dependency_install_allows_network_only_after_explicit_approval",
        "direct_human_source_edit_requires_explicit_approval",
        "trusted_memory_write_requires_explicit_approval",
        "queue_mutation_requires_explicit_approval",
        "route_mutation_requires_explicit_approval",
        "package_install_requires_separate_approval",
        "network_download_requires_separate_approval",
        "safe_local_install_copy_enabled",
        "package_system_install_requires_approval",
    ]
    false_fields = [
        "autonomous_loop_enabled",
        "background_worker_enabled",
        "model_command_execution_enabled",
        "model_trusted_memory_write_enabled",
        "provider_fallback_enabled",
        "remote_queen_runtime_enabled",
        "silent_dependency_install_enabled",
        "model_triggered_dependency_install_enabled",
        "autonomous_dependency_install_enabled",
        "system_installer_execution_enabled",
        "arbitrary_shell_execution_enabled",
        "powershell_execution_enabled",
        "subprocess_execution_enabled",
        "pip_install_route_enabled",
        "npm_install_route_enabled",
        "browser_download_route_enabled",
    ]
    for field in true_fields:
        _require(data.get(field) is True, f"{field} must be true")
    for field in false_fields:
        _require(data.get(field) is False, f"{field} must be false")
    _require(data.get("dependency_install_approval_token") == "APPROVE_INSTALL", "approval token must be APPROVE_INSTALL")

    allowed = {_norm_root(item) for item in data.get("allowed_write_roots", [])}
    expected_allowed = {
        _norm_root(_root_child("reports")),
        _norm_root(_root_child("reports", "codex_bridge")),
        _norm_root(_root_child("reports", "app")),
        _norm_root(_root_child("reports", "security")),
        _norm_root(_root_child("reports", "colony")),
        _norm_root(_root_child("reports", "proposal_autonomy")),
        _norm_root(_root_child("assets")),
        _norm_root(_root_child("models")),
    }
    _require(allowed == expected_allowed, "allowed_write_roots must stay bounded to reports/assets/models")
    conditional = {_norm_root(item) for item in data.get("conditional_write_roots", [])}
    _require(conditional == {_norm_root(_root_child("memory"))}, "conditional_write_roots must be memory only")
    blocked = {_norm_root(item) for item in data.get("blocked_roots", [])}
    for required in [
        r"C:\Windows",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\Users",
        r"\\",
        "http://",
        "https://",
    ]:
        _require(_norm_root(required) in blocked, f"blocked_roots missing {required}")


def check_helper_source(source: str) -> None:
    required_functions = [
        "normalize_user_path",
        "is_url_like",
        "is_unc_path",
        "is_blocked_root",
        "is_under_root",
        "is_allowed_read_path",
        "is_allowed_write_path",
        "is_allowed_model_path",
        "validate_read_file",
        "validate_read_folder",
        "validate_write_path",
        "validate_copy_install",
        "validate_dependency_package_name",
        "summarize_file_bounded",
        "summarize_folder_bounded",
        "write_report_safely",
        "write_file_safely",
        "copy_local_file_safely",
        "install_model_file_safely",
        "build_human_command_mode_status",
        "build_guarded_write_status",
        "build_dependency_install_plan",
        "build_package_install_requires_approval_message",
        "run_approved_dependency_install",
    ]
    for name in required_functions:
        _require_text(source, "def " + name + "(", "helper function")
    for needle in ["is_url_like", "is_unc_path", "FOLDER_SUMMARY_MAX_FILES = 200", "validate_dependency_package_name"]:
        _require_text(source, needle, "helper guard")
    for needle in [";", "&", "|", "`", "git+", "--", "-r"]:
        _require_text(source, needle, "dependency injection rejection marker")
    _require_text(source, "shutil.copy2", "local copy helper")
    _require_text(source, "Source must be an existing local file", "existing local source validation")
    _require_text(source, "is_allowed_write_path", "approved destination validation")

    tree = ast.parse(source)
    forbidden_imports = {
        "openai",
        "anthropic",
        "requests",
        "socket",
        "websocket",
        "threading",
        "multiprocessing",
        "watchdog",
        "schedule",
        "urllib",
        "http",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", 1)[0]
                _require(root_name not in forbidden_imports, f"forbidden helper import: {alias.name}")
        if isinstance(node, ast.ImportFrom):
            root_name = (node.module or "").split(".", 1)[0]
            _require(root_name not in forbidden_imports, f"forbidden helper import: {node.module}")

    function_stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            function_stack.append(node.name)
            self.generic_visit(node)
            function_stack.pop()

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                if alias.name == "subprocess":
                    _require(function_stack and function_stack[-1] == "run_approved_dependency_install", "subprocess import allowed only in run_approved_dependency_install")
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            current = function_stack[-1] if function_stack else ""
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {"system", "Popen"}:
                    raise CheckFailure(f"forbidden process call: {node.func.attr}")
                if node.func.attr == "run":
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                        _require(current == "run_approved_dependency_install", "subprocess.run allowed only in run_approved_dependency_install")
                        shell_kw = next((kw for kw in node.keywords if kw.arg == "shell"), None)
                        _require(shell_kw is not None and isinstance(shell_kw.value, ast.Constant) and shell_kw.value.value is False, "subprocess.run must use shell=False")
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                    _require(keyword.value.value is not True, "shell=True is forbidden")
            self.generic_visit(node)

    Visitor().visit(tree)
    _require("command = [sys.executable, \"-m\", \"pip\", \"install\", package]" in source, "approved dependency command must be structured sys.executable pip install list")


def check_shared_helper_source(source: str) -> None:
    _require_text(source, "HUMAN_COMMAND_CONTRACT_VERIFIER_REL", "shared verifier path constant")
    _require_text(source, "CODEX_VERIFY_SCRIPT_REL", "shared codex verify path constant")
    _require_text(source, "POST_INSTALL_VERIFIER_COMMANDS", "shared verifier commands")
    _require_text(source, "def human_command_now_stamp(", "shared report timestamp helper")
    _require_text(source, "def post_install_verifier_lines(", "shared verifier lines helper")
    _require_text(source, "def post_install_verifier_sentence(", "shared verifier sentence helper")


def check_dependency_validation_runtime() -> None:
    sys.path.insert(0, str(ROOT))
    import engel_human_command_mode as hcm

    allowed = ["llama-cpp-python", "llama-cpp-python==0.3.22", "packaging"]
    blocked = [
        "requests;whoami",
        "requests&&whoami",
        "requests|whoami",
        "requests > out.txt",
        "`whoami`",
        "'requests'",
        "https://example.invalid/pkg.whl",
        "git+https://example.invalid/repo",
        "-r",
        "-r requirements.txt",
        "--index-url",
        r"C:\tmp\package.whl",
    ]
    for package in allowed:
        result = hcm.validate_dependency_package_name(package)
        _require(result.ok, f"expected package validation PASS: {package}")
    for package in blocked:
        result = hcm.validate_dependency_package_name(package)
        _require(not result.ok, f"expected package validation BLOCKED: {package}")


def check_routes_and_docs() -> None:
    app = _read(APP_PATH)
    companion = _read(COMPANION_PATH)
    router = _read(ROUTER_PATH)
    commands = _read(COMMANDS_PATH)
    checklist = _read(CHECKLIST_PATH)
    project_index = _read(PROJECT_INDEX_PATH)
    matrix = _load_json(ROUTE_MATRIX_PATH)

    for command in [
        "human command mode status",
        "guarded write status",
        "human command help",
        "research file <path>",
        "research folder <path>",
        "install local file <source_path> to <destination_folder>",
        "install model file <source_path>",
        "dependency install plan <package> for <reason>",
        "install dependency <package> for <reason> APPROVE_INSTALL",
        "request package install <package> for <reason>",
    ]:
        _require_text(commands, command, "ENGEL_COMMANDS documentation")

    _require_text(checklist, "verify_human_command_mode_contract.py", "standard verifier checklist")
    _require_text(project_index, "Human Command Mode", "project memory index")
    _require_text(app, "handle_human_command_mode_cli", "app human command handler")
    _require_text(app, "APPROVE_INSTALL", "app approval token")
    _require_text(app, "install package ", "blocked package install route")
    _require_text(companion, "handle_human_command_mode_cli", "companion deterministic route")
    _require_text(router, "human_command_candidate", "router human command candidate")
    _require_text(router, "human_command_mode", "router human command route target")
    _require_text(router, "No provider, model runtime, or model-command execution was called", "router no-model response")

    entries = matrix.get("route_regression_matrix_entries", [])
    commands_by_name = {entry.get("command"): entry for entry in entries if isinstance(entry, dict)}
    required_matrix = [
        "human command mode status",
        "guarded write status",
        "human command help",
        "research file <path>",
        "research folder <path>",
        "research folder <path> to report <name.md>",
        "install local file <source_path> to <destination_folder>",
        "install model file <source_path>",
        "dependency install plan <package> for <reason>",
        "install dependency <package> for <reason> APPROVE_INSTALL",
        "install package <package_name>",
        "request package install <package_name> for <reason>",
    ]
    for command in required_matrix:
        entry = commands_by_name.get(command)
        _require(isinstance(entry, dict), f"route matrix missing {command}")
        _require(entry.get("content_contract_ref") == "human_command_mode_contract_expectations", f"route matrix entry missing human contract ref: {command}")
        _require(entry.get("autonomous_route") is False, f"route matrix must mark non-autonomous: {command}")
        _require(entry.get("model_route") is False, f"route matrix must mark non-model route: {command}")

    expectations = matrix.get("human_command_mode_contract_expectations")
    _require(isinstance(expectations, dict), "route matrix missing human_command_mode_contract_expectations")
    _require(expectations.get("dependency_install_approval_token") == "APPROVE_INSTALL", "route matrix approval token mismatch")
    _require(expectations.get("dependency_install_report_required") is not False, "dependency install report must be required")


def main() -> int:
    checks = [
        ("contract_json", lambda: check_contract(_load_json(CONTRACT_PATH))),
        ("helper_source_static", lambda: check_helper_source(_read(HELPER_PATH))),
        ("shared_helper_source_static", lambda: check_shared_helper_source(_read(SHARED_HELPER_PATH))),
        ("dependency_package_validation", check_dependency_validation_runtime),
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
        print("\nHuman Command Mode contract verification FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nHuman Command Mode contract verification PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
