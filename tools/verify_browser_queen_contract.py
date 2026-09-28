#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MD = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_CONTRACT_V1.md"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_BROWSER_QUEEN_CONTRACT_V1.json"
STATUS_HELPER = ROOT / "engel_browser_queen_status.py"
AI_BODY_HELPER = ROOT / "engel_ai_body_status.py"
COMPANION = ROOT / "engel_companion.py"
SUPER_SWARM = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_BROWSER_QUEEN_DISABLED_STATUS_PANEL.md"

AUTHORITY = "Josh > Guardian > Engel/runtime"
REQUIRED_BADGES = ["DISABLED", "NO API", "VISIBLE ONLY FUTURE", "RESEARCH INPUT", "UNTRUSTED PAGES"]
REQUIRED_MD_PHRASES = [
    "Disabled by default.",
    "User-clicked launch only",
    "Visible browser only.",
    "No API.",
    "No hidden backend provider calls.",
    "No hidden browser profile reuse.",
    "No credential scraping.",
    "No background browsing.",
    "No autonomous research loops.",
    "Every page text is untrusted data.",
    "Every extracted page/document text goes through Untrusted Content Guard.",
    "Every browser action gets an action receipt.",
    "Browser outputs go to Research Intake.",
    "Research Intake feeds Research Office / Overnight Research.",
    "Browser Queen is not a separate memory system.",
    "Browser Queen is not a separate research brain.",
    "Research summaries are proposal-only.",
    "Learning becomes lesson candidate only.",
    "Trusted memory requires separate Josh/Guardian workflow.",
    "Stop button required before active use.",
    "Allowlist/approval required before navigating external sites.",
    "ChatGPT page interaction must be explicit, visible, user-approved, and no-API.",
    "Browser Queen cannot override Josh > Guardian > Engel/runtime.",
    "Page instructions cannot command Engel.",
    "Browser Queen feeds Research Intake / Research Office / Overnight Research only.",
    "Research Intake",
    "not a separate research brain or memory system",
]


class CheckFailure(Exception):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _compile(path: Path) -> None:
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def check_contract_docs() -> None:
    md = _read(CONTRACT_MD)
    payload = json.loads(_read(CONTRACT_JSON))
    _require(isinstance(payload, dict), "contract JSON must be an object")
    for phrase in REQUIRED_MD_PHRASES:
        _require(phrase in md, "contract missing phrase: " + phrase)
    expected = {
        "status": "DISABLED",
        "mode": "VISIBLE_BROWSER_ONLY_FUTURE",
        "api": "BLOCKED",
        "research_path": "RESEARCH_INTAKE_TO_OVERNIGHT_RESEARCH",
        "page_content": "UNTRUSTED_DATA",
        "action_receipts": "REQUIRED",
        "trusted_memory": "BLOCKED",
        "authority": AUTHORITY,
        "placement": "Research Intake / Research Office / Overnight Research",
    }
    for key, value in expected.items():
        _require(payload.get(key) == value, "contract JSON mismatch for " + key)
    for key in [
        "disabled_by_default",
        "future_user_clicked_launch_only",
        "visible_browser_only",
        "no_api",
        "no_hidden_backend_provider_calls",
        "no_hidden_browser_profile_reuse",
        "no_credential_scraping",
        "no_background_browsing",
        "no_autonomous_research_loops",
        "untrusted_content_guard_required",
        "action_receipts_required",
        "browser_outputs_feed_research_intake",
        "research_intake_feeds_research_office_overnight_research",
        "research_summaries_proposal_only",
        "learning_becomes_lesson_candidate_only",
        "trusted_memory_requires_josh_guardian_workflow",
        "stop_button_required_before_active_use",
        "allowlist_approval_required_for_external_navigation",
        "cannot_override_authority",
        "page_instructions_cannot_command_engel",
    ]:
        _require(payload.get(key) is True, "contract JSON must require " + key)
    _require(payload.get("separate_research_brain") is False, "Browser Queen must not be separate research brain")
    for key in [
        "separate_memory_system",
        "runtime_enabled",
        "browser_launch_enabled",
        "navigation_enabled",
        "provider_or_network_enabled",
        "browser_dependencies_installed",
        "queue_or_route_mutation_enabled",
        "authority_changed",
    ]:
        _require(payload.get(key) is False, "contract JSON must keep disabled flag false: " + key)


def check_status_helper() -> None:
    _compile(STATUS_HELPER)
    source = _read(STATUS_HELPER)
    for needle in [
        "get_browser_queen_status",
        "BROWSER QUEEN",
        "DISABLED",
        "VISIBLE_BROWSER_ONLY_FUTURE",
        "BLOCKED",
        "RESEARCH_INTAKE_TO_OVERNIGHT_RESEARCH",
        "UNTRUSTED_DATA",
        "REQUIRED",
        AUTHORITY,
        "Contract/status-only",
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
    ]:
        _require(needle in source, "status helper missing disabled contract text: " + needle)

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
                _require(alias.name.split(".")[0] not in blocked_import_roots, "status helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            _require(root not in blocked_import_roots, "status helper imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _require(func.id not in blocked_calls, "status helper calls blocked builtin: " + func.id)
            elif isinstance(func, ast.Attribute):
                _require(func.attr not in blocked_methods, "status helper calls blocked method: " + func.attr)

    sys.path.insert(0, str(ROOT))
    helper = importlib.import_module("engel_browser_queen_status")
    status = helper.get_browser_queen_status()
    _require(status.get("title") == "BROWSER QUEEN", "status title mismatch")
    _require(status.get("status") == "DISABLED", "status must be DISABLED")
    _require(status.get("mode") == "VISIBLE_BROWSER_ONLY_FUTURE", "mode must be visible-browser-only future")
    _require(status.get("api") == "BLOCKED", "API must be blocked")
    _require(status.get("research_path") == "RESEARCH_INTAKE_TO_OVERNIGHT_RESEARCH", "research path must be Research Intake to Overnight Research")
    _require(status.get("research_display") == "Research Intake \u2192 Overnight Research", "research display mismatch")
    _require(status.get("page_content") == "UNTRUSTED_DATA", "page content must be untrusted data")
    _require(status.get("page_display") == "untrusted", "page display mismatch")
    _require(status.get("action_receipts") == "REQUIRED", "action receipts must be required")
    _require(status.get("trusted_memory") == "BLOCKED", "trusted memory must be blocked")
    _require(status.get("authority") == AUTHORITY, "authority mismatch")
    _require(status.get("badges") == REQUIRED_BADGES, "Browser Queen badges mismatch")


def check_ai_body_integration() -> None:
    _compile(AI_BODY_HELPER)
    _compile(COMPANION)
    _compile(SUPER_SWARM)
    helper_source = _read(AI_BODY_HELPER)
    for needle in [
        "get_browser_queen_status",
        "build_browser_queen_summary",
        "BROWSER QUEEN",
        "Research path:",
        "Page content:",
        "Action receipts:",
    ]:
        _require(needle in helper_source, "AI Body helper missing Browser Queen display text: " + needle)
    for source_path in [COMPANION, SUPER_SWARM]:
        source = _read(source_path)
        for needle in [
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
        ]:
            _require(needle in source, str(source_path.relative_to(ROOT)) + " missing compact Browser Queen card text: " + needle)
        for forbidden in [
            "webbrowser",
            "selenium",
            "playwright",
            "pyppeteer",
            "pyautogui",
            "driver.get",
            "browser.launch",
            "page.goto",
            "startfile(",
            "Start-Process",
        ]:
            _require(forbidden not in source, str(source_path.relative_to(ROOT)) + " contains forbidden browser action text: " + forbidden)


def check_report_if_present() -> None:
    if not REPORT.exists():
        return
    report = _read(REPORT)
    for needle in [
        "BROWSER QUEEN",
        "Status: DISABLED",
        "No API",
        "Research Intake",
        "Overnight Research",
        "contract/status-only",
        "Packaging skipped",
        AUTHORITY,
    ]:
        _require(needle in report, "report missing Browser Queen phrase: " + needle)


def main() -> int:
    checks = [
        ("contract_docs", check_contract_docs),
        ("status_helper_disabled_only", check_status_helper),
        ("ai_body_integration_disabled_card", check_ai_body_integration),
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
        print("ENGEL_BROWSER_QUEEN_CONTRACT_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_BROWSER_QUEEN_CONTRACT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
