#!/usr/bin/env python3
"""CT246-only Engel LoRA proof run.

This runs on engel-ai-main inside CT246. It does not use RunPod, CT245, the
offline-vault lane, or auto-deploy. A training run requires the exact approval phrase
from tools/future_train_engel_lora_README_ONLY.md.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APPROVAL_PHRASE = "APPROVE_ENGEL_LOCAL_LLM_LORA_TRAINING_RUN_V1"

ROOT = Path("/opt/engel")
TRAIN_ROOT = ROOT / "llm_training"
REPORT_ROOT = ROOT / "reports" / "llm_training"
MODEL_DEFAULT = ROOT / "models-active" / "hf-src" / "Qwen2.5-1.5B-Instruct"
DATASET_DIR = TRAIN_ROOT / "datasets" / "latest"
VENV_PY = TRAIN_ROOT / "20260702_deep_reasoning" / "venv" / "bin" / "python"
TRAIN_SCRIPT = TRAIN_ROOT / "scripts" / "train_lora.py"
EVAL_SCRIPT = TRAIN_ROOT / "scripts" / "eval_suite.py"
DATASET_BUILDER = ROOT / "tools" / "engel_build_training_dataset.py"
CANONICAL_TRAINER = ROOT / "tools" / "engel_ct246_train_lora.py"
# (2026-08-07) Adapter lineage. Budget-capped CPU runs cannot reach an epoch alone, and
# every proof run used to re-init LoRA from zero -- serial runs THREW AWAY each other's
# progress. Only PROOF_LATEST is eligible as a resume base. CANDIDATE_LATEST makes newly
# trained weights discoverable without calling them proven before evaluation finishes.
PROOF_ADAPTER_POINTER = TRAIN_ROOT / "adapters" / "PROOF_LATEST.json"
CANDIDATE_ADAPTER_POINTER = TRAIN_ROOT / "adapters" / "CANDIDATE_LATEST.json"
ADAPTER_POINTER_SCHEMA = "engel_lora_adapter_pointer_v3"
ARTIFACT_MANIFEST_SCHEMA = "engel_artifact_hash_manifest_v1"
MODEL_CARD_MANIFEST_SCHEMA = "engel_model_card_hash_manifest_v1"
MODEL_CARD_NAME = "ENGEL_MODEL_CARD.json"
PROOF_RECEIPT_SCHEMA = "engel_ct246_local_lora_model_weight_improvement_receipt_v1"
# Compatibility for existing imports/verifiers. This alias deliberately remains the
# proven pointer; a failed candidate must never become the next lineage base.
ADAPTER_POINTER = PROOF_ADAPTER_POINTER


# (2026-08-09, operator: Engel's trained models carry ENGEL names.) Naming is METADATA,
# never a path move: the lineage pointer, model-inventory verifier, ModelExpress seats,
# and the release manifest all pin paths, so a physical rename would orphan the lineage.
# Every candidate gets an ENGEL_MODEL_CARD.json inside its adapter/ and merged/ dirs;
# the card is finalized as proven only after every gate passes. Name, lineage, hashes,
# base-model provenance, and license evidence travel with the artifact.
def _slug(value: str, limit: int = 48) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return (cleaned[:limit].rstrip("-") or "llm")


def engel_model_name(
    base_model: Path, lineage: int, artifact_digest: str = "",
) -> str:
    """Return a collision-resistant Engel identity without renaming any paths."""
    family_slug = _slug(Path(base_model).name)
    digest_hex = re.sub(r"[^a-fA-F0-9]", "", artifact_digest).lower()
    if len(digest_hex) < 8:
        digest_hex = hashlib.sha256(
            str(Path(base_model).expanduser()).encode("utf-8")
        ).hexdigest()
    return (
        f"engel-core-{family_slug}-lineage{int(lineage)}-"
        f"{digest_hex[:10]}"
    )


def write_engel_model_card(
    out_dir: Path,
    name: str,
    receipt: dict[str, Any],
    base_model: Path,
    artifact_status: str = "candidate",
) -> list[str]:
    license_paths = sorted(
        [p for p in base_model.glob("LICENSE*") if p.is_file()]
        + [p for p in base_model.glob("NOTICE*") if p.is_file()]
    )
    license_files = [str(path) for path in license_paths]
    license_hashes = [
        {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in license_paths
    ]
    proof_gates = receipt.get("proof_gates") or {}
    card = {
        "schema": "engel_model_card_v2",
        "name": name,
        "artifact_id": f"{name}-{receipt.get('run_stamp') or stamp()}",
        "artifact_status": artifact_status,
        "proof_claimed": artifact_status == "proven",
        "created_at_utc": receipt.get("started_at_utc") or iso_now(),
        "updated_at_utc": iso_now(),
        "finalized_at_utc": (
            iso_now() if proof_gates.get("evaluation_suite") is not None else None
        ),
        "lineage": receipt.get("adapter_lineage"),
        "resumed_from": receipt.get("resumed_from"),
        "base_model_path": str(base_model),
        "base_model_family": base_model.name,
        "base_license_files": license_files,
        "base_license_hashes": license_hashes,
        "provenance": (
            f"LoRA fine-tune (PEFT) of {base_model.name}, trained entirely on CT246 "
            "with Hugging Face offline pins from Engel's gate-admitted receipts corpus. "
            "The merged model contains the base weights plus this adapter's delta; the "
            "base model's license and attribution continue to apply to those weights."
        ),
        "train_summary": receipt.get("train_summary") or {},
        "proof_gates": proof_gates,
        "core_hashes": receipt.get("core_hashes") or {},
        "adapter_artifacts_verified": bool(
            proof_gates.get(
                "adapter_artifacts_verified",
                (receipt.get("adapter_artifact_manifest") or {}).get("verified"),
            )
        ),
        "proof_pointer_advanced": bool(receipt.get("proof_pointer_advanced")),
        "run_receipt": receipt.get("receipt_path") or "",
        "rename_note": (
            "Physical renames must update CANDIDATE_LATEST.json, PROOF_LATEST.json, "
            "and every path consumer; until then this card IS the model's name."
        ),
    }
    written = []
    for target in (out_dir / "adapter", out_dir / "merged"):
        if target.is_dir():
            path = target / "ENGEL_MODEL_CARD.json"
            write_json(path, card)
            written.append(str(path))
    return written


def finalize_model_card_artifacts(
    out_dir: Path,
    name: str,
    receipt: dict[str, Any],
    base_model: Path,
    artifact_status: str,
) -> list[str]:
    """Write the final card pair and bind those exact bytes in the receipt.

    The weight manifest deliberately excludes the mutable metadata card.  Keeping
    card finalization in one helper prevents a caller from rewriting a card after
    its separate release manifest has been calculated.
    """
    written = write_engel_model_card(
        out_dir,
        name,
        receipt,
        base_model,
        artifact_status=artifact_status,
    )
    receipt["engel_model_cards"] = written
    receipt["model_card_artifact_manifest"] = model_card_hash_manifest(out_dir)
    return written


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _hash_record_set(records: list[dict[str, Any]]) -> str:
    """Hash a sorted file inventory, including names, sizes, and content hashes."""
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: str(item["relative_path"])):
        digest.update(str(record["relative_path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["bytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).upper().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest().upper()


def artifact_hash_manifest(
    root: Path,
    required_relative_paths: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build and immediately verify a complete, model-card-excluding manifest."""
    root = Path(root)
    root_resolved = root.resolve()
    records: list[dict[str, Any]] = []
    for file in sorted(root.rglob("*")):
        if file.is_symlink():
            raise RuntimeError(f"artifact tree contains a symlink: {file}")
        if not file.is_file():
            continue
        resolved = file.resolve()
        try:
            relative = resolved.relative_to(root_resolved).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"artifact file escapes its root: {file}") from exc
        if relative == MODEL_CARD_NAME:
            continue
        records.append(
            {
                "path": str(file),
                "relative_path": relative,
                "bytes": file.stat().st_size,
                "sha256": sha256_file(file),
            }
        )
    present = {str(record["relative_path"]) for record in records}
    missing = [item for item in required_relative_paths if item not in present]
    if missing:
        raise RuntimeError("required artifact files missing: " + ", ".join(missing))
    manifest: dict[str, Any] = {
        "schema": ARTIFACT_MANIFEST_SCHEMA,
        "root": str(root),
        "excluded_relative_paths": [MODEL_CARD_NAME],
        "file_count": len(records),
        "artifact_set_sha256": _hash_record_set(records),
        "files": records,
        "verified": True,
    }
    verify_artifact_hash_manifest(root, manifest)
    manifest["verified_at_utc"] = iso_now()
    return manifest


def verify_artifact_hash_manifest(root: Path, manifest: dict[str, Any]) -> None:
    """Fail closed if an artifact inventory no longer matches bytes on disk."""
    root = Path(root)
    if manifest.get("schema") != ARTIFACT_MANIFEST_SCHEMA:
        raise RuntimeError("artifact hash manifest schema is not current")
    if manifest.get("verified") is not True:
        raise RuntimeError("artifact hash manifest is not marked verified")
    try:
        manifest_root = Path(str(manifest.get("root") or "")).resolve(strict=True)
        actual_root = root.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"artifact hash manifest root is unavailable: {exc}") from exc
    if manifest_root != actual_root:
        raise RuntimeError("artifact hash manifest root differs from the artifact tree")
    excluded = manifest.get("excluded_relative_paths")
    if not isinstance(excluded, list) or any(
        not isinstance(item, str) or not item for item in excluded
    ):
        raise RuntimeError("artifact hash manifest exclusion list is malformed")
    if sorted(excluded) != [MODEL_CARD_NAME]:
        raise RuntimeError("artifact model-card exclusion set changed")
    expected_records = manifest.get("files")
    if not isinstance(expected_records, list) or not expected_records:
        raise RuntimeError("artifact hash manifest is empty")
    expected: dict[str, dict[str, Any]] = {}
    for record in expected_records:
        if not isinstance(record, dict):
            raise RuntimeError("artifact hash manifest contains a non-object record")
        relative = str(record.get("relative_path") or "")
        if not relative or relative in expected:
            raise RuntimeError(f"invalid or duplicate artifact path: {relative!r}")
        expected[relative] = record

    actual_paths: set[str] = set()
    for file in root.rglob("*"):
        if file.is_symlink():
            raise RuntimeError(f"artifact tree contains a symlink: {file}")
        if file.is_file():
            relative = file.relative_to(root).as_posix()
            if relative != MODEL_CARD_NAME:
                actual_paths.add(relative)
    if actual_paths != set(expected):
        missing = sorted(set(expected) - actual_paths)
        extra = sorted(actual_paths - set(expected))
        raise RuntimeError(
            f"artifact file set changed; missing={missing!r}, extra={extra!r}"
        )

    verified_records: list[dict[str, Any]] = []
    for relative in sorted(expected):
        record = expected[relative]
        file = root / relative
        size = file.stat().st_size
        digest = sha256_file(file)
        expected_size = record.get("bytes")
        if not isinstance(expected_size, int) or size != expected_size:
            raise RuntimeError(f"artifact byte count changed: {relative}")
        if digest != str(record.get("sha256") or "").upper():
            raise RuntimeError(f"artifact sha256 changed: {relative}")
        verified_records.append(
            {
                "relative_path": relative,
                "bytes": size,
                "sha256": digest,
            }
        )
    if _hash_record_set(verified_records) != str(
        manifest.get("artifact_set_sha256") or ""
    ).upper():
        raise RuntimeError("artifact set sha256 changed")


def model_card_hash_manifest(out_dir: Path) -> dict[str, Any]:
    """Hash-bind the finalized adapter and merged model cards as a separate set.

    Model cards are deliberately excluded from the model-weight tree used by the
    canary/conversion contract.  They are still release artifacts: this manifest
    makes later edits detectable without creating a circular card -> manifest ->
    card dependency.
    """
    out_dir = Path(out_dir)
    records: list[dict[str, Any]] = []
    for relative in (
        f"adapter/{MODEL_CARD_NAME}",
        f"merged/{MODEL_CARD_NAME}",
    ):
        path = out_dir / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"finalized model card missing or unsafe: {relative}")
        records.append(
            {
                "path": str(path),
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest: dict[str, Any] = {
        "schema": MODEL_CARD_MANIFEST_SCHEMA,
        "root": str(out_dir),
        "file_count": len(records),
        "artifact_set_sha256": _hash_record_set(records),
        "files": records,
        "verified": False,
    }
    # The verifier requires verified=True, so mark the completed inventory before
    # re-reading every byte. No caller observes this local object in between.
    manifest["verified"] = True
    verify_model_card_hash_manifest(out_dir, manifest)
    manifest["verified_at_utc"] = iso_now()
    return manifest


def verify_model_card_hash_manifest(out_dir: Path, manifest: dict[str, Any]) -> None:
    """Verify the exact finalized model-card pair without touching model weights."""
    out_dir = Path(out_dir)
    if manifest.get("schema") != MODEL_CARD_MANIFEST_SCHEMA:
        raise RuntimeError("model-card manifest schema is not current")
    if manifest.get("verified") is not True:
        raise RuntimeError("model-card manifest is not marked verified")
    try:
        manifest_root = Path(str(manifest.get("root") or "")).resolve(strict=True)
        actual_root = out_dir.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"model-card manifest root is unavailable: {exc}") from exc
    if manifest_root != actual_root:
        raise RuntimeError("model-card manifest root differs from the candidate output")
    expected_records = manifest.get("files")
    if not isinstance(expected_records, list) or len(expected_records) != 2:
        raise RuntimeError("model-card manifest must contain exactly two cards")
    expected_names = {
        f"adapter/{MODEL_CARD_NAME}",
        f"merged/{MODEL_CARD_NAME}",
    }
    by_name: dict[str, dict[str, Any]] = {}
    for record in expected_records:
        if not isinstance(record, dict):
            raise RuntimeError("model-card manifest contains a non-object record")
        relative = str(record.get("relative_path") or "")
        if relative not in expected_names or relative in by_name:
            raise RuntimeError(f"invalid or duplicate model-card path: {relative!r}")
        by_name[relative] = record
    if set(by_name) != expected_names:
        raise RuntimeError("model-card manifest does not bind both release cards")
    verified_records: list[dict[str, Any]] = []
    for relative in sorted(by_name):
        path = out_dir / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"model card changed or disappeared: {relative}")
        size = path.stat().st_size
        digest = sha256_file(path)
        record = by_name[relative]
        if not isinstance(record.get("bytes"), int) or record["bytes"] != size:
            raise RuntimeError(f"model-card byte count changed: {relative}")
        if digest != str(record.get("sha256") or "").upper():
            raise RuntimeError(f"model-card sha256 changed: {relative}")
        verified_records.append(
            {"relative_path": relative, "bytes": size, "sha256": digest}
        )
    if _hash_record_set(verified_records) != str(
        manifest.get("artifact_set_sha256") or ""
    ).upper():
        raise RuntimeError("model-card artifact set sha256 changed")


def core_hashes(
    receipt: dict[str, Any], base_model: Path, train_summary_path: Path,
) -> dict[str, Any]:
    """Return compact hashes suitable for pointers and model cards."""
    adapter_manifest = receipt.get("adapter_artifact_manifest") or {}
    adapter_model = next(
        (
            record
            for record in adapter_manifest.get("files", [])
            if record.get("relative_path") == "adapter_model.safetensors"
        ),
        {},
    )
    hashes: dict[str, Any] = {
        "adapter_artifact_set_sha256": adapter_manifest.get(
            "artifact_set_sha256"
        ),
        "adapter_model_sha256": adapter_model.get("sha256"),
        "dataset_files": receipt.get("training_dataset_hashes")
        or (receipt.get("preflight") or {}).get("dataset_hashes", {}),
    }
    base_config = Path(base_model) / "config.json"
    if base_config.is_file():
        hashes["base_model_config_sha256"] = sha256_file(base_config)
    if train_summary_path.is_file():
        hashes["train_summary_sha256"] = sha256_file(train_summary_path)
    eval_manifest = receipt.get("eval_artifact_manifest") or {}
    if eval_manifest.get("artifact_set_sha256"):
        hashes["evaluation_artifact_set_sha256"] = eval_manifest[
            "artifact_set_sha256"
        ]
    return hashes


def adapter_pointer_payload(
    receipt: dict[str, Any],
    out_dir: Path,
    base_model: Path,
    model_name: str,
    artifact_status: str,
) -> dict[str, Any]:
    """Build the shared v3 pointer shape for candidate and proven artifacts."""
    core = receipt.get("core_hashes") or {}
    card_manifest = receipt.get("model_card_artifact_manifest") or {}
    receipt_path = Path(str(receipt.get("receipt_path") or ""))
    receipt_sha256 = sha256_file(receipt_path) if receipt_path.is_file() else None
    return {
        "schema": ADAPTER_POINTER_SCHEMA,
        "artifact_status": artifact_status,
        "adapter": str(out_dir / "adapter"),
        "merged": str(out_dir / "merged"),
        "model": str(base_model),
        "lineage": receipt.get("adapter_lineage"),
        "resumed_from": receipt.get("resumed_from"),
        "run_receipt": receipt.get("receipt_path"),
        "run_receipt_sha256": receipt_sha256,
        "engel_model_name": model_name,
        "adapter_artifact_manifest": receipt.get("adapter_artifact_manifest"),
        "model_card_artifact_manifest": card_manifest,
        "core_hashes": core,
        "resume_bindings": {
            "base_model_config_sha256": core.get("base_model_config_sha256"),
            "adapter_artifact_set_sha256": core.get(
                "adapter_artifact_set_sha256"
            ),
            "adapter_model_sha256": core.get("adapter_model_sha256"),
            "model_card_artifact_set_sha256": card_manifest.get(
                "artifact_set_sha256"
            ),
            "run_receipt_sha256": receipt_sha256,
        },
        "proof_gates": receipt.get("proof_gates") or {},
        "model_cards": receipt.get("engel_model_cards") or [],
        "updated_at_utc": iso_now(),
    }


def load_proven_resume_pointer(pointer_path: Path, model: Path) -> dict[str, Any]:
    """Load only a fully hash-bound v3 proven pointer from the CT246 SSD.

    A present pointer is authority, not a hint. Legacy, malformed, off-volume, or
    hash-inconsistent state therefore raises and stops the cycle; silently falling
    back to a fresh adapter would hide lineage loss and could train on tampered bytes.
    """
    state: dict[str, Any] = {
        "adapter": "",
        "lineage": 0,
        "pointer_path": str(pointer_path),
        "hash_verified": False,
        "model_cards_hash_verified": False,
        "receipt_hash_verified": False,
    }
    pointer_path = Path(pointer_path).resolve(strict=False)
    require_ct246_ssd_path(pointer_path)
    if not pointer_path.is_file():
        return state
    if pointer_path.is_symlink():
        raise RuntimeError("proven adapter pointer may not be a symlink")
    try:
        pointer_bytes = pointer_path.read_bytes()
        pointer = json.loads(pointer_bytes.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"proven adapter pointer is unreadable: {exc}") from exc
    if not isinstance(pointer, dict):
        raise RuntimeError("proven adapter pointer payload is not an object")
    if pointer.get("schema") != ADAPTER_POINTER_SCHEMA:
        raise RuntimeError(
            "proven adapter pointer is legacy/unversioned; explicit migration is required"
        )
    if pointer.get("artifact_status") != "proven":
        raise RuntimeError("proven adapter pointer does not mark the artifact proven")
    if (pointer.get("proof_gates") or {}).get("passed") is not True:
        raise RuntimeError("proven adapter pointer does not carry passed proof gates")

    try:
        model_resolved = Path(model).resolve(strict=True)
        pointer_model = Path(str(pointer.get("model") or "")).resolve(strict=True)
        adapter = Path(str(pointer.get("adapter") or "")).resolve(strict=True)
        merged = Path(str(pointer.get("merged") or "")).resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"proven adapter pointer path is unavailable: {exc}") from exc
    for path in (model_resolved, pointer_model, adapter, merged):
        require_ct246_ssd_path(path)
    if pointer_model != model_resolved:
        raise RuntimeError("proven adapter pointer is bound to a different base model")
    if not adapter.is_dir() or not merged.is_dir() or adapter.parent != merged.parent:
        raise RuntimeError("proven adapter pointer has an invalid adapter/merged layout")
    if not (adapter / "adapter_model.safetensors").is_file():
        raise RuntimeError("proven adapter pointer lacks adapter_model.safetensors")

    manifest = pointer.get("adapter_artifact_manifest")
    if not isinstance(manifest, dict):
        raise RuntimeError("proven adapter pointer lacks a verified artifact manifest")
    verify_artifact_hash_manifest(adapter, manifest)

    card_manifest = pointer.get("model_card_artifact_manifest")
    if not isinstance(card_manifest, dict):
        raise RuntimeError("proven adapter pointer lacks a model-card hash manifest")
    verify_model_card_hash_manifest(adapter.parent, card_manifest)

    core = pointer.get("core_hashes")
    bindings = pointer.get("resume_bindings")
    if not isinstance(core, dict) or not isinstance(bindings, dict):
        raise RuntimeError("proven adapter pointer lacks resume hash bindings")
    adapter_record = next(
        (
            record
            for record in manifest.get("files") or []
            if isinstance(record, dict)
            and record.get("relative_path") == "adapter_model.safetensors"
        ),
        {},
    )
    expected_bindings = {
        "base_model_config_sha256": sha256_file(model_resolved / "config.json"),
        "adapter_artifact_set_sha256": str(
            manifest.get("artifact_set_sha256") or ""
        ).upper(),
        "adapter_model_sha256": str(adapter_record.get("sha256") or "").upper(),
        "model_card_artifact_set_sha256": str(
            card_manifest.get("artifact_set_sha256") or ""
        ).upper(),
    }
    if not expected_bindings["adapter_model_sha256"]:
        raise RuntimeError("adapter manifest does not bind adapter_model.safetensors")
    for key, expected in expected_bindings.items():
        actual = str(bindings.get(key) or "").upper()
        if actual != expected:
            raise RuntimeError(f"proven adapter resume binding mismatch: {key}")
        # Model-card hashes live outside core_hashes to avoid a card self-reference.
        if key != "model_card_artifact_set_sha256" and str(
            core.get(key) or ""
        ).upper() != expected:
            raise RuntimeError(f"proven adapter core hash mismatch: {key}")

    try:
        receipt_path = Path(str(pointer.get("run_receipt") or "")).resolve(
            strict=True
        )
    except OSError as exc:
        raise RuntimeError(f"proven adapter run receipt is unavailable: {exc}") from exc
    require_ct246_ssd_path(receipt_path)
    if (
        receipt_path.is_symlink()
        or not receipt_path.is_file()
        or "LATEST" in receipt_path.name.upper()
    ):
        raise RuntimeError("proven adapter pointer lacks an immutable stamped run receipt")
    try:
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"proven adapter run receipt is unreadable: {exc}") from exc
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest().upper()
    if (
        str(pointer.get("run_receipt_sha256") or "").upper() != receipt_sha256
        or str(bindings.get("run_receipt_sha256") or "").upper()
        != receipt_sha256
    ):
        raise RuntimeError("proven adapter run receipt sha256 binding mismatch")
    if not isinstance(receipt, dict) or receipt.get("schema") != PROOF_RECEIPT_SCHEMA:
        raise RuntimeError("proven adapter run receipt schema is invalid")
    if not all(
        (
            receipt.get("ok") is True,
            receipt.get("artifact_status") == "proven",
            receipt.get("proof_pointer_advanced") is True,
            (receipt.get("proof_gates") or {}).get("passed") is True,
        )
    ):
        raise RuntimeError("proven adapter run receipt is not finalized")
    receipt_summary = receipt.get("train_summary") or {}
    receipt_adapter = str(
        receipt.get("new_adapter_path") or receipt_summary.get("adapter") or ""
    )
    receipt_merged = str(
        receipt.get("new_merged_path") or receipt_summary.get("merged") or ""
    )
    try:
        receipt_adapter_path = Path(receipt_adapter).resolve(strict=True)
        receipt_merged_path = Path(receipt_merged).resolve(strict=True)
        receipt_model_path = Path(str(receipt.get("base_model") or "")).resolve(
            strict=True
        )
    except OSError as exc:
        raise RuntimeError(f"proven adapter receipt path is unavailable: {exc}") from exc
    for path in (receipt_adapter_path, receipt_merged_path, receipt_model_path):
        require_ct246_ssd_path(path)
    if receipt_adapter_path != adapter or receipt_merged_path != merged:
        raise RuntimeError("proven adapter run receipt paths differ from the pointer")
    if receipt_model_path != model_resolved:
        raise RuntimeError("proven adapter run receipt base model differs from the pointer")
    if int(receipt.get("adapter_lineage") or 0) != int(pointer.get("lineage") or 0):
        raise RuntimeError("proven adapter run receipt lineage differs from the pointer")
    receipt_manifest = receipt.get("adapter_artifact_manifest") or {}
    receipt_cards = receipt.get("model_card_artifact_manifest") or {}
    receipt_core = receipt.get("core_hashes") or {}
    if str(receipt_manifest.get("artifact_set_sha256") or "").upper() != str(
        manifest.get("artifact_set_sha256") or ""
    ).upper() or str(receipt_cards.get("artifact_set_sha256") or "").upper() != str(
        card_manifest.get("artifact_set_sha256") or ""
    ).upper():
        raise RuntimeError("proven adapter run receipt hashes differ from the pointer")
    for key, expected in expected_bindings.items():
        if key == "model_card_artifact_set_sha256":
            continue
        if str(receipt_core.get(key) or "").upper() != expected:
            raise RuntimeError(f"proven adapter run receipt core hash mismatch: {key}")

    for record in card_manifest.get("files") or []:
        card = json.loads((adapter.parent / str(record["relative_path"])).read_text(encoding="utf-8"))
        if not isinstance(card, dict) or not all(
            (
                card.get("schema") == "engel_model_card_v2",
                card.get("artifact_status") == "proven",
                card.get("proof_claimed") is True,
                card.get("proof_pointer_advanced") is True,
                card.get("name") == pointer.get("engel_model_name"),
            )
        ):
            raise RuntimeError("proven adapter model card is not finalized and bound")

    state["pointer_sha256"] = hashlib.sha256(pointer_bytes).hexdigest().upper()
    state["run_receipt"] = str(receipt_path)
    state["run_receipt_sha256"] = receipt_sha256
    state["hash_verified"] = True
    state["model_cards_hash_verified"] = True
    state["receipt_hash_verified"] = True
    state["adapter"] = str(adapter)
    state["lineage"] = int(pointer.get("lineage") or 0)
    return state


def require_ct246_ssd_path(path: Path) -> None:
    resolved = Path(path).expanduser()
    text = str(resolved)
    banned = ("/mnt/" + "engel-vault", "/mnt/ct245-offline-vault", "/workspace", "/runpod")
    if any(text == item or text.startswith(item + "/") for item in banned):
        raise RuntimeError(f"refusing non-CT246-SSD path: {resolved}")
    if not text.startswith("/opt/engel/"):
        raise RuntimeError(f"refusing path outside /opt/engel: {resolved}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    require_ct246_ssd_path(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def install_canonical_trainer() -> dict[str, Any]:
    """Atomically install and byte-verify the reviewed CT246 trainer.

    The historical training path remains stable for existing receipts and commands,
    but it is no longer an independent mutable program. Every preflight refreshes it
    from the repo-owned source and refuses to proceed unless both hashes match.
    """
    source = Path(CANONICAL_TRAINER)
    target = Path(TRAIN_SCRIPT)
    require_ct246_ssd_path(source)
    require_ct246_ssd_path(target)
    if not source.is_file():
        raise RuntimeError(f"canonical LoRA trainer missing: {source}")
    source_hash = sha256_file(source)
    source_bytes = source.stat().st_size
    target.parent.mkdir(parents=True, exist_ok=True)

    already_current = (
        target.is_file()
        and target.stat().st_size == source_bytes
        and sha256_file(target) == source_hash
    )
    if not already_current:
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        try:
            with source.open("rb") as reader, temporary.open("wb") as writer:
                for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                    writer.write(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            os.chmod(temporary, 0o750)
            if temporary.stat().st_size != source_bytes:
                raise RuntimeError("canonical LoRA trainer staging size mismatch")
            if sha256_file(temporary) != source_hash:
                raise RuntimeError("canonical LoRA trainer staging hash mismatch")
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

    installed_hash = sha256_file(target) if target.is_file() else ""
    if (
        not target.is_file()
        or target.stat().st_size != source_bytes
        or installed_hash != source_hash
    ):
        raise RuntimeError("installed LoRA trainer does not match canonical source")
    return {
        "source": str(source),
        "target": str(target),
        "bytes": source_bytes,
        "canonical_sha256": source_hash,
        "installed_sha256": installed_hash,
        "installed": not already_current,
        "verified": True,
    }


def line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def tree_records(path: Path, max_files: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for file in sorted(path.rglob("*")):
        if not file.is_file():
            continue
        records.append(
            {
                "path": str(file),
                "relative_path": file.relative_to(path).as_posix(),
                "bytes": file.stat().st_size,
                "sha256": sha256_file(file),
            }
        )
        if len(records) >= max_files:
            break
    return records


def module_check() -> dict[str, Any]:
    code = r"""
import importlib.util, json, sys
mods = {}
for name in ["torch", "transformers", "peft", "datasets", "accelerate", "safetensors"]:
    mods[name] = bool(importlib.util.find_spec(name))
try:
    import torch
    torch_info = {"version": torch.__version__, "cuda_available": bool(torch.cuda.is_available())}
except Exception as exc:
    torch_info = {"error": repr(exc)}
print(json.dumps({"python": sys.executable, "modules": mods, "torch": torch_info}, sort_keys=True))
"""
    completed = subprocess.run([str(VENV_PY), "-c", code], capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    parsed: dict[str, Any] = {}
    try:
        parsed = json.loads((completed.stdout or "{}").strip())
    except Exception:
        parsed = {"stdout": completed.stdout, "stderr": completed.stderr}
    parsed["returncode"] = completed.returncode
    return parsed


def run_cmd(name: str, cmd: list[str], timeout_s: int, log_path: Path) -> dict[str, Any]:
    require_ct246_ssd_path(log_path)
    started = time.perf_counter()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "name": name,
        "command": [str(item) for item in cmd],
        "started_at_utc": iso_now(),
        "log_path": str(log_path),
        "timeout_seconds": timeout_s,
    }
    with log_path.open("a", encoding="utf-8") as log:
        try:
            completed = subprocess.run(
                [str(item) for item in cmd],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            record["returncode"] = completed.returncode
            record["ok"] = completed.returncode == 0
        except subprocess.TimeoutExpired:
            record["ok"] = False
            record["error"] = f"timed out after {timeout_s}s"
        except Exception as exc:
            record["ok"] = False
            record["error"] = repr(exc)
    record["finished_at_utc"] = iso_now()
    record["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    try:
        record["log_tail"] = log_path.read_text(encoding="utf-8", errors="replace")[-5000:]
    except Exception:
        record["log_tail"] = ""
    return record


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    trainer_install = install_canonical_trainer()
    model = Path(args.model).resolve()
    for path in (
        TRAIN_ROOT,
        REPORT_ROOT,
        model,
        DATASET_DIR,
        VENV_PY,
        CANONICAL_TRAINER,
        TRAIN_SCRIPT,
        EVAL_SCRIPT,
    ):
        require_ct246_ssd_path(path)
    train_file = DATASET_DIR / "sft_train.jsonl"
    val_file = DATASET_DIR / "sft_val.jsonl"
    negative_file = DATASET_DIR / "negative_eval.jsonl"
    manifest_file = DATASET_DIR / "dataset_manifest.json"
    payload = {
        "ok": True,
        "schema": "engel_ct246_lora_proof_preflight_v1",
        "created_at_utc": iso_now(),
        "origin": args.origin,
        "ct246_ssd_only": True,
        "runpod_used": False,
        "ct245_used": False,
        "offline_ct245_vault_used": False,
        "model": str(model),
        "model_config_present": (model / "config.json").is_file(),
        "venv_python": str(VENV_PY),
        "canonical_trainer": trainer_install,
        "module_check": module_check(),
        "dataset_dir": str(DATASET_DIR),
        "train_records": line_count(train_file),
        "val_records": line_count(val_file),
        "dataset_manifest": {},
        "dataset_hashes": {},
        "approval_required_for_training": APPROVAL_PHRASE,
        "training_not_started": True,
    }
    if manifest_file.is_file():
        payload["dataset_manifest"] = json.loads(manifest_file.read_text(encoding="utf-8"))
    for file in (train_file, val_file, negative_file, manifest_file):
        if file.is_file():
            payload["dataset_hashes"][file.name] = {"bytes": file.stat().st_size, "sha256": sha256_file(file)}
    required_modules = payload["module_check"].get("modules", {})
    missing = [name for name in ("torch", "transformers", "peft", "datasets", "accelerate", "safetensors") if not required_modules.get(name)]
    blockers = []
    if missing:
        blockers.append("missing training modules: " + ", ".join(missing))
    if not payload["model_config_present"]:
        blockers.append("base model config missing")
    if payload["train_records"] < 1 or payload["val_records"] < 1:
        blockers.append("latest train/val dataset missing")
    payload["blockers"] = blockers
    payload["ok"] = not blockers
    out = REPORT_ROOT / f"ENGEL_CT246_LORA_PREFLIGHT_{stamp()}.json"
    payload["receipt_path"] = str(out)
    write_json(out, payload)
    write_json(REPORT_ROOT / "ENGEL_CT246_LORA_PREFLIGHT_LATEST.json", payload)
    return payload


def train(args: argparse.Namespace) -> dict[str, Any]:
    if args.approval != APPROVAL_PHRASE:
        raise RuntimeError(f"training requires exact approval phrase: {APPROVAL_PHRASE}")
    pf = preflight(args)
    if pf.get("ok") is not True:
        raise RuntimeError("preflight failed: " + "; ".join(pf.get("blockers", [])))

    run_stamp = stamp()
    run_dir = TRAIN_ROOT / "proof_runs" / run_stamp
    out_dir = run_dir / "out"
    log_dir = run_dir / "logs"
    for path in (run_dir, out_dir, log_dir):
        require_ct246_ssd_path(path)
    run_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    receipt: dict[str, Any] = {
        "ok": False,
        "schema": "engel_ct246_local_lora_model_weight_improvement_receipt_v1",
        "approval": args.approval,
        "origin": args.origin,
        "started_at_utc": iso_now(),
        "run_stamp": run_stamp,
        "run_dir": str(run_dir),
        "base_model": str(Path(args.model).resolve()),
        "ct246_ssd_only": True,
        "runpod_used": False,
        "ct245_used": False,
        "offline_ct245_vault_used": False,
        "auto_deployed": False,
        "deploy_note": "No auto-deploy. Operator must review receipt/eval before routing chat to this adapter.",
        "model_weight_improvement_claimed": False,
        "phases": [],
        "preflight": pf,
    }
    receipt_path = REPORT_ROOT / f"ENGEL_CT246_LORA_PROOF_{run_stamp}.json"
    latest_path = REPORT_ROOT / "ENGEL_CT246_LORA_PROOF_LATEST.json"
    receipt["receipt_path"] = str(receipt_path)
    receipt["candidate_pointer"] = str(CANDIDATE_ADAPTER_POINTER)
    receipt["proof_pointer"] = str(PROOF_ADAPTER_POINTER)
    receipt["proof_pointer_advanced"] = False

    def save_stamped() -> None:
        receipt["elapsed_seconds"] = round(time.perf_counter() - t0, 3)
        write_json(receipt_path, receipt)

    def publish_latest() -> None:
        # Do not mutate the payload here: PROOF_LATEST hash-binds the stamped bytes.
        write_json(latest_path, receipt)

    def save() -> None:
        save_stamped()
        publish_latest()

    save()
    dataset_phase = run_cmd(
        "build_training_dataset",
        ["python3", str(DATASET_BUILDER)],
        timeout_s=args.dataset_timeout_seconds,
        log_path=log_dir / "dataset.log",
    )
    receipt["phases"].append(dataset_phase)
    save()
    if dataset_phase.get("ok") is not True:
        receipt["finished_at_utc"] = iso_now()
        receipt["error"] = "dataset build failed"
        save()
        return receipt

    # Preflight runs before the builder so its hashes describe inputs before refresh.
    # Record the exact post-build files that the training command will consume.
    receipt["training_dataset_hashes"] = {}
    for dataset_file in (
        DATASET_DIR / "sft_train.jsonl",
        DATASET_DIR / "sft_val.jsonl",
        DATASET_DIR / "negative_eval.jsonl",
        DATASET_DIR / "dataset_manifest.json",
    ):
        if dataset_file.is_file():
            receipt["training_dataset_hashes"][dataset_file.name] = {
                "bytes": dataset_file.stat().st_size,
                "sha256": sha256_file(dataset_file),
            }
    save()

    resume_adapter = ""
    prior_lineage = 0
    resume_state: dict[str, Any] = {
        "adapter": "",
        "lineage": 0,
        "pointer_path": str(ADAPTER_POINTER),
        "hash_verified": False,
        "legacy_unhashed": False,
        "fresh_requested": bool(args.fresh),
    }
    if not args.fresh:
        try:
            resume_state = load_proven_resume_pointer(
                ADAPTER_POINTER, Path(args.model).resolve()
            )
            resume_state["fresh_requested"] = False
        except Exception as exc:
            receipt["resume_pointer"] = resume_state
            receipt["finished_at_utc"] = iso_now()
            receipt["error"] = "proven adapter hash verification failed"
            receipt["resume_pointer_error"] = repr(exc)
            save()
            return receipt
        resume_adapter = str(resume_state.get("adapter") or "")
        prior_lineage = int(resume_state.get("lineage") or 0)
    receipt["resume_pointer"] = resume_state
    receipt["resumed_from"] = resume_adapter or None
    receipt["adapter_lineage"] = prior_lineage + 1 if resume_adapter else 1
    save()

    train_deadline = time.time() + args.training_budget_seconds
    train_command = [
        str(VENV_PY),
        str(TRAIN_SCRIPT),
        "--model",
        str(Path(args.model).resolve()),
        "--train",
        str(DATASET_DIR / "sft_train.jsonl"),
        "--val",
        str(DATASET_DIR / "sft_val.jsonl"),
        "--negative",
        str(DATASET_DIR / "negative_eval.jsonl"),
        "--out",
        str(out_dir),
        "--deadline-epoch",
        str(train_deadline),
        "--epochs",
        str(args.epochs),
        "--seq",
        str(args.seq),
        # (2026-08-08, operator-directed before further lineage stacking) Bounded
        # unlikelihood on the negative TRAIN half; the eval half stays held out so the
        # contrast metric keeps measuring, not echoing.
        "--negative-train-weight",
        str(args.negative_train_weight),
    ]
    if resume_adapter:
        train_command += ["--resume-adapter", resume_adapter]
    train_phase = run_cmd(
        "train_lora",
        train_command,
        timeout_s=args.training_budget_seconds + 1800,
        log_path=log_dir / "train.log",
    )
    receipt["phases"].append(train_phase)
    summary_path = out_dir / "train_summary.json"
    if summary_path.is_file():
        receipt["train_summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
    receipt["adapter_files"] = tree_records(out_dir / "adapter")
    receipt["merged_files_count"] = len(tree_records(out_dir / "merged", max_files=20))
    save()
    if train_phase.get("ok") is not True or not (out_dir / "adapter" / "adapter_model.safetensors").is_file():
        receipt["finished_at_utc"] = iso_now()
        receipt["error"] = "training failed or adapter_model.safetensors missing"
        save()
        return receipt

    # Training has produced a candidate, not a proof. Inventory the complete adapter,
    # verify every byte immediately, and publish only CANDIDATE_LATEST before eval.
    try:
        receipt["adapter_artifact_manifest"] = artifact_hash_manifest(
            out_dir / "adapter", required_relative_paths=("adapter_model.safetensors",)
        )
    except Exception as exc:
        receipt["finished_at_utc"] = iso_now()
        receipt["error"] = "adapter artifact hash verification failed"
        receipt["artifact_hash_error"] = repr(exc)
        save()
        return receipt

    base_model = Path(args.model).resolve()
    receipt["core_hashes"] = core_hashes(receipt, base_model, summary_path)
    model_name = engel_model_name(
        base_model,
        receipt["adapter_lineage"],
        str(receipt["adapter_artifact_manifest"]["artifact_set_sha256"]),
    )
    receipt["engel_model_name"] = model_name
    receipt["artifact_status"] = "candidate"
    receipt["proof_gates"] = {
        "adapter_artifacts_verified": True,
        "evaluation_suite": None,
        "evaluation_artifacts_verified": None,
        "validation_loss_improved": None,
        "passed": False,
    }
    try:
        finalize_model_card_artifacts(
            out_dir,
            model_name,
            receipt,
            base_model,
            artifact_status="candidate",
        )
        # Persist the receipt before calculating the pointer's receipt hash.  The
        # candidate pointer is advisory, but it uses the same authenticated shape
        # as a proof pointer so operators can inspect it consistently.
        save()
        write_json(
            CANDIDATE_ADAPTER_POINTER,
            adapter_pointer_payload(
                receipt,
                out_dir,
                base_model,
                model_name,
                artifact_status="candidate",
            ),
        )
    except Exception as exc:
        receipt["finished_at_utc"] = iso_now()
        receipt["error"] = "candidate model-card finalization failed"
        receipt["model_card_hash_error"] = repr(exc)
        save()
        return receipt

    eval_phase = run_cmd(
        "eval_suite",
        [
            str(VENV_PY),
            str(EVAL_SCRIPT),
            "--base",
            str(Path(args.model).resolve()),
            "--tuned",
            str(out_dir / "merged"),
            "--out",
            str(out_dir / "eval"),
        ],
        timeout_s=args.eval_timeout_seconds,
        log_path=log_dir / "eval.log",
    )
    receipt["phases"].append(eval_phase)
    receipt["eval_files"] = tree_records(out_dir / "eval")
    eval_artifacts_verified = False
    if receipt["eval_files"]:
        try:
            receipt["eval_artifact_manifest"] = artifact_hash_manifest(
                out_dir / "eval"
            )
            eval_artifacts_verified = True
        except Exception as exc:
            receipt["eval_artifact_hash_error"] = repr(exc)

    adapter_artifacts_verified = False
    try:
        verify_artifact_hash_manifest(
            out_dir / "adapter", receipt["adapter_artifact_manifest"]
        )
        adapter_artifacts_verified = True
        receipt["adapter_artifacts_reverified_after_eval_at_utc"] = iso_now()
    except Exception as exc:
        receipt["artifact_hash_error"] = repr(exc)

    train_summary = receipt.get("train_summary") if isinstance(receipt.get("train_summary"), dict) else {}
    val_delta = train_summary.get("val_loss_delta")
    receipt["new_adapter_trained"] = True
    receipt["new_adapter_path"] = str(out_dir / "adapter")
    receipt["new_merged_path"] = str(out_dir / "merged")
    receipt["validation_loss_before"] = train_summary.get("val_loss_before")
    receipt["validation_loss_after"] = train_summary.get("val_loss")
    receipt["validation_loss_delta"] = val_delta
    # Inference-side contrast (advisory, recorded for the operator): val should drop MORE
    # than loss on gate-rejected examples, or the run absorbed style rather than standards.
    receipt["negative_loss_delta"] = train_summary.get("negative_loss_delta")
    receipt["val_minus_negative_delta"] = train_summary.get("val_minus_negative_delta")
    receipt["coverage"] = {
        "samples_seen": train_summary.get("samples_seen"),
        "epochs_effective": train_summary.get("epochs_effective"),
        "train_kept": train_summary.get("train_kept"),
        "val_kept": train_summary.get("val_kept"),
        "negative_kept": train_summary.get("negative_kept"),
        "negative_train_kept": train_summary.get("negative_train_kept"),
        "negative_train_weight": train_summary.get("negative_train_weight"),
        "seq_window": train_summary.get("seq_window"),
    }
    receipt["adapter_weight_norm_after"] = train_summary.get("adapter_weight_norm_after")
    validation_loss_improved = bool(
        isinstance(val_delta, (int, float))
        and not isinstance(val_delta, bool)
        and math.isfinite(float(val_delta))
        and float(val_delta) < 0
    )
    receipt["model_weight_improvement_claimed"] = validation_loss_improved
    receipt["proof_gates"] = {
        "adapter_artifacts_verified": adapter_artifacts_verified,
        "evaluation_suite": eval_phase.get("ok") is True,
        "evaluation_artifacts_verified": eval_artifacts_verified,
        "validation_loss_improved": validation_loss_improved,
    }
    receipt["proof_gates"]["passed"] = all(
        value is True for value in receipt["proof_gates"].values()
    )
    receipt["ok"] = bool(receipt["proof_gates"]["passed"])
    receipt["artifact_status"] = "proven" if receipt["ok"] else "candidate"
    receipt["core_hashes"] = core_hashes(receipt, base_model, summary_path)
    receipt["finished_at_utc"] = iso_now()
    # Finalize every byte before publishing either pointer. In particular, the
    # proven cards must already truthfully state that the proof pointer advanced;
    # rewriting them after hashing would invalidate both the card and weight proof.
    if receipt["ok"]:
        receipt["proof_pointer_advanced"] = True
        receipt["adapter_pointer"] = str(PROOF_ADAPTER_POINTER)

    try:
        finalize_model_card_artifacts(
            out_dir,
            model_name,
            receipt,
            base_model,
            artifact_status=receipt["artifact_status"],
        )
        verify_artifact_hash_manifest(
            out_dir / "adapter", receipt["adapter_artifact_manifest"]
        )
        verify_model_card_hash_manifest(
            out_dir, receipt["model_card_artifact_manifest"]
        )

        # The stamped receipt is immutable resume evidence. Save it before pointer
        # construction so the pointer can hash-bind its exact finalized bytes. The
        # mutable LATEST status alias is intentionally published only after the
        # durable proof pointer, eliminating a crash window where canary could read
        # a receipt that claimed a pointer advance which had not happened yet.
        save_stamped()
        candidate_payload = adapter_pointer_payload(
            receipt,
            out_dir,
            base_model,
            model_name,
            artifact_status=receipt["artifact_status"],
        )
        write_json(CANDIDATE_ADAPTER_POINTER, candidate_payload)

        # PROOF_LATEST is the durable resume base and advances last, after every
        # artifact, model card, proof gate, and stamped receipt is finalized.
        if receipt["ok"]:
            write_json(
                PROOF_ADAPTER_POINTER,
                adapter_pointer_payload(
                    receipt,
                    out_dir,
                    base_model,
                    model_name,
                    artifact_status="proven",
                ),
            )
    except Exception as exc:
        receipt["ok"] = False
        receipt["artifact_status"] = "candidate"
        receipt["proof_pointer_advanced"] = False
        receipt.pop("adapter_pointer", None)
        receipt["proof_pointer_error"] = repr(exc)
        receipt["error"] = "proof artifact finalization or pointer promotion failed"
        try:
            finalize_model_card_artifacts(
                out_dir,
                model_name,
                receipt,
                base_model,
                artifact_status="candidate",
            )
            save()
            write_json(
                CANDIDATE_ADAPTER_POINTER,
                adapter_pointer_payload(
                    receipt,
                    out_dir,
                    base_model,
                    model_name,
                    artifact_status="candidate",
                ),
            )
        except Exception as recovery_exc:
            receipt["candidate_pointer_recovery_error"] = repr(recovery_exc)
            save()
        return receipt
    try:
        publish_latest()
    except Exception as exc:
        # At this point the stamped receipt and (when proven) PROOF_LATEST are a
        # valid authenticated pair. Never roll them back merely because a mutable
        # convenience alias could not be refreshed.
        receipt["latest_status_publish_error"] = repr(exc)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", default="")
    parser.add_argument("--origin", default="manual_ct246_lora_proof_runner")
    parser.add_argument("--model", default=str(MODEL_DEFAULT))
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--training-budget-seconds", type=int, default=3600)
    parser.add_argument("--dataset-timeout-seconds", type=int, default=900)
    parser.add_argument("--eval-timeout-seconds", type=int, default=7200)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--fresh", action="store_true",
                        help="ignore the adapter lineage pointer and re-init LoRA from zero")
    parser.add_argument("--negative-train-weight", type=float, default=0.25,
                        help="bounded unlikelihood weight on the negative train half; 0 = pure SFT")
    # (2026-08-07) 768 was measured catastrophically small for this corpus: Engel's SFT
    # prompts (persona + facts + contract) median ~760-800 tokens, so the trainer's
    # zero-signal guard silently kept 108/1661 train rows and 0/43 val rows -- the first
    # live cycle "trained" on 6.5% of the corpus and reported val_loss 0.0/0.0 from an
    # empty set. Measured with the model tokenizer: seq 1536 keeps 1661/1661 train and
    # 43/43 val (max prompt 1465) with answer room to spare; the wall-clock budget still
    # caps total cost, so fewer-but-informative steps replace many wasted ones.
    parser.add_argument("--seq", type=int, default=1536)
    args = parser.parse_args()

    if args.preflight_only:
        payload = preflight(args)
    else:
        payload = train(args)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
