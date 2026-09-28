#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_HUMAN_REVIEW_RECEIPT_WRITE_APPROVAL_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_HUMAN_REVIEW_RECEIPT_WRITE_APPROVAL_CONTRACT_V1.md"
WRITER = ROOT / "engel_human_review_receipt_writer.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_HUMAN_REVIEW_RECEIPT_WRITER_V1.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_human_review_receipt_writer as writer  # noqa: E402


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
            "material_id": "VERIFY_RECEIPT_MATERIAL_001",
            "title": "Verifier receipt metadata only",
            "author_or_origin": "verifier",
            "source_type": "metadata_only_verifier_sample",
            "source_notes": "Verifier sample only; no material content is read or written.",
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
            "review_context": "verifier dry-run",
            "review_depth": "metadata_only",
            "reviewer_confidence": "medium",
        },
        "review_decision": {
            "decision": "hold_for_later",
            "approved_for_reference_only": False,
            "rejected": False,
            "hold_for_later": True,
            "needs_source_clarification": False,
            "unsafe_or_untrusted_content": False,
            "reason_for_decision": "Verifier dry-run sample remains metadata only.",
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
            "allowed_use": ["future_review_candidate"],
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
            "reference_only_notes": "Metadata-only verifier sample.",
            "citation_required": False,
            "license_or_usage_notes": "Not applicable to verifier sample.",
            "provenance_notes": "Verifier sample only.",
        },
        "engel_memory_boundary": {
            "may_inform_human_guided_research_summary": False,
            "may_not_write_trusted_memory": True,
            "requires_separate_memory_candidate_proposal": True,
            "requires_separate_human_approval_for_memory": True,
            "memory_boundary_notes": "No trusted memory write.",
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
            "final_decision": "hold_for_later",
            "reviewer_signature_or_marker": "verifier_marker",
            "timestamp": "2099-01-02T00:00:00Z",
            "next_manual_action": "Human reviewer decides the next manual step.",
            "no_automation_confirmed": True,
        },
    }


def check_required_files() -> tuple[dict, str, str, str, str]:
    for path in [CONTRACT_JSON, CONTRACT_MD, WRITER, REPORT]:
        require(path.exists(), "missing required file: " + str(path))
    payload = json.loads(read(CONTRACT_JSON))
    return payload, json.dumps(payload, sort_keys=True), read(CONTRACT_MD), read(WRITER), read(REPORT)


def check_required_text(combined: str) -> None:
    for status in [
        "RECEIPT_METADATA_WRITER_ONLY",
        "HUMAN_APPROVAL_REQUIRED",
        "APPROVAL_TOKEN_REQUIRED",
        "NO_APPROVAL_ACTION",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing receipt writer status: " + status)

    require("APPROVE_WRITE_HUMAN_REVIEW_RECEIPT" in combined, "missing required approval token")

    for phrase in [
        "metadata only",
        "bounded repo-local receipt records",
        "does not approve material",
        "not trusted memory",
        "no trusted-memory write",
        "no material content",
        "no material import",
        "no worker or runtime",
    ]:
        require(phrase in combined.lower(), "missing receipt writer boundary wording: " + phrase)


def check_contract_payload(payload: dict) -> None:
    require(payload.get("schema_name") == "engel_human_review_receipt_write_approval_contract_v1", "contract schema_name mismatch")
    token = payload.get("approval_token", {})
    require(token.get("token") == writer.APPROVAL_TOKEN, "contract token mismatch")
    for key in [
        "exact_match_required",
        "metadata_write_only",
        "does_not_approve_material_for_reference",
        "does_not_import_material",
        "does_not_write_trusted_memory",
        "does_not_trigger_learning",
        "does_not_trigger_runtime",
    ]:
        require(token.get(key) is True, "contract token flag missing: " + key)

    boundary = payload.get("writer_boundary", {})
    for key in [
        "requires_exact_approval_token",
        "bounded_repo_local_receipt_records_only",
        "no_material_import",
        "no_material_copy",
        "no_material_move",
        "no_material_scan",
        "no_indexing",
        "no_embedding",
        "no_execution",
        "no_training",
        "no_runtime_loading",
        "no_worker_or_runtime_start",
        "no_trusted_memory_write",
    ]:
        require(boundary.get(key) is True, "contract writer boundary flag missing: " + key)


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
        "approve_material",
        "import_material",
        "copy_material",
        "scan_material",
        "index_material",
        "write_trusted_memory",
        "start_worker",
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
    require(writer.APPROVAL_TOKEN == "APPROVE_WRITE_HUMAN_REVIEW_RECEIPT", "approval token constant mismatch")
    require(writer.RECEIPT_RECORDS_ROOT == ROOT / "memory" / "approved_library_human_review_receipts", "receipt root mismatch")
    for status in [
        "RECEIPT_METADATA_WRITER_ONLY",
        "HUMAN_APPROVAL_REQUIRED",
        "APPROVAL_TOKEN_REQUIRED",
        "NO_APPROVAL_ACTION",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in writer.RECEIPT_WRITER_STATUS, "writer status constant missing: " + status)

    for label in [
        "REAL_RECEIPT_METADATA_ONLY",
        "NOT_MATERIAL_APPROVAL",
        "NOT_TRUSTED_MEMORY",
        "NO_MATERIAL_CONTENT",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in writer.RECEIPT_RECORD_LABELS, "writer label missing: " + label)


def expect_token_rejection(receipt: dict, token: str) -> None:
    try:
        writer.write_receipt_record_metadata(receipt, approval_token=token, dry_run=True)
    except writer.HumanReviewReceiptApprovalError:
        return
    raise CheckFailure("writer accepted missing or wrong approval token")


def check_dry_run_smoke() -> None:
    receipt = sample_receipt_metadata()
    expect_token_rejection(receipt, "")
    expect_token_rejection(receipt, "APPROVE_WRITE_HUMAN_REVIEW_RECEIPT ")
    expect_token_rejection(receipt, "APPROVE_WRITE_HUMAN_REVIEW_RECEIPTS")

    result = writer.write_receipt_record_metadata(receipt, approval_token=writer.APPROVAL_TOKEN, dry_run=True)
    require(result["dry_run"] is True, "smoke result must be dry-run")
    require(result["written"] is False, "dry-run smoke must not write a receipt")
    require(str(writer.RECEIPT_RECORDS_ROOT) in result["output_path"], "output path must be bounded receipt root")

    record = result["record"]
    require(record["record_labels"] == writer.RECEIPT_RECORD_LABELS, "record labels mismatch")
    require(record["metadata_boundary"]["receipt_metadata_writer_only"] is True, "metadata writer boundary missing")
    require(record["metadata_boundary"]["no_material_content"] is True, "no material content boundary missing")
    require(record["approval_boundary"]["receipt_write_is_not_material_approval"] is True, "material approval boundary missing")

    invalid = sample_receipt_metadata()
    invalid["safety_boundary_acknowledgments"]["no_execution_acknowledged"] = False
    try:
        writer.write_receipt_record_metadata(invalid, approval_token=writer.APPROVAL_TOKEN, dry_run=True)
    except writer.HumanReviewReceiptValidationError:
        pass
    else:
        raise CheckFailure("writer accepted receipt without required safety acknowledgment")

    try:
        writer.receipt_record_output_path(record["receipt_record_id"], ROOT / "reports")
    except writer.HumanReviewReceiptPathError:
        pass
    else:
        raise CheckFailure("writer accepted output outside bounded receipt root")


def main() -> int:
    try:
        payload, payload_text, contract_md, source, report = check_required_files()
        combined = payload_text + "\n" + contract_md + "\n" + source + "\n" + report
        check_required_text(combined)
        check_contract_payload(payload)
        check_ast_safety(source)
        check_writer_constants()
        check_dry_run_smoke()
    except (CheckFailure, json.JSONDecodeError, SyntaxError, writer.HumanReviewReceiptWriterError) as exc:
        print("FAIL: Engel Human Review Receipt Writer V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Human Review Receipt Writer V1 verifier")
    print("- approval contract, writer, and report exist")
    print("- writer requires exact APPROVE_WRITE_HUMAN_REVIEW_RECEIPT token")
    print("- dry-run smoke created no receipt file and performed no material operations")
    print("- writer is metadata-only and does not approve material or write trusted memory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
