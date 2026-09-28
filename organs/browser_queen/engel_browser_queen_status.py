from __future__ import annotations

import json
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
BROWSER_QUEEN_BADGES = [
    "DISABLED",
    "NO API",
    "VISIBLE ONLY FUTURE",
    "RESEARCH INPUT",
    "UNTRUSTED PAGES",
]


def _base_status(contract_state: str) -> dict[str, Any]:
    return {
        "title": "BROWSER QUEEN",
        "status": "DISABLED",
        "mode": "VISIBLE_BROWSER_ONLY_FUTURE",
        "api": "BLOCKED",
        "research_path": "RESEARCH_INTAKE_TO_OVERNIGHT_RESEARCH",
        "research_display": "Research Intake \u2192 Overnight Research",
        "page_content": "UNTRUSTED_DATA",
        "page_display": "untrusted",
        "action_receipts": "REQUIRED",
        "trusted_memory": "BLOCKED",
        "contract": contract_state,
        "authority": AUTHORITY,
        "badges": list(BROWSER_QUEEN_BADGES),
        "source": "memory\\ENGEL_BROWSER_QUEEN_CONTRACT_V1.json",
        "safety_boundary": (
            "Contract/status-only. Browser Queen is disabled, visible-browser-only future research input to "
            "Research Intake, Research Office, and Overnight Research. Future Browser Queen outputs must flow through "
            "Research Intake before any Research Office / Overnight Research summary. It does not launch browsers, "
            "navigate pages, install browser dependencies, call APIs/network, run automation, scrape credentials, "
            "reuse browser profiles, read cookies/localStorage/sessionStorage, write trusted memory, "
            "mutate queues/routes/source, enable autonomy, execute model output, write ALIVE_STATE, or change authority hierarchy."
        ),
    }


def get_browser_queen_status() -> dict[str, Any]:
    contract_path = APP_ROOT / "memory" / "ENGEL_BROWSER_QUEEN_CONTRACT_V1.json"
    if not contract_path.exists():
        return _base_status("MISSING")

    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return _base_status("MALFORMED")

    if not isinstance(payload, dict):
        return _base_status("MALFORMED")

    status = _base_status("PRESENT")
    for key in [
        "status",
        "mode",
        "api",
        "research_path",
        "page_content",
        "action_receipts",
        "trusted_memory",
        "authority",
    ]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            status[key] = value.strip()

    status["research_display"] = "Research Intake \u2192 Overnight Research"
    status["page_display"] = "untrusted"
    status["badges"] = list(BROWSER_QUEEN_BADGES)
    return status


if __name__ == "__main__":
    print(json.dumps(get_browser_queen_status(), indent=2))
