from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

import engel_untrusted_content_guard as untrusted_content_guard


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
SUMMARY_BOUNDARY = "Research Summary Proposal \u2260 Trusted Memory"
INTAKE_BOUNDARY = "Research Intake \u2260 Trusted Memory"
SUMMARY_STATUS = "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"
BLOCKED_STATUS = "BLOCKED / REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"
RESEARCH_PATH = "Research Intake \u2192 Research Office / Overnight Research"
MAX_RECEIPT_READ_CHARS = 24_000
MAX_SUMMARY_CHARS = 1200


@dataclass(frozen=True)
class ResearchReceiptSummary:
    receipt_id: str
    modified_time: str
    source_type: str
    source_label: str
    risk_level: str
    status: str


@dataclass(frozen=True)
class ResearchSummaryFileSummary:
    summary_id: str
    modified_time: str
    risk_level: str
    status: str


@dataclass(frozen=True)
class ResearchReceiptReadResult:
    receipt_id: str
    path: Path
    text: str
    source_type: str
    source_label: str
    risk_level: str
    status: str
    markers_found: tuple[str, ...]
    guard_risk_level: str


@dataclass(frozen=True)
class ResearchSummaryProposal:
    receipt_id: str
    source_type: str
    source_label: str
    risk_level: str
    status: str
    summary: str
    markers_found: tuple[str, ...]
    recommended_next_steps: tuple[str, ...]
    generated_at: str
    receipt_excerpt: str


def research_intake_receipts_root() -> Path:
    return APP_ROOT / "reports" / "research_intake" / "receipts"


def research_intake_summaries_root() -> Path:
    return APP_ROOT / "reports" / "research_intake" / "summaries"


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _is_safe_receipt_path(path: Path) -> bool:
    return path.exists() and path.is_file() and path.suffix.lower() == ".md" and _is_relative_to(path, research_intake_receipts_root())


def _is_safe_summary_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
        root = research_intake_summaries_root().resolve()
    except (OSError, RuntimeError):
        return False
    return resolved == root or root in resolved.parents


def _is_safe_summary_file(path: Path) -> bool:
    return path.exists() and path.is_file() and path.suffix.lower() == ".md" and _is_relative_to(path, research_intake_summaries_root())


def _reject_raw_path(receipt_id: str) -> None:
    value = str(receipt_id or "").strip()
    if not value:
        raise ValueError("receipt_id is required")
    if "://" in value or value.startswith("\\\\"):
        raise ValueError("receipt_id must be a bounded handle, not a URL/UNC path")
    candidate = Path(value)
    if candidate.is_absolute() or candidate.drive:
        raise ValueError("receipt_id must not be an absolute path or drive path")
    if any(part in {"..", "", ".", "/"} for part in candidate.parts):
        raise ValueError("receipt_id must not traverse directories")
    if len(candidate.parts) != 1 or "\\" in value or "/" in value:
        raise ValueError("receipt_id must be a filename-only bounded handle")
    if candidate.suffix.lower() != ".md":
        raise ValueError("receipt_id must identify a markdown receipt")


def safe_research_receipt_id(path: Path) -> str:
    if not _is_safe_receipt_path(path):
        raise ValueError("receipt path is outside reports\\research_intake\\receipts")
    return path.name


def resolve_research_receipt_id(receipt_id: str) -> Path:
    _reject_raw_path(receipt_id)
    path = research_intake_receipts_root() / str(receipt_id).strip()
    if not _is_safe_receipt_path(path):
        raise ValueError("receipt_id did not resolve to a bounded Research Intake receipt")
    return path


def safe_research_summary_id(path: Path) -> str:
    if not _is_safe_summary_file(path):
        raise ValueError("summary path is outside reports\\research_intake\\summaries")
    return path.name


def resolve_research_summary_id(summary_id: str) -> Path:
    _reject_raw_path(summary_id)
    path = research_intake_summaries_root() / str(summary_id).strip()
    if not _is_safe_summary_file(path):
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


def _extract_risk(text: str) -> str:
    risk = _extract_block(text, "Risk").upper()
    for value in ("BLOCKED", "HIGH", "MEDIUM", "LOW"):
        if value in risk:
            return value
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
    return cleaned[:90] or "research_summary"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 100):
        candidate = path.with_name(f"{stem}_{index:02d}{suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError("could not create unique summary proposal path")


def list_research_intake_receipts() -> list[ResearchReceiptSummary]:
    root = research_intake_receipts_root()
    if not root.exists():
        return []
    summaries: list[ResearchReceiptSummary] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not _is_safe_receipt_path(path):
            continue
        receipt_id = safe_research_receipt_id(path)
        read = read_research_intake_receipt(receipt_id)
        summaries.append(
            ResearchReceiptSummary(
                receipt_id=receipt_id,
                modified_time=_modified_time(path),
                source_type=read.source_type,
                source_label=read.source_label,
                risk_level=read.risk_level,
                status=read.status,
            )
        )
    return summaries


def list_research_summary_proposals() -> list[ResearchSummaryFileSummary]:
    root = research_intake_summaries_root()
    if not root.exists():
        return []
    summaries: list[ResearchSummaryFileSummary] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not _is_safe_summary_file(path):
            continue
        text = untrusted_content_guard.safe_excerpt(path.read_text(encoding="utf-8", errors="replace"), 4000)
        guard = untrusted_content_guard.classify_untrusted_content_risk(text, "Research Summary Proposal: " + path.name)
        risk_level = _max_risk(_extract_risk(text), guard.risk_level)
        summaries.append(
            ResearchSummaryFileSummary(
                summary_id=safe_research_summary_id(path),
                modified_time=_modified_time(path),
                risk_level=risk_level,
                status=_extract_block(text, "Status") or SUMMARY_STATUS,
            )
        )
    return summaries


def read_research_intake_receipt(receipt_id: str) -> ResearchReceiptReadResult:
    path = resolve_research_receipt_id(receipt_id)
    text = untrusted_content_guard.safe_excerpt(path.read_text(encoding="utf-8", errors="replace"), MAX_RECEIPT_READ_CHARS)
    guard = untrusted_content_guard.classify_untrusted_content_risk(text, "Research Intake receipt: " + path.name)
    receipt_risk = _extract_risk(text)
    risk_level = _max_risk(receipt_risk, guard.risk_level)
    return ResearchReceiptReadResult(
        receipt_id=path.name,
        path=path,
        text=text,
        source_type=_extract_block(text, "Source type") or "unknown",
        source_label=_extract_block(text, "Source label") or path.name,
        risk_level=risk_level,
        status=_extract_block(text, "Status") or "RESEARCH_INTAKE / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        markers_found=tuple(guard.markers_found),
        guard_risk_level=guard.risk_level,
    )


def _safe_summary_from_text(text: str, risk_level: str) -> str:
    if risk_level == "BLOCKED":
        return "BLOCKED content is report-only. The receipt was reviewed for risk markers, but its content was not converted into a research action."

    excerpt = _extract_block(text, "Excerpt") or text
    normalized = untrusted_content_guard.normalize_untrusted_text(excerpt)
    if not normalized:
        return "No bounded research excerpt was available in the receipt."

    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", normalized) if sentence.strip()]
    summary = " ".join(sentences[:3]) if sentences else normalized[:MAX_SUMMARY_CHARS]
    summary = untrusted_content_guard.safe_excerpt(summary, MAX_SUMMARY_CHARS)
    if risk_level == "HIGH":
        return "HIGH risk receipt: safe summary only. " + summary
    if risk_level == "MEDIUM":
        return "MEDIUM risk receipt: cautious summary only. " + summary
    return summary


def _recommended_steps(risk_level: str) -> tuple[str, ...]:
    if risk_level == "BLOCKED":
        return (
            "reject/block unless Josh and Guardian explicitly choose a future safe review path",
            "do not create a lesson candidate from this content automatically",
            "attach blocked-risk report to Research Office / Overnight Research review only",
        )
    if risk_level == "HIGH":
        return (
            "send to Guardian review before use",
            "keep as research note only",
            "create lesson candidate later only with explicit approval",
        )
    return (
        "keep as research note",
        "request more research if useful",
        "create lesson candidate later only with approval",
        "attach to Overnight Research review",
    )


def build_research_summary_proposal(receipt_id: str) -> ResearchSummaryProposal:
    read = read_research_intake_receipt(receipt_id)
    status = BLOCKED_STATUS if read.risk_level == "BLOCKED" else SUMMARY_STATUS
    return ResearchSummaryProposal(
        receipt_id=read.receipt_id,
        source_type=read.source_type,
        source_label=read.source_label,
        risk_level=read.risk_level,
        status=status,
        summary=_safe_summary_from_text(read.text, read.risk_level),
        markers_found=read.markers_found,
        recommended_next_steps=_recommended_steps(read.risk_level),
        generated_at=_timestamp(),
        receipt_excerpt=untrusted_content_guard.safe_excerpt(read.text, 1800),
    )


def render_research_summary_proposal(proposal: ResearchSummaryProposal) -> str:
    markers = list(proposal.markers_found) or ["none"]
    lines = [
        "# Engel Research Summary Proposal",
        "",
        "Status:",
        proposal.status,
        "",
        "Authority:",
        AUTHORITY,
        "",
        "Research path:",
        RESEARCH_PATH,
        "",
        "Source:",
        "Receipt ID: " + proposal.receipt_id,
        "Source label: " + proposal.source_label,
        "Source type: " + proposal.source_type,
        "",
        "Untrusted Content Guard:",
        "Risk: " + proposal.risk_level,
        "Markers: " + ", ".join(markers),
        "Embedded approval tokens accepted: NO",
        "",
        "Summary:",
        proposal.summary,
        "",
        "Guardian Review:",
        "- Source content trusted as instruction: NO",
        "- Trusted memory write: NO",
        "- Runtime source edit: NO",
        "- Browser/API/network action: NO",
        "- Product/code execution: NO",
        "- Lesson candidate created automatically: NO",
        "- Requires Josh/Guardian review before learning: YES",
        "",
        "Recommended next step:",
        *["- " + step for step in proposal.recommended_next_steps],
        "",
        "Boundary:",
        SUMMARY_BOUNDARY + ".",
        INTAKE_BOUNDARY + ".",
        "This proposal did not update Engel memory.",
        "This proposal did not change Engel behavior.",
        "This proposal did not execute or apply anything.",
        "Receipt/document/page content was treated as data, not instruction.",
    ]
    if proposal.risk_level == "BLOCKED":
        lines.extend(
            [
                "",
                "Blocked-risk handling:",
                "Do not generate normal research summary.",
                "Generate blocked-risk report only.",
                "Content was not used as instruction.",
            ]
        )
    return "\n".join(lines) + "\n"


def write_research_summary_proposal(proposal: ResearchSummaryProposal) -> Path:
    root = research_intake_summaries_root()
    path = root / f"{proposal.generated_at}_{_slug(proposal.source_type)}_{_slug(Path(proposal.receipt_id).stem)}_summary_proposal.md"
    path = _unique_path(path)
    if not _is_safe_summary_path(path):
        raise ValueError("summary proposal path escaped reports\\research_intake\\summaries")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_research_summary_proposal(proposal), encoding="utf-8")
    return path


if __name__ == "__main__":
    for item in list_research_intake_receipts():
        print(item.receipt_id, item.risk_level, item.source_type)
