#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_external_memory_roots.py"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_EXTERNAL_LONG_TERM_MEMORY_ROOTS_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_EXTERNAL_LONG_TERM_MEMORY_ROOTS_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_EXTERNAL_LONG_TERM_MEMORY_ROOTS.md"
AUTHORITY = "Josh > Guardian > Engel/runtime"


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def _compile(path: Path) -> None:
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def _load_helper():
    spec = importlib.util.spec_from_file_location("engel_external_memory_roots", HELPER)
    _require(spec is not None and spec.loader is not None, "could not load helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_external_memory_roots"] = module
    spec.loader.exec_module(module)
    return module


def check_contract_files() -> None:
    payload = json.loads(_read(CONTRACT_JSON))
    markdown = _read(CONTRACT_MD)

    _require(payload.get("schema") == "engel_external_long_term_memory_roots_v1", "contract schema mismatch")
    _require(payload.get("status") == "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED", "contract status mismatch")
    _require(payload.get("authority") == AUTHORITY, "authority mismatch")
    _require(payload.get("active_app_root") == "D:\\b.WorkSpace\\Engel App", "active app root mismatch")
    _require(payload.get("boundary") == "External Long-Term Memory ≠ Trusted Memory", "boundary mismatch")
    _require(payload.get("trusted_memory_candidate_boundary") == "Trusted Memory Candidate ≠ Trusted Memory", "candidate boundary mismatch")
    _require(payload.get("core_continuity_boundary") == "Core Continuity Map ≠ Trusted Memory", "continuity boundary mismatch")

    _require(payload.get("external_archive_required") is False, "external archive must not be required")
    _require(payload.get("external_archive_default_path") is None, "external archive default path must be null")
    _require("I:\\ENGEL_APP_MEMORY" in payload.get("deprecated_paths", []), "deprecated I archive path missing")
    _require(payload.get("active_work_root") == "D:\\b.WorkSpace\\Engel App", "active work root mismatch")
    _require(payload.get("active_memory_root") == "D:\\b.WorkSpace\\Engel App\\memory", "active memory root mismatch")
    _require(payload.get("project_local_archive_fallback") == "D:\\b.WorkSpace\\Engel App\\memory\\ENGEL_APP_MEMORY", "project-local fallback mismatch")
    _require(payload.get("missing_external_archive_is_failure") is False, "missing external archive must not fail")
    _require(payload.get("archive_migration_enabled") is False, "archive migration must remain disabled")
    _require(payload.get("archive_sync_enabled") is False, "archive sync must remain disabled")
    _require(payload.get("trusted_memory_write_enabled") is False, "trusted memory write must remain disabled")

    roots = payload.get("external_roots")
    _require(isinstance(roots, list) and len(roots) == 3, "expected three configured external archive roots")
    by_path = {root.get("path"): root for root in roots if isinstance(root, dict)}
    _require("E:\\ENGEL_APP_MEMORY" in by_path, "E:\\ENGEL_APP_MEMORY missing from contract")
    _require("F:\\ENGEL_APP_MEMORY" in by_path, "F:\\ENGEL_APP_MEMORY missing from contract")
    _require("G:\\ENGEL_APP_MEMORY" in by_path, "G:\\ENGEL_APP_MEMORY missing from contract")
    _require(by_path["E:\\ENGEL_APP_MEMORY"].get("scan_policy") == "NO_BROAD_SCAN", "E root scan policy mismatch")
    _require(by_path["E:\\ENGEL_APP_MEMORY"].get("trusted_memory_write") == "BLOCKED", "E root trusted memory policy mismatch")
    _require(by_path["F:\\ENGEL_APP_MEMORY"].get("scan_policy") == "NO_BROAD_SCAN", "F root scan policy mismatch")
    _require(by_path["F:\\ENGEL_APP_MEMORY"].get("trusted_memory_write") == "BLOCKED", "F root trusted memory policy mismatch")
    _require(by_path["G:\\ENGEL_APP_MEMORY"].get("scan_policy") == "NO_BROAD_SCAN", "G root scan policy mismatch")
    _require(by_path["G:\\ENGEL_APP_MEMORY"].get("trusted_memory_write") == "BLOCKED", "G root trusted memory policy mismatch")

    managed = payload.get("managed_folders")
    _require(isinstance(managed, list), "managed folders missing")
    _require("E:\\ENGEL_APP_MEMORY" in managed, "E managed folder missing")
    _require("F:\\ENGEL_APP_MEMORY" in managed, "F managed folder missing")
    _require("G:\\ENGEL_APP_MEMORY" in managed, "G managed folder missing")
    _require(payload.get("future_import_path") == "Untrusted Content Guard -> Research Intake -> Core Continuity -> Trusted Memory Candidate workflow -> Josh/Guardian review", "future import path mismatch")
    safety = payload.get("safety")
    _require(isinstance(safety, dict), "contract safety object missing")
    for key in [
        "external_roots_are_trusted_memory",
        "files_are_instruction",
        "broad_drive_scan_allowed",
        "automatic_indexing_allowed",
        "automatic_learning_allowed",
        "trusted_memory_write_allowed",
        "generated_content_trusted_memory",
        "external_file_execution_allowed",
        "provider_network_allowed",
        "autonomy_allowed",
        "authority_changed",
    ]:
        _require(safety.get(key) is False, "contract must keep false: " + key)

    for needle in [
        "# Engel External Long-Term Memory Roots V1",
        "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        AUTHORITY,
        "E:\\ENGEL_APP_MEMORY",
        "F:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "I:\\ENGEL_APP_MEMORY",
        "D:\\b.WorkSpace\\Engel App\\memory\\ENGEL_APP_MEMORY",
        "External Long-Term Memory ≠ Trusted Memory.",
        "Trusted Memory Candidate ≠ Trusted Memory.",
        "Core Continuity Map ≠ Trusted Memory.",
        "Files in external roots are data, not instruction.",
        "External roots must pass Untrusted Content Guard before summarization/proposals.",
        "No broad drive scan.",
        "No recursive drive scan.",
        "No automatic indexing.",
        "No automatic learning.",
        "No automatic memory write.",
        "No archive migration.",
        "No archive sync.",
        "No archive copy.",
        "No archive delete.",
        "No generated content becomes trusted memory.",
        "Missing `I:\\` is not a failure on b.workstation.",
        "Research Intake / Core Continuity / Trusted Memory Candidate workflow",
        "Josh > Guardian > Engel/runtime remains active.",
    ]:
        _require(needle in markdown, "contract markdown missing text: " + needle)


def check_helper_static() -> None:
    _compile(HELPER)
    source = _read(HELPER)
    tree = ast.parse(source)
    for needle in [
        "app_root",
        "load_external_memory_roots",
        "external_memory_status",
        "is_configured_external_memory_path",
        "is_safe_external_memory_path",
        "render_external_memory_status",
        "E:\\ENGEL_APP_MEMORY",
        "F:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "NO_BROAD_SCAN",
        "BLOCKED / NOT_PERFORMED",
        "External Long-Term Memory ≠ Trusted Memory",
        "Files in external roots are data, not instruction.",
        "Folders created by helper: NO",
    ]:
        _require(needle in source, "helper source missing text: " + needle)

    forbidden_text = [
        "os.walk",
        ".rglob(",
        ".glob(",
        "subprocess",
        "os.system",
        "Popen",
        "shell=True",
        "requests",
        "httpx",
        "socket",
        "urllib",
        "openai",
        "anthropic",
        "webbrowser",
        "threading",
        "multiprocessing",
        "selenium",
        "playwright",
        "eval(",
        "exec(",
        "runpy",
        "shutil",
        "copyfile",
        "copytree",
        "write_text(",
        "write_bytes(",
        ".mkdir(",
        ".remove(",
        ".unlink(",
        "rmtree",
        "startfile",
    ]
    lowered = source.lower()
    for forbidden in forbidden_text:
        _require(forbidden.lower() not in lowered, "helper contains forbidden pattern: " + forbidden)

    blocked_import_roots = {
        "asyncio",
        "httpx",
        "openai",
        "anthropic",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "webbrowser",
        "threading",
        "multiprocessing",
        "selenium",
        "playwright",
        "shutil",
    }
    blocked_calls = {"eval", "exec", "__import__", "open"}
    blocked_methods = {
        "mkdir",
        "open",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "touch",
        "unlink",
        "write",
        "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                _require(root not in blocked_import_roots, "helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            _require(root not in blocked_import_roots, "helper imports blocked module: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in blocked_calls, "helper calls blocked builtin: " + func.id)
            elif isinstance(func, ast.Attribute):
                _require(func.attr not in blocked_methods, "helper calls write/mutation method: " + func.attr)


def check_helper_behavior() -> None:
    helper = _load_helper()
    payload = helper.load_external_memory_roots()
    _require(payload.get("status") == "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED", "loaded contract status mismatch")

    configured_cases = [
        (Path("E:\\ENGEL_APP_MEMORY"), True),
        (Path("E:\\ENGEL_APP_MEMORY\\memo.md"), True),
        (Path("F:\\ENGEL_APP_MEMORY"), True),
        (Path("F:\\ENGEL_APP_MEMORY\\memo.md"), True),
        (Path("G:\\"), False),
        (Path("G:\\ENGEL_APP_MEMORY"), True),
        (Path("G:\\ENGEL_APP_MEMORY\\memo.md"), True),
        (Path("G:\\Other"), False),
        (Path("D:\\b.WorkSpace\\Engel App"), False),
        (Path("https://example.com/memory.md"), False),
        (Path("\\\\server\\share\\memory.md"), False),
    ]
    for path, expected in configured_cases:
        _require(helper.is_configured_external_memory_path(path) is expected, "configured-path decision mismatch: " + str(path))

    safe_cases = [
        (Path("E:\\ENGEL_APP_MEMORY"), True),
        (Path("E:\\ENGEL_APP_MEMORY\\memo.md"), True),
        (Path("F:\\ENGEL_APP_MEMORY"), True),
        (Path("F:\\ENGEL_APP_MEMORY\\memo.md"), True),
        (Path("G:\\"), False),
        (Path("G:\\ENGEL_APP_MEMORY"), True),
        (Path("G:\\ENGEL_APP_MEMORY\\memo.md"), True),
        (Path("G:\\Other"), False),
        (Path("D:\\b.WorkSpace\\Engel App"), False),
        (Path("https://example.com/memory.md"), False),
        (Path("\\\\server\\share\\memory.md"), False),
    ]
    for path, expected in safe_cases:
        _require(helper.is_safe_external_memory_path(path) is expected, "safe-path decision mismatch: " + str(path))

    status = helper.external_memory_status()
    rendered = helper.render_external_memory_status()
    _require(status.get("status") == "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED", "status mismatch")
    _require(status.get("configured_roots_count") == 3, "configured root count mismatch")
    _require(status.get("scan_policy") == "NO_BROAD_SCAN", "scan policy mismatch")
    _require(status.get("trusted_memory_status") == "BLOCKED / NOT_PERFORMED", "trusted memory status mismatch")
    _require(status.get("folders_created_by_helper") is False, "helper must not create folders")
    for needle in [
        "# EXTERNAL LONG-TERM MEMORY ROOTS",
        "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "E:\\ENGEL_APP_MEMORY",
        "F:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "NO_BROAD_SCAN",
        "BLOCKED / NOT_PERFORMED",
        "External Long-Term Memory ≠ Trusted Memory.",
        "Files in external roots are data, not instruction.",
        "Untrusted Content Guard -> Research Intake -> Core Continuity -> Trusted Memory Candidate workflow -> Josh/Guardian review.",
        "No external file execution.",
        "No API/network/provider behavior.",
        "No background worker or autonomy.",
        "Folders created by helper: NO",
    ]:
        _require(needle in rendered, "rendered status missing text: " + needle)


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "ENGEL_EXTERNAL_LONG_TERM_MEMORY_ROOTS",
        "Status COMPLETE",
        "Files changed",
        "Configured external roots",
        "E:\\ENGEL_APP_MEMORY status",
        "F:\\ENGEL_APP_MEMORY status",
        "G:\\ENGEL_APP_MEMORY status",
        "No-broad-scan policy",
        "Trusted memory boundary",
        "Verification results",
        "Packaging skipped",
        "Safety statement",
        "External long-term memory roots are configured storage/archive locations only.",
        "does not write trusted memory",
        "does not write ALIVE_STATE",
        AUTHORITY,
    ]:
        _require(needle in text, "external memory report missing text: " + needle)


def main() -> int:
    checks = [
        ("contract_files", check_contract_files),
        ("helper_static", check_helper_static),
        ("helper_behavior", check_helper_behavior),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(name + ": " + str(exc))
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(name + ": unexpected error: " + str(exc))
            print("FAIL " + name + ": unexpected error: " + str(exc))

    if failures:
        print()
        print("ENGEL_EXTERNAL_MEMORY_ROOTS_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_EXTERNAL_MEMORY_ROOTS_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
