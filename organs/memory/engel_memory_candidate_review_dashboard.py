from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import sys


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
STATUS = "READ_ONLY_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"
BOUNDARY = "Trusted Memory Candidate \u2260 Trusted Memory"
TRUSTED_MEMORY_STATUS = "BLOCKED / NOT_PERFORMED"
SOURCE_TYPES = (
    "product lesson reviews",
    "research lesson reviews",
    "research summary proposals",
)


@dataclass(frozen=True)
class MemoryCandidateProposalSummary:
    path: Path
    filename: str
    modified_time: str
    highest_risk: str
    source_counts: dict[str, int]
    review_ready: bool


def memory_candidate_proposals_root() -> Path:
    return APP_ROOT / "reports" / "memory_candidate_proposals"


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _is_safe_candidate_path(path: Path) -> bool:
    root = memory_candidate_proposals_root()
    try:
        resolved_root = root.resolve()
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return (
        resolved.is_file()
        and not resolved.is_symlink()
        and resolved.suffix.lower() == ".md"
        and _is_relative_to(resolved, resolved_root)
        and not (resolved_root.exists() and resolved_root.is_symlink())
    )


def _modified_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def _extract_inline_count(text: str, label: str) -> int:
    match = re.search(r"(?im)^-\s*" + re.escape(label) + r":\s*(\d+)\b", text or "")
    return int(match.group(1)) if match else 0


def _extract_highest_risk(text: str) -> str:
    match = re.search(r"(?im)^Highest risk:\s*(BLOCKED|HIGH|MEDIUM|LOW)\b", text or "")
    return match.group(1).upper() if match else "UNKNOWN"


def _proposal_summary(path: Path) -> MemoryCandidateProposalSummary:
    text = path.read_text(encoding="utf-8", errors="replace")
    source_counts = {
        "product lesson reviews": _extract_inline_count(text, "Product lesson reviews"),
        "research lesson reviews": _extract_inline_count(text, "Research lesson reviews"),
        "research summary proposals": _extract_inline_count(text, "Research summary proposals"),
    }
    return MemoryCandidateProposalSummary(
        path=path,
        filename=path.name,
        modified_time=_modified_time(path),
        highest_risk=_extract_highest_risk(text),
        source_counts=source_counts,
        review_ready=(
            "Guardian Review:" in text
            and "Trusted memory write: NO" in text
            and "Requires separate Josh/Guardian trusted-memory workflow: YES" in text
        ),
    )


def list_memory_candidate_proposals() -> list[MemoryCandidateProposalSummary]:
    root = memory_candidate_proposals_root()
    if not root.exists() or not root.is_dir() or root.is_symlink():
        return []
    proposals = [
        _proposal_summary(path)
        for path in sorted(root.iterdir(), key=lambda item: item.name.lower())
        if _is_safe_candidate_path(path)
    ]
    return sorted(proposals, key=lambda item: (item.path.stat().st_mtime, item.filename), reverse=True)


def latest_memory_candidate_proposal() -> Path | None:
    proposals = list_memory_candidate_proposals()
    return proposals[0].path if proposals else None


def _risk_status(proposals: list[MemoryCandidateProposalSummary]) -> str:
    if not proposals:
        return "NONE"
    ranks = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "BLOCKED": 3, "UNKNOWN": -1}
    return max((item.highest_risk for item in proposals), key=lambda value: ranks.get(value, -1))


def _review_readiness(proposals: list[MemoryCandidateProposalSummary]) -> str:
    if not proposals:
        return "NO_CANDIDATES"
    ready = sum(1 for item in proposals if item.review_ready)
    return f"{ready}/{len(proposals)} READY_FOR_JOSH_GUARDIAN_REVIEW"


def render_memory_candidate_review_dashboard() -> str:
    proposals = list_memory_candidate_proposals()
    latest = proposals[0] if proposals else None
    latest_text = latest.filename if latest else "NONE"
    latest_risk = latest.highest_risk if latest else "NONE"
    latest_ready = "YES" if latest and latest.review_ready else "NO"

    lines = [
        "# TRUSTED MEMORY CANDIDATE REVIEW",
        "",
        "Status:",
        STATUS,
        "",
        "Candidates:",
        str(len(proposals)),
        "",
        "Latest:",
        latest_text,
        "",
        "Source types:",
    ]
    lines.extend("- " + source_type for source_type in SOURCE_TYPES)
    lines.extend(
        [
            "",
            "Risk status:",
            _risk_status(proposals),
            "",
            "Latest risk:",
            latest_risk,
            "",
            "Review readiness:",
            _review_readiness(proposals),
            "",
            "Latest ready:",
            latest_ready,
            "",
            "Trusted memory:",
            TRUSTED_MEMORY_STATUS,
            "",
            "Guardian Review:",
            "- Trusted memory write: NO",
            "- Engel behavior change: NO",
            "- Runtime source edit: NO",
            "- Candidate content trusted as instruction: NO",
            "- Embedded approval tokens accepted: NO",
            "- Requires future Josh/Guardian trusted-memory workflow: YES",
            "",
            "Boundary:",
            BOUNDARY + ".",
            "Review Dashboard \u2260 Trusted Memory.",
            "",
            "Safety:",
            "- Read-only dashboard only.",
            "- No trusted memory written.",
            "- No candidates applied or promoted.",
            "- No system prompt updated as accepted truth.",
            "- No runtime source edit.",
            "- No code executed.",
            "- No API/network/browser behavior.",
            "- No autonomy or queue/route mutation.",
            "",
            "Authority:",
            AUTHORITY,
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(render_memory_candidate_review_dashboard())
