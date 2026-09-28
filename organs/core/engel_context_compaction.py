"""Local context compaction — landscape gap #2 (xAI/OpenAI compaction parity).

Shrinks a message list into a local opaque compaction receipt. No provider
calls. Does not write trusted memory or ALIVE_STATE.

Contract: memory/ENGEL_CONTEXT_COMPACTION_CONTRACT_V1.md
Routes: engel.compaction.*
Verifier: tools/verify_engel_context_compaction.py
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engel_project_paths import resolve_engel_app_root

ROOT = resolve_engel_app_root(__file__)
STATE_DIR = ROOT / "runtime" / "compaction"
RECEIPT_DIR = ROOT / "reports" / "compaction"
CONTRACT_PATH = ROOT / "memory" / "ENGEL_CONTEXT_COMPACTION_CONTRACT_V1.md"

SCHEMA = "engel_context_compaction_v1"
MAX_SUMMARY_CHARS = 2400


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)


def compact_messages(
    messages: list[dict[str, str]],
    *,
    thread_id: str = "default",
    keep_system: bool = True,
) -> dict[str, Any]:
    """Build a local compaction receipt from message dicts {role, content}."""
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    cleaned: list[dict[str, str]] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip()[:32]
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        cleaned.append({"role": role, "content": content[:8000]})
    if not cleaned:
        raise ValueError("no usable messages")

    system_bits = [
        m["content"] for m in cleaned if keep_system and m["role"].casefold() == "system"
    ]
    body = [m for m in cleaned if m["role"].casefold() != "system" or not keep_system]
    # Salient local summary: last user + last assistant + role counts (no model call).
    role_counts: dict[str, int] = {}
    for item in cleaned:
        role_counts[item["role"]] = role_counts.get(item["role"], 0) + 1
    last_user = next(
        (m["content"] for m in reversed(body) if m["role"].casefold() == "user"),
        "",
    )
    last_assistant = next(
        (
            m["content"]
            for m in reversed(body)
            if m["role"].casefold() in {"assistant", "engel", "bot"}
        ),
        "",
    )
    summary_parts = [
        f"thread={thread_id}",
        f"messages={len(cleaned)}",
        f"roles={json.dumps(role_counts, sort_keys=True)}",
    ]
    if system_bits:
        summary_parts.append("system=" + system_bits[0][:400])
    if last_user:
        summary_parts.append("last_user=" + last_user[:600])
    if last_assistant:
        summary_parts.append("last_assistant=" + last_assistant[:600])
    summary = "\n".join(summary_parts)[:MAX_SUMMARY_CHARS]

    raw = json.dumps(
        {"messages": cleaned, "summary": summary},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest().upper()
    blob = hashlib.sha256((digest + "|" + summary).encode("utf-8")).hexdigest().upper()

    receipt = {
        "schema": SCHEMA,
        "created_at_utc": _now(),
        "thread_id": re.sub(r"[^a-zA-Z0-9._-]+", "-", thread_id)[:64] or "default",
        "input_message_count": len(cleaned),
        "dropped_message_count": len(cleaned),
        "summary": summary,
        "compaction_sha256": digest,
        "opaque_blob_sha256": blob,
        "provider": "local_only",
        "rehydrate_hint": (
            "Pass opaque_blob_sha256 + summary as the compacted prefix for the next "
            "local turn. Original verbose tool dumps are not retained in the receipt."
        ),
    }
    _ensure()
    path = (
        RECEIPT_DIR
        / f"ENGEL_COMPACTION_{receipt['thread_id']}_{digest[:16]}.json"
    )
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    latest = STATE_DIR / f"latest_{receipt['thread_id']}.json"
    latest.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    receipt["receipt_path"] = str(path)
    return receipt


def render_compaction_docs(payload: str = "") -> str:
    del payload
    return "\n".join(
        [
            "Engel Context Compaction V1",
            "",
            "Local parity with xAI/OpenAI compaction: shrink a long thread into a",
            "receipt (summary + hashes). No provider call. No trusted-memory write.",
            "",
            "Phrases:",
            "- engel compaction status",
            "- engel compaction docs",
            "- compact engel thread <thread_id> | role:text || role:text ...",
            "",
            f"Contract: {CONTRACT_PATH.relative_to(ROOT).as_posix()}",
        ]
    )


def render_compaction_status(payload: str = "") -> str:
    del payload
    _ensure()
    latest = sorted(STATE_DIR.glob("latest_*.json"))
    lines = [
        "Engel Compaction status",
        "",
        f"latest_threads: {len(latest)}",
        f"provider: local_only",
        "",
    ]
    for path in latest[-8:]:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        lines.append(
            f"- {row.get('thread_id')}: messages={row.get('input_message_count')} "
            f"sha={str(row.get('compaction_sha256') or '')[:16]} "
            f"at {row.get('created_at_utc')}"
        )
    if len(lines) == 5:
        lines.append("No compaction receipts yet.")
    return "\n".join(lines)


def render_compaction_compact(payload: str = "") -> str:
    text = (payload or "").strip()
    folded = text.casefold()
    for prefix in (
        "compact engel thread ",
        "engel compact thread ",
        "compact thread ",
    ):
        if folded.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    if not text:
        return (
            "Usage: compact engel thread <thread_id> | role:text || role:text\n"
            "Example: compact engel thread chat1 | user:status? || assistant:tunnels ok"
        )
    if "|" not in text:
        return "Need thread_id | messages (role:text separated by ||)"
    thread_id, body = [part.strip() for part in text.split("|", 1)]
    messages: list[dict[str, str]] = []
    for chunk in body.split("||"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            messages.append({"role": "user", "content": chunk})
            continue
        role, content = chunk.split(":", 1)
        messages.append({"role": role.strip(), "content": content.strip()})
    try:
        receipt = compact_messages(messages, thread_id=thread_id)
    except ValueError as exc:
        return f"Compaction blocked: {exc}"
    return "\n".join(
        [
            f"Compacted thread: {receipt['thread_id']}",
            f"messages_in: {receipt['input_message_count']}",
            f"compaction_sha256: {receipt['compaction_sha256']}",
            f"opaque_blob_sha256: {receipt['opaque_blob_sha256']}",
            f"receipt: {receipt['receipt_path']}",
            "",
            "Local only — no provider, no trusted-memory promotion.",
        ]
    )
