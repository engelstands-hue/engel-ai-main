from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import engel_code_companion_lesson_review as lesson_review
import engel_code_companion_lessons as lessons
import engel_code_companion_products as products


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
PATCH_LESSON_REVIEW_STATUS = "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"
PATCH_LESSON_REVIEW_QUEUE_STATUS = "READ_ONLY / PATCH_LESSON_CANDIDATES / NOT_TRUSTED_MEMORY / NOT_APPLIED"


@dataclass(frozen=True)
class PatchLessonCandidateSummary:
    candidate_id: str
    product_slug: str
    filename: str
    path: Path
    source_patch_receipt_path: Path | None
    status: str
    guard_risk: str


@dataclass(frozen=True)
class PatchLessonCandidateReadResult:
    ok: bool
    status: str
    candidate_id: str
    product_slug: str
    filename: str
    path: Path | None = None
    content: str = ""
    source_patch_receipt_path: Path | None = None
    guard_risk: str = "UNKNOWN"
    message: str = ""


@dataclass(frozen=True)
class PatchLessonReview:
    ok: bool
    status: str
    candidate_id: str
    product_slug: str
    filename: str
    source_candidate_path: Path | None
    source_patch_receipt_path: Path | None
    summary: str
    candidate_lesson: str
    guard_risk: str
    guardian_review: tuple[str, ...]
    recommended_josh_decisions: tuple[str, ...]
    source_excerpt: str = ""
    message: str = ""


@dataclass(frozen=True)
class PatchLessonReviewWriteResult:
    ok: bool
    status: str
    candidate_id: str
    product_slug: str
    review_path: Path | None
    message: str = ""


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _extract_line_after(label: str, content: str) -> str:
    lines = content.splitlines()
    label_lower = label.lower()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() == label_lower:
            for next_line in lines[index + 1 :]:
                value = next_line.strip()
                if value:
                    return value
        if stripped.lower().startswith(label_lower + ":"):
            return stripped.split(":", 1)[1].strip()
    return ""


def _extract_patch_receipt_path(content: str, product_slug: str) -> Path | None:
    if "Product Patch Apply Receipt" not in content:
        return None
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "Product Patch Apply Receipt":
            for next_line in lines[index + 1 :]:
                value = next_line.strip()
                if not value:
                    continue
                path = Path(value)
                product_path = products.product_path_for_slug(product_slug)
                receipt_root = product_path / ".engel_receipts"
                if (
                    path.name.startswith("patch_apply_")
                    and path.name.endswith(".md")
                    and _is_relative_to(path, receipt_root)
                    and path.parent.resolve(strict=False) == receipt_root.resolve(strict=False)
                ):
                    return path
                return None
    return None


def _candidate_lesson(content: str) -> str:
    lesson = _extract_line_after("Candidate Lesson", content)
    return lesson or "Patch-generated lesson candidate is ready for Josh review."


def is_patch_lesson_candidate_id(candidate_id: str) -> bool:
    read_result = read_patch_lesson_candidate(candidate_id)
    return read_result.ok


def list_patch_lesson_candidates(product_slug: str | None = None) -> list[PatchLessonCandidateSummary]:
    summaries: list[PatchLessonCandidateSummary] = []
    for summary in lesson_review.list_lesson_candidate_receipts(product_slug):
        read_result = read_patch_lesson_candidate(summary.candidate_id)
        if not read_result.ok:
            continue
        summaries.append(
            PatchLessonCandidateSummary(
                candidate_id=summary.candidate_id,
                product_slug=summary.product_slug,
                filename=summary.filename,
                path=summary.path,
                source_patch_receipt_path=read_result.source_patch_receipt_path,
                status=summary.status,
                guard_risk=summary.guard_risk,
            )
        )
    return summaries


def read_patch_lesson_candidate(candidate_id: str) -> PatchLessonCandidateReadResult:
    read_result = lesson_review.read_lesson_candidate(candidate_id)
    if not read_result.ok:
        return PatchLessonCandidateReadResult(
            False,
            "PATCH_LESSON_CANDIDATE_READ_BLOCKED",
            candidate_id,
            read_result.product_slug,
            read_result.filename,
            read_result.path,
            message=read_result.message,
        )
    if "Product Patch Apply Receipt" not in read_result.content:
        return PatchLessonCandidateReadResult(
            False,
            "PATCH_LESSON_CANDIDATE_NOT_PATCH_GENERATED",
            candidate_id,
            read_result.product_slug,
            read_result.filename,
            read_result.path,
            read_result.content,
            guard_risk=read_result.guard_risk,
            message="Selected lesson candidate is not patch-generated.",
        )
    source_patch_receipt = _extract_patch_receipt_path(read_result.content, read_result.product_slug)
    if source_patch_receipt is None:
        return PatchLessonCandidateReadResult(
            False,
            "PATCH_LESSON_CANDIDATE_SOURCE_BLOCKED",
            candidate_id,
            read_result.product_slug,
            read_result.filename,
            read_result.path,
            read_result.content,
            guard_risk=read_result.guard_risk,
            message="Patch-generated lesson candidate does not contain a bounded patch apply receipt source.",
        )
    return PatchLessonCandidateReadResult(
        True,
        "PATCH_LESSON_CANDIDATE_READ_ONLY",
        candidate_id,
        read_result.product_slug,
        read_result.filename,
        read_result.path,
        read_result.content,
        source_patch_receipt,
        read_result.guard_risk,
        "Patch-generated lesson candidate was read as untrusted data only.",
    )


def build_patch_lesson_review(candidate_id: str) -> PatchLessonReview:
    read_result = read_patch_lesson_candidate(candidate_id)
    if not read_result.ok:
        return PatchLessonReview(
            False,
            "PATCH_LESSON_REVIEW_BLOCKED",
            candidate_id,
            read_result.product_slug,
            read_result.filename,
            read_result.path,
            read_result.source_patch_receipt_path,
            "",
            "",
            read_result.guard_risk,
            (),
            (),
            "",
            read_result.message,
        )
    candidate_lesson = _candidate_lesson(read_result.content)
    guardian_review = (
        "Trusted memory write: NO",
        "Engel behavior change: NO",
        "Runtime source edit: NO",
        "Product source edit: NO",
        "Code execution: NO",
        "Package install: NO",
        "API/network: NO",
        "Requires future Josh/Guardian memory workflow: YES",
    )
    decisions = (
        "Keep for future memory-candidate review",
        "Reject",
        "Request more product evidence",
        "Request another product patch",
        "No automatic action taken",
    )
    return PatchLessonReview(
        True,
        PATCH_LESSON_REVIEW_STATUS,
        read_result.candidate_id,
        read_result.product_slug,
        read_result.filename,
        read_result.path,
        read_result.source_patch_receipt_path,
        "Patch-generated lesson candidate is ready for Josh review: " + candidate_lesson,
        candidate_lesson,
        read_result.guard_risk,
        guardian_review,
        decisions,
        read_result.content[:2_000],
        "Patch lesson review built as report-only material.",
    )


def render_patch_lesson_review(review: PatchLessonReview) -> str:
    guardian = "\n".join("- " + item for item in review.guardian_review) or "- unavailable"
    decisions = "\n".join("- " + item for item in review.recommended_josh_decisions) or "- No automatic action taken"
    return "\n".join(
        [
            "# Engel Patch Lesson Review",
            "",
            "Status:",
            review.status,
            "",
            "Authority:",
            AUTHORITY,
            "",
            "Source:",
            "Patch-generated lesson candidate",
            str(review.source_candidate_path) if review.source_candidate_path else "none",
            "",
            "Source patch apply receipt:",
            str(review.source_patch_receipt_path) if review.source_patch_receipt_path else "none",
            "",
            "Boundary:",
            "Lesson Candidate \u2260 Trusted Memory.",
            "Lesson Review \u2260 Trusted Memory.",
            "READY_FOR_JOSH_REVIEW \u2260 Trusted Memory.",
            "This review does not update Engel memory.",
            "This review does not change Engel behavior.",
            "",
            "Summary:",
            review.summary or "No summary available.",
            "",
            "Untrusted Content Guard:",
            "Risk: " + review.guard_risk,
            "Candidate content trusted as instruction: NO",
            "Embedded approval tokens accepted: NO",
            "",
            "Guardian Review:",
            guardian,
            "",
            "Recommended Josh Decision:",
            decisions,
            "",
            "Safety:",
            "- Read-only patch lesson review",
            "- No trusted memory written",
            "- No lesson applied",
            "- No memory candidate promoted",
            "- No product files changed",
            "- No runtime files changed",
            "- No code executed",
            "",
            "Candidate Lesson:",
            review.candidate_lesson or "No candidate lesson available.",
        ]
    )


def _next_patch_review_path(product_slug: str) -> Path:
    root = lesson_review.product_lesson_reviews_root(product_slug)
    root.mkdir(parents=True, exist_ok=True)
    candidate = root / f"{_timestamp()}_patch_lesson_review.md"
    if not candidate.exists():
        return candidate
    for index in range(1, 100):
        indexed = root / f"{_timestamp()}_{index:02d}_patch_lesson_review.md"
        if not indexed.exists():
            return indexed
    raise RuntimeError("Unable to create unique patch lesson review path.")


def write_patch_lesson_review(candidate_id: str) -> PatchLessonReviewWriteResult:
    review = build_patch_lesson_review(candidate_id)
    if not review.ok:
        return PatchLessonReviewWriteResult(
            False,
            "PATCH_LESSON_REVIEW_BLOCKED",
            candidate_id,
            review.product_slug,
            None,
            review.message,
        )
    try:
        review_path = _next_patch_review_path(review.product_slug)
        if not lesson_review.is_safe_lesson_review_path(review_path):
            raise ValueError("Unsafe patch lesson review path.")
        review_path.write_text(render_patch_lesson_review(review), encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as exc:
        return PatchLessonReviewWriteResult(
            False,
            "PATCH_LESSON_REVIEW_BLOCKED",
            candidate_id,
            review.product_slug,
            None,
            str(exc),
        )
    return PatchLessonReviewWriteResult(
        True,
        "PATCH_LESSON_REVIEW_CREATED / READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        candidate_id,
        review.product_slug,
        review_path,
        "Patch lesson review written as report-only material.",
    )


def render_patch_lesson_review_write_result(result: PatchLessonReviewWriteResult) -> str:
    review = build_patch_lesson_review(result.candidate_id)
    text = render_patch_lesson_review(review)
    return "\n".join(
        [
            text,
            "",
            "Review write:",
            result.status,
            "",
            "Review path:",
            str(result.review_path) if result.review_path else "none",
            "",
            "Message:",
            result.message,
        ]
    )
