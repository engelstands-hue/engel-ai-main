#!/usr/bin/env python3
"""RunPod job: quantize nvidia/Cosmos3-Nano to NF4 and prove it generates.

Runs ON THE POD. Steps: download from HF -> load transformer NF4 (bitsandbytes)
-> assemble Cosmos3OmniPipeline -> text-to-image proof render -> save_pretrained
quantized snapshot -> tar for download. Writes /workspace/quantize_report.json
and prints JOB DONE / JOB FAILED as the last line.
"""
import json
import os
import time
import traceback
from pathlib import Path

WS = Path("/workspace")
# Parameterized so the SAME job quantizes any Cosmos3 family member
# (Nano on a 24G card; Super variants need an 80G card).
MODEL_ID = os.environ.get("COSMOS3_MODEL_ID", "nvidia/Cosmos3-Nano")
SHORT = MODEL_ID.split("/")[-1]
SRC = WS / SHORT
OUT = WS / f"{SHORT}-NF4"
REPORT = WS / "quantize_report.json"
report = {"ok": False, "model_id": MODEL_ID, "steps": {}}


def step(name):
    print(f"[{time.strftime('%H:%M:%S')}] === {name} ===", flush=True)
    return time.perf_counter()


try:
    t = step(f"1. download {MODEL_ID} from HF")
    from huggingface_hub import snapshot_download

    snapshot_download(MODEL_ID, local_dir=str(SRC))
    report["steps"]["download_s"] = round(time.perf_counter() - t, 1)

    t = step("2. load transformer in NF4")
    import torch
    from diffusers import BitsAndBytesConfig
    from diffusers.models import Cosmos3OmniTransformer

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    transformer = Cosmos3OmniTransformer.from_pretrained(
        str(SRC), subfolder="transformer", quantization_config=bnb, torch_dtype=torch.bfloat16
    )
    report["steps"]["load_nf4_s"] = round(time.perf_counter() - t, 1)

    t = step("3. assemble pipeline")
    from diffusers.pipelines.cosmos import Cosmos3OmniPipeline

    # enable_safety_checker=False: the official CosmosSafetyChecker pulls the
    # GATED nvidia/Cosmos-1.0-Guardrail repo (needs an HF account + license
    # acceptance + token). Private home-lab lane runs without it; both pipeline
    # call sites isinstance-guard None. Re-enable later by accepting the HF
    # gate and dropping the flag.
    pipe = Cosmos3OmniPipeline.from_pretrained(
        str(SRC), transformer=transformer, torch_dtype=torch.bfloat16,
        enable_safety_checker=False,
    )
    pipe.enable_model_cpu_offload()
    report["steps"]["assemble_s"] = round(time.perf_counter() - t, 1)

    t = step("4. text-to-image proof render")
    result = pipe(
        prompt="a photorealistic red fox standing in golden-hour forest light, ultra detailed",
        num_frames=1,
        height=512,
        width=512,
        num_inference_steps=20,
        guidance_scale=6.0,
    )
    # Cosmos3OmniPipelineOutput.video = list of PIL frames for output_type="pil";
    # with num_frames=1 (t2i) that's a single-frame list.
    video = result.video
    img = video[0] if isinstance(video, (list, tuple)) else video
    img.save(str(WS / "proof.png"))
    report["steps"]["proof_render_s"] = round(time.perf_counter() - t, 1)

    t = step("5. save quantized snapshot")
    pipe.save_pretrained(str(OUT))
    report["steps"]["save_s"] = round(time.perf_counter() - t, 1)

    t = step("6. tar for download")
    import subprocess

    tar_path = WS / f"{SHORT.lower()}-nf4.tar"
    subprocess.run(["tar", "cf", str(tar_path), "-C", str(WS), OUT.name], check=True)
    report["steps"]["tar_s"] = round(time.perf_counter() - t, 1)
    report["tar_path"] = str(tar_path)
    report["tar_bytes"] = tar_path.stat().st_size
    report["out_gb"] = round(sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) / 1e9, 2)
    report["ok"] = True
except Exception as exc:
    report["error"] = str(exc)
    report["traceback"] = traceback.format_exc()[-3000:]

REPORT.write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2), flush=True)
print("JOB DONE" if report["ok"] else "JOB FAILED", flush=True)
