from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import engel_code_companion_products as products


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
AUTHORITY = "Josh > Guardian > Engel/runtime"
HEALTH_DELTA_STATUS = "REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"


@dataclass(frozen=True)
class ProductHealthSnapshot:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    item_statuses: tuple[tuple[str, str, str], ...]
    message: str = ""


@dataclass(frozen=True)
class ProductHealthDelta:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    before: ProductHealthSnapshot | None
    after: ProductHealthSnapshot | None
    delta_status: str
    changed_statuses: tuple[str, ...]
    recommended_next_safe_action: str
    report_path: Path | None = None
    message: str = ""


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def capture_product_health_snapshot(product_slug: str) -> ProductHealthSnapshot:
    result = products.product_health_check(product_slug)
    items = tuple((item.name, item.status, item.message) for item in result.items)
    return ProductHealthSnapshot(
        ok=result.ok,
        status=result.status,
        product_slug=result.product_slug,
        product_path=result.product_path,
        item_statuses=items,
        message=result.message,
    )


def _status_rank(status: str) -> int:
    value = str(status or "").upper()
    if value == "PASS":
        return 3
    if value in {"PASS_WITH_WARNINGS", "WARN"}:
        return 2
    if value == "INFO":
        return 1
    return 0


def _item_status_map(snapshot: ProductHealthSnapshot | None) -> dict[str, str]:
    if snapshot is None:
        return {}
    return {name: status for name, status, _message in snapshot.item_statuses}


def _issue_count(snapshot: ProductHealthSnapshot | None) -> int:
    if snapshot is None:
        return 0
    return sum(1 for _name, status, _message in snapshot.item_statuses if status in {"BLOCKED", "WARN"})


def _changed_statuses(before: ProductHealthSnapshot, after: ProductHealthSnapshot) -> tuple[str, ...]:
    before_map = _item_status_map(before)
    after_map = _item_status_map(after)
    changes: list[str] = []
    for name in sorted(set(before_map) | set(after_map)):
        before_status = before_map.get(name, "MISSING")
        after_status = after_map.get(name, "MISSING")
        if before_status != after_status:
            changes.append(f"{name}: {before_status} -> {after_status}")
    return tuple(changes)


def _delta_status(before: ProductHealthSnapshot, after: ProductHealthSnapshot) -> str:
    before_rank = _status_rank(before.status)
    after_rank = _status_rank(after.status)
    before_issues = _issue_count(before)
    after_issues = _issue_count(after)
    if after_rank > before_rank or after_issues < before_issues:
        return "improved"
    if after_rank < before_rank or after_issues > before_issues:
        return "needs review"
    return "unchanged"


def _next_safe_action(delta_status: str, after: ProductHealthSnapshot) -> str:
    if delta_status == "improved":
        return "Review the report and keep the lesson suggestion proposal-only until Josh approves a candidate."
    if delta_status == "needs review":
        return "Review the changed health statuses before creating any lesson candidate."
    if after.status == "BLOCKED":
        return "Run Health and resolve blocked product metadata before further patch work."
    return "Continue with Guardian review; no automatic learning or trusted-memory write occurred."


def build_product_health_delta(
    product_slug: str,
    before: ProductHealthSnapshot,
    after: ProductHealthSnapshot,
) -> ProductHealthDelta:
    safe_slug = products.safe_product_slug(product_slug)
    product_path = products.product_path_for_slug(safe_slug)
    if not products.is_safe_product_path(product_path):
        return ProductHealthDelta(False, "REPORT_ONLY_BLOCKED", safe_slug, None, before, after, "needs review", tuple(), "Select a bounded product.", message="Product path is unsafe.")
    if before.product_slug != safe_slug or after.product_slug != safe_slug:
        return ProductHealthDelta(False, "REPORT_ONLY_BLOCKED", safe_slug, product_path, before, after, "needs review", tuple(), "Review product health manually.", message="Health snapshot product mismatch.")
    changed = _changed_statuses(before, after)
    delta = _delta_status(before, after)
    return ProductHealthDelta(
        ok=True,
        status=HEALTH_DELTA_STATUS,
        product_slug=safe_slug,
        product_path=product_path,
        before=before,
        after=after,
        delta_status=delta,
        changed_statuses=changed,
        recommended_next_safe_action=_next_safe_action(delta, after),
        message="Product health before/after patch apply compared without executing product code.",
    )


def _snapshot_summary(snapshot: ProductHealthSnapshot | None) -> list[str]:
    if snapshot is None:
        return ["missing"]
    lines = [snapshot.status]
    for name, status, message in snapshot.item_statuses:
        lines.append(f"- {name}: {status} / {message}")
    return lines


def render_product_health_delta(delta: ProductHealthDelta) -> str:
    lines = [
        "# Product Patch Health Delta",
        "",
        "Status:",
        delta.status,
        "",
        "Authority:",
        AUTHORITY,
        "",
        "Product:",
        delta.product_slug or "none",
        "",
        "Before:",
    ]
    lines.extend(_snapshot_summary(delta.before))
    lines.extend(["", "After:"])
    lines.extend(_snapshot_summary(delta.after))
    lines.extend(["", "Delta:"])
    if delta.changed_statuses:
        lines.extend("- " + item for item in delta.changed_statuses)
    else:
        lines.append("- unchanged")
    lines.extend(
        [
            "- " + delta.delta_status,
            "",
            "Recommended next safe action:",
            delta.recommended_next_safe_action,
            "",
            "Guardian Review:",
            "- Product code execution: NO",
            "- Runtime edit: NO",
            "- Trusted memory write: NO",
            "- Lesson applied: NO",
            "- API/network: NO",
            "- Package install: NO",
            f"- {AUTHORITY} preserved: YES",
            "",
            "Boundary:",
            "Health Delta \u2260 Trusted Memory.",
            "Health Delta \u2260 Lesson.",
            "Health Delta does not apply changes.",
            "Health Delta is proposal-only evidence for later Guardian review.",
            "No product code was executed.",
            "No trusted memory was written.",
        ]
    )
    if delta.message:
        lines.extend(["", "Message:", delta.message])
    return "\n".join(lines)


def write_product_health_delta_report(delta: ProductHealthDelta) -> Path:
    if delta.product_path is None:
        raise ValueError("Health delta report requires a product path.")
    product_path = delta.product_path.resolve(strict=False)
    if not products.is_safe_product_path(product_path):
        raise ValueError("Health delta report blocked for unsafe product path.")
    receipt_dir = product_path / ".engel_receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    report = receipt_dir / f"health_delta_{_timestamp()}.md"
    index = 1
    while report.exists():
        index += 1
        report = receipt_dir / f"health_delta_{_timestamp()}_{index}.md"
    resolved = report.resolve(strict=False)
    if not _is_relative_to(resolved, product_path / ".engel_receipts"):
        raise ValueError("Health delta report escaped product receipts.")
    report.write_text(render_product_health_delta(delta), encoding="utf-8")
    return report
