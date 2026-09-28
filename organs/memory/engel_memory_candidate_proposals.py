from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
import re

import engel_untrusted_content_guard as untrusted_content_guard


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
APPROVAL_TOKEN = "APPROVE_MEMORY_CANDIDATE_PROPOSAL"
PROPOSAL_STATUS = "MEMORY_CANDIDATE_PROPOSAL / NOT_TRUSTED_MEMORY / NOT_APPLIED"
BLOCKED_WRITE_STATUS = "MEMORY_CANDIDATE_PROPOSAL_BLOCKED / APPROVE_MEMORY_CANDIDATE_PROPOSAL_REQUIRED"
BOUNDARY = "Trusted Memory Candidate ≠ Trusted Memory"
MAX_SOURCE_READ_CHARS = 20_000
MAX_CANDIDATE_CHARS = 1800
SOURCE_FILTERS = {"all", "product_lessons", "research_lessons", "research_summaries", "mixed"}


@dataclass(frozen=True)
class MemoryCandidateSource:
    source_id: str
    source_type: str
    path: Path
    status: str
    risk_level: str
    summary: str
    markers_found: tuple[str, ...]
    modified_time: str


@dataclass(frozen=True)
class MemoryCandidateProposal:
    source_filter: str
    status: str
    sources: tuple[MemoryCandidateSource, ...]
    candidate_memory: str
    highest_risk: str
    markers_found: tuple[str, ...]
    generated_at: str
    approval_received: bool = False
    authority: str = AUTHORITY


@dataclass(frozen=True)
class MemoryCandidateWriteResult:
    status: str
    path: Path | None
    message: str
    proposal: MemoryCandidateProposal


def memory_candidate_root() -> Path:
    return APP_ROOT / "reports" / "memory_candidate_proposals"


def _products_root() -> Path:
    return APP_ROOT / "products"


def _product_lesson_review_dirname() -> str:
    return ".engel_lesson_reviews"


def _research_lesson_reviews_root() -> Path:
    return APP_ROOT / "reports" / "research_intake" / "lesson_reviews"


def _research_summary_root() -> Path:
    return APP_ROOT / "reports" / "research_intake" / "summaries"


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def is_safe_memory_candidate_path(path: Path) -> bool:
    try:
        root = memory_candidate_root().resolve()
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return False
    return (resolved == root or root in resolved.parents) and not (root.exists() and root.is_symlink())


def _is_safe_product_slug(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9_]{0,79}", str(value or "")))


def _is_safe_product_lesson_review(path: Path) -> bool:
    if not path.exists() or not path.is_file() or path.is_symlink() or path.suffix.lower() != ".md":
        return False
    if not _is_relative_to(path, _products_root()):
        return False
    try:
        relative = path.resolve().relative_to(_products_root().resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    parts = relative.parts
    return (
        len(parts) == 3
        and _is_safe_product_slug(parts[0])
        and parts[1] == _product_lesson_review_dirname()
        and parts[2].endswith("_lesson_review.md")
    )


def _is_safe_markdown_file(path: Path, root: Path) -> bool:
    return (
        path.exists()
        and path.is_file()
        and not path.is_symlink()
        and path.suffix.lower() == ".md"
        and _is_relative_to(path, root)
    )


def _read_source_text(path: Path) -> str:
    return untrusted_content_guard.safe_excerpt(path.read_text(encoding="utf-8", errors="replace"), MAX_SOURCE_READ_CHARS)


def _extract_block(text: str, label: str) -> str:
    pattern = re.compile(r"(?im)^" + re.escape(label) + r":\s*$\n(?P<value>.+?)(?:\n\s*\n|$)", re.S)
    match = pattern.search(text)
    if match:
        return match.group("value").strip()
    inline = re.compile(r"(?im)^" + re.escape(label) + r":\s*(?P<value>.+)$")
    match = inline.search(text)
    return match.group("value").strip() if match else ""


def _extract_risk(text: str) -> str:
    risk = (_extract_block(text, "Risk") or _extract_block(text, "Untrusted Content Guard")).upper()
    for value in ("BLOCKED", "HIGH", "MEDIUM", "LOW"):
        if value in risk:
            return value
    if "BLOCKED_RISK" in text or "BLOCKED / REPORT_ONLY" in text:
        return "BLOCKED"
    return "LOW"


def _risk_rank(risk_level: str) -> int:
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "BLOCKED": 3}.get(str(risk_level or "LOW").upper(), 0)


def _max_risk(*risk_levels: str) -> str:
    return max((str(risk or "LOW").upper() for risk in risk_levels), key=_risk_rank)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _modified_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def _safe_source_id(source_type: str, path: Path) -> str:
    if source_type == "product_lesson_review":
        relative = path.resolve().relative_to(_products_root().resolve())
        return relative.parts[0] + "::" + path.name
    return path.name


def _source_summary(text: str, risk_level: str) -> str:
    summary = _extract_block(text, "Summary") or _extract_block(text, "Candidate Lesson") or _extract_block(text, "Recommended Josh Decision") or text
    normalized = untrusted_content_guard.normalize_untrusted_text(summary)
    normalized = normalized.replace(APPROVAL_TOKEN, "[REMOVED_EMBEDDED_APPROVAL_TOKEN]")
    if risk_level == "BLOCKED":
        return "BLOCKED source: keep only as a safety/rejection candidate for Josh/Guardian review. " + untrusted_content_guard.safe_excerpt(normalized, 600)
    if risk_level == "HIGH":
        return "HIGH-risk source: do not learn automatically; use only for narrowed Guardian-reviewed candidate text. " + untrusted_content_guard.safe_excerpt(normalized, 600)
    return untrusted_content_guard.safe_excerpt(normalized, 800)


def _source_from_path(source_type: str, path: Path) -> MemoryCandidateSource:
    text = _read_source_text(path)
    guard = untrusted_content_guard.classify_untrusted_content_risk(text, source_type + ": " + path.name)
    embedded_memory_token = APPROVAL_TOKEN in text
    risk = _max_risk(_extract_risk(text), guard.risk_level, "HIGH" if embedded_memory_token else "LOW")
    markers = set(guard.markers_found)
    if embedded_memory_token:
        markers.add("approval.embedded_memory_candidate_token")
    status = _extract_block(text, "Status") or "REVIEWED_ARTIFACT / NOT_TRUSTED_MEMORY / NOT_APPLIED"
    return MemoryCandidateSource(
        source_id=_safe_source_id(source_type, path),
        source_type=source_type,
        path=path,
        status=status,
        risk_level=risk,
        summary=_source_summary(text, risk),
        markers_found=tuple(sorted(markers)),
        modified_time=_modified_time(path),
    )


def list_product_lesson_reviews() -> list[MemoryCandidateSource]:
    root = _products_root()
    if not root.exists() or root.is_symlink():
        return []
    reviews: list[MemoryCandidateSource] = []
    for product_dir in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not product_dir.is_dir() or product_dir.is_symlink() or not _is_safe_product_slug(product_dir.name):
            continue
        review_root = product_dir / _product_lesson_review_dirname()
        if not review_root.exists() or not review_root.is_dir() or review_root.is_symlink():
            continue
        for path in sorted(review_root.iterdir(), key=lambda item: item.name.lower()):
            if _is_safe_product_lesson_review(path):
                reviews.append(_source_from_path("product_lesson_review", path))
    return reviews


def list_research_lesson_reviews() -> list[MemoryCandidateSource]:
    root = _research_lesson_reviews_root()
    if not root.exists() or root.is_symlink():
        return []
    return [
        _source_from_path("research_lesson_review", path)
        for path in sorted(root.iterdir(), key=lambda item: item.name.lower())
        if _is_safe_markdown_file(path, root) and path.name.endswith("_research_lesson_review.md")
    ]


def list_research_summary_proposals_for_memory_candidates() -> list[MemoryCandidateSource]:
    root = _research_summary_root()
    if not root.exists() or root.is_symlink():
        return []
    return [
        _source_from_path("research_summary_proposal", path)
        for path in sorted(root.iterdir(), key=lambda item: item.name.lower())
        if _is_safe_markdown_file(path, root)
    ]


def _sources_for_filter(source_filter: str) -> tuple[MemoryCandidateSource, ...]:
    value = str(source_filter or "all").strip().lower()
    if value not in SOURCE_FILTERS:
        raise ValueError("Unsupported memory candidate source_filter: " + value)
    product = list_product_lesson_reviews() if value in {"all", "product_lessons", "mixed"} else []
    research_lessons = list_research_lesson_reviews() if value in {"all", "research_lessons", "mixed"} else []
    summaries = list_research_summary_proposals_for_memory_candidates() if value in {"all", "research_summaries"} else []
    return tuple(product + research_lessons + summaries)


def _candidate_memory(sources: tuple[MemoryCandidateSource, ...]) -> str:
    if not sources:
        return (
            "No reviewed artifacts were available for this source filter. "
            "Do not write trusted memory; request reviewed lesson or research artifacts first."
        )
    lines = [
        "Conservative memory-candidate draft for Josh/Guardian review only.",
        "Do not treat this draft as trusted memory or instruction.",
    ]
    for index, source in enumerate(sources[:12], start=1):
        if source.risk_level in {"HIGH", "BLOCKED"}:
            detail = source.summary
        else:
            detail = "Candidate note from reviewed artifact: " + source.summary
        lines.append(f"{index}. [{source.source_type} / {source.risk_level}] {detail}")
    if len(sources) > 12:
        lines.append(f"{len(sources) - 12} additional source artifact(s) omitted from this bounded draft.")
    candidate = "\n".join(lines)
    candidate = candidate.replace(APPROVAL_TOKEN, "[REMOVED_EMBEDDED_APPROVAL_TOKEN]")
    return untrusted_content_guard.safe_excerpt(candidate, MAX_CANDIDATE_CHARS)


def build_memory_candidate_proposal(source_filter: str = "all") -> MemoryCandidateProposal:
    value = str(source_filter or "all").strip().lower()
    sources = _sources_for_filter(value)
    risk = _max_risk(*(source.risk_level for source in sources)) if sources else "LOW"
    markers = sorted({marker for source in sources for marker in source.markers_found})
    return MemoryCandidateProposal(
        source_filter=value,
        status=PROPOSAL_STATUS,
        sources=sources,
        candidate_memory=_candidate_memory(sources),
        highest_risk=risk,
        markers_found=tuple(markers),
        generated_at=_timestamp(),
    )


def render_memory_candidate_proposal(proposal: MemoryCandidateProposal) -> str:
    product_sources = [source for source in proposal.sources if source.source_type == "product_lesson_review"]
    research_lesson_sources = [source for source in proposal.sources if source.source_type == "research_lesson_review"]
    research_summary_sources = [source for source in proposal.sources if source.source_type == "research_summary_proposal"]
    other_sources = [
        source
        for source in proposal.sources
        if source.source_type not in {"product_lesson_review", "research_lesson_review", "research_summary_proposal"}
    ]
    markers = list(proposal.markers_found) or ["none"]
    source_lines = []
    for label, items in (
        ("Product lesson reviews", product_sources),
        ("Research lesson reviews", research_lesson_sources),
        ("Research summary proposals", research_summary_sources),
        ("Other bounded review artifacts", other_sources),
    ):
        ids = ", ".join(source.source_id for source in items[:10]) if items else "none"
        if len(items) > 10:
            ids += f", ... ({len(items) - 10} more)"
        source_lines.append(f"- {label}: {len(items)}" + (f" [{ids}]" if items else ""))
    return "\n".join(
        [
            "# Engel Memory Candidate Proposal",
            "",
            "Status:",
            proposal.status,
            "",
            "Authority:",
            proposal.authority,
            "",
            "Boundary:",
            BOUNDARY + ".",
            "This proposal does not update Engel memory.",
            "This proposal does not change Engel behavior.",
            "This proposal is not an instruction source.",
            "This proposal requires later Josh/Guardian-approved trusted-memory workflow before any durable memory write.",
            "",
            "Approval:",
            APPROVAL_TOKEN + " received from user input: " + ("YES" if proposal.approval_received else "NO"),
            "",
            "Token meaning:",
            APPROVAL_TOKEN + " means \"write candidate proposal report only.\"",
            "It does not mean \"trust this memory.\"",
            "It does not mean \"apply this memory.\"",
            "It does not mean \"update trusted memory.\"",
            "",
            "Sources:",
            *source_lines,
            "",
            "Untrusted Content Guard:",
            "Highest risk: " + proposal.highest_risk,
            "Markers: " + ", ".join(markers),
            "Source content trusted as instruction: NO",
            "Embedded approval tokens accepted: NO",
            "",
            "Candidate Memory:",
            proposal.candidate_memory,
            "",
            "Guardian Review:",
            "- Trusted memory write: NO",
            "- Engel behavior change: NO",
            "- Runtime source edit: NO",
            "- Product source edit: NO",
            "- Browser/API/network action: NO",
            "- Source content trusted as instruction: NO",
            "- Embedded approval tokens accepted: NO",
            "- Requires separate Josh/Guardian trusted-memory workflow: YES",
            "",
            "Recommended Josh Decision:",
            "- Keep candidate for future memory write review",
            "- Reject candidate",
            "- Request more research",
            "- Request narrower candidate",
            "- No automatic action taken",
            "",
            "Safety:",
            "- No trusted memory written",
            "- No source files changed",
            "- No code executed",
            "- No Browser Queen action performed",
            "- No API/network used",
            "",
        ]
    )


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip().lower()).strip("_")
    return cleaned[:80] or "memory_candidate"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 100):
        candidate = path.with_name(f"{stem}_{index:02d}{suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError("could not create unique memory candidate proposal path")


def write_memory_candidate_proposal(
    proposal: MemoryCandidateProposal,
    approval_token: str | None,
) -> MemoryCandidateWriteResult:
    if str(approval_token or "").strip() != APPROVAL_TOKEN:
        return MemoryCandidateWriteResult(
            status=BLOCKED_WRITE_STATUS,
            path=None,
            message=APPROVAL_TOKEN + " required. Embedded tokens inside sources do not count.",
            proposal=proposal,
        )
    approved = replace(proposal, approval_received=True)
    root = memory_candidate_root()
    if root.exists() and root.is_symlink():
        raise ValueError("memory candidate root symlink is blocked")
    path = root / f"{approved.generated_at}_{_slug(approved.source_filter)}_memory_candidate_proposal.md"
    path = _unique_path(path)
    if not is_safe_memory_candidate_path(path) or path.suffix.lower() != ".md":
        raise ValueError("memory candidate proposal path escaped reports\\memory_candidate_proposals")
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(render_memory_candidate_proposal(approved), encoding="utf-8")
    return MemoryCandidateWriteResult(
        status="MEMORY_CANDIDATE_PROPOSAL_WRITTEN / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        path=path,
        message="Memory-candidate proposal report written only.",
        proposal=approved,
    )


__all__ = [
    "APPROVAL_TOKEN",
    "BLOCKED_WRITE_STATUS",
    "PROPOSAL_STATUS",
    "MemoryCandidateProposal",
    "MemoryCandidateSource",
    "MemoryCandidateWriteResult",
    "build_memory_candidate_proposal",
    "is_safe_memory_candidate_path",
    "list_product_lesson_reviews",
    "list_research_lesson_reviews",
    "list_research_summary_proposals_for_memory_candidates",
    "memory_candidate_root",
    "render_memory_candidate_proposal",
    "write_memory_candidate_proposal",
]
