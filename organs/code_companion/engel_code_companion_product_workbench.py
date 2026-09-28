from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import engel_code_companion_continue_product as continue_product
import engel_code_companion_product_cycle_dashboard as cycle_dashboard
import engel_code_companion_products as products


AUTHORITY = "Josh > Guardian > Engel/runtime"
WORKBENCH_STATUS = "READ_ONLY_STATUS / NOT_TRUSTED_MEMORY / NOT_APPLIED"
BLOCKED_WORKBENCH_STATUS = "READ_ONLY_STATUS / BLOCKED / NOT_TRUSTED_MEMORY / NOT_APPLIED"
TRUSTED_MEMORY_STATUS = "BLOCKED / NOT_PERFORMED"
PRIMARY_FLOW = "Talk to Engel -> Plan -> Create/Patch/Review"
BOUNDARY_LINES: tuple[str, ...] = (
    "Runtime source edit: BLOCKED",
    "Generated code execution: BLOCKED",
    "Trusted memory write: BLOCKED / NOT_PERFORMED",
    "Browser Queen: NOT USED",
)


@dataclass(frozen=True)
class ProductWorkbenchStatus:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    current_state: str
    next_safe_action: str
    primary_flow: str = PRIMARY_FLOW
    boundaries: tuple[str, ...] = BOUNDARY_LINES
    message: str = ""


def _validate_product_slug(product_slug: str) -> tuple[str, Path]:
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


def _compact_cycle_state(dashboard: cycle_dashboard.ProductCycleDashboard) -> str:
    if not dashboard.ok:
        return "Cycle unavailable: " + (dashboard.message or dashboard.status)
    receipt = dashboard.latest_patch_apply_receipt.name if dashboard.latest_patch_apply_receipt else "missing"
    return "; ".join(
        [
            "Health: " + dashboard.health_status,
            "Patch: " + dashboard.patch_proposal_status,
            "Apply receipt: " + receipt,
            "Lesson suggestion: " + dashboard.lesson_suggestion_status,
            "Lesson candidates: " + str(dashboard.lesson_candidate_count),
            "Lesson reviews: " + str(dashboard.lesson_review_count),
        ]
    )


def _fallback_next_action(dashboard: cycle_dashboard.ProductCycleDashboard) -> str:
    if not dashboard.ok:
        return "Select a bounded product under products."
    if dashboard.health_status == "BLOCKED":
        return "Run Health."
    if dashboard.latest_patch_apply_receipt is None:
        return "Ask Engel to continue this product."
    if dashboard.lesson_suggestion_status.startswith("PRESENT") and dashboard.lesson_candidate_count == 0:
        return "Review lesson suggestion; create candidate only with APPROVE_LESSON_CANDIDATE."
    if dashboard.lesson_candidate_count > 0 and dashboard.lesson_review_count == 0:
        return "Review lesson candidate."
    if dashboard.lesson_review_count > 0:
        return "Create memory candidate proposal only if Josh approves."
    return dashboard.next_safe_action or "Review cycle status with Josh."


def recommend_next_safe_product_action(product_slug: str | None) -> str:
    if not str(product_slug or "").strip():
        return "Describe a product idea or select a product."
    try:
        safe_slug, _product_path = _validate_product_slug(str(product_slug))
    except ValueError:
        return "Select a bounded product under products."
    dashboard = cycle_dashboard.build_product_cycle_dashboard(safe_slug)
    recommendation = _fallback_next_action(dashboard)
    if recommendation == "Ask Engel to continue this product.":
        plan = continue_product.build_continue_product_plan("Engel, continue this product.", safe_slug)
        if plan.ok and plan.recommended_next_action:
            return "Ask Engel to continue this product. " + plan.recommended_next_action
    return recommendation


def summarize_product_boundaries() -> str:
    return "\n".join("- " + line for line in BOUNDARY_LINES)


def build_product_workbench_status(product_slug: str | None) -> ProductWorkbenchStatus:
    if not str(product_slug or "").strip():
        return ProductWorkbenchStatus(
            ok=True,
            status=WORKBENCH_STATUS,
            product_slug="NONE",
            product_path=None,
            current_state="No selected product.",
            next_safe_action="Describe a product idea or select a product.",
            message="No product selected; workbench is waiting for Josh.",
        )
    try:
        safe_slug, product_path = _validate_product_slug(str(product_slug))
    except ValueError as exc:
        return ProductWorkbenchStatus(
            ok=False,
            status=BLOCKED_WORKBENCH_STATUS,
            product_slug=str(product_slug or ""),
            product_path=None,
            current_state="Blocked product selection.",
            next_safe_action="Select a bounded product under products.",
            message=str(exc),
        )
    dashboard = cycle_dashboard.build_product_cycle_dashboard(safe_slug)
    return ProductWorkbenchStatus(
        ok=dashboard.ok,
        status=WORKBENCH_STATUS if dashboard.ok else BLOCKED_WORKBENCH_STATUS,
        product_slug=safe_slug,
        product_path=product_path,
        current_state=_compact_cycle_state(dashboard),
        next_safe_action=_fallback_next_action(dashboard),
        message="Selected-product workbench rendered read-only.",
    )


def render_product_workbench_status(status: ProductWorkbenchStatus) -> str:
    lines = [
        "# Engel Product Workbench",
        "",
        "Status:",
        status.status,
        "",
        "Authority:",
        AUTHORITY,
        "",
        "Selected product:",
        status.product_slug or "NONE",
        "",
        "Current state:",
        status.current_state,
        "",
        "Next safe action:",
        status.next_safe_action,
        "",
        "Primary flow:",
        status.primary_flow,
        "",
        "Boundaries:",
        *["- " + line for line in status.boundaries],
    ]
    if status.message:
        lines.extend(["", "Message:", status.message])
    lines.extend(
        [
            "",
            "Safety:",
            "Workbench is read-only.",
            "Workbench != Trusted Memory.",
            "Workbench does not apply patches.",
            "Workbench does not create lesson candidates.",
            "Workbench does not create memory candidates.",
            "Workbench does not edit product files.",
            "Workbench does not edit Engel runtime source.",
            "Workbench does not execute generated code.",
            "Workbench does not call APIs/network.",
        ]
    )
    return "\n".join(lines)


def render_selected_product_workbench(product_slug: str | None) -> str:
    return render_product_workbench_status(build_product_workbench_status(product_slug))
