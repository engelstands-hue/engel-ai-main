#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "engel_core_continuity_status_surface.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CORE_CONTINUITY_DASHBOARD_STATUS_SURFACE_UPDATE.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists(), "missing required file: " + str(path.relative_to(ROOT)))
    require(path.is_file(), "required path is not a file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def normalize(text: str) -> str:
    lowered = text.lower().replace("`", "").replace("\\", "/")
    lowered = lowered.replace("approved-for-reference", "approved for reference")
    lowered = lowered.replace("trusted-memory", "trusted memory")
    lowered = lowered.replace("exists / not_exists", "exists/not_exists")
    lowered = re.sub(r"[^a-z0-9_/]+", " ", lowered)
    return " ".join(lowered.split())


def require_text(combined: str, needle: str, label: str) -> None:
    require(normalize(needle) in normalize(combined), label + " missing expected text: " + needle)


def check_required_text(combined: str) -> None:
    require_text(combined, "Controlled Approved Library Chain", "surface title")

    for status in [
        "STATUS_SURFACE_ONLY",
        "READ_ONLY_VIEW",
        "CORE_CONTINUITY_VISIBLE",
        "CONTROLLED_LIBRARY_CHAIN_VISIBLE",
        "NO_QUEUE_MUTATION",
        "NO_RECEIPT_MUTATION",
        "NO_APPROVAL_ACTION",
        "NO_IMPORT_ACTION",
        "NO_FILE_OPERATION_ACTION",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require_text(combined, status, "status")

    for component in [
        "Manual Queue Record Draft Schema V1",
        "Manual Queue Record Create Approval Contract V1",
        "Manual Queue Record Writer V1",
        "Queue Record Viewer V1",
        "Human Review Receipt Draft Surface V1",
        "Human Review Receipt Writer V1",
        "Approved-for-Reference Decision Contract V1",
        "Approved-for-Reference Metadata Writer V1",
        "Manual Approved Library Import Assistant Contract V1",
        "Manual Import Receipt V1",
        "Bounded File Presence Checker V1",
    ]:
        require_text(combined, component, "chain component")

    for token in [
        "APPROVE_CREATE_LIBRARY_QUEUE_RECORD",
        "APPROVE_WRITE_HUMAN_REVIEW_RECEIPT",
        "APPROVE_MARK_APPROVED_FOR_REFERENCE",
    ]:
        require_text(combined, token, "approval token")

    for phrase in [
        "tokens are narrow human approval gates",
        "tokens do not grant import/copy/move/sync/scanning/indexing/training/runtime/memory authority",
        "tokens do not bypass Prompt Injection Guard, Untrusted Content Guard, Authority Hierarchy, or memory proposal rules",
        "queue metadata is not material content",
        "queue record is not approval",
        "queue record is not receipt",
        "queue record is not trusted memory",
        "receipt metadata is not trusted memory",
        "approved-for-reference is not trusted memory",
        "approved-for-reference is not model training permission",
        "approved-for-reference is not runtime permission",
        "bounded file presence check does not prove file safety or trust",
        "separate memory candidate proposal is required",
    ]:
        require_text(combined, phrase, "safety statement")

    for phrase in [
        "one explicit path",
        "must stay under approved_library",
        "returns exists/not_exists only",
        "no content read",
        "no folder scan",
        "no recursion",
        "no hashing",
        "no import",
        "no indexing",
        "no trust assertion",
    ]:
        require_text(combined, phrase, "bounded checker statement")

    for badge in [
        "READ ONLY",
        "METADATA ONLY",
        "TOKEN REQUIRED",
        "NOT TRUSTED MEMORY",
    ]:
        require_text(combined, badge, "status badge")


def check_surface_ast(source: str) -> None:
    tree = ast.parse(source)
    forbidden_imports = {
        "os",
        "shutil",
        "subprocess",
        "requests",
        "urllib",
        "socket",
        "pathlib",
        "glob",
    }
    forbidden_calls = {
        "open",
        "read_text",
        "read_bytes",
        "write",
        "write_text",
        "write_bytes",
        "writelines",
        "mkdir",
        "unlink",
        "rename",
        "replace",
        "rmdir",
        "exists",
        "is_file",
        "iterdir",
        "glob",
        "rglob",
        "copy",
        "copytree",
        "move",
        "run",
        "Popen",
        "system",
        "startfile",
        "urlopen",
        "request",
        "connect",
        "send",
        "recv",
    }
    forbidden_function_fragments = [
        "create_queue",
        "write_queue",
        "create_receipt",
        "write_receipt",
        "approve",
        "import_file",
        "scan",
        "index_file",
        "embed",
        "train",
        "load_model",
        "queue_worker",
        "active_queue_runtime",
        "trusted_memory_write",
        "route_mutation",
        "startup_mutation",
        "source_mutation",
    ]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in forbidden_imports, "forbidden active import: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            require(module not in forbidden_imports, "forbidden active import from: " + (node.module or ""))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            require(name not in forbidden_calls, "forbidden active call: " + name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lowered = node.name.lower()
            for fragment in forbidden_function_fragments:
                require(fragment not in lowered, "forbidden behavior function name: " + node.name)


def check_surface_runtime() -> None:
    sys.path.insert(0, str(ROOT))
    import engel_core_continuity_status_surface as surface  # noqa: PLC0415

    payload = surface.build_controlled_library_chain_status()
    rendered = surface.render_controlled_library_chain_status()
    require(isinstance(payload, dict), "surface payload is not a dict")
    require(isinstance(rendered, str) and rendered.strip(), "surface render is empty")
    require(len(payload.get("components", [])) == 11, "surface should expose eleven controlled-chain components")
    require(payload.get("implementation_mode") == "module-only read-only status surface", "unexpected implementation mode")
    require(payload.get("no_queue_mutation") is True, "queue mutation boundary missing")
    require(payload.get("no_receipt_mutation") is True, "receipt mutation boundary missing")
    require(payload.get("no_approval_action") is True, "approval action boundary missing")
    require(payload.get("no_import_action") is True, "import action boundary missing")
    require(payload.get("no_file_operation_action") is True, "file operation boundary missing")


def main() -> int:
    try:
        surface_source = read(SURFACE)
        report_source = read(REPORT)
        combined = surface_source + "\n" + report_source
        check_required_text(combined)
        check_surface_ast(surface_source)
        check_surface_runtime()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Core Continuity dashboard status surface verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
