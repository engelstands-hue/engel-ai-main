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

CONTRACT_ID = "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1"
MODEL_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
MODEL_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
INTEGRATION_REPORT = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_INTEGRATION_V1.md"
)

PASS_MARKER = "DEBRUIJN_GRAPH_SEQUENCE_MODEL_VERIFICATION_PASS"

REQUIRED_FILES = [
    MODEL_JSON,
    MODEL_MD,
    INTEGRATION_REPORT,
]

RELATED_FILES = [
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_V1.json",
    ROOT / "tools" / "verify_debruijn_quantum_runtime_engine_contract.py",
    ROOT / "engel_debruijn_quantum_runtime.py",
    ROOT / "tools" / "verify_debruijn_quantum_runtime_engine.py",
    ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1.json",
    ROOT / "tools" / "verify_debruijn_quantum_apply_engine_contract.py",
    ROOT / "engel_debruijn_quantum_apply.py",
    ROOT / "tools" / "verify_debruijn_quantum_apply_engine.py",
    ROOT / "tools" / "verify_debruijn_quantum_candidate_proposals.py",
    ROOT / "tools" / "verify_debruijn_quantum_entanglement_groups.py",
    ROOT / "tools" / "verify_debruijn_quantum_backend_status_consistency.py",
    ROOT / "tools" / "verify_engel_global_password_gate.py",
    ROOT / "tools" / "verify_untrusted_content_policy.py",
    ROOT / "tools" / "verify_de_bruijn_import_boundaries.py",
    ROOT / "tools" / "verify_authority_hierarchy.py",
    ROOT / "tools" / "verify_prompt_injection_guard.py",
]

REQUIRED_KEYS = [
    "model_sources",
    "node_state_model",
    "edge_transition_model",
    "append_shift_sequence_model",
    "candidate_superposition_model",
    "graph_traversal_model",
    "verifier_interference_model",
    "measurement_selection_model",
    "coverage_model",
    "edge_label_schema",
    "runtime_engine_implications",
    "apply_engine_implications",
    "build_promote_implications",
    "forbidden_behavior",
    "future_implementation_sequence",
    "safety_preserved",
    "recommended_next_slice",
]

MODEL_SOURCE_TITLES = [
    "Quantum View of the De Bruijn Graph",
    "How the De Bruijn Graph Builds the Sequence",
    "Full De Bruijn Sequence Graph",
]

NODE_STATE_TERMS = [
    "concrete Engel artifact states",
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

EDGE_TRANSITION_FIELDS = [
    "source_state",
    "target_state",
    "transition_type",
    "append_operation",
    "overlap_preserved",
    "evidence_file",
    "verifier_result",
    "safety_gate_result",
    "receipt_path",
    "human_review_status",
]

APPEND_SHIFT_TERMS = [
    "current artifact context/state",
    "valid transition",
    "new artifact or new state evidence",
    "transition record / receipt evidence",
    "Engel evolving verified project-structure map",
]

APPEND_SHIFT_EXAMPLES = [
    ("contract_present", "verifier_candidate"),
    ("verifier_present", "report_candidate"),
    ("runtime_contract_defined", "runtime_engine_candidate"),
    ("source_smoke_passed", "closeout_candidate"),
    ("closeout_ready", "selective_commit_candidate"),
]

CANDIDATE_SUPERPOSITION_TERMS = [
    "simultaneously",
    "not trusted by existence",
    "human_review_required",
    "apply_allowed false",
    "scores are classical",
    "never create trust",
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

TRAVERSAL_COVERAGE_TERMS = [
    "ordered",
    "edge label",
    "cycles",
    "review loops",
    "missing",
    "unvisited",
]

VERIFIER_INTERFERENCE_TERMS = [
    "amplify",
    "suppress",
    "untrusted-content",
    "De Bruijn import boundary",
    "authority hierarchy",
    "prompt-injection",
    "Global Password Gate",
    "candidate proposal verifier",
    "entanglement verifier",
    "backend status consistency",
    "route metadata verifier",
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

EDGE_LABEL_SCHEMA_FIELDS = [
    "node_state_id",
    "edge_transition_id",
    "edge_label",
    "append_operation",
    "overlap_preserved",
    "sequence_position",
    "visited_before",
    "coverage_status",
    "verifier_interference_score",
    "measurement_status",
    "receipt_path",
    "human_review_status",
]

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
    "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_INTEGRATION_V1",
    "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_VERIFIER_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_GRAPH_ALIGNMENT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_SOURCE_SMOKE_V2",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_GRAPH_ALIGNMENT_V1",
    "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_GRAPH_ALIGNMENT_CONTRACT_V1",
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
    "code_workspace",
}

SCAN_SUFFIXES = {".py", ".ps1", ".json", ".toml", ".yaml", ".yml", ".bat", ".cmd"}
ACTIVE_SCAN_SUBDIRS = {"tools", "scripts"}

ACTIVE_GRAPH_PATTERNS = [
    re.compile(r"silent[_\s-]*graph[_\s-]*mutation", re.IGNORECASE),
    re.compile(r"auto[_\s-]*apply.*graph|graph.*auto[_\s-]*apply", re.IGNORECASE),
    re.compile(r"auto[_\s-]*build.*graph|graph.*auto[_\s-]*build", re.IGNORECASE),
    re.compile(r"auto[_\s-]*promote.*graph|graph.*auto[_\s-]*promote", re.IGNORECASE),
    re.compile(r"traversal.*trusted[_\s-]*memory|trusted[_\s-]*memory.*traversal", re.IGNORECASE),
    re.compile(r"graph.*route[_/\s-]*queue.*mutation", re.IGNORECASE),
    re.compile(r"graph.*source.*mutation|source.*mutation.*graph", re.IGNORECASE),
    re.compile(r"graph.*trusted[_\s-]*memory[_\s-]*write", re.IGNORECASE),
    re.compile(r"graph.*provider.*network.*model|graph.*local[_\s-]*llm", re.IGNORECASE),
    re.compile(r"graph.*background.*autorun|graph.*scheduler", re.IGNORECASE),
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
    "model_contract",
    "review_required",
    "verifier",
    "scan",
    "pattern",
    "no ",
    "no_",
    "without separate",
]


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.review_required: list[str] = []
        self.infos: list[str] = []

    def line(self, level: str, message: str) -> None:
        print(f"{level} {message}", flush=True)

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.line("FAIL", message)

    def review(self, message: str) -> None:
        self.review_required.append(message)
        self.line("REVIEW_REQUIRED", message)

    def info(self, message: str) -> None:
        self.infos.append(message)
        self.line("INFO", message)

    def passed(self, message: str) -> None:
        self.line("PASS", message)

    def skip(self, message: str) -> None:
        self.line("SKIP", message)


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
        check.passed(f"{label} contains required terms")


def require_pairs(check: Check, label: str, value: Any, pairs: list[tuple[str, str]]) -> None:
    blob = normalize(value)
    missing = [f"{left} -> {right}" for left, right in pairs if not (has_term(blob, left) and has_term(blob, right))]
    if missing:
        check.fail(f"{label} missing transition examples: {', '.join(missing)}")
    else:
        check.passed(f"{label} contains required transition examples")


def require_sequence(check: Check, sequence: Any) -> None:
    if not isinstance(sequence, list):
        check.fail("future_implementation_sequence must be a list")
        return
    missing = [item for item in EXPECTED_SEQUENCE if item not in sequence]
    if missing:
        check.fail(f"future_implementation_sequence missing: {', '.join(missing)}")
        return
    positions = [sequence.index(item) for item in EXPECTED_SEQUENCE]
    if positions != sorted(positions):
        check.fail("future_implementation_sequence contains required entries out of order")
    else:
        check.passed("future_implementation_sequence contains required ordered slices")


def read_required_files(check: Check) -> tuple[dict[str, Any] | None, str, str]:
    missing = [path for path in REQUIRED_FILES if not path.exists()]
    if missing:
        for path in missing:
            check.fail(f"required model file missing: {rel(path)}")
        return None, "", ""

    for path in REQUIRED_FILES:
        check.passed(f"required model file exists: {rel(path)}")

    try:
        data = json.loads(MODEL_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        check.fail(f"model JSON is invalid: {exc}")
        return None, "", ""

    md_text = MODEL_MD.read_text(encoding="utf-8")
    report_text = INTEGRATION_REPORT.read_text(encoding="utf-8")
    check.passed("model JSON parsed")
    return data, md_text, report_text


def inspect_related_files(check: Check) -> None:
    for path in RELATED_FILES:
        if path.exists():
            check.info(f"related file present for context: {rel(path)}")
        else:
            check.skip(f"related file not present: {rel(path)}")


def check_identity(check: Check, data: dict[str, Any]) -> None:
    expected = {
        "contract_id": CONTRACT_ID,
        "status": "model_contract",
        "active_workspace": WORKSPACE_TEXT,
        "user_intent": "combined_debruijn_graph_sequence_quantum_model_for_runtime_apply_build",
    }
    for key, value in expected.items():
        if data.get(key) == value:
            check.passed(f"{key} matches expected value")
        else:
            check.fail(f"{key} expected {value!r}, got {data.get(key)!r}")

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        check.fail(f"model JSON missing required keys: {', '.join(missing)}")
    else:
        check.passed("model JSON includes all required top-level keys")


def check_model_sources(check: Check, data: dict[str, Any]) -> None:
    sources = data.get("model_sources", [])
    if not isinstance(sources, list):
        check.fail("model_sources must be a list")
        return
    blob = normalize(sources)
    missing = [title for title in MODEL_SOURCE_TITLES if not has_term(blob, title)]
    if missing:
        check.fail(f"model_sources missing visual source titles: {', '.join(missing)}")
    else:
        check.passed("model_sources include all three user visual models")


def check_models(check: Check, data: dict[str, Any], md_text: str) -> None:
    require_terms(check, "node_state_model", data.get("node_state_model"), NODE_STATE_TERMS)

    edge_model = {
        "edge_transition_model": data.get("edge_transition_model"),
        "edge_label_schema": data.get("edge_label_schema"),
    }
    require_terms(check, "edge_transition_model", edge_model, EDGE_TRANSITION_FIELDS)
    require_terms(check, "edge_transition_model no-silent rule", data.get("edge_transition_model"), ["No silent transitions"])

    append_text = {
        "append_shift_sequence_model": data.get("append_shift_sequence_model"),
        "edge_transition_model": data.get("edge_transition_model"),
        "markdown": md_text,
    }
    require_terms(check, "append_shift_sequence_model", append_text, APPEND_SHIFT_TERMS)
    require_pairs(check, "append_shift_sequence_model examples", append_text, APPEND_SHIFT_EXAMPLES)
    require_terms(check, "append_shift_sequence_model overlap rule", append_text, ["preserving", "overlap"])

    require_terms(
        check,
        "candidate_superposition_model",
        data.get("candidate_superposition_model"),
        CANDIDATE_SUPERPOSITION_TERMS,
    )

    traversal_coverage_text = {
        "graph_traversal_model": data.get("graph_traversal_model"),
        "coverage_model": data.get("coverage_model"),
    }
    require_terms(check, "graph_traversal_model and coverage_model", traversal_coverage_text, TRAVERSAL_COVERAGE_TERMS)
    require_terms(check, "coverage_model statuses", data.get("coverage_model"), COVERAGE_STATUSES)

    require_terms(check, "verifier_interference_model", data.get("verifier_interference_model"), VERIFIER_INTERFERENCE_TERMS)

    measurement_model = data.get("measurement_selection_model")
    require_terms(check, "measurement_selection_model statuses", measurement_model, MEASUREMENT_STATUSES)
    require_terms(
        check,
        "measurement_selection_model separation rules",
        measurement_model,
        [
            "runtime measurement selects reports/candidate packages only",
            "future apply engine",
            "future build/promote engine",
        ],
    )

    require_terms(check, "edge_label_schema", data.get("edge_label_schema"), EDGE_LABEL_SCHEMA_FIELDS)


def check_implications(check: Check, data: dict[str, Any]) -> None:
    require_terms(
        check,
        "runtime_engine_implications",
        data.get("runtime_engine_implications"),
        [
            "walk the graph",
            "rank missing/unverified paths",
            "write receipts/reports only",
            "never apply changes",
            "apply_allowed",
            "false",
            "human_review_required",
            "true",
            "source_mutation",
            "false",
            "route_mutation",
            "false",
            "queue_mutation",
            "false",
            "trusted_memory_write",
            "false",
        ],
    )
    require_terms(
        check,
        "apply_engine_implications",
        data.get("apply_engine_implications"),
        [
            "verified_for_apply true",
            "explicit approval phrase",
            "Global Password Gate",
            "validate paths",
            "bounded file-structure changes",
            "write apply receipt",
            "apply unverified proposal content",
        ],
    )
    require_terms(
        check,
        "build_promote_implications",
        data.get("build_promote_implications"),
        [
            "approved apply",
            "clean verifier state",
            "explicit approval phrase",
            "Global Password Gate",
            "clean selective file list",
            "auto-build from traversal",
        ],
    )


def check_forbidden_and_sequence(check: Check, data: dict[str, Any]) -> None:
    require_terms(check, "forbidden_behavior", data.get("forbidden_behavior"), FORBIDDEN_TERMS)
    require_sequence(check, data.get("future_implementation_sequence"))

    safety = data.get("safety_preserved", {})
    if safety:
        blob = normalize(safety)
        missing = [
            term
            for term in [
                "no_runtime_source_changes",
                "no_apply_source_changes",
                "no_build_promote_source_changes",
                "no_command_route_added",
                "no_staging_or_commit",
                "no_password_values_exposed",
            ]
            if not has_term(blob, term)
        ]
        if missing:
            check.fail(f"safety_preserved missing safety markers: {', '.join(missing)}")
        else:
            check.passed("safety_preserved documents non-implementation boundaries")
    else:
        check.fail("safety_preserved is missing or empty")

    if data.get("recommended_next_slice") == "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_VERIFIER_V1":
        check.passed("recommended_next_slice points to graph sequence model verifier")
    else:
        check.fail("recommended_next_slice must be ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_VERIFIER_V1")


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
        current = Path(dirpath)
        if current == ROOT:
            dirnames[:] = [
                name
                for name in dirnames
                if name in ACTIVE_SCAN_SUBDIRS and name not in EXCLUDED_DIRS
            ]
        else:
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
                if any(pattern.search(line) for pattern in ACTIVE_GRAPH_PATTERNS):
                    findings.append(f"{rel(path)}:{lineno}: {line.strip()[:160]}")

    check.info(f"active source scan inspected {scanned} source/config files")
    if findings:
        for finding in findings:
            check.review(f"possible active graph behavior: {finding}")
        check.fail("active source scan found possible active graph behavior")
    else:
        check.passed("active source scan found no active graph alignment/apply/build behavior")


def main() -> int:
    check = Check()
    if ROOT.resolve(strict=False) != Path(WORKSPACE_TEXT).resolve(strict=False):
        check.fail(f"verifier must run inside {WORKSPACE_TEXT}; resolved root is {ROOT}")
        return 1

    data, md_text, _report_text = read_required_files(check)
    inspect_related_files(check)
    if data is None:
        return 1

    check_identity(check, data)
    check_model_sources(check, data)
    check_models(check, data, md_text)
    check_implications(check, data)
    check_forbidden_and_sequence(check, data)
    active_source_scan(check)

    if check.review_required and not check.failures:
        check.info("review-required notes were emitted but no verifier-blocking failure was found")

    if check.failures:
        check.info(f"verification failed with {len(check.failures)} failure(s)")
        return 1

    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
