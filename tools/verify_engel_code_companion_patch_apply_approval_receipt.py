from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_code_companion_patch_apply_approval_receipt.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_apply_approval_receipt.py"
PHASE1_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_fix_candidate_intake.py"
PHASE2_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_plan_preview.py"
PHASE3_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_bundle_draft.py"
PHASE4_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_application_gate.py"
PHASE5_MODULE = ROOT / "engel_code_companion_patch_apply_dry_run.py"
PHASE5_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_apply_dry_run.py"
PROTECTED_ACTION_VERIFIER = ROOT / "tools" / "verify_engel_protected_action_registry.py"
PASSWORD_GATE_VERIFIER = ROOT / "tools" / "verify_engel_global_password_gate.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_APPLY_APPROVAL_RECEIPT_V1.md"
APPROVAL_ROOT = ROOT / "reports" / "code_companion_patch_apply_approvals"
APPROVAL_EXAMPLES = APPROVAL_ROOT / "examples"
APPROVAL_RECEIPTS = APPROVAL_ROOT / "receipts"
EXAMPLE_RECEIPT = APPROVAL_EXAMPLES / "patch_apply_approval_receipt_example.json"
DRY_RUN_ROOT = ROOT / "reports" / "code_companion_patch_apply_dry_runs"
DRY_RUN_EXAMPLES = DRY_RUN_ROOT / "examples"
EXAMPLE_DRY_RUN = DRY_RUN_EXAMPLES / "patch_apply_dry_run_example.json"
BUNDLE_EXAMPLE = ROOT / "reports" / "code_companion_patch_bundles" / "examples" / "patch_bundle_draft_example.json"
GATE_EXAMPLE = ROOT / "reports" / "code_companion_patch_application_gates" / "examples" / "patch_application_gate_example.json"
PLAN_EXAMPLE = ROOT / "reports" / "code_companion_patch_plans" / "examples" / "patch_plan_preview_example.json"
FIX_CANDIDATE_EXAMPLE = ROOT / "reports" / "code_companion_fix_candidates" / "examples" / "fix_candidate_example.json"

FINAL_DECISION = "PROTECTED PATCH APPROVAL RECEIPT ONLY \u2014 NOT APPROVED \u2014 NOT APPLIED"

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

REQUIRED_BLOCKED_ACTIONS = [
    "approve_without_human_review",
    "collect_or_store_password",
    "collect_or_store_approval_token",
    "apply_patch_without_approval",
    "edit_source_without_approval",
    "execute_commands_from_dry_run",
    "mutate_routes",
    "mutate_queue",
    "write_trusted_memory",
    "auto_apply",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
]

REQUIRED_COMMANDS = [
    "code companion patch approval status",
    "code companion patch approval list",
    "code companion patch approval validate-dry-run",
    "code companion patch approval receipt",
    "code companion patch approval requirements",
    "code companion patch approval show",
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
    spec = importlib.util.spec_from_file_location("engel_code_companion_patch_apply_approval_receipt", MODULE)
    require(spec is not None and spec.loader is not None, "could not load patch apply approval receipt module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_patch_apply_approval_receipt"] = module
    spec.loader.exec_module(module)
    return module


def check_phase5_present() -> None:
    for path in [
        PHASE1_VERIFIER,
        PHASE2_VERIFIER,
        PHASE3_VERIFIER,
        PHASE4_VERIFIER,
        PHASE5_MODULE,
        PHASE5_VERIFIER,
        EXAMPLE_DRY_RUN,
    ]:
        require(path.exists(), "Phase 6 dependency missing required path: " + str(path.relative_to(ROOT)))


def check_files_and_folders() -> None:
    for path in [MODULE, VERIFIER, REPORT, APPROVAL_ROOT, APPROVAL_EXAMPLES, APPROVAL_RECEIPTS, EXAMPLE_RECEIPT]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    payload = json.loads(read(EXAMPLE_RECEIPT))
    require(payload.get("status") == "approval_receipt_review_only", "example receipt status mismatch")
    require(payload.get("requires_review") is True, "example receipt must require review")
    require(payload.get("safe_to_auto_apply") is False, "example receipt must not auto-apply")
    require(payload.get("patch_applied") is False, "example receipt must not be applied")
    require(payload.get("source_files_modified") is False, "example receipt must not modify source")
    require(payload.get("application_enabled_in_this_phase") is False, "example receipt must keep application disabled")
    require(payload.get("approval_collection_enabled") is False, "example receipt must not collect approval")
    require(payload.get("password_collection_enabled") is False, "example receipt must not collect password")
    require(payload.get("human_review_required") is True, "example receipt must require human review")
    require(payload.get("human_review_completed") is False, "example receipt must not mark human review completed")
    require(payload.get("approval_token_required") is True, "example receipt must require approval token")
    require(payload.get("approval_token_present") is False, "example receipt must not contain approval token")
    require(payload.get("approval_token_verified") is False, "example receipt must not verify approval token")
    require(payload.get("password_gate_required") is True, "example receipt must require password gate")
    require(payload.get("password_verified") is False, "example receipt must not verify password")
    require(payload.get("verifier_pass_required") is True, "example receipt must require verifier pass")
    require(payload.get("verifier_pass_recorded_for_apply") is False, "example receipt must not record verifier pass for apply")
    require(payload.get("apply_authorized") is False, "example receipt must not authorize apply")
    require(payload.get("final_decision") == FINAL_DECISION, "example receipt final decision mismatch")
    for action in REQUIRED_BLOCKED_ACTIONS:
        require(action in payload.get("blocked_actions", []), "example receipt missing blocked action: " + action)


def check_static_source_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "validate_dry_run_for_receipt",
        "APPLY_DRY_RUN_ROOT",
        "approval_receipt_review_only",
        "PROTECTED PATCH APPROVAL RECEIPT ONLY",
        "NOT APPROVED",
        "NOT APPLIED",
        "approval_collection_enabled",
        "password_collection_enabled",
        "apply_authorized",
        "Approval collection is not enabled in Phase 6.",
        "Patch application is not enabled in Phase 6.",
    ]:
        require(needle in source, "module missing required boundary text: " + needle)
    for forbidden in ["requests.", "socket.", "webbrowser", "openai", "anthropic", "subprocess."]:
        require(forbidden not in source.lower(), "module contains forbidden execution/provider text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("module contains forbidden loop or async worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)


def check_runtime_receipt_creation() -> None:
    module = load_module()
    module_hash_before = module.sha256_file(MODULE)
    dry_run_hash_before = module.sha256_file(EXAMPLE_DRY_RUN)
    with tempfile.TemporaryDirectory() as temp_name:
        receipts_dir = Path(temp_name)
        result = module.create_approval_receipt(EXAMPLE_DRY_RUN, receipts_dir=receipts_dir, created_at="2026-05-17T00:00:00Z")
        receipt_json = Path(result.receipt_json)
        receipt_md = Path(result.receipt_markdown)
        require(receipt_json.exists(), "approval receipt JSON was not written")
        require(receipt_md.exists(), "approval receipt markdown was not written")
        require(receipt_json.is_relative_to(receipts_dir), "receipt JSON escaped temp receipts directory")
        require(receipt_md.is_relative_to(receipts_dir), "receipt markdown escaped temp receipts directory")
        receipt = json.loads(read(receipt_json))
        errors = module.validate_approval_receipt_payload(receipt)
        require(not errors, "receipt validation failed: " + "; ".join(errors))
        require(receipt["created_by"] == "Engel Code Companion", "created_by mismatch")
        require(receipt["trust_level"] == "untrusted_until_human_approved", "trust mismatch")
        require(receipt["status"] == "approval_receipt_review_only", "status mismatch")
        require(receipt["requires_review"] is True, "receipt must require review")
        require(receipt["safe_to_auto_apply"] is False, "receipt must not auto-apply")
        require(receipt["patch_applied"] is False, "receipt must not be applied")
        require(receipt["source_files_modified"] is False, "receipt must not modify source")
        require(receipt["application_enabled_in_this_phase"] is False, "receipt must not enable application")
        require(receipt["approval_collection_enabled"] is False, "receipt must not collect approval")
        require(receipt["password_collection_enabled"] is False, "receipt must not collect password")
        require(receipt["human_review_required"] is True, "receipt must require human review")
        require(receipt["human_review_completed"] is False, "receipt must not mark human review complete")
        require(receipt["approval_token_required"] is True, "receipt must require approval token")
        require(receipt["approval_token_present"] is False, "receipt must not contain token")
        require(receipt["approval_token_verified"] is False, "receipt must not verify token")
        require(receipt["password_gate_required"] is True, "receipt must require password gate")
        require(receipt["password_verified"] is False, "receipt must not verify password")
        require(receipt["verifier_pass_required"] is True, "receipt must require verifier")
        require(receipt["verifier_pass_recorded_for_apply"] is False, "receipt must not record verifier pass for apply")
        require(receipt["apply_authorized"] is False, "receipt must not authorize apply")
        require(receipt["final_decision"] == FINAL_DECISION, "final decision mismatch")
        for action in REQUIRED_BLOCKED_ACTIONS:
            require(action in receipt["blocked_actions"], "receipt missing blocked action: " + action)
        text = read(receipt_md)
        for needle in [
            FINAL_DECISION,
            "No source files were modified.",
            "No patch was applied.",
            "No commands from the dry-run were executed.",
            "No trusted memory was written.",
            "No approval token was collected or stored.",
            "No password was collected or stored.",
            "Future apply remains blocked.",
        ]:
            require(needle in text, "receipt markdown missing: " + needle)
        status = module.render_status(receipts_dir=receipts_dir)
        listing = module.render_list(receipts_dir=receipts_dir)
        require("approval_collection_enabled: false" in status, "status missing approval collection disabled flag")
        require("password_collection_enabled: false" in status, "status missing password collection disabled flag")
        require("patch_application_enabled: false" in status, "status missing patch application disabled flag")
        require("Code Companion patch apply approval receipts:" in listing, "list missing approval receipt heading")
    require(module.sha256_file(MODULE) == module_hash_before, "receipt creation changed source module")
    require(module.sha256_file(EXAMPLE_DRY_RUN) == dry_run_hash_before, "receipt creation changed source dry-run")


def write_temp_dry_run(payload: dict[str, object], name: str) -> Path:
    path = DRY_RUN_EXAMPLES / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def check_invalid_inputs_rejected() -> None:
    module = load_module()
    base = json.loads(read(EXAMPLE_DRY_RUN))
    temp_paths: list[Path] = []
    try:
        cases = [
            ("safe_to_auto_apply", True, "verifier_phase6_invalid_safe_to_auto_apply_dry_run.json"),
            ("requires_review", False, "verifier_phase6_invalid_requires_review_dry_run.json"),
            ("patch_applied", True, "verifier_phase6_invalid_patch_applied_dry_run.json"),
            ("source_files_modified", True, "verifier_phase6_invalid_source_modified_dry_run.json"),
            ("application_enabled_in_this_phase", True, "verifier_phase6_invalid_application_enabled_dry_run.json"),
        ]
        for field, value, name in cases:
            payload = dict(base)
            payload[field] = value
            path = write_temp_dry_run(payload, name)
            temp_paths.append(path)
            validation = module.validate_dry_run_for_receipt(path)
            require(not validation.valid, f"invalid dry-run with {field}={value!r} was accepted")

        payload = dict(base)
        payload["final_decision"] = "NOT A VALID DRY RUN"
        path = write_temp_dry_run(payload, "verifier_phase6_invalid_final_decision_dry_run.json")
        temp_paths.append(path)
        validation = module.validate_dry_run_for_receipt(path)
        require(not validation.valid, "dry-run with invalid final decision was accepted")

        for bad_path in [BUNDLE_EXAMPLE, GATE_EXAMPLE, PLAN_EXAMPLE, FIX_CANDIDATE_EXAMPLE, REPORT]:
            validation = module.validate_dry_run_for_receipt(bad_path)
            require(not validation.valid, "disallowed input was accepted: " + str(bad_path.relative_to(ROOT)))
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()


def check_risk_flags_and_stubs() -> None:
    module = load_module()
    flags = module.risk_flags_for_text("powershell run this command apply patch write memory token password chmod firewall exfiltrate")
    for flag in ["powershell", "run_this_command", "apply_patch", "write_memory", "token", "password", "chmod", "firewall", "exfiltrate"]:
        require(flag in flags, "risk flag missing: " + flag)
    require(module.main(["approve"]) == 2, "approve stub did not refuse")
    require(module.main(["apply"]) == 2, "apply stub did not refuse")
    for path in APPROVAL_RECEIPTS.glob("*.json"):
        payload = json.loads(read(path))
        require(payload.get("apply_authorized") is not True, "live receipt authorizes apply: " + str(path.relative_to(ROOT)))
        require(payload.get("approval_token_present") is not True, "live receipt marks token present: " + str(path.relative_to(ROOT)))
        require(payload.get("password_verified") is not True, "live receipt marks password verified: " + str(path.relative_to(ROOT)))


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    forbidden_commands = [
        "code companion approve patch",
        "code companion apply patch",
        "code companion auto apply",
        "code companion trusted apply",
        "code companion write memory",
        "code companion collect password",
        "code companion collect token",
    ]
    for command in forbidden_commands:
        require(command not in commands, "ENGEL_COMMANDS contains forbidden enabled command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_code_companion_patch_apply_approval_receipt.py" in codex, "codex verifier missing approval receipt verifier")
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Patch Apply Approval Receipt V1",
        "does not approve",
        "does not apply patches",
        "does not collect/store passwords or approval tokens",
        "Phase 5 dry-run",
        "human review requirement",
        "approval-token requirement",
        "password/protected-action gate",
        "future apply remains blocked",
        "Packaging skipped",
        "Code Companion Phase 6 creates protected patch apply approval receipts only",
    ]:
        require(needle in report, "report missing: " + needle)


def main() -> int:
    checks = [
        ("phase5_present", check_phase5_present),
        ("files_and_folders", check_files_and_folders),
        ("static_source_safety", check_static_source_safety),
        ("runtime_receipt_creation", check_runtime_receipt_creation),
        ("invalid_inputs_rejected", check_invalid_inputs_rejected),
        ("risk_flags_and_stubs", check_risk_flags_and_stubs),
        ("docs_and_registration", check_docs_and_registration),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS", name)
        except CheckFailure as exc:
            print("FAIL", name, "-", exc)
            failures.append(f"{name}: {exc}")
    if failures:
        print("\nEngel Code Companion Patch Apply Approval Receipt verifier FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nEngel Code Companion Patch Apply Approval Receipt verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
