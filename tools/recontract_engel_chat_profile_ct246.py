#!/usr/bin/env python3
"""Re-contract Engel's active chat profile to CT246 plus the D:-local ROG fallback."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "runtime" / "engel_standalone_chat_llm" / "engel_chat_profile.json"
MANIFEST = ROOT / "runtime" / "engel_standalone_chat_llm" / "trained_lora_adapter_manifest.json"
REPORT = ROOT / "reports" / "engel_standalone_chat_llm" / "ENGEL_CHAT_PROFILE_CT246_LATEST.json"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def recontract() -> dict[str, Any]:
    profile = load_json(PROFILE)
    manifest = load_json(MANIFEST)
    if manifest.get("ok") is not True:
        raise ValueError("trained LoRA manifest is not verified")
    adapter = manifest.get("adapter_model_gguf") if isinstance(manifest.get("adapter_model_gguf"), dict) else {}
    base_model = str(manifest.get("serving_base_gguf_model_path") or "").strip()
    adapter_path = str(adapter.get("absolute_path") or "").strip()
    if not base_model.startswith("/opt/engel/models-active/llm/"):
        raise ValueError(f"trained base model is not CT246 SSD-backed: {base_model}")
    if not adapter_path.startswith("/opt/engel/models-active/lora/"):
        raise ValueError(f"trained adapter is not CT246 SSD-backed: {adapter_path}")

    if os.name == "nt":
        local_model = ROOT / "runtime" / "gpu_models" / "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
        local_runtime = ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "cargo-target" / "debug" / "engel-ai-rs.exe"
        local_cuda_dir = ROOT / "runtime" / "gpu_llm_venv" / "Lib" / "site-packages" / "llama_cpp" / "lib"
        if not local_model.is_file() or not local_runtime.is_file() or not local_cuda_dir.is_dir():
            raise ValueError("ROG D:-local GPU fallback is incomplete")
        model_name = local_model.name
    else:
        local_model = Path(base_model)
        local_runtime = ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "cargo-target" / "debug" / "engel-ai-rs"
        local_cuda_dir = ROOT / "runtime"
        model_name = Path(base_model).name

    updated_at = utc_stamp()
    profile.update({
        "updated_at_utc": updated_at,
        "active_runtime_note": (
            "CT246 is the primary Engel chat/model runtime. The ROG GPU fallback uses only D:-local runtime files; "
            "CT246 loads its active model and trained adapter from /opt/engel SSD storage."
        ),
        "model": model_name,
        "local_gguf_model_path": str(local_model),
        "local_gguf_model_present": local_model.is_file(),
        "local_cuda_runtime_path": str(local_runtime),
        "local_cuda_runtime_present": local_runtime.is_file(),
        "local_cuda_dll_dir": str(local_cuda_dir),
        "local_cuda_dll_dir_present": local_cuda_dir.is_dir(),
        "external_profile_path": "/opt/engel/runtime/engel_standalone_chat_llm/engel_chat_profile.json",
        "external_build_receipt_path": "/opt/engel/reports/engel_standalone_chat_llm/ENGEL_STANDALONE_CHAT_LLM_PROFILE_LOCAL.json",
        "trained_lora_adapter": manifest,
        "trained_lora_adapter_manifest_path": str(MANIFEST),
        "trained_lora_adapter_gguf_path": adapter_path,
        "trained_lora_adapter_gguf_sha256": str(adapter.get("sha256") or ""),
        "trained_lora_base_gguf_model_path": base_model,
        "trained_lora_conversion_receipt_path": str(manifest.get("conversion_receipt_path") or ""),
        "trained_adapter_available": True,
        "trained_adapter_loaded_by_current_chat_runtime": bool(manifest.get("runtime_loaded_by_current_chat_endpoint")),
        "storage_authority": {
            "container": "CT246",
            "hostname": "engel-ai-main",
            "proxmox_node": "engel-spine-01",
            "active_runtime": "/opt/engel",
            "archive": "/mnt/engel-hdd-vault",
            "archive_runtime_allowed": False,
            "google_drive_used": False,
            "power_vault_used": False,
        },
    })
    encoded = json.dumps(profile, sort_keys=True)
    forbidden = [
        match.group(0)
        for match in re.finditer(r"(?i)(?:[efg]:\\|google drive|my drive|engel_app_memory|/mnt/engel-vault|engel-vault-main)", encoded)
    ]
    if forbidden:
        raise ValueError(f"detached/forbidden active profile references remain: {sorted(set(forbidden))}")
    write_json(PROFILE, profile)

    receipt = {
        "schema": "engel_chat_profile_ct246_recontract_v1",
        "ok": True,
        "updated_at_utc": updated_at,
        "profile_path": str(PROFILE),
        "manifest_path": str(MANIFEST),
        "container": "CT246",
        "hostname": "engel-ai-main",
        "proxmox_node": "engel-spine-01",
        "local_rog_fallback_model": str(local_model),
        "ct246_base_model": base_model,
        "ct246_adapter": adapter_path,
        "google_drive_used": False,
        "power_vault_used": False,
    }
    write_json(REPORT, receipt)
    return receipt


def main() -> int:
    try:
        receipt = recontract()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
