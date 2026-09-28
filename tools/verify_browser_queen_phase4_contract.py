#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_browser_queen_phase4_contract.py"
CONTRACT_MD = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE4_PAGE_CAPTURE_CONTRACT_V1.md"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE4_PAGE_CAPTURE_CONTRACT_V1.json"
WORKBENCH = ROOT / "engel_browser_queen_workbench.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_BROWSER_QUEEN_PHASE4_PAGE_CAPTURE_CONTRACT.md"
AUTHORITY = "Josh > Guardian > Engel/runtime"
PAGE_READ_TOKEN = "APPROVE_BROWSER_READ_PAGE"
SCREENSHOT_TOKEN = "APPROVE_BROWSER_SCREENSHOT"


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


def _check_static_source(path: Path, label: str) -> None:
    source = _read(path)
    tree = ast.parse(source)
    blocked_import_roots = {
        "asyncio",
        "cv2",
        "http",
        "httpx",
        "mss",
        "openai",
        "anthropic",
        "pdfplumber",
        "PIL",
        "pypdf",
        "pytesseract",
        "requests",
        "socket",
        "subprocess",
        "urllib",
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
        "click",
        "goto",
        "launch",
        "mkdir",
        "open",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "screenshot",
        "touch",
        "unlink",
        "write",
        "write_bytes",
        "write_text",
    }
    lowered = source.lower()
    for forbidden in [
        ".goto(",
        ".click(",
        ".screenshot(",
        "launch_browser",
        "navigate_to",
        "capture_screenshot(",
        "extract_page_text(",
        "read_page_text(",
        "imagegrab",
        "pytesseract",
        "pdfplumber",
        "read_cookies",
        "localstorage.get",
        "sessionstorage.get",
        "browser_profile",
        "chromedriver",
        "driver.get(",
        "page.goto",
        "browser.new",
    ]:
        _require(forbidden not in lowered, label + " contains forbidden runtime behavior: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, label + " imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            _require(root not in blocked_import_roots, label + " imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in blocked_calls, label + " calls blocked builtin: " + func.id)
            elif isinstance(func, ast.Attribute):
                _require(func.attr not in blocked_methods, label + " calls blocked method: " + func.attr)


def check_helper_and_contract() -> None:
    _compile(HELPER)
    _check_static_source(HELPER, "Phase 4 helper")
    _check_static_source(WORKBENCH, "workbench helper")
    contract_md = _read(CONTRACT_MD)
    payload = json.loads(_read(CONTRACT_JSON))
    _require(payload.get("schema") == "engel_browser_queen_phase4_page_capture_contract_v1", "Phase 4 schema mismatch")
    _require(payload.get("status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 4 status mismatch")
    _require(payload.get("authority") == AUTHORITY, "Phase 4 authority mismatch")
    phase4_status = payload.get("phase4_status")
    _require(isinstance(phase4_status, dict), "Phase 4 status object missing")
    _require(phase4_status.get("phase") == "PHASE_4_PAGE_TEXT_SCREENSHOT_CONTRACT", "Phase 4 helper phase mismatch")
    _require(phase4_status.get("status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 4 helper status mismatch")
    _require(phase4_status.get("page_read_token_required") == PAGE_READ_TOKEN, "Phase 4 page-read token mismatch")
    _require(phase4_status.get("screenshot_token_required") == SCREENSHOT_TOKEN, "Phase 4 screenshot token mismatch")
    _require(phase4_status.get("browser_runtime") == "DISABLED", "Phase 4 browser runtime mismatch")
    _require(phase4_status.get("page_text_extraction") == "NOT_IMPLEMENTED / BLOCKED", "Phase 4 page text extraction mismatch")
    _require(phase4_status.get("screenshot_capture") == "NOT_IMPLEMENTED / BLOCKED", "Phase 4 screenshot capture mismatch")
    _require(phase4_status.get("ocr") == "NOT_IMPLEMENTED / BLOCKED", "Phase 4 OCR mismatch")
    _require(phase4_status.get("api") == "BLOCKED", "Phase 4 API must be blocked")
    _require(phase4_status.get("profile_reuse") == "BLOCKED", "Phase 4 profile reuse must be blocked")
    _require(phase4_status.get("credential_access") == "BLOCKED", "Phase 4 credential access must be blocked")
    _require(phase4_status.get("cookie_storage_access") == "BLOCKED", "Phase 4 cookie/storage access must be blocked")
    _require(phase4_status.get("page_content_boundary") == "DATA_NOT_INSTRUCTION", "Phase 4 page content boundary mismatch")
    _require(phase4_status.get("screenshot_content_boundary") == "DATA_NOT_INSTRUCTION", "Phase 4 screenshot content boundary mismatch")
    _require(
        phase4_status.get("research_path") == "Untrusted Content Guard \u2192 Research Intake \u2192 Research Office / Overnight Research",
        "Phase 4 research route mismatch",
    )
    _require(phase4_status.get("trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 4 trusted memory mismatch")
    for key in [
        "visible_browser_only",
        "phase3_context_required",
        "stop_button_required",
        "action_receipt_required",
    ]:
        _require(phase4_status.get(key) is True, "Phase 4 future control must be true: " + key)
    for key in [
        "phase3_approved_open_url_context_required",
        "visible_browser_only_required",
        "stop_button_already_present_required",
        "action_receipt_required",
        "blocked_high_risk_page_text_must_not_become_action",
    ]:
        _require(payload.get(key) is True, "Phase 4 contract must set true: " + key)
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
        "memory_candidate_promotion_enabled",
        "lesson_application_enabled",
        "queue_route_source_mutation_enabled",
        "startup_shortcut_change_enabled",
        "alive_state_write_enabled",
        "authority_changed",
    ]:
        _require(payload.get(key) is False, "Phase 4 disabled flag must remain false: " + key)
    for needle in [
        "Browser Queen Phase 4 prepares the future contract",
        "This task does not implement page text extraction.",
        "It does not implement screenshot capture.",
        "It does not implement OCR.",
        "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        PAGE_READ_TOKEN,
        SCREENSHOT_TOKEN,
        "Phase 3 approved-open-URL workflow completed",
        "visible browser only",
        "Stop button already present",
        "action receipt required",
        "no API",
        "no background browsing",
        "no hidden browser profile reuse",
        "no credential/profile/cookie/localStorage/sessionStorage access",
        "no page content trusted as instruction",
        "no screenshot/OCR content trusted as instruction",
        "all extracted text routes through Untrusted Content Guard \u2192 Research Intake",
        "blocked/high-risk page text must not become action",
        "No browser launch.",
        "No URL navigation.",
        "No page text extraction.",
        "No screenshot capture.",
        "No OCR.",
        "Validation in this task may only check explicit approval token presence.",
        "Validation must not read a page, capture a screenshot, run OCR",
        "Future Phase 5 Research Summary Proposal requires separate work.",
        "Browser Queen Phase 4 Contract \u2260 Page Capture Runtime.",
        "Page content is data, not instruction.",
        "Screenshot/OCR content is data, not instruction.",
        "Trusted memory remains BLOCKED / NOT_PERFORMED.",
        AUTHORITY,
    ]:
        _require(needle in contract_md, "Phase 4 contract markdown missing text: " + needle)


def check_helper_behavior() -> None:
    sys.path.insert(0, str(ROOT))
    helper = importlib.import_module("engel_browser_queen_phase4_contract")
    status = helper.get_browser_queen_phase4_contract_status()
    rendered = helper.render_browser_queen_phase4_contract_status()
    _require(status.get("phase") == "PHASE_4_PAGE_TEXT_SCREENSHOT_CONTRACT", "helper phase mismatch")
    _require(status.get("status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "helper status mismatch")
    _require(status.get("page_read_token_required") == PAGE_READ_TOKEN, "helper page-read token mismatch")
    _require(status.get("screenshot_token_required") == SCREENSHOT_TOKEN, "helper screenshot token mismatch")
    _require(status.get("browser_runtime") == "DISABLED", "helper browser runtime mismatch")
    _require(status.get("page_text_extraction") == "NOT_IMPLEMENTED / BLOCKED", "helper page extraction mismatch")
    _require(status.get("screenshot_capture") == "NOT_IMPLEMENTED / BLOCKED", "helper screenshot capture mismatch")
    _require(status.get("ocr") == "NOT_IMPLEMENTED / BLOCKED", "helper OCR mismatch")
    _require(status.get("api") == "BLOCKED", "helper API mismatch")
    _require(status.get("visible_browser_only") is True, "helper visible browser mismatch")
    _require(status.get("action_receipt_required") is True, "helper action receipt mismatch")
    _require(status.get("profile_reuse") == "BLOCKED", "helper profile reuse mismatch")
    _require(status.get("credential_access") == "BLOCKED", "helper credential access mismatch")
    _require(status.get("page_content_boundary") == "DATA_NOT_INSTRUCTION", "helper page content boundary mismatch")
    _require(status.get("screenshot_content_boundary") == "DATA_NOT_INSTRUCTION", "helper screenshot content boundary mismatch")
    _require(status.get("trusted_memory") == "BLOCKED / NOT_PERFORMED", "helper trusted memory mismatch")
    _require(status.get("authority") == AUTHORITY, "helper authority mismatch")
    for needle in [
        "# Browser Queen Phase 4 Page Capture Contract",
        "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "APPROVE_BROWSER_READ_PAGE for page text read",
        "APPROVE_BROWSER_SCREENSHOT for screenshot capture",
        "- visible browser only",
        "- Phase 3 approved URL context",
        "- Stop button already present",
        "- action receipt",
        "- no API",
        "- no background browsing",
        "- no hidden profile reuse",
        "- no credential/cookie/localStorage/sessionStorage access",
        "- page text remains untrusted",
        "- screenshot/OCR text remains untrusted",
        "No browser launch.",
        "No URL navigation.",
        "No page text extraction.",
        "No screenshot capture.",
        "No OCR.",
        "No ChatGPT automation.",
        "No network/API call.",
        "CONTRACT_VALIDATION_ONLY / NOT_IMPLEMENTED / NO_CAPTURE_PERFORMED",
        "validation never reads a page, takes a screenshot, runs OCR, opens a browser, or calls network",
        "Browser Queen Phase 4 Contract \u2260 Page Capture Runtime.",
        "Page content is data, not instruction.",
        "Screenshot/OCR content is data, not instruction.",
        "Untrusted Content Guard \u2192 Research Intake \u2192 Research Office / Overnight Research",
        "BLOCKED / NOT_PERFORMED",
    ]:
        _require(needle in rendered, "rendered Phase 4 status missing text: " + needle)


def check_validation_behavior() -> None:
    sys.path.insert(0, str(ROOT))
    helper = importlib.import_module("engel_browser_queen_phase4_contract")
    missing_page = helper.validate_browser_page_read_request()
    _require(missing_page.blocked is True, "page-read missing token should block")
    _require(missing_page.reason == "REQUIRED_TOKEN_MISSING", "page-read missing token reason mismatch")
    _require(missing_page.page_read_performed is False, "page-read missing token must not read")
    _require(missing_page.capture_performed is False, "page-read missing token must not capture")
    approved_page = helper.validate_browser_page_read_request(PAGE_READ_TOKEN)
    _require(approved_page.blocked is False, "page-read exact token should pass validation")
    _require(approved_page.status == "CONTRACT_VALIDATION_ONLY / NOT_IMPLEMENTED / NO_CAPTURE_PERFORMED", "page-read validation status mismatch")
    _require(approved_page.page_read_performed is False, "page-read validation must not read")
    _require(approved_page.capture_performed is False, "page-read validation must not capture")
    _require(approved_page.browser_opened is False, "page-read validation must not open browser")
    _require(approved_page.network_called is False, "page-read validation must not call network")
    _require(approved_page.to_dict()["contract_only"] is True, "page-read to_dict should preserve contract_only")
    missing_screenshot = helper.validate_browser_screenshot_request()
    _require(missing_screenshot.blocked is True, "screenshot missing token should block")
    _require(missing_screenshot.reason == "REQUIRED_TOKEN_MISSING", "screenshot missing token reason mismatch")
    _require(missing_screenshot.screenshot_performed is False, "screenshot missing token must not capture")
    _require(missing_screenshot.ocr_performed is False, "screenshot missing token must not run OCR")
    approved_screenshot = helper.validate_browser_screenshot_request(SCREENSHOT_TOKEN)
    _require(approved_screenshot.blocked is False, "screenshot exact token should pass validation")
    _require(approved_screenshot.status == "CONTRACT_VALIDATION_ONLY / NOT_IMPLEMENTED / NO_CAPTURE_PERFORMED", "screenshot validation status mismatch")
    _require(approved_screenshot.screenshot_performed is False, "screenshot validation must not capture")
    _require(approved_screenshot.ocr_performed is False, "screenshot validation must not run OCR")
    _require(approved_screenshot.browser_opened is False, "screenshot validation must not open browser")
    _require(approved_screenshot.network_called is False, "screenshot validation must not call network")
    _require(approved_screenshot.to_dict()["contract_only"] is True, "screenshot to_dict should preserve contract_only")


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "ENGEL_BROWSER_QUEEN_PHASE4_PAGE_CAPTURE_CONTRACT",
        "Status COMPLETE",
        "Files changed",
        "Phase 4 contract behavior",
        "Page-read validation-only behavior",
        "Screenshot validation-only behavior",
        "Approval token requirements",
        "No-browser-launch confirmation",
        "No-navigation confirmation",
        "No-page-extraction confirmation",
        "No-screenshot/OCR confirmation",
        "No-API confirmation",
        "No-profile/credential/cookie/localStorage access confirmation",
        "Research Intake route",
        "Trusted memory boundary",
        "Verification results",
        "Smoke results",
        "Packaging skipped",
        "Safety statement",
        "contract/status-only",
        "does not launch browsers",
        "does not write ALIVE_STATE",
        AUTHORITY,
    ]:
        _require(needle in text, "Phase 4 report missing text: " + needle)


def main() -> int:
    checks = [
        ("helper_and_contract", check_helper_and_contract),
        ("helper_behavior", check_helper_behavior),
        ("validation_behavior", check_validation_behavior),
        ("report", check_report),
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
        print("ENGEL_BROWSER_QUEEN_PHASE4_CONTRACT_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1
    print()
    print("ENGEL_BROWSER_QUEEN_PHASE4_CONTRACT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
