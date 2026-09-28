#!/usr/bin/env python3
"""Local-first test: can the ROG RTX 2070 (8GB) serve Cosmos3-Nano-NF4?

Tries offload configs in order of speed until one fits:
  1. model offload  (module-level; fastest, needs the biggest module + activations in VRAM)
  2. sequential offload (leaf-level; slowest, minimal VRAM — coexists with the llama server)
Measures load + generation wall-clock and peak VRAM, saves a proof image.

Run inside gpu_image_venv. The saved NF4 pipeline loads WITHOUT re-quantizing
(bnb state is serialized) and without the gated guardrail (not saved with it).
"""
import json
import sys
import time
from pathlib import Path

MODEL = Path(r"D:\b.WorkSpace\Engel App\runtime\gpu_models\Cosmos3-Nano-NF4")
OUT = Path(r"D:\b.WorkSpace\Engel App\runtime\cosmos3_generations")
PROMPT = "a photorealistic golden retriever puppy in warm evening light, ultra detailed"

import torch
from diffusers.pipelines.cosmos import Cosmos3OmniPipeline

results = {}
for mode in ("model", "sequential"):
    print(f"=== trying offload mode: {mode} ===", flush=True)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    try:
        t = time.perf_counter()
        pipe = Cosmos3OmniPipeline.from_pretrained(
            str(MODEL), torch_dtype=torch.bfloat16, enable_safety_checker=False
        )
        if mode == "model":
            pipe.enable_model_cpu_offload()
        else:
            pipe.enable_sequential_cpu_offload()
        load_s = round(time.perf_counter() - t, 1)
        print(f"  loaded in {load_s}s", flush=True)

        t = time.perf_counter()
        result = pipe(
            prompt=PROMPT, num_frames=1, height=512, width=512,
            num_inference_steps=20, guidance_scale=6.0,
        )
        gen_s = round(time.perf_counter() - t, 1)
        peak_gb = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        video = result.video
        img = video[0] if isinstance(video, (list, tuple)) else video
        OUT.mkdir(parents=True, exist_ok=True)
        proof = OUT / f"local_2070_{mode}_proof.png"
        img.save(str(proof))
        results[mode] = {"ok": True, "load_s": load_s, "gen_s": gen_s,
                         "peak_vram_gb": peak_gb, "proof": str(proof)}
        print(f"  SUCCESS: gen {gen_s}s, peak VRAM {peak_gb}GB -> {proof}", flush=True)
        del pipe
        torch.cuda.empty_cache()
        break  # first working mode wins
    except Exception as exc:
        results[mode] = {"ok": False, "error": str(exc)[:400]}
        print(f"  FAILED: {str(exc)[:300]}", flush=True)
        try:
            del pipe
        except Exception:
            pass
        torch.cuda.empty_cache()

print(json.dumps(results, indent=2))
ok = any(v.get("ok") for v in results.values())
print("LOCAL-2070: " + ("VIABLE" if ok else "NOT VIABLE"))
sys.exit(0 if ok else 1)
