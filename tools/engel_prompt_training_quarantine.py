#!/usr/bin/env python3
"""Append-only row quarantine sidecars for immutable prompt-training packs.

A stamped JSONL pack is evidence.  Its raw bytes must never change after the
publisher hashes and marks it read-only.  Later policy reviews therefore retire a
row with an immutable sidecar that binds the pack SHA-256, exact line number, and
exact row SHA-256.  Consumers fail closed when a sidecar is malformed or no longer
matches the pack bytes it names.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUARANTINE_DIR = ROOT / "memory" / "training" / "prompt_row_quarantines"
SCHEMA = "engel_prompt_training_row_quarantine_v1"
PREFIX = "ENGEL_PROMPT_ROW_QUARANTINE_"
SUFFIX = ".json"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SAFE_PACK_NAME = re.compile(
    r"^ENGEL_PROMPT_TRAINING_PACK_[A-Za-z0-9][A-Za-z0-9_.-]*\.jsonl$"
)


def _immutable_file_problem(path: Path, label: str) -> str:
    if path.is_symlink():
        return f"{label} must be a regular non-symlink file: {path}"
    try:
        info = os.lstat(path)
    except OSError as exc:
        return f"{label} is unavailable: {path}: {exc}"
    if not stat.S_ISREG(info.st_mode):
        return f"{label} must be a regular file: {path}"
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if reparse and (getattr(info, "st_file_attributes", 0) & reparse):
        return f"{label} must not be a reparse point: {path}"
    if info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        return f"{label} is mutable: {path.name}"
    return ""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_immutable_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary = path.parent / f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    linked = False
    try:
        with temporary.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        linked = True
        temporary.unlink()
        os.chmod(path, 0o444)
    except Exception:
        if linked and path.exists():
            try:
                os.chmod(path, 0o600)
                path.unlink()
            except OSError:
                pass
        raise
    finally:
        if temporary.exists():
            try:
                os.chmod(temporary, 0o600)
                temporary.unlink()
            except OSError:
                pass


def write_sidecar(
    *,
    pack_path: Path,
    entries: list[dict[str, Any]],
    source_gate: str,
    quarantine_dir: Path | None = None,
) -> Path:
    """Write one no-overwrite sidecar; never open the source pack for writing."""

    pack_path = Path(pack_path)
    pack_bytes = pack_path.read_bytes()
    return write_sidecar_for_bytes(
        pack_name=pack_path.name,
        pack_bytes=pack_bytes,
        entries=entries,
        source_gate=source_gate,
        quarantine_dir=quarantine_dir,
    )


def write_sidecar_for_bytes(
    *,
    pack_name: str,
    pack_bytes: bytes,
    entries: list[dict[str, Any]],
    source_gate: str,
    quarantine_dir: Path | None = None,
) -> Path:
    """Bind a no-overwrite sidecar to exact prospective immutable pack bytes.

    Migration and recovery tools sometimes must publish the exclusion receipt before
    atomically restoring the bytes it names. Accepting bytes directly preserves that
    fail-closed ordering: until the named pack has those exact bytes, load_pack
    reports a binding blocker instead of applying the exclusions to another version.
    """

    pack_name = str(pack_name)
    if not _SAFE_PACK_NAME.fullmatch(pack_name):
        raise ValueError(f"unsupported prompt-training pack name: {pack_name}")
    if not isinstance(pack_bytes, bytes):
        raise TypeError("pack_bytes must be exact bytes")
    pack_sha256 = _sha256(pack_bytes)
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        line_number = int(entry.get("line_number") or entry.get("lineno") or 0)
        row_sha256 = str(entry.get("row_sha256") or "").strip().casefold()
        if line_number < 1 or not _SHA256.fullmatch(row_sha256):
            raise ValueError("quarantine entry requires a line number and row_sha256")
        normalized.append(
            {
                "line_number": line_number,
                "row_sha256": row_sha256,
                "prompt_index": entry.get("prompt_index"),
                "scheduled_hour": entry.get("scheduled_hour"),
                "run_id": str(entry.get("run_id") or ""),
                "reason": str(entry.get("reason") or "current policy refused the row"),
            }
        )
    if not normalized:
        raise ValueError("refusing an empty quarantine sidecar")
    payload = {
        "schema": SCHEMA,
        "created_at_utc": _utc_now(),
        "source_gate": str(source_gate or "unspecified"),
        "effect": "exclude matching rows from every downstream training lane",
        "pack": {
            "name": pack_name,
            "bytes": len(pack_bytes),
            "sha256": pack_sha256,
        },
        "entries": sorted(normalized, key=lambda item: item["line_number"]),
    }
    target_dir = Path(quarantine_dir or DEFAULT_QUARANTINE_DIR)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = f"{PREFIX}{stamp}_p{os.getpid()}_{pack_sha256[:12]}{SUFFIX}"
    path = target_dir / name
    _atomic_immutable_json(path, payload)
    return path


def _load_sidecars(
    quarantine_dir: Path,
) -> tuple[list[tuple[Path, dict[str, Any], str]], list[str]]:
    loaded: list[tuple[Path, dict[str, Any], str]] = []
    blockers: list[str] = []
    if not quarantine_dir.exists():
        return loaded, blockers
    if not quarantine_dir.is_dir():
        return loaded, [f"quarantine path is not a directory: {quarantine_dir}"]
    for path in sorted(quarantine_dir.glob(f"{PREFIX}*{SUFFIX}")):
        immutable_problem = _immutable_file_problem(path, "quarantine sidecar")
        if immutable_problem:
            blockers.append(immutable_problem)
            continue
        try:
            raw_bytes = path.read_bytes()
            payload = json.loads(raw_bytes.decode("utf-8-sig"))
        except Exception as exc:
            blockers.append(
                f"invalid quarantine sidecar {path.name}: {type(exc).__name__}: {exc}"
            )
            continue
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
            blockers.append(f"invalid quarantine sidecar schema: {path.name}")
            continue
        pack = payload.get("pack")
        entries = payload.get("entries")
        name = str((pack or {}).get("name") or "")
        digest = str((pack or {}).get("sha256") or "").casefold()
        if (
            not isinstance(pack, dict)
            or not _SAFE_PACK_NAME.fullmatch(name)
            or not _SHA256.fullmatch(digest)
            or not isinstance(pack.get("bytes"), int)
            or int(pack["bytes"]) < 0
            or not isinstance(entries, list)
            or not entries
        ):
            blockers.append(f"malformed quarantine binding: {path.name}")
            continue
        loaded.append((path, payload, _sha256(raw_bytes)))
    return loaded, blockers


def load_pack(
    pack_path: Path, quarantine_dir: Path | None = None
) -> dict[str, Any]:
    """Parse a pack and apply only exact, hash-bound sidecar exclusions."""

    pack_path = Path(pack_path)
    immutable_problem = _immutable_file_problem(pack_path, "stamped training pack")
    if immutable_problem:
        return {
            "schema": "engel_prompt_training_pack_with_quarantine_v1",
            "path": str(pack_path),
            "pack_sha256": "",
            "pack_bytes": 0,
            "rows": [],
            "quarantined": 0,
            "receipt_paths": [],
            "receipt_sha256": {},
            "blockers": [immutable_problem],
            "ok": False,
        }
    raw_bytes = pack_path.read_bytes()
    pack_sha256 = _sha256(raw_bytes)
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    parsed_rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        row: Any = None
        if stripped:
            try:
                row = json.loads(stripped)
            except ValueError:
                row = None
        parsed_rows.append(
            {
                "line_number": line_number,
                "raw_line": stripped,
                "row_sha256": _sha256(stripped.encode("utf-8")),
                "row": row,
                "quarantined": False,
                "quarantine_reasons": [],
            }
        )

    loaded, blockers = _load_sidecars(
        Path(quarantine_dir or DEFAULT_QUARANTINE_DIR)
    )
    receipt_paths: list[str] = []
    receipt_sha256: dict[str, str] = {}
    entries: dict[int, list[dict[str, Any]]] = {}
    for sidecar_path, payload, sidecar_sha256 in loaded:
        binding = payload["pack"]
        if binding["name"] != pack_path.name:
            continue
        receipt_paths.append(str(sidecar_path))
        receipt_sha256[str(sidecar_path)] = sidecar_sha256
        if str(binding["sha256"]).casefold() != pack_sha256:
            blockers.append(
                f"pack bytes changed after quarantine sidecar {sidecar_path.name}: "
                f"{pack_path.name}"
            )
            continue
        if int(binding.get("bytes") or -1) != len(raw_bytes):
            blockers.append(
                f"pack byte count changed after quarantine sidecar {sidecar_path.name}: "
                f"{pack_path.name}"
            )
            continue
        for entry in payload["entries"]:
            if not isinstance(entry, dict):
                blockers.append(f"non-object quarantine entry in {sidecar_path.name}")
                continue
            try:
                line_number = int(entry.get("line_number") or 0)
            except (TypeError, ValueError):
                line_number = 0
            row_sha256 = str(entry.get("row_sha256") or "").casefold()
            if line_number < 1 or not _SHA256.fullmatch(row_sha256):
                blockers.append(f"malformed quarantine entry in {sidecar_path.name}")
                continue
            entries.setdefault(line_number, []).append(entry)

    for line_number, bound in entries.items():
        if line_number > len(parsed_rows):
            blockers.append(
                f"quarantine entry names absent line {line_number} in {pack_path.name}"
            )
            continue
        parsed = parsed_rows[line_number - 1]
        for entry in bound:
            if parsed["row_sha256"] != str(entry["row_sha256"]).casefold():
                blockers.append(
                    f"quarantine row hash mismatch at {pack_path.name}:{line_number}"
                )
                continue
            parsed["quarantined"] = True
            parsed["quarantine_reasons"].append(str(entry.get("reason") or ""))

    return {
        "schema": "engel_prompt_training_pack_with_quarantine_v1",
        "path": str(pack_path),
        "pack_sha256": pack_sha256,
        "pack_bytes": len(raw_bytes),
        "rows": parsed_rows,
        "quarantined": sum(1 for item in parsed_rows if item["quarantined"]),
        "receipt_paths": sorted(set(receipt_paths)),
        "receipt_sha256": {
            path: receipt_sha256[path] for path in sorted(receipt_sha256)
        },
        "blockers": blockers,
        "ok": not blockers,
    }
