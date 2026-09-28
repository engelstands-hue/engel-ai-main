from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys
import textwrap

import engel_global_password_gate as global_password_gate


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
PROPOSAL_DIR = PROJECT_ROOT / "reports" / "memory_candidates"
RECEIPT_DIR = PROJECT_ROOT / "reports" / "memory_promotion_receipts"
APPROVAL_TOKEN = "APPROVE_PROMOTE_MEMORY_CANDIDATE"
WRITER_VERSION = "ENGEL_MEMORY_PROMOTION_WRITER_V1"

TRUSTED_MEMORY_TARGET_IMPLEMENTED = False
TRUSTED_MEMORY_TARGET_STATUS = "APPROVED_TRUSTED_MEMORY_TARGET_UNCLEAR"
TRUSTED_MEMORY_TARGET = "STOPPED_UNCLEAR_APPROVED_TRUSTED_MEMORY_LOCATION"

WRITER_STATUS = [
    "MEMORY_PROMOTION_WRITER",
    "HUMAN_APPROVAL_REQUIRED",
    "APPROVAL_TOKEN_REQUIRED",
    "SOURCE_CHAIN_REQUIRED",
    "PROMPT_INJECTION_REVIEW_REQUIRED",
    "AUTHORITY_REVIEW_REQUIRED",
    "RECEIPT_REQUIRED",
    "BOUNDED_MEMORY_WRITE_ONLY",
    "NO_SOURCE_MUTATION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_TRAINING",
    "NO_RUNTIME_TRIGGER",
    "NO_BACKGROUND_WORKER",
]

RECEIPT_FIELDS = [
    "memory_promotion_receipt_id",
    "memory_candidate_proposal_id",
    "source_research_note_id",
    "source_lesson_candidate_id",
    "source_chain",
    "approved_by",
    "approval_token",
    "promotion_decision",
    "prompt_injection_review_result",
    "authority_review_result",
    "uncertainty_notes",
    "reason_to_remember",
    "core_continuity_linkage",
    "trusted_memory_target",
    "receipt_created_at",
    "rollback_note",
    "human_intervention_required",
    "no_automatic_memory_promotion",
    "no_source_mutation",
    "no_provider_network_browser",
    "no_model_training",
    "no_runtime_trigger",
]

PROPOSAL_FIELDS = [
    "memory_candidate_proposal_id",
    "source_lesson_candidate_id",
    "source_research_note_id",
    "topic_id",
    "topic_title",
    "proposed_memory_summary",
    "reason_to_remember",
    "evidence_chain",
    "source_references",
    "uncertainty_notes",
    "prompt_injection_review_needed",
    "authority_review_needed",
    "suggested_core_continuity_linkage",
]

HEADING_TO_FIELD = {field.replace("_", " ").title(): field for field in PROPOSAL_FIELDS}

BOUNDARY_TEXT = [
    "Memory promotion requires the exact APPROVE_PROMOTE_MEMORY_CANDIDATE token.",
    "No automatic promotion is available.",
    "No trusted memory is written when the approved trusted memory location is unclear.",
    "Receipts are written only to reports\\memory_promotion_receipts.",
    "No source mutation, provider calls, network, browser, model training, runtime trigger, or background worker is used.",
]


class MemoryPromotionWriterError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def reject_unsafe_report_name(file_name: str) -> None:
    lowered = file_name.lower()
    if lowered.startswith(("http://", "https://")):
        raise MemoryPromotionWriterError("URLs are not accepted.")
    if file_name.startswith("\\\\"):
        raise MemoryPromotionWriterError("UNC paths are not accepted.")
    if any(marker in file_name for marker in ("*", "?", "[")):
        raise MemoryPromotionWriterError("Wildcard proposal names are not accepted.")
    if any(separator in file_name for separator in ("\\", "/")):
        raise MemoryPromotionWriterError("Only a proposal file name is accepted, not a path.")
    if ".." in file_name or ":" in file_name:
        raise MemoryPromotionWriterError("Path traversal and drive names are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", file_name):
        raise MemoryPromotionWriterError("Proposal names must be safe .md file names.")


def resolve_proposal_path(proposal_file_name: str) -> Path:
    reject_unsafe_report_name(proposal_file_name)
    proposal_dir = PROPOSAL_DIR.resolve()
    proposal_path = (proposal_dir / proposal_file_name).resolve()
    if not is_relative_to(proposal_path, proposal_dir):
        raise MemoryPromotionWriterError("Proposal path escaped reports\\memory_candidates.")
    if not proposal_path.exists() or not proposal_path.is_file():
        raise MemoryPromotionWriterError("Memory candidate proposal does not exist in reports\\memory_candidates.")
    return proposal_path


def parse_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            sections[current] = "\n".join(buffer).strip()

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current = HEADING_TO_FIELD.get(line[3:].strip())
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()
    return sections


def read_proposal(proposal_file_name: str) -> tuple[Path, dict[str, str], str]:
    proposal_path = resolve_proposal_path(proposal_file_name)
    text = proposal_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_markdown_sections(text)
    if "MEMORY_CANDIDATE_PROPOSAL_ONLY" not in text:
        raise MemoryPromotionWriterError("Proposal is missing MEMORY_CANDIDATE_PROPOSAL_ONLY label.")
    if "NOT_TRUSTED_MEMORY" not in text:
        raise MemoryPromotionWriterError("Proposal is missing NOT_TRUSTED_MEMORY label.")
    return proposal_path, sections, text


def source_exists_from_reference(reference: str) -> bool:
    cleaned = reference.strip().lstrip("-").strip()
    if not cleaned or cleaned.startswith(("http://", "https://", "\\\\")):
        return False
    if ":" in cleaned:
        return False
    candidate = (PROJECT_ROOT / cleaned).resolve()
    if not is_relative_to(candidate, PROJECT_ROOT.resolve()):
        return False
    return candidate.exists() and candidate.is_file()


def evaluate_promotion_conditions(proposal: dict[str, str]) -> list[str]:
    stop_reasons: list[str] = []
    if not proposal.get("memory_candidate_proposal_id"):
        stop_reasons.append("memory candidate proposal id missing")
    if not proposal.get("source_research_note_id"):
        stop_reasons.append("source research note id missing")
    if not proposal.get("source_lesson_candidate_id"):
        stop_reasons.append("source lesson candidate id missing")
    if not proposal.get("evidence_chain") or not proposal.get("source_references"):
        stop_reasons.append("source chain incomplete")
    source_reference_lines = [line for line in proposal.get("source_references", "").splitlines() if line.strip()]
    if source_reference_lines and not any(source_exists_from_reference(line) for line in source_reference_lines):
        stop_reasons.append("source research note or lesson candidate file could not be confirmed from source references")
    if "completed" not in proposal.get("prompt_injection_review_result", "").lower():
        stop_reasons.append("prompt-injection review completed result missing")
    if "completed" not in proposal.get("authority_review_result", "").lower():
        stop_reasons.append("authority review completed result missing")
    if not proposal.get("uncertainty_notes"):
        stop_reasons.append("uncertainty not recorded")
    if not proposal.get("reason_to_remember"):
        stop_reasons.append("reason to remember unclear")
    if not TRUSTED_MEMORY_TARGET_IMPLEMENTED:
        stop_reasons.append("approved trusted memory location is unclear")
    return stop_reasons


def make_receipt_id(proposal_id: str, timestamp: str, mode: str) -> str:
    seed = f"{proposal_id}|{timestamp}|{mode}|{WRITER_VERSION}".encode("utf-8")
    return "memory_promotion_receipt_" + hashlib.sha256(seed).hexdigest()[:16]


def build_receipt(proposal_file_name: str, mode: str, approval_token: str | None) -> dict[str, str]:
    proposal_path, proposal, _ = read_proposal(proposal_file_name)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    proposal_id = proposal.get("memory_candidate_proposal_id", "unknown_memory_candidate_proposal")
    stop_reasons = evaluate_promotion_conditions(proposal)
    if mode == "dry-run":
        decision = "DRY_RUN_NO_MEMORY_WRITE"
        stopped = "true"
    elif stop_reasons:
        decision = "STOPPED_NO_MEMORY_WRITE"
        stopped = "true"
    else:
        decision = "READY_FOR_BOUNDED_MEMORY_WRITE"
        stopped = "false"
    source_chain = proposal.get("evidence_chain") or proposal.get("source_references") or "source chain missing"
    return {
        "memory_promotion_receipt_id": make_receipt_id(proposal_id, timestamp, mode),
        "memory_candidate_proposal_id": proposal_id,
        "source_research_note_id": proposal.get("source_research_note_id", "unknown_source_research_note"),
        "source_lesson_candidate_id": proposal.get("source_lesson_candidate_id", "unknown_source_lesson_candidate"),
        "source_chain": source_chain,
        "approved_by": "human_exact_token_supplied" if approval_token == APPROVAL_TOKEN else "not_approved_for_write",
        "approval_token": approval_token or "not_supplied_for_dry_run",
        "promotion_decision": decision,
        "prompt_injection_review_result": proposal.get("prompt_injection_review_result", "missing_or_not_completed"),
        "authority_review_result": proposal.get("authority_review_result", "missing_or_not_completed"),
        "uncertainty_notes": proposal.get("uncertainty_notes", "missing"),
        "reason_to_remember": proposal.get("reason_to_remember", "missing"),
        "core_continuity_linkage": proposal.get("suggested_core_continuity_linkage", "Core Continuity linkage required before promotion."),
        "trusted_memory_target": TRUSTED_MEMORY_TARGET,
        "receipt_created_at": timestamp,
        "rollback_note": "No trusted memory was written; rollback is not needed. If future target is defined, record exact removal path here.",
        "human_intervention_required": "true" if stopped == "true" else "false",
        "no_automatic_memory_promotion": "true",
        "no_source_mutation": "true",
        "no_provider_network_browser": "true",
        "no_model_training": "true",
        "no_runtime_trigger": "true",
        "mode": mode,
        "proposal_path": str(proposal_path.relative_to(PROJECT_ROOT)).replace("/", "\\"),
        "stopped": stopped,
        "stop_reason": "; ".join(stop_reasons) if stop_reasons else "none",
        "writer_target_status": TRUSTED_MEMORY_TARGET_STATUS,
    }


def render_receipt(receipt: dict[str, str]) -> str:
    lines = [
        "# Engel Memory Promotion Writer V1 Receipt",
        "",
        "Status:",
        *[f"- {status}" for status in WRITER_STATUS],
        "",
        "Boundary:",
        *[f"- {item}" for item in BOUNDARY_TEXT],
        "",
    ]
    for field in RECEIPT_FIELDS + ["mode", "proposal_path", "stopped", "stop_reason", "writer_target_status"]:
        lines.extend([f"## {field.replace('_', ' ').title()}", str(receipt.get(field, "")), ""])
    return "\n".join(lines).rstrip() + "\n"


def safe_receipt_filename(receipt: dict[str, str]) -> str:
    receipt_id = re.sub(r"[^A-Za-z0-9_-]+", "_", receipt["memory_promotion_receipt_id"]).strip("_").lower()
    proposal_id = re.sub(r"[^A-Za-z0-9_-]+", "_", receipt["memory_candidate_proposal_id"]).strip("_").lower()
    return f"{receipt_id}_{proposal_id}.md"


def write_stopped_receipt(receipt: dict[str, str]) -> Path:
    receipt_dir = RECEIPT_DIR.resolve()
    root = PROJECT_ROOT.resolve()
    if not is_relative_to(receipt_dir, root):
        raise MemoryPromotionWriterError("Memory promotion receipt folder escaped the project root.")
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    receipt_path = (receipt_dir / safe_receipt_filename(receipt)).resolve()
    if not is_relative_to(receipt_path, receipt_dir):
        raise MemoryPromotionWriterError("Memory promotion receipt path escaped reports\\memory_promotion_receipts.")
    receipt_path.write_text(render_receipt(receipt), encoding="utf-8")
    return receipt_path


def usage_text() -> str:
    return textwrap.dedent(
        f"""\
        Engel Memory Promotion Writer V1

        Status:
        MEMORY_PROMOTION_WRITER / HUMAN_APPROVAL_REQUIRED / APPROVAL_TOKEN_REQUIRED / SOURCE_CHAIN_REQUIRED /
        PROMPT_INJECTION_REVIEW_REQUIRED / AUTHORITY_REVIEW_REQUIRED / RECEIPT_REQUIRED /
        BOUNDED_MEMORY_WRITE_ONLY / NO_SOURCE_MUTATION / NO_PROVIDER_CALLS / NO_NETWORK /
        NO_BROWSER / NO_MODEL_TRAINING / NO_RUNTIME_TRIGGER / NO_BACKGROUND_WORKER

        Usage:
          python engel_memory_promotion_writer.py --proposal <proposal-file-name> --dry-run
          python engel_memory_promotion_writer.py --proposal <proposal-file-name> --approve-token {APPROVAL_TOKEN} --write --password-prompt

        Current target status:
          {TRUSTED_MEMORY_TARGET_STATUS}

        Boundary:
          The approved trusted memory location is unclear, so --write stops and writes a stopped
          receipt only. No trusted memory is written until an explicit trusted-memory target is
          defined and verified.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Strictly gated approved memory promotion writer.")
    parser.add_argument("--proposal", metavar="PROPOSAL_FILE_NAME", help="Memory candidate proposal file name from reports\\memory_candidates.")
    parser.add_argument("--approve-token", metavar="TOKEN", help="Exact approval token required for --write.")
    parser.add_argument("--dry-run", action="store_true", help="Print the promotion receipt/plan without writing memory or receipt files.")
    parser.add_argument("--write", action="store_true", help="Attempt approved promotion; currently stops if trusted-memory target is unclear.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for the global password before protected write mode.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.proposal or (not args.dry_run and not args.write):
        out.write(usage_text())
        return 0
    if args.dry_run and args.write:
        err.write("Choose either --dry-run or --write, not both.\n")
        return 2
    if args.write and args.approve_token != APPROVAL_TOKEN:
        err.write(f"[STOPPED] Exact approval token required: {APPROVAL_TOKEN}\n")
        return 2
    if args.write and not args.password_prompt:
        err.write("Protected action requires --password-prompt.\n")
        return 2
    try:
        if args.write:
            global_password_gate.prompt_and_require_action("promote_memory_candidate")
        mode = "write" if args.write else "dry-run"
        receipt = build_receipt(args.proposal, mode, args.approve_token)
        rendered = render_receipt(receipt)
        if args.dry_run:
            out.write(rendered)
            return 0
        receipt_path = write_stopped_receipt(receipt)
        if receipt.get("stopped") == "true":
            out.write(f"STOPPED_MEMORY_PROMOTION {receipt_path.relative_to(PROJECT_ROOT)}\n")
            out.write("No trusted memory was written.\n")
            out.write("Stop reason: " + receipt.get("stop_reason", "unknown") + "\n")
            return 1
        out.write("READY_BUT_MEMORY_TARGET_NOT_IMPLEMENTED\n")
        return 1
    except MemoryPromotionWriterError as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1
    except global_password_gate.PasswordGateError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
