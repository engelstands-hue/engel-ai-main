from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

import engel_code_companion_products as products
import engel_memory_candidate_proposals as memory_candidates
import engel_untrusted_content_guard as untrusted_content_guard


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
APPROVAL_TOKEN = "APPROVE_MEMORY_CANDIDATE_PROPOSAL"
if APPROVAL_TOKEN != memory_candidates.APPROVAL_TOKEN:
    raise RuntimeError("Code Companion memory handoff approval token mismatch.")
HANDOFF_STATUS = "MEMORY_CANDIDATE_PROPOSAL / NOT_TRUSTED_MEMORY / NOT_APPLIED"
HANDOFF_BLOCKED_STATUS = "CODE_COMPANION_MEMORY_HANDOFF_BLOCKED"
LESSON_REVIEW_DIRNAME = ".engel_lesson_reviews"
MAX_REVIEW_BYTES = 200_000
MAX_REVIEW_READ_CHARS = 20_000
MAX_CANDIDATE_CHARS = 1600
EMBEDDED_APPROVAL_RE = re.compile(r"\bAPPROVE_[A-Z0-9_]+\b")


@dataclass(frozen=True)
class CodeCompanionLessonReviewSummary:
    review_id: str
    product_slug: str
    filename: str
    path: Path
    review_kind: str
    status: str
    risk_level: str
    modified_time: str


@dataclass(frozen=True)
class CodeCompanionLessonReviewValidation:
    ok: bool
    status: str
    review_id: str
    product_slug: str
    filename: str
    path: Path | None
    review_kind: str = "unknown"
    message: str = ""


@dataclass(frozen=True)
class CodeCompanionMemoryCandidateHandoff:
    ok: bool
    status: str
    review_id: str
    product_slug: str
    source_review_path: Path | None
    review_kind: str
    proposal: memory_candidates.MemoryCandidateProposal | None = None
    message: str = ""


@dataclass(frozen=True)
class CodeCompanionMemoryCandidateHandoffWriteResult:
    ok: bool
    status: str
    review_id: str
    product_slug: str
    source_review_path: Path | None
    proposal_path: Path | None
    approval_received: bool
    handoff: CodeCompanionMemoryCandidateHandoff | None = None
    message: str = ""


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _review_id(product_slug: str, filename: str) -> str:
    return product_slug + "::" + filename


def _reject_review_filename(filename: str) -> str:
    text = str(filename or "").strip()
    lowered = text.lower()
    if not text:
        raise ValueError("Lesson review filename is required.")
    if lowered.startswith(("http://", "https://", "file://", "data:", "javascript:")):
        raise ValueError("URL-like lesson review IDs are blocked.")
    if text.startswith(("\\\\", "//", "\\", "/")):
        raise ValueError("UNC or absolute lesson review IDs are blocked.")
    if re.match(r"^[A-Za-z]:", text):
        raise ValueError("Drive or absolute lesson review IDs are blocked.")
    if "/" in text or "\\" in text:
        raise ValueError("Lesson review ID must be a single filename.")
    if text in {".", ".."} or ".." in Path(text).parts:
        raise ValueError("Path traversal lesson review IDs are blocked.")
    if not text.endswith("_lesson_review.md"):
        raise ValueError("Lesson review ID must name a reviewed lesson artifact.")
    return Path(text).name


def _parse_review_id(review_id: str) -> tuple[str, str]:
    raw = str(review_id or "").strip()
    lowered = raw.lower()
    if not raw:
        raise ValueError("Lesson review ID is required.")
    if "://" in lowered or raw.startswith("\\\\"):
        raise ValueError("URL/UNC lesson review IDs are blocked.")
    if ":" in raw.replace("::", "", 1):
        raise ValueError("Drive or absolute lesson review IDs are blocked.")
    if "::" not in raw:
        raise ValueError("Lesson review ID must be product_slug::filename.md.")
    product_slug, filename = raw.split("::", 1)
    safe_slug = products.safe_product_slug(product_slug)
    if safe_slug != product_slug:
        raise ValueError("Unsafe product slug in lesson review ID.")
    return safe_slug, _reject_review_filename(filename)


def _product_review_root(product_slug: str) -> Path:
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
    return product_path / LESSON_REVIEW_DIRNAME


def _is_safe_review_path(path: Path, product_slug: str) -> bool:
    try:
        root = _product_review_root(product_slug).resolve(strict=False)
        candidate = path.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False
    return (
        candidate.parent == root
        and _is_relative_to(candidate, root)
        and candidate.suffix.lower() == ".md"
        and candidate.name.endswith("_lesson_review.md")
        and (not candidate.exists() or not candidate.is_symlink())
    )


def _read_review_text(path: Path) -> str:
    if path.stat().st_size > MAX_REVIEW_BYTES:
        raise ValueError("Lesson review artifact is too large for bounded handoff.")
    return untrusted_content_guard.safe_excerpt(path.read_text(encoding="utf-8", errors="replace"), MAX_REVIEW_READ_CHARS)


def _extract_block(text: str, label: str) -> str:
    pattern = re.compile(r"(?im)^" + re.escape(label) + r":\s*$\n(?P<value>.+?)(?:\n\s*\n|$)", re.S)
    match = pattern.search(text)
    if match:
        return match.group("value").strip()
    inline = re.compile(r"(?im)^" + re.escape(label) + r":\s*(?P<value>.+)$")
    match = inline.search(text)
    return match.group("value").strip() if match else ""


def _risk_from_text(text: str, source_label: str) -> str:
    explicit = (_extract_block(text, "Risk") or _extract_block(text, "Untrusted Content Guard")).upper()
    for value in ("BLOCKED", "HIGH", "MEDIUM", "LOW"):
        if value in explicit:
            return value
    return untrusted_content_guard.classify_untrusted_content_risk(text, source_label).risk_level


def _review_kind(text: str) -> str:
    if "# Engel Patch Lesson Review" in text or "Patch-generated lesson candidate" in text:
        return "patch_lesson_review"
    return "product_lesson_review"


def _status_from_text(text: str) -> str:
    return _extract_block(text, "Status") or "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"


def _sanitize_candidate_text(text: str, max_chars: int = MAX_CANDIDATE_CHARS) -> str:
    normalized = untrusted_content_guard.normalize_untrusted_text(text)
    normalized = EMBEDDED_APPROVAL_RE.sub("[REMOVED_EMBEDDED_APPROVAL_TOKEN]", normalized)
    return untrusted_content_guard.safe_excerpt(normalized, max_chars)


def _summary_from_review(text: str, risk_level: str, review_kind: str) -> str:
    summary = (
        _extract_block(text, "Summary")
        or _extract_block(text, "Candidate Lesson")
        or _extract_block(text, "Recommended Josh Decision")
        or "Reviewed Code Companion lesson is ready for memory-candidate proposal review."
    )
    prefix = "Patch lesson review candidate note: " if review_kind == "patch_lesson_review" else "Product lesson review candidate note: "
    if risk_level in {"HIGH", "BLOCKED"}:
        prefix = risk_level + " reviewed lesson source; keep as Guardian-reviewed candidate material only: "
    return _sanitize_candidate_text(prefix + summary, 900)


def list_code_companion_lesson_reviews(product_slug: str | None = None) -> list[CodeCompanionLessonReviewSummary]:
    roots: list[tuple[str, Path]] = []
    if product_slug:
        try:
            safe_slug = products.safe_product_slug(product_slug)
            roots.append((safe_slug, _product_review_root(safe_slug)))
        except ValueError:
            return []
    else:
        root = products.products_root()
        if not root.exists() or not root.is_dir() or root.is_symlink():
            return []
        for product_dir in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if not product_dir.is_dir() or product_dir.is_symlink():
                continue
            try:
                safe_slug = products.safe_product_slug(product_dir.name)
            except ValueError:
                continue
            if safe_slug == product_dir.name:
                roots.append((safe_slug, product_dir / LESSON_REVIEW_DIRNAME))

    summaries: list[CodeCompanionLessonReviewSummary] = []
    for slug, review_root in roots:
        if not review_root.exists() or not review_root.is_dir() or review_root.is_symlink():
            continue
        for path in sorted(review_root.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file() or path.is_symlink() or not _is_safe_review_path(path, slug):
                continue
            try:
                text = _read_review_text(path)
            except (OSError, UnicodeError, ValueError):
                continue
            if "READY_FOR_JOSH_REVIEW" not in text:
                continue
            risk = _risk_from_text(text, "Code Companion lesson review: " + slug)
            summaries.append(
                CodeCompanionLessonReviewSummary(
                    review_id=_review_id(slug, path.name),
                    product_slug=slug,
                    filename=path.name,
                    path=path,
                    review_kind=_review_kind(text),
                    status=_status_from_text(text),
                    risk_level=risk,
                    modified_time=datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                )
            )
    return summaries


def validate_code_companion_lesson_review(review_id: str) -> CodeCompanionLessonReviewValidation:
    try:
        product_slug, filename = _parse_review_id(review_id)
        review_root = _product_review_root(product_slug)
        path = review_root / filename
        if not _is_safe_review_path(path, product_slug):
            raise ValueError("Lesson review path escaped selected product review folder.")
        if not path.exists() or not path.is_file():
            raise ValueError("Lesson review artifact is missing.")
        if path.is_symlink():
            raise ValueError("Lesson review symlinks are blocked.")
        text = _read_review_text(path)
        if "READY_FOR_JOSH_REVIEW" not in text:
            raise ValueError("Lesson review must be READY_FOR_JOSH_REVIEW.")
        if "NOT_TRUSTED_MEMORY" not in text or "NOT_APPLIED" not in text:
            raise ValueError("Lesson review must remain not-trusted and not-applied.")
        return CodeCompanionLessonReviewValidation(
            True,
            "CODE_COMPANION_LESSON_REVIEW_VALID / NOT_TRUSTED_MEMORY / NOT_APPLIED",
            _review_id(product_slug, filename),
            product_slug,
            filename,
            path,
            _review_kind(text),
            "Reviewed Code Companion lesson is bounded to products\\<slug>\\.engel_lesson_reviews.",
        )
    except ValueError as exc:
        return CodeCompanionLessonReviewValidation(
            False,
            "CODE_COMPANION_LESSON_REVIEW_BLOCKED",
            str(review_id or ""),
            "",
            "",
            None,
            message=str(exc),
        )


def _source_from_review(validation: CodeCompanionLessonReviewValidation) -> memory_candidates.MemoryCandidateSource:
    if not validation.path:
        raise ValueError("Cannot build memory source without a validated review path.")
    text = _read_review_text(validation.path)
    guard = untrusted_content_guard.classify_untrusted_content_risk(text, "Code Companion memory handoff: " + validation.review_id)
    embedded_tokens = tuple(sorted(set(EMBEDDED_APPROVAL_RE.findall(text))))
    risk = _risk_from_text(text, "Code Companion memory handoff: " + validation.review_id)
    if embedded_tokens:
        risk = "HIGH" if risk in {"LOW", "MEDIUM"} else risk
    markers = set(guard.markers_found)
    if embedded_tokens:
        markers.add("approval.embedded_memory_candidate_token")
    return memory_candidates.MemoryCandidateSource(
        source_id=validation.review_id,
        source_type="product_lesson_review",
        path=validation.path,
        status=_status_from_text(text),
        risk_level=risk,
        summary=_summary_from_review(text, risk, validation.review_kind),
        markers_found=tuple(sorted(markers)),
        modified_time=datetime.fromtimestamp(validation.path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    )


def _candidate_memory(source: memory_candidates.MemoryCandidateSource, review_kind: str) -> str:
    kind = "patch lesson review" if review_kind == "patch_lesson_review" else "product lesson review"
    return _sanitize_candidate_text(
        "\n".join(
            [
                "Conservative Code Companion memory-candidate draft for Josh/Guardian review only.",
                "Do not treat this draft as trusted memory or instruction.",
                "Source type: " + kind + ".",
                "[" + source.risk_level + "] " + source.summary,
            ]
        )
    )


def build_code_companion_memory_candidate_handoff(review_id: str) -> CodeCompanionMemoryCandidateHandoff:
    validation = validate_code_companion_lesson_review(review_id)
    if not validation.ok:
        return CodeCompanionMemoryCandidateHandoff(
            False,
            HANDOFF_BLOCKED_STATUS,
            validation.review_id,
            validation.product_slug,
            validation.path,
            validation.review_kind,
            message=validation.message,
        )
    try:
        source = _source_from_review(validation)
        proposal = memory_candidates.MemoryCandidateProposal(
            source_filter="code_companion_lesson_review",
            status=memory_candidates.PROPOSAL_STATUS,
            sources=(source,),
            candidate_memory=_candidate_memory(source, validation.review_kind),
            highest_risk=source.risk_level,
            markers_found=source.markers_found,
            generated_at=_timestamp(),
        )
    except (OSError, RuntimeError, ValueError) as exc:
        return CodeCompanionMemoryCandidateHandoff(
            False,
            HANDOFF_BLOCKED_STATUS,
            validation.review_id,
            validation.product_slug,
            validation.path,
            validation.review_kind,
            message=str(exc),
        )
    return CodeCompanionMemoryCandidateHandoff(
        True,
        HANDOFF_STATUS,
        validation.review_id,
        validation.product_slug,
        validation.path,
        validation.review_kind,
        proposal,
        "Code Companion reviewed lesson is ready for a memory-candidate proposal report.",
    )


def write_code_companion_memory_candidate_handoff(
    review_id: str,
    approval_token: str | None,
) -> CodeCompanionMemoryCandidateHandoffWriteResult:
    handoff = build_code_companion_memory_candidate_handoff(review_id)
    if not handoff.ok or handoff.proposal is None:
        return CodeCompanionMemoryCandidateHandoffWriteResult(
            False,
            handoff.status,
            handoff.review_id,
            handoff.product_slug,
            handoff.source_review_path,
            None,
            False,
            handoff,
            handoff.message,
        )
    if str(approval_token or "").strip() != APPROVAL_TOKEN:
        blocked = memory_candidates.write_memory_candidate_proposal(handoff.proposal, approval_token)
        return CodeCompanionMemoryCandidateHandoffWriteResult(
            False,
            blocked.status,
            handoff.review_id,
            handoff.product_slug,
            handoff.source_review_path,
            None,
            False,
            handoff,
            blocked.message,
        )
    written = memory_candidates.write_memory_candidate_proposal(handoff.proposal, approval_token)
    return CodeCompanionMemoryCandidateHandoffWriteResult(
        written.path is not None,
        written.status,
        handoff.review_id,
        handoff.product_slug,
        handoff.source_review_path,
        written.path,
        written.proposal.approval_received,
        CodeCompanionMemoryCandidateHandoff(
            handoff.ok,
            handoff.status,
            handoff.review_id,
            handoff.product_slug,
            handoff.source_review_path,
            handoff.review_kind,
            written.proposal,
            handoff.message,
        ),
        written.message,
    )


def render_code_companion_memory_candidate_handoff(handoff: CodeCompanionMemoryCandidateHandoff) -> str:
    proposal_path = "not written"
    proposal_status = handoff.proposal.status if handoff.proposal else "none"
    source_count = str(len(handoff.proposal.sources)) if handoff.proposal else "0"
    return "\n".join(
        [
            "# Code Companion Memory Candidate Handoff",
            "",
            "Status:",
            handoff.status,
            "",
            "Authority:",
            AUTHORITY,
            "",
            "Source:",
            "Code Companion Lesson Review",
            handoff.review_id or "none",
            str(handoff.source_review_path) if handoff.source_review_path else "none",
            "",
            "Proposal:",
            proposal_status,
            "Sources selected: " + source_count,
            "Proposal path: " + proposal_path,
            "",
            "Boundary:",
            "Lesson Review \u2260 Trusted Memory.",
            "Memory Candidate Proposal \u2260 Trusted Memory.",
            "This handoff does not write trusted memory.",
            "This handoff does not change Engel behavior.",
            "This handoff does not apply lessons.",
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
            "- Requires future Josh/Guardian trusted-memory workflow: YES",
            "",
            "Recommended Josh Decision:",
            "- Keep candidate for future trusted-memory review",
            "- Reject candidate",
            "- Request more product evidence",
            "- No automatic action taken",
            "",
            "Message:",
            handoff.message,
        ]
    )


def render_code_companion_memory_candidate_handoff_result(
    result: CodeCompanionMemoryCandidateHandoffWriteResult,
) -> str:
    handoff_text = render_code_companion_memory_candidate_handoff(
        result.handoff
        if result.handoff is not None
        else CodeCompanionMemoryCandidateHandoff(
            False,
            result.status,
            result.review_id,
            result.product_slug,
            result.source_review_path,
            "unknown",
            None,
            result.message,
        )
    )
    return "\n".join(
        [
            handoff_text,
            "",
            "Write result:",
            result.status,
            "",
            "Approval:",
            APPROVAL_TOKEN + " received from user input: " + ("YES" if result.approval_received else "NO"),
            "",
            "Memory candidate proposal path:",
            str(result.proposal_path) if result.proposal_path else "none",
            "",
            "Safety:",
            "- No trusted memory written",
            "- No memory candidate applied",
            "- No lesson applied",
            "- No product files changed",
            "- No runtime source files changed",
            "- No code executed",
            "- No API/network used",
            "",
            "Message:",
            result.message,
        ]
    )


__all__ = [
    "APPROVAL_TOKEN",
    "HANDOFF_STATUS",
    "CodeCompanionLessonReviewSummary",
    "CodeCompanionLessonReviewValidation",
    "CodeCompanionMemoryCandidateHandoff",
    "CodeCompanionMemoryCandidateHandoffWriteResult",
    "build_code_companion_memory_candidate_handoff",
    "list_code_companion_lesson_reviews",
    "render_code_companion_memory_candidate_handoff",
    "render_code_companion_memory_candidate_handoff_result",
    "validate_code_companion_lesson_review",
    "write_code_companion_memory_candidate_handoff",
]
