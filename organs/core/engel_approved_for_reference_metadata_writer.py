#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APPROVAL_TOKEN = "APPROVE_MARK_APPROVED_FOR_REFERENCE"

WRITER_STATUS = [
    "REFERENCE_METADATA_WRITER_ONLY",
    "HUMAN_APPROVAL_REQUIRED",
    "APPROVAL_TOKEN_REQUIRED",
    "NOT_TRUSTED_MEMORY",
    "NO_LEARNING_TRIGGER",
    "NO_RUNTIME_TRIGGER",
]

REFERENCE_METADATA_LABELS = [
    "APPROVED_FOR_REFERENCE_METADATA_ONLY",
    "REFERENCE_ONLY",
    "NOT_TRUSTED_MEMORY",
    "NOT_TRAINING_PERMISSION",
    "NOT_RUNTIME_PERMISSION",
    "NOT_EXECUTION_PERMISSION",
    "NO_MATERIAL_CONTENT",
    "NO_AUTOMATION_TRIGGERED",
]

REPO_ROOT = Path(__file__).resolve().parent
REFERENCE_METADATA_ROOT = REPO_ROOT / "memory" / "approved_library_reference_metadata"

REQUIRED_QUEUE_LABELS = [
    "REAL_QUEUE_RECORD_METADATA_ONLY",
    "NOT_APPROVAL",
    "NOT_RECEIPT",
    "NOT_TRUSTED_MEMORY",
    "NO_MATERIAL_CONTENT",
    "NO_AUTOMATION_TRIGGERED",
]

REQUIRED_RECEIPT_LABELS = [
    "REAL_RECEIPT_METADATA_ONLY",
    "NOT_MATERIAL_APPROVAL",
    "NOT_TRUSTED_MEMORY",
    "NO_MATERIAL_CONTENT",
    "NO_AUTOMATION_TRIGGERED",
]

REQUIRED_CONFIRMATION_FIELDS = [
    "queue_record_exists",
    "human_review_receipt_exists",
    "receipt_says_approved_for_reference",
    "source_provenance_acceptable",
    "safety_flags_resolved_or_acknowledged",
    "reference_only_approval_confirmed",
    "not_trusted_memory_confirmed",
    "no_training_indexing_runtime_execution_confirmed",
    "no_material_import_confirmed",
    "no_automation_triggered_confirmed",
]

REFERENCE_BOUNDARY = {
    "reference_metadata_writer_only": True,
    "human_approval_required": True,
    "approval_token_required": True,
    "approved_for_reference_is_reference_only": True,
    "not_trusted_memory": True,
    "no_learning_trigger": True,
    "no_runtime_trigger": True,
    "no_training_permission": True,
    "no_indexing_permission": True,
    "no_execution_permission": True,
    "no_material_content": True,
    "no_material_import": True,
    "no_material_copy": True,
    "no_material_move": True,
    "no_material_scan": True,
    "no_embedding": True,
    "no_model_training": True,
    "no_runtime_loading": True,
    "no_command_execution": True,
    "no_trusted_memory_write": True,
    "no_worker_or_runtime_start": True,
}


class ApprovedForReferenceWriterError(Exception):
    """Base error for approved-for-reference metadata writer failures."""


class ApprovedForReferenceApprovalError(ApprovedForReferenceWriterError):
    """Raised when exact human approval token validation fails."""


class ApprovedForReferenceValidationError(ApprovedForReferenceWriterError):
    """Raised when queue, receipt, or confirmation metadata is invalid."""


class ApprovedForReferencePathError(ApprovedForReferenceWriterError):
    """Raised when reference metadata output is outside the bounded root."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ApprovedForReferenceValidationError(message)


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _string_value(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    _require(isinstance(value, str), field + " must be a string")
    text = value.strip()
    _require(text != "", field + " is required")
    return text


def _safe_identifier(value: Any) -> str:
    text = str(value or "").strip()
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
    cleaned = "".join(character if character in allowed else "_" for character in text)
    cleaned = cleaned.strip("._-")
    if not cleaned:
        raise ApprovedForReferenceValidationError("reference metadata identifier cannot be empty")
    if cleaned in {".", ".."} or ".." in cleaned:
        raise ApprovedForReferenceValidationError("reference metadata identifier cannot contain traversal markers")
    return cleaned[:180]


def validate_approval_token(approval_token: str) -> None:
    if approval_token != APPROVAL_TOKEN:
        raise ApprovedForReferenceApprovalError("exact APPROVE_MARK_APPROVED_FOR_REFERENCE token required")


def validate_bounded_reference_root(reference_root: Path | None = None) -> Path:
    root = (reference_root or REFERENCE_METADATA_ROOT).resolve()
    approved_root = REFERENCE_METADATA_ROOT.resolve()
    if not _is_relative_to(root, approved_root):
        raise ApprovedForReferencePathError("reference metadata output must stay inside memory/approved_library_reference_metadata")
    return root


def _require_labels(payload: dict[str, Any], field: str, required_labels: list[str]) -> None:
    labels = payload.get(field)
    _require(isinstance(labels, list), field + " must be a list")
    label_set = set(str(label) for label in labels)
    missing = [label for label in required_labels if label not in label_set]
    _require(not missing, field + " missing labels: " + ", ".join(missing))


def validate_queue_metadata(queue_metadata: dict[str, Any]) -> None:
    _require(isinstance(queue_metadata, dict), "queue metadata must be a JSON-like object")
    _require(
        queue_metadata.get("schema_name") == "engel_manual_library_queue_record_writer_v1_record",
        "queue metadata must come from Manual Library Queue Record Writer V1",
    )
    _require_labels(queue_metadata, "record_labels", REQUIRED_QUEUE_LABELS)
    _require("QUEUE_RECORD_METADATA_ONLY" in queue_metadata.get("writer_status", []), "queue metadata status missing")

    for field in [
        "queue_record_id",
        "material_id",
        "title",
        "category",
        "review_state",
        "receipt_status",
        "receipt_reference",
    ]:
        _string_value(queue_metadata, field)

    _require(queue_metadata.get("receipt_status") == "receipt_complete", "queue metadata must reference a completed receipt")
    _require(queue_metadata.get("metadata_only_boundary", {}).get("not_trusted_memory") is True, "queue metadata must not be trusted memory")
    _require(queue_metadata.get("metadata_only_boundary", {}).get("no_material_content") is True, "queue metadata must contain no material content")


def validate_receipt_metadata(receipt_metadata: dict[str, Any]) -> None:
    _require(isinstance(receipt_metadata, dict), "receipt metadata must be a JSON-like object")
    _require(
        receipt_metadata.get("schema_name") == "engel_human_review_receipt_writer_v1_record",
        "receipt metadata must come from Human Review Receipt Writer V1",
    )
    _require_labels(receipt_metadata, "record_labels", REQUIRED_RECEIPT_LABELS)
    _require("RECEIPT_METADATA_WRITER_ONLY" in receipt_metadata.get("writer_status", []), "receipt metadata status missing")

    for field in ["receipt_record_id", "material_id", "title", "category", "decision", "final_decision"]:
        _string_value(receipt_metadata, field)

    _require(receipt_metadata.get("decision") == "approved_for_reference", "receipt decision must be approved_for_reference")
    _require(receipt_metadata.get("final_decision") == "approved_for_reference", "receipt final_decision must be approved_for_reference")
    _require(receipt_metadata.get("metadata_boundary", {}).get("not_trusted_memory") is True, "receipt metadata must not be trusted memory")
    _require(receipt_metadata.get("metadata_boundary", {}).get("no_material_content") is True, "receipt metadata must contain no material content")

    nested = receipt_metadata.get("receipt_metadata")
    _require(isinstance(nested, dict), "receipt record must include nested receipt metadata")
    decision = nested.get("review_decision", {})
    _require(isinstance(decision, dict), "nested review decision must be present")
    _require(decision.get("decision") == "approved_for_reference", "nested receipt decision must be approved_for_reference")
    _require(decision.get("approved_for_reference_only") is True, "nested receipt must mark approved_for_reference_only true")

    acknowledgments = nested.get("safety_boundary_acknowledgments", {})
    _require(isinstance(acknowledgments, dict), "safety acknowledgments must be present")
    for field in [
        "not_trusted_memory_acknowledged",
        "no_auto_index_acknowledged",
        "no_execution_acknowledged",
        "no_training_acknowledged",
        "no_runtime_loading_acknowledged",
    ]:
        _require(acknowledgments.get(field) is True, field + " must be true")

    research_use = nested.get("research_use_boundary", {})
    _require(isinstance(research_use, dict), "research use boundary must be present")
    _require(isinstance(research_use.get("provenance_notes"), str), "receipt provenance_notes must be present")
    _require(research_use["provenance_notes"].strip() != "", "receipt provenance_notes cannot be empty")


def validate_metadata_references(queue_metadata: dict[str, Any], receipt_metadata: dict[str, Any]) -> None:
    queue_material_id = _string_value(queue_metadata, "material_id")
    receipt_material_id = _string_value(receipt_metadata, "material_id")
    _require(queue_material_id == receipt_material_id, "queue metadata and receipt metadata material_id must match")
    _require(
        queue_metadata.get("receipt_reference") == receipt_metadata.get("receipt_record_id"),
        "queue metadata receipt_reference must match receipt metadata receipt_record_id",
    )


def validate_human_confirmation(human_confirmation: dict[str, Any]) -> None:
    _require(isinstance(human_confirmation, dict), "human confirmation must be a JSON-like object")
    for field in REQUIRED_CONFIRMATION_FIELDS:
        _require(human_confirmation.get(field) is True, field + " must be true")


def reference_decision_record_id(queue_metadata: dict[str, Any], receipt_metadata: dict[str, Any]) -> str:
    raw = "__".join(
        [
            queue_metadata.get("queue_record_id", ""),
            receipt_metadata.get("receipt_record_id", ""),
            "approved_for_reference",
        ]
    )
    return _safe_identifier(raw)


def reference_metadata_output_path(record_id: str, reference_root: Path | None = None) -> Path:
    root = validate_bounded_reference_root(reference_root)
    output_path = (root / (_safe_identifier(record_id) + ".json")).resolve()
    if not _is_relative_to(output_path, root):
        raise ApprovedForReferencePathError("reference metadata output path escaped the bounded reference root")
    return output_path


def build_approved_for_reference_metadata(
    queue_metadata: dict[str, Any],
    receipt_metadata: dict[str, Any],
    human_confirmation: dict[str, Any],
    approval_token: str,
) -> dict[str, Any]:
    validate_approval_token(approval_token)
    validate_queue_metadata(queue_metadata)
    validate_receipt_metadata(receipt_metadata)
    validate_metadata_references(queue_metadata, receipt_metadata)
    validate_human_confirmation(human_confirmation)

    record_id = reference_decision_record_id(queue_metadata, receipt_metadata)
    return {
        "schema_name": "engel_approved_for_reference_metadata_writer_v1_record",
        "schema_version": "1.0",
        "writer_status": list(WRITER_STATUS),
        "record_labels": list(REFERENCE_METADATA_LABELS),
        "reference_decision_record_id": record_id,
        "queue_record_id": queue_metadata["queue_record_id"],
        "receipt_record_id": receipt_metadata["receipt_record_id"],
        "material_id": queue_metadata["material_id"],
        "title": queue_metadata["title"],
        "category": queue_metadata["category"],
        "reference_decision": "approved_for_reference",
        "reference_scope": "research/reference only",
        "source_provenance_acceptable": True,
        "safety_flags_resolved_or_acknowledged": True,
        "approval_boundary": {
            "approval_token_name": APPROVAL_TOKEN,
            "approval_token_exact_match_required": True,
            "human_approval_confirmed_for_reference_metadata_write": True,
            "approved_for_reference_is_not_trusted_memory": True,
            "approved_for_reference_is_not_training_permission": True,
            "approved_for_reference_is_not_indexing_permission": True,
            "approved_for_reference_is_not_runtime_permission": True,
            "approved_for_reference_is_not_execution_permission": True,
            "approved_for_reference_is_not_material_import": True,
        },
        "metadata_boundary": dict(REFERENCE_BOUNDARY),
        "queue_metadata_reference": {
            "queue_record_id": queue_metadata["queue_record_id"],
            "queue_record_is_metadata_only": True,
            "queue_record_is_not_approval": True,
            "queue_record_is_not_trusted_memory": True,
        },
        "receipt_metadata_reference": {
            "receipt_record_id": receipt_metadata["receipt_record_id"],
            "receipt_says_approved_for_reference": True,
            "receipt_is_metadata_only": True,
            "receipt_is_not_trusted_memory": True,
        },
        "human_confirmation": {field: human_confirmation[field] for field in REQUIRED_CONFIRMATION_FIELDS},
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }


def write_approved_for_reference_metadata(
    queue_metadata: dict[str, Any],
    receipt_metadata: dict[str, Any],
    human_confirmation: dict[str, Any],
    approval_token: str,
    reference_root: Path | None = None,
    dry_run: bool = False,
    allow_update: bool = False,
) -> dict[str, Any]:
    record = build_approved_for_reference_metadata(queue_metadata, receipt_metadata, human_confirmation, approval_token)
    output_path = reference_metadata_output_path(record["reference_decision_record_id"], reference_root)
    result = {
        "status": list(WRITER_STATUS),
        "labels": list(REFERENCE_METADATA_LABELS),
        "dry_run": bool(dry_run),
        "written": False,
        "updated": False,
        "output_path": str(output_path),
        "record": record,
    }
    if dry_run:
        return result

    output_path.parent.mkdir(parents=True, exist_ok=True)
    already_exists = output_path.exists()
    if already_exists and not allow_update:
        raise ApprovedForReferencePathError("reference metadata record already exists; refusing overwrite without allow_update")
    output_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["written"] = True
    result["updated"] = already_exists
    return result


def build_writer_manifest() -> dict[str, Any]:
    return {
        "name": "Engel Approved-for-Reference Metadata Writer V1",
        "status": list(WRITER_STATUS),
        "approval_token_required": APPROVAL_TOKEN,
        "bounded_reference_metadata_root": str(REFERENCE_METADATA_ROOT),
        "record_labels": list(REFERENCE_METADATA_LABELS),
        "metadata_boundary": dict(REFERENCE_BOUNDARY),
    }


def main() -> int:
    print(json.dumps(build_writer_manifest(), indent=2, sort_keys=True))
    print("This module does not mark material approved from the command line.")
    print("Use write_approved_for_reference_metadata with matching queue and receipt metadata plus the exact approval token.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
