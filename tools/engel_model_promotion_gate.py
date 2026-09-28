#!/usr/bin/env python3
"""Gate LoRA adapter promotion into Engel AI Main chat.

This script separates "a trained adapter exists" from "the live chat route is
serving it." Promotion requires a verified training artifact, a GGUF LoRA
adapter for the local llama.cpp runtime, a rollback snapshot, and an explicit
approval token. It never uses the CT245 offline-vault path.
"""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.request
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LATEST_VERIFIER = ROOT / "runtime" / "engel_lora_training_artifact_verifier_latest.json"
ACTIVE_MANIFEST = ROOT / "runtime" / "engel_standalone_chat_llm" / "trained_lora_adapter_manifest.json"
REPORT_DIR = ROOT / "reports" / "llm_training"
ROLLBACK_DIR = REPORT_DIR / "model_promotion_rollbacks"
APPROVAL_TOKEN = "APPROVE_ENGEL_MODEL_PROMOTION_V1"
SCHEMA = "ENGEL_MODEL_PROMOTION_GATE_V1"

FORBIDDEN_PATH_MARKERS = (
    "/mnt/" + "engel-vault",
    "\\mnt\\" + "engel-vault",
    "engel-" + "vault-main",
    "offline-ct245-vault",
    "CT245",
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def posix_foreign(path: Path) -> bool:
    """A POSIX-absolute path (e.g. /opt/engel/...) belongs to the CT-side lane
    and cannot be checked from a Windows host. Report it as cross-host, never
    as plainly 'missing' with a backslash-mangled render."""
    return os.name == "nt" and str(path).replace("\\", "/").startswith("/")


def render_path(path: Path) -> str:
    return path.as_posix() if posix_foreign(path) else str(path)


def forbidden_path(path: str | Path) -> str:
    text = str(path)
    normalized = text.replace("\\", "/")
    for marker in FORBIDDEN_PATH_MARKERS:
        if marker.replace("\\", "/").lower() in normalized.lower():
            return marker
    return ""


def file_record(files: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for item in files:
        if item.get("path") == name:
            return item
    return {}


def path_from_env_or_candidates(value: str, candidates: list[Path]) -> Path:
    env = os.environ.get(value, "").strip()
    if env:
        return Path(env).expanduser()
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def default_base_model(active: dict[str, Any]) -> Path:
    manifest_path = str(active.get("serving_base_gguf_model_path") or "").strip()
    candidates = [
        Path("/opt/engel/models-active/llm/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m.gguf"),
        ROOT / "models-active" / "llm" / "qwen2.5-7b-instruct" / "qwen2.5-7b-instruct-q5_k_m.gguf",
    ]
    if manifest_path:
        candidates.append(Path(manifest_path))
    return path_from_env_or_candidates("ENGEL_TRAINED_LORA_BASE_GGUF_MODEL", candidates)


def resolve_artifact_dir(latest: dict[str, Any]) -> Path:
    raw_text = str(latest.get("local_artifact_dir") or latest.get("external_artifact_dir") or "")
    raw = Path(raw_text)
    if raw.is_dir():
        return raw
    name = re.split(r"[\\/]+", raw_text.rstrip("\\/"))[-1]
    if name:
        for candidate in [
            Path("/opt/engel/models-active/lora") / name,
            ROOT / "models-active" / "lora" / name,
            ROOT / "runtime" / "engel_lora_training_artifacts" / name,
        ]:
            if candidate.is_dir():
                return candidate
    return raw


def latest_state(base_model: Path | None = None) -> dict[str, Any]:
    latest = read_json(LATEST_VERIFIER)
    active = read_json(ACTIVE_MANIFEST)
    files = latest.get("files") if isinstance(latest.get("files"), list) else []
    adapter = file_record(files, "adapter_model.safetensors")
    config = file_record(files, "adapter_config.json")
    training_receipt = file_record(files, "ENGEL_LORA_TRAINING_RECEIPT.json")
    artifact_dir = resolve_artifact_dir(latest)
    base = base_model or default_base_model(active)
    gguf_path = artifact_dir / "adapter_model.gguf"
    conversion_receipt = artifact_dir / "ENGEL_LORA_GGUF_CONVERSION_RECEIPT.json"
    conversion = read_json(conversion_receipt)
    active_adapter_sha = str((active.get("adapter_model") or {}).get("sha256") or "")
    latest_adapter_sha = str(adapter.get("sha256") or "")

    errors: list[str] = []
    warnings: list[str] = []
    if latest.get("ok") is not True or latest.get("training_receipt_ok") is not True:
        errors.append("latest RunPod artifact verifier is missing or not ok")
    if not artifact_dir.is_dir():
        errors.append(f"latest artifact directory missing: {artifact_dir}")
    if forbidden_path(artifact_dir):
        errors.append(f"latest artifact directory uses forbidden storage: {artifact_dir}")
    if not adapter:
        errors.append("latest verifier missing adapter_model.safetensors record")
    elif (artifact_dir / str(adapter.get("path") or "adapter_model.safetensors")).is_file():
        actual = sha256_file(artifact_dir / str(adapter.get("path") or "adapter_model.safetensors"))
        if actual.casefold() != latest_adapter_sha.casefold():
            errors.append("latest adapter_model.safetensors sha256 mismatch")
    else:
        errors.append("latest adapter_model.safetensors file missing")
    if not config or not (artifact_dir / str(config.get("path") or "adapter_config.json")).is_file():
        errors.append("latest adapter_config.json missing")
    if not training_receipt:
        warnings.append("latest verifier missing ENGEL_LORA_TRAINING_RECEIPT.json file record")
    if forbidden_path(base):
        errors.append(f"base model uses forbidden storage: {base}")
    if not base.is_file():
        if posix_foreign(base):
            # Fail-closed either way -- promotion still blocks -- but the
            # receipt must say WHY honestly: the file lives on the CT-side
            # lane, it is not "missing" on a path this host could ever check.
            errors.append(
                "serving base GGUF model is on the CT-side lane and cannot be "
                f"checked from this host: {base.as_posix()} (run the gate on "
                "CT, or point ENGEL_TRAINED_LORA_BASE_GGUF_MODEL at a local copy)"
            )
        else:
            errors.append(f"serving base GGUF model missing: {base}")
    if not gguf_path.is_file():
        errors.append(f"GGUF LoRA adapter missing: {gguf_path}")
    if not conversion_receipt.is_file() or conversion.get("ok") is not True:
        errors.append(f"conversion receipt missing or not ok: {conversion_receipt}")
    else:
        if str(conversion.get("source_adapter_sha256") or "").casefold() != latest_adapter_sha.casefold():
            errors.append("conversion receipt source adapter sha256 does not match latest artifact")
        if str(conversion.get("base_model_sha256") or "").casefold() != (sha256_file(base).casefold() if base.is_file() else ""):
            errors.append("conversion receipt base model sha256 does not match serving base")
        if str(conversion.get("output_adapter_gguf_sha256") or "").casefold() != (sha256_file(gguf_path).casefold() if gguf_path.is_file() else ""):
            errors.append("conversion receipt output GGUF sha256 does not match file")

    ready_for_promotion = not errors
    latest_is_active = bool(latest_adapter_sha and active_adapter_sha and latest_adapter_sha.casefold() == active_adapter_sha.casefold())
    return {
        "schema": SCHEMA,
        "checked_at_utc": iso_now(),
        "scope": "rog_adapter_lane",
        "scope_note": (
            "This gate sees the ROG-local adapter manifest and GGUF-conversion "
            "lane only. CT-side merged-GGUF deploys (receipts under "
            "/opt/engel/reports/llm_training/) are outside its view, so "
            "latest_is_active=false does NOT mean the latest training is "
            "unserved -- it means it is not serving through THIS lane."
        ),
        "ready_for_promotion": ready_for_promotion,
        "latest_is_active": latest_is_active,
        "errors": errors,
        "warnings": warnings,
        "latest_verifier_path": str(LATEST_VERIFIER),
        "active_manifest_path": str(ACTIVE_MANIFEST),
        "latest_artifact_dir": str(artifact_dir),
        "latest_artifact_dir_from_verifier": str(latest.get("local_artifact_dir") or latest.get("external_artifact_dir") or ""),
        "serving_base_gguf_model_path": render_path(base),
        "serving_base_gguf_model_present": base.is_file(),
        "latest_adapter_sha256": latest_adapter_sha,
        "active_adapter_sha256": active_adapter_sha,
        "adapter_gguf_path": str(gguf_path),
        "adapter_gguf_present": gguf_path.is_file(),
        "adapter_gguf_sha256": sha256_file(gguf_path) if gguf_path.is_file() else "",
        "conversion_receipt_path": str(conversion_receipt),
        "conversion_receipt_present": conversion_receipt.is_file(),
        "conversion_receipt_ok": conversion.get("ok") is True,
        "latest_training_base_model": latest.get("training_base_model", ""),
        "latest_training_gpu_name": latest.get("training_gpu_name", ""),
        "latest_training_max_steps": latest.get("training_max_steps", ""),
        "latest_training_elapsed_seconds": latest.get("training_elapsed_seconds", ""),
        "active_runtime_loaded_by_current_chat_endpoint": active.get("runtime_loaded_by_current_chat_endpoint") is True,
    }


def build_candidate_manifest(state: dict[str, Any]) -> dict[str, Any]:
    latest = read_json(LATEST_VERIFIER)
    files = latest.get("files") if isinstance(latest.get("files"), list) else []
    artifact_dir = Path(state["latest_artifact_dir"])
    adapter = file_record(files, "adapter_model.safetensors")
    config = file_record(files, "adapter_config.json")
    training_receipt = file_record(files, "ENGEL_LORA_TRAINING_RECEIPT.json")
    conversion = read_json(Path(state["conversion_receipt_path"]))
    return {
        "ok": True,
        "schema": "engel_trained_lora_adapter_manifest_v1",
        "updated_at_utc": iso_now(),
        "model_promotion_schema": SCHEMA,
        "model_promotion_candidate": True,
        "training_base_model": latest.get("training_base_model", ""),
        "training_gpu_name": latest.get("training_gpu_name", ""),
        "training_max_steps": latest.get("training_max_steps", ""),
        "training_elapsed_seconds": latest.get("training_elapsed_seconds", ""),
        "training_receipt_ok": latest.get("training_receipt_ok"),
        "local_artifact_dir": str(artifact_dir),
        "external_artifact_dir": str(artifact_dir),
        "adapter_model": adapter,
        "adapter_config": config,
        "training_receipt": training_receipt,
        "adapter_model_gguf": {
            "path": "adapter_model.gguf",
            "absolute_path": state["adapter_gguf_path"],
            "bytes": Path(state["adapter_gguf_path"]).stat().st_size,
            "sha256": state["adapter_gguf_sha256"],
        },
        "conversion_receipt_path": state["conversion_receipt_path"],
        "serving_base_gguf_model_path": state["serving_base_gguf_model_path"],
        "serving_base_gguf_model_sha256": conversion.get("base_model_sha256", ""),
        "runtime_loaded_by_current_chat_endpoint": False,
        "runtime_note": "Candidate manifest built by Engel model promotion gate; live flag is set only after promotion and probe.",
        "stage_receipts": latest.get("stage_receipts", {}),
    }


def build_conversion_manifest(base_model: Path | None = None) -> dict[str, Any]:
    latest = read_json(LATEST_VERIFIER)
    active = read_json(ACTIVE_MANIFEST)
    base = base_model or default_base_model(active)
    files = latest.get("files") if isinstance(latest.get("files"), list) else []
    adapter = file_record(files, "adapter_model.safetensors")
    config = file_record(files, "adapter_config.json")
    training_receipt = file_record(files, "ENGEL_LORA_TRAINING_RECEIPT.json")
    artifact_dir = resolve_artifact_dir(latest)
    errors: list[str] = []
    if latest.get("ok") is not True or latest.get("training_receipt_ok") is not True:
        errors.append("latest RunPod artifact verifier is missing or not ok")
    if not artifact_dir.is_dir():
        errors.append(f"latest artifact directory missing: {artifact_dir}")
    if forbidden_path(artifact_dir):
        errors.append(f"latest artifact directory uses forbidden storage: {artifact_dir}")
    if not adapter or not (artifact_dir / str(adapter.get("path") or "adapter_model.safetensors")).is_file():
        errors.append("latest adapter_model.safetensors missing")
    if not config or not (artifact_dir / str(config.get("path") or "adapter_config.json")).is_file():
        errors.append("latest adapter_config.json missing")
    if forbidden_path(base):
        errors.append(f"base model uses forbidden storage: {base}")
    if not base.is_file():
        errors.append(f"serving base GGUF model missing: {base}")
    if errors:
        raise RuntimeError("; ".join(errors))
    return {
        "ok": True,
        "schema": "engel_trained_lora_adapter_manifest_v1",
        "updated_at_utc": iso_now(),
        "model_promotion_schema": SCHEMA,
        "model_promotion_conversion_manifest": True,
        "training_base_model": latest.get("training_base_model", ""),
        "training_gpu_name": latest.get("training_gpu_name", ""),
        "training_max_steps": latest.get("training_max_steps", ""),
        "training_elapsed_seconds": latest.get("training_elapsed_seconds", ""),
        "training_receipt_ok": latest.get("training_receipt_ok"),
        "local_artifact_dir": str(artifact_dir),
        "external_artifact_dir": str(artifact_dir),
        "adapter_model": adapter,
        "adapter_config": config,
        "training_receipt": training_receipt,
        "serving_base_gguf_model_path": str(base),
        "runtime_loaded_by_current_chat_endpoint": False,
        "runtime_note": "Temporary manifest for PEFT-to-GGUF conversion; not an active chat manifest.",
        "stage_receipts": latest.get("stage_receipts", {}),
    }


def write_status(state: dict[str, Any], prefix: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{prefix}_{utc_stamp()}.json"
    write_json(path, state)
    return path


def probe_chat(url: str, prompt: str, timeout: int) -> dict[str, Any]:
    payload = json.dumps({"prompt": prompt, "max_tokens": 96}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                obj = {"raw": text}
            reply = str(obj.get("reply") or obj.get("text") or obj.get("assistant_reply") or obj.get("response") or "")
            return {"ok": bool(reply.strip()), "url": url, "response": obj, "reply_preview": reply[:300]}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def cmd_status(args: argparse.Namespace) -> int:
    state = latest_state(Path(args.base_model) if args.base_model else None)
    path = write_status(state, "ENGEL_MODEL_PROMOTION_STATUS")
    print(json.dumps({"ok": True, "ready_for_promotion": state["ready_for_promotion"], "latest_is_active": state["latest_is_active"], "report": str(path), "errors": state["errors"]}, indent=2, sort_keys=True))
    return 0 if state["ready_for_promotion"] else 1


def cmd_candidate(args: argparse.Namespace) -> int:
    state = latest_state(Path(args.base_model) if args.base_model else None)
    state_path = write_status(state, "ENGEL_MODEL_PROMOTION_CANDIDATE_CHECK")
    if not state["ready_for_promotion"]:
        print(json.dumps({"ok": False, "report": str(state_path), "errors": state["errors"]}, indent=2, sort_keys=True))
        return 1
    manifest = build_candidate_manifest(state)
    candidate_path = Path(args.output) if args.output else REPORT_DIR / f"trained_lora_adapter_manifest_candidate_{utc_stamp()}.json"
    write_json(candidate_path, manifest)
    print(json.dumps({"ok": True, "candidate_manifest": str(candidate_path), "check_report": str(state_path), "latest_adapter_sha256": state["latest_adapter_sha256"]}, indent=2, sort_keys=True))
    return 0


def cmd_conversion_manifest(args: argparse.Namespace) -> int:
    try:
        manifest = build_conversion_manifest(Path(args.base_model) if args.base_model else None)
        output = Path(args.output) if args.output else REPORT_DIR / f"trained_lora_adapter_manifest_conversion_{utc_stamp()}.json"
        write_json(output, manifest)
        print(json.dumps({"ok": True, "conversion_manifest": str(output), "artifact_dir": manifest["local_artifact_dir"], "base_model": manifest["serving_base_gguf_model_path"]}, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        report = {"schema": SCHEMA, "ok": False, "created_at_utc": iso_now(), "blocked_reason": str(exc)}
        path = write_status(report, "ENGEL_MODEL_PROMOTION_CONVERSION_MANIFEST_BLOCKED")
        print(json.dumps({"ok": False, "receipt": str(path), "blocked_reason": str(exc)}, indent=2, sort_keys=True))
        return 1


def cmd_promote(args: argparse.Namespace) -> int:
    state = latest_state(Path(args.base_model) if args.base_model else None)
    receipt: dict[str, Any] = {
        "schema": "ENGEL_MODEL_PROMOTION_RECEIPT_V1",
        "created_at_utc": iso_now(),
        "ok": False,
        "apply_performed": False,
        "approval_token_present": args.approval_token == APPROVAL_TOKEN,
        "state": state,
    }
    if args.approval_token != APPROVAL_TOKEN:
        receipt["blocked_reason"] = "missing approval token"
        path = write_status(receipt, "ENGEL_MODEL_PROMOTION_BLOCKED")
        print(json.dumps({"ok": False, "receipt": str(path), "blocked_reason": receipt["blocked_reason"]}, indent=2, sort_keys=True))
        return 1
    if not state["ready_for_promotion"]:
        receipt["blocked_reason"] = "candidate not ready for promotion"
        path = write_status(receipt, "ENGEL_MODEL_PROMOTION_BLOCKED")
        print(json.dumps({"ok": False, "receipt": str(path), "errors": state["errors"]}, indent=2, sort_keys=True))
        return 1

    ROLLBACK_DIR.mkdir(parents=True, exist_ok=True)
    rollback = ROLLBACK_DIR / f"trained_lora_adapter_manifest_before_promotion_{utc_stamp()}.json"
    if ACTIVE_MANIFEST.is_file():
        shutil.copy2(ACTIVE_MANIFEST, rollback)
    candidate = build_candidate_manifest(state)
    candidate["model_promotion_candidate"] = False
    candidate["model_promoted_at_utc"] = iso_now()
    candidate["model_promotion_receipt_pending"] = True
    write_json(ACTIVE_MANIFEST, candidate)
    receipt.update(
        {
            "apply_performed": True,
            "active_manifest_path": str(ACTIVE_MANIFEST),
            "rollback_manifest_path": str(rollback),
            "promoted_adapter_sha256": state["latest_adapter_sha256"],
            "promoted_adapter_gguf_sha256": state["adapter_gguf_sha256"],
        }
    )

    probe = {}
    if args.probe_url:
        probe = probe_chat(args.probe_url, args.probe_prompt, args.probe_timeout)
        receipt["probe"] = probe
        if probe.get("ok") is True:
            candidate["runtime_loaded_by_current_chat_endpoint"] = True
            candidate["model_promotion_receipt_pending"] = False
            candidate["model_promotion_probe_passed_at_utc"] = iso_now()
            write_json(ACTIVE_MANIFEST, candidate)
            receipt["ok"] = True
        elif args.require_probe:
            shutil.copy2(rollback, ACTIVE_MANIFEST)
            receipt["apply_performed"] = False
            receipt["rolled_back"] = True
            receipt["blocked_reason"] = "live probe failed after manifest write"
        else:
            receipt["ok"] = True
            receipt["warning"] = "live probe failed or unavailable; manifest written but runtime_loaded flag remains false"
    else:
        receipt["ok"] = True
        receipt["warning"] = "no live probe requested; manifest written but runtime_loaded flag remains false"

    path = write_status(receipt, "ENGEL_MODEL_PROMOTION_RECEIPT")
    print(json.dumps({"ok": receipt["ok"], "receipt": str(path), "probe_ok": probe.get("ok") if probe else None, "active_manifest": str(ACTIVE_MANIFEST)}, indent=2, sort_keys=True))
    return 0 if receipt["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gate Engel trained LoRA adapter promotion.")
    parser.add_argument("--base-model", default="")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    conversion = sub.add_parser("conversion-manifest")
    conversion.add_argument("--output", default="")
    candidate = sub.add_parser("candidate")
    candidate.add_argument("--output", default="")
    promote = sub.add_parser("promote")
    promote.add_argument("--approval-token", default="")
    promote.add_argument("--probe-url", default="")
    promote.add_argument("--probe-prompt", default="Say one short sentence as Engel. Do not mention backend details.")
    promote.add_argument("--probe-timeout", type=int, default=90)
    promote.add_argument("--require-probe", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "status":
        return cmd_status(args)
    if args.command == "candidate":
        return cmd_candidate(args)
    if args.command == "conversion-manifest":
        return cmd_conversion_manifest(args)
    if args.command == "promote":
        return cmd_promote(args)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
