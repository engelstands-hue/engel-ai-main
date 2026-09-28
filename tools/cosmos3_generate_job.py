#!/usr/bin/env python3
"""RunPod job: one Cosmos3 generation (text->image, text->video, image->video).

Runs ON THE POD. Env-parameterized:
  COSMOS3_MODEL_ID   (default nvidia/Cosmos3-Nano)
  COSMOS3_PROMPT     (required)
  COSMOS3_NUM_FRAMES (1 = image, >1 = video; default 1)
  COSMOS3_WIDTH/HEIGHT (default 512)
  COSMOS3_STEPS      (default 20)
  COSMOS3_SOUND      (1 to also generate audio; default 0)

Downloads the model from HF (cached on the volume across runs), loads the
transformer NF4 (fits a 24G card for Nano, 80G for Super), generates, and
writes /workspace/gen_out.png or gen_out.mp4 (+ gen_report.json).
Prints JOB DONE / JOB FAILED as the last line.
"""
import json
import os
import time
import traceback
from pathlib import Path

WS = Path("/workspace")
MODEL_ID = os.environ.get("COSMOS3_MODEL_ID", "nvidia/Cosmos3-Nano")
SHORT = MODEL_ID.split("/")[-1]
SRC = WS / SHORT
PROMPT = os.environ.get("COSMOS3_PROMPT", "").strip()
NUM_FRAMES = int(os.environ.get("COSMOS3_NUM_FRAMES", "1") or "1")
WIDTH = int(os.environ.get("COSMOS3_WIDTH", "512") or "512")
HEIGHT = int(os.environ.get("COSMOS3_HEIGHT", "512") or "512")
STEPS = int(os.environ.get("COSMOS3_STEPS", "20") or "20")
SOUND = os.environ.get("COSMOS3_SOUND", "0").strip() == "1"
report = {"ok": False, "model_id": MODEL_ID, "prompt": PROMPT, "steps": {}}

try:
    if not PROMPT:
        raise ValueError("COSMOS3_PROMPT is required")

    t = time.perf_counter()
    from huggingface_hub import snapshot_download

    snapshot_download(MODEL_ID, local_dir=str(SRC))
    report["steps"]["download_s"] = round(time.perf_counter() - t, 1)

    t = time.perf_counter()
    import torch
    from diffusers import BitsAndBytesConfig
    from diffusers.models import Cosmos3OmniTransformer
    from diffusers.pipelines.cosmos import Cosmos3OmniPipeline

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16)
    transformer = Cosmos3OmniTransformer.from_pretrained(
        str(SRC), subfolder="transformer", quantization_config=bnb, torch_dtype=torch.bfloat16
    )
    # safety checker needs the GATED nvidia/Cosmos-1.0-Guardrail; private-lab lane
    # runs without it (both pipeline call sites isinstance-guard None).
    pipe = Cosmos3OmniPipeline.from_pretrained(
        str(SRC), transformer=transformer, torch_dtype=torch.bfloat16,
        enable_safety_checker=False,
    )
    pipe.enable_model_cpu_offload()
    report["steps"]["load_s"] = round(time.perf_counter() - t, 1)

    t = time.perf_counter()
    result = pipe(
        prompt=PROMPT,
        num_frames=NUM_FRAMES,
        height=HEIGHT,
        width=WIDTH,
        num_inference_steps=STEPS,
        guidance_scale=6.0,
        enable_sound=SOUND,
    )
    report["steps"]["generate_s"] = round(time.perf_counter() - t, 1)

    video = result.video
    frames = video if isinstance(video, (list, tuple)) else [video]
    if NUM_FRAMES <= 1:
        frames[0].save(str(WS / "gen_out.png"))
        report["output"] = "gen_out.png"
    else:
        from diffusers.utils import export_to_video

        export_to_video(frames, str(WS / "gen_out.mp4"), fps=24)
        report["output"] = "gen_out.mp4"
    if SOUND and getattr(result, "sound", None) is not None:
        try:
            import torchaudio  # noqa: F401 — only if present

            torchaudio.save(str(WS / "gen_out.wav"), result.sound.cpu(), 48000)
            report["sound_output"] = "gen_out.wav"
        except Exception as exc:
            report["sound_error"] = str(exc)
    report["ok"] = True
except Exception as exc:
    report["error"] = str(exc)
    report["traceback"] = traceback.format_exc()[-2500:]

(WS / "gen_report.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2), flush=True)
print("JOB DONE" if report["ok"] else "JOB FAILED", flush=True)
