from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
import re

import engel_untrusted_content_guard as untrusted_content_guard


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
APPROVAL_TOKEN = "APPROVE_RESEARCH_LESSON_CANDIDATE"
RESEARCH_PATH = "Research Intake \u2192 Research Office / Overnight Research"
LESSON_STATUS = "PENDING_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"
BLOCKED_LESSON_STATUS = "BLOCKED_RISK_LESSON_CANDIDATE / PENDING_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"
BLOCKED_WRITE_STATUS = "RESEARCH_LESSON_CANDIDATE_BLOCKED / APPROVE_RESEARCH_LESSON_CANDIDATE_REQUIRED"
SUMMARY_BOUNDARY = "Research Summary Proposal \u2260 Trusted Memory"
INTAKE_BOUNDARY = "Research Intake \u2260 Trusted Memory"
RESEARCH_LESSON_BOUNDARY = "Research Lesson Candidate \u2260 Trusted Memory"
LESSON_BOUNDARY = "Lesson Candidate \u2260 Trusted Memory"
MAX_SUMMARY_READ_CHARS = 24_000
MAX_LESSON_CHARS = 1200


@dataclass(frozen=True)
class ResearchSummaryCandidateSource:
    summary_id: str
    modified_time: str
    source_receipt_id: str
    source_type: str
    source_label: str
    risk_level: str
    status: str


@dataclass(frozen=True)
class ResearchLessonCandidate:
    summary_id: str
    source_receipt_id: str
    source_type: str
    source_label: str
    risk_level: str
    status: str
    candidate_lesson: str
    markers_found: tuple[str, ...]
    summary_excerpt: str
    generated_at: str
    approval_received: bool = False
    authority: str = AUTHORITY
    research_path: str = RESEARCH_PATH


@dataclass(frozen=True)
class ResearchLessonCandidateWriteResult:
    status: str
    path: Path | None
    message: str
    candidate: ResearchLessonCandidate


def research_summary_root() -> Path:
    return APP_ROOT / "reports" / "research_intake" / "summaries"


def research_intake_receipts_root() -> Path:
    return APP_ROOT / "reports" / "research_intake" / "receipts"


def research_lesson_candidates_root() -> Path:
    return APP_ROOT / "reports" / "research_intake" / "lesson_candidates"


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def is_safe_research_lesson_candidate_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
        root = research_lesson_candidates_root().resolve()
    except (OSError, RuntimeError):
        return False
    return resolved == root or root in resolved.parents


def _is_safe_summary_path(path: Path) -> bool:
    return path.exists() and path.is_file() and path.suffix.lower() == ".md" and _is_relative_to(path, research_summary_root())


def _reject_raw_id(summary_id: str) -> None:
    value = str(summary_id or "").strip()
    if not value:
        raise ValueError("summary_id is required")
    if "://" in value or value.startswith("\\\\"):
        raise ValueError("summary_id must be a bounded handle, not a URL/UNC path")
    candidate = Path(value)
    if candidate.is_absolute() or candidate.drive:
        raise ValueError("summary_id must not be an absolute path or drive path")
    if any(part in {"..", "", ".", "/"} for part in candidate.parts):
        raise ValueError("summary_id must not traverse directories")
    if len(candidate.parts) != 1 or "\\" in value or "/" in value:
        raise ValueError("summary_id must be a filename-only bounded handle")
    if candidate.suffix.lower() != ".md":
        raise ValueError("summary_id must identify a markdown summary proposal")


def safe_research_summary_id(path: Path) -> str:
    if not _is_safe_summary_path(path):
        raise ValueError("summary path is outside reports\\research_intake\\summaries")
    return path.name


def resolve_research_summary_id(summary_id: str) -> Path:
    _reject_raw_id(summary_id)
    path = research_summary_root() / str(summary_id).strip()
    if not _is_safe_summary_path(path):
        raise ValueError("summary_id did not resolve to a bounded Research Summary Proposal")
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
    if "BLOCKED / REPORT_ONLY" in text:
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
    return cleaned[:80] or "research_lesson_candidate"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 100):
        candidate = path.with_name(f"{stem}_{index:02d}{suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError("could not create unique research lesson candidate path")


def _summary_text(path: Path) -> str:
    return untrusted_content_guard.safe_excerpt(path.read_text(encoding="utf-8", errors="replace"), MAX_SUMMARY_READ_CHARS)


def _summary_source(text: str, summary_id: str) -> ResearchSummaryCandidateSource:
    guard = untrusted_content_guard.classify_untrusted_content_risk(text, "Research Summary Proposal: " + summary_id)
    embedded_research_token = APPROVAL_TOKEN in text
    risk = _max_risk(_extract_risk(text), guard.risk_level, "HIGH" if embedded_research_token else "LOW")
    source_block = _extract_block(text, "Source")
    return ResearchSummaryCandidateSource(
        summary_id=summary_id,
        modified_time="",
        source_receipt_id=_extract_inline(source_block, "Receipt ID") or "unknown",
        source_type=_extract_inline(source_block, "Source type") or _extract_block(text, "Source type") or "unknown",
        source_label=_extract_inline(source_block, "Source label") or _extract_block(text, "Source label") or summary_id,
        risk_level=risk,
        status=_extract_block(text, "Status") or "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED",
    )


def list_research_summary_proposals() -> list[ResearchSummaryCandidateSource]:
    root = research_summary_root()
    if not root.exists():
        return []
    result: list[ResearchSummaryCandidateSource] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not _is_safe_summary_path(path):
            continue
        summary_id = safe_research_summary_id(path)
        source = _summary_source(_summary_text(path), summary_id)
        result.append(replace(source, modified_time=_modified_time(path)))
    return result


def _candidate_lesson(text: str, risk_level: str) -> str:
    if risk_level == "BLOCKED":
        return (
            "Blocked research content must not be learned, applied, or used as instruction. "
            "Keep only the safety finding for Josh/Guardian review."
        )
    summary = _extract_block(text, "Summary") or text
    normalized = untrusted_content_guard.normalize_untrusted_text(summary)
    if risk_level == "HIGH":
        prefix = "High-risk research should remain Guardian-reviewed before it informs future decisions: "
    elif risk_level == "MEDIUM":
        prefix = "Medium-risk research should be treated cautiously as an untrusted note: "
    else:
        prefix = "Research Office can retain this pending lesson candidate for review: "
    return prefix + untrusted_content_guard.safe_excerpt(normalized, MAX_LESSON_CHARS)


def build_research_lesson_candidate(summary_id: str) -> ResearchLessonCandidate:
    path = resolve_research_summary_id(summary_id)
    text = _summary_text(path)
    source = _summary_source(text, path.name)
    guard = untrusted_content_guard.classify_untrusted_content_risk(text, "Research Summary Proposal: " + path.name)
    markers = set(guard.markers_found)
    if APPROVAL_TOKEN in text:
        markers.add("approval.embedded_research_lesson_candidate_token")
    status = BLOCKED_LESSON_STATUS if source.risk_level == "BLOCKED" else LESSON_STATUS
    return ResearchLessonCandidate(
        summary_id=path.name,
        source_receipt_id=source.source_receipt_id,
        source_type=source.source_type,
        source_label=source.source_label,
        risk_level=source.risk_level,
        status=status,
        candidate_lesson=_candidate_lesson(text, source.risk_level),
        markers_found=tuple(sorted(markers)),
        summary_excerpt=untrusted_content_guard.safe_excerpt(text, 1800),
        generated_at=_timestamp(),
    )


def render_research_lesson_candidate(candidate: ResearchLessonCandidate) -> str:
    markers = list(candidate.markers_found) or ["none"]
    return "\n".join(
        [
            "# Engel Research Lesson Candidate",
            "",
            "Status:",
            candidate.status,
            "",
            "Authority:",
            candidate.authority,
            "",
            "Source:",
            "Research Summary Proposal",
            "Summary proposal ID: " + candidate.summary_id,
            "Source intake receipt ID: " + candidate.source_receipt_id,
            "Source type: " + candidate.source_type,
            "Source label: " + candidate.source_label,
            "",
            "Research path:",
            candidate.research_path,
            "",
            "Boundary:",
            SUMMARY_BOUNDARY + ".",
            RESEARCH_LESSON_BOUNDARY + ".",
            LESSON_BOUNDARY + ".",
            "This candidate does not update Engel memory.",
            "This candidate does not change Engel behavior.",
            "This candidate is not an instruction source.",
            "",
            "Approval:",
            APPROVAL_TOKEN + " received from user input: " + ("YES" if candidate.approval_received else "NO"),
            "",
            "Token meaning:",
            APPROVAL_TOKEN + ' means "write research lesson candidate receipt only."',
            'It does not mean "trust this lesson."',
            'It does not mean "apply this lesson."',
            'It does not mean "update memory."',
            "",
            "Untrusted Content Guard:",
            "Risk: " + candidate.risk_level,
            "Markers: " + ", ".join(markers),
            "Embedded approval tokens accepted: NO",
            "",
            "Guardian Review:",
            "- Trusted memory write: NO",
            "- Engel behavior change: NO",
            "- Runtime source edit: NO",
            "- Product source edit: NO",
            "- Browser/API/network action: NO",
            "- Research content trusted as instruction: NO",
            "- Requires later Josh/Guardian memory workflow: YES",
            "",
            "Candidate Lesson:",
            candidate.candidate_lesson,
            "",
            "Recommended Future Action:",
            "- Review candidate",
            "- Keep/reject/request more research",
            "- Convert through future memory-candidate workflow only if separately approved",
            "",
            "Safety:",
            "- No trusted memory written",
            "- No source files changed",
            "- No code executed",
            "- No Browser Queen action performed",
            "",
        ]
    )


def write_research_lesson_candidate(
    summary_id: str,
    approval_token: str | None,
) -> ResearchLessonCandidateWriteResult:
    candidate = build_research_lesson_candidate(summary_id)
    if approval_token != APPROVAL_TOKEN:
        return ResearchLessonCandidateWriteResult(
            status=BLOCKED_WRITE_STATUS,
            path=None,
            message="APPROVE_RESEARCH_LESSON_CANDIDATE_REQUIRED",
            candidate=candidate,
        )

    approved = replace(candidate, approval_received=True)
    root = research_lesson_candidates_root()
    path = root / f"{approved.generated_at}_{_slug(Path(approved.summary_id).stem)}_research_lesson_candidate.md"
    path = _unique_path(path)
    if not is_safe_research_lesson_candidate_path(path):
        raise ValueError("research lesson candidate path escaped reports\\research_intake\\lesson_candidates")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_research_lesson_candidate(approved), encoding="utf-8")
    return ResearchLessonCandidateWriteResult(
        status="RESEARCH_LESSON_CANDIDATE_CREATED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        path=path,
        message="Research lesson candidate receipt written only.",
        candidate=approved,
    )


if __name__ == "__main__":
    for item in list_research_summary_proposals():
        print(item.summary_id, item.risk_level, item.source_type)
