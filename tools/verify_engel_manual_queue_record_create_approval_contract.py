#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_MANUAL_QUEUE_RECORD_CREATE_APPROVAL_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_MANUAL_QUEUE_RECORD_CREATE_APPROVAL_CONTRACT_V1.md"
THIS_FILE = Path(__file__).resolve()


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_contract() -> tuple[dict, str, str]:
    require(CONTRACT_JSON.exists(), "missing approval contract JSON")
    require(CONTRACT_MD.exists(), "missing approval contract Markdown")
    payload = json.loads(read(CONTRACT_JSON))
    md = read(CONTRACT_MD)
    return payload, json.dumps(payload, sort_keys=True), md


def check_statuses(combined: str) -> None:
    for status in [
        "CONTRACT_ONLY",
        "APPROVAL_BOUNDARY_ONLY",
        "HUMAN_APPROVAL_REQUIRED",
        "NO_QUEUE_WRITER",
        "NO_REAL_QUEUE_RECORDS",
        "NO_ACTIVE_QUEUE_RUNTIME",
        "NO_QUEUE_WORKER",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing required status: " + status)


def check_approval_token(payload: dict, combined: str) -> None:
    token = "APPROVE_CREATE_LIBRARY_QUEUE_RECORD"
    require(token in combined, "missing future approval token")

    token_payload = payload.get("future_approval_token", {})
    require(token_payload.get("token") == token, "future approval token mismatch")
    for key in [
        "documented_for_future_use_only",
        "token_alone_is_not_sufficient",
        "requires_future_writer_contract",
        "requires_future_guard_verification",
        "does_not_create_writer",
        "does_not_write_records",
        "does_not_import_material",
        "does_not_approve_reference_use",
        "does_not_create_receipt",
        "does_not_write_trusted_memory",
    ]:
        require(token_payload.get(key) is True, "future token flag must be true: " + key)
    for key in [
        "active_now",
        "activation_in_this_step",
    ]:
        require(token_payload.get(key) is False, "future token flag must be false: " + key)


def check_approval_conditions(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    conditions = payload.get("approval_conditions", [])
    for phrase in [
        "readiness checklist completed",
        "draft report exists",
        "draft schema valid",
        "human confirms no import/copy/move/sync/index/scan/execute/train/load",
        "human confirms not trusted memory",
        "human confirms no automation triggered",
        "human explicitly approves queue metadata write",
        "queue record path is bounded to approved future queue metadata location",
        "queue record contains metadata only, not material contents",
    ]:
        require(phrase in lowered, "missing approval condition text: " + phrase)
        require(phrase in conditions, "missing approval condition in JSON list: " + phrase)

    details = payload.get("approval_condition_details", {})
    for key in [
        "readiness_checklist_completed",
        "draft_report_exists",
        "draft_schema_valid",
        "human_confirms_no_import_copy_move_sync_index_scan_execute_train_load",
        "human_confirms_not_trusted_memory",
        "human_confirms_no_automation_triggered",
        "human_explicitly_approves_queue_metadata_write",
        "queue_record_path_bounded_to_approved_future_queue_metadata_location",
        "queue_record_contains_metadata_only_not_material_contents",
    ]:
        require(details.get(key) is True, "approval condition detail must be true: " + key)


def check_boundary_statements(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    for phrase in [
        "approval contract does not create a writer",
        "approval token is not active",
        "no real queue record is written",
        "no queue runtime exists",
        "no queue worker exists",
        "approval to write metadata is not approval to import material",
        "approval to write metadata is not approval for reference",
        "approval to write metadata is not a human review receipt",
        "approval to write metadata is not trusted memory",
    ]:
        require(phrase in lowered, "missing boundary statement: " + phrase)

    boundary = payload.get("approval_boundary", {})
    for key in [
        "approval_contract_does_not_create_a_writer",
        "approval_token_is_not_active",
        "no_real_queue_record_is_written",
        "no_queue_runtime_exists",
        "no_queue_worker_exists",
        "approval_to_write_metadata_is_not_approval_to_import_material",
        "approval_to_write_metadata_is_not_approval_for_reference",
        "approval_to_write_metadata_is_not_a_human_review_receipt",
        "approval_to_write_metadata_is_not_trusted_memory",
        "approval_to_write_metadata_does_not_trigger_learning",
        "approval_to_write_metadata_does_not_trigger_runtime_loading",
        "approval_to_write_metadata_does_not_trigger_indexing",
        "approval_to_write_metadata_does_not_trigger_execution",
    ]:
        require(boundary.get(key) is True, "approval boundary flag must be true: " + key)

    safety = payload.get("safety_boundary", {})
    for key in [
        "contract_only",
        "approval_boundary_only",
        "human_approval_required",
        "no_queue_writer",
        "no_real_queue_records",
        "no_active_queue_runtime",
        "no_queue_worker",
        "not_trusted_memory",
        "no_learning_trigger",
        "no_runtime_trigger",
        "approval_contract_does_not_create_writer",
        "approval_token_not_active",
        "no_real_queue_record_written",
        "approval_to_write_metadata_not_import_material",
        "approval_to_write_metadata_not_reference_approval",
        "approval_to_write_metadata_not_receipt",
        "approval_to_write_metadata_not_trusted_memory",
        "metadata_only_boundary",
        "material_contents_forbidden",
    ]:
        require(safety.get(key) is True, "safety boundary flag must be true: " + key)


def check_metadata_scope(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    for phrase in [
        "metadata only",
        "not material content",
        "material contents",
        "bounded to an approved future queue metadata location",
    ]:
        require(phrase in lowered, "missing metadata scope wording: " + phrase)

    scope = payload.get("future_metadata_write_scope", {})
    for key in [
        "future_only",
        "queue_record_path_must_be_bounded",
        "approved_future_queue_metadata_location_required",
        "metadata_only",
        "material_contents_forbidden",
        "external_material_file_references_only",
        "source_content_not_copied_into_queue_record",
        "requires_separate_future_implementation_approval",
    ]:
        require(scope.get(key) is True, "metadata scope flag must be true: " + key)


def check_not_authorized(payload: dict, combined: str) -> None:
    for use in [
        "real_queue_creation",
        "real_approval_creation",
        "real_receipt_creation",
        "approved_for_reference_decision",
        "material_import",
        "material_copy",
        "material_move",
        "storage_sync",
        "folder_scan",
        "recursive_scan",
        "indexing",
        "embedding_or_vector_indexing",
        "summarization_of_real_materials",
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
        "trusted_memory_write",
    ]:
        require(use in payload.get("not_authorized_by_contract", []), "not-authorized use missing from JSON: " + use)
        require(use in combined, "not-authorized use missing from text: " + use)


def check_inactive_denials(payload: dict) -> None:
    denials = payload.get("inactive_behavior_denials", {})
    require(isinstance(denials, dict), "inactive behavior denials missing")
    for key, value in denials.items():
        require(value is False, "inactive behavior denial must be false: " + key)
    for key in [
        "create_queue_writer",
        "create_real_queue_record",
        "write_queue_file",
        "activate_approval_token",
        "approve_material",
        "approve_for_reference",
        "create_receipt",
        "import_material",
        "copy_material",
        "move_material",
        "sync_storage",
        "scan_folders",
        "recursive_scan",
        "index_content",
        "embed_content",
        "summarize_real_materials",
        "train_model",
        "fine_tune_model",
        "load_runtime_content",
        "execute_content",
        "call_provider_api",
        "call_network",
        "write_trusted_memory",
        "start_queue_runtime",
        "start_queue_worker",
        "change_routes",
        "change_startup",
        "change_source_behavior",
    ]:
        require(key in denials, "inactive behavior denial missing: " + key)


def check_forbidden_active_behavior(payload_text: str, md: str) -> None:
    combined_lower = (payload_text + "\n" + md).lower()
    forbidden_terms = [
        "sh" + "util",
        "copy" + "tree",
        "os." + "walk",
        "r" + "glob",
        "sub" + "process",
        "req" + "uests",
        "url" + "lib",
        "soc" + "ket",
    ]
    for term in forbidden_terms:
        require(term not in combined_lower, "forbidden active-behavior term found in contract docs: " + term)

    forbidden_phrases = [
        "file write " + "implementation for real queue records",
        "queue writer " + "implementation",
        "queue worker " + "implementation",
        "active queue runtime " + "implementation",
        "scan " + "implementation",
        "index " + "implementation",
        "vector " + "implementation",
        "model training " + "implementation",
        "runtime loader " + "implementation",
        "provider call " + "implementation",
    ]
    for phrase in forbidden_phrases:
        require(phrase not in combined_lower, "forbidden active implementation phrase found: " + phrase)

    source = read(THIS_FILE)
    tree = ast.parse(source)
    allowed_import_roots = {"ast", "json", "pathlib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                require(root in allowed_import_roots, "unexpected import in verifier: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root in allowed_import_roots or node.module == "__future__", "unexpected import-from in verifier: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
                if name == "walk" and isinstance(func.value, ast.Name) and func.value.id == "ast":
                    continue
            require(name not in {"copytree", "move", "rglob", "run", "Popen", "system"}, "forbidden active call in verifier: " + name)


def main() -> int:
    try:
        payload, payload_text, md = load_contract()
        require(payload.get("schema_name") == "engel_manual_queue_record_create_approval_contract_v1", "schema_name mismatch")
        require(payload.get("schema_version") == "1.0", "schema_version mismatch")
        combined = payload_text + "\n" + md
        check_statuses(combined)
        check_approval_token(payload, combined)
        check_approval_conditions(payload, combined)
        check_boundary_statements(payload, combined)
        check_metadata_scope(payload, combined)
        check_not_authorized(payload, combined)
        check_inactive_denials(payload)
        check_forbidden_active_behavior(payload_text, md)
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Manual Queue Record Create Approval Contract V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Manual Queue Record Create Approval Contract V1 verifier")
    print("- approval contract JSON and Markdown exist and parse")
    print("- future approval token is documented but inactive")
    print("- required approval conditions and boundary statements are present")
    print("- no queue writer, queue runtime, queue worker, real queue record, approval, receipt, trusted-memory, learning, or runtime behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
