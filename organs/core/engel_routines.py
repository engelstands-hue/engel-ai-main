"""Engel Routines V1 — worst landscape gap (Grok Bot Routines parity).

Standing responsibilities that can become DUE. Never auto-execute.
Due checks run only when Josh/an operator asks a route. Staging writes an
untrusted Meeting Room order draft for approval — no queue mutation,
no background workers, no Level 2 autonomy.

Contract: memory/ENGEL_ROUTINES_CONTRACT_V1.md
Routes: engel.routines.*
Verifier: tools/verify_engel_routines.py
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engel_project_paths import resolve_engel_app_root
from engel_prompt_injection_guard import check_prompt_injection

ROOT = resolve_engel_app_root(__file__)
STATE_DIR = ROOT / "runtime" / "routines"
ROUTINE_DIR = STATE_DIR / "defs"
STAGED_DIR = STATE_DIR / "staged"
REGISTRY_PATH = STATE_DIR / "registry.json"
RECEIPT_DIR = ROOT / "reports" / "routines"
CONTRACT_PATH = ROOT / "memory" / "ENGEL_ROUTINES_CONTRACT_V1.md"

SCHEMA_ROUTINE = "engel_routine_v1"
SCHEMA_REGISTRY = "engel_routine_registry_v1"
SCHEMA_STAGED = "engel_routine_staged_v1"

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_CREATE_PREFIXES = (
    "create engel routine ",
    "new engel routine ",
    "add engel routine ",
    "create routine ",
)
_PAUSE_PREFIXES = ("pause engel routine ", "pause routine ")
_STAGE_PREFIXES = (
    "stage engel routine ",
    "stage due routine ",
    "stage routine ",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.casefold()).strip("-")[:48] or "routine"


def _ensure_dirs() -> None:
    ROUTINE_DIR.mkdir(parents=True, exist_ok=True)
    STAGED_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _load_registry() -> dict[str, Any]:
    _ensure_dirs()
    if not REGISTRY_PATH.is_file():
        return {"schema": SCHEMA_REGISTRY, "routines": [], "updated_at_utc": _now()}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _save_registry(registry: dict[str, Any]) -> None:
    registry["schema"] = SCHEMA_REGISTRY
    registry["updated_at_utc"] = _now()
    _write_json(REGISTRY_PATH, registry)


def load_routine(slug: str) -> dict[str, Any] | None:
    path = ROUTINE_DIR / f"{slug}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_routines() -> list[dict[str, Any]]:
    registry = _load_registry()
    rows: list[dict[str, Any]] = []
    for slug in registry.get("routines") or []:
        row = load_routine(str(slug))
        if row:
            rows.append(row)
    return rows


def _parse_schedule(schedule: str) -> dict[str, Any] | None:
    text = schedule.strip()
    daily = re.fullmatch(r"daily@(\d{2}):(\d{2})", text, re.I)
    if daily:
        hour, minute = int(daily.group(1)), int(daily.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return {"kind": "daily", "hour_utc": hour, "minute_utc": minute, "raw": text}
    weekday = re.fullmatch(
        r"(mon|tue|wed|thu|fri|sat|sun)@(\d{2}):(\d{2})", text, re.I
    )
    if weekday:
        hour, minute = int(weekday.group(2)), int(weekday.group(3))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return {
                "kind": "weekday",
                "weekday": weekday.group(1).casefold(),
                "hour_utc": hour,
                "minute_utc": minute,
                "raw": text,
            }
    interval = re.fullmatch(r"interval_minutes:(\d{1,4})", text, re.I)
    if interval:
        minutes = int(interval.group(1))
        if 5 <= minutes <= 1440:
            return {"kind": "interval_minutes", "minutes": minutes, "raw": text}
    return None


def _is_due(routine: dict[str, Any], now: datetime | None = None) -> bool:
    if routine.get("paused"):
        return False
    schedule = routine.get("schedule") or {}
    kind = schedule.get("kind")
    now = now or datetime.now(timezone.utc)
    last_staged = routine.get("last_staged_at_utc") or ""
    if kind == "daily":
        target = now.replace(
            hour=int(schedule["hour_utc"]),
            minute=int(schedule["minute_utc"]),
            second=0,
            microsecond=0,
        )
        if now < target:
            return False
        day_key = now.strftime("%Y-%m-%d")
        return not str(last_staged).startswith(day_key)
    if kind == "weekday":
        names = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        if names[now.weekday()] != schedule.get("weekday"):
            return False
        target = now.replace(
            hour=int(schedule["hour_utc"]),
            minute=int(schedule["minute_utc"]),
            second=0,
            microsecond=0,
        )
        if now < target:
            return False
        day_key = now.strftime("%Y-%m-%d")
        return not str(last_staged).startswith(day_key)
    if kind == "interval_minutes":
        minutes = int(schedule["minutes"])
        if not last_staged:
            return True
        try:
            previous = datetime.strptime(last_staged, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return True
        return (now - previous).total_seconds() >= minutes * 60
    return False


def due_routines(now: datetime | None = None) -> list[dict[str, Any]]:
    return [row for row in list_routines() if _is_due(row, now=now)]


def create_routine(
    title: str,
    schedule_raw: str,
    prompt: str,
    *,
    bot_slug: str = "grok",
) -> dict[str, Any]:
    verdict = check_prompt_injection(f"{title}\n{prompt}")
    status = str(getattr(verdict, "verdict", "allow") or "allow")
    if status in {"block", "review"}:
        raise ValueError(f"Guardian blocked routine create ({status})")
    parsed = _parse_schedule(schedule_raw)
    if parsed is None:
        raise ValueError(
            "Schedule must be daily@HH:MM, weekday@HH:MM (mon..sun), "
            "or interval_minutes:N (5-1440), all UTC."
        )
    if not title.strip() or not prompt.strip():
        raise ValueError("title and prompt are required")
    slug = _slugify(title)
    if load_routine(slug) is not None:
        raise ValueError(f"routine already exists: {slug}")
    _ensure_dirs()
    row = {
        "schema": SCHEMA_ROUTINE,
        "slug": slug,
        "title": title.strip(),
        "bot_slug": _slugify(bot_slug) or "grok",
        "schedule": parsed,
        "prompt": prompt.strip(),
        "paused": False,
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "last_staged_at_utc": "",
        "stage_count": 0,
        "safety": {
            "auto_execute": False,
            "background_worker": False,
            "action_on_due": "stage_meeting_room_order_draft_only",
        },
    }
    _write_json(ROUTINE_DIR / f"{slug}.json", row)
    registry = _load_registry()
    if slug not in registry["routines"]:
        registry["routines"].append(slug)
        _save_registry(registry)
    return row


def pause_routine(slug: str, paused: bool = True) -> dict[str, Any]:
    row = load_routine(slug)
    if row is None:
        raise ValueError(f"unknown routine: {slug}")
    row["paused"] = bool(paused)
    row["updated_at_utc"] = _now()
    _write_json(ROUTINE_DIR / f"{slug}.json", row)
    return row


def stage_routine(slug: str) -> dict[str, Any]:
    """Write an untrusted Meeting Room order draft. Does not Send Job."""
    row = load_routine(slug)
    if row is None:
        raise ValueError(f"unknown routine: {slug}")
    if row.get("paused"):
        raise ValueError(f"routine is paused: {slug}")
    _ensure_dirs()
    stamped = _now()
    order_text = (
        f"[Engel Routine staged — NOT auto-run]\n"
        f"Routine: {row['title']} ({slug})\n"
        f"Bot: {row.get('bot_slug')}\n"
        f"Schedule: {(row.get('schedule') or {}).get('raw')}\n"
        f"Prompt:\n{row.get('prompt')}\n"
        f"\nSafety: stage only. Josh must approve before Meeting Room Send Job / "
        f"Android packet / any Bucket 3 action."
    )
    digest = hashlib.sha256(order_text.encode("utf-8")).hexdigest()[:16]
    staged = {
        "schema": SCHEMA_STAGED,
        "routine_slug": slug,
        "staged_at_utc": stamped,
        "digest16": digest,
        "order_text": order_text,
        "auto_execute": False,
        "meeting_room_send_job": False,
        "next_step": (
            "Review draft. If approved, hand to Meeting Room intake explicitly. "
            "Routines never call Send Job themselves."
        ),
    }
    path = STAGED_DIR / f"{slug}_{stamped.replace(':', '')}_{digest}.json"
    _write_json(path, staged)
    row["last_staged_at_utc"] = stamped
    row["stage_count"] = int(row.get("stage_count") or 0) + 1
    row["updated_at_utc"] = stamped
    _write_json(ROUTINE_DIR / f"{slug}.json", row)
    receipt = RECEIPT_DIR / f"ENGEL_ROUTINE_STAGE_{slug}_{digest}.json"
    _write_json(receipt, {"routine": row, "staged": staged, "path": str(path)})
    return {"routine": row, "staged": staged, "path": str(path), "receipt": str(receipt)}


def _strip_prefixes(text: str, prefixes: tuple[str, ...]) -> str:
    raw = (text or "").strip()
    folded = raw.casefold()
    for prefix in prefixes:
        if folded.startswith(prefix):
            return raw[len(prefix) :].strip()
    return raw


def render_routines_docs(payload: str = "") -> str:
    del payload
    return "\n".join(
        [
            "Engel Routines V1",
            "",
            "Worst landscape gap vs Grok Bot: standing responsibilities.",
            "Engel keeps Josh gates — routines become DUE and can STAGE a draft,",
            "but they never auto-run, never start a background worker, and never",
            "Send Job / mutate Android queues.",
            "",
            "Schedules (UTC): daily@HH:MM | mon@HH:MM | interval_minutes:N",
            "Phrases:",
            "- engel routines status",
            "- list engel routines",
            "- create engel routine <title> | <schedule> | <prompt>",
            "- engel routines due",
            "- stage engel routine <slug>",
            "- pause engel routine <slug>",
            "",
            f"Contract: {CONTRACT_PATH.relative_to(ROOT).as_posix()}",
            f"State: {STATE_DIR.relative_to(ROOT).as_posix()}",
        ]
    )


def render_routines_status(payload: str = "") -> str:
    del payload
    rows = list_routines()
    due = due_routines()
    lines = [
        "Engel Routines status",
        "",
        f"defined: {len(rows)}",
        f"due_now: {len(due)}",
        f"auto_execute: false",
        f"background_worker: false",
        "",
    ]
    if not rows:
        lines.append("No routines yet. Create one with: create engel routine ...")
        return "\n".join(lines)
    for row in rows:
        flag = "DUE" if row in due or _is_due(row) else ("PAUSED" if row.get("paused") else "idle")
        lines.append(
            f"- [{flag}] {row.get('slug')}: {row.get('title')} "
            f"({(row.get('schedule') or {}).get('raw')})"
        )
    lines.extend(
        [
            "",
            "When due: `stage engel routine <slug>` writes a Meeting Room draft only.",
        ]
    )
    return "\n".join(lines)


def render_routines_list(payload: str = "") -> str:
    del payload
    rows = list_routines()
    if not rows:
        return "No Engel routines defined."
    lines = ["Engel Routines", ""]
    for row in rows:
        lines.append(
            f"- {row.get('slug')} | {row.get('title')} | "
            f"{(row.get('schedule') or {}).get('raw')} | "
            f"paused={bool(row.get('paused'))} | stages={row.get('stage_count', 0)}"
        )
    return "\n".join(lines)


def render_routines_create(payload: str = "") -> str:
    rest = _strip_prefixes(payload, _CREATE_PREFIXES)
    if not rest or rest.casefold() in {"create engel routine", "create routine"}:
        return (
            "Usage: create engel routine <title> | <schedule> | <prompt>\n"
            "Example: create engel routine Morning briefing | daily@15:00 | "
            "Stage a status ask for chat tunnel health and Android worker presence."
        )
    parts = [part.strip() for part in rest.split("|")]
    if len(parts) < 3:
        return "Need title | schedule | prompt"
    title, schedule_raw, prompt = parts[0], parts[1], "|".join(parts[2:]).strip()
    try:
        row = create_routine(title, schedule_raw, prompt)
    except ValueError as exc:
        return f"Routine create blocked: {exc}"
    return (
        f"Routine created: {row['slug']}\n"
        f"Schedule: {row['schedule']['raw']} (UTC)\n"
        f"Auto-execute: false — use `engel routines due` then `stage engel routine {row['slug']}`."
    )


def render_routines_due(payload: str = "") -> str:
    del payload
    due = due_routines()
    if not due:
        return "No Engel routines are due right now. (Polling only — no background timer.)"
    lines = ["Engel Routines due now", ""]
    for row in due:
        lines.append(f"- {row.get('slug')}: {row.get('title')}")
        lines.append(f"  stage with: stage engel routine {row.get('slug')}")
    return "\n".join(lines)


def render_routines_stage(payload: str = "") -> str:
    rest = _strip_prefixes(payload, _STAGE_PREFIXES)
    slug = _slugify(rest)
    if not slug or slug in {"stage", "engel", "routine"}:
        return "Usage: stage engel routine <slug>"
    try:
        result = stage_routine(slug)
    except ValueError as exc:
        return f"Stage blocked: {exc}"
    staged = result["staged"]
    return "\n".join(
        [
            f"Staged routine draft: {slug}",
            f"digest16: {staged['digest16']}",
            f"path: {result['path']}",
            f"receipt: {result['receipt']}",
            "",
            "This did NOT Send Job, start a worker, or call a provider.",
            "Next: Josh reviews the draft, then explicit Meeting Room intake if approved.",
        ]
    )


def render_routines_pause(payload: str = "") -> str:
    rest = _strip_prefixes(payload, _PAUSE_PREFIXES)
    slug = _slugify(rest)
    if not slug:
        return "Usage: pause engel routine <slug>"
    try:
        row = pause_routine(slug, paused=True)
    except ValueError as exc:
        return f"Pause blocked: {exc}"
    return f"Paused routine: {row['slug']}"
