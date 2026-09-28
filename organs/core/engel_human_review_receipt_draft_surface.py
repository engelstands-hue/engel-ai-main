#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any


RECEIPT_DRAFT_STATUS = [
    "RECEIPT_DRAFT_ONLY",
    "HUMAN_GUIDED",
    "NO_REAL_RECEIPTS",
    "NO_APPROVAL_ACTION",
    "NOT_TRUSTED_MEMORY",
    "NO_LEARNING_TRIGGER",
    "NO_RUNTIME_TRIGGER",
]

DRAFT_LABELS = [
    "RECEIPT_DRAFT_ONLY",
    "NOT_REAL_RECEIPT",
    "NOT_APPROVAL",
    "NOT_TRUSTED_MEMORY",
    "NO_AUTOMATION_TRIGGERED",
]

RECEIPT_TEMPLATE_SECTIONS = [
    "Material Identity",
    "Human Reviewer",
    "Review Decision",
    "Safety Boundary Acknowledgments",
    "Prompt Injection / Content Risk Review",
    "Research Use Boundary",
    "Engel Memory Boundary",
    "Math / Code Specific Review",
    "Future Queen / Colony Use Notes",
    "Final Human Signoff",
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

DECISION_FIELDS = [
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

PROMPT_INJECTION_RISK_PROMPTS = [
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

MEMORY_BOUNDARY_PROMPTS = [
    "may_inform_human_guided_research_summary",
    "may_not_write_trusted_memory",
    "requires_separate_memory_candidate_proposal",
    "requires_separate_human_approval_for_memory",
    "memory_boundary_notes",
]

MATH_CODE_REVIEW_PROMPTS = [
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

REQUIRED_PREVIEW_FIELDS = [
    "material_id",
    "title",
    "category",
    "reviewer_name_or_id",
    "review_date",
    "decision",
    "reason_for_decision",
    "final_decision",
    "reviewer_signature_or_marker",
    "no_automation_confirmed",
]

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

ALLOWED_USES = [
    "human_guided_research_reference",
    "citation_source_candidate",
    "manual_study_reference",
    "future_review_candidate",
]

DISALLOWED_USES = [
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

DRAFT_BOUNDARY = {
    "receipt_draft_only": True,
    "human_guided": True,
    "no_real_receipts": True,
    "no_receipt_writer": True,
    "no_approval_action": True,
    "not_trusted_memory": True,
    "no_learning_trigger": True,
    "no_runtime_trigger": True,
    "no_material_import": True,
    "no_material_copy": True,
    "no_material_move": True,
    "no_material_scan": True,
    "no_indexing": True,
    "no_embedding": True,
    "no_execution": True,
    "no_trusted_memory_write": True,
}


def build_surface_manifest() -> dict[str, Any]:
    return {
        "surface_name": "Engel Human Review Receipt Draft Surface V1",
        "surface_type": "receipt_draft_surface",
        "status": list(RECEIPT_DRAFT_STATUS),
        "draft_labels": list(DRAFT_LABELS),
        "receipt_template_sections": list(RECEIPT_TEMPLATE_SECTIONS),
        "safety_acknowledgments": list(SAFETY_ACKNOWLEDGMENTS),
        "prompt_injection_risk_prompts": list(PROMPT_INJECTION_RISK_PROMPTS),
        "memory_boundary_prompts": list(MEMORY_BOUNDARY_PROMPTS),
        "math_code_specific_review_prompts": list(MATH_CODE_REVIEW_PROMPTS),
        "allowed_categories": list(ALLOWED_CATEGORIES),
        "allowed_decisions": list(ALLOWED_DECISIONS),
        "allowed_uses": list(ALLOWED_USES),
        "disallowed_uses": list(DISALLOWED_USES),
        "draft_boundary": dict(DRAFT_BOUNDARY),
    }


def empty_receipt_draft_shape() -> dict[str, Any]:
    return {
        "labels": list(DRAFT_LABELS),
        "material_identity": {field: "" for field in MATERIAL_IDENTITY_FIELDS},
        "human_reviewer": {field: "" for field in HUMAN_REVIEWER_FIELDS},
        "review_decision": {
            "decision": "",
            "approved_for_reference_only": False,
            "rejected": False,
            "hold_for_later": False,
            "needs_source_clarification": False,
            "unsafe_or_untrusted_content": False,
            "reason_for_decision": "",
        },
        "safety_boundary_acknowledgments": {field: False for field in SAFETY_ACKNOWLEDGMENTS},
        "prompt_injection_content_risk_review": {
            field: ("" if field == "risk_notes" else False) for field in PROMPT_INJECTION_RISK_PROMPTS
        },
        "research_use_boundary": {
            "allowed_use": [],
            "disallowed_use": list(DISALLOWED_USES),
            "reference_only_notes": "",
            "citation_required": False,
            "license_or_usage_notes": "",
            "provenance_notes": "",
        },
        "engel_memory_boundary": {
            "may_inform_human_guided_research_summary": False,
            "may_not_write_trusted_memory": True,
            "requires_separate_memory_candidate_proposal": True,
            "requires_separate_human_approval_for_memory": True,
            "memory_boundary_notes": "",
        },
        "math_code_specific_review": {
            "math_claims_need_verification": True,
            "code_examples_not_auto_executable": True,
            "commands_not_auto_runnable": True,
            "package_install_not_allowed": True,
            "technical_accuracy_notes": "",
        },
        "future_queen_colony_use_notes": {field: "" for field in QUEEN_COLONY_FIELDS},
        "final_human_signoff": {
            "final_decision": "",
            "reviewer_signature_or_marker": "",
            "timestamp": "",
            "next_manual_action": "",
            "no_automation_confirmed": False,
        },
        "draft_boundary": dict(DRAFT_BOUNDARY),
    }


def _flat_value(candidate: dict[str, Any], field: str) -> Any:
    value = candidate.get(field, "")
    if isinstance(value, str):
        return value.strip()
    return value


def build_receipt_draft_preview(candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = dict(candidate or {})
    missing_fields = [field for field in REQUIRED_PREVIEW_FIELDS if not _flat_value(candidate, field)]
    category = _flat_value(candidate, "category")
    decision = _flat_value(candidate, "decision")
    category_allowed = category in ALLOWED_CATEGORIES
    decision_allowed = decision in ALLOWED_DECISIONS

    draft = empty_receipt_draft_shape()
    for field in MATERIAL_IDENTITY_FIELDS:
        if field in candidate:
            draft["material_identity"][field] = candidate[field]
    for field in HUMAN_REVIEWER_FIELDS:
        if field in candidate:
            draft["human_reviewer"][field] = candidate[field]
    for field in DECISION_FIELDS:
        if field in candidate:
            draft["review_decision"][field] = candidate[field]
    for field in SAFETY_ACKNOWLEDGMENTS:
        if field in candidate:
            draft["safety_boundary_acknowledgments"][field] = bool(candidate[field])
    for field in PROMPT_INJECTION_RISK_PROMPTS:
        if field in candidate:
            draft["prompt_injection_content_risk_review"][field] = candidate[field]
    for field in MEMORY_BOUNDARY_PROMPTS:
        if field in candidate:
            draft["engel_memory_boundary"][field] = candidate[field]
    for field in MATH_CODE_REVIEW_PROMPTS:
        if field in candidate:
            draft["math_code_specific_review"][field] = candidate[field]
    for field in FINAL_SIGNOFF_FIELDS:
        if field in candidate:
            draft["final_human_signoff"][field] = candidate[field]

    return {
        "status": list(RECEIPT_DRAFT_STATUS),
        "labels": list(DRAFT_LABELS),
        "outcome": "receipt_draft_ready" if not missing_fields and category_allowed and decision_allowed else "receipt_draft_incomplete",
        "missing_fields": missing_fields,
        "category_allowed": category_allowed,
        "decision_allowed": decision_allowed,
        "receipt_template_sections": list(RECEIPT_TEMPLATE_SECTIONS),
        "draft_receipt": draft,
        "draft_boundary": dict(DRAFT_BOUNDARY),
        "human_authority_remains_required": True,
    }


def render_surface_text() -> str:
    manifest = build_surface_manifest()
    lines = [
        "# Engel Human Review Receipt Draft Surface V1",
        "",
        "Status:",
        " / ".join(manifest["status"]),
        "",
        "Draft labels:",
        *["- " + label for label in DRAFT_LABELS],
        "",
        "Receipt template sections:",
        *["- " + section for section in RECEIPT_TEMPLATE_SECTIONS],
        "",
        "Safety acknowledgments:",
        *["- " + field for field in SAFETY_ACKNOWLEDGMENTS],
        "",
        "Prompt-injection risk prompts:",
        *["- " + field for field in PROMPT_INJECTION_RISK_PROMPTS],
        "",
        "Memory boundary prompts:",
        *["- " + field for field in MEMORY_BOUNDARY_PROMPTS],
        "",
        "Math/code-specific review prompts:",
        *["- " + field for field in MATH_CODE_REVIEW_PROMPTS],
        "",
        "Boundary:",
        "- receipt draft only",
        "- not a real receipt",
        "- not approval",
        "- not trusted memory",
        "- no receipt writer",
        "- no trusted-memory write",
        "- no material operations",
        "- no automation triggered",
    ]
    return "\n".join(lines) + "\n"


def render_receipt_draft_preview(candidate: dict[str, Any] | None = None) -> str:
    preview = build_receipt_draft_preview(candidate)
    lines = [
        "# Receipt Draft Preview",
        "",
        "Status:",
        " / ".join(preview["status"]),
        "",
        "Labels:",
        *["- " + label for label in preview["labels"]],
        "",
        "Outcome:",
        str(preview["outcome"]),
        "",
        "Missing fields:",
        *["- " + field for field in preview["missing_fields"]],
        "",
        "Boundary:",
        "- DRAFT ONLY: this is not a real receipt",
        "- NOT APPROVAL: this does not approve material",
        "- NOT TRUSTED MEMORY: this does not write memory",
        "- NO AUTOMATION TRIGGERED",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    print(render_surface_text())
    print(json.dumps(build_receipt_draft_preview(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
