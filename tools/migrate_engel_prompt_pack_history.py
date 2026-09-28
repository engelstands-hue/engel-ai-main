#!/usr/bin/env python3
"""Recover prompt packs that old quarantine tools rewrote in place.

Dry-run is the default. Retained pre-mutation backups are the only possible original
evidence. The migration refuses promotions and unrelated content changes, publishes
exclusions for the prospective bytes first, preserves current bytes as immutable
forensic evidence, and only then restores the canonical immutable JSONL pack.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKS_DIR = ROOT / "memory" / "training" / "packs"
DEFAULT_QUARANTINE_DIR = ROOT / "memory" / "training" / "prompt_row_quarantines"
DEFAULT_SNAPSHOT_DIR = ROOT / "memory" / "training" / "prompt_pack_history_forensics"
DEFAULT_RECEIPT_DIR = (
    ROOT / "reports" / "real_training" / "prompt_pack_history_migration"
)
SCHEMA = "engel_prompt_pack_history_migration_v1"
SOURCE_GATE = "engel_prompt_pack_history_migration_v1"

sys.path.insert(0, str(ROOT / "tools"))
import engel_prompt_training_quarantine as quarantine  # noqa: E402


PACK_NAME = re.compile(
    r"^ENGEL_PROMPT_TRAINING_PACK_[A-Za-z0-9][A-Za-z0-9_.-]*[.]jsonl$"
)
BACKUP_NAME = re.compile(
    r"^(?P<base>ENGEL_PROMPT_TRAINING_PACK_[A-Za-z0-9][A-Za-z0-9_.-]*[.]jsonl)[.]"
    r"(?P<tag>pre_fabricated_citation_quarantine_bak|"
    r"pre_offcard_quarantine_bak|pre_regrade_[A-Za-z0-9_.-]+[.]bak)$"
)
SHA256 = re.compile(r"^[a-f0-9]{64}$")
OLD_MUTATION_FIELDS = frozenset(
    {
        "admit",
        "admit_reason",
        "discipline_eligibility_ok",
        "training_sample_eligible",
        "quarantined_at_utc",
        "quarantined_by",
        "prior_admit",
        "prior_admit_reason",
        "regrade_run",
        "regraded_at_utc",
    }
)
PROMOTION_FIELDS = (
    "admit",
    "discipline_eligibility_ok",
    "training_sample_eligible",
)


class MigrationRefused(RuntimeError):
    """Raised when history cannot be repaired without guessing."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_reparse(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(marker and (getattr(info, "st_file_attributes", 0) & marker))


def _require_regular(path: Path, label: str) -> None:
    if path.is_symlink() or _is_reparse(path):
        raise MigrationRefused(f"{label} is a symlink or reparse point: {path}")
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise MigrationRefused(f"{label} is unavailable: {path}: {exc}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise MigrationRefused(f"{label} is not a regular file: {path}")


def _require_safe_directory(path: Path, create: bool = False) -> None:
    if path.exists():
        if path.is_symlink() or _is_reparse(path) or not path.is_dir():
            raise MigrationRefused(f"unsafe output directory: {path}")
        return
    parent = path.parent
    if parent.exists() and (parent.is_symlink() or _is_reparse(parent)):
        raise MigrationRefused(f"unsafe output directory parent: {parent}")
    if create:
        path.mkdir(parents=True, exist_ok=True)


def _is_read_only(path: Path) -> bool:
    return not bool(path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _ensure_read_only(path: Path) -> None:
    _require_regular(path, "validated pack artifact")
    if not _is_read_only(path):
        os.chmod(path, 0o444)
    if not _is_read_only(path):
        raise MigrationRefused(f"failed to mark immutable artifact read-only: {path}")


def _read_pack(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    _require_regular(path, "pack version")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MigrationRefused(f"pack is not strict UTF-8: {path.name}") from exc
    lines = text.splitlines()
    if not lines:
        raise MigrationRefused(f"pack has no rows: {path.name}")
    rows: list[dict[str, Any]] = []
    identities: set[tuple[str, int, str]] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise MigrationRefused(f"blank row at {path.name}:{line_number}")
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise MigrationRefused(
                f"invalid JSON at {path.name}:{line_number}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise MigrationRefused(f"non-object row at {path.name}:{line_number}")
        if not isinstance(row.get("admit"), bool):
            raise MigrationRefused(f"non-boolean admit at {path.name}:{line_number}")
        run_id = row.get("run_id")
        prompt_index = row.get("prompt_index")
        prompt_sha256 = str(row.get("prompt_sha256") or "").casefold()
        if (
            not isinstance(run_id, str)
            or not run_id
            or not isinstance(prompt_index, int)
            or isinstance(prompt_index, bool)
            or prompt_index < 1
            or not SHA256.fullmatch(prompt_sha256)
        ):
            raise MigrationRefused(f"invalid row identity at {path.name}:{line_number}")
        identity = (run_id, prompt_index, prompt_sha256)
        if identity in identities:
            raise MigrationRefused(f"duplicate row identity at {path.name}:{line_number}")
        identities.add(identity)
        rows.append(row)
    return raw, rows


def canonical_pack_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Return compact UTF-8 JSONL with sorted keys and LF endings."""

    body = "\n".join(
        json.dumps(
            row,
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in rows
    )
    return (body + "\n").encode("utf-8")


def _without_mutations(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in OLD_MUTATION_FIELDS}


def _admitted_lines(rows: list[dict[str, Any]]) -> set[int]:
    return {
        line_number
        for line_number, row in enumerate(rows, start=1)
        if row.get("admit") is True
    }


def _assert_versions_equivalent(
    versions: list[tuple[Path, list[dict[str, Any]]]]
) -> None:
    reference_path, reference_rows = versions[0]
    for path, rows in versions[1:]:
        if len(rows) != len(reference_rows):
            raise MigrationRefused(
                f"row-count drift: {reference_path.name} has {len(reference_rows)}, "
                f"{path.name} has {len(rows)}"
            )
        for line_number, (reference, candidate) in enumerate(
            zip(reference_rows, rows), start=1
        ):
            if _without_mutations(reference) != _without_mutations(candidate):
                raise MigrationRefused(
                    f"unexpected non-quarantine content drift at "
                    f"{path.name}:{line_number}"
                )


def _assert_no_promotions(
    original_rows: list[dict[str, Any]],
    path: Path,
    later_rows: list[dict[str, Any]],
) -> None:
    for line_number, (original, later) in enumerate(
        zip(original_rows, later_rows), start=1
    ):
        promoted = [
            field
            for field in PROMOTION_FIELDS
            if original.get(field) is not True and later.get(field) is True
        ]
        if promoted:
            raise MigrationRefused(
                f"refusing historical promotion at {path.name}:{line_number}: "
                + ", ".join(promoted)
            )


def _promotion_details(
    original_rows: list[dict[str, Any]], later_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for line_number, (original, later) in enumerate(
        zip(original_rows, later_rows), start=1
    ):
        fields = [
            field
            for field in PROMOTION_FIELDS
            if original.get(field) is not True and later.get(field) is True
        ]
        if fields:
            details.append(
                {
                    "line_number": line_number,
                    "fields": fields,
                    "reason": str(
                        later.get("admit_reason")
                        or later.get("regrade_run")
                        or "unbound historical promotion"
                    ),
                }
            )
    return details


def _receipt_name(pack_name: str, restored_sha256: str) -> str:
    pack_id = _sha256(pack_name.encode("utf-8"))[:12]
    return (
        f"ENGEL_PROMPT_PACK_HISTORY_MIGRATION_{pack_id}_"
        f"{restored_sha256[:16]}.json"
    )


def _snapshot_name(pack_name: str, current_sha256: str) -> str:
    pack_id = _sha256(pack_name.encode("utf-8"))[:12]
    return f"ENGEL_PROMPT_PACK_FORENSIC_{pack_id}_{current_sha256[:16]}.bin"


def _load_json(path: Path) -> dict[str, Any]:
    _require_regular(path, "receipt")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise MigrationRefused(f"invalid immutable JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MigrationRefused(f"immutable JSON is not an object: {path}")
    return payload


def _existing_receipt_ok(
    receipt_path: Path,
    pack_path: Path,
    canonical: bytes,
    quarantine_dir: Path,
) -> dict[str, Any] | None:
    if not receipt_path.exists():
        return None
    payload = _load_json(receipt_path)
    restored_sha256 = _sha256(canonical)
    if (
        payload.get("schema") != SCHEMA
        or payload.get("status") != "APPLIED"
        or payload.get("pack_name") != pack_path.name
        or payload.get("restored_pack_sha256") != restored_sha256
        or _sha256(pack_path.read_bytes()) != restored_sha256
    ):
        raise MigrationRefused(
            f"existing migration receipt does not match current history: {receipt_path}"
        )
    snapshot_text = str(payload.get("forensic_snapshot") or "")
    if snapshot_text:
        snapshot = Path(snapshot_text)
        _require_regular(snapshot, "forensic snapshot")
        if _sha256(snapshot.read_bytes()) != payload.get("pre_restore_pack_sha256"):
            raise MigrationRefused(f"forensic snapshot hash mismatch: {snapshot}")
    elif payload.get("pre_restore_pack_sha256") != restored_sha256:
        raise MigrationRefused("changed pack receipt is missing its forensic snapshot")
    sidecar_text = str(payload.get("quarantine_sidecar") or "")
    if sidecar_text:
        sidecar = Path(sidecar_text)
        _require_regular(sidecar, "quarantine sidecar")
        loaded = quarantine.load_pack(pack_path, quarantine_dir)
        expected_lines = set(payload.get("demoted_line_numbers") or [])
        actual_lines = {
            int(item["line_number"])
            for item in loaded["rows"]
            if item.get("quarantined") is True
        }
        if not loaded["ok"] or not expected_lines.issubset(actual_lines):
            raise MigrationRefused(
                f"existing migration sidecar no longer validates: {sidecar}"
            )
    return payload


def plan_pack(
    pack_path: Path,
    backup_paths: list[Path],
    snapshot_dir: Path,
    receipt_dir: Path,
    quarantine_dir: Path,
    discard_unbound_promotions: bool = False,
) -> dict[str, Any]:
    if not PACK_NAME.fullmatch(pack_path.name):
        raise MigrationRefused(f"unsupported base pack name: {pack_path.name}")
    current_raw, current_rows = _read_pack(pack_path)
    backup_versions: list[tuple[Path, bytes, list[dict[str, Any]]]] = []
    for backup_path in sorted(backup_paths):
        raw, rows = _read_pack(backup_path)
        backup_versions.append((backup_path, raw, rows))
    if not backup_versions:
        raise MigrationRefused(f"no original backup candidates for {pack_path.name}")

    _assert_versions_equivalent(
        [(pack_path, current_rows)]
        + [(path, rows) for path, _raw, rows in backup_versions]
    )
    maximum = max(len(_admitted_lines(rows)) for _path, _raw, rows in backup_versions)
    leaders = [
        item
        for item in backup_versions
        if len(_admitted_lines(item[2])) == maximum
    ]
    if len(leaders) > 1:
        leader_bytes = {canonical_pack_bytes(item[2]) for item in leaders}
        if len(leader_bytes) != 1:
            raise MigrationRefused(
                f"ambiguous maximum-admission backups for {pack_path.name}"
            )
    original_path, _original_raw, original_rows = leaders[0]
    original_admits = _admitted_lines(original_rows)
    for path, _raw, rows in backup_versions:
        if not _admitted_lines(rows).issubset(original_admits):
            raise MigrationRefused(
                f"backup contains a conflicting admission promotion: {path.name}"
            )
        _assert_no_promotions(original_rows, path, rows)
    promotions = _promotion_details(original_rows, current_rows)
    if promotions and not discard_unbound_promotions:
        lines = ", ".join(str(item["line_number"]) for item in promotions)
        raise MigrationRefused(
            f"refusing unbound historical promotions in {pack_path.name}: "
            f"lines {lines}; review and pass --discard-unbound-promotions to "
            f"restore the retained original conservatively"
        )

    canonical = canonical_pack_bytes(original_rows)
    restored_sha256 = _sha256(canonical)
    current_sha256 = _sha256(current_raw)
    demoted_lines = sorted(original_admits - _admitted_lines(current_rows))
    entries: list[dict[str, Any]] = []
    canonical_lines = canonical.decode("utf-8").splitlines()
    for line_number in demoted_lines:
        original = original_rows[line_number - 1]
        current = current_rows[line_number - 1]
        entries.append(
            {
                "line_number": line_number,
                "row_sha256": _sha256(
                    canonical_lines[line_number - 1].encode("utf-8")
                ),
                "prompt_index": original.get("prompt_index"),
                "scheduled_hour": original.get("scheduled_hour"),
                "run_id": original.get("run_id"),
                "reason": str(
                    current.get("admit_reason")
                    or current.get("quarantined_by")
                    or "historical in-place demotion retained by migration"
                ),
            }
        )
    receipt_path = receipt_dir / _receipt_name(pack_path.name, restored_sha256)
    changed = current_raw != canonical
    snapshot_path = (
        snapshot_dir / _snapshot_name(pack_path.name, current_sha256)
        if changed
        else None
    )
    existing = _existing_receipt_ok(
        receipt_path, pack_path, canonical, quarantine_dir
    )
    return {
        "pack_path": pack_path,
        "pack_name": pack_path.name,
        "backup_paths": [item[0] for item in backup_versions],
        "original_path": original_path,
        "original_rows": original_rows,
        "current_raw": current_raw,
        "current_sha256": current_sha256,
        "canonical": canonical,
        "restored_sha256": restored_sha256,
        "bytes_changed": changed,
        "entries": entries,
        "demoted_lines": demoted_lines,
        "discarded_promotions": promotions,
        "snapshot_path": snapshot_path,
        "receipt_path": receipt_path,
        "candidate_admit_counts": {
            path.name: len(_admitted_lines(rows))
            for path, _raw, rows in backup_versions
        },
        "already_applied": existing is not None,
        "existing_receipt": existing,
    }


def _publish_immutable(path: Path, body: bytes) -> bool:
    _require_safe_directory(path.parent, create=True)
    if path.exists():
        _require_regular(path, "immutable artifact")
        if path.read_bytes() == body:
            return False
        raise MigrationRefused(f"refusing immutable artifact overwrite: {path}")
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
        return True
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


def _matching_sidecar(
    quarantine_dir: Path,
    pack_name: str,
    canonical: bytes,
    entries: list[dict[str, Any]],
) -> Path | None:
    if not quarantine_dir.exists():
        return None
    expected = {
        (int(item["line_number"]), str(item["row_sha256"])) for item in entries
    }
    digest = _sha256(canonical)
    for path in sorted(quarantine_dir.glob("ENGEL_PROMPT_ROW_QUARANTINE_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            pack = payload.get("pack") or {}
            actual = {
                (int(item["line_number"]), str(item["row_sha256"]))
                for item in payload.get("entries") or []
                if isinstance(item, dict)
            }
        except Exception:
            continue
        if (
            payload.get("schema") == quarantine.SCHEMA
            and payload.get("source_gate") == SOURCE_GATE
            and pack.get("name") == pack_name
            and pack.get("sha256") == digest
            and int(pack.get("bytes") or -1) == len(canonical)
            and actual == expected
        ):
            _require_regular(path, "quarantine sidecar")
            return path
    return None


def _atomic_restore(pack_path: Path, body: bytes) -> None:
    temporary = (
        pack_path.parent / f".{pack_path.name}.{os.getpid()}.{time.time_ns()}.restore"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(pack_path, 0o600)
        os.replace(temporary, pack_path)
        os.chmod(pack_path, 0o444)
    finally:
        if temporary.exists():
            try:
                os.chmod(temporary, 0o600)
                temporary.unlink()
            except OSError:
                pass
        if pack_path.exists():
            os.chmod(pack_path, 0o444)
    if pack_path.read_bytes() != body:
        raise MigrationRefused(f"atomic restore verification failed: {pack_path}")


def apply_plan(
    plan: dict[str, Any],
    quarantine_dir: Path,
) -> dict[str, Any]:
    if plan["already_applied"]:
        return {
            "pack": plan["pack_name"],
            "status": "ALREADY_APPLIED",
            "receipt_path": str(plan["receipt_path"]),
            "writes": 0,
        }

    canonical = plan["canonical"]
    entries = plan["entries"]
    sidecar: Path | None = None
    pre_restore_fail_closed = False
    if entries:
        _require_safe_directory(quarantine_dir, create=True)
        sidecar = _matching_sidecar(
            quarantine_dir, plan["pack_name"], canonical, entries
        )
        if sidecar is None:
            sidecar = quarantine.write_sidecar_for_bytes(
                pack_name=plan["pack_name"],
                pack_bytes=canonical,
                entries=entries,
                source_gate=SOURCE_GATE,
                quarantine_dir=quarantine_dir,
            )
        _ensure_read_only(plan["pack_path"])
        before_restore = quarantine.load_pack(plan["pack_path"], quarantine_dir)
        mismatch_text = "pack bytes changed after quarantine sidecar"
        pre_restore_fail_closed = (
            not before_restore["ok"]
            and any(mismatch_text in item for item in before_restore["blockers"])
        )
        if not pre_restore_fail_closed:
            raise MigrationRefused(
                f"prospective sidecar did not fail closed before restore: "
                f"{plan['pack_name']}"
            )

    snapshot_path = plan["snapshot_path"]
    if snapshot_path is not None:
        _publish_immutable(snapshot_path, plan["current_raw"])
        if snapshot_path.read_bytes() != plan["current_raw"]:
            raise MigrationRefused("forensic snapshot failed exact-byte verification")
        _atomic_restore(plan["pack_path"], canonical)
    else:
        _ensure_read_only(plan["pack_path"])
    for backup_path in plan["backup_paths"]:
        _ensure_read_only(backup_path)

    after_restore = quarantine.load_pack(plan["pack_path"], quarantine_dir)
    expected_lines = set(plan["demoted_lines"])
    actual_lines = {
        int(item["line_number"])
        for item in after_restore["rows"]
        if item.get("quarantined") is True
    }
    if (
        not after_restore["ok"]
        or not expected_lines.issubset(actual_lines)
        or _sha256(plan["pack_path"].read_bytes()) != plan["restored_sha256"]
    ):
        raise MigrationRefused(
            f"restored pack or quarantine binding failed verification: "
            f"{plan['pack_name']}: {after_restore['blockers']}"
        )

    receipt = {
        "schema": SCHEMA,
        "status": "APPLIED",
        "created_at_utc": _utc_now(),
        "pack_name": plan["pack_name"],
        "original_backup": str(plan["original_path"]),
        "candidate_admit_counts": plan["candidate_admit_counts"],
        "pre_restore_pack_sha256": plan["current_sha256"],
        "restored_pack_sha256": plan["restored_sha256"],
        "restored_pack_bytes": len(canonical),
        "forensic_snapshot": str(snapshot_path) if snapshot_path else "",
        "quarantine_sidecar": str(sidecar) if sidecar else "",
        "demoted_line_numbers": plan["demoted_lines"],
        "discarded_unbound_promotions": plan["discarded_promotions"],
        "pre_restore_sidecar_failed_closed": pre_restore_fail_closed,
        "post_restore_sidecar_valid": bool(after_restore["ok"]),
        "source_pack_read_only": _is_read_only(plan["pack_path"]),
    }
    receipt_body = (
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    _publish_immutable(plan["receipt_path"], receipt_body)
    return {
        "pack": plan["pack_name"],
        "status": "APPLIED",
        "receipt_path": str(plan["receipt_path"]),
        "snapshot_path": str(snapshot_path) if snapshot_path else "",
        "sidecar_path": str(sidecar) if sidecar else "",
        "demoted_lines": plan["demoted_lines"],
        "discarded_unbound_promotions": plan["discarded_promotions"],
        "pre_restore_sidecar_failed_closed": pre_restore_fail_closed,
        "post_restore_sidecar_valid": bool(after_restore["ok"]),
    }


def discover_backups(packs_dir: Path) -> tuple[dict[str, list[Path]], list[str]]:
    groups: dict[str, list[Path]] = {}
    blockers: list[str] = []
    for path in sorted(packs_dir.glob("*.jsonl.pre_*")):
        match = BACKUP_NAME.fullmatch(path.name)
        if not match:
            blockers.append(f"unsupported historical backup name: {path.name}")
            continue
        groups.setdefault(match.group("base"), []).append(path)
    return groups, blockers


def validate_latest_receipt_binding(
    packs_dir: Path, plans: list[dict[str, Any]]
) -> list[str]:
    latest_path = packs_dir / "ENGEL_PROMPT_TRAINING_PACK_LATEST.json"
    if not latest_path.exists():
        return []
    if latest_path.is_symlink() or not latest_path.is_file():
        return [f"LATEST pack receipt is not a regular file: {latest_path}"]
    try:
        latest = json.loads(latest_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return [f"invalid LATEST pack receipt: {exc}"]
    if not isinstance(latest, dict):
        return ["LATEST pack receipt is not an object"]
    target_name = Path(str(latest.get("pack_path") or "")).name
    for plan in plans:
        if plan["pack_name"] != target_name:
            continue
        expected = str(latest.get("pack_sha256") or "").casefold()
        if expected != plan["restored_sha256"]:
            return [
                f"LATEST receipt hash {expected or '<missing>'} does not match "
                f"canonical restored hash {plan['restored_sha256']} for {target_name}"
            ]
        if int(latest.get("rows") or -1) != len(plan["original_rows"]):
            return [f"LATEST receipt row count does not match {target_name}"]
        return []
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="publish evidence and atomically restore validated packs",
    )
    parser.add_argument(
        "--discard-unbound-promotions",
        action="store_true",
        help=(
            "conservatively restore retained originals even when the current pack "
            "contains allowlist-only promotions; every discarded promotion is receipted"
        ),
    )
    parser.add_argument("--packs-dir", default=str(DEFAULT_PACKS_DIR))
    parser.add_argument("--quarantine-dir", default=str(DEFAULT_QUARANTINE_DIR))
    parser.add_argument("--snapshot-dir", default=str(DEFAULT_SNAPSHOT_DIR))
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
    args = parser.parse_args()

    packs_dir = Path(args.packs_dir)
    quarantine_dir = Path(args.quarantine_dir)
    snapshot_dir = Path(args.snapshot_dir)
    receipt_dir = Path(args.receipt_dir)
    if (
        not packs_dir.exists()
        or packs_dir.is_symlink()
        or _is_reparse(packs_dir)
        or not packs_dir.is_dir()
    ):
        print(json.dumps({"ok": False, "blockers": [f"unsafe packs dir: {packs_dir}"]}))
        return 2

    groups, blockers = discover_backups(packs_dir)
    roster_paths = sorted(
        path
        for path in packs_dir.glob("ENGEL_PROMPT_TRAINING_PACK_*.jsonl")
        if PACK_NAME.fullmatch(path.name)
    )
    for roster_path in roster_paths:
        try:
            _read_pack(roster_path)
        except MigrationRefused as exc:
            blockers.append(f"{roster_path.name}: {exc}")
    plans: list[dict[str, Any]] = []
    for base_name, backup_paths in sorted(groups.items()):
        try:
            plans.append(
                plan_pack(
                    packs_dir / base_name,
                    backup_paths,
                    snapshot_dir,
                    receipt_dir,
                    quarantine_dir,
                    args.discard_unbound_promotions,
                )
            )
        except MigrationRefused as exc:
            blockers.append(f"{base_name}: {exc}")
    blockers.extend(validate_latest_receipt_binding(packs_dir, plans))

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "mode": "apply" if args.apply else "dry_run",
        "ok": not blockers,
        "packs_with_backups": len(groups),
        "packs_planned": len(plans),
        "validated_pack_roster_count": len(roster_paths),
        "writable_pack_roster_count": sum(
            1 for path in roster_paths if not _is_read_only(path)
        ),
        "blockers": blockers,
        "plans": [
            {
                "pack": plan["pack_name"],
                "status": (
                    "ALREADY_APPLIED" if plan["already_applied"] else "WOULD_RESTORE"
                ),
                "original_backup": plan["original_path"].name,
                "candidate_admit_counts": plan["candidate_admit_counts"],
                "current_sha256": plan["current_sha256"],
                "restored_sha256": plan["restored_sha256"],
                "demoted_line_numbers": plan["demoted_lines"],
                "discarded_unbound_promotions": plan["discarded_promotions"],
            }
            for plan in plans
        ],
    }
    if blockers:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 2
    if args.apply:
        try:
            result["applied"] = [
                apply_plan(plan, quarantine_dir) for plan in plans
            ]
            for roster_path in roster_paths:
                _ensure_read_only(roster_path)
            result["pack_roster_read_only"] = all(
                _is_read_only(path) for path in roster_paths
            )
            if not result["pack_roster_read_only"]:
                raise MigrationRefused("validated stamped-pack roster remains writable")
        except (MigrationRefused, OSError, ValueError) as exc:
            result["ok"] = False
            result["blockers"].append(f"apply failed: {type(exc).__name__}: {exc}")
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
            return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
