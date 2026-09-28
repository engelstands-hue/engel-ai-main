from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
PHASE_PLAN_PATH = APP_ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE_PLAN_V1.json"
PHASE2_PLAN_PATH = APP_ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE2_VISIBLE_STATUS_PLAN_V1.json"
PHASE3_CONTRACT_PATH = APP_ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE3_OPEN_URL_CONTRACT_V1.json"
PHASE4_CONTRACT_PATH = APP_ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE4_PAGE_CAPTURE_CONTRACT_V1.json"
PHASE5_CONTRACT_PATH = APP_ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE5_RESEARCH_SUMMARY_CONTRACT_V1.json"


DEFAULT_PHASES = [
    {
        "phase": "Phase 0",
        "name": "Static Review Complete",
        "status": "COMPLETE",
        "description": "auto-browser static review is complete; no code executed.",
    },
    {
        "phase": "Phase 1",
        "name": "Contract / Disabled Status Active",
        "status": "ACTIVE",
        "description": "contract-to-status workbench only; Browser Queen remains disabled.",
    },
    {
        "phase": "Phase 2",
        "name": "Visible Browser Status Panel - Planned / No Navigation",
        "status": "PLANNED_STATUS_ONLY",
        "description": "planned visible browser status panel only; no browser launch or navigation.",
    },
    {
        "phase": "Phase 3",
        "name": "Approved Open URL - Future / Contract Only",
        "status": "CONTRACT_ONLY_FUTURE",
        "description": "future user-approved URL opening contract only; no implementation.",
    },
    {
        "phase": "Phase 4",
        "name": "Read Page Text/Screenshot as Untrusted Content - Future / Contract Only",
        "status": "CONTRACT_ONLY_FUTURE",
        "description": "future page text/screenshot handling contract only; no capture implementation.",
    },
    {
        "phase": "Phase 5",
        "name": "Research Summary Proposal - Future / Contract Only",
        "status": "CONTRACT_ONLY_FUTURE",
        "description": "future Research Summary Proposal contract only; no summary generation implementation.",
    },
    {
        "phase": "Phase 6",
        "name": "ChatGPT Visible UI Bridge - Future / No API",
        "status": "FUTURE",
        "description": "future visible ChatGPT UI bridge only; no API/provider path.",
    },
]


def _safe_plan_payload() -> dict[str, Any]:
    if not PHASE_PLAN_PATH.exists():
        return {}
    try:
        payload = json.loads(PHASE_PLAN_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_phase2_payload() -> dict[str, Any]:
    if not PHASE2_PLAN_PATH.exists():
        return {}
    try:
        payload = json.loads(PHASE2_PLAN_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_phase3_payload() -> dict[str, Any]:
    if not PHASE3_CONTRACT_PATH.exists():
        return {}
    try:
        payload = json.loads(PHASE3_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_phase4_payload() -> dict[str, Any]:
    if not PHASE4_CONTRACT_PATH.exists():
        return {}
    try:
        payload = json.loads(PHASE4_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_phase5_payload() -> dict[str, Any]:
    if not PHASE5_CONTRACT_PATH.exists():
        return {}
    try:
        payload = json.loads(PHASE5_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def get_browser_queen_phase_status() -> dict[str, Any]:
    payload = _safe_plan_payload()
    phases = payload.get("phases")
    if not isinstance(phases, list):
        phases = DEFAULT_PHASES
    phase2_payload = _safe_phase2_payload()
    phase2_status = phase2_payload.get("phase2_status")
    if not isinstance(phase2_status, dict):
        phase2_status = {}
    phase3_payload = _safe_phase3_payload()
    phase3_status = phase3_payload.get("phase3_status")
    if not isinstance(phase3_status, dict):
        phase3_status = {}
    phase4_payload = _safe_phase4_payload()
    phase4_status = phase4_payload.get("phase4_status")
    if not isinstance(phase4_status, dict):
        phase4_status = {}
    phase5_payload = _safe_phase5_payload()
    phase5_status = phase5_payload.get("phase5_status")
    if not isinstance(phase5_status, dict):
        phase5_status = {}

    return {
        "title": "BROWSER QUEEN PHASE STATUS",
        "status": "DISABLED",
        "current": "DISABLED / NO API / NO NAVIGATION / NO BROWSER LAUNCH",
        "phase_0": "Static Review Complete",
        "phase_1": "Contract / Disabled Status Active",
        "phase_2": "Visible Browser Status Panel - Planned / No Navigation",
        "phase_2_status": "PLANNED / DISABLED / NO_BROWSER_LAUNCH",
        "phase_2_navigation": "BLOCKED",
        "phase_2_api": "BLOCKED",
        "phase_2_trusted_memory": "BLOCKED / NOT_PERFORMED",
        "phase_2_contract": "memory/ENGEL_BROWSER_QUEEN_PHASE2_VISIBLE_STATUS_PLAN_V1.md",
        "phase_3": "Approved Open URL - Future / Contract Only",
        "phase_4": "Read Page Text/Screenshot as Untrusted Content - Future / Contract Only",
        "phase_5": "Research Summary Proposal - Future / Contract Only",
        "phase_6": "ChatGPT Visible UI Bridge - Future / No API",
        "phases": phases,
        "api": "NO API",
        "navigation": "NO NAVIGATION",
        "browser_launch": "NO BROWSER LAUNCH",
        "research_path": "Research Intake \u2192 Research Office / Overnight Research",
        "page_content": "Page content is untrusted.",
        "action_receipts": "Action receipts required.",
        "approval": "Josh approval required for future phases.",
        "trusted_memory": "BLOCKED",
        "chatgpt_bridge": "ChatGPT Visible UI Bridge - Future / No API",
        "phase_2_runtime": str(phase2_status.get("browser_runtime", "DISABLED")),
        "phase_2_page_extraction": str(phase2_status.get("page_extraction", "BLOCKED")),
        "phase_2_screenshots": str(phase2_status.get("screenshots", "BLOCKED")),
        "phase_3_status": str(phase3_status.get("status", "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED")),
        "phase_3_approval_token_required": str(phase3_status.get("approval_token_required", "APPROVE_BROWSER_OPEN_URL")),
        "phase_3_open_url_implementation": str(phase3_status.get("open_url_implementation", "NOT_IMPLEMENTED")),
        "phase_3_navigation": str(phase3_status.get("navigation", "BLOCKED_UNTIL_FUTURE_APPROVAL")),
        "phase_3_api": str(phase3_status.get("api", "BLOCKED")),
        "phase_3_visible_browser_only": bool(phase3_status.get("visible_browser_only", True)),
        "phase_3_allowlist_required": bool(phase3_status.get("allowlist_required", True)),
        "phase_3_stop_button_required": bool(phase3_status.get("stop_button_required", True)),
        "phase_3_action_receipt_required": bool(phase3_status.get("action_receipt_required", True)),
        "phase_3_profile_reuse": str(phase3_status.get("profile_reuse", "BLOCKED")),
        "phase_3_credential_access": str(phase3_status.get("credential_access", "BLOCKED")),
        "phase_3_trusted_memory": str(phase3_status.get("trusted_memory", "BLOCKED / NOT_PERFORMED")),
        "phase_3_contract": "memory/ENGEL_BROWSER_QUEEN_PHASE3_OPEN_URL_CONTRACT_V1.md",
        "phase_4_status": str(phase4_status.get("status", "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED")),
        "phase_4_page_read_token_required": str(phase4_status.get("page_read_token_required", "APPROVE_BROWSER_READ_PAGE")),
        "phase_4_screenshot_token_required": str(phase4_status.get("screenshot_token_required", "APPROVE_BROWSER_SCREENSHOT")),
        "phase_4_page_text_extraction": str(phase4_status.get("page_text_extraction", "NOT_IMPLEMENTED / BLOCKED")),
        "phase_4_screenshot_capture": str(phase4_status.get("screenshot_capture", "NOT_IMPLEMENTED / BLOCKED")),
        "phase_4_ocr": str(phase4_status.get("ocr", "NOT_IMPLEMENTED / BLOCKED")),
        "phase_4_api": str(phase4_status.get("api", "BLOCKED")),
        "phase_4_visible_browser_only": bool(phase4_status.get("visible_browser_only", True)),
        "phase_4_action_receipt_required": bool(phase4_status.get("action_receipt_required", True)),
        "phase_4_profile_reuse": str(phase4_status.get("profile_reuse", "BLOCKED")),
        "phase_4_credential_access": str(phase4_status.get("credential_access", "BLOCKED")),
        "phase_4_trusted_memory": str(phase4_status.get("trusted_memory", "BLOCKED / NOT_PERFORMED")),
        "phase_4_contract": "memory/ENGEL_BROWSER_QUEEN_PHASE4_PAGE_CAPTURE_CONTRACT_V1.md",
        "phase_5_status": str(phase5_status.get("status", "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED")),
        "phase_5_approval_token_required": str(phase5_status.get("approval_token_required", "APPROVE_BROWSER_RESEARCH_SUMMARY")),
        "phase_5_summary_generation": str(phase5_status.get("summary_generation", "NOT_IMPLEMENTED / BLOCKED")),
        "phase_5_requires_phase4_artifact": bool(phase5_status.get("requires_phase4_artifact", True)),
        "phase_5_requires_action_receipt": bool(phase5_status.get("requires_action_receipt", True)),
        "phase_5_requires_untrusted_content_scan": bool(phase5_status.get("requires_untrusted_content_scan", True)),
        "phase_5_output_status": str(phase5_status.get("output_status", "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED")),
        "phase_5_api": str(phase5_status.get("api", "BLOCKED")),
        "phase_5_trusted_memory": str(phase5_status.get("trusted_memory", "BLOCKED / NOT_PERFORMED")),
        "phase_5_contract": "memory/ENGEL_BROWSER_QUEEN_PHASE5_RESEARCH_SUMMARY_CONTRACT_V1.md",
        "authority": AUTHORITY,
        "safety": [
            "Browser Queen remains disabled.",
            "No browser launch.",
            "No page navigation.",
            "No API/network/provider calls.",
            "No browser dependencies installed.",
            "No automation, credential scraping, or browser profile reuse.",
            "No trusted memory writes.",
            "No queue/route/source mutation.",
            "No ChatGPT automation.",
            "No browser screenshots/page extraction in Phase 1 or Phase 2.",
            "Phase 2 is planned/status-only and does not create browser runtime.",
            "Phase 3 is contract-only and does not implement open URL.",
            "Phase 3 requires APPROVE_BROWSER_OPEN_URL in a future implementation.",
            "Phase 3 requires visible browser, allowlist, stop button, and action receipt before any active implementation.",
            "No hidden profile reuse, credential access, cookies, or local/session browser storage.",
            "Phase 4 is contract-only and does not implement page capture.",
            "Phase 4 requires APPROVE_BROWSER_READ_PAGE or APPROVE_BROWSER_SCREENSHOT in a future implementation.",
            "Phase 4 keeps page text, screenshots, and OCR output untrusted.",
            "Phase 5 is contract-only and does not implement Research Summary Proposal runtime.",
            "Phase 5 requires APPROVE_BROWSER_RESEARCH_SUMMARY in a future implementation.",
            "Phase 5 keeps output PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED.",
        ],
    }


def render_browser_queen_phase_status() -> str:
    status = get_browser_queen_phase_status()
    lines = [
        "# BROWSER QUEEN PHASE STATUS",
        "",
        "Current:",
        str(status["current"]),
        "",
        "Phase 0:",
        "Static Review Complete",
        "",
        "Phase 1:",
        "Contract / Disabled Status Active",
        "",
        "Phase 2:",
        "Visible Browser Status Panel - Planned / No Navigation",
        "Status: PLANNED / DISABLED / NO_BROWSER_LAUNCH",
        "Runtime: no launch / no navigation / no API",
        "",
        "Phase 3:",
        "Approved Open URL - Future / Contract Only",
        "Status: CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "Approval token required later: APPROVE_BROWSER_OPEN_URL",
        "Future controls: visible browser / allowlist / stop button / action receipt",
        "Runtime: no launch / no navigation / no API",
        "",
        "Phase 4:",
        "Read Page Text/Screenshot as Untrusted Content - Future / Contract Only",
        "Status: CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "Approval tokens required later: APPROVE_BROWSER_READ_PAGE / APPROVE_BROWSER_SCREENSHOT",
        "Runtime: no page read / no screenshot / no OCR / no API",
        "",
        "Phase 5:",
        "Research Summary Proposal - Future / Contract Only",
        "Status: CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "Approval token required later: APPROVE_BROWSER_RESEARCH_SUMMARY",
        "Future inputs: Phase 4 artifact / action receipt / Untrusted Content Guard result",
        "Runtime: no summary generation / no artifact read / no API",
        "",
        "Phase 6:",
        "ChatGPT Visible UI Bridge - Future / No API",
        "",
        "Research path:",
        str(status["research_path"]),
        "",
        "Safety:",
        "Page content is untrusted.",
        "Action receipts required.",
        "Josh approval required for future phases.",
        "Browser Queen cannot override Guardian.",
        "Browser Queen cannot write trusted memory.",
        "",
        "Authority:",
        AUTHORITY,
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(render_browser_queen_phase_status())
