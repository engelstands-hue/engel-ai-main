#!/usr/bin/env python3
"""Orchestrate the Cosmos3-Nano NF4 quantization on RunPod.

Reuses the proven LoRA-training pod helpers (key resolution, ssh wait, scp,
receipts, stop). Subcommands so each phase is short + resumable:

  create                 -> create a 24GB-class pod (default RTX 4090), print pod_id
  prepare --pod-id ID    -> wait ssh, install deps, upload the job, start it (nohup)
  poll    --pod-id ID    -> tail the job log; exits 0 on JOB DONE, 2 on JOB FAILED, 3 still running
  fetch   --pod-id ID    -> download proof + report (small) to runtime/runpod/cosmos3/
  fetch-tar --pod-id ID  -> download the NF4 tar (~10G, long) to runtime/runpod/cosmos3/
  stop    --pod-id ID    -> stop the pod (idempotent)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_engel_lora_training_on_runpod import (  # noqa: E402
    redact_pod,
    runpod_request,
    scp_base,
    ssh_base,
    stop_pod,
    wait_for_ssh_target,
    write_receipt,
)

APP_ROOT = Path(__file__).resolve().parents[1]
SSH_PUBLIC_KEY_PATH = Path("D:/pod/id_ed25519.pub")
LOCAL_OUT = APP_ROOT / "runtime" / "runpod" / "cosmos3"
JOB_LOCAL = Path(__file__).resolve().parent / "cosmos3_quantize_job.py"

# torch 2.6 REQUIRED: the image's torch 2.4 cannot infer the schema of the
# cosmos3 custom attention op (string annotations) — import fails without it.
# torchvision MUST move in lockstep (0.21 pairs with 2.6): the image's 2.4-built
# torchvision against torch 2.6 breaks transformers' AutoImageProcessor import.
PIP_DEPS = (
    "torch==2.6.0 torchvision==0.21.0 diffusers==0.39.0 transformers==5.13.0 bitsandbytes accelerate "
    "huggingface_hub hf_transfer safetensors sentencepiece imageio imageio-ffmpeg cosmos_guardrail"
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def cmd_create(args: argparse.Namespace) -> int:
    public_key = SSH_PUBLIC_KEY_PATH.read_text(encoding="utf-8").strip()
    payload = {
        "name": args.name or f"engel-cosmos3-nf4-{utc_stamp()}",
        "cloudType": "SECURE",
        "computeType": "GPU",
        "gpuTypeIds": [args.gpu_type_id],
        "gpuCount": 1,
        "imageName": "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
        "containerDiskInGb": args.container_disk_gb,
        "volumeInGb": args.volume_gb,
        "volumeMountPath": "/workspace",
        "ports": ["22/tcp"],
        "env": {"SSH_PUBLIC_KEY": public_key, "PUBLIC_KEY": public_key},
    }
    response = runpod_request("POST", "/pods", payload)
    pod_id = str(response.get("id") or "")
    receipt = {
        "ok": bool(pod_id),
        "schema": "engel_runpod_cosmos3_quantize_pod_create_v1",
        "pod_id": pod_id,
        "gpu_type_id": args.gpu_type_id,
        "response": redact_pod(response),
    }
    write_receipt("RUNPOD_ENGEL_COSMOS3_POD_CREATE", receipt)
    print(json.dumps({"ok": bool(pod_id), "pod_id": pod_id}, indent=2))
    return 0 if pod_id else 1


def _ssh(pod_id: str, attempts: int = 40, delay: int = 15):
    ip, port, _pod, _receipt = wait_for_ssh_target(pod_id, attempts, delay)
    return ip, port


def cmd_prepare(args: argparse.Namespace) -> int:
    ip, port = _ssh(args.pod_id)
    scp = scp_base(port)
    subprocess.run([*scp, str(JOB_LOCAL), f"root@{ip}:/workspace/cosmos3_quantize_job.py"], check=True, timeout=120)
    model_id = getattr(args, "model", "") or "nvidia/Cosmos3-Nano"
    remote = (
        "cd /workspace && "
        # purge image-baked libs compiled against the OLD torch — a stale
        # torchaudio/xformers/flash-attn breaks the diffusers import chain with
        # undefined symbols once torch is upgraded; the job needs none of them.
        # (20260711) trailing `|| echo JOB FAILED` so a pip/dep failure emits the
        # terminal marker the poller watches for, instead of an unmarked log that
        # makes cmd_poll spin (exit 3) forever against paid pod time.
        f"nohup bash -c 'pip uninstall -y -q torchaudio xformers flash-attn flash_attn 2>/dev/null; "
        f"pip install -q {PIP_DEPS} && "
        f"COSMOS3_MODEL_ID={model_id} HF_HUB_ENABLE_HF_TRANSFER=1 python /workspace/cosmos3_quantize_job.py "
        "|| echo JOB FAILED' "
        "> /workspace/job.log 2>&1 & echo STARTED"
    )
    out = subprocess.run([*ssh_base(ip, port), remote], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print(out.stdout.strip() or out.stderr.strip())
    return 0 if "STARTED" in (out.stdout or "") else 1


def cmd_poll(args: argparse.Namespace) -> int:
    ip, port = _ssh(args.pod_id, attempts=3, delay=5)
    out = subprocess.run(
        [*ssh_base(ip, port), "tail -25 /workspace/job.log 2>/dev/null || echo NO-LOG"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    text = out.stdout or ""
    print(text.strip()[-2400:])
    if "JOB DONE" in text:
        return 0
    if "JOB FAILED" in text:
        return 2
    return 3


def cmd_fetch(args: argparse.Namespace) -> int:
    # (20260711 fix) old version ignored every scp return code and then listed the
    # WHOLE local dir as "files" — so a fully-failed fetch reported success naming
    # STALE artifacts from a previous run. Now: track per-file success and fail (1)
    # if the mandatory quantize_report.json didn't transfer this invocation.
    ip, port = _ssh(args.pod_id, attempts=3, delay=5)
    LOCAL_OUT.mkdir(parents=True, exist_ok=True)
    scp = scp_base(port)
    fetched, missing = [], []
    for name in ("quantize_report.json", "proof.png", "proof.mp4"):
        proc = subprocess.run([*scp, f"root@{ip}:/workspace/{name}", str(LOCAL_OUT / name)],
                              capture_output=True, text=True, timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        (fetched if proc.returncode == 0 else missing).append(name)
    ok = "quantize_report.json" in fetched
    print(json.dumps({"ok": ok, "fetched_to": str(LOCAL_OUT),
                      "fetched": fetched, "missing": missing}, indent=2))
    return 0 if ok else 1


def cmd_fetch_tar(args: argparse.Namespace) -> int:
    ip, port = _ssh(args.pod_id, attempts=3, delay=5)
    LOCAL_OUT.mkdir(parents=True, exist_ok=True)
    scp = scp_base(port)
    # (20260711 fix) when --model is given, fetch the EXACT expected tar name;
    # otherwise if the volume holds several *-nf4.tar (Nano then Super on one pod)
    # fail loudly rather than silently grabbing the lexically-first (always Nano).
    want = ""
    if getattr(args, "model", ""):
        want = f"/workspace/{args.model.split('/')[-1].lower()}-nf4.tar"
    if want:
        chk = subprocess.run([*ssh_base(ip, port), f"test -f {want} && echo OK"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        remote_tar = want if "OK" in (chk.stdout or "") else ""
    else:
        ls = subprocess.run([*ssh_base(ip, port), "ls /workspace/*-nf4.tar 2>/dev/null"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        tars = [t for t in (ls.stdout or "").splitlines() if t.strip()]
        if len(tars) > 1:
            print(json.dumps({"ok": False, "error": "multiple *-nf4.tar on the pod; pass --model to pick one",
                              "found": tars}, indent=2))
            return 1
        remote_tar = tars[0].strip() if tars else ""
    if not remote_tar:
        print(json.dumps({"ok": False, "error": "no *-nf4.tar on the pod"}, indent=2))
        return 1
    target = LOCAL_OUT / Path(remote_tar).name
    proc = subprocess.run([*scp, f"root@{ip}:{remote_tar}", str(target)], timeout=4 * 3600)
    print(json.dumps({"ok": proc.returncode == 0, "tar": str(target),
                      "bytes": target.stat().st_size if target.exists() else 0}, indent=2))
    return proc.returncode


def cmd_stop(args: argparse.Namespace) -> int:
    # (20260711 fix) stop_pod swallows API/network errors and returns normally,
    # so a failed /stop used to still print success + exit 0 — leaving an H100
    # billing at ~$3/hr with no signal. VERIFY the pod actually exited and shout
    # (nonzero) if it didn't, so the operator (or a script) knows to intervene.
    from run_engel_lora_training_on_runpod import status_pod

    stop_pod(args.pod_id)
    exited = False
    last = ""
    for _ in range(3):
        try:
            st = status_pod(args.pod_id)
            last = str(st.get("desiredStatus") or "")
            if last.upper() in {"EXITED", "STOPPED", "TERMINATED"}:
                exited = True
                break
        except Exception as exc:
            last = f"status check failed: {exc}"
    if exited:
        print(json.dumps({"stopped": args.pod_id, "desiredStatus": last}, indent=2))
        return 0
    print(json.dumps({
        "ok": False,
        "pod_id": args.pod_id,
        "desiredStatus": last,
        "WARNING": f"POD MAY STILL BE BILLING — verify + stop manually at runpod.io: {args.pod_id}",
    }, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create")
    p.add_argument("--name", default="")
    p.add_argument("--gpu-type-id", default="NVIDIA GeForce RTX 4090")
    p.add_argument("--container-disk-gb", type=int, default=80)
    p.add_argument("--volume-gb", type=int, default=80)
    for name in ("prepare", "poll", "fetch", "fetch-tar", "stop"):
        q = sub.add_parser(name)
        q.add_argument("--pod-id", required=True)
        if name in ("prepare", "fetch-tar"):
            q.add_argument("--model", default=("nvidia/Cosmos3-Nano" if name == "prepare" else ""),
                           help="HF model id (Super variants need an 80GB pod; on fetch-tar, picks the exact tar)")
    args = parser.parse_args()
    return {
        "create": cmd_create,
        "prepare": cmd_prepare,
        "poll": cmd_poll,
        "fetch": cmd_fetch,
        "fetch-tar": cmd_fetch_tar,
        "stop": cmd_stop,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
