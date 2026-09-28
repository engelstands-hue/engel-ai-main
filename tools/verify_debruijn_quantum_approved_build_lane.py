#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "engel_debruijn_quantum_build_promote.py"
ENGEL_APP = ROOT / "engel_app.py"
PASSWORD_GATE = ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json"
ROUTE_METADATA = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
BUILD_RECEIPT_DIR = ROOT / "reports" / "debruijn_quantum_build_receipts"
BUILD_DIRS = [ROOT / "build", ROOT / "dist", ROOT / "live", ROOT / "backups"]

PASS_MARKER = "DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_VERIFICATION_PASS"
APPROVAL_PHRASE = "APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1"
EXPECTED_FAIL_CLOSED_STATUSES = {
    "BUILD_LANE_BLOCKED_SCRIPT_MISSING",
    "BUILD_LANE_NOT_IMPLEMENTED",
}

REQUIRED_SYMBOLS = [
    "ApprovedBuildLaneResult",
    "get_approved_build_lane_contract",
    "get_approved_build_lane_allowlist",
    "redact_password_gate_result",
    "run_approved_graph_build",
]

REQUIRED_RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "lane_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_build_candidate_path",
    "candidate_id",
    "candidate_hash",
    "source_node_state_id",
    "target_node_state_id",
    "edge_transition_id",
    "edge_label",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "build_command_id",
    "exact_script_or_command_path",
    "exact_arguments",
    "allowed_working_directory",
    "timeout_lane_id",
    "timeout_seconds_soft",
    "timeout_seconds_hard",
    "elapsed_seconds",
    "timeout_classification",
    "pre_build_verifier_results",
    "post_build_verifier_results",
    "build_outputs",
    "staged_artifact_paths",
    "staged_smoke_result",
    "files_changed",
    "forbidden_actions_not_performed",
    "cleanup_status",
    "final_status",
    "human_review_required",
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
            check.fail(f"protected file changed during approved build lane verifier: {rel(path)}")
    if not check.failures:
        check.pass_("protected source/route/password metadata files unchanged")


def compare_tree_snapshot(before: dict[str, list[str]], check: Check) -> None:
    for raw, previous in before.items():
        path = Path(raw)
        current = sorted(item.name for item in path.iterdir()) if path.exists() else []
        if current != previous:
            check.fail(f"build/dist/live/backups tree changed: {rel(path)}")
    if not check.failures:
        check.pass_("build/dist/live/backups trees unchanged")


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


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def check_static_boundaries(tree: ast.Module, check: Check) -> None:
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for symbol in REQUIRED_SYMBOLS:
        if symbol not in classes and symbol not in functions:
            check.fail(f"missing approved build lane symbol: {symbol}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {"socket", "urllib", "requests", "openai", "anthropic", "llama_cpp", "torch"}:
                    check.fail(f"forbidden provider/network/model import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in {"socket", "urllib", "requests", "openai", "anthropic", "llama_cpp", "torch"}:
                check.fail(f"forbidden provider/network/model import: {node.module}")
        elif isinstance(node, ast.Call):
            name = call_name(node.func)
            if name in {"eval", "exec", "compile", "os.system"}:
                check.fail(f"forbidden call: {name}")
            if name.startswith("subprocess.") and name != "subprocess.run":
                check.fail(f"approved build lane may only use subprocess.run with shell=False: {name}")
            if name == "subprocess.run":
                for keyword in node.keywords:
                    if keyword.arg == "shell" and not (
                        isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                    ):
                        check.fail("approved build lane subprocess.run must set shell=False")
    if not check.failures:
        check.pass_("approved build lane symbols exist and static source has no provider/network/model behavior; subprocess use is bounded")


def import_module(check: Check) -> Any | None:
    spec = importlib.util.spec_from_file_location("engel_debruijn_quantum_build_promote_lane_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        check.fail("could not create import spec")
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        check.fail(f"module import failed: {exc}")
        return None
    check.pass_("build/promote module imports without approved lane side effects")
    return module


def safe_candidate_path() -> Path:
    BUILD_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    return BUILD_RECEIPT_DIR / "test_approved_build_lane_candidate_v1.json"


def write_safe_candidate(path: Path) -> None:
    candidate = {
        "candidate_id": "verifier_safe_approved_build_lane_candidate_v1",
        "source_node_state_id": "source_node_approved_build_lane_v1",
        "target_node_state_id": "target_node_approved_build_lane_v1",
        "edge_transition_id": "edge_transition_approved_build_lane_v1",
        "edge_label": "approved_build_lane_verifier_edge",
        "graph_sequence_model_contract_id": "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1",
        "runtime_receipt_path": "reports\\debruijn_quantum_runtime_receipts\\verifier_safe_runtime_receipt.json",
        "apply_receipt_path": "reports\\debruijn_quantum_apply_receipts\\verifier_safe_apply_receipt.json",
        "post_apply_verifier_results": {"status": "safe_test_evidence"},
        "selective_file_list": [
            "engel_debruijn_quantum_build_promote.py",
            "tools\\verify_debruijn_quantum_approved_build_lane.py"
        ],
        "excluded_files": [
            "memory\\ENGEL_GLOBAL_PASSWORD_GATE_V1.json",
            "memory\\MAIN_AGENT_LOG.md",
            "code_workspace\\",
            "build\\",
            "dist\\",
            "live\\",
            "backups\\"
        ],
        "build_command_id": "build_engel_main_exe",
        "build_plan": {"lane": "approved_graph_build", "structured_data_only": True},
        "promote_plan": {"lane": "separate_future_gate", "structured_data_only": True},
        "approval_phrase_required": True,
        "password_gate_required": True,
        "human_review_required": True,
        "verified_for_build_promote": True,
        "generated_outputs_classified": True
    }
    path.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_receipt_secret_safety(check: Check, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=True).lower()
    forbidden_terms = ["raw_password", "password_hash", "password_salt", "secret_value", "token_value"]
    hits = [term for term in forbidden_terms if term in text]
    if hits:
        check.fail(f"approved build lane receipt contains forbidden secret-like fields: {hits}")
    else:
        check.pass_("approved build lane receipt contains no password/salt/hash secret values")


def run_lane_smoke(module: Any, check: Check) -> None:
    protected = [MODULE_PATH, ENGEL_APP, PASSWORD_GATE, ROUTE_METADATA]
    before_files = snapshot_files(protected)
    before_trees = snapshot_tree(BUILD_DIRS)
    candidate_path = safe_candidate_path()
    write_safe_candidate(candidate_path)

    result = module.run_approved_graph_build(
        candidate_path,
        ROOT,
        approval_phrase=APPROVAL_PHRASE,
        execute_build=False,
        password_gate_result={
            "ok": True,
            "configured": True,
            "action_id": "approved_graph_build_verifier_smoke",
            "reason": "verifier_redacted_pass",
        },
    )
    result_dict = asdict(result)
    if result.final_status in EXPECTED_FAIL_CLOSED_STATUSES:
        check.pass_(f"approved build lane fail-closed at expected status {result.final_status}")
    else:
        check.fail(f"approved build lane final_status mismatch: {result.final_status}")
    if result.build_outputs == [] and result.staged_artifact_paths == [] and result.staged_smoke_result == "not_run":
        check.pass_("approved build lane produced no build outputs or staged artifacts")
    else:
        check.fail("approved build lane must not produce outputs or staged artifacts in script-missing V1")
    if len(result.files_changed) != 2 or not all(item.startswith("reports\\debruijn_quantum_build_receipts\\") for item in result.files_changed):
        check.fail(f"approved build lane files_changed must list only build receipt files: {result.files_changed}")
    else:
        check.pass_("approved build lane files_changed lists only build receipt files")

    receipt_path = ROOT / result.files_changed[0]
    receipt = read_json(receipt_path)
    missing = [field for field in REQUIRED_RECEIPT_FIELDS if field not in receipt]
    if missing:
        check.fail(f"approved build lane receipt missing fields: {missing}")
    else:
        check.pass_("approved build lane receipt includes required fields")
    if result.final_status == "BUILD_LANE_BLOCKED_SCRIPT_MISSING" and receipt.get("missing_script_paths"):
        check.pass_("approved build lane receipt records missing allowlisted scripts")
    elif result.final_status == "BUILD_LANE_NOT_IMPLEMENTED" and not receipt.get("missing_script_paths"):
        check.pass_("approved build lane recognized scripts exist but execution remains disabled")
    else:
        check.fail("approved build lane receipt script state is inconsistent with fail-closed status")
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
    print("ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: static + fail-closed lane smoke; no build, PyInstaller, promote, route, provider, network, or trusted-memory mutation.")
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
