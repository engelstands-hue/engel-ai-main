from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_code_companion_patch_application_gate.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_application_gate.py"
PHASE1_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_fix_candidate_intake.py"
PHASE2_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_plan_preview.py"
PHASE3_MODULE = ROOT / "engel_code_companion_patch_bundle_draft.py"
PHASE3_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_bundle_draft.py"
PROTECTED_ACTION_VERIFIER = ROOT / "tools" / "verify_engel_protected_action_registry.py"
PASSWORD_GATE_VERIFIER = ROOT / "tools" / "verify_engel_global_password_gate.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PROTECTED_PATCH_APPLICATION_GATE_V1.md"
GATE_ROOT = ROOT / "reports" / "code_companion_patch_application_gates"
GATE_EXAMPLES = GATE_ROOT / "examples"
GATE_RECEIPTS = GATE_ROOT / "receipts"
GATE_DRY_RUNS = GATE_ROOT / "dry_runs"
EXAMPLE_GATE = GATE_EXAMPLES / "patch_application_gate_example.json"
BUNDLE_ROOT = ROOT / "reports" / "code_companion_patch_bundles"
BUNDLE_EXAMPLE = BUNDLE_ROOT / "examples" / "patch_bundle_draft_example.json"
PLAN_EXAMPLE = ROOT / "reports" / "code_companion_patch_plans" / "examples" / "patch_plan_preview_example.json"
FIX_CANDIDATE_EXAMPLE = ROOT / "reports" / "code_companion_fix_candidates" / "examples" / "fix_candidate_example.json"

GATE_FINAL_DECISION = "PROTECTED APPLICATION GATE ONLY — NOT APPLIED"
DRY_RUN_FINAL_DECISION = "DRY RUN ONLY — NOT APPLIED"

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

REQUIRED_GATE_BLOCKED_ACTIONS = [
    "apply_patch_without_approval",
    "edit_source_without_approval",
    "execute_commands_from_bundle",
    "mutate_routes",
    "mutate_queue",
    "write_trusted_memory",
    "auto_apply",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
]

REQUIRED_APPROVALS = [
    "human_review",
    "approval_token",
    "password_gate_for_protected_actions",
    "verifier_pass_required",
]

REQUIRED_COMMANDS = [
    "code companion patch gate status",
    "code companion patch gate list",
    "code companion patch gate validate-bundle",
    "code companion patch gate check",
    "code companion patch gate dry-run",
    "code companion patch gate show",
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
    spec = importlib.util.spec_from_file_location("engel_code_companion_patch_application_gate", MODULE)
    require(spec is not None and spec.loader is not None, "could not load patch application gate module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_patch_application_gate"] = module
    spec.loader.exec_module(module)
    return module


def check_phase3_present() -> None:
    for path in [PHASE1_VERIFIER, PHASE2_VERIFIER, PHASE3_MODULE, PHASE3_VERIFIER, BUNDLE_EXAMPLE]:
        require(path.exists(), "Phase 3 dependency missing required path: " + str(path.relative_to(ROOT)))


def check_files_and_folders() -> None:
    for path in [MODULE, VERIFIER, REPORT, GATE_ROOT, GATE_EXAMPLES, GATE_RECEIPTS, GATE_DRY_RUNS, EXAMPLE_GATE]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    payload = json.loads(read(EXAMPLE_GATE))
    require(payload.get("status") == "gate_review_only", "example gate status mismatch")
    require(payload.get("requires_review") is True, "example gate must require review")
    require(payload.get("safe_to_auto_apply") is False, "example gate must not auto-apply")
    require(payload.get("patch_applied") is False, "example gate must not be applied")
    require(payload.get("source_files_modified") is False, "example gate must not modify source")
    require(payload.get("application_enabled_in_this_phase") is False, "example gate must be disabled")
    require(payload.get("approval_token_required") is True, "example gate must require approval token")
    require(payload.get("password_gate_required") is True, "example gate must require password gate")
    require(payload.get("verifier_pass_required") is True, "example gate must require verifier")
    require(payload.get("final_decision") == GATE_FINAL_DECISION, "example gate final decision mismatch")


def check_static_source_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "resolve_bundle_path",
        "BUNDLE_ROOT",
        "gate_review_only",
        "dry_run_preview_only",
        GATE_FINAL_DECISION,
        DRY_RUN_FINAL_DECISION,
        "application_enabled_in_this_phase",
        "approval_token_present",
        "password_verified",
        "Patch application is not enabled in Phase 4.",
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


def check_runtime_gate_and_dry_run() -> None:
    module = load_module()
    module_hash_before = module.sha256_file(MODULE)
    with tempfile.TemporaryDirectory() as temp_name:
        temp_root = Path(temp_name)
        receipts = temp_root / "receipts"
        dry_runs = temp_root / "dry_runs"
        gate_result = module.check_bundle(BUNDLE_EXAMPLE, receipts_dir=receipts, created_at="2026-05-17T00:00:00Z")
        dry_result = module.dry_run_bundle(BUNDLE_EXAMPLE, dry_runs_dir=dry_runs, created_at="2026-05-17T00:00:00Z")
        gate_json = Path(gate_result.gate_json)
        gate_md = Path(gate_result.gate_markdown)
        dry_json = Path(dry_result.dry_run_json)
        dry_md = Path(dry_result.dry_run_markdown)
        for path in [gate_json, gate_md, dry_json, dry_md]:
            require(path.exists(), "expected output missing: " + str(path))
        require(gate_json.is_relative_to(receipts), "gate JSON escaped temp receipt dir")
        require(gate_md.is_relative_to(receipts), "gate markdown escaped temp receipt dir")
        require(dry_json.is_relative_to(dry_runs), "dry-run JSON escaped temp dry-run dir")
        require(dry_md.is_relative_to(dry_runs), "dry-run markdown escaped temp dry-run dir")

        gate = json.loads(read(gate_json))
        dry_run = json.loads(read(dry_json))
        require(not module.validate_gate_payload(gate), "generated gate did not validate")
        require(not module.validate_dry_run_payload(dry_run), "generated dry-run did not validate")
        require(gate["created_by"] == "Engel Code Companion", "gate created_by mismatch")
        require(gate["trust_level"] == "untrusted_until_human_approved", "gate trust level mismatch")
        require(gate["status"] == "gate_review_only", "gate status mismatch")
        require(gate["requires_review"] is True, "gate must require review")
        require(gate["safe_to_auto_apply"] is False, "gate must not auto-apply")
        require(gate["patch_applied"] is False, "gate must not be applied")
        require(gate["source_files_modified"] is False, "gate must not modify source")
        require(gate["application_enabled_in_this_phase"] is False, "gate must be disabled in Phase 4")
        require(gate["approval_token_required"] is True, "gate must require approval token")
        require(gate["approval_token_present"] is False, "gate must not collect token")
        require(gate["password_gate_required"] is True, "gate must require password gate")
        require(gate["password_verified"] is False, "gate must not verify/store password")
        require(gate["verifier_pass_required"] is True, "gate must require verifier")
        require(gate["human_review_required"] is True, "gate must require human review")
        require(gate["final_decision"] == GATE_FINAL_DECISION, "gate final decision mismatch")
        for action in REQUIRED_GATE_BLOCKED_ACTIONS:
            require(action in gate["blocked_actions"], "gate missing blocked action: " + action)
        for approval in REQUIRED_APPROVALS:
            require(approval in gate["required_approvals_before_apply"], "gate missing approval: " + approval)
        gate_text = read(gate_md)
        require(GATE_FINAL_DECISION in gate_text, "gate markdown missing final decision")
        require("No source files were modified." in gate_text, "gate markdown missing no-source-edit statement")
        require("No patch was applied." in gate_text, "gate markdown missing no-patch statement")
        require("No commands from the bundle were executed." in gate_text, "gate markdown missing no-command statement")
        require("Approval token is required before any future apply." in gate_text, "gate markdown missing token requirement")
        require("Password/protected-action gate is required before any future apply." in gate_text, "gate markdown missing password requirement")
        require("Verifier pass is required before any future apply." in gate_text, "gate markdown missing verifier requirement")
        require(len(gate_text) < 19000, "gate receipt is not bounded")

        require(dry_run["status"] == "dry_run_preview_only", "dry-run status mismatch")
        require(dry_run["patch_applied"] is False, "dry-run must not apply")
        require(dry_run["source_files_modified"] is False, "dry-run must not modify source")
        require(dry_run["safe_to_auto_apply"] is False, "dry-run must not auto-apply")
        require(dry_run["requires_review"] is True, "dry-run must require review")
        require(dry_run["application_enabled_in_this_phase"] is False, "dry-run must not enable application")
        require(dry_run["final_decision"] == DRY_RUN_FINAL_DECISION, "dry-run final decision mismatch")
        dry_text = read(dry_md)
        require(DRY_RUN_FINAL_DECISION in dry_text, "dry-run markdown missing final decision")
        require("No source files were modified" in dry_text, "dry-run markdown missing no-source-edit statement")
        require(len(dry_text) < 19000, "dry-run report is not bounded")

        status = module.render_status(gate_root=temp_root / "gates", receipts_dir=receipts, dry_runs_dir=dry_runs)
        listing = module.render_list(receipts_dir=receipts, dry_runs_dir=dry_runs)
        require("patch_application_enabled: false" in status, "status missing disabled application flag")
        require("source_mutation_enabled: false" in status, "status missing source mutation disabled flag")
        require("Code Companion patch application gate receipts:" in listing, "list missing gate heading")
    require(module.sha256_file(MODULE) == module_hash_before, "gate/dry-run changed source module")


def write_temp_bundle(payload: dict[str, object], name: str) -> Path:
    path = BUNDLE_EXAMPLE.parent / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def check_invalid_bundles_rejected() -> None:
    module = load_module()
    base = json.loads(read(BUNDLE_EXAMPLE))
    temp_paths: list[Path] = []
    try:
        cases = [
            ("safe_to_auto_apply", True, "verifier_gate_invalid_safe_to_auto_apply_bundle.json"),
            ("requires_review", False, "verifier_gate_invalid_requires_review_bundle.json"),
            ("patch_applied", True, "verifier_gate_invalid_patch_applied_bundle.json"),
            ("status", "applied", "verifier_gate_invalid_applied_status_bundle.json"),
            ("status", "trusted", "verifier_gate_invalid_trusted_status_bundle.json"),
            ("status", "complete", "verifier_gate_invalid_complete_status_bundle.json"),
            ("trust_level", "trusted", "verifier_gate_invalid_trusted_level_bundle.json"),
        ]
        for field, value, name in cases:
            payload = dict(base)
            payload[field] = value
            path = write_temp_bundle(payload, name)
            temp_paths.append(path)
            result = module.validate_bundle_for_gate(path)
            require(not result.valid, f"invalid bundle with {field}={value!r} was accepted")
        payload = dict(base)
        payload["blocked_actions"] = [item for item in base["blocked_actions"] if item != "apply_patch"]
        path = write_temp_bundle(payload, "verifier_gate_invalid_missing_blocked_action_bundle.json")
        temp_paths.append(path)
        require(not module.validate_bundle_for_gate(path).valid, "missing blocked action was accepted")
        payload = dict(base)
        draft = dict(base["proposed_file_drafts"][0])
        draft["preview_only"] = False
        payload["proposed_file_drafts"] = [draft]
        path = write_temp_bundle(payload, "verifier_gate_invalid_preview_false_bundle.json")
        temp_paths.append(path)
        require(not module.validate_bundle_for_gate(path).valid, "preview_only false was accepted")
        payload = dict(base)
        draft = dict(base["proposed_file_drafts"][0])
        draft["source_file_modified"] = True
        payload["proposed_file_drafts"] = [draft]
        path = write_temp_bundle(payload, "verifier_gate_invalid_source_modified_bundle.json")
        temp_paths.append(path)
        require(not module.validate_bundle_for_gate(path).valid, "source_file_modified true was accepted")
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()


def check_risk_flags_and_source_restrictions() -> None:
    module = load_module()
    flags = module.risk_flags_for_text("powershell run this command apply patch write memory token password chmod firewall exfiltrate")
    for flag in ["powershell", "run_this_command", "apply_patch", "write_memory", "token", "password", "chmod", "firewall", "exfiltrate"]:
        require(flag in flags, "risk flag missing: " + flag)
    protected = module.target_path_info("memory\\ENGEL_COMMANDS.md")
    require("protected_memory_path" in protected.get("protected_flags", []), "protected memory path was not flagged")
    try:
        module.resolve_bundle_path(PLAN_EXAMPLE)
    except module.PatchApplicationGateError:
        pass
    else:
        raise CheckFailure("Phase 2 patch plan path was accepted by Phase 4")
    try:
        module.resolve_bundle_path(FIX_CANDIDATE_EXAMPLE)
    except module.PatchApplicationGateError:
        pass
    else:
        raise CheckFailure("Phase 1 fix candidate path was accepted by Phase 4")
    for root in [GATE_ROOT, GATE_RECEIPTS, GATE_DRY_RUNS]:
        if not root.exists():
            continue
        for path in root.iterdir():
            if path.is_file():
                require(path.suffix.lower() not in {".patch", ".diff"}, "patch/diff output exists in gate folder: " + str(path.relative_to(ROOT)))


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    forbidden_commands = [
        "code companion apply patch",
        "code companion auto apply",
        "code companion trusted apply",
        "code companion write memory",
        "code companion bypass gate",
    ]
    for command in forbidden_commands:
        require(command not in commands, "ENGEL_COMMANDS contains forbidden enabled command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_code_companion_patch_application_gate.py" in codex, "codex verifier missing patch application gate verifier")
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Protected Patch Application Gate V1",
        "does not edit source",
        "does not apply patches",
        "approval token",
        "password/protected-action gate",
        "dry-run",
        "Packaging skipped",
        "Code Companion Phase 4 creates a protected application gate and dry-run eligibility reports only",
    ]:
        require(needle in report, "report missing: " + needle)


def main() -> int:
    checks = [
        ("phase3_present", check_phase3_present),
        ("files_and_folders", check_files_and_folders),
        ("static_source_safety", check_static_source_safety),
        ("runtime_gate_and_dry_run", check_runtime_gate_and_dry_run),
        ("invalid_bundles_rejected", check_invalid_bundles_rejected),
        ("risk_flags_and_source_restrictions", check_risk_flags_and_source_restrictions),
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
        print("\nEngel Code Companion Protected Patch Application Gate verifier FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nEngel Code Companion Protected Patch Application Gate verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
