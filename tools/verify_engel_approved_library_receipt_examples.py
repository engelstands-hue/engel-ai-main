#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_JSON = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_RECEIPT_EXAMPLES_V1.json"
EXAMPLES_MD = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_RECEIPT_EXAMPLES_V1.md"
THIS_FILE = Path(__file__).resolve()


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_examples() -> tuple[dict, str, str]:
    require(EXAMPLES_JSON.exists(), "missing receipt examples JSON")
    require(EXAMPLES_MD.exists(), "missing receipt examples Markdown")
    payload = json.loads(read(EXAMPLES_JSON))
    md = read(EXAMPLES_MD)
    return payload, json.dumps(payload, sort_keys=True), md


def check_required_statuses(payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    for status in [
        "EXAMPLE_ONLY",
        "FAKE_SAMPLE_DATA_ONLY",
        "HUMAN_REVIEW_PATTERN_EXAMPLE",
        "NO_REAL_MATERIALS",
        "NO_AUTOMATIC_IMPORT",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing required status: " + status)


def check_examples(payload: dict) -> list[dict]:
    examples = payload.get("examples")
    require(isinstance(examples, list), "examples must be a list")
    require(len(examples) >= 4, "at least four examples are required")

    categories = {
        example.get("material_identity", {}).get("category")
        for example in examples
    }
    require("math" in categories, "math category missing from examples")
    require("coding_languages" in categories, "coding_languages category missing from examples")

    decisions = {
        example.get("review_decision", {}).get("decision")
        for example in examples
    }
    require("approved_for_reference" in decisions, "approved_for_reference decision missing")
    require(
        bool({"unsafe_or_untrusted_content", "rejected"} & decisions),
        "unsafe_or_untrusted_content or rejected decision missing",
    )
    require(
        bool({"hold_for_later", "needs_source_clarification"} & decisions),
        "hold_for_later or needs_source_clarification decision missing",
    )

    for index, example in enumerate(examples, start=1):
        label = "example " + str(index)
        for flag in [
            "fake_example",
            "no_real_material",
            "not_actual_approval",
            "not_trusted_memory",
            "no_automation_triggered",
        ]:
            require(example.get(flag) is True, label + " missing true flag: " + flag)
    return examples


def require_nested(example: dict, section: str, fields: list[str]) -> None:
    payload = example.get(section)
    require(isinstance(payload, dict), "missing section: " + section)
    for field in fields:
        require(field in payload, section + " missing field: " + field)


def check_receipt_shape(examples: list[dict]) -> None:
    for example in examples:
        label = example.get("example_id", "unnamed example")
        require_nested(
            example,
            "material_identity",
            [
                "material_id",
                "title",
                "author_or_origin",
                "source_type",
                "source_notes",
                "original_location",
                "intended_reference_location",
                "category",
                "subcategory",
                "version_or_date",
                "file_format",
                "estimated_scope",
            ],
        )
        require_nested(
            example,
            "human_reviewer",
            [
                "reviewer_name_or_id",
                "review_date",
                "review_context",
                "review_depth",
                "reviewer_confidence",
            ],
        )
        require_nested(
            example,
            "review_decision",
            [
                "decision",
                "approved_for_reference_only",
                "rejected",
                "hold_for_later",
                "needs_source_clarification",
                "unsafe_or_untrusted_content",
                "reason_for_decision",
            ],
        )
        require_nested(
            example,
            "safety_boundary_acknowledgments",
            [
                "not_trusted_memory_acknowledged",
                "no_auto_index_acknowledged",
                "no_execution_acknowledged",
                "no_training_acknowledged",
                "no_runtime_loading_acknowledged",
                "no_network_or_provider_action_acknowledged",
                "no_startup_or_background_action_acknowledged",
            ],
        )
        require_nested(
            example,
            "prompt_injection_content_risk_review",
            [
                "prompt_injection_risk_observed",
                "hostile_instruction_risk",
                "hidden_or_embedded_instruction_risk",
                "malicious_code_or_command_risk",
                "unsafe_external_link_or_download_risk",
                "citation_or_source_spoofing_risk",
                "poisoned_example_or_bad_training_data_risk",
                "risk_notes",
            ],
        )
        require_nested(
            example,
            "research_use_boundary",
            [
                "allowed_use",
                "disallowed_use",
                "reference_only_notes",
                "citation_required",
                "license_or_usage_notes",
                "provenance_notes",
            ],
        )
        require_nested(
            example,
            "engel_memory_boundary",
            [
                "may_inform_human_guided_research_summary",
                "may_not_write_trusted_memory",
                "requires_separate_memory_candidate_proposal",
                "requires_separate_human_approval_for_memory",
                "memory_boundary_notes",
            ],
        )
        require_nested(
            example,
            "math_code_specific_review",
            [
                "math_claims_need_verification",
                "code_examples_not_auto_executable",
                "commands_not_auto_runnable",
                "package_install_not_allowed",
                "technical_accuracy_notes",
            ],
        )
        require_nested(
            example,
            "future_queen_colony_use_notes",
            [
                "queen_visibility",
                "future_workflow_notes",
                "colony_research_notes",
                "archive_notes",
                "long_term_storage_relevance",
                "swarm_or_mycelium_risk_notes",
            ],
        )
        require_nested(
            example,
            "final_human_signoff",
            [
                "final_decision",
                "reviewer_signature_or_marker",
                "timestamp",
                "next_manual_action",
                "no_automation_confirmed",
            ],
        )
        require(
            example["final_human_signoff"].get("no_automation_confirmed") is True,
            label + " must confirm no automation",
        )


def check_disallowed_uses(payload: dict, examples: list[dict], payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    required = [
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
    ]
    inherited = set(payload.get("required_disallowed_uses", []))
    for disallowed in required:
        require(disallowed in inherited, "top-level disallowed use missing: " + disallowed)
        require(disallowed in combined, "disallowed use missing from text: " + disallowed)

    for example in examples:
        local = set(example.get("research_use_boundary", {}).get("disallowed_use", []))
        for disallowed in required:
            require(disallowed in local, example.get("example_id", "example") + " missing disallowed use: " + disallowed)


def check_required_safety_phrases(payload_text: str, md: str) -> None:
    combined = (payload_text + "\n" + md).lower()
    for phrase in [
        "fake examples only",
        "not real approvals",
        "not trusted memory",
        "no automation",
        "no import",
        "no indexing",
        "no execution",
        "no model training",
        "no runtime loading",
    ]:
        require(phrase in combined, "missing safety phrase: " + phrase)


def check_fake_boundary(payload: dict) -> None:
    boundary = payload.get("fake_data_boundary")
    require(isinstance(boundary, dict), "missing fake_data_boundary")
    for key in [
        "example_only",
        "fake_sample_data_only",
        "no_real_materials",
        "not_real_receipts",
        "not_actual_approvals",
        "not_trusted_memory",
        "no_automation_triggered",
        "no_import",
        "no_indexing",
        "no_execution",
        "no_model_training",
        "no_runtime_loading",
        "no_storage_probe",
    ]:
        require(boundary.get(key) is True, "fake data boundary must be true: " + key)


def check_inactive_denials(payload: dict) -> None:
    denials = payload.get("inactive_behavior_denials")
    require(isinstance(denials, dict), "inactive behavior denials missing")
    for key in [
        "real_material_imported",
        "real_material_copied",
        "real_material_moved",
        "real_material_synced",
        "real_material_scanned_recursively",
        "real_material_indexed",
        "real_material_embedded",
        "real_material_summarized",
        "real_material_executed",
        "real_material_trusted",
        "real_material_trained_on",
        "runtime_loaded",
        "storage_location_probed",
        "route_or_queue_or_startup_changed",
        "provider_or_network_or_browser_called",
        "package_manager_used",
        "background_worker_started",
        "queen_runtime_started",
        "model_behavior_added",
        "trusted_memory_written",
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
        "active import " + "implementation",
        "vector index " + "implementation",
        "model training " + "implementation",
        "runtime loader " + "implementation",
        "file copy " + "implementation",
        "file move " + "implementation",
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
        payload, payload_text, md = load_examples()
        require(payload.get("schema_name") == "engel_approved_library_receipt_examples_v1", "schema name mismatch")
        require(payload.get("schema_version") == "1.0", "schema version mismatch")
        check_required_statuses(payload_text, md)
        check_fake_boundary(payload)
        examples = check_examples(payload)
        check_receipt_shape(examples)
        check_disallowed_uses(payload, examples, payload_text, md)
        check_required_safety_phrases(payload_text, md)
        check_inactive_denials(payload)
        check_forbidden_active_behavior(payload_text, md)
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Approved Library Receipt Examples V1 verifier")
        print("- " + str(exc))
        return 1
    print("PASS: Engel Approved Library Receipt Examples V1 verifier")
    print("- fake/sample receipt examples exist and parse")
    print("- math and coding_languages examples include approved, hold/clarification, and unsafe/rejected decisions")
    print("- every example is fake-only, not trusted memory, and triggers no automation")
    print("- no active import, indexing, execution, training, runtime loading, or trusted-memory behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
