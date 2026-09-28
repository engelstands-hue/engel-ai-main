#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CHECKER_STATUS = [
    "BOUNDED_CHECK_ONLY",
    "EXPLICIT_PATH_ONLY",
    "NO_RECURSIVE_SCAN",
    "NO_FILE_CONTENT_READ",
    "NO_IMPORT",
    "NO_INDEXING",
    "NOT_TRUSTED_MEMORY",
]

REPO_ROOT = Path(__file__).resolve().parent
APPROVED_LIBRARY_ROOT = REPO_ROOT / "engel_library" / "approved_library"

ALLOWED_CATEGORIES = [
    "research_papers",
    "architecture_references",
    "engel_manuals",
    "offline_docs",
    "math",
    "coding_languages",
]

SAFETY_BOUNDARY = {
    "bounded_check_only": True,
    "explicit_path_only": True,
    "approved_library_scaffold_only": True,
    "no_recursive_scan": True,
    "no_file_content_read": True,
    "no_import": True,
    "no_indexing": True,
    "no_embedding": True,
    "no_hashing": True,
    "no_copy": True,
    "no_move": True,
    "no_delete": True,
    "no_execution": True,
    "no_network_or_provider_calls": True,
    "no_trusted_memory_write": True,
    "not_trusted_memory": True,
}


class BoundedFilePresenceCheckerError(Exception):
    """Base error for bounded approved-library file presence checks."""


class ExplicitPathRequiredError(BoundedFilePresenceCheckerError):
    """Raised when the caller does not provide one explicit path."""


class PathOutsideApprovedLibraryError(BoundedFilePresenceCheckerError):
    """Raised when the explicit path is outside the approved library scaffold."""


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _normalize_explicit_path(explicit_path: str | Path) -> Path:
    if isinstance(explicit_path, Path):
        candidate = explicit_path
    elif isinstance(explicit_path, str):
        if not explicit_path.strip():
            raise ExplicitPathRequiredError("one explicit approved_library file path is required")
        candidate = Path(explicit_path)
    else:
        raise ExplicitPathRequiredError("explicit path must be a string or Path")

    text = str(candidate)
    if any(token in text for token in ["*", "?", "[", "]"]):
        raise ExplicitPathRequiredError("patterns are not allowed; provide one explicit file path")
    return candidate.resolve()


def validate_approved_library_path(explicit_path: str | Path) -> Path:
    candidate = _normalize_explicit_path(explicit_path)
    approved_root = APPROVED_LIBRARY_ROOT.resolve()
    if not _is_relative_to(candidate, approved_root):
        raise PathOutsideApprovedLibraryError("path must stay under engel_library/approved_library")
    return candidate


def check_approved_library_file_presence(explicit_path: str | Path) -> dict[str, Any]:
    candidate = validate_approved_library_path(explicit_path)
    exists_as_file = candidate.exists() and candidate.is_file()
    return {
        "status": list(CHECKER_STATUS),
        "result": "exists" if exists_as_file else "not_exists",
        "exists": bool(exists_as_file),
        "explicit_path": str(candidate),
        "approved_library_root": str(APPROVED_LIBRARY_ROOT.resolve()),
        "checked_under_approved_library": True,
        "content_read": False,
        "recursive_scan": False,
        "import_performed": False,
        "indexing_performed": False,
        "trusted_memory_written": False,
        "safety_boundary": dict(SAFETY_BOUNDARY),
    }


def build_checker_manifest() -> dict[str, Any]:
    return {
        "name": "Engel Bounded File Presence Checker V1",
        "status": list(CHECKER_STATUS),
        "approved_library_root": str(APPROVED_LIBRARY_ROOT),
        "allowed_categories": list(ALLOWED_CATEGORIES),
        "safety_boundary": dict(SAFETY_BOUNDARY),
        "behavior": "Checks whether one explicit approved_library file path exists as a file.",
    }


def main() -> int:
    print(json.dumps(build_checker_manifest(), indent=2, sort_keys=True))
    print("This module does not scan folders or read file contents.")
    print("Use check_approved_library_file_presence with one explicit path from an approved local caller.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
