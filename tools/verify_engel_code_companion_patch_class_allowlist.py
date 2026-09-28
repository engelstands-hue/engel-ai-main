from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_code_companion_patch_class_allowlist.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_class_allowlist.py"
PROTECTED_APPLY = ROOT / "engel_code_companion_protected_patch_apply.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_CLASS_ALLOWLIST_V1.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "subprocess",
    "threading",
    "multiprocessing",
    "asyncio",
    "http",
    "ftplib",
    "smtplib",
    "openai",
    "anthropic",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "Popen",
    "system",
    "startfile",
    "run",
    "call",
    "check_call",
    "check_output",
    "write_text",
    "write_bytes",
    "mkdir",
    "unlink",
    "rename",
}

REQUIRED_COMMANDS = [
    "code companion patch class allowlist status",
    "code companion patch class allowlist classify",
    "code companion patch class allowlist validate-plan",
    "code companion patch class allowlist list-classes",
]

REQUIRED_CLASSES = [
    "docs_only",
    "report_only_tools",
    "verifier_only",
    "isolated_code_companion_module",
    "flutter_ui_only",
]

REQUIRED_DENIED_CLASSES = [
    "core_runtime",
    "prompts",
    "trusted_memory",
    "route_metadata",
    "live_packaging",
    "staging_packaging",
    "secrets_config",
    "startup_autorun",
    "provider_network",
    "password_gate_core",
    "approval_token_core",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_code_companion_patch_class_allowlist", MODULE)
    require(spec is not None and spec.loader is not None, "could not load allowlist module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_patch_class_allowlist"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [MODULE, VERIFIER, PROTECTED_APPLY, REPORT, COMMANDS, CODEX_VERIFY]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))


def check_static_source_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        '"default_policy": "deny"',
        '"auto_apply_allowed": False',
        '"requires_human_review": True',
        '"requires_approval_token": True',
        '"requires_password_gate": True',
        '"requires_verifier_pass": True',
        "path_traversal_denied",
        "absolute_paths_outside_repo_denied",
        "provider_api_cloud_browser_denied",
        "wsl_hermes_docker_denied",
    ] + REQUIRED_CLASSES + REQUIRED_DENIED_CLASSES:
        require(needle in source, "allowlist source missing policy text: " + needle)
    for forbidden in ["requests.", "socket.", "webbrowser.", "openai.", "anthropic.", "docker.", "wsl.exe"]:
        require(forbidden not in source.lower(), "allowlist source contains forbidden runtime text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("allowlist contains forbidden background-worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("allowlist contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, "allowlist contains forbidden call: " + name)


def assert_classification(module, path: str, allowed: bool, patch_class: str | None = None, denied_class: str | None = None) -> dict:
    result = module.classify_path(path)
    require(result["allowed"] is allowed, f"classification allowed mismatch for {path}: {result}")
    if patch_class is not None:
        require(result["patch_class"] == patch_class, f"class mismatch for {path}: {result}")
    if denied_class is not None:
        require(result["denied_class"] == denied_class, f"denied class mismatch for {path}: {result}")
    require(result["required_constraints"] or not allowed, "allowed path must include constraints")
    return result


def check_runtime_policy() -> None:
    module = load_module()
    policy = module.POLICY
    require(policy["default_policy"] == "deny", "default policy must be deny")
    require(policy["auto_apply_allowed"] is False, "auto apply must remain false")
    require(policy["requires_human_review"] is True, "human review must be required")
    require(policy["requires_approval_token"] is True, "approval token must be required")
    require(policy["requires_password_gate"] is True, "password gate must be required")
    require(policy["requires_verifier_pass"] is True, "verifier pass must be required")
    for patch_class in REQUIRED_CLASSES:
        require(patch_class in policy["allowed_classes"], "missing allowed class: " + patch_class)
    for denied_class in REQUIRED_DENIED_CLASSES:
        require(denied_class in policy["denied_classes"], "missing denied class: " + denied_class)

    assert_classification(module, "reports\\codex_bridge\\example.md", True, "docs_only")
    assert_classification(module, "tools\\verify_example.py", True, "verifier_only")
    assert_classification(module, "tools\\example_report.py", True, "report_only_tools")
    assert_classification(module, "tools\\example_status.py", True, "report_only_tools")
    assert_classification(module, "engel_code_companion_example.py", True, "isolated_code_companion_module")
    assert_classification(module, "mobile\\engel_remote_worker\\lib\\main.dart", True, "flutter_ui_only")
    assert_classification(module, "mobile\\engel_remote_worker\\test\\widget_test.dart", True, "flutter_ui_only")

    assert_classification(module, "prompts\\ENGEL_SYSTEM.md", False, denied_class="prompts")
    assert_classification(module, "memory\\ENGEL_COMMANDS.md", False, denied_class="trusted_memory")
    assert_classification(module, "scripts\\codex_verify.ps1", False, denied_class="startup_autorun")
    assert_classification(module, "live\\app\\Engel.exe", False, denied_class="live_packaging")
    assert_classification(module, "staging\\app\\Engel.exe", False, denied_class="staging_packaging")
    assert_classification(module, "routes\\route_metadata.json", False, denied_class="route_metadata")
    assert_classification(module, "config.json", False, denied_class="secrets_config")
    assert_classification(module, "engel_app.py", False, denied_class="core_runtime")
    traversal = module.classify_path("reports\\..\\memory\\ENGEL_COMMANDS.md")
    require(traversal["allowed"] is False and "traversal" in traversal["reason"], "path traversal must be denied")
    outside = module.classify_path("C:\\Windows\\notepad.exe")
    require(outside["allowed"] is False and "outside repo" in outside["reason"], "absolute outside path must be denied")


def check_plan_validation() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory(dir=ROOT / "reports" / "codex_bridge") as temp_name:
        temp_root = Path(temp_name)
        allowed_plan = temp_root / "allowlist_allowed_plan.json"
        allowed_plan.write_text(
            json.dumps({"target_files": ["reports\\codex_bridge\\example.md", "tools\\verify_example.py"]}),
            encoding="utf-8",
        )
        allowed_result = module.validate_plan(allowed_plan)
        require(allowed_result["valid"] is True, "allowed plan should validate: " + str(allowed_result))
        require(allowed_result["target_count"] == 2, "allowed plan target count mismatch")

        denied_plan = temp_root / "allowlist_denied_plan.json"
        denied_plan.write_text(
            json.dumps({"target_files": ["prompts\\ENGEL_SYSTEM.md", "engel_app.py"]}),
            encoding="utf-8",
        )
        denied_result = module.validate_plan(denied_plan)
        require(denied_result["valid"] is False, "denied plan should fail")
        require(len(denied_result["denied_targets"]) == 2, "denied plan should list denied targets")


def check_protected_apply_consults_policy() -> None:
    source = read(PROTECTED_APPLY)
    for needle in [
        "import engel_code_companion_patch_class_allowlist as patch_class_allowlist",
        "patch_class_allowlist.classify_path",
        "target denied by Phase 11 patch class allowlist",
        '"patch_class"',
        '"policy_allowed"',
    ]:
        require(needle in source, "protected apply does not consult allowlist: " + needle)


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Patch Class Allowlist V1",
        "default policy is deny",
        "docs_only",
        "report_only_tools",
        "verifier_only",
        "isolated_code_companion_module",
        "flutter_ui_only",
        "Protected paths remain denied",
        "No source patches were applied",
        "Packaging skipped",
    ]:
        require(needle in report, "allowlist report missing text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex_verify = read(CODEX_VERIFY)
    require(
        "tools\\verify_engel_code_companion_patch_class_allowlist.py" in codex_verify,
        "codex verifier does not include allowlist verifier",
    )


def main() -> int:
    try:
        check_files_exist()
        check_static_source_safety()
        check_runtime_policy()
        check_plan_validation()
        check_protected_apply_consults_policy()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Code Companion patch class allowlist verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
