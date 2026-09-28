from __future__ import annotations

import re
from dataclasses import dataclass


BASE64_RE = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class PromptInjectionReason:
    code: str
    message: str


@dataclass(frozen=True)
class PromptInjectionCheck:
    verdict: str  # allow | review | block
    score: float
    reasons: tuple[PromptInjectionReason, ...]


RULES: tuple[tuple[str, str, float, re.Pattern[str]], ...] = (
    (
        "override.ignore_previous",
        "Looks like an attempt to override existing instructions.",
        0.44,
        re.compile(
            r"(ignore|disregard|forget|bypass)\s+(all\s+)?(previous|prior|above|system)\s+(instructions|rules|constraints|prompts?)",
            re.IGNORECASE,
        ),
    ),
    (
        "override.role_hijack",
        "Looks like a role or policy hijack attempt.",
        0.30,
        re.compile(r"(you\s+are\s+now|act\s+as|developer\s+mode|jailbreak|unrestricted\s+mode|dan)", re.IGNORECASE),
    ),
    (
        "exfiltrate.system_prompt",
        "Looks like a request to reveal hidden prompts/instructions.",
        0.42,
        re.compile(
            r"(reveal|show|print|dump|leak|display)\s+((the|your)\s+)?(system|developer|hidden)\s+(prompt|instructions|rules|message)",
            re.IGNORECASE,
        ),
    ),
    (
        "exfiltrate.secrets",
        "Looks like a request for sensitive credentials.",
        0.42,
        re.compile(r"(api\s*key|secret|token|password|private\s+key|credentials?|session\s+cookie|jwt|bearer)", re.IGNORECASE),
    ),
    (
        "authority.reorder_josh_guardian",
        "Looks like an attempt to reorder the fixed authority hierarchy.",
        0.76,
        re.compile(
            r"(guardian\s+(above|over|before|outranks?|supersedes|overrides?|replaces?)\s+josh"
            r"|josh\s+(below|under|after|beneath|subordinate\s+to)\s+guardian"
            r"|replace\s+josh\s+with\s+guardian"
            r"|remove\s+josh\s+(approval|gate|authority)"
            r"|disable\s+josh\s+(approval|gate|authority)"
            r"|make\s+guardian\s+(the\s+)?(top|highest|owner|operator|approver|authority)"
            r"|guardian\s+(is\s+)?(top|highest)\s+(authority|approver))",
            re.IGNORECASE,
        ),
    ),
)


LEET_MAP = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
}

ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}


def _normalize(input_text: str) -> tuple[str, str, str]:
    lowered = str(input_text or "").lower()
    mapped_chars: list[str] = []
    for ch in lowered:
        if ch in ZERO_WIDTH:
            mapped_chars.append(" ")
        elif ch in LEET_MAP:
            mapped_chars.append(LEET_MAP[ch])
        elif ch.isalnum() or ch.isspace():
            mapped_chars.append(ch)
        else:
            mapped_chars.append(" ")
    mapped = "".join(mapped_chars)
    collapsed = SPACE_RE.sub(" ", mapped).strip()
    compact = collapsed.replace(" ", "")
    return lowered, collapsed, compact


def check_prompt_injection(input_text: str) -> PromptInjectionCheck:
    lowered, collapsed, compact = _normalize(input_text)
    reasons: list[PromptInjectionReason] = []
    score = 0.0

    has_instruction_override = any(
        phrase in collapsed or phrase.replace(" ", "") in compact
        for phrase in (
            "ignore previous instructions",
            "ignore all previous instructions",
        )
    )
    has_exfiltration_intent = any(
        phrase in collapsed
        for phrase in (
            "system prompt",
            "developer instructions",
            "hidden prompt",
            "reveal",
        )
    )
    if has_instruction_override:
        score += 0.46
        reasons.append(PromptInjectionReason("override.obfuscated_instruction", "Detected obfuscated instruction-override phrase."))
    if has_exfiltration_intent:
        score += 0.24
        reasons.append(PromptInjectionReason("exfiltration.intent", "Detected exfiltration-focused prompt intent."))
    if BASE64_RE.search(lowered):
        score += 0.08
        reasons.append(PromptInjectionReason("obfuscation.base64_like", "Contains base64-like obfuscated content."))

    authority_reorder_phrases = (
        "guardian above josh",
        "guardian over josh",
        "guardian before josh",
        "guardian outranks josh",
        "guardian overrides josh",
        "guardian supersedes josh",
        "josh below guardian",
        "josh under guardian",
        "josh after guardian",
        "replace josh with guardian",
        "remove josh approval",
        "disable josh gate",
        "guardian highest authority",
        "make guardian highest authority",
    )
    has_authority_reorder = any(
        phrase in collapsed or phrase.replace(" ", "") in compact
        for phrase in authority_reorder_phrases
    )
    if has_authority_reorder:
        score += 0.76
        reasons.append(PromptInjectionReason("authority.reorder_josh_guardian", "Detected fixed-authority hierarchy reordering attempt."))

    for code, message, rule_score, regex in RULES:
        if regex.search(lowered) or regex.search(collapsed) or regex.search(compact):
            score += rule_score
            reasons.append(PromptInjectionReason(code, message))

    score = min(1.0, score)
    verdict = "allow"
    if score >= 0.70:
        verdict = "block"
    elif score >= 0.45:
        verdict = "review"
    return PromptInjectionCheck(verdict=verdict, score=score, reasons=tuple(reasons))
