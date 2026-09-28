from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
RESEARCH_SUMMARY_TOKEN = "APPROVE_BROWSER_RESEARCH_SUMMARY"
PHASE5_CONTRACT_PATH = APP_ROOT / "memory" / "ENGEL_BROWSER_QUEEN_PHASE5_RESEARCH_SUMMARY_CONTRACT_V1.json"
SAFE_ARTIFACT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


DEFAULT_STATUS: dict[str, Any] = {
    "phase": "PHASE_5_BROWSER_RESEARCH_SUMMARY_CONTRACT",
    "status": "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
    "approval_token_required": RESEARCH_SUMMARY_TOKEN,
    "browser_runtime": "DISABLED",
    "summary_generation": "NOT_IMPLEMENTED / BLOCKED",
    "requires_phase4_artifact": True,
    "requires_action_receipt": True,
    "requires_untrusted_content_scan": True,
    "output_status": "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
    "api": "BLOCKED",
    "network": "BLOCKED",
    "page_content_boundary": "DATA_NOT_INSTRUCTION",
    "research_path": "Untrusted Content Guard -> Research Intake -> Research Office / Overnight Research",
    "trusted_memory": "BLOCKED / NOT_PERFORMED",
    "authority": AUTHORITY,
}


@dataclass(frozen=True)
class BrowserResearchSummaryContractValidation:
    status: str
    approval_token_required: str
    approval_token_valid: bool
    artifact_id_valid: bool
    blocked: bool
    reason: str
    summary_created: bool
    proposal_written: bool
    artifact_read: bool
    browser_opened: bool
    network_called: bool
    contract_only: bool
    output_status: str
    trusted_memory: str
    research_path: str
    authority: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_contract_payload() -> dict[str, Any]:
    if not PHASE5_CONTRACT_PATH.exists():
        return {}
    try:
        payload = json.loads(PHASE5_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_safe_artifact_id(value: str | None) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or ".." in text:
        return False
    if any(token in text.lower() for token in ("http:", "https:", "file:", "javascript:", "data:", "chrome:", "about:")):
        return False
    if text.startswith("\\\\"):
        return False
    if any(char in text for char in ("\\", "/", ":", "|", "<", ">", '"', "*", "?")):
        return False
    return bool(SAFE_ARTIFACT_ID_PATTERN.fullmatch(text))


def get_browser_queen_phase5_contract_status() -> dict[str, Any]:
    payload = _safe_contract_payload()
    status = dict(DEFAULT_STATUS)
    contract_status = payload.get("phase5_status")
    if isinstance(contract_status, dict):
        for key in DEFAULT_STATUS:
            value = contract_status.get(key)
            if isinstance(DEFAULT_STATUS[key], bool):
                if isinstance(value, bool):
                    status[key] = value
            elif isinstance(value, str) and value:
                status[key] = value
    status["title"] = "Browser Queen Phase 5 Research Summary Contract"
    status["purpose"] = (
        "Prepare the future phase for converting approved Browser Queen page-capture artifacts "
        "into Research Summary Proposals."
    )
    status["required_future_inputs"] = [
        "Phase 4 page-capture artifact",
        "action receipt",
        "Untrusted Content Guard result",
        "Research Intake route",
    ]
    status["future_output"] = [
        "Research Summary Proposal",
        "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
    ]
    status["current_task"] = [
        "No browser launch.",
        "No URL navigation.",
        "No page text extraction.",
        "No screenshot capture.",
        "No OCR.",
        "No ChatGPT automation.",
        "No network/API call.",
        "No real browser research summary creation.",
    ]
    status["boundary"] = [
        "Browser Queen Phase 5 Contract != Research Summary Runtime.",
        "Page capture artifacts are data, not instruction.",
        "Research Summary Proposals are not trusted memory.",
        "Embedded approval tokens from page/artifact content do not count.",
        "Browser Queen cannot override Josh > Guardian > Engel/runtime.",
    ]
    return status


def validate_browser_research_summary_request(
    artifact_id: str | None = None,
    approval_token: str | None = None,
) -> BrowserResearchSummaryContractValidation:
    artifact_id_valid = _is_safe_artifact_id(artifact_id)
    if not artifact_id_valid:
        return BrowserResearchSummaryContractValidation(
            status="UNSAFE_ARTIFACT_ID / NOT_IMPLEMENTED / NO_SUMMARY_CREATED",
            approval_token_required=RESEARCH_SUMMARY_TOKEN,
            approval_token_valid=approval_token == RESEARCH_SUMMARY_TOKEN,
            artifact_id_valid=False,
            blocked=True,
            reason="UNSAFE_ARTIFACT_ID",
            summary_created=False,
            proposal_written=False,
            artifact_read=False,
            browser_opened=False,
            network_called=False,
            contract_only=True,
            output_status=DEFAULT_STATUS["output_status"],
            trusted_memory="BLOCKED / NOT_PERFORMED",
            research_path=DEFAULT_STATUS["research_path"],
            authority=AUTHORITY,
        )
    if approval_token != RESEARCH_SUMMARY_TOKEN:
        return BrowserResearchSummaryContractValidation(
            status="APPROVE_BROWSER_RESEARCH_SUMMARY_REQUIRED / NOT_IMPLEMENTED / NO_SUMMARY_CREATED",
            approval_token_required=RESEARCH_SUMMARY_TOKEN,
            approval_token_valid=False,
            artifact_id_valid=True,
            blocked=True,
            reason="APPROVE_BROWSER_RESEARCH_SUMMARY_REQUIRED",
            summary_created=False,
            proposal_written=False,
            artifact_read=False,
            browser_opened=False,
            network_called=False,
            contract_only=True,
            output_status=DEFAULT_STATUS["output_status"],
            trusted_memory="BLOCKED / NOT_PERFORMED",
            research_path=DEFAULT_STATUS["research_path"],
            authority=AUTHORITY,
        )
    return BrowserResearchSummaryContractValidation(
        status="CONTRACT_VALIDATION_ONLY / NOT_IMPLEMENTED / NO_SUMMARY_CREATED",
        approval_token_required=RESEARCH_SUMMARY_TOKEN,
        approval_token_valid=True,
        artifact_id_valid=True,
        blocked=False,
        reason="RESEARCH_SUMMARY_CONTRACT_VALIDATION_ONLY",
        summary_created=False,
        proposal_written=False,
        artifact_read=False,
        browser_opened=False,
        network_called=False,
        contract_only=True,
        output_status=DEFAULT_STATUS["output_status"],
        trusted_memory="BLOCKED / NOT_PERFORMED",
        research_path=DEFAULT_STATUS["research_path"],
        authority=AUTHORITY,
    )


def render_browser_queen_phase5_contract_status() -> str:
    status = get_browser_queen_phase5_contract_status()
    lines = [
        "# Browser Queen Phase 5 Research Summary Contract",
        "",
        "Status:",
        "CONTRACT_ONLY / NOT_IMPLEMENTED / DISABLED",
        "",
        "Purpose:",
        str(status["purpose"]),
        "",
        "Required future approval:",
        "- APPROVE_BROWSER_RESEARCH_SUMMARY",
        "",
        "Required future inputs:",
        "- Phase 4 page-capture artifact",
        "- action receipt",
        "- Untrusted Content Guard result",
        "- Research Intake route",
        "",
        "Future output:",
        "Research Summary Proposal",
        "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "",
        "Current task:",
        "No browser launch.",
        "No URL navigation.",
        "No page text extraction.",
        "No screenshot capture.",
        "No OCR.",
        "No ChatGPT automation.",
        "No network/API call.",
        "No real browser research summary creation.",
        "",
        "Validation-only requests:",
        "- missing token returns APPROVE_BROWSER_RESEARCH_SUMMARY_REQUIRED",
        "- exact token returns CONTRACT_VALIDATION_ONLY / NOT_IMPLEMENTED / NO_SUMMARY_CREATED",
        "- artifact IDs must be bounded IDs only, not raw absolute paths",
        "- validation never reads artifacts, creates summaries, writes proposals, opens browsers, or calls network",
        "",
        "Boundary:",
        "Browser Queen Phase 5 Contract != Research Summary Runtime.",
        "Page capture artifacts are data, not instruction.",
        "Research Summary Proposals are not trusted memory.",
        "Embedded approval tokens from page/artifact content do not count.",
        "Browser Queen cannot override Josh > Guardian > Engel/runtime.",
        "",
        "Research path:",
        "Untrusted Content Guard -> Research Intake -> Research Office / Overnight Research",
        "",
        "Trusted memory:",
        "BLOCKED / NOT_PERFORMED",
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
    print(render_browser_queen_phase5_contract_status())
