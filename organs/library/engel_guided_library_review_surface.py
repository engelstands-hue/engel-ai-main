#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any


STATUS = [
    "SURFACE_ONLY",
    "GUIDED_DRAFT_ONLY",
    "HUMAN_GUIDED",
    "NO_REAL_QUEUE_RECORDS",
    "NO_ACTIVE_QUEUE_RUNTIME",
    "NO_QUEUE_WORKER",
    "NO_AUTOMATIC_IMPORT",
    "NOT_TRUSTED_MEMORY",
    "NO_LEARNING_TRIGGER",
    "NO_RUNTIME_TRIGGER",
]

DRAFT_LABELS = [
    "DRAFT_ONLY",
    "NOT_REAL_QUEUE_RECORD",
    "NOT_APPROVAL",
    "NOT_RECEIPT",
    "NOT_TRUSTED_MEMORY",
    "NO_AUTOMATION_TRIGGERED",
]

SAFE_OUTCOMES = [
    "not_ready",
    "needs_source_clarification",
    "hold_for_later",
    "unsafe_or_untrusted_content",
    "metadata_draft_ready",
]

CATEGORIES = [
    "research_papers",
    "architecture_references",
    "engel_manuals",
    "offline_docs",
    "math",
    "coding_languages",
]

RISK_CHECKS = [
    "prompt_injection_risk",
    "provenance_risk",
    "license_or_usage_risk",
    "malicious_code_or_command_risk",
    "math_verification_needed",
    "code_execution_risk",
    "duplicate_check_needed",
    "external_link_risk",
    "sensitive_content_flag",
    "receipt_mismatch_risk",
]

REQUIRED_METADATA_FIELDS = [
    "title",
    "category",
    "subcategory",
    "source_type",
    "source_notes",
    "original_location_reference",
    "intended_reference_location_reference",
    "review_state",
    "safety_flags",
    "receipt_reference",
    "next_manual_action",
]

BOUNDARY_NOTES = [
    "guided surface exists",
    "draft preview only",
    "no real queue records",
    "no approvals",
    "no receipts",
    "no automation",
    "no active queue runtime",
    "no queue worker",
    "no trusted-memory writes",
    "no import/copy/move/sync/scan/index/embed/summarize/execute/train/load",
    "human authority remains required",
]


def build_surface_manifest() -> dict[str, Any]:
    return {
        "surface_name": "Engel Guided Library Review Surface V1",
        "surface_type": "guided_draft_surface",
        "status": list(STATUS),
        "purpose": "Provide a guided, draft-only review surface for approved-library readiness metadata.",
        "draft_labels": list(DRAFT_LABELS),
        "safe_outcomes": list(SAFE_OUTCOMES),
        "categories": list(CATEGORIES),
        "risk_checks": list(RISK_CHECKS),
        "required_metadata_fields": list(REQUIRED_METADATA_FIELDS),
        "boundary_notes": list(BOUNDARY_NOTES),
        "human_authority_required": True,
        "not_trusted_memory": True,
        "no_automation_triggered": True,
    }


def create_draft_preview(candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = dict(candidate or {})
    category = candidate.get("category") if candidate.get("category") in CATEGORIES else "not_selected"
    missing_fields = [field for field in REQUIRED_METADATA_FIELDS if not candidate.get(field)]
    ready = category != "not_selected" and not missing_fields
    outcome = "metadata_draft_ready" if ready else "not_ready"
    return {
        "labels": list(DRAFT_LABELS),
        "outcome": outcome,
        "category": category,
        "missing_fields": missing_fields,
        "candidate_metadata_preview": {key: candidate.get(key, "") for key in REQUIRED_METADATA_FIELDS},
        "boundary": {
            "not_real_queue_record": True,
            "not_approval": True,
            "not_receipt": True,
            "not_trusted_memory": True,
            "no_automation_triggered": True,
            "human_authority_remains_required": True,
        },
    }


def render_surface_text() -> str:
    manifest = build_surface_manifest()
    lines = [
        "# Engel Guided Library Review Surface V1",
        "",
        "Status:",
        " / ".join(manifest["status"]),
        "",
        "Start Here:",
        "- Confirm what the material is.",
        "- Confirm where it came from.",
        "- Choose a category.",
        "- Check obvious risk flags.",
        "- Remember: this is draft preview only.",
        "",
        "Category choices:",
        *[f"- {category}" for category in CATEGORIES],
        "",
        "Risk checks:",
        *[f"- {risk}" for risk in RISK_CHECKS],
        "",
        "Draft labels:",
        *[f"- {label}" for label in DRAFT_LABELS],
        "",
        "Boundary:",
        *[f"- {note}" for note in BOUNDARY_NOTES],
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    print(render_surface_text())
    print(json.dumps(create_draft_preview(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
