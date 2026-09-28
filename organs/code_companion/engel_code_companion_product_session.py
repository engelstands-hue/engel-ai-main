from __future__ import annotations

import re
from dataclasses import dataclass


SESSION_STATUS = "SESSION_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"
SELECT_PRODUCT_REQUIRED = "SELECT_PRODUCT_REQUIRED"
MAX_PROMPT_CHARS = 1000
MAX_SUMMARY_CHARS = 2000

APPROVAL_TOKENS = (
    "APPROVE_PRODUCT_PATCH",
    "APPROVE_LESSON_CANDIDATE",
    "APPROVE_MEMORY_CANDIDATE_PROPOSAL",
)

PRODUCT_REFERENCE_PATTERNS: tuple[str, ...] = (
    r"\bthis\s+(product|app|dashboard|tool)\b",
    r"\bsame\s+(product|app|dashboard|tool)\b",
    r"\bselected\s+product\b",
    r"\bcurrent\s+product\b",
    r"\bcontinue\s+(this|that)\b",
    r"\buse\s+the\s+same\s+product\b",
    r"\bwhat\s+(next|should\s+we\s+do\s+next)\b",
    r"\bmake\s+the\s+readme\s+better\s+too\b",
)

PATCH_REFERENCE_PATTERNS: tuple[str, ...] = (
    r"\bthat\s+patch\b",
    r"\bthe\s+patch\s+we\s+just\s+discussed\b",
    r"\bapply\s+(that|the)\s+patch\b",
)

LESSON_REFERENCE_PATTERNS: tuple[str, ...] = (
    r"\bcreate\s+that\s+lesson\b",
    r"\bthat\s+lesson\s+suggestion\b",
)

MEMORY_REFERENCE_PATTERNS: tuple[str, ...] = (
    r"\bmake\s+memory\s+from\s+that\b",
    r"\bmemory\s+from\s+that\b",
)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns)


def _bounded_text(text: str, max_chars: int) -> str:
    collapsed = " ".join(str(text or "").strip().split())
    if not collapsed:
        return ""
    for token in APPROVAL_TOKENS:
        collapsed = re.sub(re.escape(token), "[APPROVAL_TOKEN_IGNORED]", collapsed, flags=re.IGNORECASE)
    if len(collapsed) > max_chars:
        return collapsed[: max_chars - 3].rstrip() + "..."
    return collapsed


def _safe_slug(product_slug: str | None) -> str:
    slug = str(product_slug or "").strip()
    if not slug:
        return ""
    slug = slug.replace("-", "_").lower()
    slug = re.sub(r"[^a-z0-9_]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:120]


@dataclass
class ProductSessionMemory:
    selected_product: str = ""
    last_action: str = "NONE"
    last_talk_prompt: str = ""
    last_plan_kind: str = ""
    last_plan_summary: str = ""
    last_project_builder_plan: str = ""
    last_continue_product_plan: str = ""
    last_patch_proposal: str = ""
    last_patch_apply: str = ""
    last_health_delta: str = ""
    last_lesson_suggestion: str = ""
    last_lesson_review: str = ""
    last_safe_next_action: str = "Select a bounded product or ask Engel for a plan."

    def update_selected_product(self, product_slug: str | None) -> None:
        safe = _safe_slug(product_slug)
        self.selected_product = safe
        self.last_action = "Selected product" if safe else self.last_action
        if safe:
            self.last_safe_next_action = "Continue planning for " + safe + "; session context cannot approve actions."

    def record_talk_prompt(self, prompt: str) -> None:
        self.last_talk_prompt = _bounded_text(prompt, MAX_PROMPT_CHARS)
        self.last_action = "Talk prompt"
        if not self.last_safe_next_action:
            self.last_safe_next_action = "Review the plan; no session reference can approve apply/create actions."

    def record_plan(self, kind: str, summary: str, product_slug: str | None) -> None:
        safe = _safe_slug(product_slug)
        if safe:
            self.selected_product = safe
        plan_kind = _bounded_text(kind, 80) or "Plan"
        bounded_summary = _bounded_text(summary, MAX_SUMMARY_CHARS)
        self.last_plan_kind = plan_kind
        self.last_plan_summary = bounded_summary
        self.last_action = plan_kind
        if "project" in plan_kind.lower():
            self.last_project_builder_plan = bounded_summary
            self.last_safe_next_action = "Create only through the existing bounded product flow and explicit approvals."
        elif "continue" in plan_kind.lower():
            self.last_continue_product_plan = bounded_summary
            self.last_safe_next_action = "Review the Continue Product plan; apply patches only with explicit APPROVE_PRODUCT_PATCH."
        else:
            self.last_safe_next_action = "Review the plan; session context is not authority."

    def record_patch_proposal(self, product_slug: str, proposal_id_or_summary: str) -> None:
        self.update_selected_product(product_slug)
        self.last_patch_proposal = _bounded_text(proposal_id_or_summary, MAX_SUMMARY_CHARS)
        self.last_action = "Patch proposal"
        self.last_safe_next_action = "Review the patch proposal; apply only with explicit APPROVE_PRODUCT_PATCH from user input."

    def record_patch_apply(self, product_slug: str, receipt_id_or_summary: str) -> None:
        self.update_selected_product(product_slug)
        self.last_patch_apply = _bounded_text(receipt_id_or_summary, MAX_SUMMARY_CHARS)
        self.last_action = "Patch apply result"
        self.last_safe_next_action = "Review the patch result and health delta; lesson candidates still require explicit APPROVE_LESSON_CANDIDATE."

    def record_health_delta(self, product_slug: str, delta_id_or_summary: str) -> None:
        self.update_selected_product(product_slug)
        self.last_health_delta = _bounded_text(delta_id_or_summary, MAX_SUMMARY_CHARS)
        self.last_action = "Health delta"
        self.last_safe_next_action = "Review the Health Delta; no lesson or memory action is automatic."

    def record_lesson_suggestion(self, product_slug: str, summary: str) -> None:
        self.update_selected_product(product_slug)
        self.last_lesson_suggestion = _bounded_text(summary, MAX_SUMMARY_CHARS)
        self.last_action = "Lesson suggestion"
        self.last_safe_next_action = "Create a lesson candidate only with explicit APPROVE_LESSON_CANDIDATE."

    def record_lesson_review(self, product_slug: str, review_id_or_summary: str) -> None:
        self.update_selected_product(product_slug)
        self.last_lesson_review = _bounded_text(review_id_or_summary, MAX_SUMMARY_CHARS)
        self.last_action = "Lesson review"
        self.last_safe_next_action = "Propose a memory candidate only through the explicit memory-candidate approval flow."

    def recommend_session_next_action(self) -> str:
        if self.last_safe_next_action:
            return self.last_safe_next_action
        if self.last_patch_proposal:
            return "Review that patch proposal; apply requires explicit APPROVE_PRODUCT_PATCH."
        if self.last_lesson_suggestion:
            return "Review that lesson suggestion; candidate creation requires explicit APPROVE_LESSON_CANDIDATE."
        if self.selected_product:
            return "Continue planning for " + self.selected_product + "; no session action is authorized."
        return "Select a bounded product or ask Engel for a plan."

    def resolve_product_reference(self, text: str) -> str | None:
        if not _matches_any(text, PRODUCT_REFERENCE_PATTERNS):
            return None
        return self.selected_product or SELECT_PRODUCT_REQUIRED

    def resolve_patch_reference(self, text: str) -> str | None:
        if not _matches_any(text, PATCH_REFERENCE_PATTERNS):
            return None
        return self.last_patch_proposal or SELECT_PRODUCT_REQUIRED

    def resolve_lesson_reference(self, text: str) -> str | None:
        if not _matches_any(text, LESSON_REFERENCE_PATTERNS):
            return None
        return self.last_lesson_suggestion or SELECT_PRODUCT_REQUIRED

    def resolve_memory_reference(self, text: str) -> str | None:
        if not _matches_any(text, MEMORY_REFERENCE_PATTERNS):
            return None
        return self.last_lesson_review or SELECT_PRODUCT_REQUIRED

    def session_context_authorizes_patch_apply(self, _text: str = "") -> bool:
        return False

    def session_context_authorizes_lesson_candidate(self, _text: str = "") -> bool:
        return False

    def session_context_authorizes_memory_candidate(self, _text: str = "") -> bool:
        return False

    def reset(self) -> None:
        self.selected_product = ""
        self.last_action = "NONE"
        self.last_talk_prompt = ""
        self.last_plan_kind = ""
        self.last_plan_summary = ""
        self.last_project_builder_plan = ""
        self.last_continue_product_plan = ""
        self.last_patch_proposal = ""
        self.last_patch_apply = ""
        self.last_health_delta = ""
        self.last_lesson_suggestion = ""
        self.last_lesson_review = ""
        self.last_safe_next_action = "Select a bounded product or ask Engel for a plan."

    def render_compact_status(self) -> str:
        return (
            "Session: "
            + (self.selected_product or "NONE")
            + " | "
            + (self.last_action or "NONE")
            + " | "
            + self.recommend_session_next_action()
        )

    def render_session_status(self) -> str:
        return "\n".join(
            [
                "# Engel Product Session Memory",
                "",
                "Status:",
                SESSION_STATUS,
                "",
                "Selected product:",
                self.selected_product or "NONE",
                "",
                "Last action:",
                self.last_action or "NONE",
                "",
                "Last Talk prompt:",
                self.last_talk_prompt or "NONE",
                "",
                "Last plan:",
                self.last_plan_summary or "NONE",
                "",
                "Last safe next action:",
                self.recommend_session_next_action(),
                "",
                "Boundaries:",
                "- Session memory trusted as authority: NO",
                "- Session memory is authority: NO",
                "- Approval tokens from session accepted: NO",
                "- Trusted memory write: NO",
                "- Product edit: NO",
                "- Runtime edit: NO",
                "- Code execution: NO",
                "",
                "Use:",
                "Session memory helps continue the current product conversation only.",
                "It cannot approve patch apply, lesson candidate creation, or memory candidate creation.",
                "Product Session Memory != Trusted Memory.",
                "Product Session Memory != Project Memory.",
                "Product Session Memory != Lesson Candidate.",
                "Product Session Memory != Memory Candidate.",
            ]
        )


def create_product_session() -> ProductSessionMemory:
    return ProductSessionMemory()
