#!/usr/bin/env python3
"""Create a provenance-bound GGUF from a passed CT246 LoRA canary.

This tool converts and canaries only. It never changes systemd, a production
route, a model seat, or a service. An operator supplies every executable path:

  python3 /opt/engel/tools/run_engel_ct246_gguf_conversion.py \
    --canary-receipt /opt/engel/reports/llm_training/ENGEL_CT246_LORA_CANARY_<stamp>.json \
    --approval APPROVE_ENGEL_PROMOTE_LORA_CANARY_<stamp>_<digest> \
    --converter /opt/engel/tools/llama.cpp/convert_hf_to_gguf.py \
    --validator /opt/engel/tools/run_engel_ct246_gguf_canary.py \
    --validator-python /opt/engel/.venv/bin/python \
    --output-dir /opt/engel/models-active/llm/<engel-model-name>

The stamped v2 conversion receipt is the only schema accepted by the separate
deployment gate. ``*_LATEST.json`` is a status alias and is never valid input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/opt/engel")
REPORT_ROOT = ROOT / "reports" / "llm_training"
RUN_ROOT = ROOT / "llm_training" / "gguf_conversion_runs"
MODEL_ROOT = ROOT / "models-active" / "llm"
LATEST_RECEIPT = REPORT_ROOT / "ENGEL_CT246_GGUF_CONVERSION_LATEST.json"

CANARY_SCHEMA = "engel_ct246_lora_canary_gate_receipt_v2"
CONTRACT_SCHEMA = "engel_lora_promotion_contract_v2"
CONVERSION_SCHEMA = "engel_gguf_conversion_receipt_v2"
PROOF_SCHEMA = "engel_ct246_local_lora_model_weight_improvement_receipt_v1"
GGUF_VALIDATOR_SCHEMA = "engel_ct246_gguf_behavioral_canary_output_v1"
GGUF_VALIDATION_BINDING_SCHEMA = "engel_gguf_conversion_validation_binding_v1"
GGUF_VALIDATOR_VERSION_NAME = "GGUF_VALIDATOR_VERSION"
GGUF_CANARY_CASE_IDS = ("normal_chat", "identity", "training_truth", "simple_math")
ALLOWED_QUANTIZATIONS = ("q8_0", "f16", "bf16", "f32")


class ConversionBlocked(RuntimeError):
    """Raised before conversion when immutable provenance cannot be established."""


class GGUFValidationBlocked(ConversionBlocked):
    """Carries a failed GGUF validation record into the conversion receipt."""

    def __init__(self, message: str, record: dict[str, Any]):
        super().__init__(message)
        self.record = record


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return sha256_bytes(raw)


def require_ct246_path(path: Path, label: str) -> Path:
    path = Path(path)
    text = str(path)
    if not text.startswith("/opt/engel/") or "/../" in text or text.endswith("/.."):
        raise ConversionBlocked(f"{label} is outside /opt/engel: {path}")
    return path


def require_model_output_dir(path: Path) -> Path:
    path = require_ct246_path(path, "output directory")
    try:
        path.resolve(strict=False).relative_to(MODEL_ROOT.resolve())
    except ValueError as exc:
        raise ConversionBlocked(
            f"output directory must stay under {MODEL_ROOT}: {path}"
        ) from exc
    return path


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    """Atomically replace mutable status data such as the LATEST alias."""
    require_ct246_path(path, "atomic output")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_new(path: Path, data: bytes, mode: int = 0o444) -> None:
    """Atomically publish a new immutable file without any overwrite window."""
    require_ct246_path(path, "immutable atomic output")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    linked = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        # A hard-link publication is same-filesystem, atomic, and fails if the
        # immutable destination appeared concurrently. os.replace is deliberately
        # reserved for the mutable LATEST status alias.
        if os.name != "nt":
            os.chmod(temporary, mode)
        os.link(temporary, path)
        linked = True
        temporary.unlink()
        if os.name == "nt":
            # Windows does not permit unlinking a read-only hard link. The CT target
            # is Linux, but keep local verification portable by applying the final
            # read-only attribute after the staging name is gone.
            os.chmod(path, mode)
    except Exception:
        if linked and path.exists():
            try:
                if os.name == "nt":
                    os.chmod(path, 0o600)
                path.unlink()
            except OSError:
                pass
        raise
    finally:
        if temporary.exists():
            try:
                if os.name == "nt":
                    os.chmod(temporary, 0o600)
                temporary.unlink()
            except OSError:
                pass


def write_final_receipt(path: Path, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        atomic_write_new(path, encoded, mode=0o444)
    except FileExistsError as exc:
        raise RuntimeError(f"refusing immutable receipt overwrite: {path}") from exc
    # LATEST is only a status alias. It is atomically replaceable and never accepted as
    # a canary, proof, or conversion input by the downstream gates.
    try:
        atomic_write(LATEST_RECEIPT, encoded, mode=0o644)
    except OSError:
        # The immutable stamped receipt is authoritative; failure of its optional status
        # alias must never invalidate or delete an otherwise verified GGUF.
        pass


def read_immutable_json(
    path: Path, label: str, require_read_only: bool = False,
) -> tuple[dict[str, Any], str]:
    path = require_ct246_path(path, label)
    if "LATEST" in path.name.upper():
        raise ConversionBlocked(f"{label} must be stamped, not a LATEST alias: {path}")
    if path.is_symlink() or not path.is_file():
        raise ConversionBlocked(f"{label} must be a regular file: {path}")
    if require_read_only and path.stat().st_mode & 0o222:
        raise ConversionBlocked(f"{label} must be immutable/read-only: {path}")
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise ConversionBlocked(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ConversionBlocked(f"{label} payload is not an object: {path}")
    return payload, sha256_bytes(raw)


def _hash_records(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: str(item["relative_path"])):
        digest.update(str(record["relative_path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["bytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).upper().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest().upper()


def tree_hash_manifest(root: Path, exclude_model_card: bool) -> dict[str, Any]:
    root = require_ct246_path(root, "input model tree")
    if root.is_symlink() or not root.is_dir():
        raise ConversionBlocked(f"input model tree missing: {root}")
    resolved_root = root.resolve()
    records: list[dict[str, Any]] = []
    excluded: list[str] = []
    for file in sorted(root.rglob("*")):
        if file.is_symlink():
            raise ConversionBlocked(f"input model tree contains a symlink: {file}")
        if not file.is_file():
            continue
        try:
            relative = file.resolve().relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise ConversionBlocked(f"input file escapes model tree: {file}") from exc
        if exclude_model_card and file.name == "ENGEL_MODEL_CARD.json":
            excluded.append(relative)
            continue
        records.append(
            {
                "path": str(file),
                "relative_path": relative,
                "bytes": file.stat().st_size,
                "sha256": sha256_file(file),
            }
        )
    if not records:
        raise ConversionBlocked(f"input model tree has no files: {root}")
    return {
        "schema": "engel_model_tree_hash_manifest_v1",
        "root": str(root),
        "hash_algorithm": "sha256(relative_path\\0bytes\\0sha256\\n)",
        "exclude_model_card": exclude_model_card,
        "excluded_relative_paths": excluded,
        "file_count": len(records),
        "total_bytes": sum(int(item["bytes"]) for item in records),
        "tree_sha256": _hash_records(records),
        "files": records,
        "computed_at_utc": iso_now(),
    }


def validate_canary_contract(
    canary_path: Path, approval: str,
) -> dict[str, Any]:
    """Purely validate/re-hash every canary promotion input; perform no conversion."""
    canary, canary_sha = read_immutable_json(
        canary_path, "canary receipt", require_read_only=True
    )
    blockers: list[str] = []
    canary_name = re.fullmatch(
        r"ENGEL_CT246_LORA_CANARY_(\d{8}T\d{6}Z)\.json", canary_path.name
    )
    if not canary_name:
        blockers.append("canary receipt filename is not a canonical immutable stamp")
    elif canary_name.group(1) != str(canary.get("run_stamp") or ""):
        blockers.append("canary filename stamp differs from canary run_stamp")
    if canary.get("schema") != CANARY_SCHEMA:
        blockers.append(f"canary schema must be {CANARY_SCHEMA}")
    if not all(
        canary.get(key) is True for key in ("ok", "canary_passed", "promotion_ready")
    ):
        blockers.append("canary is not passed and promotion-ready")
    if canary.get("provenance_stable_after_canary") is not True:
        blockers.append("canary did not record stable provenance after evaluation")
    if str(canary.get("receipt_path") or "") != str(canary_path):
        blockers.append("canary receipt_path differs from the stamped file")

    contract = canary.get("promotion_contract")
    if not isinstance(contract, dict) or contract.get("schema") != CONTRACT_SCHEMA:
        blockers.append(f"promotion contract must use {CONTRACT_SCHEMA}")
        contract = {}
    contract_sha = canonical_json_sha256(contract) if contract else ""
    if contract_sha != str(canary.get("promotion_contract_sha256") or "").upper():
        blockers.append("promotion contract SHA-256 mismatch")
    expected_phrase = (
        f"APPROVE_ENGEL_PROMOTE_LORA_CANARY_{canary.get('run_stamp')}_"
        f"{contract_sha[:16]}"
    )
    if approval != str(canary.get("promotion_approval_required") or ""):
        blockers.append("approval does not exactly match the canary receipt")
    if approval != expected_phrase:
        blockers.append("approval is not bound to the promotion contract digest")
    if str(contract.get("canary_receipt_path") or "") != str(canary_path):
        blockers.append("promotion contract identifies a different canary receipt")
    if contract.get("required_conversion_receipt_schema") != CONVERSION_SCHEMA:
        blockers.append("promotion contract does not require the canonical v2 conversion")
    required_binding_keys = {
        "canary_receipt_path",
        "canary_receipt_sha256",
        "promotion_contract_sha256",
        "proof_receipt_path",
        "proof_receipt_sha256",
        "adapter_tree_sha256",
        "merged_path",
        "merged_tree_sha256",
    }
    contract_binding_keys = set(contract.get("required_conversion_binding_keys") or [])
    if not required_binding_keys.issubset(contract_binding_keys):
        blockers.append("promotion contract omits required conversion binding keys")
    if contract.get("tree_hash_algorithm") != "sha256(relative_path\\0bytes\\0sha256\\n)":
        blockers.append("promotion contract declares an unsupported tree hash algorithm")
    if sorted(contract.get("tree_hash_excluded_relative_paths") or []) != [
        "ENGEL_MODEL_CARD.json"
    ]:
        blockers.append("promotion contract has an unexpected tree-hash exclusion set")

    contract_required_bindings = contract.get("required_conversion_bindings")
    if not isinstance(contract_required_bindings, dict):
        blockers.append("promotion contract lacks required_conversion_bindings")
        contract_required_bindings = {}
    for key in (
        "proof_receipt_path",
        "proof_receipt_sha256",
        "adapter_tree_sha256",
        "merged_path",
        "merged_tree_sha256",
    ):
        expected = str(contract.get(key) or "")
        actual = str(contract_required_bindings.get(key) or "")
        if key.endswith("sha256"):
            expected = expected.upper()
            actual = actual.upper()
        if actual != expected:
            blockers.append(f"promotion contract required binding mismatch: {key}")

    proof_path = Path(str(contract.get("proof_receipt_path") or ""))
    try:
        if not re.fullmatch(
            r"ENGEL_CT246_LORA_PROOF_\d{8}T\d{6}Z\.json", proof_path.name
        ):
            raise ConversionBlocked(
                "proof receipt filename is not a canonical immutable stamp"
            )
        proof, proof_sha = read_immutable_json(proof_path, "proof receipt")
        if proof.get("schema") != PROOF_SCHEMA:
            blockers.append(f"proof schema must be {PROOF_SCHEMA}")
        if proof_sha != str(contract.get("proof_receipt_sha256") or "").upper():
            blockers.append("proof receipt SHA-256 differs from canary contract")
        if str(proof.get("receipt_path") or "") != str(proof_path):
            blockers.append("proof receipt_path differs from the immutable proof file")
        if not all(
            (
                proof.get("ok") is True,
                proof.get("artifact_status") == "proven",
                proof.get("proof_pointer_advanced") is True,
                (proof.get("proof_gates") or {}).get("passed") is True,
            )
        ):
            blockers.append("proof receipt is not a finalized proven artifact")
        if proof.get("model_weight_improvement_claimed") is not True:
            blockers.append("proof does not claim verified model-weight improvement")
        try:
            validation_delta = float(proof.get("validation_loss_delta"))
        except (TypeError, ValueError):
            validation_delta = 0.0
        if not math.isfinite(validation_delta) or validation_delta >= 0.0:
            blockers.append("proof validation loss delta is not negative")
    except Exception as exc:
        blockers.append("proof receipt validation failed: " + repr(exc))
        proof = {}
        proof_sha = ""

    adapter_path = Path(str(contract.get("adapter_path") or ""))
    merged_path = Path(str(contract.get("merged_path") or ""))
    proof_summary = proof.get("train_summary") or {}
    if not isinstance(proof_summary, dict):
        proof_summary = {}
    proof_adapter_path = str(
        proof.get("new_adapter_path") or proof_summary.get("adapter") or ""
    )
    proof_merged_path = str(
        proof.get("new_merged_path") or proof_summary.get("merged") or ""
    )
    if proof_adapter_path != str(adapter_path):
        blockers.append("proof adapter path differs from the promotion contract")
    if proof_merged_path != str(merged_path):
        blockers.append("proof merged path differs from the promotion contract")
    proof_adapter_manifest = proof.get("adapter_artifact_manifest") or {}
    if not isinstance(proof_adapter_manifest, dict):
        proof_adapter_manifest = {}
    if proof_adapter_manifest.get("verified") is not True:
        blockers.append("proof adapter artifact manifest is not verified")
    if str(proof_adapter_manifest.get("artifact_set_sha256") or "").upper() != str(
        contract.get("adapter_tree_sha256") or ""
    ).upper():
        blockers.append("proof adapter artifact hash differs from the promotion contract")
    if str(canary.get("proof_receipt_path") or "") != str(proof_path):
        blockers.append("canary top-level proof path differs from the promotion contract")
    if str(canary.get("proof_receipt_sha256") or "").upper() != str(
        contract.get("proof_receipt_sha256") or ""
    ).upper():
        blockers.append("canary top-level proof hash differs from the promotion contract")
    if str(canary.get("proof_receipt_sha256_after_canary") or "").upper() != str(
        contract.get("proof_receipt_sha256") or ""
    ).upper():
        blockers.append("canary post-evaluation proof hash differs from the contract")
    try:
        adapter_tree = tree_hash_manifest(adapter_path, exclude_model_card=True)
        if adapter_tree["tree_sha256"] != str(
            contract.get("adapter_tree_sha256") or ""
        ).upper():
            blockers.append("adapter tree SHA-256 differs from canary contract")
        if str(canary.get("adapter_tree_sha256_after_canary") or "").upper() != str(
            contract.get("adapter_tree_sha256") or ""
        ).upper():
            blockers.append("canary post-evaluation adapter hash differs from the contract")
    except Exception as exc:
        blockers.append("adapter tree validation failed: " + repr(exc))
        adapter_tree = {}
    try:
        merged_promotion_tree = tree_hash_manifest(
            merged_path, exclude_model_card=True
        )
        if merged_promotion_tree["tree_sha256"] != str(
            contract.get("merged_tree_sha256") or ""
        ).upper():
            blockers.append("merged tree SHA-256 differs from canary contract")
        if str(canary.get("merged_tree_sha256_after_canary") or "").upper() != str(
            contract.get("merged_tree_sha256") or ""
        ).upper():
            blockers.append("canary post-evaluation merged hash differs from the contract")
        merged_complete_tree = tree_hash_manifest(
            merged_path, exclude_model_card=False
        )
    except Exception as exc:
        blockers.append("merged tree validation failed: " + repr(exc))
        merged_promotion_tree = {}
        merged_complete_tree = {}

    model_name = str(proof.get("engel_model_name") or "")
    if not re.fullmatch(r"engel-core-[a-z0-9-]+", model_name):
        blockers.append("proof lacks a safe collision-resistant engel_model_name")
    if blockers:
        raise ConversionBlocked("; ".join(blockers))
    return {
        "canary": canary,
        "canary_receipt_path": str(canary_path),
        "canary_receipt_sha256": canary_sha,
        "promotion_contract": contract,
        "promotion_contract_sha256": contract_sha,
        "proof": proof,
        "proof_receipt_path": str(proof_path),
        "proof_receipt_sha256": proof_sha,
        "adapter_tree": adapter_tree,
        "merged_promotion_tree": merged_promotion_tree,
        "merged_complete_tree": merged_complete_tree,
        "merged_path": str(merged_path),
        "model_name": model_name,
    }


def converter_version(path: Path, converter_sha256: str) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")[:200_000]
    patterns = (
        r"(?m)^\s*__version__\s*=\s*['\"]([^'\"]+)['\"]",
        r"(?m)^\s*VERSION\s*=\s*['\"]([^'\"]+)['\"]",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return {"value": match.group(1), "source": "converter_source_constant"}
    return {
        "value": f"sha256:{converter_sha256[:16]}",
        "source": "converter_source_digest",
    }


def validator_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")[:200_000]
    match = re.search(
        rf"(?m)^\s*{GGUF_VALIDATOR_VERSION_NAME}\s*=\s*['\"]([^'\"]+)['\"]",
        text,
    )
    if not match:
        raise ConversionBlocked(
            f"validator source lacks {GGUF_VALIDATOR_VERSION_NAME}"
        )
    return match.group(1)


def invoke_gguf_validator(
    *,
    gguf_path: Path,
    gguf_sha256: str,
    gguf_bytes: int,
    validator_path: Path,
    validator_python: Path,
    output_dir: Path,
    log_dir: Path,
    timeout_seconds: int,
    max_new_tokens: int,
    threads: int,
) -> dict[str, Any]:
    """Run one explicit hashed validator and return its audit binding or fail."""
    validator_path = require_ct246_path(validator_path, "GGUF validator")
    validator_python = require_ct246_path(
        validator_python, "GGUF validator Python"
    )
    if validator_path.name != "run_engel_ct246_gguf_canary.py":
        raise ConversionBlocked(
            "--validator must name run_engel_ct246_gguf_canary.py"
        )
    if validator_path.is_symlink() or not validator_path.is_file():
        raise ConversionBlocked(f"GGUF validator is not a regular file: {validator_path}")
    if not validator_python.is_file():
        raise ConversionBlocked(
            f"GGUF validator Python is not a file: {validator_python}"
        )
    if not 1 <= int(timeout_seconds) <= 7_200:
        raise ConversionBlocked("validator timeout must be between 1 and 7200 seconds")
    if not 8 <= int(max_new_tokens) <= 128:
        raise ConversionBlocked("validator max-new-tokens must be between 8 and 128")
    if not 1 <= int(threads) <= 32:
        raise ConversionBlocked("validator threads must be between 1 and 32")

    validator_sha = sha256_file(validator_path)
    version = validator_version(validator_path)
    version_sha = sha256_bytes(version.encode("utf-8"))
    python_sha = sha256_file(validator_python)
    python_version_run = subprocess.run(
        [str(validator_python), "--version"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if python_version_run.returncode != 0:
        raise ConversionBlocked("GGUF validator Python --version failed")
    python_version = (
        python_version_run.stdout or python_version_run.stderr or ""
    ).strip()

    request = {
        "schema": "engel_gguf_behavioral_canary_request_v1",
        "gguf_path": str(gguf_path),
        "gguf_sha256": gguf_sha256,
        "gguf_bytes": int(gguf_bytes),
        "max_new_tokens": int(max_new_tokens),
        "threads": int(threads),
        "context": 1024,
        "expected_validator_schema": GGUF_VALIDATOR_SCHEMA,
        "expected_validator_version": version,
        "expected_case_ids": list(GGUF_CANARY_CASE_IDS),
    }
    request_path = output_dir / "gguf_validation_request.json"
    atomic_write_new(
        request_path,
        (json.dumps(request, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        mode=0o444,
    )
    request_sha = sha256_file(request_path)
    command = [str(validator_python), str(validator_path), "--request", str(request_path)]
    command_sha = sha256_bytes(
        json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    invocation = {
        "command": command,
        "command_sha256": command_sha,
        "request_sha256": request_sha,
        "gguf_sha256": gguf_sha256,
        "validator_sha256": validator_sha,
        "validator_version": version,
        "validator_python_sha256": python_sha,
        "expected_case_ids": list(GGUF_CANARY_CASE_IDS),
        "offline_environment": {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        },
    }
    stdout_path = log_dir / "gguf_validator.stdout.json"
    stderr_path = log_dir / "gguf_validator.stderr.log"
    environment = os.environ.copy()
    environment.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    started = time.perf_counter()
    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        try:
            completed = subprocess.run(
                command,
                stdout=stdout_handle,
                stderr=stderr_handle,
                timeout=int(timeout_seconds),
                check=False,
                env=environment,
            )
            returncode: int | None = completed.returncode
            command_error = ""
        except subprocess.TimeoutExpired as exc:
            returncode = None
            command_error = repr(exc)

    stdout_record = {
        "path": str(stdout_path),
        "bytes": stdout_path.stat().st_size,
        "sha256": sha256_file(stdout_path),
    }
    stderr_record = {
        "path": str(stderr_path),
        "bytes": stderr_path.stat().st_size,
        "sha256": sha256_file(stderr_path),
    }
    try:
        parsed = json.loads(stdout_path.read_text(encoding="utf-8-sig"))
        if not isinstance(parsed, dict):
            raise ValueError("validator output is not an object")
        parse_error = ""
    except Exception as exc:
        parsed = {}
        parse_error = repr(exc)

    rows = parsed.get("rows") if isinstance(parsed.get("rows"), list) else []
    row_ids = [str(row.get("id") or "") for row in rows if isinstance(row, dict)]
    blockers: list[str] = []
    if sha256_file(request_path) != request_sha:
        blockers.append("GGUF validator changed its immutable request")
    if sha256_file(validator_path) != validator_sha:
        blockers.append("GGUF validator source changed while running")
    if sha256_file(validator_python) != python_sha:
        blockers.append("GGUF validator Python changed while running")
    if returncode != 0:
        blockers.append(
            f"GGUF validator exit was not zero: {returncode}; {command_error}"
        )
    if parse_error:
        blockers.append("GGUF validator stdout is not canonical JSON: " + parse_error)
    if parsed.get("schema") != GGUF_VALIDATOR_SCHEMA:
        blockers.append("GGUF validator output schema mismatch")
    if parsed.get("ok") is not True:
        blockers.append("GGUF behavioral canary did not pass")
    if str(parsed.get("validator_version") or "") != version:
        blockers.append("GGUF validator output version differs from source")
    if str(parsed.get("gguf_path") or "") != str(gguf_path):
        blockers.append("GGUF validator evaluated a different path")
    if str(parsed.get("gguf_sha256") or "").upper() != gguf_sha256:
        blockers.append("GGUF validator result is not bound to the converted SHA-256")
    try:
        if int(parsed.get("gguf_bytes") or -1) != int(gguf_bytes):
            blockers.append("GGUF validator result byte count mismatch")
    except (TypeError, ValueError):
        blockers.append("GGUF validator result byte count is invalid")
    if list(parsed.get("case_ids") or []) != list(GGUF_CANARY_CASE_IDS):
        blockers.append("GGUF validator case ID contract mismatch")
    if row_ids != list(GGUF_CANARY_CASE_IDS):
        blockers.append("GGUF validator case results are incomplete or reordered")
    for row in rows:
        if not isinstance(row, dict) or row.get("ok") is not True:
            blockers.append("one or more GGUF validator cases failed")
            break
        if list(row.get("quality_failures") or []):
            blockers.append("GGUF validator case reports quality failures")
            break
    case_contract = parsed.get("case_contract")
    case_contract_sha = str(parsed.get("case_contract_sha256") or "").upper()
    if not isinstance(case_contract, dict) or canonical_json_sha256(
        case_contract or {}
    ) != case_contract_sha:
        blockers.append("GGUF validator case contract hash mismatch")

    record: dict[str, Any] = {
        "ok": not blockers,
        "schema": GGUF_VALIDATION_BINDING_SCHEMA,
        "validated_gguf_path": str(gguf_path),
        "gguf_sha256": gguf_sha256,
        "gguf_bytes": int(gguf_bytes),
        "validator": {
            "path": str(validator_path),
            "sha256": validator_sha,
            "bytes": validator_path.stat().st_size,
            "version": version,
            "version_sha256": version_sha,
            "python_path": str(validator_python),
            "python_resolved_path": str(validator_python.resolve()),
            "python_sha256": python_sha,
            "python_version": python_version,
            "command": command,
            "command_sha256": command_sha,
            "invocation_contract_sha256": canonical_json_sha256(invocation),
        },
        "request": {
            "path": str(request_path),
            "sha256": request_sha,
            "payload": request,
        },
        "returncode": returncode,
        "command_error": command_error,
        "stdout": stdout_record,
        "stderr": stderr_record,
        "validator_output_schema": parsed.get("schema", ""),
        "validator_output_sha256": canonical_json_sha256(parsed),
        "validator_output": parsed,
        "case_contract_sha256": case_contract_sha,
        "case_ids": row_ids,
        "cases": rows,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "blockers": blockers,
    }
    if blockers:
        raise GGUFValidationBlocked("; ".join(blockers), record)
    return record


def normalize_quantization(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if normalized not in ALLOWED_QUANTIZATIONS:
        raise ConversionBlocked(
            "quantization must be one of: " + ", ".join(ALLOWED_QUANTIZATIONS)
        )
    return normalized


def gguf_filename(model_name: str, quantization: str) -> str:
    """Return the only output name accepted for a proven model and quantization."""
    if not re.fullmatch(r"engel-core-[a-z0-9-]+", model_name):
        raise ConversionBlocked("cannot name GGUF for an unsafe Engel model name")
    return f"{model_name}-{normalize_quantization(quantization)}.gguf"


def build_conversion_receipt(
    context: dict[str, Any],
    output: dict[str, Any],
    converter: dict[str, Any],
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    contract = context["promotion_contract"]
    validation = context.get("gguf_validation")
    if not isinstance(validation, dict) or validation.get("ok") is not True:
        raise ConversionBlocked("a passed GGUF behavioral validation is mandatory")
    if str(validation.get("gguf_sha256") or "").upper() != str(
        output.get("gguf_sha256") or ""
    ).upper():
        raise ConversionBlocked("GGUF validation is not bound to the output SHA-256")
    if int(validation.get("gguf_bytes") or -1) != int(
        output.get("gguf_bytes") or -2
    ):
        raise ConversionBlocked("GGUF validation is not bound to the output byte count")
    return {
        "ok": True,
        "schema": CONVERSION_SCHEMA,
        "created_at_utc": iso_now(),
        "run": run_metadata,
        "bindings": {
            "canary_receipt_path": context["canary_receipt_path"],
            "canary_receipt_sha256": context["canary_receipt_sha256"],
            "promotion_contract_sha256": context[
                "promotion_contract_sha256"
            ],
            "proof_receipt_path": context["proof_receipt_path"],
            "proof_receipt_sha256": context["proof_receipt_sha256"],
            "adapter_tree_sha256": context["adapter_tree"]["tree_sha256"],
            "merged_path": context["merged_path"],
            "merged_tree_sha256": context["merged_promotion_tree"][
                "tree_sha256"
            ],
        },
        "input": {
            "merged_path": context["merged_path"],
            "promotion_tree_manifest": context["merged_promotion_tree"],
            "complete_tree_manifest": context["merged_complete_tree"],
            "adapter_tree_manifest": context["adapter_tree"],
            "canary_required_conversion_schema": contract.get(
                "required_conversion_receipt_schema"
            ),
            "post_conversion_verification": context.get(
                "post_conversion_verification"
            )
            or {},
        },
        "converter": converter,
        "validation": validation,
        "output": output,
        "production_chat_affected": False,
        "service_modified": False,
        "deployment_performed": False,
    }


def run_conversion(args: argparse.Namespace) -> dict[str, Any]:
    run_stamp = stamp()
    run_id = f"{run_stamp}_{uuid.uuid4().hex[:10]}"
    receipt_path = REPORT_ROOT / f"ENGEL_CT246_GGUF_CONVERSION_{run_id}.json"
    run_dir = RUN_ROOT / run_id
    log_dir = run_dir / "logs"
    t0 = time.perf_counter()
    receipt: dict[str, Any] = {
        "ok": False,
        "schema": CONVERSION_SCHEMA,
        "created_at_utc": iso_now(),
        "receipt_path": str(receipt_path),
        "run": {"run_id": run_id, "origin": args.origin},
        "production_chat_affected": False,
        "service_modified": False,
        "deployment_performed": False,
    }
    temporary_output: Path | None = None
    final_output: Path | None = None
    output_installed = False
    try:
        canary_path = require_ct246_path(Path(args.canary_receipt), "canary receipt")
        context = validate_canary_contract(canary_path, args.approval)
        receipt["bindings"] = {
            "canary_receipt_path": context["canary_receipt_path"],
            "canary_receipt_sha256": context["canary_receipt_sha256"],
            "promotion_contract_sha256": context["promotion_contract_sha256"],
            "proof_receipt_path": context["proof_receipt_path"],
            "proof_receipt_sha256": context["proof_receipt_sha256"],
            "adapter_tree_sha256": context["adapter_tree"]["tree_sha256"],
            "merged_path": context["merged_path"],
            "merged_tree_sha256": context["merged_promotion_tree"]["tree_sha256"],
        }

        converter_path = require_ct246_path(Path(args.converter), "converter")
        if converter_path.name != "convert_hf_to_gguf.py":
            raise ConversionBlocked(
                "--converter must name the explicit local convert_hf_to_gguf.py"
            )
        if converter_path.is_symlink() or not converter_path.is_file():
            raise ConversionBlocked(f"converter is not a regular file: {converter_path}")
        converter_sha = sha256_file(converter_path)
        version = converter_version(converter_path, converter_sha)

        python_path = Path(args.converter_python or sys.executable).resolve()
        if not python_path.is_file():
            raise ConversionBlocked(f"converter Python is not a file: {python_path}")
        python_sha = sha256_file(python_path)
        python_version_run = subprocess.run(
            [str(python_path), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if python_version_run.returncode != 0:
            raise ConversionBlocked("converter Python --version failed")
        python_version = (
            python_version_run.stdout or python_version_run.stderr or ""
        ).strip()

        quantization = normalize_quantization(args.quantization)
        if not 1 <= int(args.timeout_seconds) <= 86_400:
            raise ConversionBlocked("--timeout-seconds must be between 1 and 86400")
        output_dir = require_model_output_dir(Path(args.output_dir))
        if output_dir.name != context["model_name"]:
            raise ConversionBlocked(
                "output directory name must exactly equal the proven engel_model_name: "
                + context["model_name"]
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / gguf_filename(
            context["model_name"], quantization
        )
        if final_output.exists():
            raise ConversionBlocked(f"refusing GGUF overwrite: {final_output}")
        temporary_output = output_dir / (
            f".{context['model_name']}-{quantization}.{run_id}.part.gguf"
        )
        if temporary_output.exists():
            raise ConversionBlocked(f"temporary output collision: {temporary_output}")

        command = [
            str(python_path),
            str(converter_path),
            context["merged_path"],
            "--outfile",
            str(temporary_output),
            "--outtype",
            quantization,
        ]
        command_sha = sha256_bytes(
            json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        invocation_contract = {
            "command": command,
            "command_sha256": command_sha,
            "converter_sha256": converter_sha,
            "converter_python_sha256": python_sha,
            "complete_input_tree_sha256": context["merged_complete_tree"][
                "tree_sha256"
            ],
            "offline_environment": {
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
            },
        }
        converter_record: dict[str, Any] = {
            "path": str(converter_path),
            "sha256": converter_sha,
            "bytes": converter_path.stat().st_size,
            "version": version,
            "version_sha256": canonical_json_sha256(version),
            "python_path": str(python_path),
            "python_sha256": python_sha,
            "python_version": python_version,
            "command": command,
            "command_sha256": command_sha,
            "invocation_contract_sha256": canonical_json_sha256(
                invocation_contract
            ),
        }
        receipt["converter"] = converter_record
        receipt["input"] = {
            "promotion_tree_manifest": context["merged_promotion_tree"],
            "complete_tree_manifest": context["merged_complete_tree"],
            "adapter_tree_manifest": context["adapter_tree"],
        }

        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / "converter.stdout.log"
        stderr_path = log_dir / "converter.stderr.log"
        environment = os.environ.copy()
        environment.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
        started = time.perf_counter()
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            try:
                completed = subprocess.run(
                    command,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    timeout=int(args.timeout_seconds),
                    check=False,
                    env=environment,
                )
                returncode = completed.returncode
                command_error = ""
            except subprocess.TimeoutExpired as exc:
                returncode = None
                command_error = repr(exc)
        converter_record["elapsed_seconds"] = round(
            time.perf_counter() - started, 3
        )
        converter_record["returncode"] = returncode
        converter_record["error"] = command_error
        converter_record["stdout"] = {
            "path": str(stdout_path),
            "bytes": stdout_path.stat().st_size,
            "sha256": sha256_file(stdout_path),
        }
        converter_record["stderr"] = {
            "path": str(stderr_path),
            "bytes": stderr_path.stat().st_size,
            "sha256": sha256_file(stderr_path),
        }
        if returncode != 0:
            raise RuntimeError(
                f"converter failed without a shell pipeline; returncode={returncode}, "
                f"error={command_error}"
            )

        if temporary_output.is_symlink() or not temporary_output.is_file():
            raise RuntimeError("converter did not create a regular GGUF output")
        output_stat = temporary_output.stat()
        if not stat.S_ISREG(output_stat.st_mode) or output_stat.st_size <= 4:
            raise RuntimeError("converted GGUF is empty or not a regular file")
        with temporary_output.open("rb") as handle:
            if handle.read(4) != b"GGUF":
                raise RuntimeError("converted output does not have a GGUF header")
        output_sha = sha256_file(temporary_output)

        # Re-hash after the converter exits. Any input mutation invalidates the run.
        if sha256_file(canary_path) != context["canary_receipt_sha256"]:
            raise RuntimeError("canary receipt changed during conversion")
        if sha256_file(Path(context["proof_receipt_path"])) != context[
            "proof_receipt_sha256"
        ]:
            raise RuntimeError("proof receipt changed during conversion")
        adapter_after = tree_hash_manifest(
            Path(context["promotion_contract"]["adapter_path"]),
            exclude_model_card=True,
        )
        if adapter_after["tree_sha256"] != context["adapter_tree"]["tree_sha256"]:
            raise RuntimeError("adapter tree changed during conversion")
        promotion_after = tree_hash_manifest(
            Path(context["merged_path"]), exclude_model_card=True
        )
        complete_after = tree_hash_manifest(
            Path(context["merged_path"]), exclude_model_card=False
        )
        if promotion_after["tree_sha256"] != context["merged_promotion_tree"][
            "tree_sha256"
        ]:
            raise RuntimeError("converter mutated the promotion-bound merged tree")
        if complete_after["tree_sha256"] != context["merged_complete_tree"][
            "tree_sha256"
        ]:
            raise RuntimeError("converter mutated the complete merged input tree")
        if sha256_file(converter_path) != converter_sha:
            raise RuntimeError("converter source changed during conversion")
        if sha256_file(python_path) != python_sha:
            raise RuntimeError("converter Python changed during conversion")

        try:
            validation_record = invoke_gguf_validator(
                gguf_path=temporary_output,
                gguf_sha256=output_sha,
                gguf_bytes=output_stat.st_size,
                validator_path=Path(args.validator),
                validator_python=Path(args.validator_python),
                output_dir=run_dir / "out",
                log_dir=log_dir,
                timeout_seconds=int(args.validator_timeout_seconds),
                max_new_tokens=int(args.validator_max_new_tokens),
                threads=int(args.validator_threads),
            )
            receipt["validation"] = validation_record
            context["gguf_validation"] = validation_record
        except GGUFValidationBlocked as exc:
            receipt["validation"] = exc.record
            raise

        # The validator must be observational: it may read the temporary GGUF but
        # may not change it or any provenance/conversion dependency.
        if sha256_file(temporary_output) != output_sha:
            raise RuntimeError("GGUF validator changed the converted GGUF")
        validator_after = Path(args.validator)
        validator_python_after = Path(args.validator_python)
        if sha256_file(validator_after) != validation_record["validator"]["sha256"]:
            raise RuntimeError("GGUF validator source changed during validation")
        if sha256_file(validator_python_after) != validation_record["validator"][
            "python_sha256"
        ]:
            raise RuntimeError("GGUF validator Python changed during validation")
        if sha256_file(canary_path) != context["canary_receipt_sha256"]:
            raise RuntimeError("canary receipt changed during GGUF validation")
        if sha256_file(Path(context["proof_receipt_path"])) != context[
            "proof_receipt_sha256"
        ]:
            raise RuntimeError("proof receipt changed during GGUF validation")
        adapter_validated = tree_hash_manifest(
            Path(context["promotion_contract"]["adapter_path"]),
            exclude_model_card=True,
        )
        promotion_validated = tree_hash_manifest(
            Path(context["merged_path"]), exclude_model_card=True
        )
        complete_validated = tree_hash_manifest(
            Path(context["merged_path"]), exclude_model_card=False
        )
        if adapter_validated["tree_sha256"] != adapter_after["tree_sha256"]:
            raise RuntimeError("adapter tree changed during GGUF validation")
        if promotion_validated["tree_sha256"] != promotion_after["tree_sha256"]:
            raise RuntimeError("promotion tree changed during GGUF validation")
        if complete_validated["tree_sha256"] != complete_after["tree_sha256"]:
            raise RuntimeError("complete merged tree changed during GGUF validation")
        if sha256_file(converter_path) != converter_sha:
            raise RuntimeError("converter source changed during GGUF validation")
        if sha256_file(python_path) != python_sha:
            raise RuntimeError("converter Python changed during GGUF validation")
        context["post_conversion_verification"] = {
            "canary_receipt_sha256": context["canary_receipt_sha256"],
            "proof_receipt_sha256": context["proof_receipt_sha256"],
            "adapter_tree_sha256": adapter_after["tree_sha256"],
            "promotion_tree_sha256": promotion_after["tree_sha256"],
            "complete_input_tree_sha256": complete_after["tree_sha256"],
            "converter_sha256": converter_sha,
            "converter_python_sha256": python_sha,
            "gguf_sha256_after_validation": output_sha,
            "gguf_validator_sha256": validation_record["validator"]["sha256"],
            "gguf_validator_python_sha256": validation_record["validator"][
                "python_sha256"
            ],
            "gguf_behavioral_validation_passed": True,
            "all_inputs_hash_stable": True,
        }

        os.chmod(temporary_output, 0o444)
        try:
            os.link(temporary_output, final_output)
            output_installed = True
        except FileExistsError as exc:
            raise ConversionBlocked(
                f"refusing concurrent GGUF overwrite: {final_output}"
            ) from exc
        temporary_output.unlink()
        output_record = {
            "gguf_path": str(final_output),
            "gguf_sha256": output_sha,
            "gguf_bytes": final_output.stat().st_size,
            "quantization": quantization.upper(),
            "header": "GGUF",
            "immutable_mode": "0444",
        }
        if sha256_file(final_output) != output_sha:
            raise RuntimeError("final GGUF hash changed during atomic installation")

        receipt = build_conversion_receipt(
            context,
            output_record,
            converter_record,
            {
                "run_id": run_id,
                "origin": args.origin,
                "receipt_path": str(receipt_path),
                "elapsed_seconds": round(time.perf_counter() - t0, 3),
            },
        )
        receipt["receipt_path"] = str(receipt_path)
        receipt["approval_phrase_sha256"] = sha256_bytes(
            args.approval.encode("utf-8")
        )
        write_final_receipt(receipt_path, receipt)
        return receipt
    except Exception as exc:
        if output_installed and final_output is not None and final_output.is_file():
            try:
                final_output.chmod(0o644)
                final_output.unlink()
            except OSError as cleanup_exc:
                receipt["output_cleanup_error"] = repr(cleanup_exc)
        receipt["error"] = repr(exc)
        receipt["finished_at_utc"] = iso_now()
        receipt["run"]["elapsed_seconds"] = round(time.perf_counter() - t0, 3)
        if not receipt_path.exists():
            write_final_receipt(receipt_path, receipt)
        return receipt
    finally:
        if temporary_output is not None and temporary_output.exists():
            try:
                temporary_output.unlink()
            except OSError:
                # A conversion receipt has already captured success/failure. Cleanup
                # trouble must not replace that authoritative result with a new error.
                pass


def status() -> dict[str, Any]:
    if not LATEST_RECEIPT.is_file():
        return {
            "ok": True,
            "schema": "engel_ct246_gguf_conversion_status_v1",
            "latest_present": False,
            "latest_receipt_path": str(LATEST_RECEIPT),
        }
    payload = json.loads(LATEST_RECEIPT.read_text(encoding="utf-8-sig"))
    return {
        "ok": True,
        "schema": "engel_ct246_gguf_conversion_status_v1",
        "latest_present": True,
        "latest_receipt_path": str(LATEST_RECEIPT),
        "latest_conversion_ok": payload.get("ok") is True,
        "immutable_receipt_path": payload.get("receipt_path", ""),
        "output": payload.get("output") or {},
        "updated_at_utc": iso_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--canary-receipt", default="")
    parser.add_argument("--approval", default="")
    parser.add_argument(
        "--converter",
        default="",
        help="explicit CT-local path to convert_hf_to_gguf.py",
    )
    parser.add_argument(
        "--converter-python",
        default=sys.executable,
        help="Python interpreter used for the converter; it is hashed and versioned",
    )
    parser.add_argument(
        "--validator",
        default="",
        help="explicit CT-local path to run_engel_ct246_gguf_canary.py",
    )
    parser.add_argument(
        "--validator-python",
        default="",
        help="explicit CT-local Python with llama-cpp; path and bytes are hashed",
    )
    parser.add_argument("--validator-timeout-seconds", type=int, default=1800)
    parser.add_argument("--validator-max-new-tokens", type=int, default=96)
    parser.add_argument("--validator-threads", type=int, default=8)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--quantization", default="q8_0")
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--origin", default="manual_ct246_gguf_conversion")
    args = parser.parse_args()
    if args.status:
        payload = status()
    else:
        missing = [
            name
            for name, value in (
                ("--canary-receipt", args.canary_receipt),
                ("--approval", args.approval),
                ("--converter", args.converter),
                ("--validator", args.validator),
                ("--validator-python", args.validator_python),
                ("--output-dir", args.output_dir),
            )
            if not str(value).strip()
        ]
        if missing:
            parser.error("required for conversion: " + ", ".join(missing))
        payload = run_conversion(args)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
