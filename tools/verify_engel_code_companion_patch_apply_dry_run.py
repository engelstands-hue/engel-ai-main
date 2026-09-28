from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_code_companion_patch_apply_dry_run.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_apply_dry_run.py"
PHASE1_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_fix_candidate_intake.py"
PHASE2_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_plan_preview.py"
PHASE3_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_bundle_draft.py"
PHASE4_MODULE = ROOT / "engel_code_companion_patch_application_gate.py"
PHASE4_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_application_gate.py"
PROTECTED_ACTION_VERIFIER = ROOT / "tools" / "verify_engel_protected_action_registry.py"
PASSWORD_GATE_VERIFIER = ROOT / "tools" / "verify_engel_global_password_gate.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_APPLY_DRY_RUN_V1.md"
DRY_RUN_ROOT = ROOT / "reports" / "code_companion_patch_apply_dry_runs"
DRY_RUN_EXAMPLES = DRY_RUN_ROOT / "examples"
DRY_RUN_RECEIPTS = DRY_RUN_ROOT / "receipts"
ROOT_SIMULATED_FILES = DRY_RUN_ROOT / "simulated_files"
ROOT_DIFF_PREVIEWS = DRY_RUN_ROOT / "diff_previews"
EXAMPLE_DRY_RUN = DRY_RUN_EXAMPLES / "patch_apply_dry_run_example.json"
BUNDLE_ROOT = ROOT / "reports" / "code_companion_patch_bundles"
BUNDLE_EXAMPLE = BUNDLE_ROOT / "examples" / "patch_bundle_draft_example.json"
GATE_RECEIPTS = ROOT / "reports" / "code_companion_patch_application_gates" / "receipts"
GATE_DRY_RUNS = ROOT / "reports" / "code_companion_patch_application_gates" / "dry_runs"
PLAN_EXAMPLE = ROOT / "reports" / "code_companion_patch_plans" / "examples" / "patch_plan_preview_example.json"
FIX_CANDIDATE_EXAMPLE = ROOT / "reports" / "code_companion_fix_candidates" / "examples" / "fix_candidate_example.json"

FINAL_DECISION = "PATCH APPLY DRY RUN ONLY — NOT APPLIED"
SIMULATED_FILE_BANNER = "PREVIEW ONLY — NOT APPLIED"
DIFF_PREVIEW_BANNER = "PREVIEW DIFF ONLY — NOT APPLY-READY"

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

REQUIRED_COMMANDS = [
    "code companion patch dry-run status",
    "code companion patch dry-run list",
    "code companion patch dry-run validate-input",
    "code companion patch dry-run simulate",
    "code companion patch dry-run show",
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
    spec = importlib.util.spec_from_file_location("engel_code_companion_patch_apply_dry_run", MODULE)
    require(spec is not None and spec.loader is not None, "could not load patch apply dry-run module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_patch_apply_dry_run"] = module
    spec.loader.exec_module(module)
    return module


def load_phase4_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_code_companion_patch_application_gate", PHASE4_MODULE)
    require(spec is not None and spec.loader is not None, "could not load patch application gate module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_patch_application_gate"] = module
    spec.loader.exec_module(module)
    return module


def check_phase4_present() -> None:
    for path in [PHASE1_VERIFIER, PHASE2_VERIFIER, PHASE3_VERIFIER, PHASE4_MODULE, PHASE4_VERIFIER, BUNDLE_EXAMPLE]:
        require(path.exists(), "Phase 5 dependency missing required path: " + str(path.relative_to(ROOT)))


def check_files_and_folders() -> None:
    for path in [MODULE, VERIFIER, REPORT, DRY_RUN_ROOT, DRY_RUN_EXAMPLES, DRY_RUN_RECEIPTS, ROOT_SIMULATED_FILES, ROOT_DIFF_PREVIEWS, EXAMPLE_DRY_RUN]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    payload = json.loads(read(EXAMPLE_DRY_RUN))
    require(payload.get("status") == "apply_dry_run_preview", "example dry-run status mismatch")
    require(payload.get("requires_review") is True, "example dry-run must require review")
    require(payload.get("safe_to_auto_apply") is False, "example dry-run must not auto-apply")
    require(payload.get("patch_applied") is False, "example dry-run must not be applied")
    require(payload.get("source_files_modified") is False, "example dry-run must not modify source")
    require(payload.get("application_enabled_in_this_phase") is False, "example dry-run must be disabled")
    require(payload.get("approval_token_required") is True, "example dry-run must require approval token")
    require(payload.get("password_gate_required") is True, "example dry-run must require password gate")
    require(payload.get("verifier_pass_required") is True, "example dry-run must require verifier")
    require(payload.get("final_decision") == FINAL_DECISION, "example dry-run final decision mismatch")


def check_static_source_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "resolve_dry_run_input",
        "BUNDLE_ROOT",
        "GATE_RECEIPTS",
        "apply_dry_run_preview",
        FINAL_DECISION,
        SIMULATED_FILE_BANNER,
        DIFF_PREVIEW_BANNER,
        "application_enabled_in_this_phase",
        "approval_token_present",
        "password_verified",
        "Patch application is not enabled in Phase 5.",
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


def check_runtime_simulate_from_bundle() -> None:
    module = load_module()
    module_hash_before = module.sha256_file(MODULE)
    with tempfile.TemporaryDirectory() as temp_name:
        temp_root = Path(temp_name)
        result = module.simulate(BUNDLE_EXAMPLE, root=temp_root, created_at="2026-05-17T00:00:00Z")
        folder = Path(result.dry_run_folder)
        dry_run_json = Path(result.dry_run_json)
        require(folder.exists() and folder.is_dir(), "dry-run folder was not written")
        require(dry_run_json.exists(), "dry_run.json was not written")
        require(folder.is_relative_to(temp_root), "dry-run folder escaped temp root")
        for required in [
            "README.md",
            "source_file_hashes.json",
            "simulated_change_summary.md",
            "diff_preview.md",
            "risk_review.md",
            "verification_plan.md",
        ]:
            require((folder / required).exists(), "dry-run folder missing " + required)
        simulated_root = folder / "simulated_files"
        require(simulated_root.exists() and simulated_root.is_dir(), "simulated_files folder missing")
        require(not list(folder.glob("*.patch")) and not list(folder.glob("*.diff")), "dry-run folder contains patch/diff apply files")

        dry_run = json.loads(read(dry_run_json))
        errors = module.validate_dry_run_payload(dry_run)
        require(not errors, "dry_run.json validation failed: " + "; ".join(errors))
        require(dry_run["created_by"] == "Engel Code Companion", "created_by mismatch")
        require(dry_run["trust_level"] == "untrusted_until_human_approved", "trust mismatch")
        require(dry_run["status"] == "apply_dry_run_preview", "status mismatch")
        require(dry_run["requires_review"] is True, "dry-run must require review")
        require(dry_run["safe_to_auto_apply"] is False, "dry-run must not auto-apply")
        require(dry_run["patch_applied"] is False, "dry-run must not be applied")
        require(dry_run["source_files_modified"] is False, "dry-run must not modify source")
        require(dry_run["application_enabled_in_this_phase"] is False, "dry-run must not enable application")
        require(dry_run["approval_token_required"] is True, "dry-run must require approval token")
        require(dry_run["approval_token_present"] is False, "dry-run must not collect token")
        require(dry_run["password_gate_required"] is True, "dry-run must require password gate")
        require(dry_run["password_verified"] is False, "dry-run must not verify password")
        require(dry_run["verifier_pass_required"] is True, "dry-run must require verifier")
        require(dry_run["human_review_required"] is True, "dry-run must require human review")
        require(dry_run["final_decision"] == FINAL_DECISION, "final decision mismatch")
        for action in REQUIRED_BLOCKED_ACTIONS:
            require(action in dry_run["blocked_actions"], "missing blocked action: " + action)
        hashes = json.loads(read(folder / "source_file_hashes.json"))
        require(hashes.get("source_files_modified") is False, "source hashes must state source was not modified")
        require(hashes.get("patch_applied") is False, "source hashes must state patch was not applied")
        for sim in dry_run["simulated_files"]:
            sim_path = ROOT / str(sim.get("simulated_file"))
            if not sim_path.exists():
                sim_path = folder / Path(str(sim.get("simulated_file"))).name
            require(sim_path.exists(), "simulated file missing")
            require(sim_path.suffix.lower() in {".md", ".txt"}, "simulated file must be .md/.txt")
            text = read(sim_path)
            require(SIMULATED_FILE_BANNER in text, "simulated file missing preview banner")
            require("source_file_modified: false" in text, "simulated file missing no-source-edit statement")
            require("patch_applied: false" in text, "simulated file missing no-patch statement")
        diff = read(folder / "diff_preview.md")
        require(DIFF_PREVIEW_BANNER in diff, "diff preview missing not apply-ready banner")
        require("apply command" in diff.lower(), "diff preview missing no-apply-command boundary")
        require("Verification commands listed here were not run by dry-run simulation." in read(folder / "verification_plan.md"), "verification plan missing not-run statement")
        require(FINAL_DECISION in read(folder / "README.md"), "README missing final decision")
        status = module.render_status(root=temp_root)
        listing = module.render_list(root=temp_root)
        require("patch_application_enabled: false" in status, "status missing disabled application flag")
        require("source_mutation_enabled: false" in status, "status missing source mutation disabled flag")
        require("Code Companion patch apply dry-run records:" in listing, "list missing dry-run heading")
    require(module.sha256_file(MODULE) == module_hash_before, "simulation changed source module")


def check_runtime_accepts_gate_receipt() -> None:
    module = load_module()
    phase4 = load_phase4_module()
    gate_result = None
    paths_to_delete: list[Path] = []
    try:
        gate_result = phase4.check_bundle(BUNDLE_EXAMPLE, receipts_dir=GATE_RECEIPTS, created_at="2026-05-17T00:00:01Z")
        gate_json = Path(gate_result.gate_json)
        gate_md = Path(gate_result.gate_markdown)
        paths_to_delete.extend([gate_json, gate_md])
        validation = module.validate_input(gate_json)
        require(validation.valid, "valid Phase 4 gate receipt was rejected: " + "; ".join(validation.errors))
        with tempfile.TemporaryDirectory() as temp_name:
            result = module.simulate(gate_json, root=Path(temp_name), created_at="2026-05-17T00:00:02Z")
            dry_run = json.loads(read(Path(result.dry_run_json)))
            require(dry_run.get("source_gate_id") == gate_result.gate.get("gate_id"), "source gate id was not carried into dry-run")
            require(dry_run.get("source_gate_path") == module.project_relative(gate_json), "source gate path mismatch")
            require(dry_run.get("patch_applied") is False, "gate-based dry-run must not apply")
    finally:
        for path in paths_to_delete:
            if path.exists():
                path.unlink()


def write_temp_bundle(payload: dict[str, object], name: str) -> Path:
    path = BUNDLE_EXAMPLE.parent / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def check_invalid_inputs_rejected() -> None:
    module = load_module()
    base = json.loads(read(BUNDLE_EXAMPLE))
    temp_paths: list[Path] = []
    try:
        cases = [
            ("safe_to_auto_apply", True, "verifier_apply_invalid_safe_to_auto_apply_bundle.json"),
            ("requires_review", False, "verifier_apply_invalid_requires_review_bundle.json"),
            ("patch_applied", True, "verifier_apply_invalid_patch_applied_bundle.json"),
            ("source_files_modified", True, "verifier_apply_invalid_source_modified_bundle.json"),
        ]
        for field, value, name in cases:
            payload = dict(base)
            payload[field] = value
            path = write_temp_bundle(payload, name)
            temp_paths.append(path)
            result = module.validate_input(path)
            require(not result.valid, f"invalid bundle with {field}={value!r} was accepted")

        phase4 = load_phase4_module()
        gate = phase4.build_gate_payload(BUNDLE_EXAMPLE, base, created_at="2026-05-17T00:00:03Z")
        gate["application_enabled_in_this_phase"] = True
        gate_path = GATE_RECEIPTS / "verifier_apply_invalid_application_enabled_gate.json"
        gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_paths.append(gate_path)
        result = module.validate_input(gate_path)
        require(not result.valid, "gate with application_enabled_in_this_phase true was accepted")

        for bad_path in [PLAN_EXAMPLE, FIX_CANDIDATE_EXAMPLE, ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_APPLY_DRY_RUN_V1.md"]:
            result = module.validate_input(bad_path)
            require(not result.valid, "disallowed input was accepted: " + str(bad_path.relative_to(ROOT)))
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()


def check_risk_flags_and_source_restrictions() -> None:
    module = load_module()
    flags = module.risk_flags_for_text("powershell run this command apply patch write memory token password chmod firewall exfiltrate")
    for flag in ["powershell", "run_this_command", "apply_patch", "write_memory", "token", "password", "chmod", "firewall", "exfiltrate"]:
        require(flag in flags, "risk flag missing: " + flag)
    for root in [DRY_RUN_ROOT, DRY_RUN_RECEIPTS, ROOT_SIMULATED_FILES, ROOT_DIFF_PREVIEWS]:
        if not root.exists():
            continue
        for path in root.iterdir():
            if path.is_file():
                require(path.suffix.lower() not in {".patch", ".diff"}, "patch/diff output exists in dry-run folder: " + str(path.relative_to(ROOT)))


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
    require("tools\\verify_engel_code_companion_patch_apply_dry_run.py" in codex, "codex verifier missing patch apply dry-run verifier")
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Patch Apply Dry-Run V1",
        "does not edit source",
        "does not apply patches",
        "Phase 4 gate",
        "simulated files are isolated under reports",
        "not apply-ready",
        "Packaging skipped",
        "Code Companion Phase 5 simulates patch application in reports-only dry-run folders",
    ]:
        require(needle in report, "report missing: " + needle)


def main() -> int:
    checks = [
        ("phase4_present", check_phase4_present),
        ("files_and_folders", check_files_and_folders),
        ("static_source_safety", check_static_source_safety),
        ("runtime_simulate_from_bundle", check_runtime_simulate_from_bundle),
        ("runtime_accepts_gate_receipt", check_runtime_accepts_gate_receipt),
        ("invalid_inputs_rejected", check_invalid_inputs_rejected),
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
        print("\nEngel Code Companion Patch Apply Dry-Run verifier FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nEngel Code Companion Patch Apply Dry-Run verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
