#!/usr/bin/env python3
"""Hash-prove ROG source and CT246 runtime before and after deployment.

This tool never copies or edits source files. It creates explicit manifests,
blocks stale preflights, and verifies post-deploy byte equality. A separate
deployment lane may copy only after a successful preflight receipt.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("ENGEL_APP_ROOT") or Path(__file__).resolve().parents[1]).resolve()
STATE_ROOT = Path(os.environ.get("ENGEL_SOURCE_SYNC_ROOT") or ROOT / "run" / "self_update" / "source_sync")
MAX_FILES = 200
MAX_FILE_BYTES = 16 * 1024 * 1024
ALLOWED_PREFIXES = (
    "tools/",
    "memory/",
    "reports/self_upgrade/",
    "scripts/",
    "engel_main/",
    "engel_flutter_main/",
    "mobile/engel_remote_worker/",
)
ALLOWED_ROOT_FILES = {
    "engel_agent_meeting_room.py",
    "engel_self_upgrade_system.py",
    "engel_sub_node_remote_control.py",
    "engel_windows_sub_node_agent.py",
}
PROTECTED_MARKERS = (
    "/.git/",
    "/.venv/",
    "/cache/",
    "/logs/",
    "/models-active/",
    "/node_modules/",
    "/runtime/",
    "credential",
    "password",
    "provider_key",
    "secret",
    "token",
    ".env",
)


class SourceSyncError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_relative(raw: str) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    if not value or value.startswith("/") or ":" in value:
        raise SourceSyncError("path must be relative to the declared Engel root")
    parts = [part for part in value.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise SourceSyncError("path traversal is forbidden")
    canonical = "/".join(parts)
    lowered = "/" + canonical.casefold() + "/"
    if any(marker in lowered for marker in PROTECTED_MARKERS):
        raise SourceSyncError(f"protected source path refused: {canonical}")
    if canonical not in ALLOWED_ROOT_FILES and not canonical.startswith(ALLOWED_PREFIXES):
        raise SourceSyncError(f"path is outside approved source roots: {canonical}")
    return canonical


def _entry(root: Path, relative: str) -> dict[str, Any]:
    canonical = canonical_relative(relative)
    path = (root / canonical).resolve(strict=False)
    try:
        path.relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise SourceSyncError("resolved path escaped declared root") from exc
    exists = path.is_file()
    entry: dict[str, Any] = {
        "relative_path": canonical,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "sha256": sha256_file(path) if exists else "",
    }
    if exists and entry["size_bytes"] > MAX_FILE_BYTES:
        raise SourceSyncError(f"file exceeds sync proof size limit: {canonical}")
    return entry


def build_manifest(root: Path, paths: list[str], *, role: str) -> dict[str, Any]:
    if role not in {"rog_source", "ct_target_preflight"}:
        raise SourceSyncError("manifest role must be rog_source or ct_target_preflight")
    unique = sorted({canonical_relative(path) for path in paths})
    if not unique:
        raise SourceSyncError("at least one explicit path is required")
    if len(unique) > MAX_FILES:
        raise SourceSyncError(f"manifest exceeds {MAX_FILES} files")
    resolved_root = root.resolve(strict=False)
    if not resolved_root.is_dir():
        raise SourceSyncError(f"declared root is not a directory: {resolved_root}")
    entries = [_entry(resolved_root, path) for path in unique]
    payload = {
        "schema": "ENGEL_SOURCE_SYNC_MANIFEST_V1",
        "ok": True,
        "role": role,
        "root": str(resolved_root),
        "goal": "Conical Agentic Sentient Self Upgrading System",
        "source_of_truth": "CT246 /opt/engel",
        "file_count": len(entries),
        "all_present": all(entry["exists"] for entry in entries),
        "files": entries,
        "mutation_performed": False,
        "created_at_utc": now_utc(),
    }
    payload["manifest_id"] = "sync_manifest_" + hashlib.sha256(
        json.dumps(entries, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def read_manifest(path: Path, expected_role: str | None = None) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceSyncError(f"could not read manifest: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != "ENGEL_SOURCE_SYNC_MANIFEST_V1":
        raise SourceSyncError("source-sync manifest schema mismatch")
    if expected_role and payload.get("role") != expected_role:
        raise SourceSyncError(f"expected {expected_role} manifest")
    for entry in payload.get("files", []):
        canonical_relative(str(entry.get("relative_path") or ""))
    return payload


def _by_path(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(entry["relative_path"]): entry for entry in manifest.get("files", [])}


def build_preflight(
    source: dict[str, Any],
    expected_target: dict[str, Any],
    target_root: Path,
) -> dict[str, Any]:
    if source.get("role") != "rog_source":
        raise SourceSyncError("source manifest role mismatch")
    if expected_target.get("role") != "ct_target_preflight":
        raise SourceSyncError("expected-target manifest role mismatch")
    source_files = _by_path(source)
    expected_files = _by_path(expected_target)
    if set(source_files) != set(expected_files):
        raise SourceSyncError("source and target manifests must cover identical paths")
    current = build_manifest(target_root, sorted(source_files), role="ct_target_preflight")
    current_files = _by_path(current)
    results: list[dict[str, Any]] = []
    blocked = False
    for relative in sorted(source_files):
        src = source_files[relative]
        expected = expected_files[relative]
        actual = current_files[relative]
        changed_since_snapshot = (
            bool(expected.get("exists")) != bool(actual.get("exists"))
            or str(expected.get("sha256") or "") != str(actual.get("sha256") or "")
        )
        if changed_since_snapshot:
            state = "target_drift"
            blocked = True
        elif not src.get("exists"):
            state = "source_missing"
            blocked = True
        elif not actual.get("exists"):
            state = "new_file"
        elif src.get("sha256") == actual.get("sha256"):
            state = "already_synced"
        else:
            state = "update_candidate"
        results.append(
            {
                "relative_path": relative,
                "state": state,
                "source_sha256": src.get("sha256", ""),
                "target_expected_sha256": expected.get("sha256", ""),
                "target_current_sha256": actual.get("sha256", ""),
                "target_changed_since_snapshot": changed_since_snapshot,
            }
        )
    return {
        "schema": "ENGEL_SOURCE_SYNC_PREFLIGHT_V1",
        "ok": not blocked,
        "status": "sync preflight ready" if not blocked else "sync preflight blocked",
        "source_manifest_id": source.get("manifest_id"),
        "target_manifest_id": expected_target.get("manifest_id"),
        "target_root": str(target_root.resolve(strict=False)),
        "file_count": len(results),
        "sync_allowed": not blocked,
        "files": results,
        "mutation_performed": False,
        "created_at_utc": now_utc(),
    }


def verify_post_deploy(
    source: dict[str, Any],
    preflight: dict[str, Any],
    target_root: Path,
) -> dict[str, Any]:
    if preflight.get("schema") != "ENGEL_SOURCE_SYNC_PREFLIGHT_V1" or preflight.get("sync_allowed") is not True:
        raise SourceSyncError("successful preflight receipt required")
    if preflight.get("source_manifest_id") != source.get("manifest_id"):
        raise SourceSyncError("preflight source manifest mismatch")
    source_files = _by_path(source)
    current = build_manifest(target_root, sorted(source_files), role="ct_target_preflight")
    current_files = _by_path(current)
    results: list[dict[str, Any]] = []
    for relative in sorted(source_files):
        src = source_files[relative]
        target = current_files[relative]
        match = bool(src.get("exists")) and bool(target.get("exists")) and src.get("sha256") == target.get("sha256")
        results.append(
            {
                "relative_path": relative,
                "match": match,
                "source_sha256": src.get("sha256", ""),
                "target_sha256": target.get("sha256", ""),
            }
        )
    ok = all(item["match"] for item in results)
    return {
        "schema": "ENGEL_SOURCE_SYNC_POST_DEPLOY_PROOF_V1",
        "ok": ok,
        "status": "source and CT target match" if ok else "post-deploy hash mismatch",
        "source_manifest_id": source.get("manifest_id"),
        "preflight_created_at_utc": preflight.get("created_at_utc"),
        "target_root": str(target_root.resolve(strict=False)),
        "file_count": len(results),
        "matched_count": sum(1 for item in results if item["match"]),
        "files": results,
        "mutation_performed": False,
        "verified_at_utc": now_utc(),
    }


def _default_path(kind: str) -> Path:
    return STATE_ROOT / kind / f"{kind.upper()}_{stamp()}.json"


def _emit(payload: dict[str, Any], path: Path | None = None) -> int:
    if path is not None:
        write_json(path, payload)
        payload = {**payload, "receipt_path": str(path)}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel ROG-to-CT source-sync Rosetta proof tool.")
    sub = parser.add_subparsers(dest="command", required=True)
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--root", required=True)
    snapshot.add_argument("--role", required=True, choices=["rog_source", "ct_target_preflight"])
    snapshot.add_argument("--path", action="append", required=True)
    snapshot.add_argument("--output")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--source-manifest", required=True)
    preflight.add_argument("--expected-target-manifest", required=True)
    preflight.add_argument("--target-root", required=True)
    preflight.add_argument("--output")
    post = sub.add_parser("verify-post")
    post.add_argument("--source-manifest", required=True)
    post.add_argument("--preflight", required=True)
    post.add_argument("--target-root", required=True)
    post.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot":
            payload = build_manifest(Path(args.root), args.path, role=args.role)
            output = Path(args.output) if args.output else _default_path("manifests")
            return _emit(payload, output)
        if args.command == "preflight":
            source = read_manifest(Path(args.source_manifest), "rog_source")
            expected = read_manifest(Path(args.expected_target_manifest), "ct_target_preflight")
            payload = build_preflight(source, expected, Path(args.target_root))
            output = Path(args.output) if args.output else _default_path("preflight")
            return _emit(payload, output)
        if args.command == "verify-post":
            source = read_manifest(Path(args.source_manifest), "rog_source")
            preflight_payload = json.loads(Path(args.preflight).read_text(encoding="utf-8-sig"))
            payload = verify_post_deploy(source, preflight_payload, Path(args.target_root))
            output = Path(args.output) if args.output else _default_path("post_deploy")
            return _emit(payload, output)
    except (OSError, json.JSONDecodeError, SourceSyncError) as exc:
        return _emit({"schema": "ENGEL_SOURCE_SYNC_ERROR_V1", "ok": False, "status": "blocked", "error": str(exc)})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
