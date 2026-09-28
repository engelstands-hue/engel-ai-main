#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import os
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
HELPER = ROOT / "engel_debruijn_quantum_structure_status.py"
BASE_VERIFIER = ROOT / "tools" / "verify_engel_debruijn_quantum_automation_file_structure.py"
UI_PLAN_VERIFIER = ROOT / "tools" / "verify_debruijn_quantum_file_structure_ui_plan.py"
TEMP_PARENT = ROOT / "reports" / "debruijn_quantum_file_structure"

PASS_MARKER = "DEBRUIJN_QUANTUM_STRUCTURE_STATUS_HELPER_VERIFICATION_PASS"

ALLOWED_HELPER_IMPORTS = {"__future__", "argparse", "json", "sys", "datetime", "pathlib", "typing"}

FORBIDDEN_HELPER_TOKENS = [
    "subprocess",
    "requests",
    "httpx",
    "urllib",
    "socket",
    "qiskit",
    "cirq",
    "pennylane",
    "braket",
    "openai",
    "torch",
    "tensorflow",
    "tkinter",
    "PyQt",
    "os.system",
    "eval(",
    "exec(",
    "write_text",
    "write_bytes",
    ".open(",
    "open(",
    "os.walk",
    ".rglob(",
    "glob(\"**",
    "glob('**",
]

APPROVED_SOURCE_MARKERS = [
    "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.json",
    "reports",
    "debruijn_quantum_file_structure",
    "latest_status.json",
    "latest_status.md",
    "automation_receipt_*.md",
    "candidate_fix_proposals_*.json",
]

REQUIRED_STATUS_FIELDS = [
    "available",
    "status_source",
    "backend_only",
    "ui_enabled",
    "companion_card_enabled",
    "viewer_enabled",
    "manual_scan_button_enabled",
    "contract_present",
    "contract_status",
    "automation_scope",
    "quantum_mode",
    "real_quantum_enabled",
    "provider_api_enabled",
    "network_enabled",
    "model_inference_enabled",
    "background_worker_enabled",
    "startup_autorun_enabled",
    "apply_enabled",
    "file_mutation_enabled",
    "trusted_memory_write_enabled",
    "route_mutation_enabled",
    "queue_mutation_enabled",
    "node_counts",
    "transition_counts",
    "file_count",
    "unknown_count",
    "candidate_count",
    "report_count",
    "proposal_count",
    "incomplete_entanglement_count",
    "scan_truncated",
    "latest_status_path",
    "latest_status_md_path",
    "latest_receipt_path",
    "latest_proposal_path",
    "last_updated",
    "safety_flags",
    "missing_outputs",
    "warnings",
    "human_review_required",
]

FALSE_CAPABILITY_FIELDS = [
    "ui_enabled",
    "companion_card_enabled",
    "viewer_enabled",
    "manual_scan_button_enabled",
    "real_quantum_enabled",
    "provider_api_enabled",
    "network_enabled",
    "model_inference_enabled",
    "background_worker_enabled",
    "startup_autorun_enabled",
    "apply_enabled",
    "file_mutation_enabled",
    "trusted_memory_write_enabled",
    "route_mutation_enabled",
    "queue_mutation_enabled",
]

REQUIRED_TRUE_SAFETY_FLAGS = [
    "backend_only",
    "ui_off",
    "companion_card_off",
    "viewer_off",
    "quantum_inspired_only",
    "real_quantum_off",
    "provider_api_off",
    "network_off",
    "model_inference_off",
    "background_worker_off",
    "startup_autorun_off",
    "apply_off",
    "file_move_delete_rewrite_off",
    "trusted_memory_write_off",
    "route_queue_mutation_off",
    "candidate_execution_off",
    "human_review_required_for_apply",
]


class CheckFailure(Exception):
    pass


def print_result(status: str, label: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{status} {label}{suffix}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_helper_module() -> Any:
    spec = importlib.util.spec_from_file_location("engel_debruijn_quantum_structure_status", HELPER)
    require(spec is not None and spec.loader is not None, "could not load helper module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot_tree(root: Path) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*"), key=lambda item: str(item)):
        if path.is_file():
            stat = path.stat()
            snapshot[rel(path)] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_contract(root: Path) -> None:
    write_json(
        root / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.json",
        {
            "contract_id": "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1",
            "status": "inactive_status_layer",
            "automation_scope": "manual_scan_report_propose_only",
            "quantum_computation_mode": "quantum_inspired_only_no_real_quantum_execution",
            "real_quantum_execution_enabled": False,
            "provider_api_enabled": False,
            "network_enabled": False,
            "model_inference_enabled": False,
            "background_worker_enabled": False,
            "startup_autorun_enabled": False,
            "apply_command_enabled": False,
            "file_mutation_enabled": False,
            "trusted_memory_write_enabled": False,
            "route_mutation_enabled": False,
            "queue_mutation_enabled": False,
            "human_approval_required": True,
        },
    )


def write_status_fixture(root: Path) -> None:
    report_root = root / "reports" / "debruijn_quantum_file_structure"
    write_json(
        report_root / "latest_status.json",
        {
            "status": "status_report_only",
            "scan_completed_at": "2026-05-23T00:00:00Z",
            "scan_truncated": False,
            "files_reported_count": 4,
            "node_counts": {"011": 1, "110": 1, "111": 1, "unknown": 1},
            "entanglement_groups": [
                {"entangled_group_id": "sample", "missing_files": ["verifier_python"], "status": "missing_verifier"},
                {"entangled_group_id": "complete", "missing_files": [], "status": "complete"},
            ],
            "records": [
                {"path": "tools\\verify_sample.py", "debruijn_node": "011", "candidate_nodes": ["011"], "transition_codes": ["0110"]},
                {"path": "reports\\codex_bridge\\SAMPLE.md", "debruijn_node": "110", "candidate_nodes": [], "transition_codes": ["1100"]},
                {"path": "engel_remote_worker_protocol.py", "debruijn_node": "111", "candidate_nodes": ["111"], "transition_codes": ["1110"]},
                {"path": "README.md", "debruijn_node": "unknown", "candidate_nodes": [], "transition_codes": []},
            ],
        },
    )
    write_text(report_root / "latest_status.md", "# Latest Status\n")
    write_text(report_root / "automation_receipt_20260523T000000000000Z.md", "# Receipt\n\nNo files were moved.\n")


def write_safe_proposal_fixture(root: Path) -> None:
    write_json(
        root / "reports" / "debruijn_quantum_file_structure" / "candidate_fix_proposals_20260523T000000000000Z.json",
        {
            "status": "untrusted_candidate",
            "apply_allowed": False,
            "human_review_required": True,
            "proposal_count": 2,
            "proposals": [
                {
                    "proposal_id": "one",
                    "proposal_type": "candidate_only_structure_fix",
                    "trust_status": "untrusted_candidate",
                    "apply_allowed": False,
                    "human_review_required": True,
                },
                {
                    "proposal_id": "two",
                    "proposal_type": "documentation_gap_review",
                    "trust_status": "untrusted_candidate",
                    "apply_allowed": False,
                    "human_review_required": True,
                },
            ],
        },
    )


def write_unsafe_proposal_fixture(root: Path) -> None:
    write_json(
        root / "reports" / "debruijn_quantum_file_structure" / "candidate_fix_proposals_20260523T010000000000Z.json",
        {
            "status": "trusted_existing",
            "apply_allowed": True,
            "human_review_required": False,
            "proposal_count": 1,
            "proposals": [
                {
                    "proposal_id": "bad",
                    "proposal_type": "unsafe",
                    "trust_status": "trusted_existing",
                    "apply_allowed": True,
                    "human_review_required": False,
                }
            ],
        },
    )


def verify_static_source() -> None:
    require(HELPER.exists(), "helper module is missing")
    py_compile.compile(str(HELPER), doraise=True)
    py_compile.compile(str(SELF), doraise=True)
    source = read_text(HELPER)
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    disallowed = sorted(imports - ALLOWED_HELPER_IMPORTS)
    require(not disallowed, "helper imports disallowed modules: " + ", ".join(disallowed))
    for token in FORBIDDEN_HELPER_TOKENS:
        require(token not in source, f"helper contains forbidden token: {token}")
    for marker in APPROVED_SOURCE_MARKERS:
        require(marker in source, "helper source missing approved data source marker: " + marker)
    print_result("PASS", "helper static source", "stdlib-only, no subprocess, no writes, no recursive workspace scan")


def verify_required_status_fields(status: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_STATUS_FIELDS if field not in status]
    require(not missing, "status dict missing fields: " + ", ".join(missing))
    require(status.get("status_source") == "existing_reports_only", "status_source must be existing_reports_only")
    require(status.get("backend_only") is True, "backend_only must be true")
    for field in FALSE_CAPABILITY_FIELDS:
        require(status.get(field) is False, f"{field} must be false")
    flags = status.get("safety_flags")
    require(isinstance(flags, dict), "safety_flags must be a dict")
    missing_flags = [flag for flag in REQUIRED_TRUE_SAFETY_FLAGS if flags.get(flag) is not True]
    require(not missing_flags, "safety flags missing/false: " + ", ".join(missing_flags))
    require(status.get("human_review_required") is True, "human_review_required must be true")


def verify_empty_state(helper: Any) -> None:
    TEMP_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="status_helper_empty_", dir=str(TEMP_PARENT)) as temp_name:
        root = Path(temp_name)
        write_contract(root)
        before = snapshot_tree(root)
        status = helper.build_debruijn_quantum_structure_status(root)
        after = snapshot_tree(root)
        require(before == after, "helper modified files during empty-state read")
        verify_required_status_fields(status)
        require(status.get("available") is False, "empty state must not be available")
        require("latest_status.json" in " ".join(status.get("missing_outputs", [])), "empty state must report missing latest_status.json")
        require("did not run a scan" in status.get("message", ""), "empty state must honestly state no scan was run")
    print_result("PASS", "empty state behavior", "missing outputs reported; no files written")


def verify_status_and_proposals(helper: Any) -> None:
    TEMP_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="status_helper_full_", dir=str(TEMP_PARENT)) as temp_name:
        root = Path(temp_name)
        write_contract(root)
        write_status_fixture(root)
        write_safe_proposal_fixture(root)
        before = snapshot_tree(root)
        status = helper.build_debruijn_quantum_structure_status(root)
        after = snapshot_tree(root)
        require(before == after, "helper modified files during full status read")
        verify_required_status_fields(status)
        require(status.get("available") is True, "status should be available with latest_status.json")
        require(status.get("contract_status") == "inactive_status_layer", "contract status mismatch")
        require(status.get("automation_scope") == "manual_scan_report_propose_only", "automation scope mismatch")
        require(status.get("quantum_mode") == "quantum_inspired_only_no_real_quantum_execution", "quantum mode mismatch")
        require(status.get("file_count") == 4, "file count mismatch")
        require(status.get("unknown_count") == 1, "unknown count mismatch")
        require(status.get("candidate_count") == 2, "candidate count mismatch")
        require(status.get("report_count") == 1, "report count mismatch")
        require(status.get("proposal_count") == 2, "proposal count mismatch")
        require(status.get("incomplete_entanglement_count") == 1, "incomplete entanglement count mismatch")
        require(status.get("proposal_safety_ok") is True, "safe proposals should be proposal_safety_ok")
        require(status.get("proposal_type_counts", {}).get("candidate_only_structure_fix") == 1, "proposal type count missing")
        require(status.get("latest_receipt_path") is not None, "latest receipt path missing")
        require(status.get("latest_proposal_path") is not None, "latest proposal path missing")
    print_result("PASS", "status output schema", "required counts and paths produced from existing reports")
    print_result("PASS", "proposal safety behavior", "untrusted/apply-false proposals accepted as safe")


def verify_malformed_proposal(helper: Any) -> None:
    TEMP_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="status_helper_bad_proposal_", dir=str(TEMP_PARENT)) as temp_name:
        root = Path(temp_name)
        write_contract(root)
        write_status_fixture(root)
        write_unsafe_proposal_fixture(root)
        before = snapshot_tree(root)
        status = helper.build_debruijn_quantum_structure_status(root)
        after = snapshot_tree(root)
        require(before == after, "helper modified files during unsafe proposal read")
        verify_required_status_fields(status)
        require(status.get("proposal_safety_ok") is False, "unsafe proposal must set proposal_safety_ok false")
        warnings = " ".join(status.get("warnings", []))
        for term in ["untrusted_candidate", "apply_allowed", "human_review_required"]:
            require(term in warnings, "unsafe proposal warning missing term: " + term)
    print_result("PASS", "malformed proposal handling", "warning only; no apply or mutation")


def verify_invalid_root(helper: Any) -> None:
    status = helper.build_debruijn_quantum_structure_status(r"\\server\share")
    verify_required_status_fields(status)
    require(status.get("available") is False, "network root must be unavailable")
    require(status.get("warnings"), "network root must emit warning")
    print_result("PASS", "invalid root behavior", "network-style root fails closed")


def verify_cli() -> None:
    TEMP_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="status_helper_cli_", dir=str(TEMP_PARENT)) as temp_name:
        root = Path(temp_name)
        write_contract(root)
        write_status_fixture(root)
        write_safe_proposal_fixture(root)
        before = snapshot_tree(root)
        status_result = subprocess.run(
            [sys.executable, str(HELPER), "status", "--root", str(root)],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        json_result = subprocess.run(
            [sys.executable, str(HELPER), "json", "--root", str(root)],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        blocked = subprocess.run(
            [sys.executable, str(HELPER), "scan", "--root", str(root)],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        after = snapshot_tree(root)
        require(before == after, "helper CLI modified files")
        require(status_result.returncode == 0, "status CLI failed: " + status_result.stderr)
        require("Engel De Bruijn Quantum Structure Status" in status_result.stdout, "status CLI output missing title")
        require(json_result.returncode == 0, "json CLI failed: " + json_result.stderr)
        payload = json.loads(json_result.stdout)
        verify_required_status_fields(payload)
        require(blocked.returncode != 0, "unsupported helper CLI command must fail closed")
    print_result("PASS", "helper CLI behavior", "status/json print only; unsupported command fails closed")


def verify_dependent_verifier_availability() -> None:
    require(BASE_VERIFIER.exists(), "dependent verifier missing: " + rel(BASE_VERIFIER))
    py_compile.compile(str(BASE_VERIFIER), doraise=True)
    if UI_PLAN_VERIFIER.exists():
        py_compile.compile(str(UI_PLAN_VERIFIER), doraise=True)
        result = subprocess.run(
            [sys.executable, str(UI_PLAN_VERIFIER)],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=240,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        require(result.returncode == 0, "UI plan verifier failed:\n" + result.stdout)
        require("DEBRUIJN_QUANTUM_FILE_STRUCTURE_UI_PLAN_VERIFICATION_PASS" in result.stdout, "UI plan verifier marker missing")
        print_result("PASS", "UI plan verifier dependency", "DEBRUIJN_QUANTUM_FILE_STRUCTURE_UI_PLAN_VERIFICATION_PASS")
    else:
        print_result("SKIP", "UI plan verifier dependency", "not present; backend helper remains UI-free")
    print_result("INFO", "base De Bruijn verifier dependency", "present and compiles; executed separately in post-check to avoid this helper verifier initiating scans")


def main() -> int:
    print("ENGEL_DEBRUIJN_QUANTUM_STRUCTURE_STATUS_HELPER_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: helper/source verification only; no UI, no scans, no writes outside temp fixtures")
    try:
        verify_static_source()
        helper = load_helper_module()
        require(hasattr(helper, "build_debruijn_quantum_structure_status"), "helper function missing")
        require(hasattr(helper, "load_debruijn_quantum_contract"), "contract loader function missing")
        require(hasattr(helper, "find_latest_debruijn_receipt"), "latest receipt helper function missing")
        require(hasattr(helper, "find_latest_debruijn_proposal"), "latest proposal helper function missing")
        verify_empty_state(helper)
        verify_status_and_proposals(helper)
        verify_malformed_proposal(helper)
        verify_invalid_root(helper)
        verify_cli()
        verify_dependent_verifier_availability()
    except py_compile.PyCompileError as exc:
        print_result("FAIL", "py_compile", str(exc))
        return 1
    except json.JSONDecodeError as exc:
        print_result("FAIL", "JSON parse", str(exc))
        return 1
    except (CheckFailure, OSError, subprocess.SubprocessError, SyntaxError) as exc:
        print_result("FAIL", "De Bruijn Quantum Structure status helper verifier", str(exc))
        return 1
    except Exception as exc:
        print_result("FAIL", "unexpected verifier error", f"{type(exc).__name__}: {exc}")
        return 1

    print_result("PASS", "helper behavior")
    print_result("PASS", "status output schema")
    print_result("PASS", "empty state behavior")
    print_result("PASS", "proposal safety behavior")
    print_result("PASS", "safety preserved")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
