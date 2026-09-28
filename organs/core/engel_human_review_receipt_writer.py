#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APPROVAL_TOKEN = "APPROVE_WRITE_HUMAN_REVIEW_RECEIPT"

RECEIPT_WRITER_STATUS = [
    "RECEIPT_METADATA_WRITER_ONLY",
    "HUMAN_APPROVAL_REQUIRED",
    "APPROVAL_TOKEN_REQUIRED",
    "NO_APPROVAL_ACTION",
    "NOT_TRUSTED_MEMORY",
    "NO_LEARNING_TRIGGER",
    "NO_RUNTIME_TRIGGER",
]

RECEIPT_RECORD_LABELS = [
    "REAL_RECEIPT_METADATA_ONLY",
    "NOT_MATERIAL_APPROVAL",
    "NOT_TRUSTED_MEMORY",
    "NO_MATERIAL_CONTENT",
    "NO_AUTOMATION_TRIGGERED",
]

REPO_ROOT = Path(__file__).resolve().parent
RECEIPT_RECORDS_ROOT = REPO_ROOT / "memory" / "approved_library_human_review_receipts"

ALLOWED_CATEGORIES = [
    "research_papers",
    "architecture_references",
    "engel_manuals",
    "offline_docs",
    "math",
    "coding_languages",
]

ALLOWED_DECISIONS = [
    "approved_for_reference",
    "rejected",
    "hold_for_later",
    "needs_source_clarification",
    "unsafe_or_untrusted_content",
]

MATERIAL_IDENTITY_FIELDS = [
    "material_id",
    "title",
    "author_or_origin",
    "source_type",
    "source_notes",
    "original_location",
    "intended_reference_location",
    "category",
    "subcategory",
    "version_or_date",
    "file_format",
    "estimated_scope",
]

HUMAN_REVIEWER_FIELDS = [
    "reviewer_name_or_id",
    "review_date",
    "review_context",
    "review_depth",
    "reviewer_confidence",
]

REVIEW_DECISION_FIELDS = [
    "decision",
    "approved_for_reference_only",
    "rejected",
    "hold_for_later",
    "needs_source_clarification",
    "unsafe_or_untrusted_content",
    "reason_for_decision",
]

SAFETY_ACKNOWLEDGMENTS = [
    "not_trusted_memory_acknowledged",
    "no_auto_index_acknowledged",
    "no_execution_acknowledged",
    "no_training_acknowledged",
    "no_runtime_loading_acknowledged",
    "no_network_or_provider_action_acknowledged",
    "no_startup_or_background_action_acknowledged",
]

PROMPT_INJECTION_FIELDS = [
    "prompt_injection_risk_observed",
    "hostile_instruction_risk",
    "hidden_or_embedded_instruction_risk",
    "malicious_code_or_command_risk",
    "unsafe_external_link_or_download_risk",
    "citation_or_source_spoofing_risk",
    "poisoned_example_or_bad_training_data_risk",
    "risk_notes",
]

RESEARCH_USE_FIELDS = [
    "allowed_use",
    "disallowed_use",
    "reference_only_notes",
    "citation_required",
    "license_or_usage_notes",
    "provenance_notes",
]

ENGEL_MEMORY_FIELDS = [
    "may_inform_human_guided_research_summary",
    "may_not_write_trusted_memory",
    "requires_separate_memory_candidate_proposal",
    "requires_separate_human_approval_for_memory",
    "memory_boundary_notes",
]

MATH_CODE_FIELDS = [
    "math_claims_need_verification",
    "code_examples_not_auto_executable",
    "commands_not_auto_runnable",
    "package_install_not_allowed",
    "technical_accuracy_notes",
]

QUEEN_COLONY_FIELDS = [
    "queen_visibility",
    "future_workflow_notes",
    "colony_research_notes",
    "archive_notes",
    "long_term_storage_relevance",
    "swarm_or_mycelium_risk_notes",
]

FINAL_SIGNOFF_FIELDS = [
    "final_decision",
    "reviewer_signature_or_marker",
    "timestamp",
    "next_manual_action",
    "no_automation_confirmed",
]

REQUIRED_DISALLOWED_USES = [
    "trusted_memory_write",
    "automatic_learning",
    "model_training",
    "fine_tuning",
    "embedding_or_vector_indexing",
    "runtime_loading",
    "code_execution",
    "command_execution",
    "package_install",
    "provider_or_network_action",
    "startup_action",
    "background_worker_action",
]

RECEIPT_METADATA_BOUNDARY = {
    "receipt_metadata_writer_only": True,
    "human_approval_required": True,
    "approval_token_required": True,
    "no_approval_action": True,
    "not_trusted_memory": True,
    "no_learning_trigger": True,
    "no_runtime_trigger": True,
    "metadata_only": True,
    "no_material_content": True,
    "no_material_import": True,
    "no_material_copy": True,
    "no_material_move": True,
    "no_material_scan": True,
    "no_indexing": True,
    "no_embedding": True,
    "no_execution": True,
    "no_training": True,
    "no_runtime_loading": True,
    "no_worker_or_runtime_start": True,
    "no_trusted_memory_write": True,
}


class HumanReviewReceiptWriterError(Exception):
    """Base error for human review receipt metadata writer failures."""


class HumanReviewReceiptApprovalError(HumanReviewReceiptWriterError):
    """Raised when exact human approval token validation fails."""


class HumanReviewReceiptValidationError(HumanReviewReceiptWriterError):
    """Raised when receipt metadata fails template or safety validation."""


class HumanReviewReceiptPathError(HumanReviewReceiptWriterError):
    """Raised when receipt metadata output is outside the bounded root."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HumanReviewReceiptValidationError(message)


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _require_section(payload: dict[str, Any], section: str, fields: list[str]) -> dict[str, Any]:
    value = payload.get(section)
    _require(isinstance(value, dict), section + " section must be a JSON object")
    missing = [field for field in fields if field not in value]
    _require(not missing, section + " missing fields: " + ", ".join(missing))
    return value


def _string_value(section: dict[str, Any], field: str) -> str:
    value = section.get(field)
    _require(isinstance(value, str), field + " must be a string")
    return value.strip()


def _bool_value(section: dict[str, Any], field: str) -> bool:
    value = section.get(field)
    _require(isinstance(value, bool), field + " must be a boolean")
    return value


def _safe_identifier(value: Any) -> str:
    text = str(value or "").strip()
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
    cleaned = "".join(character if character in allowed else "_" for character in text)
    cleaned = cleaned.strip("._-")
    if not cleaned:
        raise HumanReviewReceiptValidationError("receipt metadata identifier cannot be empty")
    if ".." in cleaned:
        raise HumanReviewReceiptValidationError("receipt metadata identifier cannot contain traversal markers")
    return cleaned[:160]


def validate_approval_token(approval_token: str) -> None:
    if approval_token != APPROVAL_TOKEN:
        raise HumanReviewReceiptApprovalError("exact APPROVE_WRITE_HUMAN_REVIEW_RECEIPT token required")


def validate_bounded_receipt_root(receipt_root: Path | None = None) -> Path:
    root = (receipt_root or RECEIPT_RECORDS_ROOT).resolve()
    approved_root = RECEIPT_RECORDS_ROOT.resolve()
    if not _is_relative_to(root, approved_root):
        raise HumanReviewReceiptPathError("receipt metadata output must stay inside memory/approved_library_human_review_receipts")
    return root


def validate_receipt_metadata(receipt_metadata: dict[str, Any]) -> None:
    _require(isinstance(receipt_metadata, dict), "receipt metadata must be a JSON-like object")

    material = _require_section(receipt_metadata, "material_identity", MATERIAL_IDENTITY_FIELDS)
    reviewer = _require_section(receipt_metadata, "human_reviewer", HUMAN_REVIEWER_FIELDS)
    decision = _require_section(receipt_metadata, "review_decision", REVIEW_DECISION_FIELDS)
    acknowledgments = _require_section(receipt_metadata, "safety_boundary_acknowledgments", SAFETY_ACKNOWLEDGMENTS)
    prompt_risks = _require_section(receipt_metadata, "prompt_injection_content_risk_review", PROMPT_INJECTION_FIELDS)
    research_use = _require_section(receipt_metadata, "research_use_boundary", RESEARCH_USE_FIELDS)
    memory_boundary = _require_section(receipt_metadata, "engel_memory_boundary", ENGEL_MEMORY_FIELDS)
    math_code = _require_section(receipt_metadata, "math_code_specific_review", MATH_CODE_FIELDS)
    _require_section(receipt_metadata, "future_queen_colony_use_notes", QUEEN_COLONY_FIELDS)
    signoff = _require_section(receipt_metadata, "final_human_signoff", FINAL_SIGNOFF_FIELDS)

    for field in MATERIAL_IDENTITY_FIELDS:
        _require(_string_value(material, field) != "", field + " is required")
    for field in HUMAN_REVIEWER_FIELDS:
        _require(_string_value(reviewer, field) != "", field + " is required")
    for field in ["decision", "reason_for_decision"]:
        _require(_string_value(decision, field) != "", field + " is required")
    for field in ["risk_notes"]:
        _require(isinstance(prompt_risks.get(field), str), field + " must be a string")
    for field in ["reference_only_notes", "license_or_usage_notes", "provenance_notes"]:
        _require(isinstance(research_use.get(field), str), field + " must be a string")
    for field in ["memory_boundary_notes"]:
        _require(isinstance(memory_boundary.get(field), str), field + " must be a string")
    for field in ["technical_accuracy_notes"]:
        _require(isinstance(math_code.get(field), str), field + " must be a string")
    for field in ["final_decision", "reviewer_signature_or_marker", "timestamp", "next_manual_action"]:
        _require(_string_value(signoff, field) != "", field + " is required")

    _require(material["category"] in ALLOWED_CATEGORIES, "category is not approved for receipt metadata")
    _require(decision["decision"] in ALLOWED_DECISIONS, "decision is not allowed")
    _require(signoff["final_decision"] in ALLOWED_DECISIONS, "final_decision is not allowed")

    for field in [
        "approved_for_reference_only",
        "rejected",
        "hold_for_later",
        "needs_source_clarification",
        "unsafe_or_untrusted_content",
    ]:
        _bool_value(decision, field)

    for field in SAFETY_ACKNOWLEDGMENTS:
        _require(_bool_value(acknowledgments, field) is True, field + " must be true before receipt metadata write")

    for field in [
        "prompt_injection_risk_observed",
        "hostile_instruction_risk",
        "hidden_or_embedded_instruction_risk",
        "malicious_code_or_command_risk",
        "unsafe_external_link_or_download_risk",
        "citation_or_source_spoofing_risk",
        "poisoned_example_or_bad_training_data_risk",
    ]:
        _bool_value(prompt_risks, field)

    _require(isinstance(research_use.get("allowed_use"), list), "allowed_use must be a list")
    _require(isinstance(research_use.get("disallowed_use"), list), "disallowed_use must be a list")
    disallowed = set(str(value) for value in research_use["disallowed_use"])
    missing_denials = [value for value in REQUIRED_DISALLOWED_USES if value not in disallowed]
    _require(not missing_denials, "missing required disallowed uses: " + ", ".join(missing_denials))

    _bool_value(research_use, "citation_required")

    _require(_bool_value(memory_boundary, "may_not_write_trusted_memory") is True, "may_not_write_trusted_memory must be true")
    _require(
        _bool_value(memory_boundary, "requires_separate_memory_candidate_proposal") is True,
        "requires_separate_memory_candidate_proposal must be true",
    )
    _require(
        _bool_value(memory_boundary, "requires_separate_human_approval_for_memory") is True,
        "requires_separate_human_approval_for_memory must be true",
    )
    _bool_value(memory_boundary, "may_inform_human_guided_research_summary")

    for field in [
        "math_claims_need_verification",
        "code_examples_not_auto_executable",
        "commands_not_auto_runnable",
        "package_install_not_allowed",
    ]:
        _require(_bool_value(math_code, field) is True, field + " must be true")

    _require(_bool_value(signoff, "no_automation_confirmed") is True, "no_automation_confirmed must be true")


def receipt_record_id(receipt_metadata: dict[str, Any]) -> str:
    material = receipt_metadata["material_identity"]
    reviewer = receipt_metadata["human_reviewer"]
    decision = receipt_metadata["review_decision"]
    raw = "__".join(
        [
            material.get("material_id", ""),
            reviewer.get("review_date", ""),
            reviewer.get("reviewer_name_or_id", ""),
            decision.get("decision", ""),
        ]
    )
    return _safe_identifier(raw)


def receipt_record_output_path(record_id: str, receipt_root: Path | None = None) -> Path:
    root = validate_bounded_receipt_root(receipt_root)
    output_path = (root / (_safe_identifier(record_id) + ".json")).resolve()
    if not _is_relative_to(output_path, root):
        raise HumanReviewReceiptPathError("receipt metadata output path escaped the bounded receipt root")
    return output_path


def build_receipt_record_metadata(receipt_metadata: dict[str, Any], approval_token: str) -> dict[str, Any]:
    validate_approval_token(approval_token)
    validate_receipt_metadata(receipt_metadata)
    record_id = receipt_record_id(receipt_metadata)
    return {
        "schema_name": "engel_human_review_receipt_writer_v1_record",
        "schema_version": "1.0",
        "writer_status": list(RECEIPT_WRITER_STATUS),
        "record_labels": list(RECEIPT_RECORD_LABELS),
        "receipt_record_id": record_id,
        "material_id": receipt_metadata["material_identity"]["material_id"],
        "title": receipt_metadata["material_identity"]["title"],
        "category": receipt_metadata["material_identity"]["category"],
        "decision": receipt_metadata["review_decision"]["decision"],
        "final_decision": receipt_metadata["final_human_signoff"]["final_decision"],
        "reviewer_name_or_id": receipt_metadata["human_reviewer"]["reviewer_name_or_id"],
        "review_date": receipt_metadata["human_reviewer"]["review_date"],
        "next_manual_action": receipt_metadata["final_human_signoff"]["next_manual_action"],
        "approval_boundary": {
            "approval_token_name": APPROVAL_TOKEN,
            "approval_token_exact_match_required": True,
            "human_approval_confirmed_for_receipt_metadata_write": True,
            "receipt_write_is_not_material_approval": True,
            "receipt_write_is_not_import": True,
            "receipt_write_is_not_trusted_memory": True,
        },
        "metadata_boundary": dict(RECEIPT_METADATA_BOUNDARY),
        "receipt_metadata": receipt_metadata,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }


def write_receipt_record_metadata(
    receipt_metadata: dict[str, Any],
    approval_token: str,
    receipt_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    record = build_receipt_record_metadata(receipt_metadata, approval_token)
    output_path = receipt_record_output_path(record["receipt_record_id"], receipt_root)
    result = {
        "status": list(RECEIPT_WRITER_STATUS),
        "labels": list(RECEIPT_RECORD_LABELS),
        "dry_run": bool(dry_run),
        "written": False,
        "output_path": str(output_path),
        "record": record,
    }
    if dry_run:
        return result

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise HumanReviewReceiptPathError("receipt metadata record already exists; refusing overwrite")
    output_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["written"] = True
    return result


def build_writer_manifest() -> dict[str, Any]:
    return {
        "name": "Engel Human Review Receipt Writer V1",
        "status": list(RECEIPT_WRITER_STATUS),
        "approval_token_required": APPROVAL_TOKEN,
        "bounded_receipt_records_root": str(RECEIPT_RECORDS_ROOT),
        "record_labels": list(RECEIPT_RECORD_LABELS),
        "metadata_boundary": dict(RECEIPT_METADATA_BOUNDARY),
    }


def main() -> int:
    print(json.dumps(build_writer_manifest(), indent=2, sort_keys=True))
    print("This module does not create receipt metadata from the command line.")
    print("Use write_receipt_record_metadata with the exact approval token from an approved local caller.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
