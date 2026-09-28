from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engel_browser_queen_status import get_browser_queen_status
from engel_core_v1_dashboard_status import get_core_v1_dashboard_status


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
AUTHORITY_BOUNDARY = "Josh > Guardian > Engel/runtime"
AI_WORKFLOW = "Ask \u2192 Plan \u2192 Proceed \u2192 Receipt \u2192 Review"

BODY_BADGES = [
    "JOSH FIRST",
    "GUARDIAN SECOND",
    "LOCAL ONLY",
    "WRAPPER PACKAGE",
    "NO AUTONOMY",
    "NO MODEL COMMANDS",
]

BODY_HEALTH_BADGES = [
    "AI BODY HEALTH",
    "LOCAL",
    "GUARDED",
    "REPORT-ONLY MEMORY",
    "VERIFY TO CONFIRM",
]

MARKDOWN_KNOWLEDGE_BADGES = [
    "DOCUMENTATION ONLY",
    "FLUID MAP",
    "NOT AUTOMATIC AUTHORITY",
    "NO EXECUTION",
    "NO FILE MOVES",
]

FILE_STRUCTURE_BADGES = [
    "PLAN ONLY",
    "FLUID STRUCTURE",
    "NO FILE MOVES",
    "NO IMPORT MIGRATION",
    "JOSH APPROVAL REQUIRED",
]

CODE_COMPANION_BADGES = [
    "SCRIPT CREATOR",
    "PRODUCT TEMPLATES",
    "PY / JAVA / HTML",
    "PRODUCT ONLY",
    "NOT RUNTIME",
    "READ ONLY PREVIEW",
    "OPEN FOLDER",
    "SOURCE EDITS BLOCKED",
    "NO EXECUTION",
    "APPROVAL GATED",
]

CORE_CONTINUITY_BADGES = [
    "READ ONLY INDEX",
    "NOT TRUSTED MEMORY",
    "RESEARCH SPINE",
    "JOSH FIRST",
]

BROWSER_QUEEN_DISPLAY_BADGES = [
    "DISABLED",
    "NO API",
    "VISIBLE ONLY FUTURE",
    "RESEARCH INPUT",
    "UNTRUSTED PAGES",
]
BROWSER_QUEEN_RESEARCH_PATH = "Research Intake \u2192 Overnight Research"
CORE_V1_DASHBOARD_TITLE = "ENGEL CORE V1 COMMAND CENTER"
CORE_V1_DASHBOARD_MODE = "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED"
CORE_V1_DASHBOARD_MEMORY_BOUNDARY = "NO TRUSTED MEMORY WRITE"
CORE_V1_DASHBOARD_BROWSER_BOUNDARY = "BROWSER QUEEN DISABLED"

BODY_FLOW = [
    "MIND \u2192 GUARDIAN \u2192 ACTION \u2192 MEMORY",
    "             \u2193",
    "          HIVE / GUI",
    "             \u2193",
    "          VERIFIERS",
]


def _exists(relative_path: str) -> bool:
    return (ROOT / relative_path).exists()


def _status_for_path(relative_path: str, present_status: str, missing_status: str = "MISSING") -> str:
    return present_status if _exists(relative_path) else missing_status


def architecture_map_present() -> bool:
    return _exists("engel/ENGEL_AI_ARCHITECTURE.md")


def wrapper_package_present() -> bool:
    required = [
        "engel/__init__.py",
        "engel/mind/__init__.py",
        "engel/guardian/__init__.py",
        "engel/action/__init__.py",
        "engel/memory/__init__.py",
        "engel/hive/__init__.py",
        "engel/gui/__init__.py",
        "engel/verifiers/__init__.py",
    ]
    return all(_exists(path) for path in required)


def _summary_count(summary: dict[str, Any], key: str) -> str:
    value = summary.get(key)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "UNKNOWN"


def _missing_core_continuity_status(json_state: str) -> dict[str, Any]:
    return {
        "title": "ENGEL CORE CONTINUITY",
        "status": "INDEX UNAVAILABLE",
        "json_companion": json_state,
        "products": "UNKNOWN",
        "code_examples": "UNKNOWN",
        "research_reports": "UNKNOWN",
        "lesson_candidates": "UNKNOWN",
        "lesson_reviews": "UNKNOWN",
        "browser_queen_reviews": "UNKNOWN",
        "proceed_receipts": "UNKNOWN",
        "verifiers": "UNKNOWN",
        "trusted_memory": "BLOCKED",
        "learning_status": "candidates only",
        "browser_queen": "research input to Overnight Research, not separate memory",
        "authority": AUTHORITY_BOUNDARY,
        "badges": list(CORE_CONTINUITY_BADGES),
        "source": "memory\\ENGEL_CORE_CONTINUITY_MAP_V1.json",
        "safety_boundary": (
            "Read-only AI Body display of the existing Core Continuity Map. The GUI does not rebuild the map, "
            "write continuity JSON, write trusted memory, promote lessons, apply lessons, run Browser Queen, "
            "launch browsers, execute products, call APIs/network, install packages, mutate queues/routes/source, "
            "enable autonomy, or write ALIVE_STATE."
        ),
    }


def get_core_continuity_status() -> dict[str, Any]:
    summary_path = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
    if not summary_path.exists():
        return _missing_core_continuity_status("MISSING")

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return _missing_core_continuity_status("MALFORMED")

    if not isinstance(payload, dict):
        return _missing_core_continuity_status("MALFORMED")

    status = " ".join(str(payload.get("continuity_status", "READ_ONLY_INDEX")).strip().split("_"))
    if not status:
        status = "READ ONLY INDEX"
    trusted_memory = " ".join(str(payload.get("trusted_memory_write_status", "BLOCKED")).strip().split("_"))
    if not trusted_memory:
        trusted_memory = "BLOCKED"

    return {
        **_missing_core_continuity_status("PRESENT"),
        "status": status,
        "products": _summary_count(payload, "products_count"),
        "code_examples": _summary_count(payload, "code_examples_count"),
        "research_reports": _summary_count(payload, "research_reports_count"),
        "lesson_candidates": _summary_count(payload, "lesson_candidates_count"),
        "lesson_reviews": _summary_count(payload, "lesson_reviews_count"),
        "browser_queen_reviews": _summary_count(payload, "browser_queen_review_count"),
        "proceed_receipts": _summary_count(payload, "proceed_receipts_count"),
        "verifiers": _summary_count(payload, "verifier_count"),
        "trusted_memory": trusted_memory,
        "learning_status": "candidates only",
        "browser_queen": "research input to Overnight Research, not separate memory",
        "authority": str(payload.get("authority", AUTHORITY_BOUNDARY)) or AUTHORITY_BOUNDARY,
    }


def build_markdown_knowledge_summary() -> dict[str, Any]:
    summary_path = ROOT / "memory" / "ENGEL_MARKDOWN_KNOWLEDGE_INDEX_V1.json"
    base = {
        "title": "MARKDOWN KNOWLEDGE",
        "status": "INDEX UNAVAILABLE",
        "json_companion": "MISSING",
        "files_found": "UNKNOWN",
        "indexed": "UNKNOWN",
        "summarized_excluded": "UNKNOWN",
        "critical_files": "UNKNOWN",
        "unknown_needs_review": "UNKNOWN",
        "authority": "context, not automatic authority",
        "badges": list(MARKDOWN_KNOWLEDGE_BADGES),
        "source": "memory\\ENGEL_MARKDOWN_KNOWLEDGE_INDEX_V1.json",
        "safety_boundary": (
            "Read-only documentation visibility only. The GUI does not scan markdown, rebuild the index, "
            "run verifiers, move files, execute markdown, or treat markdown as authority."
        ),
    }
    if not summary_path.exists():
        return base

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        unavailable = dict(base)
        unavailable["json_companion"] = "MALFORMED"
        return unavailable

    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict):
        unavailable = dict(base)
        unavailable["json_companion"] = "MALFORMED"
        return unavailable

    index_summary = payload["summary"]
    return {
        **base,
        "status": "DOCUMENTATION ONLY",
        "json_companion": "PRESENT",
        "files_found": _summary_count(index_summary, "all_markdown_files_found"),
        "indexed": _summary_count(index_summary, "indexed_records"),
        "summarized_excluded": _summary_count(index_summary, "summarized_or_excluded"),
        "critical_files": _summary_count(index_summary, "critical_files_identified"),
        "unknown_needs_review": _summary_count(index_summary, "unknown_needs_review_files"),
    }


def _missing_file_structure_summary(json_state: str) -> dict[str, Any]:
    return {
        "title": "FILE STRUCTURE",
        "status": "PLAN UNAVAILABLE",
        "json_companion": json_state,
        "current_layout": "UNKNOWN",
        "future_layout": "UNKNOWN",
        "migration_status": "UNKNOWN",
        "next_slice": "UNKNOWN",
        "policy": "JOSH-APPROVED SLICES ONLY",
        "live_imports_changed": "UNKNOWN",
        "files_moved_renamed": "UNKNOWN",
        "packaging_required": "UNKNOWN",
        "badges": list(FILE_STRUCTURE_BADGES),
        "source": "memory\\ENGEL_FLUID_FILE_STRUCTURE_PLAN_V1.json",
        "safety_boundary": (
            "Read-only GUI visibility only. The GUI does not rebuild the structure plan, scan project files, "
            "run verifiers, move files, change imports, package, or treat the plan as migration approval."
        ),
    }


def build_file_structure_summary() -> dict[str, Any]:
    summary_path = ROOT / "memory" / "ENGEL_FLUID_FILE_STRUCTURE_PLAN_V1.json"
    if not summary_path.exists():
        return _missing_file_structure_summary("MISSING")

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return _missing_file_structure_summary("MALFORMED")

    if not isinstance(payload, dict):
        return _missing_file_structure_summary("MALFORMED")

    policy = payload.get("fluid_structure_policy")
    future_structure = payload.get("future_structure")
    migration_slices = payload.get("migration_slices")
    recommended_next_step = payload.get("recommended_next_step")
    safety_boundaries = payload.get("safety_boundaries")
    safety_statement = str(payload.get("safety_statement", ""))

    if not isinstance(policy, dict) or not isinstance(future_structure, dict) or not isinstance(migration_slices, list):
        return _missing_file_structure_summary("MALFORMED")

    display = recommended_next_step.get("display", {}) if isinstance(recommended_next_step, dict) else {}
    next_slice_value = str(display.get("next_approved_slice", "")).strip().upper()
    if next_slice_value == "NONE":
        next_slice_value = "NONE APPROVED"
    if not next_slice_value:
        next_slice_value = "UNKNOWN"

    all_slices_not_started = all(
        isinstance(item, dict) and str(item.get("status", "")).strip().lower() == "not_started"
        for item in migration_slices
    )
    future_folders = future_structure.get("folders")
    boundary_text = " ".join(str(item).lower() for item in safety_boundaries) if isinstance(safety_boundaries, list) else ""
    safety_text = safety_statement.lower()

    live_imports_changed = "NO" if "imports" in safety_text and "does not change" in safety_text else "UNKNOWN"
    files_moved_renamed = "NO" if "no files moved or renamed" in boundary_text or "does not move, rename" in safety_text else "UNKNOWN"
    packaging_required = "NO" if "packaging" in safety_text and "does not" in safety_text else "UNKNOWN"

    return {
        "title": "FILE STRUCTURE",
        "status": "PLAN ONLY",
        "json_companion": "PRESENT",
        "current_layout": "STABLE" if policy.get("live_layout_remains_unchanged") is True else "UNKNOWN",
        "future_layout": "PLANNED" if isinstance(future_folders, list) and future_folders else "UNKNOWN",
        "migration_status": "NOT STARTED" if all_slices_not_started else "REVIEW REQUIRED",
        "next_slice": next_slice_value,
        "policy": (
            "JOSH-APPROVED SLICES ONLY"
            if policy.get("migration_requires_separate_josh_approved_slice") is True
            else "JOSH APPROVAL REQUIRED"
        ),
        "live_imports_changed": live_imports_changed,
        "files_moved_renamed": files_moved_renamed,
        "packaging_required": packaging_required,
        "badges": list(FILE_STRUCTURE_BADGES),
        "source": "memory\\ENGEL_FLUID_FILE_STRUCTURE_PLAN_V1.json",
        "safety_boundary": (
            "Read-only GUI visibility only. The GUI does not rebuild the structure plan, scan project files, "
            "run verifiers, move files, change imports, package, or treat the plan as migration approval."
        ),
    }


def build_code_companion_summary() -> dict[str, Any]:
    return {
        "title": "CODE COMPANION",
        "status": "SCRIPT CREATOR / PRODUCT TEMPLATES / PRODUCT ONLY",
        "script_creator": "Python / Java / HTML",
        "product_templates": "Python CLI, Python GUI, Java Console, HTML Dashboard, HTML Mini App",
        "products_root": "products\\",
        "examples_root": "examples\\code_companion",
        "product_preview": "read-only",
        "open_folder": "user-clicked / bounded to products\\",
        "save_root": "examples\\code_companion",
        "runtime_source_edits": "BLOCKED",
        "apply": "NOT ENABLED",
        "apply_to_engel": "NOT ENABLED",
        "overwrite": "APPROVE_CHANGE required",
        "python_validation": "ast / py_compile",
        "java_toolchain": "proposal-only unless present",
        "html": "local-only / no remote deps",
        "dependencies": "APPROVE_INSTALL required",
        "badges": list(CODE_COMPANION_BADGES),
        "source": "engel_code_companion.py + engel_code_companion_examples.py + engel_code_companion_products.py",
        "safety_boundary": (
            "Code Companion may save example-only Python, Java, and HTML files under examples\\code_companion and "
            "product-only starter folders under products\\. Product preview is read-only, and Open Folder is user-clicked "
            "and bounded to products\\. It does not edit Engel runtime source, apply to Engel, "
            "run generated code, execute previewed content, run arbitrary shell commands, call providers/network, install packages without "
            "APPROVE_INSTALL, overwrite products without APPROVE_CHANGE, write trusted memory, or mutate queues/routes."
        ),
    }


def build_browser_queen_summary() -> dict[str, Any]:
    return get_browser_queen_status()


def organ_status_cards() -> list[dict[str, Any]]:
    return [
        {
            "name": "MIND",
            "purpose": "Understanding, classification, planning, local seed brain, routing, and teaching.",
            "mapped_modules": [
                "engel_ai_intent_planner.py - " + _status_for_path("engel_ai_intent_planner.py", "ACTIVE"),
                "engel_communication_router.py - " + _status_for_path("engel_communication_router.py", "ACTIVE"),
                "engel_offline_seed_llm.py - " + _status_for_path("engel_offline_seed_llm.py", "GUARDED"),
                "engel_python_teaching_mode.py - " + _status_for_path("engel_python_teaching_mode.py", "ACTIVE"),
                "engel/mind wrappers - " + _status_for_path("engel/mind/intent_planner.py", "WRAPPER_ONLY"),
            ],
            "status": "MAPPED / ACTIVE / WRAPPER_ONLY",
            "health_indicators": ["MAPPED", "PLAN LAYER ACTIVE", "SEED BRAIN GUARDED"],
            "safety_boundary": "Planner and router stay deterministic; offline seed brain remains gated; no model commands.",
        },
        {
            "name": "GUARDIAN",
            "purpose": "Authority, prompt-injection defense, safety contracts, and approval boundaries.",
            "mapped_modules": [
                "engel_prompt_injection_guard.py - " + _status_for_path("engel_prompt_injection_guard.py", "ACTIVE"),
                "tools/verify_authority_hierarchy.py - " + _status_for_path("tools/verify_authority_hierarchy.py", "PRESENT"),
                "memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md - "
                + _status_for_path("memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md", "PRESENT"),
                "engel/guardian wrapper - " + _status_for_path("engel/guardian/prompt_injection_guard.py", "WRAPPER_ONLY"),
            ],
            "status": "ACTIVE",
            "health_indicators": ["ACTIVE", "JOSH FIRST", "INJECTION GUARD"],
            "safety_boundary": "Josh remains final authority; Guardian reviews safety; Engel/runtime stays below both.",
        },
        {
            "name": "ACTION",
            "purpose": "Human-approved deterministic action surfaces and guarded local commands.",
            "mapped_modules": [
                "engel_human_command_mode.py - " + _status_for_path("engel_human_command_mode.py", "GUARDED"),
                "AI Plan Proceed in engel_companion.py - " + _status_for_path("engel_companion.py", "GUARDED"),
                "AI Plan Proceed in Super Swarm scaffold - "
                + _status_for_path("tools/engel_super_swarm_hive_3d_scaffold.py", "GUARDED"),
                "engel/action wrapper - " + _status_for_path("engel/action/human_command_mode.py", "WRAPPER_ONLY"),
            ],
            "status": "GUARDED",
            "health_indicators": ["GUARDED", "HUMAN COMMANDS", "PROCEED CHECKED"],
            "safety_boundary": "Proceed can use only approval-free allowlisted deterministic routes; no arbitrary shell.",
        },
        {
            "name": "MEMORY",
            "purpose": "Report-only receipts, review surfaces, and future memory candidates.",
            "mapped_modules": [
                "engel_ai_proceed_receipts.py - " + _status_for_path("engel_ai_proceed_receipts.py", "REPORT_ONLY"),
                "engel_ai_receipt_viewer.py - " + _status_for_path("engel_ai_receipt_viewer.py", "READ_ONLY"),
                "reports/ai_proceed_receipts - " + _status_for_path("reports/ai_proceed_receipts", "REPORT_ONLY"),
                "engel/memory wrappers - " + _status_for_path("engel/memory/proceed_receipts.py", "WRAPPER_ONLY"),
            ],
            "status": "REPORT_ONLY / NOT TRUSTED MEMORY",
            "health_indicators": ["REPORT ONLY", "RECEIPTS", "NOT TRUSTED MEMORY"],
            "safety_boundary": "Receipts are audit artifacts only; no trust promotion, execution, queue, route, or source mutation.",
        },
        {
            "name": "HIVE",
            "purpose": "Colony Hive, Research Office, Communication Queen, Queen Links, and Super Swarm visibility.",
            "mapped_modules": [
                "engel_research_office.py - " + _status_for_path("engel_research_office.py", "LOCAL_VISUAL"),
                "engel_research_office_data.py - " + _status_for_path("engel_research_office_data.py", "READ_ONLY_DATA"),
                "tools/engel_super_swarm_hive_3d_scaffold.py - "
                + _status_for_path("tools/engel_super_swarm_hive_3d_scaffold.py", "LOCAL_VISUAL"),
                "memory/TRUSTED_REMOTE_QUEEN_PROTOCOL_DESIGN_V1.md - "
                + _status_for_path("memory/TRUSTED_REMOTE_QUEEN_PROTOCOL_DESIGN_V1.md", "PROTOCOL_GATED"),
            ],
            "status": "LOCAL VISUAL / PROTOCOL_GATED",
            "health_indicators": ["LOCAL VISUAL", "PROTOCOL GATED", "REMOTE RUNTIME OFF"],
            "safety_boundary": "Remote Queen runtime and networking stay disabled; Hive surfaces show local state only.",
        },
        {
            "name": "GUI",
            "purpose": "Companion dashboard, AI Plan panel, Proceed button, Receipt Viewer, and view controls.",
            "mapped_modules": [
                "engel_companion.py - " + _status_for_path("engel_companion.py", "VISIBLE_BODY"),
                "tools/engel_super_swarm_hive_3d_scaffold.py - "
                + _status_for_path("tools/engel_super_swarm_hive_3d_scaffold.py", "VISIBLE_BODY"),
                "engel_ui_theme.py - " + _status_for_path("engel_ui_theme.py", "PRESENT"),
                "engel/gui package - " + _status_for_path("engel/gui/__init__.py", "MAPPED"),
            ],
            "status": "READ_ONLY / VISIBLE BODY",
            "health_indicators": ["VISIBLE BODY", "PLAN PANEL", "RECEIPT VIEWER"],
            "safety_boundary": "AI Body display reads static architecture status; no verifier or command execution from this panel.",
        },
        {
            "name": "VERIFIERS",
            "purpose": "Guardian immune system and regression checks.",
            "mapped_modules": [
                "tools/verify_ai_intent_planner.py - " + _status_for_path("tools/verify_ai_intent_planner.py", "PRESENT"),
                "tools/verify_ai_proceed_receipts.py - " + _status_for_path("tools/verify_ai_proceed_receipts.py", "PRESENT"),
                "tools/verify_prompt_injection_guard.py - " + _status_for_path("tools/verify_prompt_injection_guard.py", "PRESENT"),
                "tools/verify_authority_hierarchy.py - " + _status_for_path("tools/verify_authority_hierarchy.py", "PRESENT"),
                "tools/verify_human_command_mode_contract.py - "
                + _status_for_path("tools/verify_human_command_mode_contract.py", "PRESENT"),
                "tools/verify_route_metadata_contract.py - " + _status_for_path("tools/verify_route_metadata_contract.py", "PRESENT"),
                "tools/verify_living_systems_documentation_drift.py - "
                + _status_for_path("tools/verify_living_systems_documentation_drift.py", "PRESENT"),
                "tools/verify_engel_ai_architecture_package.py - "
                + _status_for_path("tools/verify_engel_ai_architecture_package.py", "PRESENT"),
            ],
            "status": "IMMUNE SYSTEM / FILES PRESENT",
            "health_indicators": ["IMMUNE SYSTEM", "FILES PRESENT", "VERIFY TO CONFIRM"],
            "safety_boundary": "Verifier files are present; run verifiers externally to confirm current results.",
        },
    ]


def build_ai_body_status() -> dict[str, Any]:
    return {
        "title": "ENGEL AI BODY",
        "subtitle": "Local AI organs mapped under Josh-first authority.",
        "authority": AUTHORITY_BOUNDARY,
        "workflow": AI_WORKFLOW,
        "badges": list(BODY_BADGES),
        "health_badges": list(BODY_HEALTH_BADGES),
        "body_flow": list(BODY_FLOW),
        "architecture_map_present": architecture_map_present(),
        "wrapper_package_present": wrapper_package_present(),
        "markdown_knowledge": build_markdown_knowledge_summary(),
        "file_structure": build_file_structure_summary(),
        "code_companion": build_code_companion_summary(),
        "core_v1_dashboard": get_core_v1_dashboard_status(),
        "core_continuity": get_core_continuity_status(),
        "browser_queen": build_browser_queen_summary(),
        "organ_cards": organ_status_cards(),
        "runtime_note": (
            "Read-only architecture visibility only. No verifiers, commands, routes, reports, "
            "provider calls, model commands, autonomy, queue mutation, trusted-memory writes, "
            "source edits, or Remote Queen runtime are executed from this status."
        ),
    }


def render_ai_body_status_text() -> str:
    status = build_ai_body_status()
    lines = [
        "# " + str(status["title"]),
        "",
        str(status["subtitle"]),
        "",
        "Authority: " + str(status["authority"]),
        "Workflow: " + str(status["workflow"]),
        "Wiki One: wiki/ONE.md — whole Engel AI Main reads it before CODE and updates it when organs change.",
        "Wiki One journal: wiki/journal — stamp after CODE. Phrases: wiki one / wiki journal / update wiki one.",
        "Architecture map present: " + ("yes" if status["architecture_map_present"] else "no"),
        "Wrapper package present: " + ("yes" if status["wrapper_package_present"] else "no"),
        "",
        "Badges: " + " | ".join(status["badges"]),
        "AI Body health: " + " | ".join(status["health_badges"]),
        "",
        "Markdown Knowledge:",
        "Status: " + str(status["markdown_knowledge"]["status"]),
        "Files found: " + str(status["markdown_knowledge"]["files_found"]),
        "Indexed: " + str(status["markdown_knowledge"]["indexed"]),
        "Summarized/excluded: " + str(status["markdown_knowledge"]["summarized_excluded"]),
        "Critical files: " + str(status["markdown_knowledge"]["critical_files"]),
        "Unknown / Needs Review: " + str(status["markdown_knowledge"]["unknown_needs_review"]),
        "JSON companion: " + str(status["markdown_knowledge"]["json_companion"]),
        "Authority: " + str(status["markdown_knowledge"]["authority"]),
        "Badges: " + " | ".join(status["markdown_knowledge"]["badges"]),
        "Boundary: " + str(status["markdown_knowledge"]["safety_boundary"]),
        "",
        "File Structure:",
        "Status: " + str(status["file_structure"]["status"]),
        "Current layout: " + str(status["file_structure"]["current_layout"]),
        "Future layout: " + str(status["file_structure"]["future_layout"]),
        "Migration status: " + str(status["file_structure"]["migration_status"]),
        "Next slice: " + str(status["file_structure"]["next_slice"]),
        "Policy: " + str(status["file_structure"]["policy"]),
        "Live imports changed: " + str(status["file_structure"]["live_imports_changed"]),
        "Files moved/renamed: " + str(status["file_structure"]["files_moved_renamed"]),
        "Packaging required: " + str(status["file_structure"]["packaging_required"]),
        "JSON companion: " + str(status["file_structure"]["json_companion"]),
        "Badges: " + " | ".join(status["file_structure"]["badges"]),
        "Boundary: " + str(status["file_structure"]["safety_boundary"]),
        "",
        "Code Companion:",
        "Status: " + str(status["code_companion"]["status"]),
        "Script creator: " + str(status["code_companion"]["script_creator"]),
        "Product templates: " + str(status["code_companion"]["product_templates"]),
        "Products root: " + str(status["code_companion"]["products_root"]),
        "Examples root: " + str(status["code_companion"]["examples_root"]),
        "Product preview: " + str(status["code_companion"]["product_preview"]),
        "Open folder: " + str(status["code_companion"]["open_folder"]),
        "Runtime source edits: " + str(status["code_companion"]["runtime_source_edits"]),
        "Apply to Engel: " + str(status["code_companion"]["apply_to_engel"]),
        "Overwrite: " + str(status["code_companion"]["overwrite"]),
        "Python validation: " + str(status["code_companion"]["python_validation"]),
        "Java toolchain: " + str(status["code_companion"]["java_toolchain"]),
        "HTML: " + str(status["code_companion"]["html"]),
        "Dependencies: " + str(status["code_companion"]["dependencies"]),
        "Badges: " + " | ".join(status["code_companion"]["badges"]),
        "Boundary: " + str(status["code_companion"]["safety_boundary"]),
        "",
        "ENGEL CORE V1 COMMAND CENTER:",
        "Core: " + str(status["core_v1_dashboard"]["core_status"]),
        "Authority: " + str(status["core_v1_dashboard"]["authority"]),
        "Flow: " + str(status["core_v1_dashboard"]["flow"]),
        "Products: " + str(status["core_v1_dashboard"]["products_count"]),
        "Research: "
        + str(status["core_v1_dashboard"]["research_intake_receipts_count"])
        + " receipts / "
        + str(status["core_v1_dashboard"]["research_summary_proposals_count"])
        + " summaries",
        "Lessons: "
        + str(status["core_v1_dashboard"]["lesson_candidates_count"])
        + " product / "
        + str(status["core_v1_dashboard"]["research_lesson_candidates_count"])
        + " research",
        "Reviews: "
        + str(status["core_v1_dashboard"]["lesson_reviews_count"])
        + " product / "
        + str(status["core_v1_dashboard"]["research_lesson_reviews_count"])
        + " research",
        "Memory candidates: " + str(status["core_v1_dashboard"]["memory_candidate_proposals_count"]),
        "Browser Queen: "
        + str(status["core_v1_dashboard"]["browser_queen_status"])
        + " \u2192 Research Intake",
        "Trusted Memory: " + str(status["core_v1_dashboard"]["trusted_memory_status"]),
        "Guards: Untrusted Content Guard "
        + str(status["core_v1_dashboard"]["untrusted_content_guard"])
        + " / Prompt Injection Guard "
        + str(status["core_v1_dashboard"]["prompt_injection_guard"]),
        "Status: " + str(status["core_v1_dashboard"]["dashboard_mode"]),
        "Badges: " + " | ".join(status["core_v1_dashboard"]["badges"]),
        "Boundary: " + str(status["core_v1_dashboard"]["safety_boundary"]),
        "",
        "ENGEL CORE CONTINUITY:",
        "Status: " + str(status["core_continuity"]["status"]),
        "Products: " + str(status["core_continuity"]["products"]),
        "Code examples: " + str(status["core_continuity"]["code_examples"]),
        "Research reports: " + str(status["core_continuity"]["research_reports"]),
        "Lessons: "
        + str(status["core_continuity"]["lesson_candidates"])
        + " / "
        + str(status["core_continuity"]["lesson_reviews"]),
        "Browser Queen: " + str(status["core_continuity"]["browser_queen"]),
        "Trusted memory: " + str(status["core_continuity"]["trusted_memory"]),
        "Learning status: " + str(status["core_continuity"]["learning_status"]),
        "JSON companion: " + str(status["core_continuity"]["json_companion"]),
        "Badges: " + " | ".join(status["core_continuity"]["badges"]),
        "Boundary: " + str(status["core_continuity"]["safety_boundary"]),
        "",
        "BROWSER QUEEN:",
        "Status: " + str(status["browser_queen"]["status"]),
        "Mode: " + str(status["browser_queen"]["mode"]),
        "API: " + str(status["browser_queen"]["api"]),
        "Research path: " + str(status["browser_queen"]["research_display"]),
        "Page content: " + str(status["browser_queen"]["page_display"]),
        "Action receipts: " + str(status["browser_queen"]["action_receipts"]),
        "Trusted memory: " + str(status["browser_queen"]["trusted_memory"]),
        "Badges: " + " | ".join(status["browser_queen"]["badges"]),
        "Boundary: " + str(status["browser_queen"]["safety_boundary"]),
        "",
        "Body flow:",
        *status["body_flow"],
        "",
        "Organs:",
    ]
    for card in status["organ_cards"]:
        lines.extend(
            [
                "",
                "## " + str(card["name"]),
                "Purpose: " + str(card["purpose"]),
                "Status: " + str(card["status"]),
                "Health: " + " | ".join(str(item) for item in card.get("health_indicators", [])),
                "Mapped modules:",
            ]
        )
        for module in card["mapped_modules"]:
            lines.append("- " + str(module))
        lines.append("Safety: " + str(card["safety_boundary"]))
    lines.extend(["", "Runtime note:", str(status["runtime_note"])])
    return "\n".join(lines)
