#!/usr/bin/env python3
"""Train Engel's voice SLM — a LoRA on Qwen2.5-0.5B-Instruct.

This is the one roster entry that genuinely deserves a fine-tune: it is a GENERATION
task (speak as Engel), not classification, so a linear head cannot do it.

Runs on CT246 CPU (24 cores) on purpose. The RTX 2070 is ~86% full holding the chat
model (7004/8192 MiB) and a 0.5B LoRA would not fit beside it without evicting live
chat. A 0.5B adapter on 600 graded examples is small enough that CPU is the right
trade: slower training, zero chat downtime.

Evaluation is the interesting part. Held-out loss says the model learned SOMETHING, but
it cannot say the output sounds like Engel. So generated replies are scored by Engel's
REAL style gate (`reply_passes_style` from the live chat runner) and compared against the
untuned base on the same prompts. If the adapter does not raise the gate pass rate, it
is not worth loading.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("/opt/engel")
BASE_REL = "models-active/hf-src/Qwen2.5-0.5B-Instruct"
VOICE_REL = "memory/personality/engel_voice_examples.jsonl"

SYSTEM = (
    "You are Engel, Joshua's own local AI. Answer as Engel in Engel's voice: direct, "
    "practical, first person, no product-assistant filler."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_pairs(root: Path, min_grade: float) -> list[dict[str, str]]:
    path = root / VOICE_REL
    pairs = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        prompt = str(row.get("user") or "").strip()
        reply = str(row.get("reply") or "").strip()
        try:
            grade = float(row.get("grade") or 0)
        except (TypeError, ValueError):
            grade = 0.0
        # Train only on replies Engel's own grader liked. Fine-tuning on mediocre
        # replies teaches mediocrity, and the corpus carries the grade for free.
        if prompt and reply and grade >= min_grade:
            pairs.append({"prompt": prompt, "reply": reply, "grade": grade})
    return pairs


def chat_ids(tokenizer, messages: list[dict[str, str]]) -> list[int]:
    """Token ids for a chat prompt, normalised across transformers versions.

    apply_chat_template(tokenize=True) returns a plain list on some versions, a
    BatchEncoding on others, and a tensor when return_tensors is set. Depending on
    which you get, `+ list` raises TypeError and `.shape` raises AttributeError --
    both of which bit this trainer. Normalise once, here.
    """
    out = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    if hasattr(out, "input_ids"):
        out = out.input_ids
    if hasattr(out, "tolist"):
        out = out.tolist()
    while isinstance(out, list) and out and isinstance(out[0], list):
        out = out[0]
    return [int(token) for token in out]


def build_batch(tokenizer, pairs: list[dict[str, str]], max_len: int):
    import torch

    input_ids, labels = [], []
    for pair in pairs:
        prompt_ids = chat_ids(
            tokenizer,
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": pair["prompt"]},
            ],
        )
        reply_ids = tokenizer(pair["reply"], add_special_tokens=False)["input_ids"]
        reply_ids = reply_ids + [tokenizer.eos_token_id]
        ids = (prompt_ids + reply_ids)[:max_len]
        # Mask the prompt: the model is graded on producing the REPLY, not on
        # reciting the question back.
        lab = ([-100] * len(prompt_ids) + reply_ids)[:max_len]
        pad = max_len - len(ids)
        input_ids.append(ids + [tokenizer.pad_token_id] * pad)
        labels.append(lab + [-100] * pad)
    return (
        torch.tensor(input_ids, dtype=torch.long),
        torch.tensor(labels, dtype=torch.long),
    )


def style_pass_rate(root: Path, model, tokenizer, prompts: list[str]) -> dict[str, Any]:
    """Score generated replies with Engel's live style gate."""
    sys.path.insert(0, str(root / "tools"))
    try:
        from run_engel_standalone_chat_llm import reply_passes_style
    except Exception as exc:  # noqa: BLE001
        return {"scored": False, "reason": f"style gate unavailable: {type(exc).__name__}"}
    import torch

    passed, samples, scored_n = 0, [], 0
    for prompt in prompts:
        # apply_chat_template with return_tensors can hand back a BatchEncoding rather
        # than a tensor depending on transformers version, and generate() then dies on
        # .shape. Build the id list and wrap it here so the version does not matter.
        try:
            id_list = chat_ids(
                tokenizer,
                [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            )
            ids = torch.tensor([id_list], dtype=torch.long)
            with torch.no_grad():
                out = model.generate(
                    ids,
                    max_new_tokens=90,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                )
            text = tokenizer.decode(
                out[0][ids.shape[-1]:], skip_special_tokens=True
            ).strip()
            score = reply_passes_style(prompt, text)
        except Exception as exc:  # noqa: BLE001
            # An eval hiccup must not throw away a finished training run.
            samples.append({"prompt": prompt, "error": f"{type(exc).__name__}: {exc}"})
            continue
        scored_n += 1
        ok = score.get("ok") is True
        passed += 1 if ok else 0
        samples.append(
            {
                "prompt": prompt,
                "reply": text[:220],
                "style_ok": ok,
                "failed": [k for k, v in (score.get("checks") or {}).items() if v is False][:4],
            }
        )
    if not scored_n:
        return {"scored": False, "reason": "no prompt could be scored", "samples": samples}
    return {
        "scored": True,
        "prompts": len(prompts),
        "prompts_scored": scored_n,
        "style_pass": passed,
        "style_pass_rate": round(passed / scored_n, 3),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the Engel voice SLM (LoRA)")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--min-grade", type=float, default=0.7)
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--max-len", type=int, default=320)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--eval-prompts", type=int, default=8)
    args = parser.parse_args()

    root = Path(args.root)
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.set_num_threads(max(1, min(24, torch.get_num_threads() or 8)))
    base = root / BASE_REL
    pairs = load_pairs(root, args.min_grade)
    if len(pairs) < 50:
        print(json.dumps({"ok": False, "status": f"only {len(pairs)} graded pairs"}))
        return 1
    random.Random(17).shuffle(pairs)
    holdout = pairs[: max(20, len(pairs) // 10)]
    train = pairs[len(holdout):]

    tokenizer = AutoTokenizer.from_pretrained(str(base))
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(str(base), dtype=torch.float32)

    eval_prompts = [p["prompt"] for p in holdout[: args.eval_prompts]]
    before = style_pass_rate(root, model, tokenizer, eval_prompts)

    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        ),
    )
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=args.lr
    )
    model.train()
    started = time.perf_counter()
    losses = []
    step = 0
    while step < args.max_steps:
        for index in range(0, len(train), args.batch):
            if step >= args.max_steps:
                break
            batch = train[index : index + args.batch]
            if not batch:
                continue
            ids, labels = build_batch(tokenizer, batch, args.max_len)
            out = model(input_ids=ids, labels=labels)
            out.loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            losses.append(float(out.loss.detach()))
            step += 1
            if step % 20 == 0:
                print(f"  step {step}/{args.max_steps} loss={losses[-1]:.4f}", flush=True)
    train_seconds = time.perf_counter() - started

    model.eval()
    with torch.no_grad():
        ids, labels = build_batch(tokenizer, holdout[: min(24, len(holdout))], args.max_len)
        holdout_loss = float(model(input_ids=ids, labels=labels).loss)
    after = style_pass_rate(root, model, tokenizer, eval_prompts)

    out_dir = root / "models-active" / "slm" / "voice"
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    improved = (
        after.get("scored") is True
        and before.get("scored") is True
        and after["style_pass_rate"] >= before["style_pass_rate"]
    )
    report = {
        "schema": "engel_slm_voice_training_report_v1",
        "task": "voice",
        "generated_at_utc": _now(),
        "ok": bool(improved),
        "status": (
            "adapter trained and did not regress the style gate"
            if improved
            else "adapter trained but style gate did NOT improve — do not load"
        ),
        "base_model": str(base),
        "device": "cpu",
        "graded_pairs_used": len(pairs),
        "min_grade": args.min_grade,
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "trainable_params": trainable,
        "steps": step,
        "first_loss": round(losses[0], 4) if losses else None,
        "last_loss": round(sum(losses[-10:]) / max(1, len(losses[-10:])), 4) if losses else None,
        "holdout_loss": round(holdout_loss, 4),
        "train_seconds": round(train_seconds, 1),
        "style_gate_before": before,
        "style_gate_after": after,
        "adapter_dir": str(out_dir),
    }
    receipts = root / "reports" / "slm"
    receipts.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (receipts / f"ENGEL_SLM_VOICE_{stamp}.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "TRAINING_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "style_gate_before"}, indent=2, sort_keys=True))
    return 0 if improved else 1


if __name__ == "__main__":
    raise SystemExit(main())
