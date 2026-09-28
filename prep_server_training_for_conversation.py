#!/usr/bin/env python
"""Prep the LoRA training package on D: for server (RunPod) training focused on real conversation feel."""
import json
from pathlib import Path
import zipfile
import hashlib
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
PKG_DIR = ROOT / "runtime" / "engel_lora_training_package"
DATASET = PKG_DIR / "dataset" / "engel_standalone_sft.jsonl"
ZIP_PATH = PKG_DIR / "engel_standalone_lora_training_package.zip"
MANIFEST = PKG_DIR / "manifest.json"

print("=== Prep server training for better conversational Chat LLM ===")

# 1. Enhance dataset with natural conversation examples
lines = DATASET.read_text(encoding="utf-8").strip().splitlines()
print(f"Current dataset rows: {len(lines)}")

conv_examples = [
    {"messages": [
        {"role": "system", "content": "You are Engel AI Main, Joshua's local companion. Speak like a real ongoing conversation - natural, direct, with memory of what was just said."},
        {"role": "user", "content": "the last version felt robotic"},
        {"role": "assistant", "content": "Right, the low temp and strict guards were making it stiff. I bumped temperature and rewrote the prompt assembly so replies flow better and reference prior turns naturally."}
    ]},
    {"messages": [
        {"role": "system", "content": "You are Engel AI Main..."},
        {"role": "user", "content": "remember we were tuning the SSD chat?"},
        {"role": "assistant", "content": "Yes. The goal was to make the fast local model on CT246 SSD feel like a normal back-and-forth instead of reading instructions. Prompt labels and sampling are the main levers."}
    ]},
    {"messages": [
        {"role": "system", "content": "You are Engel AI Main..."},
        {"role": "user", "content": "keep it short this time"},
        {"role": "assistant", "content": "Got it. Short answer: changes are live for more natural chat."}
    ]},
]

for ex in conv_examples:
    lines.append(json.dumps(ex, ensure_ascii=False))

DATASET.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Updated dataset rows: {len(lines)}")

# 2. Rebuild the zip (local only)
print("Rebuilding zip...")
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
    for p in PKG_DIR.rglob("*"):
        if p.is_file() and p != ZIP_PATH:
            arcname = p.relative_to(PKG_DIR)
            zf.write(p, arcname)
print(f"Zip updated: {ZIP_PATH}")

# 3. Update manifest (D: only)
sha = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest().upper()
manifest = {
    "base_model_default": "qwen2.5-7b-instruct" if "qwen" in str(DATASET.read_text()) else "mistralai/Mistral-7B-Instruct-v0.3",
    "dataset_rows": len(lines),
    "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest().upper(),
    "training_output_root": "/mnt/engel-hdd-vault/training-outputs/runpod/standalone_llm_training",
    "ok": True,
    "schema": "engel_lora_training_package_v2",
    "training_kind": "real LoRA adapter fine-tune package focused on natural conversation for Chat LLM on SSD",
    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    "workspace_root": str(PKG_DIR),
    "zip_path": str(ZIP_PATH),
    "zip_sha256": sha,
}
MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print("Manifest updated on D:.")

print("\nPackage ready for server training.")
print("Next (when budget confirmed): use tools/run_engel_lora_training_on_runpod.py with --budget-usd")
