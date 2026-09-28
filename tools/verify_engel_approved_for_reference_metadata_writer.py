#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "engel_approved_for_reference_metadata_writer.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_APPROVED_FOR_REFERENCE_METADATA_WRITER_V1.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_approved_for_reference_metadata_writer as writer  # noqa: E402
import engel_human_review_receipt_writer as receipt_writer  # noqa: E402
import engel_manual_library_queue_record_writer as queue_writer  # noqa: E402


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sample_receipt_metadata() -> dict:
    return {
        "material_identity": {
            "material_id": "VERIFY_REFERENCE_MATERIAL_001",
            "title": "Verifier approved reference metadata sample",
            "author_or_origin": "verifier",
            "source_type": "metadata_only_verifier_sample",
            "source_notes": "Verifier sample only; no material content is read.",
            "original_location": "REFERENCE_ONLY_ORIGINAL_LOCATION",
            "intended_reference_location": "REFERENCE_ONLY_APPROVED_LIBRARY_LOCATION",
            "category": "math",
            "subcategory": "verification",
            "version_or_date": "2099-01-01",
            "file_format": "metadata_only",
            "estimated_scope": "small",
        },
        "human_reviewer": {
            "reviewer_name_or_id": "verifier_human_marker",
            "review_date": "2099-01-02",
            "review_context": "approved-for-reference verifier dry-run",
            "review_depth": "metadata_only",
            "reviewer_confidence": "high",
        },
        "review_decision": {
            "decision": "approved_for_reference",
            "approved_for_reference_only": True,
            "rejected": False,
            "hold_for_later": False,
            "needs_source_clarification": False,
            "unsafe_or_untrusted_content": False,
            "reason_for_decision": "Verifier sample confirms reference-only decision boundaries.",
        },
        "safety_boundary_acknowledgments": {
            "not_trusted_memory_acknowledged": True,
            "no_auto_index_acknowledged": True,
            "no_execution_acknowledged": True,
            "no_training_acknowledged": True,
            "no_runtime_loading_acknowledged": True,
            "no_network_or_provider_action_acknowledged": True,
            "no_startup_or_background_action_acknowledged": True,
        },
        "prompt_injection_content_risk_review": {
            "prompt_injection_risk_observed": False,
            "hostile_instruction_risk": False,
            "hidden_or_embedded_instruction_risk": False,
            "malicious_code_or_command_risk": False,
            "unsafe_external_link_or_download_risk": False,
            "citation_or_source_spoofing_risk": False,
            "poisoned_example_or_bad_training_data_risk": False,
            "risk_notes": "No real material reviewed by verifier.",
        },
        "research_use_boundary": {
            "allowed_use": ["human_guided_research_reference"],
            "disallowed_use": [
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
            ],
            "reference_only_notes": "Reference-only metadata sample.",
            "citation_required": True,
            "license_or_usage_notes": "Verifier sample only.",
            "provenance_notes": "Verifier sample provenance acknowledged for dry-run metadata validation.",
        },
        "engel_memory_boundary": {
            "may_inform_human_guided_research_summary": True,
            "may_not_write_trusted_memory": True,
            "requires_separate_memory_candidate_proposal": True,
            "requires_separate_human_approval_for_memory": True,
            "memory_boundary_notes": "Approved-for-reference is not trusted memory.",
        },
        "math_code_specific_review": {
            "math_claims_need_verification": True,
            "code_examples_not_auto_executable": True,
            "commands_not_auto_runnable": True,
            "package_install_not_allowed": True,
            "technical_accuracy_notes": "Verifier sample only.",
        },
        "future_queen_colony_use_notes": {
            "queen_visibility": "metadata visibility only",
            "future_workflow_notes": "No active workflow.",
            "colony_research_notes": "No colony action.",
            "archive_notes": "No archive action.",
            "long_term_storage_relevance": "No storage probing.",
            "swarm_or_mycelium_risk_notes": "No runtime behavior.",
        },
        "final_human_signoff": {
            "final_decision": "approved_for_reference",
            "reviewer_signature_or_marker": "verifier_marker",
            "timestamp": "2099-01-02T00:00:00Z",
            "next_manual_action": "Metadata may be marked approved for reference only.",
            "no_automation_confirmed": True,
        },
    }


def human_confirmation() -> dict:
    return {
        "queue_record_exists": True,
        "human_review_receipt_exists": True,
        "receipt_says_approved_for_reference": True,
        "source_provenance_acceptable": True,
        "safety_flags_resolved_or_acknowledged": True,
        "reference_only_approval_confirmed": True,
        "not_trusted_memory_confirmed": True,
        "no_training_indexing_runtime_execution_confirmed": True,
        "no_material_import_confirmed": True,
        "no_automation_triggered_confirmed": True,
    }


def build_receipt_record() -> dict:
    return receipt_writer.build_receipt_record_metadata(
        sample_receipt_metadata(),
        approval_token=receipt_writer.APPROVAL_TOKEN,
    )


def build_queue_record(receipt_record: dict) -> dict:
    draft = {
        "queue_record_id": "VERIFY_APPROVED_REFERENCE_QUEUE_001",
        "material_id": receipt_record["material_id"],
        "title": receipt_record["title"],
        "category": receipt_record["category"],
        "subcategory": "verification_only",
        "source_type": "verifier_fake_metadata",
        "source_notes": "Verifier-created metadata only; no material file is referenced or opened.",
        "original_location_reference": "FAKE_REFERENCE_ONLY_DO_NOT_USE",
        "intended_reference_location_reference": "FAKE_APPROVED_LIBRARY_REFERENCE_ONLY_DO_NOT_USE",
        "submitted_by": "verifier",
        "submitted_date": "2099-01-01",
        "review_state": "approved_for_reference",
        "priority": "normal",
        "reviewer_assigned": "human_required",
        "human_review_required": True,
        "receipt_required": True,
        "receipt_reference": receipt_record["receipt_record_id"],
        "receipt_status": "receipt_complete",
        "safety_flags": ["verifier_dry_run_only", "metadata_only", "reference_only"],
        "prompt_injection_risk": "acknowledged_no_unresolved_risk_in_verifier_sample",
        "provenance_risk": "acknowledged_no_unresolved_risk_in_verifier_sample",
        "license_or_usage_risk": "acknowledged_no_unresolved_risk_in_verifier_sample",
        "malicious_code_or_command_risk": "acknowledged_no_unresolved_risk_in_verifier_sample",
        "math_verification_needed": True,
        "code_execution_risk": "not_applicable",
        "duplicate_check_needed": False,
        "external_link_risk": "not_applicable",
        "sensitive_content_flag": False,
        "allowed_uses": [
            "human_review_tracking",
            "manual_research_triage",
            "human_guided_reference_decision",
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
            "real_approval_creation",
            "real_receipt_creation",
        ],
        "not_trusted_memory": True,
        "no_automation_triggered": True,
        "next_manual_action": "Human-approved reference metadata write only.",
        "created_by_human_confirmation": True,
        "draft_only": True,
        "not_real_queue_record_until_approved": True,
    }
    return queue_writer.build_queue_record_metadata(draft, approval_token=queue_writer.APPROVAL_TOKEN)


def check_required_files() -> tuple[str, str]:
    require(WRITER.exists(), "missing approved-for-reference metadata writer")
    require(REPORT.exists(), "missing approved-for-reference metadata writer report")
    return read(WRITER), read(REPORT)


def check_required_text(combined: str) -> None:
    for status in [
        "REFERENCE_METADATA_WRITER_ONLY",
        "HUMAN_APPROVAL_REQUIRED",
        "APPROVAL_TOKEN_REQUIRED",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing writer status: " + status)

    require("APPROVE_MARK_APPROVED_FOR_REFERENCE" in combined, "missing approval token")

    for phrase in [
        "reference metadata writer only",
        "exact approval token",
        "bounded repo-local reference metadata",
        "metadata only",
        "not trusted memory",
        "not training permission",
        "not runtime permission",
        "not execution permission",
        "no material content",
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
        "iterdir",
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
    forbidden_function_fragments = [
        "import_material",
        "copy_material",
        "scan_material",
        "index_material",
        "write_trusted_memory",
        "start_worker",
        "execute_material",
        "train_model",
    ]
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
        elif isinstance(node, ast.FunctionDef):
            lowered = node.name.lower()
            for fragment in forbidden_function_fragments:
                require(fragment not in lowered, "forbidden active function name in writer: " + node.name)


def check_writer_constants() -> None:
    require(writer.APPROVAL_TOKEN == "APPROVE_MARK_APPROVED_FOR_REFERENCE", "approval token constant mismatch")
    require(
        writer.REFERENCE_METADATA_ROOT == ROOT / "memory" / "approved_library_reference_metadata",
        "reference metadata root mismatch",
    )
    for status in [
        "REFERENCE_METADATA_WRITER_ONLY",
        "HUMAN_APPROVAL_REQUIRED",
        "APPROVAL_TOKEN_REQUIRED",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in writer.WRITER_STATUS, "writer status missing: " + status)
    for label in [
        "APPROVED_FOR_REFERENCE_METADATA_ONLY",
        "REFERENCE_ONLY",
        "NOT_TRUSTED_MEMORY",
        "NOT_TRAINING_PERMISSION",
        "NOT_RUNTIME_PERMISSION",
        "NOT_EXECUTION_PERMISSION",
        "NO_MATERIAL_CONTENT",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in writer.REFERENCE_METADATA_LABELS, "writer label missing: " + label)


def expect_token_rejection(queue_record: dict, receipt_record: dict, token: str) -> None:
    try:
        writer.write_approved_for_reference_metadata(
            queue_record,
            receipt_record,
            human_confirmation(),
            approval_token=token,
            dry_run=True,
        )
    except writer.ApprovedForReferenceApprovalError:
        return
    raise CheckFailure("writer accepted missing or wrong approval token")


def check_dry_run_smoke() -> None:
    receipt_record = build_receipt_record()
    queue_record = build_queue_record(receipt_record)

    expect_token_rejection(queue_record, receipt_record, "")
    expect_token_rejection(queue_record, receipt_record, "APPROVE_MARK_APPROVED_FOR_REFERENCE ")
    expect_token_rejection(queue_record, receipt_record, "APPROVE_MARK_APPROVED_FOR_REFERENCES")

    result = writer.write_approved_for_reference_metadata(
        queue_record,
        receipt_record,
        human_confirmation(),
        approval_token=writer.APPROVAL_TOKEN,
        dry_run=True,
    )
    require(result["dry_run"] is True, "smoke result must be dry-run")
    require(result["written"] is False, "dry-run smoke must not write reference metadata")
    require(str(writer.REFERENCE_METADATA_ROOT) in result["output_path"], "dry-run path must stay under reference metadata root")

    record = result["record"]
    require(record["record_labels"] == writer.REFERENCE_METADATA_LABELS, "record labels mismatch")
    require(record["reference_decision"] == "approved_for_reference", "reference decision mismatch")
    require(record["metadata_boundary"]["not_trusted_memory"] is True, "not trusted memory boundary missing")
    require(record["metadata_boundary"]["no_material_content"] is True, "no material content boundary missing")
    require(record["approval_boundary"]["approved_for_reference_is_not_training_permission"] is True, "training boundary missing")

    bad_receipt = dict(receipt_record)
    bad_receipt["decision"] = "hold_for_later"
    try:
        writer.write_approved_for_reference_metadata(
            queue_record,
            bad_receipt,
            human_confirmation(),
            approval_token=writer.APPROVAL_TOKEN,
            dry_run=True,
        )
    except writer.ApprovedForReferenceValidationError:
        pass
    else:
        raise CheckFailure("writer accepted receipt without approved_for_reference decision")

    bad_queue = dict(queue_record)
    bad_queue["receipt_reference"] = "different_receipt"
    try:
        writer.write_approved_for_reference_metadata(
            bad_queue,
            receipt_record,
            human_confirmation(),
            approval_token=writer.APPROVAL_TOKEN,
            dry_run=True,
        )
    except writer.ApprovedForReferenceValidationError:
        pass
    else:
        raise CheckFailure("writer accepted mismatched queue/receipt reference")

    bad_confirmation = human_confirmation()
    bad_confirmation["not_trusted_memory_confirmed"] = False
    try:
        writer.write_approved_for_reference_metadata(
            queue_record,
            receipt_record,
            bad_confirmation,
            approval_token=writer.APPROVAL_TOKEN,
            dry_run=True,
        )
    except writer.ApprovedForReferenceValidationError:
        pass
    else:
        raise CheckFailure("writer accepted missing human boundary confirmation")

    try:
        writer.reference_metadata_output_path(record["reference_decision_record_id"], ROOT / "reports")
    except writer.ApprovedForReferencePathError:
        pass
    else:
        raise CheckFailure("writer accepted output outside bounded reference metadata root")


def main() -> int:
    try:
        source, report = check_required_files()
        check_required_text(source + "\n" + report)
        check_ast_safety(source)
        check_writer_constants()
        check_dry_run_smoke()
    except (
        CheckFailure,
        SyntaxError,
        writer.ApprovedForReferenceWriterError,
        queue_writer.QueueRecordWriterError,
        receipt_writer.HumanReviewReceiptWriterError,
    ) as exc:
        print("FAIL: Engel Approved-for-Reference Metadata Writer V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Approved-for-Reference Metadata Writer V1 verifier")
    print("- writer exists and requires exact APPROVE_MARK_APPROVED_FOR_REFERENCE token")
    print("- queue metadata and receipt metadata references are validated")
    print("- dry-run smoke created no reference metadata file")
    print("- writer is reference metadata only and not trusted memory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
