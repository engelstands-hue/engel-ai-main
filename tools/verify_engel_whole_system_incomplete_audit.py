from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_whole_system_incomplete_audit.py"
VERIFIER = ROOT / "tools" / "verify_engel_whole_system_incomplete_audit.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_WHOLE_SYSTEM_INCOMPLETE_ITEMS_AUDIT.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "subprocess",
    "threading",
    "multiprocessing",
    "asyncio",
    "http",
    "ftplib",
    "smtplib",
    "openai",
    "anthropic",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "Popen",
    "system",
    "startfile",
    "run",
    "call",
    "check_call",
    "check_output",
    "write_text",
    "write_bytes",
    "mkdir",
    "unlink",
    "rename",
    "replace",
}

REQUIRED_COMMANDS = [
    "whole system incomplete audit status",
    "whole system incomplete audit report",
    "whole system incomplete audit json",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_whole_system_incomplete_audit", MODULE)
    require(spec is not None and spec.loader is not None, "could not load whole-system audit module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_whole_system_incomplete_audit"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [MODULE, VERIFIER, REPORT, COMMANDS, CODEX_VERIFY]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "read_only_report_only",
        "critical",
        "high",
        "medium",
        "low",
        "evidence",
        "suggested_next_action",
        "blocks_engel_ai_setup",
        "blocks_packaging",
        "blocks_real_apply",
        "blocks_phone_automation",
    ]:
        require(needle in source, "audit source missing required text: " + needle)
    for forbidden in ["requests.", "socket.", "webbrowser.", "openai.", "anthropic.", "subprocess.", ".rglob(", "os.walk("]:
        require(forbidden not in source.lower(), "audit source contains forbidden behavior: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("audit contains forbidden worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("audit contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, "audit contains forbidden call: " + name)


def check_runtime_output() -> None:
    module = load_module()
    payload = module.audit_payload()
    require(payload["mode"] == "read_only_report_only", "audit mode mismatch")
    require(payload["item_count"] >= 4, "audit should include multiple incomplete items")
    for bucket in ["critical", "high", "medium", "low"]:
        require(bucket in payload["buckets"], "missing priority bucket: " + bucket)
        require(isinstance(payload["buckets"][bucket], list), "bucket is not a list: " + bucket)
    flattened = [entry for bucket in payload["buckets"].values() for entry in bucket]
    require(all(entry.get("evidence") for entry in flattened), "each audit item must include evidence")
    require(any(entry.get("blocks_real_apply") for entry in flattened), "audit must identify real apply blocker")
    require(any(entry.get("blocks_engel_ai_setup") for entry in flattened), "audit must identify Engel AI setup blocker")
    status = module.render_status()
    report = module.render_report()
    json_payload = json.loads(json.dumps(payload))
    require("critical:" in status and "high:" in status and "medium:" in status and "low:" in status, "status missing buckets")
    require("## Ranked Priorities" in report, "report missing ranked priorities")
    require(json_payload["safety"]["source_mutation"] is False, "audit must be non-mutating")
    require(module.main(["status"]) == 0, "status command failed")
    require(module.main(["json"]) == 0, "json command failed")
    require(module.main(["report"]) == 0, "report command failed")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "Engel Whole-System Incomplete Items Audit",
        "Critical",
        "High",
        "Medium",
        "Low",
        "evidence",
        "suggested next action",
        "blocks: AI setup",
        "read-only/report-only",
    ]:
        require(needle in report, "audit report missing text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require(
        "tools\\verify_engel_whole_system_incomplete_audit.py" in codex,
        "codex verifier missing whole-system audit verifier",
    )


def main() -> int:
    try:
        check_files_exist()
        check_static_safety()
        check_runtime_output()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel whole-system incomplete audit verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
