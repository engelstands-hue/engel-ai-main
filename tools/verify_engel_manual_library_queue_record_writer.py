#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "engel_manual_library_queue_record_writer.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MANUAL_LIBRARY_QUEUE_RECORD_WRITER_V1.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_manual_library_queue_record_writer as writer  # noqa: E402


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sample_draft_metadata() -> dict:
    return {
        "queue_record_id": "VERIFY_DRY_RUN_QUEUE_RECORD_001",
        "material_id": "VERIFY_DRY_RUN_MATERIAL_001",
        "title": "Verifier dry-run metadata record",
        "category": "math",
        "subcategory": "verification_only",
        "source_type": "verifier_fake_metadata",
        "source_notes": "Verifier-created metadata only; no material file is referenced or opened.",
        "original_location_reference": "FAKE_REFERENCE_ONLY_DO_NOT_USE",
        "intended_reference_location_reference": "FAKE_APPROVED_LIBRARY_REFERENCE_ONLY_DO_NOT_USE",
        "submitted_by": "verifier",
        "submitted_date": "2099-01-01",
        "review_state": "human_review_pending",
        "priority": "normal",
        "reviewer_assigned": "human_required",
        "human_review_required": True,
        "receipt_required": True,
        "receipt_reference": "receipt_missing",
        "receipt_status": "receipt_missing",
        "safety_flags": ["verifier_dry_run_only", "metadata_only"],
        "prompt_injection_risk": "not_assessed_verifier_fake_metadata",
        "provenance_risk": "not_assessed_verifier_fake_metadata",
        "license_or_usage_risk": "not_assessed_verifier_fake_metadata",
        "malicious_code_or_command_risk": "not_assessed_verifier_fake_metadata",
        "math_verification_needed": True,
        "code_execution_risk": "not_applicable",
        "duplicate_check_needed": False,
        "external_link_risk": "not_applicable",
        "sensitive_content_flag": False,
        "allowed_uses": [
            "human_review_tracking",
            "manual_research_triage",
            "future_review_candidate",
        ],
        "disallowed_uses": [
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
            "real_queue_creation",
            "real_approval_creation",
            "real_receipt_creation",
        ],
        "not_trusted_memory": True,
        "no_automation_triggered": True,
        "next_manual_action": "Human reviewer decides whether to proceed outside verifier dry run.",
        "created_by_human_confirmation": True,
        "draft_only": True,
        "not_real_queue_record_until_approved": True,
    }


def check_required_files() -> tuple[str, str]:
    require(WRITER.exists(), "missing manual library queue record writer")
    require(REPORT.exists(), "missing manual library queue record writer report")
    return read(WRITER), read(REPORT)


def check_required_text(combined: str) -> None:
    for status in [
        "METADATA_WRITER_ONLY",
        "HUMAN_APPROVAL_REQUIRED",
        "APPROVAL_TOKEN_REQUIRED",
        "QUEUE_RECORD_METADATA_ONLY",
        "NO_MATERIAL_IMPORT",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing writer status: " + status)

    require("APPROVE_CREATE_LIBRARY_QUEUE_RECORD" in combined, "missing approval token")

    for label in [
        "REAL_QUEUE_RECORD_METADATA_ONLY",
        "NOT_APPROVAL",
        "NOT_RECEIPT",
        "NOT_TRUSTED_MEMORY",
        "NO_MATERIAL_CONTENT",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in combined, "missing metadata-only record label: " + label)

    for phrase in [
        "metadata writer only",
        "exact approval token",
        "bounded repo-local queue metadata folder",
        "metadata only",
        "not trusted memory",
        "no material content",
        "no material operations",
    ]:
        require(phrase in combined.lower(), "missing boundary wording: " + phrase)


def check_ast_safety(source: str) -> None:
    tree = ast.parse(source)
    forbidden_imports = {
        "os",
        "shutil",
        "subprocess",
        "requests",
        "urllib",
        "socket",
        "glob",
    }
    forbidden_calls = {
        "open",
        "read_text",
        "copy",
        "copytree",
        "move",
        "rename",
        "replace",
        "unlink",
        "rmdir",
        "rglob",
        "glob",
        "walk",
        "run",
        "Popen",
        "system",
        "startfile",
        "exec",
        "eval",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                require(root not in forbidden_imports, "forbidden import in writer: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root not in forbidden_imports, "forbidden import-from in writer: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            require(name not in forbidden_calls, "forbidden active call in writer: " + name)


def check_writer_constants() -> None:
    require(writer.APPROVAL_TOKEN == "APPROVE_CREATE_LIBRARY_QUEUE_RECORD", "approval token constant mismatch")
    require(writer.QUEUE_METADATA_ROOT == ROOT / "memory" / "approved_library_manual_review_queue", "queue root must be repo-local memory queue metadata folder")
    require("METADATA_WRITER_ONLY" in writer.WRITER_STATUS, "writer status missing METADATA_WRITER_ONLY")
    require("APPROVAL_TOKEN_REQUIRED" in writer.WRITER_STATUS, "writer status missing APPROVAL_TOKEN_REQUIRED")
    for label in [
        "REAL_QUEUE_RECORD_METADATA_ONLY",
        "NOT_APPROVAL",
        "NOT_RECEIPT",
        "NOT_TRUSTED_MEMORY",
        "NO_MATERIAL_CONTENT",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in writer.RECORD_REQUIRED_LABELS, "writer label missing: " + label)


def expect_approval_rejection(draft: dict, token: str) -> None:
    try:
        writer.write_queue_record_metadata(draft, approval_token=token, dry_run=True)
    except writer.QueueRecordApprovalError:
        return
    raise CheckFailure("writer accepted missing or wrong approval token")


def check_smoke_dry_run() -> None:
    draft = sample_draft_metadata()
    expect_approval_rejection(draft, "")
    expect_approval_rejection(draft, "APPROVE_CREATE_LIBRARY_QUEUE_RECORD ")
    expect_approval_rejection(draft, "APPROVE_CREATE_LIBRARY_QUEUE_RECORDS")

    result = writer.write_queue_record_metadata(
        draft,
        approval_token=writer.APPROVAL_TOKEN,
        dry_run=True,
    )
    require(result["dry_run"] is True, "smoke result must be dry-run")
    require(result["written"] is False, "dry-run smoke must not write a record")
    require(str(writer.QUEUE_METADATA_ROOT) in result["output_path"], "dry-run output path must stay in bounded queue root")

    record = result["record"]
    require(record["queue_record_id"] == draft["queue_record_id"], "record id mismatch")
    require(record["record_labels"] == writer.RECORD_REQUIRED_LABELS, "record labels mismatch")
    require(record["metadata_only_boundary"]["queue_record_metadata_only"] is True, "metadata-only boundary missing")
    require(record["metadata_only_boundary"]["no_material_content"] is True, "no material content boundary missing")
    require(record["approval_boundary"]["approval_token_name"] == writer.APPROVAL_TOKEN, "approval token name missing in boundary")

    bad_category = dict(draft)
    bad_category["category"] = "external_materials"
    try:
        writer.write_queue_record_metadata(bad_category, approval_token=writer.APPROVAL_TOKEN, dry_run=True)
    except writer.QueueRecordValidationError:
        pass
    else:
        raise CheckFailure("writer accepted an unapproved category")

    try:
        writer.queue_record_output_path(draft["queue_record_id"], ROOT / "reports")
    except writer.QueueRecordPathError:
        pass
    else:
        raise CheckFailure("writer accepted output outside bounded queue metadata root")


def main() -> int:
    try:
        source, report = check_required_files()
        check_required_text(source + "\n" + report)
        check_ast_safety(source)
        check_writer_constants()
        check_smoke_dry_run()
    except (CheckFailure, SyntaxError, writer.QueueRecordWriterError) as exc:
        print("FAIL: Engel Manual Library Queue Record Writer V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Manual Library Queue Record Writer V1 verifier")
    print("- writer exists and requires exact APPROVE_CREATE_LIBRARY_QUEUE_RECORD token")
    print("- bounded output path stays under memory/approved_library_manual_review_queue")
    print("- dry-run smoke created no queue file and performed no material operations")
    print("- writer contains no import/copy/move/scan/index/embed/execute/train/load/provider/trusted-memory behavior")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
