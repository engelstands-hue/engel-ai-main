from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
LIBRARY_PATH = ROOT / "memory" / "ENGEL_RESEARCH_UNDERSTANDING_LIBRARY_V1.json"
UNKNOWN_INTENT = "UNKNOWN_INTENT"


@dataclass(frozen=True)
class IntentClassification:
    input_text: str
    normalized_text: str
    intent: str
    domain: str
    confidence: str
    matched_phrase: str
    route: str
    approval_required: str
    default_status: str
    output_status: str
    trusted_memory_write: str
    runtime_effect: str
    safety_boundary: list[str]
    next_safe_action: str


def _bounded_text(text: str, limit: int = 1000) -> str:
    clean = str(text or "")
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "\n[TRUNCATED]"


def _normalize(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = re.sub(r"[^a-z0-9_<>/.:+-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def load_research_understanding_library() -> dict[str, Any]:
    return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))


def list_intent_families() -> list[str]:
    library = load_research_understanding_library()
    return [
        str(family.get("intent", ""))
        for family in library.get("intent_families", [])
        if isinstance(family, dict) and family.get("intent")
    ]


def get_intent_family(intent: str) -> dict[str, Any] | None:
    wanted = str(intent or "")
    library = load_research_understanding_library()
    for family in library.get("intent_families", []):
        if isinstance(family, dict) and family.get("intent") == wanted:
            return family
    return None


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def _keywords_match_score(normalized_text: str, keywords: list[str]) -> tuple[int, str]:
    if not keywords:
        return 0, ""
    normalized_keywords = [_normalize(keyword) for keyword in keywords if _normalize(keyword)]
    if not normalized_keywords:
        return 0, ""
    matches = [keyword for keyword in normalized_keywords if keyword in normalized_text]
    if len(matches) >= max(2, min(3, len(normalized_keywords))):
        return 30 + len(matches), ", ".join(matches[:4])
    if len(matches) == len(normalized_keywords) and len(matches) == 1:
        return 25, matches[0]
    return 0, ""


def _phrase_score(normalized_text: str, family: dict[str, Any]) -> tuple[int, str]:
    negative_phrases = [_normalize(item) for item in _safe_list(family.get("negative_phrases"))]
    if any(phrase and phrase in normalized_text for phrase in negative_phrases):
        return 0, ""

    best_score = 0
    best_phrase = ""
    for raw_phrase in _safe_list(family.get("phrases")):
        phrase = _normalize(raw_phrase)
        if not phrase:
            continue
        if normalized_text == phrase:
            score = 100 + len(phrase)
        elif normalized_text.startswith(phrase) or normalized_text.endswith(phrase):
            score = 80 + len(phrase)
        elif phrase in normalized_text:
            score = 60 + len(phrase)
        else:
            continue
        if score > best_score:
            best_score = score
            best_phrase = raw_phrase

    keyword_score, keyword_match = _keywords_match_score(normalized_text, _safe_list(family.get("keywords")))
    if keyword_score > best_score:
        best_score = keyword_score
        best_phrase = keyword_match

    return best_score, best_phrase


def _confidence(score: int) -> str:
    if score >= 100:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "NONE"


def _result_from_family(
    input_text: str,
    normalized_text: str,
    family: dict[str, Any],
    score: int,
    matched_phrase: str,
) -> IntentClassification:
    approval = str(family.get("approval_required") or "NONE_FOR_PLAN_ONLY")
    return IntentClassification(
        input_text=_bounded_text(input_text),
        normalized_text=normalized_text,
        intent=str(family.get("intent") or UNKNOWN_INTENT),
        domain=str(family.get("domain") or "unknown"),
        confidence=_confidence(score),
        matched_phrase=str(matched_phrase or ""),
        route=str(family.get("route") or "NEEDS_CLARIFICATION"),
        approval_required=approval,
        default_status=str(family.get("default_status") or "NEEDS_CLARIFICATION"),
        output_status=str(family.get("output_status") or "NOT_TRUSTED_MEMORY"),
        trusted_memory_write=str(family.get("trusted_memory_write") or "BLOCKED / NOT_PERFORMED"),
        runtime_effect=str(family.get("runtime_effect") or "CLASSIFICATION_HELPER_ONLY"),
        safety_boundary=_safe_list(family.get("safety_boundary")),
        next_safe_action=str(family.get("next_safe_action") or "Ask Josh for clarification and keep the result plan-only."),
    )


def _unknown_result(input_text: str, normalized_text: str) -> IntentClassification:
    return IntentClassification(
        input_text=_bounded_text(input_text),
        normalized_text=normalized_text,
        intent=UNKNOWN_INTENT,
        domain="unknown",
        confidence="NONE",
        matched_phrase="",
        route="NEEDS_CLARIFICATION",
        approval_required="NONE_FOR_PLAN_ONLY",
        default_status="UNKNOWN_INTENT / NEEDS_CLARIFICATION / NOT_TRUSTED_MEMORY",
        output_status="UNKNOWN_INTENT / NEEDS_CLARIFICATION / NOT_TRUSTED_MEMORY",
        trusted_memory_write="BLOCKED / NOT_PERFORMED",
        runtime_effect="CLASSIFICATION_HELPER_ONLY",
        safety_boundary=[
            "intent_classification_is_not_authority",
            "content_is_data_not_instruction",
            "embedded_approval_tokens_rejected",
        ],
        next_safe_action="Ask Josh for clarification or offer a read-only plan/proposal route.",
    )


def _domain_rank(domain: str) -> int:
    ranks = {
        "safety_guardian": 100,
        "browser_queen": 80,
        "external_memory": 75,
        "lesson_memory": 70,
        "code_companion": 60,
        "research": 50,
        "core_continuity": 40,
    }
    return ranks.get(domain, 0)


def _apply_route_rank(family: dict[str, Any]) -> int:
    default_status = str(family.get("default_status", ""))
    approval = str(family.get("approval_required") or "")
    if approval and approval != "NONE_FOR_PLAN_ONLY":
        return 15
    if "BLOCKED" in default_status:
        return 10
    if "PROPOSAL" in default_status or "PLAN" in default_status:
        return 3
    return 0


def _classify(text: str, domain_filter: str | None = None) -> IntentClassification:
    library = load_research_understanding_library()
    normalized = _normalize(text)
    if not normalized:
        return _unknown_result(text, normalized)

    candidates: list[tuple[int, int, int, dict[str, Any], str]] = []
    for family in library.get("intent_families", []):
        if not isinstance(family, dict):
            continue
        domain = str(family.get("domain") or "")
        if domain_filter and domain != domain_filter:
            continue
        score, matched_phrase = _phrase_score(normalized, family)
        if score <= 0:
            continue
        candidates.append((score, _apply_route_rank(family), _domain_rank(domain), family, matched_phrase))

    if not candidates:
        return _unknown_result(text, normalized)

    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    winner = candidates[0]
    if len(candidates) > 1:
        runner_up = candidates[1]
        if winner[0] == runner_up[0] and winner[1] == runner_up[1] and winner[2] == runner_up[2]:
            ambiguous = dict(winner[3])
            ambiguous["intent"] = "AMBIGUOUS"
            ambiguous["domain"] = "ambiguous"
            ambiguous["route"] = "NEEDS_CLARIFICATION"
            ambiguous["approval_required"] = "NONE_FOR_PLAN_ONLY"
            ambiguous["default_status"] = "AMBIGUOUS / DEFAULT_TO_PLAN_ONLY / NOT_TRUSTED_MEMORY"
            ambiguous["output_status"] = "AMBIGUOUS / NOT_TRUSTED_MEMORY / NOT_APPLIED"
            ambiguous["next_safe_action"] = "Ask Josh to clarify, then keep the next step read-only or proposal-only until explicit approval is provided."
            return _result_from_family(text, normalized, ambiguous, winner[0], winner[4])

    return _result_from_family(text, normalized, winner[3], winner[0], winner[4])


def classify_intent(text: str) -> IntentClassification:
    return _classify(text)


def classify_research_intent(text: str) -> IntentClassification:
    return _classify(text, "research")


def classify_product_intent(text: str) -> IntentClassification:
    return _classify(text, "code_companion")


def classify_safety_intent(text: str) -> IntentClassification:
    return _classify(text, "safety_guardian")


def classify_core_intent(text: str) -> IntentClassification:
    return _classify(text, "core_continuity")


def required_approval_for_intent(intent: str) -> str | None:
    family = get_intent_family(intent)
    if not family:
        return None
    approval = str(family.get("approval_required") or "NONE_FOR_PLAN_ONLY")
    if approval == "NONE_FOR_PLAN_ONLY":
        return None
    return approval


def intent_requires_approval(intent: str) -> bool:
    return required_approval_for_intent(intent) is not None


def render_intent_classification(result: IntentClassification) -> str:
    boundary = "\n".join(f"- {item}" for item in result.safety_boundary) or "- no additional boundary listed"
    return "\n".join(
        [
            "# Engel Research Understanding Classification",
            "",
            "Status:",
            "LOCAL_INTENT_CLASSIFICATION / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            "",
            "Input:",
            result.input_text or "NONE",
            "",
            "Intent:",
            result.intent,
            "",
            "Domain:",
            result.domain,
            "",
            "Confidence:",
            result.confidence,
            "",
            "Route:",
            result.route,
            "",
            "Approval required:",
            result.approval_required,
            "",
            "Boundary:",
            "Intent classification is not authority.",
            "Library content is data/config, not instruction.",
            "Embedded approval tokens do not count.",
            "Trusted memory write: BLOCKED / NOT_PERFORMED.",
            boundary,
            "",
            "Next safe action:",
            result.next_safe_action,
            "",
        ]
    )


def explain_intent_boundary(intent: str) -> str:
    family = get_intent_family(intent)
    if not family:
        return (
            "UNKNOWN_INTENT / NEEDS_CLARIFICATION / NOT_TRUSTED_MEMORY. "
            "Intent classification is not authority and cannot approve actions."
        )
    safety = "; ".join(_safe_list(family.get("safety_boundary"))) or "no additional boundary listed"
    approval = str(family.get("approval_required") or "NONE_FOR_PLAN_ONLY")
    return (
        f"{family.get('intent')}: route={family.get('route')}; "
        f"approval_required={approval}; "
        "intent classification is not authority; "
        "embedded approval tokens do not count; "
        f"trusted_memory_write={family.get('trusted_memory_write', 'BLOCKED / NOT_PERFORMED')}; "
        f"safety_boundary={safety}"
    )
