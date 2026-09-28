#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib
import json
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

HELPER = ROOT / "engel_ai_body_status.py"
COMPANION = ROOT / "engel_companion.py"
SUPER_SWARM = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
ROUTES = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
MARKDOWN_INDEX_JSON = ROOT / "memory" / "ENGEL_MARKDOWN_KNOWLEDGE_INDEX_V1.json"
FLUID_FILE_STRUCTURE_JSON = ROOT / "memory" / "ENGEL_FLUID_FILE_STRUCTURE_PLAN_V1.json"
CORE_CONTINUITY_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
BROWSER_QUEEN_CONTRACT_JSON = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_CONTRACT_V1.json"

AUTHORITY = "Josh > Guardian > Engel/runtime"
WORKFLOW = "Ask \u2192 Plan \u2192 Proceed \u2192 Receipt \u2192 Review"
ORGANS = ["MIND", "GUARDIAN", "ACTION", "MEMORY", "HIVE", "GUI", "VERIFIERS"]
REQUIRED_HEALTH_INDICATORS = {
    "MIND": ["MAPPED", "PLAN LAYER ACTIVE", "SEED BRAIN GUARDED"],
    "GUARDIAN": ["ACTIVE", "JOSH FIRST", "INJECTION GUARD"],
    "ACTION": ["GUARDED", "HUMAN COMMANDS", "PROCEED CHECKED"],
    "MEMORY": ["REPORT ONLY", "RECEIPTS", "NOT TRUSTED MEMORY"],
    "HIVE": ["LOCAL VISUAL", "PROTOCOL GATED", "REMOTE RUNTIME OFF"],
    "GUI": ["VISIBLE BODY", "PLAN PANEL", "RECEIPT VIEWER"],
    "VERIFIERS": ["IMMUNE SYSTEM", "FILES PRESENT", "VERIFY TO CONFIRM"],
}
HEALTH_SUMMARY = ["AI BODY HEALTH", "LOCAL", "GUARDED", "REPORT-ONLY MEMORY", "VERIFY TO CONFIRM"]
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
BROWSER_QUEEN_BADGES = [
    "DISABLED",
    "NO API",
    "VISIBLE ONLY FUTURE",
    "RESEARCH INPUT",
    "UNTRUSTED PAGES",
]
CORE_V1_DASHBOARD_BADGES = [
    "CORE V1",
    "READ ONLY",
    "JOSH FIRST",
    "GUARDIAN ACTIVE",
    "NO TRUSTED MEMORY WRITE",
    "BROWSER QUEEN DISABLED",
]
LIVE_VERIFIER_PASS_TERMS = ["PASS", "PASSED", "PASSING", "LIVE PASS", "LIVE HEALTH PASS"]


class CheckFailure(Exception):
    pass


def _term(*parts: str) -> str:
    return "".join(parts)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + _rel(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _compile(path: Path) -> None:
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + _rel(path) + ": " + str(exc)) from exc


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker))
    _require(start >= 0, "missing start marker: " + start_marker)
    _require(end >= 0, "missing end marker: " + end_marker)
    return text[start:end]


def _forbidden_terms() -> list[str]:
    return [
        _term("op", "enai"),
        _term("anth", "ropic"),
        _term("api", "_", "key"),
        _term("requests", "."),
        _term("http", "://"),
        _term("https", "://"),
        _term("sock", "et"),
        _term("web", "sock", "et"),
        _term("u", "dp"),
        _term("t", "cp"),
        _term("blue", "tooth"),
        _term("md", "ns"),
        _term("zero", "conf"),
        _term("thread", "ing"),
        _term("multi", "processing"),
        _term("watch", "dog"),
        _term("sche", "dule"),
        _term("while", " True"),
        _term("Start", "-", "Process"),
        _term("os", ".", "system"),
        _term("P", "open"),
        _term("shell", "=", "True"),
        _term("local", "host", ":", "11434"),
        _term("ol", "lama"),
    ]


def check_helper_static() -> None:
    _compile(HELPER)
    source = _read(HELPER)
    lowered = source.lower()
    for term in _forbidden_terms():
        _require(term.lower() not in lowered, "helper contains forbidden term: " + term)
    for forbidden in [
        "build_markdown_knowledge_index",
        "verify_markdown_knowledge_index",
        "verify_fluid_file_structure_plan",
        "build_engel_core_continuity_map",
        "verify_engel_core_continuity_map",
        "ENGEL_FLUID_FILE_STRUCTURE_PLAN.md",
        ".rglob(",
        ".glob(",
        "iterdir(",
        "os.walk",
    ]:
        _require(forbidden.lower() not in lowered, "helper must not scan/rebuild/run plan or index behavior: " + forbidden)
    for needle in [
        "get_core_continuity_status",
        "get_core_v1_dashboard_status",
        "get_browser_queen_status",
        "build_browser_queen_summary",
        "ENGEL CORE V1 COMMAND CENTER",
        "CORE V1",
        "READ ONLY",
        "NO TRUSTED MEMORY WRITE",
        "BROWSER QUEEN DISABLED",
        "Untrusted Content Guard",
        "Prompt Injection Guard",
        "ENGEL_CORE_CONTINUITY_MAP_V1.json",
        "ENGEL CORE CONTINUITY",
        "READ ONLY INDEX",
        "NOT TRUSTED MEMORY",
        "RESEARCH SPINE",
        "research input to Overnight Research, not separate memory",
        "write continuity JSON",
        "BROWSER QUEEN",
        "DISABLED",
        "NO API",
        "VISIBLE ONLY FUTURE",
        "RESEARCH INPUT",
        "UNTRUSTED PAGES",
        "Research Intake",
        "Overnight Research",
        "Action receipts:",
    ]:
        _require(needle in source, "helper missing Core Continuity read-only display text: " + needle)

    tree = ast.parse(source)
    blocked_import_roots = {
        "http",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "webbrowser",
        "threading",
        "multiprocessing",
    }
    blocked_calls = {"eval", "exec", "compile", "__import__"}
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
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            _require(root not in blocked_import_roots, "helper imports from blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in blocked_calls, "helper calls blocked builtin: " + func.id)
            if isinstance(func, ast.Attribute):
                _require(func.attr not in blocked_methods, "helper calls blocked method: " + func.attr)


def _expected_markdown_summary() -> dict[str, str]:
    payload = json.loads(MARKDOWN_INDEX_JSON.read_text(encoding="utf-8"))
    summary = payload["summary"]

    def fmt(key: str) -> str:
        value = summary[key]
        return f"{value:,}" if isinstance(value, int) else str(value)

    return {
        "files_found": fmt("all_markdown_files_found"),
        "indexed": fmt("indexed_records"),
        "summarized_excluded": fmt("summarized_or_excluded"),
        "critical_files": fmt("critical_files_identified"),
        "unknown_needs_review": fmt("unknown_needs_review_files"),
    }


def _expected_file_structure_summary() -> dict[str, str]:
    payload = json.loads(FLUID_FILE_STRUCTURE_JSON.read_text(encoding="utf-8"))
    policy = payload["fluid_structure_policy"]
    future_structure = payload["future_structure"]
    migration_slices = payload["migration_slices"]
    recommended_next_step = payload["recommended_next_step"]
    display = recommended_next_step["display"]
    next_slice = str(display["next_approved_slice"]).upper()
    if next_slice == "NONE":
        next_slice = "NONE APPROVED"
    all_slices_not_started = all(str(item.get("status", "")).lower() == "not_started" for item in migration_slices)
    safety_text = str(payload.get("safety_statement", "")).lower()
    boundaries = " ".join(str(item).lower() for item in payload.get("safety_boundaries", []))
    return {
        "status": "PLAN ONLY",
        "json_companion": "PRESENT",
        "current_layout": "STABLE" if policy.get("live_layout_remains_unchanged") is True else "UNKNOWN",
        "future_layout": "PLANNED" if future_structure.get("folders") else "UNKNOWN",
        "migration_status": "NOT STARTED" if all_slices_not_started else "REVIEW REQUIRED",
        "next_slice": next_slice,
        "policy": "JOSH-APPROVED SLICES ONLY",
        "live_imports_changed": "NO" if "imports" in safety_text and "does not change" in safety_text else "UNKNOWN",
        "files_moved_renamed": "NO" if "no files moved or renamed" in boundaries or "does not move, rename" in safety_text else "UNKNOWN",
        "packaging_required": "NO" if "packaging" in safety_text and "does not" in safety_text else "UNKNOWN",
    }


def _expected_core_continuity_summary() -> dict[str, str]:
    payload = json.loads(CORE_CONTINUITY_JSON.read_text(encoding="utf-8"))

    def fmt(key: str) -> str:
        value = payload[key]
        return f"{value:,}" if isinstance(value, int) else str(value)

    return {
        "status": str(payload["continuity_status"]).replace("_", " "),
        "json_companion": "PRESENT",
        "products": fmt("products_count"),
        "code_examples": fmt("code_examples_count"),
        "research_reports": fmt("research_reports_count"),
        "lesson_candidates": fmt("lesson_candidates_count"),
        "lesson_reviews": fmt("lesson_reviews_count"),
        "browser_queen_reviews": fmt("browser_queen_review_count"),
        "proceed_receipts": fmt("proceed_receipts_count"),
        "verifiers": fmt("verifier_count"),
        "trusted_memory": str(payload["trusted_memory_write_status"]).replace("_", " "),
        "authority": AUTHORITY,
        "browser_queen": "research input to Overnight Research, not separate memory",
        "learning_status": "candidates only",
    }


def _expected_browser_queen_summary() -> dict[str, str]:
    payload = json.loads(BROWSER_QUEEN_CONTRACT_JSON.read_text(encoding="utf-8"))
    return {
        "title": "BROWSER QUEEN",
        "status": str(payload["status"]),
        "mode": str(payload["mode"]),
        "api": str(payload["api"]),
        "research_path": str(payload["research_path"]),
        "research_display": "Research Intake \u2192 Overnight Research",
        "page_content": str(payload["page_content"]),
        "page_display": "untrusted",
        "action_receipts": str(payload["action_receipts"]),
        "trusted_memory": str(payload["trusted_memory"]),
        "authority": AUTHORITY,
    }


def _expected_core_v1_dashboard_summary() -> dict[str, str]:
    payload = json.loads(CORE_CONTINUITY_JSON.read_text(encoding="utf-8"))

    def fmt(key: str) -> str:
        value = payload[key]
        return f"{value:,}" if isinstance(value, int) else str(value)

    return {
        "core_status": "LIVE BASELINE",
        "authority": AUTHORITY,
        "products_count": fmt("products_count"),
        "research_intake_receipts_count": fmt("research_intake_receipts_count"),
        "research_summary_proposals_count": fmt("research_summary_proposals_count"),
        "lesson_candidates_count": fmt("lesson_candidates_count"),
        "lesson_reviews_count": fmt("lesson_reviews_count"),
        "research_lesson_candidates_count": fmt("research_lesson_candidates_count"),
        "research_lesson_reviews_count": fmt("research_lesson_reviews_count"),
        "memory_candidate_proposals_count": fmt("memory_candidate_proposals_count"),
        "browser_queen_status": "DISABLED",
        "browser_queen_path": "Research Intake \u2192 Overnight Research",
        "trusted_memory_status": str(payload["memory_candidate_trusted_memory_status"]),
        "untrusted_content_guard": "ACTIVE",
        "prompt_injection_guard": "ACTIVE",
        "dashboard_mode": "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
    }


def check_helper_behavior() -> None:
    sys.path.insert(0, str(ROOT))
    helper = importlib.import_module("engel_ai_body_status")
    status = helper.build_ai_body_status()
    rendered = helper.render_ai_body_status_text()
    direct_markdown_summary = helper.build_markdown_knowledge_summary()
    direct_file_structure_summary = helper.build_file_structure_summary()
    direct_code_companion_summary = helper.build_code_companion_summary()
    direct_core_v1_dashboard_status = helper.get_core_v1_dashboard_status()
    direct_core_continuity_status = helper.get_core_continuity_status()
    direct_browser_queen_summary = helper.build_browser_queen_summary()
    _require(status.get("authority") == AUTHORITY, "helper authority mismatch")
    _require(status.get("workflow") == WORKFLOW, "helper workflow mismatch")
    _require(status.get("architecture_map_present") is True, "architecture map should be present")
    _require(status.get("wrapper_package_present") is True, "wrapper package should be present")
    for organ in ORGANS:
        _require(organ in rendered, "helper/rendered status missing organ: " + organ)
    _require("Verifier files are present; run verifiers externally to confirm current results." in rendered, "missing honest verifier state text")
    health_badges = status.get("health_badges")
    _require(health_badges == HEALTH_SUMMARY, "helper health summary badges mismatch")
    markdown_summary = status.get("markdown_knowledge")
    _require(markdown_summary == direct_markdown_summary, "helper build_ai_body_status must expose Markdown Knowledge summary")
    _require(isinstance(markdown_summary, dict), "Markdown Knowledge summary must be a dict")
    _require(markdown_summary.get("title") == "MARKDOWN KNOWLEDGE", "Markdown Knowledge title mismatch")
    _require(markdown_summary.get("status") == "DOCUMENTATION ONLY", "Markdown Knowledge must state documentation-only")
    _require(markdown_summary.get("json_companion") == "PRESENT", "Markdown Knowledge JSON companion should be present")
    _require(markdown_summary.get("authority") == "context, not automatic authority", "Markdown Knowledge authority note mismatch")
    _require(markdown_summary.get("badges") == MARKDOWN_KNOWLEDGE_BADGES, "Markdown Knowledge badges mismatch")
    expected_markdown_counts = _expected_markdown_summary()
    for key, expected in expected_markdown_counts.items():
        _require(markdown_summary.get(key) == expected, "Markdown Knowledge count mismatch for " + key)
    boundary = str(markdown_summary.get("safety_boundary", ""))
    for phrase in [
        "Read-only documentation visibility only.",
        "does not scan markdown",
        "rebuild the index",
        "run verifiers",
        "move files",
        "execute markdown",
        "treat markdown as authority",
    ]:
        _require(phrase in boundary, "Markdown Knowledge boundary missing phrase: " + phrase)
    for needle in [
        "Markdown Knowledge:",
        "DOCUMENTATION ONLY",
        "context, not automatic authority",
        "NO EXECUTION",
        "NO FILE MOVES",
    ]:
        _require(needle in rendered, "rendered status missing Markdown Knowledge text: " + needle)

    file_structure = status.get("file_structure")
    _require(file_structure == direct_file_structure_summary, "helper build_ai_body_status must expose Fluid File Structure summary")
    _require(isinstance(file_structure, dict), "Fluid File Structure summary must be a dict")
    _require(file_structure.get("title") == "FILE STRUCTURE", "Fluid File Structure title mismatch")
    _require(file_structure.get("badges") == FILE_STRUCTURE_BADGES, "Fluid File Structure badges mismatch")
    expected_file_structure = _expected_file_structure_summary()
    for key, expected in expected_file_structure.items():
        _require(file_structure.get(key) == expected, "Fluid File Structure field mismatch for " + key)
    structure_boundary = str(file_structure.get("safety_boundary", ""))
    for phrase in [
        "Read-only GUI visibility only.",
        "does not rebuild the structure plan",
        "scan project files",
        "run verifiers",
        "move files",
        "change imports",
        "package",
        "migration approval",
    ]:
        _require(phrase in structure_boundary, "Fluid File Structure boundary missing phrase: " + phrase)
    for needle in [
        "File Structure:",
        "PLAN ONLY",
        "Current layout: STABLE",
        "Future layout: PLANNED",
        "Migration status: NOT STARTED",
        "Next slice: NONE APPROVED",
        "Policy: JOSH-APPROVED SLICES ONLY",
        "Live imports changed: NO",
        "Files moved/renamed: NO",
        "Packaging required: NO",
        "FLUID STRUCTURE",
        "NO IMPORT MIGRATION",
        "JOSH APPROVAL REQUIRED",
    ]:
        _require(needle in rendered, "rendered status missing Fluid File Structure text: " + needle)

    code_companion = status.get("code_companion")
    _require(code_companion == direct_code_companion_summary, "helper build_ai_body_status must expose Code Companion summary")
    _require(isinstance(code_companion, dict), "Code Companion summary must be a dict")
    _require(code_companion.get("title") == "CODE COMPANION", "Code Companion title mismatch")
    _require(code_companion.get("status") == "SCRIPT CREATOR / PRODUCT TEMPLATES / PRODUCT ONLY", "Code Companion status mismatch")
    _require(code_companion.get("script_creator") == "Python / Java / HTML", "Code Companion language summary mismatch")
    _require(
        code_companion.get("product_templates") == "Python CLI, Python GUI, Java Console, HTML Dashboard, HTML Mini App",
        "Code Companion product template summary mismatch",
    )
    _require(code_companion.get("products_root") == "products\\", "Code Companion products root mismatch")
    _require(code_companion.get("examples_root") == "examples\\code_companion", "Code Companion examples root mismatch")
    _require(code_companion.get("product_preview") == "read-only", "Code Companion product preview boundary mismatch")
    _require(code_companion.get("open_folder") == "user-clicked / bounded to products\\", "Code Companion open-folder boundary mismatch")
    _require(code_companion.get("save_root") == "examples\\code_companion", "Code Companion save root mismatch")
    _require(code_companion.get("runtime_source_edits") == "BLOCKED", "Code Companion runtime source edit boundary mismatch")
    _require(code_companion.get("apply") == "NOT ENABLED", "Code Companion apply boundary mismatch")
    _require(code_companion.get("apply_to_engel") == "NOT ENABLED", "Code Companion apply-to-Engel boundary mismatch")
    _require(code_companion.get("overwrite") == "APPROVE_CHANGE required", "Code Companion overwrite gate mismatch")
    _require(code_companion.get("python_validation") == "ast / py_compile", "Code Companion Python validation mismatch")
    _require(code_companion.get("java_toolchain") == "proposal-only unless present", "Code Companion Java toolchain mismatch")
    _require(code_companion.get("html") == "local-only / no remote deps", "Code Companion HTML boundary mismatch")
    _require(code_companion.get("dependencies") == "APPROVE_INSTALL required", "Code Companion dependency approval mismatch")
    _require(code_companion.get("badges") == CODE_COMPANION_BADGES, "Code Companion badges mismatch")
    code_boundary = str(code_companion.get("safety_boundary", ""))
    for phrase in [
        "examples\\code_companion",
        "products\\",
        "Product preview is read-only",
        "Open Folder is user-clicked",
        "does not edit Engel runtime source",
        "apply to Engel",
        "run generated code",
        "execute previewed content",
        "run arbitrary shell commands",
        "call providers/network",
        "install packages without APPROVE_INSTALL",
        "overwrite products without APPROVE_CHANGE",
        "write trusted memory",
        "mutate queues/routes",
    ]:
        _require(phrase in code_boundary, "Code Companion boundary missing phrase: " + phrase)
    for needle in [
        "Code Companion:",
        "SCRIPT CREATOR / PRODUCT TEMPLATES / PRODUCT ONLY",
        "Script creator: Python / Java / HTML",
        "Product templates: Python CLI, Python GUI, Java Console, HTML Dashboard, HTML Mini App",
        "Products root: products\\",
        "Examples root: examples\\code_companion",
        "Product preview: read-only",
        "Open folder: user-clicked / bounded to products\\",
        "Runtime source edits: BLOCKED",
        "Apply to Engel: NOT ENABLED",
        "Overwrite: APPROVE_CHANGE required",
        "Python validation: ast / py_compile",
        "Java toolchain: proposal-only unless present",
        "HTML: local-only / no remote deps",
        "Dependencies: APPROVE_INSTALL required",
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
    ]:
        _require(needle in rendered, "rendered status missing Code Companion text: " + needle)

    core_v1_dashboard = status.get("core_v1_dashboard")
    _require(core_v1_dashboard == direct_core_v1_dashboard_status, "helper build_ai_body_status must expose Core V1 dashboard status")
    _require(isinstance(core_v1_dashboard, dict), "Core V1 dashboard status must be a dict")
    _require(core_v1_dashboard.get("title") == "ENGEL CORE V1 COMMAND CENTER", "Core V1 dashboard title mismatch")
    _require(core_v1_dashboard.get("badges") == CORE_V1_DASHBOARD_BADGES, "Core V1 dashboard badges mismatch")
    expected_dashboard = _expected_core_v1_dashboard_summary()
    for key, expected in expected_dashboard.items():
        _require(core_v1_dashboard.get(key) == expected, "Core V1 dashboard field mismatch for " + key)
    dashboard_boundary = str(core_v1_dashboard.get("safety_boundary", ""))
    for phrase in [
        "Compact read-only Core V1 status display only",
        "does not rebuild maps or reports from GUI",
        "write trusted memory",
        "promote memory candidates",
        "apply lessons",
        "run Browser Queen",
        "launch browsers",
        "call APIs/network",
        "install packages",
        "execute product/external code",
        "mutate queues/routes/source",
        "enable autonomy",
        "write ALIVE_STATE",
        "change authority hierarchy",
    ]:
        _require(phrase in dashboard_boundary, "Core V1 dashboard boundary missing phrase: " + phrase)
    for needle in [
        "ENGEL CORE V1 COMMAND CENTER:",
        "Core: LIVE BASELINE",
        "Authority: " + AUTHORITY,
        "Flow: Talk-to-Code \u2192 Products/Research \u2192 Lessons \u2192 Reviews \u2192 Memory Candidates",
        "Products: " + expected_dashboard["products_count"],
        "Research: "
        + expected_dashboard["research_intake_receipts_count"]
        + " receipts / "
        + expected_dashboard["research_summary_proposals_count"]
        + " summaries",
        "Lessons: "
        + expected_dashboard["lesson_candidates_count"]
        + " product / "
        + expected_dashboard["research_lesson_candidates_count"]
        + " research",
        "Reviews: "
        + expected_dashboard["lesson_reviews_count"]
        + " product / "
        + expected_dashboard["research_lesson_reviews_count"]
        + " research",
        "Memory candidates: " + expected_dashboard["memory_candidate_proposals_count"],
        "Browser Queen: DISABLED \u2192 Research Intake",
        "Trusted Memory: " + expected_dashboard["trusted_memory_status"],
        "Guards: Untrusted Content Guard ACTIVE / Prompt Injection Guard ACTIVE",
        "Status: READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
        "CORE V1",
        "READ ONLY",
        "JOSH FIRST",
        "GUARDIAN ACTIVE",
        "NO TRUSTED MEMORY WRITE",
        "BROWSER QUEEN DISABLED",
    ]:
        _require(needle in rendered, "rendered status missing Core V1 dashboard text: " + needle)

    core_continuity = status.get("core_continuity")
    _require(core_continuity == direct_core_continuity_status, "helper build_ai_body_status must expose Core Continuity status")
    _require(isinstance(core_continuity, dict), "Core Continuity status must be a dict")
    _require(core_continuity.get("title") == "ENGEL CORE CONTINUITY", "Core Continuity title mismatch")
    _require(core_continuity.get("badges") == CORE_CONTINUITY_BADGES, "Core Continuity badges mismatch")
    expected_core = _expected_core_continuity_summary()
    for key, expected in expected_core.items():
        _require(core_continuity.get(key) == expected, "Core Continuity field mismatch for " + key)
    continuity_boundary = str(core_continuity.get("safety_boundary", ""))
    for phrase in [
        "Read-only AI Body display",
        "existing Core Continuity Map",
        "does not rebuild the map",
        "write continuity JSON",
        "write trusted memory",
        "promote lessons",
        "apply lessons",
        "run Browser Queen",
        "launch browsers",
        "call APIs/network",
        "mutate queues/routes/source",
        "write ALIVE_STATE",
    ]:
        _require(phrase in continuity_boundary, "Core Continuity boundary missing phrase: " + phrase)
    for needle in [
        "ENGEL CORE CONTINUITY:",
        "Status: READ ONLY INDEX",
        "Products: " + expected_core["products"],
        "Code examples: " + expected_core["code_examples"],
        "Research reports: " + expected_core["research_reports"],
        "Lessons: " + expected_core["lesson_candidates"] + " / " + expected_core["lesson_reviews"],
        "Browser Queen: research input to Overnight Research, not separate memory",
        "Trusted memory: " + expected_core["trusted_memory"],
        "Learning status: candidates only",
        "READ ONLY INDEX",
        "NOT TRUSTED MEMORY",
        "RESEARCH SPINE",
        "JOSH FIRST",
    ]:
        _require(needle in rendered, "rendered status missing Core Continuity text: " + needle)

    browser_queen = status.get("browser_queen")
    _require(browser_queen == direct_browser_queen_summary, "helper build_ai_body_status must expose Browser Queen summary")
    _require(isinstance(browser_queen, dict), "Browser Queen status must be a dict")
    _require(browser_queen.get("badges") == BROWSER_QUEEN_BADGES, "Browser Queen badges mismatch")
    expected_browser_queen = _expected_browser_queen_summary()
    for key, expected in expected_browser_queen.items():
        _require(browser_queen.get(key) == expected, "Browser Queen field mismatch for " + key)
    browser_boundary = str(browser_queen.get("safety_boundary", ""))
    for phrase in [
        "Contract/status-only",
        "disabled",
        "Research Intake",
        "Research Office",
        "Overnight Research",
        "does not launch browsers",
        "navigate pages",
        "install browser dependencies",
        "call APIs/network",
        "run automation",
        "scrape credentials",
        "reuse browser profiles",
        "write trusted memory",
        "mutate queues/routes/source",
        "enable autonomy",
        "write ALIVE_STATE",
    ]:
        _require(phrase in browser_boundary, "Browser Queen boundary missing phrase: " + phrase)
    for needle in [
        "BROWSER QUEEN:",
        "Status: DISABLED",
        "Mode: VISIBLE_BROWSER_ONLY_FUTURE",
        "API: BLOCKED",
        "Research path: Research Intake \u2192 Overnight Research",
        "Page content: untrusted",
        "Action receipts: REQUIRED",
        "Trusted memory: BLOCKED",
        "DISABLED",
        "NO API",
        "VISIBLE ONLY FUTURE",
        "RESEARCH INPUT",
        "UNTRUSTED PAGES",
    ]:
        _require(needle in rendered, "rendered status missing Browser Queen text: " + needle)

    cards = status.get("organ_cards")
    _require(isinstance(cards, list), "helper organ_cards must be a list")
    by_name: dict[str, dict[str, object]] = {}
    for card in cards:
        _require(isinstance(card, dict), "helper organ card must be a dict")
        name = str(card.get("name", ""))
        _require(name not in by_name, "duplicate organ card: " + name)
        by_name[name] = card

    for organ, expected_indicators in REQUIRED_HEALTH_INDICATORS.items():
        _require(organ in by_name, "helper missing organ card: " + organ)
        card = by_name[organ]
        indicators = card.get("health_indicators")
        _require(isinstance(indicators, list), organ + " health_indicators must be a list")
        _require(indicators == expected_indicators, organ + " health_indicators mismatch")
        rendered_health = " | ".join(str(item) for item in indicators)
        _require(rendered_health in rendered, "rendered status missing health indicators for " + organ)

        status_text = str(card.get("status", ""))
        safety_text = str(card.get("safety_boundary", ""))
        health_text = " ".join(str(item) for item in indicators)
        fake_live_text = (status_text + " " + safety_text + " " + health_text).upper()
        for term in LIVE_VERIFIER_PASS_TERMS:
            _require(term not in fake_live_text, organ + " claims fake live verifier health: " + term)

    verifier_indicators = by_name["VERIFIERS"].get("health_indicators", [])
    _require("VERIFY TO CONFIRM" in verifier_indicators, "VERIFIERS must say VERIFY TO CONFIRM")


def check_gui_sources() -> None:
    companion = _read(COMPANION)
    super_swarm = _read(SUPER_SWARM)
    for source, label, start_marker, end_marker in [
        (
            companion,
            "Companion",
            "ENGEL_AI_BODY_COMPANION_PANEL_START",
            "ENGEL_AI_BODY_COMPANION_PANEL_END",
        ),
        (
            super_swarm,
            "Super Swarm",
            "ENGEL_AI_BODY_SUPER_SWARM_PANEL_START",
            "ENGEL_AI_BODY_SUPER_SWARM_PANEL_END",
        ),
    ]:
        _compile(COMPANION if label == "Companion" else SUPER_SWARM)
        _require("ENGEL AI BODY" in source, label + " missing ENGEL AI BODY")
        _require("AI Body" in source, label + " missing AI Body tab text")
        panel = _between(source, start_marker, end_marker)
        for organ in ORGANS:
            _require(organ in panel or "organ_cards" in panel, label + " body panel missing organ source path: " + organ)
        for needle in [
            "JOSH FIRST",
            "GUARDIAN SECOND",
            "LOCAL ONLY",
            "NO AUTONOMY",
            "NO MODEL COMMANDS",
            "VERIFY TO CONFIRM",
            AUTHORITY,
            "workflow",
            "organ_cards",
            "health_badges",
            "health_indicators",
            "MARKDOWN KNOWLEDGE",
            "DOCUMENTATION ONLY",
            "FLUID MAP",
            "NOT AUTOMATIC AUTHORITY",
            "NO EXECUTION",
            "NO FILE MOVES",
            "context, not automatic authority",
            "FILE STRUCTURE",
            "PLAN ONLY",
            "FLUID STRUCTURE",
            "NO IMPORT MIGRATION",
            "JOSH APPROVAL REQUIRED",
            "file_structure",
            "CODE COMPANION",
            "SCRIPT CREATOR",
            "PRODUCT TEMPLATES",
            "PY / JAVA / HTML",
            "PRODUCT ONLY",
            "NOT RUNTIME",
            "SOURCE EDITS BLOCKED",
            "APPROVAL GATED",
            "products",
            "examples",
            "code_companion",
            "Runtime source edits:",
            "Apply to Engel:",
            "Overwrite:",
            "Python validation:",
            "Java toolchain:",
            "HTML:",
            "APPROVE_INSTALL required",
            "ENGEL CORE V1 COMMAND CENTER",
            "CORE V1",
            "READ ONLY",
            "JOSH FIRST",
            "GUARDIAN ACTIVE",
            "NO TRUSTED MEMORY WRITE",
            "BROWSER QUEEN DISABLED",
            "Core:",
            "Memory candidates:",
            "Trusted Memory:",
            "Untrusted Content Guard",
            "Prompt Injection Guard",
            "ENGEL CORE CONTINUITY",
            "READ ONLY INDEX",
            "NOT TRUSTED MEMORY",
            "RESEARCH SPINE",
            "research input to Overnight Research, not separate memory",
            "Trusted memory:",
            "BROWSER QUEEN",
            "DISABLED",
            "NO API",
            "VISIBLE ONLY FUTURE",
            "RESEARCH INPUT",
            "UNTRUSTED PAGES",
            "Research Intake",
            "Overnight Research",
            "Page text:",
            "Receipts:",
            "Status:",
            "Current layout:",
            "Future layout:",
            "Migration status:",
            "Next slice:",
            "Live imports changed:",
            "Files moved/renamed:",
            "Packaging required:",
        ]:
            _require(needle in source or needle in panel, label + " missing required body text: " + needle)
        for forbidden in [
            "handle_human_command_mode_cli",
            "subprocess",
            "os.system",
            "Popen",
            "Start-Process",
            "shell=True",
            "write_proceed_receipt",
            "APPROVE_REPORT",
            ".write_text",
            ".write(",
            "unlink(",
            "remove(",
            "route mutation",
            "queue mutation",
            "trusted-memory writeback",
            "build_engel_core_continuity_map",
        ]:
            _require(forbidden not in panel, label + " AI Body panel contains forbidden operation: " + forbidden)
        _require("verify_" not in panel.lower(), label + " AI Body panel must not run verifiers automatically")
        for term in LIVE_VERIFIER_PASS_TERMS:
            _require(term not in panel.upper(), label + " AI Body panel claims fake live verifier health: " + term)


def check_route_optional_absent_or_documented() -> None:
    app_route_added = "ai body status" in (_read(ROOT / "engel_app.py").lower())
    if not app_route_added:
        return
    routes = _read(ROUTES).lower()
    commands = _read(COMMANDS).lower()
    _require("ai body status" in routes, "ai body status route missing route metadata")
    _require("read_only" in routes or "read-only" in routes, "ai body status route metadata missing read-only")
    _require("no_write" in routes or "no-write" in routes, "ai body status route metadata missing no-write")
    _require("ai body status" in commands, "ai body status route missing command docs")


def main() -> int:
    checks = [
        ("helper_static_read_only", check_helper_static),
        ("helper_behavior_body_status", check_helper_behavior),
        ("gui_sources_ai_body_panel", check_gui_sources),
        ("optional_route_absent_or_documented", check_route_optional_absent_or_documented),
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
        print("ENGEL_AI_BODY_STATUS_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_AI_BODY_STATUS_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
