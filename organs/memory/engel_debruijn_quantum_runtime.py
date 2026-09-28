#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(r"D:\b.WorkSpace\Engel App")
ENGINE_ID = "debruijn_quantum_runtime_engine"
MODEL_CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1"
RUNTIME_CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_V1"
GRAPH_SEQUENCE_MODEL_CONTRACT_ID = "ENGEL_DEBRUIJN_GRAPH_SEQUENCE_MODEL_V1"

RUNTIME_RECEIPT_FOLDER = Path("reports") / "debruijn_quantum_runtime_receipts"
RUNTIME_REPORT_ONLY = "runtime_report_only"
RUNTIME_PREPARE_APPLY_CANDIDATE = "runtime_prepare_apply_candidate"
ALLOWED_ACTION_TYPES = {RUNTIME_REPORT_ONLY, RUNTIME_PREPARE_APPLY_CANDIDATE}

MAX_SCAN_FILES = 10000
MAX_CANDIDATE_STATES = 500
MAX_TRANSITION_DEPTH = 6
MAX_RUNTIME_SECONDS = 180
MAX_OUTPUT_BYTES = 200000
MAX_RANKED_CANDIDATES = 25

EXCLUDED_SCAN_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    "live",
    "backups",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

SENSITIVE_KEY_PARTS = ("password", "salt", "hash", "secret", "token")

SAFETY_FLAGS = [
    "no_apply",
    "no_trust",
    "no_promote",
    "no_source_mutation",
    "no_route_mutation",
    "no_queue_mutation",
    "no_trusted_memory_write",
]

GRAPH_COVERAGE_STATUSES = [
    "unvisited",
    "candidate_generated",
    "verifier_reviewed",
    "suppressed",
    "approved_for_apply_candidate",
    "applied_review_required",
    "verified_complete",
]

GRAPH_MEASUREMENT_STATUSES = [
    "unmeasured_candidate",
    "report_only_selected",
    "human_review_required",
    "verified_for_apply",
    "approved_apply_candidate",
    "applied_review_required",
    "build_promote_candidate",
    "verified_complete",
]

RUNTIME_FORBIDDEN_MEASUREMENT_STATUSES = {
    "verified_for_apply",
    "approved_apply_candidate",
    "applied_review_required",
    "build_promote_candidate",
}

FORBIDDEN_ACTIONS_NOT_PERFORMED = [
    "no source files edited",
    "no routes mutated",
    "no queues mutated",
    "no trusted memory written",
    "no memory promoted",
    "no proposals applied",
    "no proposals trusted",
    "no proposals promoted",
    "no external AI provider or network called",
    "no local LLM inference run",
    "no packages installed",
    "no build/promote/stage/commit",
    "no autorun background worker scheduler or startup hook created",
]


@dataclass
class BasisState:
    state_id: str
    state_type: str
    artifact_path: str | None
    present: bool
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    node_state_id: str | None = None
    coverage_status: str | None = None

    def __post_init__(self) -> None:
        if self.node_state_id is None:
            self.node_state_id = self.state_id
        if self.coverage_status is None:
            self.coverage_status = basis_coverage_status(self.state_type, self.present)


@dataclass
class CandidateState:
    candidate_id: str
    state_path: list[str]
    source_artifacts: list[str]
    target_artifacts: list[str]
    confidence_or_weight: float
    verifier_interference_result: dict[str, Any]
    safety_flags: list[str]
    human_review_required: bool
    apply_allowed: bool
    runtime_generated: bool
    candidate_edges: list[str] = field(default_factory=list)
    coverage_status: str = "candidate_generated"
    measurement_status: str = "human_review_required"


@dataclass
class TransitionPath:
    transition_id: str
    from_state: str
    to_state: str
    transition_type: str
    allowed_in_runtime: bool
    requires_apply_engine: bool
    reason: str
    candidate_id: str | None = None
    source_state: str | None = None
    target_state: str | None = None
    edge_transition_id: str | None = None
    edge_label: str | None = None
    append_operation: str | None = None
    overlap_preserved: bool = True
    sequence_position: int = 0
    visited_before: bool = False
    coverage_status: str = "candidate_generated"
    evidence_file: str | None = None
    verifier_result: str = "review_required"
    safety_gate_result: str = "runtime_report_only_no_apply"
    receipt_path: str | None = None
    human_review_status: str = "human_review_required"
    verifier_interference_score: float = 0.0
    measurement_status: str = "human_review_required"

    def __post_init__(self) -> None:
        if self.source_state is None:
            self.source_state = self.from_state
        if self.target_state is None:
            self.target_state = self.to_state
        if self.edge_transition_id is None:
            self.edge_transition_id = self.transition_id


@dataclass
class RuntimeResult:
    engine_id: str
    action_type: str
    started_at: str
    ended_at: str
    input_root: str
    files_scanned_count: int
    basis_states_count: int
    candidates_generated_count: int
    transition_paths_count: int
    verifier_interference_summary: dict[str, Any]
    ranked_candidates: list[dict[str, Any]]
    outputs_written: list[str]
    files_changed_by_runtime: list[str]
    forbidden_actions_not_performed: list[str]
    final_status: str
    human_review_required: bool
    receipt_id: str
    model_contract_id: str
    runtime_contract_id: str
    password_gate_required: bool
    password_gate_result: str
    rejected_candidates: list[dict[str, Any]]
    review_required_candidates: list[dict[str, Any]]
    no_apply_performed: bool
    next_required_gate: str
    no_trust_performed: bool = True
    no_promote_performed: bool = True
    node_state_count: int = 0
    edge_transition_count: int = 0
    traversal_sequence_length: int = 0
    coverage_summary: dict[str, Any] = field(default_factory=dict)
    unvisited_edges: list[dict[str, Any]] = field(default_factory=list)
    repeated_edges: list[dict[str, Any]] = field(default_factory=list)
    graph_sequence_model_contract_id: str = GRAPH_SEQUENCE_MODEL_CONTRACT_ID
    edge_labels: list[dict[str, Any]] = field(default_factory=list)
    selected_edge_candidates: list[dict[str, Any]] = field(default_factory=list)
    measurement_summary: dict[str, Any] = field(default_factory=dict)


def basis_coverage_status(state_type: str, present: bool) -> str:
    if not present or "missing" in state_type:
        return "unvisited"
    if state_type in {"proposal_untrusted", "candidate_proposal_present"}:
        return "candidate_generated"
    if state_type in {"verifier_present", "safety_gate_present", "password_gate_required"}:
        return "verifier_reviewed"
    return "verified_complete"


def edge_coverage_status(candidate: CandidateState, allowed_in_runtime: bool) -> str:
    if not allowed_in_runtime:
        return "unvisited"
    result = candidate.verifier_interference_result
    classification = str(result.get("final_candidate_classification", "review_required_candidate"))
    if classification == "blocked_candidate":
        return "suppressed"
    if classification == "ranked_report_only_candidate":
        return "verifier_reviewed"
    return "candidate_generated"


def edge_measurement_status(candidate: CandidateState, allowed_in_runtime: bool) -> str:
    if not allowed_in_runtime:
        return "unmeasured_candidate"
    classification = str(candidate.verifier_interference_result.get("final_candidate_classification", "review_required_candidate"))
    if classification == "ranked_report_only_candidate":
        return "human_review_required"
    return "unmeasured_candidate"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_slug() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond:06d}Z"


def resolve_workspace_root(root: Path | str | None = None) -> Path:
    raw_root = DEFAULT_ROOT if root is None else Path(root)
    text = str(raw_root)
    if text.startswith("\\\\") or text.startswith("//") or "://" in text:
        raise ValueError("Only local workspace paths are allowed.")
    resolved = raw_root.resolve(strict=False)
    default_resolved = DEFAULT_ROOT.resolve(strict=False)
    if resolved != default_resolved and default_resolved not in resolved.parents:
        raise ValueError(f"Runtime root must stay inside {default_resolved}.")
    return resolved


def relative_path(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve(strict=False).relative_to(root.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def bounded_path(root: Path, relative: str | Path) -> Path:
    path = (root / relative).resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    if path != root_resolved and root_resolved not in path.parents:
        raise ValueError(f"Path escapes runtime root: {relative}")
    return path


def candidate_id_for(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"runtime_candidate_{digest}"


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _redacted_password_gate_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"gate_config_present": False, "configured": False, "secret_values": "not_read"}
    data = _safe_read_json(path)
    if not isinstance(data, dict):
        return {"gate_config_present": True, "configured": "unknown", "secret_values": "redacted"}
    sensitive_present = False
    non_sensitive_keys: list[str] = []
    configured = False
    for key, value in data.items():
        key_text = str(key).lower()
        if any(part in key_text for part in SENSITIVE_KEY_PARTS):
            sensitive_present = True
            if value not in (None, "", [], {}):
                configured = True
            continue
        non_sensitive_keys.append(str(key))
        if key_text in {"enabled", "configured", "password_gate_configured", "gate_enabled"} and bool(value):
            configured = True
    return {
        "gate_config_present": True,
        "configured": configured,
        "sensitive_fields_present": sensitive_present,
        "non_sensitive_keys": sorted(non_sensitive_keys)[:20],
        "secret_values": "redacted",
    }


def _registry_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"registry_present": False, "approved_inactive_entry_present": False}
    text = ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"registry_present": True, "approved_inactive_entry_present": "unknown"}
    return {
        "registry_present": True,
        "approved_inactive_entry_present": "verifier_health_check" in text and "approved_inactive" in text,
    }


def _proposal_metadata(paths: list[Path], root: Path) -> dict[str, Any]:
    latest = paths[-1] if paths else None
    latest_data = _safe_read_json(latest) if latest else None
    latest_status = latest_data.get("status") if isinstance(latest_data, dict) else None
    latest_apply_allowed = latest_data.get("apply_allowed") if isinstance(latest_data, dict) else None
    latest_human_review_required = latest_data.get("human_review_required") if isinstance(latest_data, dict) else None
    return {
        "proposal_count": len(paths),
        "latest_proposal_path": relative_path(root, latest) if latest else None,
        "latest_status": latest_status,
        "latest_apply_allowed": latest_apply_allowed,
        "latest_human_review_required": latest_human_review_required,
    }


def _add_presence_state(
    states: list[BasisState],
    root: Path,
    state_id: str,
    present_type: str,
    missing_type: str,
    path: Path,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    present = path.exists()
    states.append(
        BasisState(
            state_id=state_id,
            state_type=present_type if present else missing_type,
            artifact_path=relative_path(root, path),
            present=present,
            source=source,
            metadata=metadata or {},
        )
    )


def compute_basis_states(root: Path) -> list[BasisState]:
    root = resolve_workspace_root(root)
    states: list[BasisState] = []

    runtime_contract = bounded_path(root, Path("memory") / "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_CONTRACT_V1.json")
    runtime_contract_data = _safe_read_json(runtime_contract) or {}

    _add_presence_state(
        states,
        root,
        "runtime_engine_contract",
        "contract_present",
        "contract_missing",
        runtime_contract,
        "runtime_contract",
        {"contract_id": runtime_contract_data.get("contract_id")},
    )
    _add_presence_state(
        states,
        root,
        "runtime_engine_contract_verifier",
        "verifier_present",
        "verifier_missing",
        bounded_path(root, Path("tools") / "verify_debruijn_quantum_runtime_engine_contract.py"),
        "runtime_contract_verifier",
    )
    _add_presence_state(
        states,
        root,
        "runtime_engine_implementation_verifier",
        "verifier_present",
        "verifier_missing",
        bounded_path(root, Path("tools") / "verify_debruijn_quantum_runtime_engine.py"),
        "runtime_engine_verifier",
    )
    _add_presence_state(
        states,
        root,
        "runtime_engine_implementation_report",
        "report_present",
        "report_missing",
        bounded_path(root, Path("reports") / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_RUNTIME_ENGINE_V1.md"),
        "runtime_engine_report",
    )
    _add_presence_state(
        states,
        root,
        "route_metadata",
        "route_metadata_present",
        "route_metadata_missing",
        bounded_path(root, Path("memory") / "ROUTE_VERIFICATION_SET_V1.json"),
        "route_metadata",
    )
    _add_presence_state(
        states,
        root,
        "runtime_module_source",
        "runtime_source_present",
        "runtime_source_missing",
        bounded_path(root, "engel_debruijn_quantum_runtime.py"),
        "runtime_module",
    )

    proposal_paths = sorted((root / "reports" / "debruijn_quantum_file_structure").glob("candidate_fix_proposals_*.json"))
    proposal_meta = _proposal_metadata(proposal_paths, root)
    states.append(
        BasisState(
            state_id="candidate_proposals",
            state_type="candidate_proposal_present" if proposal_paths else "candidate_proposal_missing",
            artifact_path=proposal_meta.get("latest_proposal_path"),
            present=bool(proposal_paths),
            source="debruijn_generated_proposals",
            metadata=proposal_meta,
        )
    )
    if proposal_paths:
        states.append(
            BasisState(
                state_id="proposal_untrusted_state",
                state_type="proposal_untrusted",
                artifact_path=proposal_meta.get("latest_proposal_path"),
                present=True,
                source="debruijn_generated_proposals",
                metadata={
                    "trust_status": "untrusted_candidate",
                    "apply_allowed": False,
                    "human_review_required": True,
                },
            )
        )

    registry_path = bounded_path(root, Path("memory") / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json")
    states.append(
        BasisState(
            state_id="approved_inactive_registry",
            state_type="approved_inactive",
            artifact_path=relative_path(root, registry_path),
            present=registry_path.exists(),
            source="agent_skill_registry",
            metadata=_registry_metadata(registry_path),
        )
    )

    runtime_disabled = runtime_contract_data.get("runtime_enabled_now") is False
    states.append(
        BasisState(
            state_id="runtime_disabled",
            state_type="runtime_disabled",
            artifact_path=relative_path(root, runtime_contract),
            present=runtime_disabled,
            source="runtime_contract",
            metadata={"runtime_enabled_now": bool(runtime_contract_data.get("runtime_enabled_now", False))},
        )
    )
    states.append(
        BasisState(
            state_id="runtime_contract_defined",
            state_type="runtime_contract_defined",
            artifact_path=relative_path(root, runtime_contract),
            present=runtime_contract.exists(),
            source="runtime_contract",
            metadata={"status": runtime_contract_data.get("status")},
        )
    )

    apply_contract = bounded_path(root, Path("memory") / "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1.json")
    build_contract = bounded_path(root, Path("memory") / "ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_CONTRACT_V1.json")
    states.append(
        BasisState(
            state_id="apply_engine_contract",
            state_type="apply_contract_missing" if not apply_contract.exists() else "contract_present",
            artifact_path=relative_path(root, apply_contract),
            present=apply_contract.exists(),
            source="future_apply_contract",
            metadata={"future_only": True},
        )
    )
    states.append(
        BasisState(
            state_id="build_promote_contract",
            state_type="build_contract_missing" if not build_contract.exists() else "contract_present",
            artifact_path=relative_path(root, build_contract),
            present=build_contract.exists(),
            source="future_build_promote_contract",
            metadata={"future_only": True},
        )
    )

    safety_gate_paths = [
        Path("tools") / "verify_engel_global_password_gate.py",
        Path("tools") / "verify_untrusted_content_policy.py",
        Path("tools") / "verify_authority_hierarchy.py",
        Path("tools") / "verify_prompt_injection_guard.py",
    ]
    present_gates = [str(path).replace("/", "\\") for path in safety_gate_paths if bounded_path(root, path).exists()]
    states.append(
        BasisState(
            state_id="safety_gate_set",
            state_type="safety_gate_present" if len(present_gates) == len(safety_gate_paths) else "safety_gate_missing",
            artifact_path=None,
            present=len(present_gates) == len(safety_gate_paths),
            source="safety_verifiers",
            metadata={"present_gates": present_gates, "expected_gate_count": len(safety_gate_paths)},
        )
    )

    password_config = bounded_path(root, Path("memory") / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json")
    states.append(
        BasisState(
            state_id="global_password_gate",
            state_type="password_gate_required",
            artifact_path=relative_path(root, password_config),
            present=password_config.exists(),
            source="global_password_gate",
            metadata=_redacted_password_gate_metadata(password_config),
        )
    )

    return states


def _candidate(
    kind: str,
    source_artifacts: list[str],
    target_artifacts: list[str],
    state_path: list[str],
    weight: float,
) -> CandidateState:
    candidate_id = candidate_id_for(kind, ",".join(source_artifacts), ",".join(target_artifacts))
    return CandidateState(
        candidate_id=candidate_id,
        state_path=state_path,
        source_artifacts=source_artifacts,
        target_artifacts=target_artifacts,
        confidence_or_weight=round(weight, 3),
        verifier_interference_result={
            "reinforced_by": [],
            "suppressed_by": [],
            "blocker_reasons": [],
            "review_required_reasons": ["human review required before any apply/build/trust/promotion"],
            "final_candidate_classification": "review_required_candidate",
        },
        safety_flags=list(SAFETY_FLAGS),
        human_review_required=True,
        apply_allowed=False,
        runtime_generated=True,
        candidate_edges=[],
        coverage_status="candidate_generated",
        measurement_status="human_review_required",
    )


def compute_candidate_superposition(basis_states: list[BasisState]) -> list[CandidateState]:
    candidates: list[CandidateState] = []
    by_id = {state.state_id: state for state in basis_states}
    by_type = {state.state_type: state for state in basis_states}

    for state in basis_states:
        if state.state_type == "contract_missing":
            candidates.append(
                _candidate(
                    "missing_contract",
                    [state.artifact_path or state.state_id],
                    [state.artifact_path or "unknown_contract"],
                    ["missing_contract", "contract_candidate"],
                    0.72,
                )
            )
        elif state.state_type == "verifier_missing":
            candidates.append(
                _candidate(
                    "missing_verifier",
                    [state.artifact_path or state.state_id],
                    [state.artifact_path or "unknown_verifier"],
                    ["missing_verifier", "verifier_candidate"],
                    0.74,
                )
            )
        elif state.state_type == "report_missing":
            candidates.append(
                _candidate(
                    "missing_report",
                    [state.artifact_path or state.state_id],
                    [state.artifact_path or "unknown_report"],
                    ["missing_report", "report_candidate"],
                    0.7,
                )
            )
        elif state.state_type == "runtime_source_missing":
            candidates.append(
                _candidate(
                    "missing_runtime_source",
                    [state.artifact_path or state.state_id],
                    ["engel_debruijn_quantum_runtime.py"],
                    ["runtime_contract_defined", "runtime_source_candidate"],
                    0.88,
                )
            )
        elif state.state_type == "apply_contract_missing":
            candidates.append(
                _candidate(
                    "missing_apply_contract",
                    [state.artifact_path or state.state_id],
                    ["memory\\ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1.json"],
                    ["runtime_contract_defined", "apply_contract_candidate"],
                    0.64,
                )
            )
        elif state.state_type == "build_contract_missing":
            candidates.append(
                _candidate(
                    "missing_build_promote_contract",
                    [state.artifact_path or state.state_id],
                    ["memory\\ENGEL_DEBRUIJN_QUANTUM_BUILD_PROMOTE_CONTRACT_V1.json"],
                    ["runtime_contract_defined", "build_contract_candidate"],
                    0.61,
                )
            )

    proposal_state = by_type.get("proposal_untrusted")
    if proposal_state is not None:
        candidates.append(
            _candidate(
                "generated_proposals_untrusted",
                [proposal_state.artifact_path or "reports\\debruijn_quantum_file_structure"],
                ["human_review_queue_future"],
                ["candidate_proposal_present", "proposal_untrusted", "candidate_verified_for_review"],
                0.58,
            )
        )

    route_state = by_id.get("route_metadata")
    route_path = route_state.artifact_path if route_state else None
    route_has_runtime_command = False
    if route_path:
        route_file = resolve_workspace_root(None) / route_path
        try:
            route_has_runtime_command = "engel ai debruijn quantum runtime" in route_file.read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            route_has_runtime_command = False
    if route_state is not None and route_state.present and not route_has_runtime_command:
        candidates.append(
            _candidate(
                "runtime_route_missing_future_only",
                [route_state.artifact_path or "memory\\ROUTE_VERIFICATION_SET_V1.json"],
                ["future_command_contract_only_route_metadata"],
                ["route_metadata_present", "route_documentation_missing", "route_doc_candidate"],
                0.55,
            )
        )

    return candidates[:MAX_CANDIDATE_STATES]


def _append_operation_for_transition(transition_type: str, to_state: str) -> str:
    if "verifier" in transition_type or "verifier" in to_state:
        return "append verifier evidence while preserving contract context"
    if "report" in transition_type or "report" in to_state:
        return "append report evidence while preserving verifier context"
    if "runtime_source" in transition_type or "runtime_engine" in transition_type:
        return "append implementation candidate while preserving contract boundary"
    if "route" in transition_type:
        return "append route documentation evidence while preserving route metadata context"
    if "apply" in transition_type:
        return "append future apply eligibility evidence while preserving runtime report-only boundary"
    if "build" in transition_type:
        return "append future build/promote evidence while preserving apply/build contract boundary"
    return "append candidate review evidence while preserving source artifact context"


def _edge_label_for(sequence_position: int, from_state: str, to_state: str, transition_type: str) -> str:
    return f"{sequence_position:04d}:{from_state}->{to_state}:{transition_type}"


def _transition_path(
    candidate: CandidateState,
    from_state: str,
    to_state: str,
    transition_type: str,
    sequence_position: int,
    visited_before: bool,
    allowed_in_runtime: bool,
    requires_apply_engine: bool,
    reason: str,
) -> TransitionPath:
    transition_id = candidate_id_for(candidate.candidate_id, transition_type, str(sequence_position))
    evidence_file = candidate.source_artifacts[0] if candidate.source_artifacts else None
    coverage_status = edge_coverage_status(candidate, allowed_in_runtime)
    measurement_status = edge_measurement_status(candidate, allowed_in_runtime)
    return TransitionPath(
        transition_id=transition_id,
        from_state=from_state,
        to_state=to_state,
        transition_type=transition_type,
        allowed_in_runtime=allowed_in_runtime,
        requires_apply_engine=requires_apply_engine,
        reason=reason,
        candidate_id=candidate.candidate_id,
        source_state=from_state,
        target_state=to_state,
        edge_transition_id=transition_id,
        edge_label=_edge_label_for(sequence_position, from_state, to_state, transition_type),
        append_operation=_append_operation_for_transition(transition_type, to_state),
        overlap_preserved=allowed_in_runtime and not requires_apply_engine,
        sequence_position=sequence_position,
        visited_before=visited_before,
        coverage_status=coverage_status,
        evidence_file=evidence_file,
        verifier_result=str(candidate.verifier_interference_result.get("final_candidate_classification", "review_required_candidate")),
        safety_gate_result="runtime_report_only_no_apply",
        receipt_path="pending_runtime_receipt",
        human_review_status="human_review_required",
        verifier_interference_score=candidate.confidence_or_weight,
        measurement_status=measurement_status,
    )


def compute_transition_paths(candidates: list[CandidateState]) -> list[TransitionPath]:
    transitions: list[TransitionPath] = []
    visited_edges: set[tuple[str, str, str]] = set()
    sequence_position = 1
    for candidate in candidates:
        path = candidate.state_path
        if "contract_candidate" in path:
            transition_type = "missing_contract_to_contract_candidate"
            from_state = "missing_contract"
            to_state = "contract_candidate"
        elif "verifier_candidate" in path:
            transition_type = "missing_verifier_to_verifier_candidate"
            from_state = "missing_verifier"
            to_state = "verifier_candidate"
        elif "report_candidate" in path:
            transition_type = "missing_report_to_report_candidate"
            from_state = "missing_report"
            to_state = "report_candidate"
        elif "route_doc_candidate" in path:
            transition_type = "route_documentation_missing_to_route_doc_candidate"
            from_state = "route_documentation_missing"
            to_state = "route_doc_candidate"
        else:
            transition_type = "candidate_untrusted_to_candidate_verified_for_review"
            from_state = "candidate_untrusted"
            to_state = "candidate_verified_for_review"

        for transition_args in [
            (
                from_state,
                to_state,
                transition_type,
                True,
                False,
                "Report-only transition; no file mutation or apply is performed.",
            ),
            (
                "candidate_verified_for_review",
                "approved_apply_candidate",
                "future_apply_only_review_to_approved_apply_candidate",
                False,
                True,
                "Future apply lane only; runtime V1 cannot execute this transition.",
            ),
            (
                "approved_apply_candidate",
                "applied_change",
                "future_apply_engine_only_approved_apply_candidate_to_applied_change",
                False,
                True,
                "Future apply engine only; runtime V1 never applies changes.",
            ),
        ]:
            edge_key = (transition_args[0], transition_args[1], transition_args[2])
            transition = _transition_path(
                candidate,
                transition_args[0],
                transition_args[1],
                transition_args[2],
                sequence_position,
                edge_key in visited_edges,
                transition_args[3],
                transition_args[4],
                transition_args[5],
            )
            transitions.append(transition)
            candidate.candidate_edges.append(transition.edge_transition_id or transition.transition_id)
            visited_edges.add(edge_key)
            sequence_position += 1
    return transitions[: MAX_CANDIDATE_STATES * MAX_TRANSITION_DEPTH]


def _gate_presence(root: Path) -> dict[str, bool]:
    return {
        "proposal_verifier": (root / "tools" / "verify_debruijn_quantum_candidate_proposals.py").exists(),
        "entanglement_verifier": (root / "tools" / "verify_debruijn_quantum_entanglement_groups.py").exists(),
        "backend_status_consistency_verifier": (root / "tools" / "verify_debruijn_quantum_backend_status_consistency.py").exists(),
        "untrusted_content_policy": (root / "tools" / "verify_untrusted_content_policy.py").exists(),
        "authority_hierarchy": (root / "tools" / "verify_authority_hierarchy.py").exists(),
        "prompt_injection_guard": (root / "tools" / "verify_prompt_injection_guard.py").exists(),
        "route_metadata_verifier": (root / "tools" / "verify_route_metadata_contract.py").exists(),
        "core_continuity_verifier": (root / "tools" / "verify_engel_core_continuity_map.py").exists(),
        "global_password_gate": (root / "tools" / "verify_engel_global_password_gate.py").exists(),
    }


def apply_verifier_interference(candidates: list[CandidateState], root: Path) -> list[CandidateState]:
    root = resolve_workspace_root(root)
    gates = _gate_presence(root)
    reinforced_by = [name for name, present in gates.items() if present]
    missing_gates = [name for name, present in gates.items() if not present]

    for candidate in candidates:
        result = candidate.verifier_interference_result
        result["reinforced_by"] = list(reinforced_by)
        result["suppressed_by"] = []
        result["blocker_reasons"] = []
        result["review_required_reasons"] = sorted(
            set(result.get("review_required_reasons", []) + ["runtime candidates remain untrusted and report-only"])
        )

        if missing_gates:
            result["blocker_reasons"].append("missing safety/verifier gates: " + ", ".join(missing_gates))
        if "generated_proposals_untrusted" in candidate.candidate_id or "proposal_untrusted" in candidate.state_path:
            result["suppressed_by"].append("untrusted_content_policy")
            result["review_required_reasons"].append("generated proposals remain untrusted_candidate")
        if any("route" in item for item in candidate.state_path):
            result["suppressed_by"].append("route_metadata_verifier_until_future_route_contract")
        if any("apply" in item or "build" in item for item in candidate.state_path):
            result["suppressed_by"].append("future_apply_build_gate")
            result["review_required_reasons"].append("apply/build requires separate approved engine")

        if result["blocker_reasons"]:
            result["final_candidate_classification"] = "blocked_candidate"
            candidate.confidence_or_weight = round(max(0.0, candidate.confidence_or_weight - 0.25), 3)
        elif result["suppressed_by"]:
            result["final_candidate_classification"] = "review_required_candidate"
            candidate.confidence_or_weight = round(max(0.0, candidate.confidence_or_weight - 0.08), 3)
        else:
            result["final_candidate_classification"] = "ranked_report_only_candidate"
            candidate.confidence_or_weight = round(min(0.99, candidate.confidence_or_weight + 0.05), 3)

        candidate.apply_allowed = False
        candidate.human_review_required = True
        candidate.runtime_generated = True
        candidate.safety_flags = sorted(set(candidate.safety_flags + SAFETY_FLAGS))
        classification = result.get("final_candidate_classification")
        candidate.coverage_status = "suppressed" if classification == "blocked_candidate" else "candidate_generated"
        candidate.measurement_status = "human_review_required"

    return candidates


def select_ranked_candidates(candidates: list[CandidateState], max_candidates: int = MAX_RANKED_CANDIDATES) -> list[CandidateState]:
    def sort_key(candidate: CandidateState) -> tuple[int, int, float, str]:
        result = candidate.verifier_interference_result
        blockers = len(result.get("blocker_reasons", []))
        suppressed = len(result.get("suppressed_by", []))
        return (blockers, suppressed, -candidate.confidence_or_weight, candidate.candidate_id)

    return sorted(candidates, key=sort_key)[:max_candidates]


def _count_files_bounded(root: Path) -> int:
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name.lower() not in EXCLUDED_SCAN_DIRS and not (Path(dirpath) / name).is_symlink()
        ]
        for _filename in filenames:
            count += 1
            if count >= MAX_SCAN_FILES:
                return count
    return count


def _candidate_dict(candidate: CandidateState) -> dict[str, Any]:
    data = asdict(candidate)
    data["human_review_required"] = True
    data["apply_allowed"] = False
    data["runtime_generated"] = True
    if data.get("measurement_status") in RUNTIME_FORBIDDEN_MEASUREMENT_STATUSES:
        data["measurement_status"] = "human_review_required"
    return data


def _transition_dict(transition: TransitionPath) -> dict[str, Any]:
    data = asdict(transition)
    data["source_state"] = transition.source_state or transition.from_state
    data["target_state"] = transition.target_state or transition.to_state
    data["edge_transition_id"] = transition.edge_transition_id or transition.transition_id
    data["edge_label"] = transition.edge_label or _edge_label_for(
        transition.sequence_position,
        transition.from_state,
        transition.to_state,
        transition.transition_type,
    )
    data["human_review_status"] = "human_review_required"
    if data.get("measurement_status") in RUNTIME_FORBIDDEN_MEASUREMENT_STATUSES:
        data["measurement_status"] = "unmeasured_candidate"
    return data


def _coverage_summary(basis_states: list[BasisState], transitions: list[TransitionPath]) -> dict[str, Any]:
    node_counts = {status: 0 for status in GRAPH_COVERAGE_STATUSES}
    edge_counts = {status: 0 for status in GRAPH_COVERAGE_STATUSES}
    for state in basis_states:
        status = state.coverage_status or "unvisited"
        node_counts[status] = node_counts.get(status, 0) + 1
    for transition in transitions:
        status = transition.coverage_status or "unvisited"
        edge_counts[status] = edge_counts.get(status, 0) + 1
    return {
        "node_states": dict(sorted(node_counts.items())),
        "edge_transitions": dict(sorted(edge_counts.items())),
        "node_state_count": len(basis_states),
        "edge_transition_count": len(transitions),
    }


def _measurement_summary(candidates: list[CandidateState], transitions: list[TransitionPath]) -> dict[str, Any]:
    counts = {status: 0 for status in GRAPH_MEASUREMENT_STATUSES}
    for candidate in candidates:
        status = candidate.measurement_status
        if status in RUNTIME_FORBIDDEN_MEASUREMENT_STATUSES:
            status = "human_review_required"
        counts[status] = counts.get(status, 0) + 1
    for transition in transitions:
        status = transition.measurement_status
        if status in RUNTIME_FORBIDDEN_MEASUREMENT_STATUSES:
            status = "unmeasured_candidate"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _selected_edge_candidates(
    ranked_candidates: list[CandidateState],
    transitions: list[TransitionPath],
) -> list[dict[str, Any]]:
    ranked_ids = {candidate.candidate_id for candidate in ranked_candidates}
    selected: list[dict[str, Any]] = []
    for transition in transitions:
        if transition.candidate_id not in ranked_ids or not transition.allowed_in_runtime:
            continue
        edge = _transition_dict(transition)
        edge["measurement_status"] = "report_only_selected"
        edge["apply_allowed"] = False
        edge["human_review_required"] = True
        selected.append(edge)
    return selected[:MAX_RANKED_CANDIDATES]


def _interference_summary(candidates: list[CandidateState]) -> dict[str, Any]:
    classifications: dict[str, int] = {}
    reinforced_by: set[str] = set()
    suppressed_by: set[str] = set()
    blocker_reasons: set[str] = set()
    review_required_reasons: set[str] = set()
    for candidate in candidates:
        result = candidate.verifier_interference_result
        classification = str(result.get("final_candidate_classification", "unknown"))
        classifications[classification] = classifications.get(classification, 0) + 1
        reinforced_by.update(str(item) for item in result.get("reinforced_by", []))
        suppressed_by.update(str(item) for item in result.get("suppressed_by", []))
        blocker_reasons.update(str(item) for item in result.get("blocker_reasons", []))
        review_required_reasons.update(str(item) for item in result.get("review_required_reasons", []))
    return {
        "classification_counts": dict(sorted(classifications.items())),
        "reinforced_by": sorted(reinforced_by),
        "suppressed_by": sorted(suppressed_by),
        "blocker_reasons": sorted(blocker_reasons),
        "review_required_reasons": sorted(review_required_reasons),
    }


def build_runtime_status(root: Path | str | None = None) -> dict[str, Any]:
    resolved_root = resolve_workspace_root(root)
    basis_states = compute_basis_states(resolved_root)
    candidates = compute_candidate_superposition(basis_states)
    candidates = apply_verifier_interference(candidates, resolved_root)
    transitions = compute_transition_paths(candidates)
    ranked = select_ranked_candidates(candidates)
    edge_labels = [_transition_dict(transition) for transition in transitions]
    return {
        "engine_id": ENGINE_ID,
        "mode": "local_offline_report_only",
        "input_root": str(resolved_root),
        "files_scanned_count": _count_files_bounded(resolved_root),
        "basis_states_count": len(basis_states),
        "candidates_generated_count": len(candidates),
        "transition_paths_count": len(transitions),
        "ranked_candidates_count": len(ranked),
        "graph_sequence_model_contract_id": GRAPH_SEQUENCE_MODEL_CONTRACT_ID,
        "node_state_count": len(basis_states),
        "edge_transition_count": len(transitions),
        "traversal_sequence_length": len(edge_labels),
        "coverage_summary": _coverage_summary(basis_states, transitions),
        "unvisited_edges_count": len([edge for edge in edge_labels if edge.get("coverage_status") == "unvisited"]),
        "repeated_edges_count": len([edge for edge in edge_labels if edge.get("visited_before") is True]),
        "selected_edge_candidates_count": len(_selected_edge_candidates(ranked, transitions)),
        "safety_boundary": {
            "apply_enabled": False,
            "build_promote_enabled": False,
            "trusted_memory_write_enabled": False,
            "source_mutation_enabled": False,
            "route_mutation_enabled": False,
            "queue_mutation_enabled": False,
            "provider_api_enabled": False,
            "network_enabled": False,
            "model_or_local_llm_enabled": False,
            "background_or_autorun_enabled": False,
        },
        "receipt_folder": str(RUNTIME_RECEIPT_FOLDER).replace("/", "\\"),
        "human_review_required": True,
        "no_apply_performed": True,
        "no_trust_performed": True,
        "no_promote_performed": True,
    }


def _receipt_paths(root: Path, receipt_id: str) -> tuple[Path, Path]:
    folder = bounded_path(root, RUNTIME_RECEIPT_FOLDER)
    folder.mkdir(parents=True, exist_ok=True)
    return (
        folder / f"debruijn_quantum_runtime_{receipt_id}.json",
        folder / f"debruijn_quantum_runtime_{receipt_id}.md",
    )


def _runtime_result_to_markdown(result: RuntimeResult) -> str:
    lines = [
        "# De Bruijn Quantum Runtime Receipt",
        "",
        f"receipt_id: `{result.receipt_id}`",
        f"engine_id: `{result.engine_id}`",
        f"action_type: `{result.action_type}`",
        f"started_at: `{result.started_at}`",
        f"ended_at: `{result.ended_at}`",
        f"input_root: `{result.input_root}`",
        f"model_contract_id: `{result.model_contract_id}`",
        f"runtime_contract_id: `{result.runtime_contract_id}`",
        f"files_scanned_count: `{result.files_scanned_count}`",
        f"basis_states_count: `{result.basis_states_count}`",
        f"candidates_generated_count: `{result.candidates_generated_count}`",
        f"transition_paths_count: `{result.transition_paths_count}`",
        f"graph_sequence_model_contract_id: `{result.graph_sequence_model_contract_id}`",
        f"node_state_count: `{result.node_state_count}`",
        f"edge_transition_count: `{result.edge_transition_count}`",
        f"traversal_sequence_length: `{result.traversal_sequence_length}`",
        f"password_gate_required: `{str(result.password_gate_required).lower()}`",
        f"password_gate_result: `{result.password_gate_result}`",
        f"final_status: `{result.final_status}`",
        f"human_review_required: `{str(result.human_review_required).lower()}`",
        f"no_apply_performed: `{str(result.no_apply_performed).lower()}`",
        f"no_trust_performed: `{str(result.no_trust_performed).lower()}`",
        f"no_promote_performed: `{str(result.no_promote_performed).lower()}`",
        f"next_required_gate: `{result.next_required_gate}`",
        "",
        "## Outputs Written",
    ]
    lines.extend(f"- `{path}`" for path in result.outputs_written)
    lines.extend(["", "## Files Changed By Runtime"])
    lines.extend(f"- `{path}`" for path in result.files_changed_by_runtime)
    lines.extend(["", "## Verifier Interference Summary"])
    lines.append("```json")
    lines.append(json.dumps(result.verifier_interference_summary, indent=2, sort_keys=True))
    lines.append("```")
    lines.extend(["", "## Graph Coverage Summary"])
    lines.append("```json")
    lines.append(json.dumps(result.coverage_summary, indent=2, sort_keys=True))
    lines.append("```")
    lines.extend(["", "## Measurement Summary"])
    lines.append("```json")
    lines.append(json.dumps(result.measurement_summary, indent=2, sort_keys=True))
    lines.append("```")
    lines.extend(["", "## Selected Edge Candidates"])
    for edge in result.selected_edge_candidates:
        lines.append(
            f"- `{edge['edge_transition_id']}` {edge['source_state']} -> {edge['target_state']} "
            f"measurement={edge['measurement_status']} coverage={edge['coverage_status']}"
        )
    lines.extend(["", "## Edge Labels"])
    for edge in result.edge_labels[:MAX_RANKED_CANDIDATES]:
        lines.append(
            f"- `{edge['edge_label']}` append=`{edge['append_operation']}` "
            f"overlap_preserved={str(edge['overlap_preserved']).lower()}"
        )
    lines.extend(["", "## Ranked Candidates"])
    for candidate in result.ranked_candidates:
        lines.append(
            f"- `{candidate['candidate_id']}` weight={candidate['confidence_or_weight']} "
            f"classification={candidate['verifier_interference_result'].get('final_candidate_classification')}"
        )
    lines.extend(["", "## Forbidden Actions Not Performed"])
    lines.extend(f"- {item}" for item in result.forbidden_actions_not_performed)
    return "\n".join(lines) + "\n"


def _stamp_graph_receipt_paths(result: RuntimeResult, receipt_path: str) -> None:
    for edge in result.edge_labels:
        edge["receipt_path"] = receipt_path
    for edge in result.selected_edge_candidates:
        edge["receipt_path"] = receipt_path
    for edge in result.unvisited_edges:
        edge["receipt_path"] = receipt_path
    for edge in result.repeated_edges:
        edge["receipt_path"] = receipt_path


def write_runtime_receipts(root: Path, result: RuntimeResult) -> RuntimeResult:
    json_path, md_path = _receipt_paths(root, result.receipt_id)
    result.outputs_written = [relative_path(root, json_path) or str(json_path), relative_path(root, md_path) or str(md_path)]
    result.files_changed_by_runtime = list(result.outputs_written)
    _stamp_graph_receipt_paths(result, result.outputs_written[0])
    json_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_runtime_result_to_markdown(result), encoding="utf-8")
    return result


def run_debruijn_quantum_runtime(root: Path | str | None = None, action_type: str = RUNTIME_REPORT_ONLY) -> RuntimeResult:
    if action_type not in ALLOWED_ACTION_TYPES:
        raise ValueError(f"Unsupported runtime action_type: {action_type}")
    started_monotonic = time.monotonic()
    started_at = utc_now()
    resolved_root = resolve_workspace_root(root)

    basis_states = compute_basis_states(resolved_root)
    candidates = compute_candidate_superposition(basis_states)
    candidates = apply_verifier_interference(candidates, resolved_root)
    transitions = compute_transition_paths(candidates)
    ranked = select_ranked_candidates(candidates)
    edge_labels = [_transition_dict(transition) for transition in transitions]
    unvisited_edges = [edge for edge in edge_labels if edge.get("coverage_status") == "unvisited"]
    repeated_edges = [edge for edge in edge_labels if edge.get("visited_before") is True]
    selected_edge_candidates = _selected_edge_candidates(ranked, transitions)

    elapsed = time.monotonic() - started_monotonic
    final_status = "runtime_report_only_pass"
    if elapsed > MAX_RUNTIME_SECONDS:
        final_status = "runtime_limit_review_required"

    ranked_dicts = [_candidate_dict(candidate) for candidate in ranked]
    rejected = [
        _candidate_dict(candidate)
        for candidate in candidates
        if candidate.candidate_id not in {item["candidate_id"] for item in ranked_dicts}
    ][:MAX_RANKED_CANDIDATES]
    review_required = [
        _candidate_dict(candidate)
        for candidate in candidates
        if candidate.verifier_interference_result.get("final_candidate_classification") != "ranked_report_only_candidate"
    ][:MAX_RANKED_CANDIDATES]

    password_gate_required = action_type == RUNTIME_PREPARE_APPLY_CANDIDATE
    next_required_gate = (
        "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1"
        if action_type == RUNTIME_PREPARE_APPLY_CANDIDATE
        else "human_review"
    )
    password_gate_result = "required_for_future_apply" if password_gate_required else "not_required"
    receipt_id = timestamp_slug()
    result = RuntimeResult(
        engine_id=ENGINE_ID,
        action_type=action_type,
        started_at=started_at,
        ended_at=utc_now(),
        input_root=str(resolved_root),
        files_scanned_count=_count_files_bounded(resolved_root),
        basis_states_count=len(basis_states),
        candidates_generated_count=len(candidates),
        transition_paths_count=len(transitions),
        verifier_interference_summary=_interference_summary(candidates),
        ranked_candidates=ranked_dicts,
        outputs_written=[],
        files_changed_by_runtime=[],
        forbidden_actions_not_performed=list(FORBIDDEN_ACTIONS_NOT_PERFORMED),
        final_status=final_status,
        human_review_required=True,
        receipt_id=receipt_id,
        model_contract_id=MODEL_CONTRACT_ID,
        runtime_contract_id=RUNTIME_CONTRACT_ID,
        password_gate_required=password_gate_required,
        password_gate_result=password_gate_result,
        rejected_candidates=rejected,
        review_required_candidates=review_required,
        no_apply_performed=True,
        next_required_gate=next_required_gate,
        no_trust_performed=True,
        no_promote_performed=True,
        node_state_count=len(basis_states),
        edge_transition_count=len(transitions),
        traversal_sequence_length=len(edge_labels),
        coverage_summary=_coverage_summary(basis_states, transitions),
        unvisited_edges=unvisited_edges[:MAX_RANKED_CANDIDATES],
        repeated_edges=repeated_edges[:MAX_RANKED_CANDIDATES],
        graph_sequence_model_contract_id=GRAPH_SEQUENCE_MODEL_CONTRACT_ID,
        edge_labels=edge_labels,
        selected_edge_candidates=selected_edge_candidates,
        measurement_summary=_measurement_summary(candidates, transitions),
    )
    return write_runtime_receipts(resolved_root, result)


def _print_status(status: dict[str, Any]) -> None:
    print("Engel De Bruijn Quantum Runtime Engine Status")
    print(f"engine_id: {status['engine_id']}")
    print(f"mode: {status['mode']}")
    print(f"input_root: {status['input_root']}")
    print(f"files_scanned_count: {status['files_scanned_count']}")
    print(f"basis_states_count: {status['basis_states_count']}")
    print(f"candidates_generated_count: {status['candidates_generated_count']}")
    print(f"transition_paths_count: {status['transition_paths_count']}")
    print(f"ranked_candidates_count: {status['ranked_candidates_count']}")
    print(f"graph_sequence_model_contract_id: {status['graph_sequence_model_contract_id']}")
    print(f"node_state_count: {status['node_state_count']}")
    print(f"edge_transition_count: {status['edge_transition_count']}")
    print(f"traversal_sequence_length: {status['traversal_sequence_length']}")
    print(f"unvisited_edges_count: {status['unvisited_edges_count']}")
    print(f"repeated_edges_count: {status['repeated_edges_count']}")
    print(f"selected_edge_candidates_count: {status['selected_edge_candidates_count']}")
    print(f"receipt_folder: {status['receipt_folder']}")
    print("safety_boundary:")
    for key, value in sorted(status["safety_boundary"].items()):
        print(f"  {key}: {str(value).lower()}")
    print("human_review_required: true")
    print("no_apply_performed: true")
    print("no_trust_performed: true")
    print("no_promote_performed: true")
    print("status_writes_files: false")


def _print_run_summary(result: RuntimeResult) -> None:
    print("Engel De Bruijn Quantum Runtime Engine")
    print(f"action_type: {result.action_type}")
    print(f"final_status: {result.final_status}")
    print(f"commands_or_apply_run: false")
    print(f"candidates_generated_count: {result.candidates_generated_count}")
    print(f"ranked_candidates_count: {len(result.ranked_candidates)}")
    print(f"edge_transition_count: {result.edge_transition_count}")
    print(f"selected_edge_candidates_count: {len(result.selected_edge_candidates)}")
    print(f"graph_sequence_model_contract_id: {result.graph_sequence_model_contract_id}")
    print(f"password_gate_result: {result.password_gate_result}")
    print("receipt_paths:")
    for path in result.outputs_written:
        print(f"  - {path}")
    print("safety_boundary: no apply, no trust, no promote, no source/route/queue/trusted-memory mutation")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel De Bruijn Quantum local report-only runtime engine")
    parser.add_argument("command", choices=["status", "run-report", "prepare-apply-candidate"])
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Local Engel workspace root; must stay inside D:\\b.WorkSpace\\Engel App")
    args = parser.parse_args(argv)

    try:
        root = resolve_workspace_root(args.root)
    except ValueError as exc:
        print(f"SAFE_ERROR: {exc}", file=sys.stderr)
        return 2

    if args.command == "status":
        _print_status(build_runtime_status(root))
        return 0
    if args.command == "run-report":
        _print_run_summary(run_debruijn_quantum_runtime(root, RUNTIME_REPORT_ONLY))
        return 0
    if args.command == "prepare-apply-candidate":
        _print_run_summary(run_debruijn_quantum_runtime(root, RUNTIME_PREPARE_APPLY_CANDIDATE))
        return 0

    print("SAFE_ERROR: unsupported runtime command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
