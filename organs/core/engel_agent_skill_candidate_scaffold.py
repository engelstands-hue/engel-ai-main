#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "reports" / "agent_skill_candidates"
DEFAULT_RECEIPT_ROOT = PROJECT_ROOT / "reports" / "codex_bridge"
APPROVED_STORAGE_ROOTS = (DEFAULT_STORAGE_ROOT,)

CANDIDATE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

REQUIRED_VERIFIERS = [
    "python .\\tools\\verify_agent_skill_candidate_scaffold.py",
    "python .\\tools\\verify_agent_skill_candidate_pipeline.py",
]

COMMON_FALSE_DEFAULTS = {
    "runtime_enabled": False,
    "autorun_enabled": False,
    "trusted_memory_write_allowed": False,
    "source_mutation_allowed": False,
    "route_mutation_allowed": False,
    "queue_mutation_allowed": False,
    "network_allowed": False,
    "provider_api_allowed": False,
    "package_install_allowed": False,
    "mobile_runtime_allowed": False,
    "remote_queen_runtime_allowed": False,
}

COMMON_TRUE_DEFAULTS = {
    "required_human_review": True,
    "approval_required_for_inactive_registry": True,
    "activation_contract_required": True,
    "receipt_required": True,
}

FORBIDDEN_ACTIONS_DEFAULT = [
    "run automatically",
    "self-activate",
    "self-register as live",
    "write trusted memory",
    "promote candidate memory",
    "mutate source",
    "mutate routes",
    "mutate queues",
    "install packages",
    "call providers or network",
    "run local LLM inference",
    "start model servers",
    "enable Mobile runtime",
    "enable Remote Queen runtime",
    "create live agents or live skills",
    "bypass Global Password Gate",
    "bypass approval tokens",
    "bypass verifiers",
]

AGENT_REQUIRED_FIELDS = [
    "candidate_id",
    "candidate_type",
    "name",
    "purpose",
    "description",
    "owner",
    "created_by",
    "created_at",
    "status",
    "trust_status",
    "allowed_inputs",
    "allowed_outputs",
    "allowed_context",
    "forbidden_context",
    "allowed_actions",
    "forbidden_actions",
    "allowed_files",
    "forbidden_files",
    "required_verifiers",
    "required_human_review",
    "external_ai_lanes_requested",
    "collaboration_room_allowed",
    "runtime_enabled",
    "autorun_enabled",
    "trusted_memory_write_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "network_allowed",
    "provider_api_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
    "approval_required_for_inactive_registry",
    "activation_contract_required",
    "receipt_required",
]

SKILL_REQUIRED_FIELDS = [
    "candidate_id",
    "candidate_type",
    "skill_name",
    "description",
    "trigger_conditions",
    "input_schema",
    "output_schema",
    "owner",
    "created_by",
    "created_at",
    "status",
    "trust_status",
    "allowed_files",
    "forbidden_files",
    "allowed_actions",
    "forbidden_actions",
    "required_verifiers",
    "required_human_review",
    "external_ai_lanes_requested",
    "install_enabled",
    "runtime_enabled",
    "autorun_enabled",
    "trusted_memory_write_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "network_allowed",
    "provider_api_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
    "approval_required_for_inactive_registry",
    "activation_contract_required",
    "receipt_required",
]


class CandidateScaffoldError(ValueError):
    pass


def validate_candidate_id(candidate_id: str) -> str:
    if not isinstance(candidate_id, str):
        raise CandidateScaffoldError("candidate_id must be a string")
    if not CANDIDATE_ID_RE.fullmatch(candidate_id):
        raise CandidateScaffoldError(
            "candidate_id must use only letters, numbers, underscore, or hyphen and be 1-80 characters"
        )
    if ".." in candidate_id or "/" in candidate_id or "\\" in candidate_id:
        raise CandidateScaffoldError("candidate_id must not contain path traversal or separators")
    return candidate_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise CandidateScaffoldError(f"{field} must be a list")
    return [str(item) for item in value]


def _as_mapping(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CandidateScaffoldError(f"{field} must be an object")
    return dict(value)


def _resolve(path: Path) -> Path:
    return path.resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        _resolve(path).relative_to(_resolve(root))
        return True
    except ValueError:
        return False


def _project_relative(path: Path) -> str:
    try:
        return str(_resolve(path).relative_to(_resolve(PROJECT_ROOT))).replace("/", "\\")
    except ValueError:
        return str(path)


def _ensure_inside_project(path: Path, label: str) -> Path:
    resolved = _resolve(path)
    if not _is_relative_to(resolved, PROJECT_ROOT):
        raise CandidateScaffoldError(f"{label} must stay inside {PROJECT_ROOT}")
    return resolved


def _ensure_approved_storage(storage_root: Path, approved_roots: tuple[Path, ...]) -> Path:
    resolved_root = _ensure_inside_project(storage_root, "storage_root")
    if not any(resolved_root == _resolve(root) or _is_relative_to(resolved_root, root) for root in approved_roots):
        allowed = ", ".join(_project_relative(root) for root in approved_roots)
        raise CandidateScaffoldError(f"storage_root must be inside approved candidate storage: {allowed}")
    return resolved_root


def build_agent_candidate(
    *,
    candidate_id: str,
    name: str,
    purpose: str,
    description: str = "",
    owner: str = "Josh",
    created_by: str = "Engel",
    created_at: str | None = None,
    allowed_inputs: list[str] | None = None,
    allowed_outputs: list[str] | None = None,
    allowed_context: list[str] | None = None,
    forbidden_context: list[str] | None = None,
    allowed_actions: list[str] | None = None,
    forbidden_actions: list[str] | None = None,
    allowed_files: list[str] | None = None,
    forbidden_files: list[str] | None = None,
    required_verifiers: list[str] | None = None,
    external_ai_lanes_requested: list[str] | None = None,
) -> dict[str, Any]:
    candidate_id = validate_candidate_id(candidate_id)
    candidate = {
        "candidate_id": candidate_id,
        "candidate_type": "agent",
        "name": str(name),
        "purpose": str(purpose),
        "description": str(description),
        "owner": str(owner),
        "created_by": str(created_by),
        "created_at": str(created_at or _utc_now()),
        "status": "candidate_only",
        "trust_status": "untrusted_candidate",
        "allowed_inputs": _as_list(allowed_inputs, "allowed_inputs"),
        "allowed_outputs": _as_list(allowed_outputs, "allowed_outputs"),
        "allowed_context": _as_list(allowed_context, "allowed_context"),
        "forbidden_context": _as_list(forbidden_context, "forbidden_context"),
        "allowed_actions": _as_list(allowed_actions, "allowed_actions"),
        "forbidden_actions": _as_list(forbidden_actions, "forbidden_actions") or list(FORBIDDEN_ACTIONS_DEFAULT),
        "allowed_files": _as_list(allowed_files, "allowed_files"),
        "forbidden_files": _as_list(forbidden_files, "forbidden_files"),
        "required_verifiers": _as_list(required_verifiers, "required_verifiers") or list(REQUIRED_VERIFIERS),
        "external_ai_lanes_requested": _as_list(external_ai_lanes_requested, "external_ai_lanes_requested"),
        "collaboration_room_allowed": False,
    }
    candidate.update(COMMON_FALSE_DEFAULTS)
    candidate.update(COMMON_TRUE_DEFAULTS)
    validate_candidate_schema(candidate)
    return candidate


def build_skill_candidate(
    *,
    candidate_id: str,
    skill_name: str,
    description: str,
    trigger_conditions: list[str] | None = None,
    input_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
    owner: str = "Josh",
    created_by: str = "Engel",
    created_at: str | None = None,
    allowed_files: list[str] | None = None,
    forbidden_files: list[str] | None = None,
    allowed_actions: list[str] | None = None,
    forbidden_actions: list[str] | None = None,
    required_verifiers: list[str] | None = None,
    external_ai_lanes_requested: list[str] | None = None,
) -> dict[str, Any]:
    candidate_id = validate_candidate_id(candidate_id)
    candidate = {
        "candidate_id": candidate_id,
        "candidate_type": "skill",
        "skill_name": str(skill_name),
        "description": str(description),
        "trigger_conditions": _as_list(trigger_conditions, "trigger_conditions"),
        "input_schema": _as_mapping(input_schema, "input_schema"),
        "output_schema": _as_mapping(output_schema, "output_schema"),
        "owner": str(owner),
        "created_by": str(created_by),
        "created_at": str(created_at or _utc_now()),
        "status": "candidate_only",
        "trust_status": "untrusted_candidate",
        "allowed_files": _as_list(allowed_files, "allowed_files"),
        "forbidden_files": _as_list(forbidden_files, "forbidden_files"),
        "allowed_actions": _as_list(allowed_actions, "allowed_actions"),
        "forbidden_actions": _as_list(forbidden_actions, "forbidden_actions") or list(FORBIDDEN_ACTIONS_DEFAULT),
        "required_verifiers": _as_list(required_verifiers, "required_verifiers") or list(REQUIRED_VERIFIERS),
        "external_ai_lanes_requested": _as_list(external_ai_lanes_requested, "external_ai_lanes_requested"),
        "install_enabled": False,
    }
    candidate.update(COMMON_FALSE_DEFAULTS)
    candidate.update(COMMON_TRUE_DEFAULTS)
    validate_candidate_schema(candidate)
    return candidate


def validate_candidate_schema(candidate: dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        raise CandidateScaffoldError("candidate must be an object")
    candidate_id = validate_candidate_id(str(candidate.get("candidate_id", "")))
    if candidate.get("candidate_id") != candidate_id:
        raise CandidateScaffoldError("candidate_id must be a valid string")

    candidate_type = candidate.get("candidate_type")
    if candidate_type == "agent":
        required = AGENT_REQUIRED_FIELDS
    elif candidate_type == "skill":
        required = SKILL_REQUIRED_FIELDS
    else:
        raise CandidateScaffoldError("candidate_type must be agent or skill")

    missing = [field for field in required if field not in candidate]
    if missing:
        raise CandidateScaffoldError(f"candidate missing required fields: {missing}")
    if candidate.get("status") != "candidate_only":
        raise CandidateScaffoldError("status must be candidate_only")
    if candidate.get("trust_status") != "untrusted_candidate":
        raise CandidateScaffoldError("trust_status must be untrusted_candidate")

    for field in COMMON_FALSE_DEFAULTS:
        if candidate.get(field) is not False:
            raise CandidateScaffoldError(f"{field} must be false")
    for field in COMMON_TRUE_DEFAULTS:
        if candidate.get(field) is not True:
            raise CandidateScaffoldError(f"{field} must be true")
    if candidate_type == "agent" and candidate.get("collaboration_room_allowed") is not False:
        raise CandidateScaffoldError("collaboration_room_allowed must be false for agent candidates")
    if candidate_type == "skill" and candidate.get("install_enabled") is not False:
        raise CandidateScaffoldError("install_enabled must be false for skill candidates")

    list_fields = [
        "allowed_files",
        "forbidden_files",
        "allowed_actions",
        "forbidden_actions",
        "required_verifiers",
        "external_ai_lanes_requested",
    ]
    if candidate_type == "agent":
        list_fields.extend(["allowed_inputs", "allowed_outputs", "allowed_context", "forbidden_context"])
    if candidate_type == "skill":
        list_fields.append("trigger_conditions")
        if not isinstance(candidate.get("input_schema"), dict) or not isinstance(candidate.get("output_schema"), dict):
            raise CandidateScaffoldError("skill input_schema and output_schema must be objects")
    for field in list_fields:
        if not isinstance(candidate.get(field), list):
            raise CandidateScaffoldError(f"{field} must be a list")


def candidate_file_paths(candidate: dict[str, Any], storage_root: Path) -> tuple[Path, Path]:
    validate_candidate_schema(candidate)
    candidate_id = validate_candidate_id(str(candidate["candidate_id"]))
    candidate_type = str(candidate["candidate_type"])
    if candidate_type == "agent":
        return storage_root / f"{candidate_id}.agent.json", storage_root / f"{candidate_id}.agent.md"
    if candidate_type == "skill":
        return storage_root / f"{candidate_id}.skill.json", storage_root / f"{candidate_id}.skill.md"
    raise CandidateScaffoldError("candidate_type must be agent or skill")


def render_candidate_markdown(candidate: dict[str, Any], receipt_path: Path | None = None) -> str:
    validate_candidate_schema(candidate)
    candidate_type = str(candidate["candidate_type"])
    title = candidate.get("name") if candidate_type == "agent" else candidate.get("skill_name")
    receipt_text = _project_relative(receipt_path) if receipt_path else "receipt pending until scaffold write"

    lines = [
        f"# {title}",
        "",
        f"candidate_id: {candidate['candidate_id']}",
        f"candidate_type: {candidate_type}",
        "status: candidate_only",
        "trust_status: untrusted_candidate",
        f"owner: {candidate['owner']}",
        f"created_by: {candidate['created_by']}",
        f"created_at: {candidate['created_at']}",
        "",
    ]

    if candidate_type == "agent":
        lines.extend(
            [
                "## Purpose",
                str(candidate["purpose"]),
                "",
                "## Description",
                str(candidate["description"]),
                "",
                "## Allowed Work",
                json.dumps(candidate["allowed_actions"], indent=2, sort_keys=True),
                "",
                "## Allowed Inputs",
                json.dumps(candidate["allowed_inputs"], indent=2, sort_keys=True),
                "",
                "## Allowed Outputs",
                json.dumps(candidate["allowed_outputs"], indent=2, sort_keys=True),
                "",
                "## Allowed Context",
                json.dumps(candidate["allowed_context"], indent=2, sort_keys=True),
                "",
                "## Forbidden Context",
                json.dumps(candidate["forbidden_context"], indent=2, sort_keys=True),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Trigger Conditions",
                json.dumps(candidate["trigger_conditions"], indent=2, sort_keys=True),
                "",
                "## Input Schema",
                json.dumps(candidate["input_schema"], indent=2, sort_keys=True),
                "",
                "## Output Schema",
                json.dumps(candidate["output_schema"], indent=2, sort_keys=True),
                "",
                "## Allowed Work",
                json.dumps(candidate["allowed_actions"], indent=2, sort_keys=True),
                "",
            ]
        )

    lines.extend(
        [
            "## Allowed Files",
            json.dumps(candidate["allowed_files"], indent=2, sort_keys=True),
            "",
            "## Forbidden Files",
            json.dumps(candidate["forbidden_files"], indent=2, sort_keys=True),
            "",
            "## Forbidden Actions",
            json.dumps(candidate["forbidden_actions"], indent=2, sort_keys=True),
            "",
            "## Required Verifiers",
            json.dumps(candidate["required_verifiers"], indent=2, sort_keys=True),
            "",
            "## Approval Status",
            "required_human_review: true",
            "approval_required_for_inactive_registry: true",
            "activation_contract_required: true",
            "receipt_required: true",
            "",
            "## Disabled Runtime Boundary",
        ]
    )
    if candidate_type == "skill":
        lines.append("install_enabled: false")
    if candidate_type == "agent":
        lines.append("collaboration_room_allowed: false")
    for field in COMMON_FALSE_DEFAULTS:
        lines.append(f"{field}: false")
    lines.extend(
        [
            "",
            "## External AI Request Status",
            "External AI requests are request-only and do not grant permission.",
            f"external_ai_lanes_requested: {json.dumps(candidate['external_ai_lanes_requested'], sort_keys=True)}",
            "",
            "## Receipt Link",
            receipt_text,
            "",
            "## Safety Statement",
            "This scaffold is not live, not installed, not trusted, not active, and not runnable.",
            "It cannot write trusted memory, mutate source/routes/queues, call providers/network, install packages, or enable runtime/autorun.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_receipt(
    candidate: dict[str, Any],
    *,
    files_created: list[Path],
    schema_validation_result: str,
    verifier_result: str,
) -> str:
    validate_candidate_schema(candidate)
    files = "\n".join(f"- `{_project_relative(path)}`" for path in files_created)
    false_defaults = "\n".join(f"- `{field}: false`" for field in COMMON_FALSE_DEFAULTS)
    type_line = "install_enabled: false" if candidate["candidate_type"] == "skill" else "collaboration_room_allowed: false"
    return f"""# ENGEL_AGENT_SKILL_CANDIDATE_SCAFFOLD_{candidate['candidate_id']}

Status: scaffold_receipt

## Candidate

- candidate_id: `{candidate['candidate_id']}`
- candidate_type: `{candidate['candidate_type']}`
- status: `candidate_only`
- trust_status: `untrusted_candidate`

## Files Created

{files}

## Validation

- schema_validation_result: `{schema_validation_result}`
- verifier_result: `{verifier_result}`
- human_review_required: `true`

## Safety Defaults

- `{type_line}`
{false_defaults}
- `approval_required_for_inactive_registry: true`
- `activation_contract_required: true`
- `receipt_required: true`

## Safety Statement

This candidate is not live, not installed, not active, and not runnable.

No trusted-memory write, runtime enablement, autorun enablement, source mutation, route mutation, queue mutation, provider/API/network behavior, package install, Mobile runtime, or Remote Queen runtime was enabled by this scaffold operation.
"""


def write_candidate_scaffold(
    candidate: dict[str, Any],
    *,
    storage_root: Path | None = None,
    receipt_root: Path | None = None,
    approved_storage_roots: tuple[Path, ...] | None = None,
    verifier_result: str = "pending_post_write_verification",
    overwrite: bool = False,
) -> dict[str, Any]:
    validate_candidate_schema(candidate)
    approved_roots = approved_storage_roots or APPROVED_STORAGE_ROOTS
    target_storage = _ensure_approved_storage(storage_root or DEFAULT_STORAGE_ROOT, approved_roots)
    target_receipt_root = _ensure_inside_project(receipt_root or DEFAULT_RECEIPT_ROOT, "receipt_root")
    json_path, md_path = candidate_file_paths(candidate, target_storage)
    receipt_path = target_receipt_root / f"ENGEL_AGENT_SKILL_CANDIDATE_SCAFFOLD_{candidate['candidate_id']}.md"

    for path in (json_path, md_path):
        if path.suffix.lower() not in {".json", ".md"}:
            raise CandidateScaffoldError(f"candidate scaffold may only write JSON/MD files: {path}")
        if not _is_relative_to(path, target_storage):
            raise CandidateScaffoldError(f"candidate file escaped approved storage: {path}")
    if receipt_path.suffix.lower() != ".md":
        raise CandidateScaffoldError("receipt must be markdown")
    if not _is_relative_to(receipt_path, target_receipt_root):
        raise CandidateScaffoldError("receipt path escaped receipt root")

    planned = [json_path, md_path, receipt_path]
    if not overwrite:
        existing = [path for path in planned if path.exists()]
        if existing:
            raise CandidateScaffoldError("refusing to overwrite existing scaffold files: " + ", ".join(str(path) for path in existing))

    target_storage.mkdir(parents=True, exist_ok=True)
    target_receipt_root.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(candidate, indent=2, sort_keys=True) + "\n"
    md_text = render_candidate_markdown(candidate, receipt_path)
    receipt_text = render_receipt(
        candidate,
        files_created=[json_path, md_path],
        schema_validation_result="PASS",
        verifier_result=verifier_result,
    )

    if overwrite:
        json_path.write_text(json_text, encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")
        receipt_path.write_text(receipt_text, encoding="utf-8")
    else:
        json_path.write_text(json_text, encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")
        receipt_path.write_text(receipt_text, encoding="utf-8")

    return {
        "candidate_id": candidate["candidate_id"],
        "candidate_type": candidate["candidate_type"],
        "json_path": json_path,
        "markdown_path": md_path,
        "receipt_path": receipt_path,
        "schema_validation_result": "PASS",
        "verifier_result": verifier_result,
        "persistent_candidate_written": True,
        "runtime_enabled": False,
        "autorun_enabled": False,
        "trusted_memory_write_allowed": False,
    }


__all__ = [
    "APPROVED_STORAGE_ROOTS",
    "COMMON_FALSE_DEFAULTS",
    "CandidateScaffoldError",
    "DEFAULT_RECEIPT_ROOT",
    "DEFAULT_STORAGE_ROOT",
    "build_agent_candidate",
    "build_skill_candidate",
    "candidate_file_paths",
    "render_candidate_markdown",
    "render_receipt",
    "validate_candidate_id",
    "validate_candidate_schema",
    "write_candidate_scaffold",
]
