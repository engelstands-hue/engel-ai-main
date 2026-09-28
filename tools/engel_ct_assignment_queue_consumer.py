#!/usr/bin/env python3
"""Ship CT-approved remote worker assignments into the ROG phone intake.

This is a bridge, not an approval system. It validates the same assignment
packet contract used by Engel Communication Router, sends only candidate work
to the ROG LAN receiver, and writes receipts for every decision.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any
from urllib import error, request


DEFAULT_TARGET_URL = "http://127.0.0.1:18765/queue/import-assignment"
MAX_PACKET_BYTES = 128 * 1024
ACCEPTED_ROG_STATUSES = {"imported_assignment", "already_present"}
FINAL_DECISION = "CT ASSIGNMENT SHIPPED AS CANDIDATE WORK ONLY - NOT TRUSTED - NOT APPLIED"
REQUIRED_BLOCKED_ACTIONS = {
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
}
ALLOWED_WORKERS = {"android_worker_alpha", "android_worker_beta", "android_worker_gamma"}
ALLOWED_TASK_TYPES = {
    "draft_notes",
    "summarize_text",
    "review_status",
    "extract_topics",
    "classify_untrusted_content",
    "prepare_library_candidate_notes",
    "prepare_memory_candidate_notes",
    "compare_summaries",
    "check_document_against_safety_rules",
    "draft_research_note",
    "draft_candidate_json",
    "format_report_draft",
    "classify_file",
    "compute_small_local_task",
    "return_status",
    "return_logs",
    "return_receipt",
    "draft_code_artifact",
    "web_research_brief",
    "conical_requirements_analysis",
    "conical_verification_plan",
    "conical_dependency_risk_check",
}


@dataclass
class ConsumerConfig:
    root: Path
    target_url: str
    approved_dir: Path
    shipped_dir: Path
    invalid_dir: Path
    receipt_dir: Path
    timeout_seconds: float
    dry_run: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_slug(value: Any, limit: int = 120) -> str:
    text = str(value or "unknown").strip().lower()
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text).strip("_")
    return (cleaned or "unknown")[:limit]


def default_root() -> Path:
    env_root = os.environ.get("ENGEL_APP_ROOT") or os.environ.get("ENGEL_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    if Path("/opt/engel").exists():
        return Path("/opt/engel")
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_packet(path: Path) -> tuple[Any | None, list[str]]:
    try:
        if not path.is_file():
            return None, ["not a file"]
        if path.stat().st_size > MAX_PACKET_BYTES:
            return None, [f"packet exceeds {MAX_PACKET_BYTES} bytes"]
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"]
    except OSError as exc:
        return None, [f"read failed: {exc}"]


def producer_validator(root: Path):
    sys.path.insert(0, str(root))
    try:
        from engel_communication_queen_assignment_producer import validate_assignment_packet

        return validate_assignment_packet
    except Exception:
        return None
    finally:
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass


def fallback_validate(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["assignment packet must be a JSON object"]
    errors: list[str] = []
    expected = {
        "packet_version": "1",
        "approved_by": "Engel Core",
        "approval_scope": "remote_worker_assignment_only",
        "assignment_mode": "remote_worker_auto",
        "trust_level": "untrusted_until_reviewed",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "not_trusted_memory": True,
        "no_direct_control": True,
    }
    required = [
        "packet_id",
        "created_at",
        "created_by",
        "worker_target",
        "task_type",
        "title",
        "instructions",
        "allowed_outputs",
        "blocked_actions",
    ]
    for field in required:
        if field not in payload or payload.get(field) in ("", None):
            errors.append(f"missing required field: {field}")
    for field, value in expected.items():
        if payload.get(field) != value:
            errors.append(f"{field} must be {value!r}")
    if payload.get("worker_target") not in ALLOWED_WORKERS:
        errors.append("worker_target must be a known Android remote worker")
    if payload.get("task_type") not in ALLOWED_TASK_TYPES:
        errors.append("task_type is not allowed")
    if payload.get("allowed_outputs") != ["draft_result_json"]:
        errors.append("allowed_outputs must be draft_result_json only")
    blocked_actions = payload.get("blocked_actions")
    if not isinstance(blocked_actions, list):
        errors.append("blocked_actions must be a list")
    else:
        for action in sorted(REQUIRED_BLOCKED_ACTIONS):
            if action not in blocked_actions:
                errors.append(f"blocked_actions missing: {action}")
    for field in (
        "auto_apply",
        "trusted",
        "write_trusted_memory",
        "execute_commands",
        "mutate_source",
        "mutate_routes",
        "mutate_queue",
        "control_engel",
    ):
        if payload.get(field) is True:
            errors.append(f"forbidden true field: {field}")
    return errors


def validate_packet(root: Path, payload: Any) -> list[str]:
    validator = producer_validator(root)
    if validator is None:
        return fallback_validate(payload)
    return list(validator(payload))


def unique_destination(directory: Path, source: Path, packet_id: Any) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    base = f"{utc_stamp()}_{safe_slug(packet_id)}_{safe_slug(source.stem, 80)}"
    candidate = directory / f"{base}{source.suffix.lower() or '.json'}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{base}_{counter}{source.suffix.lower() or '.json'}"
        counter += 1
    return candidate


def write_receipt(
    config: ConsumerConfig,
    *,
    action: str,
    packet_path: Path,
    packet: Any,
    packet_sha256: str = "",
    destination_path: Path | None = None,
    response: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> Path:
    config.receipt_dir.mkdir(parents=True, exist_ok=True)
    packet_id = packet.get("packet_id") if isinstance(packet, dict) else packet_path.stem
    receipt_path = config.receipt_dir / (
        f"CT_ASSIGNMENT_QUEUE_CONSUMER_{utc_stamp()}_{safe_slug(packet_id)}.json"
    )
    receipt = {
        "timestamp_utc": utc_now(),
        "action": action,
        "source_system": "ct246_engel_ai_main",
        "packet_path": str(packet_path),
        "packet_sha256": packet_sha256,
        "destination_path": str(destination_path) if destination_path else None,
        "target_url": config.target_url,
        "packet_id": packet_id,
        "worker_target": packet.get("worker_target") if isinstance(packet, dict) else None,
        "task_type": packet.get("task_type") if isinstance(packet, dict) else None,
        "title": packet.get("title") if isinstance(packet, dict) else None,
        "errors": errors or [],
        "rog_response": response or {},
        "final_decision": FINAL_DECISION,
        "candidate_only": True,
        "requires_review": True,
        "safe_to_auto_apply": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "dry_run": config.dry_run,
        "consumer": "engel_ct_assignment_queue_consumer.py",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def post_assignment(config: ConsumerConfig, packet_path: Path, packet: dict[str, Any], packet_sha256: str) -> tuple[int, dict[str, Any]]:
    wrapper = {
        "assignment": packet,
        "source_system": "ct246_engel_ai_main",
        "source_path": str(packet_path),
        "source_sha256": packet_sha256,
        "candidate_only": True,
        "requires_review": True,
        "safe_to_auto_apply": False,
        "trusted_memory_write": False,
        "auto_apply": False,
    }
    payload = json.dumps(wrapper).encode("utf-8")
    req = request.Request(
        config.target_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "EngelCTAssignmentConsumer/1"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=config.timeout_seconds) as response:
            text = response.read().decode("utf-8", errors="replace")
            data = json.loads(text) if text.strip() else {}
            return response.status, data if isinstance(data, dict) else {"raw": data}
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(text) if text.strip() else {}
        except json.JSONDecodeError:
            data = {"raw": text}
        return exc.code, data if isinstance(data, dict) else {"raw": data}


def move_packet(source: Path, destination: Path, dry_run: bool) -> Path:
    if dry_run:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return destination


def consume_file(config: ConsumerConfig, packet_path: Path) -> dict[str, Any]:
    packet, load_errors = load_json_packet(packet_path)
    packet_sha256 = sha256_file(packet_path) if packet_path.is_file() else ""
    packet_id = packet.get("packet_id") if isinstance(packet, dict) else packet_path.stem

    if load_errors:
        destination = unique_destination(config.invalid_dir, packet_path, packet_id)
        moved_to = move_packet(packet_path, destination, config.dry_run)
        receipt = write_receipt(
            config,
            action="rejected_invalid_json_moved_to_invalid",
            packet_path=packet_path,
            packet=packet if isinstance(packet, dict) else {"packet_id": packet_id},
            packet_sha256=packet_sha256,
            destination_path=moved_to,
            errors=load_errors,
        )
        return {"path": str(packet_path), "action": "invalid", "receipt": str(receipt)}

    validation_errors = validate_packet(config.root, packet)
    if validation_errors:
        destination = unique_destination(config.invalid_dir, packet_path, packet_id)
        moved_to = move_packet(packet_path, destination, config.dry_run)
        receipt = write_receipt(
            config,
            action="rejected_invalid_contract_moved_to_invalid",
            packet_path=packet_path,
            packet=packet,
            packet_sha256=packet_sha256,
            destination_path=moved_to,
            errors=validation_errors,
        )
        return {"path": str(packet_path), "action": "invalid", "receipt": str(receipt)}

    if config.dry_run:
        receipt = write_receipt(
            config,
            action="dry_run_valid_candidate_not_shipped",
            packet_path=packet_path,
            packet=packet,
            packet_sha256=packet_sha256,
        )
        return {"path": str(packet_path), "action": "dry_run_valid", "receipt": str(receipt)}

    try:
        status_code, response = post_assignment(config, packet_path, packet, packet_sha256)
    except Exception as exc:
        receipt = write_receipt(
            config,
            action="post_failed_left_in_approved",
            packet_path=packet_path,
            packet=packet,
            packet_sha256=packet_sha256,
            errors=[str(exc)],
        )
        return {"path": str(packet_path), "action": "post_failed", "receipt": str(receipt)}

    accepted = response.get("accepted") is True and response.get("status") in ACCEPTED_ROG_STATUSES
    if status_code == 200 and accepted:
        destination = unique_destination(config.shipped_dir, packet_path, packet.get("packet_id"))
        moved_to = move_packet(packet_path, destination, config.dry_run)
        receipt = write_receipt(
            config,
            action="shipped_to_rog_and_moved_to_shipped",
            packet_path=packet_path,
            packet=packet,
            packet_sha256=packet_sha256,
            destination_path=moved_to,
            response=response,
        )
        return {"path": str(packet_path), "action": "shipped", "receipt": str(receipt)}

    receipt = write_receipt(
        config,
        action="rog_rejected_or_unavailable_left_in_approved",
        packet_path=packet_path,
        packet=packet,
        packet_sha256=packet_sha256,
        response=response,
        errors=[f"status_code={status_code}", f"response_status={response.get('status')}"],
    )
    return {"path": str(packet_path), "action": "not_shipped", "receipt": str(receipt)}


def approved_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return [path for path in sorted(directory.glob("*.json"), key=lambda item: item.name.lower()) if path.is_file()]


def consume_once(config: ConsumerConfig, max_files: int) -> dict[str, Any]:
    files = approved_files(config.approved_dir)[:max_files]
    results = [consume_file(config, path) for path in files]
    counts: dict[str, int] = {}
    for result in results:
        counts[result["action"]] = counts.get(result["action"], 0) + 1
    return {
        "ok": True,
        "timestamp_utc": utc_now(),
        "approved_dir": str(config.approved_dir),
        "target_url": config.target_url,
        "files_seen": len(files),
        "counts": counts,
        "results": results,
        "candidate_only": True,
        "trusted_memory_write": False,
        "auto_apply": False,
    }


def build_config(args: argparse.Namespace) -> ConsumerConfig:
    root = Path(args.root).expanduser().resolve()
    assignment_root = root / "remote_workers" / "communication_queen_assignments"
    return ConsumerConfig(
        root=root,
        target_url=args.target_url,
        approved_dir=Path(args.approved_dir).resolve() if args.approved_dir else assignment_root / "approved",
        shipped_dir=Path(args.shipped_dir).resolve() if args.shipped_dir else assignment_root / "shipped_to_rog",
        invalid_dir=Path(args.invalid_dir).resolve() if args.invalid_dir else assignment_root / "invalid",
        receipt_dir=Path(args.receipt_dir).resolve() if args.receipt_dir else root / "reports" / "ct_assignment_queue_consumer",
        timeout_seconds=args.timeout,
        dry_run=args.dry_run,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ship CT approved remote worker assignments to ROG intake.")
    parser.add_argument("--root", default=str(default_root()))
    parser.add_argument("--target-url", default=os.environ.get("ENGEL_ROG_ASSIGNMENT_IMPORT_URL", DEFAULT_TARGET_URL))
    parser.add_argument("--approved-dir", default="")
    parser.add_argument("--shipped-dir", default="")
    parser.add_argument("--invalid-dir", default="")
    parser.add_argument("--receipt-dir", default="")
    parser.add_argument("--max", type=int, default=25)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--once", action="store_true", help="Run one scan and exit.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = build_config(args)
    result = consume_once(config, max(1, args.max))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
