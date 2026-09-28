from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_code_companion_protected_patch_apply.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_protected_patch_apply.py"
PHASE1_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_fix_candidate_intake.py"
PHASE2_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_plan_preview.py"
PHASE3_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_bundle_draft.py"
PHASE4_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_application_gate.py"
PHASE5_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_apply_dry_run.py"
PHASE6_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_apply_approval_receipt.py"
PROTECTED_ACTION_VERIFIER = ROOT / "tools" / "verify_engel_protected_action_registry.py"
PASSWORD_GATE_VERIFIER = ROOT / "tools" / "verify_engel_global_password_gate.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PROTECTED_PATCH_APPLY_MVP_V1.md"
APPLY_ROOT = ROOT / "reports" / "code_companion_patch_applies"
APPLY_RECEIPTS = APPLY_ROOT / "receipts"
APPLY_BACKUPS = APPLY_ROOT / "backups"
APPLY_ROLLBACK = APPLY_ROOT / "rollback"
APPLY_EXAMPLES = APPLY_ROOT / "examples"
EXAMPLE_REFUSAL = APPLY_EXAMPLES / "protected_patch_apply_refusal_example.json"
APPROVAL_EXAMPLE = ROOT / "reports" / "code_companion_patch_apply_approvals" / "examples" / "patch_apply_approval_receipt_example.json"
BUNDLE_ROOT = ROOT / "reports" / "code_companion_patch_bundles"
DRY_RUN_ROOT = ROOT / "reports" / "code_companion_patch_apply_dry_runs"
APPROVAL_RECEIPTS = ROOT / "reports" / "code_companion_patch_apply_approvals" / "receipts"

APPLY_FINAL_DECISION = "PROTECTED PATCH APPLIED WITH HUMAN APPROVAL"
REFUSAL_FINAL_DECISION = "PROTECTED PATCH APPLY REFUSED \u2014 NOT APPLIED"
PASSWORD_GATE_REQUIRED_MESSAGE = "Protected password gate integration is required before real apply."

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
    "code companion protected patch apply status",
    "code companion protected patch apply validate",
    "code companion protected patch apply preflight",
    "code companion protected patch apply apply",
    "code companion protected patch apply show",
    "code companion protected patch apply rollback-info",
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
    spec = importlib.util.spec_from_file_location("engel_code_companion_protected_patch_apply", MODULE)
    require(spec is not None and spec.loader is not None, "could not load protected patch apply module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_protected_patch_apply"] = module
    spec.loader.exec_module(module)
    return module


def check_phase6_present() -> None:
    for path in [
        PHASE1_VERIFIER,
        PHASE2_VERIFIER,
        PHASE3_VERIFIER,
        PHASE4_VERIFIER,
        PHASE5_VERIFIER,
        PHASE6_VERIFIER,
        PROTECTED_ACTION_VERIFIER,
        PASSWORD_GATE_VERIFIER,
        APPROVAL_EXAMPLE,
    ]:
        require(path.exists(), "Phase 7 dependency missing required path: " + str(path.relative_to(ROOT)))


def check_files_and_folders() -> None:
    for path in [MODULE, VERIFIER, REPORT, APPLY_ROOT, APPLY_RECEIPTS, APPLY_BACKUPS, APPLY_ROLLBACK, APPLY_EXAMPLES, EXAMPLE_REFUSAL]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    payload = json.loads(read(EXAMPLE_REFUSAL))
    require(payload.get("final_decision") == REFUSAL_FINAL_DECISION, "example refusal final decision mismatch")
    require(payload.get("patch_applied") is False, "example refusal must not apply")
    require(payload.get("safe_to_auto_apply") is False, "example refusal must not auto-apply")
    require(payload.get("auto_apply") is False, "example refusal must not auto-apply")
    require(payload.get("trusted_memory_written") is False, "example refusal must not write trusted memory")
    require(payload.get("routes_mutated") is False, "example refusal must not mutate routes")
    require(payload.get("queues_mutated") is False, "example refusal must not mutate queues")
    require(payload.get("provider_calls_made") is False, "example refusal must not call providers")
    require(payload.get("approval_token_verified") is False, "example refusal must not verify token")
    require(payload.get("password_gate_verified") is False, "example refusal must not verify password")
    require(PASSWORD_GATE_REQUIRED_MESSAGE in payload.get("refusal_reason", ""), "example refusal missing password-gate reason")


def check_static_source_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_PRODUCT_PATCH",
        "run_code_companion_low_risk_patch_apply",
        PASSWORD_GATE_REQUIRED_MESSAGE,
        "PROTECTED PATCH APPLY REFUSED",
        "NOT APPLIED",
        APPLY_FINAL_DECISION,
        "MAX_CHANGED_FILES = 3",
        "MAX_BYTES_PER_CHANGE = 20 * 1024",
        "MAX_TOTAL_PATCH_BYTES = 50 * 1024",
        "backup_targets",
        "shutil.copy2",
        "rollback_metadata",
        "auto_apply: false",
        "safe_to_auto_apply",
        "trusted_memory_written",
        "routes_mutated",
        "queues_mutated",
        "provider_calls_made",
        "run_pre_apply_verifiers",
        "Pre-apply verifier execution is not enabled",
    ]:
        require(needle in source, "module missing required boundary text: " + needle)
    for forbidden in ["requests.", "socket.", "webbrowser", "openai", "anthropic", "docker", "wsl.exe", "hermes"]:
        require(forbidden not in source.lower(), "module contains forbidden provider/runtime text: " + forbidden)
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


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixture_paths(stem: str) -> dict[str, Path]:
    bundle_folder = BUNDLE_ROOT / f"verifier_phase7_{stem}_bundle"
    dry_folder = DRY_RUN_ROOT / f"verifier_phase7_{stem}_dry_run"
    approval_json = APPROVAL_RECEIPTS / f"PATCH_APPLY_APPROVAL_RECEIPT_verifier_phase7_{stem}.json"
    approval_md = APPROVAL_RECEIPTS / f"PATCH_APPLY_APPROVAL_RECEIPT_verifier_phase7_{stem}.md"
    target = APPLY_EXAMPLES / f"verifier_phase7_{stem}_target.md"
    return {
        "bundle_folder": bundle_folder,
        "bundle_json": bundle_folder / "bundle.json",
        "draft": bundle_folder / "proposed_files" / "01_verifier.proposed.md",
        "dry_folder": dry_folder,
        "dry_json": dry_folder / "dry_run.json",
        "approval_json": approval_json,
        "approval_md": approval_md,
        "target": target,
    }


def cleanup_fixture(paths: dict[str, Path]) -> None:
    for key in ["approval_json", "approval_md", "target"]:
        path = paths[key]
        if path.exists():
            path.unlink()
    for key in ["bundle_folder", "dry_folder"]:
        folder = paths[key]
        if folder.exists():
            shutil.rmtree(folder)


def create_valid_chain_fixture(stem: str, *, unsafe_target: str | None = None) -> dict[str, Path]:
    module = load_module()
    paths = fixture_paths(stem)
    cleanup_fixture(paths)
    target_rel = unsafe_target or module.project_relative(paths["target"])
    replacement = "# Verifier Phase 7 Target\n\nThis would be a tiny reports-only test fixture.\n"
    draft_text = f"""# Proposed File Draft

PREVIEW ONLY - NOT APPLIED

PHASE7_REPLACEMENT_CONTENT

```text
{replacement.rstrip()}
```
"""
    bundle = {
        "bundle_version": "1",
        "bundle_id": f"verifier_phase7_{stem}_bundle",
        "created_at": "2026-05-17T00:00:00Z",
        "created_by": "Engel Code Companion",
        "source_plan_id": "verifier_phase7_plan",
        "source_plan_path": "reports\\code_companion_patch_plans\\examples\\patch_plan_preview_example.json",
        "source_plan_hash": "verifier_fixture",
        "trust_level": "untrusted_until_human_review",
        "status": "draft_bundle_preview",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "final_decision": patch_bundle_final_decision(),
        "title": "Verifier Phase 7 bundle",
        "problem_summary": "Verifier-only reports fixture.",
        "bundle_summary": "Replace a reports-only fixture file with tiny text.",
        "target_files": [target_rel],
        "proposed_file_drafts": [
            {
                "target_file": target_rel,
                "draft_file": "proposed_files/01_verifier.proposed.md",
                "change_type": "docs_only",
                "preview_only": True,
                "source_file_modified": False,
                "requires_manual_review": True,
            }
        ],
        "verification_plan": [
            {
                "command": "python tools\\verify_engel_code_companion_protected_patch_apply.py",
                "purpose": "Verify Phase 7 protected patch apply MVP.",
                "manual_only": True,
                "executed_by_bundle_creation": False,
            }
        ],
        "risk_flags": [],
        "blocked_actions": [
            "apply_patch",
            "edit_source",
            "execute_commands",
            "mutate_routes",
            "mutate_queue",
            "write_trusted_memory",
            "auto_apply",
            "provider_call",
            "browser_task",
            "download",
            "install_package",
        ],
        "required_approvals_before_apply": [
            "human_review",
            "approval_token",
            "password_gate_for_protected_actions",
            "verifier_pass_required",
        ],
        "notes": "Draft bundle only. No source files were modified.",
    }
    paths["draft"].parent.mkdir(parents=True, exist_ok=True)
    paths["draft"].write_text(draft_text, encoding="utf-8")
    write_json(paths["bundle_json"], bundle)
    (paths["bundle_folder"] / "README.md").write_text(
        "# Verifier Phase 7 Bundle\n\nPATCH BUNDLE DRAFT ONLY - NOT APPLIED\n\nNo source files were modified.\n",
        encoding="utf-8",
    )
    (paths["bundle_folder"] / "proposed_changes.md").write_text(
        "# Proposed Changes\n\nPREVIEW ONLY - NOT APPLIED\n",
        encoding="utf-8",
    )
    (paths["bundle_folder"] / "verification_plan.md").write_text(
        "# Verification Plan\n\nPREVIEW ONLY - COMMANDS NOT RUN BY BUNDLE CREATION\n",
        encoding="utf-8",
    )
    (paths["bundle_folder"] / "risk_review.md").write_text(
        "# Risk Review\n\nPREVIEW ONLY - NOT APPLIED\n",
        encoding="utf-8",
    )
    write_json(
        paths["bundle_folder"] / "source_manifest.json",
        {
            "bundle_id": bundle["bundle_id"],
            "source_files_modified": False,
            "patch_applied": False,
            "safe_to_auto_apply": False,
            "target_files": [target_rel],
        },
    )
    dry_run = {
        "dry_run_version": "1",
        "dry_run_id": f"verifier_phase7_{stem}_apply_dry_run",
        "created_at": "2026-05-17T00:00:00Z",
        "created_by": "Engel Code Companion",
        "source_bundle_id": bundle["bundle_id"],
        "source_bundle_path": module.project_relative(paths["bundle_json"]),
        "source_bundle_hash": module.sha256_file(paths["bundle_json"]),
        "source_gate_id": None,
        "source_gate_path": None,
        "source_gate_hash": None,
        "trust_level": "untrusted_until_human_approved",
        "status": "apply_dry_run_preview",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "source_files_modified": False,
        "application_enabled_in_this_phase": False,
        "approval_token_required": True,
        "approval_token_present": False,
        "password_gate_required": True,
        "password_verified": False,
        "verifier_pass_required": True,
        "human_review_required": True,
        "target_files_checked": [],
        "target_file_hashes_before": [],
        "simulated_files": [],
        "diff_previews": [],
        "missing_target_files": [],
        "protected_path_flags": [],
        "risk_flags": [],
        "verification_plan": [],
        "blocked_actions": list(module.REQUIRED_BLOCKED_ACTIONS),
        "final_decision": module.patch_apply_dry_run.FINAL_DECISION,
    }
    write_json(paths["dry_json"], dry_run)
    approval = {
        "approval_receipt_version": "1",
        "approval_receipt_id": f"verifier_phase7_{stem}_approval_receipt",
        "created_at": "2026-05-17T00:00:00Z",
        "created_by": "Engel Code Companion",
        "source_dry_run_id": dry_run["dry_run_id"],
        "source_dry_run_path": module.project_relative(paths["dry_json"]),
        "source_dry_run_hash": module.sha256_file(paths["dry_json"]),
        "trust_level": "untrusted_until_human_approved",
        "status": "approval_receipt_review_only",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "source_files_modified": False,
        "application_enabled_in_this_phase": False,
        "approval_collection_enabled": False,
        "password_collection_enabled": False,
        "human_review_required": True,
        "human_review_completed": False,
        "approval_token_required": True,
        "approval_token_present": False,
        "approval_token_verified": False,
        "password_gate_required": True,
        "password_verified": False,
        "verifier_pass_required": True,
        "verifier_pass_recorded_for_apply": False,
        "apply_authorized": False,
        "eligible_for_future_apply_consideration": True,
        "required_approvals_before_apply": [
            "human_review",
            "approval_token",
            "password_gate_for_protected_actions",
            "verifier_pass_required",
        ],
        "blocked_actions": [
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
        ],
        "target_files": [target_rel],
        "risk_flags": [],
        "verification_plan": [],
        "final_decision": module.approval_receipt.APPROVAL_FINAL_DECISION,
    }
    write_json(paths["approval_json"], approval)
    paths["approval_md"].write_text("# Verifier Phase 7 approval receipt fixture\n", encoding="utf-8")
    return paths


def patch_bundle_final_decision() -> str:
    module = importlib.util.spec_from_file_location("engel_code_companion_patch_bundle_draft_for_const", ROOT / "engel_code_companion_patch_bundle_draft.py")
    require(module is not None and module.loader is not None, "could not load bundle module for final decision")
    loaded = importlib.util.module_from_spec(module)
    sys.modules["engel_code_companion_patch_bundle_draft_for_const"] = loaded
    module.loader.exec_module(loaded)
    return loaded.FINAL_DECISION


def check_validation_and_preflight() -> None:
    module = load_module()
    validation = module.validate_chain(APPROVAL_EXAMPLE)
    require(validation.valid, "example approval receipt did not validate: " + "; ".join(validation.errors))
    preflight = module.preflight_context(APPROVAL_EXAMPLE)
    require(preflight["eligible_for_apply_attempt"] is False, "example receipt became apply-eligible")
    require(any("example approval receipts cannot be applied" in err for err in preflight["errors"]), "example preflight missing example refusal")

    paths = create_valid_chain_fixture("valid")
    try:
        validation = module.validate_chain(paths["approval_json"])
        require(validation.valid, "valid fixture chain did not validate: " + "; ".join(validation.errors))
        preflight = module.preflight_context(paths["approval_json"])
        require(preflight["eligible_for_apply_attempt"] is True, "valid fixture preflight was not eligible before password gate")
        require(preflight["safe_target_count"] == 1, "valid fixture safe target count mismatch")
        rendered = module.render_preflight(paths["approval_json"])
        require("APPROVE_PRODUCT_PATCH" in rendered, "preflight missing approval token")
        require("auto_apply: false" in rendered, "preflight missing auto_apply false")
    finally:
        cleanup_fixture(paths)


def check_refusal_paths() -> None:
    module = load_module()
    paths = create_valid_chain_fixture("refusal")
    target_hash = module.sha256_file(MODULE)
    try:
        with tempfile.TemporaryDirectory() as temp_name:
            receipts_dir = Path(temp_name)
            missing_confirm = module.protected_apply(
                paths["approval_json"],
                approval_token="APPROVE_PRODUCT_PATCH",
                confirm_human_approved=False,
                receipts_dir=receipts_dir,
                created_at="2026-05-17T00:00:00Z",
            )
            require(missing_confirm["patch_applied"] is False, "missing human confirmation applied patch")
            require("Human confirmation" in missing_confirm["refusal_reason"], "missing-confirm refusal reason mismatch")

            missing_token = module.protected_apply(
                paths["approval_json"],
                approval_token="",
                confirm_human_approved=True,
                receipts_dir=receipts_dir,
                created_at="2026-05-17T00:00:01Z",
            )
            require(missing_token["patch_applied"] is False, "missing token applied patch")
            require("APPROVE_PRODUCT_PATCH" in missing_token["refusal_reason"], "missing-token refusal reason mismatch")

            missing_password = module.protected_apply(
                paths["approval_json"],
                approval_token="APPROVE_PRODUCT_PATCH",
                confirm_human_approved=True,
                receipts_dir=receipts_dir,
                created_at="2026-05-17T00:00:02Z",
            )
            require(missing_password["patch_applied"] is False, "missing password gate applied patch")
            require(PASSWORD_GATE_REQUIRED_MESSAGE in missing_password["refusal_reason"], "missing-password refusal reason mismatch")

            receipts = list(receipts_dir.glob("*.json"))
            require(len(receipts) == 3, "expected three temp refusal receipts")
            for path in receipts:
                payload = json.loads(read(path))
                require(payload.get("final_decision") == REFUSAL_FINAL_DECISION, "refusal receipt final decision mismatch")
                require(payload.get("patch_applied") is False, "refusal receipt marked applied")
                require(payload.get("approval_token_verified") is not True or "missing" not in path.name, "refusal receipt unexpectedly verified token")
                text = read(path)
                require("APPROVE_PRODUCT_PATCH" not in text or payload.get("approval_token_verified") is False, "raw token leaked into unexpected receipt state")
            require(not paths["target"].exists(), "refusal path wrote target file")
    finally:
        cleanup_fixture(paths)
    require(module.sha256_file(MODULE) == target_hash, "refusal path changed source module")


def check_unsafe_inputs_rejected() -> None:
    module = load_module()
    unsafe = module.target_path_info("engel_app.py")
    require(unsafe["allowed"] is False, "root runtime source was allowed")
    unsafe = module.target_path_info("memory\\ENGEL_COMMANDS.md")
    require(unsafe["allowed"] is False, "memory path was allowed by default")
    unsafe = module.target_path_info("scripts\\codex_verify.ps1")
    require(unsafe["allowed"] is False, "codex verifier script was allowed by default")
    unsafe = module.target_path_info("live\\app\\Engel.exe")
    require(unsafe["allowed"] is False, "live executable path was allowed")
    safe = module.target_path_info("reports\\code_companion_patch_applies\\examples\\safe_fixture.md")
    require(safe["allowed"] is True, "reports fixture path should be allowed")

    paths = create_valid_chain_fixture("unsafe", unsafe_target="engel_app.py")
    try:
        preflight = module.preflight_context(paths["approval_json"])
        require(preflight["eligible_for_apply_attempt"] is False, "unsafe target preflight became eligible")
        require(any("target rejected" in err for err in preflight["errors"]), "unsafe target rejection missing")
    finally:
        cleanup_fixture(paths)

    validation = module.validate_chain(ROOT / "reports" / "code_companion_patch_apply_dry_runs" / "examples" / "patch_apply_dry_run_example.json")
    require(not validation.valid, "raw Phase 5 dry-run was accepted as Phase 7 approval receipt")


def check_no_live_apply_artifacts() -> None:
    for folder in [APPLY_RECEIPTS, APPLY_BACKUPS, APPLY_ROLLBACK]:
        for path in folder.iterdir():
            if path.name == ".gitkeep":
                continue
            raise CheckFailure("unexpected live apply artifact left by verifier: " + str(path.relative_to(ROOT)))


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_code_companion_protected_patch_apply.py" in codex, "codex verifier missing Phase 7 verifier")
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Protected Patch Apply MVP V1",
        "Apply gate chain",
        "APPROVE_PRODUCT_PATCH",
        "password/protected-action gate",
        "Bound limits",
        "Allowed paths",
        "Denied paths",
        "Backup and rollback behavior",
        "real apply is still blocked",
        "Full codex verifier result",
        "Safety boundary statement",
    ]:
        require(needle in report, "Phase 7 report missing: " + needle)


def main() -> int:
    checks = [
        ("phase6_present", check_phase6_present),
        ("files_and_folders", check_files_and_folders),
        ("static_source_safety", check_static_source_safety),
        ("validation_and_preflight", check_validation_and_preflight),
        ("refusal_paths", check_refusal_paths),
        ("unsafe_inputs_rejected", check_unsafe_inputs_rejected),
        ("no_live_apply_artifacts", check_no_live_apply_artifacts),
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
        print("\nEngel Code Companion Protected Patch Apply verifier FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nEngel Code Companion Protected Patch Apply verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
