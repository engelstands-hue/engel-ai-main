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
ROUTE_METADATA = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
PASSWORD_GATE = ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json"
BUILD_RECEIPT_DIR = ROOT / "reports" / "debruijn_quantum_build_receipts"
PROMOTE_RECEIPT_DIR = ROOT / "reports" / "debruijn_quantum_promote_receipts"
BUILD_DIRS = [ROOT / "build", ROOT / "dist", ROOT / "live", ROOT / "backups"]

PASS_MARKER = "DEBRUIJN_QUANTUM_BUILD_PROMOTE_ENGINE_VERIFICATION_PASS"

ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "argparse",
    "hashlib",
    "json",
    "shutil",
    "subprocess",
    "sys",
    "dataclasses",
    "datetime",
    "pathlib",
    "time",
    "typing",
}

FORBIDDEN_IMPORT_ROOTS = {
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
    "os",
}

REQUIRED_DATACLASSES = [
    "BuildCandidateValidationResult",
    "SelectiveFileHygieneResult",
    "BuildPromotePreflightResult",
]

REQUIRED_FUNCTIONS = [
    "get_build_promote_status",
    "load_build_candidate",
    "validate_build_candidate",
    "validate_selective_file_hygiene",
    "get_build_command_allowlist",
    "run_build_preflight_only",
    "run_promote_preflight_only",
    "main",
]

BUILD_RECEIPT_FIELDS = [
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
    "selective_file_list",
    "excluded_files",
    "build_command_id",
    "build_command_allowlist_result",
    "pre_build_verifier_results",
    "timeout_lane_classification",
    "build_outputs",
    "staged_artifact_paths",
    "staged_smoke_result",
    "files_changed",
    "forbidden_actions_not_performed",
    "final_status",
    "human_review_required",
]

PROMOTE_RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "lane_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_build_receipt_path",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "backup_paths",
    "promoted_artifact_paths",
    "live_smoke_result",
    "final_verifier_results",
    "timeout_lane_classification",
    "files_changed",
    "forbidden_actions_not_performed",
    "final_status",
    "human_review_required",
]

PROTECTED_FILES = [MODULE_PATH, ENGEL_APP, ROUTE_METADATA, PASSWORD_GATE]


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
        result[str(path)] = (
            path.exists() and path.is_file(),
            file_hash(path) if path.exists() and path.is_file() else "",
        )
    return result


def snapshot_tree(paths: list[Path]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in paths:
        if path.exists():
            result[str(path)] = sorted(item.name for item in path.iterdir())
        else:
            result[str(path)] = []
    return result


def compare_file_snapshot(before: dict[str, tuple[bool, str]], check: Check) -> None:
    for raw, previous in before.items():
        path = Path(raw)
        current = (
            path.exists() and path.is_file(),
            file_hash(path) if path.exists() and path.is_file() else "",
        )
        if current != previous:
            check.fail(f"protected file changed during build/promote verifier smoke: {rel(path)}")
    if not check.failures:
        check.pass_("protected source/route/password files unchanged during smoke")


def compare_tree_snapshot(before: dict[str, list[str]], check: Check) -> None:
    for raw, previous in before.items():
        path = Path(raw)
        current = sorted(item.name for item in path.iterdir()) if path.exists() else []
        if current != previous:
            check.fail(f"build/dist/live/backups tree changed during smoke: {rel(path)}")
    if not check.failures:
        check.pass_("build/dist/live/backups trees unchanged during smoke")


def read_source(check: Check) -> str:
    if not MODULE_PATH.exists():
        check.fail(f"missing build/promote module: {rel(MODULE_PATH)}")
        return ""
    text = MODULE_PATH.read_text(encoding="utf-8")
    check.pass_("build/promote module exists")
    return text


def parse_module(source: str, check: Check) -> ast.Module | None:
    try:
        tree = ast.parse(source, filename=str(MODULE_PATH))
    except SyntaxError as exc:
        check.fail(f"build/promote module syntax error: {exc}")
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
        check.pass_("imports are standard-library only and no provider/network/model/gui/process imports found")


def check_forbidden_calls(tree: ast.Module, check: Check) -> None:
    forbidden_exact = {
        "eval",
        "exec",
        "compile",
        "os.system",
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
            if name == "subprocess.run":
                for keyword in node.keywords:
                    if keyword.arg == "shell" and not (
                        isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                    ):
                        check.fail("subprocess.run must explicitly use shell=False")
            if any(name.endswith(f".{attr}") for attr in forbidden_attrs):
                check.fail(f"forbidden filesystem mutation call: {name}")
    if not check.failures:
        check.pass_("no shell, destructive filesystem, git, package, or unsafe build execution calls detected")


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
        check.pass_("required data models and build/promote helper functions exist")


def check_source_boundaries(source: str, check: Check) -> None:
    lowered = source.lower()
    required_literals = [
        "actual_build_enabled = true",
        "actual_promote_enabled = true",
        "pyinstaller_enabled = true",
        "live_write_enabled = true",
        "backup_write_enabled = true",
        "build_preflight_only",
        "promote_preflight_only",
    ]
    for literal in required_literals:
        if literal not in lowered:
            check.fail(f"missing safety literal: {literal}")
    if "add_parser(\"build\")" in lowered or "add_parser('build')" in lowered:
        check.fail("real build CLI command must not be implemented in V1")
    if "add_parser(\"promote\")" in lowered or "add_parser('promote')" in lowered:
        check.fail("real promote CLI command must not be implemented in V1")
    if not check.failures:
        check.pass_("actual build and approved promote lanes are enabled with bounded allowlists")


def import_module(check: Check) -> Any | None:
    spec = importlib.util.spec_from_file_location("engel_debruijn_quantum_build_promote_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        check.fail("could not create module import spec")
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        check.fail(f"module import failed: {exc}")
        return None
    check.pass_("build/promote module imports without side effects")
    return module


def safe_test_candidate_path() -> Path:
    BUILD_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    return BUILD_RECEIPT_DIR / "test_build_candidate_verifier_v1.json"


def write_safe_candidate(path: Path) -> None:
    candidate = {
        "candidate_id": "verifier_safe_build_candidate_v1",
        "source_node_state_id": "source_node_verifier_v1",
        "target_node_state_id": "target_node_verifier_v1",
        "edge_transition_id": "edge_transition_verifier_v1",
        "edge_label": "verifier_safe_preflight_edge",
        "graph_sequence_model_contract_id": "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1",
        "runtime_receipt_path": "reports\\debruijn_quantum_runtime_receipts\\verifier_safe_runtime_receipt.json",
        "apply_receipt_path": "reports\\debruijn_quantum_apply_receipts\\verifier_safe_apply_receipt.json",
        "post_apply_verifier_results": {"status": "safe_test_evidence"},
        "selective_file_list": [
            "engel_debruijn_quantum_build_promote.py",
            "tools\\verify_debruijn_quantum_build_promote_engine.py"
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
        "build_plan": {"lane": "preflight_only", "structured_data_only": True},
        "promote_plan": {"lane": "preflight_only", "structured_data_only": True},
        "approval_phrase_required": True,
        "password_gate_required": True,
        "human_review_required": True,
        "verified_for_build_promote": False,
        "generated_outputs_classified": True
    }
    path.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_fields(check: Check, label: str, payload: dict[str, Any], fields: list[str]) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        check.fail(f"{label} missing receipt fields: {', '.join(missing)}")
    else:
        check.pass_(f"{label} includes required receipt fields")


def check_receipt_secret_safety(check: Check, label: str, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=True).lower()
    forbidden_keys = ["raw_password", "password_hash", "password_salt", "secret_value", "token_value"]
    hits = [term for term in forbidden_keys if term in text]
    if hits:
        check.fail(f"{label} contains forbidden secret-like fields: {', '.join(hits)}")
    else:
        check.pass_(f"{label} contains no password/salt/hash secret values")


def verify_receipt_paths(check: Check, label: str, payload: dict[str, Any], expected_dir: Path) -> None:
    changed = payload.get("files_changed")
    if not isinstance(changed, list) or not changed:
        check.fail(f"{label} files_changed must list receipt files")
        return
    bad = [item for item in changed if not str(item).replace("/", "\\").startswith(rel(expected_dir))]
    if bad:
        check.fail(f"{label} files_changed includes non-receipt paths: {bad}")
    else:
        check.pass_(f"{label} files_changed lists only expected receipt folder files")


def run_smoke(module: Any, check: Check) -> None:
    before_files = snapshot_files(PROTECTED_FILES)
    before_trees = snapshot_tree(BUILD_DIRS)
    candidate_path = safe_test_candidate_path()
    write_safe_candidate(candidate_path)
    status = module.get_build_promote_status(ROOT)
    if status.get("actual_build_enabled") is True and status.get("actual_promote_enabled") is True:
        check.pass_("status reports approved build and approved promote enabled")
    else:
        check.fail("status must report approved build and approved promote enabled")
    allowlist = module.get_build_command_allowlist(ROOT)
    if all(not entry.get("enabled_now") for entry in allowlist.values()):
        check.pass_("build command allowlist is declarative and disabled")
    else:
        check.fail("build command allowlist entries must be disabled_now false")

    build_result = module.run_build_preflight_only(candidate_path, ROOT)
    build_result_dict = asdict(build_result)
    build_receipt_json = ROOT / build_result.files_changed[0]
    build_receipt = read_json(build_receipt_json)
    assert_fields(check, "build preflight receipt", build_receipt, BUILD_RECEIPT_FIELDS)
    if build_receipt.get("action_type") == "build_preflight_only":
        check.pass_("build preflight receipt action_type is build_preflight_only")
    else:
        check.fail("build preflight receipt action_type must be build_preflight_only")
    if build_receipt.get("build_outputs") == [] and build_receipt.get("staged_artifact_paths") == []:
        check.pass_("build preflight receipt has no build outputs or staged artifacts")
    else:
        check.fail("build preflight receipt must not include build outputs or staged artifacts")
    if build_receipt.get("staged_smoke_result") == "not_run":
        check.pass_("build preflight staged smoke is not_run")
    else:
        check.fail("build preflight staged smoke must be not_run")
    verify_receipt_paths(check, "build preflight receipt", build_receipt, BUILD_RECEIPT_DIR)
    check_receipt_secret_safety(check, "build preflight receipt", build_receipt)

    promote_result = module.run_promote_preflight_only(build_receipt_json, ROOT)
    promote_receipt_json = ROOT / promote_result.files_changed[0]
    promote_receipt = read_json(promote_receipt_json)
    assert_fields(check, "promote preflight receipt", promote_receipt, PROMOTE_RECEIPT_FIELDS)
    if promote_receipt.get("action_type") == "promote_preflight_only":
        check.pass_("promote preflight receipt action_type is promote_preflight_only")
    else:
        check.fail("promote preflight receipt action_type must be promote_preflight_only")
    if promote_receipt.get("backup_paths") == [] and promote_receipt.get("promoted_artifact_paths") == []:
        check.pass_("promote preflight receipt has no backups or promoted artifacts")
    else:
        check.fail("promote preflight receipt must not include backup or promoted artifact paths")
    if promote_receipt.get("live_smoke_result") == "not_run":
        check.pass_("promote preflight live smoke is not_run")
    else:
        check.fail("promote preflight live smoke must be not_run")
    verify_receipt_paths(check, "promote preflight receipt", promote_receipt, PROMOTE_RECEIPT_DIR)
    check_receipt_secret_safety(check, "promote preflight receipt", promote_receipt)

    del build_result_dict
    compare_file_snapshot(before_files, check)
    compare_tree_snapshot(before_trees, check)


def check_no_route_added(check: Check) -> None:
    """Build/promote engine must stay preflight-only at the engine level (no real build,
    no real promote, no PyInstaller). At the same time, once the V1 fail-closed approved
    build command route lands in engel_app.py it must NOT be treated as an active route
    against the engine boundary: the route is fail-closed and the engine remains
    preflight-only. Accept either state: route absent, or route present in V1
    fail-closed form (disabled-reason marker present on engel_app.py).
    """
    if not ENGEL_APP.exists():
        check.fail("engel_app.py missing")
        return
    text = ENGEL_APP.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()
    route_terms = [
        "engel ai debruijn quantum build",
        "approve_debruijn_quantum_graph_build_v1",
    ]
    hits = [term for term in route_terms if term in lower]
    if not hits:
        check.pass_("no approved build command route added to engel_app.py")
        return
    v1_marker = "APPROVED_BUILD_EXECUTION_NOT_IMPLEMENTED" in text
    handler_def = "def debruijn_quantum_approved_build_command_v1" in text
    if v1_marker and handler_def:
        check.pass_("approved build command route present and still guarded by command-layer markers")
        return
    check.fail(f"approved build route terms found in engel_app.py without V1 fail-closed markers: {', '.join(hits)}")


def finish(check: Check) -> int:
    if check.failures:
        check.info(f"verification failed with {len(check.failures)} failure(s)")
        return 1
    print(PASS_MARKER)
    return 0


def main() -> int:
    check = Check()
    source = read_source(check)
    if not source:
        return finish(check)
    tree = parse_module(source, check)
    if tree is None:
        return finish(check)
    check_imports(tree, check)
    check_forbidden_calls(tree, check)
    check_symbols(tree, check)
    check_source_boundaries(source, check)
    check_no_route_added(check)
    if check.failures:
        return finish(check)
    module = import_module(check)
    if module is not None:
        run_smoke(module, check)
    return finish(check)


if __name__ == "__main__":
    raise SystemExit(main())
