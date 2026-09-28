from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from run_engel_lora_training_on_runpod import redact_pod, runpod_request, write_receipt


SSH_PUBLIC_KEY_PATH = Path("D:/pod/id_ed25519.pub")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a temporary RunPod pod for Engel LoRA training.")
    parser.add_argument("--name", default=f"engel-lora-budget-h100-{utc_stamp()}")
    parser.add_argument("--gpu-type-id", default="NVIDIA H100 80GB HBM3")
    parser.add_argument("--container-disk-gb", type=int, default=80)
    parser.add_argument("--volume-gb", type=int, default=40)
    args = parser.parse_args()

    public_key = SSH_PUBLIC_KEY_PATH.read_text(encoding="utf-8").strip()
    payload = {
        "name": args.name,
        "cloudType": "SECURE",
        "computeType": "GPU",
        "gpuTypeIds": [args.gpu_type_id],
        "gpuCount": 1,
        "imageName": "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04",
        "containerDiskInGb": args.container_disk_gb,
        "volumeInGb": args.volume_gb,
        "volumeMountPath": "/workspace",
        "ports": ["8888/http", "22/tcp"],
        "env": {
            "SSH_PUBLIC_KEY": public_key,
            "PUBLIC_KEY": public_key,
            "JUPYTER_PASSWORD": "engel-training",
        },
    }
    try:
        response = runpod_request("POST", "/pods", payload)
        pod_id = str(response.get("id") or "")
        receipt = {
            "ok": bool(pod_id),
            "schema": "engel_runpod_lora_training_pod_create_v1",
            "created_at_utc": iso_now(),
            "pod_id": pod_id,
            "name": args.name,
            "gpu_type_id": args.gpu_type_id,
            "container_disk_gb": args.container_disk_gb,
            "volume_gb": args.volume_gb,
            "response": redact_pod(response),
        }
        path = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_POD_CREATE", receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        print(f"receipt={path}")
        return 0 if pod_id else 1
    except Exception as exc:
        receipt = {
            "ok": False,
            "schema": "engel_runpod_lora_training_pod_create_v1",
            "created_at_utc": iso_now(),
            "name": args.name,
            "gpu_type_id": args.gpu_type_id,
            "error": str(exc),
        }
        path = write_receipt("RUNPOD_ENGEL_LORA_TRAINING_POD_CREATE", receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        print(f"receipt={path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
