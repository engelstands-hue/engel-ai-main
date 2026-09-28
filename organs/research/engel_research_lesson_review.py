from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

import engel_untrusted_content_guard as untrusted_content_guard


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
REVIEW_STATUS = "READY_FOR_JOSH_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"
RESEARCH_LESSON_BOUNDARY = "Research Lesson Candidate \u2260 Trusted Memory"
REVIEW_BOUNDARY = "Research Lesson Review \u2260 Trusted Memory"
MAX_CANDIDATE_READ_CHARS = 24_000


@dataclass(frozen=True)
class ResearchLessonCandidateSummary:
    candidate_id: str
    modified_time: str
    risk_level: str
    status: str
    source_summary_id: str


@dataclass(frozen=True)
class ResearchLessonReadResult:
    candidate_id: str
    path: Path
    text: str
    risk_level: str
    status: str
    source_summary_id: str
    markers_found: tuple[str, ...]


@dataclass(frozen=True)
class ResearchLessonReview:
    candidate_id: str
    risk_level: str
    status: str
    source_summary_id: str
    summary: str
    markers_found: tuple[str, ...]
    generated_at: str


@dataclass(frozen=True)
class ResearchLessonReviewWriteResult:
    status: str
    path: Path
    review: ResearchLessonReview


def research_lesson_candidates_root() -> Path:
    return APP_ROOT / "reports" / "research_intake" / "lesson_candidates"


def research_lesson_reviews_root() -> Path:
    return APP_ROOT / "reports" / "research_intake" / "lesson_reviews"


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _is_safe_candidate_path(path: Path) -> bool:
    return path.exists() and path.is_file() and path.suffix.lower() == ".md" and _is_relative_to(path, research_lesson_candidates_root())


def _is_safe_review_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
        root = research_lesson_reviews_root().resolve()
    except (OSError, RuntimeError):
        return False
    return resolved == root or root in resolved.parents


def _reject_raw_id(candidate_id: str) -> None:
    value = str(candidate_id or "").strip()
    if not value:
        raise ValueError("candidate_id is required")
    if "://" in value or value.startswith("\\\\"):
        raise ValueError("candidate_id must be a bounded handle, not a URL/UNC path")
    candidate = Path(value)
    if candidate.is_absolute() or candidate.drive:
        raise ValueError("candidate_id must not be an absolute path or drive path")
    if any(part in {"..", "", ".", "/"} for part in candidate.parts):
        raise ValueError("candidate_id must not traverse directories")
    if len(candidate.parts) != 1 or "\\" in value or "/" in value:
        raise ValueError("candidate_id must be a filename-only bounded handle")
    if candidate.suffix.lower() != ".md":
        raise ValueError("candidate_id must identify a markdown research lesson candidate")


def safe_research_lesson_candidate_id(path: Path) -> str:
    if not _is_safe_candidate_path(path):
        raise ValueError("candidate path is outside reports\\research_intake\\lesson_candidates")
    return path.name


def resolve_research_lesson_candidate_id(candidate_id: str) -> Path:
    _reject_raw_id(candidate_id)
    path = research_lesson_candidates_root() / str(candidate_id).strip()
    if not _is_safe_candidate_path(path):
        raise ValueError("candidate_id did not resolve to a bounded research lesson candidate")
    return path


def _extract_block(text: str, label: str) -> str:
    pattern = re.compile(r"(?im)^" + re.escape(label) + r":\s*$\n(?P<value>.+?)(?:\n\s*\n|$)", re.S)
    match = pattern.search(text)
    if match:
        return match.group("value").strip()
    inline = re.compile(r"(?im)^" + re.escape(label) + r":\s*(?P<value>.+)$")
    match = inline.search(text)
    return match.group("value").strip() if match else ""


def _extract_inline(text: str, label: str) -> str:
    pattern = re.compile(r"(?im)^" + re.escape(label) + r":\s*(?P<value>.+)$")
    match = pattern.search(text)
    return match.group("value").strip() if match else ""


def _extract_risk(text: str) -> str:
    risk = (_extract_block(text, "Risk") or _extract_inline(text, "Risk")).upper()
    for value in ("BLOCKED", "HIGH", "MEDIUM", "LOW"):
        if value in risk:
            return value
    if "BLOCKED_RISK_LESSON_CANDIDATE" in text:
        return "BLOCKED"
    return "LOW"


def _risk_rank(risk_level: str) -> int:
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "BLOCKED": 3}.get(risk_level, 0)


def _max_risk(*risk_levels: str) -> str:
    return max((str(risk or "LOW").upper() for risk in risk_levels), key=_risk_rank)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _modified_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip().lower()).strip("_")
    return cleaned[:80] or "research_lesson_review"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 100):
        candidate = path.with_name(f"{stem}_{index:02d}{suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError("could not create unique research lesson review path")


def list_research_lesson_candidates() -> list[ResearchLessonCandidateSummary]:
    root = research_lesson_candidates_root()
    if not root.exists():
        return []
    summaries: list[ResearchLessonCandidateSummary] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not _is_safe_candidate_path(path):
            continue
        read = read_research_lesson_candidate(path.name)
        summaries.append(
            ResearchLessonCandidateSummary(
                candidate_id=path.name,
                modified_time=_modified_time(path),
                risk_level=read.risk_level,
                status=read.status,
                source_summary_id=read.source_summary_id,
            )
        )
    return summaries


def read_research_lesson_candidate(candidate_id: str) -> ResearchLessonReadResult:
    path = resolve_research_lesson_candidate_id(candidate_id)
    text = untrusted_content_guard.safe_excerpt(path.read_text(encoding="utf-8", errors="replace"), MAX_CANDIDATE_READ_CHARS)
    guard = untrusted_content_guard.classify_untrusted_content_risk(text, "Research Lesson Candidate: " + path.name)
    risk = _max_risk(_extract_risk(text), guard.risk_level)
    source_block = _extract_block(text, "Source")
    return ResearchLessonReadResult(
        candidate_id=path.name,
        path=path,
        text=text,
        risk_level=risk,
        status=_extract_block(text, "Status") or "PENDING_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        source_summary_id=_extract_inline(source_block, "Summary proposal ID") or "unknown",
        markers_found=tuple(guard.markers_found),
    )


def _review_summary(candidate_text: str, risk_level: str) -> str:
    lesson = _extract_block(candidate_text, "Candidate Lesson") or candidate_text
    normalized = untrusted_content_guard.normalize_untrusted_text(lesson)
    prefix = "Review candidate for Josh decision."
    if risk_level == "BLOCKED":
        prefix = "Blocked-risk candidate: review only as a safety finding."
    elif risk_level == "HIGH":
        prefix = "High-risk candidate: Guardian review is required before any future use."
    return prefix + " " + untrusted_content_guard.safe_excerpt(normalized, 1000)


def build_research_lesson_review(candidate_id: str) -> ResearchLessonReview:
    read = read_research_lesson_candidate(candidate_id)
    return ResearchLessonReview(
        candidate_id=read.candidate_id,
        risk_level=read.risk_level,
        status=REVIEW_STATUS,
        source_summary_id=read.source_summary_id,
        summary=_review_summary(read.text, read.risk_level),
        markers_found=read.markers_found,
        generated_at=_timestamp(),
    )


def render_research_lesson_review(review: ResearchLessonReview) -> str:
    markers = list(review.markers_found) or ["none"]
    return "\n".join(
        [
            "# Engel Research Lesson Review Summary",
            "",
            "Status:",
            review.status,
            "",
            "Authority:",
            AUTHORITY,
            "",
            "Source:",
            "Research Lesson Candidate",
            "Candidate ID: " + review.candidate_id,
            "Source summary proposal ID: " + review.source_summary_id,
            "",
            "Boundary:",
            RESEARCH_LESSON_BOUNDARY + ".",
            REVIEW_BOUNDARY + ".",
            "This review does not update Engel memory.",
            "This review does not change Engel behavior.",
            "",
            "Untrusted Content Guard:",
            "Risk: " + review.risk_level,
            "Markers: " + ", ".join(markers),
            "Embedded approval tokens accepted: NO",
            "",
            "Summary:",
            review.summary,
            "",
            "Guardian Review:",
            "- Trusted memory write: NO",
            "- Engel behavior change: NO",
            "- Runtime source edit: NO",
            "- Product source edit: NO",
            "- Browser/API/network action: NO",
            "- Candidate content trusted as instruction: NO",
            "- Requires later Josh/Guardian memory workflow: YES",
            "",
            "Recommended Josh Decision:",
            "- Keep for future memory-candidate review",
            "- Reject",
            "- Request more research",
            "- Request product/code proposal",
            "- No automatic action taken",
            "",
            "Safety:",
            "- Read-only review",
            "- No lesson applied",
            "- No trusted memory written",
            "- No code executed",
            "",
        ]
    )


def write_research_lesson_review(candidate_id: str) -> ResearchLessonReviewWriteResult:
    review = build_research_lesson_review(candidate_id)
    root = research_lesson_reviews_root()
    path = root / f"{review.generated_at}_{_slug(Path(review.candidate_id).stem)}_research_lesson_review.md"
    path = _unique_path(path)
    if not _is_safe_review_path(path):
        raise ValueError("research lesson review path escaped reports\\research_intake\\lesson_reviews")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_research_lesson_review(review), encoding="utf-8")
    return ResearchLessonReviewWriteResult(status=review.status, path=path, review=review)


if __name__ == "__main__":
    for item in list_research_lesson_candidates():
        print(item.candidate_id, item.risk_level, item.status)
