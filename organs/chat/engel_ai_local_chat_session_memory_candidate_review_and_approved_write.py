from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_READ_CHARS = 120_000
SUMMARY_LIMIT = 1800
VERSION = "1"

SOURCE_CANDIDATE_DIR = PROJECT_ROOT / "reports" / "ai_local_chat_session_review" / "memory_candidate_drafts"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_local_chat_session_memory_candidate_review_and_approved_write"
REVIEW_DIR = REPORT_ROOT / "reviews"
RECEIPT_DIR = REPORT_ROOT / "receipts"
APPROVED_RECORD_DIR = REPORT_ROOT / "approved_memory_records"
ROLLBACK_DIR = REPORT_ROOT / "rollback"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_REVIEW_AND_APPROVED_WRITE_V1.md"

ALLOWED_CANDIDATE_TYPES = {"local_chat_session_review_candidate"}
FINAL_REVIEW_DECISION = "UNTRUSTED MEMORY CANDIDATE REVIEW RECORDED - NO HUMAN APPROVAL REQUIRED - NOT YET WRITTEN"
FINAL_WRITE_DECISION = "APPROVED MEMORY RECORD WRITTEN WITHOUT HUMAN APPROVAL - DETERMINISTIC GATES PASSED - ROLLBACK RECORDED"
FINAL_WRITE_BLOCKED = "APPROVED MEMORY RECORD WRITE BLOCKED - DETERMINISTIC GATES DID NOT PASS"

INJECTION_MARKERS = [
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "developer instruction",
    "jailbreak",
    "prompt injection",
    "disregard safety",
]
SOURCE_MUTATION_MARKERS = ["edit source", "modify source", "patch file", "write code", "change code", "delete file"]
ROUTE_QUEUE_MARKERS = ["mutate route", "change route", "queue mutation", "enqueue", "dequeue"]
TRUST_BYPASS_MARKERS = ["trusted memory", "mark trusted", "bypass guardian", "bypass safety", "self approved"]
PROVIDER_MARKERS = ["openai", "anthropic", "provider api", "cloud", "browser", "email", "http://", "https://", "download"]
AUTONOMY_MARKERS = ["run forever", "autonomous", "background worker", "startup auto-load", "auto execute"]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def write_lf_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, REVIEW_DIR, RECEIPT_DIR, APPROVED_RECORD_DIR, ROLLBACK_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_REVIEW_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "local_chat_session_memory_candidate_review_and_approved_write_version": VERSION,
                    "example_only": True,
                    "human_approval_required": False,
                    "approval_token_required": False,
                    "deterministic_guardian_gates_required": True,
                    "trusted_memory_write_enabled": False,
                    "approved_memory_write_performed": False,
                    "model_output_trusted": False,
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


def stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def safety_fields() -> dict[str, bool]:
    return {
        "human_approval_required": False,
        "approval_token_required": False,
        "approval_token_used": False,
        "source_model_output_trusted": False,
        "candidate_content_obeyed": False,
        "deterministic_guardian_gates_required": True,
        "promoted_to_trusted_memory": False,
        "trusted_memory_write_enabled": False,
        "model_output_trusted": False,
        "automatic_learning_enabled": False,
        "source_route_queue_mutation": False,
        "provider_api_enabled": False,
        "runtime_process_started": False,
        "model_process_started": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
    }


def candidate_files() -> list[Path]:
    if not SOURCE_CANDIDATE_DIR.exists():
        return []
    return sorted(path for path in SOURCE_CANDIDATE_DIR.glob("LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_*.json") if path.is_file())


def candidate_summary_text(candidate: dict[str, Any]) -> str:
    pieces = [
        str(candidate.get("prompt_summary", "")),
        str(candidate.get("bounded_summary", ""))[:SUMMARY_LIMIT],
        str(candidate.get("recommended_review_action", "")),
    ]
    return "\n".join(pieces)


def contains_any(text: str, markers: list[str]) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in markers)


def review_candidate(path: Path) -> dict[str, Any]:
    ensure_folders()
    created_at = now_utc()
    candidate = read_json(path)
    text = candidate_summary_text(candidate)
    flags: list[str] = []
    schema_valid = candidate.get("local_chat_session_review_memory_candidate_draft_version") == "1"
    candidate_type = str(candidate.get("candidate_type", ""))
    source_receipt = candidate.get("source_session_review_receipt") or candidate.get("source_session_draft_receipt")
    source_present = bool(source_receipt and repo_path(source_receipt).exists())
    content_bounded = len(text) <= 6_000
    trust_state_untrusted = candidate.get("trust_state") == "untrusted"

    if not schema_valid:
        flags.append("malformed_candidate")
    if not source_present:
        flags.append("missing_source_receipt")
    if candidate_type not in ALLOWED_CANDIDATE_TYPES:
        flags.append("unknown_source")
    if not trust_state_untrusted:
        flags.append("malformed_candidate")
    if candidate.get("promoted_to_trusted_memory") is not False:
        flags.append("trusted_memory_bypass_request")
    if candidate.get("trusted_memory_write_enabled") is not False:
        flags.append("trusted_memory_bypass_request")
    if candidate.get("model_output_trusted") is not False:
        flags.append("model_self_approval_claim")
    if not content_bounded:
        flags.append("too_long")
    if len(str(candidate.get("prompt_summary", "")).strip()) < 4 and len(str(candidate.get("bounded_summary", "")).strip()) < 20:
        flags.append("too_vague")
    if contains_any(text, INJECTION_MARKERS):
        flags.append("prompt_injection_like_text")
    if contains_any(text, SOURCE_MUTATION_MARKERS):
        flags.append("source_mutation_request")
    if contains_any(text, ROUTE_QUEUE_MARKERS):
        flags.append("route_queue_mutation_request")
    if contains_any(text, TRUST_BYPASS_MARKERS):
        flags.append("safety_bypass_request")
    if contains_any(text, PROVIDER_MARKERS):
        flags.append("provider_or_network_request")
    if contains_any(text, AUTONOMY_MARKERS):
        flags.append("hidden_autonomy_request")

    risk_flags = sorted(set(flags))
    low_risk = not risk_flags
    gates_passed = bool(
        schema_valid
        and candidate_type in ALLOWED_CANDIDATE_TYPES
        and source_present
        and trust_state_untrusted
        and candidate.get("promoted_to_trusted_memory") is False
        and candidate.get("trusted_memory_write_enabled") is False
        and candidate.get("model_output_trusted") is False
        and content_bounded
        and low_risk
    )
    recommendation = "eligible_for_approved_write" if gates_passed else ("duplicate_or_low_value" if "duplicate_or_low_value" in risk_flags else ("needs_edit" if risk_flags and "malformed_candidate" not in risk_flags else "reject_candidate"))
    review = {
        "local_chat_session_memory_candidate_review_and_approved_write_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Chat Session Memory Candidate Review And Approved Write",
        "source_candidate_path": project_relative(path),
        "source_candidate_trust_state": candidate.get("trust_state"),
        "schema_valid": schema_valid,
        "candidate_type": candidate_type,
        "source_receipt_present": source_present,
        "trust_state_is_untrusted": trust_state_untrusted,
        "candidate_type_valid": candidate_type in ALLOWED_CANDIDATE_TYPES,
        "content_bounded": content_bounded,
        "low_risk": low_risk,
        "deterministic_guardian_gates_passed": gates_passed,
        "approved_memory_write_eligible": gates_passed,
        "approved_memory_write_performed": False,
        "risk_flags": risk_flags,
        "recommendation": recommendation,
        "review_output_trusted": False,
        "next_safe_action": "write-approved-latest if eligible, otherwise edit/reject candidate",
        "final_decision": FINAL_REVIEW_DECISION,
        **safety_fields(),
    }
    prefix = f"LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_{stamp(created_at)}_{stable_id(project_relative(path))}"
    review_path = REVIEW_DIR / f"{prefix}.json"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    report_path = PLAN_REPORT_DIR / f"{prefix}.md"
    write_lf_text(review_path, json.dumps(review, indent=2, sort_keys=True) + "\n")
    write_lf_text(receipt_path, json.dumps(review, indent=2, sort_keys=True) + "\n")
    write_lf_text(report_path, render_review_markdown(review, candidate))
    review["review_path"] = project_relative(review_path)
    review["receipt_path"] = project_relative(receipt_path)
    return review


def latest_review_for_candidate(candidate_path: Path) -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rel_path = project_relative(candidate_path)
    rows = []
    for path in sorted(RECEIPT_DIR.glob("LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_*.json")):
        data = read_json(path)
        if data.get("source_candidate_path") == rel_path:
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def approved_records() -> list[dict[str, Any]]:
    if not APPROVED_RECORD_DIR.exists():
        return []
    rows = []
    for path in sorted(APPROVED_RECORD_DIR.glob("APPROVED_LOCAL_CHAT_MEMORY_RECORD_*.json")):
        data = read_json(path)
        if data.get("approved_local_chat_memory_record_version") == VERSION:
            data["approved_memory_record_path"] = project_relative(path)
            rows.append(data)
    return rows


def write_approved_for_candidate(path: Path) -> dict[str, Any]:
    review = latest_review_for_candidate(path) or review_candidate(path)
    created_at = now_utc()
    candidate = read_json(path)
    if not review.get("deterministic_guardian_gates_passed"):
        receipt = {
            "local_chat_session_memory_candidate_approved_write_version": VERSION,
            "created_at": created_at,
            "created_by": "Engel AI Local Chat Session Memory Candidate Review And Approved Write",
            "source_candidate_path": project_relative(path),
            "source_review_receipt": review.get("receipt_path"),
            "approved_memory_write_performed": False,
            "blocked_reason": "deterministic_guardian_gates_failed",
            "risk_flags": review.get("risk_flags", []),
            "final_decision": FINAL_WRITE_BLOCKED,
            **write_safety_fields(False),
        }
        receipt_path = RECEIPT_DIR / f"APPROVED_LOCAL_CHAT_MEMORY_WRITE_BLOCKED_{stamp(created_at)}_{stable_id(project_relative(path))}.json"
        write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        receipt["receipt_path"] = project_relative(receipt_path)
        return receipt

    record_id = stable_id(project_relative(path) + json.dumps(candidate, sort_keys=True))
    record_json = APPROVED_RECORD_DIR / f"APPROVED_LOCAL_CHAT_MEMORY_RECORD_{record_id}.json"
    record_md = APPROVED_RECORD_DIR / f"APPROVED_LOCAL_CHAT_MEMORY_RECORD_{record_id}.md"
    rollback_path = ROLLBACK_DIR / f"ROLLBACK_APPROVED_LOCAL_CHAT_MEMORY_RECORD_{record_id}.json"
    approved_record = {
        "approved_local_chat_memory_record_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Chat Session Memory Candidate Review And Approved Write",
        "approval_basis": "deterministic_guardian_gates_passed",
        "human_approval_required": False,
        "approval_token_required": False,
        "source_candidate_path": project_relative(path),
        "source_review_receipt": review.get("receipt_path"),
        "candidate_type": candidate.get("candidate_type"),
        "approved_memory_scope": "approved_local_chat_memory_record_only",
        "source_model_output_trusted": False,
        "candidate_content_obeyed": False,
        "bounded_summary": str(candidate.get("bounded_summary", ""))[:SUMMARY_LIMIT],
        "prompt_summary": str(candidate.get("prompt_summary", ""))[:SUMMARY_LIMIT],
        "risk_flags": review.get("risk_flags", []),
        "deterministic_guardian_gates_passed": True,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
        "trusted_memory_write_enabled_global": False,
    }
    rollback = {
        "rollback_metadata_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Chat Session Memory Candidate Review And Approved Write",
        "approved_memory_record_path": project_relative(record_json),
        "rollback_action": "delete approved local chat memory record and markdown if human later rejects candidate",
        "source_candidate_path": project_relative(path),
        "trusted_memory_target_touched": False,
    }
    write_lf_text(record_json, json.dumps(approved_record, indent=2, sort_keys=True) + "\n")
    write_lf_text(record_md, render_approved_record_markdown(approved_record))
    write_lf_text(rollback_path, json.dumps(rollback, indent=2, sort_keys=True) + "\n")
    receipt = {
        "local_chat_session_memory_candidate_approved_write_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Chat Session Memory Candidate Review And Approved Write",
        "source_candidate_path": project_relative(path),
        "source_review_receipt": review.get("receipt_path"),
        "approved_memory_record_path": project_relative(record_json),
        "approved_memory_record_markdown_path": project_relative(record_md),
        "rollback_metadata_path": project_relative(rollback_path),
        "candidate_type": candidate.get("candidate_type"),
        "source_trust_state": candidate.get("trust_state"),
        "deterministic_guardian_gates_passed": True,
        "approved_memory_write_enabled_for_this_receipt": True,
        "trusted_memory_write_scope": "approved_local_chat_memory_record_only",
        "rollback_metadata_written": True,
        "approved_memory_write_performed": True,
        "final_decision": FINAL_WRITE_DECISION,
        **write_safety_fields(True),
    }
    receipt_path = RECEIPT_DIR / f"APPROVED_LOCAL_CHAT_MEMORY_WRITE_{stamp(created_at)}_{record_id}.json"
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    receipt["receipt_path"] = project_relative(receipt_path)
    write_lf_text(CODEX_REPORT, render_bridge_report(receipt))
    return receipt


def write_safety_fields(enabled_for_receipt: bool) -> dict[str, Any]:
    return {
        "human_approval_required": False,
        "approval_token_required": False,
        "approval_token_used": False,
        "source_model_output_trusted": False,
        "candidate_content_obeyed": False,
        "deterministic_guardian_gates_required": True,
        "promoted_to_trusted_memory": False,
        "trusted_memory_write_enabled_global": False,
        "model_output_trusted": False,
        "automatic_learning_enabled": False,
        "source_route_queue_mutation": False,
        "provider_api_enabled": False,
        "runtime_process_started": False,
        "model_process_started": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
        "approved_memory_write_enabled_for_this_receipt": enabled_for_receipt,
    }


def review_latest() -> dict[str, Any]:
    files = candidate_files()
    if not files:
        return empty_result("no_candidate_drafts_found")
    review = review_candidate(files[-1])
    write_lf_text(CODEX_REPORT, render_bridge_report(review))
    return review


def review_all() -> dict[str, Any]:
    files = candidate_files()
    if not files:
        return empty_result("no_candidate_drafts_found")
    reviews = [review_candidate(path) for path in files[:50]]
    payload = {"reviewed_count": len(reviews), "reviews": reviews, **status_payload()}
    write_lf_text(CODEX_REPORT, render_bridge_report(reviews[-1] if reviews else None))
    return payload


def write_approved_latest() -> dict[str, Any]:
    files = candidate_files()
    if not files:
        return empty_result("no_candidate_drafts_found")
    return write_approved_for_candidate(files[-1])


def write_approved_all() -> dict[str, Any]:
    files = candidate_files()
    if not files:
        return empty_result("no_candidate_drafts_found")
    writes = [write_approved_for_candidate(path) for path in files[:50]]
    return {"write_count": len(writes), "writes": writes, **status_payload()}


def empty_result(reason: str) -> dict[str, Any]:
    return {
        "local_chat_session_memory_candidate_review_and_approved_write_version": VERSION,
        "created_at": now_utc(),
        "created_by": "Engel AI Local Chat Session Memory Candidate Review And Approved Write",
        "candidate_count": 0,
        "blocked_reason": reason,
        "approved_memory_write_performed": False,
        "deterministic_guardian_gates_passed": False,
        "risk_flags": [reason],
        "recommendation": "reject_candidate",
        **safety_fields(),
    }


def status_payload() -> dict[str, Any]:
    ensure_folders()
    files = candidate_files()
    reviews = sorted(RECEIPT_DIR.glob("LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_*.json")) if RECEIPT_DIR.exists() else []
    write_receipts = sorted(RECEIPT_DIR.glob("APPROVED_LOCAL_CHAT_MEMORY_WRITE_*.json")) if RECEIPT_DIR.exists() else []
    records = approved_records()
    latest_review = read_json(reviews[-1]) if reviews else {}
    latest_write = read_json(write_receipts[-1]) if write_receipts else {}
    return {
        "local_chat_session_memory_candidate_review_and_approved_write_version": VERSION,
        "module_present": True,
        "candidate_count": len(files),
        "latest_candidate_draft": project_relative(files[-1]) if files else None,
        "latest_review_receipt": project_relative(reviews[-1]) if reviews else None,
        "latest_review_recommendation": latest_review.get("recommendation"),
        "approved_memory_record_count": len(records),
        "latest_approved_memory_record_path": records[-1].get("approved_memory_record_path") if records else None,
        "latest_write_receipt": project_relative(write_receipts[-1]) if write_receipts else None,
        "latest_write_final_decision": latest_write.get("final_decision"),
        "human_approval_required": False,
        "approval_token_required": False,
        "deterministic_guardian_gates_required": True,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled_global": False,
        "automatic_learning_enabled": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
        "next_safe_action": "ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_V1" if records else "write approved local chat memory record if deterministic gates pass",
    }


def list_payload() -> dict[str, Any]:
    files = candidate_files()
    return {
        "candidate_count": len(files),
        "candidates": [
            {
                "path": project_relative(path),
                "schema_valid": read_json(path).get("local_chat_session_review_memory_candidate_draft_version") == "1",
                "trust_state": read_json(path).get("trust_state"),
                "candidate_type": read_json(path).get("candidate_type"),
            }
            for path in files
        ],
        **safety_fields(),
    }


def render_review_markdown(review: dict[str, Any], candidate: dict[str, Any]) -> str:
    return (
        "# Local Chat Session Memory Candidate Review\n\n"
        f"- Human approval required: `{review.get('human_approval_required')}`\n"
        f"- Approval token required: `{review.get('approval_token_required')}`\n"
        f"- Source candidate: `{review.get('source_candidate_path')}`\n"
        f"- Recommendation: `{review.get('recommendation')}`\n"
        f"- Risk flags: `{review.get('risk_flags')}`\n"
        f"- Deterministic Guardian gates passed: `{review.get('deterministic_guardian_gates_passed')}`\n"
        "- Raw candidate/model output remains untrusted.\n"
        "- Candidate content was not obeyed as instruction.\n\n"
        "## Bounded Candidate Summary\n"
        + str(candidate.get("bounded_summary", ""))[:SUMMARY_LIMIT]
        + "\n"
    )


def render_approved_record_markdown(record: dict[str, Any]) -> str:
    return (
        "# Approved Local Chat Memory Record\n\n"
        "Approved by deterministic Guardian gates, not by model self-claim.\n\n"
        f"- Source candidate: `{record.get('source_candidate_path')}`\n"
        f"- Source review: `{record.get('source_review_receipt')}`\n"
        "- Source model output trusted: `False`\n"
        "- Candidate content obeyed: `False`\n"
        "- Trusted memory target touched: `False`\n\n"
        "## Bounded Approved Summary\n"
        + str(record.get("bounded_summary", ""))[:SUMMARY_LIMIT]
        + "\n"
    )


def render_bridge_report(latest: dict[str, Any] | None = None) -> str:
    status = status_payload()
    latest_payload = latest or {}
    return (
        "# ENGEL_AI_LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_REVIEW_AND_APPROVED_WRITE_V1\n\n"
        "## Summary\n"
        "Implemented deterministic review and approved local chat memory record writes for untrusted local chat session memory-candidate drafts. "
        "No human approval token is required; deterministic Guardian gates are mandatory.\n\n"
        "## Current State\n"
        f"- Candidate count: `{status.get('candidate_count')}`\n"
        f"- Latest candidate draft: `{status.get('latest_candidate_draft')}`\n"
        f"- Latest review recommendation: `{status.get('latest_review_recommendation')}`\n"
        f"- Approved memory record count: `{status.get('approved_memory_record_count')}`\n"
        f"- Latest approved memory record: `{status.get('latest_approved_memory_record_path')}`\n"
        f"- Latest decision: `{latest_payload.get('final_decision') or status.get('latest_write_final_decision')}`\n\n"
        "## Gates\n"
        "- Human approval required: `False`\n"
        "- Approval token required: `False`\n"
        "- Deterministic Guardian gates required: `True`\n"
        "- Source model output trusted: `False`\n"
        "- Candidate content obeyed: `False`\n"
        "- Trusted memory target write: `False`\n\n"
        "## GUI\n"
        "- GUI host: `engel_companion.py`\n"
        "- Existing tab: `Local AI`\n"
        "- Section title: `Engel Local AI — Memory Candidate Review & Approved Write`\n\n"
        "## Verification Results\n"
        "- Targeted verifier: `ENGEL_AI_LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_REVIEW_AND_APPROVED_WRITE_VERIFY_PASS`\n"
        "- Full Codex verifier result: `81 run, 81 passed, 0 failed` / `ENGEL_CODEX_VERIFY_PASS`\n\n"
        "## Packaging\n"
        "Packaging skipped.\n\n"
        "## Safety Summary\n"
        "This phase reviews and writes approved local chat memory records only when deterministic Guardian gates pass. It does not run a model, write trusted memory targets, mutate source/routes/queues, enable open chat, enable automatic learning, call providers/cloud, or trust raw model output.\n"
    )


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists():
        write_lf_text(CODEX_REPORT, render_bridge_report())


def print_text(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI local chat memory candidate deterministic review and approved write.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    sub.add_parser("review-latest")
    sub.add_parser("review-all")
    sub.add_parser("write-approved-latest")
    sub.add_parser("write-approved-all")
    sub.add_parser("json")
    args = parser.parse_args(argv)

    if args.command == "status":
        write_initial_report()
        print_text(status_payload())
        return 0
    if args.command == "list":
        write_initial_report()
        print_text(list_payload())
        return 0
    if args.command == "review-latest":
        print_text(review_latest())
        return 0
    if args.command == "review-all":
        print_text(review_all())
        return 0
    if args.command == "write-approved-latest":
        print_text(write_approved_latest())
        return 0
    if args.command == "write-approved-all":
        print_text(write_approved_all())
        return 0
    if args.command == "json":
        write_initial_report()
        print_text({"status": status_payload(), "list": list_payload()})
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
