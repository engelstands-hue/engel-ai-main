from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import engel_code_companion_product_session as product_session
import engel_research_understanding_library as understanding_library


COMMAND_STATUS = "COMMAND_RESOLUTION / NOT_TRUSTED_MEMORY / NOT_APPLIED"
UNKNOWN_INTENT = "UNKNOWN_INTENT"
SELECT_PRODUCT_REQUIRED = "SELECT_PRODUCT_REQUIRED"
SELECT_RESEARCH_SOURCE_REQUIRED = "SELECT_RESEARCH_SOURCE_REQUIRED"
NONE_FOR_PLAN_ONLY = "NONE_FOR_PLAN_ONLY"

APPROVE_PRODUCT_PATCH = "APPROVE_PRODUCT_PATCH"
APPROVE_LESSON_CANDIDATE = "APPROVE_LESSON_CANDIDATE"
APPROVE_MEMORY_CANDIDATE_PROPOSAL = "APPROVE_MEMORY_CANDIDATE_PROPOSAL"

APPROVAL_TOKENS = (
    APPROVE_PRODUCT_PATCH,
    APPROVE_LESSON_CANDIDATE,
    APPROVE_MEMORY_CANDIDATE_PROPOSAL,
)

PRODUCT_REQUIRED_INTENTS = {
    "continue_product",
    "improve_product",
    "patch_proposal",
    "apply_patch",
    "product_health",
    "health_delta",
    "product_cycle",
    "product_context",
    "product_session_memory",
    "readme_manifest_proposal",
    "product_test_plan",
    "product_preview",
    "product_open_folder",
    "product_workbench",
    "product_next_safe_action",
    "product_explain_status",
    "create_lesson_candidate",
    "review_lesson_candidate",
    "patch_lesson_review",
    "product_lesson_review",
    "memory_candidate_proposal",
    "memory_candidate_review",
    "memory_candidate_handoff",
}

RESEARCH_SOURCE_REQUIRED_INTENTS = {
    "summarize_research",
    "classify_research",
    "extract_findings",
    "extract_risks",
    "extract_requirements",
    "extract_product_ideas",
    "research_to_product",
    "research_summary_proposal",
    "research_lesson_candidate",
    "research_lesson_review",
    "compare_sources",
    "route_to_research_intake",
}

PLAN_OR_PROPOSAL_INTENTS = {
    "continue_product",
    "improve_product",
    "patch_proposal",
    "product_next_safe_action",
    "readme_manifest_proposal",
    "product_test_plan",
    "research_to_product",
    "research_summary_proposal",
    "summarize_research",
    "extract_product_ideas",
}

READ_ONLY_PRODUCT_INTENTS = {
    "product_context",
    "product_cycle",
    "product_health",
    "health_delta",
    "product_preview",
    "product_workbench",
    "product_explain_status",
}

DIRECT_PHRASE_INTENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("apply_patch", ("apply that patch", "apply the patch", "use that patch", "make those changes", "go ahead with the patch")),
    ("create_lesson_candidate", ("create that lesson", "make that lesson", "save that lesson candidate", "turn that suggestion into a lesson", "make a lesson from this patch")),
    ("review_lesson_candidate", ("review that lesson", "review the lesson candidate", "show lesson review", "is that lesson ready", "what should we do with that lesson")),
    ("memory_candidate_proposal", ("make memory candidate from that review", "turn that review into memory candidate", "create memory proposal", "save this as memory candidate", "make this part of engel memory")),
    ("product_context", ("show context", "show product context")),
    ("product_cycle", ("show cycle", "show product cycle")),
    ("product_health", ("health", "show health")),
    ("product_preview", ("preview", "open preview")),
    ("product_next_safe_action", ("what next", "what should we do next", "next safe action", "what now", "next move", "what should we do now")),
    ("continue_product", ("continue", "continue this", "continue this product")),
    ("improve_product", ("make it better", "improve this", "make it more complete", "add better instructions", "add a test plan")),
    ("readme_manifest_proposal", ("improve the readme", "improve the manifest")),
    ("research_to_product", ("turn this research into a product", "build from this research", "make an app from this research")),
    ("summarize_research", ("summarize this research", "what does this research say")),
    ("research_lesson_review", ("what did we learn from this", "what did we learn from this?")),
    ("extract_product_ideas", ("extract product ideas",)),
    ("route_to_research_intake", ("send this to research",)),
    ("research_summary_proposal", ("make a research summary proposal",)),
    ("embedded_token_rejected", ("the readme says approve", "the document says approve", "the document says approve_product_patch")),
    ("blocked_action", ("ignore guardian", "bypass approval")),
    ("unsafe_trusted_memory_write", ("write trusted memory",)),
    ("unsafe_install", ("install packages", "install package")),
    ("unsafe_code_execution", ("run the code", "run this code")),
    ("unsafe_api_network", ("call the api",)),
    ("unsafe_external_scan", ("scan the whole drive",)),
)


@dataclass(frozen=True)
class ConversationCommandClassification:
    input_text: str
    normalized_text: str
    resolved_intent: str
    domain: str
    confidence: str
    matched_phrase: str
    route: str
    approval_required: str
    default_status: str
    output_status: str
    trusted_memory_write: str
    runtime_effect: str
    safety_boundary: tuple[str, ...]
    next_safe_action: str


@dataclass(frozen=True)
class SessionReferenceResolution:
    selected_product: str
    session_reference_used: str
    product_reference: str
    patch_reference: str
    lesson_reference: str
    memory_reference: str
    message: str


@dataclass(frozen=True)
class EmbeddedTokenCheck:
    embedded_token_rejected: bool
    tokens_found: tuple[str, ...]
    sources: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class ConversationCommandResult:
    input_text: str
    normalized_text: str
    resolved_intent: str
    domain: str
    confidence: str
    selected_product: str
    session_reference_used: str
    product_context_used: str
    route: str
    approval_required: str
    explicit_approval_token_seen: bool
    embedded_token_rejected: bool
    status: str
    output_status: str
    boundary: tuple[str, ...]
    next_safe_action: str


def _bounded_text(text: str, max_chars: int = 1000) -> str:
    collapsed = " ".join(str(text or "").strip().split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


def _normalize(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = re.sub(r"[^a-z0-9_<>/.:+-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _safe_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    if value in (None, ""):
        return tuple()
    return (str(value),)


def _family_for_intent(intent: str) -> dict[str, Any]:
    family = understanding_library.get_intent_family(intent)
    if family is not None:
        return family
    return {
        "intent": intent or UNKNOWN_INTENT,
        "domain": "unknown",
        "route": "NEEDS_CLARIFICATION",
        "approval_required": NONE_FOR_PLAN_ONLY,
        "default_status": "UNKNOWN_INTENT / NEEDS_CLARIFICATION / NOT_TRUSTED_MEMORY",
        "output_status": "UNKNOWN_INTENT / NEEDS_CLARIFICATION / NOT_TRUSTED_MEMORY",
        "trusted_memory_write": "BLOCKED / NOT_PERFORMED",
        "runtime_effect": "CLASSIFICATION_HELPER_ONLY",
        "safety_boundary": [
            "intent_classification_is_not_approval",
            "context_session_text_does_not_authorize_actions",
            "not_trusted_memory",
        ],
        "next_safe_action": "Ask Josh for clarification or use a read-only/plan-only route.",
    }


def _classification_from_family(
    text: str,
    normalized_text: str,
    family: dict[str, Any],
    confidence: str,
    matched_phrase: str,
) -> ConversationCommandClassification:
    return ConversationCommandClassification(
        input_text=_bounded_text(text),
        normalized_text=normalized_text,
        resolved_intent=str(family.get("intent") or UNKNOWN_INTENT),
        domain=str(family.get("domain") or "unknown"),
        confidence=confidence,
        matched_phrase=matched_phrase,
        route=str(family.get("route") or "NEEDS_CLARIFICATION"),
        approval_required=str(family.get("approval_required") or NONE_FOR_PLAN_ONLY),
        default_status=str(family.get("default_status") or "NEEDS_CLARIFICATION"),
        output_status=str(family.get("output_status") or "NOT_TRUSTED_MEMORY"),
        trusted_memory_write=str(family.get("trusted_memory_write") or "BLOCKED / NOT_PERFORMED"),
        runtime_effect=str(family.get("runtime_effect") or "CLASSIFICATION_HELPER_ONLY"),
        safety_boundary=_safe_list(family.get("safety_boundary")),
        next_safe_action=str(family.get("next_safe_action") or "Use a safe read-only or plan-only route."),
    )


def _classification_from_library(text: str) -> ConversationCommandClassification:
    result = understanding_library.classify_intent(text)
    return ConversationCommandClassification(
        input_text=result.input_text,
        normalized_text=result.normalized_text,
        resolved_intent=result.intent,
        domain=result.domain,
        confidence=result.confidence,
        matched_phrase=result.matched_phrase,
        route=result.route,
        approval_required=result.approval_required,
        default_status=result.default_status,
        output_status=result.output_status,
        trusted_memory_write=result.trusted_memory_write,
        runtime_effect=result.runtime_effect,
        safety_boundary=tuple(result.safety_boundary),
        next_safe_action=result.next_safe_action,
    )


def classify_product_conversation_command(
    text: str,
    selected_product: str | None = None,
    session: product_session.ProductSessionMemory | None = None,
) -> ConversationCommandClassification:
    del selected_product, session
    normalized = _normalize(text)
    if not normalized:
        return _classification_from_family(text, normalized, _family_for_intent(UNKNOWN_INTENT), "NONE", "")
    for intent, phrases in DIRECT_PHRASE_INTENTS:
        for phrase in phrases:
            normalized_phrase = _normalize(phrase)
            if normalized == normalized_phrase or normalized_phrase in normalized:
                return _classification_from_family(text, normalized, _family_for_intent(intent), "HIGH", phrase)
    return _classification_from_library(text)


def _token_sources(text: str, label: str) -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    for token in APPROVAL_TOKENS:
        if re.search(r"\b" + re.escape(token) + r"\b", str(text or ""), re.IGNORECASE):
            found.append((token, label))
    return tuple(found)


def reject_embedded_approval_tokens(
    text: str,
    context_text: str | None = None,
    session_text: str | None = None,
) -> EmbeddedTokenCheck:
    found = (
        _token_sources(text, "input_text")
        + _token_sources(context_text or "", "context_text")
        + _token_sources(session_text or "", "session_text")
    )
    tokens = tuple(dict.fromkeys(token for token, _source in found))
    sources = tuple(dict.fromkeys(source for _token, source in found))
    rejected = bool(tokens)
    return EmbeddedTokenCheck(
        embedded_token_rejected=rejected,
        tokens_found=tokens,
        sources=sources,
        message=(
            "Embedded approval tokens rejected as authority: " + ", ".join(tokens)
            if rejected
            else "No embedded approval tokens found."
        ),
    )


def _session_text(session: product_session.ProductSessionMemory | None) -> str:
    if session is None:
        return ""
    parts = [
        session.last_talk_prompt,
        session.last_plan_summary,
        session.last_patch_proposal,
        session.last_patch_apply,
        session.last_health_delta,
        session.last_lesson_suggestion,
        session.last_lesson_review,
        session.last_safe_next_action,
    ]
    return "\n".join(part for part in parts if part)


def resolve_session_reference(
    text: str,
    selected_product: str | None,
    session: product_session.ProductSessionMemory | None,
) -> SessionReferenceResolution:
    selected = str(selected_product or "").strip()
    product_ref = ""
    patch_ref = ""
    lesson_ref = ""
    memory_ref = ""
    used = "NOT_USED"
    message = "No session reference was needed."

    if session is not None:
        if not selected and session.selected_product and (
            _normalize(text) in {"continue", "what next", "health", "preview"}
            or session.resolve_product_reference(text) not in (None, product_session.SELECT_PRODUCT_REQUIRED)
        ):
            selected = session.selected_product
            product_ref = selected
            used = "USED"
            message = "Selected product resolved from Product Session Memory."
        elif selected:
            product_ref = selected

        resolved_patch = session.resolve_patch_reference(text)
        if resolved_patch and resolved_patch != product_session.SELECT_PRODUCT_REQUIRED:
            patch_ref = resolved_patch
            used = "USED"
            message = "Patch reference resolved from Product Session Memory."

        resolved_lesson = session.resolve_lesson_reference(text)
        if resolved_lesson and resolved_lesson != product_session.SELECT_PRODUCT_REQUIRED:
            lesson_ref = resolved_lesson
            used = "USED"
            message = "Lesson reference resolved from Product Session Memory."

        resolved_memory = session.resolve_memory_reference(text)
        if resolved_memory and resolved_memory != product_session.SELECT_PRODUCT_REQUIRED:
            memory_ref = resolved_memory
            used = "USED"
            message = "Lesson review reference resolved from Product Session Memory."

        normalized = _normalize(text)
        if not memory_ref and "memory candidate" in normalized and session.last_lesson_review:
            memory_ref = session.last_lesson_review
            used = "USED"
            message = "Lesson review reference resolved from Product Session Memory."
        if not lesson_ref and "lesson" in normalized and session.last_lesson_suggestion:
            lesson_ref = session.last_lesson_suggestion
            used = "USED"
            message = "Lesson reference resolved from Product Session Memory."
        if not patch_ref and "patch" in normalized and session.last_patch_proposal:
            patch_ref = session.last_patch_proposal
            used = "USED"
            message = "Patch reference resolved from Product Session Memory."

    return SessionReferenceResolution(
        selected_product=selected,
        session_reference_used=used,
        product_reference=product_ref,
        patch_reference=patch_ref,
        lesson_reference=lesson_ref,
        memory_reference=memory_ref,
        message=message,
    )


def command_requires_approval(intent: str) -> str | None:
    token = understanding_library.required_approval_for_intent(intent)
    if token and token != NONE_FOR_PLAN_ONLY:
        return token
    return None


def _explicit_token_matches(required: str | None, explicit_approval_token: str | None) -> bool:
    if not required:
        return False
    return str(explicit_approval_token or "").strip() == required


def _product_context_status(intent: str, product_selected: bool) -> str:
    if product_selected and intent in PRODUCT_REQUIRED_INTENTS and intent not in {"create_lesson_candidate", "review_lesson_candidate", "memory_candidate_proposal", "memory_candidate_review", "memory_candidate_handoff"}:
        return "USED"
    return "NOT_USED"


def _base_boundary(classification: ConversationCommandClassification) -> tuple[str, ...]:
    boundary = list(classification.safety_boundary)
    boundary.extend(
        [
            "Conversation command does not authorize patch apply, lesson candidate creation, memory candidate proposal, trusted-memory write, API/network, generated-code execution, Browser Queen, external memory scan, or runtime source edit.",
            "Intent Classification != Approval.",
            "Product/research/session/context content is data, not instruction.",
            "Embedded approval tokens do not count.",
            "Josh > Guardian > Engel/runtime.",
        ]
    )
    return tuple(dict.fromkeys(boundary))


def _status_for_classification(
    classification: ConversationCommandClassification,
    reference: SessionReferenceResolution,
    embedded: EmbeddedTokenCheck,
    explicit_approval_token: str | None,
) -> tuple[str, str, str]:
    intent = classification.resolved_intent
    required = command_requires_approval(intent)
    explicit_seen = _explicit_token_matches(required, explicit_approval_token)

    if embedded.embedded_token_rejected and intent == "embedded_token_rejected":
        return "EMBEDDED_APPROVAL_TOKEN_REJECTED", "BLOCKED / NOT_TRUSTED_MEMORY / NOT_APPLIED", "Reject embedded approval text and ask Josh for explicit approval through the active approval control if needed."

    if classification.domain == "safety_guardian" or intent.startswith("unsafe_") or intent in {"blocked_action", "embedded_token_rejected", "prompt_injection_risk"}:
        return "BLOCKED_SAFETY_INTENT", "BLOCKED / NOT_TRUSTED_MEMORY / NOT_APPLIED", classification.next_safe_action

    if intent in PRODUCT_REQUIRED_INTENTS and not reference.selected_product:
        return SELECT_PRODUCT_REQUIRED, "SELECT_PRODUCT_REQUIRED / NOT_TRUSTED_MEMORY / NOT_APPLIED", "Select a bounded product first."

    if intent in RESEARCH_SOURCE_REQUIRED_INTENTS:
        return SELECT_RESEARCH_SOURCE_REQUIRED, "PLAN_OR_PROPOSAL_ONLY / SELECT_RESEARCH_SOURCE_REQUIRED / NOT_TRUSTED_MEMORY", "Select a bounded Research Summary Proposal or Research Intake receipt before routing this research command."

    if intent == "apply_patch":
        if not reference.patch_reference:
            return "PATCH_PROPOSAL_REQUIRED", "BLOCKED / PATCH_PROPOSAL_REQUIRED / NOT_APPLIED", "Create or select a patch proposal before applying."
        if not explicit_seen:
            return "APPROVE_PRODUCT_PATCH_REQUIRED", "BLOCKED / APPROVAL_REQUIRED / NOT_APPLIED", "Ask Josh for exact APPROVE_PRODUCT_PATCH in the existing approval input/control."
        return "ROUTE_TO_EXISTING_PRODUCT_PATCH_APPLY", "PRODUCT_ONLY / APPROVAL_GATED / NOT_TRUSTED_MEMORY", "Route to the existing Product Patch Apply flow; do not edit runtime source or execute generated code."

    if intent in {"create_lesson_candidate", "research_lesson_candidate"}:
        if not reference.lesson_reference and not reference.patch_reference:
            return "LESSON_REFERENCE_REQUIRED", "BLOCKED / LESSON_REFERENCE_REQUIRED / NOT_APPLIED", "Create or select a lesson suggestion, patch receipt, or lesson candidate source first."
        if not explicit_seen:
            return "APPROVE_LESSON_CANDIDATE_REQUIRED", "BLOCKED / APPROVAL_REQUIRED / NOT_APPLIED", "Ask Josh for exact APPROVE_LESSON_CANDIDATE in the existing approval input/control."
        return "ROUTE_TO_EXISTING_LESSON_CANDIDATE_BRIDGE", "LESSON_CANDIDATE_RECEIPT_ONLY / APPROVAL_GATED / NOT_TRUSTED_MEMORY", "Route to the existing Lesson Candidate bridge; this does not write trusted memory."

    if intent in {"memory_candidate_proposal", "memory_candidate_handoff"}:
        if not reference.memory_reference:
            return "LESSON_REVIEW_REQUIRED", "BLOCKED / LESSON_REVIEW_REQUIRED / NOT_APPLIED", "Review a lesson first before proposing a memory candidate."
        if not explicit_seen:
            return "APPROVE_MEMORY_CANDIDATE_PROPOSAL_REQUIRED", "BLOCKED / APPROVAL_REQUIRED / NOT_APPLIED", "Ask Josh for exact APPROVE_MEMORY_CANDIDATE_PROPOSAL in the existing approval input/control."
        return "ROUTE_TO_EXISTING_MEMORY_CANDIDATE_PROPOSAL_WORKFLOW", "MEMORY_CANDIDATE_PROPOSAL_ONLY / APPROVAL_GATED / NOT_TRUSTED_MEMORY", "Route to the existing Memory Candidate Handoff/proposal workflow; this does not write trusted memory."

    if intent in {"review_lesson_candidate", "patch_lesson_review", "product_lesson_review", "research_lesson_review"}:
        return "READY_FOR_JOSH_REVIEW", "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED", "Route to lesson review only; do not apply the lesson or create memory."

    if intent in READ_ONLY_PRODUCT_INTENTS:
        return "READ_ONLY_STATUS", "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED", classification.next_safe_action

    if intent in PLAN_OR_PROPOSAL_INTENTS:
        output = "PATCH_PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED" if intent in {"improve_product", "patch_proposal", "readme_manifest_proposal", "product_test_plan"} else "PLAN_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"
        return output.split(" / ", 1)[0], output, classification.next_safe_action

    if intent == UNKNOWN_INTENT:
        return "UNKNOWN_INTENT / NEEDS_CLARIFICATION", "UNKNOWN_INTENT / NEEDS_CLARIFICATION / NOT_TRUSTED_MEMORY", "Ask Josh for clarification or choose a read-only/plan-only route."

    return classification.default_status, classification.output_status, classification.next_safe_action


def resolve_product_conversation_command(
    text: str,
    selected_product: str | None = None,
    session: product_session.ProductSessionMemory | None = None,
    explicit_approval_token: str | None = None,
) -> ConversationCommandResult:
    classification = classify_product_conversation_command(text, selected_product, session)
    reference = resolve_session_reference(text, selected_product, session)
    embedded = reject_embedded_approval_tokens(text, session_text=_session_text(session))
    required = command_requires_approval(classification.resolved_intent)
    explicit_seen = _explicit_token_matches(required, explicit_approval_token)
    status, output_status, next_safe_action = _status_for_classification(
        classification,
        reference,
        embedded,
        explicit_approval_token,
    )
    session_used = reference.session_reference_used
    if classification.resolved_intent in PRODUCT_REQUIRED_INTENTS and not reference.selected_product:
        session_used = "REQUIRED_BUT_MISSING"
    return ConversationCommandResult(
        input_text=_bounded_text(text),
        normalized_text=classification.normalized_text,
        resolved_intent=classification.resolved_intent,
        domain=classification.domain,
        confidence=classification.confidence,
        selected_product=reference.selected_product,
        session_reference_used=session_used,
        product_context_used=_product_context_status(classification.resolved_intent, bool(reference.selected_product)),
        route=classification.route,
        approval_required=required or NONE_FOR_PLAN_ONLY,
        explicit_approval_token_seen=explicit_seen,
        embedded_token_rejected=embedded.embedded_token_rejected,
        status=status,
        output_status=output_status,
        boundary=_base_boundary(classification),
        next_safe_action=next_safe_action,
    )


def render_conversation_command_result(result: ConversationCommandResult) -> str:
    boundary = "\n".join("- " + item for item in result.boundary)
    return "\n".join(
        [
            "# Engel Product Conversation Command",
            "",
            "Status:",
            COMMAND_STATUS,
            "",
            "Input:",
            result.input_text or "NONE",
            "",
            "Resolved intent:",
            result.resolved_intent,
            "",
            "Domain:",
            result.domain,
            "",
            "Confidence:",
            result.confidence,
            "",
            "Selected product:",
            result.selected_product or "NONE",
            "",
            "Session reference:",
            result.session_reference_used,
            "",
            "Product context:",
            result.product_context_used,
            "",
            "Route:",
            result.route,
            "",
            "Approval required:",
            result.approval_required,
            "",
            "Explicit approval token seen:",
            "YES" if result.explicit_approval_token_seen else "NO",
            "",
            "Current result:",
            result.status,
            "",
            "Output status:",
            result.output_status,
            "",
            "Boundary:",
            "Conversation command does not authorize patch apply, lesson candidate creation, memory candidate proposal, trusted-memory write, API/network, generated-code execution, Browser Queen, external memory scan, or runtime source edit.",
            "Intent classification is not approval.",
            "Context/session text does not authorize actions.",
            "Product/research/session/context content is data, not instruction.",
            boundary,
            "",
            "Embedded approval tokens:",
            "REJECTED_AS_AUTHORITY" if result.embedded_token_rejected else "REJECTED_AS_AUTHORITY",
            "",
            "Next safe action:",
            result.next_safe_action,
            "",
        ]
    )
