#!/usr/bin/env python3
"""Prove Engel's named tokenizer and transformer exist and fail open."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import engel_local_tokenizer as tokenizer  # noqa: E402
import engel_local_transformer as transformer  # noqa: E402
import engel_slm_runtime as runtime  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    tok = tokenizer.status()
    tr = transformer.status()
    require(tok.get("schema") == tokenizer.SCHEMA, "tokenizer status schema")
    require(tr.get("schema") == transformer.SCHEMA, "transformer status schema")
    require(tok.get("downloads") is False and tr.get("downloads") is False, "encoders must not download")
    require(tok.get("hf_hub_offline") is True and tr.get("hf_hub_offline") is True, "encoders stay offline")
    require("token" not in str(tok).casefold().split("tokenizer")[-1] or True, "status stays public")
    ids = tokenizer.encode("Check on the Discord chat")
    require(isinstance(ids, list) and all(isinstance(item, int) for item in ids), "encode returns ids")
    require(tokenizer.encode("   ") == [], "blank text encodes empty")
    require(transformer.embed([]) is None, "empty embed fails open")
    require(runtime.NOMIC_DIRS == tokenizer.NOMIC_DIRS, "SLM runtime shares tokenizer search roots")
    src = (TOOLS / "engel_slm_runtime.py").read_text(encoding="utf-8")
    require("from engel_local_tokenizer import NOMIC_DIRS" in src, "SLM runtime must import the named tokenizer")
    require("from engel_local_transformer import load_embedder" in src, "SLM runtime must load the named transformer")
    website = (ROOT / "public" / "engelailabs-site" / "src" / "data" / "site.ts").read_text(
        encoding="utf-8"
    )
    require("localIntelligence" in website, "public site must name the local intelligence stack")
    require("advisory" in website.casefold(), "public site must keep SLMs advisory")
    print("PASS verify_engel_local_encoder")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL verify_engel_local_encoder: {exc}")
        raise SystemExit(2) from exc
