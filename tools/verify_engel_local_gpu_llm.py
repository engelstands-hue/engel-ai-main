from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CUDA_RUNTIME_DIR = Path("F:/ENGEL_APP_MEMORY/runtimes/llama.cpp/candidates/llama-b9198-bin-win-cuda-12.4-x64")
CUDART_DIR = Path("F:/ENGEL_APP_MEMORY/runtimes/llama.cpp/candidates/cudart-llama-bin-win-cuda-12.4-x64")
LLAMA_CLI = CUDA_RUNTIME_DIR / "llama-cli.exe"
MODEL_PATH = Path("G:/ENGEL_APP_MEMORY/models/manual_downloads/mistral-7b-instruct-v0.3/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf")
WORKSPACE_RECEIPT_DIR = ROOT / "reports" / "engel_local_gpu_llm" / "receipts"
EXTERNAL_RECEIPT_DIR = Path("F:/ENGEL_APP_MEMORY/local_standalone_chat_llm/gpu_receipts")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_os_drive(path: Path) -> bool:
    return Path(path).drive.lower() == "c:"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if is_os_drive(path):
        raise RuntimeError(f"refusing to write GPU proof receipt on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_text(command: list[str], env: dict[str, str], timeout: int = 30) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


def nvidia_query() -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=timestamp,name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "command": command}
    text = completed.stdout.strip()
    sample: dict[str, Any] = {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "raw": text,
        "stderr": completed.stderr.strip()[:1000],
        "command": command,
    }
    if text:
        parts = [part.strip() for part in text.splitlines()[0].split(",")]
        if len(parts) >= 7:
            sample.update(
                {
                    "timestamp": parts[0],
                    "name": parts[1],
                    "memory_used_mib": int(float(parts[2])),
                    "memory_total_mib": int(float(parts[3])),
                    "utilization_gpu_percent": int(float(parts[4])),
                    "temperature_c": int(float(parts[5])),
                    "power_draw_w": float(parts[6]) if parts[6] not in {"[Not Supported]", "N/A"} else None,
                }
            )
    return sample


def run_gpu_probe(env: dict[str, str], timeout: int) -> dict[str, Any]:
    prompt = "<|im_start|>user\nSay exactly: GPU probe ok.\n<|im_end|>\n<|im_start|>assistant\n"
    command = [
        str(LLAMA_CLI),
        "-m",
        str(MODEL_PATH),
        "-p",
        prompt,
        "-n",
        "24",
        "-c",
        "1024",
        "-t",
        "4",
        "-ngl",
        "99",
        "--device",
        "CUDA0",
        "--split-mode",
        "none",
        "--simple-io",
        "--no-display-prompt",
        "--single-turn",
        "--offline",
    ]
    samples: list[dict[str, Any]] = []
    stop = threading.Event()

    def sampler() -> None:
        while not stop.is_set():
            samples.append(nvidia_query())
            stop.wait(1.0)

    thread = threading.Thread(target=sampler, daemon=True)
    before = nvidia_query()
    thread.start()
    started = time.perf_counter()
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=30)
            timed_out = True
    finally:
        stop.set()
        thread.join(timeout=5)
    after = nvidia_query()
    return {
        "command": command,
        "returncode": proc.returncode,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "nvidia_before": before,
        "nvidia_samples": samples,
        "nvidia_after": after,
    }


def main() -> int:
    stamp = utc_stamp()
    workspace_receipt = WORKSPACE_RECEIPT_DIR / f"ENGEL_LOCAL_GPU_LLM_PROOF_{stamp}.json"
    external_receipt = EXTERNAL_RECEIPT_DIR / f"ENGEL_LOCAL_GPU_LLM_PROOF_{stamp}.json"
    env = os.environ.copy()
    env["PATH"] = f"{CUDA_RUNTIME_DIR};{CUDART_DIR};{env.get('PATH', '')}"
    env["TEMP"] = str(ROOT / "runtime" / "temp")
    env["TMP"] = str(ROOT / "runtime" / "temp")

    device_list = run_text([str(LLAMA_CLI), "--list-devices"], env=env, timeout=30)
    version = run_text([str(LLAMA_CLI), "--version"], env=env, timeout=30)
    probe = run_gpu_probe(env=env, timeout=300)
    stderr_lower = probe["stderr"].lower()
    stdout_text = probe["stdout"].strip()
    samples = [sample for sample in probe["nvidia_samples"] if sample.get("ok")]
    before_memory = int((probe["nvidia_before"] or {}).get("memory_used_mib") or 0)
    peak_memory = max([int(sample.get("memory_used_mib") or 0) for sample in samples] + [before_memory])
    memory_delta = peak_memory - before_memory
    cuda_log_hits = [
        term
        for term in ["cuda0", "ggml_cuda", "offloaded", "offload", "gpu layers", "cuda"]
        if term in stderr_lower
    ]

    receipt = {
        "ok": False,
        "schema": "engel_local_gpu_llm_proof_v1",
        "updated_at_utc": iso_now(),
        "provider": "local-rust-cuda-mistral-gguf",
        "runtime": str(LLAMA_CLI),
        "runtime_present": LLAMA_CLI.exists(),
        "cuda_runtime_dir": str(CUDA_RUNTIME_DIR),
        "cudart_dir": str(CUDART_DIR),
        "cudart_dir_present": CUDART_DIR.exists(),
        "model_path": str(MODEL_PATH),
        "model_present": MODEL_PATH.exists(),
        "gpu_backend": "cuda",
        "gpu_device": "CUDA0",
        "gpu_layers_requested": 99,
        "device_list": device_list,
        "version": version,
        "probe_command": probe["command"],
        "probe_returncode": probe["returncode"],
        "probe_timed_out": probe["timed_out"],
        "probe_elapsed_ms": probe["elapsed_ms"],
        "probe_stdout_preview": stdout_text[:1200],
        "probe_stderr_preview": probe["stderr"][:3000],
        "cuda_log_hits": cuda_log_hits,
        "nvidia_before": probe["nvidia_before"],
        "nvidia_samples": samples[:120],
        "nvidia_after": probe["nvidia_after"],
        "nvidia_memory_peak_mib": peak_memory,
        "nvidia_memory_delta_mib": memory_delta,
        "workspace_receipt_path": str(workspace_receipt),
        "external_receipt_path": str(external_receipt),
        "api_key_value_visible": False,
        "network_enabled": False,
        "provider_api_enabled": False,
        "c_drive_used": False,
    }
    receipt["ok"] = (
        LLAMA_CLI.exists()
        and MODEL_PATH.exists()
        and "CUDA0" in (device_list.get("stdout") or "")
        and probe["returncode"] == 0
        and not probe["timed_out"]
        and bool(stdout_text)
        and (bool(cuda_log_hits) or memory_delta >= 500)
    )
    write_json(workspace_receipt, receipt)
    write_json(external_receipt, receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
