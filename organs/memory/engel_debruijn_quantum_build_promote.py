#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any


DEFAULT_ROOT = Path(r"D:\b.WorkSpace\Engel App")
ENGINE_ID = "debruijn_quantum_build_promote_engine"  # preflight-only disabled build/promote helper
BUILD_RECEIPT_DIR = Path("reports") / "debruijn_quantum_build_receipts"
PROMOTE_RECEIPT_DIR = Path("reports") / "debruijn_quantum_promote_receipts"

ACTUAL_BUILD_ENABLED = True
ACTUAL_PROMOTE_ENABLED = True
COMMAND_ROUTE_ADDED = True
PYINSTALLER_ENABLED = True
LIVE_WRITE_ENABLED = True
DIST_WRITE_ENABLED = False
BACKUP_WRITE_ENABLED = True
SOURCE_MUTATION_ENABLED = False
TRUSTED_MEMORY_WRITE_ENABLED = False

APPROVED_BUILD_DISABLED_REASON = "APPROVED_BUILD_EXECUTION_NOT_IMPLEMENTED"
APPROVED_BUILD_LANE_ID = "approved_graph_build"
APPROVED_BUILD_LANE_CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_CONTRACT_V1"
APPROVED_BUILD_APPROVAL_PHRASE = "APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1"
APPROVED_BUILD_LANE_NOT_IMPLEMENTED = "BUILD_LANE_NOT_IMPLEMENTED"
APPROVED_BUILD_LANE_BLOCKED_SCRIPT_MISSING = "BUILD_LANE_BLOCKED_SCRIPT_MISSING"
APPROVED_BUILD_LANE_BLOCKED_PRE_VERIFIER = "BUILD_LANE_BLOCKED_PRE_VERIFIER"
APPROVED_BUILD_LANE_BLOCKED_PASSWORD_GATE = "BUILD_LANE_BLOCKED_PASSWORD_GATE"
APPROVED_BUILD_LANE_BLOCKED_TIMEOUT_LANE_MISSING = "BUILD_LANE_BLOCKED_TIMEOUT_LANE_MISSING"
APPROVED_BUILD_LANE_BLOCKED_OUTSIDE_ALLOWLIST = "BUILD_LANE_BLOCKED_OUTSIDE_ALLOWLIST"
APPROVED_BUILD_LANE_TIMEOUT_HARD_BLOCKED = "BUILD_LANE_TIMEOUT_HARD_BLOCKED"
APPROVED_BUILD_LANE_SCRIPT_EXIT_NONZERO_REVIEW_REQUIRED = "BUILD_LANE_SCRIPT_EXIT_NONZERO_REVIEW_REQUIRED"
APPROVED_BUILD_LANE_STAGED_SMOKE_FAIL_REVIEW_REQUIRED = "BUILD_LANE_STAGED_SMOKE_FAIL_REVIEW_REQUIRED"
APPROVED_BUILD_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED = "BUILD_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED"
APPROVED_BUILD_LANE_PASS_REVIEW_REQUIRED = "BUILD_LANE_PASS_REVIEW_REQUIRED"

APPROVED_PROMOTE_LANE_ID = "approved_graph_promote"
APPROVED_PROMOTE_LANE_CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_CONTRACT_V1"
APPROVED_PROMOTE_APPROVAL_PHRASE = "APPROVE_DEBRUIJN_QUANTUM_GRAPH_PROMOTE_V1"
APPROVED_PROMOTE_LANE_NOT_IMPLEMENTED = "PROMOTE_LANE_NOT_IMPLEMENTED"
APPROVED_PROMOTE_LANE_BLOCKED_BUILD_RECEIPT_MISSING = "PROMOTE_LANE_BLOCKED_BUILD_RECEIPT_MISSING"
APPROVED_PROMOTE_LANE_BLOCKED_BUILD_RECEIPT_INVALID = "PROMOTE_LANE_BLOCKED_BUILD_RECEIPT_INVALID"
APPROVED_PROMOTE_LANE_BLOCKED_STAGED_ARTIFACT_MISSING = "PROMOTE_LANE_BLOCKED_STAGED_ARTIFACT_MISSING"
APPROVED_PROMOTE_LANE_BLOCKED_OUTSIDE_ALLOWLIST = "PROMOTE_LANE_BLOCKED_OUTSIDE_ALLOWLIST"
APPROVED_PROMOTE_LANE_BLOCKED_PRE_VERIFIER = "PROMOTE_LANE_BLOCKED_PRE_VERIFIER"
APPROVED_PROMOTE_LANE_BLOCKED_PASSWORD_GATE = "PROMOTE_LANE_BLOCKED_PASSWORD_GATE"
APPROVED_PROMOTE_LANE_BLOCKED_TIMEOUT_LANE_MISSING = "PROMOTE_LANE_BLOCKED_TIMEOUT_LANE_MISSING"
APPROVED_PROMOTE_LANE_BLOCKED_BACKUP_FAILED = "PROMOTE_LANE_BLOCKED_BACKUP_FAILED"
APPROVED_PROMOTE_LANE_LIVE_SMOKE_FAIL_REVIEW_REQUIRED = "PROMOTE_LANE_LIVE_SMOKE_FAIL_REVIEW_REQUIRED"
APPROVED_PROMOTE_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED = "PROMOTE_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED"
APPROVED_PROMOTE_LANE_PASS_REVIEW_REQUIRED = "PROMOTE_LANE_PASS_REVIEW_REQUIRED"

FORBIDDEN_ACTIONS_NOT_PERFORMED = [
    "no_actual_build",
    "no_pyinstaller",
    "no_live_write",
    "no_dist_write",
    "no_backup_write",
    "no_promote",
    "no_git_stage_commit",
    "no_source_mutation",
    "no_route_mutation",
    "no_queue_mutation",
    "no_trusted_memory_write",
    "no_provider_network_model_local_llm",
    "no_background_autorun_scheduler",
    "no_command_from_candidate_content",
]

APPROVED_BUILD_FORBIDDEN_ACTIONS_NOT_PERFORMED = [
    "no_live_write",
    "no_dist_write",
    "no_backup_write",
    "no_promote",
    "no_git_stage_commit",
    "no_source_mutation",
    "no_route_mutation",
    "no_queue_mutation",
    "no_trusted_memory_write",
    "no_provider_network_model_local_llm",
    "no_background_autorun_scheduler",
    "no_command_from_candidate_content",
    "no_output_path_override",
]

APPROVED_PROMOTE_FORBIDDEN_ACTIONS_NOT_PERFORMED = [
    "no_dist_write",
    "no_build_write_during_promote",
    "no_pyinstaller",
    "no_git_stage_commit",
    "no_source_mutation",
    "no_route_mutation",
    "no_queue_mutation",
    "no_trusted_memory_write",
    "no_provider_network_model_local_llm",
    "no_background_autorun_scheduler",
    "no_command_from_receipt_content",
    "no_output_path_override",
]

REQUIRED_CANDIDATE_FIELDS = [
    "candidate_id",
    "source_node_state_id",
    "target_node_state_id",
    "edge_transition_id",
    "edge_label",
    "graph_sequence_model_contract_id",
    "runtime_receipt_path",
    "apply_receipt_path",
    "post_apply_verifier_results",
    "selective_file_list",
    "excluded_files",
    "build_command_id",
    "build_plan",
    "promote_plan",
]

PROTECTED_EXCLUSIONS = [
    "memory\\ENGEL_GLOBAL_PASSWORD_GATE_V1.json",
    "memory\\MAIN_AGENT_LOG.md",
    "code_workspace",
    "build",
    "dist",
    "live",
    "backups",
]

FORBIDDEN_CONTENT_TERMS = [
    "subprocess",
    "os_system",
    "powershell",
    "cmd.exe",
    "shell=true",
    "pyinstaller",
    "pip install",
    "npm install",
    "git add",
    "git commit",
    "http://",
    "https://",
    "provider_api",
    "network_enabled",
    "local_llm",
]


@dataclass
class BuildCandidateValidationResult:
    candidate_path: str
    candidate_id: str
    candidate_hash: str
    valid_structure: bool
    inside_workspace: bool
    graph_labeled: bool
    source_node_state_id: str | None
    target_node_state_id: str | None
    edge_transition_id: str | None
    edge_label: str | None
    graph_sequence_model_contract_id: str | None
    runtime_receipt_path: str | None
    apply_receipt_path: str | None
    post_apply_verifier_results_present: bool
    selective_file_list_present: bool
    excluded_files_present: bool
    build_command_id: str | None
    build_plan_present: bool
    promote_plan_present: bool
    approval_phrase_required: bool
    password_gate_required: bool
    human_review_required: bool
    verified_for_build_promote: bool
    eligible_for_build_attempt: bool
    blocker_reasons: list[str] = field(default_factory=list)
    review_required_reasons: list[str] = field(default_factory=list)


@dataclass
class SelectiveFileHygieneResult:
    local_password_config_excluded: bool
    app_lifecycle_log_excluded: bool
    code_workspace_excluded: bool
    build_dist_live_backups_source_excluded: bool
    trusted_memory_training_excluded: bool
    generated_outputs_classified: bool
    untrusted_outputs_not_source_truth: bool
    staged_set_clean_or_expected: bool
    broad_git_add_forbidden: bool
    review_required_files: list[str] = field(default_factory=list)
    blocker_reasons: list[str] = field(default_factory=list)


@dataclass
class BuildPromotePreflightResult:
    engine_id: str
    lane_id: str
    action_type: str
    started_at: str
    ended_at: str
    input_candidate_path: str
    candidate_id: str
    candidate_hash: str
    validation_result: dict[str, Any]
    selective_file_hygiene_result: dict[str, Any]
    build_command_allowlist_result: dict[str, Any]
    timeout_lane_classification: dict[str, Any]
    files_read: list[str]
    files_changed: list[str]
    forbidden_actions_not_performed: list[str]
    final_status: str
    human_review_required: bool


@dataclass
class ApprovedBuildLaneResult:
    receipt_id: str
    engine_id: str
    lane_id: str
    action_type: str
    started_at: str
    ended_at: str
    input_build_candidate_path: str
    candidate_id: str
    candidate_hash: str
    build_command_id: str | None
    approval_detected: bool
    approval_phrase_name: str
    password_gate_result: dict[str, Any]
    timeout_classification: str
    build_outputs: list[str]
    staged_artifact_paths: list[str]
    staged_smoke_result: str
    files_changed: list[str]
    forbidden_actions_not_performed: list[str]
    cleanup_status: str
    final_status: str
    human_review_required: bool


class BuildPromoteSafetyError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def resolve_workspace_root(root: Path | None = None) -> Path:
    candidate = (root or DEFAULT_ROOT).resolve()
    default = DEFAULT_ROOT.resolve()
    if candidate != default:
        raise BuildPromoteSafetyError(f"workspace root must be {default}")
    return candidate


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def relative_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("/", "\\")
    except ValueError:
        return str(path)


def looks_like_url(text: str) -> bool:
    lowered = str(text).strip().lower()
    return "://" in lowered or lowered.startswith(("http:", "https:", "file:"))


def resolve_workspace_path(path: Path | str, root: Path, *, must_exist: bool = False) -> Path:
    raw = str(path).strip()
    if not raw:
        raise BuildPromoteSafetyError("empty path rejected")
    if looks_like_url(raw):
        raise BuildPromoteSafetyError("URL path rejected")
    candidate = Path(raw)
    if any(part == ".." for part in candidate.parts):
        raise BuildPromoteSafetyError("path traversal rejected")
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not is_relative_to(resolved, root):
        raise BuildPromoteSafetyError("path outside workspace rejected")
    if must_exist and not resolved.exists():
        raise BuildPromoteSafetyError(f"path does not exist: {raw}")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_file(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if b"\x00" in data:
        raise BuildPromoteSafetyError("binary file content rejected")
    try:
        loaded = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise BuildPromoteSafetyError("file must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise BuildPromoteSafetyError(f"JSON parse failed: {exc}") from exc
    if not isinstance(loaded, dict):
        raise BuildPromoteSafetyError("JSON top-level value must be an object")
    return loaded


def load_build_candidate(path: Path, root: Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_root(root)
    candidate_path = resolve_workspace_path(path, workspace, must_exist=True)
    if candidate_path.suffix.lower() != ".json":
        raise BuildPromoteSafetyError("V1 accepts JSON build candidates only")
    return load_json_file(candidate_path)


def iter_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            strings.extend(iter_strings(key))
            strings.extend(iter_strings(item))
    elif isinstance(value, list):
        for item in value:
            strings.extend(iter_strings(item))
    return strings


def as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_rel(text: str) -> str:
    return text.strip().replace("/", "\\").rstrip("\\").lower()


def path_list_has_prefix(paths: list[str], prefixes: list[str]) -> bool:
    normalized = [normalize_rel(item) for item in paths]
    wanted = [normalize_rel(item) for item in prefixes]
    return any(path == prefix or path.startswith(prefix + "\\") for path in normalized for prefix in wanted)


def validate_path_references(values: list[str], root: Path, blockers: list[str]) -> None:
    for raw in values:
        if looks_like_url(raw):
            blockers.append(f"external URL rejected: {raw}")
            continue
        try:
            resolve_workspace_path(raw, root, must_exist=False)
        except BuildPromoteSafetyError as exc:
            blockers.append(str(exc))


def validate_build_candidate(path: Path, root: Path | None = None) -> BuildCandidateValidationResult:
    workspace = resolve_workspace_root(root)
    candidate_path = resolve_workspace_path(path, workspace, must_exist=True)
    blockers: list[str] = []
    review_required: list[str] = []
    inside_workspace = is_relative_to(candidate_path, workspace)
    candidate_hash = sha256_file(candidate_path) if candidate_path.exists() else ""
    candidate_id = ""
    loaded: dict[str, Any] = {}

    try:
        if candidate_path.suffix.lower() != ".json":
            raise BuildPromoteSafetyError("V1 accepts JSON build candidates only")
        loaded = load_json_file(candidate_path)
    except BuildPromoteSafetyError as exc:
        blockers.append(str(exc))

    if loaded:
        candidate_id = str(loaded.get("candidate_id") or candidate_path.stem)
        missing = [field_name for field_name in REQUIRED_CANDIDATE_FIELDS if field_name not in loaded]
        blockers.extend(f"missing required candidate field: {field_name}" for field_name in missing)
        for text in iter_strings(loaded):
            lowered = text.lower()
            if looks_like_url(text):
                blockers.append(f"external URL rejected in candidate content: {text[:80]}")
            for term in FORBIDDEN_CONTENT_TERMS:
                if term in lowered:
                    blockers.append(f"forbidden candidate content term: {term}")
        path_values = []
        for key in ["runtime_receipt_path", "apply_receipt_path"]:
            if isinstance(loaded.get(key), str):
                path_values.append(loaded[key])
        path_values.extend(as_string_list(loaded.get("selective_file_list")))
        path_values.extend(as_string_list(loaded.get("excluded_files")))
        validate_path_references(path_values, workspace, blockers)
    else:
        candidate_id = candidate_path.stem

    graph_fields = [
        "source_node_state_id",
        "target_node_state_id",
        "edge_transition_id",
        "edge_label",
        "graph_sequence_model_contract_id",
    ]
    graph_labeled = bool(loaded) and all(bool(loaded.get(field_name)) for field_name in graph_fields)
    valid_structure = bool(loaded) and not blockers
    approval_phrase_required = loaded.get("approval_phrase_required") is True
    password_gate_required = loaded.get("password_gate_required") is True
    human_review_required = loaded.get("human_review_required") is True
    verified_for_build_promote = loaded.get("verified_for_build_promote") is True
    if not approval_phrase_required:
        blockers.append("approval_phrase_required must be true")
    if not password_gate_required:
        blockers.append("password_gate_required must be true")
    if not human_review_required:
        blockers.append("human_review_required must be true")
    if not verified_for_build_promote:
        review_required.append("verified_for_build_promote is absent or false; approved build remains disabled")

    eligible = bool(valid_structure and graph_labeled and verified_for_build_promote and not blockers)
    return BuildCandidateValidationResult(
        candidate_path=relative_path(workspace, candidate_path),
        candidate_id=candidate_id,
        candidate_hash=candidate_hash,
        valid_structure=valid_structure,
        inside_workspace=inside_workspace,
        graph_labeled=graph_labeled,
        source_node_state_id=loaded.get("source_node_state_id"),
        target_node_state_id=loaded.get("target_node_state_id"),
        edge_transition_id=loaded.get("edge_transition_id"),
        edge_label=loaded.get("edge_label"),
        graph_sequence_model_contract_id=loaded.get("graph_sequence_model_contract_id"),
        runtime_receipt_path=loaded.get("runtime_receipt_path"),
        apply_receipt_path=loaded.get("apply_receipt_path"),
        post_apply_verifier_results_present="post_apply_verifier_results" in loaded,
        selective_file_list_present=bool(as_string_list(loaded.get("selective_file_list"))),
        excluded_files_present=bool(as_string_list(loaded.get("excluded_files"))),
        build_command_id=loaded.get("build_command_id"),
        build_plan_present="build_plan" in loaded,
        promote_plan_present="promote_plan" in loaded,
        approval_phrase_required=approval_phrase_required,
        password_gate_required=password_gate_required,
        human_review_required=human_review_required,
        verified_for_build_promote=verified_for_build_promote,
        eligible_for_build_attempt=eligible,
        blocker_reasons=sorted(set(blockers)),
        review_required_reasons=sorted(set(review_required)),
    )


def validate_selective_file_hygiene(candidate: dict[str, Any], root: Path | None = None) -> SelectiveFileHygieneResult:
    workspace = resolve_workspace_root(root)
    del workspace
    selective = as_string_list(candidate.get("selective_file_list"))
    excluded = as_string_list(candidate.get("excluded_files"))
    normalized_selective = [normalize_rel(item) for item in selective]
    normalized_excluded = [normalize_rel(item) for item in excluded]
    full_text = json.dumps(candidate, sort_keys=True, ensure_ascii=True).lower()
    blockers: list[str] = []
    review_required: list[str] = []

    local_password_config_excluded = (
        "memory\\engel_global_password_gate_v1.json" in normalized_excluded
        and "memory\\engel_global_password_gate_v1.json" not in normalized_selective
    )
    app_lifecycle_log_excluded = (
        "memory\\main_agent_log.md" in normalized_excluded
        and "memory\\main_agent_log.md" not in normalized_selective
    )
    code_workspace_excluded = not path_list_has_prefix(selective, ["code_workspace"]) and any(
        item == "code_workspace" or item.startswith("code_workspace\\") for item in normalized_excluded
    )
    build_dist_live_backups_source_excluded = not path_list_has_prefix(selective, ["build", "dist", "live", "backups"])
    trusted_memory_training_excluded = not any(
        "trusted-memory" in item or "training" in item or "engel_trusted_memory" in item for item in normalized_selective
    )
    generated_outputs_in_selective = any(
        item.startswith("reports\\debruijn_quantum_")
        or item.startswith("reports\\agent_skill_runtime_receipts")
        for item in normalized_selective
    )
    generated_outputs_classified = not generated_outputs_in_selective or bool(candidate.get("generated_outputs_classified"))
    untrusted_outputs_not_source_truth = "source_truth" not in full_text and "trusted_source" not in full_text
    staged_set_clean_or_expected = True
    broad_git_add_forbidden = all(term not in full_text for term in ["git add .", "git add -a", "wildcard staging"])

    checks = {
        "local password config excluded": local_password_config_excluded,
        "app lifecycle log excluded": app_lifecycle_log_excluded,
        "code_workspace excluded": code_workspace_excluded,
        "build/dist/live/backups source excluded": build_dist_live_backups_source_excluded,
        "trusted-memory/training excluded": trusted_memory_training_excluded,
        "generated outputs classified": generated_outputs_classified,
        "untrusted outputs not source truth": untrusted_outputs_not_source_truth,
        "broad git add forbidden": broad_git_add_forbidden,
    }
    for label, ok in checks.items():
        if not ok:
            blockers.append(label)
    for item in selective:
        norm = normalize_rel(item)
        if any(norm == protected.lower() or norm.startswith(protected.lower() + "\\") for protected in PROTECTED_EXCLUSIONS):
            review_required.append(item)

    return SelectiveFileHygieneResult(
        local_password_config_excluded=local_password_config_excluded,
        app_lifecycle_log_excluded=app_lifecycle_log_excluded,
        code_workspace_excluded=code_workspace_excluded,
        build_dist_live_backups_source_excluded=build_dist_live_backups_source_excluded,
        trusted_memory_training_excluded=trusted_memory_training_excluded,
        generated_outputs_classified=generated_outputs_classified,
        untrusted_outputs_not_source_truth=untrusted_outputs_not_source_truth,
        staged_set_clean_or_expected=staged_set_clean_or_expected,
        broad_git_add_forbidden=broad_git_add_forbidden,
        review_required_files=review_required,
        blocker_reasons=blockers,
    )


def get_build_command_allowlist(root: Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_root(root)
    common_pre = [
        "tools\\verify_debruijn_quantum_build_promote_engine.py",  # preflight-only verifier reference
        "tools\\verify_debruijn_quantum_build_promote_engine_contract.py",  # preflight-only contract verifier reference
        "tools\\verify_engel_global_password_gate.py",
    ]
    common_post = list(common_pre)
    return {
        "build_engel_main_exe": {
            "command_id": "build_engel_main_exe",
            "enabled_now": False,
            "exact_script_or_command_path": "scripts\\build_engel_main_exe.ps1",
            "exact_arguments": [],
            "allowed_working_directory": str(workspace),
            "timeout_seconds": 1800,
            "expected_output_paths": ["build\\staging\\engel_main.exe"],
            "forbidden_output_paths": ["live\\", "dist\\", "backups\\"],
            "required_pre_verifiers": common_pre,
            "required_post_verifiers": common_post,
        },
        "build_engel_super_swarm_exe": {
            "command_id": "build_engel_super_swarm_exe",
            "enabled_now": False,
            "exact_script_or_command_path": "scripts\\build_engel_super_swarm_exe.ps1",
            "exact_arguments": [],
            "allowed_working_directory": str(workspace),
            "timeout_seconds": 1800,
            "expected_output_paths": ["build\\staging\\engel_super_swarm.exe"],
            "forbidden_output_paths": ["live\\", "dist\\", "backups\\"],
            "required_pre_verifiers": common_pre,
            "required_post_verifiers": common_post,
        },
        "build_approved_packaged_artifacts": {
            "command_id": "build_approved_packaged_artifacts",
            "enabled_now": False,
            "exact_script_or_command_path": "scripts\\build_approved_packaged_artifacts.ps1",
            "exact_arguments": [],
            "allowed_working_directory": str(workspace),
            "timeout_seconds": 1800,
            "expected_output_paths": ["build\\staging\\"],
            "forbidden_output_paths": ["live\\", "dist\\", "backups\\"],
            "required_pre_verifiers": common_pre,
            "required_post_verifiers": common_post,
        },
    }


def get_approved_build_lane_contract(root: Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_root(root)
    path = workspace / "memory" / f"{APPROVED_BUILD_LANE_CONTRACT_ID}.json"
    if not path.exists():
        raise BuildPromoteSafetyError(f"approved build lane contract missing: {relative_path(workspace, path)}")
    contract = load_json_file(path)
    if contract.get("contract_id") != APPROVED_BUILD_LANE_CONTRACT_ID:
        raise BuildPromoteSafetyError("approved build lane contract_id mismatch")
    return contract


def get_approved_build_lane_allowlist(root: Path | None = None) -> dict[str, dict[str, Any]]:
    workspace = resolve_workspace_root(root)
    contract = get_approved_build_lane_contract(workspace)
    entries = contract.get("fixed_command_allowlist")
    if not isinstance(entries, list):
        raise BuildPromoteSafetyError("approved build lane allowlist missing")
    allowlist: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise BuildPromoteSafetyError("approved build lane allowlist entry is not an object")
        command_id = str(entry.get("command_id") or "")
        if not command_id:
            raise BuildPromoteSafetyError("approved build lane allowlist entry missing command_id")
        script_path = resolve_workspace_path(str(entry.get("exact_script_or_command_path") or ""), workspace, must_exist=False)
        if not relative_path(workspace, script_path).lower().startswith("scripts\\"):
            raise BuildPromoteSafetyError(f"approved build script must be under scripts\\: {command_id}")
        for output in as_string_list(entry.get("expected_output_paths")):
            resolved_output = resolve_workspace_path(output, workspace, must_exist=False)
            output_rel = relative_path(workspace, resolved_output).lower()
            if output_rel.startswith(("live\\", "dist\\", "backups\\")):
                raise BuildPromoteSafetyError(f"approved build output hits forbidden root: {output}")
        allowlist[command_id] = dict(entry)
    return allowlist


def get_timeout_lane_classification(root: Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_root(root)
    contract = workspace / "memory" / "ENGEL_VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_V1.json"
    verifier = workspace / "tools" / "verify_verifier_timeout_lane_classification_contract.py"
    return {
        "contract_present": contract.exists(),
        "verifier_present": verifier.exists(),
        "classification": "future_dependency_absent_preflight_only" if not contract.exists() else "available_for_future_policy",
        "quick_smoke_check": "not_run_by_preflight_v1",
        "standard_verifier_stack": "not_run_by_preflight_v1",
        "long_running_verifier_stack": "not_run_by_preflight_v1",
        "receipt_report_only_timeout_classification": True,
        "human_review_required": True,
    }


def get_build_promote_status(root: Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_root(root)
    return {
        "engine_id": ENGINE_ID,
        "module_present": True,
        "build_engine_enabled_now": ACTUAL_BUILD_ENABLED,
        "promote_engine_enabled_now": ACTUAL_PROMOTE_ENABLED,
        "actual_build_enabled": ACTUAL_BUILD_ENABLED,
        "actual_promote_enabled": ACTUAL_PROMOTE_ENABLED,
        "command_route_added_now": COMMAND_ROUTE_ADDED,
        "pyinstaller_enabled_now": PYINSTALLER_ENABLED,
        "live_write_enabled_now": LIVE_WRITE_ENABLED,
        "backup_write_enabled_now": BACKUP_WRITE_ENABLED,
        "lanes_available": [
            "build_preflight_only",
            "approved_graph_build",
            "promote_preflight_only",
            "approved_graph_promote",
        ],
        "lanes_disabled_future": [],
        "receipt_folders": {
            "build": str(workspace / BUILD_RECEIPT_DIR),
            "promote": str(workspace / PROMOTE_RECEIPT_DIR),
        },
        "safety_boundary": [
            "actual build allowed only through approved_graph_build",
            "actual promote allowed only through approved_graph_promote",
            "exact script allowlist only",
            "Global Password Gate required by route",
            "human_review_required remains true",
            "approved promote writes only declared live target and backup path",
            "no dist write",
            "no shell=True execution",
            "no git stage/commit",
            "no provider/network/model/local LLM",
            "no background/autorun/scheduler",
        ],
        "approved_build_lane_status": "available_with_gate_and_exact_allowlist",
        "approved_build_lane_v1_present": True,
        "approved_build_lane_no_execute_verifier_status": APPROVED_BUILD_LANE_NOT_IMPLEMENTED,
        "approved_promote_lane_status": "available_with_gate_and_declared_live_target_allowlist",
        "approved_promote_lane_v1_present": True,
    }


def ensure_receipt_dir(root: Path, folder: Path) -> Path:
    path = root / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json_and_md(root: Path, folder: Path, stem: str, payload: dict[str, Any], title: str) -> list[str]:
    receipt_dir = ensure_receipt_dir(root, folder)
    json_path = receipt_dir / f"{stem}.json"
    md_path = receipt_dir / f"{stem}.md"
    changed = [relative_path(root, json_path), relative_path(root, md_path)]
    payload["files_changed"] = changed
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_lines = [
        f"# {title}",
        "",
        f"- `receipt_id`: `{payload.get('receipt_id')}`",
        f"- `engine_id`: `{payload.get('engine_id')}`",
        f"- `lane_id`: `{payload.get('lane_id')}`",
        f"- `action_type`: `{payload.get('action_type')}`",
        f"- `final_status`: `{payload.get('final_status')}`",
        f"- `human_review_required`: `{payload.get('human_review_required')}`",
        "",
        "This is preflight-only evidence. No build, promote, PyInstaller, live/dist/build/backups write, git staging, or source mutation was performed.",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return changed


def build_receipt_payload(
    root: Path,
    receipt_id: str,
    started_at: str,
    ended_at: str,
    candidate_path: Path,
    candidate: dict[str, Any],
    validation: BuildCandidateValidationResult,
    hygiene: SelectiveFileHygieneResult,
    allowlist_result: dict[str, Any],
    timeout: dict[str, Any],
    final_status: str,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "engine_id": ENGINE_ID,
        "lane_id": "build_preflight_only",
        "action_type": "build_preflight_only",
        "started_at": started_at,
        "ended_at": ended_at,
        "input_build_candidate_path": relative_path(root, candidate_path),
        "candidate_id": validation.candidate_id,
        "candidate_hash": validation.candidate_hash,
        "source_node_state_id": validation.source_node_state_id,
        "target_node_state_id": validation.target_node_state_id,
        "edge_transition_id": validation.edge_transition_id,
        "edge_label": validation.edge_label,
        "approval_detected": False,
        "approval_phrase_name": "not_used",
        "password_gate_result": "not_required_for_preflight",
        "selective_file_list": as_string_list(candidate.get("selective_file_list")),
        "excluded_files": as_string_list(candidate.get("excluded_files")),
        "build_command_id": validation.build_command_id,
        "build_command_allowlist_result": allowlist_result,
        "pre_build_verifier_results": {"preflight_only": "not_run_by_v1"},
        "timeout_lane_classification": timeout,
        "build_outputs": [],
        "staged_artifact_paths": [],
        "staged_smoke_result": "not_run",
        "files_changed": [],
        "forbidden_actions_not_performed": FORBIDDEN_ACTIONS_NOT_PERFORMED,
        "final_status": final_status,
        "human_review_required": True,
        "validation_result": asdict(validation),
        "selective_file_hygiene_result": asdict(hygiene),
        "approved_build_execution_state": APPROVED_BUILD_DISABLED_REASON,
    }


def redact_password_gate_result(password_gate_result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(password_gate_result, dict):
        return {"ok": False, "reason": "missing_password_gate_result", "redacted": True}
    ok = bool(password_gate_result.get("ok") or password_gate_result.get("passed"))
    configured = bool(password_gate_result.get("configured", True))
    reason = str(password_gate_result.get("reason") or ("pass" if ok else "failed"))
    action_id = str(password_gate_result.get("action_id") or "approved_graph_build")
    return {
        "ok": ok,
        "configured": configured,
        "reason": reason,
        "action_id": action_id,
        "redacted": True,
    }


def run_gate_verifier(verifier_path: str, root: Path, timeout_seconds: int = 120) -> dict[str, Any]:
    resolved = resolve_workspace_path(verifier_path, root, must_exist=False)
    if not resolved.exists():
        return {
            "verifier": verifier_path,
            "status": "missing",
            "passed": False,
            "human_review_required": True,
        }
    started = monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, str(resolved)],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            shell=False,
        )
        elapsed = round(monotonic() - started, 3)
        return {
            "verifier": verifier_path,
            "status": "pass" if completed.returncode == 0 else "fail",
            "passed": completed.returncode == 0,
            "returncode": completed.returncode,
            "elapsed_seconds": elapsed,
            "stdout_tail": (completed.stdout or "")[-1200:],
            "stderr_tail": (completed.stderr or "")[-1200:],
            "human_review_required": True,
        }
    except subprocess.TimeoutExpired:
        elapsed = round(monotonic() - started, 3)
        return {
            "verifier": verifier_path,
            "status": "timeout",
            "passed": False,
            "elapsed_seconds": elapsed,
            "human_review_required": True,
        }


def run_approved_build_gate_verifiers(root: Path, verifier_paths: list[str]) -> dict[str, Any]:
    unique: list[str] = []
    for item in verifier_paths:
        if item not in unique:
            unique.append(item)
    results = [run_gate_verifier(item, root) for item in unique]
    return {
        "results": results,
        "passed": all(result.get("passed") is True for result in results),
        "human_review_required": True,
    }


def expected_staged_paths(root: Path, allowlist_entry: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    existing: list[str] = []
    missing: list[str] = []
    for item in as_string_list((allowlist_entry or {}).get("expected_output_paths")):
        resolved = resolve_workspace_path(item, root, must_exist=False)
        if item.endswith(("\\", "/")):
            if resolved.exists() and resolved.is_dir():
                existing.append(relative_path(root, resolved))
            else:
                missing.append(relative_path(root, resolved))
        elif resolved.exists() and resolved.is_file():
            existing.append(relative_path(root, resolved))
        else:
            missing.append(relative_path(root, resolved))
    return existing, missing


def run_exact_approved_build_script(root: Path, allowlist_entry: dict[str, Any]) -> dict[str, Any]:
    script_rel = str(allowlist_entry.get("exact_script_or_command_path") or "")
    script_path = resolve_workspace_path(script_rel, root, must_exist=True)
    if not relative_path(root, script_path).lower().startswith("scripts\\"):
        raise BuildPromoteSafetyError("approved build script must remain under scripts\\")
    if allowlist_entry.get("exact_arguments") not in ([], None):
        raise BuildPromoteSafetyError("approved build script exact_arguments must be empty")
    timeout_seconds = int(allowlist_entry.get("timeout_seconds_hard") or allowlist_entry.get("timeout_seconds_soft") or 3600)
    started = monotonic()
    try:
        completed = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            shell=False,
        )
        elapsed = round(monotonic() - started, 3)
        return {
            "status": "completed",
            "returncode": completed.returncode,
            "elapsed_seconds": elapsed,
            "stdout_tail": (completed.stdout or "")[-1200:],
            "stderr_tail": (completed.stderr or "")[-1200:],
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(monotonic() - started, 3)
        return {
            "status": "timeout",
            "returncode": None,
            "elapsed_seconds": elapsed,
            "stdout_tail": ((exc.stdout or "") if isinstance(exc.stdout, str) else "")[-1200:],
            "stderr_tail": ((exc.stderr or "") if isinstance(exc.stderr, str) else "")[-1200:],
            "timeout": True,
        }


def approved_build_lane_receipt_payload(
    root: Path,
    receipt_id: str,
    started_at: str,
    ended_at: str,
    candidate_path: Path,
    candidate: dict[str, Any],
    validation: BuildCandidateValidationResult,
    hygiene: SelectiveFileHygieneResult,
    allowlist_entry: dict[str, Any] | None,
    password_gate_result: dict[str, Any],
    timeout: dict[str, Any],
    final_status: str,
    cleanup_status: str,
    missing_script_paths: list[str],
    approval_detected: bool,
    blocker_reasons: list[str],
) -> dict[str, Any]:
    exact_script = str((allowlist_entry or {}).get("exact_script_or_command_path") or "")
    exact_arguments = (allowlist_entry or {}).get("exact_arguments") or []
    timeout_soft = (allowlist_entry or {}).get("timeout_seconds_soft")
    timeout_hard = (allowlist_entry or {}).get("timeout_seconds_hard")
    timeout_lane_id = (allowlist_entry or {}).get("timeout_lane_id")
    return {
        "receipt_id": receipt_id,
        "engine_id": ENGINE_ID,
        "lane_id": APPROVED_BUILD_LANE_ID,
        "action_type": APPROVED_BUILD_LANE_ID,
        "started_at": started_at,
        "ended_at": ended_at,
        "input_build_candidate_path": relative_path(root, candidate_path),
        "candidate_id": validation.candidate_id,
        "candidate_hash": validation.candidate_hash,
        "source_node_state_id": validation.source_node_state_id,
        "target_node_state_id": validation.target_node_state_id,
        "edge_transition_id": validation.edge_transition_id,
        "edge_label": validation.edge_label,
        "approval_detected": approval_detected,
        "approval_phrase_name": APPROVED_BUILD_APPROVAL_PHRASE,
        "password_gate_result": password_gate_result,
        "selective_file_list": as_string_list(candidate.get("selective_file_list")),
        "excluded_files": as_string_list(candidate.get("excluded_files")),
        "build_command_id": validation.build_command_id,
        "exact_script_or_command_path": exact_script,
        "exact_arguments": exact_arguments,
        "allowed_working_directory": str(root),
        "timeout_lane_id": timeout_lane_id,
        "timeout_seconds_soft": timeout_soft,
        "timeout_seconds_hard": timeout_hard,
        "elapsed_seconds": 0,
        "timeout_classification": "not_started_script_missing" if missing_script_paths else "not_started_v1_fail_closed",
        "pre_build_verifier_results": {"approved_build_lane_v1": "not_run_before_script_missing_block"},
        "post_build_verifier_results": {"approved_build_lane_v1": "not_run_no_build_attempt"},
        "build_command_allowlist_result": {
            "known_command_id": allowlist_entry is not None,
            "command_id": validation.build_command_id,
            "exact_script_or_command_path": exact_script,
            "actual_execution": "not_started",
        },
        "timeout_lane_classification": timeout,
        "missing_script_paths": missing_script_paths,
        "build_outputs": [],
        "staged_artifact_paths": [],
        "staged_smoke_result": "not_run",
        "files_changed": [],
        "forbidden_actions_not_performed": FORBIDDEN_ACTIONS_NOT_PERFORMED,
        "cleanup_status": cleanup_status,
        "final_status": final_status,
        "human_review_required": True,
        "validation_result": asdict(validation),
        "selective_file_hygiene_result": asdict(hygiene),
        "blocker_reasons": blocker_reasons,
        "implementation_note": (
            "Approved build lane V1 is bounded and fail-closed. It validates the graph "
            "candidate, allowlist, approval phrase, and redacted password-gate result, "
            "then stops before script execution when allowlisted scripts are missing. "
            "No subprocess, build, PyInstaller, promote, git, or live/dist/backups write occurred."
        ),
    }


def write_approved_build_lane_receipt(root: Path, receipt_id: str, payload: dict[str, Any]) -> list[str]:
    receipt_dir = ensure_receipt_dir(root, BUILD_RECEIPT_DIR)
    json_path = receipt_dir / f"{receipt_id}.json"
    md_path = receipt_dir / f"{receipt_id}.md"
    receipt_files = [relative_path(root, json_path), relative_path(root, md_path)]
    existing_changed = as_string_list(payload.get("files_changed"))
    payload["receipt_files_changed"] = receipt_files
    payload["files_changed"] = sorted(set(existing_changed + receipt_files))
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_lines = [
        "# De Bruijn Quantum Approved Build Lane Receipt",
        "",
        f"- `receipt_id`: `{payload.get('receipt_id')}`",
        f"- `engine_id`: `{payload.get('engine_id')}`",
        f"- `lane_id`: `{payload.get('lane_id')}`",
        f"- `action_type`: `{payload.get('action_type')}`",
        f"- `build_command_id`: `{payload.get('build_command_id')}`",
        f"- `final_status`: `{payload.get('final_status')}`",
        f"- `human_review_required`: `{payload.get('human_review_required')}`",
        "",
        "Approved build lane receipt. Human review is still required. No promote, live/dist/backups write, git staging, provider/model/network call, or trusted-memory write was performed.",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return as_string_list(payload.get("files_changed"))


def run_approved_graph_build(
    candidate_path: Path,
    root: Path | None = None,
    *,
    approval_phrase: str | None = None,
    password_gate_result: dict[str, Any] | None = None,
    execute_build: bool | None = None,
) -> ApprovedBuildLaneResult:
    workspace = resolve_workspace_root(root)
    started = utc_now()
    resolved_candidate = resolve_workspace_path(candidate_path, workspace, must_exist=True)
    candidate = load_build_candidate(resolved_candidate, workspace)
    validation = validate_build_candidate(resolved_candidate, workspace)
    hygiene = validate_selective_file_hygiene(candidate, workspace)
    allowlist = get_approved_build_lane_allowlist(workspace)
    allowlist_entry = allowlist.get(str(validation.build_command_id or ""))
    redacted_gate = redact_password_gate_result(password_gate_result)
    timeout = get_timeout_lane_classification(workspace)
    blockers: list[str] = []
    missing_scripts: list[str] = []
    final_status = APPROVED_BUILD_LANE_NOT_IMPLEMENTED
    pre_verifier_results: dict[str, Any] = {"status": "not_run"}
    post_verifier_results: dict[str, Any] = {"status": "not_run"}
    build_outputs: list[str] = []
    staged_artifact_paths: list[str] = []
    staged_smoke_result = "not_run"
    elapsed_seconds = 0.0
    timeout_classification = "not_started_v1_fail_closed"
    script_result: dict[str, Any] = {"status": "not_started"}
    allowed_to_execute = ACTUAL_BUILD_ENABLED if execute_build is None else bool(execute_build)

    if approval_phrase != APPROVED_BUILD_APPROVAL_PHRASE:
        blockers.append("exact approved build lane approval phrase required")
    if validation.blocker_reasons:
        blockers.extend(validation.blocker_reasons)
    if not validation.eligible_for_build_attempt:
        blockers.extend(validation.review_required_reasons)
    if hygiene.blocker_reasons:
        blockers.extend(hygiene.blocker_reasons)
    if allowlist_entry is None:
        blockers.append("build_command_id outside approved build lane allowlist")
    if not redacted_gate.get("ok"):
        blockers.append("Global Password Gate did not pass")
    if not timeout.get("contract_present") or not timeout.get("verifier_present"):
        blockers.append("timeout lane classification dependency missing")

    if blockers:
        if any("Password Gate" in item for item in blockers):
            final_status = APPROVED_BUILD_LANE_BLOCKED_PASSWORD_GATE
        elif allowlist_entry is None:
            final_status = APPROVED_BUILD_LANE_BLOCKED_OUTSIDE_ALLOWLIST
        elif not timeout.get("contract_present") or not timeout.get("verifier_present"):
            final_status = APPROVED_BUILD_LANE_BLOCKED_TIMEOUT_LANE_MISSING
        else:
            final_status = APPROVED_BUILD_LANE_BLOCKED_PRE_VERIFIER
    else:
        for entry in allowlist.values():
            script = resolve_workspace_path(str(entry.get("exact_script_or_command_path") or ""), workspace, must_exist=False)
            if not script.exists():
                missing_scripts.append(relative_path(workspace, script))
        if missing_scripts:
            final_status = APPROVED_BUILD_LANE_BLOCKED_SCRIPT_MISSING
        elif not allowed_to_execute:
            final_status = APPROVED_BUILD_LANE_NOT_IMPLEMENTED
            blockers.append("approved build execution disabled for this verifier/smoke call")
        elif not ACTUAL_BUILD_ENABLED or not PYINSTALLER_ENABLED:
            final_status = APPROVED_BUILD_LANE_NOT_IMPLEMENTED
            blockers.append("approved build execution is not enabled by engine flags")
        else:
            selected_pre_verifiers = [
                "tools\\verify_debruijn_quantum_approved_build_script_allowlist_contract.py",
                "tools\\verify_engel_global_password_gate.py",
            ]
            pre_verifier_results = run_approved_build_gate_verifiers(workspace, selected_pre_verifiers)
            if not pre_verifier_results.get("passed"):
                final_status = APPROVED_BUILD_LANE_BLOCKED_PRE_VERIFIER
                blockers.append("approved build pre-verifier subset failed")
            else:
                script_result = run_exact_approved_build_script(workspace, allowlist_entry)
                elapsed_seconds = float(script_result.get("elapsed_seconds") or 0.0)
                if script_result.get("timeout"):
                    final_status = APPROVED_BUILD_LANE_TIMEOUT_HARD_BLOCKED
                    timeout_classification = "hard_timeout_blocked"
                    blockers.append("approved build script exceeded hard timeout")
                elif int(script_result.get("returncode") or 0) != 0:
                    final_status = APPROVED_BUILD_LANE_SCRIPT_EXIT_NONZERO_REVIEW_REQUIRED
                    timeout_classification = "completed_nonzero_review_required"
                    blockers.append("approved build script exited nonzero")
                else:
                    existing_outputs, missing_outputs = expected_staged_paths(workspace, allowlist_entry)
                    build_outputs = existing_outputs
                    staged_artifact_paths = existing_outputs
                    if missing_outputs:
                        final_status = APPROVED_BUILD_LANE_STAGED_SMOKE_FAIL_REVIEW_REQUIRED
                        staged_smoke_result = "expected_outputs_missing"
                        timeout_classification = "completed_output_review_required"
                        blockers.append("approved build script completed but expected output paths were missing: " + ", ".join(missing_outputs))
                    else:
                        staged_smoke_result = "expected_outputs_present"
                        timeout_classification = "completed_with_expected_outputs_review_required"
                        post_verifier_results = run_approved_build_gate_verifiers(
                            workspace,
                            [
                                "tools\\verify_debruijn_quantum_approved_build_script_allowlist_contract.py",
                                "tools\\verify_engel_global_password_gate.py",
                            ],
                        )
                        if not post_verifier_results.get("passed"):
                            final_status = APPROVED_BUILD_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED
                            blockers.append("approved build post-verifier subset failed")
                        else:
                            final_status = APPROVED_BUILD_LANE_PASS_REVIEW_REQUIRED

    if not build_outputs and allowlist_entry and final_status not in {
        APPROVED_BUILD_LANE_BLOCKED_PRE_VERIFIER,
        APPROVED_BUILD_LANE_BLOCKED_PASSWORD_GATE,
        APPROVED_BUILD_LANE_BLOCKED_TIMEOUT_LANE_MISSING,
        APPROVED_BUILD_LANE_BLOCKED_OUTSIDE_ALLOWLIST,
        APPROVED_BUILD_LANE_BLOCKED_SCRIPT_MISSING,
        APPROVED_BUILD_LANE_NOT_IMPLEMENTED,
    }:
        existing_outputs, _missing_outputs = expected_staged_paths(workspace, allowlist_entry)
        build_outputs = existing_outputs
        staged_artifact_paths = existing_outputs

    forbidden_actions = (
        APPROVED_BUILD_FORBIDDEN_ACTIONS_NOT_PERFORMED
        if final_status
        in {
            APPROVED_BUILD_LANE_PASS_REVIEW_REQUIRED,
            APPROVED_BUILD_LANE_SCRIPT_EXIT_NONZERO_REVIEW_REQUIRED,
            APPROVED_BUILD_LANE_STAGED_SMOKE_FAIL_REVIEW_REQUIRED,
            APPROVED_BUILD_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED,
            APPROVED_BUILD_LANE_TIMEOUT_HARD_BLOCKED,
        }
        else FORBIDDEN_ACTIONS_NOT_PERFORMED
    )

    cleanup_status = (
        "completed_no_cleanup_required"
        if final_status
        in {
            APPROVED_BUILD_LANE_PASS_REVIEW_REQUIRED,
            APPROVED_BUILD_LANE_SCRIPT_EXIT_NONZERO_REVIEW_REQUIRED,
            APPROVED_BUILD_LANE_STAGED_SMOKE_FAIL_REVIEW_REQUIRED,
            APPROVED_BUILD_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED,
        }
        else "not_required_no_build_started"
    )
    if final_status == APPROVED_BUILD_LANE_TIMEOUT_HARD_BLOCKED:
        cleanup_status = "timeout_returned_control_to_engine"

    receipt_changed_files = list(build_outputs)
    receipt_changed_files.extend(staged_artifact_paths)

    ended = utc_now()
    receipt_id = f"debruijn_quantum_approved_build_lane_{timestamp_slug()}"
    payload = approved_build_lane_receipt_payload(
        workspace,
        receipt_id,
        started,
        ended,
        resolved_candidate,
        candidate,
        validation,
        hygiene,
        allowlist_entry,
        redacted_gate,
        timeout,
        final_status,
        cleanup_status,
        missing_scripts,
        approval_phrase == APPROVED_BUILD_APPROVAL_PHRASE,
        sorted(set(blockers)),
    )
    payload.update(
        {
            "elapsed_seconds": elapsed_seconds,
            "timeout_classification": timeout_classification,
            "pre_build_verifier_results": pre_verifier_results,
            "post_build_verifier_results": post_verifier_results,
            "build_outputs": build_outputs,
            "staged_artifact_paths": staged_artifact_paths,
            "staged_smoke_result": staged_smoke_result,
            "script_result": script_result,
            "files_changed": sorted(set(receipt_changed_files)),
            "forbidden_actions_not_performed": forbidden_actions,
            "implementation_note": (
                "Approved build lane may execute only the exact allowlisted script after approval, "
                "redacted password gate result, candidate validation, timeout dependency, and "
                "verifier subset pass. It never promotes and never writes live/dist/backups."
            )
        }
    )
    files_changed = write_approved_build_lane_receipt(workspace, receipt_id, payload)
    return ApprovedBuildLaneResult(
        receipt_id=receipt_id,
        engine_id=ENGINE_ID,
        lane_id=APPROVED_BUILD_LANE_ID,
        action_type=APPROVED_BUILD_LANE_ID,
        started_at=started,
        ended_at=ended,
        input_build_candidate_path=relative_path(workspace, resolved_candidate),
        candidate_id=validation.candidate_id,
        candidate_hash=validation.candidate_hash,
        build_command_id=validation.build_command_id,
        approval_detected=approval_phrase == APPROVED_BUILD_APPROVAL_PHRASE,
        approval_phrase_name=APPROVED_BUILD_APPROVAL_PHRASE,
        password_gate_result=redacted_gate,
        timeout_classification=str(payload.get("timeout_classification")),
        build_outputs=build_outputs,
        staged_artifact_paths=staged_artifact_paths,
        staged_smoke_result=staged_smoke_result,
        files_changed=files_changed,
        forbidden_actions_not_performed=forbidden_actions,
        cleanup_status=cleanup_status,
        final_status=final_status,
        human_review_required=True,
    )


def run_build_preflight_only(candidate_path: Path, root: Path | None = None) -> BuildPromotePreflightResult:
    workspace = resolve_workspace_root(root)
    started = utc_now()
    resolved_candidate = resolve_workspace_path(candidate_path, workspace, must_exist=True)
    candidate = load_build_candidate(resolved_candidate, workspace)
    validation = validate_build_candidate(resolved_candidate, workspace)
    hygiene = validate_selective_file_hygiene(candidate, workspace)
    allowlist = get_build_command_allowlist(workspace)
    known_command = validation.build_command_id in allowlist
    allowlist_result = {
        "known_command_id": known_command,
        "build_command_id": validation.build_command_id,
        "enabled_now": False,
        "actual_execution": "disabled",
        "reason": APPROVED_BUILD_DISABLED_REASON,
    }
    timeout = get_timeout_lane_classification(workspace)
    if validation.blocker_reasons or hygiene.blocker_reasons or not known_command:
        final_status = "BUILD_PREFLIGHT_BLOCKED"
    elif validation.review_required_reasons:
        final_status = "BUILD_PREFLIGHT_REVIEW_REQUIRED"
    else:
        final_status = "BUILD_PREFLIGHT_READY_BUILD_DISABLED"
    ended = utc_now()
    receipt_id = f"debruijn_quantum_build_preflight_{timestamp_slug()}"
    payload = build_receipt_payload(
        workspace,
        receipt_id,
        started,
        ended,
        resolved_candidate,
        candidate,
        validation,
        hygiene,
        allowlist_result,
        timeout,
        final_status,
    )
    stem = receipt_id
    files_changed = write_json_and_md(workspace, BUILD_RECEIPT_DIR, stem, payload, "De Bruijn Quantum Build Preflight Receipt")
    return BuildPromotePreflightResult(
        engine_id=ENGINE_ID,
        lane_id="build_preflight_only",
        action_type="build_preflight_only",
        started_at=started,
        ended_at=ended,
        input_candidate_path=relative_path(workspace, resolved_candidate),
        candidate_id=validation.candidate_id,
        candidate_hash=validation.candidate_hash,
        validation_result=asdict(validation),
        selective_file_hygiene_result=asdict(hygiene),
        build_command_allowlist_result=allowlist_result,
        timeout_lane_classification=timeout,
        files_read=[relative_path(workspace, resolved_candidate)],
        files_changed=files_changed,
        forbidden_actions_not_performed=FORBIDDEN_ACTIONS_NOT_PERFORMED,
        final_status=final_status,
        human_review_required=True,
    )


def promote_receipt_payload(
    root: Path,
    receipt_id: str,
    started_at: str,
    ended_at: str,
    build_receipt_path: Path,
    build_receipt: dict[str, Any],
    timeout: dict[str, Any],
    final_status: str,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "engine_id": ENGINE_ID,
        "lane_id": "promote_preflight_only",
        "action_type": "promote_preflight_only",
        "started_at": started_at,
        "ended_at": ended_at,
        "input_build_receipt_path": relative_path(root, build_receipt_path),
        "approval_detected": False,
        "approval_phrase_name": "not_used",
        "password_gate_result": "not_required_for_preflight",
        "backup_paths": [],
        "promoted_artifact_paths": [],
        "live_smoke_result": "not_run",
        "final_verifier_results": {"preflight_only": "not_run_by_v1"},
        "timeout_lane_classification": timeout,
        "files_changed": [],
        "forbidden_actions_not_performed": FORBIDDEN_ACTIONS_NOT_PERFORMED,
        "final_status": final_status,
        "human_review_required": True,
        "source_build_receipt_final_status": build_receipt.get("final_status"),
    }


def run_promote_preflight_only(build_receipt_path: Path, root: Path | None = None) -> BuildPromotePreflightResult:
    workspace = resolve_workspace_root(root)
    started = utc_now()
    resolved_receipt = resolve_workspace_path(build_receipt_path, workspace, must_exist=True)
    if resolved_receipt.suffix.lower() != ".json":
        raise BuildPromoteSafetyError("promote preflight accepts JSON build receipt only")
    build_receipt = load_json_file(resolved_receipt)
    blockers = []
    if build_receipt.get("engine_id") != ENGINE_ID:
        blockers.append("build receipt engine_id mismatch")
    if not str(build_receipt.get("action_type", "")).endswith("preflight_only"):
        blockers.append("V1 promote preflight expects preflight-only build receipt evidence")
    timeout = get_timeout_lane_classification(workspace)
    final_status = "PROMOTE_PREFLIGHT_BLOCKED" if blockers else "PROMOTE_PREFLIGHT_REVIEW_REQUIRED"
    ended = utc_now()
    receipt_id = f"debruijn_quantum_promote_preflight_{timestamp_slug()}"
    payload = promote_receipt_payload(
        workspace,
        receipt_id,
        started,
        ended,
        resolved_receipt,
        build_receipt,
        timeout,
        final_status,
    )
    if blockers:
        payload["blocker_reasons"] = blockers
    files_changed = write_json_and_md(workspace, PROMOTE_RECEIPT_DIR, receipt_id, payload, "De Bruijn Quantum Promote Preflight Receipt")
    return BuildPromotePreflightResult(
        engine_id=ENGINE_ID,
        lane_id="promote_preflight_only",
        action_type="promote_preflight_only",
        started_at=started,
        ended_at=ended,
        input_candidate_path=relative_path(workspace, resolved_receipt),
        candidate_id=str(build_receipt.get("candidate_id") or "unknown"),
        candidate_hash=str(build_receipt.get("candidate_hash") or ""),
        validation_result={"build_receipt_valid": not blockers, "blocker_reasons": blockers},
        selective_file_hygiene_result={},
        build_command_allowlist_result={"actual_execution": "disabled", "reason": "PROMOTE_EXECUTION_NOT_IMPLEMENTED"},
        timeout_lane_classification=timeout,
        files_read=[relative_path(workspace, resolved_receipt)],
        files_changed=files_changed,
        forbidden_actions_not_performed=FORBIDDEN_ACTIONS_NOT_PERFORMED,
        final_status=final_status,
        human_review_required=True,
    )


@dataclass
class ApprovedPromoteLaneResult:
    receipt_id: str
    engine_id: str
    lane_id: str
    action_type: str
    started_at: str
    ended_at: str
    input_build_receipt_path: str
    build_receipt_engine_id: str
    build_receipt_final_status: str
    build_command_id: str | None
    candidate_id: str
    candidate_hash: str
    source_node_state_id: str
    target_node_state_id: str
    edge_transition_id: str
    edge_label: str
    approval_detected: bool
    approval_phrase_name: str
    password_gate_result: dict[str, Any]
    expected_staged_artifact_paths: list[str]
    actual_staged_artifact_paths: list[str]
    live_target_path: str
    backup_target_path: str
    backup_paths: list[str]
    backup_hash_manifest: dict[str, str]
    promoted_artifact_paths: list[str]
    live_smoke_command_id: str
    live_smoke_result: str
    timeout_lane_id: str
    timeout_seconds_soft: int
    timeout_seconds_hard: int
    elapsed_seconds: float
    timeout_classification: str
    pre_promote_verifier_results: dict[str, Any]
    post_promote_verifier_results: dict[str, Any]
    rollback_note: str
    files_changed: list[str]
    forbidden_actions_not_performed: list[str]
    cleanup_status: str
    final_status: str
    human_review_required: bool


def get_approved_promote_lane_contract(root: Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_root(root)
    path = workspace / "memory" / f"{APPROVED_PROMOTE_LANE_CONTRACT_ID}.json"
    if not path.exists():
        raise BuildPromoteSafetyError(f"approved promote lane contract missing: {relative_path(workspace, path)}")
    contract = load_json_file(path)
    if contract.get("contract_id") != APPROVED_PROMOTE_LANE_CONTRACT_ID:
        raise BuildPromoteSafetyError("approved promote lane contract_id mismatch")
    return contract


def get_approved_promote_lane_allowlist(root: Path | None = None) -> dict[str, dict[str, Any]]:
    workspace = resolve_workspace_root(root)
    contract = get_approved_promote_lane_contract(workspace)
    entries = contract.get("live_target_allowlist")
    if not isinstance(entries, list):
        raise BuildPromoteSafetyError("approved promote lane allowlist missing")
    allowlist: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise BuildPromoteSafetyError("approved promote lane allowlist entry is not an object")
        command_id = str(entry.get("build_command_id") or "")
        if not command_id:
            raise BuildPromoteSafetyError("approved promote lane allowlist entry missing build_command_id")
        live_target = str(entry.get("live_target_path") or "").lower()
        if not live_target.startswith("live\\"):
            raise BuildPromoteSafetyError(f"promote live_target_path must be under live\\: {command_id}")
        backup_target = str(entry.get("backup_target_path") or "").lower()
        if not backup_target.startswith("backups\\"):
            raise BuildPromoteSafetyError(f"promote backup_target_path must be under backups\\: {command_id}")
        allowlist[command_id] = dict(entry)
    return allowlist


def write_approved_promote_lane_receipt(root: Path, receipt_id: str, payload: dict[str, Any]) -> list[str]:
    receipt_dir = ensure_receipt_dir(root, PROMOTE_RECEIPT_DIR)
    json_path = receipt_dir / f"{receipt_id}.json"
    md_path = receipt_dir / f"{receipt_id}.md"
    receipt_files = [relative_path(root, json_path), relative_path(root, md_path)]
    existing_changed = as_string_list(payload.get("files_changed"))
    payload["receipt_files_changed"] = receipt_files
    payload["files_changed"] = sorted(set(existing_changed + receipt_files))
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_lines = [
        "# De Bruijn Quantum Approved Promote Lane Receipt",
        "",
        f"- `receipt_id`: `{payload.get('receipt_id')}`",
        f"- `engine_id`: `{payload.get('engine_id')}`",
        f"- `lane_id`: `{payload.get('lane_id')}`",
        f"- `action_type`: `{payload.get('action_type')}`",
        f"- `final_status`: `{payload.get('final_status')}`",
        f"- `build_command_id`: `{payload.get('build_command_id')}`",
        f"- `live_target_path`: `{payload.get('live_target_path')}`",
        f"- `backup_target_path`: `{payload.get('backup_target_path')}`",
        f"- `live_smoke_result`: `{payload.get('live_smoke_result')}`",
        f"- `timeout_classification`: `{payload.get('timeout_classification')}`",
        f"- `human_review_required`: `{payload.get('human_review_required')}`",
        "",
        "Approved promote lane receipt. Human review is still required. The lane never runs a build or PyInstaller, never writes dist, never stages or commits, and never writes trusted memory.",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return as_string_list(payload.get("files_changed"))


def timestamped_allowlist_path(path_text: str, stamp: str) -> str:
    return str(path_text or "").replace("<timestamp>", stamp)


def validate_promote_target(root: Path, path_text: str, required_prefix: str) -> Path:
    normalized = normalize_rel(timestamped_allowlist_path(path_text, timestamp_slug()))
    prefix = normalize_rel(required_prefix)
    if not (normalized == prefix.rstrip("\\") or normalized.startswith(prefix.rstrip("\\") + "\\")):
        raise BuildPromoteSafetyError(f"promote target must stay under {required_prefix}: {path_text}")
    return resolve_workspace_path(path_text, root, must_exist=False)


def validate_promote_artifact_smoke(staged: Path, live: Path) -> dict[str, Any]:
    if not staged.exists() or not staged.is_file():
        return {"passed": False, "status": "staged_artifact_missing"}
    if not live.exists() or not live.is_file():
        return {"passed": False, "status": "live_artifact_missing"}
    staged_hash = sha256_file(staged)
    live_hash = sha256_file(live)
    with live.open("rb") as handle:
        signature = handle.read(2)
    pe_header_ok = signature == b"MZ"
    return {
        "passed": staged_hash == live_hash and pe_header_ok,
        "status": "live_hash_matches_staged_and_pe_header_ok" if staged_hash == live_hash and pe_header_ok else "live_smoke_failed",
        "staged_sha256": staged_hash,
        "live_sha256": live_hash,
        "pe_header_ok": pe_header_ok,
    }


def run_promote_verifier_subset(root: Path, verifier_paths: list[str]) -> dict[str, Any]:
    return run_approved_build_gate_verifiers(root, verifier_paths)


def run_approved_graph_promote(
    build_receipt_path: Path,
    root: Path | None = None,
    *,
    approval_phrase: str | None = None,
    password_gate_result: dict[str, Any] | None = None,
) -> ApprovedPromoteLaneResult:
    workspace = resolve_workspace_root(root)
    started = utc_now()
    resolved_receipt = resolve_workspace_path(build_receipt_path, workspace, must_exist=True)
    if resolved_receipt.suffix.lower() != ".json":
        raise BuildPromoteSafetyError("approved promote lane accepts JSON build receipt only")
    receipt_rel = relative_path(workspace, resolved_receipt).lower()
    if not receipt_rel.startswith("reports\\debruijn_quantum_build_receipts\\"):
        raise BuildPromoteSafetyError(
            "approved promote lane requires a build receipt under reports\\debruijn_quantum_build_receipts\\"
        )
    build_receipt = load_json_file(resolved_receipt)
    redacted_gate = redact_password_gate_result(password_gate_result)
    timeout = get_timeout_lane_classification(workspace)
    blockers: list[str] = []
    missing_staged: list[str] = []
    allowlist_entry: dict[str, Any] | None = None
    final_status = APPROVED_PROMOTE_LANE_NOT_IMPLEMENTED
    promote_stamp = timestamp_slug()
    backup_paths: list[str] = []
    backup_hash_manifest: dict[str, str] = {}
    promoted_artifact_paths: list[str] = []
    live_smoke_result = "not_run"
    live_smoke_details: dict[str, Any] = {}
    pre_promote_verifier_results: dict[str, Any] = {"status": "not_run"}
    post_promote_verifier_results: dict[str, Any] = {"status": "not_run"}
    promote_files_changed: list[str] = []
    elapsed_seconds = 0.0
    timeout_classification = "not_started"
    rollback_note = "no live or backup write attempted; no rollback required"
    cleanup_status = "not_started"

    build_engine_id = str(build_receipt.get("engine_id") or "")
    build_final = str(build_receipt.get("final_status") or "")
    build_command_id = str(build_receipt.get("build_command_id") or "") or None
    candidate_id = str(build_receipt.get("candidate_id") or "")
    candidate_hash = str(build_receipt.get("candidate_hash") or "")
    source_node = str(build_receipt.get("source_node_state_id") or "")
    target_node = str(build_receipt.get("target_node_state_id") or "")
    edge_transition_id = str(build_receipt.get("edge_transition_id") or "")
    edge_label = str(build_receipt.get("edge_label") or "")

    if approval_phrase != APPROVED_PROMOTE_APPROVAL_PHRASE:
        blockers.append("exact approved promote lane approval phrase required")
    if build_engine_id != ENGINE_ID:
        blockers.append("build_receipt engine_id does not match approved build lane engine")
    if build_final != APPROVED_BUILD_LANE_PASS_REVIEW_REQUIRED:
        blockers.append("build_receipt final_status must be BUILD_LANE_PASS_REVIEW_REQUIRED before promote")
    if build_receipt.get("human_review_required") is not True:
        blockers.append("build_receipt human_review_required must be true")
    try:
        allowlist = get_approved_promote_lane_allowlist(workspace)
    except BuildPromoteSafetyError as exc:
        allowlist = {}
        blockers.append(str(exc))
    if build_command_id and build_command_id in allowlist:
        allowlist_entry = allowlist[build_command_id]
    else:
        blockers.append("build_command_id outside approved promote lane allowlist")
    if not redacted_gate.get("ok"):
        blockers.append("Global Password Gate did not pass")
    if not timeout.get("contract_present") or not timeout.get("verifier_present"):
        blockers.append("timeout lane classification dependency missing")

    expected_staged: list[str] = []
    actual_staged: list[str] = []
    live_target_path = ""
    backup_target_path = ""
    live_smoke_command_id = ""
    timeout_lane_id = "report_only_timeout_classification"
    timeout_seconds_soft = 0
    timeout_seconds_hard = 0
    if allowlist_entry is not None:
        expected_staged = as_string_list(allowlist_entry.get("expected_staged_artifact_paths"))
        live_target_path = str(allowlist_entry.get("live_target_path") or "")
        backup_target_path = timestamped_allowlist_path(str(allowlist_entry.get("backup_target_path") or ""), promote_stamp)
        live_smoke_command_id = str(allowlist_entry.get("live_smoke_command_id") or "")
        timeout_lane_id = str(allowlist_entry.get("timeout_lane_id") or timeout_lane_id)
        timeout_seconds_soft = int(allowlist_entry.get("timeout_seconds_soft") or 0)
        timeout_seconds_hard = int(allowlist_entry.get("timeout_seconds_hard") or 0)
        receipt_staged = as_string_list(build_receipt.get("staged_artifact_paths"))
        normalized_expected = sorted(normalize_rel(item) for item in expected_staged)
        normalized_receipt = sorted(normalize_rel(item) for item in receipt_staged)
        if normalized_receipt != normalized_expected:
            blockers.append("build_receipt staged_artifact_paths do not match promote allowlist")
        for path_str in expected_staged:
            resolved = resolve_workspace_path(path_str, workspace, must_exist=False)
            if not resolved.exists():
                missing_staged.append(relative_path(workspace, resolved))
            elif not resolved.is_file():
                blockers.append("V1 approved promote supports file artifacts only: " + relative_path(workspace, resolved))
            else:
                actual_staged.append(relative_path(workspace, resolved))

    if blockers and any("Password Gate" in item for item in blockers):
        final_status = APPROVED_PROMOTE_LANE_BLOCKED_PASSWORD_GATE
    elif blockers and any("allowlist" in item for item in blockers):
        final_status = APPROVED_PROMOTE_LANE_BLOCKED_OUTSIDE_ALLOWLIST
    elif blockers and (not timeout.get("contract_present") or not timeout.get("verifier_present")):
        final_status = APPROVED_PROMOTE_LANE_BLOCKED_TIMEOUT_LANE_MISSING
    elif blockers and any("engine_id" in item or "build_receipt" in item for item in blockers):
        final_status = APPROVED_PROMOTE_LANE_BLOCKED_BUILD_RECEIPT_INVALID
    elif blockers:
        final_status = APPROVED_PROMOTE_LANE_BLOCKED_PRE_VERIFIER
    elif missing_staged:
        final_status = APPROVED_PROMOTE_LANE_BLOCKED_STAGED_ARTIFACT_MISSING
    elif not ACTUAL_PROMOTE_ENABLED or not LIVE_WRITE_ENABLED or not BACKUP_WRITE_ENABLED:
        final_status = APPROVED_PROMOTE_LANE_NOT_IMPLEMENTED
        blockers.append("approved promote execution is disabled by engine flags")
    else:
        promote_started = monotonic()
        pre_promote_verifier_results = run_promote_verifier_subset(
            workspace,
            [
                "tools\\verify_debruijn_quantum_approved_build_script_allowlist_contract.py",
                "tools\\verify_engel_global_password_gate.py",
            ],
        )
        if not pre_promote_verifier_results.get("passed"):
            final_status = APPROVED_PROMOTE_LANE_BLOCKED_PRE_VERIFIER
            blockers.append("approved promote pre-verifier subset failed")
        else:
            try:
                if len(actual_staged) != 1:
                    raise BuildPromoteSafetyError("approved promote V1 requires exactly one staged file artifact")
                staged_path = resolve_workspace_path(actual_staged[0], workspace, must_exist=True)
                live_path = resolve_workspace_path(live_target_path, workspace, must_exist=False)
                backup_path = resolve_workspace_path(backup_target_path, workspace, must_exist=False)
                live_rel = normalize_rel(relative_path(workspace, live_path))
                backup_rel = normalize_rel(relative_path(workspace, backup_path))
                if not (live_rel == "live" or live_rel.startswith("live\\")):
                    raise BuildPromoteSafetyError("live target must remain under live\\")
                if not (backup_rel == "backups" or backup_rel.startswith("backups\\")):
                    raise BuildPromoteSafetyError("backup target must remain under backups\\")
                if live_path.exists():
                    if not live_path.is_file():
                        raise BuildPromoteSafetyError("existing live target is not a file")
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(live_path, backup_path)
                    backup_rel_text = relative_path(workspace, backup_path)
                    backup_paths.append(backup_rel_text)
                    backup_hash_manifest[backup_rel_text] = sha256_file(backup_path)
                    promote_files_changed.append(backup_rel_text)
                    if sha256_file(live_path) != sha256_file(backup_path):
                        raise BuildPromoteSafetyError("backup hash mismatch after copy")
                live_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged_path, live_path)
                promoted_rel = relative_path(workspace, live_path)
                promoted_artifact_paths.append(promoted_rel)
                promote_files_changed.append(promoted_rel)
                live_smoke_details = validate_promote_artifact_smoke(staged_path, live_path)
                live_smoke_result = str(live_smoke_details.get("status") or "not_run")
                if not live_smoke_details.get("passed"):
                    final_status = APPROVED_PROMOTE_LANE_LIVE_SMOKE_FAIL_REVIEW_REQUIRED
                    blockers.append("approved promote live smoke failed")
                else:
                    post_promote_verifier_results = run_promote_verifier_subset(
                        workspace,
                        [
                            "tools\\verify_debruijn_quantum_approved_build_script_allowlist_contract.py",
                            "tools\\verify_engel_global_password_gate.py",
                        ],
                    )
                    if not post_promote_verifier_results.get("passed"):
                        final_status = APPROVED_PROMOTE_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED
                        blockers.append("approved promote post-verifier subset failed")
                    else:
                        final_status = APPROVED_PROMOTE_LANE_PASS_REVIEW_REQUIRED
                timeout_classification = (
                    "completed_live_hash_matches_staged_review_required"
                    if final_status == APPROVED_PROMOTE_LANE_PASS_REVIEW_REQUIRED
                    else "completed_promote_review_required"
                )
                rollback_note = (
                    "restore the backup artifact to the live target if rollback is explicitly approved"
                    if backup_paths
                    else "no prior live artifact existed; remove the promoted live artifact if rollback is explicitly approved"
                )
                cleanup_status = "completed_no_cleanup_required"
            except Exception as exc:
                final_status = APPROVED_PROMOTE_LANE_BLOCKED_BACKUP_FAILED
                blockers.append("approved promote backup/live copy failed: " + type(exc).__name__ + ": " + str(exc))
                cleanup_status = "blocked_before_or_during_promote"
                rollback_note = "manual review required; evidence and any created backup/live files were left in place"
        elapsed_seconds = round(monotonic() - promote_started, 3)

    ended = utc_now()
    receipt_id = f"debruijn_quantum_approved_promote_lane_{promote_stamp}"
    payload: dict[str, Any] = {
        "receipt_id": receipt_id,
        "engine_id": ENGINE_ID,
        "lane_id": APPROVED_PROMOTE_LANE_ID,
        "action_type": APPROVED_PROMOTE_LANE_ID,
        "started_at": started,
        "ended_at": ended,
        "input_build_receipt_path": relative_path(workspace, resolved_receipt),
        "build_receipt_engine_id": build_engine_id,
        "build_receipt_final_status": build_final,
        "build_command_id": build_command_id,
        "candidate_id": candidate_id,
        "candidate_hash": candidate_hash,
        "source_node_state_id": source_node,
        "target_node_state_id": target_node,
        "edge_transition_id": edge_transition_id,
        "edge_label": edge_label,
        "approval_detected": approval_phrase == APPROVED_PROMOTE_APPROVAL_PHRASE,
        "approval_phrase_name": APPROVED_PROMOTE_APPROVAL_PHRASE,
        "password_gate_result": redacted_gate,
        "expected_staged_artifact_paths": expected_staged,
        "actual_staged_artifact_paths": actual_staged,
        "missing_staged_artifact_paths": missing_staged,
        "live_target_path": live_target_path,
        "backup_target_path": backup_target_path,
        "backup_paths": backup_paths,
        "backup_hash_manifest": backup_hash_manifest,
        "promoted_artifact_paths": promoted_artifact_paths,
        "live_smoke_command_id": live_smoke_command_id,
        "live_smoke_result": live_smoke_result,
        "live_smoke_details": live_smoke_details,
        "timeout_lane_id": timeout_lane_id,
        "timeout_seconds_soft": timeout_seconds_soft,
        "timeout_seconds_hard": timeout_seconds_hard,
        "elapsed_seconds": elapsed_seconds,
        "timeout_classification": timeout_classification,
        "pre_promote_verifier_results": pre_promote_verifier_results,
        "post_promote_verifier_results": post_promote_verifier_results,
        "rollback_note": rollback_note,
        "files_changed": sorted(set(promote_files_changed)),
        "forbidden_actions_not_performed": APPROVED_PROMOTE_FORBIDDEN_ACTIONS_NOT_PERFORMED,
        "cleanup_status": cleanup_status,
        "final_status": final_status,
        "human_review_required": True,
        "blocker_reasons": sorted(set(blockers)),
    }
    files_changed = write_approved_promote_lane_receipt(workspace, receipt_id, payload)
    return ApprovedPromoteLaneResult(
        receipt_id=receipt_id,
        engine_id=ENGINE_ID,
        lane_id=APPROVED_PROMOTE_LANE_ID,
        action_type=APPROVED_PROMOTE_LANE_ID,
        started_at=started,
        ended_at=ended,
        input_build_receipt_path=relative_path(workspace, resolved_receipt),
        build_receipt_engine_id=build_engine_id,
        build_receipt_final_status=build_final,
        build_command_id=build_command_id,
        candidate_id=candidate_id,
        candidate_hash=candidate_hash,
        source_node_state_id=source_node,
        target_node_state_id=target_node,
        edge_transition_id=edge_transition_id,
        edge_label=edge_label,
        approval_detected=payload["approval_detected"],
        approval_phrase_name=APPROVED_PROMOTE_APPROVAL_PHRASE,
        password_gate_result=redacted_gate,
        expected_staged_artifact_paths=expected_staged,
        actual_staged_artifact_paths=actual_staged,
        live_target_path=live_target_path,
        backup_target_path=backup_target_path,
        backup_paths=backup_paths,
        backup_hash_manifest=backup_hash_manifest,
        promoted_artifact_paths=promoted_artifact_paths,
        live_smoke_command_id=live_smoke_command_id,
        live_smoke_result=live_smoke_result,
        timeout_lane_id=timeout_lane_id,
        timeout_seconds_soft=timeout_seconds_soft,
        timeout_seconds_hard=timeout_seconds_hard,
        elapsed_seconds=elapsed_seconds,
        timeout_classification=timeout_classification,
        pre_promote_verifier_results=pre_promote_verifier_results,
        post_promote_verifier_results=post_promote_verifier_results,
        rollback_note=rollback_note,
        files_changed=files_changed,
        forbidden_actions_not_performed=APPROVED_PROMOTE_FORBIDDEN_ACTIONS_NOT_PERFORMED,
        cleanup_status=cleanup_status,
        final_status=final_status,
        human_review_required=True,
    )


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="De Bruijn Quantum Build/Promote preflight-only helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    build_parser = sub.add_parser("build-preflight")
    build_parser.add_argument("candidate_path")
    promote_parser = sub.add_parser("promote-preflight")
    promote_parser.add_argument("build_receipt_path")
    args = parser.parse_args(argv)
    root = resolve_workspace_root(DEFAULT_ROOT)

    try:
        if args.command == "status":
            print_json(get_build_promote_status(root))
            return 0
        if args.command == "build-preflight":
            result = run_build_preflight_only(Path(args.candidate_path), root)
            print_json(asdict(result))
            return 0
        if args.command == "promote-preflight":
            result = run_promote_preflight_only(Path(args.build_receipt_path), root)
            print_json(asdict(result))
            return 0
    except BuildPromoteSafetyError as exc:
        print_json({"error": str(exc), "final_status": "REJECTED", "human_review_required": True})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
