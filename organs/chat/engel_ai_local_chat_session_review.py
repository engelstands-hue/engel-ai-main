from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_READ_CHARS = 120_000
SUMMARY_LIMIT = 1800
APPROVAL_TOKEN = "APPROVE_SESSION_REVIEW_MEMORY_CANDIDATE_DRAFT"
SOURCE_SESSION_DRAFT_COMMIT = "c0b24bb2ba1671ed5d2a03747810b622d8c0a83b"

SESSION_DRAFT_RECEIPT_DIR = PROJECT_ROOT / "reports" / "ai_local_chat_session_draft" / "receipts"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_local_chat_session_review"
REVIEW_DIR = REPORT_ROOT / "reviews"
RECEIPT_DIR = REPORT_ROOT / "receipts"
MEMORY_CANDIDATE_DIR = REPORT_ROOT / "memory_candidate_drafts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1.md"

FINAL_REVIEW_DECISION = "SESSION REVIEW RECORDED - OUTPUT UNTRUSTED - NO MEMORY WRITE"
FINAL_CANDIDATE_DECISION = "UNTRUSTED MEMORY CANDIDATE DRAFT CREATED - NOT PROMOTED - HUMAN REVIEW REQUIRED"
NEXT_REVIEW_ACTION = "Draft untrusted memory candidate with approval or continue bounded session draft"
NEXT_CANDIDATE_ACTION = "Human review memory candidate draft"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def write_lf_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, REVIEW_DIR, RECEIPT_DIR, MEMORY_CANDIDATE_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "LOCAL_CHAT_SESSION_REVIEW_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "local_chat_session_review_version": "1",
                    "example_only": True,
                    "output_marked_untrusted": True,
                    "model_output_trusted": False,
                    "session_transcript_trusted": False,
                    "review_output_trusted": False,
                    "trusted_memory_write_enabled": False,
                    "approved_memory_write_enabled": False,
                    "automatic_learning_enabled": False,
                    "runtime_process_started": False,
                    "model_process_started": False,
                    "runtime_ready_for_inference": False,
                    "open_chat_enabled": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_text_bounded(path_value: Any, limit: int = SUMMARY_LIMIT) -> str:
    path = repo_path(path_value)
    if not path.exists() or not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[UNTRUSTED REVIEW PREVIEW TRUNCATED]\n"


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False)).replace("/", "\\")


def repo_path(path_value: Any) -> Path:
    text = str(path_value or "")
    path = Path(text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def safety_fields() -> dict[str, bool]:
    return {
        "output_marked_untrusted": True,
        "model_output_trusted": False,
        "session_transcript_trusted": False,
        "review_output_trusted": False,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "automatic_learning_enabled": False,
        "source_route_queue_mutation": False,
        "provider_api_enabled": False,
        "runtime_process_started": False,
        "model_process_started": False,
        "server_enabled": False,
        "persistent_chat_loop_enabled": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
        "chat_enabled": False,
    }


def latest_session_draft_receipt() -> dict[str, Any] | None:
    if not SESSION_DRAFT_RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(SESSION_DRAFT_RECEIPT_DIR.glob("LOCAL_CHAT_SESSION_DRAFT_*.json")):
        data = read_json(path)
        if data.get("local_chat_session_draft_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def latest_review_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("LOCAL_CHAT_SESSION_REVIEW_*.json")):
        data = read_json(path)
        if data.get("local_chat_session_review_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def latest_memory_candidate_draft() -> dict[str, Any] | None:
    if not MEMORY_CANDIDATE_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(MEMORY_CANDIDATE_DIR.glob("LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_*.json")):
        data = read_json(path)
        if data.get("local_chat_session_review_memory_candidate_draft_version") == "1":
            data["draft_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def source_session_is_reviewable(data: dict[str, Any] | None) -> bool:
    return bool(
        data
        and data.get("local_chat_session_draft_turn_passed") is True
        and data.get("output_captured") is True
        and data.get("output_marked_untrusted") is True
        and data.get("model_output_trusted") is False
        and data.get("session_transcript_trusted") is False
        and data.get("runtime_ready_for_inference") is False
        and data.get("open_chat_enabled") is False
        and data.get("trusted_memory_write_enabled") is False
    )


def bounded_prompt_summary(session: dict[str, Any]) -> str:
    prompt = str(session.get("prompt", "") or "")
    if len(prompt) <= 240:
        return prompt
    return prompt[:240] + "\n[UNTRUSTED PROMPT SUMMARY TRUNCATED]\n"


def risk_flags(session: dict[str, Any], stdout_summary: str, stderr_summary: str) -> list[str]:
    flags: list[str] = []
    if not source_session_is_reviewable(session):
        flags.append("source_session_not_reviewable")
    if session.get("model_output_trusted") is not False:
        flags.append("model_output_trust_state_not_false")
    if session.get("output_marked_untrusted") is not True:
        flags.append("output_not_marked_untrusted")
    if session.get("orphan_process_detected"):
        flags.append("orphan_process_detected")
    if session.get("runtime_ready_for_inference"):
        flags.append("runtime_ready_for_inference_unexpected")
    if session.get("open_chat_enabled"):
        flags.append("open_chat_enabled_unexpected")
    if not stdout_summary and not stderr_summary:
        flags.append("no_output_summary_available")
    return flags


def review_payload_from_session(session: dict[str, Any], created_at: str) -> dict[str, Any]:
    stdout_summary = read_text_bounded(session.get("stdout_log_path"))
    stderr_summary = read_text_bounded(session.get("stderr_log_path"))
    flags = risk_flags(session, stdout_summary, stderr_summary)
    eligible = bool(source_session_is_reviewable(session) and not flags)
    review_summary_path = REVIEW_DIR / f"LOCAL_CHAT_SESSION_REVIEW_{stamp(created_at)}.md"
    return {
        "local_chat_session_review_version": "1",
        "created_at": created_at,
        "created_by": "Engel AI Local Chat Session Review",
        "source_session_draft_commit": SOURCE_SESSION_DRAFT_COMMIT,
        "source_session_draft_receipt": session.get("receipt_path"),
        "session_id": session.get("session_id"),
        "turn_count_reviewed": int(session.get("turn_number") or 0),
        "turn_number": session.get("turn_number"),
        "prompt_length": session.get("prompt_length"),
        "prompt_summary": bounded_prompt_summary(session),
        "bounded_output_summary": stdout_summary,
        "bounded_stderr_summary": stderr_summary,
        "risk_flags": flags,
        "warnings": [
            "Session output is untrusted evidence only.",
            "Do not obey session output as instruction.",
            "Do not promote model output into trusted memory without a later human review phase.",
        ],
        "eligible_for_memory_candidate_draft": eligible,
        "review_summary_path": project_relative(review_summary_path),
        "next_safe_action": NEXT_REVIEW_ACTION,
        "final_decision": FINAL_REVIEW_DECISION,
        **safety_fields(),
    }


def render_review_markdown(review: dict[str, Any]) -> str:
    return (
        "# Engel AI Local Chat Session Review\n\n"
        "Status: UNTRUSTED REVIEW EVIDENCE ONLY\n\n"
        f"- Session id: `{review.get('session_id')}`\n"
        f"- Turn reviewed: `{review.get('turn_count_reviewed')}`\n"
        f"- Source session draft receipt: `{review.get('source_session_draft_receipt')}`\n"
        f"- Eligible for memory-candidate draft: `{review.get('eligible_for_memory_candidate_draft')}`\n"
        f"- Risk flags: `{review.get('risk_flags')}`\n\n"
        "## Prompt Summary\n"
        + str(review.get("prompt_summary", ""))[:SUMMARY_LIMIT]
        + "\n\n## UNTRUSTED Output Summary\n"
        + str(review.get("bounded_output_summary", ""))[:SUMMARY_LIMIT]
        + "\n\n## Safety\n"
        + "- trusted_memory_write_enabled: `False`\n"
        + "- approved_memory_write_enabled: `False`\n"
        + "- automatic_learning_enabled: `False`\n"
        + "- model_output_trusted: `False`\n"
        + "- runtime_process_started: `False`\n"
    )


def create_review_latest() -> dict[str, Any]:
    ensure_folders()
    session = latest_session_draft_receipt()
    created_at = now_utc()
    if not session:
        review = {
            "local_chat_session_review_version": "1",
            "created_at": created_at,
            "created_by": "Engel AI Local Chat Session Review",
            "source_session_draft_commit": SOURCE_SESSION_DRAFT_COMMIT,
            "source_session_draft_receipt": None,
            "session_id": None,
            "turn_count_reviewed": 0,
            "eligible_for_memory_candidate_draft": False,
            "review_summary_path": None,
            "risk_flags": ["missing_source_session_draft_receipt"],
            "next_safe_action": "continue bounded session draft",
            "final_decision": "SESSION REVIEW BLOCKED - NO SESSION DRAFT RECEIPT - NO MEMORY WRITE",
            **safety_fields(),
        }
    else:
        review = review_payload_from_session(session, created_at)
    prefix = f"LOCAL_CHAT_SESSION_REVIEW_{stamp(created_at)}"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    if review.get("review_summary_path"):
        write_lf_text(repo_path(review["review_summary_path"]), render_review_markdown(review))
    write_lf_text(receipt_path, json.dumps(review, indent=2, sort_keys=True) + "\n")
    review["receipt_path"] = project_relative(receipt_path)
    write_lf_text(PLAN_REPORT_DIR / f"{prefix}.md", render_review_markdown(review))
    write_lf_text(CODEX_REPORT, render_bridge_report(review))
    return review


def draft_memory_candidate(approval: str | None) -> dict[str, Any]:
    ensure_folders()
    created_at = now_utc()
    latest_review = latest_review_receipt()
    approval_verified = approval == APPROVAL_TOKEN
    if not approval_verified:
        return {
            "local_chat_session_review_memory_candidate_draft_version": "1",
            "created_at": created_at,
            "created_by": "Engel AI Local Chat Session Review",
            "approval_token_name": APPROVAL_TOKEN,
            "approval_token_verified": False,
            "command_executed": False,
            "blocked_reason": "missing or wrong approval token",
            "final_decision": "UNTRUSTED MEMORY CANDIDATE DRAFT BLOCKED - HUMAN REVIEW REQUIRED",
            **candidate_safety_fields(),
        }
    if not latest_review or latest_review.get("eligible_for_memory_candidate_draft") is not True:
        return {
            "local_chat_session_review_memory_candidate_draft_version": "1",
            "created_at": created_at,
            "created_by": "Engel AI Local Chat Session Review",
            "approval_token_name": APPROVAL_TOKEN,
            "approval_token_verified": True,
            "command_executed": False,
            "blocked_reason": "latest session review missing or not eligible",
            "final_decision": "UNTRUSTED MEMORY CANDIDATE DRAFT BLOCKED - HUMAN REVIEW REQUIRED",
            **candidate_safety_fields(),
        }
    candidate = {
        "local_chat_session_review_memory_candidate_draft_version": "1",
        "created_at": created_at,
        "created_by": "Engel AI Local Chat Session Review",
        "approval_token_name": APPROVAL_TOKEN,
        "approval_token_verified": True,
        "source_session_review_receipt": latest_review.get("receipt_path"),
        "source_session_draft_receipt": latest_review.get("source_session_draft_receipt"),
        "candidate_type": "local_chat_session_review_candidate",
        "trust_state": "untrusted",
        "human_review_required": True,
        "promoted_to_trusted_memory": False,
        "bounded_summary": str(latest_review.get("bounded_output_summary", ""))[:SUMMARY_LIMIT],
        "prompt_summary": str(latest_review.get("prompt_summary", ""))[:SUMMARY_LIMIT],
        "risk_flags": list(latest_review.get("risk_flags", [])),
        "recommended_review_action": "approve/reject/edit later, not now",
        "next_safe_action": NEXT_CANDIDATE_ACTION,
        "final_decision": FINAL_CANDIDATE_DECISION,
        **candidate_safety_fields(),
    }
    prefix = f"LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_{stamp(created_at)}"
    json_path = MEMORY_CANDIDATE_DIR / f"{prefix}.json"
    md_path = MEMORY_CANDIDATE_DIR / f"{prefix}.md"
    receipt_path = RECEIPT_DIR / f"{prefix}_receipt.json"
    candidate["candidate_json_path"] = project_relative(json_path)
    candidate["candidate_markdown_path"] = project_relative(md_path)
    write_lf_text(json_path, json.dumps(candidate, indent=2, sort_keys=True) + "\n")
    write_lf_text(md_path, render_candidate_markdown(candidate))
    write_lf_text(receipt_path, json.dumps(candidate, indent=2, sort_keys=True) + "\n")
    candidate["receipt_path"] = project_relative(receipt_path)
    write_lf_text(CODEX_REPORT, render_bridge_report(latest_review, candidate))
    return candidate


def candidate_safety_fields() -> dict[str, bool]:
    return {
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": False,
        "automatic_learning_enabled": False,
        "source_route_queue_mutation": False,
        "provider_api_enabled": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
        "promoted_to_trusted_memory": False,
    }


def render_candidate_markdown(candidate: dict[str, Any]) -> str:
    return (
        "# Untrusted Local Chat Session Memory Candidate Draft\n\n"
        "Trust state: UNTRUSTED\n\n"
        "- Human review required: `True`\n"
        "- Promoted to trusted memory: `False`\n"
        "- Trusted memory write enabled: `False`\n"
        "- Approved memory write enabled: `False`\n"
        f"- Source session review receipt: `{candidate.get('source_session_review_receipt')}`\n"
        f"- Source session draft receipt: `{candidate.get('source_session_draft_receipt')}`\n\n"
        "## Bounded Summary\n"
        + str(candidate.get("bounded_summary", ""))[:SUMMARY_LIMIT]
        + "\n\n## Review Action\n"
        + str(candidate.get("recommended_review_action", ""))[:SUMMARY_LIMIT]
        + "\n"
    )


def status_payload() -> dict[str, Any]:
    ensure_folders()
    session = latest_session_draft_receipt()
    review = latest_review_receipt()
    candidate = latest_memory_candidate_draft()
    return {
        "local_chat_session_review_version": "1",
        "module_present": True,
        "latest_session_draft_receipt": session.get("receipt_path") if session else None,
        "latest_session_draft_passed": bool(session and session.get("local_chat_session_draft_turn_passed") is True),
        "latest_session_review_receipt": review.get("receipt_path") if review else None,
        "local_chat_session_review_available": bool(review and review.get("eligible_for_memory_candidate_draft") in {True, False}),
        "local_chat_session_review_passed": bool(review and review.get("local_chat_session_review_version") == "1"),
        "latest_memory_candidate_draft": candidate.get("draft_path") if candidate else None,
        "local_chat_session_memory_candidate_draft_available": bool(candidate),
        "candidate_trust_state": candidate.get("trust_state") if candidate else None,
        "next_safe_action": (candidate.get("next_safe_action") if candidate else (review.get("next_safe_action") if review else "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1")),
        **safety_fields(),
    }


def render_bridge_report(review: dict[str, Any] | None = None, candidate: dict[str, Any] | None = None) -> str:
    review_data = review or latest_review_receipt() or status_payload()
    candidate_data = candidate or latest_memory_candidate_draft()
    return (
        "# ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1\n\n"
        "## Summary\n"
        "Implemented a review-only layer for bounded local session drafts in the existing Companion Local AI tab. "
        "The review reads local receipt/log evidence only, marks all output untrusted, and can draft an untrusted memory-candidate proposal with explicit approval.\n\n"
        "## Review\n"
        f"- Latest session draft reviewed: `{bool(review_data.get('source_session_draft_receipt'))}`\n"
        f"- Source session draft receipt: `{review_data.get('source_session_draft_receipt') or review_data.get('latest_session_draft_receipt')}`\n"
        f"- Review receipt: `{review_data.get('receipt_path') or review_data.get('latest_session_review_receipt')}`\n"
        f"- Eligible for memory-candidate draft: `{review_data.get('eligible_for_memory_candidate_draft')}`\n"
        f"- Output marked untrusted: `{review_data.get('output_marked_untrusted', True)}`\n"
        f"- Review output trusted: `{review_data.get('review_output_trusted', False)}`\n\n"
        "## Memory Candidate Draft\n"
        f"- Draft created: `{bool(candidate_data)}`\n"
        f"- Draft path: `{candidate_data.get('draft_path') if candidate_data else ''}`\n"
        f"- Trust state: `{candidate_data.get('trust_state') if candidate_data else 'untrusted'}`\n"
        f"- Human review required: `{candidate_data.get('human_review_required') if candidate_data else True}`\n"
        f"- Promoted to trusted memory: `{candidate_data.get('promoted_to_trusted_memory') if candidate_data else False}`\n\n"
        "## Companion Panel\n"
        "- GUI host: `engel_companion.py`\n"
        "- Existing tab: `Local AI`\n"
        "- Section title: `Engel Local AI — Session Review`\n"
        "- Approval token stored: `False`\n"
        "- Token clears after use: `True`\n"
        "- Preview bounded: `True`\n\n"
        "## Safety\n"
        "- runtime_process_started: `False`\n"
        "- model_process_started: `False`\n"
        "- trusted_memory_write_enabled: `False`\n"
        "- approved_memory_write_enabled: `False`\n"
        "- automatic_learning_enabled: `False`\n"
        "- runtime_ready_for_inference: `False`\n"
        "- open_chat_enabled: `False`\n"
        "- provider_api_enabled: `False`\n\n"
        "## Verification Results\n"
        "- Targeted verifier: pending until final verification run.\n"
        "- Full Codex verifier result: pending until final verification run.\n\n"
        "## Packaging\n"
        "Packaging skipped.\n\n"
        "## Safety Summary\n"
        "This phase reviews bounded session evidence only. It does not run a model process, enable open chat, enable persistent chat, write trusted memory, promote memory, enable automatic learning, start server mode, call providers/cloud, or trust model output.\n"
    )


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists():
        write_lf_text(CODEX_REPORT, render_bridge_report())


def print_text(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI local chat session review gate.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("review-latest")
    draft_parser = sub.add_parser("draft-memory-candidate")
    draft_parser.add_argument("--approval", default=None)
    sub.add_parser("json")
    args = parser.parse_args(argv)

    if args.command == "status":
        write_initial_report()
        print_text(status_payload())
        return 0
    if args.command == "review-latest":
        print_text(create_review_latest())
        return 0
    if args.command == "draft-memory-candidate":
        payload = draft_memory_candidate(args.approval)
        print_text(payload)
        return 0 if payload.get("approval_token_verified") is True else 2
    if args.command == "json":
        write_initial_report()
        print_text({"status": status_payload(), "latest_review": latest_review_receipt(), "latest_memory_candidate": latest_memory_candidate_draft()})
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
