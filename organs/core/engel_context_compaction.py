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
MAINTAINED_SCHEMA = "engel_conversation_maintained_v1"
MAX_SUMMARY_CHARS = 2400
_STATUS_LOG_MARKERS = (
    "runner pid:",
    "runpod was not used",
    "i will not mark the model upgraded",
    "sent that through the agent meeting room",
    "room result:",
    "order main-",
    "log: /opt/engel",
    "log: /workspace",
    ": assigned",
)


def looks_like_status_log(text: Any) -> bool:
    """True when a turn is an operations ledger, not the work itself."""
    low = " ".join(str(text or "").casefold().split())
    if not low:
        return False
    if low.count("assigned") >= 2 or ": assigned" in low:
        return True
    hits = sum(1 for marker in _STATUS_LOG_MARKERS if marker in low)
    if "runner pid:" in low and "log:" in low:
        return True
    return hits >= 2


def read_host_memory(meminfo: str | None = None) -> dict[str, Any]:
    """Read RAM/swap from /proc/meminfo. Swap already in use blocks new runners."""
    if meminfo is None:
        try:
            meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
        except OSError:
            meminfo = ""
    values: dict[str, int] = {}
    for line in str(meminfo or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":") and parts[1].isdigit():
            values[parts[0][:-1]] = int(parts[1])
    swap_total = values.get("SwapTotal", 0)
    swap_free = values.get("SwapFree", swap_total)
    swap_used = max(0, swap_total - swap_free)
    return {
        "swap_total_kb": swap_total,
        "swap_free_kb": swap_free,
        "swap_used_kb": swap_used,
        "swap_in_use": swap_used > 0,
        "mem_available_kb": values.get("MemAvailable", 0),
        "new_process_allowed": swap_used == 0,
    }


def work_text(text: Any, limit: int = 280) -> str:
    """First useful sentence, empty when the text is only a status log."""
    raw = " ".join(str(text or "").split())
    if not raw or looks_like_status_log(raw):
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", raw, maxsplit=1)[0].strip()
    if sentence.casefold().startswith("main ui routed answer returned to station:"):
        sentence = sentence.split(":", 1)[1].strip()
    return sentence[: max(0, limit)]


def training_spoken_reply(
    *,
    started: bool,
    blocked_reason: str = "",
    row_count: Any = None,
    swap_in_use: bool = False,
) -> str:
    """What a desk should say. Pid and log path stay in the receipt."""
    rows = ""
    if row_count:
        rows = f" The package has {row_count} rows."
    reason = str(blocked_reason or "")
    if reason == "swap" or swap_in_use:
        return (
            "I did not start another training process. Swap is already in use, "
            "so a new runner would page memory instead of train."
            + rows
            + " The conversation stays in the compressed digest, and the model "
            "is not upgraded without a verified local receipt."
        )
    if reason == "already_running":
        return (
            "Training is already running. I did not start a second runner. "
            "A duplicate would compete for RAM and push the host into swap."
            + rows
            + " This desk stays on the compressed conversation until that run "
            "writes its receipt."
        )
    if reason == "log_only":
        return (
            "That was a status log, not the work. I am not starting another run "
            "from a pid line, and I am not putting the log path back into chat."
            + rows
            + " The maintained digest keeps the conversation without holding the raw log."
        )
    if started:
        return (
            "I started one local training run."
            + rows
            + " The work is the dataset pass on this server. "
            "The model is not upgraded until the local receipt is verified. "
            "RunPod is not in this run. Older turns stay compressed so the raw log "
            "is not what this chat holds in memory."
        )
    if reason == "package_only":
        return (
            "The training package is built and waiting."
            + rows
            + " I did not start a runner. Say run training when you want one local "
            "pass. I will still refuse a second runner, and I will refuse any runner "
            "while swap is in use."
        )
    return (
        "Training was requested, but the package is not ready yet. "
        "I did not start a runner and I did not put a pid into chat."
    )


def meeting_room_work_reply(prompt: str, summary: str = "", station_text: str = "") -> str:
    useful = work_text(summary, 400) or work_text(station_text, 400) or work_text(prompt, 300)
    if useful:
        return (
            f"The room is doing this work: {useful} "
            "Assignment status stays in the receipt, not in chat."
        )
    return (
        "The room accepted the order and is doing the work. "
        "Assignment status stays in the receipt, not in chat."
    )


def visible_meeting_room_work(meeting_room: dict[str, Any], prompt: str) -> str:
    """Speak returned work. Skip Assigned / order-id ledgers."""
    completion = meeting_room.get("completion") if isinstance(meeting_room.get("completion"), dict) else {}
    chunks: list[str] = []
    for source in (completion, meeting_room):
        if not isinstance(source, dict):
            continue
        for item in source.get("returned_previews") or []:
            text = work_text(item, 400)
            if text:
                chunks.append(text)
        for item in source.get("station_outcomes") or []:
            if not isinstance(item, dict):
                continue
            text = work_text(item.get("reply"), 400)
            if text:
                agent = str(item.get("agent") or "Agent").strip()
                chunks.append(f"{agent}: {text}")
        for item in source.get("collaboration_dialogue") or []:
            if not isinstance(item, dict):
                continue
            text = work_text(item.get("text"), 300)
            if text:
                chunks.append(text)
        summary = work_text(source.get("summary"), 400)
        if summary:
            chunks.append(summary)
    seen: set[str] = set()
    unique: list[str] = []
    for chunk in chunks:
        key = chunk.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    if unique:
        body = " ".join(unique[:3])[:900]
        return (
            f"The room did this work: {body} "
            "Assignment status stays in the receipt, not in chat."
        )
    return meeting_room_work_reply(prompt, "", "")


def replace_status_log_with_work(prompt: str, reply: str) -> str:
    low = " ".join(str(reply or "").casefold().split())
    if "training" in low or "runner pid:" in low:
        rows = None
        match = re.search(r"(\d+)\s+rows", str(reply or ""), re.IGNORECASE)
        if match:
            rows = int(match.group(1))
        return training_spoken_reply(
            started=False,
            blocked_reason="log_only",
            row_count=rows,
        )
    return meeting_room_work_reply(prompt, "", reply)


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


def maintain_conversation(
    messages: list[dict[str, str]],
    *,
    thread_id: str = "engel-main-chat",
    meminfo: str | None = None,
    max_recent: int = 4,
    max_chars: int = 1600,
    write: bool = True,
) -> dict[str, Any]:
    """Fold a thread into one overwritten digest plus a short recent window.

    Status logs are omitted. The raw transcript is not copied into the maintained
    file. While swap is in use the window shrinks and new_process_allowed is false.
    """
    host = read_host_memory(meminfo)
    if host["swap_in_use"]:
        max_recent = min(max_recent, 2)
        max_chars = min(max_chars, 700)
    cleaned: list[dict[str, str]] = []
    omitted_logs = 0
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip()[:32] or "user"
        content = " ".join(str(item.get("content") or "").split())
        if not content:
            continue
        if role.casefold() in {"assistant", "engel", "bot"} and looks_like_status_log(content):
            omitted_logs += 1
            continue
        snippet = work_text(content, 180) or content[:180]
        cleaned.append({"role": role, "content": snippet})
    recent = cleaned[-max(1, max_recent) :] if cleaned else []
    older = cleaned[: max(0, len(cleaned) - len(recent))]
    digest = " | ".join(f"{row['role']}: {row['content']}" for row in older)[:max_chars]
    lines: list[str] = []
    if digest:
        lines.append("MAINTAINED CONVERSATION (compressed): " + digest)
    for row in recent:
        lines.append(f"{row['role']}: {row['content'][:240]}")
    context = "\n".join(lines).strip()[:max_chars]
    safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", thread_id)[:64] or "engel-main-chat"
    state = {
        "schema": MAINTAINED_SCHEMA,
        "updated_at_utc": _now(),
        "thread_id": safe_id,
        "maintained": True,
        "provider": "local_only",
        "swap_in_use": host["swap_in_use"],
        "new_process_allowed": host["new_process_allowed"],
        "swap_used_kb": host["swap_used_kb"],
        "omitted_status_logs": omitted_logs,
        "kept_turns": len(cleaned),
        "digest": digest,
        "recent": recent,
        "context": context,
        "memory_policy": "compressed_working_set_no_new_process_while_swap_in_use",
        "trusted_memory_write_enabled": False,
    }
    if write:
        _ensure()
        path = STATE_DIR / f"maintained_{safe_id}.json"
        path.write_text(
            json.dumps(state, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        state["state_path"] = str(path)
    return state


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
