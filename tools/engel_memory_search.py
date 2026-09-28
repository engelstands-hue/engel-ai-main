#!/usr/bin/env python3
"""Engel semantic memory - nomic-embed powered recall on engel-ai-main.

Lets Engel retrieve relevant past facts/conversation by MEANING, not just
recency, so chat stops forgetting things Joshua told it earlier. Runs fully
local on CT 246 (nomic-embed-text-v1.5, no external providers).

  build_index()          -> (re)embed all memory sources into the index
  search(query, k)       -> top-k relevant snippets with scores

HTTP service (engel-memory-search):
  GET  /health
  POST /search {query, k}   -> {ok, results:[{text, source, score}]}
  POST /reindex             -> rebuild the index
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("ENGEL_APP_ROOT", "/opt/engel"))
MODEL_DIR = os.environ.get("ENGEL_EMBED_MODEL", "/opt/engel/models-active/hf-src/nomic-embed-text-v1.5")
INDEX_PATH = Path(os.environ.get("ENGEL_MEMORY_INDEX", "/opt/engel/runtime/memory_index/engel_memory_index.json"))
HOST = os.environ.get("ENGEL_MEMORY_SEARCH_HOST", "127.0.0.1")
PORT = int(os.environ.get("ENGEL_MEMORY_SEARCH_PORT", "8940"))
THREADS = int(os.environ.get("ENGEL_MEMORY_SEARCH_THREADS", "8"))
REJECTED_CHAT_SAMPLES_PATH = ROOT / "memory" / "persistent_chat" / "ENGEL_CHAT_REJECTED_SAMPLES.jsonl"

# nomic-embed uses task prefixes; these are required for good retrieval.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

_MODEL = None
_MODEL_LOCK = threading.Lock()
_INDEX: dict = {"vectors": [], "items": []}
_INDEX_LOCK = threading.Lock()

RETIRED_STORAGE_MEMORY_DOCS = {
    "ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_V1.md",
    "ENGEL_COMPUTER_CONTROL_PIPELINE_CONTRACT_V1.md",
    "ENGEL_MAIN_SERVER_MERGE_V1.md",
    "ENGEL_MAIN_TRUSTED_VAULT_STORAGE_V1.md",
    "ENGEL_SELF_UPDATING_SYSTEM_EXPANDED_BUILD_PLAN_V1.md",
    "ENGEL_STALE_STATIC_ROUTE_CLEANUP_20260629.md",
    "ENGEL_STORAGE_AND_READMODEL_RECORD_20260703.md",
    "ENGEL_VAULT_OFFLINE_INTENTIONAL_SSD_ONLY_20260630.md",
    "SUB_ENGEL_DESKTOP_SERVER_UPDATE_V1.md",
}
RETIRED_STORAGE_MARKERS = (
    "power" + "vault",
    "/mnt/" + "engel-vault",
    "engel-" + "vault-main",
    "ct" + "245",
)
RETIRED_STORAGE_PATTERNS = (
    re.compile(r"\bpower\s*vault\b", re.IGNORECASE),
    re.compile(r"\bct\s*245\b", re.IGNORECASE),
    re.compile(r"engel[-_]vault[-_](?:main|thin|vg)", re.IGNORECASE),
)


def _contains_retired_storage_reference(text: str) -> bool:
    lowered = str(text or "").casefold()
    return any(marker in lowered for marker in RETIRED_STORAGE_MARKERS) or any(
        pattern.search(lowered) for pattern in RETIRED_STORAGE_PATTERNS
    )


def _chat_sample_key(prompt: str, reply: str) -> str:
    normalized = "\n".join(
        (
            " ".join(str(prompt or "").split()).casefold(),
            " ".join(str(reply or "").split()).casefold(),
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _rejected_chat_sample_keys() -> set[str]:
    active: set[str] = set()
    if not REJECTED_CHAT_SAMPLES_PATH.is_file():
        return active
    for line in REJECTED_CHAT_SAMPLES_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        sample_key = str(item.get("sample_key") or "").strip()
        if not sample_key:
            continue
        if item.get("active") is False:
            active.discard(sample_key)
        else:
            active.add(sample_key)
    return active


def _get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            import torch
            from sentence_transformers import SentenceTransformer

            torch.set_num_threads(THREADS)
            _MODEL = SentenceTransformer(MODEL_DIR, trust_remote_code=True, device="cpu")
    return _MODEL


def _memory_snippets() -> list[dict]:
    """Gather durable, high-value memory text (skip canned/template noise)."""
    items: list[dict] = []
    canned = ("Use the Discord bridge media tool", "Agent Meeting Room has a live server room",
              "Good morning, Joshua. I am ready", "server chat brain is connected")

    # Durable person/project facts first - highest priority, always indexed.
    facts_path = ROOT / "memory" / "engel_person_project_facts.jsonl"
    if facts_path.is_file():
        for line in facts_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj = json.loads(line)
            except Exception:
                continue
            fact = str(obj.get("fact") or "").strip()
            if len(fact) >= 3 and not _contains_retired_storage_reference(fact):
                items.append({"text": "Durable fact Joshua asked Engel to remember: " + fact, "source": "saved_facts"})

    tape = ROOT / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
    rejected_sample_keys = _rejected_chat_sample_keys()
    if tape.is_file():
        for line in tape.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj = json.loads(line)
            except Exception:
                continue
            raw_prompt = str(obj.get("prompt") or "")
            raw_reply = str(obj.get("assistant_reply") or "")
            if _contains_retired_storage_reference(raw_prompt + "\n" + raw_reply):
                continue
            prompt = " ".join(raw_prompt.split())[:400]
            reply = " ".join(raw_reply.split())[:600]
            status = str(obj.get("status") or "").casefold()
            if obj.get("ok") is not True or obj.get("quality_gate_degraded") is True:
                continue
            if "quality warning" in status or "quality check failed" in status or "style check failed" in status:
                continue
            if _chat_sample_key(raw_prompt, raw_reply) in rejected_sample_keys:
                continue
            if len(prompt) < 6 or len(reply) < 30 or any(c in reply for c in canned):
                continue
            items.append({"text": f"Joshua: {prompt}\nEngel: {reply}", "source": "chat_memory"})

    # Person/project facts and markdown records under memory/ (short docs).
    mem_dir = ROOT / "memory"
    if mem_dir.is_dir():
        for md in mem_dir.glob("*.md"):
            if md.name in RETIRED_STORAGE_MEMORY_DOCS:
                continue
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if _contains_retired_storage_reference(text):
                continue
            for para in text.split("\n\n"):
                para = " ".join(para.split())
                if 40 <= len(para) <= 800:
                    items.append({"text": para, "source": f"memory/{md.name}"})
    # De-dup by text.
    seen = set()
    unique = []
    for it in items:
        key = it["text"][:160]
        if key not in seen:
            seen.add(key)
            unique.append(it)
    # Keep explicit owner facts and preferences even when chat history grows
    # past the bounded index size. These sources are part of every Engel
    # surface's durable contract and must not be displaced by routine turns.
    pinned_sources = {
        "saved_facts",
        "memory/ENGEL_OWNER_PREFERENCES_V1.md",
        "memory/ENGEL_PRIMARY_GOAL_V1.md",
    }
    pinned = [it for it in unique if it["source"] in pinned_sources]
    ordinary = [it for it in unique if it["source"] not in pinned_sources]
    if len(pinned) >= 4000:
        return pinned[-4000:]
    return pinned + ordinary[-(4000 - len(pinned)) :]


def build_index() -> dict:
    model = _get_model()
    items = _memory_snippets()
    if not items:
        return {"ok": False, "status": "no memory snippets found"}
    texts = [DOC_PREFIX + it["text"] for it in items]
    started = time.perf_counter()
    vectors = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    with _INDEX_LOCK:
        _INDEX["vectors"] = [v.tolist() for v in vectors]
        _INDEX["items"] = items
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps({"built_at_utc": datetime.now(timezone.utc).isoformat(), "count": len(items),
                    "items": items, "vectors": _INDEX["vectors"]}),
        encoding="utf-8",
    )
    return {"ok": True, "count": len(items), "seconds": round(time.perf_counter() - started, 1)}


def _load_index() -> None:
    if _INDEX["items"]:
        return
    if INDEX_PATH.is_file():
        try:
            data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            with _INDEX_LOCK:
                _INDEX["items"] = data.get("items") or []
                _INDEX["vectors"] = data.get("vectors") or []
        except Exception:
            pass


def search(query: str, k: int = 5) -> list[dict]:
    _load_index()
    if not _INDEX["items"]:
        build_index()
    if not _INDEX["items"]:
        return []
    import numpy as np

    model = _get_model()
    q = model.encode([QUERY_PREFIX + query], normalize_embeddings=True)[0]
    mat = np.array(_INDEX["vectors"], dtype="float32")
    scores = mat @ np.array(q, dtype="float32")
    top = scores.argsort()[::-1][:k]
    out = []
    for idx in top:
        score = float(scores[idx])
        if score < 0.35:  # relevance floor - don't inject noise
            continue
        it = _INDEX["items"][idx]
        out.append({"text": it["text"], "source": it["source"], "score": round(score, 3)})
    return out


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
        if urllib.parse.urlparse(self.path).path == "/health":
            _load_index()
            self._send({"ok": True, "service": "engel-memory-search", "indexed": len(_INDEX["items"])})
            return
        self._send({"ok": False, "status": "unknown route"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8", errors="replace") or "{}")
        except Exception:
            self._send({"ok": False, "status": "bad JSON"}, 400)
            return
        if path == "/reindex":
            self._send(build_index())
            return
        if path == "/search":
            query = str(payload.get("query") or "").strip()
            if not query:
                self._send({"ok": False, "status": "empty query"}, 400)
                return
            self._send({"ok": True, "results": search(query, int(payload.get("k") or 5))})
            return
        self._send({"ok": False, "status": "unknown route"}, 404)


def main() -> int:
    print(f"engel-memory-search on {HOST}:{PORT} model={MODEL_DIR}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "build":
        print(json.dumps(build_index(), indent=2))
    else:
        raise SystemExit(main())
