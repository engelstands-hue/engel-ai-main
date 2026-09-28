#!/usr/bin/env python3
"""Engel Communication Router approved Remote Worker assignment producer.

Phase 6 creates local, human-triggered assignment packets for the existing
Remote Worker Phase 5 polling lane. Assignment content is untrusted work
material, never a command, route, trusted-memory write, source edit, or apply
instruction.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any

from engel_branding import (
    ENGEL_COMMUNICATION_ROUTER_NAME,
    ENGEL_CORE_NAME,
    is_engel_communication_router_name,
)


ASSIGNMENT_ROOT = Path("remote_workers") / "communication_queen_assignments"
APPROVED_DIR = ASSIGNMENT_ROOT / "approved"
CLAIMED_DIR = ASSIGNMENT_ROOT / "claimed"
RETURNED_DIR = ASSIGNMENT_ROOT / "returned"
INVALID_DIR = ASSIGNMENT_ROOT / "invalid"
EXAMPLES_DIR = ASSIGNMENT_ROOT / "examples"
RETIRED_DIR = ASSIGNMENT_ROOT / "retired"
REPORT_DIR = Path("reports") / "communication_queen_assignments"
MAX_TEXT_BYTES = 128 * 1024
MAX_EMBEDDED_TEXT = 4000
MAX_PREVIEW = 1200
MAX_ASSIGNMENT_FILES = 200
EXPECTED_WORKER = "android_worker_alpha"  # kept for back-compat with callers + default CLI worker
FINAL_DECISION = "APPROVED FOR REMOTE WORKER ASSIGNMENT ONLY - UNTRUSTED RESULT REQUIRED"
PRODUCER_NAME = ENGEL_COMMUNICATION_ROUTER_NAME + " Remote Worker Assignment Producer V1"

# Per-worker allowed task types. Source of truth: each worker's
# config/worker_capabilities.json + config/worker_identity.json on disk.
# Adding a worker here also requires the matching capabilities/identity files
# in remote_workers/<worker_id>/config/ to keep the on-phone validation honest.
WORKER_ALLOWED_TASK_TYPES: dict[str, set[str]] = {
    "android_worker_alpha": {
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
    },
    "android_worker_beta": {
        "draft_candidate_json",
        "format_report_draft",
        "classify_file",
        "return_status",
        "return_logs",
        "return_receipt",
        "draft_code_artifact",
        "web_research_brief",
        "conical_verification_plan",
    },
    "android_worker_gamma": {
        # Samsung Galaxy A14 5G (ANDROID_WORKER_GAMMA), assigned 2026-07-04, lan
        # transport, app v1.0.12+. Small local compute / report formatting
        # worker per remote_workers/android_worker_gamma/config/.
        "compute_small_local_task",
        "format_report_draft",
        "summarize_text",
        "classify_file",
        "return_status",
        "return_logs",
        "return_receipt",
        "conical_dependency_risk_check",
        "web_research_brief",
        "draft_code_artifact",
    },
}

# Flat union of all allowed task types across workers — used by validate_assignment_packet
# when it doesn't know which worker the packet targets ahead of time.
ALLOWED_TASK_TYPES: set[str] = set().union(*WORKER_ALLOWED_TASK_TYPES.values())
ALLOWED_WORKERS: set[str] = set(WORKER_ALLOWED_TASK_TYPES.keys())

BLOCKED_TASK_TYPES = {
    "execute_command",
    "run_command",
    "shell",
    "powershell",
    "cmd",
    "bash",
    "wsl",
    "run_route",
    "edit_source",
    "apply_patch",
    "write_memory",
    "trusted_memory_write",
    "approve_memory",
    "promote_memory",
    "mutate_queue",
    "mutate_routes",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
    "start_worker",
    "start_server",
    "auto_apply",
    "control_engel",
}

REQUIRED_BLOCKED_ACTIONS = [
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
]

RISK_PATTERNS = [
    "run this command",
    "execute",
    "powershell",
    "cmd.exe",
    "bash",
    "wsl",
    "curl",
    "invoke-webrequest",
    "download",
    "install",
    "write memory",
    "trusted memory",
    "apply patch",
    "modify source",
    "mutate route",
    "mutate queue",
    "auto apply",
    "bypass",
    "ignore previous instructions",
    "disable verifier",
    "approve this",
    "promote this",
    "delete files",
    "exfiltrate",
    "token",
    "secret",
    "password",
]

ALLOWED_SOURCE_SUFFIXES = {".txt", ".md", ".json"}
REJECTED_SOURCE_SUFFIXES = {
    ".exe",
    ".bat",
    ".ps1",
    ".cmd",
    ".sh",
    ".dll",
    ".zip",
    ".pdf",
    ".docx",
}

ALLOWED_SOURCE_ROOTS = [
    Path("reports").resolve(),
    Path("memory").resolve(),
    Path("remote_workers").resolve(),
    Path("library_intake").resolve(),
    Path("engel_library").resolve(),
]


@dataclass(frozen=True)
class SourceMaterial:
    path: str | None
    sha256: str | None
    preview: str
    truncated: bool
    size_bytes: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_stamp(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def timestamp_file(value: str) -> str:
    return value.replace("-", "").replace(":", "").replace("Z", "Z")


def ensure_scaffold() -> None:
    for directory in [
        ASSIGNMENT_ROOT,
        APPROVED_DIR,
        CLAIMED_DIR,
        RETURNED_DIR,
        INVALID_DIR,
        EXAMPLES_DIR,
        RETIRED_DIR,
        REPORT_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bounded(value: Any, limit: int = MAX_PREVIEW) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def slugify(value: str, limit: int = 60) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip().lower())
    cleaned = cleaned.strip("_")
    return (cleaned or "assignment")[:limit].strip("_") or "assignment"


def safe_packet_id(worker: str, task_type: str, title: str, created_at: str) -> str:
    return f"{timestamp_file(created_at)}_{slugify(worker, 40)}_{slugify(task_type, 40)}_{slugify(title, 64)}"


def risk_flags_for_text(*texts: str) -> list[str]:
    combined = "\n".join(texts).lower()
    return [pattern for pattern in RISK_PATTERNS if pattern in combined]


def resolve_safe_source(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_file():
        raise ValueError("source path must be an existing file")
    if path.suffix.lower() in REJECTED_SOURCE_SUFFIXES:
        raise ValueError("source file type is rejected for Phase 6")
    if path.suffix.lower() not in ALLOWED_SOURCE_SUFFIXES:
        raise ValueError("source file type is not allowed for Phase 6")
    resolved = path.resolve()
    if not any(resolved == root or root in resolved.parents for root in ALLOWED_SOURCE_ROOTS):
        raise ValueError("source file is outside approved Engel roots")
    if resolved.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("source file is too large for bounded Phase 6 intake")
    return resolved


def read_source_material(path_text: str | None) -> SourceMaterial:
    if not path_text:
        return SourceMaterial(None, None, "", False, 0)
    path = resolve_safe_source(path_text)
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    preview = text[:MAX_EMBEDDED_TEXT]
    return SourceMaterial(
        path=str(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        preview=preview,
        truncated=len(text) > MAX_EMBEDDED_TEXT,
        size_bytes=len(raw),
    )


def assignment_path_for(packet_id: str, directory: Path = APPROVED_DIR) -> Path:
    return directory / f"{slugify(packet_id, 180)}.json"


def build_assignment_packet(
    *,
    worker: str,
    task_type: str,
    title: str,
    instructions: str,
    source: SourceMaterial | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    created = created_at or utc_stamp()
    source = source or SourceMaterial(None, None, "", False, 0)
    packet_id = safe_packet_id(worker, task_type, title, created)
    source_refs: list[dict[str, Any]] = []
    if source.path:
        source_refs.append(
            {
                "source_path": source.path,
                "source_sha256": source.sha256,
                "size_bytes": source.size_bytes,
                "preview_truncated": source.truncated,
            }
        )
    source_summary = bounded(source.preview, MAX_PREVIEW) if source.preview else ""
    return {
        "packet_version": "1",
        "packet_id": packet_id,
        "created_at": created,
        "created_by": ENGEL_COMMUNICATION_ROUTER_NAME,
        "approved_by": ENGEL_CORE_NAME,
        "approval_scope": "remote_worker_assignment_only",
        "assignment_mode": "remote_worker_auto",
        "trust_level": "untrusted_until_reviewed",
        "worker_target": worker,
        "task_type": task_type,
        "title": title.strip(),
        "instructions": bounded(instructions, MAX_EMBEDDED_TEXT),
        "source_summary": source_summary,
        "source_refs": source_refs,
        "allowed_outputs": ["draft_result_json"],
        "blocked_actions": list(REQUIRED_BLOCKED_ACTIONS),
        "requires_review": True,
        "safe_to_auto_apply": False,
        "not_trusted_memory": True,
        "no_direct_control": True,
        "risk_flags": risk_flags_for_text(instructions, source.preview),
    }


def validate_assignment_packet(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["assignment packet must be a JSON object"]
    required_fields = [
        "packet_version",
        "packet_id",
        "created_at",
        "created_by",
        "approved_by",
        "approval_scope",
        "assignment_mode",
        "trust_level",
        "worker_target",
        "task_type",
        "title",
        "instructions",
        "allowed_outputs",
        "blocked_actions",
        "requires_review",
        "safe_to_auto_apply",
        "not_trusted_memory",
        "no_direct_control",
    ]
    for field in required_fields:
        if field not in payload:
            errors.append(f"missing required field: {field}")
    expected_values = {
        "packet_version": "1",
        "approved_by": ENGEL_CORE_NAME,
        "approval_scope": "remote_worker_assignment_only",
        "assignment_mode": "remote_worker_auto",
        "trust_level": "untrusted_until_reviewed",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "not_trusted_memory": True,
        "no_direct_control": True,
    }
    for field, expected in expected_values.items():
        if field in payload and payload.get(field) != expected:
            errors.append(f"{field} must be {expected!r}")
    if "created_by" in payload and not is_engel_communication_router_name(payload.get("created_by")):
        errors.append(f"created_by must be {ENGEL_COMMUNICATION_ROUTER_NAME!r}")
    worker_target = str(payload.get("worker_target", ""))
    if worker_target not in ALLOWED_WORKERS:
        errors.append("worker_target must be one of " + ", ".join(sorted(ALLOWED_WORKERS)))
    task_type = str(payload.get("task_type", ""))
    if task_type in BLOCKED_TASK_TYPES:
        errors.append("blocked task type")
    if task_type and task_type not in ALLOWED_TASK_TYPES:
        errors.append("task_type is not allowed")
    if worker_target in WORKER_ALLOWED_TASK_TYPES and task_type and task_type not in WORKER_ALLOWED_TASK_TYPES[worker_target]:
        errors.append("task_type not allowed for " + worker_target)
    title = str(payload.get("title", "")).strip()
    instructions = str(payload.get("instructions", "")).strip()
    packet_id = str(payload.get("packet_id", "")).strip()
    if not packet_id:
        errors.append("packet_id must be non-empty")
    if not title:
        errors.append("title must be non-empty")
    if not instructions:
        errors.append("instructions must be non-empty")
    if payload.get("allowed_outputs") != ["draft_result_json"]:
        errors.append("allowed_outputs must be draft_result_json only")
    blocked_actions = payload.get("blocked_actions")
    if not isinstance(blocked_actions, list):
        errors.append("blocked_actions must be a list")
    else:
        for action in REQUIRED_BLOCKED_ACTIONS:
            if action not in blocked_actions:
                errors.append(f"blocked_actions missing: {action}")
    for field in [
        "auto_apply",
        "trusted",
        "write_trusted_memory",
        "execute_commands",
        "mutate_source",
        "mutate_routes",
        "mutate_queue",
        "control_engel",
    ]:
        if payload.get(field) is True:
            errors.append(f"forbidden true field: {field}")
    return errors


def write_packet(packet: dict[str, Any], directory: Path = APPROVED_DIR) -> tuple[Path, str]:
    ensure_scaffold()
    directory.mkdir(parents=True, exist_ok=True)
    errors = validate_assignment_packet(packet)
    if errors:
        raise ValueError("; ".join(errors))
    path = assignment_path_for(str(packet["packet_id"]), directory)
    if path.exists():
        raise FileExistsError("assignment packet already exists: " + str(path))
    text = json.dumps(packet, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")
    return path, sha256_text(text + "\n")


def write_receipt(
    *,
    action: str,
    packet: dict[str, Any],
    packet_path: Path,
    packet_sha256: str,
    source: SourceMaterial | None = None,
    report_dir: Path = REPORT_DIR,
) -> Path:
    ensure_scaffold()
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = utc_stamp()
    packet_id = str(packet.get("packet_id", "unknown"))
    receipt_path = report_dir / f"COMMUNICATION_QUEEN_ASSIGNMENT_{timestamp_file(timestamp)}_{slugify(packet_id, 120)}.md"
    risk_flags = packet.get("risk_flags", [])
    source = source or SourceMaterial(None, None, "", False, 0)
    text = f"""# Engel Communication Router Assignment Receipt

- timestamp: `{timestamp}`
- action: `{action}`
- packet path: `{packet_path}`
- packet SHA-256: `{packet_sha256}`
- packet_id: `{bounded(packet_id, 160)}`
- worker_target: `{bounded(packet.get("worker_target"), 80)}`
- task_type: `{bounded(packet.get("task_type"), 80)}`
- title: `{bounded(packet.get("title"), 160)}`
- source path: `{bounded(source.path, 200)}`
- source SHA-256: `{bounded(source.sha256, 80)}`
- risk flags: `{", ".join(risk_flags) if isinstance(risk_flags, list) and risk_flags else "none"}`
- allowed outputs: `{packet.get("allowed_outputs")}`
- blocked actions: `{packet.get("blocked_actions")}`
- final decision: `{FINAL_DECISION}`

This assignment is not trusted memory.
This assignment does not authorize command execution.
This assignment does not authorize source/route/queue mutation.
This assignment does not authorize auto-apply.
Returned worker output remains untrusted and review-required.
"""
    receipt_path.write_text(text, encoding="utf-8")
    return receipt_path


def create_assignment(
    *,
    worker: str,
    task_type: str,
    title: str,
    instructions: str,
    source_path: str | None = None,
    approved_dir: Path = APPROVED_DIR,
    report_dir: Path = REPORT_DIR,
) -> tuple[dict[str, Any], Path, Path]:
    if worker not in ALLOWED_WORKERS:
        raise ValueError("worker must be one of " + ", ".join(sorted(ALLOWED_WORKERS)))
    if task_type in BLOCKED_TASK_TYPES:
        raise ValueError("blocked task type")
    if task_type not in ALLOWED_TASK_TYPES:
        raise ValueError("task_type is not allowed")
    if task_type not in WORKER_ALLOWED_TASK_TYPES[worker]:
        raise ValueError("task_type " + task_type + " not allowed for " + worker)
    if not title.strip():
        raise ValueError("title is required")
    if not instructions.strip():
        raise ValueError("instructions are required")
    source = read_source_material(source_path)
    packet = build_assignment_packet(
        worker=worker,
        task_type=task_type,
        title=title,
        instructions=instructions,
        source=source,
    )
    packet_path, packet_sha = write_packet(packet, approved_dir)
    receipt_path = write_receipt(
        action="created",
        packet=packet,
        packet_path=packet_path,
        packet_sha256=packet_sha,
        source=source,
        report_dir=report_dir,
    )
    return packet, packet_path, receipt_path


def approved_assignment_files(directory: Path = APPROVED_DIR) -> list[Path]:
    ensure_scaffold()
    if not directory.exists():
        return []
    files = [path for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()) if path.is_file()]
    return [path for path in files if path.suffix.lower() == ".json"][:MAX_ASSIGNMENT_FILES]


def load_json(path: Path) -> Any:
    try:
        if not path.is_file() or path.stat().st_size > MAX_TEXT_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def status_payload() -> dict[str, Any]:
    ensure_scaffold()
    receipts = sorted(REPORT_DIR.glob("COMMUNICATION_QUEEN_ASSIGNMENT_*.md"))
    return {
        "producer": PRODUCER_NAME,
        "approved_count": len(approved_assignment_files(APPROVED_DIR)),
        "claimed_count": len(list(CLAIMED_DIR.glob("*.json"))),
        "returned_count": len(list(RETURNED_DIR.glob("*.json"))),
        "invalid_count": len(list(INVALID_DIR.glob("*.json"))),
        "retired_count": len(list(RETIRED_DIR.glob("*.json"))),
        "allowed_task_types": sorted(ALLOWED_TASK_TYPES),
        "assignment_root": str(ASSIGNMENT_ROOT),
        "approved_dir": str(APPROVED_DIR),
        "report_dir": str(REPORT_DIR),
        "latest_receipt": str(receipts[-1]) if receipts else None,
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
    }


def list_assignments(directory: Path = APPROVED_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in approved_assignment_files(directory):
        payload = load_json(path)
        if not isinstance(payload, dict):
            rows.append({"path": str(path), "valid": False, "errors": ["invalid JSON object"]})
            continue
        errors = validate_assignment_packet(payload)
        rows.append(
            {
                "path": str(path),
                "valid": not errors,
                "packet_id": payload.get("packet_id"),
                "task_type": payload.get("task_type"),
                "worker_target": payload.get("worker_target"),
                "title": payload.get("title"),
                "created_at": payload.get("created_at"),
                "safe_to_auto_apply": payload.get("safe_to_auto_apply"),
                "requires_review": payload.get("requires_review"),
                "errors": errors[:5],
            }
        )
    return rows


def validate_file(path_text: str) -> tuple[bool, list[str], dict[str, Any] | None]:
    path = Path(path_text)
    payload = load_json(path)
    errors = validate_assignment_packet(payload)
    return not errors, errors, payload if isinstance(payload, dict) else None


def find_approved_packet(packet_id: str, directory: Path = APPROVED_DIR) -> Path | None:
    target = slugify(packet_id, 180)
    for path in approved_assignment_files(directory):
        if path.stem == target:
            return path
        payload = load_json(path)
        if isinstance(payload, dict) and payload.get("packet_id") == packet_id:
            return path
    return None


def retire_assignment(
    packet_id: str,
    *,
    approved_dir: Path = APPROVED_DIR,
    retired_dir: Path = RETIRED_DIR,
    report_dir: Path = REPORT_DIR,
) -> tuple[Path, Path]:
    ensure_scaffold()
    path = find_approved_packet(packet_id, approved_dir)
    if path is None:
        raise FileNotFoundError("approved assignment not found")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("approved assignment is not valid JSON")
    retired_dir.mkdir(parents=True, exist_ok=True)
    target = retired_dir / path.name
    if target.exists():
        raise FileExistsError("retired assignment already exists")
    shutil.move(str(path), str(target))
    packet_sha = sha256_file(target)
    receipt_path = write_receipt(
        action="retired",
        packet=payload,
        packet_path=target,
        packet_sha256=packet_sha,
        report_dir=report_dir,
    )
    return target, receipt_path


def render_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create Engel Communication Router approved Remote Worker assignments.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    validate = sub.add_parser("validate")
    validate.add_argument("path")
    create = sub.add_parser("create")
    create.add_argument("--worker", default=EXPECTED_WORKER)
    create.add_argument("--task-type", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--instructions")
    create.add_argument("--instructions-file")
    create.add_argument("--source-file")
    retire = sub.add_parser("retire")
    retire.add_argument("packet_id")
    receipt = sub.add_parser("receipt")
    receipt.add_argument("packet_id")
    args = parser.parse_args(argv)

    if args.command == "status":
        print(render_json(status_payload()))
        return 0
    if args.command == "list":
        print(render_json(list_assignments()))
        return 0
    if args.command == "validate":
        valid, errors, payload = validate_file(args.path)
        print(render_json({"valid": valid, "errors": errors, "packet_id": payload.get("packet_id") if payload else None}))
        return 0 if valid else 1
    if args.command == "create":
        instructions = args.instructions or ""
        source_path = args.source_file
        if args.instructions_file:
            source = read_source_material(args.instructions_file)
            instructions = source.preview
            source_path = args.source_file or args.instructions_file
        packet, packet_path, receipt_path = create_assignment(
            worker=args.worker,
            task_type=args.task_type,
            title=args.title,
            instructions=instructions,
            source_path=source_path,
        )
        print(render_json({"created": True, "packet_id": packet["packet_id"], "packet_path": str(packet_path), "receipt_path": str(receipt_path)}))
        return 0
    if args.command == "retire":
        retired_path, receipt_path = retire_assignment(args.packet_id)
        print(render_json({"retired": True, "retired_path": str(retired_path), "receipt_path": str(receipt_path)}))
        return 0
    if args.command == "receipt":
        path = find_approved_packet(args.packet_id)
        if path is None:
            print(render_json({"found": False, "error": "approved assignment not found"}))
            return 1
        payload = load_json(path)
        if not isinstance(payload, dict):
            print(render_json({"found": False, "error": "invalid assignment JSON"}))
            return 1
        receipt_path = write_receipt(
            action="validated",
            packet=payload,
            packet_path=path,
            packet_sha256=sha256_file(path),
        )
        print(render_json({"found": True, "receipt_path": str(receipt_path)}))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
