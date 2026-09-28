from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_code_companion_patch_bundle_draft.py"
PHASE1_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_fix_candidate_intake.py"
PHASE2_MODULE = ROOT / "engel_code_companion_patch_plan_preview.py"
PHASE2_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_plan_preview.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_bundle_draft.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_BUNDLE_DRAFT_V1.md"
BUNDLE_ROOT = ROOT / "reports" / "code_companion_patch_bundles"
BUNDLE_EXAMPLES = BUNDLE_ROOT / "examples"
BUNDLE_RECEIPTS = BUNDLE_ROOT / "receipts"
EXAMPLE_BUNDLE = BUNDLE_EXAMPLES / "patch_bundle_draft_example.json"
PLAN_EXAMPLE = ROOT / "reports" / "code_companion_patch_plans" / "examples" / "patch_plan_preview_example.json"
FINAL_DECISION = "PATCH BUNDLE DRAFT ONLY — NOT APPLIED"

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
]

REQUIRED_APPROVALS = [
    "human_review",
    "approval_token",
    "password_gate_for_protected_actions",
    "verifier_pass_required",
]

REQUIRED_COMMANDS = [
    "code companion patch bundle status",
    "code companion patch bundle list",
    "code companion patch bundle validate",
    "code companion patch bundle create",
    "code companion patch bundle show",
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
    spec = importlib.util.spec_from_file_location("engel_code_companion_patch_bundle_draft", MODULE)
    require(spec is not None and spec.loader is not None, "could not load patch bundle draft module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_patch_bundle_draft"] = module
    spec.loader.exec_module(module)
    return module


def check_phase2_present() -> None:
    for path in [PHASE1_VERIFIER, PHASE2_MODULE, PHASE2_VERIFIER, PLAN_EXAMPLE]:
        require(path.exists(), "Phase 2 dependency missing required path: " + str(path.relative_to(ROOT)))


def check_files_and_folders() -> None:
    for path in [MODULE, VERIFIER, REPORT, BUNDLE_ROOT, BUNDLE_EXAMPLES, BUNDLE_RECEIPTS, EXAMPLE_BUNDLE]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    payload = json.loads(read(EXAMPLE_BUNDLE))
    require(payload.get("status") == "draft_bundle_preview", "example bundle status mismatch")
    require(payload.get("requires_review") is True, "example bundle must require review")
    require(payload.get("safe_to_auto_apply") is False, "example bundle must not auto-apply")
    require(payload.get("patch_applied") is False, "example bundle must not be applied")
    require(payload.get("final_decision") == FINAL_DECISION, "example bundle final decision mismatch")


def check_static_source_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "resolve_plan_path",
        "PLAN_ROOT",
        "draft_bundle_preview",
        "safe_to_auto_apply",
        "patch_applied",
        "Draft bundle only. No source files were modified.",
        FINAL_DECISION,
        "PREVIEW ONLY - NOT APPLIED",
        "executed_by_bundle_creation",
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


def check_runtime_create_validate() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as temp_name:
        temp_root = Path(temp_name)
        bundle_root = temp_root / "bundles"
        receipt_dir = temp_root / "receipts"
        result = module.create_patch_bundle_draft(
            PLAN_EXAMPLE,
            bundle_root=bundle_root,
            receipt_dir=receipt_dir,
            created_at="2026-05-17T00:00:00Z",
        )
        bundle_folder = Path(result.bundle_folder)
        bundle_json = Path(result.bundle_json)
        receipt_path = Path(result.receipt_path)
        require(bundle_folder.exists() and bundle_folder.is_dir(), "bundle folder was not written")
        require(bundle_json.exists(), "bundle.json was not written")
        require(receipt_path.exists(), "receipt was not written")
        require(bundle_folder.is_relative_to(bundle_root), "bundle escaped temp bundle root")
        require(receipt_path.is_relative_to(receipt_dir), "receipt escaped temp receipt dir")

        bundle = json.loads(read(bundle_json))
        validation = module.validate_bundle_file(bundle_folder)
        require(validation.valid, "created bundle did not validate: " + "; ".join(validation.errors))
        require(bundle["created_by"] == "Engel Code Companion", "created_by mismatch")
        require(bundle["trust_level"] == "untrusted_until_human_review", "trust level mismatch")
        require(bundle["status"] == "draft_bundle_preview", "status mismatch")
        require(bundle["requires_review"] is True, "bundle must require review")
        require(bundle["safe_to_auto_apply"] is False, "bundle must not auto-apply")
        require(bundle["patch_applied"] is False, "bundle must not be applied")
        require(bundle.get("final_decision") == FINAL_DECISION, "bundle final decision mismatch")
        for action in REQUIRED_BLOCKED_ACTIONS:
            require(action in bundle["blocked_actions"], "missing blocked action: " + action)
        for approval in REQUIRED_APPROVALS:
            require(approval in bundle["required_approvals_before_apply"], "missing approval: " + approval)
        for draft in bundle["proposed_file_drafts"]:
            require(draft.get("preview_only") is True, "proposed draft must be preview only")
            require(draft.get("source_file_modified") is False, "proposed draft must not modify source")
            draft_file = bundle_folder / str(draft.get("draft_file", "")).replace("/", "\\")
            require(draft_file.exists(), "proposed draft file was not written")
            require(draft_file.suffix.lower() in {".md", ".txt"}, "proposed draft file must be .md/.txt")
            require("PREVIEW ONLY" in read(draft_file), "proposed draft missing preview banner")

        for required_file in ["README.md", "proposed_changes.md", "verification_plan.md", "risk_review.md", "source_manifest.json"]:
            require((bundle_folder / required_file).exists(), "bundle missing " + required_file)
        manifest = json.loads(read(bundle_folder / "source_manifest.json"))
        require(manifest.get("source_files_modified") is False, "manifest must state source files were not modified")
        require(manifest.get("patch_applied") is False, "manifest must state patch was not applied")
        receipt = read(receipt_path)
        require(FINAL_DECISION in receipt, "receipt missing exact final decision")
        require("No source files were modified." in receipt, "receipt missing no-source-edit statement")
        require("No patch was applied." in receipt, "receipt missing no-patch statement")
        require("No commands from the plan were executed." in receipt, "receipt missing no-command statement")
        require("Bundle is untrusted until human review." in receipt, "receipt missing untrusted statement")
        require(len(receipt) < 15000, "receipt is not bounded")

        status = module.render_status(bundle_root=bundle_root, receipt_dir=receipt_dir)
        listing = module.render_list(bundle_root=bundle_root)
        require("No patch apply" in status, "status missing preview safety boundary")
        require("Code Companion patch bundle drafts:" in listing, "list missing created bundle")


def write_temp_plan(payload: dict[str, object], name: str) -> Path:
    path = PLAN_EXAMPLE.parent / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def check_invalid_plans_rejected() -> None:
    module = load_module()
    base = json.loads(read(PLAN_EXAMPLE))
    temp_paths: list[Path] = []
    try:
        for field, value, name in [
            ("safe_to_auto_apply", True, "verifier_invalid_safe_to_auto_apply_plan.json"),
            ("requires_review", False, "verifier_invalid_requires_review_plan.json"),
            ("patch_applied", True, "verifier_invalid_patch_applied_plan.json"),
            ("status", "applied", "verifier_invalid_applied_status_plan.json"),
            ("status", "trusted", "verifier_invalid_trusted_status_plan.json"),
            ("status", "complete", "verifier_invalid_complete_status_plan.json"),
        ]:
            payload = dict(base)
            payload[field] = value
            path = write_temp_plan(payload, name)
            temp_paths.append(path)
            with tempfile.TemporaryDirectory() as temp_name:
                try:
                    module.create_patch_bundle_draft(path, bundle_root=Path(temp_name) / "bundles", receipt_dir=Path(temp_name) / "receipts")
                except module.PatchBundleDraftError:
                    pass
                else:
                    raise CheckFailure(f"invalid plan with {field}={value!r} was accepted")
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()


def check_bundle_validation_rejections() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as temp_name:
        result = module.create_patch_bundle_draft(
            PLAN_EXAMPLE,
            bundle_root=Path(temp_name) / "bundles",
            receipt_dir=Path(temp_name) / "receipts",
            created_at="2026-05-17T00:00:00Z",
        )
        bundle = json.loads(read(Path(result.bundle_json)))
    unsafe = dict(bundle)
    unsafe["safe_to_auto_apply"] = True
    require(not module.validate_bundle_payload(unsafe).valid, "safe_to_auto_apply true was not rejected")
    unsafe = dict(bundle)
    unsafe["patch_applied"] = True
    require(not module.validate_bundle_payload(unsafe).valid, "patch_applied true was not rejected")
    unsafe = dict(bundle)
    unsafe["requires_review"] = False
    require(not module.validate_bundle_payload(unsafe).valid, "requires_review false was not rejected")
    unsafe = dict(bundle)
    unsafe["final_decision"] = "PATCH BUNDLE DRAFT ONLY - NOT APPLIED"
    require(not module.validate_bundle_payload(unsafe).valid, "non-exact final decision was not rejected")
    for bad_status in ["applied", "trusted", "complete", "completed"]:
        unsafe = dict(bundle)
        unsafe["status"] = bad_status
        require(not module.validate_bundle_payload(unsafe).valid, "bad status was not rejected: " + bad_status)
    unsafe = dict(bundle)
    unsafe["blocked_actions"] = [item for item in bundle["blocked_actions"] if item != "apply_patch"]
    require(not module.validate_bundle_payload(unsafe).valid, "missing blocked action was not rejected")
    unsafe = dict(bundle)
    unsafe["required_approvals_before_apply"] = [item for item in bundle["required_approvals_before_apply"] if item != "approval_token"]
    require(not module.validate_bundle_payload(unsafe).valid, "missing required approval was not rejected")
    unsafe = dict(bundle)
    draft = dict(bundle["proposed_file_drafts"][0])
    draft["preview_only"] = False
    unsafe["proposed_file_drafts"] = [draft]
    require(not module.validate_bundle_payload(unsafe).valid, "preview_only false was not rejected")
    unsafe = dict(bundle)
    draft = dict(bundle["proposed_file_drafts"][0])
    draft["source_file_modified"] = True
    unsafe["proposed_file_drafts"] = [draft]
    require(not module.validate_bundle_payload(unsafe).valid, "source_file_modified true was not rejected")


def check_risk_flags_and_source_restrictions() -> None:
    module = load_module()
    flags = module.risk_flags_for_text("powershell apply patch write memory token password delete files exfiltrate")
    for flag in ["powershell", "apply_patch", "write_memory", "token", "password", "delete_files", "exfiltrate"]:
        require(flag in flags, "risk flag missing: " + flag)
    try:
        module.resolve_plan_path(ROOT / "reports" / "code_companion_fix_candidates" / "examples" / "fix_candidate_example.json")
    except module.PatchBundleDraftError:
        pass
    else:
        raise CheckFailure("raw fix candidate path was accepted as a bundle input")
    for path in BUNDLE_ROOT.iterdir():
        if path.is_file():
            require(path.suffix.lower() not in {".patch", ".diff"}, "patch/diff output exists in live bundle root")


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_code_companion_patch_bundle_draft.py" in codex, "codex verifier missing patch bundle draft verifier")
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Patch Bundle Draft V1",
        "Patch bundle draft",
        "does not edit source",
        "does not apply patches",
        "proposed_files",
        "Packaging skipped",
        "Code Companion Phase 3 creates isolated patch bundle drafts only",
    ]:
        require(needle in report, "report missing: " + needle)


def main() -> int:
    checks = [
        ("phase2_present", check_phase2_present),
        ("files_and_folders", check_files_and_folders),
        ("static_source_safety", check_static_source_safety),
        ("runtime_create_validate", check_runtime_create_validate),
        ("invalid_plans_rejected", check_invalid_plans_rejected),
        ("bundle_validation_rejections", check_bundle_validation_rejections),
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
        print("\nEngel Code Companion Patch Bundle Draft verifier FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nEngel Code Companion Patch Bundle Draft verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
