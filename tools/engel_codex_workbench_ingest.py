#!/usr/bin/env python3
"""Build bounded, lineage-preserving context packs for Engel chat turns.

The ingest lane consumes only attachment receipts and explicitly supplied context
items. It never opens a client-provided source path. Raw inline payloads stay in
the attachment intake lane; this module stores redacted text chunks, summaries,
and provenance under CT246's self-update runtime root.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from engel_chat_failure_corpus_builder import redact_text, redact_value


ROOT = Path(os.environ.get("ENGEL_APP_ROOT", Path(__file__).resolve().parents[1]))
DEFAULT_CONTEXT_PACK_ROOT = ROOT / "run" / "self_update" / "context_packs"
DEFAULT_CHUNK_CHARS = 4000
DEFAULT_CHUNK_OVERLAP = 240
DEFAULT_MAX_ITEM_CHARS = 48000
DEFAULT_MAX_CHUNKS = 64
ALLOWED_CONTEXT_KINDS = {
    "file",
    "folder",
    "image",
    "pdf",
    "screenshot",
    "pasted_text",
    "terminal_output",
    "receipt",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _clean_scalar(value: Any, limit: int) -> str:
    clean, _ = redact_text(str(value or ""))
    return clean.replace("\x00", "").strip()[:limit]


def _safe_name(value: Any, fallback: str) -> str:
    raw = _clean_scalar(value, 160)
    clean = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw).strip(" .")
    return clean[:120] or fallback


def _context_kind(item: dict[str, Any], *, attachment: bool) -> str:
    explicit = str(item.get("context_kind") or item.get("kind") or "").strip().casefold()
    mime = str(item.get("mime_type") or item.get("mime") or "").strip().casefold()
    name = str(item.get("name") or item.get("path") or "").strip().casefold()
    source = str(item.get("source") or "").strip().casefold()
    if explicit == "folder" or mime == "application/x-directory":
        return "folder"
    if mime == "application/pdf" or name.endswith(".pdf"):
        return "pdf"
    if mime.startswith("image/"):
        return "screenshot" if "screen" in source or "screenshot" in name else "image"
    if explicit in ALLOWED_CONTEXT_KINDS:
        return explicit
    if explicit == "text":
        if "terminal" in source or name.endswith((".log", ".out")):
            return "terminal_output"
        if "receipt" in source or "receipt" in name:
            return "receipt"
        return "file" if attachment else "pasted_text"
    if "terminal" in source:
        return "terminal_output"
    if "receipt" in source or "receipt" in name:
        return "receipt"
    return "file" if attachment else "pasted_text"


def _chunk_text(text: str, chunk_chars: int, overlap: int, max_chunks: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text) and len(chunks) < max_chunks:
        end = min(len(text), start + chunk_chars)
        if end < len(text):
            boundary = max(text.rfind("\n", start + chunk_chars // 2, end), text.rfind(" ", start + chunk_chars // 2, end))
            if boundary > start:
                end = boundary
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [chunk for chunk in chunks if chunk]


def _extractive_summary(text: str, *, limit: int = 560) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return "No readable text was supplied; metadata and lineage were retained."
    if len(compact) <= limit:
        return compact
    sentence_end = max(compact.rfind(". ", 0, limit), compact.rfind("; ", 0, limit))
    end = sentence_end + 1 if sentence_end >= limit // 2 else limit
    return compact[:end].rstrip() + "..."


def _normalized_item(item: dict[str, Any], index: int, *, attachment: bool) -> dict[str, Any]:
    kind = _context_kind(item, attachment=attachment)
    text_value = (
        item.get("text")
        or item.get("content")
        or item.get("text_preview")
        or item.get("folder_manifest")
        or item.get("terminal_output")
        or ""
    )
    text_clean, text_redactions = redact_text(str(text_value or ""))
    if kind in {"image", "screenshot"} and not text_clean:
        shown_name = _safe_name(item.get("name") or item.get("path"), f"context_{index + 1}")
        text_clean = (
            f"User attached a {kind} named {shown_name}. "
            "This is a real picture, not an empty file. "
            "Answer from what is visible in the picture. "
            "Do not say no readable text was supplied."
        )
    lineage_value, lineage_redactions = redact_value(
        {
            "source": item.get("source") or ("Engel chat attachment intake" if attachment else "Engel chat context item"),
            "source_attachment_id": item.get("id") or "",
            "source_path": item.get("source_path") or item.get("path") or "",
            "stored_path": item.get("stored_path") or "",
            "source_sha256": item.get("sha256") or "",
            "schema": item.get("schema") or "",
        }
    )
    return {
        "item_id": f"context_item_{index + 1}",
        "kind": kind,
        "name": _safe_name(item.get("name") or item.get("path"), f"context_{index + 1}"),
        "mime_type": _clean_scalar(item.get("mime_type") or item.get("mime") or "text/plain", 120),
        "size_bytes": int(item.get("size_bytes") or item.get("size") or len(text_clean.encode("utf-8"))),
        "text": text_clean,
        "text_truncated_at_source": bool(item.get("text_preview_truncated") or item.get("inline_truncated")),
        "lineage": lineage_value,
        "redaction_count": int(text_redactions) + int(lineage_redactions),
        "attachment_receipt": attachment,
    }


def build_context_pack(
    *,
    prompt: str,
    attachments: list[dict[str, Any]] | None = None,
    context_items: list[dict[str, Any]] | None = None,
    request: dict[str, Any] | None = None,
    source: str = "engel-ai-main-chat",
    root: str | Path | None = None,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> dict[str, Any]:
    attachments = attachments if isinstance(attachments, list) else []
    context_items = context_items if isinstance(context_items, list) else []
    request = request if isinstance(request, dict) else {}
    pack_root = Path(root or os.environ.get("ENGEL_CONTEXT_PACK_ROOT") or DEFAULT_CONTEXT_PACK_ROOT)
    raw_items: list[tuple[dict[str, Any], bool]] = []
    raw_items.extend((item, True) for item in attachments if isinstance(item, dict))
    raw_items.extend((item, False) for item in context_items if isinstance(item, dict))
    if not raw_items:
        return {
            "schema": "ENGEL_CODEX_WORKBENCH_CONTEXT_PACK_V1",
            "ok": True,
            "created": False,
            "status": "no context input supplied",
            "item_count": 0,
            "chunk_count": 0,
            "source_lineage_retained": True,
            "training_candidate": False,
            "trusted_memory_write": False,
            "external_array_used": False,
            "prompt_context": "",
        }

    normalized = [_normalized_item(item, index, attachment=attachment) for index, (item, attachment) in enumerate(raw_items)]
    identity = json.dumps(
        {
            "prompt_sha256": _sha256_text(str(prompt or "")),
            "conversation_id": str(request.get("conversation_id") or ""),
            "items": [
                {
                    "kind": item["kind"],
                    "name": item["name"],
                    "source_sha256": item["lineage"].get("source_sha256", ""),
                    "text_sha256": _sha256_text(item["text"]),
                }
                for item in normalized
            ],
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    pack_id = f"context_pack_{_stamp()}_{_sha256_text(identity)[:12]}"
    pack_dir = pack_root / pack_id
    chunks_dir = pack_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=False)

    manifest_items: list[dict[str, Any]] = []
    prompt_lines = [f"Engel context pack {pack_id} contains verified user-supplied context:"]
    total_chunks = 0
    all_redactions = 0
    content_types: set[str] = set()
    for item in normalized:
        source_text = item.pop("text")
        bounded = source_text[:max_item_chars]
        ingest_truncated = len(source_text) > len(bounded)
        available_slots = max(0, max_chunks - total_chunks)
        item_chunks = _chunk_text(bounded, max(128, chunk_chars), max(0, chunk_overlap), available_slots)
        chunk_records: list[dict[str, Any]] = []
        for chunk_index, chunk in enumerate(item_chunks):
            chunk_id = f"{item['item_id']}_chunk_{chunk_index + 1:03d}"
            chunk_record = {
                "schema": "ENGEL_CODEX_WORKBENCH_CONTEXT_CHUNK_V1",
                "pack_id": pack_id,
                "chunk_id": chunk_id,
                "item_id": item["item_id"],
                "kind": item["kind"],
                "ordinal": chunk_index + 1,
                "text": chunk,
                "sha256": _sha256_text(chunk),
                "source_lineage": item["lineage"],
                "trusted_memory_write": False,
            }
            chunk_path = chunks_dir / f"{chunk_id}.json"
            chunk_path.write_text(json.dumps(chunk_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            chunk_records.append({"chunk_id": chunk_id, "path": str(chunk_path), "sha256": chunk_record["sha256"], "chars": len(chunk)})
        summary = _extractive_summary(bounded)
        manifest_item = {
            **item,
            "summary": summary,
            "content_sha256": _sha256_text(source_text),
            "ingested_chars": len(bounded),
            "ingest_truncated": ingest_truncated or (bool(bounded) and not item_chunks),
            "chunks": chunk_records,
        }
        manifest_items.append(manifest_item)
        total_chunks += len(chunk_records)
        all_redactions += int(item.get("redaction_count") or 0)
        content_types.add(str(item["kind"]))
        prompt_lines.append(f"- {item['kind']}: {item['name']} - {summary}")

    manifest = {
        "schema": "ENGEL_CODEX_WORKBENCH_CONTEXT_PACK_MANIFEST_V1",
        "ok": True,
        "pack_id": pack_id,
        "created_at_utc": _iso_now(),
        "source": _clean_scalar(source, 160),
        "source_request": {
            "conversation_id": _clean_scalar(request.get("conversation_id") or "", 128),
            "request_id": _clean_scalar(request.get("id") or request.get("request_id") or "", 128),
            "prompt_sha256": _sha256_text(str(prompt or "")),
        },
        "item_count": len(manifest_items),
        "chunk_count": total_chunks,
        "content_types": sorted(content_types),
        "redaction_count": all_redactions,
        "source_lineage_retained": True,
        "untrusted_context": True,
        "eval_candidate": False,
        "training_candidate": False,
        "trusted_memory_write": False,
        "external_array_used": False,
        "items": manifest_items,
    }
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    prompt_context = "\n".join(prompt_lines)
    return {
        "schema": "ENGEL_CODEX_WORKBENCH_CONTEXT_PACK_V1",
        "ok": True,
        "created": True,
        "status": "context pack created",
        "pack_id": pack_id,
        "context_pack_path": str(pack_dir),
        "manifest_path": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "item_count": len(manifest_items),
        "chunk_count": total_chunks,
        "content_types": sorted(content_types),
        "source_lineage_retained": True,
        "untrusted_context": True,
        "eval_candidate": False,
        "training_candidate": False,
        "trusted_memory_write": False,
        "external_array_used": False,
        "prompt_context": prompt_context[:12000],
    }


def status_snapshot(root: str | Path | None = None) -> dict[str, Any]:
    pack_root = Path(root or os.environ.get("ENGEL_CONTEXT_PACK_ROOT") or DEFAULT_CONTEXT_PACK_ROOT)
    manifests = sorted(pack_root.glob("context_pack_*/manifest.json"), reverse=True) if pack_root.is_dir() else []
    latest: dict[str, Any] = {}
    if manifests:
        try:
            latest = json.loads(manifests[0].read_text(encoding="utf-8"))
        except Exception:
            latest = {}
    return {
        "schema": "ENGEL_CODEX_WORKBENCH_CONTEXT_PACK_STATUS_V1",
        "ok": True,
        "status": "context pack ingest ready",
        "context_pack_root": str(pack_root),
        "pack_count": len(manifests),
        "latest_pack_id": latest.get("pack_id", ""),
        "latest_item_count": latest.get("item_count", 0),
        "latest_chunk_count": latest.get("chunk_count", 0),
        "source_lineage_retained": True,
        "training_candidate": False,
        "trusted_memory_write": False,
        "external_array_used": False,
    }


if __name__ == "__main__":
    print(json.dumps(status_snapshot(), indent=2, sort_keys=True))
