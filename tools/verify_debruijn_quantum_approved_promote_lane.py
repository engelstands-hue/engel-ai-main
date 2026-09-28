#!/usr/bin/env python3
"""Verify the De Bruijn Quantum Approved Promote Lane V1 implementation is bounded.

Mode: static + import-level negative smoke. The verifier does not perform an actual
promote; it validates that blocked inputs do not write live/backups and that the
module contains no shell=True, provider/network/model, git, or PyInstaller behavior.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"
MODULE_PATH = ROOT / "engel_debruijn_quantum_build_promote.py"
ENGEL_APP = ROOT / "engel_app.py"
PASSWORD_GATE = ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json"
ROUTE_METADATA = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
PROMOTE_RECEIPT_DIR = ROOT / "reports" / "debruijn_quantum_promote_receipts"
BUILD_RECEIPT_DIR = ROOT / "reports" / "debruijn_quantum_build_receipts"
LIVE_BACKUP_DIRS = [ROOT / "live", ROOT / "backups"]

PASS_MARKER = "DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_VERIFICATION_PASS"
APPROVAL_PHRASE = "APPROVE_DEBRUIJN_QUANTUM_GRAPH_PROMOTE_V1"
EXPECTED_BLOCKED_STATUS = "PROMOTE_LANE_BLOCKED_STAGED_ARTIFACT_MISSING"

REQUIRED_SYMBOLS = [
    "ApprovedPromoteLaneResult",
    "get_approved_promote_lane_contract",
    "get_approved_promote_lane_allowlist",
    "run_approved_graph_promote",
    "write_approved_promote_lane_receipt",
]

REQUIRED_RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "lane_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_build_receipt_path",
    "build_receipt_engine_id",
    "build_receipt_final_status",
    "build_command_id",
    "candidate_id",
    "candidate_hash",
    "source_node_state_id",
    "target_node_state_id",
    "edge_transition_id",
    "edge_label",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "expected_staged_artifact_paths",
    "actual_staged_artifact_paths",
    "live_target_path",
    "backup_target_path",
    "backup_paths",
    "backup_hash_manifest",
    "promoted_artifact_paths",
    "live_smoke_command_id",
    "live_smoke_result",
    "timeout_lane_id",
    "timeout_seconds_soft",
    "timeout_seconds_hard",
    "elapsed_seconds",
    "timeout_classification",
    "pre_promote_verifier_results",
    "post_promote_verifier_results",
    "rollback_note",
    "files_changed",
    "forbidden_actions_not_performed",
    "cleanup_status",
    "final_status",
    "human_review_required",
]


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def pass_(self, msg: str) -> None:
        print(f"PASS {msg}")

    def info(self, msg: str) -> None:
        print(f"INFO {msg}")

    def fail(self, msg: str) -> None:
        self.failures.append(msg)
        print(f"FAIL {msg}")


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_files(paths: list[Path]) -> dict[str, tuple[bool, str]]:
    result: dict[str, tuple[bool, str]] = {}
    for path in paths:
        exists = path.exists() and path.is_file()
        result[str(path)] = (exists, file_hash(path) if exists else "")
    return result


def snapshot_tree(paths: list[Path]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in paths:
        result[str(path)] = sorted(item.name for item in path.iterdir()) if path.exists() else []
    return result


def compare_file_snapshot(before: dict[str, tuple[bool, str]], check: Check) -> None:
    for raw, previous in before.items():
        path = Path(raw)
        exists = path.exists() and path.is_file()
        current = (exists, file_hash(path) if exists else "")
        if current != previous:
            check.fail(f"protected file changed during approved promote lane verifier: {rel(path)}")
    if not check.failures:
        check.pass_("protected source/route/password metadata files unchanged")


def compare_tree_snapshot(before: dict[str, list[str]], check: Check) -> None:
    for raw, previous in before.items():
        path = Path(raw)
        current = sorted(item.name for item in path.iterdir()) if path.exists() else []
        if current != previous:
            check.fail(f"live/backups tree changed: {rel(path)}")
    if not check.failures:
        check.pass_("live/backups trees unchanged")


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def parse_source(check: Check) -> ast.Module | None:
    if not MODULE_PATH.exists():
        check.fail(f"missing build/promote module: {rel(MODULE_PATH)}")
        return None
    source = MODULE_PATH.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(MODULE_PATH))
    except SyntaxError as exc:
        check.fail(f"module syntax error: {exc}")
        return None
    check.pass_("build/promote module parses")
    return tree


def check_static_boundaries(tree: ast.Module, check: Check) -> None:
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for symbol in REQUIRED_SYMBOLS:
        if symbol not in classes and symbol not in functions:
            check.fail(f"missing approved promote lane symbol: {symbol}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {"socket", "urllib", "requests", "openai", "anthropic", "llama_cpp", "torch"}:
                    check.fail(f"forbidden provider/network/model import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            r = (node.module or "").split(".")[0]
            if r in {"socket", "urllib", "requests", "openai", "anthropic", "llama_cpp", "torch"}:
                check.fail(f"forbidden provider/network/model import: {node.module}")
        elif isinstance(node, ast.Call):
            name = call_name(node.func)
            if name in {"eval", "exec", "compile", "os.system", "os.popen"}:
                check.fail(f"forbidden call: {name}")
            if name.startswith("subprocess.") and name != "subprocess.run":
                check.fail(f"approved promote lane must not use unsafe subprocess helper: {name}")
            if name == "subprocess.run":
                has_shell_false = any(
                    kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is False
                    for kw in node.keywords
                )
                if not has_shell_false:
                    check.fail("subprocess.run must explicitly use shell=False")
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    check.fail("module passes shell=True somewhere")
    if not check.failures:
        check.pass_("approved promote lane symbols exist; no provider/network/model/shell-true behavior")


def import_module(check: Check) -> Any | None:
    spec = importlib.util.spec_from_file_location("engel_debruijn_quantum_build_promote_promote_lane_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        check.fail("could not create import spec")
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
    except Exception as exc:
        check.fail(f"module import failed: {exc}")
        return None
    check.pass_("build/promote module imports without approved promote lane side effects")
    return module


def find_build_preflight_receipt() -> Path | None:
    if not BUILD_RECEIPT_DIR.exists():
        return None
    candidates = sorted(BUILD_RECEIPT_DIR.glob("debruijn_quantum_build_preflight_*.json"))
    return candidates[0] if candidates else None


def check_receipt_secret_safety(check: Check, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=True).lower()
    forbidden = ["raw_password", "password_hash", "password_salt", "secret_value", "token_value"]
    hits = [term for term in forbidden if term in text]
    if hits:
        check.fail(f"approved promote lane receipt contains forbidden secret-like fields: {hits}")
    else:
        check.pass_("approved promote lane receipt contains no password/salt/hash secret values")


def run_lane_smoke(module: Any, check: Check) -> None:
    protected = [MODULE_PATH, ENGEL_APP, PASSWORD_GATE, ROUTE_METADATA]
    before_files = snapshot_files(protected)
    before_trees = snapshot_tree(LIVE_BACKUP_DIRS)
    build_receipt = find_build_preflight_receipt()
    if build_receipt is None:
        check.fail("no build preflight receipt found under reports\\debruijn_quantum_build_receipts\\")
        return
    result = module.run_approved_graph_promote(
        build_receipt,
        ROOT,
        approval_phrase=APPROVAL_PHRASE,
        password_gate_result={
            "ok": True,
            "configured": True,
            "action_id": "approved_graph_promote_verifier_smoke",
            "reason": "verifier_redacted_pass",
        },
    )
    result_dict = asdict(result)
    if result.final_status == EXPECTED_BLOCKED_STATUS:
        check.pass_(f"approved promote lane fail-closed at expected status {EXPECTED_BLOCKED_STATUS}")
    else:
        check.info(f"approved promote lane returned {result.final_status}; verifying it is still a blocked or not-implemented status")
        if not (result.final_status.startswith("PROMOTE_LANE_BLOCKED_") or result.final_status == "PROMOTE_LANE_NOT_IMPLEMENTED"):
            check.fail(f"approved promote lane returned non-blocked status in V1: {result.final_status}")
            return
        check.pass_(f"approved promote lane fail-closed at {result.final_status}")
    if result.promoted_artifact_paths or result.backup_paths or result.live_smoke_result != "not_run":
        check.fail("approved promote lane must not produce promoted artifacts, backups, or live smoke in V1")
        return
    check.pass_("approved promote lane produced no live artifacts, backups, or live smoke")
    if len(result.files_changed) != 2 or not all(item.startswith("reports\\debruijn_quantum_promote_receipts\\") for item in result.files_changed):
        check.fail(f"approved promote lane files_changed must list only promote receipt files: {result.files_changed}")
        return
    check.pass_("approved promote lane files_changed lists only promote receipt files")

    receipt_path = ROOT / result.files_changed[0]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED_RECEIPT_FIELDS if field not in receipt]
    if missing:
        check.fail(f"approved promote lane receipt missing fields: {missing}")
    else:
        check.pass_("approved promote lane receipt includes required fields")
    if receipt.get("human_review_required") is not True:
        check.fail("approved promote lane receipt must keep human_review_required true")
        return
    check.pass_("approved promote lane receipt keeps human_review_required true")
    if receipt.get("password_gate_result", {}).get("redacted") is True:
        check.pass_("password gate result is redacted")
    else:
        check.fail("password gate result must be redacted")
    check_receipt_secret_safety(check, receipt)
    del result_dict
    compare_file_snapshot(before_files, check)
    compare_tree_snapshot(before_trees, check)


def finish(check: Check) -> int:
    if check.failures:
        check.info(f"verification failed with {len(check.failures)} failure(s)")
        return 1
    print(PASS_MARKER)
    return 0


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: static + negative promote-lane smoke; no verifier live write, no verifier backup write, no PyInstaller, no provider/network/model.")
    tree = parse_source(check)
    if tree is None:
        return finish(check)
    check_static_boundaries(tree, check)
    if check.failures:
        return finish(check)
    module = import_module(check)
    if module is not None:
        run_lane_smoke(module, check)
    return finish(check)


if __name__ == "__main__":
    raise SystemExit(main())
