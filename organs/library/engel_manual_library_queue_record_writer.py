#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APPROVAL_TOKEN = "APPROVE_CREATE_LIBRARY_QUEUE_RECORD"

WRITER_STATUS = [
    "METADATA_WRITER_ONLY",
    "HUMAN_APPROVAL_REQUIRED",
    "APPROVAL_TOKEN_REQUIRED",
    "QUEUE_RECORD_METADATA_ONLY",
    "NO_MATERIAL_IMPORT",
    "NOT_TRUSTED_MEMORY",
    "NO_LEARNING_TRIGGER",
    "NO_RUNTIME_TRIGGER",
]

RECORD_REQUIRED_LABELS = [
    "REAL_QUEUE_RECORD_METADATA_ONLY",
    "NOT_APPROVAL",
    "NOT_RECEIPT",
    "NOT_TRUSTED_MEMORY",
    "NO_MATERIAL_CONTENT",
    "NO_AUTOMATION_TRIGGERED",
]

REPO_ROOT = Path(__file__).resolve().parent
QUEUE_METADATA_ROOT = REPO_ROOT / "memory" / "approved_library_manual_review_queue"

REQUIRED_DRAFT_FIELDS = [
    "queue_record_id",
    "material_id",
    "title",
    "category",
    "subcategory",
    "source_type",
    "source_notes",
    "original_location_reference",
    "intended_reference_location_reference",
    "submitted_by",
    "submitted_date",
    "review_state",
    "priority",
    "reviewer_assigned",
    "human_review_required",
    "receipt_required",
    "receipt_reference",
    "receipt_status",
    "safety_flags",
    "prompt_injection_risk",
    "provenance_risk",
    "license_or_usage_risk",
    "malicious_code_or_command_risk",
    "math_verification_needed",
    "code_execution_risk",
    "duplicate_check_needed",
    "external_link_risk",
    "sensitive_content_flag",
    "allowed_uses",
    "disallowed_uses",
    "not_trusted_memory",
    "no_automation_triggered",
    "next_manual_action",
    "created_by_human_confirmation",
    "draft_only",
    "not_real_queue_record_until_approved",
]

ALLOWED_CATEGORIES = [
    "research_papers",
    "architecture_references",
    "engel_manuals",
    "offline_docs",
    "math",
    "coding_languages",
]

ALLOWED_REVIEW_STATES = [
    "human_review_pending",
    "in_human_review",
    "approved_for_reference",
    "rejected",
    "hold_for_later",
    "needs_source_clarification",
    "unsafe_or_untrusted_content",
    "receipt_missing",
    "receipt_complete",
]

ALLOWED_RECEIPT_STATUSES = [
    "receipt_missing",
    "receipt_complete",
]

REQUIRED_DISALLOWED_USES = [
    "trusted_memory_write",
    "automatic_learning",
    "automatic_import",
    "automatic_copy",
    "automatic_move",
    "automatic_sync",
    "recursive_scan",
    "indexing",
    "embedding_or_vector_indexing",
    "model_training",
    "fine_tuning",
    "runtime_loading",
    "code_execution",
    "command_execution",
    "package_install",
    "provider_or_network_action",
    "startup_action",
    "background_worker_action",
    "queen_runtime_action",
    "real_approval_creation",
    "real_receipt_creation",
]

METADATA_ONLY_BOUNDARY = {
    "metadata_writer_only": True,
    "human_approval_required": True,
    "approval_token_required": True,
    "queue_record_metadata_only": True,
    "no_material_import": True,
    "no_material_content": True,
    "not_approval": True,
    "not_receipt": True,
    "not_trusted_memory": True,
    "no_automation_triggered": True,
    "no_learning_trigger": True,
    "no_runtime_trigger": True,
    "no_queue_runtime": True,
    "no_queue_worker": True,
}


class QueueRecordWriterError(Exception):
    """Base error for manual library queue metadata writer failures."""


class QueueRecordApprovalError(QueueRecordWriterError):
    """Raised when explicit human approval token validation fails."""


class QueueRecordValidationError(QueueRecordWriterError):
    """Raised when draft metadata does not satisfy the schema boundary."""


class QueueRecordPathError(QueueRecordWriterError):
    """Raised when a requested metadata output path is outside the approved root."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise QueueRecordValidationError(message)


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _safe_record_id(value: Any) -> str:
    record_id = str(value or "").strip()
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
    if not record_id:
        raise QueueRecordValidationError("queue_record_id is required")
    if record_id in {".", ".."}:
        raise QueueRecordValidationError("queue_record_id cannot be a path marker")
    if any(character not in allowed for character in record_id):
        raise QueueRecordValidationError("queue_record_id must be a simple metadata identifier")
    if ".." in record_id:
        raise QueueRecordValidationError("queue_record_id cannot contain traversal markers")
    return record_id


def validate_approval_token(approval_token: str) -> None:
    if approval_token != APPROVAL_TOKEN:
        raise QueueRecordApprovalError("exact APPROVE_CREATE_LIBRARY_QUEUE_RECORD token required")


def validate_bounded_queue_root(queue_root: Path | None = None) -> Path:
    root = (queue_root or QUEUE_METADATA_ROOT).resolve()
    approved_root = QUEUE_METADATA_ROOT.resolve()
    if not _is_relative_to(root, approved_root):
        raise QueueRecordPathError("queue metadata output must stay inside memory/approved_library_manual_review_queue")
    return root


def validate_draft_metadata(draft_metadata: dict[str, Any]) -> None:
    if not isinstance(draft_metadata, dict):
        raise QueueRecordValidationError("draft metadata must be a JSON-like object")

    missing = [field for field in REQUIRED_DRAFT_FIELDS if field not in draft_metadata]
    _require(not missing, "missing required draft metadata fields: " + ", ".join(missing))

    _safe_record_id(draft_metadata["queue_record_id"])
    _require(draft_metadata["category"] in ALLOWED_CATEGORIES, "category is not approved for queue metadata")
    _require(draft_metadata["review_state"] in ALLOWED_REVIEW_STATES, "review_state is not allowed")
    _require(draft_metadata["receipt_status"] in ALLOWED_RECEIPT_STATUSES, "receipt_status is not allowed")

    for flag in [
        "human_review_required",
        "receipt_required",
        "not_trusted_memory",
        "no_automation_triggered",
        "created_by_human_confirmation",
        "draft_only",
        "not_real_queue_record_until_approved",
    ]:
        _require(draft_metadata.get(flag) is True, flag + " must be true")

    for list_field in ["safety_flags", "allowed_uses", "disallowed_uses"]:
        _require(isinstance(draft_metadata.get(list_field), list), list_field + " must be a list")

    disallowed = set(str(value) for value in draft_metadata["disallowed_uses"])
    missing_denials = [value for value in REQUIRED_DISALLOWED_USES if value not in disallowed]
    _require(not missing_denials, "missing required disallowed uses: " + ", ".join(missing_denials))

    for text_field in [
        "material_id",
        "title",
        "subcategory",
        "source_type",
        "source_notes",
        "original_location_reference",
        "intended_reference_location_reference",
        "submitted_by",
        "submitted_date",
        "priority",
        "reviewer_assigned",
        "receipt_reference",
        "prompt_injection_risk",
        "provenance_risk",
        "license_or_usage_risk",
        "malicious_code_or_command_risk",
        "code_execution_risk",
        "external_link_risk",
        "next_manual_action",
    ]:
        _require(isinstance(draft_metadata.get(text_field), str), text_field + " must be a string")


def build_queue_record_metadata(draft_metadata: dict[str, Any], approval_token: str) -> dict[str, Any]:
    validate_approval_token(approval_token)
    validate_draft_metadata(draft_metadata)

    source_draft = {field: draft_metadata[field] for field in REQUIRED_DRAFT_FIELDS}
    record_id = _safe_record_id(draft_metadata["queue_record_id"])
    return {
        "schema_name": "engel_manual_library_queue_record_writer_v1_record",
        "schema_version": "1.0",
        "writer_status": list(WRITER_STATUS),
        "record_labels": list(RECORD_REQUIRED_LABELS),
        "queue_record_id": record_id,
        "material_id": draft_metadata["material_id"],
        "title": draft_metadata["title"],
        "category": draft_metadata["category"],
        "subcategory": draft_metadata["subcategory"],
        "review_state": draft_metadata["review_state"],
        "receipt_status": draft_metadata["receipt_status"],
        "receipt_reference": draft_metadata["receipt_reference"],
        "safety_flags": list(draft_metadata["safety_flags"]),
        "risk_summary": {
            "prompt_injection_risk": draft_metadata["prompt_injection_risk"],
            "provenance_risk": draft_metadata["provenance_risk"],
            "license_or_usage_risk": draft_metadata["license_or_usage_risk"],
            "malicious_code_or_command_risk": draft_metadata["malicious_code_or_command_risk"],
            "math_verification_needed": draft_metadata["math_verification_needed"],
            "code_execution_risk": draft_metadata["code_execution_risk"],
            "duplicate_check_needed": draft_metadata["duplicate_check_needed"],
            "external_link_risk": draft_metadata["external_link_risk"],
            "sensitive_content_flag": draft_metadata["sensitive_content_flag"],
        },
        "source_location_reference": draft_metadata["original_location_reference"],
        "intended_reference_location_reference": draft_metadata["intended_reference_location_reference"],
        "next_manual_action": draft_metadata["next_manual_action"],
        "approval_boundary": {
            "approval_token_name": APPROVAL_TOKEN,
            "approval_token_exact_match_required": True,
            "human_approval_confirmed_for_metadata_write": True,
            "approval_is_not_material_import": True,
            "approval_is_not_reference_approval": True,
            "approval_is_not_receipt": True,
            "approval_is_not_trusted_memory": True,
        },
        "metadata_only_boundary": dict(METADATA_ONLY_BOUNDARY),
        "source_draft_metadata": source_draft,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }


def queue_record_output_path(record_id: str, queue_root: Path | None = None) -> Path:
    root = validate_bounded_queue_root(queue_root)
    safe_id = _safe_record_id(record_id)
    output_path = (root / (safe_id + ".json")).resolve()
    if not _is_relative_to(output_path, root):
        raise QueueRecordPathError("queue metadata output path escaped the bounded queue root")
    return output_path


def write_queue_record_metadata(
    draft_metadata: dict[str, Any],
    approval_token: str,
    queue_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    record = build_queue_record_metadata(draft_metadata, approval_token)
    output_path = queue_record_output_path(record["queue_record_id"], queue_root)

    result = {
        "status": list(WRITER_STATUS),
        "labels": list(RECORD_REQUIRED_LABELS),
        "dry_run": bool(dry_run),
        "written": False,
        "output_path": str(output_path),
        "record": record,
    }
    if dry_run:
        return result

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise QueueRecordPathError("queue metadata record already exists; refusing overwrite")
    output_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["written"] = True
    return result


def build_writer_manifest() -> dict[str, Any]:
    return {
        "name": "Engel Manual Library Queue Record Writer V1",
        "status": list(WRITER_STATUS),
        "approval_token_required": APPROVAL_TOKEN,
        "bounded_queue_metadata_root": str(QUEUE_METADATA_ROOT),
        "record_required_labels": list(RECORD_REQUIRED_LABELS),
        "metadata_only_boundary": dict(METADATA_ONLY_BOUNDARY),
    }


def main() -> int:
    print(json.dumps(build_writer_manifest(), indent=2, sort_keys=True))
    print("This module does not create a queue record from the command line.")
    print("Use write_queue_record_metadata with the exact approval token from an approved local caller.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
