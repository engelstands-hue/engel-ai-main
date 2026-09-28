#!/usr/bin/env python3
"""Engel AI Main local tokenizer.

This is the named tokenizer surface for release review. It does not download
weights, call Hugging Face, or invent a new vocabulary. It locates the local
Nomic Embed Text v1.5 tokenizer files when they are present and otherwise
falls open to a deterministic Unicode n-gram encoder so chat never blocks.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("ENGEL_ROOT") or Path(__file__).resolve().parents[1])

NOMIC_DIRS = (
    os.environ.get("ENGEL_NOMIC_EMBED_DIR", ""),
    "/opt/engel/models-active/hf-src/nomic-embed-text-v1.5",
    str(ROOT / "models-active" / "hf-src" / "nomic-embed-text-v1.5"),
)
TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "special_tokens_map.json",
)
SCHEMA = "engel_local_tokenizer_status_v1"


def nomic_dir() -> Path | None:
    for candidate in NOMIC_DIRS:
        path = Path(candidate) if candidate else None
        if path is not None and path.is_dir() and (path / "tokenizer.json").is_file():
            return path
    return None


def present_files(directory: Path | None = None) -> list[str]:
    folder = directory or nomic_dir()
    if folder is None:
        return []
    return [name for name in TOKENIZER_FILES if (folder / name).is_file()]


def status() -> dict[str, Any]:
    folder = nomic_dir()
    files = present_files(folder)
    ready = folder is not None and "tokenizer.json" in files
    return {
        "schema": SCHEMA,
        "name": "Engel local tokenizer",
        "backend": "nomic-embed-text-v1.5" if ready else "unicode_ngram_fallback",
        "ready": ready,
        "nomic_tokenizer_present": ready,
        "files_present": files,
        "hf_hub_offline": True,
        "downloads": False,
        "authority": "advisory_feature_encoder",
    }


def encode(text: str, *, max_tokens: int = 256) -> list[int]:
    """Return token ids. Never raises. Never phones a hub."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    body = str(text or "")
    if not body.strip():
        return []
    folder = nomic_dir()
    if folder is not None:
        try:
            from transformers import AutoTokenizer  # lazy, optional

            tokenizer = AutoTokenizer.from_pretrained(
                str(folder),
                local_files_only=True,
                trust_remote_code=False,
            )
            ids = tokenizer.encode(body, add_special_tokens=False)
            if isinstance(ids, list):
                return [int(item) for item in ids[: max(1, int(max_tokens))]]
        except Exception:
            pass
    return _ngram_ids(body, max_tokens=max_tokens)


def _ngram_ids(text: str, *, max_tokens: int) -> list[int]:
    compact = " ".join(str(text).casefold().split())
    if not compact:
        return []
    grams: list[int] = []
    window = compact if len(compact) < 3 else compact
    for index in range(len(window) - 2):
        piece = window[index : index + 3]
        digest = hashlib.sha256(piece.encode("utf-8")).digest()
        grams.append(int.from_bytes(digest[:4], "little") % 50000)
        if len(grams) >= max(1, int(max_tokens)):
            break
    return grams or [int.from_bytes(hashlib.sha256(compact.encode("utf-8")).digest()[:4], "little") % 50000]
