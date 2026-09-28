#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_JSON = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_MANUAL_REVIEW_QUEUE_READINESS_CHECKLIST_V1.json"
CHECKLIST_MD = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_MANUAL_REVIEW_QUEUE_READINESS_CHECKLIST_V1.md"
THIS_FILE = Path(__file__).resolve()


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_checklist() -> tuple[dict, str, str]:
    require(CHECKLIST_JSON.exists(), "missing readiness checklist JSON")
    require(CHECKLIST_MD.exists(), "missing readiness checklist Markdown")
    payload = json.loads(read(CHECKLIST_JSON))
    md = read(CHECKLIST_MD)
    return payload, json.dumps(payload, sort_keys=True), md


def check_statuses(combined: str) -> None:
    for status in [
        "CHECKLIST_ONLY",
        "HUMAN_GUIDED",
        "ENGEL_GUIDED_READINESS",
        "READINESS_GUIDE_ONLY",
        "LESS_HUMAN_FRICTION",
        "HUMAN_AUTHORITY_REQUIRED",
        "NO_REAL_QUEUE_RECORDS",
        "NO_ACTIVE_QUEUE_RUNTIME",
        "NO_QUEUE_WORKER",
        "NO_AUTOMATIC_IMPORT",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing required status: " + status)


def check_low_friction_concepts(combined: str) -> None:
    lowered = combined.lower()
    for phrase in [
        "less human interaction",
        "fewer repeated questions",
        "prefilled safe defaults",
        "single-screen human decision",
        "stop/go gate",
        "minimal typing",
        "human authority checkpoint",
        "no silent escalation",
    ]:
        require(phrase in lowered, "missing low-friction concept: " + phrase)


def check_sections(md: str) -> None:
    for section in [
        "Start Here",
        "Fast Safety Gate",
        "STOP if any answer is No or Unsure",
        "Engel Can Help Later, But Not Yet",
        "Category Picker",
        "Risk Quick Check",
        "Decision Helper",
        "Required Metadata",
        "Final Human Confirmation",
        "Safe Output",
        "Glossary",
    ]:
        require(section in md, "missing user-friendly section: " + section)


def check_human_error_prevention(combined: str) -> None:
    lowered = combined.lower()
    for phrase in [
        "if unsure, stop",
        "if source is unknown, stop",
        "approved_library is not trusted memory",
        "queue record is not approval",
        "receipt is required",
        "no automation is triggered",
        "next_manual_action is descriptive only",
        "human authority remains required",
    ]:
        require(phrase in lowered, "missing human-error prevention phrase: " + phrase)


def check_stop_conditions(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    stop_conditions = payload.get("stop_conditions")
    require(isinstance(stop_conditions, list), "stop_conditions must be a list")
    for condition in [
        "unknown source",
        "suspicious instructions",
        "hidden prompt instructions",
        "ignore rules",
        "run commands",
        "install packages",
        "download more files",
        "credentials",
        "secrets",
        "malware-like code",
        "unclear license",
        "unclear provenance",
        "reviewer is unsure",
    ]:
        require(condition in stop_conditions, "stop condition missing from JSON: " + condition)
        require(condition in lowered, "stop condition missing from Markdown/text: " + condition)


def check_categories(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    categories = [item.get("category") for item in payload.get("category_picker", []) if isinstance(item, dict)]
    for category in [
        "research_papers",
        "architecture_references",
        "engel_manuals",
        "offline_docs",
        "math",
        "coding_languages",
    ]:
        require(category in categories, "category missing from category picker: " + category)
        require(category in lowered, "category missing from text: " + category)


def check_review_states(combined: str) -> None:
    lowered = combined.lower()
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
        require(state in lowered, "review state guidance missing: " + state)


def check_outputs(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    for output in [
        "not_ready",
        "needs_source_clarification",
        "hold_for_later",
        "unsafe_or_untrusted_content",
        "metadata_ready_for_human_queue_record_draft",
    ]:
        require(output in payload.get("safe_outputs", []), "safe output missing from JSON: " + output)
        require(output in lowered, "safe output missing from text: " + output)

    for output in [
        "imported_material",
        "approved_material",
        "trusted_memory",
        "trained_model_data",
        "indexed_content",
        "executed_code",
        "runtime_loaded_content",
    ]:
        require(output in payload.get("forbidden_outputs", []), "forbidden output missing from JSON: " + output)
        require(output in lowered, "forbidden output missing from text: " + output)


def check_uses(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    for use in [
        "human_readiness_check",
        "manual_review_preflight",
        "metadata_quality_check",
        "human_error_reduction",
        "low_friction_human_guidance",
        "future_queue_record_preparation",
        "future_engel_guided_ui_pattern",
    ]:
        require(use in payload.get("allowed_uses", []), "allowed use missing from JSON: " + use)
        require(use in lowered, "allowed use missing from text: " + use)

    for use in [
        "real_queue_creation",
        "real_approval_creation",
        "real_receipt_creation",
        "trusted_memory_write",
        "automatic_learning",
        "automatic_import",
        "automatic_copy",
        "automatic_move",
        "automatic_sync",
        "recursive_scan",
        "indexing",
        "embedding_or_vector_indexing",
        "summarization_of_real_materials",
        "model_training",
        "fine_tuning",
        "runtime_loading",
        "inference",
        "code_execution",
        "command_execution",
        "package_install",
        "provider_or_network_action",
        "startup_action",
        "background_worker_action",
        "queen_runtime_action",
        "silent_escalation",
        "autonomous_decision",
    ]:
        require(use in payload.get("disallowed_uses", []), "disallowed use missing from JSON: " + use)
        require(use in lowered, "disallowed use missing from text: " + use)


def check_structured_fields(payload: dict) -> None:
    for key in [
        "schema_name",
        "schema_version",
        "status",
        "purpose",
        "engel_architecture_role",
        "human_error_reduction_goal",
        "less_human_interaction_design",
        "human_authority_boundary",
        "checklist_sections",
        "quick_safety_gate",
        "stop_conditions",
        "safe_review_preconditions",
        "category_picker",
        "risk_quick_check",
        "decision_helper",
        "required_metadata_fields",
        "final_human_confirmations",
        "safe_outputs",
        "forbidden_outputs",
        "glossary_terms",
        "future_engel_guided_ui_notes",
        "allowed_uses",
        "disallowed_uses",
        "safety_boundary",
        "inactive_behavior_denials",
        "related_contracts",
    ]:
        require(key in payload, "missing top-level JSON key: " + key)

    require(payload.get("schema_name") == "engel_approved_library_manual_review_queue_readiness_checklist_v1", "schema_name mismatch")
    require(payload.get("schema_version") == "1.0", "schema_version mismatch")
    require(isinstance(payload.get("required_metadata_fields"), list), "required_metadata_fields must be a list")
    require(len(payload["required_metadata_fields"]) >= 10, "required_metadata_fields should cover core queue metadata")

    safety = payload.get("safety_boundary")
    require(isinstance(safety, dict), "safety_boundary must be a dict")
    for key in [
        "checklist_only",
        "human_guided",
        "human_authority_required",
        "no_real_queue_records",
        "no_real_approvals",
        "no_real_receipts",
        "no_active_queue_runtime",
        "no_queue_worker",
        "no_automatic_import",
        "no_recursive_scan",
        "no_indexing",
        "no_embedding",
        "no_summarization_of_real_materials",
        "no_execution",
        "no_training",
        "no_runtime_loading",
        "no_inference",
        "no_trusted_memory_write",
        "no_silent_escalation",
        "no_autonomous_decision",
        "no_storage_location_probe",
    ]:
        require(safety.get(key) is True, "safety_boundary flag must be true: " + key)

    denials = payload.get("inactive_behavior_denials")
    require(isinstance(denials, dict), "inactive_behavior_denials must be a dict")
    for key, value in denials.items():
        require(value is False, "inactive behavior denial must be false: " + key)


def check_required_glossary(combined: str) -> None:
    lowered = combined.lower()
    for term in [
        "queue record",
        "material",
        "approved_library",
        "quarantine_imports",
        "human review receipt",
        "approved_for_reference",
        "trusted memory",
        "memory candidate proposal",
        "prompt injection",
        "provenance",
        "license/usage risk",
        "next_manual_action",
    ]:
        require(term in lowered, "glossary term missing: " + term)


def check_no_active_behavior(payload_text: str, md: str) -> None:
    combined_lower = (payload_text + "\n" + md).lower()
    for raw_term in [
        "shutil",
        "copytree",
        "os.walk",
        "rglob",
        "subprocess",
        "requests",
        "urllib",
        "socket",
    ]:
        require(raw_term not in combined_lower, "forbidden active-behavior library term found in checklist docs: " + raw_term)

    for phrase in [
        "active queue worker implementation",
        "active queue runtime implementation",
        "file copy implementation",
        "file move implementation",
        "scan implementation",
        "index implementation",
        "vector implementation",
        "model training implementation",
        "runtime loader implementation",
        "provider call implementation",
    ]:
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
            require(name not in {"copytree", "move", "walk", "rglob", "run", "Popen", "system"}, "forbidden active call in verifier: " + name)


def main() -> int:
    try:
        payload, payload_text, md = load_checklist()
        combined = payload_text + "\n" + md
        check_statuses(combined)
        check_low_friction_concepts(combined)
        check_sections(md)
        check_human_error_prevention(combined)
        check_stop_conditions(payload, combined)
        check_categories(payload, combined)
        check_review_states(combined)
        check_outputs(payload, combined)
        check_uses(payload, combined)
        check_structured_fields(payload)
        check_required_glossary(combined)
        check_no_active_behavior(payload_text, md)
    except (CheckFailure, json.JSONDecodeError) as exc:
        print("[FAIL]", exc)
        return 1

    print("PASS: Engel Approved Library Manual Review Queue Readiness Checklist V1 verifier")
    print("- checklist JSON and Markdown exist and parse")
    print("- low-friction, human-guided readiness design is present")
    print("- stop/go gates, safe outputs, forbidden outputs, categories, and review states are covered")
    print("- checklist preserves human authority and triggers no queue runtime, automation, import, or trusted-memory behavior")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
