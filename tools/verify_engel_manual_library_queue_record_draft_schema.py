#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_JSON = ROOT / "memory" / "ENGEL_MANUAL_LIBRARY_QUEUE_RECORD_DRAFT_SCHEMA_V1.json"
SCHEMA_MD = ROOT / "memory" / "ENGEL_MANUAL_LIBRARY_QUEUE_RECORD_DRAFT_SCHEMA_V1.md"
THIS_FILE = Path(__file__).resolve()


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_schema() -> tuple[dict, str, str]:
    require(SCHEMA_JSON.exists(), "missing draft schema JSON")
    require(SCHEMA_MD.exists(), "missing draft schema Markdown")
    payload = json.loads(read(SCHEMA_JSON))
    md = read(SCHEMA_MD)
    return payload, json.dumps(payload, sort_keys=True), md


def check_statuses(combined: str) -> None:
    for status in [
        "SCHEMA_ONLY",
        "DRAFT_RECORD_SHAPE_ONLY",
        "HUMAN_AUTHORITY_REQUIRED",
        "NO_REAL_QUEUE_RECORDS",
        "NO_QUEUE_WRITER",
        "NO_ACTIVE_QUEUE_RUNTIME",
        "NO_QUEUE_WORKER",
        "NO_AUTOMATIC_IMPORT",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing required status: " + status)


def check_schema_fields(payload: dict, combined: str) -> None:
    fields = set(payload.get("schema_fields", []))
    required_fields = [
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
        "receipt_status",
        "safety_flags",
        "prompt_injection_risk",
        "provenance_risk",
        "license_or_usage_risk",
        "malicious_code_or_command_risk",
        "math_verification_needed",
        "code_execution_risk",
        "duplicate_check_needed",
        "external_link_risk",
        "sensitive_content_flag",
        "allowed_uses",
        "disallowed_uses",
        "not_trusted_memory",
        "no_automation_triggered",
        "next_manual_action",
        "created_by_human_confirmation",
        "draft_only",
        "not_real_queue_record_until_approved",
    ]
    definitions = payload.get("field_definitions", {})
    template = payload.get("record_template", {})
    for field in required_fields:
        require(field in fields, "schema field missing from JSON list: " + field)
        require(field in definitions, "schema field missing definition: " + field)
        require(field in template, "schema field missing from record template: " + field)
        require(field in combined, "schema field missing from combined text: " + field)


def check_categories(payload: dict, combined: str) -> None:
    for category in [
        "research_papers",
        "architecture_references",
        "engel_manuals",
        "offline_docs",
        "math",
        "coding_languages",
    ]:
        require(category in payload.get("categories", []), "category missing from JSON: " + category)
        require(category in combined, "category missing from text: " + category)


def check_review_states(payload: dict, combined: str) -> None:
    for state in [
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


def check_draft_labels(payload: dict, combined: str) -> None:
    for label in [
        "DRAFT_ONLY",
        "NOT_REAL_QUEUE_RECORD",
        "NOT_APPROVAL",
        "NOT_RECEIPT",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in payload.get("draft_labels", []), "draft label missing from JSON: " + label)
        require(label in payload.get("record_template", {}).get("draft_labels", []), "draft label missing from template: " + label)
        require(label in combined, "draft label missing from text: " + label)


def check_boundary_statements(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    for phrase in [
        "a draft schema is not a real queue record",
        "a draft record is not an approval",
        "a draft record is not a receipt",
        "a draft record is not trusted memory",
        "creating the schema does not create a writer",
        "creating the schema does not activate a queue runtime",
        "explicit future approval is required before any real queue record can be written",
    ]:
        require(phrase in lowered, "missing boundary statement: " + phrase)

    boundary = payload.get("safety_boundary", {})
    for key in [
        "schema_only",
        "draft_record_shape_only",
        "draft_schema_is_not_real_queue_record",
        "draft_record_is_not_approval",
        "draft_record_is_not_receipt",
        "draft_record_is_not_trusted_memory",
        "creating_schema_does_not_create_writer",
        "creating_schema_does_not_activate_queue_runtime",
        "explicit_future_approval_required_before_real_queue_record_can_be_written",
        "no_real_queue_records",
        "no_queue_writer",
        "no_active_queue_runtime",
        "no_queue_worker",
        "no_automatic_import",
        "no_recursive_scan",
        "no_indexing",
        "no_embedding",
        "no_training",
        "no_runtime_loading",
        "no_execution",
        "no_provider_or_network_action",
        "no_trusted_memory_write",
    ]:
        require(boundary.get(key) is True, "safety boundary flag must be true: " + key)


def check_required_booleans(payload: dict) -> None:
    template = payload.get("record_template", {})
    for key in [
        "human_review_required",
        "receipt_required",
        "not_trusted_memory",
        "no_automation_triggered",
        "created_by_human_confirmation",
        "draft_only",
        "not_real_queue_record_until_approved",
    ]:
        require(template.get(key) is True, "record template boolean must be true: " + key)

    authority = payload.get("human_authority_boundary", {})
    for key in [
        "human_authority_required",
        "created_by_human_confirmation_required",
        "future_real_record_requires_explicit_approval",
        "future_real_record_requires_separate_writer_contract",
        "future_real_record_requires_verification",
        "schema_does_not_authorize_record_write",
        "schema_does_not_authorize_reference_approval",
        "schema_does_not_authorize_memory",
    ]:
        require(authority.get(key) is True, "human authority flag must be true: " + key)


def check_uses(payload: dict, combined: str) -> None:
    for use in [
        "human_review_tracking",
        "manual_research_triage",
        "human_guided_reference_decision",
        "future_review_candidate",
        "metadata_ready_for_human_queue_record_draft",
    ]:
        require(use in payload.get("allowed_uses", []), "allowed use missing from JSON: " + use)
        require(use in combined, "allowed use missing from text: " + use)

    for use in [
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
    ]:
        require(use in payload.get("disallowed_uses", []), "disallowed use missing from JSON: " + use)
        require(use in combined, "disallowed use missing from text: " + use)


def check_inactive_denials(payload: dict) -> None:
    denials = payload.get("inactive_behavior_denials", {})
    require(isinstance(denials, dict), "inactive behavior denials missing")
    for key, value in denials.items():
        require(value is False, "inactive behavior denial must be false: " + key)
    for key in [
        "create_real_queue_record",
        "write_queue_file",
        "approve_material",
        "create_receipt",
        "import_material",
        "copy_material",
        "move_material",
        "sync_storage",
        "scan_folders",
        "recursive_scan",
        "index_content",
        "embed_content",
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
        require(term not in combined_lower, "forbidden active-behavior term found in schema docs: " + term)

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
        payload, payload_text, md = load_schema()
        require(payload.get("schema_name") == "engel_manual_library_queue_record_draft_schema_v1", "schema_name mismatch")
        require(payload.get("schema_version") == "1.0", "schema_version mismatch")
        combined = payload_text + "\n" + md
        check_statuses(combined)
        check_schema_fields(payload, combined)
        check_categories(payload, combined)
        check_review_states(payload, combined)
        check_draft_labels(payload, combined)
        check_boundary_statements(payload, combined)
        check_required_booleans(payload)
        check_uses(payload, combined)
        check_inactive_denials(payload)
        check_forbidden_active_behavior(payload_text, md)
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Manual Library Queue Record Draft Schema V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Manual Library Queue Record Draft Schema V1 verifier")
    print("- schema JSON and Markdown exist and parse")
    print("- required fields, categories, review states, and draft labels are present")
    print("- schema remains draft-only, not a real queue record, approval, receipt, or trusted memory")
    print("- no queue writer, queue runtime, queue worker, import, indexing, execution, training, runtime loading, provider, or trusted-memory behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
