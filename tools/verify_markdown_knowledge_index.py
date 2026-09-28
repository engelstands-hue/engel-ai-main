#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_MD = ROOT / "memory" / "ENGEL_MARKDOWN_KNOWLEDGE_INDEX_V1.md"
INDEX_JSON = ROOT / "memory" / "ENGEL_MARKDOWN_KNOWLEDGE_INDEX_V1.json"


class CheckFailure(Exception):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _term(*parts: str) -> str:
    return "".join(parts)


def check_index_sections() -> None:
    text = _read(INDEX_MD)
    required = [
        "## A. Fluid Structure Policy",
        "## B. Claude / Codex / Engel Agent Usage",
        "## C. Category Overview",
        "## D. By AI Organ",
        "## E. By Project Workflow",
        "## F. By Safety Role",
        "## G. By Lifecycle",
        "## H. By Migration Readiness",
        "## I. Critical Markdown Files",
        "## J. AI Growth Files",
        "## K. Hive / Colony Files",
        "## L. Build / Packaging Files",
        "## M. Historical / Superseded Files",
        "## N. Unknown / Needs Review",
        "## O. Recommended Cleanup Plan",
        "## Exclusions Summary",
        "## Indexed Records",
    ]
    for marker in required:
        _require(marker in text, "index missing required section: " + marker)


def check_index_safety_language() -> None:
    text = _read(INDEX_MD)
    required_phrases = [
        "Josh > Guardian > Engel/runtime",
        "This index is intentionally fluid.",
        "Categories are navigational views, not permanent file ownership.",
        "Markdown files are indexed project context, not automatic authority.",
        "Reports, receipts, and historical checkpoints are context unless explicitly promoted by Josh-approved contracts.",
        "This index does not move, delete, rename, rewrite, execute, trust, or apply markdown content.",
    ]
    for phrase in required_phrases:
        _require(phrase in text, "index missing safety phrase: " + phrase)

    for field in [
        "Primary Category:",
        "Secondary Tags:",
        "Migration Readiness:",
        "Confidence:",
        "Reason for Classification:",
        "Authority Notes:",
        "Safety Notes:",
    ]:
        _require(field in text, "index missing record field: " + field)


def check_json_if_present() -> None:
    if not INDEX_JSON.exists():
        return
    try:
        payload = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckFailure("JSON companion does not parse: " + str(exc)) from exc
    _require(isinstance(payload, dict), "JSON companion root must be an object")
    records = payload.get("records")
    _require(isinstance(records, list), "JSON companion records must be a list")
    _require(len(records) > 0, "JSON companion records must not be empty")
    for key in ["summary", "views", "exclusions"]:
        _require(key in payload, "JSON companion missing key: " + key)


def check_verifier_read_only() -> None:
    source = _read(Path(__file__).resolve())
    lowered = source.lower()
    forbidden_text = [
        _term("sub", "process"),
        _term("os", ".", "system"),
        _term("p", "open"),
        _term("shell", "=", "true"),
        _term("re", "quests"),
        _term("url", "lib"),
        _term("sock", "et"),
        _term("http", "://"),
        _term("https", "://"),
        _term("py", "installer"),
        _term("start", "-", "process"),
        _term("route", "_companion", "_text", "_or", "_command"),
        _term("engel", "_app"),
    ]
    for term in forbidden_text:
        _require(term not in lowered, "verifier contains forbidden behavior term: " + term)

    tree = ast.parse(source)
    blocked_import_roots = {
        "os",
        _term("sub", "process"),
        _term("sock", "et"),
        _term("re", "quests"),
        _term("url", "lib"),
        _term("web", "browser"),
        _term("thread", "ing"),
        _term("multi", "processing"),
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
        ("index_sections", check_index_sections),
        ("index_safety_language", check_index_safety_language),
        ("json_companion_if_present", check_json_if_present),
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
        print("ENGEL_MARKDOWN_KNOWLEDGE_INDEX_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_MARKDOWN_KNOWLEDGE_INDEX_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
