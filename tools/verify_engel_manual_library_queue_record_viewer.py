#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "engel_manual_library_queue_record_viewer.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MANUAL_LIBRARY_QUEUE_RECORD_VIEWER_V1.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_manual_library_queue_record_viewer as viewer  # noqa: E402


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sample_record_payload() -> dict:
    return {
        "record_labels": [
            "REAL_QUEUE_RECORD_METADATA_ONLY",
            "NOT_APPROVAL",
            "NOT_RECEIPT",
            "NOT_TRUSTED_MEMORY",
            "NO_MATERIAL_CONTENT",
            "NO_AUTOMATION_TRIGGERED",
        ],
        "queue_record_id": "VIEWER_SAMPLE_RECORD",
        "material_id": "VIEWER_SAMPLE_MATERIAL",
        "title": "Viewer sample metadata only",
        "category": "math",
        "subcategory": "viewer_sample",
        "review_state": "human_review_pending",
        "receipt_status": "receipt_missing",
        "receipt_reference": "receipt_missing",
        "safety_flags": ["metadata_only", "viewer_sample"],
        "next_manual_action": "Human reviewer decides the next manual step.",
    }


def check_required_files() -> tuple[str, str]:
    require(VIEWER.exists(), "missing manual library queue record viewer")
    require(REPORT.exists(), "missing manual library queue record viewer report")
    return read(VIEWER), read(REPORT)


def check_required_text(combined: str) -> None:
    for status in [
        "READ_ONLY_VIEWER",
        "METADATA_ONLY",
        "NO_QUEUE_MUTATION",
        "NO_APPROVAL_ACTION",
        "NO_RECEIPT_ACTION",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing viewer status: " + status)

    for phrase in [
        "read-only viewer",
        "metadata only",
        "bounded repo-local queue metadata",
        "show safety labels",
        "show review states",
        "show receipt status",
        "show next manual action",
        "no queue mutation",
        "no approval action",
        "no receipt action",
        "no trusted-memory write",
    ]:
        require(phrase in combined.lower(), "missing viewer boundary wording: " + phrase)


def check_ast_safety(source: str) -> None:
    tree = ast.parse(source)
    forbidden_imports = {
        "os",
        "shutil",
        "subprocess",
        "requests",
        "urllib",
        "socket",
        "glob",
    }
    forbidden_calls = {
        "open",
        "write",
        "write_text",
        "writelines",
        "mkdir",
        "unlink",
        "rename",
        "replace",
        "rmdir",
        "copy",
        "copytree",
        "move",
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
    forbidden_imported_names = {
        "write_queue_record_metadata",
        "build_queue_record_metadata",
        "validate_approval_token",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                require(root not in forbidden_imports, "forbidden import in viewer: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root not in forbidden_imports, "forbidden import-from in viewer: " + str(node.module))
            for alias in node.names:
                require(alias.name not in forbidden_imported_names, "viewer imported writer action helper: " + alias.name)
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            require(name not in forbidden_calls, "forbidden mutation or active call in viewer: " + name)
        elif isinstance(node, ast.FunctionDef):
            lowered = node.name.lower()
            for fragment in ["write", "create", "delete", "approve", "receipt_action", "mutate"]:
                require(fragment not in lowered, "forbidden action-like viewer function: " + node.name)


def check_viewer_constants() -> None:
    for status in [
        "READ_ONLY_VIEWER",
        "METADATA_ONLY",
        "NO_QUEUE_MUTATION",
        "NO_APPROVAL_ACTION",
        "NO_RECEIPT_ACTION",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in viewer.VIEWER_STATUS, "viewer status constant missing: " + status)

    require(viewer.QUEUE_METADATA_ROOT == ROOT / "memory" / "approved_library_manual_review_queue", "viewer must use writer bounded queue metadata root")
    for key in [
        "read_only_viewer",
        "metadata_only",
        "no_queue_mutation",
        "no_approval_action",
        "no_receipt_action",
        "not_trusted_memory",
        "no_material_import",
        "no_external_location_scan",
        "no_indexing",
        "no_embedding",
        "no_execution",
        "no_trusted_memory_write",
    ]:
        require(viewer.READ_ONLY_BOUNDARY.get(key) is True, "viewer boundary flag missing: " + key)


def check_read_only_smoke() -> None:
    manifest = viewer.build_viewer_manifest()
    require(manifest["bounded_queue_metadata_root"].endswith("memory\\approved_library_manual_review_queue") or manifest["bounded_queue_metadata_root"].endswith("memory/approved_library_manual_review_queue"), "manifest queue root mismatch")

    records = viewer.list_queue_record_views()
    require(isinstance(records, list), "viewer list result must be a list")

    record_view = viewer.build_record_view(sample_record_payload())
    require(record_view["queue_record_id"] == "VIEWER_SAMPLE_RECORD", "record view id mismatch")
    require(record_view["review_state"] == "human_review_pending", "record view state mismatch")
    require(record_view["receipt_status"] == "receipt_missing", "record view receipt status mismatch")
    require(record_view["read_only_boundary"]["no_queue_mutation"] is True, "record view mutation boundary missing")

    rendered = viewer.render_record_view(record_view).lower()
    for phrase in [
        "read-only viewer",
        "metadata only",
        "no queue mutation",
        "no approval action",
        "no receipt action",
        "not trusted memory",
    ]:
        require(phrase in rendered, "rendered view missing phrase: " + phrase)

    try:
        viewer.list_queue_record_paths(ROOT / "reports")
    except viewer.QueueRecordPathError:
        pass
    else:
        raise CheckFailure("viewer accepted queue root outside bounded metadata folder")


def main() -> int:
    try:
        source, report = check_required_files()
        check_required_text(source + "\n" + report)
        check_ast_safety(source)
        check_viewer_constants()
        check_read_only_smoke()
    except (CheckFailure, SyntaxError, viewer.QueueRecordViewerError, viewer.QueueRecordPathError) as exc:
        print("FAIL: Engel Manual Library Queue Record Viewer V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Manual Library Queue Record Viewer V1 verifier")
    print("- viewer exists and uses the bounded repo-local queue metadata root")
    print("- viewer lists/displays metadata only and performs no queue mutation")
    print("- viewer exposes labels, review state, receipt status, and next manual action")
    print("- viewer contains no edit/create/delete/approve/import/scan/index/embed/execute/trusted-memory behavior")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
