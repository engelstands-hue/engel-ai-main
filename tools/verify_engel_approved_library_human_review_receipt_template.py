#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_JSON = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_HUMAN_REVIEW_RECEIPT_TEMPLATE_V1.json"
TEMPLATE_MD = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_HUMAN_REVIEW_RECEIPT_TEMPLATE_V1.md"
THIS_FILE = Path(__file__).resolve()


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_template() -> tuple[dict, str, str]:
    require(TEMPLATE_JSON.exists(), "missing template JSON")
    require(TEMPLATE_MD.exists(), "missing template Markdown")
    payload = json.loads(read(TEMPLATE_JSON))
    md = read(TEMPLATE_MD)
    return payload, json.dumps(payload, sort_keys=True), md


def check_required_statuses(payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    for status in [
        "TEMPLATE_ONLY",
        "HUMAN_REVIEW_ONLY",
        "NO_AUTOMATIC_IMPORT",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing required status: " + status)


def check_architecture_wording(payload_text: str, md: str) -> None:
    combined = (payload_text + "\n" + md).lower()
    for phrase in [
        "engel is more than code",
        "human judgment checkpoint",
        "future queen",
        "colony",
        "long-term storage",
        "research/reference only",
        "not trusted memory",
    ]:
        require(phrase in combined, "missing architecture wording: " + phrase)


def check_receipt_sections(payload: dict, md: str) -> None:
    section_names = [section.get("name") for section in payload.get("receipt_sections", [])]
    for section in [
        "Material Identity",
        "Human Reviewer",
        "Review Decision",
        "Safety Boundary Acknowledgments",
        "Prompt Injection / Content Risk Review",
        "Research Use Boundary",
        "Engel Memory Boundary",
        "Math / Code Specific Review",
        "Future Queen / Colony Use Notes",
        "Final Human Signoff",
    ]:
        require(section in section_names, "JSON missing receipt section: " + section)
        require(section in md, "Markdown missing receipt section: " + section)


def check_lists(payload: dict, payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    for decision in [
        "approved_for_reference",
        "rejected",
        "hold_for_later",
        "needs_source_clarification",
        "unsafe_or_untrusted_content",
    ]:
        require(decision in payload.get("allowed_decisions", []), "decision missing from JSON: " + decision)
        require(decision in combined, "decision missing from template text: " + decision)
    for disallowed in [
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
    ]:
        require(disallowed in payload.get("disallowed_uses", []), "disallowed use missing from JSON: " + disallowed)
        require(disallowed in combined, "disallowed use missing from template text: " + disallowed)
    for category in ["math", "coding_languages"]:
        require(category in payload.get("categories", []), "category missing from JSON: " + category)
        require(category in combined, "category missing from template text: " + category)


def check_boundary_statements(payload_text: str, md: str) -> None:
    combined = (payload_text + "\n" + md).lower()
    for phrase in [
        "approved_for_reference does not mean trusted memory",
        "separate memory candidate proposal required",
        "no automation is triggered by a receipt",
        "code examples are not auto executable",
        "math claims need verification",
    ]:
        require(phrase in combined, "missing boundary statement: " + phrase)


def check_required_fields(payload: dict) -> None:
    required_fields = set(payload.get("required_fields", []))
    for field in [
        "material_id",
        "title",
        "author_or_origin",
        "source_type",
        "source_notes",
        "original_location",
        "intended_reference_location",
        "reviewer_name_or_id",
        "review_date",
        "decision",
        "not_trusted_memory_acknowledged",
        "no_auto_index_acknowledged",
        "no_execution_acknowledged",
        "prompt_injection_risk_observed",
        "may_not_write_trusted_memory",
        "requires_separate_memory_candidate_proposal",
        "math_claims_need_verification",
        "code_examples_not_auto_executable",
        "queen_visibility",
        "colony_research_notes",
        "long_term_storage_relevance",
        "swarm_or_mycelium_risk_notes",
        "no_automation_confirmed",
    ]:
        require(field in required_fields, "required field missing: " + field)


def check_inactive_denials(payload: dict) -> None:
    denials = payload.get("inactive_behavior_denials")
    require(isinstance(denials, dict), "inactive behavior denials missing")
    for key in [
        "import_materials",
        "copy_materials",
        "move_materials",
        "sync_materials",
        "scan_materials",
        "recursive_scan",
        "index_materials",
        "embed_materials",
        "summarize_materials",
        "execute_materials",
        "trust_materials",
        "train_on_materials",
        "runtime_load_materials",
        "probe_storage_locations",
        "change_routes",
        "change_queues",
        "change_startup",
        "call_provider_api",
        "call_network",
        "start_browser",
        "use_package_manager",
        "start_background_worker",
        "write_trusted_memory",
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
        "auto import implementation",
        "vector index implementation",
        "model training implementation",
        "runtime loader implementation",
        "file copy implementation",
        "file move implementation",
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
        payload, payload_text, md = load_template()
        require(payload.get("schema_name") == "engel_approved_library_human_review_receipt_template_v1", "schema name mismatch")
        require(payload.get("schema_version") == "1.0", "schema version mismatch")
        check_required_statuses(payload_text, md)
        check_architecture_wording(payload_text, md)
        check_receipt_sections(payload, md)
        check_lists(payload, payload_text, md)
        check_boundary_statements(payload_text, md)
        check_required_fields(payload)
        check_inactive_denials(payload)
        check_forbidden_active_behavior(payload_text, md)
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Approved Library Human Review Receipt Template V1 verifier")
        print("- " + str(exc))
        return 1
    print("PASS: Engel Approved Library Human Review Receipt Template V1 verifier")
    print("- template JSON and Markdown exist and parse")
    print("- required statuses, sections, decisions, categories, and safety acknowledgments are present")
    print("- approved_for_reference remains research/reference only, not trusted memory")
    print("- no active import, indexing, execution, training, runtime loading, or trusted-memory behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
