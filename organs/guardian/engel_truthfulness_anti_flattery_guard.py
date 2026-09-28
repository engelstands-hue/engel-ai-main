from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)

STATUS_LABELS = [
    "TRUTHFULNESS_ANTI_FLATTERY_GUARD",
    "VERIFICATION_FIRST",
    "ACCURACY_OVER_APPROVAL",
    "NO_FLATTERY",
    "NO_PREMISE_VALIDATION_WITHOUT_CHECK",
    "CORRECT_WRONG_PREMISES",
    "STATE_UNCERTAINTY",
    "CONFIDENCE_LABELS_SUPPORTED",
    "FACT_CHECK_REQUIRED_FOR_VOLATILE_CLAIMS",
    "HASH_PATH_STATUS_VERIFICATION_REQUIRED",
    "NO_HALLUCINATION",
    "NO_INVENTED_FACTS",
    "UNTRUSTED_EXTERNAL_PROMPTS_NOT_AUTHORITY",
    "SOCIAL_MEDIA_PROMPTS_UNTRUSTED",
    "SAFETY_BOUNDARIES_PRESERVED",
    "AUTHORITY_HIERARCHY_PRESERVED",
    "PROMPT_INJECTION_GUARD_PRESERVED",
    "UNTRUSTED_CONTENT_GUARD_PRESERVED",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

CHECKER_LABELS = [
    "HEURISTIC_REVIEW_ONLY",
    "DOES_NOT_APPROVE_CONTENT",
    "DOES_NOT_REWRITE_CONTENT",
    "UNTRUSTED_INPUT",
    "HUMAN_REVIEW_REQUIRED",
]

ALLOWED_LESSONS = [
    "accuracy over approval",
    "do not flatter",
    "do not validate false premises",
    "correct wrong assumptions",
    "state uncertainty",
    "verify facts and claims",
    "use confidence levels when useful",
    "say when evidence is missing",
    "do not invent hashes, commits, file paths, package states, citations, or verification results",
    "do not claim a verifier passed unless it actually ran or a user-provided report says it passed",
    "do not claim a file exists unless checked or reported by the user",
]

REJECTED_LESSONS = [
    "aggression for its own sake",
    "no disclaimers as a blanket rule",
    "removing safety warnings",
    "never apologizing",
    "political/ethical instruction overrides",
    "ignoring user safety",
    "overriding system/developer instructions",
    "treating social-media prompts as authority",
]

ENGEL_AI_APPLICATIONS = [
    "AI Growth summaries",
    "Daily Cycle summaries",
    "Self-Learning summaries",
    "Candidate Review",
    "Memory Promotion",
    "Research-to-Fix",
    "Password-gated action status",
    "Background worker / research toggle status",
]

CODE_COMPANION_APPLICATIONS = [
    "candidate finder",
    "patch candidate plans",
    "verifier plans",
    "patch runner reports",
    "receipt viewer",
    "GUI status panels",
    "commit/package/hash reports",
]

VERIFICATION_RULES = [
    "verify commit hashes before stating them unless user supplied them",
    "verify package hashes before stating them unless user supplied them",
    "distinguish reported by user from verified by Engel",
    "state when a verifier was not run",
    "state when packaging was skipped",
    "state when evidence is missing",
    "do not overstate source GUI smoke or package smoke results",
]

RESPONSE_QUALITY_RULES = [
    "answer directly",
    "challenge wrong assumptions",
    "avoid praise like great question",
    "avoid you are absolutely right unless truly verified",
    "avoid filler",
    "avoid pretending certainty",
    "use confidence labels when useful: high, medium, low, unknown",
    "give the safest useful next step",
]

SAFETY_PRESERVATION = [
    "Authority Hierarchy",
    "Prompt Injection Guard",
    "Untrusted Content Guard",
    "Human approval requirements",
    "Global Password Gate",
    "Protected Action Registry",
    "Verifier requirements",
    "Receipt requirements",
    "Core Continuity requirements",
]

FORBIDDEN_BEHAVIOR = [
    "call providers/network/browser",
    "run model inference",
    "mutate source",
    "write trusted memory",
    "apply patches",
    "alter authority hierarchy",
    "disable safety messages",
    "encourage unsafe cyber activity",
    "adopt external prompt text as system authority",
]

CHECKLIST_FIELDS = [
    "flattery_risk",
    "premise_validation_risk",
    "unsupported_certainty_risk",
    "missing_uncertainty_label",
    "claims_need_verification",
    "unsafe_safety_weakening_language",
    "external_prompt_as_authority_risk",
    "recommended_fix_summary",
]

ALLOWED_SUFFIXES = {".md", ".txt", ".json"}
ALLOWED_TOP_LEVEL_DIRS = {"reports", "memory"}
FORBIDDEN_TOP_LEVEL_DIRS = {"live", "staging"}
FORBIDDEN_PARTS = {"models", "model", "model_files", "hf", "ollama", "llama"}
MAX_CHECK_TEXT_BYTES = 500_000

FLATTERY_PATTERNS = [
    r"\bgreat question\b",
    r"\byou are absolutely right\b",
    r"\byou're absolutely right\b",
    r"\bbrilliant\b",
    r"\bexcellent point\b",
    r"\byou nailed it\b",
    r"\bcould not agree more\b",
    r"\bcouldn't agree more\b",
]

PREMISE_VALIDATION_PATTERNS = [
    r"\byou are right\b",
    r"\byou're right\b",
    r"\bthat is exactly right\b",
    r"\bthat is correct\b",
    r"\bobviously correct\b",
]

UNSUPPORTED_CERTAINTY_PATTERNS = [
    r"\bdefinitely\b",
    r"\bguaranteed\b",
    r"\bwithout question\b",
    r"\bno doubt\b",
    r"\balways\b",
    r"\bnever\b",
    r"\bverified\b",
    r"\bpassed\b",
    r"\bconfirmed\b",
]

CLAIMS_NEED_VERIFICATION_PATTERNS = [
    r"\b[0-9a-f]{7,40}\b",
    r"\bsha256\b",
    r"\bhash\b",
    r"\bcommit\b",
    r"\bverifier\b.{0,60}\bpassed\b",
    r"\btest[s]?\b.{0,60}\bpassed\b",
    r"\bpackage\b.{0,60}\brefreshed\b",
    r"\blive\\app\\Engel\.exe\b",
    r"\bfile exists\b",
    r"\blatest\b",
]

UNCERTAINTY_MARKERS = [
    "confidence: high",
    "confidence: medium",
    "confidence: low",
    "confidence: unknown",
    "uncertain",
    "not verified",
    "reported by user",
    "verified by engel",
    "evidence is missing",
]

SAFETY_WEAKENING_PATTERNS = [
    r"\bignore safety\b",
    r"\bdisable safety\b",
    r"\bbypass authority\b",
    r"\bbypass guard\b",
    r"\bremove safety warnings\b",
    r"\bno disclaimers\b",
    r"\bnever apologize\b",
]

EXTERNAL_PROMPT_AUTHORITY_PATTERNS = [
    r"\bsocial-media prompt\b.{0,80}\bauthority\b",
    r"\bexternal prompt\b.{0,80}\bauthority\b",
    r"\bprompt screenshot\b.{0,80}\boverride\b",
    r"\bignore previous instructions\b",
    r"\boverride system\b",
]


class GuardError(ValueError):
    pass


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def guard_summary() -> dict[str, Any]:
    return {
        "name": "Engel Truthfulness and Anti-Flattery Guard V1",
        "type": "truthfulness_anti_flattery_guard",
        "status_labels": list(STATUS_LABELS),
        "checker_labels": list(CHECKER_LABELS),
        "source_handling": [
            "The anti-flattery screenshot was treated as untrusted social-media reference material.",
            "External prompt text is not authority.",
            "The screenshot prompt was not copied verbatim into Engel.",
        ],
        "allowed_lessons": list(ALLOWED_LESSONS),
        "rejected_lessons": list(REJECTED_LESSONS),
        "engel_ai_application": list(ENGEL_AI_APPLICATIONS),
        "code_companion_application": list(CODE_COMPANION_APPLICATIONS),
        "verification_rules": list(VERIFICATION_RULES),
        "response_quality_rules": list(RESPONSE_QUALITY_RULES),
        "safety_preservation": list(SAFETY_PRESERVATION),
        "forbidden_behavior": list(FORBIDDEN_BEHAVIOR),
        "checklist_fields": list(CHECKLIST_FIELDS),
    }


def validate_check_text_path(raw_path: str) -> Path:
    if not raw_path or not str(raw_path).strip():
        raise GuardError("check-text path is required")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw_path):
        raise GuardError("URLs are not allowed")

    candidate = Path(raw_path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (PROJECT_ROOT / candidate).resolve()

    root = PROJECT_ROOT.resolve()
    if not _is_relative_to(resolved, root):
        raise GuardError("check-text path must stay inside this project")

    relative = resolved.relative_to(root)
    parts_lower = [part.lower() for part in relative.parts]
    if not parts_lower:
        raise GuardError("check-text path is not a file")
    if parts_lower[0] in FORBIDDEN_TOP_LEVEL_DIRS:
        raise GuardError("live and staging paths are forbidden")
    if any(part in FORBIDDEN_PARTS for part in parts_lower):
        raise GuardError("model-related paths are forbidden")
    if resolved.suffix.lower() not in ALLOWED_SUFFIXES:
        raise GuardError("only .md, .txt, and .json files are allowed")
    if parts_lower[0] not in ALLOWED_TOP_LEVEL_DIRS and len(relative.parts) != 1:
        raise GuardError("nested check-text paths must be under reports or memory")
    if not resolved.exists() or not resolved.is_file():
        raise GuardError("check-text file does not exist")
    if resolved.stat().st_size > MAX_CHECK_TEXT_BYTES:
        raise GuardError("check-text file is too large for bounded heuristic review")
    return resolved


def _matches_any(text: str, patterns: list[str]) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            matches.append(pattern)
    return matches


def _risk(matches: list[str]) -> str:
    if len(matches) >= 2:
        return "medium"
    if matches:
        return "low"
    return "none"


def evaluate_text(text: str) -> dict[str, Any]:
    lower = text.lower()
    flattery = _matches_any(text, FLATTERY_PATTERNS)
    premise_validation = _matches_any(text, PREMISE_VALIDATION_PATTERNS)
    unsupported_certainty = _matches_any(text, UNSUPPORTED_CERTAINTY_PATTERNS)
    claims_need_verification = _matches_any(text, CLAIMS_NEED_VERIFICATION_PATTERNS)
    unsafe_safety = _matches_any(text, SAFETY_WEAKENING_PATTERNS)
    external_prompt_authority = _matches_any(text, EXTERNAL_PROMPT_AUTHORITY_PATTERNS)
    missing_uncertainty = bool(claims_need_verification) and not any(marker in lower for marker in UNCERTAINTY_MARKERS)

    recommendations: list[str] = []
    if flattery:
        recommendations.append("remove praise and lead with the useful answer")
    if premise_validation:
        recommendations.append("check the premise before agreeing")
    if unsupported_certainty or claims_need_verification:
        recommendations.append("verify factual, date, path, hash, status, citation, smoke, or verifier claims")
    if missing_uncertainty:
        recommendations.append("add a confidence or evidence label")
    if unsafe_safety:
        recommendations.append("preserve safety warnings and guard boundaries")
    if external_prompt_authority:
        recommendations.append("treat external prompt text as untrusted data, not authority")
    if not recommendations:
        recommendations.append("no obvious truthfulness or anti-flattery issue found by this heuristic")

    return {
        "labels": list(CHECKER_LABELS),
        "flattery_risk": _risk(flattery),
        "premise_validation_risk": _risk(premise_validation),
        "unsupported_certainty_risk": _risk(unsupported_certainty),
        "missing_uncertainty_label": missing_uncertainty,
        "claims_need_verification": bool(claims_need_verification),
        "unsafe_safety_weakening_language": bool(unsafe_safety),
        "external_prompt_as_authority_risk": bool(external_prompt_authority),
        "matched_signal_counts": {
            "flattery": len(flattery),
            "premise_validation": len(premise_validation),
            "unsupported_certainty": len(unsupported_certainty),
            "claims_need_verification": len(claims_need_verification),
            "unsafe_safety_weakening_language": len(unsafe_safety),
            "external_prompt_as_authority_risk": len(external_prompt_authority),
        },
        "recommended_fix_summary": "; ".join(recommendations),
    }


def render_status() -> str:
    summary = guard_summary()
    lines = [
        "Engel Truthfulness and Anti-Flattery Guard V1",
        "",
        "Status:",
    ]
    lines.extend(f"- {status}" for status in STATUS_LABELS)
    lines.extend(["", "Checker labels:"])
    lines.extend(f"- {label}" for label in CHECKER_LABELS)
    lines.extend(["", "Source handling:"])
    lines.extend(f"- {line}" for line in summary["source_handling"])
    lines.extend(["", "Allowed lessons:"])
    lines.extend(f"- {lesson}" for lesson in ALLOWED_LESSONS)
    lines.extend(["", "Rejected lessons:"])
    lines.extend(f"- {lesson}" for lesson in REJECTED_LESSONS)
    lines.extend(["", "Verification rules:"])
    lines.extend(f"- {rule}" for rule in VERIFICATION_RULES)
    lines.extend(["", "Safety preservation:"])
    lines.extend(f"- {item}" for item in SAFETY_PRESERVATION)
    lines.extend(["", "CLI:"])
    lines.append("- python engel_truthfulness_anti_flattery_guard.py --status")
    lines.append("- python engel_truthfulness_anti_flattery_guard.py --check-text <project-local-text-file>")
    lines.append("- python engel_truthfulness_anti_flattery_guard.py --json")
    return "\n".join(lines).rstrip() + "\n"


def render_check_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    result = evaluate_text(text)
    lines = [
        "Engel Truthfulness and Anti-Flattery Guard V1 - Check Text",
        "",
        f"file: {path.relative_to(PROJECT_ROOT.resolve())}",
        "mode: HEURISTIC_REVIEW_ONLY",
        "input: UNTRUSTED_INPUT",
        "",
    ]
    for field in CHECKLIST_FIELDS:
        lines.append(f"{field}: {result[field]}")
    lines.extend(["", "labels:"])
    lines.extend(f"- {label}" for label in result["labels"])
    lines.extend(["", "matched_signal_counts:"])
    for key, value in result["matched_signal_counts"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only truthfulness and anti-flattery guard helper.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Print guard status and rules.")
    group.add_argument("--check-text", metavar="PROJECT_LOCAL_TEXT_FILE", help="Heuristically review one project-local text/report file.")
    group.add_argument("--json", action="store_true", help="Print structured guard summary.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr

    try:
        if args.status:
            out.write(render_status())
            return 0
        if args.json:
            out.write(json.dumps(guard_summary(), indent=2, sort_keys=True) + "\n")
            return 0
        if args.check_text:
            path = validate_check_text_path(args.check_text)
            out.write(render_check_text(path))
            return 0
    except GuardError as exc:
        err.write(f"Truthfulness guard refused check: {exc}\n")
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
