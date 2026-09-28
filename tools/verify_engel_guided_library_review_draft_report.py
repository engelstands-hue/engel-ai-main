#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRAFT_BUILDER = ROOT / "engel_guided_library_review_draft_report.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_GUIDED_LIBRARY_REVIEW_DRAFT_REPORT_V1.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_files() -> tuple[str, str]:
    require(DRAFT_BUILDER.exists(), "missing draft report builder")
    require(REPORT.exists(), "missing draft report report")
    require(DRAFT_BUILDER.is_file(), "draft report builder path is not a file")
    require(REPORT.is_file(), "draft report report path is not a file")
    return read(DRAFT_BUILDER), read(REPORT)


def check_required_text(combined: str) -> None:
    for label in [
        "DRAFT_ONLY",
        "NOT_REAL_QUEUE_RECORD",
        "NOT_APPROVAL",
        "NOT_RECEIPT",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in combined, "missing draft label: " + label)
    for status in [
        "DRAFT_REPORT_ONLY",
        "DRY_RUN_ONLY",
        "HUMAN_GUIDED",
        "NO_REAL_QUEUE_RECORDS",
        "NO_REAL_APPROVALS",
        "NO_REAL_RECEIPTS",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing status: " + status)
    for phrase in [
        "draft report only",
        "dry run only",
        "not a real queue record",
        "not an approval",
        "not a receipt",
        "not trusted memory",
        "no automation triggered",
        "no queue runtime/worker",
        "no trusted-memory write",
        "human authority remains required",
    ]:
        require(phrase in combined, "missing required boundary phrase: " + phrase)


def check_ast_safety(source: str) -> None:
    tree = ast.parse(source)
    forbidden_imports = {"os", "shutil", "subprocess", "requests", "urllib", "socket", "pathlib"}
    forbidden_calls = {
        "open",
        "write",
        "write_text",
        "writelines",
        "unlink",
        "rename",
        "replace",
        "rmdir",
        "mkdir",
        "copy",
        "copytree",
        "move",
        "run",
        "Popen",
        "system",
        "startfile",
    }
    forbidden_function_fragments = [
        "write_queue",
        "create_queue_record",
        "create_approval",
        "create_receipt",
        "write_trusted_memory",
        "start_worker",
        "queue_worker",
    ]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "forbidden import: " + alias.name)
        if isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            require(module not in forbidden_imports, "forbidden import from: " + (node.module or ""))
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            require(name not in forbidden_calls, "forbidden active call: " + name)
        if isinstance(node, ast.FunctionDef):
            lowered = node.name.lower()
            for fragment in forbidden_function_fragments:
                require(fragment not in lowered, "forbidden queue/trust writer function: " + node.name)


def check_dry_run_only(source: str) -> None:
    lowered = source.lower()
    require("render_draft_report" in source, "render_draft_report function missing")
    require("build_draft_report" in source, "build_draft_report function missing")
    require("queue_record_id" not in lowered, "draft builder should not create queue_record_id")
    require("trusted_memory_write" not in lowered, "draft builder should not expose trusted_memory_write")
    require("reports/drafts" not in lowered, "draft builder should not save reports")
    require("reports/codex_bridge" not in lowered, "draft builder should not save reports")


def main() -> int:
    try:
        source, report = check_files()
        check_required_text(source + "\n" + report)
        check_ast_safety(source)
        check_dry_run_only(source)
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Guided Library Review Draft Report V1 verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
