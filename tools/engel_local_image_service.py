#!/usr/bin/env python3
"""Engel's OWN image engine - Stable Diffusion Turbo on the engel-ai-main CPU.

High-quality image generation with NO external providers: weights live on the
server SSD, nothing leaves the machine at generation time.

  GET  /health                          -> {ok, model_loaded, busy}
  POST /generate {prompt, width, height, steps, negative}
                                        -> {ok, path, seconds, ...}

The pipeline loads once and stays warm (single-flight; CPU threads pinned).
Output PNGs land in /opt/engel/runtime/local_images/.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODEL_DIR = os.environ.get("ENGEL_LOCAL_IMAGE_MODEL", "/opt/engel/models-active/hf-src/sd-turbo")
OUTPUT_DIR = Path(os.environ.get("ENGEL_LOCAL_IMAGE_OUTPUT", "/opt/engel/runtime/local_images"))
HOST = os.environ.get("ENGEL_LOCAL_IMAGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("ENGEL_LOCAL_IMAGE_PORT", "8930"))
THREADS = int(os.environ.get("ENGEL_LOCAL_IMAGE_THREADS", "14"))
# "cpu" (default, CT246) or "cuda" (ROG RTX 2070 quality lane).
DEVICE = os.environ.get("ENGEL_LOCAL_IMAGE_DEVICE", "cpu").strip().lower()
# CUDA offload mode: "sequential" (default; coexists with the resident llama
# :8899 server in <1G VRAM), "model" (faster, needs ~6G free), or "none".
OFFLOAD = os.environ.get("ENGEL_LOCAL_IMAGE_OFFLOAD", "sequential").strip().lower()

_LOCK = threading.Lock()
_STATE: dict = {"model_loaded": False, "load_seconds": None, "generations": 0}
_PIPE = None


def _get_pipe():
    global _PIPE
    if _PIPE is not None:
        return _PIPE
    import torch
    from diffusers import AutoPipelineForText2Image

    torch.set_num_threads(THREADS)
    started = time.perf_counter()
    if DEVICE == "cuda" and torch.cuda.is_available():
        # GPU quality lane (ROG RTX 2070): fp16 weights; offload keeps VRAM low
        # enough to coexist with the resident llama.cpp :8899 server.
        try:
            pipe = AutoPipelineForText2Image.from_pretrained(
                MODEL_DIR, torch_dtype=torch.float16, variant="fp16"
            )
        except Exception:
            pipe = AutoPipelineForText2Image.from_pretrained(MODEL_DIR, torch_dtype=torch.float16)
        if OFFLOAD == "sequential":
            pipe.enable_sequential_cpu_offload()
        elif OFFLOAD == "model":
            pipe.enable_model_cpu_offload()
        else:
            pipe = pipe.to("cuda")
        _STATE["device"] = f"cuda(offload={OFFLOAD})"
    else:
        pipe = AutoPipelineForText2Image.from_pretrained(MODEL_DIR, torch_dtype=torch.float32)
        pipe = pipe.to("cpu")
        _STATE["device"] = "cpu"
    pipe.set_progress_bar_config(disable=True)
    _STATE["model_loaded"] = True
    _STATE["load_seconds"] = round(time.perf_counter() - started, 1)
    _PIPE = pipe
    return pipe


def generate(prompt: str, width: int, height: int, steps: int, negative: str) -> dict:
    if not _LOCK.acquire(blocking=False):
        return {"ok": False, "busy": True, "status": "image engine is busy with another generation"}
    try:
        pipe = _get_pipe()
        started = time.perf_counter()
        # sd-turbo is adversarially distilled: guidance must be 0.0 and very
        # few steps; dimensions snap to multiples of 8.
        width = max(256, min(768, (width // 8) * 8))
        height = max(256, min(768, (height // 8) * 8))
        steps = max(1, min(6, steps))
        result = pipe(
            prompt=prompt,
            negative_prompt=negative or None,
            num_inference_steps=steps,
            guidance_scale=0.0,
            width=width,
            height=height,
        )
        image = result.images[0]
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = OUTPUT_DIR / f"engel_local_{stamp}.png"
        image.save(out)
        _STATE["generations"] += 1
        return {
            "ok": True,
            "path": str(out),
            "bytes": out.stat().st_size,
            "seconds": round(time.perf_counter() - started, 1),
            "width": width,
            "height": height,
            "steps": steps,
            "engine": f"engel-local-{Path(MODEL_DIR).name} (no external providers)",
        }
    except Exception as exc:
        return {"ok": False, "status": f"local image generation failed: {exc}"}
    finally:
        _LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send({"ok": True, "service": "engel-local-image", "busy": _LOCK.locked(), **_STATE})
            return
        if parsed.path == "/file":
            qs = urllib.parse.parse_qs(parsed.query)
            raw = (qs.get("path") or [""])[0]
            path = Path(raw).resolve()
            if not str(path).startswith(str(OUTPUT_DIR.resolve())) or not path.is_file():
                self._send({"ok": False, "status": "file not found"}, 404)
                return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._send({"ok": False, "status": "unknown route"}, 404)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/generate":
            self._send({"ok": False, "status": "unknown route"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8", errors="replace") or "{}")
        except Exception:
            self._send({"ok": False, "status": "bad JSON body"}, 400)
            return
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            self._send({"ok": False, "status": "empty prompt"}, 400)
            return
        result = generate(
            prompt,
            int(payload.get("width") or 512),
            int(payload.get("height") or 512),
            int(payload.get("steps") or os.environ.get("ENGEL_LOCAL_IMAGE_STEPS", "2")),
            str(payload.get("negative") or ""),
        )
        self._send(result)


def main() -> int:
    print(f"engel-local-image on {HOST}:{PORT} model={MODEL_DIR}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
