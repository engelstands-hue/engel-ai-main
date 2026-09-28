#!/usr/bin/env python3
"""Fail-closed cross-run novelty checks for scheduled Engel prompt training.

Scheduled prompt training is practice, not a replay queue.  A prompt that already
appears in a stamped training pack has already reached the model, whether its answer
was admitted or rejected.  Re-running it spends compute without adding a new training
question and can overweight one lesson in both the SFT and SLM datasets.

This module deliberately hashes the *unwrapped base prompt*.  Training-level guidance,
answer contracts, timestamps, nonces, and other delivery text cannot make an old lesson
new.  Historical inputs are the uniquely named pack files; mutable ``LATEST`` aliases
are never consulted.  Every pack's raw SHA-256 is recorded so a session receipt names
the exact history snapshot on which its novelty decision depended.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, BinaryIO, Iterable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

DEFAULT_PACKS_DIR = ROOT / "memory" / "training" / "packs"
DEFAULT_PROMPT_RUN_CLAIM = (
    ROOT / "runtime" / "one_hour_local_only_chat_training" / "prompt_run.lock"
)
DEFAULT_RESERVATIONS_DIR = ROOT / "memory" / "training" / "prompt_use_reservations"
PACK_ROW_SCHEMA = "engel_prompt_training_pack_row_v1"
PREFLIGHT_SCHEMA = "engel_scheduled_prompt_novelty_preflight_v1"
PROMPT_RUN_CLAIM_SCHEMA = "engel_prompt_training_os_claim_v1"
PROMPT_USE_RESERVATION_SCHEMA = "engel_prompt_use_reservation_v1"
CANONICALIZATION = "unicode_nfkc_casefold_collapsed_whitespace_v1"
PACK_PREFIX = "ENGEL_PROMPT_TRAINING_PACK_"
PACK_SUFFIX = ".jsonl"
_PACK_NAME = re.compile(
    r"^ENGEL_PROMPT_TRAINING_PACK_[A-Za-z0-9][A-Za-z0-9_.-]*\.jsonl$"
)
RESERVATION_PREFIX = "ENGEL_PROMPT_USE_RESERVATION_"
RESERVATION_SUFFIX = ".json"
_RESERVATION_NAME = re.compile(
    r"^ENGEL_PROMPT_USE_RESERVATION_[a-f0-9]{64}\.json$"
)
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class PromptNoveltyBlocked(RuntimeError):
    """Raised when scheduled work cannot prove that every planned prompt is new."""


class PromptRunClaimBlocked(RuntimeError):
    """Raised when another process owns the OS-released prompt-run claim."""


class PromptRunClaim:
    """Non-blocking, process-bound claim held for an entire prompt-training run.

    The JSON stored after byte zero is diagnostic only.  Ownership is the kernel lock
    on byte zero (Windows) or the open file description (POSIX), so a killed process
    releases the claim without trusting a timestamp or mutable sentinel.
    """

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = Path(path).resolve()
        self.run_id = str(run_id or "").strip()
        if not self.run_id:
            raise ValueError("prompt-run claim requires a non-empty run_id")
        self.owner_pid = os.getpid()
        self.acquired_at_epoch: float | None = None
        self._handle: BinaryIO | None = None

    @property
    def held(self) -> bool:
        return self._handle is not None and not self._handle.closed

    @property
    def owner_record(self) -> dict[str, Any]:
        return {
            "schema": PROMPT_RUN_CLAIM_SCHEMA,
            "run_id": self.run_id,
            "owner_pid": self.owner_pid,
            "claim_path": str(self.path),
            "acquired_at_epoch": self.acquired_at_epoch,
            "lock_semantics": "kernel-released exclusive nonblocking lock",
        }

    @staticmethod
    def _read_last_record(path: Path) -> dict[str, Any]:
        try:
            raw = path.read_bytes()
            value = json.loads(raw[1:].decode("utf-8-sig")) if len(raw) > 1 else {}
            return value if isinstance(value, dict) else {}
        except (OSError, UnicodeDecodeError, ValueError, TypeError):
            return {}

    def _lock(self, handle: BinaryIO) -> None:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(self, handle: BinaryIO) -> None:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def acquire(self) -> "PromptRunClaim":
        if self.held:
            raise RuntimeError("prompt-run claim is already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise PromptRunClaimBlocked(
                f"prompt-run claim path must not be a symlink: {self.path}"
            )
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        handle = os.fdopen(descriptor, "r+b", buffering=0)
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
                os.fsync(handle.fileno())
            self._lock(handle)
        except (OSError, BlockingIOError) as exc:
            handle.close()
            recorded = self._read_last_record(self.path)
            raise PromptRunClaimBlocked(
                "another prompt-training process owns the exclusive OS claim: "
                + json.dumps(
                    {
                        "claim_path": str(self.path),
                        "requested_run_id": self.run_id,
                        "recorded_owner": recorded,
                    },
                    sort_keys=True,
                )
            ) from exc
        self._handle = handle
        self.owner_pid = os.getpid()
        self.acquired_at_epoch = time.time()
        encoded = json.dumps(
            self.owner_record, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        handle.seek(1)
        handle.write(encoded)
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())
        return self

    def require_owner(self, run_id: str) -> None:
        if not self.held:
            raise RuntimeError("prompt-run side effect refused: OS claim is not held")
        if self.owner_pid != os.getpid():
            raise RuntimeError(
                "prompt-run side effect refused: claim belongs to a different process"
            )
        if self.run_id != str(run_id or "").strip():
            raise RuntimeError(
                "prompt-run side effect refused: run_id does not match the OS claim"
            )

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None or handle.closed:
            return
        try:
            self._unlock(handle)
        finally:
            handle.close()

    def __enter__(self) -> "PromptRunClaim":
        return self.acquire()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()


def acquire_prompt_run_claim(
    path: Path = DEFAULT_PROMPT_RUN_CLAIM,
    run_id: str = "",
) -> PromptRunClaim:
    """Return a context manager that acquires the exclusive prompt-run claim."""

    return PromptRunClaim(path, run_id)


def _reservation_id(run_id: str, prompt_position: int, prompt_hash: str) -> str:
    identity = f"{run_id}\0{prompt_position}\0{prompt_hash}".encode("utf-8")
    return _sha256_bytes(identity)


def _reservation_path(
    reservations_dir: Path,
    run_id: str,
    prompt_position: int,
    prompt_hash: str,
) -> Path:
    reservation_id = _reservation_id(run_id, prompt_position, prompt_hash)
    return Path(reservations_dir) / (
        f"{RESERVATION_PREFIX}{reservation_id}{RESERVATION_SUFFIX}"
    )


def publish_prompt_use_reservation(
    *,
    reservations_dir: Path = DEFAULT_RESERVATIONS_DIR,
    prompt_run_claim: PromptRunClaim,
    run_id: str,
    prompt_position: int,
    base_prompt: str,
    history_snapshot_sha256: str,
    history_pack_snapshot_sha256: str,
    history_reservation_snapshot_sha256: str,
    planned_prompt_set_sha256: str,
) -> dict[str, Any]:
    """Atomically consume one prompt immediately before UI delivery.

    A crash after this publication may conservatively consume this one lesson, but a
    failed/missing training pack can never make an already-delivered lesson look new.
    The file is uniquely named, hard-linked into place without overwrite, and read-only.
    """

    prompt_run_claim.require_owner(run_id)
    run_id = str(run_id or "").strip()
    prompt_position = int(prompt_position)
    base_prompt = str(base_prompt or "").strip()
    if not run_id or prompt_position < 1 or not base_prompt:
        raise ValueError("reservation requires run_id, positive position, and base prompt")
    hash_fields = {
        "history_snapshot_sha256": str(history_snapshot_sha256 or "").casefold(),
        "history_pack_snapshot_sha256": str(
            history_pack_snapshot_sha256 or ""
        ).casefold(),
        "history_reservation_snapshot_sha256": str(
            history_reservation_snapshot_sha256 or ""
        ).casefold(),
        "planned_prompt_set_sha256": str(planned_prompt_set_sha256 or "").casefold(),
    }
    invalid = [key for key, value in hash_fields.items() if not _SHA256.fullmatch(value)]
    if invalid:
        raise ValueError(f"reservation has invalid SHA-256 field(s): {invalid}")
    prompt_hash = canonical_base_prompt_sha256(base_prompt)
    reservation_id = _reservation_id(run_id, prompt_position, prompt_hash)
    payload = {
        "schema": PROMPT_USE_RESERVATION_SCHEMA,
        "reservation_id": reservation_id,
        "run_id": run_id,
        "prompt_position": prompt_position,
        "base_prompt": base_prompt,
        "base_prompt_sha256": prompt_hash,
        "base_prompt_hash_canonicalization": CANONICALIZATION,
        **hash_fields,
        "created_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        ),
        "prompt_run_claim": prompt_run_claim.owner_record,
    }
    reservations_dir = Path(reservations_dir)
    reservations_dir.mkdir(parents=True, exist_ok=True)
    path = _reservation_path(
        reservations_dir, run_id, prompt_position, prompt_hash
    )
    if path.exists():
        raise RuntimeError(f"refusing prompt-use reservation overwrite: {path}")
    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    temporary = reservations_dir / (
        f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    linked = False
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
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
    return {
        **payload,
        "path": str(path),
        "bytes": len(body.encode("utf-8")),
        "sha256": _sha256_bytes(body.encode("utf-8")),
        "immutable": True,
    }


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_base_prompt(value: Any) -> str:
    """Return the stable identity text for a training question.

    Collapsing whitespace and case prevents a replay from being disguised by wrapping,
    indentation, or capitalization.  NFKC closes common Unicode presentation variants.
    No semantic words are added or removed.
    """

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def canonical_base_prompt_sha256(value: Any) -> str:
    canonical = canonical_base_prompt(value)
    if not canonical:
        raise ValueError("base prompt cannot be empty")
    return _sha256_bytes(canonical.encode("utf-8"))


def _accepted_stored_prompt_hashes(value: Any) -> dict[str, str]:
    """Hashes written by the current canonical writer and older runner revisions."""

    stripped = str(value or "").strip()
    return {
        "canonical_v1": canonical_base_prompt_sha256(stripped),
        "legacy_casefold_v0": _sha256_bytes(stripped.casefold().encode("utf-8")),
        "legacy_exact_v0": _sha256_bytes(stripped.encode("utf-8")),
    }


def material_card_sha256(card: dict[str, Any]) -> str:
    """Hash real lesson content, excluding timestamps, IDs, and cosmetic metadata."""

    payload = {
        key: canonical_base_prompt(card.get(key))
        for key in ("topic", "scenario", "constraint", "proof")
    }
    artifacts = card.get("artifacts")
    if isinstance(artifacts, list):
        payload["artifacts"] = sorted(
            canonical_base_prompt(item) for item in artifacts if str(item).strip()
        )
    # Problem order determines which exact question is delivered at each position, so it
    # is part of the lesson identity.  Document and artifact bindings are handled below.
    problem_ids = card.get("problem_ids")
    if isinstance(problem_ids, list):
        payload["problem_ids"] = [
            canonical_base_prompt(item)
            for item in problem_ids
            if str(item).strip()
        ]
    documents = card.get("documents")
    if isinstance(documents, list):
        payload["documents"] = sorted(
            canonical_base_prompt(item) for item in documents if str(item).strip()
        )
    anchors = card.get("evidence_anchors")
    if isinstance(anchors, list):
        payload["evidence_anchors"] = sorted(
            (
                {
                    "document": canonical_base_prompt(item.get("document")),
                    "section": canonical_base_prompt(item.get("section")),
                }
                for item in anchors
                if isinstance(item, dict)
                and str(item.get("document") or "").strip()
                and str(item.get("section") or "").strip()
            ),
            key=lambda item: (item["document"], item["section"]),
        )
    grounding_records = card.get("_grounding_artifact_records")
    if isinstance(grounding_records, list):
        payload["grounding_artifact_records"] = sorted(
            (
                {
                    "path": canonical_base_prompt(item.get("path")),
                    "sha256": str(item.get("sha256") or "").strip().casefold(),
                    "bytes": int(item.get("bytes") or 0),
                }
                for item in grounding_records
                if isinstance(item, dict)
            ),
            key=lambda item: (item["path"], item["sha256"], item["bytes"]),
        )
    if not all(payload.get(key) for key in ("topic", "scenario", "constraint", "proof")):
        raise ValueError("material card must contain topic, scenario, constraint, and proof")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(encoded)


def _history_snapshot_sha256(pack_records: list[dict[str, Any]]) -> str:
    stable = [
        {
            "name": record["name"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }
        for record in pack_records
    ]
    return _sha256_bytes(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _hash_set_sha256(hashes: Iterable[str]) -> str:
    body = "\n".join(sorted(set(hashes))).encode("ascii")
    return _sha256_bytes(body)


def load_prompt_history(
    packs_dir: Path = DEFAULT_PACKS_DIR,
    reservations_dir: Path | None = None,
) -> dict[str, Any]:
    """Read and hash every canonical stamped pack, failing closed on corruption.

    Older packs predate the ``base_prompt_sha256`` field, so the authoritative hash is
    always recomputed from ``base_prompt``.  When a stored hash is present it must agree.
    Both admitted and rejected rows count: either one proves the prompt was already run.
    """

    packs_dir = Path(packs_dir)
    reservations_dir = (
        Path(reservations_dir)
        if reservations_dir is not None
        else packs_dir.parent / DEFAULT_RESERVATIONS_DIR.name
    )
    pack_records: list[dict[str, Any]] = []
    reservation_records: list[dict[str, Any]] = []
    occurrences: dict[str, list[dict[str, Any]]] = {}
    problems: list[str] = []
    row_count = 0
    rows_without_stored_hash = 0
    stored_hash_scheme_counts: dict[str, int] = {}

    if packs_dir.exists() and not packs_dir.is_dir():
        problems.append(f"history path is not a directory: {packs_dir}")
        candidates: list[Path] = []
    elif not packs_dir.exists():
        candidates = []
    else:
        candidates = sorted(
            path
            for path in packs_dir.glob(f"{PACK_PREFIX}*{PACK_SUFFIX}")
            if _PACK_NAME.fullmatch(path.name)
        )

    for path in candidates:
        if path.is_symlink() or not path.is_file():
            problems.append(f"history pack must be a regular non-symlink file: {path}")
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            problems.append(f"history pack could not be read: {path}: {exc}")
            continue
        pack_records.append(
            {
                "name": path.name,
                "path": str(path),
                "bytes": len(raw),
                "sha256": _sha256_bytes(raw),
                "read_only": not bool(path.stat().st_mode & 0o222),
            }
        )
        if not pack_records[-1]["read_only"]:
            problems.append(f"history pack is mutable: {path.name}")
        for line_number, raw_line in enumerate(raw.splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                problems.append(f"invalid JSON in {path.name}:{line_number}: {exc}")
                continue
            if not isinstance(row, dict) or row.get("schema") != PACK_ROW_SCHEMA:
                problems.append(
                    f"invalid pack row schema in {path.name}:{line_number}"
                )
                continue
            base_prompt = str(row.get("base_prompt") or "").strip()
            if not base_prompt:
                problems.append(f"missing base_prompt in {path.name}:{line_number}")
                continue
            row_count += 1
            prompt_hash = canonical_base_prompt_sha256(base_prompt)
            stored_hash = str(row.get("base_prompt_sha256") or "").strip().casefold()
            if stored_hash:
                accepted_hashes = _accepted_stored_prompt_hashes(base_prompt)
                matched_schemes = [
                    scheme
                    for scheme, expected in accepted_hashes.items()
                    if stored_hash == expected
                ]
                if not matched_schemes:
                    problems.append(
                        f"base_prompt_sha256 mismatch in {path.name}:{line_number}"
                    )
                    continue
                scheme = matched_schemes[0]
                stored_hash_scheme_counts[scheme] = (
                    stored_hash_scheme_counts.get(scheme, 0) + 1
                )
            else:
                rows_without_stored_hash += 1
            occurrences.setdefault(prompt_hash, []).append(
                {
                    "source": "training_pack",
                    "pack": path.name,
                    "line": line_number,
                    "run_id": str(row.get("run_id") or ""),
                    "prompt_index": row.get("prompt_index"),
                    "admit": row.get("admit") is True,
                }
            )

    if reservations_dir.exists() and not reservations_dir.is_dir():
        problems.append(f"reservation history path is not a directory: {reservations_dir}")
        reservation_candidates: list[Path] = []
    elif not reservations_dir.exists():
        reservation_candidates = []
    else:
        reservation_candidates = sorted(
            reservations_dir.glob(
                f"{RESERVATION_PREFIX}*{RESERVATION_SUFFIX}"
            )
        )

    seen_run_positions: dict[tuple[str, int], str] = {}
    seen_reservation_prompt_hashes: dict[str, str] = {}
    valid_reservation_count = 0
    for path in reservation_candidates:
        if not _RESERVATION_NAME.fullmatch(path.name):
            problems.append(f"invalid prompt-use reservation filename: {path.name}")
            continue
        if path.is_symlink() or not path.is_file():
            problems.append(
                f"prompt-use reservation must be a regular non-symlink file: {path}"
            )
            continue
        try:
            raw = path.read_bytes()
            read_only = not bool(path.stat().st_mode & 0o222)
        except OSError as exc:
            problems.append(f"prompt-use reservation could not be read: {path}: {exc}")
            continue
        reservation_records.append(
            {
                "name": path.name,
                "path": str(path),
                "bytes": len(raw),
                "sha256": _sha256_bytes(raw),
                "read_only": read_only,
            }
        )
        if not read_only:
            problems.append(f"prompt-use reservation is mutable: {path.name}")
        try:
            value = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"invalid prompt-use reservation {path.name}: {exc}")
            continue
        if not isinstance(value, dict) or value.get("schema") != PROMPT_USE_RESERVATION_SCHEMA:
            problems.append(f"invalid prompt-use reservation schema: {path.name}")
            continue
        run_id = str(value.get("run_id") or "").strip()
        base_prompt = str(value.get("base_prompt") or "").strip()
        try:
            prompt_position = int(value.get("prompt_position") or 0)
        except (TypeError, ValueError):
            prompt_position = 0
        stored_prompt_hash = str(value.get("base_prompt_sha256") or "").casefold()
        if not run_id or prompt_position < 1 or not base_prompt:
            problems.append(
                f"reservation lacks run_id, positive position, or base prompt: {path.name}"
            )
            continue
        prompt_hash = canonical_base_prompt_sha256(base_prompt)
        reservation_id = _reservation_id(run_id, prompt_position, prompt_hash)
        expected_name = f"{RESERVATION_PREFIX}{reservation_id}{RESERVATION_SUFFIX}"
        claim_record = value.get("prompt_run_claim")
        try:
            claim_owner_pid = (
                int(claim_record.get("owner_pid") or 0)
                if isinstance(claim_record, dict)
                else 0
            )
        except (TypeError, ValueError):
            claim_owner_pid = 0
        hash_bindings = (
            "history_snapshot_sha256",
            "history_pack_snapshot_sha256",
            "history_reservation_snapshot_sha256",
            "planned_prompt_set_sha256",
        )
        invalid_bindings = [
            key
            for key in hash_bindings
            if not _SHA256.fullmatch(str(value.get(key) or "").casefold())
        ]
        binding_ok = (
            value.get("reservation_id") == reservation_id
            and path.name == expected_name
            and stored_prompt_hash == prompt_hash
            and value.get("base_prompt_hash_canonicalization") == CANONICALIZATION
            and bool(str(value.get("created_at_utc") or "").strip())
            and isinstance(claim_record, dict)
            and str(claim_record.get("run_id") or "") == run_id
            and claim_owner_pid > 0
            and bool(str(claim_record.get("claim_path") or "").strip())
            and not invalid_bindings
        )
        if not binding_ok:
            problems.append(
                f"prompt-use reservation binding mismatch: {path.name}"
                + (f" invalid_hash_fields={invalid_bindings}" if invalid_bindings else "")
            )
            continue
        run_position = (run_id, prompt_position)
        if run_position in seen_run_positions:
            problems.append(
                "conflicting prompt-use reservations for "
                f"run={run_id} position={prompt_position}: "
                f"{seen_run_positions[run_position]} and {path.name}"
            )
            continue
        if prompt_hash in seen_reservation_prompt_hashes:
            problems.append(
                "canonical prompt was reserved more than once: "
                f"{seen_reservation_prompt_hashes[prompt_hash]} and {path.name}"
            )
            continue
        seen_run_positions[run_position] = path.name
        seen_reservation_prompt_hashes[prompt_hash] = path.name
        valid_reservation_count += 1
        occurrences.setdefault(prompt_hash, []).append(
            {
                "source": "prompt_use_reservation",
                "reservation": path.name,
                "run_id": run_id,
                "prompt_position": prompt_position,
                "created_at_utc": value.get("created_at_utc"),
                "admit": None,
            }
        )

    unique_hashes = sorted(occurrences)
    pack_snapshot = _history_snapshot_sha256(pack_records)
    reservation_snapshot = _history_snapshot_sha256(reservation_records)
    combined_records = [
        {**record, "name": f"pack/{record['name']}"} for record in pack_records
    ] + [
        {**record, "name": f"reservation/{record['name']}"}
        for record in reservation_records
    ]
    return {
        "ok": not problems,
        "packs_dir": str(packs_dir),
        "reservations_dir": str(reservations_dir),
        "source_policy": (
            "canonical stamped JSONL packs plus immutable pre-delivery prompt-use "
            "reservations; mutable LATEST aliases excluded"
        ),
        "canonicalization": CANONICALIZATION,
        "history_pack_count": len(pack_records),
        "history_read_only_pack_count": sum(
            1 for record in pack_records if record["read_only"]
        ),
        "history_writable_legacy_pack_count": sum(
            1 for record in pack_records if not record["read_only"]
        ),
        "history_row_count": row_count,
        "history_reservation_file_count": len(reservation_records),
        "history_valid_reservation_count": valid_reservation_count,
        "history_observation_count": row_count + valid_reservation_count,
        "history_rows_without_stored_hash": rows_without_stored_hash,
        "history_stored_hash_scheme_counts": stored_hash_scheme_counts,
        "history_unique_prompt_count": len(unique_hashes),
        "history_prompt_hashes": unique_hashes,
        "history_prompt_set_sha256": _hash_set_sha256(unique_hashes),
        "history_pack_snapshot_sha256": pack_snapshot,
        "history_reservation_snapshot_sha256": reservation_snapshot,
        "history_snapshot_sha256": _history_snapshot_sha256(combined_records),
        "history_packs": pack_records,
        "history_reservations": reservation_records,
        "occurrences": occurrences,
        "problems": problems,
    }


def evaluate_scheduled_prompt_novelty(
    base_prompts: Iterable[Any],
    packs_dir: Path = DEFAULT_PACKS_DIR,
    reservations_dir: Path | None = None,
) -> dict[str, Any]:
    """Return a complete, receipt-ready novelty decision for one scheduled plan."""

    prompts = [str(prompt or "").strip() for prompt in base_prompts]
    history = load_prompt_history(packs_dir, reservations_dir)
    plan_hashes: list[str] = []
    empty_positions: list[int] = []
    for position, prompt in enumerate(prompts, start=1):
        if not prompt:
            empty_positions.append(position)
            continue
        plan_hashes.append(canonical_base_prompt_sha256(prompt))

    counts: dict[str, int] = {}
    for prompt_hash in plan_hashes:
        counts[prompt_hash] = counts.get(prompt_hash, 0) + 1
    duplicate_hashes = sorted(
        prompt_hash for prompt_hash, count in counts.items() if count > 1
    )
    history_hashes = set(history["history_prompt_hashes"])
    replayed_hashes = sorted(set(plan_hashes).intersection(history_hashes))
    novel_hashes = sorted(set(plan_hashes).difference(history_hashes))
    replayed = [
        {
            "base_prompt_sha256": prompt_hash,
            "plan_positions": [
                position
                for position, value in enumerate(plan_hashes, start=1)
                if value == prompt_hash
            ],
            "history_occurrences": history["occurrences"].get(prompt_hash, []),
        }
        for prompt_hash in replayed_hashes
    ]
    blockers = list(history["problems"])
    if empty_positions:
        blockers.append(f"empty base prompt at plan position(s): {empty_positions}")
    if duplicate_hashes:
        blockers.append(
            "scheduled plan repeats canonical base prompts within this run: "
            + ", ".join(duplicate_hashes)
        )
    if replayed_hashes:
        blockers.append(
            f"scheduled plan replays {len(replayed_hashes)} historical base prompt(s)"
        )
    ok = bool(prompts and not blockers and len(plan_hashes) == len(prompts))
    return {
        "schema": PREFLIGHT_SCHEMA,
        "requested": True,
        "ok": ok,
        "decision": "PASS" if ok else "BLOCK",
        "canonicalization": CANONICALIZATION,
        "planned_prompt_count": len(prompts),
        "planned_unique_prompt_count": len(set(plan_hashes)),
        "planned_prompt_hashes": plan_hashes,
        "planned_prompt_set_sha256": _hash_set_sha256(plan_hashes),
        "novel_prompt_count": len(novel_hashes),
        "novel_prompt_hashes": novel_hashes,
        "replayed_prompt_count": len(replayed_hashes),
        "replayed_prompt_hashes": replayed_hashes,
        "replayed": replayed,
        "in_plan_duplicate_count": len(duplicate_hashes),
        "in_plan_duplicate_hashes": duplicate_hashes,
        "history_pack_count": history["history_pack_count"],
        "history_read_only_pack_count": history["history_read_only_pack_count"],
        "history_writable_legacy_pack_count": history[
            "history_writable_legacy_pack_count"
        ],
        "history_row_count": history["history_row_count"],
        "history_reservation_file_count": history[
            "history_reservation_file_count"
        ],
        "history_valid_reservation_count": history[
            "history_valid_reservation_count"
        ],
        "history_observation_count": history["history_observation_count"],
        "history_unique_prompt_count": history["history_unique_prompt_count"],
        "history_prompt_hashes": history["history_prompt_hashes"],
        "history_prompt_set_sha256": history["history_prompt_set_sha256"],
        "history_pack_snapshot_sha256": history["history_pack_snapshot_sha256"],
        "history_reservation_snapshot_sha256": history[
            "history_reservation_snapshot_sha256"
        ],
        "history_snapshot_sha256": history["history_snapshot_sha256"],
        "history_packs": history["history_packs"],
        "history_reservations": history["history_reservations"],
        "history_rows_without_stored_hash": history[
            "history_rows_without_stored_hash"
        ],
        "history_stored_hash_scheme_counts": history[
            "history_stored_hash_scheme_counts"
        ],
        "blockers": blockers,
    }


def require_scheduled_prompt_novelty(preflight: dict[str, Any]) -> None:
    if preflight.get("ok") is True:
        return
    compact = {
        "decision": preflight.get("decision"),
        "planned_prompt_count": preflight.get("planned_prompt_count"),
        "novel_prompt_count": preflight.get("novel_prompt_count"),
        "replayed_prompt_count": preflight.get("replayed_prompt_count"),
        "replayed_prompt_hashes": preflight.get("replayed_prompt_hashes"),
        "history_pack_snapshot_sha256": preflight.get(
            "history_pack_snapshot_sha256"
        ),
        "history_reservation_snapshot_sha256": preflight.get(
            "history_reservation_snapshot_sha256"
        ),
        "history_snapshot_sha256": preflight.get("history_snapshot_sha256"),
        "blockers": preflight.get("blockers"),
    }
    raise PromptNoveltyBlocked(
        "scheduled prompt novelty preflight refused the run before chat/training side "
        "effects: " + json.dumps(compact, sort_keys=True)
    )


def template_base_prompts(
    template_path: Path,
    hours: int,
    trainings_per_hour: int,
    start_index: int = 1,
) -> list[str]:
    """Load exactly the base prompts a scheduled template would select."""

    from engel_ui_prompt_training_support import select_balanced_training_prompts

    if not 1 <= int(hours) <= 8:
        raise ValueError("hours must be from 1 through 8")
    if not 1 <= int(trainings_per_hour) <= 10:
        raise ValueError("trainings per hour must be from 1 through 10")
    payload = json.loads(Path(template_path).read_text(encoding="utf-8-sig"))
    cycles = payload.get("cycle_prompt_sets") if isinstance(payload, dict) else None
    controls = payload.get("scheduled_controls") if isinstance(payload, dict) else None
    available = len(cycles) if isinstance(cycles, list) else 0
    maximum_hours = (
        int(controls.get("maximum_hours") or available)
        if isinstance(controls, dict)
        else available
    )
    if not isinstance(cycles, list) or not 1 <= maximum_hours <= min(8, available):
        raise ValueError("template has an invalid scheduled maximum-hours contract")
    if hours > maximum_hours:
        raise ValueError(
            f"template supports at most {maximum_hours} scheduled hours; requested {hours}"
        )
    selected: list[str] = []
    for scheduled_hour in range(1, hours + 1):
        cycle = cycles[scheduled_hour - 1]
        prompts = cycle.get("prompts") if isinstance(cycle, dict) else None
        if not isinstance(prompts, list):
            raise ValueError(f"scheduled cycle {scheduled_hour} has no prompt list")
        clean = [str(item).strip() for item in prompts if str(item).strip()]
        selected.extend(
            prompt
            for _position, prompt in select_balanced_training_prompts(
                clean, trainings_per_hour
            )
        )
    start = max(1, int(start_index))
    remaining = selected[start - 1 :]
    if not remaining:
        raise ValueError(f"start index {start} is past the scheduled prompt plan")
    return remaining


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--hours", type=int, default=1)
    parser.add_argument("--trainings-per-hour", type=int, default=6)
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--packs-dir", type=Path, default=DEFAULT_PACKS_DIR)
    parser.add_argument("--reservations-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    prompts = template_base_prompts(
        args.template,
        args.hours,
        args.trainings_per_hour,
        args.start_index,
    )
    receipt = evaluate_scheduled_prompt_novelty(
        prompts, args.packs_dir, args.reservations_dir
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
