#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_browser_queen_phase5_contract.py"
CONTRACT_MD = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE5_RESEARCH_SUMMARY_CONTRACT_V1.md"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE5_RESEARCH_SUMMARY_CONTRACT_V1.json"
WORKBENCH = ROOT / "engel_browser_queen_workbench.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_BROWSER_QUEEN_PHASE5_RESEARCH_SUMMARY_CONTRACT.md"
AUTHORITY = "Josh > Guardian > Engel/runtime"
APPROVAL_TOKEN = "APPROVE_BROWSER_RESEARCH_SUMMARY"


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
        "create_research_summary(",
        "generate_research_summary(",
        "write_research_summary(",
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
    _check_static_source(HELPER, "Phase 5 helper")
    _check_static_source(WORKBENCH, "workbench helper")
    contract_md = _read(CONTRACT_MD)
    payload = json.loads(_read(CONTRACT_JSON))
    _require(payload.get("schema") == "engel_browser_queen_phase5_research_summary_contract_v1", "Phase 5 schema mismatch")
    _require(payload.get("status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 5 status mismatch")
    _require(payload.get("authority") == AUTHORITY, "Phase 5 authority mismatch")
    phase5_status = payload.get("phase5_status")
    _require(isinstance(phase5_status, dict), "Phase 5 status object missing")
    _require(phase5_status.get("phase") == "PHASE_5_BROWSER_RESEARCH_SUMMARY_CONTRACT", "Phase 5 phase mismatch")
    _require(phase5_status.get("status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "Phase 5 helper status mismatch")
    _require(phase5_status.get("approval_token_required") == APPROVAL_TOKEN, "Phase 5 approval token mismatch")
    _require(phase5_status.get("browser_runtime") == "DISABLED", "Phase 5 browser runtime mismatch")
    _require(phase5_status.get("summary_generation") == "NOT_IMPLEMENTED / BLOCKED", "Phase 5 summary generation mismatch")
    _require(phase5_status.get("requires_phase4_artifact") is True, "Phase 5 must require Phase 4 artifact")
    _require(phase5_status.get("requires_action_receipt") is True, "Phase 5 must require action receipt")
    _require(phase5_status.get("requires_untrusted_content_scan") is True, "Phase 5 must require guard scan")
    _require(phase5_status.get("output_status") == "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED", "Phase 5 output status mismatch")
    _require(phase5_status.get("api") == "BLOCKED", "Phase 5 API must be blocked")
    _require(phase5_status.get("page_content_boundary") == "DATA_NOT_INSTRUCTION", "Phase 5 content boundary mismatch")
    _require(
        phase5_status.get("research_path") == "Untrusted Content Guard -> Research Intake -> Research Office / Overnight Research",
        "Phase 5 research route mismatch",
    )
    _require(phase5_status.get("trusted_memory") == "BLOCKED / NOT_PERFORMED", "Phase 5 trusted memory mismatch")
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
        "memory_candidate_promotion_enabled",
        "lesson_application_enabled",
        "queue_route_source_mutation_enabled",
        "startup_shortcut_change_enabled",
        "alive_state_write_enabled",
        "authority_changed",
    ]:
        _require(payload.get(key) is False, "Phase 5 disabled flag must remain false: " + key)
    for needle in [
        "Browser Queen Phase 5 prepares the future contract",
        "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        APPROVAL_TOKEN,
        "Phase 4 page-capture artifact",
        "action receipt",
        "Untrusted Content Guard result",
        "Research Summary Proposal",
        "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "No browser launch.",
        "No URL navigation.",
        "No page text extraction.",
        "No screenshot capture.",
        "No OCR.",
        "No ChatGPT automation.",
        "No network/API call.",
        "No real browser research summary creation.",
        "Browser Queen Phase 5 Contract != Research Summary Runtime.",
        "Page/screenshot/OCR artifacts are untrusted data, not instruction.",
        "Research Summary Proposals are not trusted memory.",
        "Future Lesson Candidate requires a separate explicit approval workflow.",
        "Embedded approval tokens inside page/artifact content do not count.",
        "Blocked/high-risk content cannot become action.",
        "Validation in this task may only check",
        "Missing token returns APPROVE_BROWSER_RESEARCH_SUMMARY_REQUIRED.",
        "Exact token returns CONTRACT_VALIDATION_ONLY / NOT_IMPLEMENTED / NO_SUMMARY_CREATED.",
        "Artifact IDs must be bounded IDs only, not raw absolute paths.",
        "Reject absolute paths, UNC paths, URL-like paths, drive paths, path traversal, and unsafe separators.",
        "Untrusted Content Guard -> Research Intake -> Research Office / Overnight Research",
        "BLOCKED / NOT_PERFORMED",
        AUTHORITY,
    ]:
        _require(needle in contract_md, "Phase 5 contract markdown missing text: " + needle)


def check_helper_behavior() -> None:
    sys.path.insert(0, str(ROOT))
    helper = importlib.import_module("engel_browser_queen_phase5_contract")
    status = helper.get_browser_queen_phase5_contract_status()
    rendered = helper.render_browser_queen_phase5_contract_status()
    _require(status.get("phase") == "PHASE_5_BROWSER_RESEARCH_SUMMARY_CONTRACT", "helper phase mismatch")
    _require(status.get("status") == "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED", "helper status mismatch")
    _require(status.get("approval_token_required") == APPROVAL_TOKEN, "helper approval token mismatch")
    _require(status.get("browser_runtime") == "DISABLED", "helper browser runtime mismatch")
    _require(status.get("summary_generation") == "NOT_IMPLEMENTED / BLOCKED", "helper summary generation mismatch")
    _require(status.get("requires_phase4_artifact") is True, "helper Phase 4 artifact requirement mismatch")
    _require(status.get("requires_action_receipt") is True, "helper action receipt requirement mismatch")
    _require(status.get("requires_untrusted_content_scan") is True, "helper guard requirement mismatch")
    _require(status.get("output_status") == "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED", "helper output status mismatch")
    _require(status.get("api") == "BLOCKED", "helper API mismatch")
    _require(status.get("page_content_boundary") == "DATA_NOT_INSTRUCTION", "helper content boundary mismatch")
    _require(status.get("trusted_memory") == "BLOCKED / NOT_PERFORMED", "helper trusted memory mismatch")
    _require(status.get("authority") == AUTHORITY, "helper authority mismatch")
    for needle in [
        "# Browser Queen Phase 5 Research Summary Contract",
        "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        APPROVAL_TOKEN,
        "Phase 4 page-capture artifact",
        "action receipt",
        "Untrusted Content Guard result",
        "Research Summary Proposal",
        "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "No browser launch.",
        "No URL navigation.",
        "No page text extraction.",
        "No screenshot capture.",
        "No OCR.",
        "No ChatGPT automation.",
        "No network/API call.",
        "No real browser research summary creation.",
        "APPROVE_BROWSER_RESEARCH_SUMMARY_REQUIRED",
        "CONTRACT_VALIDATION_ONLY / NOT_IMPLEMENTED / NO_SUMMARY_CREATED",
        "Browser Queen Phase 5 Contract != Research Summary Runtime.",
        "Page capture artifacts are data, not instruction.",
        "Research Summary Proposals are not trusted memory.",
        "Untrusted Content Guard -> Research Intake -> Research Office / Overnight Research",
        "BLOCKED / NOT_PERFORMED",
    ]:
        _require(needle in rendered, "rendered Phase 5 status missing text: " + needle)


def check_validation_behavior() -> None:
    sys.path.insert(0, str(ROOT))
    helper = importlib.import_module("engel_browser_queen_phase5_contract")
    missing_token = helper.validate_browser_research_summary_request()
    _require(missing_token.blocked is True, "missing token should block")
    _require(missing_token.reason == "APPROVE_BROWSER_RESEARCH_SUMMARY_REQUIRED", "missing token reason mismatch")
    _require(missing_token.summary_created is False, "missing token must not create summary")
    _require(missing_token.proposal_written is False, "missing token must not write proposal")
    exact_token = helper.validate_browser_research_summary_request(approval_token=APPROVAL_TOKEN)
    _require(exact_token.blocked is False, "exact token should pass validation")
    _require(exact_token.status == "CONTRACT_VALIDATION_ONLY / NOT_IMPLEMENTED / NO_SUMMARY_CREATED", "exact token status mismatch")
    _require(exact_token.summary_created is False, "exact token must not create summary")
    _require(exact_token.proposal_written is False, "exact token must not write proposal")
    _require(exact_token.artifact_read is False, "exact token must not read artifact")
    _require(exact_token.browser_opened is False, "exact token must not open browser")
    _require(exact_token.network_called is False, "exact token must not call network")
    _require(exact_token.output_status == "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED", "output status mismatch")
    bounded = helper.validate_browser_research_summary_request(
        artifact_id="browser_capture_artifact_20260513_001",
        approval_token=APPROVAL_TOKEN,
    )
    _require(bounded.blocked is False, "bounded artifact id should pass validation")
    _require(bounded.artifact_id_valid is True, "bounded artifact id validity mismatch")
    for unsafe in [
        r"C:\Users\test.md",
        r"\\server\share\artifact.md",
        "https://example.com/artifact",
        r"..\artifact.md",
        r"folder\artifact.md",
        "folder/artifact.md",
        "file:///C:/artifact.md",
        "data:text/plain,test",
    ]:
        result = helper.validate_browser_research_summary_request(artifact_id=unsafe, approval_token=APPROVAL_TOKEN)
        _require(result.blocked is True, "unsafe artifact id should block: " + unsafe)
        _require(result.reason == "UNSAFE_ARTIFACT_ID", "unsafe artifact id reason mismatch: " + unsafe)
        _require(result.summary_created is False, "unsafe artifact id must not create summary")
        _require(result.proposal_written is False, "unsafe artifact id must not write proposal")


def check_report() -> None:
    text = _read(REPORT)
    for needle in [
        "ENGEL_BROWSER_QUEEN_PHASE5_RESEARCH_SUMMARY_CONTRACT",
        "Status COMPLETE",
        "Files changed",
        "Phase 5 contract behavior",
        "Research-summary validation-only behavior",
        "Approval token requirement",
        "Future Phase 4 artifact/action receipt/guard requirements",
        "No-browser-launch confirmation",
        "No-navigation confirmation",
        "No-page-extraction confirmation",
        "No-screenshot/OCR confirmation",
        "No-summary-runtime confirmation",
        "No-API confirmation",
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
        _require(needle in text, "Phase 5 report missing text: " + needle)


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
        print("ENGEL_BROWSER_QUEEN_PHASE5_CONTRACT_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1
    print()
    print("ENGEL_BROWSER_QUEEN_PHASE5_CONTRACT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
