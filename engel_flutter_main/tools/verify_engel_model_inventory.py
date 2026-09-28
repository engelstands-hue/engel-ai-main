#!/usr/bin/env python3
"""Build or verify the Engel local/free model inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "dist" / "ENGEL_MODEL_INVENTORY_20260607.json"
MODEL_ROOTS = [
    Path(r"F:\ENGEL_APP_MEMORY\models"),
    Path(r"E:\ENGEL_APP_MEMORY\models"),
    Path(r"G:\ENGEL_APP_MEMORY\models"),
    ROOT / "models",
]
COSMOS_ROOT = Path(r"F:\ENGEL_APP_MEMORY\models\cosmos3")
MANUAL_ROOT = Path(r"G:\ENGEL_APP_MEMORY\models\manual_downloads")
MODEL_SUFFIXES = {".gguf", ".safetensors"}
REQUIRED_GGUF = [
    r"G:\ENGEL_APP_MEMORY\models\manual_downloads\mistral-7b-instruct-v0.3\Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
    r"G:\ENGEL_APP_MEMORY\models\manual_downloads\qwen2.5-0.5b-instruct\qwen2.5-0.5b-instruct-q5_k_m.gguf",
    r"G:\ENGEL_APP_MEMORY\models\manual_downloads\qwen2.5-3b-instruct\qwen2.5-3b-instruct-q5_k_m.gguf",
    r"G:\ENGEL_APP_MEMORY\models\manual_downloads\qwen2.5-7b-instruct\qwen2.5-7b-instruct-q5_k_m.gguf",
    r"G:\ENGEL_APP_MEMORY\models\manual_downloads\qwen2.5-7b-instruct\qwen2.5-7b-instruct-q5_k_m-00001-of-00002.gguf",
    r"G:\ENGEL_APP_MEMORY\models\manual_downloads\qwen2.5-7b-instruct\qwen2.5-7b-instruct-q5_k_m-00002-of-00002.gguf",
]
REQUIRED_COSMOS_FOLDERS = [
    "Cosmos3-Nano",
    "Cosmos3-Nano-Policy-DROID",
    "Cosmos3-Super",
    "Cosmos3-Super-Image2Video",
    "Cosmos3-Super-Text2Image",
]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def model_files_under(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in MODEL_SUFFIXES
    ]
    return sorted(files, key=lambda path: str(path).lower())


def file_row(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(
            stat.st_mtime,
            timezone.utc,
        ).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "suffix": path.suffix.lower(),
    }


def build_inventory() -> dict[str, object]:
    all_model_files: list[Path] = []
    root_rows = []
    for root in MODEL_ROOTS:
        files = model_files_under(root)
        all_model_files.extend(files)
        root_rows.append(
            {
                "path": str(root),
                "exists": root.exists(),
                "model_file_count": len(files),
                "model_bytes": sum(path.stat().st_size for path in files),
            }
        )

    gguf_files = [path for path in all_model_files if path.suffix.lower() == ".gguf"]
    safetensors_files = [
        path for path in all_model_files if path.suffix.lower() == ".safetensors"
    ]
    cosmos_files = model_files_under(COSMOS_ROOT)
    manual_files = model_files_under(MANUAL_ROOT)
    manual_gguf_files = [path for path in manual_files if path.suffix.lower() == ".gguf"]
    cosmos_folders = [
        path.name for path in sorted(COSMOS_ROOT.iterdir(), key=lambda item: item.name.lower())
        if path.is_dir()
    ] if COSMOS_ROOT.exists() else []

    inventory = {
        "schema": "engel_model_inventory_v1",
        "generated_at_utc": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "model_roots": root_rows,
        "cosmos_root": str(COSMOS_ROOT),
        "manual_download_root": str(MANUAL_ROOT),
        "counts": {
            "all_model_files": len(all_model_files),
            "gguf_files": len(gguf_files),
            "safetensors_files": len(safetensors_files),
            "cosmos_files": len(cosmos_files),
            "cosmos_folders": len(cosmos_folders),
            "manual_download_model_files": len(manual_files),
            "manual_download_gguf_files": len(manual_gguf_files),
            "total_model_bytes": sum(path.stat().st_size for path in all_model_files),
        },
        "required_gguf": [file_row(Path(path_text)) for path_text in REQUIRED_GGUF],
        "required_cosmos_folders": cosmos_folders,
        "manual_download_files": [file_row(path) for path in manual_files],
        "cosmos_summary": [
            {
                "folder": folder,
                "path": str(COSMOS_ROOT / folder),
                "model_file_count": len(model_files_under(COSMOS_ROOT / folder)),
                "model_bytes": sum(path.stat().st_size for path in model_files_under(COSMOS_ROOT / folder)),
            }
            for folder in cosmos_folders
        ],
        "routing_policy": [
            "planner chooses local/free before paid or remote routes",
            "GGUF text models route through local LLM lane",
            "Cosmos3 roots route through multimodal/action lane",
            "remote provider or RunPod routes remain guarded",
        ],
    }
    canonical = json.dumps(inventory, indent=2, sort_keys=True)
    inventory["inventory_content_sha256"] = sha256_text(canonical)
    return inventory


def verify_inventory(inventory: dict[str, object], current: dict[str, object]) -> None:
    require(inventory.get("schema") == "engel_model_inventory_v1", "inventory schema mismatch")
    for root in MODEL_ROOTS:
        root_text = str(root)
        if root.exists():
            continue
        if root_text.endswith(r"Engel App\models"):
            continue
        require(root.parent.exists(), f"model memory root missing: {root.parent}")
    for path_text in REQUIRED_GGUF:
        path = Path(path_text)
        require(path.exists(), f"required GGUF missing: {path}")
        require(path.stat().st_size > 0, f"required GGUF empty: {path}")
    for folder in REQUIRED_COSMOS_FOLDERS:
        path = COSMOS_ROOT / folder
        require(path.exists(), f"required Cosmos3 folder missing: {path}")
        require(model_files_under(path), f"required Cosmos3 folder has no model files: {path}")

    comparable_current = dict(current)
    comparable_inventory = dict(inventory)
    comparable_current.pop("generated_at_utc", None)
    comparable_inventory.pop("generated_at_utc", None)
    comparable_current.pop("inventory_content_sha256", None)
    comparable_inventory.pop("inventory_content_sha256", None)
    require(
        comparable_inventory == comparable_current,
        "model inventory does not match current disk scan",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write current inventory")
    args = parser.parse_args()
    current = build_inventory()

    if args.write:
        INVENTORY.parent.mkdir(parents=True, exist_ok=True)
        INVENTORY.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "wrote": str(INVENTORY), "counts": current["counts"]}, indent=2))
        return 0

    require(INVENTORY.exists(), f"inventory missing: {INVENTORY}")
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    verify_inventory(inventory, current)
    print(
        json.dumps(
            {
                "ok": True,
                "inventory": str(INVENTORY),
                "counts": inventory["counts"],
                "required_gguf_checked": len(REQUIRED_GGUF),
                "required_cosmos_folders_checked": len(REQUIRED_COSMOS_FOLDERS),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1)
