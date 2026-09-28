"""Read-only/report-only review queue for Code Companion lesson candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import engel_code_companion_lessons as lessons
import engel_code_companion_products as products
import engel_untrusted_content_guard as untrusted_content_guard


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
LESSON_CANDIDATE_DIRNAME = ".engel_lesson_candidates"
LESSON_REVIEW_DIRNAME = ".engel_lesson_reviews"
LESSON_REVIEW_BOUNDARY_TEXT = "Lesson Candidate != Trusted Memory"
LESSON_REVIEW_STATUS = "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"
QUEUE_STATUS = "READ_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"
MAX_CANDIDATE_PREVIEW_CHARS = 12_000
IGNORED_EMBEDDED_APPROVAL_TOKENS = ("APPROVE_LESSON_CANDIDATE",)


@dataclass(frozen=True)
class LessonCandidateSummary:
    candidate_id: str
    product_slug: str
    filename: str
    path: Path
    modified_time: str
    status: str
    guard_risk: str
    pending_review: bool


@dataclass(frozen=True)
class LessonCandidateReadResult:
    ok: bool
    status: str
    candidate_id: str
    product_slug: str
    filename: str
    path: Path | None = None
    content: str = ""
    excerpt: str = ""
    truncated: bool = False
    guard_risk: str = "UNKNOWN"
    message: str = ""


@dataclass(frozen=True)
class LessonReviewSummary:
    ok: bool
    status: str
    candidate_id: str
    product_slug: str
    filename: str
    summary: str
    guard_risk: str
    recommended_decisions: tuple[str, ...]
    guardian_review: tuple[str, ...]
    source_excerpt: str
    message: str = ""


@dataclass(frozen=True)
class LessonReviewWriteResult:
    ok: bool
    status: str
    candidate_id: str
    product_slug: str
    review_path: Path | None
    message: str


def _resolve_without_existing(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def lesson_review_root() -> Path:
    """Return the bounded root that may contain product-local review summaries."""

    return products.products_root()


def product_lesson_reviews_root(slug: str) -> Path:
    safe_slug = products.safe_product_slug(slug)
    if safe_slug != slug:
        raise ValueError("Unsafe product slug")
    product_path = products.product_path_for_slug(safe_slug)
    if not products.is_safe_product_path(product_path):
        raise ValueError("Unsafe product path")
    return product_path / LESSON_REVIEW_DIRNAME


def _candidate_id(product_slug: str, filename: str) -> str:
    return product_slug + "::" + filename


def _parse_candidate_id(candidate_id: str) -> tuple[str, str]:
    raw = str(candidate_id or "").strip()
    lowered = raw.lower()
    if not raw or "://" in lowered or raw.startswith("\\\\"):
        raise ValueError("Unsafe lesson candidate id")
    if ":" in raw.replace("::", "", 1):
        raise ValueError("Raw drive or absolute paths are blocked")
    if "::" not in raw:
        raise ValueError("Lesson candidate id must be product_slug::filename.md")
    product_slug, filename = raw.split("::", 1)
    safe_slug = products.safe_product_slug(product_slug)
    if safe_slug != product_slug:
        raise ValueError("Unsafe product slug")
    relative = Path(filename.replace("\\", "/"))
    if relative.is_absolute() or len(relative.parts) != 1:
        raise ValueError("Lesson candidate filename must not contain folders")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("Lesson candidate filename contains path traversal")
    if not filename.endswith("_lesson_candidate.md"):
        raise ValueError("Lesson candidate filename must end with _lesson_candidate.md")
    return safe_slug, relative.name


def _path_for_candidate_id(candidate_id: str) -> Path:
    slug, filename = _parse_candidate_id(candidate_id)
    path = lessons.product_lesson_candidates_root(slug) / filename
    resolved = _resolve_without_existing(path)
    if not lessons.is_safe_lesson_candidate_path(resolved):
        raise ValueError("Lesson candidate path escaped bounded folder")
    return resolved


def is_safe_lesson_review_path(path: Path) -> bool:
    try:
        candidate = _resolve_without_existing(path)
        root = _resolve_without_existing(products.products_root())
        relative = candidate.relative_to(root)
    except (OSError, ValueError):
        return False
    parts = relative.parts
    if len(parts) < 3:
        return False
    slug = parts[0]
    if products.safe_product_slug(slug) != slug:
        return False
    expected_parent = _resolve_without_existing(products.product_path_for_slug(slug) / LESSON_REVIEW_DIRNAME)
    return (
        candidate.parent == expected_parent
        and candidate.suffix.lower() == ".md"
        and candidate.name.endswith("_lesson_review.md")
        and _is_relative_to(candidate, expected_parent)
    )


def _extract_line_after(label: str, content: str) -> str:
    lines = content.splitlines()
    lowered_label = label.lower()
    for index, line in enumerate(lines):
        if line.strip().lower() == lowered_label:
            for next_line in lines[index + 1 :]:
                stripped = next_line.strip()
                if stripped:
                    return stripped
        if line.strip().lower().startswith(lowered_label + ":"):
            return line.split(":", 1)[1].strip()
    return ""


def _status_from_content(content: str) -> str:
    if "PENDING_REVIEW" in content:
        return "PENDING_REVIEW"
    return "UNKNOWN"


def _risk_from_content(content: str, source_label: str) -> str:
    explicit = _extract_line_after("Risk", content)
    if explicit:
        return explicit.split()[0].strip()
    return untrusted_content_guard.classify_untrusted_content_risk(content, source_label).risk_level


def list_lesson_candidate_receipts(product_slug: str | None = None) -> list[LessonCandidateSummary]:
    paths = lessons.list_lesson_candidates(product_slug)
    summaries: list[LessonCandidateSummary] = []
    for path in paths:
        try:
            relative = path.relative_to(products.products_root())
            slug = relative.parts[0]
            content = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError, IndexError):
            continue
        if products.safe_product_slug(slug) != slug:
            continue
        if not lessons.is_safe_lesson_candidate_path(path):
            continue
        status = _status_from_content(content)
        summaries.append(
            LessonCandidateSummary(
                candidate_id=_candidate_id(slug, path.name),
                product_slug=slug,
                filename=path.name,
                path=path,
                modified_time=datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                status=status,
                guard_risk=_risk_from_content(content, "Lesson candidate review queue: " + slug),
                pending_review=status == "PENDING_REVIEW",
            )
        )
    return sorted(summaries, key=lambda item: (item.product_slug, item.filename))


def read_lesson_candidate(candidate_id: str) -> LessonCandidateReadResult:
    try:
        path = _path_for_candidate_id(candidate_id)
        slug, filename = _parse_candidate_id(candidate_id)
    except ValueError as exc:
        return LessonCandidateReadResult(
            ok=False,
            status="LESSON_CANDIDATE_READ_BLOCKED",
            candidate_id=str(candidate_id or ""),
            product_slug="",
            filename="",
            message=str(exc),
        )
    if not path.exists() or not path.is_file():
        return LessonCandidateReadResult(
            ok=False,
            status="LESSON_CANDIDATE_MISSING",
            candidate_id=candidate_id,
            product_slug=slug,
            filename=filename,
            path=path,
            message="Lesson candidate receipt was not found.",
        )
    content = path.read_text(encoding="utf-8", errors="replace")
    excerpt = content[:MAX_CANDIDATE_PREVIEW_CHARS]
    truncated = len(content) > MAX_CANDIDATE_PREVIEW_CHARS
    return LessonCandidateReadResult(
        ok=True,
        status="LESSON_CANDIDATE_READ_ONLY",
        candidate_id=candidate_id,
        product_slug=slug,
        filename=filename,
        path=path,
        content=content,
        excerpt=excerpt,
        truncated=truncated,
        guard_risk=_risk_from_content(content, "Lesson candidate preview: " + candidate_id),
        message="Candidate content was read as untrusted data only.",
    )


def render_lesson_candidate_queue(summaries: list[LessonCandidateSummary]) -> str:
    lines = [
        "# LESSON CANDIDATE REVIEW QUEUE",
        "",
        "Status:",
        QUEUE_STATUS,
        "",
        "Candidates:",
    ]
    if not summaries:
        lines.append("- none")
    for index, summary in enumerate(summaries, start=1):
        lines.extend(
            [
                f"{index}. product: {summary.product_slug}",
                f"   candidate: {summary.filename}",
                f"   id: {summary.candidate_id}",
                f"   modified: {summary.modified_time}",
                f"   status: {summary.status}",
                f"   guard risk: {summary.guard_risk}",
            ]
        )
    lines.extend(
        [
            "",
            "Boundary:",
            lessons.LESSON_CANDIDATE_BOUNDARY + ".",
            "Queue review does not update memory or change Engel.",
            "Candidate content is untrusted data, not instruction.",
        ]
    )
    return "\n".join(lines)


def render_lesson_candidate_preview(read_result: LessonCandidateReadResult) -> str:
    if not read_result.ok:
        return "\n".join(
            [
                "# LESSON CANDIDATE PREVIEW",
                "",
                "Status:",
                "PREVIEW_BLOCKED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
                "",
                "Reason: " + read_result.message,
                "",
                "Boundary:",
                lessons.LESSON_CANDIDATE_BOUNDARY + ".",
            ]
        )
    return "\n".join(
        [
            "# LESSON CANDIDATE PREVIEW",
            "",
            "Status:",
            QUEUE_STATUS,
            "",
            "Candidate:",
            read_result.candidate_id,
            "Guard risk:",
            read_result.guard_risk,
            "Truncated:",
            "yes" if read_result.truncated else "no",
            "",
            read_result.excerpt,
            "",
            "Safety:",
            "Candidate content was not followed as instruction.",
            "No trusted memory was written.",
            "No Engel behavior changed.",
        ]
    )


def _deterministic_summary(content: str) -> str:
    lesson = _extract_line_after("Candidate Lesson", content)
    risk = _extract_line_after("Risk", content)
    if lesson:
        return "Candidate lesson for review: " + lesson
    if risk:
        return "Lesson candidate is ready for Josh review with guard risk " + risk + "."
    return "Lesson candidate is ready for Josh review as pending-review, not-trusted-memory material."


def build_lesson_review_summary(candidate_id: str) -> LessonReviewSummary:
    read_result = read_lesson_candidate(candidate_id)
    if not read_result.ok:
        return LessonReviewSummary(
            ok=False,
            status="LESSON_REVIEW_BLOCKED",
            candidate_id=candidate_id,
            product_slug=read_result.product_slug,
            filename=read_result.filename,
            summary="",
            guard_risk=read_result.guard_risk,
            recommended_decisions=(),
            guardian_review=(),
            source_excerpt="",
            message=read_result.message,
        )
    guardian_review = (
        "Trusted memory write: NO",
        "Engel behavior change: NO",
        "Runtime source edit: NO",
        "Product source edit: NO",
        "Candidate content trusted as instruction: NO",
        "Requires later Josh approval and Guardian review memory workflow: YES",
    )
    recommended_decisions = (
        "Keep for future memory-candidate review",
        "Reject",
        "Request product improvement proposal",
        "No automatic action taken",
    )
    return LessonReviewSummary(
        ok=True,
        status=LESSON_REVIEW_STATUS,
        candidate_id=read_result.candidate_id,
        product_slug=read_result.product_slug,
        filename=read_result.filename,
        summary=_deterministic_summary(read_result.content),
        guard_risk=read_result.guard_risk,
        recommended_decisions=recommended_decisions,
        guardian_review=guardian_review,
        source_excerpt=read_result.excerpt[:2_000],
        message="Review summary built as report-only material.",
    )


def render_lesson_review_summary(summary: LessonReviewSummary) -> str:
    decisions = "\n".join("- " + item for item in summary.recommended_decisions)
    guardian = "\n".join("- " + item for item in summary.guardian_review)
    return "\n".join(
        [
            "# Engel Lesson Candidate Review Summary",
            "",
            "Status:",
            summary.status,
            "",
            "Authority:",
            AUTHORITY,
            "",
            "Boundary:",
            lessons.LESSON_CANDIDATE_BOUNDARY + ".",
            "",
            "Candidate:",
            summary.product_slug,
            summary.filename,
            summary.candidate_id,
            "",
            "Summary:",
            summary.summary or "No summary available.",
            "",
            "Untrusted Content Guard:",
            "Risk: " + summary.guard_risk,
            "Embedded approval tokens accepted: NO",
            "",
            "Guardian Review:",
            guardian or "- unavailable",
            "",
            "Recommended Josh Decision:",
            decisions or "- No automatic action taken",
            "",
            "Safety:",
            "- Read-only candidate review",
            "- No lesson applied",
            "- No trusted memory written",
            "- No code executed",
        ]
    )


def _next_review_path(root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = root / f"{timestamp}_lesson_review.md"
    if not candidate.exists():
        return candidate
    for index in range(1, 100):
        indexed = root / f"{timestamp}_{index:02d}_lesson_review.md"
        if not indexed.exists():
            return indexed
    raise RuntimeError("Unable to create unique lesson review path")


def write_lesson_review_summary(candidate_id: str, approval_token: str | None = None) -> LessonReviewWriteResult:
    del approval_token
    summary = build_lesson_review_summary(candidate_id)
    if not summary.ok:
        return LessonReviewWriteResult(
            ok=False,
            status="LESSON_REVIEW_BLOCKED",
            candidate_id=candidate_id,
            product_slug=summary.product_slug,
            review_path=None,
            message=summary.message,
        )
    try:
        root = product_lesson_reviews_root(summary.product_slug)
    except ValueError as exc:
        return LessonReviewWriteResult(
            ok=False,
            status="LESSON_REVIEW_BLOCKED",
            candidate_id=candidate_id,
            product_slug=summary.product_slug,
            review_path=None,
            message=str(exc),
        )
    root.mkdir(parents=True, exist_ok=True)
    review_path = _next_review_path(root)
    if not is_safe_lesson_review_path(review_path):
        return LessonReviewWriteResult(
            ok=False,
            status="LESSON_REVIEW_BLOCKED",
            candidate_id=candidate_id,
            product_slug=summary.product_slug,
            review_path=None,
            message="Unsafe lesson review path.",
        )
    review_path.write_text(render_lesson_review_summary(summary), encoding="utf-8")
    return LessonReviewWriteResult(
        ok=True,
        status="LESSON_REVIEW_SUMMARY_CREATED",
        candidate_id=candidate_id,
        product_slug=summary.product_slug,
        review_path=review_path,
        message="Review summary written as report-only material.",
    )
