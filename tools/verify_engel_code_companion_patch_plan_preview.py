from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_code_companion_patch_plan_preview.py"
PHASE1_MODULE = ROOT / "engel_code_companion_fix_candidate_intake.py"
PHASE1_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_fix_candidate_intake.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_plan_preview.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_PLAN_PREVIEW_V1.md"
PLAN_DIR = ROOT / "reports" / "code_companion_patch_plans"
PLAN_EXAMPLES = PLAN_DIR / "examples"
PLAN_RECEIPTS = PLAN_DIR / "receipts"
EXAMPLE_PLAN = PLAN_EXAMPLES / "patch_plan_preview_example.json"
CANDIDATE_EXAMPLE = ROOT / "reports" / "code_companion_fix_candidates" / "examples" / "fix_candidate_example.json"

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
    "unlink",
    "remove",
    "rename",
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
    "code companion patch plan status",
    "code companion patch plan list",
    "code companion patch plan validate",
    "code companion patch plan create",
    "code companion patch plan show",
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
    spec = importlib.util.spec_from_file_location("engel_code_companion_patch_plan_preview", MODULE)
    require(spec is not None and spec.loader is not None, "could not load patch plan preview module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_patch_plan_preview"] = module
    spec.loader.exec_module(module)
    return module


def check_phase1_present() -> None:
    for path in [PHASE1_MODULE, PHASE1_VERIFIER, CANDIDATE_EXAMPLE]:
        require(path.exists(), "Phase 1 missing required path: " + str(path.relative_to(ROOT)))


def check_files_and_folders() -> None:
    for path in [MODULE, VERIFIER, REPORT, PLAN_DIR, PLAN_EXAMPLES, PLAN_RECEIPTS, EXAMPLE_PLAN]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    payload = json.loads(read(EXAMPLE_PLAN))
    require(payload.get("status") == "draft_plan_preview", "example plan status mismatch")
    require(payload.get("requires_review") is True, "example plan must require review")
    require(payload.get("safe_to_auto_apply") is False, "example plan must not auto-apply")
    require(payload.get("patch_applied") is False, "example plan must not be applied")


def check_static_source_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "resolve_candidate_path",
        "FIX_CANDIDATE_ROOT",
        "draft_plan_preview",
        "safe_to_auto_apply",
        "patch_applied",
        "No source files were modified",
        "PATCH PLAN PREVIEW ONLY",
        "required_approvals_before_apply",
    ]:
        require(needle in source, "module missing required boundary text: " + needle)
    for forbidden in ["requests.", "socket.", "webbrowser", "openai", "anthropic", "subprocess."]:
        require(forbidden not in source.lower(), "module contains forbidden execution/provider text: " + forbidden)
    require(".patch" not in source and ".diff" not in source, "module must not create patch/diff output files")
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
        plan_dir = temp_root / "plans"
        receipt_dir = temp_root / "receipts"
        result = module.create_patch_plan_preview(
            CANDIDATE_EXAMPLE,
            plan_dir=plan_dir,
            receipt_dir=receipt_dir,
            created_at="2026-05-16T00:00:00Z",
        )
        plan_path = Path(result.plan_path)
        receipt_path = Path(result.receipt_path)
        require(plan_path.exists(), "plan preview was not written")
        require(receipt_path.exists(), "receipt was not written")
        require(plan_path.is_relative_to(plan_dir), "plan escaped temp plan dir")
        require(receipt_path.is_relative_to(receipt_dir), "receipt escaped temp receipt dir")
        require(plan_path.suffix == ".json", "plan must be JSON")
        require(receipt_path.suffix == ".md", "receipt must be markdown")

        plan = json.loads(read(plan_path))
        validation = module.validate_plan_payload(plan)
        require(validation.valid, "generated plan did not validate: " + "; ".join(validation.errors))
        require(plan["created_by"] == "Engel Code Companion", "created_by mismatch")
        require(plan["trust_level"] == "untrusted_until_human_review", "trust level mismatch")
        require(plan["status"] == "draft_plan_preview", "status mismatch")
        require(plan["requires_review"] is True, "plan must require review")
        require(plan["safe_to_auto_apply"] is False, "plan must not auto-apply")
        require(plan["patch_applied"] is False, "plan must not be applied")
        for action in REQUIRED_BLOCKED_ACTIONS:
            require(action in plan["blocked_actions"], "missing blocked action: " + action)
        for approval in REQUIRED_APPROVALS:
            require(approval in plan["required_approvals_before_apply"], "missing approval: " + approval)
        for command in plan["verification_plan"]:
            require(command.get("manual_only") is True, "verification commands must be manual only")

        receipt = read(receipt_path)
        require("PATCH PLAN PREVIEW ONLY" in receipt, "receipt missing preview-only decision")
        require("No source files were modified." in receipt, "receipt missing no-source-edit statement")
        require("No patch was applied." in receipt, "receipt missing no-patch statement")
        require("No commands from the candidate were executed." in receipt, "receipt missing no-command statement")
        require(len(receipt) < 12000, "receipt is not bounded")

        status = module.render_status(plan_dir=plan_dir, receipt_dir=receipt_dir)
        listing = module.render_list(plan_dir=plan_dir)
        require("No patch apply" in status, "status missing preview safety boundary")
        require("Code Companion patch plan previews:" in listing, "list missing created plan")


def write_temp_candidate(payload: dict[str, object], name: str) -> Path:
    path = CANDIDATE_EXAMPLE.parent / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def check_invalid_candidates_rejected() -> None:
    module = load_module()
    base = json.loads(read(CANDIDATE_EXAMPLE))
    temp_paths: list[Path] = []
    try:
        for field, value, name in [
            ("safe_to_auto_apply", True, "verifier_invalid_safe_to_auto_apply_candidate.json"),
            ("requires_review", False, "verifier_invalid_requires_review_candidate.json"),
            ("patch_applied", True, "verifier_invalid_patch_applied_candidate.json"),
        ]:
            payload = dict(base)
            payload[field] = value
            path = write_temp_candidate(payload, name)
            temp_paths.append(path)
            with tempfile.TemporaryDirectory() as temp_name:
                try:
                    module.create_patch_plan_preview(path, plan_dir=Path(temp_name) / "plans", receipt_dir=Path(temp_name) / "receipts")
                except module.PatchPlanPreviewError:
                    pass
                else:
                    raise CheckFailure(f"invalid candidate with {field}={value!r} was accepted")
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()


def check_plan_validation_rejections() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as temp_name:
        result = module.create_patch_plan_preview(
            CANDIDATE_EXAMPLE,
            plan_dir=Path(temp_name) / "plans",
            receipt_dir=Path(temp_name) / "receipts",
            created_at="2026-05-16T00:00:00Z",
        )
        plan = json.loads(read(Path(result.plan_path)))
    unsafe = dict(plan)
    unsafe["safe_to_auto_apply"] = True
    require(not module.validate_plan_payload(unsafe).valid, "safe_to_auto_apply true was not rejected")
    unsafe = dict(plan)
    unsafe["patch_applied"] = True
    require(not module.validate_plan_payload(unsafe).valid, "patch_applied true was not rejected")
    unsafe = dict(plan)
    unsafe["requires_review"] = False
    require(not module.validate_plan_payload(unsafe).valid, "requires_review false was not rejected")
    for bad_status in ["applied", "trusted", "complete", "completed"]:
        unsafe = dict(plan)
        unsafe["status"] = bad_status
        require(not module.validate_plan_payload(unsafe).valid, "bad status was not rejected: " + bad_status)
    unsafe = dict(plan)
    unsafe["blocked_actions"] = [item for item in plan["blocked_actions"] if item != "apply_patch"]
    require(not module.validate_plan_payload(unsafe).valid, "missing blocked action was not rejected")
    unsafe = dict(plan)
    unsafe["required_approvals_before_apply"] = [item for item in plan["required_approvals_before_apply"] if item != "approval_token"]
    require(not module.validate_plan_payload(unsafe).valid, "missing required approval was not rejected")
    unsafe = dict(plan)
    unsafe["verification_plan"] = [dict(plan["verification_plan"][0], already_run=True)]
    require(not module.validate_plan_payload(unsafe).valid, "already_run verification command was not rejected")


def check_risk_flags_and_source_restrictions() -> None:
    module = load_module()
    flags = module.risk_flags_for_text("powershell apply patch write memory token password delete files exfiltrate")
    for flag in ["powershell", "apply_patch", "write_memory", "token", "password", "delete_files", "exfiltrate"]:
        require(flag in flags, "risk flag missing: " + flag)
    try:
        module.resolve_candidate_path(ROOT / "reports" / "remote_worker_results" / ".gitkeep")
    except module.PatchPlanPreviewError:
        pass
    else:
        raise CheckFailure("raw report/result path was accepted as a patch plan input")
    for path in PLAN_DIR.glob("*"):
        require(path.suffix.lower() not in {".patch", ".diff"}, "patch/diff output exists in live plan folder")


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_code_companion_patch_plan_preview.py" in codex, "codex verifier missing patch plan preview verifier")
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Patch Plan Preview V1",
        "Patch plan preview",
        "does not edit source",
        "does not apply patches",
        "Packaging skipped",
        "Code Companion Phase 2 creates human-reviewable patch plan previews only",
    ]:
        require(needle in report, "report missing: " + needle)


def main() -> int:
    checks = [
        ("phase1_present", check_phase1_present),
        ("files_and_folders", check_files_and_folders),
        ("static_source_safety", check_static_source_safety),
        ("runtime_create_validate", check_runtime_create_validate),
        ("invalid_candidates_rejected", check_invalid_candidates_rejected),
        ("plan_validation_rejections", check_plan_validation_rejections),
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
        print("\nEngel Code Companion Patch Plan Preview verifier FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nEngel Code Companion Patch Plan Preview verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

