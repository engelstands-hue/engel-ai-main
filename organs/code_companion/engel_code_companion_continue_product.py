from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import engel_code_companion_contextual_talk as contextual_talk
import engel_code_companion_patch_proposals as patch_proposals
import engel_code_companion_product_cycle_dashboard as cycle_dashboard
import engel_code_companion_products as products
import engel_untrusted_content_guard as untrusted_content_guard


AUTHORITY = "Josh > Guardian > Engel/runtime"
CONTINUE_PRODUCT_PLAN = "CONTINUE_PRODUCT_PLAN"
CONTINUE_PRODUCT_STATUS = "PLAN_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"
SELECT_PRODUCT_REQUIRED = "SELECT_PRODUCT_REQUIRED"
BLOCKED_UNSAFE_CONTINUE_PRODUCT_REQUEST = "BLOCKED_UNSAFE_CONTINUE_PRODUCT_REQUEST"

CONTINUE_PATTERNS: tuple[str, ...] = (
    r"\bcontinue\s+that\b",
    r"\bcontinue\s+this\b",
    r"\bcontinue\s+this\s+product\b",
    r"\bcontinue\s+selected\s+product\b",
    r"\bcontinue\s+the\s+same\s+product\b",
    r"\bwhat\s+next\b",
    r"\bwhat\s+should\s+we\s+do\s+next\b",
    r"\bnext\s+with\s+this\s+(app|product|dashboard|tool)\b",
    r"\bnext\s+safe\s+action\b",
    r"\badd\s+a\s+small\s+next\s+feature\s+proposal\b",
    r"\bnext\s+feature\s+proposal\b",
    r"\bmake\s+this\s+product\s+more\s+complete\b",
    r"\bmake\s+this\s+app\s+more\s+complete\b",
    r"\bimprove\s+this\s+product'?s?\s+instructions\b",
    r"\bimprove\s+this\s+app'?s?\s+instructions\b",
    r"\bimprove\s+selected\s+product'?s?\s+instructions\b",
)

UNSAFE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("runtime source edit", r"\b(edit|modify|patch|rewrite|change)\b.{0,60}\b(engel runtime|runtime source|engel source|engel_companion)\b"),
    ("package install", r"\b(install|pip install|npm install|add package|download package)\b"),
    ("api or network", r"\b(api|network|provider|requests|socket|websocket|fetch|scrape)\b"),
    ("execute code", r"\b(execute|run)\b.{0,40}\b(generated code|product code|now|immediately)\b"),
    ("trusted memory write", r"\b(write|update|store|make permanent)\b.{0,40}\b(trusted memory|memory index|durable memory)\b"),
    ("browser queen", r"\b(browser queen|launch browser|open browser|chrome|edge|firefox)\b"),
    ("external memory scan", r"\b(scan|crawl|index)\b.{0,40}\b(external memory|e:\\|g:\\)\b"),
    ("auto approval", r"\b(auto[- ]?approve|APPROVE_[A-Z_]+)\b"),
)


@dataclass(frozen=True)
class ContinueProductPlan:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    current_state: str
    recommended_next_action: str
    action_kind: str
    patch_proposal_text: str = ""
    context_text: str = ""
    guardian_review: tuple[str, ...] = ()
    safety_notes: tuple[str, ...] = ()
    message: str = ""
    blocked_reason: str = ""


def is_continue_product_request(text: str) -> bool:
    lowered = (text or "").lower()
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in CONTINUE_PATTERNS):
        return True
    if "this product" in lowered and any(phrase in lowered for phrase in ("what next", "next step", "more complete", "continue")):
        return True
    if "this app" in lowered and any(phrase in lowered for phrase in ("what next", "next step", "more complete", "continue")):
        return True
    return False


def _unsafe_markers(text: str) -> tuple[str, ...]:
    markers: list[str] = []
    lowered = (text or "").lower()
    for label, pattern in UNSAFE_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            markers.append(label)
    guard = untrusted_content_guard.detect_prompt_injection_markers(text or "")
    if guard.authority_attack:
        markers.append("authority attack")
    if guard.tool_attack:
        markers.append("tool attack")
    if guard.memory_attack:
        markers.append("memory attack")
    return tuple(dict.fromkeys(markers))


def _product_root(product_slug: str) -> tuple[str, Path]:
    safe_slug = products.safe_product_slug(product_slug)
    if safe_slug != str(product_slug or "").strip():
        raise ValueError("Unsafe product slug rejected.")
    product_path = products.product_path_for_slug(safe_slug)
    if not products.is_safe_product_path(product_path):
        raise ValueError("Selected product must stay under products.")
    if not product_path.exists() or not product_path.is_dir():
        raise ValueError("Selected product does not exist under products.")
    if product_path.is_symlink():
        raise ValueError("Selected product symlinks are blocked.")
    return safe_slug, product_path


def _current_state_text(dashboard: cycle_dashboard.ProductCycleDashboard) -> str:
    return "\n".join(
        [
            "- Health: " + dashboard.health_status,
            "- Improvement proposal: " + dashboard.improvement_proposal_status,
            "- Patch proposal: " + dashboard.patch_proposal_status,
            "- Patch apply receipt: " + (dashboard.latest_patch_apply_receipt.name if dashboard.latest_patch_apply_receipt else "missing"),
            "- Lesson suggestion: " + dashboard.lesson_suggestion_status,
            "- Lesson candidates: " + str(dashboard.lesson_candidate_count),
            "- Lesson reviews: " + str(dashboard.lesson_review_count),
            "- Trusted memory: BLOCKED / NOT_PERFORMED",
        ]
    )


def _choose_action_kind(text: str, dashboard: cycle_dashboard.ProductCycleDashboard) -> tuple[str, str]:
    lowered = (text or "").lower()
    if dashboard.health_status == "BLOCKED" or "health" in lowered:
        return "health_review", "Review product health and resolve blocked metadata before patching."
    if dashboard.lesson_suggestion_status.startswith("PRESENT") and dashboard.lesson_candidate_count == 0:
        return "lesson_candidate_suggestion", "Review the existing patch lesson suggestion; create a candidate only with APPROVE_LESSON_CANDIDATE."
    if "feature" in lowered or "more complete" in lowered or "next step" in lowered:
        return "product_plan_extension", "Draft a small product plan extension before proposing file changes."
    if any(word in lowered for word in ("instruction", "readme", "docs", "manifest", "copy", "patch", "improve")):
        return "patch_proposal", "Create a product-only patch proposal with diff preview."
    if dashboard.latest_patch_apply_receipt is None:
        return "patch_proposal", "Create a conservative product-only patch proposal with diff preview."
    return "product_plan_extension", "Review the cycle and choose a small product plan extension; no automatic action taken."


def _patch_request_for_action(text: str, action_kind: str) -> str:
    lowered = (text or "").lower()
    if action_kind != "patch_proposal":
        return ""
    if "instruction" in lowered or "readme" in lowered or "docs" in lowered:
        return "Engel, improve this product's README and instructions."
    if "manifest" in lowered:
        return "Engel, improve this product's manifest and README."
    if "copy" in lowered:
        return "Engel, improve this product's dashboard copy and README."
    return "Engel, improve this product's README and add a smoke test."


def build_continue_product_plan(text: str, selected_product: str | None = None) -> ContinueProductPlan:
    idea = " ".join((text or "").split())
    markers = _unsafe_markers(idea)
    if markers:
        return ContinueProductPlan(
            ok=False,
            status=BLOCKED_UNSAFE_CONTINUE_PRODUCT_REQUEST,
            product_slug=str(selected_product or ""),
            product_path=None,
            current_state="blocked",
            recommended_next_action="Request blocked by Guardian review.",
            action_kind="blocked",
            context_text=contextual_talk.render_context_for_selected_product(None),
            guardian_review=(
                "Product files changed now: NO",
                "Runtime source edit: NO",
                "Code execution: NO",
                "Package install: NO",
                "API/network: NO",
                "Trusted memory write: NO",
                f"{AUTHORITY} preserved: YES",
            ),
            safety_notes=("Unsafe request markers: " + ", ".join(markers), "No files were changed."),
            blocked_reason=BLOCKED_UNSAFE_CONTINUE_PRODUCT_REQUEST,
        )
    if not str(selected_product or "").strip():
        return ContinueProductPlan(
            ok=False,
            status=SELECT_PRODUCT_REQUIRED,
            product_slug="",
            product_path=None,
            current_state="No selected product.",
            recommended_next_action="Select a bounded product first.",
            action_kind="select_product",
            context_text=contextual_talk.render_context_for_selected_product(None),
            guardian_review=(
                "Product files changed now: NO",
                "Runtime source edit: NO",
                "Code execution: NO",
                "Package install: NO",
                "API/network: NO",
                "Trusted memory write: NO",
                "Approval required before apply: YES",
                f"{AUTHORITY} preserved: YES",
            ),
            safety_notes=(SELECT_PRODUCT_REQUIRED, "No files were changed.", "No product code was executed."),
            blocked_reason=SELECT_PRODUCT_REQUIRED,
        )
    try:
        safe_slug, product_path = _product_root(str(selected_product))
    except ValueError as exc:
        return ContinueProductPlan(
            ok=False,
            status=SELECT_PRODUCT_REQUIRED,
            product_slug=str(selected_product or ""),
            product_path=None,
            current_state="Blocked product selection.",
            recommended_next_action="Select a bounded product under products.",
            action_kind="select_product",
            context_text=contextual_talk.render_context_for_selected_product(str(selected_product or "")),
            guardian_review=(
                "Product files changed now: NO",
                "Runtime source edit: NO",
                "Code execution: NO",
                "Package install: NO",
                "API/network: NO",
                "Trusted memory write: NO",
                f"{AUTHORITY} preserved: YES",
            ),
            safety_notes=(str(exc), "No files were changed."),
            blocked_reason=SELECT_PRODUCT_REQUIRED,
        )

    dashboard = cycle_dashboard.build_product_cycle_dashboard(safe_slug)
    action_kind, recommendation = _choose_action_kind(idea, dashboard)
    context_text = contextual_talk.render_context_for_selected_product(safe_slug)
    patch_text = ""
    if action_kind == "patch_proposal":
        patch_request = _patch_request_for_action(idea, action_kind)
        proposal = patch_proposals.build_product_patch_proposal(safe_slug, patch_request)
        patch_text = patch_proposals.render_product_patch_proposal(proposal)

    return ContinueProductPlan(
        ok=True,
        status=CONTINUE_PRODUCT_STATUS,
        product_slug=safe_slug,
        product_path=product_path,
        current_state=_current_state_text(dashboard),
        recommended_next_action=recommendation,
        action_kind=action_kind,
        patch_proposal_text=patch_text,
        context_text=context_text,
        guardian_review=(
            "Product files changed now: NO",
            "Runtime source edit: NO",
            "Code execution: NO",
            "Package install: NO",
            "API/network: NO",
            "Trusted memory write: NO",
            "Approval required before apply: YES",
            f"{AUTHORITY} preserved: YES",
        ),
        safety_notes=(
            "Continue Product Plan != Applied Change.",
            "Talk-to-Code Continue Product Plan != Trusted Memory.",
            "Use existing APPROVE_PRODUCT_PATCH flow before product files can change.",
            "Use existing APPROVE_LESSON_CANDIDATE flow before lesson candidate receipts can be written.",
            "No product files were changed.",
            "No product code was executed.",
        ),
        message="Continue Product Plan rendered from selected product status/dashboard.",
    )


def render_continue_product_plan(plan: ContinueProductPlan) -> str:
    lines = [
        "# ENGEL CONTINUE PRODUCT PLAN",
        "",
        "Status:",
        plan.status,
        "",
        "Authority:",
        AUTHORITY,
        "",
        "Selected product:",
        plan.product_slug or "none",
        "",
        "Current state:",
        plan.current_state,
        "",
        "Recommended next action:",
        plan.recommended_next_action,
        "",
        "Action kind:",
        plan.action_kind,
        "",
        plan.context_text,
        "",
        "Guardian Review:",
    ]
    lines.extend("- " + item for item in plan.guardian_review)
    lines.extend(
        [
            "",
            "Boundary:",
            "Continue Product Plan != Applied Change.",
            "Continue Product Plan != Trusted Memory.",
            "No patches were applied.",
            "No lesson candidates were created.",
            "No trusted memory was written.",
            "",
            "Safety:",
        ]
    )
    lines.extend("- " + item for item in plan.safety_notes)
    if plan.patch_proposal_text:
        lines.extend(["", "Patch proposal preview:", "", plan.patch_proposal_text])
    if plan.message:
        lines.extend(["", "Message:", plan.message])
    if plan.blocked_reason:
        lines.extend(["", "Blocked reason:", plan.blocked_reason])
    return "\n".join(lines)
