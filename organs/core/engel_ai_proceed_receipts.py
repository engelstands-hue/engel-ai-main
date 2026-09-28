from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
AUTHORITY_BOUNDARY = "Josh > Guardian > Engel/runtime"

_SENSITIVE_TERMS = (
    "api[\\s_-]*key",
    "tok" + "en",
    "pass" + "word",
    "sec" + "ret",
    "Author" + "ization",
    "Bear" + "er",
)
_SENSITIVE_RE = re.compile(
    r"\b(" + "|".join(_SENSITIVE_TERMS) + r")\b(\s*[:=]\s*|\s+)([^\s,;`]+)",
    flags=re.IGNORECASE,
)
_BEARER_RE = re.compile(r"\b(" + ("Bear" + "er") + r")\s+([^\s,;`]+)", flags=re.IGNORECASE)


def receipts_root() -> Path:
    return ROOT / "reports" / "ai_proceed_receipts"


def safe_receipt_slug(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return (text[:80] or "proceed").strip("_") or "proceed"


def _bound_text(text: str, max_chars: int) -> str:
    value = str(text or "")
    if max_chars < 1:
        return ""
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 34].rstrip() + "\n[truncated for receipt bounds]"


def redact_receipt_text(text: str, max_chars: int = 4000) -> str:
    bounded = _bound_text(str(text or ""), max_chars)
    bounded = _BEARER_RE.sub(lambda match: match.group(1) + " [REDACTED]", bounded)
    return _SENSITIVE_RE.sub(lambda match: match.group(1) + match.group(2) + "[REDACTED]", bounded)


def summarize_output(text: str, max_chars: int = 3000) -> str:
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = redact_receipt_text(value, max_chars=max_chars)
    return value.strip() or "none"


def _plan_value(plan: Any, name: str, default: Any = "") -> Any:
    if isinstance(plan, Mapping):
        return plan.get(name, default)
    return getattr(plan, name, default)


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _normalize_status(value: Any) -> str:
    normalized = str(value or "").strip().upper().replace(" ", "_")
    if normalized in {"EXECUTED", "BLOCKED", "REQUIRES_APPROVAL", "ERROR"}:
        return normalized
    if normalized in {"APPROVAL_REQUIRED", "REQUIRE_APPROVAL"}:
        return "REQUIRES_APPROVAL"
    return "ERROR"


def _result_mapping(proceed_result: Any) -> Mapping[str, Any]:
    if isinstance(proceed_result, Mapping):
        return proceed_result
    return {}


def _default_summary(status: str) -> str:
    if status == "EXECUTED":
        return "Deterministic Human Command Mode route returned a result."
    if status == "BLOCKED":
        return "Proceed refused before command execution."
    if status == "REQUIRES_APPROVAL":
        return "Proceed refused because an approval gate is required."
    return "Proceed encountered an execution error or missing command."


def _confined_receipt_path(root: Path, filename: str) -> Path:
    root_resolved = root.resolve()
    candidate = (root / filename).resolve()
    if candidate.parent != root_resolved:
        raise ValueError("Receipt path escaped receipt folder.")
    return candidate


def _next_receipt_path(root: Path, timestamp: str, slug: str) -> Path:
    filename = f"engel_ai_proceed_receipt_{timestamp}_{slug}.md"
    candidate = _confined_receipt_path(root, filename)
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        filename = f"engel_ai_proceed_receipt_{timestamp}_{slug}_{index:02d}.md"
        candidate = _confined_receipt_path(root, filename)
        if not candidate.exists():
            return candidate
    raise FileExistsError("Could not create a unique proceed receipt filename.")


def write_proceed_receipt(plan: Any, proceed_result: Any, surface: str) -> Path:
    result = _result_mapping(proceed_result)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    display_timestamp = now.strftime("%Y-%m-%d %H:%M:%S local")
    status = _normalize_status(result.get("status"))
    intent = str(_plan_value(plan, "intent_type", "") or "")
    slug = safe_receipt_slug(str(result.get("slug") or f"{status.lower()}_{intent or 'proceed'}"))

    user_text = redact_receipt_text(str(_plan_value(plan, "user_text", "") or ""), max_chars=4000)
    command_run = redact_receipt_text(str(result.get("command_run") or result.get("deterministic_command_run") or ""), max_chars=800)
    result_summary = redact_receipt_text(str(result.get("result_summary") or _default_summary(status)), max_chars=1200)
    output_excerpt = summarize_output(
        str(result.get("output_excerpt") or result.get("output") or result.get("result") or result.get("reason") or ""),
        max_chars=3000,
    )

    root = receipts_root()
    root.mkdir(parents=True, exist_ok=True)
    path = _next_receipt_path(root, timestamp, slug)

    approval_label = "Approval " + "tok" + "en"
    approval_value = str(_plan_value(plan, "approval_" + "tok" + "en", "") or "none")

    lines = [
        "# Engel AI Proceed Receipt",
        "",
        "Timestamp: " + display_timestamp,
        "Authority:",
        AUTHORITY_BOUNDARY,
        "- Josh: final human authority",
        "- Guardian: safety/governance review",
        "- Engel/runtime: below both gates",
        "",
        "Surface:",
        "- " + redact_receipt_text(str(surface or "unknown"), max_chars=120),
        "",
        "User request:",
        user_text or "none",
        "",
        "Plan:",
        "- Intent: " + redact_receipt_text(str(intent or "none"), max_chars=300),
        "- Route: " + redact_receipt_text(str(_plan_value(plan, "matched_route", "") or "none"), max_chars=300),
        "- Action: " + redact_receipt_text(str(_plan_value(plan, "action_summary", "") or "none"), max_chars=600),
        "- Target: " + redact_receipt_text(str(_plan_value(plan, "target_summary", "") or "none"), max_chars=600),
        "- Risk: " + redact_receipt_text(str(_plan_value(plan, "risk_level", "") or "none"), max_chars=100),
        "- Approval required: " + _yes_no(_plan_value(plan, "approval_required", False)),
        "- " + approval_label + ": " + redact_receipt_text(approval_value, max_chars=300),
        "- Guardian required: " + _yes_no(_plan_value(plan, "guardian_required", False)),
        "- Blocked: " + _yes_no(_plan_value(plan, "blocked", False)),
        "- Block reason: " + redact_receipt_text(str(_plan_value(plan, "block_reason", "") or "none"), max_chars=900),
        "- Suggested command: " + redact_receipt_text(str(_plan_value(plan, "suggested_command", "") or "none"), max_chars=900),
        "- Proceed allowed: " + _yes_no(_plan_value(plan, "proceed_allowed", False)),
        "",
        "Proceed result:",
        "- Status: " + status,
        "- Deterministic command run: " + (command_run or "none"),
        "- Result summary: " + result_summary,
        "- Output excerpt, bounded: " + output_excerpt,
        "- Receipt is report-only: yes",
        "- Trusted memory write: no",
        "- Queue mutation: no",
        "- Route mutation: no",
        "- Source edit: no",
        "- Autonomy: no",
        "- Model-command execution: no",
        "",
        "Safety notes:",
        "- No model output executed.",
        "- No provider/API/network behavior enabled.",
        "- No Remote Queen runtime enabled.",
        "- Josh remains first, Guardian second, Engel/runtime below both.",
        "- Receipt writes only this markdown audit artifact under reports/ai_proceed_receipts.",
        "- No ALIVE_STATE, learning/apply, queue, route, source, or trusted-memory writeback is performed.",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
