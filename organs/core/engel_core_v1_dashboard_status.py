from __future__ import annotations

import json
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
CORE_V1_TITLE = "ENGEL CORE V1 COMMAND CENTER"
CORE_V1_BADGES = [
    "CORE V1",
    "READ ONLY",
    "JOSH FIRST",
    "GUARDIAN ACTIVE",
    "NO TRUSTED MEMORY WRITE",
    "BROWSER QUEEN DISABLED",
]
CORE_V1_FLOW = "Talk-to-Code \u2192 Products/Research \u2192 Lessons \u2192 Reviews \u2192 Memory Candidates"
BROWSER_QUEEN_RESEARCH_PATH = "Research Intake \u2192 Overnight Research"


def _read_json(relative_path: str) -> tuple[dict[str, Any] | None, str]:
    path = APP_ROOT / relative_path
    if not path.exists():
        return None, "MISSING"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "MALFORMED"
    if not isinstance(payload, dict):
        return None, "MALFORMED"
    return payload, "PRESENT"


def _status_for_file(relative_path: str) -> str:
    return "PRESENT" if (APP_ROOT / relative_path).exists() else "MISSING"


def _count(payload: dict[str, Any] | None, key: str) -> str:
    if not isinstance(payload, dict):
        return "UNKNOWN"
    value = payload.get(key)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "UNKNOWN"


def _field(payload: dict[str, Any] | None, key: str, fallback: str) -> str:
    if not isinstance(payload, dict):
        return fallback
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _base_status(json_state: str = "UNKNOWN") -> dict[str, Any]:
    return {
        "title": CORE_V1_TITLE,
        "core_status": "INDEX UNAVAILABLE",
        "authority": AUTHORITY,
        "flow": CORE_V1_FLOW,
        "products_count": "UNKNOWN",
        "research_intake_receipts_count": "UNKNOWN",
        "research_summary_proposals_count": "UNKNOWN",
        "lesson_candidates_count": "UNKNOWN",
        "lesson_reviews_count": "UNKNOWN",
        "research_lesson_candidates_count": "UNKNOWN",
        "research_lesson_reviews_count": "UNKNOWN",
        "memory_candidate_proposals_count": "UNKNOWN",
        "browser_queen_status": "DISABLED",
        "browser_queen_path": BROWSER_QUEEN_RESEARCH_PATH,
        "trusted_memory_status": "BLOCKED / NOT_PERFORMED",
        "untrusted_content_guard": "ACTIVE",
        "prompt_injection_guard": "ACTIVE",
        "package_baseline": "Core Stabilization V1",
        "dashboard_mode": "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
        "json_companion": json_state,
        "research_intake_contract": _status_for_file("memory/ENGEL_RESEARCH_INTAKE_QUEUE_CONTRACT_V1.json"),
        "memory_candidate_contract": _status_for_file("memory/ENGEL_MEMORY_CANDIDATE_WORKFLOW_CONTRACT_V1.json"),
        "browser_queen_contract": _status_for_file("memory/ENGEL_BROWSER_QUEEN_CONTRACT_V1.json"),
        "checkpoint_report": _status_for_file("reports/codex_bridge/ENGEL_CORE_STABILIZATION_CHECKPOINT_V1.md"),
        "badges": list(CORE_V1_BADGES),
        "safety_boundary": (
            "Compact read-only Core V1 status display only. It does not rebuild maps or reports from GUI, "
            "write trusted memory, promote memory candidates, apply lessons, run Browser Queen, launch browsers, "
            "call APIs/network, install packages, execute product/external code, mutate queues/routes/source, "
            "enable autonomy, write ALIVE_STATE, expand path permissions, or change authority hierarchy."
        ),
    }


def get_core_v1_dashboard_status() -> dict[str, Any]:
    continuity, continuity_state = _read_json("memory/ENGEL_CORE_CONTINUITY_MAP_V1.json")
    browser_queen, _browser_state = _read_json("memory/ENGEL_BROWSER_QUEEN_CONTRACT_V1.json")
    memory_candidate, _memory_state = _read_json("memory/ENGEL_MEMORY_CANDIDATE_WORKFLOW_CONTRACT_V1.json")
    research_intake, _research_state = _read_json("memory/ENGEL_RESEARCH_INTAKE_QUEUE_CONTRACT_V1.json")

    status = _base_status(continuity_state)
    if not isinstance(continuity, dict):
        return status

    browser_status = _field(
        browser_queen,
        "status",
        _field(continuity, "browser_queen_runtime_status", "DISABLED"),
    )
    trusted_memory = _field(
        continuity,
        "memory_candidate_trusted_memory_status",
        _field(memory_candidate, "trusted_memory_write", _field(continuity, "trusted_memory_write_status", "BLOCKED")),
    )
    research_trusted = _field(research_intake, "trusted_memory_write", "BLOCKED")
    if trusted_memory == "BLOCKED" and research_trusted == "BLOCKED":
        trusted_memory = "BLOCKED / NOT_PERFORMED"

    status.update(
        {
            "core_status": "LIVE BASELINE",
            "authority": _field(continuity, "authority", AUTHORITY),
            "products_count": _count(continuity, "products_count"),
            "research_intake_receipts_count": _count(continuity, "research_intake_receipts_count"),
            "research_summary_proposals_count": _count(continuity, "research_summary_proposals_count"),
            "lesson_candidates_count": _count(continuity, "lesson_candidates_count"),
            "lesson_reviews_count": _count(continuity, "lesson_reviews_count"),
            "research_lesson_candidates_count": _count(continuity, "research_lesson_candidates_count"),
            "research_lesson_reviews_count": _count(continuity, "research_lesson_reviews_count"),
            "memory_candidate_proposals_count": _count(continuity, "memory_candidate_proposals_count"),
            "browser_queen_status": browser_status,
            "browser_queen_path": BROWSER_QUEEN_RESEARCH_PATH,
            "trusted_memory_status": trusted_memory,
            "dashboard_mode": "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
        }
    )
    return status


def render_core_v1_dashboard_status() -> str:
    status = get_core_v1_dashboard_status()
    return "\n".join(
        [
            CORE_V1_TITLE,
            "Core: " + str(status["core_status"]),
            "Authority: " + str(status["authority"]),
            "Flow: " + str(status["flow"]),
            "Products: " + str(status["products_count"]),
            "Research: "
            + str(status["research_intake_receipts_count"])
            + " receipts / "
            + str(status["research_summary_proposals_count"])
            + " summaries",
            "Lessons: "
            + str(status["lesson_candidates_count"])
            + " product / "
            + str(status["research_lesson_candidates_count"])
            + " research",
            "Reviews: "
            + str(status["lesson_reviews_count"])
            + " product / "
            + str(status["research_lesson_reviews_count"])
            + " research",
            "Memory candidates: " + str(status["memory_candidate_proposals_count"]),
            "Browser Queen: " + str(status["browser_queen_status"]) + " \u2192 Research Intake",
            "Trusted Memory: " + str(status["trusted_memory_status"]),
            "Guards: Untrusted Content Guard "
            + str(status["untrusted_content_guard"])
            + " / Prompt Injection Guard "
            + str(status["prompt_injection_guard"]),
            "Status: " + str(status["dashboard_mode"]),
            "Badges: " + " | ".join(str(item) for item in status["badges"]),
            "Boundary: " + str(status["safety_boundary"]),
        ]
    )
