#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_JSON = ROOT / "memory" / "ENGEL_MANUAL_IMPORT_RECEIPT_V1.json"
RECEIPT_MD = ROOT / "memory" / "ENGEL_MANUAL_IMPORT_RECEIPT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MANUAL_IMPORT_RECEIPT_V1.md"
THIS_FILE = Path(__file__).resolve()


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_receipt() -> tuple[dict, str, str, str]:
    for path in [RECEIPT_JSON, RECEIPT_MD, REPORT]:
        require(path.exists(), "missing required file: " + str(path))
    payload = json.loads(read(RECEIPT_JSON))
    return payload, json.dumps(payload, sort_keys=True), read(RECEIPT_MD), read(REPORT)


def check_statuses(combined: str) -> None:
    for status in [
        "RECEIPT_TEMPLATE_ONLY",
        "HUMAN_RECORDED_ACTION",
        "NO_FILE_OPERATIONS",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing required status: " + status)


def check_required_fields(payload: dict, combined: str) -> None:
    required_fields = [
        "import_receipt_id",
        "material_id",
        "queue_record_reference",
        "human_review_receipt_reference",
        "approved_for_reference_reference",
        "human_importer",
        "import_date",
        "source_location_reference",
        "approved_library_location_reference",
        "category",
        "file_name",
        "file_format",
        "checksum_optional",
        "human_confirms_manual_action",
        "no_automation_used",
        "not_trusted_memory",
        "no_indexing_performed",
        "no_execution_performed",
        "notes",
    ]
    fields = payload.get("required_fields", [])
    template = payload.get("receipt_template", {})
    meanings = payload.get("field_meanings", {})
    for field in required_fields:
        require(field in fields, "missing required field in JSON required_fields: " + field)
        require(field in template, "missing required field in receipt_template: " + field)
        require(field in meanings, "missing field meaning: " + field)
        require(field in combined, "missing required field text: " + field)


def check_categories(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    categories = payload.get("approved_library_categories", [])
    for category in [
        "research_papers",
        "architecture_references",
        "engel_manuals",
        "offline_docs",
        "math",
        "coding_languages",
    ]:
        require(category in categories, "missing category in JSON: " + category)
        require(category in lowered, "missing category text: " + category)


def check_receipt_boundary(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    boundary = payload.get("receipt_boundary", {})
    for key in [
        "receipt_template_only",
        "records_human_action_after_the_fact",
        "does_not_move_or_copy_files",
        "does_not_place_material",
        "does_not_import_material",
        "does_not_create_approved_library_content",
        "not_trusted_memory",
        "no_learning_trigger",
        "no_runtime_trigger",
        "no_indexing",
        "no_execution",
        "no_training",
    ]:
        require(boundary.get(key) is True, "receipt boundary flag must be true: " + key)

    safety = payload.get("safety_boundary", {})
    for key in [
        "no_file_operations",
        "no_copy",
        "no_move",
        "no_sync",
        "no_folder_scan",
        "no_download",
        "no_indexing",
        "no_embedding",
        "no_training",
        "no_runtime_loading",
        "no_execution",
        "no_trusted_memory_write",
        "no_storage_probing",
    ]:
        require(safety.get(key) is True, "safety boundary flag must be true: " + key)

    confirmations = payload.get("required_confirmations", [])
    for field in [
        "human_confirms_manual_action",
        "no_automation_used",
        "not_trusted_memory",
        "no_indexing_performed",
        "no_execution_performed",
    ]:
        require(field in confirmations, "missing required confirmation: " + field)

    for phrase in [
        "after-the-fact receipt",
        "human reports the manual action already happened",
        "this receipt template does not move files",
        "not a file operation",
        "not an importer",
        "not trusted memory",
        "does not cause the placement",
        "does not perform material operations",
    ]:
        require(phrase in lowered, "missing receipt boundary phrase: " + phrase)


def check_inactive_denials(payload: dict) -> None:
    denials = payload.get("inactive_behavior_denials", {})
    require(isinstance(denials, dict), "inactive_behavior_denials must be a dict")
    for key, value in denials.items():
        require(value is False, "inactive behavior denial must be false: " + key)


def check_no_active_implementation_terms(payload_text: str, md: str, report: str) -> None:
    combined_lower = (payload_text + "\n" + md + "\n" + report).lower()
    for phrase in [
        "file operation implementation",
        "copy implementation",
        "move implementation",
        "sync implementation",
        "import implementation",
        "scan implementation",
        "download implementation",
        "index implementation",
        "runtime loader implementation",
        "trusted memory writer",
        "active receipt writer",
        "material placement engine",
    ]:
        require(phrase not in combined_lower, "forbidden active implementation phrase found: " + phrase)


def check_verifier_ast_safety() -> None:
    source = read(THIS_FILE)
    tree = ast.parse(source)
    allowed_import_roots = {"ast", "json", "pathlib"}
    forbidden_calls = {
        "copy",
        "copytree",
        "move",
        "rename",
        "replace",
        "unlink",
        "rmdir",
        "mkdir",
        "write_text",
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
                require(root in allowed_import_roots, "unexpected import in verifier: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root in allowed_import_roots or node.module == "__future__", "unexpected import-from in verifier: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if name == "walk" and isinstance(node.func.value, ast.Name) and node.func.value.id == "ast":
                    continue
            require(name not in forbidden_calls, "forbidden active call in verifier: " + name)


def main() -> int:
    try:
        payload, payload_text, md, report = load_receipt()
        require(payload.get("schema_name") == "engel_manual_import_receipt_v1", "schema_name mismatch")
        require(payload.get("schema_version") == "1.0", "schema_version mismatch")
        combined = payload_text + "\n" + md + "\n" + report
        check_statuses(combined)
        check_required_fields(payload, combined)
        check_categories(payload, combined)
        check_receipt_boundary(payload, combined)
        check_inactive_denials(payload)
        check_no_active_implementation_terms(payload_text, md, report)
        check_verifier_ast_safety()
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Manual Import Receipt V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Manual Import Receipt V1 verifier")
    print("- receipt JSON, Markdown, and report exist and parse")
    print("- required fields, statuses, categories, and confirmations are present")
    print("- receipt remains after-the-fact and has no file-operation behavior")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
