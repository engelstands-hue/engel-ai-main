from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import engel_approved_memory_promotion
import engel_candidate_set_approval


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
APPROVAL_RECEIPT = (
    ROOT
    / "reports"
    / "candidate_set_approvals"
    / "ENGEL_CANDIDATE_SET_APPROVAL_186_LESSON_24_MEMORY.json"
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def _normalize_relpath(path_text: str) -> str:
    text = str(path_text or "").replace("/", "\\").strip()
    while "\\\\" in text:
        text = text.replace("\\\\", "\\")
    return text.rstrip("\\").casefold()


def _load_receipt() -> dict[str, Any]:
    if not APPROVAL_RECEIPT.exists():
        return {}
    return json.loads(APPROVAL_RECEIPT.read_text(encoding="utf-8-sig"))


def _runtime_memory_candidates() -> list[dict[str, Any]]:
    items = engel_approved_memory_promotion.discover_candidates()
    return sorted(items, key=lambda item: str(item.get("source_path", "")))


def _receipt_memory_candidates(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    items = receipt.get("memory_candidates", [])
    if not isinstance(items, list):
        return []
    return sorted(
        [item for item in items if isinstance(item, dict)],
        key=lambda item: str(item.get("source_path", "")),
    )


def _candidate_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": item.get("candidate_id", ""),
        "source_path": item.get("source_path", ""),
        "source_hash": item.get("source_hash", ""),
        "size_bytes": item.get("size_bytes", 0),
        "validation_status": item.get("validation_status", item.get("validation_status_before_approval", "")),
        "promotion_status": item.get("promotion_status", "not_promoted"),
        "trusted_memory_written": False,
    }


def build_inventory() -> dict[str, Any]:
    all_runtime_candidates = _runtime_memory_candidates()
    receipt = _load_receipt()
    receipt_candidates = _receipt_memory_candidates(receipt)

    runtime_by_path = {
        _normalize_relpath(str(item.get("source_path", ""))): item for item in all_runtime_candidates
    }
    receipt_by_path = {
        _normalize_relpath(str(item.get("source_path", ""))): item for item in receipt_candidates
    }

    extra_runtime_keys = sorted(set(runtime_by_path) - set(receipt_by_path))
    missing_runtime_keys = sorted(set(receipt_by_path) - set(runtime_by_path))
    approved_runtime_keys = sorted(set(runtime_by_path) & set(receipt_by_path))
    approved_runtime_candidates = [runtime_by_path[key] for key in approved_runtime_keys]

    expected_memory_count = int(
        receipt.get(
            "expected_memory_candidate_count",
            getattr(engel_candidate_set_approval, "EXPECTED_MEMORY_COUNT", 24),
        )
        or 24
    )
    runtime_count = len(approved_runtime_candidates)
    all_runtime_count = len(all_runtime_candidates)
    receipt_count = len(receipt_candidates)
    counts_match = runtime_count == expected_memory_count == receipt_count

    if counts_match:
        finding = "current_memory_candidate_count_matches_approved_receipt"
    elif runtime_count > expected_memory_count:
        finding = "runtime_memory_candidate_count_exceeds_approved_receipt"
    elif runtime_count < expected_memory_count:
        finding = "runtime_memory_candidate_count_below_approved_receipt"
    else:
        finding = "receipt_memory_candidate_count_differs_from_expected"

    return {
        "schema": "engel_memory_candidate_inventory_v1",
        "generated_at": now_utc(),
        "active_workspace": str(ROOT),
        "mode": "REPORT_ONLY_STATIC_INVENTORY",
        "approval_receipt": project_relative(APPROVAL_RECEIPT),
        "approval_receipt_exists": APPROVAL_RECEIPT.exists(),
        "expected_memory_candidate_count": expected_memory_count,
        "approved_receipt_memory_candidate_count": receipt_count,
        "runtime_memory_candidate_count": runtime_count,
        "all_runtime_memory_candidate_count": all_runtime_count,
        "pending_unapproved_memory_candidate_count": len(extra_runtime_keys),
        "counts_match": counts_match,
        "finding": finding,
        "extra_runtime_candidates": [
            _candidate_summary(runtime_by_path[key]) for key in extra_runtime_keys
        ],
        "missing_runtime_candidates": [
            _candidate_summary(receipt_by_path[key]) for key in missing_runtime_keys
        ],
        "runtime_candidates": [_candidate_summary(item) for item in approved_runtime_candidates],
        "all_runtime_candidates": [_candidate_summary(item) for item in all_runtime_candidates],
        "safety": {
            "report_only": True,
            "memory_promotion_enabled": False,
            "trusted_memory_write_enabled": False,
            "approved_memory_write_enabled": False,
            "candidate_approval_enabled": False,
            "fix_apply_enabled": False,
            "source_mutation_enabled": False,
            "queue_route_mutation_enabled": False,
            "provider_calls_enabled": False,
            "model_runtime_enabled": False,
            "background_worker_enabled": False,
        },
    }


def render_inventory_status() -> str:
    inventory = build_inventory()
    lines = [
        "Engel Memory Candidate Inventory",
        "",
        "Mode: report-only static inventory",
        "Active workspace: " + str(inventory["active_workspace"]),
        "Approval receipt: " + str(inventory["approval_receipt"]),
        "Approval receipt exists: " + str(inventory["approval_receipt_exists"]),
        "",
        "Counts:",
        "- expected memory candidates: " + str(inventory["expected_memory_candidate_count"]),
        "- approved receipt memory candidates: " + str(inventory["approved_receipt_memory_candidate_count"]),
        "- approved runtime memory candidates: " + str(inventory["runtime_memory_candidate_count"]),
        "- all runtime memory candidates: " + str(inventory["all_runtime_memory_candidate_count"]),
        "- pending unapproved memory candidates: " + str(inventory["pending_unapproved_memory_candidate_count"]),
        "- counts match: " + str(inventory["counts_match"]),
        "- finding: " + str(inventory["finding"]),
        "",
        "Extra runtime candidates:",
    ]
    extras = inventory["extra_runtime_candidates"]
    if extras:
        for item in extras:
            lines.append("- " + str(item.get("source_path", "")))
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Missing runtime candidates:")
    missing = inventory["missing_runtime_candidates"]
    if missing:
        for item in missing:
            lines.append("- " + str(item.get("source_path", "")))
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Safety:",
            "- REPORT_ONLY",
            "- NO_MEMORY_PROMOTION",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_APPROVED_MEMORY_WRITE",
            "- NO_CANDIDATE_APPROVAL",
            "- NO_FIX_APPLY",
            "- NO_SOURCE_MUTATION",
            "- NO_QUEUE_ROUTE_MUTATION",
            "- NO_PROVIDER_CALL",
            "- NO_MODEL_RUNTIME",
            "- NO_BACKGROUND_WORKER",
        ]
    )
    return "\n".join(lines)


def render_inventory_report() -> str:
    inventory = build_inventory()
    body = render_inventory_status()
    return "\n".join(
        [
            "# Engel Memory Candidate Inventory",
            "",
            body,
            "",
            "Candidate Paths:",
            *["- " + str(item.get("source_path", "")) for item in inventory["runtime_candidates"]],
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report-only Engel memory candidate inventory.")
    parser.add_argument("command", choices=("status", "json", "report"), nargs="?", default="status")
    args = parser.parse_args(argv)
    if args.command == "json":
        print(json.dumps(build_inventory(), indent=2, sort_keys=True))
    elif args.command == "report":
        print(render_inventory_report())
    else:
        print(render_inventory_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
