from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_code_companion_password_gate_integration.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_password_gate_integration.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PROTECTED_APPLY_PASSWORD_GATE_INTEGRATION_SMOKE.md"
RECEIPT_ROOT = ROOT / "reports" / "code_companion_password_gate_integration"
PROTECTED_APPLY_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_protected_patch_apply.py"
TINY_DOC_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_tiny_doc_patch_smoke.py"
PASSWORD_GATE_VERIFIER = ROOT / "tools" / "verify_engel_global_password_gate.py"
PROTECTED_ACTION_VERIFIER = ROOT / "tools" / "verify_engel_protected_action_registry.py"
AUTHORITY_VERIFIER = ROOT / "tools" / "verify_authority_hierarchy.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

APPROVAL_TOKEN = "APPROVE_PRODUCT_PATCH"

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
}

REQUIRED_COMMANDS = [
    "code companion password gate integration status",
    "code companion password gate integration check",
    "code companion password gate integration smoke-refusal",
    "code companion password gate integration validate-receipt",
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
    spec = importlib.util.spec_from_file_location("engel_code_companion_password_gate_integration", MODULE)
    require(spec is not None and spec.loader is not None, "could not load password gate integration module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_password_gate_integration"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [
        MODULE,
        VERIFIER,
        REPORT,
        RECEIPT_ROOT,
        PROTECTED_APPLY_VERIFIER,
        TINY_DOC_VERIFIER,
        PASSWORD_GATE_VERIFIER,
        PROTECTED_ACTION_VERIFIER,
        AUTHORITY_VERIFIER,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_PRODUCT_PATCH",
        "REQUIRED_TOKEN_REDACTED",
        "password_collection_enabled_in_this_phase",
        "patch_application_enabled",
        "No password or approval token was stored.",
        "PASSWORD GATE UNCONFIGURED",
        "PROTECTED APPLY REFUSED",
        "verify_password_gate(password_prompt=False)",
    ]:
        require(needle in source, "module missing integration safety text: " + needle)
    for forbidden in ["getpass", "--password", "requests.", "socket.", "webbrowser.", "openai.", "anthropic.", "docker.", "wsl.exe"]:
        require(forbidden not in source.lower(), "module contains forbidden collection/runtime text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("module contains forbidden worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("module contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)


def check_runtime_status_and_receipts() -> None:
    module = load_module()
    status = module.gate_status()
    require(status["protected_apply_module_present"] is True, "protected apply module not detected")
    require(status["global_password_gate_present"] is True, "global password gate not detected")
    require(status["protected_action_registry_present"] is True, "protected action registry not detected")
    require(status["approval_token_required"] is True, "approval token must be required")
    require(status["required_approval_token"] == APPROVAL_TOKEN, "exact approval token must be advertised by status")
    require(status["password_gate_required"] is True, "password gate must be required")
    require(status["password_collection_enabled_in_this_phase"] is False, "password collection must be disabled")
    require(status["patch_application_enabled"] is False, "patch application must remain disabled")
    require(status["auto_apply"] is False, "auto apply must remain false")

    with tempfile.TemporaryDirectory() as temp_name:
        temp_root = Path(temp_name)
        check_result = module.check(temp_root, created_at="2026-05-17T00:00:00Z")
        smoke_result = module.smoke_refusal(temp_root, created_at="2026-05-17T00:00:01Z")
        for result in [check_result, smoke_result]:
            json_path = ROOT / result.json_path if not Path(result.json_path).is_absolute() else Path(result.json_path)
            if not json_path.exists():
                json_path = temp_root / Path(result.json_path).name
            require(json_path.exists(), "receipt JSON was not written")
            valid, errors = module.validate_receipt(json_path)
            require(valid, "receipt failed validation: " + "; ".join(errors))
            text = read(json_path)
            require(APPROVAL_TOKEN not in text, "receipt contains raw approval token")
            payload = json.loads(text)
            for field in [
                "patch_applied",
                "source_files_modified",
                "trusted_memory_written",
                "routes_mutated",
                "queues_mutated",
                "provider_calls_made",
                "password_or_approval_token_stored",
                "password_collection_enabled_in_this_phase",
                "patch_application_enabled",
            ]:
                require(payload[field] is False, f"{field} must remain false")
        smoke = smoke_result.payload
        cases = {case["case"]: case for case in smoke["smoke_cases"]}
        require(cases["missing_token"]["refused"] is True, "missing token must refuse")
        require(cases["wrong_token"]["refused"] is True, "wrong token must refuse")
        require(cases["correct_token"]["approval_token_verified"] is True, "correct token case must verify token")
        require(cases["correct_token"]["refused"] is True, "correct token must still refuse without password gate")
        require(smoke["password_verified"] is False, "password must not verify in refusal smoke")
        require(smoke["patch_applied"] is False, "smoke must not apply a patch")

    require(module.main(["status"]) == 0, "status command failed")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Protected Apply Password Gate Integration Smoke",
        "Password gate status",
        "PASSWORD GATE UNCONFIGURED",
        "No password or approval token was stored",
        "No source patch was applied",
        "Packaging skipped",
    ]:
        require(needle in report, "integration report missing text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require(
        "tools\\verify_engel_code_companion_password_gate_integration.py" in codex,
        "codex verifier missing password gate integration verifier",
    )


def main() -> int:
    try:
        check_files_exist()
        check_static_safety()
        check_runtime_status_and_receipts()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Code Companion password gate integration verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
