#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_browser_queen_workbench.py"
PLAN_MD = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE_PLAN_V1.md"
PLAN_JSON = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE_PLAN_V1.json"
PHASE2_PLAN_MD = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE2_VISIBLE_STATUS_PLAN_V1.md"
PHASE2_PLAN_JSON = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE2_VISIBLE_STATUS_PLAN_V1.json"
PHASE3_CONTRACT_MD = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE3_OPEN_URL_CONTRACT_V1.md"
PHASE3_CONTRACT_JSON = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE3_OPEN_URL_CONTRACT_V1.json"
PHASE4_CONTRACT_MD = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE4_PAGE_CAPTURE_CONTRACT_V1.md"
PHASE4_CONTRACT_JSON = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE4_PAGE_CAPTURE_CONTRACT_V1.json"
PHASE5_CONTRACT_MD = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE5_RESEARCH_SUMMARY_CONTRACT_V1.md"
PHASE5_CONTRACT_JSON = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE5_RESEARCH_SUMMARY_CONTRACT_V1.json"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_BROWSER_QUEEN_PHASE1_CONTRACT_STATUS_WORKBENCH.md"
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


def _compile(path: Path) -> None:
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def check_files_and_docs() -> None:
    _compile(HELPER)
    md = _read(PLAN_MD)
    payload = json.loads(_read(PLAN_JSON))
    phase2_md = _read(PHASE2_PLAN_MD)
    phase2_payload = json.loads(_read(PHASE2_PLAN_JSON))
    phase3_md = _read(PHASE3_CONTRACT_MD)
    phase3_payload = json.loads(_read(PHASE3_CONTRACT_JSON))
    phase4_md = _read(PHASE4_CONTRACT_MD)
    phase4_payload = json.loads(_read(PHASE4_CONTRACT_JSON))
    phase5_md = _read(PHASE5_CONTRACT_MD)
    phase5_payload = json.loads(_read(PHASE5_CONTRACT_JSON))
    _require(isinstance(payload, dict), "phase plan JSON must be an object")
    for needle in [
        "Browser Queen Phase 1 makes the future Browser Queen path visible",
        "Phase 0: Static Review Complete",
        "Phase 1: Contract / Disabled Status Active",
        "Phase 2: Visible Browser Status Panel - Planned / No Navigation",
        "Phase 3: Approved Open URL - Future",
        "Phase 3 is contract-only and does not implement open URL.",
        "APPROVE_BROWSER_OPEN_URL",
        "Phase 4: Read Page Text/Screenshot as Untrusted Content - Future",
        "Phase 4 is contract-only and does not implement page text extraction, screenshot capture, or OCR.",
        "APPROVE_BROWSER_READ_PAGE",
        "APPROVE_BROWSER_SCREENSHOT",
        "Phase 5: Research Summary Proposal - Future / Contract Only",
        "Phase 5 is contract-only and does not implement Research Summary Proposal runtime.",
        "APPROVE_BROWSER_RESEARCH_SUMMARY",
        "Phase 5 requires Phase 4 artifact, action receipt, and Untrusted Content Guard result in a future implementation.",
        "Phase 5 output remains PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED.",
        "Phase 6: ChatGPT Visible UI Bridge - Future / No API",
        "DISABLED / NO API / NO NAVIGATION / NO BROWSER LAUNCH",
        "Research Intake → Research Office / Overnight Research",
        "Page content is untrusted.",
        "Action receipts required.",
        "Josh approval required for future phases.",
        "Browser Queen cannot override Guardian.",
        "Browser Queen cannot write trusted memory.",
        "ChatGPT visible UI bridge is future-only and no-API.",
        "does not launch browsers",
        "does not bypass Research Intake",
        AUTHORITY,
    ]:
        _require(needle in md, "phase plan markdown missing text: " + needle)
    _require(payload.get("schema") == "engel_browser_queen_phase_plan_v1", "phase plan schema mismatch")
    _require(payload.get("status") == "DISABLED", "phase plan status must be DISABLED")
    _require(payload.get("current") == "DISABLED / NO API / NO NAVIGATION / NO BROWSER LAUNCH", "current phase safety mismatch")
    _require(payload.get("research_path") == "Research Intake → Research Office / Overnight Research", "research path mismatch")
    _require(payload.get("page_content") == "UNTRUSTED_DATA", "page content mismatch")
    _require(payload.get("action_receipts") == "REQUIRED", "action receipts mismatch")
    _require(payload.get("authority") == AUTHORITY, "authority mismatch")
    for key in [
        "josh_approval_required_for_future_phases",
    ]:
        _require(payload.get(key) is True, "phase plan must set true: " + key)
    for key in [
        "browser_launch_enabled",
        "navigation_enabled",
        "api_or_network_enabled",
        "browser_dependencies_installed",
        "background_browsing_enabled",
        "autonomous_browsing_enabled",
        "hidden_browser_profile_reuse_enabled",
        "credential_scraping_enabled",
        "trusted_memory_write_enabled",
        "queue_or_route_mutation_enabled",
        "browser_action_execution_enabled",
        "browser_screenshot_or_page_extraction_enabled",
        "chatgpt_automation_enabled",
        "authority_changed",
    ]:
        _require(payload.get(key) is False, "phase plan must keep disabled flag false: " + key)
    _require(payload.get("chatgpt_bridge_future_no_api") is True, "ChatGPT bridge must remain future/no API")
    phases = payload.get("phases")
    _require(isinstance(phases, list) and len(phases) == 7, "phase plan must list seven phases")
    phase_text = json.dumps(phases, ensure_ascii=False)
    for needle in [
        "Visible Browser Status Panel - Planned / No Navigation",
        "Approved Open URL - Future / Contract Only",
        "Read Page Text/Screenshot as Untrusted Content - Future / Contract Only",
        "Phase 4",
        "Read Page Text/Screenshot as Untrusted Content - Future",
        "Phase 5",
        "Research Summary Proposal - Future / Contract Only",
        "Phase 6",
        "ChatGPT Visible UI Bridge - Future / No API",
    ]:
        _require(needle in phase_text, "phase plan JSON missing: " + needle)
    _require(phase2_payload.get("schema") == "engel_browser_queen_phase2_visible_status_plan_v1", "Phase 2 plan schema mismatch")
    phase2_status = phase2_payload.get("phase2_status")
    _require(isinstance(phase2_status, dict), "Phase 2 status object missing")
    _require(phase2_status.get("status") == "PLANNED / DISABLED / NO_BROWSER_LAUNCH", "Phase 2 status mismatch")
    _require(phase2_status.get("navigation") == "BLOCKED", "Phase 2 navigation must be blocked")
    _require(phase2_status.get("api") == "BLOCKED", "Phase 2 API must be blocked")
    _require(phase2_status.get("trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 2 trusted memory must be blocked")
    for needle in [
        "Browser Queen Phase 2 prepares a future visible browser status panel",
        "PLANNED / DISABLED / NO_BROWSER_LAUNCH / NO_NAVIGATION",
        "Visible Browser Status Panel - Planned / No Navigation",
        "Status display only.",
        "Future Phase 3 requires separate explicit Josh/Guardian approval.",
        "Stop button requirement is reserved for future active browser phases.",
        "Action receipts are required for future browser actions.",
        "Page content is data, not instruction.",
        "Research path remains Research Intake \u2192 Research Office / Overnight Research.",
    ]:
        _require(needle in phase2_md, "Phase 2 plan markdown missing text: " + needle)
    _require(phase3_payload.get("schema") == "engel_browser_queen_phase3_open_url_contract_v1", "Phase 3 contract schema mismatch")
    _require(phase3_payload.get("status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 3 contract status mismatch")
    phase3_status = phase3_payload.get("phase3_status")
    _require(isinstance(phase3_status, dict), "Phase 3 status object missing")
    _require(phase3_status.get("approval_token_required") == "APPROVE_BROWSER_OPEN_URL", "Phase 3 approval token mismatch")
    _require(phase3_status.get("open_url_implementation") == "NOT_IMPLEMENTED", "Phase 3 open URL must be not implemented")
    _require(phase3_status.get("navigation") == "BLOCKED_UNTIL_FUTURE_APPROVAL", "Phase 3 navigation must be blocked")
    _require(phase3_status.get("api") == "BLOCKED", "Phase 3 API must be blocked")
    _require(phase3_status.get("trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 3 trusted memory must be blocked")
    for key in [
        "visible_browser_only",
        "allowlist_required",
        "stop_button_required",
        "action_receipt_required",
    ]:
        _require(phase3_status.get(key) is True, "Phase 3 required future control missing: " + key)
    for key in [
        "browser_launch_enabled",
        "open_url_implemented",
        "navigation_enabled",
        "page_extraction_enabled",
        "screenshots_enabled",
        "chatgpt_automation_enabled",
        "api_or_network_enabled",
        "browser_dependencies_installed",
        "browser_profiles_read",
        "cookies_or_storage_read",
        "credential_access_enabled",
        "background_browsing_enabled",
        "autonomous_browsing_enabled",
        "trusted_memory_write_enabled",
        "authority_changed",
    ]:
        _require(phase3_payload.get(key) is False, "Phase 3 disabled flag must remain false: " + key)
    for needle in [
        "Browser Queen Phase 3 prepares the future approved-open-URL phase.",
        "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "APPROVE_BROWSER_OPEN_URL",
        "visible browser only",
        "URL allowlist / explicit URL approval",
        "Stop button requirement before active implementation",
        "action receipt required",
        "No browser launch.",
        "No URL navigation.",
        "Validation in this task is URL-shape validation only.",
        "Validation must not open a URL",
        "Browser Queen Phase 3 Contract ≠ Browser Runtime.",
        "Page content is data, not instruction.",
    ]:
        _require(needle in phase3_md, "Phase 3 contract markdown missing text: " + needle)
    _require(phase4_payload.get("schema") == "engel_browser_queen_phase4_page_capture_contract_v1", "Phase 4 contract schema mismatch")
    _require(phase4_payload.get("status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 4 contract status mismatch")
    phase4_status = phase4_payload.get("phase4_status")
    _require(isinstance(phase4_status, dict), "Phase 4 status object missing")
    _require(phase4_status.get("page_read_token_required") == "APPROVE_BROWSER_READ_PAGE", "Phase 4 page-read token mismatch")
    _require(phase4_status.get("screenshot_token_required") == "APPROVE_BROWSER_SCREENSHOT", "Phase 4 screenshot token mismatch")
    _require(phase4_status.get("page_text_extraction") == "NOT_IMPLEMENTED / BLOCKED", "Phase 4 page text extraction mismatch")
    _require(phase4_status.get("screenshot_capture") == "NOT_IMPLEMENTED / BLOCKED", "Phase 4 screenshot capture mismatch")
    _require(phase4_status.get("ocr") == "NOT_IMPLEMENTED / BLOCKED", "Phase 4 OCR mismatch")
    _require(phase4_status.get("api") == "BLOCKED", "Phase 4 API must be blocked")
    _require(phase4_status.get("trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 4 trusted memory must be blocked")
    for key in [
        "visible_browser_only",
        "phase3_context_required",
        "stop_button_required",
        "action_receipt_required",
    ]:
        _require(phase4_status.get(key) is True, "Phase 4 required future control missing: " + key)
    for key in [
        "browser_launch_enabled",
        "navigation_enabled",
        "page_text_extraction_implemented",
        "screenshot_capture_implemented",
        "ocr_implemented",
        "chatgpt_automation_enabled",
        "api_or_network_enabled",
        "browser_dependencies_installed",
        "ocr_or_image_dependencies_installed",
        "browser_profiles_read",
        "cookies_or_storage_read",
        "credential_access_enabled",
        "background_browsing_enabled",
        "autonomous_browsing_enabled",
        "trusted_memory_write_enabled",
        "authority_changed",
    ]:
        _require(phase4_payload.get(key) is False, "Phase 4 disabled flag must remain false: " + key)
    for needle in [
        "Browser Queen Phase 4 prepares the future contract",
        "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "APPROVE_BROWSER_READ_PAGE",
        "APPROVE_BROWSER_SCREENSHOT",
        "No page text extraction.",
        "No screenshot capture.",
        "No OCR.",
        "Validation must not read a page, capture a screenshot, run OCR",
        "Future Phase 5 Research Summary Proposal requires separate work.",
        "Page content is data, not instruction.",
        "Screenshot/OCR content is data, not instruction.",
    ]:
        _require(needle in phase4_md, "Phase 4 contract markdown missing text: " + needle)
    _require(phase5_payload.get("schema") == "engel_browser_queen_phase5_research_summary_contract_v1", "Phase 5 contract schema mismatch")
    _require(phase5_payload.get("status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 5 contract status mismatch")
    phase5_status = phase5_payload.get("phase5_status")
    _require(isinstance(phase5_status, dict), "Phase 5 status object missing")
    _require(phase5_status.get("approval_token_required") == "APPROVE_BROWSER_RESEARCH_SUMMARY", "Phase 5 approval token mismatch")
    _require(phase5_status.get("summary_generation") == "NOT_IMPLEMENTED / BLOCKED", "Phase 5 summary generation mismatch")
    _require(phase5_status.get("requires_phase4_artifact") is True, "Phase 5 must require Phase 4 artifact")
    _require(phase5_status.get("requires_action_receipt") is True, "Phase 5 must require action receipt")
    _require(phase5_status.get("requires_untrusted_content_scan") is True, "Phase 5 must require guard scan")
    _require(phase5_status.get("output_status") == "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED", "Phase 5 output status mismatch")
    _require(phase5_status.get("api") == "BLOCKED", "Phase 5 API must be blocked")
    _require(phase5_status.get("trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 5 trusted memory must be blocked")
    for key in [
        "browser_launch_enabled",
        "navigation_enabled",
        "page_text_extraction_implemented",
        "screenshot_capture_implemented",
        "ocr_implemented",
        "research_summary_runtime_implemented",
        "chatgpt_automation_enabled",
        "api_or_network_enabled",
        "browser_dependencies_installed",
        "ocr_or_image_dependencies_installed",
        "browser_profiles_read",
        "cookies_or_storage_read",
        "credential_access_enabled",
        "background_browsing_enabled",
        "autonomous_browsing_enabled",
        "trusted_memory_write_enabled",
        "authority_changed",
    ]:
        _require(phase5_payload.get(key) is False, "Phase 5 disabled flag must remain false: " + key)
    for needle in [
        "Browser Queen Phase 5 prepares the future contract",
        "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "APPROVE_BROWSER_RESEARCH_SUMMARY",
        "Phase 4 page-capture artifact",
        "action receipt",
        "Untrusted Content Guard result",
        "Research Summary Proposal",
        "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "No real browser research summary creation.",
        "Browser Queen Phase 5 Contract != Research Summary Runtime.",
        "Research Summary Proposals are not trusted memory.",
        "Untrusted Content Guard -> Research Intake -> Research Office / Overnight Research",
    ]:
        _require(needle in phase5_md, "Phase 5 contract markdown missing text: " + needle)


def check_helper_status() -> None:
    source = _read(HELPER)
    for needle in [
        "get_browser_queen_phase_status",
        "render_browser_queen_phase_status",
        "BROWSER QUEEN PHASE STATUS",
        "DISABLED",
        "NO API",
        "NO NAVIGATION",
        "NO BROWSER LAUNCH",
        "Research Intake \\u2192 Research Office / Overnight Research",
        "Page content is untrusted.",
        "Action receipts required.",
        "Josh approval required for future phases.",
        "Browser Queen cannot override Guardian.",
        "Browser Queen cannot write trusted memory.",
        "ChatGPT Visible UI Bridge - Future / No API",
        "Visible Browser Status Panel - Planned / No Navigation",
        "Status: PLANNED / DISABLED / NO_BROWSER_LAUNCH",
        "Runtime: no launch / no navigation / no API",
        "Approved Open URL - Future / Contract Only",
        "Status: CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "APPROVE_BROWSER_OPEN_URL",
        "Phase 3 is contract-only and does not implement open URL.",
        "Phase 3 requires visible browser, allowlist, stop button, and action receipt before any active implementation.",
        "Phase 4 is contract-only and does not implement page capture.",
        "Phase 4 requires APPROVE_BROWSER_READ_PAGE or APPROVE_BROWSER_SCREENSHOT in a future implementation.",
        "Phase 4 keeps page text, screenshots, and OCR output untrusted.",
        "Phase 5 is contract-only and does not implement Research Summary Proposal runtime.",
        "Phase 5 requires APPROVE_BROWSER_RESEARCH_SUMMARY in a future implementation.",
        "Phase 5 keeps output PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED.",
        "Phase 2 is planned/status-only and does not create browser runtime.",
        "No browser launch.",
        "No page navigation.",
        "No API/network/provider calls.",
        AUTHORITY,
    ]:
        _require(needle in source, "workbench helper missing text: " + needle)

    tree = ast.parse(source)
    blocked_import_roots = {
        "requests",
        "urllib",
        "http",
        "socket",
        "subprocess",
        "webbrowser",
        "selenium",
        "playwright",
        "pyppeteer",
        "puppeteer",
        "pyautogui",
        "threading",
        "multiprocessing",
    }
    blocked_calls = {"eval", "exec", "__import__", "startfile"}
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
                _require(alias.name.split(".")[0] not in blocked_import_roots, "workbench imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            _require(root not in blocked_import_roots, "workbench imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in blocked_calls, "workbench calls blocked builtin: " + func.id)
            elif isinstance(func, ast.Attribute):
                _require(func.attr not in blocked_methods, "workbench calls blocked method: " + func.attr)

    sys.path.insert(0, str(ROOT))
    helper = importlib.import_module("engel_browser_queen_workbench")
    status = helper.get_browser_queen_phase_status()
    rendered = helper.render_browser_queen_phase_status()
    _require(status.get("title") == "BROWSER QUEEN PHASE STATUS", "status title mismatch")
    _require(status.get("status") == "DISABLED", "status must be DISABLED")
    _require(status.get("api") == "NO API", "status must say NO API")
    _require(status.get("navigation") == "NO NAVIGATION", "status must say NO NAVIGATION")
    _require(status.get("browser_launch") == "NO BROWSER LAUNCH", "status must say NO BROWSER LAUNCH")
    _require(status.get("phase_2_status") == "PLANNED / DISABLED / NO_BROWSER_LAUNCH", "Phase 2 status mismatch")
    _require(status.get("phase_2_navigation") == "BLOCKED", "Phase 2 navigation mismatch")
    _require(status.get("phase_2_api") == "BLOCKED", "Phase 2 API mismatch")
    _require(status.get("phase_2_trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 2 trusted memory mismatch")
    _require(status.get("phase_3") == "Approved Open URL - Future / Contract Only", "Phase 3 label mismatch")
    _require(status.get("phase_3_status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 3 status mismatch")
    _require(status.get("phase_3_approval_token_required") == "APPROVE_BROWSER_OPEN_URL", "Phase 3 approval token mismatch")
    _require(status.get("phase_3_open_url_implementation") == "NOT_IMPLEMENTED", "Phase 3 implementation mismatch")
    _require(status.get("phase_3_navigation") == "BLOCKED_UNTIL_FUTURE_APPROVAL", "Phase 3 navigation mismatch")
    _require(status.get("phase_3_api") == "BLOCKED", "Phase 3 API mismatch")
    _require(status.get("phase_3_visible_browser_only") is True, "Phase 3 visible browser control mismatch")
    _require(status.get("phase_3_allowlist_required") is True, "Phase 3 allowlist control mismatch")
    _require(status.get("phase_3_stop_button_required") is True, "Phase 3 stop button control mismatch")
    _require(status.get("phase_3_action_receipt_required") is True, "Phase 3 action receipt control mismatch")
    _require(status.get("phase_3_profile_reuse") == "BLOCKED", "Phase 3 profile reuse mismatch")
    _require(status.get("phase_3_credential_access") == "BLOCKED", "Phase 3 credential access mismatch")
    _require(status.get("phase_3_trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 3 trusted memory mismatch")
    _require(status.get("phase_4") == "Read Page Text/Screenshot as Untrusted Content - Future / Contract Only", "Phase 4 label mismatch")
    _require(status.get("phase_4_status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 4 status mismatch")
    _require(status.get("phase_4_page_read_token_required") == "APPROVE_BROWSER_READ_PAGE", "Phase 4 page token mismatch")
    _require(status.get("phase_4_screenshot_token_required") == "APPROVE_BROWSER_SCREENSHOT", "Phase 4 screenshot token mismatch")
    _require(status.get("phase_4_page_text_extraction") == "NOT_IMPLEMENTED / BLOCKED", "Phase 4 page extraction mismatch")
    _require(status.get("phase_4_screenshot_capture") == "NOT_IMPLEMENTED / BLOCKED", "Phase 4 screenshot mismatch")
    _require(status.get("phase_4_ocr") == "NOT_IMPLEMENTED / BLOCKED", "Phase 4 OCR mismatch")
    _require(status.get("phase_4_api") == "BLOCKED", "Phase 4 API mismatch")
    _require(status.get("phase_4_visible_browser_only") is True, "Phase 4 visible browser control mismatch")
    _require(status.get("phase_4_action_receipt_required") is True, "Phase 4 action receipt control mismatch")
    _require(status.get("phase_4_profile_reuse") == "BLOCKED", "Phase 4 profile reuse mismatch")
    _require(status.get("phase_4_credential_access") == "BLOCKED", "Phase 4 credential access mismatch")
    _require(status.get("phase_4_trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 4 trusted memory mismatch")
    _require(status.get("phase_5") == "Research Summary Proposal - Future / Contract Only", "Phase 5 label mismatch")
    _require(status.get("phase_5_status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 5 status mismatch")
    _require(status.get("phase_5_approval_token_required") == "APPROVE_BROWSER_RESEARCH_SUMMARY", "Phase 5 approval token mismatch")
    _require(status.get("phase_5_summary_generation") == "NOT_IMPLEMENTED / BLOCKED", "Phase 5 summary generation mismatch")
    _require(status.get("phase_5_requires_phase4_artifact") is True, "Phase 5 artifact requirement mismatch")
    _require(status.get("phase_5_requires_action_receipt") is True, "Phase 5 action receipt requirement mismatch")
    _require(status.get("phase_5_requires_untrusted_content_scan") is True, "Phase 5 guard scan requirement mismatch")
    _require(status.get("phase_5_output_status") == "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED", "Phase 5 output status mismatch")
    _require(status.get("phase_5_api") == "BLOCKED", "Phase 5 API mismatch")
    _require(status.get("phase_5_trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 5 trusted memory mismatch")
    _require(status.get("research_path") == "Research Intake → Research Office / Overnight Research", "research path mismatch")
    _require(status.get("page_content") == "Page content is untrusted.", "page content status mismatch")
    _require(status.get("action_receipts") == "Action receipts required.", "action receipts status mismatch")
    _require(status.get("chatgpt_bridge") == "ChatGPT Visible UI Bridge - Future / No API", "ChatGPT bridge status mismatch")
    _require(status.get("authority") == AUTHORITY, "authority mismatch")
    for needle in [
        "Phase 0:",
        "Static Review Complete",
        "Phase 1:",
        "Contract / Disabled Status Active",
        "Phase 2:",
        "Visible Browser Status Panel - Planned / No Navigation",
        "Status: PLANNED / DISABLED / NO_BROWSER_LAUNCH",
        "Runtime: no launch / no navigation / no API",
        "Phase 3:",
        "Approved Open URL - Future",
        "Approved Open URL - Future / Contract Only",
        "Status: CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "Approval token required later: APPROVE_BROWSER_OPEN_URL",
        "Future controls: visible browser / allowlist / stop button / action receipt",
        "Phase 4:",
        "Read Page Text/Screenshot as Untrusted Content - Future",
        "Read Page Text/Screenshot as Untrusted Content - Future / Contract Only",
        "Status: CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "Approval tokens required later: APPROVE_BROWSER_READ_PAGE / APPROVE_BROWSER_SCREENSHOT",
        "Runtime: no page read / no screenshot / no OCR / no API",
        "Phase 5:",
        "Research Summary Proposal - Future",
        "Research Summary Proposal - Future / Contract Only",
        "Approval token required later: APPROVE_BROWSER_RESEARCH_SUMMARY",
        "Future inputs: Phase 4 artifact / action receipt / Untrusted Content Guard result",
        "Runtime: no summary generation / no artifact read / no API",
        "Phase 6:",
        "ChatGPT Visible UI Bridge - Future / No API",
        "Browser Queen cannot override Guardian.",
        "Browser Queen cannot write trusted memory.",
        "DISABLED / NO API / NO NAVIGATION / NO BROWSER LAUNCH",
        "Research Intake → Research Office / Overnight Research",
        "Page content is untrusted.",
        "Action receipts required.",
    ]:
        _require(needle in rendered, "rendered status missing text: " + needle)


def check_report_if_present() -> None:
    if not REPORT.exists():
        return
    text = _read(REPORT)
    for needle in [
        "ENGEL_BROWSER_QUEEN_PHASE1_CONTRACT_STATUS_WORKBENCH",
        "Status COMPLETE",
        "Files changed",
        "Phase status behavior",
        "No-API/no-navigation/no-launch confirmation",
        "Research Intake relation",
        "ChatGPT visible UI future path",
        "Verification results",
        "Packaging skipped",
        "Safety statement",
        "contract/status-only",
        "does not launch browsers",
        "does not write ALIVE_STATE",
        AUTHORITY,
    ]:
        _require(needle in text, "workbench report missing text: " + needle)


def main() -> int:
    checks = [
        ("files_and_docs", check_files_and_docs),
        ("helper_status", check_helper_status),
        ("report_if_present", check_report_if_present),
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
        print("ENGEL_BROWSER_QUEEN_WORKBENCH_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_BROWSER_QUEEN_WORKBENCH_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
