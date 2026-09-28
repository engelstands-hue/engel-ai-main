#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_OFFICE = ROOT / "engel_research_office.py"
COMPANION = ROOT / "engel_companion.py"
SURFACE = ROOT / "engel_guided_library_review_surface.py"
DRAFT_REPORT = ROOT / "engel_guided_library_review_draft_report.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_GUIDED_LIBRARY_REVIEW_UI_TAB_V1.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def between(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    require(start_index >= 0, "missing marker: " + start)
    end_index = text.find(end, start_index)
    require(end_index >= 0, "missing marker: " + end)
    return text[start_index:end_index]


def check_files() -> tuple[str, str, str]:
    for path in [RESEARCH_OFFICE, COMPANION, SURFACE, DRAFT_REPORT, REPORT]:
        require(path.exists(), "missing required file: " + str(path.relative_to(ROOT)))
        require(path.is_file(), "required path is not a file: " + str(path.relative_to(ROOT)))
    return read(RESEARCH_OFFICE), read(COMPANION), read(REPORT)


def check_required_ui_text(source: str) -> None:
    required = [
        'self.tabs.addTab(self._make_guided_library_review_tab(), "Guided Library Review")',
        "Guided Library Review",
        "Fast Safety Gate",
        "Stop Conditions",
        "Category Picker",
        "Risk Checks",
        "Decision Helper",
        "Required Metadata",
        "Draft Preview",
        "Final Human Confirmation",
        "Copy Draft Report",
        "NO REAL QUEUE WRITER",
        "draft-only",
        "draft preview",
        "no real queue records",
        "no approvals",
        "no receipts",
        "no automation",
        "human authority remains required",
        "no real queue creation",
        "no import",
        "no scanning",
        "no indexing",
        "no memory writes",
        "no background workers",
        "no route/startup changes",
        "no provider/network/browser calls",
        "no package installs",
        "no model/runtime loading",
    ]
    lowered = source.lower()
    for needle in required:
        haystack = lowered if needle == needle.lower() else source
        require(needle in haystack, "missing UI text: " + needle)
    for label in [
        "DRAFT_ONLY",
        "NOT_REAL_QUEUE_RECORD",
        "NOT_APPROVAL",
        "NOT_RECEIPT",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in source, "missing required draft label: " + label)


def check_ui_block_safety(source: str) -> None:
    panel = between(
        source,
        "# ENGEL_GUIDED_LIBRARY_REVIEW_UI_TAB_V1_PANEL_START",
        "# ENGEL_GUIDED_LIBRARY_REVIEW_UI_TAB_V1_PANEL_END",
    )
    imports = between(
        source,
        "# ENGEL_GUIDED_LIBRARY_REVIEW_UI_TAB_V1_IMPORTS_START",
        "# ENGEL_GUIDED_LIBRARY_REVIEW_UI_TAB_V1_IMPORTS_END",
    )
    for needle in [
        "import shutil",
        "import subprocess",
        "import requests",
        "import urllib",
        "import socket",
        "os.walk",
        ".rglob(",
        ".glob(",
        "copytree(",
        "move(",
        "Popen(",
        "subprocess.",
        "requests.",
        "urllib.",
        "socket.",
        "QThread",
        "threading.",
        "start_worker",
        "queue_worker",
        "active_queue_runtime",
        "write_trusted_memory",
        "create_queue_record",
        "create_approval",
        "create_receipt",
        "import_material",
        "route_mutation",
        "startup_mutation",
        "source_mutation",
    ]:
        require(needle not in panel, "forbidden active behavior in UI block: " + needle)
    for needle in ["from engel_guided_library_review_draft_report import", "from engel_guided_library_review_surface import"]:
        require(needle in imports, "missing local UI helper import: " + needle)


def check_no_real_queue_action(source: str) -> None:
    tree = ast.parse(source)
    forbidden_button_words = [
        "create queue",
        "create real queue",
        "real queue creation",
        "approve material",
        "create receipt",
        "write memory",
        "import material",
    ]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        if func_name != "QPushButton":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        button_text = node.args[0].value.lower()
        for phrase in forbidden_button_words:
            require(phrase not in button_text, "forbidden real queue/action button exists: " + node.args[0].value)


def check_report(report: str) -> None:
    for needle in [
        "ENGEL GUIDED LIBRARY REVIEW UI TAB V1",
        "Status COMPLETE",
        "Files read first",
        "Files created/updated",
        "Guided Library Review tab",
        "Fast Safety Gate",
        "Stop Conditions",
        "Category Picker",
        "Risk Checks",
        "Decision Helper",
        "Required Metadata",
        "Draft Preview",
        "Final Human Confirmation",
        "Copy Draft Report",
        "DRAFT_ONLY",
        "NOT_REAL_QUEUE_RECORD",
        "NOT_APPROVAL",
        "NOT_RECEIPT",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
        "no real queue records, approvals, or receipts were created",
        "no import/copy/move/sync/index/scan/execute/train/load behavior",
        "no queue runtime or queue worker",
        "no storage probing",
        "Verification results",
        "GUI smoke",
        "Packaging skipped",
        "Git status summary",
    ]:
        require(needle in report, "report missing text: " + needle)


def main() -> int:
    try:
        research_source, _companion_source, report = check_files()
        check_required_ui_text(research_source)
        check_ui_block_safety(research_source)
        check_no_real_queue_action(research_source)
        check_report(report)
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Guided Library Review UI tab verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
