#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_JSON = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_MANUAL_REVIEW_QUEUE_EXAMPLES_V1.json"
EXAMPLES_MD = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_MANUAL_REVIEW_QUEUE_EXAMPLES_V1.md"
THIS_FILE = Path(__file__).resolve()


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_examples() -> tuple[dict, str, str]:
    require(EXAMPLES_JSON.exists(), "missing manual review queue examples JSON")
    require(EXAMPLES_MD.exists(), "missing manual review queue examples Markdown")
    payload = json.loads(read(EXAMPLES_JSON))
    md = read(EXAMPLES_MD)
    return payload, json.dumps(payload, sort_keys=True), md


def check_required_statuses(payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    for status in [
        "EXAMPLE_ONLY",
        "FAKE_SAMPLE_DATA_ONLY",
        "QUEUE_PATTERN_EXAMPLE",
        "NO_REAL_QUEUE_RECORDS",
        "NO_ACTIVE_QUEUE_RUNTIME",
        "NO_QUEUE_WORKER",
        "NO_AUTOMATIC_IMPORT",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing required status: " + status)


def check_examples(payload: dict) -> list[dict]:
    examples = payload.get("examples")
    require(isinstance(examples, list), "examples must be a list")
    require(len(examples) >= 6, "at least six examples are required")
    require(payload.get("example_count") == len(examples), "example_count must match examples length")

    categories = {example.get("category") for example in examples}
    for category in ["math", "coding_languages"]:
        require(category in categories, "category missing from examples: " + category)
        require(category in payload.get("categories_represented", []), "category missing from top-level list: " + category)

    review_states = {example.get("review_state") for example in examples}
    top_review_states = set(payload.get("review_states_represented", []))
    for state in [
        "human_review_pending",
        "in_human_review",
        "approved_for_reference",
        "rejected",
        "hold_for_later",
        "needs_source_clarification",
        "unsafe_or_untrusted_content",
    ]:
        require(state in review_states, "review state missing from examples: " + state)
        require(state in top_review_states, "review state missing from top-level list: " + state)

    receipt_statuses = {example.get("receipt_status") for example in examples}
    for status in ["receipt_missing", "receipt_complete"]:
        require(status in receipt_statuses, "receipt status missing from examples: " + status)
        require(status in top_review_states, "receipt status missing from top-level review state list: " + status)
        require(status in payload.get("receipt_statuses_represented", []), "receipt status missing top-level receipt list: " + status)

    for index, example in enumerate(examples, start=1):
        label = "example " + str(index)
        for flag in [
            "fake_example",
            "no_real_material",
            "not_actual_queue_record",
            "not_actual_approval",
            "not_actual_receipt",
            "not_trusted_memory",
            "no_automation_triggered",
            "no_active_queue_runtime",
            "no_queue_worker",
        ]:
            require(example.get(flag) is True, label + " missing true flag: " + flag)
    return examples


def check_required_fields(examples: list[dict]) -> None:
    fields = [
        "queue_record_id",
        "material_id",
        "title",
        "category",
        "source_notes",
        "original_location_reference",
        "intended_reference_location_reference",
        "review_state",
        "human_review_required",
        "receipt_required",
        "receipt_reference",
        "receipt_status",
        "safety_flags",
        "allowed_uses",
        "disallowed_uses",
        "next_manual_action",
    ]
    for example in examples:
        label = example.get("queue_record_id", "unnamed example")
        for field in fields:
            require(field in example, label + " missing field: " + field)
        require(example.get("human_review_required") is True, label + " must require human review")
        require(example.get("receipt_required") is True, label + " must require receipt")
        require(isinstance(example.get("safety_flags"), list), label + " safety_flags must be a list")
        require(isinstance(example.get("allowed_uses"), list), label + " allowed_uses must be a list")
        require(isinstance(example.get("disallowed_uses"), list), label + " disallowed_uses must be a list")


def check_uses(payload: dict, examples: list[dict], payload_text: str, md: str) -> None:
    combined = payload_text + "\n" + md
    allowed_general = {
        "human_review_tracking",
        "manual_research_triage",
        "human_guided_reference_decision",
        "future_review_candidate",
    }
    allowed_approved_extra = {"human_guided_research_reference"}
    for allowed in sorted(allowed_general | allowed_approved_extra):
        require(allowed in payload.get("allowed_uses", []), "top-level allowed use missing: " + allowed)
        require(allowed in combined, "allowed use missing from text: " + allowed)

    required_disallowed = [
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
    ]
    inherited = set(payload.get("disallowed_uses", []))
    for disallowed in required_disallowed:
        require(disallowed in inherited, "top-level disallowed use missing: " + disallowed)
        require(disallowed in combined, "disallowed use missing from text: " + disallowed)

    for example in examples:
        label = example.get("queue_record_id", "example")
        local_allowed = set(example.get("allowed_uses", []))
        permitted = set(allowed_general)
        if example.get("review_state") == "approved_for_reference":
            permitted |= allowed_approved_extra
        require(local_allowed <= permitted, label + " has non-permitted allowed use")
        local_disallowed = set(example.get("disallowed_uses", []))
        for disallowed in required_disallowed:
            require(disallowed in local_disallowed, label + " missing disallowed use: " + disallowed)


def check_boundaries(payload: dict, payload_text: str, md: str) -> None:
    combined = (payload_text + "\n" + md).lower()
    for phrase in [
        "fake queue examples are not real queue records",
        "queue metadata is not material content",
        "review state is not authority",
        "archived metadata does not equal trust",
        "next_manual_action is descriptive only",
        "no active queue runtime",
        "no queue worker",
        "no automation is triggered",
        "separate human review receipt is required",
        "separate memory candidate proposal is required",
    ]:
        require(phrase in combined, "missing safety phrase: " + phrase)

    fake_boundary = payload.get("fake_data_boundary")
    require(isinstance(fake_boundary, dict), "missing fake_data_boundary")
    for key in [
        "fake_examples_only",
        "no_real_materials",
        "not_actual_queue_records",
        "not_actual_approvals",
        "not_actual_receipts",
        "not_trusted_memory",
        "no_automation_triggered",
        "no_active_queue_runtime",
        "no_queue_worker",
    ]:
        require(fake_boundary.get(key) is True, "fake data boundary must be true: " + key)

    safety = payload.get("safety_boundary")
    require(isinstance(safety, dict), "missing safety_boundary")
    for key in [
        "fake_queue_examples_are_not_real_queue_records",
        "fake_queue_examples_are_not_approvals",
        "fake_queue_examples_are_not_receipts",
        "fake_queue_examples_are_not_trusted_memory",
        "fake_queue_examples_do_not_represent_real_material_contents",
        "queue_metadata_is_not_material_content",
        "review_state_is_not_authority",
        "archived_metadata_does_not_equal_trust",
        "next_manual_action_is_descriptive_only",
        "no_active_queue_runtime",
        "no_queue_worker",
        "no_automation_triggered",
        "no_import",
        "no_indexing",
        "no_embedding",
        "no_scan",
        "no_summarization",
        "no_execution",
        "no_training",
        "no_runtime_loading",
        "no_storage_location_probe",
        "future_queens_get_visibility_not_authority",
        "separate_human_review_receipt_required",
        "separate_memory_candidate_proposal_required",
    ]:
        require(safety.get(key) is True, "safety boundary must be true: " + key)


def check_inactive_denials(payload: dict) -> None:
    denials = payload.get("inactive_behavior_denials")
    require(isinstance(denials, dict), "inactive behavior denials missing")
    for key in [
        "real_queue_records_created",
        "real_approvals_created",
        "real_receipts_created",
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
        "active_queue_runtime_started",
        "queue_worker_started",
        "storage_location_probed",
        "route_or_startup_or_source_changed",
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
        "active queue worker " + "implementation",
        "active queue runtime " + "implementation",
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
        payload, payload_text, md = load_examples()
        require(payload.get("schema_name") == "engel_approved_library_manual_review_queue_examples_v1", "schema name mismatch")
        require(payload.get("schema_version") == "1.0", "schema version mismatch")
        check_required_statuses(payload_text, md)
        examples = check_examples(payload)
        check_required_fields(examples)
        check_uses(payload, examples, payload_text, md)
        check_boundaries(payload, payload_text, md)
        check_inactive_denials(payload)
        check_forbidden_active_behavior(payload_text, md)
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Approved Library Manual Review Queue Examples V1 verifier")
        print("- " + str(exc))
        return 1
    print("PASS: Engel Approved Library Manual Review Queue Examples V1 verifier")
    print("- fake queue-record examples exist and parse")
    print("- math and coding_languages examples cover pending, in-review, approved, rejected/unsafe, hold, and source-clarification states")
    print("- receipt_missing and receipt_complete cases are represented")
    print("- every example is fake-only, not trusted memory, and triggers no queue runtime or automation")
    print("- no active import, indexing, execution, training, runtime loading, queue worker, or trusted-memory behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
