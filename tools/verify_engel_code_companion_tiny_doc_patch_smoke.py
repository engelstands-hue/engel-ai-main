from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE7_MODULE = ROOT / "engel_code_companion_protected_patch_apply.py"
PHASE7_VERIFIER = ROOT / "tools" / "verify_engel_code_companion_protected_patch_apply.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_tiny_doc_patch_smoke.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_TINY_DOCUMENTATION_PATCH_APPLY_SMOKE.md"
TARGET_DOC = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_TINY_DOC_PATCH_SMOKE.md"
APPLY_ROOT = ROOT / "reports" / "code_companion_patch_applies"
APPLY_RECEIPTS = APPLY_ROOT / "receipts"
APPLY_BACKUPS = APPLY_ROOT / "backups"
APPLY_ROLLBACK = APPLY_ROOT / "rollback"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

BLOCKED_STATUS = "Phase 8 status: BLOCKED - NOT APPLIED"
SUCCESS_STATUS = "Phase 8 status: SUCCESS - DOCUMENTATION PATCH APPLIED"
APPLY_FINAL_DECISION = "PROTECTED PATCH APPLIED WITH HUMAN APPROVAL"
REFUSAL_FINAL_DECISION = "PROTECTED PATCH APPLY REFUSED"

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


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def check_required_files() -> None:
    for path in [PHASE7_MODULE, PHASE7_VERIFIER, VERIFIER, REPORT, APPLY_ROOT, APPLY_RECEIPTS, APPLY_BACKUPS, APPLY_ROLLBACK]:
        require(path.exists(), "missing required path: " + relative(path))


def check_static_safety() -> None:
    source = read(VERIFIER)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("verifier contains forbidden loop or async worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in FORBIDDEN_CALLS, "verifier contains forbidden call: " + name)


def receipt_json_files() -> list[Path]:
    return sorted(APPLY_RECEIPTS.glob("*.json"))


def phase8_receipt_files() -> list[Path]:
    matches: list[Path] = []
    target_name = TARGET_DOC.name.lower()
    for path in receipt_json_files():
        text = read(path).lower()
        if "tiny_doc_patch_smoke" in text or target_name in text or "phase 8" in text:
            matches.append(path)
    return matches


def load_json(path: Path) -> dict[str, object]:
    payload = json.loads(read(path))
    require(isinstance(payload, dict), "JSON root must be an object: " + relative(path))
    return payload


def check_report_common() -> str:
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Tiny Documentation Patch Apply Smoke",
        "Target documentation file",
        "Approval gate result",
        "Password/protected-action gate result",
        "Pre-apply verifier result",
        "Backup path",
        "Apply receipt path",
        "Rollback metadata path",
        "Post-apply verifier result",
        "Final full codex verifier result",
        "Safety boundaries preserved",
    ]:
        require(needle in report, "Phase 8 report missing: " + needle)
    require(BLOCKED_STATUS in report or SUCCESS_STATUS in report, "Phase 8 report must declare blocked or success status")
    return report


def check_blocked_report(report: str) -> None:
    require(BLOCKED_STATUS in report, "blocked report missing blocked status")
    for needle in [
        "Phase 7 protected apply path refused real apply readiness",
        "password/protected-action integration",
        "No documentation patch was applied",
        "Target file was not created",
        "Backup path: none",
        "Apply receipt path: none",
        "Rollback metadata path: none",
        "Post-apply verifier result: not reached because no apply occurred",
        "Full codex verifier result:",
    ]:
        require(needle in report, "blocked Phase 8 report missing: " + needle)
    require("ENGEL_CODEX_VERIFY_PASS" in report or "Pending final run" in report, "blocked Phase 8 report missing final or pending codex result")
    require(not TARGET_DOC.exists(), "blocked Phase 8 must not create target documentation file")
    require(not phase8_receipt_files(), "blocked Phase 8 must not leave a Phase 8 apply receipt")
    for folder in [APPLY_BACKUPS, APPLY_ROLLBACK]:
        for path in folder.rglob("*"):
            if path.name == ".gitkeep":
                continue
            text = str(path).lower()
            require("tiny_doc_patch_smoke" not in text and "phase8" not in text and "phase_8" not in text, "blocked Phase 8 left apply artifact: " + relative(path))


def check_success_report(report: str) -> None:
    require(SUCCESS_STATUS in report, "success report missing success status")
    require(TARGET_DOC.exists(), "success Phase 8 target documentation file is missing")
    require(TARGET_DOC.suffix.lower() == ".md", "target file must be markdown")
    require(TARGET_DOC.stat().st_size <= 5 * 1024, "target documentation file exceeds 5 KB")
    target = read(TARGET_DOC)
    for needle in [
        "# Engel Code Companion Tiny Documentation Patch Smoke",
        "documentation-only",
        "No source code behavior changed",
    ]:
        require(needle in target, "target documentation missing: " + needle)
    forbidden = ["```python", "```powershell", "```bash", "subprocess", "provider_call", "trusted memory write"]
    lowered = target.lower()
    for needle in forbidden:
        require(needle not in lowered, "target documentation contains forbidden executable/source marker: " + needle)

    receipts = phase8_receipt_files()
    require(receipts, "success Phase 8 must have an apply receipt")
    matching_receipts: list[Path] = []
    for path in receipts:
        payload = load_json(path)
        files_changed = payload.get("files_changed")
        files_text = json.dumps(files_changed, sort_keys=True)
        if TARGET_DOC.name in files_text:
            matching_receipts.append(path)
            require(payload.get("final_decision") == APPLY_FINAL_DECISION, "apply receipt final decision mismatch")
            require(payload.get("patch_applied") is True, "apply receipt must mark documentation patch applied")
            require(payload.get("safe_to_auto_apply") is False, "apply receipt must keep safe_to_auto_apply false")
            require(payload.get("auto_apply") is False, "apply receipt must keep auto_apply false")
            require(payload.get("trusted_memory_written") is False, "apply receipt must not write trusted memory")
            require(payload.get("routes_mutated") is False, "apply receipt must not mutate routes")
            require(payload.get("queues_mutated") is False, "apply receipt must not mutate queues")
            require(payload.get("provider_calls_made") is False, "apply receipt must not call providers")
            require(payload.get("approval_token_verified") is True, "apply receipt must record approval token verification")
            require(payload.get("password_gate_verified") is True, "apply receipt must record password gate verification")
            require(payload.get("pre_apply_verifier_passed") is True, "apply receipt must record pre-apply verifier pass")
            require(payload.get("post_apply_verifier_passed") is True, "apply receipt must record post-apply verifier pass")
    require(matching_receipts, "no apply receipt references the target documentation file")

    rollback_matches = [path for path in APPLY_ROLLBACK.glob("*.json") if TARGET_DOC.name in read(path)]
    require(rollback_matches, "success Phase 8 must have rollback metadata for the target")
    backup_matches = [path for path in APPLY_BACKUPS.rglob("*") if path.is_file() and path.name != ".gitkeep" and TARGET_DOC.name in str(path)]
    require(backup_matches, "success Phase 8 must have a target backup")


def check_codex_registration() -> None:
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_code_companion_tiny_doc_patch_smoke.py" in codex, "codex verifier missing Phase 8 verifier")


def check_phase7_still_safe() -> None:
    phase7 = read(PHASE7_MODULE)
    for needle in [
        "APPROVE_PRODUCT_PATCH",
        "run_code_companion_low_risk_patch_apply",
        "Protected password gate integration is required before real apply.",
        "safe_to_auto_apply",
        "trusted_memory_written",
        "routes_mutated",
        "queues_mutated",
        "provider_calls_made",
    ]:
        require(needle in phase7, "Phase 7 module missing safety text: " + needle)


def main() -> int:
    checks = [
        ("required_files", check_required_files),
        ("static_safety", check_static_safety),
        ("phase7_still_safe", check_phase7_still_safe),
        ("codex_registration", check_codex_registration),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS", name)
        except CheckFailure as exc:
            print("FAIL", name, "-", exc)
            failures.append(f"{name}: {exc}")
    try:
        report = check_report_common()
        if BLOCKED_STATUS in report:
            check_blocked_report(report)
            print("PASS blocked_smoke_honesty")
        else:
            check_success_report(report)
            print("PASS success_smoke_artifacts")
    except CheckFailure as exc:
        print("FAIL phase8_report_and_artifacts -", exc)
        failures.append(f"phase8_report_and_artifacts: {exc}")
    if failures:
        print("\nEngel Code Companion Tiny Documentation Patch Smoke verifier FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nEngel Code Companion Tiny Documentation Patch Smoke verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
