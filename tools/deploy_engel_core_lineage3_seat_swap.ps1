[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CanaryReceipt,

    [Parameter(Mandatory = $true)]
    [string]$PromotionApproval,

    [Parameter(Mandatory = $true)]
    [string]$ConversionReceipt,

    [string]$KeyPath = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519",

    [ValidatePattern('^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+$')]
    [string]$SshTarget = "root@192.0.2.50",

    [ValidateRange(1, 65535)]
    [int]$SshPort = 24622,

    [ValidatePattern('^[A-Za-z0-9@_.-]+\.service$')]
    [string]$ServiceName = "engel-main-chat.service",

    [ValidatePattern('^http://127\.0\.0\.1:[0-9]+/health$')]
    [string]$HealthUrl = "http://127.0.0.1:8765/health",

    [ValidatePattern('^http://127\.0\.0\.1:[0-9]+/chat$')]
    [string]$ChatUrl = "http://127.0.0.1:8765/chat"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-ImmutableCtReceiptPath {
    param([string]$Path, [string]$Label)
    if (-not $Path.StartsWith('/opt/engel/', [System.StringComparison]::Ordinal)) {
        throw "$Label must be an absolute CT246 /opt/engel path."
    }
    if ($Path -match '(^|/)\.\.(/|$)' -or $Path -match '[\r\n\x00]') {
        throw "$Label contains an unsafe path component."
    }
    if ([System.IO.Path]::GetFileName($Path).ToUpperInvariant().Contains('LATEST')) {
        throw "$Label must be an immutable receipt, not a LATEST alias."
    }
}

Assert-ImmutableCtReceiptPath -Path $CanaryReceipt -Label "CanaryReceipt"
Assert-ImmutableCtReceiptPath -Path $ConversionReceipt -Label "ConversionReceipt"
if ($PromotionApproval -notmatch '^APPROVE_ENGEL_PROMOTE_LORA_CANARY_[0-9]{8}T[0-9]{6}Z_[A-F0-9]{16}$') {
    throw "PromotionApproval is not a minted canary promotion phrase."
}
if (-not (Test-Path -LiteralPath $KeyPath -PathType Leaf)) {
    throw "CT246 SSH key not found at the supplied KeyPath."
}

# The remote program validates every receipt and artifact before its first mutation.
# It routes directly to a correctly named converted GGUF; it never copies q8 bytes over
# a q5 filename. The only switch is an atomic systemd drop-in replacement, with an
# immutable, unique rollback copy restored automatically on any post-switch failure.
$remoteProgram = @'
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path
from typing import Any

CANARY_SCHEMA = "engel_ct246_lora_canary_gate_receipt_v2"
CONVERSION_SCHEMA = "engel_gguf_conversion_receipt_v2"
CONTRACT_SCHEMA = "engel_lora_promotion_contract_v2"
GGUF_VALIDATION_SCHEMA = "engel_gguf_conversion_validation_binding_v1"
GGUF_VALIDATOR_OUTPUT_SCHEMA = "engel_ct246_gguf_behavioral_canary_output_v1"
GGUF_CANARY_CASE_IDS = ("normal_chat", "identity", "training_truth", "simple_math")
EXPECTED_SERVICE = "engel-main-chat.service"
MODEL_ROOT = Path("/opt/engel/models-active/llm")
RECEIPT_ROOT = Path("/opt/engel/reports/llm_training/deployments")
OVERRIDE_NAME = "90-engel-lora-promoted-model.conf"
ABSENT_SENTINEL = b"__ENGEL_OVERRIDE_ABSENT__\n"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def require_opt_path(path: Path, label: str) -> Path:
    path = Path(path)
    text = str(path)
    if not text.startswith("/opt/engel/") or "/../" in text or text.endswith("/.."):
        raise RuntimeError(f"{label} is outside /opt/engel: {path}")
    return path


def read_immutable(
    path: Path, label: str, require_read_only: bool = False
) -> tuple[dict[str, Any], str, bytes]:
    path = require_opt_path(path, label)
    if "LATEST" in path.name.upper():
        raise RuntimeError(f"{label} must not be a LATEST alias: {path}")
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{label} must be a regular immutable file: {path}")
    if require_read_only and path.stat().st_mode & 0o222:
        raise RuntimeError(f"{label} is still writable; immutable mode is required: {path}")
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} payload is not an object")
    return payload, sha256_bytes(raw), raw


def hash_records(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: str(item["relative_path"])):
        digest.update(str(record["relative_path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["bytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).upper().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest().upper()


def tree_hash(root: Path) -> dict[str, Any]:
    root = require_opt_path(root, "artifact tree")
    if not root.is_dir():
        raise RuntimeError(f"artifact tree missing: {root}")
    resolved_root = root.resolve()
    records: list[dict[str, Any]] = []
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.name == "ENGEL_MODEL_CARD.json":
            continue
        try:
            relative = file.resolve().relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"artifact file escapes tree: {file}") from exc
        records.append({
            "relative_path": relative,
            "bytes": file.stat().st_size,
            "sha256": sha256_file(file),
        })
    if not records:
        raise RuntimeError(f"artifact tree contains no files: {root}")
    return {
        "root": str(root),
        "file_count": len(records),
        "total_bytes": sum(int(item["bytes"]) for item in records),
        "tree_sha256": hash_records(records),
    }


def file_record(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "present": False}
    return {
        "path": str(path),
        "present": True,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {command!r}; "
            f"stderr={(completed.stderr or '')[-1000:]}"
        )
    return completed


def service_environment(service: str) -> dict[str, str]:
    raw = run(
        ["systemctl", "show", service, "--property=Environment", "--value"]
    ).stdout.strip()
    values: dict[str, str] = {}
    for token in shlex.split(raw):
        if "=" in token:
            key, value = token.split("=", 1)
            values[key] = value
    return values


def http_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"non-object response from {url}")
    return parsed


def contains_value(value: Any, expected: str) -> bool:
    if isinstance(value, dict):
        return any(contains_value(item, expected) for item in value.values())
    if isinstance(value, list):
        return any(contains_value(item, expected) for item in value)
    return str(value) == expected


def conversion_contract_blockers(
    conversion: dict[str, Any], expected_bindings: dict[str, str]
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    """Pure fail-closed validator, kept testable without SSH or service mutation."""
    blockers: list[str] = []
    if conversion.get("schema") != CONVERSION_SCHEMA:
        blockers.append(
            f"conversion receipt schema cannot prove provenance; require {CONVERSION_SCHEMA} "
            "with bindings for immutable canary/proof receipts, promotion contract, "
            "adapter tree, merged tree, and output GGUF"
        )
    if conversion.get("ok") is not True:
        blockers.append("conversion receipt is not ok")
    bindings = conversion.get("bindings")
    output = conversion.get("output")
    if not isinstance(bindings, dict):
        blockers.append("conversion receipt lacks a bindings object")
        bindings = {}
    if not isinstance(output, dict):
        blockers.append("conversion receipt lacks an output object")
        output = {}
    for key, expected in expected_bindings.items():
        actual = str(bindings.get(key) or "")
        if key.endswith("sha256"):
            actual = actual.upper()
        if actual != expected:
            blockers.append(f"conversion binding mismatch: {key}")

    validation = conversion.get("validation")
    if not isinstance(validation, dict):
        blockers.append("conversion receipt lacks mandatory GGUF validation")
        validation = {}
    if validation.get("schema") != GGUF_VALIDATION_SCHEMA:
        blockers.append("GGUF validation binding schema mismatch")
    if validation.get("ok") is not True:
        blockers.append("GGUF behavioral validation did not pass")
    output_sha = str(output.get("gguf_sha256") or "").upper()
    if str(validation.get("gguf_sha256") or "").upper() != output_sha:
        blockers.append("GGUF validation is not bound to the output SHA-256")
    try:
        if int(validation.get("gguf_bytes") or -1) != int(
            output.get("gguf_bytes") or -2
        ):
            blockers.append("GGUF validation is not bound to the output byte count")
    except (TypeError, ValueError):
        blockers.append("GGUF validation/output byte counts are invalid")

    validator = validation.get("validator")
    if not isinstance(validator, dict):
        blockers.append("GGUF validation lacks validator provenance")
        validator = {}
    if Path(str(validator.get("path") or "")).name != "run_engel_ct246_gguf_canary.py":
        blockers.append("GGUF validation did not use the canonical validator source")
    for key in (
        "sha256",
        "version_sha256",
        "python_sha256",
        "command_sha256",
        "invocation_contract_sha256",
    ):
        if not re.fullmatch(r"[A-F0-9]{64}", str(validator.get(key) or "").upper()):
            blockers.append(f"GGUF validator provenance lacks a valid {key}")
    validator_version = str(validator.get("version") or "")
    if not validator_version:
        blockers.append("GGUF validator version is empty")
    elif sha256_bytes(validator_version.encode("utf-8")) != str(
        validator.get("version_sha256") or ""
    ).upper():
        blockers.append("GGUF validator version hash mismatch")
    command = validator.get("command")
    if not isinstance(command, list) or not command:
        blockers.append("GGUF validator command is missing")
    else:
        actual_command_sha = sha256_bytes(
            json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        if actual_command_sha != str(validator.get("command_sha256") or "").upper():
            blockers.append("GGUF validator command hash mismatch")

    for stream_name in ("stdout", "stderr"):
        stream = validation.get(stream_name)
        if not isinstance(stream, dict) or not re.fullmatch(
            r"[A-F0-9]{64}", str((stream or {}).get("sha256") or "").upper()
        ):
            blockers.append(f"GGUF validation lacks bound {stream_name} hash")

    case_ids = validation.get("case_ids")
    cases = validation.get("cases")
    if list(case_ids or []) != list(GGUF_CANARY_CASE_IDS):
        blockers.append("GGUF validation case IDs differ from the canonical contract")
    if (
        not isinstance(cases, list)
        or len(cases) != len(GGUF_CANARY_CASE_IDS)
        or any(not isinstance(row, dict) for row in cases)
        or [str(row.get("id") or "") for row in cases]
        != list(GGUF_CANARY_CASE_IDS)
    ):
        blockers.append("GGUF validation case results are incomplete or reordered")
    else:
        for row in cases:
            if row.get("ok") is not True or list(row.get("quality_failures") or []):
                blockers.append("one or more GGUF behavioral validation cases failed")
                break
    if not re.fullmatch(
        r"[A-F0-9]{64}", str(validation.get("case_contract_sha256") or "").upper()
    ):
        blockers.append("GGUF validation lacks a case-contract hash")
    validator_output = validation.get("validator_output")
    if not isinstance(validator_output, dict):
        blockers.append("GGUF validation lacks canonical validator output")
        validator_output = {}
    validator_output_sha = str(
        validation.get("validator_output_sha256") or ""
    ).upper()
    if canonical_json_sha256(validator_output) != validator_output_sha:
        blockers.append("canonical GGUF validator output hash mismatch")
    try:
        validator_output_bytes_match = int(
            validator_output.get("gguf_bytes") or -1
        ) == int(output.get("gguf_bytes") or -2)
    except (TypeError, ValueError):
        validator_output_bytes_match = False
    if (
        validator_output.get("schema") != GGUF_VALIDATOR_OUTPUT_SCHEMA
        or validator_output.get("ok") is not True
        or str(validator_output.get("gguf_sha256") or "").upper() != output_sha
        or not validator_output_bytes_match
        or str(validator_output.get("validator_version") or "")
        != validator_version
        or list(validator_output.get("case_ids") or []) != list(GGUF_CANARY_CASE_IDS)
        or validator_output.get("rows") != cases
        or str(validator_output.get("case_contract_sha256") or "").upper()
        != str(validation.get("case_contract_sha256") or "").upper()
    ):
        blockers.append("canonical validator output is not a passed result for this GGUF")
    return blockers, bindings, output


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
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


def write_deployment_receipt(path: Path, receipt: dict[str, Any]) -> None:
    encoded = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write(path, encoded, mode=0o444)


def rollback_override(
    override_path: Path, backup_path: Path, service: str, old_targets: dict[str, str]
) -> dict[str, Any]:
    result: dict[str, Any] = {"attempted": True, "ok": False}
    try:
        backup = backup_path.read_bytes()
        if backup == ABSENT_SENTINEL:
            if override_path.exists():
                override_path.unlink()
        else:
            atomic_write(override_path, backup)
        run(["systemctl", "daemon-reload"])
        run(["systemctl", "restart", service])
        run(["systemctl", "is-active", "--quiet", service])
        restored = service_environment(service)
        result["restored_target_environment"] = {
            key: restored.get(key, "")
            for key in ("ENGEL_LOCAL_GGUF_MODEL", "ENGEL_QUICK_CHAT_GGUF_MODEL")
        }
        for key, expected in old_targets.items():
            if restored.get(key, "") != expected:
                raise RuntimeError(f"rollback environment mismatch for {key}")
        result["ok"] = True
    except Exception as exc:
        result["error"] = repr(exc)
    return result


def main() -> int:
    if len(sys.argv) != 7:
        raise RuntimeError("expected canary, approval, conversion, service, health, chat")
    canary_path = Path(sys.argv[1])
    approval = sys.argv[2]
    conversion_path = Path(sys.argv[3])
    service = sys.argv[4]
    health_url = sys.argv[5]
    chat_url = sys.argv[6]
    if service != EXPECTED_SERVICE:
        raise RuntimeError(f"refusing unexpected service: {service}")
    if not re.fullmatch(r"http://127\.0\.0\.1:\d+/(health|chat)", health_url):
        raise RuntimeError("health URL must be CT loopback")
    if not re.fullmatch(r"http://127\.0\.0\.1:\d+/(health|chat)", chat_url):
        raise RuntimeError("chat URL must be CT loopback")

    deployment_id = f"{stamp()}_{uuid.uuid4().hex[:10]}"
    receipt_path = RECEIPT_ROOT / f"ENGEL_CT246_LORA_DEPLOYMENT_{deployment_id}.json"
    receipt: dict[str, Any] = {
        "ok": False,
        "schema": "engel_ct246_lora_deployment_receipt_v2",
        "deployment_id": deployment_id,
        "started_at_utc": now(),
        "canary_receipt_path": str(canary_path),
        "conversion_receipt_path": str(conversion_path),
        "service": service,
        "health_url": health_url,
        "chat_url": chat_url,
        "approval_phrase_sha256": sha256_bytes(approval.encode("utf-8")),
        "mutation_started": False,
        "rollback": {"attempted": False, "ok": None},
    }
    override_dir = Path(f"/etc/systemd/system/{service}.d")
    override_path = override_dir / OVERRIDE_NAME
    backup_path: Path | None = None
    old_targets: dict[str, str] = {}

    try:
        canary, canary_sha, _ = read_immutable(
            canary_path, "canary receipt", require_read_only=True
        )
        conversion, conversion_sha, _ = read_immutable(
            conversion_path, "conversion receipt"
        )
        receipt["canary_receipt_sha256"] = canary_sha
        receipt["conversion_receipt_sha256"] = conversion_sha
        blockers: list[str] = []
        if canary.get("schema") != CANARY_SCHEMA:
            blockers.append(f"canary schema must be {CANARY_SCHEMA}")
        if not all(
            canary.get(key) is True for key in ("ok", "canary_passed", "promotion_ready")
        ):
            blockers.append("canary is not passed and promotion-ready")
        if str(canary.get("receipt_path") or "") != str(canary_path):
            blockers.append("canary receipt_path does not match the immutable file")
        if str(canary.get("promotion_approval_required") or "") != approval:
            blockers.append("promotion phrase does not exactly match the minted canary phrase")

        contract = canary.get("promotion_contract")
        if not isinstance(contract, dict) or contract.get("schema") != CONTRACT_SCHEMA:
            blockers.append(f"promotion contract must use {CONTRACT_SCHEMA}")
            contract = {}
        contract_sha = canonical_json_sha256(contract) if contract else ""
        if contract_sha != str(canary.get("promotion_contract_sha256") or "").upper():
            blockers.append("promotion contract SHA-256 does not match canary receipt")
        expected_phrase = (
            f"APPROVE_ENGEL_PROMOTE_LORA_CANARY_{canary.get('run_stamp')}_"
            f"{contract_sha[:16]}"
        )
        if approval != expected_phrase:
            blockers.append("promotion phrase is not bound to this contract digest")
        if str(contract.get("canary_receipt_path") or "") != str(canary_path):
            blockers.append("promotion contract names a different canary receipt")

        proof_path = Path(str(contract.get("proof_receipt_path") or ""))
        try:
            proof, proof_sha, _ = read_immutable(proof_path, "proof receipt")
            receipt["proof_receipt_path"] = str(proof_path)
            receipt["proof_receipt_sha256"] = proof_sha
            if proof_sha != str(contract.get("proof_receipt_sha256") or "").upper():
                blockers.append("actual proof receipt SHA-256 differs from promotion contract")
            if not all(
                (
                    proof.get("ok") is True,
                    proof.get("artifact_status") == "proven",
                    proof.get("proof_pointer_advanced") is True,
                )
            ):
                blockers.append("immutable proof is no longer a promoted proof artifact")
        except Exception as exc:
            blockers.append("immutable proof validation failed: " + repr(exc))
            proof_sha = ""

        adapter_path = Path(str(contract.get("adapter_path") or ""))
        merged_path = Path(str(contract.get("merged_path") or ""))
        try:
            adapter_tree = tree_hash(adapter_path)
            merged_tree = tree_hash(merged_path)
            receipt["adapter_tree"] = adapter_tree
            receipt["merged_tree"] = merged_tree
            if adapter_tree["tree_sha256"] != str(
                contract.get("adapter_tree_sha256") or ""
            ).upper():
                blockers.append("actual adapter tree hash differs from canary contract")
            if merged_tree["tree_sha256"] != str(
                contract.get("merged_tree_sha256") or ""
            ).upper():
                blockers.append("actual merged tree hash differs from canary contract")
        except Exception as exc:
            blockers.append("artifact tree validation failed: " + repr(exc))

        expected_bindings = {
            "canary_receipt_path": str(canary_path),
            "canary_receipt_sha256": canary_sha,
            "promotion_contract_sha256": contract_sha,
            "proof_receipt_path": str(proof_path),
            "proof_receipt_sha256": proof_sha,
            "adapter_tree_sha256": str(contract.get("adapter_tree_sha256") or "").upper(),
            "merged_path": str(merged_path),
            "merged_tree_sha256": str(contract.get("merged_tree_sha256") or "").upper(),
        }
        conversion_blockers, bindings, output = conversion_contract_blockers(
            conversion, expected_bindings
        )
        blockers.extend(conversion_blockers)

        gguf_path = Path(str(output.get("gguf_path") or ""))
        quantization = str(output.get("quantization") or "").strip()
        try:
            gguf_path = require_opt_path(gguf_path, "converted GGUF")
            gguf_path.resolve().relative_to(MODEL_ROOT.resolve())
            if gguf_path.is_symlink() or not gguf_path.is_file():
                raise RuntimeError("converted GGUF must be a regular file")
            if gguf_path.suffix.casefold() != ".gguf":
                raise RuntimeError("converted output is not a .gguf file")
            quant_slug = re.sub(r"[^a-z0-9]+", "_", quantization.casefold()).strip("_")
            name_slug = re.sub(r"[^a-z0-9]+", "_", gguf_path.name.casefold()).strip("_")
            if not quant_slug or quant_slug not in name_slug:
                raise RuntimeError("GGUF filename does not identify its quantization")
            if quant_slug.startswith("q8") and re.search(r"q5", name_slug):
                raise RuntimeError("refusing q8 bytes under a q5-named GGUF")
            gguf = file_record(gguf_path)
            receipt["converted_gguf"] = gguf
            if gguf["sha256"] != str(output.get("gguf_sha256") or "").upper():
                blockers.append("actual GGUF SHA-256 differs from conversion receipt")
            if int(gguf["bytes"]) != int(output.get("gguf_bytes") or -1):
                blockers.append("actual GGUF byte count differs from conversion receipt")
        except Exception as exc:
            blockers.append("GGUF validation failed: " + repr(exc))

        if blockers:
            receipt["blockers"] = blockers
            raise RuntimeError("deployment blocked before mutation: " + "; ".join(blockers))

        # Capture every currently selected model hash and the exact route override before
        # changing anything. These records make rollback and later root-cause review exact.
        old_environment = service_environment(service)
        old_targets = {
            key: old_environment.get(key, "")
            for key in ("ENGEL_LOCAL_GGUF_MODEL", "ENGEL_QUICK_CHAT_GGUF_MODEL")
        }
        receipt["pre_deploy_environment"] = old_targets
        receipt["pre_deploy_model_files"] = {
            key: file_record(Path(value)) if value else {"path": "", "present": False}
            for key, value in old_targets.items()
        }
        receipt["pre_deploy_override"] = file_record(override_path)

        # Re-read every mutable dependency immediately before the atomic switch.
        if sha256_file(canary_path) != canary_sha:
            raise RuntimeError("canary receipt changed during deployment preflight")
        if sha256_file(conversion_path) != conversion_sha:
            raise RuntimeError("conversion receipt changed during deployment preflight")
        if sha256_file(proof_path) != proof_sha:
            raise RuntimeError("proof receipt changed during deployment preflight")
        if tree_hash(adapter_path)["tree_sha256"] != adapter_tree["tree_sha256"]:
            raise RuntimeError("adapter tree changed during deployment preflight")
        if tree_hash(merged_path)["tree_sha256"] != merged_tree["tree_sha256"]:
            raise RuntimeError("merged tree changed during deployment preflight")
        if sha256_file(gguf_path) != gguf["sha256"]:
            raise RuntimeError("GGUF changed during deployment preflight")
        receipt["pre_mutation_reverified"] = True

        override_dir.mkdir(parents=True, exist_ok=True)
        backup_path = override_dir / (
            f"{OVERRIDE_NAME}.rollback.{deployment_id}.{canary_sha[:12]}.bak"
        )
        backup_bytes = override_path.read_bytes() if override_path.is_file() else ABSENT_SENTINEL
        descriptor = os.open(
            backup_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444
        )
        with os.fdopen(descriptor, "wb") as backup_handle:
            backup_handle.write(backup_bytes)
            backup_handle.flush()
            os.fsync(backup_handle.fileno())
        os.chmod(backup_path, 0o444)
        if sha256_file(backup_path) != sha256_bytes(backup_bytes):
            raise RuntimeError("rollback backup hash does not match the live override")
        receipt["rollback_backup"] = file_record(backup_path)

        override = (
            "[Service]\n"
            f'Environment="ENGEL_LOCAL_GGUF_MODEL={gguf_path}"\n'
            f'Environment="ENGEL_QUICK_CHAT_GGUF_MODEL={gguf_path}"\n'
        ).encode("utf-8")
        receipt["mutation_started"] = True
        atomic_write(override_path, override)
        run(["systemctl", "daemon-reload"])
        run(["systemctl", "restart", service])
        run(["systemctl", "is-active", "--quiet", service])

        deployed_environment = service_environment(service)
        for key in ("ENGEL_LOCAL_GGUF_MODEL", "ENGEL_QUICK_CHAT_GGUF_MODEL"):
            if deployed_environment.get(key) != str(gguf_path):
                raise RuntimeError(f"service environment did not switch {key}")
        deployed_hash = sha256_file(gguf_path)
        if deployed_hash != gguf["sha256"]:
            raise RuntimeError("deployed GGUF hash changed after service restart")

        health = http_json(health_url)
        if health.get("ok") is not True or not contains_value(health, str(gguf_path)):
            raise RuntimeError("health route does not prove the deployed GGUF path")
        route = http_json(
            chat_url,
            {"message": "Good morning Engel. Reply naturally in one short sentence."},
        )
        route_receipt = route.get("receipt") if isinstance(route.get("receipt"), dict) else {}
        runtime_provider = str(
            route.get("runtime_provider") or route_receipt.get("runtime_provider") or ""
        )
        if (
            route.get("ok") is not True
            or runtime_provider != "llama-cpp-python-local-gguf"
            or not contains_value(route, str(gguf_path))
        ):
            raise RuntimeError("chat route did not execute the deployed local GGUF")

        receipt.update({
            "ok": True,
            "status": "deployed and route-verified",
            "production_chat_affected": True,
            "deployed_gguf_path": str(gguf_path),
            "deployed_gguf_sha256": deployed_hash,
            "post_deploy_environment": {
                key: deployed_environment.get(key, "")
                for key in ("ENGEL_LOCAL_GGUF_MODEL", "ENGEL_QUICK_CHAT_GGUF_MODEL")
            },
            "health_verification": health,
            "route_verification": route,
            "finished_at_utc": now(),
        })
        write_deployment_receipt(receipt_path, receipt)
        print(json.dumps({
            "ok": True,
            "deployment_receipt_path": str(receipt_path),
            "deployed_gguf_path": str(gguf_path),
            "deployed_gguf_sha256": deployed_hash,
        }, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        receipt["error"] = repr(exc)
        if receipt.get("mutation_started") is True and backup_path is not None:
            receipt["rollback"] = rollback_override(
                override_path, backup_path, service, old_targets
            )
        receipt["finished_at_utc"] = now()
        try:
            write_deployment_receipt(receipt_path, receipt)
        except Exception as receipt_exc:
            print(
                json.dumps({
                    "ok": False,
                    "error": repr(exc),
                    "deployment_receipt_error": repr(receipt_exc),
                }, indent=2, sort_keys=True),
                file=sys.stderr,
            )
            return 1
        print(json.dumps({
            "ok": False,
            "error": repr(exc),
            "rollback": receipt.get("rollback"),
            "deployment_receipt_path": str(receipt_path),
        }, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'@

$remoteProgram = $remoteProgram -replace "`r`n", "`n"
$sshArguments = @(
    '-i', $KeyPath,
    '-p', [string]$SshPort,
    $SshTarget,
    'python3', '-',
    $CanaryReceipt,
    $PromotionApproval,
    $ConversionReceipt,
    $ServiceName,
    $HealthUrl,
    $ChatUrl
)

$result = $remoteProgram | & ssh @sshArguments 2>&1
$exitCode = $LASTEXITCODE
$result | Write-Output
if ($exitCode -ne 0) {
    throw "CT246 deployment refused or rolled back (ssh exit $exitCode). See the emitted immutable deployment receipt."
}
