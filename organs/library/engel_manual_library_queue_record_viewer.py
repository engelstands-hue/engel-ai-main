#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engel_manual_library_queue_record_writer import (
    ALLOWED_RECEIPT_STATUSES,
    ALLOWED_REVIEW_STATES,
    QUEUE_METADATA_ROOT,
    RECORD_REQUIRED_LABELS,
    QueueRecordPathError,
    validate_bounded_queue_root,
)


VIEWER_STATUS = [
    "READ_ONLY_VIEWER",
    "METADATA_ONLY",
    "NO_QUEUE_MUTATION",
    "NO_APPROVAL_ACTION",
    "NO_RECEIPT_ACTION",
    "NOT_TRUSTED_MEMORY",
    "NO_LEARNING_TRIGGER",
    "NO_RUNTIME_TRIGGER",
]

READ_ONLY_BOUNDARY = {
    "read_only_viewer": True,
    "metadata_only": True,
    "no_queue_mutation": True,
    "no_approval_action": True,
    "no_receipt_action": True,
    "not_trusted_memory": True,
    "no_learning_trigger": True,
    "no_runtime_trigger": True,
    "no_material_import": True,
    "no_external_location_scan": True,
    "no_indexing": True,
    "no_embedding": True,
    "no_execution": True,
    "no_trusted_memory_write": True,
}

DISPLAY_FIELDS = [
    "queue_record_id",
    "material_id",
    "title",
    "category",
    "subcategory",
    "review_state",
    "receipt_status",
    "receipt_reference",
    "safety_flags",
    "next_manual_action",
]


class QueueRecordViewerError(Exception):
    """Base error for read-only queue metadata viewer failures."""


class QueueRecordViewerDataError(QueueRecordViewerError):
    """Raised when a queue metadata record cannot be displayed safely."""


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def bounded_viewer_root(queue_root: Path | None = None) -> Path:
    return validate_bounded_queue_root(queue_root)


def list_queue_record_paths(queue_root: Path | None = None) -> list[Path]:
    root = bounded_viewer_root(queue_root)
    if not root.exists():
        return []
    if not root.is_dir():
        raise QueueRecordPathError("queue metadata root is not a directory")

    paths: list[Path] = []
    for child in root.iterdir():
        resolved = child.resolve()
        if not _is_relative_to(resolved, root):
            raise QueueRecordPathError("queue metadata path escaped the bounded root")
        if child.is_file() and child.suffix.lower() == ".json":
            paths.append(resolved)
    return sorted(paths, key=lambda path: path.name.lower())


def load_queue_record_metadata(record_path: Path, queue_root: Path | None = None) -> dict[str, Any]:
    root = bounded_viewer_root(queue_root)
    resolved = Path(record_path).resolve()
    if not _is_relative_to(resolved, root):
        raise QueueRecordPathError("record path must stay inside the bounded queue metadata root")
    if resolved.suffix.lower() != ".json":
        raise QueueRecordViewerDataError("queue metadata viewer only reads JSON metadata records")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise QueueRecordViewerDataError("queue metadata record must be a JSON object")
    return payload


def build_record_view(payload: dict[str, Any], source_path: Path | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise QueueRecordViewerDataError("queue metadata record must be a JSON object")

    review_state = payload.get("review_state", "")
    receipt_status = payload.get("receipt_status", "")
    if review_state and review_state not in ALLOWED_REVIEW_STATES:
        raise QueueRecordViewerDataError("queue metadata record has an unknown review_state")
    if receipt_status and receipt_status not in ALLOWED_RECEIPT_STATUSES:
        raise QueueRecordViewerDataError("queue metadata record has an unknown receipt_status")

    labels = payload.get("record_labels", [])
    if labels and not isinstance(labels, list):
        raise QueueRecordViewerDataError("record_labels must be a list")

    return {
        "viewer_status": list(VIEWER_STATUS),
        "source_path": str(source_path) if source_path else "",
        "record_labels": list(labels),
        "expected_metadata_labels": list(RECORD_REQUIRED_LABELS),
        "queue_record_id": payload.get("queue_record_id", ""),
        "material_id": payload.get("material_id", ""),
        "title": payload.get("title", ""),
        "category": payload.get("category", ""),
        "subcategory": payload.get("subcategory", ""),
        "review_state": review_state,
        "receipt_status": receipt_status,
        "receipt_reference": payload.get("receipt_reference", ""),
        "safety_flags": list(payload.get("safety_flags", [])) if isinstance(payload.get("safety_flags", []), list) else [],
        "next_manual_action": payload.get("next_manual_action", ""),
        "read_only_boundary": dict(READ_ONLY_BOUNDARY),
    }


def list_queue_record_views(queue_root: Path | None = None) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for record_path in list_queue_record_paths(queue_root):
        payload = load_queue_record_metadata(record_path, queue_root)
        views.append(build_record_view(payload, record_path))
    return views


def render_record_view(record_view: dict[str, Any]) -> str:
    lines = [
        "Manual Library Queue Record Metadata View",
        "Status: " + " / ".join(VIEWER_STATUS),
        "Labels:",
        *["- " + str(label) for label in record_view.get("record_labels", [])],
        "Metadata:",
    ]
    for field in DISPLAY_FIELDS:
        value = record_view.get(field, "")
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        lines.append("- " + field + ": " + str(value))
    lines.extend(
        [
            "Boundary:",
            "- read-only viewer",
            "- metadata only",
            "- no queue mutation",
            "- no approval action",
            "- no receipt action",
            "- not trusted memory",
            "- no learning trigger",
            "- no runtime trigger",
        ]
    )
    return "\n".join(lines) + "\n"


def render_queue_record_list(queue_root: Path | None = None) -> str:
    views = list_queue_record_views(queue_root)
    lines = [
        "# Engel Manual Library Queue Record Viewer V1",
        "",
        "Status:",
        " / ".join(VIEWER_STATUS),
        "",
        "Queue metadata root:",
        str(bounded_viewer_root(queue_root)),
        "",
        "Record count:",
        str(len(views)),
        "",
    ]
    if not views:
        lines.append("No bounded repo-local queue metadata records found.")
    else:
        for view in views:
            lines.append(render_record_view(view).rstrip())
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_viewer_manifest() -> dict[str, Any]:
    return {
        "name": "Engel Manual Library Queue Record Viewer V1",
        "status": list(VIEWER_STATUS),
        "bounded_queue_metadata_root": str(QUEUE_METADATA_ROOT),
        "display_fields": list(DISPLAY_FIELDS),
        "read_only_boundary": dict(READ_ONLY_BOUNDARY),
    }


def main() -> int:
    print(render_queue_record_list())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
