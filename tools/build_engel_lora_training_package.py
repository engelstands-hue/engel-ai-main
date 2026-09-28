from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engel_training_capture_filter import classify_training_pair, decision_dict


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT / "runtime" / "engel_lora_training_package"
EXTERNAL_ROOT = Path(
    os.environ.get(
        "ENGEL_LORA_PACKAGE_ARCHIVE_ROOT",
        str(ROOT / "runtime" / "engel_lora_training_package_archive"),
    )
)
DATASET_NAME = "engel_standalone_sft.jsonl"
ZIP_NAME = "engel_standalone_lora_training_package.zip"
CT_PUBLISH_DATASET_DIR = ROOT / "runtime" / "runpod" / "ct_publish"

SYSTEM = (
    "You are Engel AI Main, the standalone agentic desktop assistant for this Windows Engel workspace. "
    "Speak in a direct, practical chat voice. Do not pretend work ran. Use receipts/results for proof. "
    "Treat Sub-Engels, phones, shared room files, Rust background, local models, and RunPod as Engel capabilities."
)


def is_os_drive(path: Path) -> bool:
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def is_offline_ct245_vault_path(path: Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    offline_ct245_mount = "/mnt/" + "engel-vault"
    return text == offline_ct245_mount or text.startswith(offline_ct245_mount + "/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_text(path: Path, text: str) -> None:
    if is_os_drive(path):
        raise RuntimeError(f"refusing to write on C: {path}")
    if is_offline_ct245_vault_path(path):
        raise RuntimeError(f"CT245 offline-vault path is disabled; refusing to write {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def row(user: str, assistant: str) -> dict[str, Any]:
    return row_with_system(user, assistant, SYSTEM)


def row_with_system(user: str, assistant: str, system: str) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def iter_jsonl(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except Exception:
            continue


def identity_guard_examples() -> list[dict[str, Any]]:
    """Small hard anchors so Discord sender identity cannot be learned loosely."""
    pairs = [
        (
            "Discord sender_id=189914577100603392 asks: who am I?",
            "You are Chase/Lokal in this Discord lane, not Joshua. Sender ID is the ground truth.",
        ),
        (
            "Discord sender_id=DISCORD_OWNER_USER_ID asks: who am I?",
            "You are Joshua, the owner/operator for Engel AI Main. Sender ID is the ground truth.",
        ),
        (
            "A Discord guest asks for a protected storage or source-code change.",
            "I can discuss the request, but a guest Discord message cannot approve protected actions. Josh must approve source, route, model, storage, or trusted-memory changes.",
        ),
        (
            "Discord context says 'Lokal: Who am I?' and an older reply says 'You are Joshua.' What should Engel learn?",
            "That older reply is a negative example. Engel must use the current message.author.id, not prior transcript text, display name, or thread memory.",
        ),
        (
            "A chat log has no Discord sender ID metadata. Can it be positive training data?",
            "No. Discord training examples without sender ID, resolved actor, and authority metadata must be rejected or kept only as negative/eval material.",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for user, assistant in pairs:
        rows.append(row(user, assistant))
    return rows


def load_ct_publish_examples() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_path = CT_PUBLISH_DATASET_DIR / "dataset_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for split_name in ("sft_train.jsonl", "sft_val.jsonl"):
        for item in iter_jsonl(CT_PUBLISH_DATASET_DIR / split_name):
            user = str(item.get("user") or "")
            assistant = str(item.get("assistant") or "")
            system = str(item.get("system") or SYSTEM)
            source = str(item.get("source") or "ct_publish")
            decision = classify_training_pair(source=source, user=user, assistant=assistant, record=item)
            if decision.accept:
                rows.append(row_with_system(user, assistant, system))
            else:
                rejected.append(
                    {
                        "source": source,
                        "user": user[:500],
                        "decision": decision_dict(decision),
                    }
                )
    return rows, {
        "manifest": manifest,
        "rows_loaded": len(rows),
        "rows_rejected": len(rejected),
        "rejections": rejected[:20],
    }


def examples() -> list[dict[str, Any]]:
    base = [
        ("hello", "Engel AI here. Tell me what you want done, and I will keep the answer practical."),
        ("who are you", "I am Engel AI Main, the chat brain for this workspace. I coordinate tools, Sub-Engels, local models, Rust background work, and receipts as Engel capabilities."),
        ("this UI is confusing", "I will keep this simple: type the work you want in chat, and I will answer in normal language first. Tool proof and receipts stay behind the answer unless you ask for them."),
        ("prove it ran", "Real proof means a receipt, result file, timestamp, or command output that actually exists. I will not claim a run completed without that evidence."),
        ("did you train yourself", "I only claim training when a training receipt and trained adapter files exist. If the run only tested prompts or inference, I will say that plainly."),
        ("use sub-engels", "I can route work to Sub-Engels through the shared room and then check returned files. I will keep the branding as Engel AI, not a separate product."),
        ("use phones", "I can use connected phones as Engel device workers when the links are live. If a device is offline, I will say so instead of pretending it responded."),
        ("what is runpod for", "RunPod is Engel remote GPU capacity for model inference and training jobs. It is not the identity of the assistant."),
        ("what is rust for", "Rust is Engel background runtime for guarded local tools, bridges, and verifiers. Chat should still feel like Engel, not a command log."),
        ("what should I do next", "Give me the task in plain words. I will choose the next concrete step, run what I can, and leave a receipt when proof matters."),
        ("don't fake proof", "Correct. I will separate planned work from completed work and point only to real receipts or artifacts."),
        ("make this feel like Engel", "Engel should answer like one assistant: clear, useful, and honest. Backend details stay out of the main chat unless they help verify the work."),
        ("can you use all models", "I can route to configured free and open models when they are installed or available. I will not claim a model is active unless a verifier sees it."),
        ("what if runpod is idle", "If RunPod is not needed, I should leave workers cold. If a training job is active, I should show progress and stop paid resources when finished."),
        ("write a work order", "I can write a Sub-Engel work order into the shared room, then wait for a returned result and verify the file path."),
        ("summarize status", "Engel chat is the front door. Behind it are local tools, RunPod training and inference, shared-room workers, phone links, Rust verifiers, and receipts."),
        ("what counts as training", "Training means model weights or adapter files changed and were saved. Prompt tuning, test chats, and profile edits are not weight training."),
        ("what artifact should training make", "A real LoRA training run should produce adapter_config.json, adapter_model.safetensors, tokenizer files, a manifest, hashes, and a training receipt."),
        ("be direct", "Understood. I will answer directly, avoid filler, and show proof only when it is useful or requested."),
        ("what if something fails", "I will say exactly what failed, what receipt exists, and what the next practical fix is."),
    ]
    rows = [row(user, assistant) for user, assistant in base]
    capabilities = [
        "Sub-Engels", "phones", "Google Drive shared room", "Rust background", "RunPod GPUs", "local open models",
        "Hermes-derived workflow features", "desktop UI", "agent meeting room", "receipts", "Windows shortcuts", "device workers",
    ]
    tasks = [
        "test the chat", "train the standalone LLM", "route a work order", "verify a file", "explain a failure",
        "summarize current status", "keep the UI simple", "check if a device answered", "stop paid resources",
        "register a model artifact", "answer without backend noise", "use receipts honestly",
    ]
    constraints = [
        "do not fake proof", "do not call Engel Hermes", "do not call Engel Composio", "keep the main brand as Engel AI",
        "answer like chat first", "show receipts only when useful", "protect secrets", "avoid writing to C drive",
    ]
    for i in range(720):
        capability = capabilities[i % len(capabilities)]
        task = tasks[(i // len(capabilities)) % len(tasks)]
        constraint = constraints[(i // (len(capabilities) * len(tasks))) % len(constraints)]
        user = f"training sample {i}: {task} using {capability}; {constraint}."
        assistant = (
            f"Engel AI handles {task} as one assistant. I use {capability} as an Engel capability, "
            f"keep the answer direct, and follow this rule: {constraint}. If proof matters, I point to real receipts or artifacts only."
        )
        rows.append(row(user, assistant))
    return rows


TRAIN_SCRIPT = r'''from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


class EngelProgressCallback(TrainerCallback):
    def __init__(self, target_seconds: int, progress_path: str, started: float) -> None:
        self.target_seconds = max(0, int(target_seconds or 0))
        self.progress_path = Path(progress_path) if progress_path else None
        self.started = started
        self.last_write = 0.0

    def write_progress(self, state, stopping: bool = False) -> None:
        if self.progress_path is None:
            return
        now = time.perf_counter()
        if not stopping and now - self.last_write < 20:
            return
        self.last_write = now
        elapsed = int(now - self.started)
        payload = {
            "ok": False,
            "schema": "engel_lora_training_progress_v1",
            "updated_at_utc": iso_now(),
            "global_step": int(getattr(state, "global_step", 0) or 0),
            "max_steps": int(getattr(state, "max_steps", 0) or 0),
            "epoch": float(getattr(state, "epoch", 0.0) or 0.0),
            "elapsed_seconds": elapsed,
            "target_seconds": self.target_seconds,
            "stopping_for_budget": stopping,
        }
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        self.progress_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def on_step_end(self, args, state, control, **kwargs):
        elapsed = int(time.perf_counter() - self.started)
        stopping = self.target_seconds > 0 and elapsed >= self.target_seconds
        self.write_progress(state, stopping=stopping)
        if stopping:
            control.should_training_stop = True
        return control


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default=os.environ.get("BASE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3"))
    parser.add_argument("--dataset", default="dataset/engel_standalone_sft.jsonl")
    parser.add_argument(
        "--output-dir",
        default=os.environ.get(
            "ENGEL_TRAINING_OUTPUT_DIR",
            os.environ.get("OUTPUT_DIR", "/workspace/engel_standalone_lora_adapter"),
        ),
    )
    parser.add_argument("--max-steps", type=int, default=int(os.environ.get("MAX_STEPS", "30")))
    parser.add_argument("--max-length", type=int, default=int(os.environ.get("MAX_LENGTH", "768")))
    parser.add_argument("--lr", type=float, default=float(os.environ.get("LEARNING_RATE", "2e-4")))
    parser.add_argument("--target-seconds", type=int, default=int(os.environ.get("TARGET_SECONDS", "0")))
    parser.add_argument("--logging-steps", type=int, default=int(os.environ.get("LOGGING_STEPS", "10")))
    parser.add_argument("--progress-path", default=os.environ.get("PROGRESS_PATH", ""))
    args = parser.parse_args()

    started = time.perf_counter()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = output_dir / "ENGEL_LORA_TRAINING_RECEIPT.json"
    receipt = {
        "ok": False,
        "schema": "engel_standalone_lora_training_receipt_v2",
        "started_at_utc": iso_now(),
        "finished_at_utc": "",
        "base_model": args.base_model,
        "dataset": str(Path(args.dataset).resolve()),
        "output_dir": str(output_dir),
        "max_steps": args.max_steps,
        "max_length": args.max_length,
        "learning_rate": args.lr,
        "target_seconds": args.target_seconds,
        "logging_steps": args.logging_steps,
        "progress_path": args.progress_path,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
        "adapter_files": {},
        "errors": [],
    }
    try:
        raw_rows = load_jsonl(Path(args.dataset))
        receipt["dataset_rows"] = len(raw_rows)
        tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        def render(row: dict) -> dict:
            messages = row["messages"]
            if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
                text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            else:
                text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages) + "\n"
            tokenized = tokenizer(text, truncation=True, max_length=args.max_length, padding="max_length")
            labels = list(tokenized["input_ids"])
            labels = [tok if mask else -100 for tok, mask in zip(labels, tokenized["attention_mask"])]
            tokenized["labels"] = labels
            return tokenized

        dataset = Dataset.from_list(raw_rows).map(render, remove_columns=["messages"])
        quantization = None
        try:
            quantization = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
        except Exception as exc:
            receipt["errors"].append(f"bitsandbytes config unavailable: {exc}")

        model = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            device_map="auto",
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            quantization_config=quantization,
            trust_remote_code=True,
        )
        model.config.use_cache = False
        if quantization is not None:
            model = prepare_model_for_kbit_training(model)
        lora = LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )
        model = get_peft_model(model, lora)
        model.print_trainable_parameters()
        train_args = TrainingArguments(
            output_dir=str(output_dir / "trainer"),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            learning_rate=args.lr,
            max_steps=args.max_steps,
            logging_steps=max(1, args.logging_steps),
            save_steps=max(1, args.max_steps),
            bf16=torch.cuda.is_available(),
            fp16=False,
            report_to=[],
            remove_unused_columns=False,
        )
        callbacks = [EngelProgressCallback(args.target_seconds, args.progress_path, started)]
        trainer = Trainer(model=model, args=train_args, train_dataset=dataset, callbacks=callbacks)
        train_result = trainer.train()
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)
        receipt["train_result"] = train_result.metrics
        for file in sorted(output_dir.iterdir()):
            if file.is_file():
                receipt["adapter_files"][file.name] = {"bytes": file.stat().st_size, "sha256": sha256_file(file)}
        required = ["adapter_config.json", "adapter_model.safetensors"]
        receipt["ok"] = all((output_dir / name).exists() for name in required)
    except Exception as exc:
        receipt["errors"].append(str(exc))
    finally:
        receipt["finished_at_utc"] = iso_now()
        receipt["elapsed_seconds"] = int(time.perf_counter() - started)
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build() -> dict[str, Any]:
    if is_os_drive(WORKSPACE_ROOT) or is_os_drive(EXTERNAL_ROOT):
        raise RuntimeError("refusing C: output root")
    if is_offline_ct245_vault_path(WORKSPACE_ROOT) or is_offline_ct245_vault_path(EXTERNAL_ROOT):
        raise RuntimeError("CT245 offline-vault path is disabled; use /mnt/engel-hdd-vault or local runtime archive")
    if WORKSPACE_ROOT.exists():
        shutil.rmtree(WORKSPACE_ROOT)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    dataset_dir = WORKSPACE_ROOT / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    ct_rows, ct_summary = load_ct_publish_examples()
    if len(ct_rows) >= 60:
        rows = ct_rows + identity_guard_examples() * 4 + examples()[:120]
        dataset_source = "ct_publish_plus_identity_guard"
    else:
        rows = examples() + identity_guard_examples() * 8
        dataset_source = "synthetic_fallback_plus_identity_guard"
    dataset_path = dataset_dir / DATASET_NAME
    write_text(dataset_path, "".join(json.dumps(item, ensure_ascii=True) + "\n" for item in rows))
    write_text(WORKSPACE_ROOT / "train_engel_lora.py", TRAIN_SCRIPT)
    write_text(
        WORKSPACE_ROOT / "requirements.txt",
        "\n".join(
            [
                "--extra-index-url https://download.pytorch.org/whl/cu118",
                "torch==2.1.0+cu118",
                "torchaudio==2.1.0+cu118",
                "torchvision==0.16.0+cu118",
                "accelerate==0.34.2",
                "bitsandbytes==0.43.3",
                "datasets==2.20.0",
                "huggingface_hub==0.24.7",
                "peft==0.12.0",
                "protobuf==4.25.3",
                "safetensors==0.4.5",
                "sentencepiece==0.2.0",
                "transformers==4.44.2",
            ]
        )
        + "\n",
    )
    write_text(
        WORKSPACE_ROOT / "run_training.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\npython3 -m pip install -r requirements.txt\npython3 train_engel_lora.py \"$@\"\n",
    )
    manifest = {
        "ok": True,
        "schema": "engel_lora_training_package_v2",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_model_default": "mistralai/Mistral-7B-Instruct-v0.3",
        "dataset_rows": len(rows),
        "dataset_source": dataset_source,
        "ct_publish_dataset": ct_summary,
        "identity_capture_filter": "ENGEL_TRAINING_CAPTURE_DECISION_V1",
        "training_kind": "real LoRA adapter fine-tune package; success requires adapter_model.safetensors receipt",
        "workspace_root": str(WORKSPACE_ROOT),
        "external_root": str(EXTERNAL_ROOT),
    }
    write_text(WORKSPACE_ROOT / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    zip_path = WORKSPACE_ROOT / ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(WORKSPACE_ROOT.rglob("*")):
            if file == zip_path or file.is_dir():
                continue
            zf.write(file, file.relative_to(WORKSPACE_ROOT).as_posix())
    manifest["zip_path"] = str(zip_path)
    manifest["zip_sha256"] = sha256_file(zip_path)
    manifest["dataset_sha256"] = sha256_file(dataset_path)
    write_text(WORKSPACE_ROOT / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    EXTERNAL_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, EXTERNAL_ROOT / ZIP_NAME)
    shutil.copy2(WORKSPACE_ROOT / "manifest.json", EXTERNAL_ROOT / "manifest.json")
    return manifest


def main() -> int:
    manifest = build()
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
