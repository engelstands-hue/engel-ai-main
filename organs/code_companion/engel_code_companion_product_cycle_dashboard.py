from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import engel_code_companion_lesson_review as lesson_review
import engel_code_companion_patch_lesson_bridge as patch_lesson_bridge
import engel_code_companion_patch_proposals as patch_proposals
import engel_code_companion_products as products


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
DASHBOARD_STATUS = "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED"
TRUSTED_MEMORY_STATUS = "BLOCKED / NOT_PERFORMED"
CYCLE_STAGES = "Health -> Improve -> Patch Proposal -> Patch Apply -> Lesson Candidate -> Lesson Review"


@dataclass(frozen=True)
class ProductCycleDashboard:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    health_status: str
    improvement_proposal_status: str
    patch_proposal_status: str
    latest_patch_apply_receipt: Path | None
    lesson_suggestion_status: str
    lesson_candidate_count: int
    lesson_review_count: int
    next_safe_action: str
    message: str = ""


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


def _lesson_review_count(product_slug: str) -> int:
    try:
        root = lesson_review.product_lesson_reviews_root(product_slug)
    except ValueError:
        return 0
    if not root.exists():
        return 0
    return sum(1 for path in root.glob("*_lesson_review.md") if path.is_file() and lesson_review.is_safe_lesson_review_path(path))


def _lesson_suggestion_status(product_slug: str, receipt: Path | None) -> str:
    if receipt is None:
        return "MISSING / PATCH_APPLY_REQUIRED"
    validation = patch_lesson_bridge.validate_patch_apply_receipt(product_slug, receipt.name)
    if validation.ok:
        return "PRESENT / PROPOSAL_ONLY / NOT_WRITTEN"
    return "MISSING / INVALID_PATCH_RECEIPT"


def _next_action(
    *,
    health_status: str,
    patch_receipt: Path | None,
    lesson_suggestion_status: str,
    lesson_candidate_count: int,
    lesson_review_count: int,
) -> str:
    if health_status == "BLOCKED":
        return "Run Health and review blocked/missing product metadata."
    if patch_receipt is None:
        return "Generate a patch proposal or apply an approved product-only patch."
    if lesson_suggestion_status.startswith("PRESENT") and lesson_candidate_count == 0:
        return "Create lesson candidate only with APPROVE_LESSON_CANDIDATE."
    if lesson_candidate_count > 0 and lesson_review_count == 0:
        return "Review lesson candidate for READY_FOR_JOSH_REVIEW."
    return "Review cycle status with Josh; no automatic action taken."


def build_product_cycle_dashboard(product_slug: str) -> ProductCycleDashboard:
    try:
        safe_slug, product_path = _product_root(product_slug)
    except ValueError as exc:
        return ProductCycleDashboard(
            ok=False,
            status="PRODUCT_CYCLE_DASHBOARD_BLOCKED",
            product_slug=str(product_slug or ""),
            product_path=None,
            health_status="BLOCKED",
            improvement_proposal_status="BLOCKED",
            patch_proposal_status="BLOCKED",
            latest_patch_apply_receipt=None,
            lesson_suggestion_status="BLOCKED",
            lesson_candidate_count=0,
            lesson_review_count=0,
            next_safe_action="Select a bounded product under products.",
            message=str(exc),
        )

    health = products.product_health_check(safe_slug)
    improvement = products.build_product_improvement_proposal(safe_slug)
    patch = patch_proposals.build_product_patch_proposal(safe_slug, "Create a patch proposal for this product.")
    latest_receipt = patch_lesson_bridge.latest_patch_apply_receipt(safe_slug)
    suggestion_status = _lesson_suggestion_status(safe_slug, latest_receipt)
    lesson_candidates = lesson_review.list_lesson_candidate_receipts(safe_slug)
    review_count = _lesson_review_count(safe_slug)
    next_action = _next_action(
        health_status=health.status,
        patch_receipt=latest_receipt,
        lesson_suggestion_status=suggestion_status,
        lesson_candidate_count=len(lesson_candidates),
        lesson_review_count=review_count,
    )
    return ProductCycleDashboard(
        ok=True,
        status=DASHBOARD_STATUS,
        product_slug=safe_slug,
        product_path=product_path,
        health_status=health.status,
        improvement_proposal_status=improvement.status if improvement.ok else "MISSING / " + improvement.status,
        patch_proposal_status="PRESENT / " + patch.status if patch.ok else "MISSING / " + patch.status,
        latest_patch_apply_receipt=latest_receipt,
        lesson_suggestion_status=suggestion_status,
        lesson_candidate_count=len(lesson_candidates),
        lesson_review_count=review_count,
        next_safe_action=next_action,
        message="Product improvement cycle dashboard rendered read-only.",
    )


def render_product_cycle_dashboard(dashboard: ProductCycleDashboard) -> str:
    receipt = dashboard.latest_patch_apply_receipt.name if dashboard.latest_patch_apply_receipt else "missing"
    if not dashboard.ok:
        return "\n".join(
            [
                "# Product Improvement Cycle",
                "",
                "Status:",
                "READ_ONLY_STATUS / BLOCKED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
                "",
                "Selected product:",
                dashboard.product_slug or "none",
                "",
                "Reason:",
                dashboard.message,
                "",
                "Boundary:",
                "Dashboard is read-only.",
                "Dashboard != Trusted Memory.",
                "Dashboard does not apply patches.",
                "Dashboard does not create lessons.",
                "Dashboard does not write trusted memory.",
            ]
        )
    return "\n".join(
        [
            "# Product Improvement Cycle",
            "",
            "Status:",
            dashboard.status,
            "",
            "Authority:",
            AUTHORITY,
            "",
            "Selected product:",
            dashboard.product_slug,
            "",
            "Cycle:",
            "Health -> Improve -> Patch Proposal -> Patch Apply -> Lesson Candidate -> Lesson Review",
            "Health \u2192 Improve \u2192 Patch Proposal \u2192 Patch Apply \u2192 Lesson Candidate \u2192 Lesson Review",
            "",
            "Latest:",
            "- Health: " + dashboard.health_status,
            "- Improvement proposal: " + dashboard.improvement_proposal_status,
            "- Patch proposal: " + dashboard.patch_proposal_status,
            "- Patch apply receipt: " + receipt,
            "- Lesson suggestion: " + dashboard.lesson_suggestion_status,
            "- Lesson candidates: " + str(dashboard.lesson_candidate_count),
            "- Lesson reviews: " + str(dashboard.lesson_review_count),
            "",
            "Trusted memory:",
            TRUSTED_MEMORY_STATUS,
            "",
            "Next safe action:",
            dashboard.next_safe_action,
            "",
            "Read policy:",
            "Selected product only.",
            "No broad scans.",
            "",
            "Boundary:",
            "Dashboard is read-only.",
            "Dashboard != Trusted Memory.",
            "Dashboard does not apply patches.",
            "Dashboard does not create lessons.",
            "Dashboard does not write trusted memory.",
            "Dashboard does not edit product files.",
            "Dashboard does not execute code.",
        ]
    )


def render_selected_product_cycle_dashboard(product_slug: str) -> str:
    return render_product_cycle_dashboard(build_product_cycle_dashboard(product_slug))
