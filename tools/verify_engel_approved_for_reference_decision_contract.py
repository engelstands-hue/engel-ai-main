#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_APPROVED_FOR_REFERENCE_DECISION_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_APPROVED_FOR_REFERENCE_DECISION_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_APPROVED_FOR_REFERENCE_DECISION_CONTRACT_V1.md"
THIS_FILE = Path(__file__).resolve()


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_contract() -> tuple[dict, str, str, str]:
    for path in [CONTRACT_JSON, CONTRACT_MD, REPORT]:
        require(path.exists(), "missing required file: " + str(path))
    payload = json.loads(read(CONTRACT_JSON))
    return payload, json.dumps(payload, sort_keys=True), read(CONTRACT_MD), read(REPORT)


def check_statuses(combined: str) -> None:
    for status in [
        "CONTRACT_ONLY",
        "REFERENCE_DECISION_BOUNDARY_ONLY",
        "HUMAN_APPROVAL_REQUIRED",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing required status: " + status)


def check_future_token(payload: dict, combined: str) -> None:
    token = "APPROVE_MARK_APPROVED_FOR_REFERENCE"
    require(token in combined, "missing future token")
    token_payload = payload.get("future_token", {})
    require(token_payload.get("token") == token, "future token mismatch")
    for key in [
        "documented_only_in_this_step",
        "does_not_create_writer",
        "does_not_mark_material_now",
        "does_not_import_material",
        "does_not_write_trusted_memory",
        "does_not_grant_training_permission",
        "does_not_grant_indexing_permission",
        "does_not_grant_runtime_permission",
        "does_not_grant_execution_permission",
    ]:
        require(token_payload.get(key) is True, "future token flag must be true: " + key)
    require(token_payload.get("active_now") is False, "future token must be inactive now")


def check_required_conditions(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    conditions = payload.get("required_future_conditions", [])
    for condition in [
        "queue record exists",
        "human review receipt exists",
        "receipt says approved_for_reference",
        "source/provenance acceptable",
        "safety flags resolved or acknowledged",
        "human explicitly confirms reference-only approval",
        "human confirms not trusted memory",
        "human confirms no training/indexing/runtime/execution permission",
    ]:
        require(condition in conditions, "missing condition in JSON: " + condition)
        require(condition in lowered, "missing condition text: " + condition)


def check_boundary_statements(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    for phrase in [
        "approved-for-reference means research/reference only",
        "approved-for-reference is not trusted memory",
        "approved-for-reference is not training permission",
        "approved-for-reference is not runtime permission",
        "approved-for-reference is not execution permission",
        "approved-for-reference is not indexing permission",
        "approved-for-reference is not import permission",
        "approved-for-reference is not a memory candidate proposal",
        "approved-for-reference does not bypass prompt injection guard",
        "approved-for-reference does not bypass untrusted content guard",
        "approved-for-reference does not override authority hierarchy",
    ]:
        require(phrase in lowered, "missing boundary statement: " + phrase)

    scope = payload.get("future_decision_scope", {})
    for key in [
        "reference_only",
        "human_approval_required",
        "queue_record_required",
        "human_review_receipt_required",
        "receipt_must_say_approved_for_reference",
        "source_provenance_must_be_acceptable",
        "safety_flags_must_be_resolved_or_acknowledged",
        "no_trusted_memory_write",
        "no_learning_trigger",
        "no_runtime_trigger",
        "no_model_training",
        "no_fine_tuning",
        "no_indexing",
        "no_embedding",
        "no_execution",
        "no_import",
        "no_copy",
        "no_move",
        "no_sync",
        "no_scan",
        "no_writer_behavior",
    ]:
        require(scope.get(key) is True, "future decision scope flag must be true: " + key)


def check_inactive_denials(payload: dict) -> None:
    denials = payload.get("inactive_behavior_denials", {})
    require(isinstance(denials, dict), "inactive behavior denials missing")
    for key, value in denials.items():
        require(value is False, "inactive behavior denial must be false: " + key)
    for key in [
        "write_approved_for_reference_metadata",
        "create_writer",
        "mark_material_approved_now",
        "import_material",
        "copy_material",
        "move_material",
        "sync_material",
        "scan_material",
        "recursive_scan",
        "index_content",
        "embed_content",
        "summarize_real_material",
        "execute_content",
        "train_model",
        "fine_tune_model",
        "load_runtime_content",
        "write_trusted_memory",
        "start_worker",
        "start_runtime",
        "change_routes",
        "change_startup",
        "change_source_behavior",
    ]:
        require(key in denials, "inactive behavior denial missing: " + key)


def check_no_writer_behavior(combined: str) -> None:
    lowered = combined.lower()
    for phrase in [
        "does not create a writer",
        "token is inactive now",
        "no writer is created",
        "no approved-for-reference metadata is written",
        "no material is marked approved now",
    ]:
        require(phrase in lowered, "missing no-writer/no-action phrase: " + phrase)


def check_forbidden_active_behavior(payload_text: str, md: str, report: str) -> None:
    combined_lower = (payload_text + "\n" + md + "\n" + report).lower()
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
        require(term not in combined_lower, "forbidden active-behavior term found in contract/report: " + term)

    forbidden_phrases = [
        "writer " + "implementation",
        "file write " + "implementation",
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
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if name == "walk" and isinstance(node.func.value, ast.Name) and node.func.value.id == "ast":
                    continue
            require(name not in {"copytree", "move", "rglob", "run", "Popen", "system"}, "forbidden active call in verifier: " + name)


def main() -> int:
    try:
        payload, payload_text, md, report = load_contract()
        require(payload.get("schema_name") == "engel_approved_for_reference_decision_contract_v1", "schema_name mismatch")
        require(payload.get("schema_version") == "1.0", "schema_version mismatch")
        combined = payload_text + "\n" + md + "\n" + report
        check_statuses(combined)
        check_future_token(payload, combined)
        check_required_conditions(payload, combined)
        check_boundary_statements(payload, combined)
        check_inactive_denials(payload)
        check_no_writer_behavior(combined)
        check_forbidden_active_behavior(payload_text, md, report)
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Approved-for-Reference Decision Contract V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Approved-for-Reference Decision Contract V1 verifier")
    print("- contract JSON, Markdown, and report exist and parse")
    print("- future token is documented but inactive")
    print("- required conditions and reference-only boundaries are present")
    print("- no approved-for-reference writer, material approval, trusted memory, training, runtime, indexing, or execution behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
