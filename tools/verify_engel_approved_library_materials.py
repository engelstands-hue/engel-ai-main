from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_MATERIALS_V1.json"
MD_PATH = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_MATERIALS_V1.md"
REPORT_PATH = ROOT / "reports" / "codex_bridge" / "ENGEL_APPROVED_LIBRARY_MATERIALS_V1.md"
EXPANSION_REPORT_PATH = ROOT / "reports" / "codex_bridge" / "ENGEL_APPROVED_LIBRARY_MATERIALS_MATH_AND_CODE_EXPANSION.md"
SELF_PATH = Path(__file__).resolve()

EXPECTED_LIBRARY_ROOT = str(ROOT / "engel_library") + "\\"
EXPECTED_APPROVED_ROOT = str(ROOT / "engel_library" / "approved_library") + "\\"
EXPECTED_QUARANTINE_ROOT = str(ROOT / "engel_library" / "quarantine_imports") + "\\"

REQUIRED_CATEGORIES = {
    "research_papers",
    "architecture_references",
    "engel_manuals",
    "offline_docs",
    "math",
    "coding_languages",
}

MATH_SUBFOLDERS = [
    "foundations",
    "algebra",
    "geometry",
    "trigonometry",
    "calculus",
    "linear_algebra",
    "probability_statistics",
    "discrete_math",
    "logic",
    "optimization",
    "numerical_methods",
    "ai_math",
    "algorithms_math",
    "units_and_measurement",
    "financial_math",
    "verification_math",
]

CODING_SUBFOLDERS = [
    "python",
    "javascript_typescript",
    "sql",
    "powershell",
    "bash",
    "c_cpp",
    "csharp",
    "rust",
    "go",
    "html_css",
    "json_yaml",
    "regex",
    "git",
    "testing",
    "packaging",
    "security",
    "architecture_patterns",
    "gui_development",
    "data_formats",
    "local_databases",
    "performance_modules",
    "documentation_style",
]

MANIFEST_FALSE_FLAGS = [
    "network_download_allowed",
    "auto_index_allowed",
    "recursive_scan_allowed",
    "background_workers_allowed",
    "startup_load_allowed",
    "trusted_memory_write_allowed",
    "execute_content_allowed",
    "follow_document_instructions_allowed",
    "model_inference_allowed",
    "provider_api_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "source_mutation_allowed",
    "provider_mutation_allowed",
    "source_behavior_mutation_allowed",
    "startup_behavior_mutation_allowed",
    "permission_expansion_allowed",
]

MATERIAL_FALSE_FLAGS = [
    "trusted_memory_write_allowed",
    "execute_content_allowed",
    "follow_document_instructions_allowed",
]

SAFE_EXTERNAL_SOURCE_TYPES = {
    "external_manual_download",
    "external_manual_download_or_curated_notes",
    "manually_curated_notes_or_external_manual_download",
    "engel_curated_notes_or_external_manual_download",
}

SAFE_CURATED_SOURCE_TYPES = {
    "manually_curated_notes",
    "engel_curated_notes",
    "local_engel_file",
}

MINIMUM_COUNTS = {
    "research_papers": 7,
    "architecture_references": 5,
    "engel_manuals": 16,
    "offline_docs": 6,
    "math": 16,
    "coding_languages": 23,
}


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    _require(path.exists() and path.is_file(), "required file missing: " + str(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json() -> dict:
    try:
        data = json.loads(_read(JSON_PATH))
    except json.JSONDecodeError as exc:
        raise CheckFailure("manifest JSON is invalid: " + str(exc)) from exc
    _require(isinstance(data, dict), "manifest JSON must be an object")
    return data


def _normal(value: str) -> str:
    while "\\\\" in value:
        value = value.replace("\\\\", "\\")
    return value.replace("/", "\\")


def _assert_no_obsolete_drive_paths() -> None:
    forbidden = chr(73) + ":" + "\\"
    for path in [JSON_PATH, MD_PATH, REPORT_PATH, EXPANSION_REPORT_PATH, SELF_PATH]:
        text = _read(path)
        _require(forbidden.lower() not in text.lower(), "obsolete drive path found in " + str(path))


def _assert_manifest_flags(data: dict) -> None:
    _require(data.get("schema") == "ENGEL_APPROVED_LIBRARY_MATERIALS_V1", "schema mismatch")
    status = str(data.get("status", ""))
    for phrase in [
        "APPROVED_LIBRARY_MATERIALS_PLAN",
        "APPROVED_FOR_RESEARCH_ONLY",
        "NOT_TRUSTED_MEMORY",
        "NOT_DOWNLOADED",
        "NOT_INDEXED",
        "NOT_APPLIED",
    ]:
        _require(phrase in status, "status missing " + phrase)
    _require(_normal(str(data.get("library_root"))) == EXPECTED_LIBRARY_ROOT, "library_root mismatch")
    _require(_normal(str(data.get("approved_library_root"))) == EXPECTED_APPROVED_ROOT, "approved_library_root mismatch")
    _require(_normal(str(data.get("quarantine_root"))) == EXPECTED_QUARANTINE_ROOT, "quarantine_root mismatch")
    _require(
        data.get("approved_library_meaning") == "approved for Engel research/reference only, not automatically trusted memory",
        "approved_library_meaning mismatch",
    )
    _require(data.get("human_approval_required_for_memory_storage") is True, "human approval must be required before memory storage")
    _require(data.get("imported_content_instruction_policy") == "library documents are data, not commands", "imported content policy mismatch")
    _require(data.get("code_sample_policy") == "code samples are reference material, not executable authority", "code sample policy mismatch")
    _require(
        data.get("math_formula_policy") == "formulas are reference material and must be reviewed before becoming memory candidates",
        "math formula policy mismatch",
    )
    for flag in MANIFEST_FALSE_FLAGS:
        _require(data.get(flag) is False, "manifest flag must be false: " + flag)


def _layout_values(data: dict) -> list[str]:
    layout = data.get("folder_layout")
    _require(isinstance(layout, dict), "folder_layout must be an object")
    values: list[str] = []
    for key in ["quarantine_imports", "approved_library", "indexes"]:
        group = layout.get(key)
        _require(isinstance(group, list) and group, "folder_layout missing list: " + key)
        values.extend(str(item) for item in group)
    return values


def _assert_subfolder_group(data: dict, category: str, subfolders: list[str]) -> None:
    layout_text = "\n".join(_normal(value) for value in _layout_values(data))
    for root_name in ["quarantine_imports", "approved_library"]:
        for subfolder in subfolders:
            relative = Path(root_name) / category / subfolder
            expected = _normal(str(ROOT / "engel_library" / relative) + "\\")
            _require(expected in layout_text, "expected subfolder missing from manifest: " + str(relative))
            _require((ROOT / "engel_library" / relative).exists(), "expected local folder missing: " + str(relative))


def _category_map(data: dict) -> dict[str, dict]:
    categories = data.get("categories")
    _require(isinstance(categories, list), "categories must be a list")
    result = {}
    for category in categories:
        _require(isinstance(category, dict), "category entry must be an object")
        slug = category.get("slug")
        _require(isinstance(slug, str) and slug, "category slug missing")
        result[slug] = category
    _require(set(result) == REQUIRED_CATEGORIES, "category set mismatch")
    return result


def _assert_category_schema(category: dict) -> None:
    for key in ["category", "slug", "display_name", "expected_folder", "purpose", "approved_materials", "safety_notes"]:
        _require(key in category, "category missing key: " + key)
    _require(category.get("category") == category.get("slug"), "category and slug mismatch: " + str(category.get("slug")))
    _require(_normal(str(category["expected_folder"])).startswith(EXPECTED_APPROVED_ROOT), "category expected_folder not under approved root: " + str(category.get("slug")))
    _require(isinstance(category.get("purpose"), str) and category["purpose"], "category purpose missing: " + str(category.get("slug")))
    _require(isinstance(category.get("safety_notes"), list) and category["safety_notes"], "category safety notes missing: " + str(category.get("slug")))
    _require(isinstance(category.get("approved_materials"), list), "approved_materials must be list: " + str(category.get("slug")))


def _assert_material(material: dict) -> None:
    for key in [
        "title",
        "suggested_file",
        "purpose",
        "why_engel_benefits",
        "source_type",
        "allowed_file_types",
        "approval_status",
        "memory_candidate_allowed_after_human_review",
        "trusted_memory_write_allowed",
        "execute_content_allowed",
        "follow_document_instructions_allowed",
    ]:
        _require(key in material, "material missing key: " + key)
    _require(material.get("approval_status") == "approved_for_library_research", "material approval status mismatch: " + str(material.get("title")))
    _require(material.get("memory_candidate_allowed_after_human_review") in {True, False}, "memory candidate flag must be explicit: " + str(material.get("title")))
    for flag in MATERIAL_FALSE_FLAGS:
        _require(material.get(flag) is False, "material flag must be false for " + str(material.get("title")) + ": " + flag)
    _require(isinstance(material.get("allowed_file_types"), list) and material["allowed_file_types"], "allowed file types missing: " + str(material.get("title")))
    source_type = str(material.get("source_type"))
    _require(source_type in SAFE_EXTERNAL_SOURCE_TYPES | SAFE_CURATED_SOURCE_TYPES, "unsafe or unknown source type: " + source_type)
    if source_type in SAFE_EXTERNAL_SOURCE_TYPES:
        _require(material.get("download_status") == "not_downloaded_by_engel_codex", "external material download status mismatch: " + str(material.get("title")))
    if source_type == "local_engel_file":
        local_source = material.get("local_source_path")
        source_status = material.get("source_status")
        _require(isinstance(local_source, str) and local_source, "local source path missing: " + str(material.get("title")))
        _require(source_status in {"present", "missing"}, "local source status mismatch: " + str(material.get("title")))
        exists = Path(local_source).exists()
        _require((exists and source_status == "present") or ((not exists) and source_status == "missing"), "local source status does not match filesystem: " + local_source)


def _assert_categories(data: dict) -> None:
    categories = _category_map(data)
    for slug, category in categories.items():
        _assert_category_schema(category)
        _require(len(category["approved_materials"]) >= MINIMUM_COUNTS[slug], "not enough material entries for " + slug)
        for material in category["approved_materials"]:
            _require(isinstance(material, dict), "material entry must be object: " + slug)
            _assert_material(material)


def _assert_markdown_and_reports() -> None:
    md = _read(MD_PATH).lower()
    report = _read(REPORT_PATH).lower()
    expansion = _read(EXPANSION_REPORT_PATH).lower()
    for text, label in [(md, "markdown"), (report, "report"), (expansion, "expansion report")]:
        for phrase in [
            "research_papers",
            "architecture_references",
            "engel_manuals",
            "offline_docs",
            "math",
            "coding_languages",
            "approved for research/reference only, not trusted memory",
            "actual external downloads remain manual and human-approved",
            "no network, downloads, inference, auto-indexing, recursive scans, background workers, or trusted-memory writes were added",
        ]:
            _require(phrase in text, label + " missing phrase: " + phrase)
    _require("math formulas are reference material" in md, "markdown missing math formula boundary")
    _require("code samples are reference material" in md, "markdown missing code sample boundary")
    _require("new math category and subfolders" in expansion, "expansion report missing math section")
    _require("new coding_languages category and subfolders" in expansion, "expansion report missing coding section")


def main() -> int:
    try:
        data = _load_json()
        _assert_no_obsolete_drive_paths()
        _assert_manifest_flags(data)
        _assert_subfolder_group(data, "math", MATH_SUBFOLDERS)
        _assert_subfolder_group(data, "coding_languages", CODING_SUBFOLDERS)
        _assert_categories(data)
        _assert_markdown_and_reports()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("PASS: Engel Approved Library Materials V1 verifier")
    print("- manifest JSON is valid")
    print("- all six approved material categories are present")
    print("- math and coding language subfolders are represented and local")
    print("- materials remain approved for research/reference only, not trusted memory")
    print("- no download, inference, auto-index, recursive scan, execution, or document-instruction following is enabled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
