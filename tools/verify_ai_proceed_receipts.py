#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

RECEIPTS = ROOT / "engel_ai_proceed_receipts.py"
COMPANION = ROOT / "engel_companion.py"
SUPER_SWARM = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
AUTHORITY = "Josh > Guardian > Engel/runtime"


class CheckFailure(Exception):
    pass


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _method_body(text: str, marker: str) -> str:
    start = text.find(marker)
    _require(start >= 0, f"missing method marker: {marker}")
    next_method = text.find("\n    def ", start + len(marker))
    next_class = text.find("\nclass ", start + len(marker))
    candidates = [idx for idx in (next_method, next_class) if idx >= 0]
    end = min(candidates) if candidates else len(text)
    return text[start:end]


def _term(*parts: str) -> str:
    return "".join(parts)


def _forbidden_source_terms() -> list[str]:
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


def _load_receipt_module():
    spec = importlib.util.spec_from_file_location("engel_ai_proceed_receipts", RECEIPTS)
    _require(spec is not None and spec.loader is not None, "could not load receipt helper spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_ai_proceed_receipts"] = module
    spec.loader.exec_module(module)
    return module


def check_receipt_source_static() -> None:
    source = _read(RECEIPTS)
    tree = ast.parse(source)

    for needle in [
        "def receipts_root() -> Path:",
        "def safe_receipt_slug(",
        "def redact_receipt_text(",
        "def summarize_output(",
        "def write_proceed_receipt(",
        'ROOT / "reports" / "ai_proceed_receipts"',
        "Receipt is report-only: yes",
        "Trusted memory write: no",
        "Queue mutation: no",
        "Route mutation: no",
        "Source edit: no",
        "Autonomy: no",
        "Model-command execution: no",
        AUTHORITY,
        "max_chars=4000",
        "max_chars=3000",
        "path.write_text",
    ]:
        _require(needle in source, f"missing receipt helper text: {needle}")

    lowered = source.lower()
    for term in _forbidden_source_terms():
        _require(term.lower() not in lowered, f"forbidden receipt helper pattern present: {term}")

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

    _require('ROOT / "memory"' not in source, "receipt helper must not target memory")
    _require('ROOT / "queues"' not in source, "receipt helper must not target queues")
    _require("ROUTE_VERIFICATION_SET" not in source, "receipt helper must not mutate route metadata")
    _require(".py\"" not in source, "receipt helper must not target source files")


def check_receipt_behavior() -> Path:
    module = _load_receipt_module()
    expected_root = (ROOT / "reports" / "ai_proceed_receipts").resolve()
    actual_root = module.receipts_root().resolve()
    _require(actual_root == expected_root, f"receipt root mismatch: {actual_root}")

    hidden_a = "abc123-private"
    hidden_b = "xyz987-private"
    hidden_c = "super-private"
    plan = SimpleNamespace(
        user_text=(
            "research this folder D:\\Engel App\\reports "
            + ("API" + "_" + "KEY")
            + "="
            + hidden_a
            + " "
            + ("Author" + "ization")
            + ": "
            + ("Bear" + "er")
            + " "
            + hidden_b
        ),
        intent_type="human_file_research",
        matched_route="research folder <path>",
        action_summary="Research a local folder through the existing deterministic route.",
        target_summary="D:\\Engel App\\reports",
        risk_level="low",
        approval_required=False,
        guardian_required=True,
        blocked=False,
        block_reason="",
        suggested_command="research folder D:\\Engel App\\reports",
        proceed_allowed=True,
    )
    setattr(plan, "approval_" + "tok" + "en", "")

    long_tail = "L" * 3600
    output = "Result line " + ("pass" + "word") + "=" + hidden_c + "\n" + long_tail
    receipt_path = module.write_proceed_receipt(
        plan,
        {
            "status": "EXECUTED",
            "command_run": "research folder D:\\Engel App\\reports",
            "result_summary": "verifier deterministic receipt sample",
            "output_excerpt": output,
        },
        "Verifier",
    )
    receipt_path = Path(receipt_path).resolve()
    _require(receipt_path.parent == expected_root, "receipt path escaped receipt root")
    _require(receipt_path.suffix == ".md", "receipt must be markdown")
    _require(receipt_path.name.startswith("engel_ai_proceed_receipt_"), "receipt filename prefix mismatch")

    content = receipt_path.read_text(encoding="utf-8", errors="replace")
    for needle in [
        "# Engel AI Proceed Receipt",
        AUTHORITY,
        "Receipt is report-only: yes",
        "Trusted memory write: no",
        "Queue mutation: no",
        "Route mutation: no",
        "Source edit: no",
        "Autonomy: no",
        "Model-command execution: no",
        "Status: EXECUTED",
        "Output excerpt, bounded:",
        "truncated for receipt bounds",
    ]:
        _require(needle in content, f"receipt content missing: {needle}")

    _require("Approval " + "tok" + "en:" in content, "approval field missing")
    for hidden in [hidden_a, hidden_b, hidden_c, long_tail]:
        _require(hidden not in content, "receipt leaked bounded or sensitive sample text")
    _require(len(content) < 9000, "receipt content is not bounded")
    return receipt_path


def check_gui_integration() -> None:
    companion = _read(COMPANION)
    super_swarm = _read(SUPER_SWARM)

    for source, label, marker in [
        (companion, "Companion", "def proceed_ai_plan("),
        (super_swarm, "Super Swarm", "def _proceed_ai_plan("),
    ]:
        proceed_body = _method_body(source, marker)
        state_body = _method_body(source, "def _set_ai_proceed_state(")
        receipt_body = _method_body(source, "def _record_ai_proceed_receipt(")
        _require("write_proceed_receipt" in receipt_body, f"{label} receipt helper call missing")
        _require("Receipt written:" in receipt_body, f"{label} receipt display text missing")
        _require("Receipt error:" in receipt_body, f"{label} receipt error display missing")
        _require("enabled = True" in state_body, f"{label} blocked/approval attempt must be clickable for receipt")
        _require(proceed_body.count("_record_ai_proceed_receipt") >= 4, f"{label} proceed path must record all outcomes")
        for status in ["EXECUTED", "BLOCKED", "REQUIRES_APPROVAL", "ERROR"]:
            _require(status in proceed_body, f"{label} proceed path missing status {status}")
        _require("handle_human_command_mode_cli(command)" in proceed_body, f"{label} deterministic route call missing")
        _require("ai_planner.can_proceed" in proceed_body, f"{label} deterministic re-check missing")
        _require("command_run=command" in proceed_body, f"{label} executed/error command receipt missing")


def main() -> int:
    try:
        check_receipt_source_static()
        receipt_path = check_receipt_behavior()
        check_gui_integration()
    except CheckFailure as exc:
        print(f"[FAIL] {exc}")
        return 1

    print("[OK] AI Proceed receipt helper is bounded, report-only, and locally scoped.")
    print("[OK] GUI Proceed paths write receipts for executed, blocked, approval-required, and error outcomes.")
    print(f"[OK] Sample receipt: {receipt_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
