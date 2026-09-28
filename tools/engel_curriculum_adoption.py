#!/usr/bin/env python3
"""Hash-bound explicit confirmation for generated Engel curricula.

The digest phrase prevents accidental/broad adoption and the read-only receipt detects
later drift. It is deliberately not described as cryptographic proof of human identity;
that would require a separately provisioned operator-held signing key.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RECEIPT_SCHEMA = "engel_curriculum_adoption_receipt_v1"
_UNBOUND_FIELDS = {
    "adoption",
    "adopted_at_utc",
    "adoption_receipt",
    "generated_at_utc",
    "proposal_sha256",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_proposal_bytes(payload: dict[str, Any]) -> bytes:
    canonical = {
        key: value for key, value in payload.items() if key not in _UNBOUND_FIELDS
    }
    return json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def proposal_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_proposal_bytes(payload)).hexdigest().upper()


def normalized_kind(kind: str) -> str:
    value = re.sub(r"[^A-Z0-9]+", "_", str(kind).upper()).strip("_")
    if not value:
        raise ValueError("curriculum adoption kind is empty")
    return value


def required_approval(kind: str, proposal: dict[str, Any]) -> str:
    digest = proposal_sha256(proposal)
    return f"APPROVE_ENGEL_ADOPT_{normalized_kind(kind)}_{digest[:16]}"


def _atomic_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with stage.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, path)
    finally:
        try:
            stage.unlink()
        except FileNotFoundError:
            pass


def _publish_read_only_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"refusing to overwrite adoption receipt: {path.name}")
        if path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
            raise RuntimeError(f"existing adoption receipt is mutable: {path.name}")
        return
    stage = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with stage.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(stage, path)
        # A hard link shares the Windows read-only attribute. Remove the staging
        # name before hardening the published name or cleanup cannot unlink it.
        stage.unlink()
        path.chmod(0o444)
    finally:
        try:
            stage.unlink()
        except FileNotFoundError:
            pass


def verify_adoption(
    adopted_path: Path,
    *,
    expected_kind: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    """Authenticate an adopted pointer against its immutable receipt."""

    path = Path(adopted_path)
    problems: list[str] = []
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            raise ValueError("adopted curriculum is not a regular non-link file")
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, None, [f"adopted curriculum could not be authenticated: {exc}"]
    if not isinstance(payload, dict):
        return None, None, ["adopted curriculum is not a JSON object"]
    if payload.get("adoption") != "adopted":
        problems.append("curriculum is not explicitly adopted")
    if not str(payload.get("adopted_at_utc") or "").strip():
        problems.append("curriculum has no adoption timestamp")
    expected_proposal_sha = proposal_sha256(payload)
    if str(payload.get("proposal_sha256") or "").upper() != expected_proposal_sha:
        problems.append("adopted curriculum proposal SHA-256 is invalid")
    receipt_name = str(payload.get("adoption_receipt") or "")
    if (
        not receipt_name
        or Path(receipt_name).name != receipt_name
        or "/" in receipt_name
        or "\\" in receipt_name
    ):
        problems.append("adoption receipt path is absent or unsafe")
        return payload, None, problems
    receipt_path = path.parent / receipt_name
    try:
        receipt_info = os.lstat(receipt_path)
        if (
            not stat.S_ISREG(receipt_info.st_mode)
            or receipt_path.is_symlink()
            or bool(
                receipt_info.st_mode
                & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            )
        ):
            raise ValueError("receipt must be a regular read-only non-link file")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return payload, None, problems + [f"adoption receipt is invalid: {exc}"]
    if not isinstance(receipt, dict):
        return payload, None, problems + ["adoption receipt is not a JSON object"]
    actual_sha = hashlib.sha256(raw).hexdigest().upper()
    expected_kind_value = normalized_kind(expected_kind)
    checks = {
        "receipt schema": receipt.get("schema") == RECEIPT_SCHEMA,
        "adoption kind": receipt.get("kind") == expected_kind_value,
        "adopted filename": receipt.get("adopted_filename") == path.name,
        "adopted byte count": receipt.get("adopted_bytes") == len(raw),
        "adopted SHA-256": str(receipt.get("adopted_sha256") or "").upper()
        == actual_sha,
        "proposal SHA-256": str(receipt.get("proposal_sha256") or "").upper()
        == expected_proposal_sha,
        "receipt filename": receipt.get("receipt_filename") == receipt_name,
        "approval contract": receipt.get("approval_contract")
        == required_approval(expected_kind_value, payload),
    }
    problems.extend(f"{label} binding is invalid" for label, ok in checks.items() if not ok)
    return payload, receipt, problems


def adopt_proposal(
    proposal: dict[str, Any],
    adopted_path: Path,
    *,
    kind: str,
    approval: str,
) -> tuple[dict[str, Any], Path]:
    """Publish a mutable pointer whose exact bytes are bound by an immutable receipt."""

    expected = required_approval(kind, proposal)
    if approval != expected:
        raise ValueError(f"exact adoption approval required: {expected}")
    adopted_path = Path(adopted_path)
    digest = proposal_sha256(proposal)
    kind_value = normalized_kind(kind)
    receipt_name = (
        f"ENGEL_CURRICULUM_ADOPTION_{kind_value}_{digest[:16]}.json"
    )
    receipt_path = adopted_path.parent / receipt_name

    if adopted_path.is_file() and receipt_path.is_file():
        existing, _, problems = verify_adoption(
            adopted_path, expected_kind=kind_value
        )
        if (
            existing is not None
            and not problems
            and str(existing.get("proposal_sha256") or "").upper() == digest
        ):
            return existing, receipt_path
        if receipt_path.exists():
            raise RuntimeError(
                "the immutable receipt name already exists but does not authenticate "
                "the adopted curriculum"
            )

    adopted = dict(proposal)
    adopted.update(
        {
            "adoption": "adopted",
            "adopted_at_utc": _utc_now(),
            "proposal_sha256": digest,
            "adoption_receipt": receipt_name,
        }
    )
    adopted_raw = (
        json.dumps(adopted, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "kind": kind_value,
        "created_at_utc": _utc_now(),
        "receipt_filename": receipt_name,
        "adopted_filename": adopted_path.name,
        "adopted_bytes": len(adopted_raw),
        "adopted_sha256": hashlib.sha256(adopted_raw).hexdigest().upper(),
        "proposal_sha256": digest,
        "approval_contract": expected,
        "authorization_semantics": (
            "explicit_digest_confirmation_not_cryptographic_identity"
        ),
    }
    receipt_raw = (
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    _atomic_replace(adopted_path, adopted_raw)
    _publish_read_only_new(receipt_path, receipt_raw)
    verified, _, problems = verify_adoption(
        adopted_path, expected_kind=kind_value
    )
    if verified is None or problems:
        raise RuntimeError("published curriculum adoption did not verify: " + " | ".join(problems))
    return adopted, receipt_path
