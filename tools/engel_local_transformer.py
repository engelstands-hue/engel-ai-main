#!/usr/bin/env python3
"""Engel AI Main local embedding transformer.

This is the named transformer surface for release review. The encoder is the
local Nomic Embed Text v1.5 SentenceTransformer when those files exist.
Missing files, missing Python deps, or load errors fail open to None so chat
and SLM serving never block. No Hugging Face Hub calls.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from engel_local_tokenizer import NOMIC_DIRS, nomic_dir

MODEL_FILES = (
    "model.safetensors",
    "config.json",
    "modules.json",
    "config_sentence_transformers.json",
)
SCHEMA = "engel_local_transformer_status_v1"


def present_files(directory: Path | None = None) -> list[str]:
    folder = directory or nomic_dir()
    if folder is None:
        return []
    names = [name for name in MODEL_FILES if (folder / name).is_file()]
    if folder is not None and (folder / "onnx").is_dir():
        names.append("onnx")
    return names


def status() -> dict[str, Any]:
    folder = nomic_dir()
    files = present_files(folder)
    ready = folder is not None and "model.safetensors" in files and "config.json" in files
    return {
        "schema": SCHEMA,
        "name": "Engel local embedding transformer",
        "backend": "nomic-embed-text-v1.5" if ready else "unavailable_fail_open",
        "ready": ready,
        "nomic_encoder_present": ready,
        "files_present": files,
        "hf_hub_offline": True,
        "downloads": False,
        "device": "cpu",
        "authority": "advisory_feature_encoder",
    }


def load_embedder() -> Any:
    """Load the local encoder or raise FileNotFoundError. Callers must fail open."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from sentence_transformers import SentenceTransformer  # lazy

    folder = nomic_dir()
    if folder is None:
        raise FileNotFoundError("nomic-embed model directory not found")
    return SentenceTransformer(
        str(folder),
        trust_remote_code=False,
        local_files_only=True,
        device="cpu",
    )


def embed(texts: list[str]) -> list[list[float]] | None:
    """Return embeddings or None. Never raises into a chat turn."""
    payload = [str(item or "") for item in (texts or [])]
    if not payload:
        return None
    try:
        model = load_embedder()
        vectors = model.encode(payload, batch_size=16, show_progress_bar=False)
    except Exception:
        return None
    try:
        return [[float(value) for value in row] for row in vectors]
    except Exception:
        return None


def nomic_search_dirs() -> tuple[str, ...]:
    return tuple(item for item in NOMIC_DIRS if item)
