#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_debruijn_quantum_automation_file_structure.py"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.md"
OUTPUT_ROOT = ROOT / "reports" / "debruijn_quantum_file_structure"

PASS_MARKER = "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_VERIFY_PASS"

REQUIRED_FALSE_FLAGS = [
    "runtime_enabled",
    "network_enabled",
    "provider_api_enabled",
    "quantum_provider_enabled",
    "real_quantum_execution_enabled",
    "model_inference_enabled",
    "background_worker_enabled",
    "startup_autorun_enabled",
    "file_mutation_enabled",
    "source_rewrite_enabled",
    "file_move_enabled",
    "file_delete_enabled",
    "trusted_memory_write_enabled",
    "route_mutation_enabled",
    "queue_mutation_enabled",
    "candidate_execution_enabled",
    "auto_collapse_enabled",
    "auto_approval_enabled",
    "apply_command_enabled",
]

EXPECTED_NODES = {
    "000",
    "001",
    "010",
    "011",
    "100",
    "101",
    "110",
    "111",
}

EXPECTED_TRANSITIONS = {
    "0001",
    "0010",
    "0101",
    "1011",
    "0110",
    "1100",
    "1000",
    "0111",
    "1110",
    "0100",
    "1001",
    "1101",
    "1010",
}

EXPECTED_STATES = {
    "observed_untrusted",
    "candidate_superposition",
    "measured_passed_unapproved",
    "measured_failed",
    "stale_decohered",
    "rejected",
    "approved_inactive",
    "trusted_existing",
    "unknown_unclassified",
}

ALLOWED_OUTPUT_PATTERNS = [
    re.compile(r"^\.gitkeep$"),
    re.compile(r"^latest_status\.json$"),
    re.compile(r"^latest_status\.md$"),
    re.compile(r"^automation_receipt_\d{8}T\d{6}\d{6}Z\.md$"),
    re.compile(r"^candidate_fix_proposals_\d{8}T\d{6}\d{6}Z\.json$"),
]

FORBIDDEN_SOURCE_PATTERNS = [
    "requests",
    "httpx",
    "urllib",
    "socket",
    "subprocess",
    "os.system",
    "eval(",
    "exec(",
    "qiskit",
    "cirq",
    "pennylane",
    "braket",
    "quantum_provider",
    "shutil.move",
    "os.remove",
    ".unlink(",
    "rmtree",
    "trusted_memory_write_enabled" + " = True",
    "route_mutation_enabled = True",
    "queue_mutation_enabled = True",
    "file_delete_enabled = True",
    "file_move_enabled = True",
]

REQUIRED_RECORD_FIELDS = [
    "path",
    "name",
    "extension",
    "debruijn_node",
    "node_label",
    "matched_rules",
    "classification_reason",
    "candidate_nodes",
    "selected_priority",
    "transition_codes",
    "transition_labels",
    "quantum_state",
    "trust_status",
    "candidate_status",
    "human_review_required",
    "collapse_allowed",
    "runtime_enabled",
    "safe_to_execute",
    "entangled_group_id",
    "entangled_expected_files",
    "entangled_found_files",
    "missing_entangled_files",
    "measurement_required",
    "automation_actions_allowed",
    "automation_actions_forbidden",
]


class VerificationError(Exception):
    pass


def emit(level: str, message: str) -> None:
    print(f"{level}: {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise VerificationError(f"Missing required JSON: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"Invalid JSON in {path}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def run_module(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MODULE), *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def verify_contract() -> None:
    contract = load_json(CONTRACT_JSON)
    require(CONTRACT_MD.exists(), f"Missing required Markdown contract: {CONTRACT_MD}")
    require(contract.get("contract_id") == "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1", "contract_id mismatch")
    require(contract.get("status") == "inactive_status_layer", "status must remain inactive_status_layer")
    require(contract.get("active_workspace") == r"D:\b.WorkSpace\Engel App", "active_workspace mismatch")
    require(contract.get("automation_scope") == "manual_scan_report_propose_only", "automation_scope mismatch")
    require(contract.get("automation_enabled") is True, "automation_enabled should indicate manual status/report capability")
    for key in REQUIRED_FALSE_FLAGS:
        require(contract.get(key) is False, f"{key} must be false")
    require(contract.get("human_approval_required") is True, "human_approval_required must be true")
    require(set(contract.get("nodes", {}).keys()) == EXPECTED_NODES, "3-bit node map mismatch")
    require(set(contract.get("transitions", {}).keys()) == EXPECTED_TRANSITIONS, "4-bit transition map mismatch")
    require(set(contract.get("quantum_state_enums", [])) == EXPECTED_STATES, "quantum state enum mismatch")
    require("manual_scan_report" in contract.get("automation_modes", {}), "manual_scan_report mode missing")
    require("candidate_proposal" in contract.get("automation_modes", {}), "candidate_proposal mode missing")
    emit("PASS", "contract JSON and Markdown are present and safety flags are closed")


def verify_static_source() -> None:
    require(MODULE.exists(), f"Missing module: {MODULE}")
    source = MODULE.read_text(encoding="utf-8")
    for pattern in FORBIDDEN_SOURCE_PATTERNS:
        require(pattern not in source, f"forbidden source pattern found in module: {pattern}")
    for command in [
        "help",
        "examples",
        "commands",
        "safety",
        "status",
        "automation-status",
        "scan",
        "json",
        "automation-json",
        "entanglement",
        "scan-report",
        "propose-fixes",
    ]:
        require(command in source, f"required command marker missing: {command}")
    for command in ["apply", "collapse", "promote", "trust", "move", "delete", "rewrite", "repair", "autorun", "daemon", "watch", "schedule", "sync", "provider", "quantum-run"]:
        require(command in source, f"forbidden command safe-error marker missing: {command}")
    py_compile.compile(str(MODULE), doraise=True)
    py_compile.compile(str(Path(__file__)), doraise=True)
    emit("PASS", "module and verifier compile and contain safe command boundaries")


def verify_output_folder() -> None:
    require(OUTPUT_ROOT.exists(), f"Missing output folder: {OUTPUT_ROOT}")
    for path in OUTPUT_ROOT.iterdir():
        if path.is_dir():
            continue
        require(any(pattern.match(path.name) for pattern in ALLOWED_OUTPUT_PATTERNS), f"unexpected output file in De Bruijn report folder: {path.name}")
    emit("PASS", "output folder contains only allowed status/proposal file names")


def output_snapshot() -> dict[str, tuple[int, int]]:
    if not OUTPUT_ROOT.exists():
        return {}
    snapshot: dict[str, tuple[int, int]] = {}
    for path in sorted(OUTPUT_ROOT.iterdir(), key=lambda item: item.name):
        if path.is_file():
            stat = path.stat()
            snapshot[path.name] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def create_sample_root() -> tempfile.TemporaryDirectory[str]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    temp = tempfile.TemporaryDirectory(prefix="verify_debruijn_", dir=str(OUTPUT_ROOT))
    root = Path(temp.name)
    (root / "memory").mkdir()
    (root / "tools").mkdir()
    (root / "reports" / "codex_bridge").mkdir(parents=True)
    (root / "memory" / "ENGEL_SAMPLE_CONTRACT_V1.json").write_text('{"contract_id":"ENGEL_SAMPLE_CONTRACT_V1"}\n', encoding="utf-8")
    (root / "memory" / "ENGEL_SAMPLE_CONTRACT_V1.md").write_text("# ENGEL_SAMPLE_CONTRACT_V1\n", encoding="utf-8")
    (root / "tools" / "verify_engel_sample_contract.py").write_text("print('sample verifier placeholder')\n", encoding="utf-8")
    (root / "reports" / "codex_bridge" / "ENGEL_SAMPLE_CONTRACT_V1.md").write_text("# sample report\n", encoding="utf-8")
    (root / "engel_remote_worker_protocol.py").write_text("# remote boundary sample\n", encoding="utf-8")
    (root / "README.md").write_text("# sample\n", encoding="utf-8")
    return temp


def parse_json_output(result: subprocess.CompletedProcess[str], command: str) -> dict[str, Any]:
    require(result.returncode == 0, f"{command} failed: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{command} did not emit valid JSON: {exc}") from exc


def verify_discovery_commands() -> None:
    before = output_snapshot()
    discovery_cases = [
        ([], ["Quantum-inspired only", "Safe manual commands", "Forbidden commands fail closed", "no apply/move/delete/trust/promote exists in V1"]),
        (["help"], ["Quantum-inspired only", "Safe manual commands", "Forbidden commands fail closed", "proposal apply_allowed remains false"]),
        (["examples"], ["Status:", "Scan current root:", "JSON scan:", "scan-report writes reports only", "propose-fixes writes untrusted candidate proposals only", "proposal apply_allowed remains false"]),
        (["commands"], ["Safe command list", "help", "scan-report --root .", "propose-fixes --root .", "Forbidden commands fail closed"]),
        (["safety"], ["quantum-inspired only", "no real quantum computation", "no quantum/provider/cloud API", "no network/provider calls", "no model inference", "no background worker", "no startup autorun", "no file move/delete/rewrite", "no candidate execution", "no trusted-memory write", "no memory promotion", "no route/queue mutation", "no apply/collapse/trust/promote behavior"]),
    ]
    for args, expected_phrases in discovery_cases:
        result = run_module(args)
        label = "no-arg help" if not args else args[0]
        require(result.returncode == 0, f"{label} failed: {result.stderr.strip()}")
        output = result.stdout
        for phrase in expected_phrases:
            require(phrase in output, f"{label} output missing phrase: {phrase}")
    after = output_snapshot()
    require(before == after, "discovery commands must not write or modify report files")
    emit("PASS", "help/examples/commands/safety discovery works and writes no files")


def verify_commands() -> None:
    with create_sample_root() as temp_root:
        root = Path(temp_root)
        for command in ["status", "automation-status"]:
            result = run_module([command])
            require(result.returncode == 0, f"{command} failed: {result.stderr.strip()}")

        scan_result = run_module(["json", "--root", str(root)])
        scan = parse_json_output(scan_result, "json")
        require(scan.get("root_exists") is True, "sample scan root should exist")
        require(scan.get("files_reported_count", 0) >= 5, "sample scan should report files")
        for record in scan.get("records", []):
            missing = [field for field in REQUIRED_RECORD_FIELDS if field not in record]
            require(not missing, f"record missing fields {missing}: {record.get('path')}")
            require(record.get("collapse_allowed") is False, "record collapse_allowed must be false")
            require(record.get("runtime_enabled") is False, "record runtime_enabled must be false")
            require(record.get("safe_to_execute") is False, "record safe_to_execute must be false")

        nodes = {record.get("debruijn_node") for record in scan.get("records", [])}
        require("011" in nodes, "sample verifier should classify as node 011")
        require("111" in nodes, "sample remote boundary should classify as node 111")

        for command in ["scan", "automation-json", "entanglement"]:
            result = run_module([command, "--root", str(root)])
            require(result.returncode == 0, f"{command} failed: {result.stderr.strip()}")

        report_payload = parse_json_output(run_module(["scan-report", "--root", str(root)]), "scan-report")
        require(report_payload.get("status") == "status_report_only", "scan-report status mismatch")
        for output in report_payload.get("output_files", []):
            require(Path(output).exists(), f"scan-report output missing: {output}")

        proposal_payload = parse_json_output(run_module(["propose-fixes", "--root", str(root)]), "propose-fixes")
        require(proposal_payload.get("status") == "untrusted_candidate", "proposal status mismatch")
        require(proposal_payload.get("apply_allowed") is False, "proposal apply_allowed must be false")

        for forbidden_command in [
            "apply",
            "collapse",
            "promote",
            "trust",
            "move",
            "delete",
            "rewrite",
            "repair",
            "autorun",
            "daemon",
            "watch",
            "schedule",
            "sync",
            "provider",
            "quantum-run",
        ]:
            blocked = run_module([forbidden_command, "--root", str(root)])
            require(blocked.returncode != 0, f"{forbidden_command} command must fail closed")
            require("SAFE_ERROR" in blocked.stderr, f"{forbidden_command} command must return safe error")
    emit("PASS", "safe CLI commands work and unsafe command fails closed")


def verify_generated_outputs() -> None:
    verify_output_folder()
    latest_json = OUTPUT_ROOT / "latest_status.json"
    latest_md = OUTPUT_ROOT / "latest_status.md"
    require(latest_json.exists(), "scan-report did not write latest_status.json")
    require(latest_md.exists(), "scan-report did not write latest_status.md")
    latest = load_json(latest_json)
    require(latest.get("status") == "status_report_only", "latest_status.json status mismatch")
    require(latest.get("safety", {}).get("files_moved") is False, "latest status must confirm no file movement")
    proposals = sorted(OUTPUT_ROOT.glob("candidate_fix_proposals_*.json"))
    require(proposals, "propose-fixes did not write a proposal JSON")
    proposal = load_json(proposals[-1])
    require(proposal.get("status") == "untrusted_candidate", "proposal JSON must remain untrusted_candidate")
    require(proposal.get("apply_allowed") is False, "proposal JSON apply_allowed must be false")
    receipts = sorted(OUTPUT_ROOT.glob("automation_receipt_*.md"))
    require(receipts, "receipt was not created")
    receipt_text = receipts[-1].read_text(encoding="utf-8", errors="replace")
    for phrase in [
        "No files were moved.",
        "No files were deleted.",
        "No source files were rewritten.",
        "No candidate content was executed.",
        "No trusted memory was promoted.",
        "No routes were mutated.",
        "No live queues were mutated.",
        "No provider/API/network/quantum service was called.",
        "No automatic approval or collapse occurred.",
    ]:
        require(phrase in receipt_text, f"receipt missing safety phrase: {phrase}")
    emit("PASS", "generated scan/proposal outputs are report-only and untrusted")


def main() -> int:
    try:
        verify_contract()
        verify_static_source()
        verify_output_folder()
        verify_discovery_commands()
        verify_commands()
        verify_generated_outputs()
    except VerificationError as exc:
        emit("FAIL", str(exc))
        return 1
    except py_compile.PyCompileError as exc:
        emit("FAIL", str(exc))
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
