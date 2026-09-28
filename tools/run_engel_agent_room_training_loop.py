#!/usr/bin/env python3
"""Run a saved Engel Agent Meeting Room chat training loop.

The loop drives the same CT chat route used by Engel AI Main, mirrors every
turn into the Meeting Room event bus, and records a durable report. It does not
fine-tune model weights directly; it grows Engel's persistent supervised chat
memory and room history that the local LLM stack reads on later turns.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHAT_URL = "http://127.0.0.1:8765" if str(ROOT).replace("\\", "/") == "/opt/engel" else "http://127.0.0.1:24680"
DEFAULT_ROOM_URL = "http://127.0.0.1:8790"
DEFAULT_REPORT_ROOT = ROOT / "reports" / "agent_room_training"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def clip(value: Any, limit: int = 700) -> str:
    text = " ".join(str(value or "").replace("\r", " ").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 60.0) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=body, method=method.upper(), headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            parsed = json.loads(raw) if raw.strip() else {}
            if not isinstance(parsed, dict):
                parsed = {"ok": False, "value": parsed}
            parsed["_http_status"] = int(resp.status)
            return parsed
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except Exception:
            parsed = {"ok": False, "error": clip(raw, 2000)}
        if not isinstance(parsed, dict):
            parsed = {"ok": False, "value": parsed}
        parsed["_http_status"] = int(exc.code)
        return parsed
    except Exception as exc:
        return {"ok": False, "_http_status": 0, "error": str(exc)}


def get_json(url: str, timeout: float = 20.0) -> dict[str, Any]:
    return http_json("GET", url, None, timeout=timeout)


def post_json(url: str, payload: dict[str, Any], timeout: float = 90.0) -> dict[str, Any]:
    return http_json("POST", url, payload, timeout=timeout)


def event_tail(room_url: str, since: int = 0, limit: int = 100) -> dict[str, Any]:
    return get_json(f"{room_url.rstrip('/')}/room/events?since={since}&limit={limit}", timeout=20.0)


def last_event_id(events_payload: dict[str, Any], fallback: int = 0) -> int:
    try:
        return int(events_payload.get("last_event_id") or fallback)
    except Exception:
        return fallback


def prompt_plan() -> list[dict[str, str]]:
    prompts = [
        ("Hey Engel, what changed in the room since last check?", "room"),
        ("Can you make the agent room feel less empty?", "room"),
        ("Use ChatGPT for a friendly user reply about the server room being online.", "openai"),
        ("Have Alpha and Beta report connection status.", "phones"),
        ("Use Claude to review one risk in the meeting room setup.", "anthropic"),
        ("Create a small room task: verify saved memory.", "room"),
        ("What is one fix for repeating chat?", "chat"),
        ("Use Grok for a current-style take on fast assistants.", "xai"),
        ("Give me a normal short conversation reply, no checklist.", "chat"),
        ("Use Gemini to summarize the room state in plain language.", "gemini"),
        ("Which device should own UI work right now?", "room"),
        ("Ask the memory agent what it learned from this turn.", "memory"),
        ("Have the phone workers do a tiny status-only job.", "phones"),
        ("Give me one concrete next action for the server room.", "room"),
        ("Use Claude for a concise code-review style warning.", "anthropic"),
        ("Use ChatGPT for a warmer customer-support version.", "openai"),
        ("What should Sub-Engel handle if it checks in?", "sub-engel"),
        ("Do a quick sanity check on storage: SSD only.", "storage"),
        ("Use Grok to phrase the update like a live project note.", "xai"),
        ("Keep this natural: what are we testing now?", "chat"),
        ("Use Gemini for a careful long-context summary.", "gemini"),
        ("Give the agents a small collaborative task.", "room"),
        ("What did the room save from the last request?", "memory"),
        ("Check phones again without pretending if one is offline.", "phones"),
        ("Make a short plan to reduce chat lag.", "chat"),
        ("Use Claude to point out a missing test.", "anthropic"),
        ("Use ChatGPT to make the same answer friendlier.", "openai"),
        ("Use Grok to make it sharper and shorter.", "xai"),
        ("Tell me what the agent meeting room is doing right now.", "room"),
        ("Add one memory lesson from this training run.", "memory"),
        ("Give me a final normal user-facing update.", "chat"),
        ("Are the agents and devices still connected?", "room"),
    ]
    return [{"prompt": prompt, "tag": tag} for prompt, tag in prompts]


def extract_receipt(chat_payload: dict[str, Any]) -> dict[str, Any]:
    receipt = chat_payload.get("receipt")
    return receipt if isinstance(receipt, dict) else {}


def extract_provider(chat_payload: dict[str, Any]) -> str:
    receipt = extract_receipt(chat_payload)
    return str(
        receipt.get("selected_provider")
        or receipt.get("provider")
        or chat_payload.get("provider")
        or "unknown"
    )


def memory_appended(chat_payload: dict[str, Any]) -> bool:
    receipt = extract_receipt(chat_payload)
    return bool(receipt.get("persistent_chat_memory_appended") is True)


def room_used(chat_payload: dict[str, Any]) -> bool:
    receipt = extract_receipt(chat_payload)
    return bool(receipt.get("meeting_room_server_used") is True or receipt.get("agent_meeting_room_used") is True)


def phone_status_from_health(health: dict[str, Any]) -> dict[str, Any]:
    phone = health.get("phone_bridge")
    if not isinstance(phone, dict):
        return {"live_count": 0, "expected_count": 0, "workers": {}}
    workers = phone.get("workers") if isinstance(phone.get("workers"), dict) else {}
    return {
        "live_count": int(phone.get("live_count") or 0),
        "expected_count": int(phone.get("expected_count") or 0),
        "workers": {
            str(worker_id): {
                "live": bool(worker.get("live") is True) if isinstance(worker, dict) else False,
                "transport": str(worker.get("transport") or "") if isinstance(worker, dict) else "",
                "observed_ip": str(worker.get("observed_ip") or "") if isinstance(worker, dict) else "",
            }
            for worker_id, worker in workers.items()
        },
    }


def checkin_room(room_url: str, participant_id: str, name: str, role: str, status: str, capabilities: list[str]) -> dict[str, Any]:
    return post_json(
        f"{room_url.rstrip('/')}/room/checkin",
        {
            "participant_id": participant_id,
            "name": name,
            "kind": role,
            "role": role,
            "status": status,
            "capabilities": capabilities,
            "source": "engel-agent-room-training-loop",
        },
        timeout=20.0,
    )


def register_training_participants(room_url: str, health: dict[str, Any]) -> list[dict[str, Any]]:
    records = [
        checkin_room(
            room_url,
            "rog-controller-training-loop",
            "ROG Controller Training Loop",
            "controller",
            "online",
            ["chat", "verification", "room-viewer"],
        ),
        checkin_room(
            room_url,
            "engel-ai-main-ct246",
            "Engel AI Main CT 246",
            "server-orchestrator",
            "online",
            ["chat", "memory", "providers", "meeting-room"],
        ),
        checkin_room(
            room_url,
            "sub-engel-desktop",
            "Sub-Engel Desktop",
            "sub-engel-worker",
            "expected-or-online",
            ["desktop-worker", "code", "verification"],
        ),
    ]
    phone = phone_status_from_health(health)
    workers = phone.get("workers") if isinstance(phone.get("workers"), dict) else {}
    for worker_id, worker in workers.items():
        records.append(
            checkin_room(
                room_url,
                worker_id,
                worker_id.replace("_", " ").title(),
                "android-worker",
                "online" if worker.get("live") else "offline",
                ["android", "phone-worker", str(worker.get("transport") or "unknown")],
            )
        )
    return records


def run_loop(args: argparse.Namespace) -> dict[str, Any]:
    chat_url = args.chat_url.rstrip("/")
    room_url = args.room_url.rstrip("/")
    run_id = "engel_agent_room_training_" + stamp()
    out_dir = Path(args.out_root).expanduser().resolve() / run_id
    turns_path = out_dir / "turns.jsonl"
    checkpoint_path = out_dir / "checkpoint.json"
    receipt_path = out_dir / "receipt.json"

    started_mono = time.monotonic()
    started_utc = utc_now()
    duration_seconds = max(0, int(args.minutes * 60))
    deadline = started_mono + duration_seconds
    plan = prompt_plan()

    initial_health = get_json(f"{chat_url}/health", timeout=30.0)
    initial_room = get_json(f"{room_url}/virtual-environments/engel3d-office/state", timeout=30.0)
    initial_events = event_tail(room_url, since=0, limit=1)
    event_before = last_event_id(initial_events, 0)
    checkins = register_training_participants(room_url, initial_health)

    summary: dict[str, Any] = {
        "schema": "engel_agent_room_training_loop_receipt_v1",
        "ok": False,
        "run_id": run_id,
        "started_at_utc": started_utc,
        "updated_at_utc": started_utc,
        "chat_url": chat_url,
        "room_url": room_url,
        "report_dir": str(out_dir),
        "turns_path": str(turns_path),
        "requested_minutes": args.minutes,
        "requested_interval_seconds": args.interval_seconds,
        "event_id_before": event_before,
        "event_id_after": event_before,
        "turn_count": 0,
        "ok_turn_count": 0,
        "memory_appended_count": 0,
        "meeting_room_used_count": 0,
        "providers_seen": {},
        "tags_seen": {},
        "phone_live_samples": [],
        "checkins": checkins,
        "initial_health_ok": bool(initial_health.get("ok") is True),
        "initial_room_ok": bool(initial_room.get("ok") is True),
        "initial_agent_count": int(initial_room.get("agent_count") or 0),
        "active_runtime_storage": (
            initial_room.get("runtime_storage", {}).get("active_runtime_storage")
            if isinstance(initial_room.get("runtime_storage"), dict)
            else ""
        ),
        "vault_used_for_active_runtime": (
            initial_room.get("runtime_storage", {}).get("vault_used_for_active_runtime")
            if isinstance(initial_room.get("runtime_storage"), dict)
            else None
        ),
    }
    write_json(checkpoint_path, summary)

    turn_index = 0
    last_seen_event = event_before
    while True:
        if args.max_turns and turn_index >= args.max_turns:
            break
        if duration_seconds > 0 and time.monotonic() >= deadline and turn_index > 0:
            break
        if duration_seconds <= 0 and turn_index > 0 and not args.max_turns:
            break

        item = plan[turn_index % len(plan)]
        prompt = item["prompt"]
        tag = item["tag"]
        turn_started = utc_now()
        health = get_json(f"{chat_url}/health", timeout=25.0)
        phone_status = phone_status_from_health(health)
        phone_status["sample_at_utc"] = turn_started
        room_task = post_json(
            f"{room_url}/virtual-environments/engel3d-office/task",
            {
                "task": prompt,
                "source": "engel-agent-room-training-loop",
                "tag": tag,
            },
            timeout=20.0,
        )
        chat_payload = post_json(
            f"{chat_url}/chat",
            {
                "prompt": prompt,
                "source": "engel-agent-room-training-loop",
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
                "training_capture": True,
                "room_training_tag": tag,
            },
            timeout=args.chat_timeout_seconds,
        )
        assistant_reply = str(
            chat_payload.get("assistant_reply")
            or extract_receipt(chat_payload).get("assistant_reply")
            or extract_receipt(chat_payload).get("assistant_output_text")
            or ""
        )
        primary_room_used = room_used(chat_payload)
        backup_room_mirror: dict[str, Any] = {}
        if not primary_room_used and assistant_reply.strip():
            backup_room_mirror = post_json(
                f"{room_url}/room/chat",
                {
                    "prompt": prompt,
                    "assistant_reply": assistant_reply,
                    "source": "engel-agent-room-training-loop-backup-room-mirror",
                },
                timeout=20.0,
            )
        backup_room_used = bool(
            backup_room_mirror.get("ok") is True
            and backup_room_mirror.get("meeting_room_server_used") is True
        )
        events_after_turn = event_tail(room_url, since=last_seen_event, limit=100)
        last_seen_event = last_event_id(events_after_turn, last_seen_event)
        provider = extract_provider(chat_payload)
        turn_record = {
            "schema": "engel_agent_room_training_turn_v1",
            "run_id": run_id,
            "turn": turn_index + 1,
            "tag": tag,
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "started_at_utc": turn_started,
            "completed_at_utc": utc_now(),
            "chat_ok": bool(chat_payload.get("ok") is True),
            "chat_http_status": int(chat_payload.get("_http_status") or 0),
            "assistant_reply_preview": clip(assistant_reply, 900),
            "provider": provider,
            "runtime_provider": str(chat_payload.get("runtime_provider") or extract_receipt(chat_payload).get("runtime_provider") or ""),
            "persistent_chat_memory_appended": memory_appended(chat_payload),
            "meeting_room_server_used": bool(primary_room_used or backup_room_used),
            "primary_meeting_room_server_used": primary_room_used,
            "backup_room_mirror_used": backup_room_used,
            "backup_room_mirror_http_status": int(backup_room_mirror.get("_http_status") or 0) if backup_room_mirror else 0,
            "room_task_ok": bool(room_task.get("ok") is True),
            "room_task_event_id": (
                room_task.get("event", {}).get("id") if isinstance(room_task.get("event"), dict) else None
            ),
            "events_after_turn_count": int(events_after_turn.get("event_count") or 0),
            "last_event_id": last_seen_event,
            "phone_status": phone_status,
            "chat_status": str(chat_payload.get("status") or ""),
            "error": clip(chat_payload.get("error") or extract_receipt(chat_payload).get("error"), 600),
        }
        append_jsonl(turns_path, turn_record)

        summary["turn_count"] = int(summary["turn_count"]) + 1
        if turn_record["chat_ok"]:
            summary["ok_turn_count"] = int(summary["ok_turn_count"]) + 1
        if turn_record["persistent_chat_memory_appended"]:
            summary["memory_appended_count"] = int(summary["memory_appended_count"]) + 1
        if turn_record["meeting_room_server_used"]:
            summary["meeting_room_used_count"] = int(summary["meeting_room_used_count"]) + 1
        providers_seen = summary["providers_seen"]
        if isinstance(providers_seen, dict):
            providers_seen[provider] = int(providers_seen.get(provider) or 0) + 1
        tags_seen = summary["tags_seen"]
        if isinstance(tags_seen, dict):
            tags_seen[tag] = int(tags_seen.get(tag) or 0) + 1
        phone_samples = summary["phone_live_samples"]
        if isinstance(phone_samples, list):
            phone_samples.append(phone_status)
            del phone_samples[:-20]
        summary["event_id_after"] = last_seen_event
        summary["updated_at_utc"] = utc_now()
        summary["elapsed_seconds"] = round(time.monotonic() - started_mono, 1)
        summary["last_prompt"] = prompt
        summary["last_reply_preview"] = turn_record["assistant_reply_preview"]
        write_json(checkpoint_path, summary)

        turn_index += 1
        if args.max_turns and turn_index >= args.max_turns:
            break
        if duration_seconds > 0 and time.monotonic() >= deadline:
            break
        if duration_seconds <= 0:
            break
        remaining = max(0.0, deadline - time.monotonic())
        sleep_for = min(float(args.interval_seconds), remaining)
        if sleep_for > 0:
            time.sleep(sleep_for)

    final_health = get_json(f"{chat_url}/health", timeout=30.0)
    final_room = get_json(f"{room_url}/virtual-environments/engel3d-office/state", timeout=30.0)
    final_events = event_tail(room_url, since=0, limit=1)
    event_after = last_event_id(final_events, int(summary.get("event_id_after") or 0))
    elapsed = round(time.monotonic() - started_mono, 1)
    one_hour_required = args.minutes >= 60 and not args.max_turns
    summary.update(
        {
            "ok": bool(
                int(summary.get("turn_count") or 0) > 0
                and int(summary.get("memory_appended_count") or 0) > 0
                and int(summary.get("meeting_room_used_count") or 0) > 0
                and event_after > event_before
            ),
            "completed_at_utc": utc_now(),
            "updated_at_utc": utc_now(),
            "elapsed_seconds": elapsed,
            "one_hour_required": one_hour_required,
            "one_hour_requirement_met": (elapsed >= 3600.0) if one_hour_required else True,
            "event_id_after": event_after,
            "room_event_growth": max(0, event_after - event_before),
            "final_health_ok": bool(final_health.get("ok") is True),
            "final_room_ok": bool(final_room.get("ok") is True),
            "final_agent_count": int(final_room.get("agent_count") or 0),
            "final_status_counts": final_room.get("status_counts") if isinstance(final_room.get("status_counts"), dict) else {},
            "final_phone_status": phone_status_from_health(final_health),
            "checkpoint_path": str(checkpoint_path),
            "receipt_path": str(receipt_path),
        }
    )
    write_json(checkpoint_path, summary)
    write_json(receipt_path, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--interval-seconds", type=float, default=90.0)
    parser.add_argument("--max-turns", type=int, default=0)
    parser.add_argument("--chat-url", default=DEFAULT_CHAT_URL)
    parser.add_argument("--room-url", default=DEFAULT_ROOM_URL)
    parser.add_argument("--out-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--max-tokens", type=int, default=360)
    parser.add_argument("--temperature", type=float, default=0.45)
    parser.add_argument("--chat-timeout-seconds", type=float, default=120.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_loop(args)
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    if args.minutes >= 60 and not args.max_turns and result.get("one_hour_requirement_met") is not True:
        return 2
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
