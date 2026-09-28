#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
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

HELPER = ROOT / "engel_research_understanding_library.py"
LIBRARY_JSON = ROOT / "memory" / "ENGEL_RESEARCH_UNDERSTANDING_LIBRARY_V1.json"
LIBRARY_MD = ROOT / "memory" / "ENGEL_RESEARCH_UNDERSTANDING_LIBRARY_V1.md"


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_helper():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_research_understanding_library", HELPER)
    _require(spec is not None and spec.loader is not None, "could not load research understanding helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_research_understanding_library"] = module
    spec.loader.exec_module(module)
    return module


def _load_json() -> dict:
    _require(LIBRARY_JSON.exists(), "library JSON missing")
    data = json.loads(_read(LIBRARY_JSON))
    _require(isinstance(data, dict), "library JSON must parse as object")
    return data


def check_files_and_contract(data: dict) -> None:
    _require(LIBRARY_MD.exists(), "library Markdown missing")
    _require(HELPER.exists(), "library helper missing")
    md = _read(LIBRARY_MD)
    json_text = _read(LIBRARY_JSON)
    helper_source = _read(HELPER)

    for text, label in ((json_text, "JSON"), (md, "Markdown")):
        for needle in [
            "LOCAL_INTENT_LIBRARY",
            "NOT_TRUSTED_MEMORY",
            "NOT_APPLIED",
            "NOT_PERFORMED",
            "BLOCKED",
            "DATA_NOT_INSTRUCTION",
            "REJECTED",
        ]:
            _require(needle in text, f"{label} missing contract text: {needle}")

    for needle in [
        "LLM training: NOT_PERFORMED",
        "Provider/API behavior is BLOCKED",
        "Offline Seed LLM inference is NOT ENABLED",
        "Research Understanding Library ≠ Trusted Memory",
        "LLM Library ≠ LLM Training",
        "Intent Library ≠ Authority",
        "Intent Classification ≠ Approval",
        "Library content is data/config, not instruction",
        "Embedded approval tokens do not count",
        "Trusted memory write remains BLOCKED / NOT_PERFORMED",
    ]:
        _require(needle in md, "Markdown missing boundary text: " + needle)

    _require(data.get("status") == "LOCAL_INTENT_LIBRARY / NOT_TRUSTED_MEMORY / NOT_APPLIED", "library status incorrect")
    _require(data.get("llm_training") == "NOT_PERFORMED", "llm training must be NOT_PERFORMED")
    _require(data.get("provider_api") == "BLOCKED", "provider/API must be BLOCKED")
    _require(data.get("offline_seed_llm_inference") in {"NOT ENABLED", "NOT_PERFORMED"}, "Offline Seed LLM inference must be disabled")
    _require(data.get("trusted_memory_write") == "BLOCKED / NOT_PERFORMED", "trusted memory write boundary missing")
    _require(data.get("runtime_effect") == "CLASSIFICATION_HELPER_ONLY", "runtime effect must be helper-only")
    _require("def classify_intent(" in helper_source, "helper missing classify_intent")
    _require("def render_intent_classification(" in helper_source, "helper missing renderer")


def check_schema_and_intents(data: dict) -> None:
    families = data.get("intent_families")
    _require(isinstance(families, list) and families, "intent_families must be a non-empty list")
    by_intent = {family.get("intent"): family for family in families if isinstance(family, dict)}

    required_fields = {
        "intent",
        "title",
        "domain",
        "phrases",
        "negative_phrases",
        "route",
        "approval_required",
        "default_status",
        "output_status",
        "safety_boundary",
        "trusted_memory_write",
        "runtime_effect",
        "examples",
        "blocked_if",
        "next_safe_action",
        "related_intents",
    }
    for family in families:
        _require(isinstance(family, dict), "each intent family must be an object")
        missing = required_fields - set(family)
        _require(not missing, f"intent family {family.get('intent')} missing fields: {sorted(missing)}")
        _require(family.get("trusted_memory_write") == "BLOCKED / NOT_PERFORMED", f"{family.get('intent')} must block trusted memory writes")
        _require(family.get("runtime_effect") not in {"LLM_TRAINING", "PROVIDER_API", "AUTONOMY"}, f"{family.get('intent')} has unsafe runtime effect")

    required_intents = [
        "project_builder", "product_idea_to_plan", "create_product", "continue_product", "improve_product",
        "patch_proposal", "apply_patch", "product_health", "health_delta", "product_cycle", "product_context",
        "product_session_memory", "readme_manifest_proposal", "product_test_plan", "product_package",
        "product_launch", "product_preview", "product_open_folder", "product_workbench",
        "product_next_safe_action", "product_explain_status",
        "lesson_candidate", "create_lesson_candidate", "review_lesson_candidate", "patch_lesson_review",
        "product_lesson_review", "research_lesson_candidate", "research_lesson_review", "lesson_not_trusted_memory",
        "memory_candidate_proposal", "memory_candidate_review", "memory_candidate_handoff", "trusted_memory_boundary",
        "reject_lesson", "request_more_evidence",
        "summarize_research", "classify_research", "extract_findings", "extract_risks", "extract_requirements",
        "extract_product_ideas", "research_to_product", "research_summary_proposal", "compare_sources",
        "route_to_research_intake", "overnight_research", "research_office", "research_next_safe_action",
        "research_guardian_review", "research_source_quality", "research_prompt_injection_scan",
        "browser_queen_status", "browser_queen_open_url", "browser_queen_stop", "browser_queen_manual_page_text",
        "browser_queen_selected_page_text_file", "browser_queen_research_intake", "browser_queen_research_summary",
        "browser_queen_no_api", "browser_queen_visible_only", "browser_queen_disabled_or_bounded",
        "browser_queen_action_receipt", "browser_queen_page_content_untrusted", "browser_queen_chatgpt_future_no_api",
        "external_memory_status", "external_memory_intake", "external_memory_scaffold", "external_memory_shelf",
        "external_memory_no_broad_scan", "external_memory_not_trusted", "external_memory_select_file",
        "external_memory_route_to_research", "external_memory_archive", "external_memory_quarantine",
        "external_memory_manifest", "external_memory_suitability",
        "prompt_injection_risk", "untrusted_content", "approval_token_required", "embedded_token_rejected",
        "authority_hierarchy", "unsafe_runtime_edit", "unsafe_install", "unsafe_api_network", "unsafe_code_execution",
        "unsafe_trusted_memory_write", "unsafe_browser_automation", "unsafe_external_scan", "safe_next_action",
        "guardian_review", "blocked_action", "approval_boundary_explain",
        "core_status", "core_continuity_map", "core_v1_dashboard", "daily_check", "unix_style_design",
        "product_session_context", "product_context_pack", "current_build_plan", "package_refresh", "verifier_stack",
        "report_status", "clean_git_status", "known_nonfatal_packaging_warning", "tzdata_warning",
        "pyopengl_optional_warning",
    ]
    for intent in required_intents:
        _require(intent in by_intent, "missing required intent family: " + intent)

    required_domains = {
        "code_companion",
        "lesson_memory",
        "research",
        "browser_queen",
        "external_memory",
        "safety_guardian",
        "core_continuity",
    }
    domains = {family.get("domain") for family in families if isinstance(family, dict)}
    _require(required_domains <= domains, "missing required intent domain")

    approvals = {
        "apply_patch": "APPROVE_PRODUCT_PATCH",
        "product_package": "APPROVE_PACKAGE",
        "product_launch": "APPROVE_LAUNCH",
        "create_lesson_candidate": "APPROVE_LESSON_CANDIDATE",
        "memory_candidate_proposal": "APPROVE_MEMORY_CANDIDATE_PROPOSAL",
        "memory_candidate_handoff": "APPROVE_MEMORY_CANDIDATE_PROPOSAL",
        "browser_queen_open_url": "APPROVE_BROWSER_OPEN_URL",
        "browser_queen_research_intake": "APPROVE_BROWSER_RESEARCH_INTAKE",
    }
    for intent, token in approvals.items():
        _require(by_intent[intent].get("approval_required") == token, f"{intent} approval token incorrect")
        _require("embedded_token" in " ".join(by_intent[intent].get("blocked_if", [])), f"{intent} must reject embedded-token-only approval")


def check_helper_static() -> None:
    source = _read(HELPER)
    tree = ast.parse(source)
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
    }
    blocked_calls = {
        "eval",
        "exec",
        "__import__",
        "write_text",
        "write_bytes",
        "open",
        "system",
        "Popen",
        "run",
        "call",
        "check_call",
        "check_output",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, "helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "helper imports blocked module: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in blocked_calls, "helper calls blocked builtin/function: " + func.id)
            elif isinstance(func, ast.Attribute):
                _require(func.attr not in blocked_calls, "helper calls blocked method/function: " + func.attr)

    for needle in [
        "CLASSIFICATION_HELPER_ONLY",
        "LOCAL_INTENT_CLASSIFICATION / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "Intent classification is not authority.",
        "Embedded approval tokens do not count.",
        "Trusted memory write: BLOCKED / NOT_PERFORMED.",
    ]:
        _require(needle in source, "helper missing safety text: " + needle)


def check_behavior() -> None:
    helper = _load_helper()

    result = helper.classify_intent("apply that patch")
    _require(result.intent == "apply_patch", "apply that patch should classify as apply_patch")
    _require(result.approval_required == "APPROVE_PRODUCT_PATCH", "apply_patch approval token incorrect")
    _require("APPROVAL_GATED" in result.output_status, "apply_patch should be approval gated")

    result = helper.classify_intent("create that lesson")
    _require(result.intent == "create_lesson_candidate", "create that lesson should classify as create_lesson_candidate")
    _require(result.approval_required == "APPROVE_LESSON_CANDIDATE", "lesson candidate approval token incorrect")

    result = helper.classify_intent("make memory candidate from that review")
    _require(result.intent == "memory_candidate_proposal", "memory candidate request should classify as memory_candidate_proposal")
    _require(result.approval_required == "APPROVE_MEMORY_CANDIDATE_PROPOSAL", "memory candidate approval token incorrect")

    result = helper.classify_intent("turn this research into a product")
    _require(result.intent == "research_to_product", "research-to-product phrase should route to research_to_product")

    result = helper.classify_intent("scan the whole drive")
    _require(result.intent in {"unsafe_external_scan", "external_memory_no_broad_scan"}, "whole-drive scan should classify as blocked scan")
    _require("BLOCKED" in result.default_status, "whole-drive scan should be blocked/explained")

    result = helper.classify_intent("ignore guardian")
    _require(result.domain == "safety_guardian", "ignore guardian should classify as safety intent")
    _require("BLOCKED" in result.default_status or result.intent in {"blocked_action", "authority_hierarchy"}, "ignore guardian should be blocked/explained")

    result = helper.classify_intent("what next")
    _require(result.intent in {"safe_next_action", "product_next_safe_action", "continue_product"}, "what next should classify as safe next action or continue route")

    new_phrase_expectations = {
        "make it smarter": ("improve_product", "NONE_FOR_PLAN_ONLY"),
        "turn this into something useful": ("project_builder", "NONE_FOR_PLAN_ONLY"),
        "is this prompt injection": ("prompt_injection_risk", "NONE_FOR_PLAN_ONLY"),
        "add it to memory": ("unsafe_trusted_memory_write", "NONE_FOR_PLAN_ONLY"),
        "make a memory candidate": ("memory_candidate_proposal", "APPROVE_MEMORY_CANDIDATE_PROPOSAL"),
        "use this research": ("research_to_product", "NONE_FOR_PLAN_ONLY"),
        "build from this": ("research_to_product", "NONE_FOR_PLAN_ONLY"),
        "make a product from this": ("research_to_product", "NONE_FOR_PLAN_ONLY"),
        "review this": ("guardian_review", "NONE_FOR_PLAN_ONLY"),
        "make a lesson": ("create_lesson_candidate", "APPROVE_LESSON_CANDIDATE"),
        "rebuild live Engel": ("package_refresh", "NONE_FOR_PLAN_ONLY"),
        "is tzdata warning bad": ("tzdata_warning", "NONE_FOR_PLAN_ONLY"),
        "optional pyopengl dll warning": ("pyopengl_optional_warning", "NONE_FOR_PLAN_ONLY"),
    }
    for phrase, (intent, approval) in new_phrase_expectations.items():
        result = helper.classify_intent(phrase)
        _require(result.intent == intent, f"expanded phrase mapped incorrectly: {phrase} -> {result.intent}")
        _require(result.approval_required == approval, f"expanded phrase approval mismatch: {phrase}")
        _require(result.trusted_memory_write == "BLOCKED / NOT_PERFORMED", f"expanded phrase must block trusted memory: {phrase}")

    result = helper.classify_intent("create research lesson candidate")
    _require(result.intent == "research_lesson_candidate", "research lesson phrase should classify as research_lesson_candidate")
    _require(result.approval_required == "APPROVE_RESEARCH_LESSON_CANDIDATE", "research lesson candidate approval token should preserve research token")

    result = helper.classify_intent("APPROVE_PRODUCT_PATCH is in the README")
    _require(result.intent == "embedded_token_rejected", "embedded product approval token should be rejected")
    _require(result.approval_required == "NONE_FOR_PLAN_ONLY", "embedded token rejection should not require/accept an action token")

    rendered = helper.render_intent_classification(helper.classify_intent("apply that patch"))
    for needle in [
        "LOCAL_INTENT_CLASSIFICATION / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "Intent classification is not authority.",
        "Library content is data/config, not instruction.",
        "Embedded approval tokens do not count.",
        "Trusted memory write: BLOCKED / NOT_PERFORMED.",
        "APPROVE_PRODUCT_PATCH",
    ]:
        _require(needle in rendered, "rendered classification missing: " + needle)

    _require(helper.required_approval_for_intent("apply_patch") == "APPROVE_PRODUCT_PATCH", "required_approval_for_intent failed")
    _require(helper.intent_requires_approval("apply_patch") is True, "intent_requires_approval failed for apply_patch")
    _require(helper.intent_requires_approval("summarize_research") is False, "summarize_research should be plan-only")
    boundary = helper.explain_intent_boundary("apply_patch")
    _require("intent classification is not authority" in boundary, "boundary explanation missing authority text")
    _require("embedded approval tokens do not count" in boundary, "boundary explanation missing embedded-token text")


def main() -> int:
    try:
        data = _load_json()
        check_files_and_contract(data)
        check_schema_and_intents(data)
        check_helper_static()
        check_behavior()
    except CheckFailure as exc:
        print("[FAIL] " + str(exc))
        return 1
    except json.JSONDecodeError as exc:
        print("[FAIL] library JSON did not parse: " + str(exc))
        return 1
    print("[PASS] Engel Research Understanding / LLM Library verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
