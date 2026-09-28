#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "engel_bounded_file_presence_checker.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_BOUNDED_FILE_PRESENCE_CHECKER_V1.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_bounded_file_presence_checker as checker  # noqa: E402


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_required_files() -> tuple[str, str]:
    require(CHECKER.exists(), "missing bounded file presence checker")
    require(REPORT.exists(), "missing bounded file presence checker report")
    return read(CHECKER), read(REPORT)


def check_required_text(combined: str) -> None:
    for status in [
        "BOUNDED_CHECK_ONLY",
        "EXPLICIT_PATH_ONLY",
        "NO_RECURSIVE_SCAN",
        "NO_FILE_CONTENT_READ",
        "NO_IMPORT",
        "NO_INDEXING",
        "NOT_TRUSTED_MEMORY",
    ]:
        require(status in combined, "missing checker status: " + status)

    for phrase in [
        "one explicit approved_library file path",
        "checks whether one explicit approved_library file path exists",
        "no recursive scan",
        "no file content read",
        "no import",
        "no indexing",
        "not trusted memory",
        "exists",
        "not_exists",
    ]:
        require(phrase in combined.lower(), "missing checker boundary wording: " + phrase)


def check_checker_constants() -> None:
    require(checker.APPROVED_LIBRARY_ROOT == ROOT / "engel_library" / "approved_library", "approved library root mismatch")
    for status in [
        "BOUNDED_CHECK_ONLY",
        "EXPLICIT_PATH_ONLY",
        "NO_RECURSIVE_SCAN",
        "NO_FILE_CONTENT_READ",
        "NO_IMPORT",
        "NO_INDEXING",
        "NOT_TRUSTED_MEMORY",
    ]:
        require(status in checker.CHECKER_STATUS, "checker status missing: " + status)
    for category in [
        "research_papers",
        "architecture_references",
        "engel_manuals",
        "offline_docs",
        "math",
        "coding_languages",
    ]:
        require(category in checker.ALLOWED_CATEGORIES, "allowed category missing: " + category)
    for key in [
        "explicit_path_only",
        "approved_library_scaffold_only",
        "no_recursive_scan",
        "no_file_content_read",
        "no_import",
        "no_indexing",
        "no_hashing",
        "no_copy",
        "no_move",
        "no_delete",
        "no_execution",
        "no_network_or_provider_calls",
        "no_trusted_memory_write",
    ]:
        require(checker.SAFETY_BOUNDARY.get(key) is True, "safety boundary flag missing: " + key)


def check_ast_safety(source: str) -> None:
    tree = ast.parse(source)
    forbidden_imports = {
        "os",
        "shutil",
        "subprocess",
        "requests",
        "urllib",
        "socket",
        "glob",
        "hashlib",
    }
    forbidden_calls = {
        "open",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "copy",
        "copytree",
        "move",
        "rename",
        "replace",
        "unlink",
        "rmdir",
        "mkdir",
        "iterdir",
        "rglob",
        "glob",
        "walk",
        "run",
        "Popen",
        "system",
        "startfile",
        "exec",
        "eval",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                require(root not in forbidden_imports, "forbidden import in checker: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root not in forbidden_imports, "forbidden import-from in checker: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            require(name not in forbidden_calls, "forbidden active call in checker: " + name)


def check_explicit_path_behavior() -> None:
    missing_path = checker.APPROVED_LIBRARY_ROOT / "math" / "VERIFIER_EXPECTED_MISSING_FILE.md"
    result = checker.check_approved_library_file_presence(missing_path)
    require(result["result"] == "not_exists", "missing explicit file should return not_exists")
    require(result["exists"] is False, "missing explicit file should not exist")
    require(result["content_read"] is False, "checker must not read content")
    require(result["recursive_scan"] is False, "checker must not scan recursively")
    require(result["import_performed"] is False, "checker must not import")
    require(result["indexing_performed"] is False, "checker must not index")
    require(result["trusted_memory_written"] is False, "checker must not write trusted memory")

    try:
        checker.check_approved_library_file_presence(ROOT / "memory" / "ENGEL_MANUAL_IMPORT_RECEIPT_V1.md")
    except checker.PathOutsideApprovedLibraryError:
        pass
    else:
        raise CheckFailure("checker accepted path outside approved_library")

    try:
        checker.check_approved_library_file_presence(str(checker.APPROVED_LIBRARY_ROOT / "*.md"))
    except checker.ExplicitPathRequiredError:
        pass
    else:
        raise CheckFailure("checker accepted a pattern instead of one explicit path")

    try:
        checker.check_approved_library_file_presence("")
    except checker.ExplicitPathRequiredError:
        pass
    else:
        raise CheckFailure("checker accepted empty path")


def main() -> int:
    try:
        source, report = check_required_files()
        combined = source + "\n" + report
        check_required_text(combined)
        check_checker_constants()
        check_ast_safety(source)
        check_explicit_path_behavior()
    except (CheckFailure, SyntaxError, checker.BoundedFilePresenceCheckerError) as exc:
        print("FAIL: Engel Bounded File Presence Checker V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Bounded File Presence Checker V1 verifier")
    print("- checker exists and is explicit-path only")
    print("- bounded path check stays under engel_library/approved_library")
    print("- smoke returned exists/not_exists without content reads, recursion, imports, or indexing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
