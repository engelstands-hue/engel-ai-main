#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_FLUID_FILE_STRUCTURE_PLAN.md"
JSON_PLAN = ROOT / "memory" / "ENGEL_FLUID_FILE_STRUCTURE_PLAN_V1.json"
AUTHORITY = "Josh > Guardian > Engel/runtime"


class CheckFailure(Exception):
    pass


def _term(*parts: str) -> str:
    return "".join(parts)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + _rel(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def check_report_exists() -> None:
    _require(REPORT.exists() and REPORT.is_file(), "report does not exist: " + _rel(REPORT))


def check_json_if_present() -> None:
    if not JSON_PLAN.exists():
        return
    try:
        payload = json.loads(JSON_PLAN.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckFailure("optional JSON does not parse: " + str(exc)) from exc
    _require(isinstance(payload, dict), "optional JSON root must be an object")
    _require(payload.get("authority") == AUTHORITY, "optional JSON authority mismatch")
    _require(payload.get("status") == "COMPLETE", "optional JSON status must be COMPLETE")
    _require(isinstance(payload.get("future_structure"), dict), "optional JSON missing future_structure object")
    _require(isinstance(payload.get("live_to_future_mapping"), list), "optional JSON missing mapping list")
    _require(isinstance(payload.get("migration_slices"), list), "optional JSON missing migration_slices list")
    _require(
        payload.get("fluid_structure_policy", {}).get("live_layout_remains_unchanged") is True,
        "optional JSON must state live layout remains unchanged",
    )


def check_report_required_text() -> None:
    text = _read(REPORT)
    required = [
        "## 1. Status",
        "COMPLETE",
        "## 2. Purpose",
        "## 3. Fluid Structure Policy",
        "This structure is intentionally fluid.",
        "live layout remains unchanged",
        "## 4. Current Live Layout Summary",
        "## 5. Future AI-Ready Structure",
        "D:\\Engel App",
        "app\\",
        "engel\\",
        "mind\\",
        "guardian\\",
        "action\\",
        "memory\\",
        "hive\\",
        "gui\\",
        "verifiers\\",
        "reports\\",
        "models\\",
        "live\\",
        "staging\\",
        "backups\\",
        "docs\\",
        "## 6. Folder Meanings",
        "## 7. Live-to-Future Mapping Table",
        "| Current live file or folder | Future home candidate | Migration note |",
        "engel_app.py",
        "engel_companion.py",
        "engel_ai_intent_planner.py",
        "engel_communication_router.py",
        "engel_prompt_injection_guard.py",
        "tools\\verify_*.py",
        "## 8. Dependency / Dependent Notes",
        "## 9. Migration Slices",
        "Slice 1: docs/index structure only",
        "Slice 10: packaging path update",
        "## 10. Naming Conventions",
        "## 11. Safety Boundaries",
        "## 12. Claude / Codex / Engel Usage",
        "## 13. Recommended Next Step",
        AUTHORITY,
        "no files moved or renamed",
        "No files were moved, renamed, deleted, archived, rewritten, promoted, imported differently, routed differently, packaged, or executed as part of migration.",
        "Fluid file structure planning is documentation-only.",
    ]
    for marker in required:
        _require(marker in text, "report missing required text: " + marker)


def check_report_safety_statement() -> None:
    text = _read(REPORT)
    required_phrases = [
        "does not move, rename, delete, rewrite, execute, trust, or apply files",
        "does not change runtime behavior, imports, routes",
        "provider/API/network behavior",
        "browser/email behavior",
        "autonomy",
        "model-command execution",
        "Remote Queen runtime",
        "queue mutation",
        "source-edit autonomy",
        "package installs",
        "arbitrary shell execution",
        "fake live data",
        "ALIVE_STATE writes",
        "path permissions",
        "packaging",
        "authority hierarchy",
    ]
    for phrase in required_phrases:
        _require(phrase in text, "safety statement missing phrase: " + phrase)


def check_verifier_read_only() -> None:
    source = _read(Path(__file__).resolve())
    lowered = source.lower()
    forbidden_text = [
        _term("sub", "process"),
        _term("os", ".", "system"),
        _term("p", "open"),
        _term("shell", "=", "true"),
        _term("requests", "."),
        _term("url", "lib"),
        _term("sock", "et"),
        _term("http", "://"),
        _term("https", "://"),
        _term("web", "browser"),
        _term("py", "installer"),
        _term("start", "-", "process"),
        _term("route", "_companion", "_text", "_or", "_command"),
        _term("engel", "_app", " import"),
    ]
    for term in forbidden_text:
        _require(term not in lowered, "verifier contains forbidden behavior term: " + term)

    tree = ast.parse(source)
    blocked_import_roots = {
        "os",
        _term("sub", "process"),
        _term("sock", "et"),
        _term("requests"),
        _term("url", "lib"),
        _term("web", "browser"),
        _term("thread", "ing"),
        _term("multi", "processing"),
        _term("import", "lib"),
    }
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
    blocked_calls = {"eval", "exec", "compile", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                _require(root not in blocked_import_roots, "verifier imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            _require(root not in blocked_import_roots, "verifier imports from blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in blocked_calls, "verifier calls blocked builtin: " + func.id)
            if isinstance(func, ast.Attribute):
                _require(func.attr not in blocked_methods, "verifier calls blocked method: " + func.attr)


def main() -> int:
    checks = [
        ("report_exists", check_report_exists),
        ("optional_json_parses", check_json_if_present),
        ("report_required_text", check_report_required_text),
        ("report_safety_statement", check_report_safety_statement),
        ("verifier_read_only", check_verifier_read_only),
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
        print("ENGEL_FLUID_FILE_STRUCTURE_PLAN_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_FLUID_FILE_STRUCTURE_PLAN_VERIFICATION_PASS")
    print("Authority: " + AUTHORITY)
    print("Scope: documentation-only; live layout remains unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
