#!/usr/bin/env python3
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "engel_debruijn_quantum_apply.py"
ENGEL_APP = ROOT / "engel_app.py"
ROUTE_METADATA = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
PASSWORD_GATE = ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json"
APPLY_RECEIPT_DIR = ROOT / "reports" / "debruijn_quantum_apply_receipts"
PROPOSAL_DIR = ROOT / "reports" / "debruijn_quantum_file_structure"

PASS_MARKER = "DEBRUIJN_QUANTUM_APPLY_ENGINE_VERIFICATION_PASS"

ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "argparse",
    "hashlib",
    "json",
    "sys",
    "dataclasses",
    "datetime",
    "pathlib",
    "typing",
}

FORBIDDEN_IMPORT_ROOTS = {
    "subprocess",
    "socket",
    "urllib",
    "requests",
    "http",
    "ftplib",
    "smtplib",
    "openai",
    "anthropic",
    "llama_cpp",
    "torch",
    "tensorflow",
    "tkinter",
    "PyQt5",
    "PyQt6",
    "shutil",
}

REQUIRED_DATACLASSES = [
    "ProposalValidationResult",
    "ApplyPlan",
    "ApplyResult",
]

REQUIRED_FUNCTIONS = [
    "load_proposal",
    "validate_proposal",
    "build_apply_plan",
    "write_apply_receipt",
    "validate_only",
    "dry_run_apply_plan",
    "status_payload",
    "main",
]

REQUIRED_RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_proposal_path",
    "proposal_id",
    "proposal_hash",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "pre_apply_verifier_results",
    "files_read",
    "files_changed",
    "files_not_changed",
    "target_paths_validated",
    "forbidden_actions_not_performed",
    "post_apply_verifier_results",
    "rollback_note",
    "final_status",
    "human_review_required",
]

PROTECTED_FILES = [
    MODULE_PATH,
    ENGEL_APP,
    ROUTE_METADATA,
    PASSWORD_GATE,
]


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def pass_(self, message: str) -> None:
        print(f"PASS {message}")

    def info(self, message: str) -> None:
        print(f"INFO {message}")

    def fail(self, message: str) -> None:
        self.failures.append(message)
        print(f"FAIL {message}")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(paths: list[Path]) -> dict[str, tuple[bool, str]]:
    result: dict[str, tuple[bool, str]] = {}
    for path in paths:
        if path.exists() and path.is_file():
            result[str(path)] = (True, file_hash(path))
        else:
            result[str(path)] = (False, "")
    return result


def compare_snapshot(before: dict[str, tuple[bool, str]], check: Check) -> None:
    for raw, previous in before.items():
        path = Path(raw)
        current = (path.exists() and path.is_file(), file_hash(path) if path.exists() and path.is_file() else "")
        if current != previous:
            check.fail(f"protected file changed during apply verifier smoke: {path}")
    if not check.failures:
        check.pass_("protected source/route/password files unchanged during smoke")


def read_source(check: Check) -> str:
    if not MODULE_PATH.exists():
        check.fail(f"missing apply module: {MODULE_PATH}")
        return ""
    text = MODULE_PATH.read_text(encoding="utf-8")
    check.pass_("apply module exists")
    return text


def parse_module(source: str, check: Check) -> ast.Module | None:
    try:
        tree = ast.parse(source, filename=str(MODULE_PATH))
    except SyntaxError as exc:
        check.fail(f"apply module syntax error: {exc}")
        return None
    check.pass_("apply module parses")
    return tree


def check_imports(tree: ast.Module, check: Check) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    check.fail(f"forbidden import: {alias.name}")
                elif root not in ALLOWED_IMPORT_ROOTS:
                    check.fail(f"non-stdlib-or-unexpected import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                check.fail(f"forbidden import: {node.module}")
            elif root not in ALLOWED_IMPORT_ROOTS:
                check.fail(f"non-stdlib-or-unexpected import: {node.module}")
    if not check.failures:
        check.pass_("imports are standard-library only and no provider/network/model/gui imports found")


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def check_forbidden_calls(tree: ast.Module, check: Check) -> None:
    forbidden_exact = {
        "eval",
        "exec",
        "compile",
        "os.system",
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
    }
    forbidden_attrs = {"unlink", "rmdir", "rename", "replace", "chmod"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = call_name(node.func)
            if name in forbidden_exact:
                check.fail(f"forbidden call: {name}")
            if any(name.endswith(f".{attr}") for attr in forbidden_attrs):
                check.fail(f"forbidden filesystem mutation call: {name}")
    if not check.failures:
        check.pass_("no command execution, destructive filesystem, git, build, or package calls detected")


def check_symbols(tree: ast.Module, check: Check) -> None:
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for name in REQUIRED_DATACLASSES:
        if name not in classes:
            check.fail(f"missing dataclass/model: {name}")
    for name in REQUIRED_FUNCTIONS:
        if name not in functions:
            check.fail(f"missing function: {name}")
    if all(name in classes for name in REQUIRED_DATACLASSES) and all(name in functions for name in REQUIRED_FUNCTIONS):
        check.pass_("required data models and apply helper functions exist")


def check_source_boundaries(source: str, check: Check) -> None:
    lowered = source.lower()
    required_literals = [
        "actual_apply_enabled = false",
        "command_route_added = false",
        "trusted_memory_write_enabled = false",
        "build_promote_enabled = false",
        "not_required_for_validate_or_dry_run",
        "dry_run_apply_plan",
    ]
    for literal in required_literals:
        if literal not in lowered:
            check.fail(f"missing safety literal: {literal}")
    if "add_parser(\"apply\")" in lowered or "add_parser('apply')" in lowered:
        check.fail("real apply CLI command must not be implemented in V1")
    if not check.failures:
        check.pass_("actual apply, route, trusted-memory, and build/promote flags remain disabled")


def check_no_engel_route(check: Check) -> None:
    if not ENGEL_APP.exists():
        check.fail("engel_app.py missing")
        return
    text = ENGEL_APP.read_text(encoding="utf-8", errors="ignore").lower()
    route_terms = [
        "engel ai debruijn quantum apply",
        "approve_debruijn_quantum_apply_verified_proposal_v1",
    ]
    hits = [term for term in route_terms if term in text]
    if hits:
        check.fail(f"apply command route appears present in engel_app.py: {hits}")
    else:
        check.pass_("no De Bruijn apply route added to engel_app.py")


def import_apply_module(check: Check) -> Any | None:
    spec = importlib.util.spec_from_file_location("engel_debruijn_quantum_apply_verify_target", MODULE_PATH)
    if spec is None or spec.loader is None:
        check.fail("could not build import spec for apply module")
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - verifier reports import failure safely.
        check.fail(f"apply module import failed: {exc}")
        return None
    check.pass_("apply module imports without side effects")
    return module


def latest_candidate_proposal() -> Path | None:
    if not PROPOSAL_DIR.exists():
        return None
    proposals = sorted(PROPOSAL_DIR.glob("candidate_fix_proposals_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return proposals[0] if proposals else None


def receipt_listing() -> set[Path]:
    if not APPLY_RECEIPT_DIR.exists():
        return set()
    return {path.resolve() for path in APPLY_RECEIPT_DIR.glob("*") if path.is_file()}


def run_cli_main(module: Any, args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            result = module.main(args)
            code = int(result) if result is not None else 0
        except SystemExit as exc:
            code = int(exc.code) if isinstance(exc.code, int) else 1
    return code, stdout.getvalue(), stderr.getvalue()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_receipt(path: Path, check: Check) -> None:
    payload = load_json(path)
    for field in REQUIRED_RECEIPT_FIELDS:
        if field not in payload:
            check.fail(f"dry-run receipt missing field {field}: {path}")
    if payload.get("engine_id") != "debruijn_quantum_apply_engine":
        check.fail("dry-run receipt engine_id mismatch")
    if payload.get("action_type") != "dry_run_apply_plan":
        check.fail("dry-run receipt action_type mismatch")
    if payload.get("approval_detected") is not False:
        check.fail("dry-run receipt must not detect approval")
    if payload.get("password_gate_result") != "not_required_for_validate_or_dry_run":
        check.fail("dry-run receipt password gate result must be dry-run/not-required")
    if payload.get("files_changed") != []:
        check.fail("dry-run receipt files_changed must be empty")
    if payload.get("human_review_required") is not True:
        check.fail("dry-run receipt must keep human_review_required true")
    raw = path.read_text(encoding="utf-8", errors="ignore").lower()
    for secret in ("password_hash", "password_salt", "salt:", "password:"):
        if secret in raw:
            check.fail(f"receipt may expose secret marker {secret}: {path}")
    if not check.failures:
        check.pass_(f"dry-run receipt validated: {path}")


def run_smoke(module: Any, check: Check) -> None:
    proposal = latest_candidate_proposal()
    if proposal is None:
        check.fail("no candidate proposal available for apply verifier smoke")
        return
    before_receipts = receipt_listing()
    before_protected = snapshot(PROTECTED_FILES)

    code, stdout, stderr = run_cli_main(module, ["status"])
    if code != 0:
        check.fail(f"status CLI failed with {code}: {stderr.strip()}")
    elif receipt_listing() != before_receipts:
        check.fail("status CLI wrote files")
    elif "actual_apply_enabled" in stdout and "false" in stdout.lower():
        check.pass_("status CLI is read-only and reports actual apply disabled")
    else:
        check.fail("status CLI output did not confirm disabled apply state")

    code, stdout, stderr = run_cli_main(module, ["validate", str(proposal)])
    if code != 0:
        check.fail(f"validate CLI failed with {code}: {stderr.strip()}")
    else:
        data = json.loads(stdout)
        if data.get("valid_structure") is not True:
            check.fail("validate CLI did not recognize candidate proposal structure")
        elif data.get("eligible_for_apply_attempt") is not False:
            check.fail("unverified candidate must not be eligible for apply attempt")
        elif data.get("verified_for_apply") is not False:
            check.fail("sample candidate should remain unverified for apply")
        else:
            check.pass_("validate CLI accepts structure but keeps unverified proposal ineligible")

    before_dry_run = receipt_listing()
    code, stdout, stderr = run_cli_main(module, ["dry-run", str(proposal)])
    if code != 0:
        check.fail(f"dry-run CLI failed with {code}: {stderr.strip()}")
    else:
        payload = json.loads(stdout)
        validation = payload.get("validation", {})
        plan = payload.get("plan", {})
        receipt_paths = payload.get("receipt_paths", [])
        if validation.get("eligible_for_apply_attempt") is not False:
            check.fail("dry-run made unverified proposal eligible")
        if plan.get("apply_enabled") is not False or plan.get("dry_run_only") is not True:
            check.fail("dry-run plan must keep apply disabled and dry_run_only true")
        if not receipt_paths:
            check.fail("dry-run did not report receipt paths")
        new_receipts = receipt_listing() - before_dry_run
        if not new_receipts:
            check.fail("dry-run did not write receipt files")
        for receipt in sorted(new_receipts):
            if receipt.suffix == ".json":
                check_receipt(receipt, check)
            if not str(receipt).startswith(str(APPLY_RECEIPT_DIR.resolve())):
                check.fail(f"dry-run wrote outside apply receipt folder: {receipt}")
        if new_receipts and all(str(path).startswith(str(APPLY_RECEIPT_DIR.resolve())) for path in new_receipts):
            check.pass_("dry-run wrote only apply receipt folder files")

    code, _, _ = run_cli_main(module, ["apply", str(proposal)])
    if code == 0:
        check.fail("apply CLI command unexpectedly succeeded")
    else:
        check.pass_("real apply CLI command is absent/rejected")

    compare_snapshot(before_protected, check)


def main() -> int:
    check = Check()
    source = read_source(check)
    tree = parse_module(source, check) if source else None
    if tree is not None:
        check_imports(tree, check)
        check_forbidden_calls(tree, check)
        check_symbols(tree, check)
        check_source_boundaries(source, check)
    check_no_engel_route(check)
    module = import_apply_module(check)
    if module is not None:
        run_smoke(module, check)

    if check.failures:
        print(f"FAIL apply engine verification failed with {len(check.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
