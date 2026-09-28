from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import engel_approved_memory_promotion
import engel_candidate_learning_output_review


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
APPROVAL_TOKEN = "APPROVE_EXISTING_CANDIDATE_SET_186_LESSON_24_MEMORY_NO_PROMOTION_NO_WRITE"
EXPECTED_LESSON_COUNT = 186
EXPECTED_MEMORY_COUNT = 24
RECEIPT_ROOT = ROOT / "reports" / "candidate_set_approvals"
APPROVAL_RECEIPT = RECEIPT_ROOT / "ENGEL_CANDIDATE_SET_APPROVAL_186_LESSON_24_MEMORY.json"
BLOCKED_RECEIPT = RECEIPT_ROOT / "ENGEL_CANDIDATE_SET_APPROVAL_186_LESSON_24_MEMORY_BLOCKED.json"
TRUSTED_MEMORY_TARGET = "memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl"

STATUS_LABELS = [
    "CANDIDATE_SET_APPROVAL",
    "HUMAN_APPROVAL_RECORDED",
    "LESSON_CANDIDATES_APPROVED_FOR_LEARNING_REVIEW",
    "MEMORY_CANDIDATES_APPROVED_FOR_FUTURE_PROMOTION",
    "CANDIDATE_APPROVAL_ONLY",
    "NO_MEMORY_PROMOTION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PATCH_APPLY",
    "NO_LEARNING_JOB_RUN",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_PACKAGE_INSTALL",
    "NO_DOWNLOAD",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "TRUSTED_MEMORY_TARGET_REMAINS_DISABLED",
]


class CandidateSetApprovalError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")


def trusted_memory_target_exists() -> bool:
    target = (ROOT / TRUSTED_MEMORY_TARGET).resolve(strict=False)
    return target.exists()


def lesson_candidates() -> list[dict[str, object]]:
    items = engel_candidate_learning_output_review.collect_items("lesson_candidate")
    return sorted(items, key=lambda item: str(item.get("path", "")))


def memory_candidates() -> list[dict[str, object]]:
    items = engel_approved_memory_promotion.discover_candidates()
    approved_paths = approved_receipt_memory_paths()
    if approved_paths:
        items = [
            item
            for item in items
            if _normalize_relpath(str(item.get("source_path", ""))) in approved_paths
        ]
    return sorted(items, key=lambda item: str(item.get("source_path", "")))


def _normalize_relpath(path_text: str) -> str:
    text = str(path_text or "").replace("/", "\\").strip()
    return "\\".join(part for part in text.split("\\") if part).casefold()


def approved_receipt_memory_paths() -> set[str]:
    if not APPROVAL_RECEIPT.exists() or not APPROVAL_RECEIPT.is_file():
        return set()
    try:
        receipt = json.loads(APPROVAL_RECEIPT.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return set()
    items = receipt.get("memory_candidates", [])
    if not isinstance(items, list):
        return set()
    return {
        _normalize_relpath(str(item.get("source_path", "")))
        for item in items
        if isinstance(item, dict) and item.get("source_path")
    }


def count_status() -> dict[str, object]:
    lessons = lesson_candidates()
    memory = memory_candidates()
    return {
        "schema_version": "1.0",
        "generated_at": now_utc(),
        "status": STATUS_LABELS,
        "approval_token": APPROVAL_TOKEN,
        "expected_lesson_candidate_count": EXPECTED_LESSON_COUNT,
        "actual_lesson_candidate_count": len(lessons),
        "expected_memory_candidate_count": EXPECTED_MEMORY_COUNT,
        "actual_memory_candidate_count": len(memory),
        "counts_match": len(lessons) == EXPECTED_LESSON_COUNT and len(memory) == EXPECTED_MEMORY_COUNT,
        "trusted_memory_target": TRUSTED_MEMORY_TARGET,
        "trusted_memory_target_exists": trusted_memory_target_exists(),
        "trusted_memory_target_status": "disabled_until_human_target_approval",
        "approval_scope": [
            "lesson candidates approved for future learning/review use",
            "memory candidate proposals approved for future promotion eligibility",
        ],
        "approval_limitations": [
            "candidate approval is not promotion",
            "memory candidate approval is not trusted-memory write",
            "lesson candidate approval is not execution",
            "fix candidate approval is not patch apply",
            "trusted memory target remains disabled",
        ],
    }


def receipt_id_for(timestamp: str, lesson_count: int, memory_count: int, blocked: bool) -> str:
    seed = f"{APPROVAL_TOKEN}|{timestamp}|{lesson_count}|{memory_count}|{blocked}".encode("utf-8")
    suffix = hashlib.sha256(seed).hexdigest()[:16]
    return "candidate_set_approval_blocked_" + suffix if blocked else "candidate_set_approval_" + suffix


def lesson_record(item: dict[str, object]) -> dict[str, object]:
    return {
        "item_id": item.get("item_id", ""),
        "candidate_type": item.get("candidate_type", "lesson_candidate"),
        "category": item.get("category", "lesson_candidate"),
        "path": item.get("path", ""),
        "sha256": item.get("sha256", ""),
        "size_bytes": item.get("size_bytes", 0),
        "review_state_before_approval": item.get("review_state", ""),
        "warning_flags": item.get("warning_flags", []),
        "approval_status": "human_approved_for_learning_review",
        "approved_for": "future_learning_review_use",
        "content_trust": "untrusted_until_future_approved_flow",
        "no_execution": True,
        "no_trusted_memory_write": True,
        "no_patch_apply": True,
    }


def memory_record(item: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_id": item.get("candidate_id", ""),
        "source_path": item.get("source_path", ""),
        "source_type": item.get("source_type", "memory_candidate_proposal"),
        "source_hash": item.get("source_hash", ""),
        "size_bytes": item.get("size_bytes", 0),
        "validation_status_before_approval": item.get("validation_status", ""),
        "warning_flags": item.get("warning_flags", []),
        "approval_status": "human_approved_for_future_promotion",
        "approved_for": "future_promotion_eligibility_only",
        "promotion_status": "not_promoted",
        "trusted_memory_written": False,
        "content_trust": "untrusted_until_future_promotion_flow",
        "no_trusted_memory_write": True,
        "no_memory_promotion": True,
        "no_patch_apply": True,
    }


def build_receipt(blocked: bool = False, blocked_reason: str = "") -> dict[str, object]:
    lessons = lesson_candidates()
    memory = memory_candidates()
    timestamp = now_utc()
    counts_match = len(lessons) == EXPECTED_LESSON_COUNT and len(memory) == EXPECTED_MEMORY_COUNT
    blocked = blocked or not counts_match
    if not counts_match and not blocked_reason:
        blocked_reason = (
            "candidate counts did not match expected set: "
            f"lessons {len(lessons)}/{EXPECTED_LESSON_COUNT}, memory {len(memory)}/{EXPECTED_MEMORY_COUNT}"
        )
    return {
        "schema_version": "1.0",
        "receipt_type": "engel_candidate_set_approval_v1",
        "receipt_id": receipt_id_for(timestamp, len(lessons), len(memory), blocked),
        "created_at": timestamp,
        "created_by": "explicit_human_instruction_via_codex",
        "approval_token": APPROVAL_TOKEN,
        "status": "blocked_count_mismatch" if blocked else "candidate_set_approved_for_next_stage",
        "blocked": blocked,
        "blocked_reason": blocked_reason,
        "expected_lesson_candidate_count": EXPECTED_LESSON_COUNT,
        "approved_lesson_candidate_count": len(lessons) if not blocked else 0,
        "actual_lesson_candidate_count": len(lessons),
        "expected_memory_candidate_count": EXPECTED_MEMORY_COUNT,
        "approved_memory_candidate_count": len(memory) if not blocked else 0,
        "actual_memory_candidate_count": len(memory),
        "lesson_candidate_approval_status": "human_approved_for_learning_review" if not blocked else "not_approved_count_mismatch",
        "memory_candidate_approval_status": "human_approved_for_future_promotion" if not blocked else "not_approved_count_mismatch",
        "approval_scope": [
            "approve lesson candidates for future learning/review use",
            "approve memory candidate proposals for future promotion eligibility",
        ],
        "approval_limitations": [
            "no trusted memory was written",
            "no memory promotion occurred",
            "no patch or fix was applied",
            "no learning job was run",
            "no model loading, inference, or training occurred",
            "no provider, network, browser, WSL, Hermes, Android, package install, download, worker, or startup behavior occurred",
        ],
        "trusted_memory_target": TRUSTED_MEMORY_TARGET,
        "trusted_memory_target_status": "disabled_until_human_target_approval",
        "trusted_memory_target_exists": trusted_memory_target_exists(),
        "trusted_memory_written": False,
        "memory_promotion_occurred": False,
        "patch_or_fix_applied": False,
        "learning_job_run": False,
        "source_mutation": False,
        "route_mutation": False,
        "model_loading": False,
        "inference": False,
        "training": False,
        "provider_network_browser": False,
        "wsl_hermes_android_runtime": False,
        "package_install": False,
        "download": False,
        "background_worker": False,
        "startup_autorun": False,
        "fake_approvals": False,
        "fake_promoted_memory": False,
        "fake_candidate_records": False,
        "lesson_candidates": [] if blocked else [lesson_record(item) for item in lessons],
        "memory_candidates": [] if blocked else [memory_record(item) for item in memory],
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    resolved_root = RECEIPT_ROOT.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    if not is_relative_to(resolved_root, ROOT) or not is_relative_to(resolved_path, resolved_root):
        raise CandidateSetApprovalError("receipt path escaped reports\\candidate_set_approvals")
    RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_receipt() -> tuple[Path, dict[str, object]]:
    receipt = build_receipt()
    path = BLOCKED_RECEIPT if receipt["blocked"] else APPROVAL_RECEIPT
    write_json(path, receipt)
    return path, receipt


def verify_receipt(path: Path = APPROVAL_RECEIPT) -> dict[str, object]:
    if not path.exists() or not path.is_file():
        raise CandidateSetApprovalError("approval receipt does not exist: " + project_relative(path))
    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    lessons = lesson_candidates()
    memory = memory_candidates()
    failures: list[str] = []
    if receipt.get("approval_token") != APPROVAL_TOKEN:
        failures.append("approval token mismatch")
    if receipt.get("blocked") is not False:
        failures.append("receipt is blocked")
    if len(lessons) != EXPECTED_LESSON_COUNT:
        failures.append("current lesson candidate count mismatch")
    if len(memory) != EXPECTED_MEMORY_COUNT:
        failures.append("current memory candidate count mismatch")
    if receipt.get("approved_lesson_candidate_count") != EXPECTED_LESSON_COUNT:
        failures.append("approved lesson count mismatch")
    if receipt.get("approved_memory_candidate_count") != EXPECTED_MEMORY_COUNT:
        failures.append("approved memory count mismatch")
    if len(receipt.get("lesson_candidates", [])) != EXPECTED_LESSON_COUNT:
        failures.append("lesson candidate record count mismatch")
    if len(receipt.get("memory_candidates", [])) != EXPECTED_MEMORY_COUNT:
        failures.append("memory candidate record count mismatch")
    for key in [
        "trusted_memory_written",
        "memory_promotion_occurred",
        "patch_or_fix_applied",
        "learning_job_run",
        "source_mutation",
        "route_mutation",
        "provider_network_browser",
        "wsl_hermes_android_runtime",
        "model_loading",
        "inference",
        "training",
        "package_install",
        "download",
        "background_worker",
        "startup_autorun",
        "fake_approvals",
        "fake_promoted_memory",
        "fake_candidate_records",
    ]:
        if receipt.get(key) is not False:
            failures.append("safety field must be false: " + key)
    lesson_paths = [str(item.get("path", "")) for item in lessons]
    receipt_lesson_paths = [str(item.get("path", "")) for item in receipt.get("lesson_candidates", [])]
    if receipt_lesson_paths != lesson_paths:
        failures.append("lesson candidate paths do not match current scan")
    memory_paths = [str(item.get("source_path", "")) for item in memory]
    receipt_memory_paths = [str(item.get("source_path", "")) for item in receipt.get("memory_candidates", [])]
    if receipt_memory_paths != memory_paths:
        failures.append("memory candidate paths do not match current scan")
    if receipt.get("trusted_memory_target_status") != "disabled_until_human_target_approval":
        failures.append("trusted memory target status must remain disabled")
    return {
        "valid": not failures,
        "failures": failures,
        "receipt_path": project_relative(path),
        "current_lesson_candidate_count": len(lessons),
        "current_memory_candidate_count": len(memory),
        "current_trusted_memory_target_exists": trusted_memory_target_exists(),
    }


def render_status() -> str:
    status = count_status()
    lines = [
        "Engel Candidate Set Approval V1",
        "",
        "Status:",
        *[f"- {label}" for label in STATUS_LABELS],
        "",
        f"Lesson candidates: {status['actual_lesson_candidate_count']} / {status['expected_lesson_candidate_count']}",
        f"Memory candidates: {status['actual_memory_candidate_count']} / {status['expected_memory_candidate_count']}",
        f"Counts match: {status['counts_match']}",
        f"Approval token: {APPROVAL_TOKEN}",
        f"Trusted memory target: {TRUSTED_MEMORY_TARGET}",
        f"Trusted memory target status: {status['trusted_memory_target_status']}",
        f"Trusted memory target exists: {status['trusted_memory_target_exists']}",
        "",
        "Candidate approval is not promotion.",
        "No trusted memory write, patch apply, or learning job run is performed.",
    ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Candidate Set Approval V1.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show current candidate set counts and boundaries.")
    mode.add_argument("--json", action="store_true", help="Print structured status JSON.")
    mode.add_argument("--write-receipt", action="store_true", help="Write the explicit human approval receipt if counts match.")
    mode.add_argument("--verify-receipt", action="store_true", help="Verify the approval receipt against the current scan.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        if args.json:
            out.write(json.dumps(count_status(), indent=2, sort_keys=True) + "\n")
            return 0
        if args.write_receipt:
            path, receipt = write_receipt()
            if receipt["blocked"]:
                err.write("BLOCKED_CANDIDATE_SET_APPROVAL " + project_relative(path) + "\n")
                return 1
            out.write("WROTE_CANDIDATE_SET_APPROVAL " + project_relative(path) + "\n")
            return 0
        if args.verify_receipt:
            result = verify_receipt()
            out.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
            return 0 if result["valid"] else 1
        out.write(render_status())
        return 0
    except (CandidateSetApprovalError, json.JSONDecodeError) as exc:
        err.write("[STOPPED] " + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
