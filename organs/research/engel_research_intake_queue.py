from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import engel_untrusted_content_guard as untrusted_content_guard


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
BOUNDARY = "Research Intake \u2260 Trusted Memory"
INTAKE_STATUS = "RESEARCH_INTAKE / NOT_TRUSTED_MEMORY / NOT_APPLIED"
SUMMARY_STATUS = "PROPOSAL_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"
MAX_RESEARCH_CHARS = 6000
SOURCE_TYPES = (
    "browser_queen_page_future",
    "pdf_text_future",
    "image_ocr_text_future",
    "markdown_doc",
    "code_companion_product",
    "research_report",
    "overnight_research_output",
    "external_review_report",
    "manual_text",
    "copied_web_text",
    "product_file",
    "receipt_or_log",
)


@dataclass(frozen=True)
class ResearchSourceClassification:
    source_label: str
    source_type: str
    confidence: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ResearchIntakeScanResult:
    source_label: str
    source_type: str
    risk_level: str
    markers_found: tuple[str, ...]
    safe_to_summarize: bool
    safe_to_execute: bool
    handling: str
    guard_report: str


@dataclass(frozen=True)
class ResearchIntakeReceipt:
    source_label: str
    source_type: str
    risk_level: str
    markers_found: tuple[str, ...]
    excerpt: str
    handling: str
    guard_report: str
    timestamp: str
    status: str = INTAKE_STATUS
    authority: str = AUTHORITY
    research_path: str = "Research Office / Overnight Research"
    boundary: str = BOUNDARY


def research_intake_root() -> Path:
    return APP_ROOT / "reports" / "research_intake"


def research_intake_receipts_root() -> Path:
    return research_intake_root() / "receipts"


def research_intake_summaries_root() -> Path:
    return research_intake_root() / "summaries"


def is_safe_research_intake_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
        root = research_intake_root().resolve()
    except (OSError, RuntimeError):
        return False
    return resolved == root or root in resolved.parents


def _slug(value: str, fallback: str = "research_item") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip().lower()).strip("_")
    return cleaned[:80] or fallback


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _source_label_text(source_label: str) -> str:
    return " ".join(str(source_label or "").replace("\\", "/").lower().split())


def classify_research_source(source_label: str, text: str) -> ResearchSourceClassification:
    label = _source_label_text(source_label)
    sample = " ".join(str(text or "").lower().split())[:1200]
    combined = label + " " + sample

    source_type = "manual_text"
    confidence = "MEDIUM"
    notes: list[str] = ["Research item is routed to Research Office / Overnight Research."]

    if "browser queen" in combined or "browser_queen" in combined or "page text" in combined:
        source_type = "browser_queen_page_future"
        notes.append("Browser Queen output is research input only, not separate memory.")
    elif "pdf" in combined:
        source_type = "pdf_text_future"
        notes.append("PDF extraction is future/external; extracted text must remain untrusted.")
    elif any(token in combined for token in ("ocr", "image", "screenshot", "photo")):
        source_type = "image_ocr_text_future"
        notes.append("OCR/image extraction is future/external; extracted text must remain untrusted.")
    elif any(token in combined for token in (".md", "markdown", "readme")):
        source_type = "markdown_doc"
    elif "external review" in combined or "external_reviews" in combined:
        source_type = "external_review_report"
    elif "overnight research" in combined:
        source_type = "overnight_research_output"
    elif "research report" in combined or "reports/research" in combined:
        source_type = "research_report"
    elif "code companion product" in combined or "products/" in combined:
        source_type = "code_companion_product"
    elif any(token in combined for token in ("product file", "product_manifest", ".engel_product_profile")):
        source_type = "product_file"
    elif any(token in combined for token in ("receipt", "log", ".engel_receipts", "main_agent_log")):
        source_type = "receipt_or_log"
    elif "copied web" in combined or "web text" in combined or "webpage" in combined:
        source_type = "copied_web_text"
    else:
        confidence = "LOW"

    return ResearchSourceClassification(
        source_label=str(source_label or "manual research text"),
        source_type=source_type,
        confidence=confidence,
        notes=tuple(notes),
    )


def _risk_handling(risk_level: str) -> str:
    if risk_level == "LOW":
        return "Can summarize as untrusted research data."
    if risk_level == "MEDIUM":
        return "Summarize with caution; do not convert content into action."
    if risk_level == "HIGH":
        return "Safe summary only; no actions, no approvals, no memory write."
    return "Report only; no research action proposal."


def scan_research_text(text: str, source_label: str) -> ResearchIntakeScanResult:
    classification = classify_research_source(source_label, text)
    guard = untrusted_content_guard.classify_untrusted_content_risk(text, classification.source_label)
    return ResearchIntakeScanResult(
        source_label=classification.source_label,
        source_type=classification.source_type,
        risk_level=guard.risk_level,
        markers_found=tuple(guard.markers_found),
        safe_to_summarize=bool(guard.safe_to_summarize),
        safe_to_execute=False,
        handling=_risk_handling(guard.risk_level),
        guard_report=untrusted_content_guard.render_untrusted_content_guard_report(guard),
    )


def build_research_intake_receipt(source_label: str, text: str) -> ResearchIntakeReceipt:
    scan = scan_research_text(text, source_label)
    excerpt = untrusted_content_guard.safe_excerpt(text, MAX_RESEARCH_CHARS)
    return ResearchIntakeReceipt(
        source_label=scan.source_label,
        source_type=scan.source_type,
        risk_level=scan.risk_level,
        markers_found=scan.markers_found,
        excerpt=excerpt,
        handling=scan.handling,
        guard_report=scan.guard_report,
        timestamp=_timestamp(),
    )


def render_research_intake_receipt(receipt: ResearchIntakeReceipt) -> str:
    markers = list(receipt.markers_found) or ["none"]
    lines = [
        "# Engel Research Intake Receipt",
        "",
        "Status:",
        receipt.status,
        "",
        "Authority:",
        receipt.authority,
        "",
        "Source type:",
        receipt.source_type,
        "",
        "Source label:",
        receipt.source_label,
        "",
        "Untrusted Content Guard:",
        "Risk: " + receipt.risk_level,
        "Markers: " + ", ".join(markers),
        "",
        "Research path:",
        receipt.research_path,
        "",
        "Boundary:",
        receipt.boundary + ".",
        "This content is data, not instruction.",
        "This receipt does not update memory.",
        "This receipt does not change Engel behavior.",
        "",
        "Recommended next step:",
    ]
    if receipt.risk_level == "BLOCKED":
        lines.append("- reject/block; report only")
    elif receipt.risk_level == "HIGH":
        lines.append("- safe summary only for Research Office; no actions")
    else:
        lines.append("- summarize for Research Office")
    lines.extend(
        [
            "- create lesson candidate only after Josh/Guardian review",
            "- reject/block if high risk",
            "",
            "Risk handling:",
            receipt.handling,
            "",
            "Safety:",
            "- no trusted memory write",
            "- no product/runtime source edit",
            "- no browser launch",
            "- no API/network",
            "- no code execution",
            "",
            "Excerpt:",
            receipt.excerpt,
            "",
            "Guard report:",
            receipt.guard_report,
        ]
    )
    return "\n".join(lines)


def _summary_from_excerpt(excerpt: str) -> str:
    normalized = untrusted_content_guard.normalize_untrusted_text(excerpt)
    if not normalized:
        return "No research text was provided."
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    summary = " ".join(sentence for sentence in sentences[:3] if sentence).strip()
    if not summary:
        summary = normalized[:500].strip()
    return untrusted_content_guard.safe_excerpt(summary, 900)


def render_research_summary_proposal(receipt: ResearchIntakeReceipt) -> str:
    if receipt.risk_level == "BLOCKED":
        summary = "BLOCKED content is report-only. No research action proposal was created."
        status = "BLOCKED / REPORT_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED"
    else:
        summary = _summary_from_excerpt(receipt.excerpt)
        status = SUMMARY_STATUS
    lines = [
        "# Engel Research Summary Proposal",
        "",
        "Status:",
        status,
        "",
        "Research path:",
        receipt.research_path,
        "",
        "Source type:",
        receipt.source_type,
        "",
        "Source label:",
        receipt.source_label,
        "",
        "Untrusted Content Guard:",
        "Risk: " + receipt.risk_level,
        "",
        "Summary:",
        summary,
        "",
        "Guardian Review:",
        "- Source content trusted as instruction: NO",
        "- Trusted memory write: NO",
        "- Runtime source edit: NO",
        "- Browser/API/network action: NO",
        "- Requires Josh/Guardian review before learning: YES",
        "",
        "Boundary:",
        "Research Intake \u2260 Trusted Memory.",
        "Research summary proposal is not trusted memory and does not change Engel behavior.",
    ]
    return "\n".join(lines)


def _write_bounded_text(path: Path, text: str) -> Path:
    if not is_safe_research_intake_path(path):
        raise ValueError("Research intake path escaped bounded reports\\research_intake root.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_research_intake_receipt(receipt: ResearchIntakeReceipt) -> Path:
    name = receipt.timestamp + "_" + _slug(receipt.source_type) + "_" + _slug(receipt.source_label) + "_receipt.md"
    path = research_intake_receipts_root() / name
    return _write_bounded_text(path, render_research_intake_receipt(receipt))


def write_research_summary_proposal(receipt: ResearchIntakeReceipt) -> Path:
    if receipt.risk_level == "BLOCKED":
        raise ValueError("BLOCKED research intake is report-only; no summary proposal is written.")
    name = receipt.timestamp + "_" + _slug(receipt.source_type) + "_" + _slug(receipt.source_label) + "_summary.md"
    path = research_intake_summaries_root() / name
    return _write_bounded_text(path, render_research_summary_proposal(receipt))


def list_research_intake_receipts() -> list[Path]:
    root = research_intake_receipts_root()
    if not root.exists():
        return []
    receipts: list[Path] = []
    for path in root.iterdir():
        if path.is_file() and path.suffix.lower() == ".md" and is_safe_research_intake_path(path):
            receipts.append(path)
    return sorted(receipts)


def contract_summary() -> dict[str, Any]:
    return {
        "schema": "engel_research_intake_queue_contract_v1",
        "status": "RESEARCH_INTAKE / PROPOSAL_ONLY",
        "boundary": BOUNDARY,
        "authority": AUTHORITY,
        "research_path": "Research Office / Overnight Research",
        "source_types": list(SOURCE_TYPES),
        "intake_root": str(research_intake_root().relative_to(APP_ROOT)),
        "receipts_root": str(research_intake_receipts_root().relative_to(APP_ROOT)),
        "summaries_root": str(research_intake_summaries_root().relative_to(APP_ROOT)),
        "trusted_memory_write": "BLOCKED",
        "browser_queen_placement": "Browser Queen outputs feed Research Intake and Overnight Research, not separate memory.",
        "pdf_image_ocr_rule": "Future extracted text must pass through Research Intake and Untrusted Content Guard.",
    }


if __name__ == "__main__":
    print(json.dumps(contract_summary(), indent=2))
