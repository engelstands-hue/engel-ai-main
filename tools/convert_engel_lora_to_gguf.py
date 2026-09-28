from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from safetensors.torch import safe_open


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "runtime" / "engel_standalone_chat_llm" / "trained_lora_adapter_manifest.json"
DEFAULT_BASE_MODEL = Path("/opt/engel/models-active/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m.gguf")

GGUF_MAGIC = b"GGUF"
GGUF_VERSION = 3
GGUF_ALIGNMENT = 32

GGUF_TYPE_UINT32 = 4
GGUF_TYPE_FLOAT32 = 6
GGUF_TYPE_STRING = 8

GGML_TYPE_F32 = 0


TENSOR_MAP = {
    "q_proj": "attn_q",
    "k_proj": "attn_k",
    "v_proj": "attn_v",
    "o_proj": "attn_output",
    "gate_proj": "ffn_gate",
    "up_proj": "ffn_up",
    "down_proj": "ffn_down",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def gguf_string(value: str) -> bytes:
    data = value.encode("utf-8")
    return struct.pack("<Q", len(data)) + data


def gguf_kv_string(key: str, value: str) -> bytes:
    return gguf_string(key) + struct.pack("<I", GGUF_TYPE_STRING) + gguf_string(value)


def gguf_kv_u32(key: str, value: int) -> bytes:
    return gguf_string(key) + struct.pack("<II", GGUF_TYPE_UINT32, int(value))


def gguf_kv_f32(key: str, value: float) -> bytes:
    return gguf_string(key) + struct.pack("<If", GGUF_TYPE_FLOAT32, float(value))


def pad_len(offset: int, alignment: int = GGUF_ALIGNMENT) -> int:
    return (alignment - (offset % alignment)) % alignment


def convert_tensor_name(name: str) -> str:
    match = re.fullmatch(
        r"base_model\.model\.model\.layers\.(\d+)\.(self_attn|mlp)\."
        r"(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)\.lora_([AB])\.weight",
        name,
    )
    if not match:
        raise ValueError(f"unsupported LoRA tensor name: {name}")
    layer, _block, module, side = match.groups()
    suffix = "lora_a" if side == "A" else "lora_b"
    return f"blk.{int(layer)}.{TENSOR_MAP[module]}.weight.{suffix}"


def adapter_paths(manifest_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    manifest = read_json(manifest_path)
    artifact_dir = Path(str(manifest.get("local_artifact_dir") or ""))
    if not artifact_dir.is_dir():
        raise FileNotFoundError(f"local artifact dir missing: {artifact_dir}")
    adapter = artifact_dir / str(manifest.get("adapter_model", {}).get("path") or "adapter_model.safetensors")
    config = artifact_dir / str(manifest.get("adapter_config", {}).get("path") or "adapter_config.json")
    if not adapter.is_file():
        raise FileNotFoundError(adapter)
    if not config.is_file():
        raise FileNotFoundError(config)
    return adapter, config, manifest


def load_tensors(adapter_path: Path) -> list[dict[str, Any]]:
    tensors: list[dict[str, Any]] = []
    with safe_open(str(adapter_path), framework="pt", device="cpu") as handle:
        for source_name in sorted(handle.keys(), key=lambda item: [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", item)]):
            target_name = convert_tensor_name(source_name)
            tensor = handle.get_tensor(source_name).detach().cpu().to(dtype=None)
            array = tensor.numpy().astype(np.float32, copy=False)
            contiguous = np.ascontiguousarray(array)
            tensors.append(
                {
                    "name": target_name,
                    "source_name": source_name,
                    "shape": list(contiguous.shape),
                    "gguf_dims": list(reversed(contiguous.shape)),
                    "dtype": GGML_TYPE_F32,
                    "data": contiguous.tobytes(order="C"),
                }
            )
    return tensors


def write_gguf(path: Path, tensors: list[dict[str, Any]], metadata: list[bytes]) -> None:
    tensor_infos = bytearray()
    data_offset = 0
    for item in tensors:
        data = item["data"]
        data_offset += pad_len(data_offset)
        item["offset"] = data_offset
        dims = item["gguf_dims"]
        tensor_infos += gguf_string(item["name"])
        tensor_infos += struct.pack("<I", len(dims))
        for dim in dims:
            tensor_infos += struct.pack("<Q", int(dim))
        tensor_infos += struct.pack("<I", int(item["dtype"]))
        tensor_infos += struct.pack("<Q", int(item["offset"]))
        data_offset += len(data)

    header = bytearray()
    header += GGUF_MAGIC
    header += struct.pack("<IQQ", GGUF_VERSION, len(tensors), len(metadata))
    for kv in metadata:
        header += kv
    header += tensor_infos
    header += b"\x00" * pad_len(len(header))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(header)
        current = 0
        for item in tensors:
            padding = int(item["offset"]) - current
            if padding > 0:
                handle.write(b"\x00" * padding)
                current += padding
            data = item["data"]
            handle.write(data)
            current += len(data)


def convert(manifest_path: Path, output_path: Path, base_model_path: Path) -> dict[str, Any]:
    adapter_path, config_path, manifest = adapter_paths(manifest_path)
    config = read_json(config_path)
    base_model = Path(base_model_path)
    if not base_model.is_file():
        raise FileNotFoundError(base_model)
    if str(config.get("base_model_name_or_path") or "") != "Qwen/Qwen2.5-7B-Instruct":
        raise RuntimeError("adapter config base model is not Qwen/Qwen2.5-7B-Instruct")
    tensors = load_tensors(adapter_path)
    alpha = float(config.get("lora_alpha") or 0.0)
    metadata = [
        gguf_kv_string("general.architecture", "qwen2"),
        gguf_kv_string("general.name", "engel-qwen2.5-7b-instruct-lora"),
        gguf_kv_string("general.type", "adapter"),
        gguf_kv_u32("general.file_type", 0),
        gguf_kv_u32("general.alignment", GGUF_ALIGNMENT),
        gguf_kv_string("adapter.type", "lora"),
        gguf_kv_f32("adapter.lora.alpha", alpha),
        gguf_kv_string("adapter.lora.task_name", str(config.get("task_type") or "CAUSAL_LM")),
    ]
    write_gguf(output_path, tensors, metadata)
    receipt = {
        "ok": True,
        "schema": "engel_lora_peft_to_gguf_conversion_v1",
        "converted_at_utc": iso_now(),
        "manifest_path": str(manifest_path),
        "source_adapter_safetensors": str(adapter_path),
        "source_adapter_sha256": sha256_file(adapter_path),
        "source_config": str(config_path),
        "base_model_path": str(base_model),
        "base_model_sha256": sha256_file(base_model),
        "output_adapter_gguf": str(output_path),
        "output_adapter_gguf_bytes": output_path.stat().st_size,
        "output_adapter_gguf_sha256": sha256_file(output_path),
        "tensor_count": len(tensors),
        "lora_alpha": alpha,
        "lora_rank": int(config.get("r") or 0),
        "training_base_model": manifest.get("training_base_model"),
        "runtime_target": "llama.cpp --lora",
    }
    receipt_path = output_path.with_name("ENGEL_LORA_GGUF_CONVERSION_RECEIPT.json")
    write_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    write_json(receipt_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert Engel PEFT LoRA safetensors to llama.cpp GGUF LoRA.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--base-model", default=str(DEFAULT_BASE_MODEL))
    parser.add_argument("--output", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest_path = Path(args.manifest)
    adapter_path, _config_path, _manifest = adapter_paths(manifest_path)
    output = Path(args.output) if args.output else adapter_path.with_name("adapter_model.gguf")
    receipt = convert(manifest_path, output, Path(args.base_model))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
