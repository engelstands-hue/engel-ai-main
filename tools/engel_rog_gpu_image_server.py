#!/usr/bin/env python3
"""ROG GPU image-lane launcher: sdxl-turbo fp16 on the RTX 2070 at 127.0.0.1:8931.

Scheduled tasks can't set env vars, so this shim pins the GPU-lane config in
process env and then runs the shared engel_local_image_service in-process.
Runs under engel_hidden_launch.py (script mode) so pythonw never crashes on
prints. The CT246 CPU sd-turbo instance (:8930) is untouched — this is the
quality lane; sequential offload keeps VRAM <1G so it coexists with the
resident llama.cpp :8899 big-lane server.
"""
import os
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("ENGEL_LOCAL_IMAGE_MODEL", str(ROOT / "runtime" / "gpu_models" / "sdxl-turbo"))
os.environ.setdefault("ENGEL_LOCAL_IMAGE_OUTPUT", str(ROOT / "runtime" / "local_images_gpu"))
os.environ.setdefault("ENGEL_LOCAL_IMAGE_HOST", "127.0.0.1")
os.environ.setdefault("ENGEL_LOCAL_IMAGE_PORT", "8931")
os.environ.setdefault("ENGEL_LOCAL_IMAGE_DEVICE", "cuda")
os.environ.setdefault("ENGEL_LOCAL_IMAGE_OFFLOAD", "sequential")
os.environ.setdefault("ENGEL_LOCAL_IMAGE_STEPS", "4")

runpy.run_path(str(ROOT / "tools" / "engel_local_image_service.py"), run_name="__main__")
