#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any

from engel_guided_library_review_surface import (
    CATEGORIES,
    DRAFT_LABELS,
    REQUIRED_METADATA_FIELDS,
    RISK_CHECKS,
    create_draft_preview,
)


DRAFT_REPORT_STATUS = [
    "DRAFT_REPORT_ONLY",
    "DRY_RUN_ONLY",
    "HUMAN_GUIDED",
    "NO_REAL_QUEUE_RECORDS",
    "NO_REAL_APPROVALS",
    "NO_REAL_RECEIPTS",
    "NOT_TRUSTED_MEMORY",
    "NO_AUTOMATION_TRIGGERED",
    "NO_LEARNING_TRIGGER",
    "NO_RUNTIME_TRIGGER",
]

DRY_RUN_BOUNDARY = [
    "draft report only",
    "dry run only",
    "not a real queue record",
    "not an approval",
    "not a receipt",
    "not trusted memory",
    "no automation triggered",
    "no import/copy/move/sync",
    "no folder scan",
    "no indexing/embedding",
    "no execution",
    "no training",
    "no runtime loading",
    "no trusted-memory write",
    "no queue runtime/worker",
    "no route/startup/source changes",
]

DEFAULT_DRAFT_METADATA = {
    "title": "Untitled guided library review draft",
    "category": "not_selected",
    "subcategory": "",
    "source_type": "",
    "source_notes": "",
    "original_location_reference": "",
    "intended_reference_location_reference": "",
    "review_state": "not_ready",
    "safety_flags": [],
    "receipt_reference": "NOT_RECEIPT",
    "next_manual_action": "Human must complete review before any real queue record can be considered.",
}


def normalize_metadata(metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = dict(DEFAULT_DRAFT_METADATA)
    if metadata:
        for key in REQUIRED_METADATA_FIELDS:
            if key in metadata:
                normalized[key] = metadata[key]
    if normalized.get("category") not in CATEGORIES:
        normalized["category"] = "not_selected"
    if not isinstance(normalized.get("safety_flags"), list):
        normalized["safety_flags"] = [str(normalized["safety_flags"])]
    return normalized


def build_draft_report(metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = normalize_metadata(metadata)
    preview = create_draft_preview(normalized)
    return {
        "report_name": "Engel Guided Library Review Draft Report V1",
        "status": list(DRAFT_REPORT_STATUS),
        "labels": list(DRAFT_LABELS),
        "preview": preview,
        "metadata": normalized,
        "risk_checks": list(RISK_CHECKS),
        "boundary": {
            "draft_report_only": True,
            "dry_run_only": True,
            "not_real_queue_record": True,
            "not_approval": True,
            "not_receipt": True,
            "not_trusted_memory": True,
            "no_automation_triggered": True,
            "human_authority_remains_required": True,
        },
    }


def render_draft_report(metadata: dict[str, Any] | None = None) -> str:
    report = build_draft_report(metadata)
    preview = report["preview"]
    normalized = report["metadata"]
    lines = [
        "# Engel Guided Library Review Draft Report V1",
        "",
        "Status:",
        " / ".join(report["status"]),
        "",
        "Draft labels:",
        *[f"- {label}" for label in report["labels"]],
        "",
        "Outcome:",
        str(preview["outcome"]),
        "",
        "Guided metadata preview:",
        *[f"- {field}: {normalized.get(field, '')}" for field in REQUIRED_METADATA_FIELDS],
        "",
        "Missing required metadata:",
        *[f"- {field}" for field in preview["missing_fields"]],
        "",
        "Risk checks to keep visible:",
        *[f"- {risk}" for risk in report["risk_checks"]],
        "",
        "Boundary:",
        *[f"- {note}" for note in DRY_RUN_BOUNDARY],
        "",
        "Human authority:",
        "- human authority remains required",
        "- this draft does not approve material",
        "- this draft does not create a receipt",
        "- this draft does not create a queue record",
    ]
    return "\n".join(lines) + "\n"


def parse_metadata_argument(raw_metadata: str) -> dict[str, Any] | None:
    parsed = json.loads(raw_metadata)
    if not isinstance(parsed, dict):
        raise ValueError("metadata JSON must be an object")
    return parsed


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    metadata = None
    if argv:
        try:
            metadata = parse_metadata_argument(argv[0])
        except (json.JSONDecodeError, ValueError) as exc:
            print("DRAFT_ONLY / DRY_RUN_ONLY / NOT_REAL_QUEUE_RECORD")
            print("Invalid metadata JSON:", exc)
            print("No queue record, approval, receipt, import, memory, or automation was created.")
            return 2
    print(render_draft_report(metadata))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
