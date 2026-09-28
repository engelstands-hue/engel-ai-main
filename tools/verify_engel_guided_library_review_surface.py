#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "engel_guided_library_review_surface.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_GUIDED_LIBRARY_REVIEW_SURFACE_V1.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_files() -> tuple[str, str]:
    require(SURFACE.exists(), "missing guided library review surface")
    require(REPORT.exists(), "missing guided library review surface report")
    require(SURFACE.is_file(), "surface path is not a file")
    require(REPORT.is_file(), "report path is not a file")
    return read(SURFACE), read(REPORT)


def check_required_text(combined: str) -> None:
    for status in [
        "SURFACE_ONLY",
        "GUIDED_DRAFT_ONLY",
        "HUMAN_GUIDED",
        "NO_REAL_QUEUE_RECORDS",
        "NO_ACTIVE_QUEUE_RUNTIME",
        "NO_QUEUE_WORKER",
        "NO_AUTOMATIC_IMPORT",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing status: " + status)
    for label in [
        "DRAFT_ONLY",
        "NOT_REAL_QUEUE_RECORD",
        "NOT_APPROVAL",
        "NOT_RECEIPT",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in combined, "missing draft label: " + label)
    for phrase in [
        "guided surface exists",
        "draft preview only",
        "no real queue records",
        "no approvals",
        "no receipts",
        "no automation",
        "no active queue runtime",
        "no queue worker",
        "no trusted-memory writes",
        "no import/copy/move/sync/scan/index/embed/summarize/execute/train/load",
        "human authority remains required",
    ]:
        require(phrase in combined, "missing boundary phrase: " + phrase)
    for category in ["math", "coding_languages"]:
        require(category in combined, "missing category: " + category)


def check_surface_ast(source: str) -> None:
    tree = ast.parse(source)
    forbidden_imports = {"os", "shutil", "subprocess", "requests", "urllib", "socket"}
    forbidden_calls = {
        "open",
        "write",
        "write_text",
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


def main() -> int:
    try:
        source, report = check_files()
        check_required_text(source + "\n" + report)
        check_surface_ast(source)
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Guided Library Review Surface V1 verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
