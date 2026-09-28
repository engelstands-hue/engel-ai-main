#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE_JSON = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_MANUAL_REVIEW_QUEUE_CONTRACT_V1.json"
QUEUE_MD = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_MANUAL_REVIEW_QUEUE_CONTRACT_V1.md"
THIS_FILE = Path(__file__).resolve()


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_contract() -> tuple[dict, str, str]:
    require(QUEUE_JSON.exists(), "missing manual review queue contract JSON")
    require(QUEUE_MD.exists(), "missing manual review queue contract Markdown")
    payload = json.loads(read(QUEUE_JSON))
    md = read(QUEUE_MD)
    return payload, json.dumps(payload, sort_keys=True), md


def check_required_statuses(payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    for status in [
        "CONTRACT_ONLY",
        "QUEUE_SHAPE_ONLY",
        "HUMAN_REVIEW_REQUIRED",
        "NO_ACTIVE_QUEUE_RUNTIME",
        "NO_AUTOMATIC_IMPORT",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing required status: " + status)


def check_required_lists(payload: dict, payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    for area in [
        "candidate_materials",
        "review_pending",
        "in_human_review",
        "approved_for_reference",
        "rejected",
        "hold_for_later",
        "needs_source_clarification",
        "unsafe_or_untrusted_content",
        "receipt_required",
        "archived_queue_records",
    ]:
        require(area in payload.get("queue_areas", []), "queue area missing from JSON: " + area)
        require(area in combined, "queue area missing from text: " + area)

    for state in [
        "candidate_material_recorded",
        "human_review_pending",
        "in_human_review",
        "approved_for_reference",
        "rejected",
        "hold_for_later",
        "needs_source_clarification",
        "unsafe_or_untrusted_content",
        "receipt_missing",
        "receipt_complete",
    ]:
        require(state in payload.get("review_states", []), "review state missing from JSON: " + state)
        require(state in combined, "review state missing from text: " + state)

    for category in ["math", "coding_languages"]:
        require(category in payload.get("categories", []), "category missing from JSON: " + category)
        require(category in combined, "category missing from text: " + category)


def check_record_fields(payload: dict, payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    fields = set(payload.get("queue_record_fields", []))
    for field in [
        "queue_record_id",
        "material_id",
        "title",
        "category",
        "subcategory",
        "source_type",
        "source_notes",
        "original_location_reference",
        "intended_reference_location_reference",
        "submitted_by",
        "submitted_date",
        "review_state",
        "priority",
        "reviewer_assigned",
        "human_review_required",
        "receipt_required",
        "receipt_reference",
        "safety_flags",
        "prompt_injection_risk",
        "provenance_risk",
        "license_or_usage_risk",
        "malicious_code_or_command_risk",
        "math_verification_needed",
        "code_execution_risk",
        "allowed_uses",
        "disallowed_uses",
        "not_trusted_memory",
        "no_automation_triggered",
        "notes",
        "next_manual_action",
    ]:
        require(field in fields, "queue record field missing from JSON: " + field)
        require(field in combined, "queue record field missing from text: " + field)


def check_uses(payload: dict, payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    for allowed in [
        "human_review_tracking",
        "manual_research_triage",
        "human_guided_reference_decision",
        "future_review_candidate",
    ]:
        require(allowed in payload.get("allowed_uses", []), "allowed use missing from JSON: " + allowed)
        require(allowed in combined, "allowed use missing from text: " + allowed)

    for disallowed in [
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
    ]:
        require(disallowed in payload.get("disallowed_uses", []), "disallowed use missing from JSON: " + disallowed)
        require(disallowed in combined, "disallowed use missing from text: " + disallowed)


def check_safety_statements(payload_text: str, md: str) -> None:
    combined = (payload_text + "\n" + md).lower()
    for phrase in [
        "queue record is not an approval",
        "queue record is not a receipt",
        "queue record is not trusted memory",
        "no active queue runtime",
        "no automation is triggered",
        "human review is required",
        "human review receipt is required",
        "approved for reference is not trusted memory",
        "separate memory candidate proposal",
    ]:
        require(phrase in combined, "missing safety statement: " + phrase)


def check_safety_boundary(payload: dict) -> None:
    boundary = payload.get("safety_boundary")
    require(isinstance(boundary, dict), "missing safety boundary")
    for key in [
        "queue_records_are_references_metadata_only",
        "queue_record_is_not_approval",
        "queue_record_is_not_receipt",
        "queue_record_is_not_trusted_memory",
        "queue_record_does_not_permit_import",
        "human_review_required_before_reference_approval",
        "human_review_receipt_required_before_reference_approval",
        "approved_for_reference_is_not_trusted_memory",
        "separate_memory_candidate_proposal_required",
        "no_active_queue_runtime",
        "no_queue_worker",
        "no_automation_triggered",
        "no_automatic_import",
        "no_copy",
        "no_move",
        "no_sync",
        "no_recursive_scan",
        "no_indexing",
        "no_embedding",
        "no_summarization",
        "no_execution",
        "no_training",
        "no_runtime_loading",
        "no_startup_behavior",
        "no_provider_network_calls",
        "no_package_manager",
        "no_queen_runtime_behavior",
        "no_trusted_memory_write",
    ]:
        require(boundary.get(key) is True, "safety boundary must be true: " + key)


def check_receipt_linkage(payload: dict) -> None:
    linkage = payload.get("required_receipt_linkage")
    require(isinstance(linkage, dict), "missing required receipt linkage")
    for key in [
        "receipt_required_for_approved_for_reference",
        "receipt_template",
        "receipt_examples",
        "receipt_reference_field",
        "receipt_missing_state",
        "receipt_complete_state",
        "receipt_boundary",
    ]:
        require(key in linkage, "receipt linkage missing: " + key)
    require(linkage.get("receipt_required_for_approved_for_reference") is True, "receipt linkage must require receipt")


def check_inactive_denials(payload: dict) -> None:
    denials = payload.get("inactive_behavior_denials")
    require(isinstance(denials, dict), "inactive behavior denials missing")
    for key in [
        "scan_folders",
        "import_files",
        "copy_materials",
        "move_materials",
        "sync_storage",
        "index_content",
        "embed_content",
        "summarize_real_materials",
        "execute_content",
        "train_models",
        "fine_tune_models",
        "load_runtime_content",
        "write_trusted_memory",
        "start_queue_runtime",
        "start_queue_worker",
        "start_background_worker",
        "call_provider_api",
        "call_network",
        "start_browser",
        "use_package_manager",
        "probe_storage_locations",
        "change_routes",
        "change_startup",
        "activate_queen_runtime",
        "load_model",
    ]:
        require(denials.get(key) is False, "inactive behavior denial must be false: " + key)


def check_forbidden_active_behavior(payload_text: str, md: str) -> None:
    combined = (payload_text + "\n" + md).lower()
    blocked_fragments = [
        "sh" + "util",
        "copy" + "tree",
        "os." + "walk",
        "r" + "glob",
        "sub" + "process",
        "req" + "uests",
        "url" + "lib",
        "soc" + "ket",
        "active queue worker " + "implementation",
        "file copy " + "implementation",
        "file move " + "implementation",
        "scan " + "implementation",
        "index " + "implementation",
        "vector " + "implementation",
        "model training " + "implementation",
        "runtime loader " + "implementation",
        "provider call " + "implementation",
    ]
    for fragment in blocked_fragments:
        require(fragment not in combined, "forbidden active behavior text found: " + fragment)

    source = read(THIS_FILE)
    tree = ast.parse(source)
    blocked_import_roots = {
        "sh" + "util",
        "sub" + "process",
        "req" + "uests",
        "url" + "lib",
        "soc" + "ket",
    }
    blocked_call_names = {
        "copy" + "tree",
        "r" + "glob",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                require(root not in blocked_import_roots, "verifier imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            require(root not in blocked_import_roots, "verifier imports blocked module: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                require(func.id not in blocked_call_names, "verifier calls blocked function: " + func.id)
            elif isinstance(func, ast.Attribute):
                require(func.attr not in blocked_call_names, "verifier calls blocked method: " + func.attr)


def main() -> int:
    try:
        payload, payload_text, md = load_contract()
        require(payload.get("schema_name") == "engel_approved_library_manual_review_queue_contract_v1", "schema name mismatch")
        require(payload.get("schema_version") == "1.0", "schema version mismatch")
        check_required_statuses(payload_text, md)
        check_required_lists(payload, payload_text, md)
        check_record_fields(payload, payload_text, md)
        check_uses(payload, payload_text, md)
        check_safety_statements(payload_text, md)
        check_safety_boundary(payload)
        check_receipt_linkage(payload)
        check_inactive_denials(payload)
        check_forbidden_active_behavior(payload_text, md)
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Approved Library Manual Review Queue Contract V1 verifier")
        print("- " + str(exc))
        return 1
    print("PASS: Engel Approved Library Manual Review Queue Contract V1 verifier")
    print("- contract JSON and Markdown exist and parse")
    print("- queue areas, record fields, review states, categories, and receipt linkage are present")
    print("- queue records remain metadata only, not approvals, receipts, trusted memory, or automation")
    print("- no active queue runtime, import, indexing, execution, training, runtime loading, or trusted-memory behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
