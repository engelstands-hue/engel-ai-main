#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_MANUAL_APPROVED_LIBRARY_IMPORT_ASSISTANT_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_MANUAL_APPROVED_LIBRARY_IMPORT_ASSISTANT_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MANUAL_APPROVED_LIBRARY_IMPORT_ASSISTANT_CONTRACT_V1.md"
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
        "HUMAN_GUIDED_IMPORT_PLANNING_ONLY",
        "NO_FILE_OPERATIONS",
        "NO_AUTOMATIC_IMPORT",
        "NO_COPY",
        "NO_MOVE",
        "NO_SYNC",
        "NOT_TRUSTED_MEMORY",
    ]:
        require(status in combined, "missing required status: " + status)


def check_future_only_language(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    require(payload.get("future_only") is True, "future_only flag must be true")
    for phrase in [
        "future-only",
        "contract-only",
        "human-guided import planning only",
        "manual instructions only",
        "the human remains the actor",
        "engel only plans and reminds",
    ]:
        require(phrase in lowered, "missing future-only/manual-boundary wording: " + phrase)


def check_categories(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    categories = payload.get("approved_library_categories", [])
    require(isinstance(categories, list), "approved_library_categories must be a list")
    slugs = {item.get("slug") for item in categories if isinstance(item, dict)}
    for category in [
        "research_papers",
        "architecture_references",
        "engel_manuals",
        "offline_docs",
        "math",
        "coding_languages",
    ]:
        require(category in slugs, "missing category in JSON: " + category)
        require(category in lowered, "missing category text: " + category)


def check_future_assistant_scope(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    may = payload.get("future_assistant_may", [])
    must_not = payload.get("future_assistant_must_not", [])
    for item in [
        "tell a human where a file should go",
        "display safe manual instructions",
        "remind about receipts and reference approval",
        "generate a checklist",
    ]:
        require(item in may, "missing future assistant may item: " + item)
        require(item in lowered, "missing future assistant may text: " + item)

    for item in [
        "copy files",
        "move files",
        "sync folders",
        "scan folders",
        "download files",
        "index content",
        "embed content",
        "train models",
        "load runtime content",
        "write trusted memory",
    ]:
        require(item in must_not, "missing future assistant must-not item: " + item)
        require(item in lowered, "missing future assistant must-not text: " + item)


def check_boundaries(payload: dict, combined: str) -> None:
    lowered = combined.lower()
    safety = payload.get("safety_boundary", {})
    for key in [
        "contract_only",
        "human_guided_import_planning_only",
        "future_only",
        "no_file_operations",
        "no_automatic_import",
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
        "not_trusted_memory",
    ]:
        require(safety.get(key) is True, "safety boundary flag must be true: " + key)

    denials = payload.get("inactive_behavior_denials", {})
    require(isinstance(denials, dict), "inactive_behavior_denials must be a dict")
    for key, value in denials.items():
        require(value is False, "inactive behavior denial must be false: " + key)

    for phrase in [
        "does not implement copying",
        "does not create folders",
        "does not touch files",
        "does not probe",
        "approved_library is not trusted memory",
        "category selection is not permission",
        "this contract does not create folders and does not touch files",
    ]:
        require(phrase in lowered, "missing boundary phrase: " + phrase)


def check_no_active_implementation_terms(payload_text: str, md: str, report: str) -> None:
    combined_lower = (payload_text + "\n" + md + "\n" + report).lower()
    for phrase in [
        "copy implementation",
        "move implementation",
        "sync implementation",
        "import implementation",
        "scan implementation",
        "download implementation",
        "index implementation",
        "runtime loader implementation",
        "trusted memory writer",
        "automatic placement engine",
        "background worker",
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
        payload, payload_text, md, report = load_contract()
        require(payload.get("schema_name") == "engel_manual_approved_library_import_assistant_contract_v1", "schema_name mismatch")
        require(payload.get("schema_version") == "1.0", "schema_version mismatch")
        combined = payload_text + "\n" + md + "\n" + report
        check_statuses(combined)
        check_future_only_language(payload, combined)
        check_categories(payload, combined)
        check_future_assistant_scope(payload, combined)
        check_boundaries(payload, combined)
        check_no_active_implementation_terms(payload_text, md, report)
        check_verifier_ast_safety()
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Manual Approved Library Import Assistant Contract V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Manual Approved Library Import Assistant Contract V1 verifier")
    print("- contract JSON, Markdown, and report exist and parse")
    print("- required statuses, categories, and future-only assistant boundaries are present")
    print("- contract defines manual guidance only and no active file operations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
