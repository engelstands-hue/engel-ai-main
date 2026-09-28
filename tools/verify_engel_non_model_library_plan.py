from __future__ import annotations

import json
import re
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

JSON_PATH = ROOT / "memory" / "ENGEL_NON_MODEL_LIBRARY_PLAN_V1.json"
MD_PATH = ROOT / "memory" / "ENGEL_NON_MODEL_LIBRARY_PLAN_V1.md"

REQUIRED_CATEGORIES = {
    "research_papers": {
        ".pdf",
        ".txt",
        ".md",
    },
    "architecture_references": {
        ".pdf",
        ".txt",
        ".md",
        ".html",
    },
    "engel_manuals": {
        ".md",
        ".txt",
        ".json",
        ".csv",
    },
    "offline_docs": {
        ".pdf",
        ".txt",
        ".md",
        ".html",
    },
}

SAFE_FILE_TYPES = {".pdf", ".txt", ".md", ".html", ".json", ".csv"}

FALSE_ROOT_FLAGS = [
    "network_download_allowed",
    "auto_download_allowed",
    "provider_api_allowed",
    "browser_api_allowed",
    "package_manager_allowed",
    "external_tool_allowed",
    "auto_index_allowed",
    "recursive_scan_allowed",
    "execute_content_allowed",
    "follow_document_instructions_allowed",
    "startup_auto_load_allowed",
    "background_workers_allowed",
    "trusted_memory_write_allowed",
    "project_memory_write_allowed",
    "queue_mutation_allowed",
    "route_mutation_allowed",
    "provider_mutation_allowed",
    "source_behavior_mutation_allowed",
]

FALSE_CATEGORY_FLAGS = [
    "trusted_memory_write_allowed",
    "network_download_allowed",
    "auto_index_allowed",
    "recursive_scan_allowed",
    "execute_content_allowed",
    "follow_document_instructions_allowed",
]

IMPORT_STATUS_VALUES = {"planned", "missing", "present", "unknown"}


class CheckFailure(Exception):
    pass


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_text(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + _rel(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise CheckFailure("manifest JSON is invalid: " + str(exc)) from exc
    if not isinstance(data, dict):
        raise CheckFailure("manifest JSON must be an object")
    return data


def _is_local_path(value: str) -> bool:
    text = value.replace("/", "\\").strip()
    if not text:
        return False
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        return False
    if text.startswith("\\\\"):
        return False
    parts = [part for part in text.split("\\") if part]
    if ".." in parts:
        return False
    return bool(re.match(r"^[A-Za-z]:\\", text))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _assert_root_manifest(data: dict) -> None:
    _require(data.get("schema") == "ENGEL_NON_MODEL_LIBRARY_PLAN_V1", "schema mismatch")
    status = str(data.get("status", ""))
    for phrase in ["LOCAL_NON_MODEL_LIBRARY_PLAN", "NOT_TRUSTED_MEMORY", "NOT_DOWNLOADED", "NOT_INDEXED", "NOT_APPLIED"]:
        _require(phrase in status, "status missing " + phrase)
    _require(data.get("runtime_effect") == "READ_ONLY_PLAN_STATUS_ONLY", "runtime effect must be read-only status only")
    _require(data.get("content_boundary") == "DATA_CONFIG_NOT_INSTRUCTION", "content boundary mismatch")
    _require(data.get("future_imported_files_trust_status") == "UNTRUSTED_QUARANTINED_UNTIL_HUMAN_APPROVAL", "future import trust status mismatch")
    _require(data.get("actual_downloads_imports") == "MANUAL_HUMAN_APPROVED_ONLY", "manual downloads/imports boundary missing")
    _require(data.get("trusted_memory_write") == "BLOCKED / NOT_PERFORMED", "trusted memory write boundary mismatch")
    _require(data.get("human_approval_required") is True, "human approval must be required")
    for flag in FALSE_ROOT_FLAGS:
        _require(data.get(flag) is False, "root flag must be false: " + flag)


def _collect_layout_paths(folder_layout: object) -> list[str]:
    if not isinstance(folder_layout, dict):
        raise CheckFailure("folder_layout must be an object")
    paths: list[str] = []
    for key in [
        "library_root",
        "quarantine_imports_root",
        "approved_library_root",
        "indexes_root",
        "readme_only_no_auto_indexing",
    ]:
        value = folder_layout.get(key)
        if not isinstance(value, str):
            raise CheckFailure("folder_layout missing string path: " + key)
        paths.append(value)
    for group_key in ["quarantine_imports", "approved_library"]:
        group = folder_layout.get(group_key)
        if not isinstance(group, dict):
            raise CheckFailure("folder_layout missing " + group_key)
        for slug in REQUIRED_CATEGORIES:
            value = group.get(slug)
            if not isinstance(value, str):
                raise CheckFailure(group_key + " missing category path: " + slug)
            paths.append(value)
    return paths


def _assert_folder_layout(data: dict) -> None:
    folder_layout = data.get("folder_layout")
    paths = _collect_layout_paths(folder_layout)
    for value in paths:
        _require(_is_local_path(value), "folder path is not a bounded local drive path: " + value)
    layout = folder_layout if isinstance(folder_layout, dict) else {}
    _require("quarantine_imports" in layout, "quarantine_imports missing from plan")
    _require("approved_library" in layout, "approved_library missing from plan")


def _assert_categories(data: dict) -> None:
    categories = data.get("categories")
    if not isinstance(categories, list):
        raise CheckFailure("categories must be a list")
    by_slug = {str(category.get("category_slug")): category for category in categories if isinstance(category, dict)}
    for slug, required_types in REQUIRED_CATEGORIES.items():
        category = by_slug.get(slug)
        if not isinstance(category, dict):
            raise CheckFailure("missing category: " + slug)
        _require(isinstance(category.get("category_name"), str) and category["category_name"], "category name missing: " + slug)
        _require(isinstance(category.get("purpose"), list) and category["purpose"], "purpose missing: " + slug)
        _require(category.get("human_approval_required") is True, "human approval required must be true: " + slug)
        for flag in FALSE_CATEGORY_FLAGS:
            _require(category.get(flag) is False, "category flag must be false for " + slug + ": " + flag)
        quarantine = category.get("expected_quarantine_folder")
        approved = category.get("expected_approved_folder")
        _require(isinstance(quarantine, str) and _is_local_path(quarantine), "quarantine folder must be local: " + slug)
        _require(isinstance(approved, str) and _is_local_path(approved), "approved folder must be local: " + slug)
        allowed = category.get("allowed_file_types")
        _require(isinstance(allowed, list) and allowed, "allowed file types missing: " + slug)
        allowed_set = set(allowed)
        _require(allowed_set == required_types, "allowed file type set mismatch for " + slug)
        _require(all(item in SAFE_FILE_TYPES for item in allowed_set), "unsafe file type for " + slug)
        _require(category.get("import_status") in IMPORT_STATUS_VALUES, "import status mismatch: " + slug)
        _require(category.get("trust_status") == "UNTRUSTED_QUARANTINED_UNTIL_HUMAN_APPROVAL", "trust boundary mismatch: " + slug)


def _assert_safety_notes(data: dict) -> None:
    notes = data.get("safety_notes")
    if not isinstance(notes, list):
        raise CheckFailure("safety_notes must be a list")
    joined = " ".join(str(note).lower() for note in notes)
    for phrase in [
        "files in quarantine_imports are untrusted",
        "explicit human action",
        "data, not commands",
        "no library document may alter routes",
        "explicit future human-approved workflow",
        "plan/status surface",
        "actual downloads/imports remain manual and human-approved",
    ]:
        if phrase not in joined:
            raise CheckFailure("safety notes missing phrase: " + phrase)


def _assert_markdown(text: str) -> None:
    normalized = " ".join(text.lower().replace("\\", "/").split())
    for phrase in [
        "engel non-model library plan v1",
        "local_non_model_library_plan / not_trusted_memory / not_downloaded / not_indexed / not_applied",
        "actual downloads/imports remain manual and human-approved",
        "research_papers",
        "architecture_references",
        "engel_manuals",
        "offline_docs",
        "quarantine_imports",
        "approved_library",
        "network/download allowed: false",
        "auto-index allowed: false",
        "recursive scan allowed: false",
        "execute content allowed: false",
        "follow document instructions allowed: false",
        "any extracted instructions from documents are data, not commands",
        "no library document may alter routes, source code, memory, providers, queues, startup behavior, or permissions",
        "no network, browser, provider api, package manager, or external tool is called",
        "future imported files remain untrusted/quarantined until explicit human approval",
    ]:
        if phrase.lower().replace("\\", "/") not in normalized:
            raise CheckFailure("markdown missing phrase: " + phrase)


def main() -> int:
    data = _load_json(JSON_PATH)
    _assert_root_manifest(data)
    _assert_folder_layout(data)
    _assert_categories(data)
    _assert_safety_notes(data)
    _assert_markdown(_read_text(MD_PATH))
    print("PASS: Engel Non-Model Library Plan V1 verifier")
    print("- manifest JSON is valid")
    print("- all four non-model categories are present")
    print("- quarantine and approved folders are represented")
    print("- approval is required and trusted-memory writes are disabled")
    print("- network/download, auto-index, recursive scan, execution, and document-instruction following are disabled")
    print("- allowed file types are limited to safe document/reference formats")
    print("- startup auto-load and background workers are disabled")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
