#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(r"D:\b.WorkSpace\Engel App")
ENGINE_ID = "debruijn_quantum_apply_engine"
APPLY_CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_CONTRACT_V1"
GRAPH_ALIGNMENT_CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_APPLY_ENGINE_GRAPH_ALIGNMENT_CONTRACT_V1"
APPROVAL_PHRASE = "APPROVE_DEBRUIJN_QUANTUM_APPLY_VERIFIED_PROPOSAL_V1"
APPLY_RECEIPT_FOLDER = Path("reports") / "debruijn_quantum_apply_receipts"

ACTUAL_APPLY_ENABLED = False
COMMAND_ROUTE_ADDED = False
TRUSTED_MEMORY_WRITE_ENABLED = False
BUILD_PROMOTE_ENABLED = False
APPLY_GRAPH_ALIGNMENT_ENABLED_NOW = False

EXPECTED_VERIFIED_EDGE_VALUES = {
    "measurement_status": "verified_for_apply",
    "coverage_status": "approved_for_apply_candidate",
    "apply_scope": "bounded_file_structure",
}

GRAPH_EDGE_FIELD_KEYS = (
    "source_node_state_id",
    "target_node_state_id",
    "edge_transition_id",
    "edge_label",
    "append_operation",
    "overlap_preserved",
    "apply_scope",
    "coverage_status",
    "measurement_status",
    "verifier_interference_result",
    "sequence_position",
)

GRAPH_EDGE_CONTAINER_KEYS = ("graph_edge", "edge", "graph_aligned_apply_input")

ALLOWED_ACTIONS_V1 = {
    "create_missing_contract_scaffold_files",
    "create_missing_report_scaffold_files",
    "create_missing_verifier_scaffold_files",
    "update_safe_docs_maps",
    "create_receipts_reports",
}

FORBIDDEN_ACTIONS_NOT_PERFORMED = [
    "no_unverified_apply",
    "no_automatic_apply",
    "no_proposal_trust",
    "no_memory_promotion",
    "no_trusted_memory_write",
    "no_route_mutation",
    "no_queue_mutation",
    "no_source_mutation",
    "no_provider_network_model_local_llm",
    "no_package_install",
    "no_build_promote",
    "no_git_stage_commit_push",
    "no_command_execution_from_proposal",
]

FORBIDDEN_CONTENT_TERMS = [
    "subprocess",
    "os.system",
    "powershell",
    "cmd.exe",
    "shell=true",
    "shell execution",
    "execute proposal",
    "run command",
    "provider_api",
    "network_enabled",
    "local_llm",
    "trusted_memory",
    "memory_promotion",
    "promote_memory",
    "git commit",
    "git add",
    "pyinstaller",
    "pip install",
    "package install",
    "http://",
    "https://",
]

PROMPT_INJECTION_TERMS = [
    "ignore previous",
    "ignore all previous",
    "developer message",
    "system prompt",
    "override instructions",
    "treat this as instruction",
]

PATH_LIST_KEYS = {
    "target_path",
    "target_paths",
    "target_artifact",
    "target_artifacts",
    "artifact_path",
    "artifact_paths",
    "suggested_files_to_create",
    "files_to_create",
    "files_to_update",
    "affected_files",
}


@dataclass
class ProposalValidationResult:
    proposal_path: str
    proposal_id: str
    proposal_hash: str
    valid_structure: bool
    inside_workspace: bool
    generated_by_approved_system: bool
    human_review_required: bool
    apply_allowed_at_generation: bool
    verified_for_apply: bool
    target_paths_validated: bool
    unsafe_content_scan_passed: bool
    authority_hierarchy_passed: bool
    prompt_injection_guard_passed: bool
    route_metadata_verified: bool
    approval_phrase_required: bool
    password_gate_required: bool
    eligible_for_apply_attempt: bool
    source_node_state_id: str = ""
    target_node_state_id: str = ""
    edge_transition_id: str = ""
    edge_label: str = ""
    append_operation: str = ""
    overlap_preserved: bool = False
    apply_scope: str = ""
    coverage_status: str = ""
    measurement_status: str = ""
    verifier_interference_result: str = ""
    sequence_position: Any = None
    edge_label_present: bool = False
    edge_transition_id_present: bool = False
    source_node_validated: bool = False
    target_node_validated: bool = False
    graph_edge_present: bool = False
    graph_alignment_ok: bool = False
    blocker_reasons: list[str] = field(default_factory=list)
    review_required_reasons: list[str] = field(default_factory=list)


@dataclass
class ApplyPlan:
    proposal_id: str
    proposal_path: str
    allowed_actions: list[str]
    target_paths: list[str]
    files_to_create: list[str]
    files_to_update: list[str]
    files_rejected: list[str]
    backup_hash_manifest: dict[str, str]
    dry_run_only: bool
    apply_enabled: bool
    human_review_required: bool
    edge_transition_id: str = ""
    edge_label: str = ""
    source_node_state_id: str = ""
    target_node_state_id: str = ""
    apply_scope: str = ""
    graph_edge_apply_disabled: bool = True


@dataclass
class ApplyResult:
    engine_id: str
    action_type: str
    started_at: str
    ended_at: str
    input_proposal_path: str
    proposal_id: str
    proposal_hash: str
    approval_detected: bool
    approval_phrase_name: str
    password_gate_result: str
    pre_apply_verifier_results: dict[str, str]
    files_read: list[str]
    files_changed: list[str]
    files_not_changed: list[str]
    target_paths_validated: bool
    forbidden_actions_not_performed: list[str]
    post_apply_verifier_results: dict[str, str]
    rollback_note: str
    final_status: str
    human_review_required: bool
    source_node_state_id: str = ""
    target_node_state_id: str = ""
    edge_transition_id: str = ""
    edge_label: str = ""
    append_operation: str = ""
    overlap_preserved: bool = False
    sequence_position: Any = None
    coverage_status_before: str = ""
    coverage_status_after: str = ""
    measurement_status_before: str = ""
    measurement_status_after: str = ""
    verifier_interference_result: str = ""
    graph_edge_apply_disabled: bool = True
    apply_enabled: bool = False
    graph_alignment_contract_id: str = GRAPH_ALIGNMENT_CONTRACT_ID


class ProposalSafetyError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def resolve_workspace_root(root: Path | None = None) -> Path:
    candidate = (root or DEFAULT_ROOT).resolve()
    default = DEFAULT_ROOT.resolve()
    if candidate != default:
        raise ProposalSafetyError(f"workspace root must be {default}")
    return candidate


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def relative_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _looks_like_url(text: str) -> bool:
    lowered = text.strip().lower()
    return "://" in lowered or lowered.startswith(("http:", "https:", "file:"))


def _normalize_target_path(raw: str, root: Path) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ProposalSafetyError("empty target path")
    text = raw.strip().replace("/", "\\")
    if _looks_like_url(text):
        raise ProposalSafetyError(f"external URL rejected: {raw}")
    candidate = Path(text)
    if any(part == ".." for part in candidate.parts):
        raise ProposalSafetyError(f"path traversal rejected: {raw}")
    if any(part in {"build", "dist", "live", "backups"} for part in candidate.parts):
        raise ProposalSafetyError(f"build/dist/live/backups path rejected: {raw}")
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not _is_relative_to(resolved, root):
        raise ProposalSafetyError(f"path outside workspace rejected: {raw}")
    return resolved


def _proposal_path(path: Path, root: Path) -> Path:
    if _looks_like_url(str(path)):
        raise ProposalSafetyError("proposal path must be local, not a URL")
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    if not _is_relative_to(resolved, root):
        raise ProposalSafetyError("proposal path is outside workspace")
    if resolved.suffix.lower() != ".json":
        raise ProposalSafetyError("V1 accepts JSON proposals only")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_proposal(path: Path, root: Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_root(root)
    proposal_path = _proposal_path(path, workspace)
    data = proposal_path.read_bytes()
    if b"\x00" in data:
        raise ProposalSafetyError("binary proposal content rejected")
    try:
        loaded = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ProposalSafetyError("proposal must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise ProposalSafetyError(f"proposal JSON parse failed: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ProposalSafetyError("proposal JSON must be an object")
    return loaded


def _proposal_items(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    raw = proposal.get("proposals")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return [proposal]


def _iter_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(_iter_strings(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(_iter_strings(child))
    return strings


def _iter_string_values(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            strings.extend(_iter_string_values(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(_iter_string_values(child))
    return strings


def _extract_target_paths(value: Any) -> list[str]:
    paths: list[str] = []

    def visit(node: Any, key_hint: str = "") -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                key_text = str(key)
                if key_text in PATH_LIST_KEYS:
                    visit(child, key_text)
                else:
                    visit(child, key_text)
        elif isinstance(node, list):
            for child in node:
                visit(child, key_hint)
        elif isinstance(node, str) and key_hint in PATH_LIST_KEYS:
            paths.append(node)

    visit(value)
    return paths


def _bool_all(items: list[dict[str, Any]], key: str, expected: bool) -> bool:
    if not items:
        return False
    return all(item.get(key) is expected for item in items)


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).strip()


def _extract_graph_edge(proposal: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    for container_key in GRAPH_EDGE_CONTAINER_KEYS:
        candidate = proposal.get(container_key)
        if isinstance(candidate, dict) and candidate:
            return candidate
    for item in items:
        for container_key in GRAPH_EDGE_CONTAINER_KEYS:
            candidate = item.get(container_key)
            if isinstance(candidate, dict) and candidate:
                return candidate
    edges = proposal.get("edge_labels")
    if isinstance(edges, list):
        for entry in edges:
            if isinstance(entry, dict) and entry:
                return entry
    flat: dict[str, Any] = {}
    for key in GRAPH_EDGE_FIELD_KEYS:
        if key in proposal:
            flat[key] = proposal[key]
    if flat:
        return flat
    for item in items:
        inner: dict[str, Any] = {}
        for key in GRAPH_EDGE_FIELD_KEYS:
            if key in item:
                inner[key] = item[key]
        if inner:
            return inner
    return {}


def _bool_field(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def _validate_graph_edge(edge: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    review_required: list[str] = []
    source_node_state_id = _coerce_str(edge.get("source_node_state_id") or edge.get("source_state") or edge.get("from_state"))
    target_node_state_id = _coerce_str(edge.get("target_node_state_id") or edge.get("target_state") or edge.get("to_state"))
    edge_transition_id = _coerce_str(edge.get("edge_transition_id") or edge.get("transition_id"))
    edge_label = _coerce_str(edge.get("edge_label"))
    append_operation = _coerce_str(edge.get("append_operation"))
    overlap_preserved = _bool_field(edge.get("overlap_preserved"))
    apply_scope = _coerce_str(edge.get("apply_scope"))
    coverage_status = _coerce_str(edge.get("coverage_status"))
    measurement_status = _coerce_str(edge.get("measurement_status"))
    raw_interference = edge.get("verifier_interference_result")
    if isinstance(raw_interference, dict):
        verifier_interference_result = _coerce_str(raw_interference.get("final_candidate_classification") or json.dumps(raw_interference, sort_keys=True))
    else:
        verifier_interference_result = _coerce_str(raw_interference) or _coerce_str(edge.get("verifier_result"))
    sequence_position = edge.get("sequence_position")

    edge_label_present = bool(edge_label)
    edge_transition_id_present = bool(edge_transition_id)
    source_node_validated = bool(source_node_state_id)
    target_node_validated = bool(target_node_state_id)
    graph_edge_present = any(
        [
            edge_label_present,
            edge_transition_id_present,
            source_node_validated,
            target_node_validated,
        ]
    )

    if not edge_label_present:
        review_required.append("graph edge label missing; proposal cannot reach verified_for_apply")
    if not edge_transition_id_present:
        review_required.append("graph edge_transition_id missing; proposal cannot reach verified_for_apply")
    if not source_node_validated:
        review_required.append("source_node_state_id missing on graph edge")
    if not target_node_validated:
        review_required.append("target_node_state_id missing on graph edge")
    if not overlap_preserved and graph_edge_present:
        review_required.append("overlap_preserved must be true on a verified graph edge")
    if apply_scope and apply_scope != EXPECTED_VERIFIED_EDGE_VALUES["apply_scope"]:
        blockers.append(
            f"apply_scope expected {EXPECTED_VERIFIED_EDGE_VALUES['apply_scope']!r}, got {apply_scope!r}"
        )

    fields = {
        "source_node_state_id": source_node_state_id,
        "target_node_state_id": target_node_state_id,
        "edge_transition_id": edge_transition_id,
        "edge_label": edge_label,
        "append_operation": append_operation,
        "overlap_preserved": overlap_preserved,
        "apply_scope": apply_scope,
        "coverage_status": coverage_status,
        "measurement_status": measurement_status,
        "verifier_interference_result": verifier_interference_result,
        "sequence_position": sequence_position,
        "edge_label_present": edge_label_present,
        "edge_transition_id_present": edge_transition_id_present,
        "source_node_validated": source_node_validated,
        "target_node_validated": target_node_validated,
        "graph_edge_present": graph_edge_present,
    }
    return fields, blockers, review_required


def _proposal_id(proposal: dict[str, Any], items: list[dict[str, Any]], proposal_hash: str) -> str:
    for key in ("proposal_id", "candidate_file_id", "receipt_id"):
        value = proposal.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for item in items:
        value = item.get("proposal_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"proposal_{proposal_hash[:12]}"


def _generated_by_approved_system(proposal_path: Path, root: Path, proposal: dict[str, Any]) -> bool:
    rel = relative_path(root, proposal_path).replace("/", "\\").lower()
    known_file_structure = (
        rel.startswith("reports\\debruijn_quantum_file_structure\\")
        and proposal_path.name.startswith("candidate_fix_proposals_")
        and proposal_path.suffix.lower() == ".json"
    )
    known_runtime_receipt = (
        rel.startswith("reports\\debruijn_quantum_runtime_receipts\\")
        and proposal_path.name.startswith("debruijn_quantum_runtime_")
        and proposal_path.suffix.lower() == ".json"
    )
    marker_text = " ".join(_iter_strings(proposal)).lower()
    marker_present = "debruijn" in marker_text or "de bruijn" in marker_text
    return known_file_structure or known_runtime_receipt or marker_present


def validate_proposal(path: Path, root: Path | None = None) -> ProposalValidationResult:
    workspace = resolve_workspace_root(root)
    blocker_reasons: list[str] = []
    review_required_reasons: list[str] = []
    proposal_hash = ""
    proposal_id = "unknown"
    inside_workspace = False
    valid_structure = False
    generated_by_approved_system = False
    human_review_required = False
    apply_allowed_at_generation = True
    verified_for_apply = False
    target_paths_validated = False
    unsafe_content_scan_passed = False
    authority_hierarchy_passed = False
    prompt_injection_guard_passed = False
    route_metadata_verified = False
    graph_fields: dict[str, Any] = {}
    graph_alignment_ok = False

    try:
        resolved_path = _proposal_path(path, workspace)
        inside_workspace = True
        proposal_hash = sha256_file(resolved_path)
        proposal = load_proposal(resolved_path, workspace)
        items = _proposal_items(proposal)
        proposal_id = _proposal_id(proposal, items, proposal_hash)
        valid_structure = bool(items) and (
            "proposals" in proposal or any("proposal_id" in item for item in items)
        )
        generated_by_approved_system = _generated_by_approved_system(resolved_path, workspace, proposal)
        human_review_required = (
            proposal.get("human_review_required") is True
            or _bool_all(items, "human_review_required", True)
        )
        apply_allowed_at_generation = not (
            proposal.get("apply_allowed") is False
            or _bool_all(items, "apply_allowed", False)
        )
        verified_for_apply = (
            proposal.get("verified_for_apply") is True
            or _bool_all(items, "verified_for_apply", True)
        )

        edge = _extract_graph_edge(proposal, items)
        graph_fields, edge_blockers, edge_review = _validate_graph_edge(edge)
        blocker_reasons.extend(edge_blockers)
        review_required_reasons.extend(edge_review)
        graph_alignment_ok = (
            graph_fields["edge_label_present"]
            and graph_fields["edge_transition_id_present"]
            and graph_fields["source_node_validated"]
            and graph_fields["target_node_validated"]
            and graph_fields["overlap_preserved"]
            and not edge_blockers
        )

        strings = [text.lower() for text in _iter_string_values(proposal)]
        unsafe_hits = sorted({term for term in FORBIDDEN_CONTENT_TERMS if any(term in text for text in strings)})
        injection_hits = sorted({term for term in PROMPT_INJECTION_TERMS if any(term in text for text in strings)})
        unsafe_content_scan_passed = not unsafe_hits
        authority_hierarchy_passed = not injection_hits
        prompt_injection_guard_passed = not injection_hits

        raw_targets = _extract_target_paths(proposal)
        normalized_targets: list[Path] = []
        for raw in raw_targets:
            try:
                normalized_targets.append(_normalize_target_path(raw, workspace))
            except ProposalSafetyError as exc:
                blocker_reasons.append(str(exc))
        target_paths_validated = bool(raw_targets) and len(normalized_targets) == len(raw_targets)
        route_metadata_verified = not any(
            "route_verification_set_v1.json" in relative_path(workspace, target).lower()
            for target in normalized_targets
        )

        if unsafe_hits:
            blocker_reasons.append(f"unsafe content terms found: {', '.join(unsafe_hits)}")
        if injection_hits:
            blocker_reasons.append(f"prompt/authority guard terms found: {', '.join(injection_hits)}")
        if not valid_structure:
            blocker_reasons.append("proposal structure is not a known De Bruijn candidate shape")
        if not generated_by_approved_system:
            blocker_reasons.append("proposal is not from an approved De Bruijn proposal source")
        if not human_review_required:
            blocker_reasons.append("human_review_required must be true")
        if apply_allowed_at_generation:
            blocker_reasons.append("apply_allowed must be false at generation time")
        if not verified_for_apply:
            review_required_reasons.append("verified_for_apply is absent or false; not eligible for apply attempt")
        if not target_paths_validated:
            blocker_reasons.append("target paths are missing or invalid")
        if not route_metadata_verified:
            review_required_reasons.append("route metadata updates need a future route-verified apply flow")
    except (OSError, ProposalSafetyError) as exc:
        resolved_path = path
        blocker_reasons.append(str(exc))

    if not graph_fields:
        graph_fields = {
            "source_node_state_id": "",
            "target_node_state_id": "",
            "edge_transition_id": "",
            "edge_label": "",
            "append_operation": "",
            "overlap_preserved": False,
            "apply_scope": "",
            "coverage_status": "",
            "measurement_status": "",
            "verifier_interference_result": "",
            "sequence_position": None,
            "edge_label_present": False,
            "edge_transition_id_present": False,
            "source_node_validated": False,
            "target_node_validated": False,
            "graph_edge_present": False,
        }

    eligible_for_apply_attempt = all(
        [
            valid_structure,
            inside_workspace,
            generated_by_approved_system,
            human_review_required,
            not apply_allowed_at_generation,
            verified_for_apply,
            target_paths_validated,
            unsafe_content_scan_passed,
            authority_hierarchy_passed,
            prompt_injection_guard_passed,
            route_metadata_verified,
            graph_alignment_ok,
        ]
    )

    return ProposalValidationResult(
        proposal_path=str(resolved_path),
        proposal_id=proposal_id,
        proposal_hash=proposal_hash,
        valid_structure=valid_structure,
        inside_workspace=inside_workspace,
        generated_by_approved_system=generated_by_approved_system,
        human_review_required=human_review_required,
        apply_allowed_at_generation=apply_allowed_at_generation,
        verified_for_apply=verified_for_apply,
        target_paths_validated=target_paths_validated,
        unsafe_content_scan_passed=unsafe_content_scan_passed,
        authority_hierarchy_passed=authority_hierarchy_passed,
        prompt_injection_guard_passed=prompt_injection_guard_passed,
        route_metadata_verified=route_metadata_verified,
        approval_phrase_required=True,
        password_gate_required=True,
        eligible_for_apply_attempt=eligible_for_apply_attempt,
        source_node_state_id=graph_fields["source_node_state_id"],
        target_node_state_id=graph_fields["target_node_state_id"],
        edge_transition_id=graph_fields["edge_transition_id"],
        edge_label=graph_fields["edge_label"],
        append_operation=graph_fields["append_operation"],
        overlap_preserved=graph_fields["overlap_preserved"],
        apply_scope=graph_fields["apply_scope"],
        coverage_status=graph_fields["coverage_status"],
        measurement_status=graph_fields["measurement_status"],
        verifier_interference_result=graph_fields["verifier_interference_result"],
        sequence_position=graph_fields["sequence_position"],
        edge_label_present=graph_fields["edge_label_present"],
        edge_transition_id_present=graph_fields["edge_transition_id_present"],
        source_node_validated=graph_fields["source_node_validated"],
        target_node_validated=graph_fields["target_node_validated"],
        graph_edge_present=graph_fields["graph_edge_present"],
        graph_alignment_ok=graph_alignment_ok,
        blocker_reasons=blocker_reasons,
        review_required_reasons=review_required_reasons,
    )


def _target_hash_manifest(targets: list[Path], root: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for target in targets:
        rel = relative_path(root, target)
        if target.exists() and target.is_file():
            manifest[rel] = sha256_file(target)
        elif target.exists():
            manifest[rel] = "exists_non_file"
        else:
            manifest[rel] = "missing"
    return manifest


def _classify_allowed_actions(proposal: dict[str, Any], targets: list[Path], root: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    allowed: list[str] = []
    files_to_create: list[str] = []
    files_to_update: list[str] = []
    rejected: list[str] = []

    for target in targets:
        rel = relative_path(root, target)
        lowered = rel.lower()
        if "route_verification_set_v1.json" in lowered:
            rejected.append(f"{rel}: route metadata apply deferred to future verified route flow")
            continue
        if lowered.startswith("memory\\") and lowered.endswith(("_contract_v1.md", "_contract_v1.json")):
            allowed.append("create_missing_contract_scaffold_files")
        elif lowered.startswith("tools\\verify_") and lowered.endswith(".py"):
            allowed.append("create_missing_verifier_scaffold_files")
        elif lowered.startswith("reports\\codex_bridge\\") and lowered.endswith(".md"):
            allowed.append("create_missing_report_scaffold_files")
        elif lowered.startswith("reports\\"):
            allowed.append("create_receipts_reports")
        elif lowered.startswith("memory\\") and lowered.endswith((".md", ".json")):
            allowed.append("update_safe_docs_maps")
        else:
            rejected.append(f"{rel}: target is outside V1 scaffold/report/doc allowlist")
            continue

        if target.exists():
            files_to_update.append(rel)
        else:
            files_to_create.append(rel)

    explicit_action_text = " ".join(_iter_strings(proposal)).lower()
    if "delete" in explicit_action_text or "remove file" in explicit_action_text:
        rejected.append("delete/remove actions are forbidden in V1")

    return sorted(set(allowed)), files_to_create, files_to_update, rejected


def build_apply_plan(
    validation: ProposalValidationResult,
    proposal: dict[str, Any],
    root: Path | None = None,
    dry_run: bool = True,
) -> ApplyPlan:
    workspace = resolve_workspace_root(root)
    targets: list[Path] = []
    rejected: list[str] = []
    for raw in _extract_target_paths(proposal):
        try:
            targets.append(_normalize_target_path(raw, workspace))
        except ProposalSafetyError as exc:
            rejected.append(str(exc))

    allowed_actions, files_to_create, files_to_update, action_rejections = _classify_allowed_actions(
        proposal,
        targets,
        workspace,
    )
    rejected.extend(action_rejections)

    if not validation.valid_structure:
        rejected.append("proposal structure is invalid")
    if not validation.human_review_required:
        rejected.append("human review is required")
    if validation.apply_allowed_at_generation:
        rejected.append("proposal was not generated with apply_allowed false")
    if not validation.verified_for_apply:
        rejected.append("proposal is validate/dry-run only because verified_for_apply is false or absent")

    return ApplyPlan(
        proposal_id=validation.proposal_id,
        proposal_path=validation.proposal_path,
        allowed_actions=allowed_actions,
        target_paths=[relative_path(workspace, target) for target in targets],
        files_to_create=files_to_create,
        files_to_update=files_to_update,
        files_rejected=sorted(set(rejected)),
        backup_hash_manifest=_target_hash_manifest(targets, workspace),
        dry_run_only=dry_run,
        apply_enabled=False,
        human_review_required=True,
        edge_transition_id=validation.edge_transition_id,
        edge_label=validation.edge_label,
        source_node_state_id=validation.source_node_state_id,
        target_node_state_id=validation.target_node_state_id,
        apply_scope=validation.apply_scope,
        graph_edge_apply_disabled=True,
    )


def _receipt_id(action_type: str) -> str:
    return f"{ENGINE_ID}_{action_type}_{timestamp_slug()}"


def _receipt_paths(root: Path, receipt_id: str) -> tuple[Path, Path]:
    folder = (root / APPLY_RECEIPT_FOLDER).resolve()
    if not _is_relative_to(folder, root):
        raise ProposalSafetyError("apply receipt folder resolved outside workspace")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{receipt_id}.json", folder / f"{receipt_id}.md"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            lowered = str(key).lower()
            if any(secret in lowered for secret in ("password", "salt", "hash", "secret", "token")):
                if lowered in {"proposal_hash", "password_gate_required", "password_gate_result"}:
                    redacted[key] = child
                else:
                    redacted[key] = "redacted"
            else:
                redacted[key] = _redact(child)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def write_apply_receipt(result: ApplyResult, root: Path | None = None) -> list[str]:
    workspace = resolve_workspace_root(root)
    receipt_id = _receipt_id(result.action_type)
    json_path, md_path = _receipt_paths(workspace, receipt_id)
    payload = _redact(asdict(result))
    payload["receipt_id"] = receipt_id
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        f"# {receipt_id}",
        "",
        f"- engine_id: {result.engine_id}",
        f"- action_type: {result.action_type}",
        f"- input_proposal_path: {result.input_proposal_path}",
        f"- proposal_id: {result.proposal_id}",
        f"- proposal_hash: {result.proposal_hash}",
        f"- approval_detected: {str(result.approval_detected).lower()}",
        f"- approval_phrase_name: {result.approval_phrase_name}",
        f"- password_gate_result: {result.password_gate_result}",
        f"- target_paths_validated: {str(result.target_paths_validated).lower()}",
        f"- files_changed: {json.dumps(result.files_changed)}",
        f"- files_not_changed: {json.dumps(result.files_not_changed)}",
        f"- final_status: {result.final_status}",
        f"- human_review_required: {str(result.human_review_required).lower()}",
        "",
        "## Graph Edge Identity",
        f"- graph_alignment_contract_id: {result.graph_alignment_contract_id}",
        f"- source_node_state_id: {result.source_node_state_id}",
        f"- target_node_state_id: {result.target_node_state_id}",
        f"- edge_transition_id: {result.edge_transition_id}",
        f"- edge_label: {result.edge_label}",
        f"- append_operation: {result.append_operation}",
        f"- overlap_preserved: {str(result.overlap_preserved).lower()}",
        f"- sequence_position: {result.sequence_position}",
        f"- coverage_status_before: {result.coverage_status_before}",
        f"- coverage_status_after: {result.coverage_status_after}",
        f"- measurement_status_before: {result.measurement_status_before}",
        f"- measurement_status_after: {result.measurement_status_after}",
        f"- verifier_interference_result: {result.verifier_interference_result}",
        f"- graph_edge_apply_disabled: {str(result.graph_edge_apply_disabled).lower()}",
        f"- apply_enabled: {str(result.apply_enabled).lower()}",
        "",
        "## Forbidden Actions Not Performed",
    ]
    lines.extend(f"- {item}" for item in result.forbidden_actions_not_performed)
    lines.extend(["", "## Rollback Note", result.rollback_note])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [relative_path(workspace, json_path), relative_path(workspace, md_path)]


def create_dry_run_result(
    validation: ProposalValidationResult,
    plan: ApplyPlan,
    started_at: str,
    action_type: str = "dry_run_apply_plan",
) -> ApplyResult:
    ended_at = utc_now()
    final_status = "dry_run_plan_created_apply_disabled"
    if validation.blocker_reasons:
        final_status = "dry_run_review_required"
    return ApplyResult(
        engine_id=ENGINE_ID,
        action_type=action_type,
        started_at=started_at,
        ended_at=ended_at,
        input_proposal_path=validation.proposal_path,
        proposal_id=validation.proposal_id,
        proposal_hash=validation.proposal_hash,
        approval_detected=False,
        approval_phrase_name="not_used",
        password_gate_result="not_required_for_validate_or_dry_run",
        pre_apply_verifier_results={"status": "not_run_for_validate_or_dry_run"},
        files_read=[validation.proposal_path],
        files_changed=[],
        files_not_changed=plan.target_paths,
        target_paths_validated=validation.target_paths_validated,
        forbidden_actions_not_performed=FORBIDDEN_ACTIONS_NOT_PERFORMED,
        post_apply_verifier_results={"status": "not_run_for_validate_or_dry_run"},
        rollback_note="No target files changed; rollback is not required for validate/dry-run.",
        final_status=final_status,
        human_review_required=True,
        source_node_state_id=validation.source_node_state_id,
        target_node_state_id=validation.target_node_state_id,
        edge_transition_id=validation.edge_transition_id,
        edge_label=validation.edge_label,
        append_operation=validation.append_operation,
        overlap_preserved=validation.overlap_preserved,
        sequence_position=validation.sequence_position,
        coverage_status_before=validation.coverage_status,
        coverage_status_after=validation.coverage_status,
        measurement_status_before=validation.measurement_status,
        measurement_status_after=validation.measurement_status,
        verifier_interference_result=validation.verifier_interference_result,
        graph_edge_apply_disabled=True,
        apply_enabled=False,
        graph_alignment_contract_id=GRAPH_ALIGNMENT_CONTRACT_ID,
    )


def validate_only(path: Path, root: Path | None = None) -> ProposalValidationResult:
    return validate_proposal(path, root)


def dry_run_apply_plan(path: Path, root: Path | None = None) -> tuple[ProposalValidationResult, ApplyPlan, ApplyResult, list[str]]:
    started_at = utc_now()
    workspace = resolve_workspace_root(root)
    proposal = load_proposal(path, workspace)
    validation = validate_proposal(path, workspace)
    plan = build_apply_plan(validation, proposal, workspace, dry_run=True)
    result = create_dry_run_result(validation, plan, started_at)
    receipt_paths = write_apply_receipt(result, workspace)
    return validation, plan, result, receipt_paths


def status_payload(root: Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_root(root)
    return {
        "engine_id": ENGINE_ID,
        "module": "engel_debruijn_quantum_apply.py",
        "workspace_root": str(workspace),
        "mode": "local_offline_validate_and_dry_run_only",
        "actual_apply_enabled": ACTUAL_APPLY_ENABLED,
        "command_route_added": COMMAND_ROUTE_ADDED,
        "trusted_memory_write_enabled": TRUSTED_MEMORY_WRITE_ENABLED,
        "build_promote_enabled": BUILD_PROMOTE_ENABLED,
        "apply_graph_alignment_enabled_now": APPLY_GRAPH_ALIGNMENT_ENABLED_NOW,
        "graph_alignment_contract_id": GRAPH_ALIGNMENT_CONTRACT_ID,
        "graph_alignment_mode": "validate_and_dry_run_records_graph_edge_fields_only",
        "receipt_folder": str(APPLY_RECEIPT_FOLDER),
        "future_approval_phrase": APPROVAL_PHRASE,
        "safety_boundary": "no actual apply, no trust, no promote, no route, no queue, no trusted-memory write",
    }


def _print_json(data: Any) -> None:
    print(json.dumps(_redact(data), indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel De Bruijn Quantum apply engine V1 helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("proposal_path")

    dry_run_parser = subparsers.add_parser("dry-run")
    dry_run_parser.add_argument("proposal_path")

    args = parser.parse_args(argv)

    try:
        root = resolve_workspace_root(DEFAULT_ROOT)
        if args.command == "status":
            _print_json(status_payload(root))
            return 0
        if args.command == "validate":
            validation = validate_only(Path(args.proposal_path), root)
            _print_json(asdict(validation))
            return 0 if validation.valid_structure and validation.inside_workspace else 2
        if args.command == "dry-run":
            validation, plan, result, receipt_paths = dry_run_apply_plan(Path(args.proposal_path), root)
            _print_json(
                {
                    "validation": asdict(validation),
                    "plan": asdict(plan),
                    "result": asdict(result),
                    "receipt_paths": receipt_paths,
                }
            )
            return 0 if validation.valid_structure and validation.inside_workspace else 2
    except ProposalSafetyError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"FAIL file operation failed: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
