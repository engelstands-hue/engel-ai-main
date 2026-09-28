from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import engel_code_companion_lessons as lessons
import engel_code_companion_products as products


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
APPROVE_LESSON_CANDIDATE = lessons.LESSON_CANDIDATE_APPROVAL_TOKEN
BRIDGE_BLOCKED = "LESSON_CANDIDATE_BLOCKED / APPROVE_LESSON_CANDIDATE_REQUIRED"
BRIDGE_CREATED = "LESSON_CANDIDATE_CREATED / PENDING_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"


@dataclass(frozen=True)
class PatchApplyReceiptValidation:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    receipt_path: Path | None
    message: str = ""


@dataclass(frozen=True)
class PatchApplyLessonCandidate:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    source_receipt_path: Path | None
    candidate_lesson: str
    changed_files: tuple[str, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class PatchApplyLessonBridgeResult:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    source_receipt_path: Path | None
    lesson_candidate_receipt_path: Path | None = None
    candidate_lesson: str = ""
    approval_received: bool = False
    message: str = ""


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _product_root(product_slug: str) -> tuple[str, Path]:
    safe_slug = products.safe_product_slug(product_slug)
    if safe_slug != str(product_slug or "").strip():
        raise ValueError("Selected product must be a safe product slug.")
    product_path = products.product_path_for_slug(safe_slug)
    if not products.is_safe_product_path(product_path):
        raise ValueError("Selected product must stay under products.")
    if not product_path.exists() or not product_path.is_dir():
        raise ValueError("Selected product does not exist under products.")
    if product_path.is_symlink():
        raise ValueError("Selected product symlinks are blocked.")
    return safe_slug, product_path


def _receipts_root(product_path: Path) -> Path:
    return product_path / ".engel_receipts"


def _reject_receipt_id(receipt_id: str) -> None:
    text = str(receipt_id or "").strip()
    lowered = text.lower()
    if not text:
        return
    if lowered.startswith(("http://", "https://", "file://", "data:", "javascript:")):
        raise ValueError("URL-like patch receipt IDs are blocked.")
    if text.startswith(("\\\\", "//", "\\", "/")):
        raise ValueError("UNC or absolute patch receipt IDs are blocked.")
    if re.match(r"^[A-Za-z]:", text):
        raise ValueError("Drive or absolute patch receipt IDs are blocked.")
    if "/" in text or "\\" in text:
        raise ValueError("Patch receipt ID must be a single receipt filename.")
    if text in {".", ".."} or ".." in Path(text).parts:
        raise ValueError("Path traversal patch receipt IDs are blocked.")
    if not (text.startswith("patch_apply_") and text.endswith(".md")):
        raise ValueError("Patch receipt ID must name a product patch apply receipt.")


def latest_patch_apply_receipt(product_slug: str) -> Path | None:
    try:
        _safe_slug, product_path = _product_root(product_slug)
    except ValueError:
        return None
    receipt_root = _receipts_root(product_path)
    if not receipt_root.exists():
        return None
    receipts = [
        path
        for path in receipt_root.glob("patch_apply_*.md")
        if path.is_file() and not path.is_symlink()
    ]
    receipts = [path for path in receipts if _is_relative_to(path, receipt_root)]
    if not receipts:
        return None
    return sorted(receipts, key=lambda item: item.stat().st_mtime, reverse=True)[0]


def validate_patch_apply_receipt(product_slug: str, receipt_id: str | Path | None = None) -> PatchApplyReceiptValidation:
    try:
        safe_slug, product_path = _product_root(product_slug)
        if receipt_id is None or str(receipt_id).strip() == "":
            receipt_path = latest_patch_apply_receipt(safe_slug)
            if receipt_path is None:
                raise ValueError("No product patch apply receipt is available for this product.")
        else:
            text = str(receipt_id)
            _reject_receipt_id(text)
            receipt_path = _receipts_root(product_path) / text

        receipt_root = _receipts_root(product_path).resolve(strict=False)
        candidate = receipt_path.resolve(strict=False)
        if candidate.parent != receipt_root or not _is_relative_to(candidate, receipt_root):
            raise ValueError("Patch receipt must stay under selected product .engel_receipts.")
        if not receipt_path.exists() or not receipt_path.is_file():
            raise ValueError("Patch apply receipt is missing.")
        if receipt_path.is_symlink():
            raise ValueError("Patch apply receipt symlinks are blocked.")
        text = receipt_path.read_text(encoding="utf-8", errors="replace")
        for needle in (
            "# Engel Product Patch Apply Receipt",
            "PATCH_APPLIED_PRODUCT_ONLY / NOT_TRUSTED_MEMORY / NOT_EXECUTED",
            "Lesson Candidate Auto-Suggestion:",
            "Future token required before candidate receipt: APPROVE_LESSON_CANDIDATE",
        ):
            if needle not in text:
                raise ValueError("Patch apply receipt is not a valid suggestion source.")
        return PatchApplyReceiptValidation(
            True,
            "PATCH_APPLY_RECEIPT_VALID / PRODUCT_ONLY",
            safe_slug,
            product_path,
            receipt_path,
            "Patch apply receipt is bounded to selected product.",
        )
    except ValueError as exc:
        return PatchApplyReceiptValidation(
            False,
            "PATCH_APPLY_RECEIPT_BLOCKED",
            str(product_slug or ""),
            None,
            None,
            str(exc),
        )


def _changed_files_from_receipt(text: str) -> tuple[str, ...]:
    files: list[str] = []
    in_files = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "Files changed:":
            in_files = True
            continue
        if in_files and not stripped:
            break
        if in_files and stripped.startswith("- "):
            item = stripped[2:].strip().replace("\\", "/")
            if item and item != "none":
                files.append(item)
    return tuple(files)


def _lesson_from_changed_files(changed_files: tuple[str, ...]) -> str:
    joined = " ".join(item.lower() for item in changed_files)
    if "readme" in joined and "test" in joined:
        return "Approved product patches that change documentation should keep a bounded smoke-test plan aligned with the README."
    if "readme" in joined:
        return "Approved product patches should leave clear README instructions for future preview, health, and review steps."
    if "product_manifest.json" in joined or ".engel_product_profile.json" in joined:
        return "Approved product patches that update manifests should preserve product-only boundaries and explicit metadata."
    if "src/" in joined or "index.html" in joined or "styles.css" in joined:
        return "Approved source-facing product patches should remain product-only and be validated without executing generated code."
    return "Approved product patches should be reviewed for reusable product-building lessons before any future memory workflow."


def build_patch_apply_lesson_candidate(product_slug: str, receipt_id: str | Path | None = None) -> PatchApplyLessonCandidate:
    validation = validate_patch_apply_receipt(product_slug, receipt_id)
    if not validation.ok or validation.receipt_path is None:
        return PatchApplyLessonCandidate(
            False,
            "LESSON_CANDIDATE_BLOCKED",
            validation.product_slug,
            validation.product_path,
            validation.receipt_path,
            "",
            (),
            validation.message,
        )
    text = validation.receipt_path.read_text(encoding="utf-8", errors="replace")
    changed_files = _changed_files_from_receipt(text)
    return PatchApplyLessonCandidate(
        True,
        lessons.LESSON_CANDIDATE_STATUS,
        validation.product_slug,
        validation.product_path,
        validation.receipt_path,
        _lesson_from_changed_files(changed_files),
        changed_files,
        "Patch apply lesson candidate built from product-local patch apply receipt.",
    )


def _next_lesson_receipt_path(product_slug: str) -> Path:
    root = lessons.product_lesson_candidates_root(product_slug)
    root.mkdir(parents=True, exist_ok=True)
    candidate = root / f"{_timestamp()}_lesson_candidate.md"
    if not candidate.exists():
        return candidate
    for index in range(1, 100):
        indexed = root / f"{_timestamp()}_{index:02d}_lesson_candidate.md"
        if not indexed.exists():
            return indexed
    raise RuntimeError("Unable to create unique patch lesson candidate receipt path.")


def _render_patch_lesson_candidate_receipt(candidate: PatchApplyLessonCandidate, approval_received: bool) -> str:
    source_path = str(candidate.source_receipt_path) if candidate.source_receipt_path else "none"
    changed = "\n".join("- " + item for item in candidate.changed_files) or "- none"
    approval = "YES" if approval_received else "NO"
    return "\n".join(
        [
            "# Engel Product Lesson Candidate",
            "",
            "Status:",
            lessons.LESSON_CANDIDATE_STATUS,
            "",
            "Authority:",
            AUTHORITY,
            "",
            "Source:",
            "Product Patch Apply Receipt",
            source_path,
            "",
            "Selected product:",
            candidate.product_slug,
            "",
            "Approval:",
            f"APPROVE_LESSON_CANDIDATE received from user input: {approval}",
            "",
            "Token meaning:",
            'APPROVE_LESSON_CANDIDATE means "write lesson candidate receipt only."',
            'It does not mean "trust this lesson."',
            'It does not mean "apply this lesson."',
            'It does not mean "write trusted memory."',
            "",
            "Boundary:",
            "Lesson Candidate \u2260 Trusted Memory.",
            "Patch Apply Lesson Suggestion \u2260 Trusted Memory.",
            "This candidate does not update Engel memory.",
            "This candidate does not change Engel behavior.",
            "This candidate is not an instruction source.",
            "",
            "Changed files from patch receipt:",
            changed,
            "",
            "Guardian Review:",
            "- Trusted memory write: NO",
            "- Engel behavior change: NO",
            "- Runtime source edit: NO",
            "- Product source edit: NO",
            "- Code execution: NO",
            "- Package install: NO",
            "- API/network: NO",
            "- Embedded approval tokens accepted: NO",
            "- Requires later Josh/Guardian memory workflow: YES",
            "",
            "Candidate Lesson:",
            candidate.candidate_lesson or "No deterministic lesson candidate available.",
            "",
            "Recommended Future Action:",
            "- Review candidate",
            "- Keep/reject/request more product evidence",
            "- Convert through future memory-candidate workflow only if separately approved",
            "",
        ]
    )


def create_patch_apply_lesson_candidate_receipt(
    product_slug: str,
    receipt_id: str | Path | None = None,
    approval_token: str | None = None,
) -> PatchApplyLessonBridgeResult:
    try:
        safe_slug, product_path = _product_root(product_slug)
    except ValueError as exc:
        return PatchApplyLessonBridgeResult(False, "LESSON_CANDIDATE_BLOCKED", str(product_slug or ""), None, None, message=str(exc))

    validation = validate_patch_apply_receipt(safe_slug, receipt_id)
    if not validation.ok:
        return PatchApplyLessonBridgeResult(False, validation.status, safe_slug, product_path, None, message=validation.message)

    if str(approval_token or "").strip() != APPROVE_LESSON_CANDIDATE:
        return PatchApplyLessonBridgeResult(
            False,
            BRIDGE_BLOCKED,
            safe_slug,
            product_path,
            validation.receipt_path,
            approval_received=False,
            message="Exact APPROVE_LESSON_CANDIDATE token is required from explicit user input. No lesson candidate was written.",
        )

    candidate = build_patch_apply_lesson_candidate(safe_slug, validation.receipt_path.name if validation.receipt_path else None)
    if not candidate.ok:
        return PatchApplyLessonBridgeResult(False, candidate.status, safe_slug, product_path, validation.receipt_path, message=candidate.message)

    try:
        receipt_path = _next_lesson_receipt_path(safe_slug)
        if not lessons.is_safe_lesson_candidate_path(receipt_path):
            raise ValueError("Unsafe lesson candidate receipt path.")
        receipt_path.write_text(_render_patch_lesson_candidate_receipt(candidate, approval_received=True), encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as exc:
        return PatchApplyLessonBridgeResult(False, "LESSON_CANDIDATE_BLOCKED", safe_slug, product_path, validation.receipt_path, candidate_lesson=candidate.candidate_lesson, approval_received=True, message=str(exc))

    return PatchApplyLessonBridgeResult(
        True,
        BRIDGE_CREATED,
        safe_slug,
        product_path,
        validation.receipt_path,
        receipt_path,
        candidate.candidate_lesson,
        approval_received=True,
        message="Product lesson candidate receipt written from patch apply suggestion as pending review.",
    )


def render_patch_apply_lesson_bridge_result(result: PatchApplyLessonBridgeResult) -> str:
    approval = "YES" if result.approval_received else "NO"
    return "\n".join(
        [
            "# Engel Patch Apply Approved Lesson Candidate Bridge",
            "",
            "Status:",
            result.status,
            "",
            "Authority:",
            AUTHORITY,
            "",
            "Selected product:",
            result.product_slug or "none",
            "",
            "Source:",
            "Product Patch Apply Receipt",
            str(result.source_receipt_path) if result.source_receipt_path else "none",
            "",
            "Lesson candidate receipt:",
            str(result.lesson_candidate_receipt_path) if result.lesson_candidate_receipt_path else "none",
            "",
            "Approval:",
            f"APPROVE_LESSON_CANDIDATE received from user input: {approval}",
            "",
            "Token meaning:",
            'APPROVE_LESSON_CANDIDATE means "write lesson candidate receipt only."',
            'It does not mean "trust this lesson."',
            'It does not mean "apply this lesson."',
            'It does not mean "write trusted memory."',
            "",
            "Boundary:",
            "Lesson Candidate \u2260 Trusted Memory.",
            "Patch Apply Lesson Suggestion \u2260 Trusted Memory.",
            "This bridge does not update Engel memory.",
            "This bridge does not change Engel behavior.",
            "This bridge does not edit product files during lesson creation.",
            "",
            "Guardian Review:",
            "- Trusted memory write: NO",
            "- Engel behavior change: NO",
            "- Runtime source edit: NO",
            "- Product source edit: NO",
            "- Code execution: NO",
            "- Package install: NO",
            "- API/network: NO",
            "- Embedded approval tokens accepted: NO",
            "- Requires later Josh/Guardian memory workflow: YES",
            "",
            "Candidate Lesson:",
            result.candidate_lesson or "No lesson candidate was written.",
            "",
            "Recommended Future Action:",
            "- Review candidate",
            "- Keep/reject/request more product evidence",
            "- Convert through future memory-candidate workflow only if separately approved",
            "",
            "Message:",
            result.message,
        ]
    )
