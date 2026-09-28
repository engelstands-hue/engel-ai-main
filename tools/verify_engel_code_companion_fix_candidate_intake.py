from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_code_companion_fix_candidate_intake.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_fix_candidate_intake.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_FIX_CANDIDATE_INTAKE_V1.md"
CANDIDATE_DIR = ROOT / "reports" / "code_companion_fix_candidates"
EXAMPLES_DIR = CANDIDATE_DIR / "examples"
RECEIPTS_DIR = CANDIDATE_DIR / "receipts"
EXAMPLE = EXAMPLES_DIR / "fix_candidate_example.json"

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
    "rglob",
    "walk",
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

REQUIRED_COMMANDS = [
    "code companion fix candidate status",
    "code companion fix candidate list",
    "code companion fix candidate validate",
    "code companion fix candidate intake",
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
    spec = importlib.util.spec_from_file_location("engel_code_companion_fix_candidate_intake", MODULE)
    require(spec is not None and spec.loader is not None, "could not load intake module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_fix_candidate_intake"] = module
    spec.loader.exec_module(module)
    return module


def check_files_and_folders() -> None:
    for path in [MODULE, VERIFIER, REPORT, CANDIDATE_DIR, EXAMPLES_DIR, RECEIPTS_DIR, EXAMPLE]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    payload = json.loads(read(EXAMPLE))
    require(payload.get("safe_to_auto_apply") is False, "example candidate must not auto-apply")
    require(payload.get("requires_review") is True, "example candidate must require review")
    require(payload.get("patch_applied") is False, "example candidate must not be marked applied")


def check_static_source_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "ALLOWED_SOURCE_ROOTS",
        "MAX_SOURCE_BYTES",
        "REQUIRED_BLOCKED_ACTIONS",
        "safe_to_auto_apply",
        "patch_applied",
        "untrusted_until_human_review",
        "UNTRUSTED FIX CANDIDATE DRAFT ONLY - NOT APPLIED",
    ]:
        require(needle in source, "module missing required boundary text: " + needle)
    for forbidden in ["os.system", "subprocess", "requests.", "urllib", "socket.", "webbrowser", "openai", "anthropic"]:
        require(forbidden not in source.lower(), "module contains forbidden provider/network/execution text: " + forbidden)
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


def check_runtime_intake_and_validation() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as temp_name:
        temp_root = Path(temp_name)
        candidate_dir = temp_root / "candidates"
        receipt_dir = temp_root / "receipts"
        result = module.intake_source_file(
            REPORT,
            candidate_dir=candidate_dir,
            receipt_dir=receipt_dir,
            created_at="2026-05-16T00:00:00Z",
        )
        candidate_path = Path(result.candidate_path)
        receipt_path = Path(result.receipt_path)
        require(candidate_path.exists(), "candidate was not written")
        require(receipt_path.exists(), "receipt was not written")
        require(candidate_path.is_relative_to(candidate_dir), "candidate escaped temp candidate dir")
        require(receipt_path.is_relative_to(receipt_dir), "receipt escaped temp receipt dir")

        payload = json.loads(read(candidate_path))
        validation = module.validate_candidate_payload(payload)
        require(validation.valid, "generated candidate did not validate: " + "; ".join(validation.errors))
        require(payload["created_by"] == "Engel Code Companion", "created_by mismatch")
        require(payload["trust_level"] == "untrusted_until_human_review", "trust level mismatch")
        require(payload["requires_review"] is True, "candidate must require review")
        require(payload["safe_to_auto_apply"] is False, "candidate must not auto-apply")
        require(payload["patch_applied"] is False, "candidate must not be applied")
        for action in REQUIRED_BLOCKED_ACTIONS:
            require(action in payload["blocked_actions"], "candidate missing blocked action: " + action)
        require(len(payload["problem_summary"]) <= module.MAX_SUMMARY_CHARS + 20, "problem summary is not bounded")
        receipt = read(receipt_path)
        require("No patch was applied" in receipt, "receipt missing no-patch boundary")
        require("No source, route, queue, or trusted memory was mutated" in receipt, "receipt missing mutation boundary")

        unsafe = dict(payload)
        unsafe["safe_to_auto_apply"] = True
        require(not module.validate_candidate_payload(unsafe).valid, "safe_to_auto_apply true was not rejected")
        unsafe = dict(payload)
        unsafe["requires_review"] = False
        require(not module.validate_candidate_payload(unsafe).valid, "requires_review false was not rejected")
        unsafe = dict(payload)
        unsafe["patch_applied"] = True
        require(not module.validate_candidate_payload(unsafe).valid, "patch_applied true was not rejected")
        unsafe = dict(payload)
        unsafe["blocked_actions"] = [item for item in payload["blocked_actions"] if item != "apply_patch"]
        require(not module.validate_candidate_payload(unsafe).valid, "missing blocked action was not rejected")

        status = module.render_status(candidate_dir=candidate_dir, receipts_dir=receipt_dir)
        listing = module.render_list(candidate_dir=candidate_dir)
        require("No patch apply" in status, "status missing safety boundary")
        require("Code Companion fix candidate files:" in listing, "list output missing candidate")

        flags = module.risk_flags_for_text("run this command in powershell, apply patch, write memory, token password")
        for flag in ["run_this_command", "powershell", "apply_patch", "write_memory", "token", "password"]:
            require(flag in flags, "risk flag missing: " + flag)


def check_source_restrictions() -> None:
    module = load_module()
    try:
        module.resolve_source_path(ROOT / "memory" / "ENGEL_COMMANDS.md")
    except module.FixCandidateIntakeError:
        pass
    else:
        raise CheckFailure("source outside allowed report roots was accepted")


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_code_companion_fix_candidate_intake.py" in codex, "codex verifier missing Code Companion intake verifier")
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Fix Candidate Intake V1",
        "untrusted fix candidate",
        "Packaging skipped",
        "No patches are applied",
        "No source, route, queue, or trusted-memory mutation",
    ]:
        require(needle in report, "report missing: " + needle)


def main() -> int:
    checks = [
        ("files_and_folders", check_files_and_folders),
        ("static_source_safety", check_static_source_safety),
        ("runtime_intake_and_validation", check_runtime_intake_and_validation),
        ("source_restrictions", check_source_restrictions),
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
        print("\nEngel Code Companion Fix Candidate Intake verifier FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nEngel Code Companion Fix Candidate Intake verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
