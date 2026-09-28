#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULE = ROOT / "engel_debruijn_quantum_runtime.py"
RECEIPT_FOLDER = ROOT / "reports" / "debruijn_quantum_runtime_receipts"
PASS_MARKER = "DEBRUIJN_QUANTUM_RUNTIME_ENGINE_VERIFICATION_PASS"

PROTECTED_FILES = [
    ROOT / "engel_app.py",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_V1.json",
    RUNTIME_MODULE,
]

REQUIRED_MODELS = [
    "BasisState",
    "CandidateState",
    "TransitionPath",
    "RuntimeResult",
]

REQUIRED_BASIS_FIELDS = [
    "node_state_id",
    "state_type",
    "artifact_path",
    "present",
    "source",
    "metadata",
    "coverage_status",
]

REQUIRED_EDGE_FIELDS = [
    "source_state",
    "target_state",
    "transition_type",
    "edge_transition_id",
    "edge_label",
    "append_operation",
    "overlap_preserved",
    "sequence_position",
    "visited_before",
    "coverage_status",
    "evidence_file",
    "verifier_result",
    "safety_gate_result",
    "receipt_path",
    "human_review_status",
    "verifier_interference_score",
    "measurement_status",
]

REQUIRED_GRAPH_RESULT_FIELDS = [
    "node_state_count",
    "edge_transition_count",
    "traversal_sequence_length",
    "coverage_summary",
    "unvisited_edges",
    "repeated_edges",
    "graph_sequence_model_contract_id",
    "edge_labels",
    "selected_edge_candidates",
    "measurement_summary",
    "no_trust_performed",
    "no_promote_performed",
]

FORBIDDEN_RUNTIME_MEASUREMENT_STATUSES = {
    "verified_for_apply",
    "approved_apply_candidate",
    "applied_review_required",
    "build_promote_candidate",
}

REQUIRED_FUNCTIONS = [
    "compute_basis_states",
    "compute_candidate_superposition",
    "compute_transition_paths",
    "apply_verifier_interference",
    "select_ranked_candidates",
    "run_debruijn_quantum_runtime",
    "write_runtime_receipts",
    "build_runtime_status",
]

FORBIDDEN_IMPORT_TOKENS = [
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "http.client",
    "ftplib",
    "paramiko",
    "openai",
    "anthropic",
    "transformers",
    "llama_cpp",
    "torch",
    "tensorflow",
    "multiprocessing",
    "threading",
    "asyncio",
]

FORBIDDEN_SOURCE_PATTERNS = [
    "shell=True",
    "os.system",
    "popen",
    "runpy",
    "exec(",
    "eval(",
    "git add",
    "git commit",
    "git push",
    "pyinstaller",
    "pip install",
    "trusted_memory_write_enabled_now = True",
    "source_mutation_enabled_now = True",
    "route_mutation_enabled_now = True",
    "queue_mutation_enabled_now = True",
    "provider_api_enabled_now = True",
    "network_enabled_now = True",
    "local_llm_inference_enabled_now = True",
    "background_worker_enabled_now = True",
    "auto_apply",
    "auto_build",
    "auto_promote",
]


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.infos: list[str] = []

    def line(self, level: str, message: str) -> None:
        print(f"{level} {message}")

    def pass_(self, message: str) -> None:
        self.line("PASS", message)

    def info(self, message: str) -> None:
        self.infos.append(message)
        self.line("INFO", message)

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.line("FAIL", message)


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def file_hash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_files(paths: list[Path]) -> dict[str, tuple[str | None, int | None]]:
    snapshot: dict[str, tuple[str | None, int | None]] = {}
    for path in paths:
        try:
            mtime = path.stat().st_mtime_ns if path.exists() else None
        except OSError:
            mtime = None
        snapshot[rel(path)] = (file_hash(path), mtime)
    return snapshot


def receipt_listing() -> set[str]:
    if not RECEIPT_FOLDER.exists():
        return set()
    return {rel(path) for path in RECEIPT_FOLDER.glob("*") if path.is_file()}


def load_runtime_module(check: Check) -> Any | None:
    if not RUNTIME_MODULE.exists():
        check.fail("runtime module missing")
        return None
    spec = importlib.util.spec_from_file_location("engel_debruijn_quantum_runtime", RUNTIME_MODULE)
    if spec is None or spec.loader is None:
        check.fail("runtime module import spec could not be created")
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        check.fail(f"runtime module import failed: {type(exc).__name__}: {exc}")
        return None
    check.pass_("runtime module imports without side effects")
    return module


def check_static_source(check: Check) -> None:
    text = RUNTIME_MODULE.read_text(encoding="utf-8")
    lowered = text.lower()
    for token in FORBIDDEN_IMPORT_TOKENS:
        if f"import {token}" in lowered or f"from {token}" in lowered:
            check.fail(f"forbidden import token found: {token}")
    for pattern in FORBIDDEN_SOURCE_PATTERNS:
        pattern_lower = pattern.lower()
        for line in lowered.splitlines():
            if pattern_lower not in line:
                continue
            if any(marker in line for marker in ["no_", "no ", "not ", "forbidden", "false", "never"]):
                continue
            check.fail(f"forbidden source pattern found: {pattern}")
    if ".write_text(" in text:
        if "RUNTIME_RECEIPT_FOLDER" not in text or "write_runtime_receipts" not in text:
            check.fail("write_text appears outside declared runtime receipt writer pattern")
    if "open(" in text:
        check.fail("raw open() calls are not allowed in runtime module")
    check.pass_("static source safety scan")


def check_models_and_functions(check: Check, module: Any) -> None:
    for name in REQUIRED_MODELS:
        if not hasattr(module, name):
            check.fail(f"missing data model {name}")
    for name in REQUIRED_FUNCTIONS:
        if not callable(getattr(module, name, None)):
            check.fail(f"missing function {name}")
    for key, upper in {
        "MAX_SCAN_FILES": 10000,
        "MAX_CANDIDATE_STATES": 500,
        "MAX_TRANSITION_DEPTH": 6,
        "MAX_RUNTIME_SECONDS": 180,
        "MAX_OUTPUT_BYTES": 200000,
    }.items():
        value = getattr(module, key, None)
        if not isinstance(value, int) or value > upper:
            check.fail(f"{key} must be integer <= {upper}, got {value!r}")
    for model_name, required_fields in {
        "BasisState": REQUIRED_BASIS_FIELDS,
        "TransitionPath": REQUIRED_EDGE_FIELDS,
        "RuntimeResult": REQUIRED_GRAPH_RESULT_FIELDS,
    }.items():
        model = getattr(module, model_name, None)
        if not is_dataclass(model):
            check.fail(f"{model_name} must remain a dataclass")
            continue
        model_fields = {field.name for field in fields(model)}
        missing = [field for field in required_fields if field not in model_fields]
        if missing:
            check.fail(f"{model_name} missing graph-alignment fields: {missing}")
    check.pass_("data models, functions, and runtime limits")


def check_status_is_read_only(check: Check, module: Any) -> None:
    before_files = snapshot_files(PROTECTED_FILES)
    before_receipts = receipt_listing()
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = module.main(["status"])
    after_files = snapshot_files(PROTECTED_FILES)
    after_receipts = receipt_listing()
    if code != 0:
        check.fail(f"status CLI returned {code}")
    if before_files != after_files:
        check.fail("status CLI modified protected files")
    if before_receipts != after_receipts:
        check.fail("status CLI wrote runtime receipts")
    output = stdout.getvalue().lower()
    if "status_writes_files: false" not in output:
        check.fail("status CLI did not declare read-only behavior")
    for marker in [
        "graph_sequence_model_contract_id:",
        "node_state_count:",
        "edge_transition_count:",
        "traversal_sequence_length:",
        "selected_edge_candidates_count:",
        "no_trust_performed: true",
        "no_promote_performed: true",
    ]:
        if marker not in output:
            check.fail(f"status CLI missing graph-alignment marker {marker}")
    check.pass_("status CLI read-only smoke")


def check_unsafe_cli_rejected(check: Check, module: Any) -> None:
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            result = module.main(["apply"])
    except SystemExit as exc:
        result = int(exc.code or 0)
    if result == 0:
        check.fail("unsafe CLI command was accepted")
    else:
        check.pass_("unsafe CLI command rejected")


def check_graph_alignment_result(check: Check, result: Any, receipt_json: Path | None) -> None:
    for field_name in REQUIRED_GRAPH_RESULT_FIELDS:
        if not hasattr(result, field_name):
            check.fail(f"runtime result missing graph field {field_name}")

    if getattr(result, "graph_sequence_model_contract_id", None) != "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1":
        check.fail("runtime result graph_sequence_model_contract_id mismatch")
    if getattr(result, "node_state_count", 0) <= 0:
        check.fail("runtime result node_state_count must be positive")
    if getattr(result, "edge_transition_count", 0) <= 0:
        check.fail("runtime result edge_transition_count must be positive")
    if getattr(result, "traversal_sequence_length", None) != getattr(result, "edge_transition_count", None):
        check.fail("runtime result traversal_sequence_length must match edge_transition_count")
    if getattr(result, "no_trust_performed", None) is not True:
        check.fail("runtime result must set no_trust_performed true")
    if getattr(result, "no_promote_performed", None) is not True:
        check.fail("runtime result must set no_promote_performed true")

    edge_labels = getattr(result, "edge_labels", [])
    selected_edges = getattr(result, "selected_edge_candidates", [])
    if not isinstance(edge_labels, list) or not edge_labels:
        check.fail("runtime result edge_labels must be a non-empty list")
    if not isinstance(selected_edges, list) or not selected_edges:
        check.fail("runtime result selected_edge_candidates must be a non-empty list")

    for edge in list(edge_labels)[:10] + list(selected_edges)[:10]:
        for field_name in REQUIRED_EDGE_FIELDS:
            if field_name not in edge:
                check.fail(f"edge label missing field {field_name}")
        if not edge.get("edge_label"):
            check.fail("edge label cannot be empty")
        if edge.get("measurement_status") in FORBIDDEN_RUNTIME_MEASUREMENT_STATUSES:
            check.fail(f"runtime edge used future-only measurement status {edge.get('measurement_status')}")
        if edge.get("human_review_status") != "human_review_required":
            check.fail("edge label must keep human_review_required status")

    for candidate in getattr(result, "ranked_candidates", []):
        if candidate.get("measurement_status") in FORBIDDEN_RUNTIME_MEASUREMENT_STATUSES:
            check.fail(f"runtime candidate used future-only measurement status {candidate.get('measurement_status')}")
        if candidate.get("coverage_status") not in {"candidate_generated", "suppressed", "verifier_reviewed"}:
            check.fail(f"runtime candidate has unexpected coverage_status {candidate.get('coverage_status')}")

    if receipt_json is not None and receipt_json.exists():
        try:
            receipt = json.loads(receipt_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            check.fail(f"runtime receipt JSON could not be parsed: {exc}")
            return
        for field_name in REQUIRED_GRAPH_RESULT_FIELDS:
            if field_name not in receipt:
                check.fail(f"runtime receipt missing graph field {field_name}")
        if not receipt.get("edge_labels"):
            check.fail("runtime receipt must include edge_labels")
        if not receipt.get("selected_edge_candidates"):
            check.fail("runtime receipt must include selected_edge_candidates")
        if receipt.get("no_trust_performed") is not True:
            check.fail("runtime receipt must set no_trust_performed true")
        if receipt.get("no_promote_performed") is not True:
            check.fail("runtime receipt must set no_promote_performed true")
    check.pass_("graph-sequence runtime alignment result")


def check_runtime_report_only_smoke(check: Check, module: Any) -> None:
    before_files = snapshot_files(PROTECTED_FILES)
    before_receipts = receipt_listing()
    result = module.run_debruijn_quantum_runtime(ROOT, "runtime_report_only")
    after_files = snapshot_files(PROTECTED_FILES)
    after_receipts = receipt_listing()

    changed_protected = {
        path: (before_files.get(path), after_files.get(path))
        for path in before_files
        if before_files.get(path) != after_files.get(path)
    }
    if changed_protected:
        check.fail(f"report-only runtime modified protected files: {sorted(changed_protected)}")

    new_receipts = after_receipts - before_receipts
    reported_changes = set(result.files_changed_by_runtime)
    if not new_receipts:
        check.fail("report-only runtime did not create receipt files")
    if new_receipts != reported_changes:
        check.fail(f"receipt files mismatch new={sorted(new_receipts)} reported={sorted(reported_changes)}")
    if any(not path.startswith(r"reports\debruijn_quantum_runtime_receipts" + "\\") for path in reported_changes):
        check.fail("runtime wrote outside approved receipt folder")
    receipt_json = next(
        (
            ROOT / path
            for path in reported_changes
            if path.endswith(".json") and path.startswith(r"reports\debruijn_quantum_runtime_receipts" + "\\")
        ),
        None,
    )
    if result.action_type != "runtime_report_only":
        check.fail("runtime result action_type mismatch")
    if result.no_apply_performed is not True:
        check.fail("runtime result must set no_apply_performed true")
    if result.human_review_required is not True:
        check.fail("runtime result must require human review")
    if result.password_gate_result not in {"not_required", "required_for_future_apply", "redacted"}:
        check.fail("runtime result has unexpected password gate result")

    for candidate in result.ranked_candidates:
        if candidate.get("apply_allowed") is not False:
            check.fail(f"candidate {candidate.get('candidate_id')} apply_allowed is not false")
        if candidate.get("human_review_required") is not True:
            check.fail(f"candidate {candidate.get('candidate_id')} human_review_required is not true")
        if candidate.get("runtime_generated") is not True:
            check.fail(f"candidate {candidate.get('candidate_id')} runtime_generated is not true")

    check_graph_alignment_result(check, result, receipt_json)
    check.pass_("report-only runtime smoke writes only approved receipts")


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local runtime verification only; no apply, route, queue, trusted-memory, provider, model, build, git, or package behavior")

    check_static_source(check)
    module = load_runtime_module(check)
    if module is not None:
        check_models_and_functions(check, module)
        check_status_is_read_only(check, module)
        check_unsafe_cli_rejected(check, module)
        check_runtime_report_only_smoke(check, module)

    if check.failures:
        check.line("FAIL", f"failure_count={len(check.failures)}")
        return 1

    check.pass_("runtime engine implementation result")
    check.pass_("receipt-only mutation result")
    check.pass_("candidate safety result")
    check.pass_("safety preserved")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
