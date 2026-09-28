#!/usr/bin/env python3
"""Engel Cosmos3 on-demand generation lane (RunPod-backed).

Joshua's world-model lane: text->image / text->video / image->video via the
NF4-quantized Cosmos3 family. Local hardware can't hold these (2070 = 8G VRAM),
so generation runs on an on-demand RunPod pod and the output lands locally.

  one-shot:  python engel_cosmos3_generate.py run --prompt "..." [--video] [--super]
  session:   create-pod / generate --pod-id ID --prompt "..." / stop --pod-id ID
             (a kept-open session pod amortizes the ~10-20 min model download
              across many generations; each generate is then just load+render)

Cost anchor (2026-07): Nano fits a 24G RTX 4090 (~$0.35-0.69/hr); Super variants
need an 80G H100 (~$2.4-3/hr). A one-shot Nano image is a few cents.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_engel_cosmos3_nano_quantize_on_runpod import (  # noqa: E402
    PIP_DEPS,
    cmd_stop,
)
from run_engel_lora_training_on_runpod import (  # noqa: E402
    redact_pod,
    runpod_request,
    scp_base,
    ssh_base,
    wait_for_ssh_target,
    write_receipt,
)

APP_ROOT = Path(__file__).resolve().parents[1]
SSH_PUBLIC_KEY_PATH = Path("D:/pod/id_ed25519.pub")
JOB_LOCAL = Path(__file__).resolve().parent / "cosmos3_generate_job.py"
OUT_ROOT = APP_ROOT / "runtime" / "cosmos3_generations"

NANO = "nvidia/Cosmos3-Nano"
SUPER = "nvidia/Cosmos3-Super"
SUPER_T2I = "nvidia/Cosmos3-Super-Text2Image"
SUPER_I2V = "nvidia/Cosmos3-Super-Image2Video"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_pod(super_class: bool) -> str:
    public_key = SSH_PUBLIC_KEY_PATH.read_text(encoding="utf-8").strip()
    payload = {
        "name": f"engel-cosmos3-gen-{utc_stamp()}",
        "cloudType": "SECURE",
        "computeType": "GPU",
        "gpuTypeIds": ["NVIDIA H100 80GB HBM3" if super_class else "NVIDIA GeForce RTX 4090"],
        "gpuCount": 1,
        "imageName": "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
        "containerDiskInGb": 40,
        "volumeInGb": 250 if super_class else 80,
        "volumeMountPath": "/workspace",
        "ports": ["22/tcp"],
        "env": {"SSH_PUBLIC_KEY": public_key, "PUBLIC_KEY": public_key},
    }
    response = runpod_request("POST", "/pods", payload)
    pod_id = str(response.get("id") or "")
    write_receipt("RUNPOD_ENGEL_COSMOS3_GEN_POD_CREATE",
                  {"ok": bool(pod_id), "pod_id": pod_id, "response": redact_pod(response)})
    if not pod_id:
        raise RuntimeError("pod create failed")
    return pod_id


def generate_on_pod(pod_id: str, model_id: str, prompt: str, num_frames: int,
                    width: int, height: int, steps: int, sound: bool,
                    timeout_s: int = 3600) -> Path:
    ip, port, _pod, _r = wait_for_ssh_target(pod_id, 40, 15)
    scp = scp_base(port)
    subprocess.run([*scp, str(JOB_LOCAL), f"root@{ip}:/workspace/cosmos3_generate_job.py"],
                   check=True, timeout=120)
    prompt_b64 = __import__("base64").b64encode(prompt.encode("utf-8")).decode("ascii")
    remote = (
        "cd /workspace && rm -f gen_report.json gen_out.png gen_out.mp4 && "
        f"nohup bash -c 'pip uninstall -y -q torchaudio xformers flash-attn flash_attn 2>/dev/null; "
        f"pip install -q {PIP_DEPS} && "
        f"COSMOS3_MODEL_ID={model_id} COSMOS3_PROMPT=\"$(echo {prompt_b64} | base64 -d)\" "
        f"COSMOS3_NUM_FRAMES={num_frames} COSMOS3_WIDTH={width} COSMOS3_HEIGHT={height} "
        f"COSMOS3_STEPS={steps} COSMOS3_SOUND={'1' if sound else '0'} "
        # `|| echo JOB FAILED` so a pip/launch failure emits the terminal marker the
        # poll loop watches for — otherwise it spins the full timeout on paid GPU time.
        "python /workspace/cosmos3_generate_job.py || echo JOB FAILED' "
        "> /workspace/job.log 2>&1 & echo STARTED"
    )
    try:
        subprocess.run([*ssh_base(ip, port), remote], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        pass  # nohup fires anyway; poll below is authoritative
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(20)
        out = subprocess.run([*ssh_base(ip, port), "tail -3 /workspace/job.log 2>/dev/null"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        text = out.stdout or ""
        if "JOB DONE" in text:
            break
        if "JOB FAILED" in text:
            log = subprocess.run([*ssh_base(ip, port), "tail -40 /workspace/job.log"],
                                 capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            raise RuntimeError("generation failed:\n" + (log.stdout or "")[-2000:])
    else:
        raise TimeoutError(f"generation exceeded {timeout_s}s")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    fetched: Path | None = None
    for name in ("gen_out.png", "gen_out.mp4", "gen_out.wav", "gen_report.json"):
        local = OUT_ROOT / f"{stamp}_{name}"
        proc = subprocess.run([*scp, f"root@{ip}:/workspace/{name}", str(local)],
                              capture_output=True, text=True, timeout=1800, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.returncode == 0 and name.startswith("gen_out") and fetched is None:
            fetched = local
    if fetched is None:
        raise RuntimeError("no output produced")
    return fetched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="one-shot: create pod, generate, fetch, stop pod")
    gen = sub.add_parser("generate", help="generate on an existing session pod")
    gen.add_argument("--pod-id", required=True)
    for p in (run, gen):
        p.add_argument("--prompt", required=True)
        p.add_argument("--video", action="store_true", help="text->video (5s / 121 frames)")
        p.add_argument("--frames", type=int, default=0, help="explicit frame count")
        p.add_argument("--size", default="512x512")
        p.add_argument("--steps", type=int, default=20)
        p.add_argument("--sound", action="store_true")
        p.add_argument("--super", dest="super_", action="store_true",
                       help="use Cosmos3-Super (H100 class)")
        p.add_argument("--model", default="", help="explicit HF model id override")

    cp = sub.add_parser("create-pod", help="open a session pod (reuse across generates)")
    cp.add_argument("--super", dest="super_", action="store_true")
    st = sub.add_parser("stop", help="stop a session pod")
    st.add_argument("--pod-id", required=True)

    args = parser.parse_args()
    if args.cmd == "create-pod":
        print(json.dumps({"pod_id": create_pod(args.super_)}, indent=2))
        return 0
    if args.cmd == "stop":
        return cmd_stop(args)

    model = args.model or (SUPER if args.super_ else NANO)
    frames = args.frames or (121 if args.video else 1)
    width, height = (int(v) for v in args.size.lower().split("x"))
    pod_id = getattr(args, "pod_id", "")
    one_shot = args.cmd == "run"
    if one_shot:
        pod_id = create_pod(args.super_)
        print(f"pod: {pod_id}", flush=True)
    try:
        out = generate_on_pod(pod_id, model, args.prompt, frames, width, height,
                              args.steps, args.sound)
        print(json.dumps({"ok": True, "output": str(out), "model": model,
                          "pod_id": pod_id}, indent=2))
        return 0
    finally:
        if one_shot:
            try:
                cmd_stop(argparse.Namespace(pod_id=pod_id))
            except Exception:
                print(f"WARNING: stop the pod manually: {pod_id}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
