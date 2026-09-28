#!/usr/bin/env python3
"""Discord desk ↔ Engel ↔ Android worker pipe (no Discord on phones).

Canonical flow:
  Discord desk mouth / Main on-charter
    → enqueue_from_desk(...) creates a Communication Queen assignment
    → phone polls Meeting Room / LAN worker queue (existing path)
    → phone returns untrusted draft_result_json
    → collect_pending_replies / format_discord_reply for desk mouth reply

Phones never install or run Discord. They only see approved assignment packets
with optional origin attribution. Results stay review-gated.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from engel_android_worker_agent_brain import (
    WORKER_IDS,
    binding_for_worker,
    worker_bindings,
)
from engel_branding import ENGEL_COMMUNICATION_ROUTER_NAME
from engel_communication_queen_assignment_producer import (
    APPROVED_DIR,
    RETURNED_DIR,
    SourceMaterial,
    build_assignment_packet,
    ensure_scaffold,
    utc_stamp,
    write_packet,
    write_receipt,
)
from engel_device_capability_registry import (
    infer_job_type_from_text,
    select_worker_for_job,
)
from engel_project_paths import resolve_engel_app_root

APP_ROOT = resolve_engel_app_root(__file__)
PIPE_ROOT = APP_ROOT / "remote_workers" / "discord_android_pipe"
PIPE_OUTBOX = PIPE_ROOT / "pending_discord_replies"
PIPE_SENT = PIPE_ROOT / "sent_discord_replies"
PIPE_OPEN = PIPE_ROOT / "open_jobs"
PIPE_RECEIPTS = APP_ROOT / "reports" / "discord_android_pipe"
PIPE_SCHEMA = "engel_discord_android_worker_pipe_v1"
CLAIMED_DIR = APP_ROOT / "remote_workers" / "communication_queen_assignments" / "claimed"
DEFAULT_ROG_RETURNED_LOOKUP_URL = "http://127.0.0.1:18765/queue/returned-result"
SELF_TASK_MAX_STEPS = 6
_SELF_TASK_DONE_MARKERS = (
    "that is enough",
    "no further",
    "nothing more to look up",
    "work is finished",
    "no next task",
)
_SELF_TASK_FAIL_MARKERS = (
    "no search results",
    "search_http_",
    "search failed",
    "failed to fetch",
)

DESK_MOUTHS = {
    "main": "Engel AI Main",
    "research": "Engel Research",
    "product": "Engel Product",
    "community": "Engel Community",
    "support": "Engel Support",
    "sales": "Engel Sales",
    "ops": "Engel Ops",
}

# Desk → preferred worker when capability selector is inconclusive.
DESK_DEFAULT_WORKER = {
    "research": "android_worker_alpha",
    "product": "android_worker_alpha",
    "ops": "android_worker_beta",
    "support": "android_worker_beta",
    "community": "android_worker_gamma",
    "sales": "android_worker_gamma",
    "main": "android_worker_alpha",
}

DESK_DEFAULT_TASK = {
    "research": "web_research_brief",
    "product": "draft_code_artifact",
    "ops": "draft_candidate_json",
    "support": "format_report_draft",
    "community": "summarize_text",
    "sales": "format_report_draft",
    "main": "web_research_brief",
}


def _ensure_pipe_dirs() -> None:
    ensure_scaffold()
    for path in (PIPE_ROOT, PIPE_OUTBOX, PIPE_SENT, PIPE_OPEN, PIPE_RECEIPTS):
        path.mkdir(parents=True, exist_ok=True)


def _open_job_path(packet_id: str) -> Path:
    return PIPE_OPEN / f"{_clean_id(packet_id, 120)}.json"


def write_open_job(record: dict[str, Any]) -> Path:
    """Track Discord-origin packet so returns without embedded origin still ship."""
    _ensure_pipe_dirs()
    packet_id = _clean_id(record.get("packet_id"), 120)
    path = _open_job_path(packet_id)
    payload = dict(record)
    payload["schema"] = PIPE_SCHEMA
    payload["packet_id"] = packet_id
    payload.setdefault("tracked_at", utc_stamp())
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_open_job(packet_id: str) -> dict[str, Any] | None:
    return _load_json(_open_job_path(packet_id))


def _origin_from_claimed_assignment(packet_id: str) -> dict[str, Any] | None:
    """Recover Discord origin from claimed assignment copy (results omit it)."""
    pid = str(packet_id or "").strip()
    if not pid or not CLAIMED_DIR.exists():
        return None
    needle = pid.casefold()
    for path in sorted(CLAIMED_DIR.glob("*_assignment.json"), reverse=True):
        packet = _load_json(path)
        if not packet:
            continue
        if str(packet.get("packet_id") or "").casefold() != needle:
            continue
        origin = packet.get("origin")
        return origin if isinstance(origin, dict) else None
    return None


def resolve_result_origin(
    result: dict[str, Any],
    *,
    packet_id: str = "",
) -> dict[str, Any] | None:
    assignment = result.get("assignment") if isinstance(result.get("assignment"), dict) else None
    if assignment and isinstance(assignment.get("origin"), dict):
        return assignment["origin"]
    if isinstance(result.get("origin"), dict):
        return result["origin"]
    pid = str(
        packet_id
        or result.get("task_packet_id")
        or result.get("packet_id")
        or (assignment or {}).get("packet_id")
        or ""
    )
    open_job = load_open_job(pid) if pid else None
    if open_job and isinstance(open_job.get("origin"), dict):
        return open_job["origin"]
    claimed_origin = _origin_from_claimed_assignment(pid) if pid else None
    if claimed_origin:
        return claimed_origin
    return None


def _clean_id(value: Any, limit: int = 64) -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "", str(value or "").strip())
    return text[:limit]


def _desk_id(value: str) -> str:
    desk = str(value or "main").strip().lower()
    return desk if desk in DESK_MOUTHS else "main"


def resolve_worker_and_task(
    *,
    text: str,
    desk_id: str,
    worker_id: str | None = None,
    task_type: str | None = None,
) -> tuple[str, str]:
    desk = _desk_id(desk_id)
    if worker_id and worker_id in WORKER_IDS:
        chosen_worker = worker_id
    else:
        inferred = infer_job_type_from_text(text, DESK_DEFAULT_TASK.get(desk, "summarize_text"))
        selected = select_worker_for_job(inferred, text) or {}
        chosen_worker = str(selected.get("worker_id") or "")
        if chosen_worker not in WORKER_IDS:
            chosen_worker = DESK_DEFAULT_WORKER.get(desk, "android_worker_alpha")
    binding = binding_for_worker(chosen_worker)
    preferred = list(binding.get("preferred_job_types") or [])
    phone_limbs = {"web_research_brief", "draft_code_artifact"}
    if task_type:
        chosen_task = task_type
    else:
        inferred_task = infer_job_type_from_text(text, DESK_DEFAULT_TASK.get(desk, "summarize_text"))
        if inferred_task in phone_limbs:
            chosen_task = inferred_task
        elif inferred_task in preferred or not preferred:
            chosen_task = inferred_task
        else:
            chosen_task = preferred[0]
        if preferred and chosen_task not in preferred and chosen_task not in phone_limbs:
            chosen_task = preferred[0]
    return chosen_worker, chosen_task


def enqueue_from_desk(
    *,
    desk_id: str,
    text: str,
    title: str | None = None,
    worker_id: str | None = None,
    task_type: str | None = None,
    channel_id: str | None = None,
    message_id: str | None = None,
    thread_id: str | None = None,
    guild_id: str | None = None,
    parent_packet_id: str | None = None,
    loop_step: int | None = None,
    origin_prompt: str | None = None,
    loop_reason: str | None = None,
) -> dict[str, Any]:
    """Create a CQ assignment from a Discord desk ask. No Discord secrets stored."""
    _ensure_pipe_dirs()
    desk = _desk_id(desk_id)
    body = str(text or "").strip()
    if not body:
        return {"ok": False, "error": "empty desk text"}
    chosen_worker, chosen_task = resolve_worker_and_task(
        text=body,
        desk_id=desk,
        worker_id=worker_id,
        task_type=task_type,
    )
    binding = binding_for_worker(chosen_worker)
    job_title = (title or f"Discord {DESK_MOUTHS[desk]} → {binding.get('agent_name') or chosen_worker}").strip()
    instructions = "\n".join(
        [
            f"Desk origin: {DESK_MOUTHS[desk]} ({desk})",
            f"Assigned agent: {binding.get('agent_name') or chosen_worker}",
            f"Assigned brain: {binding.get('brain_label') or 'n/a'} [{binding.get('brain_id') or 'n/a'}]",
            "Return an untrusted draft only. Do not execute commands or control Engel.",
            f"Working sandbox is on this phone at /storage/emulated/0/Download/EngelRemoteWorker/desks/{desk}.",
            "Read that folder before you draft. Append sandbox/journal/turns.jsonl. The server copy is a pointer.",
            "Discord is not installed on this phone.",
            "",
            "Desk request:",
            body[:3500],
        ]
    )
    packet = build_assignment_packet(
        worker=chosen_worker,
        task_type=chosen_task,
        title=job_title[:160],
        instructions=instructions,
        source=SourceMaterial(None, None, body[:1200], len(body) > 1200, len(body.encode("utf-8"))),
    )
    # Attribution only — never store tokens/secrets.
    packet["origin"] = {
        "source": "discord_desk",
        "pipe": PIPE_SCHEMA,
        "desk_id": desk,
        "desk_mouth": DESK_MOUTHS[desk],
        "channel_id": _clean_id(channel_id),
        "message_id": _clean_id(message_id),
        "thread_id": _clean_id(thread_id),
        "guild_id": _clean_id(guild_id),
        "discord_on_phone": False,
        "reply_via": "engel_main_or_desk_mouth",
        "parent_packet_id": _clean_id(parent_packet_id, 120),
        "loop_step": int(loop_step or 1),
        "loop_reason": str(loop_reason or "initial")[:80],
        "origin_prompt": str(origin_prompt or body)[:1500],
    }
    packet["agent_binding"] = {
        "agent_id": binding.get("agent_id"),
        "agent_name": binding.get("agent_name"),
        "meeting_room_label": binding.get("meeting_room_label"),
    }
    packet["brain_binding"] = {
        "brain_id": binding.get("brain_id"),
        "brain_label": binding.get("brain_label"),
        "brain_lane": binding.get("brain_lane"),
        "on_device_model_runtime": False,
    }
    path, sha = write_packet(packet, APPROVED_DIR)
    receipt = write_receipt(
        action="discord_desk_enqueue",
        packet=packet,
        packet_path=path,
        packet_sha256=sha,
    )
    open_job_path = write_open_job(
        {
            "packet_id": packet["packet_id"],
            "worker_id": chosen_worker,
            "task_type": chosen_task,
            "desk_id": desk,
            "origin": packet["origin"],
            "agent_name": binding.get("agent_name"),
            "brain_label": binding.get("brain_label"),
            "assignment_path": str(path),
            "parent_packet_id": _clean_id(parent_packet_id, 120),
            "loop_step": int(loop_step or 1),
            "loop_reason": str(loop_reason or "initial")[:80],
            "origin_prompt": str(origin_prompt or body)[:1500],
        }
    )
    pipe_receipt = PIPE_RECEIPTS / f"PIPE_ENQUEUE_{packet['packet_id']}.json"
    pipe_receipt.write_text(
        json.dumps(
            {
                "ok": True,
                "schema": PIPE_SCHEMA,
                "packet_id": packet["packet_id"],
                "worker_id": chosen_worker,
                "task_type": chosen_task,
                "desk_id": desk,
                "assignment_path": str(path),
                "receipt_path": str(receipt),
                "open_job_path": str(open_job_path),
                "created_at": utc_stamp(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "packet_id": packet["packet_id"],
        "worker_id": chosen_worker,
        "task_type": chosen_task,
        "desk_id": desk,
        "agent_name": binding.get("agent_name"),
        "brain_label": binding.get("brain_label"),
        "assignment_path": str(path),
        "receipt_path": str(receipt),
        "pipe_receipt": str(pipe_receipt),
        "open_job_path": str(open_job_path),
        "discord_on_phone": False,
        "loop_step": int(loop_step or 1),
        "parent_packet_id": _clean_id(parent_packet_id, 120),
        "loop_reason": str(loop_reason or "initial")[:80],
    }


def channel_has_open_phone_job(channel_id: str) -> bool:
    """True when this Discord channel already has an unsent phone job in flight."""
    needle = _clean_id(channel_id)
    if not needle or not PIPE_OPEN.exists():
        return False
    for path in PIPE_OPEN.glob("*.json"):
        job = _load_json(path)
        if not isinstance(job, dict):
            continue
        origin = job.get("origin") if isinstance(job.get("origin"), dict) else {}
        if _clean_id(origin.get("channel_id")) != needle:
            continue
        packet_id = str(job.get("packet_id") or path.stem)
        if (PIPE_SENT / f"{packet_id}.json").exists():
            continue
        return True
    return False


def propose_next_phone_task(
    *,
    origin_text: str,
    last_task_type: str,
    result_summary: str,
    loop_step: int,
    desk_id: str = "main",
) -> dict[str, Any] | None:
    """Decide the next needed phone task. None means the loop is done.

    Bounded: max SELF_TASK_MAX_STEPS, one retry on failed search, research→create
    when the original ask wanted creation. No unbounded autonomy.
    """
    step = int(loop_step or 1)
    if step >= SELF_TASK_MAX_STEPS:
        return None
    origin = str(origin_text or "").strip()
    summary = str(result_summary or "").strip()
    if not origin:
        return None
    low_sum = summary.casefold()
    low_origin = origin.casefold()
    if any(marker in low_sum for marker in _SELF_TASK_DONE_MARKERS):
        return None
    last = str(last_task_type or "").strip()
    if (
        last == "web_research_brief"
        and any(marker in low_sum for marker in _SELF_TASK_FAIL_MARKERS)
        and step < 2
    ):
        return {
            "task_type": "web_research_brief",
            "title": f"{DESK_MOUTHS.get(desk_id, 'Desk')} retry web research",
            "text": origin,
            "reason": "search_retry",
        }
    wants_create = last != "draft_code_artifact" and (
        infer_job_type_from_text(origin, "") == "draft_code_artifact"
        or any(
            needle in low_origin
            for needle in (
                "write code",
                "create code",
                "make a game",
                "create a game",
                "then create",
                "then write",
                "and make",
                "and create",
                "build it",
                "draft code",
            )
        )
    )
    if last == "web_research_brief" and wants_create:
        return {
            "task_type": "draft_code_artifact",
            "title": f"{DESK_MOUTHS.get(desk_id, 'Desk')} create from research",
            "text": origin[:1500] + "\n\nResearch draft to use:\n" + summary[:800],
            "reason": "research_then_create",
        }
    return None


def enqueue_needed_followup(
    *,
    parent_packet_id: str,
    result_summary: str = "",
    allow: bool = True,
) -> dict[str, Any] | None:
    """Queue the next needed phone task after a return. No-op at cap/stop/in-flight."""
    if not allow:
        return None
    parent = load_open_job(parent_packet_id) or {}
    if not parent:
        return None
    origin = parent.get("origin") if isinstance(parent.get("origin"), dict) else {}
    channel_id = str(origin.get("channel_id") or "")
    desk_id = str(parent.get("desk_id") or origin.get("desk_id") or "main")
    origin_text = str(parent.get("origin_prompt") or origin.get("origin_prompt") or "")
    last_task = str(parent.get("task_type") or "")
    step = int(parent.get("loop_step") or origin.get("loop_step") or 1)
    if channel_has_open_phone_job(channel_id):
        # Parent is still the open job until marked sent; ignore self.
        sent = PIPE_SENT / f"{parent_packet_id}.json"
        others = False
        if PIPE_OPEN.exists():
            for path in PIPE_OPEN.glob("*.json"):
                job = _load_json(path)
                if not isinstance(job, dict):
                    continue
                pid = str(job.get("packet_id") or "")
                if pid in {parent_packet_id, path.stem}:
                    continue
                job_origin = job.get("origin") if isinstance(job.get("origin"), dict) else {}
                if _clean_id(job_origin.get("channel_id")) == _clean_id(channel_id):
                    if not (PIPE_SENT / f"{pid}.json").exists():
                        others = True
                        break
        if others:
            return None
    nxt = propose_next_phone_task(
        origin_text=origin_text,
        last_task_type=last_task,
        result_summary=result_summary,
        loop_step=step,
        desk_id=desk_id,
    )
    if not nxt:
        return None
    queued = enqueue_from_desk(
        desk_id=desk_id,
        text=str(nxt.get("text") or origin_text),
        title=str(nxt.get("title") or "Desk follow-up"),
        task_type=str(nxt.get("task_type") or ""),
        channel_id=channel_id,
        message_id=str(origin.get("message_id") or ""),
        thread_id=str(origin.get("thread_id") or ""),
        guild_id=str(origin.get("guild_id") or ""),
        parent_packet_id=parent_packet_id,
        loop_step=step + 1,
        origin_prompt=origin_text,
        loop_reason=str(nxt.get("reason") or "followup"),
    )
    if isinstance(queued, dict) and queued.get("ok"):
        queued["loop_max"] = SELF_TASK_MAX_STEPS
    return queued


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _result_summary(payload: dict[str, Any]) -> str:
    for key in ("summary", "result_text", "draft_text", "result", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:1800]
    nested = payload.get("result")
    if isinstance(nested, dict):
        for key in ("summary", "result_text", "draft_text"):
            value = nested.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:1800]
    return "(worker returned a draft with no summary text)"


def _search_engine_page(url: str) -> bool:
    host = urlparse(str(url or "")).netloc.casefold()
    return host == "duckduckgo.com" or host.endswith(".duckduckgo.com")


def public_phone_result_text(summary: str) -> str:
    """Spoken lookup lines. Device JSON and the search-engine page stay out of chat."""
    text = str(summary or "").strip()
    if not text:
        return ""
    data: Any = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                data = None
    if not isinstance(data, dict):
        low = text.casefold()
        if any(
            marker in low
            for marker in (
                "supported_abis",
                "search_endpoint",
                "device_capabilities",
                "html.duckduckgo.com",
                "private search without javascript",
            )
        ):
            return ""
        return text
    results = data.get("results")
    if not isinstance(results, list):
        nested = data.get("result")
        results = nested.get("results") if isinstance(nested, dict) else None
    lines: list[str] = []
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = " ".join(str(item.get("title") or "").split())
            snippet = " ".join(str(item.get("snippet") or "").split())
            if _search_engine_page(url) or "private search without javascript" in title.casefold():
                continue
            if not title and not snippet:
                continue
            line = title
            if url:
                line = f"{title} — {url}" if title else url
            if snippet:
                line = f"{line}: {snippet}" if line else snippet
            lines.append("- " + line)
    if lines:
        query = " ".join(str(data.get("query") or "").split())
        head = f"Lookup: {query}" if query else "Lookup findings:"
        return head + "\n" + "\n".join(lines[:5])
    if (
        data.get("candidate_type")
        or data.get("device_capabilities")
        or data.get("search_endpoint")
        or data.get("supported_abis")
    ):
        return ""
    return text


def format_discord_reply(
    *,
    worker_id: str,
    packet: dict[str, Any] | None,
    result: dict[str, Any],
) -> str:
    binding = binding_for_worker(worker_id)
    origin = (packet or {}).get("origin") if isinstance(packet, dict) else {}
    if not isinstance(origin, dict):
        origin = {}
    desk = origin.get("desk_mouth") or "Engel Discord desk"
    agent = binding.get("agent_name") or worker_id
    brain = binding.get("brain_label") or "dedicated brain"
    summary = _result_summary(result)
    spoken = public_phone_result_text(summary)
    if not spoken:
        return ""
    if spoken != summary.strip():
        return spoken
    return "\n".join(
        [
            f"{agent} ({brain}) finished a Discord-pipe draft for {desk}.",
            "Review-only — not trusted memory, not auto-applied.",
            "",
            spoken,
        ]
    )


def collect_pending_replies(limit: int = 20) -> list[dict[str, Any]]:
    """Scan returned CQ results that originated from Discord desks."""
    _ensure_pipe_dirs()
    pending: list[dict[str, Any]] = []
    if not RETURNED_DIR.exists():
        return pending
    for path in sorted(RETURNED_DIR.glob("*_result.json"), reverse=True):
        if len(pending) >= limit:
            break
        result = _load_json(path)
        if not result:
            continue
        assignment = result.get("assignment") if isinstance(result.get("assignment"), dict) else None
        packet_id = str(
            result.get("task_packet_id")
            or result.get("packet_id")
            or (assignment or {}).get("packet_id")
            or ""
        )
        origin = resolve_result_origin(result, packet_id=packet_id)
        if not isinstance(origin, dict) or origin.get("source") != "discord_desk":
            continue
        if origin.get("pipe") not in (None, PIPE_SCHEMA):
            continue
        if not packet_id:
            packet_id = path.stem
        sent_marker = PIPE_SENT / f"{packet_id}.json"
        outbox_marker = PIPE_OUTBOX / f"{packet_id}.json"
        if sent_marker.exists() or outbox_marker.exists():
            continue
        worker_id = str(
            result.get("from_worker_id")
            or result.get("worker_id")
            or (assignment or {}).get("worker_target")
            or (load_open_job(packet_id) or {}).get("worker_id")
            or ""
        )
        packet_for_reply = assignment if isinstance(assignment, dict) else {"origin": origin}
        if "origin" not in packet_for_reply:
            packet_for_reply = {**packet_for_reply, "origin": origin}
        reply_text = format_discord_reply(
            worker_id=worker_id, packet=packet_for_reply, result=result
        )
        open_job = load_open_job(packet_id) or {}
        record = {
            "schema": PIPE_SCHEMA,
            "packet_id": packet_id,
            "worker_id": worker_id,
            "desk_id": origin.get("desk_id"),
            "desk_mouth": origin.get("desk_mouth"),
            "channel_id": origin.get("channel_id"),
            "message_id": origin.get("message_id"),
            "thread_id": origin.get("thread_id"),
            "guild_id": origin.get("guild_id"),
            "result_path": str(path),
            "reply_text": reply_text,
            "result_summary": _result_summary(result),
            "task_type": open_job.get("task_type") or (assignment or {}).get("task_type"),
            "loop_step": open_job.get("loop_step") or origin.get("loop_step") or 1,
            "origin_prompt": open_job.get("origin_prompt") or origin.get("origin_prompt") or "",
            "requires_review": True,
            "safe_to_auto_apply": False,
            "discord_on_phone": False,
            "collected_at": utc_stamp(),
        }
        outbox_marker.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pending.append(record)
    return pending


def pull_rog_returned_result(
    *,
    packet_id: str,
    worker_id: str,
    lookup_url: str | None = None,
) -> dict[str, Any]:
    """Pull one ROG returned result over the CT→ROG tunnel (or local loopback)."""
    import os
    import urllib.error
    import urllib.parse
    import urllib.request

    pid = str(packet_id or "").strip()
    wid = str(worker_id or "").strip()
    if not pid or not wid:
        return {"ok": False, "error": "packet_id and worker_id required"}
    base = (
        lookup_url
        or os.environ.get("ENGEL_ROG_RETURNED_LOOKUP_URL")
        or DEFAULT_ROG_RETURNED_LOOKUP_URL
    )
    query = urllib.parse.urlencode({"packet_id": pid, "worker_id": wid})
    url = f"{base}?{query}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "EngelDiscordAndroidPipe/1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            raw = resp.read().decode("utf-8", "replace")
            data = json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:240]
        except Exception:  # noqa: BLE001
            body = ""
        return {
            "ok": False,
            "error": "http_error",
            "http_status": getattr(exc, "code", None),
            "detail": body or str(exc)[:160],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:160]}
    if not isinstance(data, dict) or not data.get("ok"):
        return {
            "ok": False,
            "error": "not_found_or_blocked",
            "response": data if isinstance(data, dict) else {},
        }
    result = data.get("result")
    if not isinstance(result, dict):
        return {"ok": False, "error": "missing_result_payload"}
    _ensure_pipe_dirs()
    RETURNED_DIR.mkdir(parents=True, exist_ok=True)
    origin = resolve_result_origin(result, packet_id=pid) or (load_open_job(pid) or {}).get("origin")
    if isinstance(origin, dict) and "origin" not in result:
        result = {**result, "origin": origin}
    stamp = utc_stamp()
    safe_pid = _clean_id(pid, 120) or "packet"
    out_path = RETURNED_DIR / f"{stamp}_{safe_pid}_result.json"
    # Avoid duplicate local copies of the same packet.
    for existing in RETURNED_DIR.glob(f"*_{safe_pid}_result.json"):
        out_path = existing
        break
    else:
        out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "packet_id": pid,
        "worker_id": wid,
        "result_path": str(out_path),
        "source": "rog_returned_lookup",
    }


def list_outbox_replies(limit: int = 20) -> list[dict[str, Any]]:
    """Load already-collected Discord replies waiting to be posted."""
    _ensure_pipe_dirs()
    pending: list[dict[str, Any]] = []
    if not PIPE_OUTBOX.exists():
        return pending
    for path in sorted(PIPE_OUTBOX.glob("*.json"), reverse=True):
        if len(pending) >= limit:
            break
        record = _load_json(path)
        if not record:
            continue
        packet_id = str(record.get("packet_id") or path.stem)
        if (PIPE_SENT / f"{packet_id}.json").exists():
            continue
        pending.append(record)
    return pending


def sync_open_jobs_from_rog(limit: int = 20) -> list[dict[str, Any]]:
    """Materialize ROG phone returns onto this host, then collect Discord replies."""
    _ensure_pipe_dirs()
    pulled = 0
    if PIPE_OPEN.exists():
        for path in sorted(PIPE_OPEN.glob("*.json"), reverse=True):
            if pulled >= limit:
                break
            job = _load_json(path)
            if not job:
                continue
            packet_id = str(job.get("packet_id") or "")
            worker_id = str(job.get("worker_id") or "")
            if not packet_id or not worker_id:
                continue
            if (PIPE_SENT / f"{packet_id}.json").exists():
                continue
            # Prefer local return if already present.
            local_hit = False
            if RETURNED_DIR.exists():
                for returned in RETURNED_DIR.glob(f"*_{_clean_id(packet_id, 120)}_result.json"):
                    if returned.is_file():
                        local_hit = True
                        break
            if local_hit:
                continue
            outcome = pull_rog_returned_result(packet_id=packet_id, worker_id=worker_id)
            if outcome.get("ok"):
                pulled += 1
    # Fresh collects first, then any already-queued outbox items.
    fresh = collect_pending_replies(limit=limit)
    seen = {str(item.get("packet_id") or "") for item in fresh}
    for item in list_outbox_replies(limit=limit):
        pid = str(item.get("packet_id") or "")
        if pid and pid not in seen:
            fresh.append(item)
            seen.add(pid)
        if len(fresh) >= limit:
            break
    return fresh


def mark_reply_sent(packet_id: str, *, note: str = "posted_by_desk_mouth") -> dict[str, Any]:
    _ensure_pipe_dirs()
    pid = str(packet_id or "").strip()
    if not pid:
        return {"ok": False, "error": "missing packet_id"}
    outbox = PIPE_OUTBOX / f"{pid}.json"
    sent = PIPE_SENT / f"{pid}.json"
    payload = _load_json(outbox) or {"packet_id": pid}
    payload["sent_at"] = utc_stamp()
    payload["sent_note"] = note
    sent.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if outbox.exists():
        outbox.unlink()
    return {"ok": True, "packet_id": pid, "sent_path": str(sent)}


def pipe_colony_snapshot() -> dict[str, Any]:
    _ensure_pipe_dirs()
    approved_discord = 0
    if APPROVED_DIR.exists():
        for path in APPROVED_DIR.glob("*.json"):
            packet = _load_json(path)
            origin = packet.get("origin") if isinstance(packet, dict) else None
            if isinstance(origin, dict) and origin.get("source") == "discord_desk":
                approved_discord += 1
    pending = list(PIPE_OUTBOX.glob("*.json")) if PIPE_OUTBOX.exists() else []
    sent = list(PIPE_SENT.glob("*.json")) if PIPE_SENT.exists() else []
    open_jobs = list(PIPE_OPEN.glob("*.json")) if PIPE_OPEN.exists() else []
    workers = []
    for worker_id, record in worker_bindings().items():
        workers.append(
            {
                "worker_id": worker_id,
                "agent_name": record.get("agent_name"),
                "brain_label": record.get("brain_label"),
                "serial": record.get("adb_serial"),
                "desk_affinity": record.get("desk_affinity") or [],
            }
        )
    return {
        "schema": PIPE_SCHEMA,
        "discord_on_phone": False,
        "approved_discord_assignments": approved_discord,
        "open_discord_jobs": len(open_jobs),
        "pending_discord_replies": len(pending),
        "sent_discord_replies": len(sent),
        "workers": workers,
        "authority": "Josh > Guardian > Engel/runtime",
        "generated_at": utc_stamp(),
    }


def render_discord_android_pipe_status(payload: str = "") -> str:
    del payload
    snap = pipe_colony_snapshot()
    lines = [
        "# Discord <-> Android Worker Pipe",
        "",
        "Phones never run Discord. Desk bots talk to Engel; Engel talks to phones.",
        f"Schema: `{snap['schema']}`",
        f"Approved Discord-origin assignments waiting: {snap['approved_discord_assignments']}",
        f"Open Discord pipe jobs (awaiting phone return): {snap['open_discord_jobs']}",
        f"Pending desk replies: {snap['pending_discord_replies']}",
        f"Sent desk replies: {snap['sent_discord_replies']}",
        "",
        "## Workers visible to desks",
    ]
    for worker in snap["workers"]:
        lines.append(
            f"- {worker['worker_id']}: {worker['agent_name']} / {worker['brain_label']} "
            f"(serial {worker['serial']}; desks {', '.join(worker['desk_affinity'] or [])})"
        )
    lines += [
        "",
        "Enqueue: engel_discord_android_worker_pipe.enqueue_from_desk(...)",
        "Collect: collect_pending_replies() → desk mouth posts reply_text",
        "Safety: review-only drafts, no trusted-memory write, no phone Discord APK.",
        "",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discord↔Android worker pipe (no Discord on phones).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--enqueue", action="store_true")
    mode.add_argument("--collect", action="store_true")
    parser.add_argument("--desk", default="main")
    parser.add_argument("--text", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--worker", default="")
    parser.add_argument("--task-type", default="")
    parser.add_argument("--channel-id", default="")
    parser.add_argument("--message-id", default="")
    parser.add_argument("--thread-id", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.status:
        print(render_discord_android_pipe_status())
        return 0
    if args.collect:
        pending = collect_pending_replies()
        print(json.dumps({"count": len(pending), "pending": pending}, indent=2))
        return 0
    result = enqueue_from_desk(
        desk_id=args.desk,
        text=args.text,
        title=args.title or None,
        worker_id=args.worker or None,
        task_type=args.task_type or None,
        channel_id=args.channel_id or None,
        message_id=args.message_id or None,
        thread_id=args.thread_id or None,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
