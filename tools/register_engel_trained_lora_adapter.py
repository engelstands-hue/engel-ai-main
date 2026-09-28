from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PROFILE_DIR = ROOT / "runtime" / "engel_standalone_chat_llm"
WORKSPACE_PROFILE_PATH = WORKSPACE_PROFILE_DIR / "engel_chat_profile.json"
WORKSPACE_MANIFEST_PATH = WORKSPACE_PROFILE_DIR / "trained_lora_adapter_manifest.json"
WORKSPACE_LORA_VERIFIER = ROOT / "runtime" / "engel_lora_training_artifact_verifier_latest.json"
WORKSPACE_RECEIPT_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "receipts"

RUNPOD_MEMORY_ROOT = Path(os.environ.get("ENGEL_RUNPOD_MEMORY_ROOT", str(ROOT / "runtime" / "runpod")))
EXTERNAL_PROFILE_DIR = RUNPOD_MEMORY_ROOT / "standalone_chat_llm"
EXTERNAL_PROFILE_PATH = EXTERNAL_PROFILE_DIR / "engel_chat_profile.json"
EXTERNAL_MANIFEST_PATH = EXTERNAL_PROFILE_DIR / "trained_lora_adapter_manifest.json"
EXTERNAL_RECEIPT_DIR = EXTERNAL_PROFILE_DIR / "receipts"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_os_drive(path: Path) -> bool:
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if is_os_drive(path):
        raise RuntimeError(f"refusing to write on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_record(files: list[dict[str, Any]], path_name: str) -> dict[str, Any]:
    for item in files:
        if item.get("path") == path_name:
            return item
    return {}


def build_manifest(verifier: dict[str, Any]) -> dict[str, Any]:
    files = verifier.get("files") if isinstance(verifier.get("files"), list) else []
    adapter = file_record(files, "adapter_model.safetensors")
    config = file_record(files, "adapter_config.json")
    training_receipt = file_record(files, "ENGEL_LORA_TRAINING_RECEIPT.json")
    return {
        "ok": bool(verifier.get("ok") is True and adapter and config),
        "schema": "engel_trained_lora_adapter_manifest_v1",
        "updated_at_utc": iso_now(),
        "training_base_model": verifier.get("training_base_model", ""),
        "training_gpu_name": verifier.get("training_gpu_name", ""),
        "training_max_steps": verifier.get("training_max_steps", ""),
        "training_elapsed_seconds": verifier.get("training_elapsed_seconds", ""),
        "training_receipt_ok": verifier.get("training_receipt_ok"),
        "local_artifact_dir": verifier.get("local_artifact_dir", ""),
        "external_artifact_dir": verifier.get("external_artifact_dir", ""),
        "adapter_model": adapter,
        "adapter_config": config,
        "training_receipt": training_receipt,
        "runtime_loaded_by_current_chat_endpoint": False,
        "runtime_note": (
            "This is a real trained LoRA adapter artifact. The existing standalone chat endpoint must be launched "
            "with this adapter before live chat replies can be claimed as adapter-served."
        ),
        "stage_receipts": verifier.get("stage_receipts", {}),
    }


def register() -> dict[str, Any]:
    verifier = load_json(WORKSPACE_LORA_VERIFIER)
    if verifier.get("ok") is not True:
        raise RuntimeError(f"latest LoRA verifier is missing or not ok: {WORKSPACE_LORA_VERIFIER}")
    manifest = build_manifest(verifier)
    if manifest["ok"] is not True:
        raise RuntimeError("latest LoRA verifier does not include required adapter files")

    profile = load_json(WORKSPACE_PROFILE_PATH)
    profile.update(
        {
            "weights_finetuned": True,
            "trained_adapter_available": True,
            "trained_adapter_loaded_by_current_chat_runtime": False,
            "trained_lora_adapter_manifest_path": str(WORKSPACE_MANIFEST_PATH),
            "trained_lora_adapter": manifest,
            "weights_finetune_claim": (
                "Real RunPod LoRA training completed and produced adapter_model.safetensors. "
                "The current chat endpoint is not marked adapter-loaded until a serving runtime loads this adapter."
            ),
        }
    )

    write_json(WORKSPACE_MANIFEST_PATH, manifest)
    write_json(EXTERNAL_MANIFEST_PATH, manifest)
    write_json(WORKSPACE_PROFILE_PATH, profile)
    write_json(EXTERNAL_PROFILE_PATH, profile)

    receipt = {
        "ok": True,
        "schema": "engel_trained_lora_adapter_registration_v1",
        "updated_at_utc": iso_now(),
        "workspace_profile_path": str(WORKSPACE_PROFILE_PATH),
        "external_profile_path": str(EXTERNAL_PROFILE_PATH),
        "workspace_manifest_path": str(WORKSPACE_MANIFEST_PATH),
        "external_manifest_path": str(EXTERNAL_MANIFEST_PATH),
        "adapter_model_sha256": manifest["adapter_model"].get("sha256"),
        "adapter_model_bytes": manifest["adapter_model"].get("bytes"),
        "training_base_model": manifest["training_base_model"],
        "training_gpu_name": manifest["training_gpu_name"],
        "training_max_steps": manifest["training_max_steps"],
        "runtime_loaded_by_current_chat_endpoint": False,
        "api_key_value_visible": False,
        "c_drive_used": False,
    }
    stamp = utc_stamp()
    workspace_receipt = WORKSPACE_RECEIPT_DIR / f"ENGEL_LORA_ADAPTER_REGISTER_{stamp}.json"
    external_receipt = EXTERNAL_RECEIPT_DIR / f"ENGEL_LORA_ADAPTER_REGISTER_{stamp}.json"
    receipt["workspace_receipt_path"] = str(workspace_receipt)
    receipt["external_receipt_path"] = str(external_receipt)
    write_json(workspace_receipt, receipt)
    write_json(external_receipt, receipt)
    return receipt


def main() -> int:
    receipt = register()
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
