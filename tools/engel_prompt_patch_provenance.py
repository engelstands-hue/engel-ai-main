#!/usr/bin/env python3
"""Tamper-evident prompt-to-patch provenance for Engel self-upgrade cycles."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterator


ROOT = Path(os.environ.get("ENGEL_ROOT") or Path(__file__).resolve().parents[1])
REPORT_ROOT = ROOT / "reports" / "self_upgrade" / "provenance"
LEDGER_PATH = REPORT_ROOT / "prompt_patch_ledger.jsonl"
ENTRY_ROOT = REPORT_ROOT / "entries"
GOAL_ID = "engel_conical_agentic_sentient_self_upgrading_system"

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|session[_-]?token|password)"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{12,}",
        re.IGNORECASE,
    ),
)


class ProvenanceError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_text(value: Any, limit: int = 5000) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit]


def contains_secret_like_text(*values: Any) -> bool:
    text = "\n".join(clean_text(value, 12000) for value in values)
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def confined_reference(path: Path, *, root: Path) -> dict[str, Any]:
    root = root.resolve()
    candidate = path.resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ProvenanceError(f"evidence path escaped Engel root: {candidate}") from exc
    if not candidate.is_file():
        raise ProvenanceError(f"evidence file is missing: {candidate}")
    return {
        "path": relative.as_posix(),
        "sha256": file_sha256(candidate),
        "bytes": candidate.stat().st_size,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


@contextmanager
def _append_lock(ledger_path: Path) -> Iterator[None]:
    lock_path = ledger_path.with_suffix(ledger_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    if lock_path.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8", errors="strict").splitlines(),
        1,
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProvenanceError(
                f"malformed provenance ledger line {line_number}"
            ) from exc
        if not isinstance(payload, dict):
            raise ProvenanceError(
                f"non-object provenance ledger line {line_number}"
            )
        entries.append(payload)
    return entries


def _is_ephemeral_cycle_fixture(entry: dict[str, Any]) -> bool:
    references = entry.get("references") or {}
    if not isinstance(references, dict) or not references:
        return False
    prefix = "runtime/temp/cycle_verify_"
    paths: list[str] = []
    for reference in references.values():
        if not isinstance(reference, dict):
            return False
        path = str(reference.get("path") or "").replace("\\", "/")
        if not path:
            return False
        paths.append(path)
    return bool(paths) and all(path.startswith(prefix) for path in paths)


def _operation_summary(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ProvenanceError(f"operation {index} is not an object")
        file_name = clean_text(operation.get("file"), 500)
        old_text = str(operation.get("old_text") or "")
        new_text = str(operation.get("new_text") or "")
        if not file_name or not old_text:
            raise ProvenanceError(f"operation {index} lacks file or old_text")
        if contains_secret_like_text(old_text, new_text):
            raise ProvenanceError(
                f"operation {index} contains secret-like material"
            )
        summaries.append(
            {
                "index": index,
                "file": file_name.replace("\\", "/"),
                "old_text_sha256": hashlib.sha256(
                    old_text.encode("utf-8")
                ).hexdigest(),
                "new_text_sha256": hashlib.sha256(
                    new_text.encode("utf-8")
                ).hexdigest(),
                "old_text_bytes": len(old_text.encode("utf-8")),
                "new_text_bytes": len(new_text.encode("utf-8")),
            }
        )
    if not summaries:
        raise ProvenanceError("at least one patch operation is required")
    return summaries


def record_cycle_provenance(
    *,
    cycle_id: str,
    actor: str,
    request: dict[str, Any],
    issue_path: Path,
    distributed_review_path: Path,
    candidate_path: Path,
    patch_path: Path,
    candidate: dict[str, Any],
    operations: list[dict[str, Any]],
    root: Path = ROOT,
    ledger_path: Path = LEDGER_PATH,
    entry_root: Path = ENTRY_ROOT,
) -> dict[str, Any]:
    prompt = {
        "source": clean_text(request.get("source"), 500),
        "symptom": clean_text(request.get("symptom"), 5000),
        "diagnosis": clean_text(request.get("diagnosis"), 5000),
        "patch_plan": clean_text(request.get("patch_plan"), 5000),
        "lesson": clean_text(request.get("lesson"), 3000),
    }
    if contains_secret_like_text(*prompt.values()):
        raise ProvenanceError("self-upgrade request contains secret-like material")
    operation_summaries = _operation_summary(operations)
    references = {
        "issue": confined_reference(issue_path, root=root),
        "distributed_review": confined_reference(
            distributed_review_path,
            root=root,
        ),
        "candidate": confined_reference(candidate_path, root=root),
        "patch": confined_reference(patch_path, root=root),
    }
    request_payload = {
        "prompt": prompt,
        "files_to_change": [
            clean_text(value, 500).replace("\\", "/")
            for value in list(request.get("files_to_change") or [])
        ],
        "operations": operation_summaries,
    }
    with _append_lock(ledger_path):
        existing = _read_ledger(ledger_path)
        previous_sha = (
            str(existing[-1].get("entry_sha256") or "") if existing else ""
        )
        base: dict[str, Any] = {
            "schema": "ENGEL_PROMPT_PATCH_PROVENANCE_V1",
            "goal_id": GOAL_ID,
            "provenance_id": "",
            "cycle_id": clean_text(cycle_id, 200),
            "actor": clean_text(actor, 200),
            "created_at_utc": utc_now(),
            "request": prompt,
            "request_sha256": canonical_sha256(request_payload),
            "candidate_id": clean_text(candidate.get("candidate_id"), 200),
            "risk_level": clean_text(candidate.get("risk_level"), 80),
            "required_verifiers": [
                clean_text(value, 500)
                for value in list(candidate.get("required_verifiers") or [])
            ],
            "distributed_worker_ids": [
                clean_text(value, 200)
                for value in list(
                    candidate.get("distributed_review_worker_ids") or []
                )
            ],
            "operations": operation_summaries,
            "references": references,
            "previous_entry_sha256": previous_sha,
            "ledger_path": ledger_path.resolve().relative_to(
                root.resolve()
            ).as_posix(),
            "secret_material_stored": False,
            "source_mutation_performed": False,
            "entry_sha256": "",
        }
        provenance_seed = dict(base)
        provenance_seed.pop("provenance_id", None)
        provenance_seed.pop("entry_sha256", None)
        base["provenance_id"] = (
            "prompt_patch_" + canonical_sha256(provenance_seed)[:20]
        )
        hash_payload = dict(base)
        hash_payload.pop("entry_sha256", None)
        base["entry_sha256"] = canonical_sha256(hash_payload)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    base,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
    receipt_path = entry_root / f"{base['provenance_id']}.json"
    _atomic_write_json(receipt_path, base)
    result = dict(base)
    result.update(
        {
            "ok": True,
            "receipt_path": str(receipt_path),
            "ledger_path_absolute": str(ledger_path),
        }
    )
    return result


def verify_ledger(
    *,
    root: Path = ROOT,
    ledger_path: Path = LEDGER_PATH,
    entry_root: Path = ENTRY_ROOT,
) -> dict[str, Any]:
    errors: list[str] = []
    production_entry_count = 0
    fixture_entry_count = 0
    try:
        entries = _read_ledger(ledger_path)
    except ProvenanceError as exc:
        entries = []
        errors.append(str(exc))
    previous = ""
    for index, entry in enumerate(entries):
        fixture_entry = _is_ephemeral_cycle_fixture(entry)
        if fixture_entry:
            fixture_entry_count += 1
        else:
            production_entry_count += 1
        expected_previous = str(entry.get("previous_entry_sha256") or "")
        if expected_previous != previous:
            errors.append(f"entry {index} previous hash mismatch")
        hash_payload = dict(entry)
        claimed = str(hash_payload.pop("entry_sha256", "") or "")
        computed = canonical_sha256(hash_payload)
        if not claimed or claimed != computed:
            errors.append(f"entry {index} entry hash mismatch")
        if entry.get("secret_material_stored") is not False:
            errors.append(f"entry {index} secret-material flag is unsafe")
        if entry.get("source_mutation_performed") is not False:
            errors.append(f"entry {index} claims provenance mutated source")
        for label, reference in (entry.get("references") or {}).items():
            if not isinstance(reference, dict):
                errors.append(f"entry {index} reference {label} is invalid")
                continue
            candidate = (root / str(reference.get("path") or "")).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                errors.append(f"entry {index} reference {label} escaped root")
                continue
            if not candidate.is_file():
                if not fixture_entry:
                    errors.append(f"entry {index} reference {label} is missing")
            elif file_sha256(candidate) != str(reference.get("sha256") or ""):
                errors.append(f"entry {index} reference {label} hash mismatch")
        receipt = entry_root / f"{entry.get('provenance_id', '')}.json"
        if not receipt.is_file():
            errors.append(f"entry {index} immutable receipt is missing")
        else:
            try:
                receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                receipt_payload = {}
            if receipt_payload != entry:
                errors.append(f"entry {index} immutable receipt mismatch")
        previous = claimed
    return {
        "schema": "ENGEL_PROMPT_PATCH_PROVENANCE_VERIFY_V1",
        "goal_id": GOAL_ID,
        "ok": production_entry_count > 0 and not errors,
        "entry_count": len(entries),
        "production_entry_count": production_entry_count,
        "fixture_entry_count": fixture_entry_count,
        "fixture_reference_policy": (
            "ephemeral verifier references excluded from production evidence checks; "
            "chain and immutable receipt still verified"
        ),
        "latest_entry_sha256": previous,
        "errors": errors,
        "ledger_path": str(ledger_path),
        "source_mutation_performed": False,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "verify"])
    args = parser.parse_args()
    payload = verify_ledger()
    if args.command == "status" and not LEDGER_PATH.is_file():
        payload["status"] = "no provenance entries recorded"
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
