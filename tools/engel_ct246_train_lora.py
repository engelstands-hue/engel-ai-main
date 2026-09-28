#!/usr/bin/env python3
"""Canonical time-budgeted CPU LoRA SFT trainer for Engel on CT246.

Trains only on assistant tokens (prompt tokens are label-masked), stops at the
wall-clock deadline, and saves both the adapter and a merged fp16 model.  This
file is the reviewed source installed by run_engel_ct246_local_lora_proof.py;
the installed training script must hash-match this file before preflight or
training can proceed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

# Training is local by construction, not merely because the current host happens
# to have a warm cache. Assign (rather than setdefault) before importing any Hugging
# Face package so inherited values cannot silently re-enable network resolution.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
# Cap the CPU pool before torch starts its own threads. Sixteen threads on this
# host left Chat and the trainer fighting, and each optimizer step took minutes.
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["MKL_NUM_THREADS"] = "8"
os.environ["OPENBLAS_NUM_THREADS"] = "8"


def budgeted_training_schedule(
    deadline_epoch: float,
    now: float,
    step_seconds: float = 50.0,
    reserve_seconds: float = 1500.0,
) -> tuple[int, int]:
    """Fit max_steps and warmup to the wall clock, not to a full 3-epoch plan.

    Three epochs of this corpus is about a thousand optimizer steps. On CPU that
    is more than a day, while the weekly budget is a few hours. Warmup computed
    as a fraction of the thousand-step plan then consumes the entire budget, and
    the cosine schedule never starts. The reserve leaves time to measure and merge
    after the last step.
    """
    window = float(deadline_epoch) - float(now) - float(reserve_seconds)
    if window < 600.0:
        window = 600.0
    steps = max(20, int(window / max(1.0, float(step_seconds))))
    warmup = max(1, min(8, steps // 10))
    return steps, warmup


import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)


def require_local_model_directory(
    raw_path: str,
    label: str,
    required_files: tuple[str, ...],
) -> Path:
    """Resolve an existing local model directory or fail before HF is called."""
    if not str(raw_path or "").strip():
        raise ValueError(f"{label} path is empty")
    candidate = Path(raw_path).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{label} is not an existing local path: {candidate}") from exc
    if not resolved.is_dir():
        raise ValueError(f"{label} is not a local directory: {resolved}")
    missing = [name for name in required_files if not (resolved / name).is_file()]
    if missing:
        raise ValueError(f"{label} is missing required local files: {missing}")
    return resolved


def load_rows(path: str) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def normalize_negative_prompt(value: object) -> str:
    """Canonical prompt key used to keep negative evidence in one split."""
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def canonical_negative_reply(value: object) -> str:
    """Whitespace-canonical reply key for stable exact-pair de-duplication."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def split_negative_prompt_groups(
    rows: list[dict],
    training_enabled: bool,
) -> tuple[list[dict], list[dict], dict]:
    """Deterministically split negative rows without prompt-group leakage.

    Rows sharing a normalized user prompt always stay together, even when their
    replies differ. Exact canonical prompt/reply repeats collapse stable-first so
    duplicated capture evidence cannot overweight either side. Groups are ordered
    by size then prompt digest and greedily assigned to the smaller side, with the
    largest group seeded into held-out evaluation. If fewer than two groups exist,
    or negative-aware training is disabled, every usable row remains held out.
    """
    unique: list[tuple[str, str, dict]] = []
    seen_pairs: set[tuple[str, str]] = set()
    invalid_rows = 0
    duplicate_pairs = 0
    for row in rows:
        prompt = normalize_negative_prompt(row.get("user"))
        reply = canonical_negative_reply(row.get("assistant"))
        if not prompt or not reply:
            invalid_rows += 1
            continue
        pair = (prompt, reply)
        if pair in seen_pairs:
            duplicate_pairs += 1
            continue
        seen_pairs.add(pair)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        unique.append((prompt, prompt_hash, row))

    grouped: dict[str, list[tuple[str, dict]]] = {}
    for prompt, prompt_hash, row in unique:
        grouped.setdefault(prompt, []).append((prompt_hash, row))

    assignment: dict[str, str] = {}
    held_out_all_reason = ""
    ordered_groups = sorted(
        grouped.items(),
        key=lambda item: (
            -len(item[1]),
            item[1][0][0],
        ),
    )
    if not training_enabled:
        held_out_all_reason = "negative-aware training disabled"
        assignment = {prompt: "eval" for prompt in grouped}
    elif len(ordered_groups) < 2:
        held_out_all_reason = "fewer than two normalized prompt groups"
        assignment = {prompt: "eval" for prompt in grouped}
    else:
        train_rows_assigned = 0
        eval_rows_assigned = 0
        for index, (prompt, members) in enumerate(ordered_groups):
            size = len(members)
            if index == 0:
                side = "eval"
            elif index == 1:
                side = "train"
            else:
                # Largest-first list scheduling minimizes row imbalance greedily.
                # Ties stay held out, keeping the contrast side at least as strong.
                side = "train" if train_rows_assigned < eval_rows_assigned else "eval"
            assignment[prompt] = side
            if side == "train":
                train_rows_assigned += size
            else:
                eval_rows_assigned += size

    train_rows: list[dict] = []
    eval_rows: list[dict] = []
    for prompt, prompt_hash, row in unique:
        decorated = dict(row)
        decorated["_negative_prompt_group_sha256"] = prompt_hash
        if assignment.get(prompt) == "train":
            decorated["_negative"] = True
            train_rows.append(decorated)
        else:
            eval_rows.append(decorated)

    train_hashes = sorted(
        {row["_negative_prompt_group_sha256"] for row in train_rows}
    )
    eval_hashes = sorted(
        {row["_negative_prompt_group_sha256"] for row in eval_rows}
    )
    if set(train_hashes).intersection(eval_hashes):
        raise RuntimeError("negative prompt group crossed train/eval boundary")
    stats = {
        "schema": "engel_negative_prompt_group_split_v1",
        "strategy": "normalized_prompt_largest_first_stable_hash_v1",
        "source_rows": len(rows),
        "usable_unique_pairs": len(unique),
        "invalid_rows_dropped": invalid_rows,
        "duplicate_pairs_dropped": duplicate_pairs,
        "prompt_groups": len(grouped),
        "training_enabled": bool(training_enabled),
        "held_out_all": not train_rows,
        "held_out_all_reason": held_out_all_reason,
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "train_groups": len(train_hashes),
        "eval_groups": len(eval_hashes),
        "train_group_hashes": train_hashes,
        "eval_group_hashes": eval_hashes,
    }
    return train_rows, eval_rows, stats


class SftDataset(torch.utils.data.Dataset):
    def __init__(self, rows: list[dict], tokenizer, max_len: int):
        # Zero-signal guard: if the prompt alone fills the sequence window the
        # whole example is label-masked and contributes NOTHING (wasted steps
        # that still count toward the schedule). Drop those up front.
        self.tok = tokenizer
        self.max_len = max_len
        kept = []
        dropped = 0
        for row in rows:
            msgs = [
                {"role": "system", "content": row["system"]},
                {"role": "user", "content": row["user"]},
            ]
            prompt_text = tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True
            )
            if (
                len(tokenizer(prompt_text, add_special_tokens=False)["input_ids"])
                >= max_len - 16
            ):
                dropped += 1
                continue
            kept.append(row)
        if dropped:
            print(
                f"dataset: dropped {dropped} zero-signal examples "
                "(prompt >= seq window)",
                flush=True,
            )
        self.rows = kept
        self.dropped = dropped

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        row = self.rows[idx]
        msgs = [
            {"role": "system", "content": row["system"]},
            {"role": "user", "content": row["user"]},
        ]
        prompt_text = self.tok.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True
        )
        full_text = prompt_text + row["assistant"] + self.tok.eos_token
        prompt_ids = self.tok(prompt_text, add_special_tokens=False)["input_ids"]
        full_ids = self.tok(full_text, add_special_tokens=False)["input_ids"][: self.max_len]
        labels = list(full_ids)
        for i in range(min(len(prompt_ids), len(labels))):
            labels[i] = -100
        return {
            "input_ids": torch.tensor(full_ids, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
            "attention_mask": torch.ones(len(full_ids), dtype=torch.long),
            # Gate-rejected examples use bounded unlikelihood below.
            "negative": torch.tensor(
                1 if row.get("_negative") else 0, dtype=torch.long
            ),
        }


def collate(batch, pad_id: int):
    max_len = max(item["input_ids"].size(0) for item in batch)

    def pad(tensor, value):
        out = torch.full((max_len,), value, dtype=torch.long)
        out[: tensor.size(0)] = tensor
        return out

    return {
        "input_ids": torch.stack([pad(item["input_ids"], pad_id) for item in batch]),
        "labels": torch.stack([pad(item["labels"], -100) for item in batch]),
        "attention_mask": torch.stack(
            [pad(item["attention_mask"], 0) for item in batch]
        ),
        "negative": torch.stack([item["negative"] for item in batch]),
    }


def negative_aware_loss(logits, labels, negative, negative_weight: float):
    """Standard CE for admitted rows; bounded unlikelihood for rejected rows.

    For negative rows this minimizes ``-log(1 - p(token))`` on assistant tokens,
    pushing probability away from rejected continuations.  The probability clamp
    keeps the loss finite, and ``negative_weight`` bounds the negative contribution.
    Gradient ascent on CE is intentionally not used because it is unbounded.
    """
    shift_logits = logits[:, :-1, :]
    shift_labels = labels[:, 1:]
    mask = shift_labels != -100
    safe_labels = shift_labels.clamp(min=0)
    logprobs = torch.log_softmax(shift_logits.float(), dim=-1)
    token_logprobs = logprobs.gather(
        -1, safe_labels.unsqueeze(-1)
    ).squeeze(-1)
    token_counts = mask.sum(dim=1).clamp(min=1)
    ce_per_example = -(token_logprobs * mask).sum(dim=1) / token_counts
    probs = token_logprobs.exp().clamp(max=1.0 - 1e-4)
    unlikelihood_tokens = -torch.log1p(-probs)
    ul_per_example = (unlikelihood_tokens * mask).sum(dim=1) / token_counts
    negative = negative.to(dtype=torch.bool)
    loss_vec = torch.where(
        negative,
        float(negative_weight) * ul_per_example,
        ce_per_example,
    )
    return loss_vec.mean()


class NegativeAwareTrainer(Trainer):
    def __init__(self, *args, negative_weight: float = 0.25, **kwargs):
        super().__init__(*args, **kwargs)
        self._negative_weight = float(negative_weight)

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        negative = inputs.pop("negative")
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = negative_aware_loss(
            outputs.logits, labels, negative, self._negative_weight
        )
        return (loss, outputs) if return_outputs else loss


def self_test() -> int:
    """Prove the negative-aware loss math without loading a model."""
    torch.manual_seed(7)
    vocab, seq = 11, 6
    logits = torch.randn(2, seq, vocab)
    labels = torch.randint(0, vocab, (2, seq))
    labels[:, :2] = -100
    zeros = torch.tensor([0, 0])

    # (a) All-positive loss equals plain per-example-mean CE.
    mine = negative_aware_loss(logits, labels, zeros, 0.25)
    shift_logits, shift_labels = logits[:, :-1], labels[:, 1:]
    mask = shift_labels != -100
    logprobs = torch.log_softmax(shift_logits.float(), -1)
    selected = logprobs.gather(
        -1, shift_labels.clamp(min=0).unsqueeze(-1)
    ).squeeze(-1)
    manual = (-(selected * mask).sum(1) / mask.sum(1)).mean()
    ok_a = torch.allclose(mine, manual, atol=1e-5)
    print(
        f"self-test a (positive==CE): {ok_a} "
        f"({float(mine):.5f} vs {float(manual):.5f})"
    )

    # (b) Making negative tokens more likely must increase negative loss.
    negatives = torch.tensor([1, 1])
    high = logits.clone()
    for batch_index in range(2):
        for token_index in range(seq - 1):
            target = labels[batch_index, token_index + 1]
            if target != -100:
                high[batch_index, token_index, target] += 6.0
    loss_high = negative_aware_loss(high, labels, negatives, 0.25)
    loss_low = negative_aware_loss(logits, labels, negatives, 0.25)
    ok_b = loss_high > loss_low
    print(
        f"self-test b (likely-negatives cost more): {ok_b} "
        f"({float(loss_high):.5f} > {float(loss_low):.5f})"
    )

    # (c) p ~= 1 stays finite because of the clamp.
    extreme = logits.clone()
    for batch_index in range(2):
        for token_index in range(seq - 1):
            target = labels[batch_index, token_index + 1]
            if target != -100:
                extreme[batch_index, token_index, target] += 100.0
    loss_extreme = negative_aware_loss(extreme, labels, negatives, 0.25)
    ok_c = torch.isfinite(loss_extreme)
    print(
        f"self-test c (clamp keeps finite): {bool(ok_c)} "
        f"({float(loss_extreme):.4f})"
    )
    passed = bool(ok_a and ok_b and ok_c)
    print("SELF-TEST:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


class DeadlineCallback(TrainerCallback):
    def __init__(self, deadline_epoch: float):
        self.deadline = deadline_epoch

    def on_step_end(self, args, state, control, **kwargs):
        if time.time() >= self.deadline:
            print(
                f"DEADLINE reached at step {state.global_step}; stopping.",
                flush=True,
            )
            control.should_training_stop = True
        return control


class StepLogCallback(TrainerCallback):
    """Write a plain step line. The tqdm log uses carriage returns and looks frozen."""

    def on_log(self, args, state, control, logs=None, **kwargs):
        if isinstance(logs, dict) and "loss" in logs:
            print(
                f"step {int(state.global_step)} loss {float(logs['loss']):.4f}",
                flush=True,
            )
        return control


def main() -> int:
    import sys

    if "--self-test" in sys.argv:
        return self_test()

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--train", required=True)
    parser.add_argument("--val", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--deadline-epoch", type=float, required=True)
    parser.add_argument("--seq", type=int, default=1536)
    parser.add_argument("--epochs", type=float, default=3.0)
    # Budget-capped runs accumulate through the proven adapter lineage.
    parser.add_argument("--resume-adapter", default="")
    # Rejected examples are split into negative-train and held-out contrast sets.
    parser.add_argument("--negative", default="")
    parser.add_argument("--negative-train-weight", type=float, default=0.25)
    args = parser.parse_args()

    model_path = require_local_model_directory(
        args.model, "base model", ("config.json",)
    )
    resume_path: Path | None = None
    if args.resume_adapter:
        resume_path = require_local_model_directory(
            args.resume_adapter,
            "resume adapter",
            ("adapter_config.json", "adapter_model.safetensors"),
        )

    torch.set_num_threads(8)
    max_steps, warmup_steps = budgeted_training_schedule(
        args.deadline_epoch, time.time()
    )
    print(
        f"schedule: max_steps={max_steps} warmup_steps={warmup_steps}",
        flush=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_path), local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(model_path), dtype=torch.float32, local_files_only=True
    )
    model.config.use_cache = False

    resumed_from = None
    if resume_path is not None:
        model = PeftModel.from_pretrained(
            model,
            str(resume_path),
            is_trainable=True,
            local_files_only=True,
        )
        resumed_from = str(resume_path)
        print(f"resume: continuing adapter {resumed_from}", flush=True)
    else:
        lora = LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=[
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ],
        )
        model = get_peft_model(model, lora)
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    model.gradient_checkpointing_enable()
    model.print_trainable_parameters()

    train_rows = load_rows(args.train)
    val_rows = load_rows(args.val)
    val_ds = SftDataset(val_rows, tokenizer, args.seq)

    # The negative file is both training signal and measuring stick, so split it
    # deterministically. Never evaluate contrast on rows used for unlikelihood.
    negative_train_rows: list[dict] = []
    negative_ds = None
    _, _, negative_split = split_negative_prompt_groups([], training_enabled=False)
    if args.negative and Path(args.negative).is_file():
        negative_rows = [
            {
                "system": row.get("system") or "",
                "user": row["user"],
                "assistant": row["assistant"],
            }
            for row in load_rows(args.negative)
            if row.get("user") and row.get("assistant")
        ]
        # Prompt groups, not individual rows, are the unit of separation. A model
        # must never train on one rejection for a prompt and be evaluated on another
        # rejection for that same normalized prompt.
        negative_train_rows, negative_eval_rows, negative_split = (
            split_negative_prompt_groups(
                negative_rows,
                training_enabled=args.negative_train_weight > 0,
            )
        )
        negative_ds = SftDataset(negative_eval_rows, tokenizer, args.seq)
        print(
            f"negative split: {len(negative_train_rows)} train / "
            f"{len(negative_eval_rows)} held-out eval across "
            f"{negative_split['prompt_groups']} prompt groups",
            flush=True,
        )
    train_ds = SftDataset(train_rows + negative_train_rows, tokenizer, args.seq)
    pad_id = (
        tokenizer.pad_token_id
        if tokenizer.pad_token_id is not None
        else tokenizer.eos_token_id
    )

    training_args = TrainingArguments(
        output_dir=args.out + "/checkpoints",
        num_train_epochs=args.epochs,
        max_steps=max_steps,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        learning_rate=1.5e-4,
        lr_scheduler_type="cosine",
        warmup_steps=warmup_steps,
        logging_steps=5,
        save_steps=25,
        save_total_limit=2,
        report_to=[],
        use_cpu=True,
        dataloader_num_workers=0,
        seed=7,
        # Required: otherwise Trainer strips the custom negative flag before
        # NegativeAwareTrainer.compute_loss sees it.
        remove_unused_columns=False,
    )

    def measure_loss(dataset, label: str, cap: int = 64) -> float | None:
        # Empty means unmeasured, never a perfect-looking 0.0.
        if dataset is None or len(dataset) == 0:
            print(f"{label} SET EMPTY -- unmeasured", flush=True)
            return None
        model.eval()
        losses = []
        with torch.no_grad():
            for index in range(min(cap, len(dataset))):
                item = dataset[index]
                output = model(
                    input_ids=item["input_ids"].unsqueeze(0),
                    labels=item["labels"].unsqueeze(0),
                    attention_mask=item["attention_mask"].unsqueeze(0),
                )
                losses.append(float(output.loss))
        model.train()
        return sum(losses) / len(losses)

    def trainable_weight_norm() -> float:
        total = 0.0
        for parameter in model.parameters():
            if parameter.requires_grad:
                total += float(parameter.detach().float().norm()) ** 2
        return round(total**0.5, 6)

    if len(train_ds) == 0:
        print(
            "TRAIN SET EMPTY after zero-signal guard -- nothing to train; "
            f"raise --seq (dropped {train_ds.dropped} of {len(train_rows)})",
            flush=True,
        )
        return 3

    val_loss_before = measure_loss(val_ds, "VAL")
    if val_loss_before is not None:
        print(f"val_loss_before_training: {val_loss_before:.4f}", flush=True)
    negative_loss_before = measure_loss(negative_ds, "NEGATIVE")
    weight_norm_before = trainable_weight_norm()

    trainer = NegativeAwareTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        data_collator=lambda batch: collate(batch, pad_id),
        callbacks=[
            DeadlineCallback(args.deadline_epoch),
            StepLogCallback(),
        ],
        negative_weight=args.negative_train_weight,
    )
    started = time.time()
    result = trainer.train()
    train_seconds = int(time.time() - started)

    adapter_dir = args.out + "/adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    val_loss = measure_loss(val_ds, "VAL")
    negative_loss = measure_loss(negative_ds, "NEGATIVE")
    weight_norm_after = trainable_weight_norm()

    merged_dir = args.out + "/merged"
    merged = model.merge_and_unload().to(torch.float16)
    merged.save_pretrained(merged_dir)
    tokenizer.save_pretrained(merged_dir)

    def delta(after, before):
        return (
            round(after - before, 4)
            if after is not None and before is not None
            else None
        )

    val_delta = delta(val_loss, val_loss_before)
    negative_delta = delta(negative_loss, negative_loss_before)
    negative_train_kept_hashes = sorted(
        {
            str(row.get("_negative_prompt_group_sha256") or "")
            for row in train_ds.rows
            if row.get("_negative") and row.get("_negative_prompt_group_sha256")
        }
    )
    negative_eval_kept_hashes = sorted(
        {
            str(row.get("_negative_prompt_group_sha256") or "")
            for row in (negative_ds.rows if negative_ds is not None else [])
            if row.get("_negative_prompt_group_sha256")
        }
    )
    if set(negative_train_kept_hashes).intersection(negative_eval_kept_hashes):
        raise RuntimeError("kept negative prompt group crossed train/eval boundary")
    samples_seen = (
        int(result.global_step)
        * training_args.per_device_train_batch_size
        * training_args.gradient_accumulation_steps
    )
    summary = {
        "steps": int(result.global_step),
        "train_loss": float(result.training_loss),
        "val_loss_before": val_loss_before,
        "val_loss": val_loss,
        "val_loss_delta": val_delta,
        "negative_loss_before": negative_loss_before,
        "negative_loss": negative_loss,
        "negative_loss_delta": negative_delta,
        "val_minus_negative_delta": (
            delta(val_delta, negative_delta)
            if None not in (val_delta, negative_delta)
            else None
        ),
        "adapter_weight_norm_before": weight_norm_before,
        "adapter_weight_norm_after": weight_norm_after,
        "resumed_from": resumed_from,
        "samples_seen": samples_seen,
        "epochs_effective": round(samples_seen / max(1, len(train_ds)), 3),
        "train_seconds": train_seconds,
        "train_examples": len(train_rows),
        "train_kept": sum(
            1 for row in train_ds.rows if not row.get("_negative")
        ),
        "negative_train_kept": sum(
            1 for row in train_ds.rows if row.get("_negative")
        ),
        "negative_train_weight": args.negative_train_weight,
        "negative_split": negative_split,
        "negative_train_kept_groups": len(negative_train_kept_hashes),
        "negative_eval_kept_groups": len(negative_eval_kept_hashes),
        "negative_train_kept_group_hashes": negative_train_kept_hashes,
        "negative_eval_kept_group_hashes": negative_eval_kept_hashes,
        "train_dropped_zero_signal": train_ds.dropped,
        "val_examples": len(val_rows),
        "val_kept": len(val_ds),
        "val_dropped_zero_signal": val_ds.dropped,
        "negative_eval_kept": len(negative_ds) if negative_ds is not None else 0,
        "negative_kept": len(negative_ds) if negative_ds is not None else 0,
        "seq_window": args.seq,
        "adapter": adapter_dir,
        "merged": merged_dir,
    }
    Path(args.out, "train_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("TRAIN-SUMMARY " + json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
