#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

VIEWER = ROOT / "engel_ai_receipt_viewer.py"
COMPANION = ROOT / "engel_companion.py"
SUPER_SWARM = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
RECEIPT_ROOT = ROOT / "reports" / "ai_proceed_receipts"


class CheckFailure(Exception):
    pass


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _term(*parts: str) -> str:
    return "".join(parts)


def _method_body(text: str, marker: str) -> str:
    start = text.find(marker)
    _require(start >= 0, f"missing method marker: {marker}")
    next_method = text.find("\n    def ", start + len(marker))
    next_class = text.find("\nclass ", start + len(marker))
    candidates = [idx for idx in (next_method, next_class) if idx >= 0]
    end = min(candidates) if candidates else len(text)
    return text[start:end]


def _forbidden_terms() -> list[str]:
    return [
        _term("op", "enai"),
        _term("anth", "ropic"),
        _term("api", "_", "key"),
        _term("requests", "."),
        _term("http", "://"),
        _term("https", "://"),
        _term("sock", "et"),
        _term("web", "sock", "et"),
        _term("u", "dp"),
        _term("t", "cp"),
        _term("blue", "tooth"),
        _term("md", "ns"),
        _term("zero", "conf"),
        _term("thread", "ing"),
        _term("multi", "processing"),
        _term("watch", "dog"),
        _term("sche", "dule"),
        _term("while", " True"),
        _term("Start", "-", "Process"),
        _term("os", ".", "system"),
        _term("P", "open"),
        _term("shell", "=", "True"),
        _term("local", "host", ":", "11434"),
        _term("ol", "lama"),
    ]


def _load_viewer_module():
    spec = importlib.util.spec_from_file_location("engel_ai_receipt_viewer", VIEWER)
    _require(spec is not None and spec.loader is not None, "could not load viewer helper spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_ai_receipt_viewer"] = module
    spec.loader.exec_module(module)
    return module


def check_viewer_source_static() -> None:
    source = _read(VIEWER)
    tree = ast.parse(source)

    for needle in [
        "class ReceiptSummary",
        "def receipts_root() -> Path:",
        "def list_receipts(",
        "def parse_receipt_summary(",
        "def read_receipt_bounded(",
        "def is_safe_receipt_path(",
        'ROOT / "reports" / "ai_proceed_receipts"',
        "MAX_RECEIPT_DISPLAY_CHARS = 12000",
        "root.iterdir()",
        'child.suffix.lower() == ".md"',
        "resolved.parent == root",
    ]:
        _require(needle in source, f"missing viewer helper text: {needle}")

    lowered = source.lower()
    for term in _forbidden_terms():
        _require(term.lower() not in lowered, f"forbidden viewer helper pattern present: {term}")

    for forbidden in [
        "rglob",
        "glob(\"**",
        "glob('**",
        "walk(",
        "write_text",
        "write_bytes",
        ".write(",
        "unlink(",
        "remove(",
        "rmdir(",
        "mkdir(",
        "replace(",
        "rename(",
        "exec(",
        "eval(",
        "__import__",
    ]:
        _require(forbidden not in source, f"forbidden viewer helper operation present: {forbidden}")

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    blocked_imports = {
        _term("requests"),
        _term("sock", "et"),
        _term("web", "sock", "et"),
        _term("thread", "ing"),
        _term("multi", "processing"),
        _term("sub", "process"),
    }
    _require(not (imported & blocked_imports), f"blocked imports present: {sorted(imported & blocked_imports)}")


def check_viewer_behavior() -> None:
    module = _load_viewer_module()
    _require(module.receipts_root().resolve() == RECEIPT_ROOT.resolve(), "receipt root mismatch")

    outside = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_PROCEED_ACTION_RECEIPTS.md"
    _require(module.is_safe_receipt_path(outside) is False, "outside report path should be rejected")
    _require(module.is_safe_receipt_path(Path(".." ) / "CODEX_JOB.md") is False, "relative escape should be rejected")
    _require(module.is_safe_receipt_path(Path("not_a_receipt.txt")) is False, "non-markdown receipt should be rejected")
    _require(module.is_safe_receipt_path(Path("\\\\server\\share\\receipt.md")) is False, "network path should be rejected")

    summaries = module.list_receipts(limit=25)
    _require(isinstance(summaries, list), "list_receipts must return a list")
    _require(len(summaries) <= 25, "list_receipts exceeded limit")
    for summary in summaries:
        _require(summary.path.resolve().parent == RECEIPT_ROOT.resolve(), "summary path outside receipt root")
        _require(summary.filename.endswith(".md"), "summary filename is not markdown")
        _require(summary.status, "summary status missing")
        _require(summary.intent, "summary intent missing")
        text = module.read_receipt_bounded(summary.path, max_chars=12000)
        _require(len(text) <= 12035, "bounded receipt read is too large")
        break


def check_gui_static() -> None:
    companion = _read(COMPANION)
    super_swarm = _read(SUPER_SWARM)

    for source, label, refresh_marker, open_marker in [
        (companion, "Companion", "def refresh_ai_receipts(", "def open_selected_ai_receipt("),
        (super_swarm, "Super Swarm", "def _refresh_ai_receipts(", "def _open_selected_ai_receipt("),
    ]:
        for needle in [
            "PROCEED RECEIPTS",
            "REPORT ONLY",
            "READ ONLY",
            "NOT TRUSTED MEMORY",
            "NO EXECUTION",
            "Refresh Receipts",
            "Open Selected",
            "list_receipts(limit=25)",
            "read_receipt_bounded",
            "is_safe_receipt_path",
            "setReadOnly(True)",
        ]:
            _require(needle in source, f"{label} missing receipt viewer text: {needle}")

        refresh_body = _method_body(source, refresh_marker)
        open_body = _method_body(source, open_marker)
        combined = refresh_body + "\n" + open_body
        for forbidden in [
            "write_proceed_receipt",
            "handle_human_command_mode_cli",
            "route_companion_text_or_command",
            "learning proposals apply",
            "APPROVE_REPORT",
            "APPROVE_INSTALL",
            ".setPlainText(content); exec",
        ]:
            _require(forbidden not in combined, f"{label} viewer must not trigger action/trust path: {forbidden}")
        _require("max_chars=12000" in open_body, f"{label} viewer must bound opened content")


def main() -> int:
    try:
        check_viewer_source_static()
        check_viewer_behavior()
        check_gui_static()
    except CheckFailure as exc:
        print(f"[FAIL] {exc}")
        return 1

    print("[OK] AI receipt viewer helper is read-only, bounded, and locally scoped.")
    print("[OK] GUI receipt viewers expose report-only/read-only/no-trust/no-execution labels.")
    print("[OK] Receipt viewer rejects paths outside reports\\ai_proceed_receipts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
