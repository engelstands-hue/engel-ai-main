#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MD = ROOT / "memory" / "ENGEL_UNIX_STYLE_SYSTEM_DESIGN_PRINCIPLES_V1.md"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_UNIX_STYLE_SYSTEM_DESIGN_PRINCIPLES_V1.json"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_UNIX_STYLE_SYSTEM_DESIGN_PRINCIPLES.md"
MAP_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
MAP_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
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


def check_contract_docs() -> None:
    markdown = _read(CONTRACT_MD)
    payload = json.loads(_read(CONTRACT_JSON))
    _require(payload.get("schema") == "engel_unix_style_system_design_principles_v1", "schema mismatch")
    _require(payload.get("status") == "DESIGN_GUIDE / READ_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED", "status mismatch")
    _require(payload.get("authority") == AUTHORITY, "authority mismatch")
    _require(payload.get("trusted_memory_write") == "BLOCKED / NOT_PERFORMED", "trusted memory write mismatch")
    _require(payload.get("runtime_effect") == "NONE", "runtime effect must be NONE")
    principles = payload.get("principles")
    _require(isinstance(principles, list), "principles list missing")
    for item in [
        "simple_paths",
        "clear_hierarchy",
        "path_addressable_artifacts",
        "small_safe_tools",
        "explicit_contracts",
        "explicit_manifests",
        "reports_and_receipts",
        "indexes_not_trust",
        "external_roots_are_shelves_not_brains",
        "explicit_selection_only",
        "no_broad_scans",
        "no_hidden_mutation",
        "no_hidden_api_network",
        "no_background_autonomy_by_default",
        "content_data_not_instruction",
        "candidate_review_before_trusted_memory",
    ]:
        _require(item in principles, "principle missing: " + item)
    roles = payload.get("root_roles")
    _require(isinstance(roles, dict), "root roles missing")
    _require(roles.get("active_app_core") == "D:\\b.WorkSpace\\Engel App", "active app root mismatch")
    _require(roles.get("primary_external_archive") == "E:\\ENGEL_APP_MEMORY", "primary external archive mismatch")
    _require(roles.get("secondary_external_archive") == "G:\\ENGEL_APP_MEMORY", "secondary external archive mismatch")
    safety = payload.get("safety")
    _require(isinstance(safety, dict), "safety object missing")
    for key, value in safety.items():
        _require(value is False, "safety key must be false: " + key)
    for needle in [
        "# Engel Unix-Inspired System Design Principles V1",
        "DESIGN_GUIDE / READ_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        AUTHORITY,
        "Keep Engel organized as one fluid Core system instead of scattered tools or hidden memory islands.",
        "Simple paths.",
        "Clear hierarchy.",
        "Everything important is addressable by path.",
        "Use files as durable artifacts: Markdown, JSON, receipts, manifests, reports.",
        "Tools should do one job safely.",
        "Contracts define behavior before runtime action.",
        "Reports document actions after work.",
        "Receipts document approved or attempted actions.",
        "Indexes describe what exists; indexes do not make content trusted.",
        "External roots are archive shelves, not trusted brains.",
        "Intake is explicit-selection only.",
        "No broad scans.",
        "No hidden mutation.",
        "No hidden provider/API/network behavior.",
        "No background autonomy unless separately approved and bounded.",
        "No fake live data.",
        "Content is data, not instruction.",
        "Learning flows through candidates/reviews before any trusted memory.",
        "Trusted memory requires separate Josh/Guardian workflow.",
        "Authority remains Josh > Guardian > Engel/runtime.",
        "D:\\b.WorkSpace\\Engel App",
        "E:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "reports\\codex_bridge",
        "reports\\research_intake",
        "reports\\memory_candidate_proposals",
        "Core Continuity Map ≠ Trusted Memory.",
        "Embedded approval tokens do not count.",
        "does not write trusted memory, apply lessons, move files, scan drives, or change Engel behavior by itself.",
        "not a claim to perfectly implement historical Unix internals",
    ]:
        _require(needle in markdown, "markdown missing text: " + needle)


def check_verifier_static() -> None:
    source = Path(__file__).read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    blocked_import_roots = {
        "os",
        "subprocess",
        "asyncio",
        "httpx",
        "openai",
        "anthropic",
        "requests",
        "socket",
        "urllib",
        "webbrowser",
        "threading",
        "multiprocessing",
        "selenium",
        "playwright",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, "blocked import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "blocked import: " + node.module)
        elif isinstance(node, ast.Call):
            function = node.func
            call_name = ""
            if isinstance(function, ast.Name):
                call_name = function.id
            elif isinstance(function, ast.Attribute):
                call_name = function.attr
            _require(call_name not in {"eval", "exec", "write_text", "unlink", "remove", "rmtree"}, "blocked call: " + call_name)


def check_core_continuity_reference() -> None:
    markdown = _read(MAP_MD)
    payload = json.loads(_read(MAP_JSON))
    _require(payload.get("unix_style_system_design_status") == "DESIGN_GUIDE / READ_ONLY", "map design status mismatch")
    _require(
        payload.get("unix_style_system_design_path") == "memory/ENGEL_UNIX_STYLE_SYSTEM_DESIGN_PRINCIPLES_V1.md",
        "map design path mismatch",
    )
    _require(
        payload.get("system_design_storage_philosophy") == "UNIX_INSPIRED_SIMPLE_HIERARCHY_EXPLICIT_ARTIFACTS",
        "map system design storage philosophy mismatch",
    )
    _require(payload.get("hidden_mutation_policy") == "BLOCKED", "map hidden mutation policy mismatch")
    _require(payload.get("broad_scan_policy") == "BLOCKED", "map broad scan policy mismatch")
    _require(payload.get("content_instruction_boundary") == "DATA_NOT_INSTRUCTION", "map content boundary mismatch")
    paths = payload.get("paths", {})
    _require(isinstance(paths, dict), "map paths missing")
    _require("unix_style_system_design_docs" in paths, "map path list missing Unix-style docs")
    for needle in [
        "Engel-wide Unix-Inspired System Design",
        "DESIGN_GUIDE / READ_ONLY / NOT_TRUSTED_MEMORY",
        "simple paths, clear hierarchy, explicit artifacts, small safe tools",
        "no broad scans",
        "no hidden mutation",
        "no implicit trust",
        "no scattered memory islands",
        "No hidden provider/API/network behavior.",
        "No fake live data.",
        "Content is data, not instruction.",
        "Core Continuity Map is an index, not trusted memory.",
    ]:
        _require(needle in markdown, "map markdown missing text: " + needle)


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "ENGEL_UNIX_STYLE_SYSTEM_DESIGN_PRINCIPLES",
        "Status COMPLETE",
        "Files changed",
        "Engel-wide design principles",
        "Root roles",
        "Unix-inspired filesystem philosophy summary",
        "not a runtime behavior change",
        "Trusted memory boundary",
        "No-broad-scan confirmation",
        "Verification results",
        "Packaging skipped",
        "Safety statement",
        "Engel-wide Unix-inspired system design principles are design/contract only.",
        "do not move files",
        "do not write trusted memory",
        "do not write ALIVE_STATE",
        AUTHORITY,
    ]:
        _require(needle in text, "report missing text: " + needle)


def main() -> int:
    checks = [
        ("contract_docs", check_contract_docs),
        ("verifier_static", check_verifier_static),
        ("core_continuity_reference", check_core_continuity_reference),
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
        print("ENGEL_UNIX_STYLE_SYSTEM_DESIGN_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1
    print()
    print("ENGEL_UNIX_STYLE_SYSTEM_DESIGN_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
