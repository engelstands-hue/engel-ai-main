#!/usr/bin/env python3
"""Validate CT246 paths against explicit runtime and archive roles.

This is the first boundary in Engel's self-upgrade loop. It prevents generated
work from treating Windows drives or any undeclared location as an active
CT246 path. Checks are non-destructive. Quarantine is limited to a path below
the configured CT runtime root and requires the exact owner token.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import threading
from typing import Any, Iterable


ROOT = Path(os.environ.get("ENGEL_APP_ROOT") or Path(__file__).resolve().parents[1]).resolve()
STATE_ROOT = Path(os.environ.get("ENGEL_PATH_QUARANTINE_ROOT") or ROOT / "run" / "self_update" / "path_quarantine")
EVENTS_PATH = STATE_ROOT / "blocked_path_events.jsonl"
RECEIPT_DIR = STATE_ROOT / "receipts"
ITEM_DIR = STATE_ROOT / "items"
QUARANTINE_TOKEN = "APPROVE_ENGEL_PATH_QUARANTINE_V1"
MAX_SCAN_ENTRIES = 100_000
PRUNED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "archive",
    "artifacts",
    "backups",
    "cache",
    "cargo-home",
    "datasets",
    "downloads",
    "external-drive-capture",
    "llama.cpp",
    "logs",
    "memory",
    "models-active",
    "node_modules",
    "reports",
    "site-packages",
    "snapshots",
    "target",
    "training-outputs",
    "venv",
    "virtual-environments",
}

ACTIVE_ROOT = "/opt/engel"
ARCHIVE_ROOT = "/mnt/engel-hdd-vault"
PURPOSE_ROOTS = {
    "active_runtime": (ACTIVE_ROOT,),
    "source": (ACTIVE_ROOT,),
    "evidence": (ACTIVE_ROOT,),
    "archive": (ARCHIVE_ROOT,),
}
INVALID_RUNTIME_MARKERS = {"unapproved-storage-alias"}
WINDOWS_EXTERNAL_DRIVES = {"e", "f", "g"}
_APPEND_LOCK = threading.Lock()


class PathBoundaryError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _normalize(raw_path: str) -> str:
    value = str(raw_path or "").strip().replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")
    return value


def _segments(normalized: str) -> list[str]:
    return [part for part in normalized.casefold().split("/") if part not in {"", "."}]


def _windows_external_drive(segments: Iterable[str]) -> str:
    for segment in segments:
        if len(segment) == 2 and segment[1] == ":" and segment[0] in WINDOWS_EXTERNAL_DRIVES:
            return segment.upper()
    return ""


def _within_root(normalized: str, root: str) -> bool:
    lowered = normalized.casefold()
    allowed = root.casefold()
    return lowered == allowed or lowered.startswith(allowed + "/")


def check_path(raw_path: str, *, purpose: str = "active_runtime") -> dict[str, Any]:
    normalized = _normalize(raw_path)
    lowered = normalized.casefold()
    segments = _segments(normalized)
    reasons: list[str] = []

    if not normalized:
        reasons.append("path is empty")

    drive = _windows_external_drive(segments)
    if drive:
        reasons.append(f"Windows external drive {drive} is not a CT246 runtime path")

    invalid_markers = sorted(INVALID_RUNTIME_MARKERS.intersection(segments))
    if invalid_markers:
        reasons.append("unapproved storage alias marker: " + ", ".join(invalid_markers))

    if purpose == "active_runtime" and _within_root(normalized, ARCHIVE_ROOT):
        reasons.append("Dell HDD vault is archive-only and cannot host active runtime work")

    allowed_roots = PURPOSE_ROOTS.get(purpose)
    if allowed_roots is None:
        reasons.append(f"unknown path purpose: {purpose}")
    elif normalized and not any(_within_root(normalized, root) for root in allowed_roots):
        reasons.append(
            f"{purpose} path is outside approved roots: " + ", ".join(allowed_roots)
        )

    return {
        "schema": "ENGEL_RUNTIME_PATH_CHECK_V1",
        "ok": not reasons,
        "allowed": not reasons,
        "raw_path": str(raw_path or ""),
        "normalized_path": normalized,
        "purpose": purpose,
        "reasons": reasons,
        "active_runtime_root": ACTIVE_ROOT,
        "archive_root": ARCHIVE_ROOT,
        "source_of_truth": "CT246 /opt/engel",
        "checked_at_utc": now_utc(),
    }


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with _APPEND_LOCK:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            if os.name != "nt":
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                if os.name != "nt":
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def record_blocked_path(
    check: dict[str, Any],
    *,
    source: str,
    events_path: Path = EVENTS_PATH,
) -> dict[str, Any]:
    if check.get("allowed") is True:
        raise PathBoundaryError("allowed paths do not create blocked-path events")
    created = now_utc()
    event = {
        "schema": "ENGEL_SELF_UPDATE_PATH_BLOCKED_EVENT_V1",
        "event_id": "path_blocked_" + hashlib.sha256(
            f"{check.get('normalized_path')}|{check.get('purpose')}|{created}".encode("utf-8")
        ).hexdigest()[:16],
        "event_type": "runtime.path.blocked",
        "created_at_utc": created,
        "source": source,
        "path_check": check,
        "issue_required": True,
        "candidate_only": True,
        "source_mutation": False,
        "trusted_memory_write": False,
    }
    _append_jsonl(events_path, event)
    return event


def scan_runtime_tree(
    scan_root: Path,
    *,
    state_root: Path = STATE_ROOT,
    max_entries: int = MAX_SCAN_ENTRIES,
    record_events: bool = True,
) -> dict[str, Any]:
    root = scan_root.resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise PathBoundaryError(f"scan root is not a directory: {root}")
    blocked: list[dict[str, Any]] = []
    pruned: list[str] = []
    scanned = 0
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        entries = [Path(current) / name for name in dirnames + filenames]
        for entry in entries:
            scanned += 1
            if scanned > max_entries:
                break
            rel = entry.relative_to(root).as_posix()
            synthetic_ct_path = str(PurePosixPath(ACTIVE_ROOT) / rel)
            check = check_path(synthetic_ct_path, purpose="active_runtime")
            if check["allowed"] and entry.is_symlink():
                target = _normalize(str(entry.resolve(strict=False)))
                check = check_path(target, purpose="active_runtime")
                if not check["allowed"]:
                    check["raw_path"] = str(entry)
                    check["normalized_path"] = _normalize(str(entry))
                    check["symlink_target"] = target
            if not check["allowed"]:
                item = {"local_path": str(entry), "relative_path": rel, "check": check}
                if record_events:
                    item["event"] = record_blocked_path(
                        check,
                        source="runtime_path_scan",
                        events_path=state_root / "blocked_path_events.jsonl",
                    )
                blocked.append(item)
        kept_dirnames: list[str] = []
        for name in dirnames:
            if name.casefold() in PRUNED_DIRECTORY_NAMES:
                pruned.append((Path(current) / name).relative_to(root).as_posix())
            else:
                kept_dirnames.append(name)
        dirnames[:] = kept_dirnames
        if scanned > max_entries:
            break
    return {
        "schema": "ENGEL_RUNTIME_PATH_SCAN_V1",
        "ok": not blocked,
        "status": "clean" if not blocked else "blocked paths found",
        "scan_root": str(root),
        "entries_scanned": min(scanned, max_entries),
        "scan_truncated": scanned > max_entries,
        "blocked_count": len(blocked),
        "blocked": blocked,
        "pruned_directory_count": len(pruned),
        "pruned_directories": pruned[:200],
        "destructive_action": False,
        "scanned_at_utc": now_utc(),
    }


def quarantine_path(
    target: Path,
    *,
    approval_token: str,
    runtime_root: Path = ROOT,
    state_root: Path = STATE_ROOT,
) -> dict[str, Any]:
    if approval_token != QUARANTINE_TOKEN:
        raise PathBoundaryError("exact quarantine approval token required")
    runtime = runtime_root.resolve(strict=False)
    resolved = target.resolve(strict=False)
    try:
        rel = resolved.relative_to(runtime)
    except ValueError as exc:
        raise PathBoundaryError("quarantine target must stay below the CT246 runtime root") from exc
    if rel == Path(".") or resolved == runtime:
        raise PathBoundaryError("runtime root cannot be quarantined")
    if not resolved.exists():
        raise PathBoundaryError("quarantine target does not exist")
    quarantine_root = state_root.resolve(strict=False)
    try:
        resolved.relative_to(quarantine_root)
    except ValueError:
        pass
    else:
        raise PathBoundaryError("target is already inside the quarantine root")

    synthetic_path = str(PurePosixPath(ACTIVE_ROOT) / rel.as_posix())
    check = check_path(synthetic_path, purpose="active_runtime")
    if check["allowed"]:
        raise PathBoundaryError("only a path that fails the CT246 boundary may be quarantined")

    destination = state_root / "items" / f"{_stamp()}__{resolved.name}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(resolved), str(destination))
    receipt = {
        "schema": "ENGEL_RUNTIME_PATH_QUARANTINE_RECEIPT_V1",
        "ok": True,
        "status": "quarantined",
        "source_path": str(resolved),
        "destination_path": str(destination),
        "path_check": check,
        "approval_token_accepted": True,
        "deleted": False,
        "created_at_utc": now_utc(),
    }
    receipt_path = state_root / "receipts" / f"PATH_QUARANTINE_{_stamp()}.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _print(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel CT246 runtime path normalizer and quarantine guard.")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    check = sub.add_parser("check")
    check.add_argument("--path", required=True)
    check.add_argument("--purpose", default="active_runtime")
    check.add_argument("--source", default="manual_check")
    scan = sub.add_parser("scan")
    scan.add_argument("--root", default=str(ROOT))
    scan.add_argument("--max-entries", type=int, default=MAX_SCAN_ENTRIES)
    quarantine = sub.add_parser("quarantine")
    quarantine.add_argument("--path", required=True)
    quarantine.add_argument("--approval-token", default="")
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            return _print(
                {
                    "schema": "ENGEL_RUNTIME_PATH_BOUNDARY_STATUS_V1",
                    "ok": True,
                    "status": "ready",
                    "goal": "Conical Agentic Sentient Self Upgrading System",
                    "source_of_truth": "CT246 /opt/engel",
                    "active_runtime_root": ACTIVE_ROOT,
                    "archive_root": ARCHIVE_ROOT,
                    "purpose_roots": PURPOSE_ROOTS,
                    "quarantine_root": str(STATE_ROOT),
                    "quarantine_requires_token": True,
                    "destructive_default": False,
                }
            )
        if args.command == "check":
            result = check_path(args.path, purpose=args.purpose)
            if not result["allowed"]:
                result["blocked_event"] = record_blocked_path(result, source=args.source)
            return _print(result)
        if args.command == "scan":
            return _print(
                scan_runtime_tree(
                    Path(args.root),
                    max_entries=max(1, min(args.max_entries, MAX_SCAN_ENTRIES)),
                )
            )
        if args.command == "quarantine":
            return _print(
                quarantine_path(Path(args.path), approval_token=args.approval_token)
            )
    except (OSError, PathBoundaryError) as exc:
        return _print(
            {
                "schema": "ENGEL_RUNTIME_PATH_BOUNDARY_ERROR_V1",
                "ok": False,
                "status": "blocked",
                "error": str(exc),
            }
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
