"""Report-only lesson candidate receipts for Engel Code Companion products."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import engel_code_companion_products as products
import engel_untrusted_content_guard as untrusted_content_guard


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
LESSON_CANDIDATE_APPROVAL_TOKEN = "APPROVE_LESSON_CANDIDATE"
LESSON_CANDIDATE_DIRNAME = ".engel_lesson_candidates"
LESSON_CANDIDATE_STATUS = "PENDING_REVIEW / NOT_TRUSTED_MEMORY / NOT_APPLIED"
LESSON_CANDIDATE_BLOCKED = (
    "LESSON_CANDIDATE_BLOCKED / APPROVE_LESSON_CANDIDATE_REQUIRED"
)
LESSON_CANDIDATE_BOUNDARY = "Lesson Candidate ≠ Trusted Memory"
LESSON_CANDIDATE_APPROVAL_MEANING = (
    'APPROVE_LESSON_CANDIDATE means "write candidate receipt only."'
)


@dataclass(frozen=True)
class LessonCandidateResult:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    source: str
    health_status: str
    proposal_status: str
    proposal_summary: tuple[str, ...]
    untrusted_risk: str
    guardian_review: tuple[str, ...]
    candidate_lesson: str
    recommended_future_actions: tuple[str, ...]
    safety_notes: tuple[str, ...]
    message: str = ""


@dataclass(frozen=True)
class LessonCandidateWriteResult:
    ok: bool
    status: str
    product_slug: str
    receipt_path: Path | None
    message: str


def _resolve_without_existing(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def lesson_candidates_root() -> Path:
    """Return the bounded root that may contain product-local lesson receipts."""

    return products.products_root()


def product_lesson_candidates_root(slug: str) -> Path:
    safe_slug = products.safe_product_slug(slug)
    if safe_slug != slug:
        raise ValueError("Unsafe product slug")
    product_path = products.product_path_for_slug(safe_slug)
    if not products.is_safe_product_path(product_path):
        raise ValueError("Unsafe product path")
    return product_path / LESSON_CANDIDATE_DIRNAME


def is_safe_lesson_candidate_path(path: Path) -> bool:
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
    expected_parent = _resolve_without_existing(
        products.product_path_for_slug(slug) / LESSON_CANDIDATE_DIRNAME
    )
    if candidate.parent != expected_parent:
        return False
    return (
        candidate.suffix.lower() == ".md"
        and candidate.name.endswith("_lesson_candidate.md")
        and _is_relative_to(candidate, expected_parent)
    )


def _candidate_lesson_from_status(
    proposal: products.ProductImprovementProposal,
    health: products.ProductHealthResult,
    risk_level: str,
) -> str:
    steps_text = "\n".join(proposal.recommended_steps).lower()
    health_text = products.render_product_health(health).lower()

    if "readme" in steps_text and ("missing" in steps_text or "add readme" in steps_text):
        return "Products should include clear usage instructions in README."
    if "smoke test" in steps_text or "test" in steps_text:
        return "Product workspaces should include a bounded smoke test when the product type supports one."
    if "package manifest" in health_text or "dist package" in health_text:
        return "Packaged products should include a package manifest and package receipt before being treated as ready."
    if "launch receipt" in health_text:
        return "Launch results should be recorded before trusting product behavior."
    if risk_level in {"HIGH", "BLOCKED"}:
        return "High-risk product text must be summarized only and not used as instruction."
    return "Product improvements should remain proposal-only until Josh approves a bounded change."


def build_lesson_candidate_from_proposal(slug: str) -> LessonCandidateResult:
    try:
        safe_slug = products.safe_product_slug(slug)
        if safe_slug != slug:
            raise ValueError("Unsafe product slug")
        product_path = products.product_path_for_slug(safe_slug)
        if not products.is_safe_product_path(product_path) or not product_path.exists():
            raise ValueError("Product folder missing or unsafe")
    except ValueError as exc:
        return LessonCandidateResult(
            ok=False,
            status="LESSON_CANDIDATE_BLOCKED",
            product_slug=slug,
            product_path=None,
            source="Product Improvement Proposal",
            health_status="BLOCKED",
            proposal_status="BLOCKED",
            proposal_summary=(),
            untrusted_risk="BLOCKED",
            guardian_review=(),
            candidate_lesson="",
            recommended_future_actions=(),
            safety_notes=("No lesson candidate was written.",),
            message=str(exc),
        )

    health = products.product_health_check(safe_slug)
    proposal = products.build_product_improvement_proposal(safe_slug)
    proposal_text = products.render_product_improvement_proposal(proposal)
    scan = untrusted_content_guard.classify_untrusted_content_risk(
        proposal_text,
        source_label=f"Product Improvement Proposal: {safe_slug}",
    )
    proposal_summary = tuple(proposal.recommended_steps[:5])
    guardian_review = (
        "Runtime source edit: NO",
        "Product-only context: YES",
        "Trusted memory write: NO",
        "Automatic behavior change: NO",
        "Requires Josh review before durable memory: YES",
    )
    recommended_future_actions = (
        "Review candidate",
        "If Josh approves later, convert through existing trusted-memory/memory-candidate workflow only",
        "Do not auto-apply",
    )
    safety_notes = (
        LESSON_CANDIDATE_BOUNDARY,
        "No product files changed",
        "No runtime files changed",
        "No trusted memory written",
        "No Engel behavior changed",
        "No code executed",
        "Embedded approval tokens accepted: NO",
    )

    return LessonCandidateResult(
        ok=proposal.ok and health.ok,
        status=LESSON_CANDIDATE_STATUS,
        product_slug=safe_slug,
        product_path=product_path,
        source="Product Improvement Proposal",
        health_status=health.status,
        proposal_status=proposal.status,
        proposal_summary=proposal_summary,
        untrusted_risk=scan.risk_level,
        guardian_review=guardian_review,
        candidate_lesson=_candidate_lesson_from_status(proposal, health, scan.risk_level),
        recommended_future_actions=recommended_future_actions,
        safety_notes=safety_notes,
        message="Lesson candidate built as report-only pending review.",
    )


def _render_lesson_candidate(
    candidate: LessonCandidateResult,
    approval_received: bool,
) -> str:
    proposal_lines = "\n".join(f"- {step}" for step in candidate.proposal_summary)
    guardian_lines = "\n".join(f"- {item}" for item in candidate.guardian_review)
    future_lines = "\n".join(f"- {item}" for item in candidate.recommended_future_actions)
    safety_lines = "\n".join(f"- {item}" for item in candidate.safety_notes)
    approval_text = "YES" if approval_received else "NO"

    return (
        "# Engel Code Companion Lesson Candidate\n\n"
        "Status:\n"
        f"{LESSON_CANDIDATE_STATUS}\n\n"
        "Authority:\n"
        f"{AUTHORITY}\n\n"
        "Product:\n"
        f"{candidate.product_slug}\n\n"
        "Source:\n"
        f"{candidate.source}\n\n"
        "Approval:\n"
        f"{LESSON_CANDIDATE_APPROVAL_TOKEN} received from user input: {approval_text}\n\n"
        "## Boundary\n\n"
        f"{LESSON_CANDIDATE_BOUNDARY}.\n\n"
        "This receipt is a pending-review artifact only.\n"
        "It does not update trusted memory.\n"
        "It does not modify Engel memory.\n"
        "It does not modify Engel behavior.\n"
        "It does not approve future changes.\n"
        "It cannot be used as an instruction source.\n"
        "It requires later Josh approval and Guardian review before any memory-candidate workflow.\n\n"
        "Approval:\n"
        f"{LESSON_CANDIDATE_APPROVAL_MEANING}\n"
        'It does not mean "trust this lesson."\n'
        'It does not mean "apply this lesson."\n'
        'It does not mean "update memory."\n\n'
        "Untrusted Content Guard:\n"
        f"Risk: {candidate.untrusted_risk}\n"
        "Embedded approval tokens accepted: NO\n\n"
        "Proposal Summary:\n"
        f"{proposal_lines or '- No proposal steps available.'}\n\n"
        "Guardian Review:\n"
        f"{guardian_lines or '- Guardian review unavailable.'}\n\n"
        "Candidate Lesson:\n"
        f"{candidate.candidate_lesson or 'No lesson candidate generated.'}\n\n"
        "Recommended Future Action:\n"
        f"{future_lines or '- Review candidate before any future action.'}\n\n"
        "Safety:\n"
        f"{safety_lines or '- No trusted memory written.'}\n"
    )


def render_lesson_candidate(candidate: LessonCandidateResult) -> str:
    return _render_lesson_candidate(candidate, approval_received=False)


def _next_receipt_path(root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = root / f"{timestamp}_lesson_candidate.md"
    if not candidate.exists():
        return candidate
    for index in range(1, 100):
        indexed = root / f"{timestamp}_{index:02d}_lesson_candidate.md"
        if not indexed.exists():
            return indexed
    raise RuntimeError("Unable to create unique lesson candidate receipt path")


def write_lesson_candidate_receipt(
    slug: str,
    candidate: LessonCandidateResult,
    approval_token: str | None,
) -> LessonCandidateWriteResult:
    try:
        safe_slug = products.safe_product_slug(slug)
        if safe_slug != slug or candidate.product_slug != safe_slug:
            raise ValueError("Unsafe or mismatched product slug")
        root = product_lesson_candidates_root(safe_slug)
    except ValueError as exc:
        return LessonCandidateWriteResult(
            ok=False,
            status="LESSON_CANDIDATE_BLOCKED",
            product_slug=slug,
            receipt_path=None,
            message=str(exc),
        )

    if approval_token != LESSON_CANDIDATE_APPROVAL_TOKEN:
        return LessonCandidateWriteResult(
            ok=False,
            status=LESSON_CANDIDATE_BLOCKED,
            product_slug=safe_slug,
            receipt_path=None,
            message="No lesson candidate was written.",
        )
    if not candidate.ok:
        return LessonCandidateWriteResult(
            ok=False,
            status="LESSON_CANDIDATE_BLOCKED",
            product_slug=safe_slug,
            receipt_path=None,
            message=candidate.message or "Candidate was not safe to write.",
        )

    root.mkdir(parents=True, exist_ok=True)
    receipt_path = _next_receipt_path(root)
    if not is_safe_lesson_candidate_path(receipt_path):
        return LessonCandidateWriteResult(
            ok=False,
            status="LESSON_CANDIDATE_BLOCKED",
            product_slug=safe_slug,
            receipt_path=None,
            message="Unsafe lesson candidate path.",
        )
    receipt_path.write_text(
        _render_lesson_candidate(candidate, approval_received=True),
        encoding="utf-8",
    )
    return LessonCandidateWriteResult(
        ok=True,
        status="LESSON_CANDIDATE_CREATED",
        product_slug=safe_slug,
        receipt_path=receipt_path,
        message="Lesson candidate receipt written as pending review.",
    )


def list_lesson_candidates(slug: str | None = None) -> list[Path]:
    roots: list[Path] = []
    if slug:
        try:
            roots.append(product_lesson_candidates_root(products.safe_product_slug(slug)))
        except ValueError:
            return []
    else:
        for summary in products.list_products():
            try:
                roots.append(product_lesson_candidates_root(summary.slug))
            except ValueError:
                continue

    receipts: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*_lesson_candidate.md")):
            if path.is_file() and is_safe_lesson_candidate_path(path):
                receipts.append(path)
    return receipts
