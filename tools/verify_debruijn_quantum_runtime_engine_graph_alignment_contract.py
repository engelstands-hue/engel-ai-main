#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"

CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / f"{CONTRACT_ID}.md"

PASS_MARKER = "DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_CONTRACT_VERIFICATION_PASS"

REQUIRED_FILES = [
    CONTRACT_JSON,
    CONTRACT_MD,
    CONTRACT_REPORT,
]

RELATED_FILES = [
    ROOT / "memory" / "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1.json",
    ROOT / "tools" / "verify_debruijn_graph_sequence_model.py",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_V1.json",
    ROOT / "tools" / "verify_debruijn_quantum_runtime_engine_contract.py",
    ROOT / "engel_debruijn_quantum_runtime.py",
    ROOT / "tools" / "verify_debruijn_quantum_runtime_engine.py",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1.json",
    ROOT / "tools" / "verify_debruijn_quantum_apply_engine_contract.py",
    ROOT / "engel_debruijn_quantum_apply.py",
    ROOT / "tools" / "verify_debruijn_quantum_apply_engine.py",
]

FALSE_FLAGS = [
    "graph_alignment_enabled_now",
    "runtime_source_changed_now",
    "apply_source_changed_now",
    "build_promote_changed_now",
    "command_route_added_now",
    "source_mutation_enabled_now",
    "route_mutation_enabled_now",
    "queue_mutation_enabled_now",
    "trusted_memory_write_enabled_now",
    "provider_api_enabled_now",
    "network_enabled_now",
    "local_llm_inference_enabled_now",
    "background_worker_enabled_now",
    "autorun_enabled_now",
    "build_promote_enabled_now",
]

REQUIRED_KEYS = [
    "current_enabled_flags",
    "node_state_alignment",
    "edge_transition_alignment",
    "append_shift_alignment",
    "traversal_coverage_alignment",
    "measurement_alignment",
    "receipt_alignment",
    "runtime_output_alignment",
    "safety_boundary",
    "future_verifier",
    "future_implementation_sequence",
    "safety_preserved",
    "recommended_next_slice",
]

NODE_FIELDS = [
    "node_state_id",
    "state_type",
    "artifact_path",
    "present",
    "source",
    "metadata",
    "coverage_status",
]

NODE_STATES = [
    "concrete artifact states",
    "basis states",
    "candidate states",
    "contract_present",
    "verifier_present",
    "report_present",
    "route_documented",
    "proposal_untrusted",
    "runtime_contract_defined",
    "apply_contract_missing",
    "build_contract_missing",
    "password_gate_required",
    "human_review_required",
]

EDGE_FIELDS = [
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
]

APPEND_SHIFT_TERMS = [
    "current artifact context/state",
    "valid transition",
    "new artifact or state evidence",
    "preserved context from previous state",
    "verified project-structure map",
]

APPEND_SHIFT_EXAMPLES = [
    ("contract_present", "verifier_candidate"),
    ("verifier_present", "report_candidate"),
    ("runtime_contract_defined", "runtime_engine_candidate"),
    ("source_smoke_passed", "closeout_candidate"),
    ("closeout_ready", "selective_commit_candidate"),
]

TRAVERSAL_TERMS = [
    "ordered traversal",
    "visited edges",
    "unvisited edges",
    "repeated review loops",
    "cycles",
    "missing edge detection",
    "coverage summaries",
]

COVERAGE_STATUSES = [
    "unvisited",
    "candidate_generated",
    "verifier_reviewed",
    "suppressed",
    "approved_for_apply_candidate",
    "applied_review_required",
    "verified_complete",
]

MEASUREMENT_STATUSES = [
    "unmeasured_candidate",
    "report_only_selected",
    "human_review_required",
    "verified_for_apply",
    "approved_apply_candidate",
    "applied_review_required",
    "build_promote_candidate",
    "verified_complete",
]

FUTURE_ONLY_MEASUREMENTS = [
    "approved_apply_candidate",
    "applied_review_required",
    "build_promote_candidate",
]

RECEIPT_FIELDS = [
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
]

EDGE_LABEL_RECEIPT_FIELDS = [
    "source_state",
    "target_state",
    "transition_type",
    "append_operation",
    "overlap_preserved",
    "evidence_file",
    "verifier_result",
    "safety_gate_result",
    "human_review_status",
]

RUNTIME_OUTPUT_TERMS = [
    "graph status summary",
    "node state report",
    "edge transition report",
    "coverage report",
    "ranked edge candidates",
    "selected report-only transitions",
    "receipt path",
]

RUNTIME_OUTPUT_REQUIRED_VALUES = {
    "apply_allowed": False,
    "human_review_required": True,
    "no_apply_performed": True,
    "no_trust_performed": True,
    "no_promote_performed": True,
}

FORBIDDEN_TERMS = [
    "silent graph mutation",
    "unlabelled transition",
    "applying an edge without verifier evidence",
    "treating repeated traversal as trusted memory",
    "auto-trusting generated proposals",
    "auto-applying generated proposals",
    "auto-building from traversal",
    "auto-promoting from traversal",
    "source mutation outside approved apply flow",
    "route/queue mutation outside approved apply flow",
    "trusted-memory write without approved memory promotion flow",
    "provider/network/model/local LLM behavior without separate approved contract",
    "background/autorun/scheduler without separate approved contract",
    "password/salt/hash exposure",
    "committing local password config",
]

EXPECTED_SEQUENCE = [
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_SOURCE_SMOKE_V2",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_CLOSEOUT_REVIEW_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1",
]

EXCLUDED_DIRS = {
    ".git",
    "build",
    "dist",
    "live",
    "backups",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "reports",
    "memory",
}

SCAN_SUFFIXES = {".py", ".ps1", ".json", ".toml", ".yaml", ".yml", ".bat", ".cmd"}

ACTIVE_PATTERNS = [
    re.compile(r"graph_alignment_enabled_now\s*=\s*true", re.IGNORECASE),
    re.compile(r"runtime_source_changed_now\s*=\s*true", re.IGNORECASE),
    re.compile(r"apply_source_changed_now\s*=\s*true", re.IGNORECASE),
    re.compile(r"build_promote_changed_now\s*=\s*true", re.IGNORECASE),
    re.compile(r"command_route_added_now\s*=\s*true", re.IGNORECASE),
    re.compile(r"silent[_\s-]*graph[_\s-]*mutation", re.IGNORECASE),
    re.compile(r"unlabelled[_\s-]*transition", re.IGNORECASE),
    re.compile(r"auto[_\s-]*apply.*graph.*transition|graph.*transition.*auto[_\s-]*apply", re.IGNORECASE),
    re.compile(r"auto[_\s-]*build.*graph.*transition|graph.*transition.*auto[_\s-]*build", re.IGNORECASE),
    re.compile(r"auto[_\s-]*promote.*graph.*transition|graph.*transition.*auto[_\s-]*promote", re.IGNORECASE),
    re.compile(r"traversal.*trusted[_\s-]*memory|trusted[_\s-]*memory.*traversal", re.IGNORECASE),
    re.compile(r"source.*mutation.*graph.*alignment|graph.*alignment.*source.*mutation", re.IGNORECASE),
    re.compile(r"route.*queue.*mutation.*graph.*alignment|graph.*alignment.*route.*queue.*mutation", re.IGNORECASE),
    re.compile(r"trusted[_\s-]*memory[_\s-]*write.*graph.*alignment|graph.*alignment.*trusted[_\s-]*memory[_\s-]*write", re.IGNORECASE),
    re.compile(r"provider.*network.*model.*graph.*alignment|graph.*alignment.*provider.*network.*model", re.IGNORECASE),
    re.compile(r"local[_\s-]*llm.*graph.*alignment|graph.*alignment.*local[_\s-]*llm", re.IGNORECASE),
    re.compile(r"background.*autorun.*graph.*alignment|graph.*alignment.*background.*autorun", re.IGNORECASE),
    re.compile(r"scheduler.*graph.*alignment|graph.*alignment.*scheduler", re.IGNORECASE),
]

SAFE_LINE_MARKERS = [
    "forbid",
    "forbidden",
    "must not",
    "do not",
    "never",
    "disabled",
    "future",
    "contract",
    "contract_only",
    "review_required",
    "verifier",
    "scan",
    "pattern",
    "no ",
    "no_",
    "without separate",
    "false",
]


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.review_required: list[str] = []

    def line(self, level: str, message: str) -> None:
        print(f"{level} {message}", flush=True)

    def pass_(self, message: str) -> None:
        self.line("PASS", message)

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.line("FAIL", message)

    def info(self, message: str) -> None:
        self.line("INFO", message)

    def skip(self, message: str) -> None:
        self.line("SKIP", message)

    def review(self, message: str) -> None:
        self.review_required.append(message)
        self.line("REVIEW_REQUIRED", message)


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def normalize(value: Any) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    text = text.lower().replace("\\", " ")
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_term(blob: str, term: str) -> bool:
    return normalize(term) in blob


def require_terms(check: Check, label: str, value: Any, terms: list[str]) -> None:
    blob = normalize(value)
    missing = [term for term in terms if not has_term(blob, term)]
    if missing:
        check.fail(f"{label} missing required terms: {', '.join(missing)}")
    else:
        check.pass_(f"{label} contains required terms")


def require_pairs(check: Check, label: str, value: Any, pairs: list[tuple[str, str]]) -> None:
    blob = normalize(value)
    missing = [f"{left} -> {right}" for left, right in pairs if not (has_term(blob, left) and has_term(blob, right))]
    if missing:
        check.fail(f"{label} missing examples: {', '.join(missing)}")
    else:
        check.pass_(f"{label} contains required examples")


def read_required(check: Check) -> tuple[dict[str, Any] | None, str, str]:
    missing = [path for path in REQUIRED_FILES if not path.exists()]
    if missing:
        for path in missing:
            check.fail(f"required graph-alignment contract file missing: {rel(path)}")
        return None, "", ""
    for path in REQUIRED_FILES:
        check.pass_(f"required graph-alignment contract file exists: {rel(path)}")
    try:
        data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        check.fail(f"contract JSON is invalid: {exc}")
        return None, "", ""
    check.pass_("contract JSON parsed")
    return (
        data,
        CONTRACT_MD.read_text(encoding="utf-8"),
        CONTRACT_REPORT.read_text(encoding="utf-8"),
    )


def inspect_related(check: Check) -> None:
    for path in RELATED_FILES:
        if path.exists():
            check.info(f"related file present for context: {rel(path)}")
        else:
            check.skip(f"related file not present: {rel(path)}")


def check_identity_and_flags(check: Check, data: dict[str, Any]) -> None:
    expected = {
        "contract_id": CONTRACT_ID,
        "status": "contract_only",
        "active_workspace": WORKSPACE_TEXT,
        "aligns_runtime_engine": "debruijn_quantum_runtime_engine",
        "source_model_contract": "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1",
    }
    for key, value in expected.items():
        if data.get(key) == value:
            check.pass_(f"{key} matches expected value")
        else:
            check.fail(f"{key} expected {value!r}, got {data.get(key)!r}")

    missing_keys = [key for key in REQUIRED_KEYS if key not in data]
    if missing_keys:
        check.fail(f"contract JSON missing required keys: {', '.join(missing_keys)}")
    else:
        check.pass_("contract JSON includes all required top-level keys")

    current_flags = data.get("current_enabled_flags", {})
    for flag in FALSE_FLAGS:
        top_value = data.get(flag)
        nested_value = current_flags.get(flag) if isinstance(current_flags, dict) else None
        if top_value is False and nested_value is False:
            check.pass_(f"{flag} is false at top level and in current_enabled_flags")
        else:
            check.fail(f"{flag} must be false at top level and in current_enabled_flags")


def check_node_edge_append(check: Check, data: dict[str, Any]) -> None:
    node = data.get("node_state_alignment")
    require_terms(check, "node_state_alignment fields", node, NODE_FIELDS)
    require_terms(check, "node_state_alignment states", node, NODE_STATES)

    edge = data.get("edge_transition_alignment")
    require_terms(check, "edge_transition_alignment fields", edge, EDGE_FIELDS)
    require_terms(check, "edge_transition_alignment no-silent rule", edge, ["no silent transitions"])

    append = data.get("append_shift_alignment")
    require_terms(check, "append_shift_alignment mapping", append, APPEND_SHIFT_TERMS)
    require_pairs(check, "append_shift_alignment examples", append, APPEND_SHIFT_EXAMPLES)


def check_traversal_measurement_receipts(check: Check, data: dict[str, Any]) -> None:
    traversal = data.get("traversal_coverage_alignment")
    require_terms(check, "traversal_coverage_alignment tracking", traversal, TRAVERSAL_TERMS)
    require_terms(check, "traversal_coverage_alignment statuses", traversal, COVERAGE_STATUSES)

    measurement = data.get("measurement_alignment")
    require_terms(check, "measurement_alignment statuses", measurement, MEASUREMENT_STATUSES)
    require_terms(check, "measurement_alignment future-only apply/build statuses", measurement, FUTURE_ONLY_MEASUREMENTS)
    require_terms(
        check,
        "measurement_alignment runtime restriction",
        measurement,
        ["runtime", "must", "not", "set", "future", "apply", "build", "external"],
    )

    receipt = data.get("receipt_alignment")
    require_terms(check, "receipt_alignment graph fields", receipt, RECEIPT_FIELDS)
    require_terms(check, "receipt_alignment edge label fields", receipt, EDGE_LABEL_RECEIPT_FIELDS)

    output = data.get("runtime_output_alignment")
    require_terms(check, "runtime_output_alignment reports", output, RUNTIME_OUTPUT_TERMS)
    required_values = output.get("runtime_output_must_keep") if isinstance(output, dict) else None
    if not isinstance(required_values, dict):
        check.fail("runtime_output_alignment.runtime_output_must_keep must be a mapping")
    else:
        for key, expected in RUNTIME_OUTPUT_REQUIRED_VALUES.items():
            if required_values.get(key) == expected:
                check.pass_(f"runtime_output_alignment requires {key} == {expected}")
            else:
                check.fail(f"runtime_output_alignment must require {key} == {expected}")


def check_safety_sequence(check: Check, data: dict[str, Any]) -> None:
    safety = data.get("safety_boundary")
    require_terms(check, "safety_boundary forbidden behavior", safety, FORBIDDEN_TERMS)

    future_verifier = data.get("future_verifier")
    require_terms(
        check,
        "future_verifier",
        future_verifier,
        [
            "tools\\verify_debruijn_quantum_runtime_engine_graph_alignment_contract.py",
            "graph alignment currently disabled",
            "source not changed",
            "graph model verifier passes",
            "runtime engine verifier passes",
        ],
    )

    sequence = data.get("future_implementation_sequence")
    if not isinstance(sequence, list):
        check.fail("future_implementation_sequence must be a list")
    else:
        missing = [item for item in EXPECTED_SEQUENCE if item not in sequence]
        if missing:
            check.fail(f"future_implementation_sequence missing: {', '.join(missing)}")
        else:
            positions = [sequence.index(item) for item in EXPECTED_SEQUENCE]
            if positions == sorted(positions):
                check.pass_("future_implementation_sequence contains required ordered slices")
            else:
                check.fail("future_implementation_sequence contains required entries out of order")

    preserved = data.get("safety_preserved")
    require_terms(
        check,
        "safety_preserved",
        preserved,
        [
            "contract_only",
            "no_runtime_source_changed",
            "no_apply_source_changed",
            "no_build_promote_source_changed",
            "no_command_route_added",
            "no_staging_or_commit",
            "no_password_values_exposed",
        ],
    )

    if data.get("recommended_next_slice") == "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_VERIFIER_V1":
        check.pass_("recommended_next_slice points to graph-alignment verifier")
    else:
        check.fail("recommended_next_slice must be ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_VERIFIER_V1")


def should_skip_path(path: Path) -> bool:
    try:
        rel_parts = path.resolve(strict=False).relative_to(ROOT.resolve(strict=False)).parts
    except ValueError:
        return True
    if any(part in EXCLUDED_DIRS for part in rel_parts):
        return True
    if path == Path(__file__).resolve():
        return True
    if len(rel_parts) >= 2 and rel_parts[0] == "tools" and path.name.startswith("verify_"):
        return True
    return path.suffix.lower() not in SCAN_SUFFIXES


def is_safe_line(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in SAFE_LINE_MARKERS)


def active_source_scan(check: Check) -> None:
    findings: list[str] = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS and not name.startswith(".")]
        for filename in filenames:
            path = Path(dirpath) / filename
            if should_skip_path(path):
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                check.review(f"could not read active source file {rel(path)}: {exc}")
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if is_safe_line(line):
                    continue
                if any(pattern.search(line) for pattern in ACTIVE_PATTERNS):
                    findings.append(f"{rel(path)}:{lineno}: {line.strip()[:160]}")

    check.info(f"active source scan inspected {scanned} source/config files")
    if findings:
        for finding in findings:
            check.review(f"possible active graph-alignment behavior: {finding}")
        check.fail("active source scan found possible active graph-alignment behavior")
    else:
        check.pass_("active source scan found no active runtime graph-alignment behavior")


def main() -> int:
    check = Check()
    if ROOT.resolve(strict=False) != Path(WORKSPACE_TEXT).resolve(strict=False):
        check.fail(f"verifier must run inside {WORKSPACE_TEXT}; resolved root is {ROOT}")
        return 1

    data, _md_text, _report_text = read_required(check)
    inspect_related(check)
    if data is None:
        return 1

    check_identity_and_flags(check, data)
    check_node_edge_append(check, data)
    check_traversal_measurement_receipts(check, data)
    check_safety_sequence(check, data)
    active_source_scan(check)

    if check.failures:
        check.info(f"verification failed with {len(check.failures)} failure(s)")
        return 1

    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
