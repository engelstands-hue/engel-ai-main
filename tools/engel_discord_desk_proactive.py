#!/usr/bin/env python3
"""Proactive desk standing-watch posts for Engel Discord forum mouths.

Named desks only (research/product/community/support/sales/ops). Off unless
ENGEL_DISCORD_PROACTIVE=1. Posts to primary CHANNEL_ID only (forum-aware).

Standing-watch is charter-driven and (when a thought_fn is supplied) SLM-shaped
per desk — not an identical hourly copy-paste. Owner stop/quiet silences until
Josh says resume (permanent until clear_owner_silence).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROACTIVE_NAMED_DESKS = frozenset(
    {
        "research",
        "product",
        "community",
        "support",
        "sales",
        "ops",
        "architect",
        "memory",
        "builder",
        "proof",
        "training",
    }
)
# Floor keeps misconfig from blasting; default cadence is slower (6h).
PROACTIVE_MIN_INTERVAL_SECONDS = 3600.0
PROACTIVE_DEFAULT_INTERVAL_SECONDS = 21600.0
# Owner silence with until_unix=0 means permanent until resume.
OWNER_SILENCE_HOLD_SECONDS = float(
    os.environ.get("ENGEL_DISCORD_PROACTIVE_OWNER_SILENCE_SECONDS", "0") or "0"
)
DESK_STAGGER_SECONDS = {
    "research": 0,
    "product": 420,
    "community": 840,
    "support": 1260,
    "sales": 1680,
    "ops": 2100,
    "architect": 120,
    "memory": 240,
    "builder": 360,
    "proof": 480,
    "training": 600,
}
DUTY_DESKS = frozenset({"architect", "memory", "builder", "proof", "training", "ops"})
# Working sandbox lives on the phone. The server folder is a pointer.
PHONE_SANDBOX_ROOT = "/storage/emulated/0/Download/EngelRemoteWorker/desks"
DESK_PHONE_WORKER = {
    "research": "android_worker_alpha",
    "product": "android_worker_alpha",
    "architect": "android_worker_alpha",
    "training": "android_worker_alpha",
    "support": "android_worker_beta",
    "ops": "android_worker_beta",
    "builder": "android_worker_beta",
    "community": "android_worker_gamma",
    "sales": "android_worker_gamma",
    "memory": "android_worker_gamma",
    "proof": "android_worker_gamma",
}
COLLAB_KINDS = ("idea", "skill", "command", "loop")
COLLAB_INVITEES = {
    "research": ("product", "ops"),
    "product": ("research", "community"),
    "community": ("sales", "support"),
    "support": ("ops", "product"),
    "sales": ("community", "product"),
    "ops": ("research", "support"),
}
CANDIDATE_ROOT = Path(__file__).resolve().parents[1] / "reports" / "desk_collab_candidates"
# Josh's house #general — collab posts go here so every mouth can hear them.
COLLAB_HOUSE_CHANNEL_ID = str(
    os.environ.get("ENGEL_DISCORD_COLLAB_CHANNEL_ID") or "1148755186752430163"
).strip()
_PROACTIVE_TASK: asyncio.Task | None = None
_DAILY_BOARD_TASK: asyncio.Task | None = None


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def proactive_enabled(desk_name: str) -> bool:
    return (
        str(os.environ.get("ENGEL_DISCORD_PROACTIVE", "0") or "0").strip().lower()
        in {"1", "true", "yes", "on"}
        and str(desk_name or "").strip().lower() in PROACTIVE_NAMED_DESKS
    )


def proactive_interval() -> float:
    try:
        raw = float(
            os.environ.get(
                "ENGEL_DISCORD_PROACTIVE_INTERVAL_SECONDS",
                str(int(PROACTIVE_DEFAULT_INTERVAL_SECONDS)),
            )
            or PROACTIVE_DEFAULT_INTERVAL_SECONDS
        )
    except (TypeError, ValueError):
        raw = PROACTIVE_DEFAULT_INTERVAL_SECONDS
    return max(PROACTIVE_MIN_INTERVAL_SECONDS, raw)


def proactive_state_path(run_dir: Path) -> Path:
    return Path(run_dir) / "proactive_state.json"


def load_state(run_dir: Path) -> dict[str, Any]:
    path = proactive_state_path(run_dir)
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        logging.exception("proactive state load failed")
    return {}


def save_state(run_dir: Path, payload: dict[str, Any]) -> None:
    path = proactive_state_path(run_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        logging.exception("proactive state save failed")


def owner_silence_active(run_dir: Path) -> tuple[bool, str]:
    """True when Josh paused proactive standing-watch for this mouth.

    until_unix=0 with owner_silenced=True means permanent until resume.
    """
    state = load_state(run_dir)
    if not bool(state.get("owner_silenced")):
        return False, "not silenced"
    until = float(state.get("owner_silence_until_unix") or 0.0)
    now = time.time()
    if until > 0.0 and now >= until:
        cleared = dict(state)
        cleared["owner_silenced"] = False
        cleared["owner_silence_cleared_at_utc"] = _iso_now()
        cleared["owner_silence_clear_reason"] = "expired"
        save_state(run_dir, cleared)
        return False, "silence expired"
    reason = str(state.get("owner_silence_reason") or "owner_silence").strip() or "owner_silence"
    return True, reason


def note_owner_silence(
    run_dir: Path,
    *,
    reason: str = "owner_stop",
    hold_seconds: float | None = None,
    channel_id: str = "",
) -> dict[str, Any]:
    """Persist Josh stop/quiet so the proactive loop skips posts until resume."""
    hold_raw = OWNER_SILENCE_HOLD_SECONDS if hold_seconds is None else float(hold_seconds)
    # 0 = permanent until clear_owner_silence (Josh resume).
    until = 0.0 if hold_raw <= 0 else time.time() + max(60.0, hold_raw)
    state = load_state(run_dir)
    state.update(
        {
            "schema": str(state.get("schema") or "engel_discord_proactive_state_v1"),
            "owner_silenced": True,
            "owner_silence_reason": str(reason or "owner_stop")[:120],
            "owner_silence_at_utc": _iso_now(),
            "owner_silence_until_unix": until,
            "owner_silence_channel_id": str(channel_id or "").strip(),
        }
    )
    save_state(run_dir, state)
    logging.info(
        "Discord proactive owner silence armed reason=%s until=%s",
        reason,
        "permanent" if until <= 0 else int(until),
    )
    return state


def clear_owner_silence(run_dir: Path, *, reason: str = "owner_resume") -> dict[str, Any]:
    state = load_state(run_dir)
    if not state:
        return {}
    state["owner_silenced"] = False
    state["owner_silence_until_unix"] = 0.0
    state["owner_silence_cleared_at_utc"] = _iso_now()
    state["owner_silence_clear_reason"] = str(reason or "owner_resume")[:120]
    save_state(run_dir, state)
    logging.info("Discord proactive owner silence cleared reason=%s", reason)
    return state


def desk_slm_model(desk_name: str = "") -> str:
    """Distinct per-desk model lane from env (set on each mouth unit)."""
    env = str(os.environ.get("ENGEL_NVIDIA_CHAT_MODEL") or "").strip()
    if env:
        return env
    defaults = {
        "research": "nvidia/nemotron-3-super-120b-a12b",
        "product": "nvidia/nemotron-3-ultra-550b-a55b",
        "community": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "support": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "sales": "nvidia/nemotron-3-nano-30b-a3b",
        "ops": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "main": "nvidia/nemotron-3-super-120b-a12b",
    }
    key = str(desk_name or "").strip().lower() or "main"
    return defaults.get(key, defaults["main"])


def _content_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]


def focus_for_desk(desk: str, charter: dict[str, Any]) -> str:
    """Rotate focus so standing-watch is not the same sentence every cycle."""
    wants = charter.get("wants") if isinstance(charter.get("wants"), list) else []
    works = charter.get("works_on") if isinstance(charter.get("works_on"), list) else []
    items = [str(item).strip() for item in wants if str(item).strip()]
    if not items:
        items = [str(item).strip() for item in works if str(item).strip()]
    if not items:
        duty = str(charter.get("duty") or "").strip()
        return duty or f"{desk} lane"
    # Day-of-year + hour buckets + desk name → stable but rotating focus.
    now = datetime.now(timezone.utc)
    bucket = (now.timetuple().tm_yday * 24 + now.hour) + sum(ord(c) for c in desk)
    return items[bucket % len(items)]


def collab_kind_for_desk(desk: str) -> str:
    name = str(desk or "desk").strip().lower() or "desk"
    now = datetime.now(timezone.utc)
    idx = (now.timetuple().tm_yday + now.hour + sum(ord(c) for c in name)) % len(COLLAB_KINDS)
    return COLLAB_KINDS[idx]


def collab_invite_names(desk: str) -> list[str]:
    names = []
    for peer in COLLAB_INVITEES.get(str(desk or "").strip().lower(), ()):
        names.append(f"Engel {peer.title()}")
    return names


def collab_invite_line(desk: str) -> str:
    names = collab_invite_names(desk)
    if not names:
        return "Engel AI Main, collab if this helps the house."
    return ", ".join(names) + " — collab if this is your lane. Engel AI Main welcome too."


def desk_is_invited_to_collab(text: str, desk_name: str) -> bool:
    low = " ".join(str(text or "").casefold().split())
    desk = str(desk_name or "").strip().lower()
    if not low or not desk:
        return False
    needles = (
        f"engel {desk}",
        f"{desk} desk",
        f"engel {desk},",
    )
    return any(needle in low for needle in needles)


def is_desk_collab_idea(text: str) -> bool:
    low = " ".join(str(text or "").casefold().split())
    return "collab" in low and any(
        kind in low for kind in ("idea", "skill", "command", "loop")
    )


def save_collab_candidate(
    *,
    desk: str,
    kind: str,
    title: str,
    body: str,
    focus: str,
    invite: list[str],
) -> Path:
    folder = collab_candidate_dir(desk)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = folder / f"DESK_COLLAB_{desk}_{kind}_{stamp}.json"
    payload = {
        "schema": "engel_desk_collab_candidate_v1",
        "desk": desk,
        "kind": kind,
        "title": title,
        "body": body[:4000],
        "focus": focus,
        "invite": invite,
        "signoff_bucket": 2,
        "applied": False,
        "auto_apply_allowed": False,
        "created_at_utc": _iso_now(),
        "authority": "Josh > Guardian > Engel/runtime",
        "note": "Candidate only. Skills/commands/loops do not change runtime until Josh signs off.",
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _engel_root() -> Path:
    """This mouth's sandbox. ENGEL_ROOT wins so a desk does not read Main's tree."""
    env = str(os.environ.get("ENGEL_ROOT") or "").strip()
    if env:
        root = Path(env)
        if root.is_dir():
            return root
    here = Path(__file__).resolve().parents[1]
    if (here / "tools").is_dir():
        return here
    opt = Path("/opt/engel")
    if opt.is_dir():
        return opt
    return here


def _latest_receipt(root: Path) -> Path | None:
    folder = root / "reports" / "codex_bridge"
    if not folder.is_dir():
        return None
    files = [path for path in folder.glob("*.md") if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _architect_duty(root: Path) -> str:
    state = root / "memory" / "architect_state"
    if not state.is_dir():
        return (
            "Architect checked the plan folder. It is not on disk. "
            "Nothing is at Joshua's approval gate. I did not approve anything."
        )
    plans = [path for path in state.rglob("*") if path.is_file() and path.suffix in {".json", ".md"}]
    if not plans:
        return (
            "Architect checked the plan folder. No plan or spec file is there. "
            "Nothing is at Joshua's approval gate. I did not approve anything."
        )
    newest = max(plans, key=lambda path: path.stat().st_mtime)
    rel = newest.relative_to(root).as_posix()
    return (
        f"Architect read {rel}. It stays a proposal until Joshua passes the founder gate. "
        "I did not approve it."
    )


def _memory_duty(root: Path) -> str:
    receipt = _latest_receipt(root)
    if receipt is None:
        return (
            "Memory checked the receipt shelf. No receipt file is there. "
            "I did not promote anything into trusted memory."
        )
    rel = receipt.relative_to(root).as_posix()
    return (
        f"Memory recorded the latest receipt: {rel}. "
        "It stays a receipt. I did not promote it into trusted memory."
    )


def _builder_duty(root: Path) -> str:
    receipt = _latest_receipt(root)
    if receipt is None:
        return "Builder checked for an open draft. No receipt names files. I did not apply a patch."
    rel = receipt.relative_to(root).as_posix()
    return (
        f"Builder read {rel} and left the files named there unapplied. "
        "I did not apply a patch from Discord."
    )


def _proof_duty(root: Path) -> str:
    script = root / "tools" / "verify_engel_discord_desk_manager.py"
    if not script.is_file():
        return (
            "Proof looked for tools/verify_engel_discord_desk_manager.py. "
            "The checker is missing. That is not a pass."
        )
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "Proof ran verify_engel_discord_desk_manager.py. It timed out. That is not a pass."
    except OSError as exc:
        return f"Proof could not start the checker ({type(exc).__name__}). That is not a pass."
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    detail = lines[-1] if lines else "no output"
    status = "PASS" if proc.returncode == 0 else "FAIL"
    return f"Proof ran verify_engel_discord_desk_manager.py: {status}. {detail}"


def _training_duty(root: Path) -> str:
    index_path = root / "memory" / "training" / "engel_main" / "templates" / "curricula_index.json"
    if not index_path.is_file():
        return "Training checked the curriculum index. It is not on this server. No run was started."
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "Training found the curriculum index but could not read it. No run was started."
    rows = payload.get("curricula") if isinstance(payload.get("curricula"), list) else []
    parts: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("id") or "curriculum")
        status = str(row.get("novelty_status") or "unknown")
        hours = row.get("novel_hours_available")
        parts.append(f"{name} {status} {hours}h")
    cycle_path = root / "reports" / "real_training" / "ENGEL_REAL_TRAINING_CYCLE_LATEST.json"
    cycle = "No cycle receipt is on disk."
    if cycle_path.is_file():
        try:
            cycle_payload = json.loads(cycle_path.read_text(encoding="utf-8"))
            cycle = f"Last model cycle status is {cycle_payload.get('status') or 'unknown'}."
        except (OSError, json.JSONDecodeError):
            cycle = "The last cycle receipt could not be read."
    joined = "; ".join(parts) if parts else "no curricula listed"
    return f"Training read the live index. {joined}. {cycle} No run was started."


def _ops_duty() -> str:
    units = (
        "engel-discord-bridge.service",
        "engel-discord-desk-research.service",
        "engel-discord-desk-product.service",
        "engel-discord-desk-community.service",
        "engel-discord-desk-support.service",
        "engel-discord-desk-sales.service",
        "engel-discord-desk-ops.service",
        "engel-discord-desk-architect.service",
        "engel-discord-desk-memory.service",
        "engel-discord-desk-builder.service",
        "engel-discord-desk-proof.service",
        "engel-discord-desk-training.service",
        "engel-main-chat.service",
    )
    if not Path("/bin/systemctl").is_file() and not Path("/usr/bin/systemctl").is_file():
        return "Ops is not on the server host, so no service check was run."
    down: list[str] = []
    for unit in units:
        try:
            proc = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            down.append(f"{unit} unchecked")
            continue
        state = (proc.stdout or "").strip() or "unknown"
        if state != "active":
            down.append(f"{unit} {state}")
    if not down:
        return f"Ops checked {len(units)} services. All are active."
    return "Ops checked services. Not active: " + "; ".join(down) + "."


def _is_main_engel_root(path: Path) -> bool:
    """True for Engel AI Main's tree, including a Windows resolve of /opt/engel."""
    try:
        resolved = path.resolve()
    except OSError:
        return True
    if resolved.name == "engel" and resolved.parent.name == "opt":
        return True
    try:
        if resolved == Path("/opt/engel").resolve():
            return True
    except OSError:
        return True
    return False


def phone_sandbox_for(desk: str) -> dict[str, str]:
    """Where this desk works. Empty when the desk has no phone."""
    name = str(desk or "").strip().lower()
    worker = DESK_PHONE_WORKER.get(name, "")
    if not worker:
        return {}
    return {
        "desk": name,
        "worker_id": worker,
        "phone_sandbox": f"{PHONE_SANDBOX_ROOT}/{name}",
        "discord_on_phone": "false",
    }


def desk_sandbox_root() -> Path | None:
    """Isolated desk tree only. Never Engel AI Main's /opt/engel."""
    env = str(os.environ.get("ENGEL_ROOT") or "").strip()
    if not env:
        return None
    root = Path(env)
    if not root.is_dir() or root.parent.name != "desks" or _is_main_engel_root(root):
        return None
    return root


def _sandbox_base(desk: str, root: Path | None = None) -> Path | None:
    name = str(desk or "").strip().lower()
    if not name or name == "main":
        return None
    if root is not None:
        base = Path(root)
        if _is_main_engel_root(base):
            return None
        return base
    return desk_sandbox_root()


def collab_candidate_dir(desk: str = "") -> Path:
    base = _sandbox_base(desk) if str(desk or "").strip() else desk_sandbox_root()
    if base is not None:
        return base / "sandbox" / "collab"
    return CANDIDATE_ROOT


def ensure_desk_sandbox(
    desk: str,
    root: Path | None = None,
    charter: dict[str, Any] | None = None,
) -> Path | None:
    """Create this desk's working room: inbox, work, journal, collab."""
    base = _sandbox_base(desk, root)
    if base is None:
        return None
    name = str(desk or "").strip().lower()
    sandbox = base / "sandbox"
    for folder in ("inbox", "work", "journal", "collab"):
        (sandbox / folder).mkdir(parents=True, exist_ok=True)
    readme = sandbox / "README.md"
    if not readme.is_file() or readme.stat().st_size == 0:
        readme.write_text(
            f"# {name} sandbox\n\n"
            "This is the working room for this desk. It is not Wiki One for Engel AI Main.\n"
            "Before you speak, read wiki/ONE.md, inbox/LAST_ASK.md, work/OPEN.md, "
            "work/latest_duty.md, and journal/turns.jsonl.\n"
            "After you speak, the bridge appends journal/turns.jsonl.\n"
            "Do not recite the charter. Do not repeat the last journal line.\n"
            "You cannot approve protected actions, start a training run, or apply a patch from Discord.\n",
            encoding="utf-8",
        )
    open_work = sandbox / "work" / "OPEN.md"
    if not open_work.is_file() or open_work.stat().st_size == 0:
        open_work.write_text(
            f"# Open work for {name}\n\n"
            "No filed ask yet. When an ask arrives it is copied to inbox/LAST_ASK.md.\n"
            "Write the result of that ask in this file. Do not leave the canned charter here.\n",
            encoding="utf-8",
        )
    charter_path = sandbox / "CHARTER.json"
    if isinstance(charter, dict) and charter:
        safe = {
            key: charter.get(key)
            for key in ("addressed_as", "duty", "works_on", "wants")
            if key in charter
        }
        safe["desk"] = name
        charter_path.write_text(json.dumps(safe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif not charter_path.is_file():
        charter_path.write_text(json.dumps({"desk": name}, indent=2) + "\n", encoding="utf-8")
    phone = phone_sandbox_for(name)
    if phone:
        (sandbox / "PHONE.json").write_text(
            json.dumps(
                {
                    "working_sandbox": phone["phone_sandbox"],
                    "worker_id": phone["worker_id"],
                    "server_copy_is_pointer_only": True,
                    "discord_on_phone": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return sandbox


def write_desk_duty_note(desk: str, text: str, root: Path | None = None) -> Path | None:
    body = str(text or "").strip()
    if not body:
        return None
    sandbox = ensure_desk_sandbox(desk, root)
    if sandbox is None:
        return None
    path = sandbox / "work" / "latest_duty.md"
    path.write_text(body + "\n", encoding="utf-8")
    return path


def file_desk_ask(desk: str, prompt: str, root: Path | None = None) -> Path | None:
    body = " ".join(str(prompt or "").split())[:800]
    if not body:
        return None
    sandbox = ensure_desk_sandbox(desk, root)
    if sandbox is None:
        return None
    path = sandbox / "inbox" / "LAST_ASK.md"
    path.write_text(body + "\n", encoding="utf-8")
    return path


def _journal_rows(sandbox: Path, limit: int = 8) -> list[dict[str, Any]]:
    path = sandbox / "journal" / "turns.jsonl"
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def note_desk_sandbox_turn(
    desk: str,
    kind: str,
    text: str,
    root: Path | None = None,
) -> Path | None:
    body = " ".join(str(text or "").split())[:500]
    if not body:
        return None
    sandbox = ensure_desk_sandbox(desk, root)
    if sandbox is None:
        return None
    path = sandbox / "journal" / "turns.jsonl"
    row = {
        "at": _iso_now(),
        "desk": str(desk or "").strip().lower(),
        "kind": str(kind or "turn")[:40],
        "text": body,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return path
    if len(lines) > 200:
        path.write_text("\n".join(lines[-80:]) + "\n", encoding="utf-8")
    return path


def _norm_speak(text: str) -> str:
    return " ".join(str(text or "").casefold().split())


def sandbox_repeats_last(text: str, desk: str = "", root: Path | None = None) -> bool:
    base = _sandbox_base(desk, root)
    if base is None:
        return False
    rows = _journal_rows(base / "sandbox", limit=1)
    if not rows:
        return False
    last = _norm_speak(str(rows[-1].get("text") or ""))
    current = _norm_speak(text)
    if not last or not current:
        return False
    if current == last:
        return True
    # A collab invite appended after the duty line must still count as the same script.
    if len(current) >= 24 and (current in last or last in current):
        return True
    return False


def read_desk_sandbox_brief(desk: str, root: Path | None = None, limit: int = 1400) -> str:
    parts: list[str] = []
    phone = phone_sandbox_for(desk)
    if phone:
        parts.append(
            f"phone sandbox: {phone['phone_sandbox']} on {phone['worker_id']} "
            "(work from the phone; this server folder is a pointer; no Discord on the phone)"
        )
    base = _sandbox_base(desk, root)
    if base is None:
        return " | ".join(parts)[:limit]
    sandbox = base / "sandbox"
    if not sandbox.is_dir():
        return " | ".join(parts)[:limit]
    files = (
        ("last ask", sandbox / "inbox" / "LAST_ASK.md", 220),
        ("open work", sandbox / "work" / "OPEN.md", 220),
        ("last duty file", sandbox / "work" / "latest_duty.md", 280),
    )
    for label, path, cap in files:
        if not path.is_file():
            continue
        try:
            text = " ".join(path.read_text(encoding="utf-8").split())[:cap]
        except OSError:
            text = ""
        if text:
            parts.append(f"{label}: {text}")
    notes = [
        str(row.get("text") or "").strip()
        for row in _journal_rows(sandbox, limit=3)
        if str(row.get("text") or "").strip()
    ]
    if notes:
        parts.append("journal: " + " || ".join(notes)[:360])
    inbox = sandbox / "inbox"
    if inbox.is_dir():
        names = sorted(path.name for path in inbox.iterdir() if path.is_file())[:6]
        if names:
            parts.append("inbox files: " + ", ".join(names))
    return " | ".join(parts)[:limit]


def speak_from_sandbox(
    desk: str,
    charter: dict[str, Any],
    focus: str,
    duty_text: str = "",
) -> str:
    """One check-in grounded in this desk's files, used when the model is absent."""
    name = str(desk or "").strip().lower() or "desk"
    addressed = str((charter or {}).get("addressed_as") or f"Engel {name.title()}").strip()
    brief = read_desk_sandbox_brief(name)
    focus_bit = str(focus or f"{name} lane").strip()
    if str(duty_text or "").strip():
        core = str(duty_text).strip()
    elif brief:
        core = f"I read my sandbox for {focus_bit}. {brief[:420]}"
    else:
        core = f"My sandbox focus this cycle is {focus_bit}."
    line = f"{addressed}: {core}"
    if "collab" not in line.casefold():
        line = line.rstrip() + " " + collab_invite_line(name)
    return line[:1800]


def desk_duty_report(desk: str) -> str:
    """Do the desk's real check and return the result. No invented job."""
    name = str(desk or "").strip().lower()
    root = _engel_root()
    if name == "architect":
        text = _architect_duty(root)
    elif name == "memory":
        text = _memory_duty(root)
    elif name == "builder":
        text = _builder_duty(root)
    elif name == "proof":
        text = _proof_duty(root)
    elif name == "training":
        text = _training_duty(root)
    elif name == "ops":
        text = _ops_duty()
    else:
        return ""
    text = str(text or "").strip()
    if not text:
        return ""
    return f"{_iso_now()} {text}"


def _is_waiting_talk(text: str) -> bool:
    low = " ".join(str(text or "").casefold().split())
    return any(
        phrase in low
        for phrase in (
            "waiting on a real ask",
            "nothing else is queued",
            "won't invent a job",
            "i am waiting",
            "i'm waiting",
        )
    )


def ping_for_desk(
    desk: str,
    charter_loader: Callable[[str], dict[str, Any]] | None = None,
    *,
    thought_fn: Callable[..., str] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Build a standing-watch title/body. Prefer SLM thought_fn; else charter rotate."""
    name = str(desk or "").strip().lower() or "desk"
    charter: dict[str, Any] = {}
    if callable(charter_loader):
        try:
            charter = charter_loader(name) or {}
        except Exception:
            charter = {}
    addressed = str(charter.get("addressed_as") or f"Engel {name.title()}").strip()
    focus = focus_for_desk(name, charter)
    model = desk_slm_model(name)
    kind = collab_kind_for_desk(name)
    invite = collab_invite_names(name)
    title = f"{addressed}"
    try:
        ensure_desk_sandbox(name, charter=charter)
    except Exception:
        logging.exception("desk sandbox ensure failed desk=%s", name)
    duty_body = ""
    if name in DUTY_DESKS:
        try:
            duty_body = desk_duty_report(name).strip()
        except Exception:
            logging.exception("desk duty failed desk=%s", name)
            duty_body = ""
        if duty_body:
            try:
                write_desk_duty_note(name, duty_body)
            except Exception:
                logging.exception("desk duty note failed desk=%s", name)
    sandbox_brief = ""
    try:
        sandbox_brief = read_desk_sandbox_brief(name)
    except Exception:
        logging.exception("desk sandbox brief failed desk=%s", name)
        sandbox_brief = ""
    body = ""
    source = "sandbox_files"
    if callable(thought_fn):
        try:
            try:
                thought = str(
                    thought_fn(
                        desk_name=name,
                        charter=charter,
                        focus=focus,
                        model=model,
                        duty_result=duty_body,
                        sandbox_brief=sandbox_brief,
                    )
                    or ""
                ).strip()
            except TypeError:
                thought = str(
                    thought_fn(
                        desk_name=name,
                        charter=charter,
                        focus=focus,
                        model=model,
                    )
                    or ""
                ).strip()
            same_script = _norm_speak(thought) == _norm_speak(duty_body) and bool(duty_body)
            if (
                thought
                and not _is_waiting_talk(thought)
                and not same_script
                and not sandbox_repeats_last(thought, name)
            ):
                body = thought[:1600]
                source = "sandbox_thought"
        except Exception:
            logging.exception("proactive SLM thought failed desk=%s", name)
    if not body and duty_body and not sandbox_repeats_last(duty_body, name):
        body = duty_body[:1600]
        source = "desk_duty"
    if not body:
        fallback = speak_from_sandbox(name, charter, focus, duty_text="")
        if fallback and not sandbox_repeats_last(fallback, name):
            body = fallback[:1600]
            source = "sandbox_files"
    if not body:
        return title, "", {
            "focus": focus,
            "model": model,
            "source": "no_duty",
            "addressed_as": addressed,
            "content_hash": "",
            "collab_kind": kind,
            "invite": invite,
            "candidate_path": "",
        }
    if "collab" not in body.casefold():
        body = (body.rstrip() + " " + collab_invite_line(name))[:1800]
    try:
        note_desk_sandbox_turn(name, source, body)
    except Exception:
        logging.exception("desk sandbox journal failed desk=%s", name)
    candidate_path = ""
    try:
        candidate_path = str(
            save_collab_candidate(
                desk=name,
                kind=kind,
                title=title,
                body=body,
                focus=focus,
                invite=invite,
            )
        )
    except Exception:
        logging.exception("collab candidate save failed desk=%s", name)
    meta = {
        "focus": focus,
        "model": model,
        "source": source,
        "addressed_as": addressed,
        "content_hash": _content_hash(body),
        "collab_kind": kind,
        "invite": invite,
        "candidate_path": candidate_path,
    }
    return title, body, meta


def rest(
    method: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    token = str(token or "").strip()
    if not token:
        return 0, {"error": "missing bot token"}
    data = None
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "EngelAIMain-DiscordBridge (local; proactive)",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"https://discord.com/api/v10{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", "replace")
            return int(resp.status), (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        try:
            parsed: Any = json.loads(detail) if detail else {"error": detail}
        except Exception:
            parsed = {"error": detail}
        return int(exc.code), parsed
    except Exception as exc:
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


def _parse_discord_ts(value: object) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except Exception:
        return 0.0


def primary_recent_bot_activity(
    *,
    token: str,
    channel_id: str,
    interval: float,
) -> tuple[bool, str]:
    channel = str(channel_id or "").strip()
    if not channel:
        return True, "no primary CHANNEL_ID"
    code, ch = rest("GET", f"/channels/{channel}", token)
    if code != 200 or not isinstance(ch, dict):
        return True, f"channel get HTTP {code}"
    ctype = int(ch.get("type") or -1)
    now = time.time()
    cutoff = now - max(interval, PROACTIVE_MIN_INTERVAL_SECONDS)
    if ctype == 15:
        guild_id = str(ch.get("guild_id") or "").strip()
        newest = 0.0
        if guild_id:
            acode, active = rest("GET", f"/guilds/{guild_id}/threads/active", token)
            threads = active.get("threads") if acode == 200 and isinstance(active, dict) else []
            if not isinstance(threads, list):
                threads = []
            for thr in threads:
                if not isinstance(thr, dict):
                    continue
                if str(thr.get("parent_id") or "") != channel:
                    continue
                ts = _parse_discord_ts(thr.get("last_message_timestamp"))
                if ts <= 0:
                    try:
                        snow = int(str(thr.get("id") or "0"))
                        ts = ((snow >> 22) + 1420070400000) / 1000.0
                    except Exception:
                        ts = 0.0
                newest = max(newest, ts)
        if newest >= cutoff:
            return True, f"forum recent thread activity ({int(now - newest)}s ago)"
        return False, "forum quiet"
    mcode, rows = rest("GET", f"/channels/{channel}/messages?limit=8", token)
    if mcode != 200 or not isinstance(rows, list):
        return True, f"messages get HTTP {mcode}"
    for item in rows:
        if not isinstance(item, dict):
            continue
        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        ts = _parse_discord_ts(item.get("timestamp"))
        if ts < cutoff:
            continue
        if bool(author.get("bot")):
            return True, f"recent bot message ({int(now - ts)}s ago)"
        return True, f"recent human message ({int(now - ts)}s ago)"
    return False, "text quiet"


DAILY_PUBLIC_BOARDS = {
    "research": {
        "title": "Research competitions",
        "query": "open AI hackathons competitions contests to enter",
        "lead": "Engel Research daily board. Public competitions and contests we can enter:",
    },
    "sales": {
        "title": "Sales AI credits",
        "query": "public AI API free credits coupons discounts",
        "lead": "Engel Sales daily board. Public AI usage credits, coupons, and discounts:",
    },
}


def daily_board_due(state: dict[str, Any], desk: str) -> bool:
    if desk not in DAILY_PUBLIC_BOARDS:
        return False
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if str(state.get("last_daily_board_date") or "") != today:
        return True
    try:
        count = int(state.get("last_daily_board_count") or 0)
    except (TypeError, ValueError):
        count = 0
    if count < 1:
        return True
    # A reply inside an old standing thread does not show up as the day's post.
    return str(state.get("kind") or "") != "forum_thread"


def _read_public(url: str, limit: int = 200_000) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read(limit).decode("utf-8", "replace")


def _clean_title(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw)
    return " ".join(
        text.replace("&amp;", "&").replace("&#x27;", "'").replace("&quot;", '"').split()
    )[:180]


def fetch_public_board_lines(query: str) -> list[str]:
    """Read public search titles once. No accounts, no private codes."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    html = _read_public(url)
    if html.lower().count("anomaly") > 5:
        return []
    titles = re.findall(
        r'<a[^>]*class="result__a"[^>]*>(.*?)</a>',
        html,
        flags=re.I | re.S,
    )
    lines: list[str] = []
    for raw in titles:
        text = _clean_title(raw)
        if text and text not in lines:
            lines.append(text)
        if len(lines) >= 6:
            break
    return lines


def fetch_devpost_hackathons() -> list[str]:
    """Public Devpost hackathon list. Used when search is blocked."""
    raw = _read_public("https://devpost.com/api/hackathons?status=upcoming")
    payload = json.loads(raw)
    rows = payload.get("hackathons") if isinstance(payload, dict) else []
    lines: list[str] = []
    if not isinstance(rows, list):
        return lines
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        place = row.get("displayed_location") if isinstance(row.get("displayed_location"), dict) else {}
        where = str(place.get("location") or "").strip()
        state = str(row.get("open_state") or "").strip()
        line = title
        extra = ", ".join(part for part in (where, state) if part)
        if extra:
            line = f"{title} ({extra})"
        if line not in lines:
            lines.append(line[:180])
        if len(lines) >= 6:
            break
    return lines


def fetch_public_ai_credit_lines() -> list[str]:
    """Public free-tier list lines that mention AI, GPU, or credits."""
    raw = _read_public("https://raw.githubusercontent.com/ripienaar/free-for-dev/master/README.md")
    wanted = (" ai", "llm", "gpu", "credit", "openai", "nvidia", "hugging", "inference")
    lines: list[str] = []
    for row in raw.splitlines():
        text = row.strip()
        if text.startswith("- "):
            text = text[2:].strip()
        elif text.startswith("* "):
            text = text[2:].strip()
        else:
            continue
        low = text.casefold()
        if not any(term in low for term in wanted):
            continue
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        if " - " not in clean:
            continue
        if clean and clean not in lines:
            lines.append(clean[:180])
        if len(lines) >= 6:
            break
    return lines


def daily_board_for_desk(desk: str) -> tuple[str, str]:
    spec = DAILY_PUBLIC_BOARDS[desk]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    query = f"{spec['query']} {today}"
    try:
        lines = fetch_public_board_lines(query)
    except Exception:
        logging.exception("daily public board lookup failed desk=%s", desk)
        lines = []
    if not lines and desk == "research":
        try:
            lines = fetch_devpost_hackathons()
        except Exception:
            logging.exception("devpost hackathon lookup failed")
            lines = []
    if not lines and desk == "sales":
        try:
            lines = fetch_public_ai_credit_lines()
        except Exception:
            logging.exception("public AI credit lookup failed")
            lines = []
    lead = f"Fresh public pull {today}. {spec['lead']}"
    if lines:
        body = lead + "\n" + "\n".join(f"- {line}" for line in lines)
    else:
        body = (
            f"{lead}\n"
            "The public lookup returned no titles today. I am not inventing contests or codes."
        )
    return f"{spec['title']} {today}", body[:1900]


def should_post(
    *,
    desk_name: str,
    run_dir: Path,
    channel_id: str,
    token: str,
    interval: float | None = None,
    force: bool = False,
    daily_board: bool = False,
) -> tuple[bool, str]:
    if not daily_board and not proactive_enabled(desk_name):
        return False, "proactive disabled"
    silenced, silence_reason = owner_silence_active(run_dir)
    if silenced:
        return False, f"owner silenced ({silence_reason})"
    if not str(channel_id or "").strip():
        return False, "no CHANNEL_ID"
    wait = float(interval if interval is not None else proactive_interval())
    if force:
        return True, "forced"
    state = load_state(run_dir)
    last = float(state.get("last_post_unix") or 0.0)
    now = time.time()
    if last and (now - last) < wait:
        return False, f"state cooldown {int(wait - (now - last))}s left"
    return True, "cooled"


def post_ping(
    *,
    desk_name: str,
    run_dir: Path,
    channel_id: str,
    token: str,
    charter_loader: Callable[[str], dict[str, Any]] | None = None,
    write_status: Callable[..., Any] | None = None,
    thought_fn: Callable[..., str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    desk = str(desk_name or "desk").strip().lower() or "desk"
    prior_state = load_state(run_dir)
    daily = daily_board_due(prior_state, desk)
    channel = str(channel_id or "").strip() if daily else str(
        COLLAB_HOUSE_CHANNEL_ID or channel_id or ""
    ).strip()
    if daily:
        title, body = daily_board_for_desk(desk)
        title_count = sum(1 for line in body.splitlines() if line.startswith("- "))
        meta = {
            "model": desk_slm_model(desk),
            "focus": "daily public board",
            "source": "daily_public_board",
            "content_hash": _content_hash(body),
            "title_count": title_count,
        }
        if title_count < 1:
            return {
                "ok": False,
                "posted": False,
                "status": "public lookup returned no titles",
                "schema": "engel_discord_proactive_post_v1",
                "desk": desk,
                "source": "daily_public_board",
                "slm_model": meta.get("model"),
            }
    else:
        title, body, meta = ping_for_desk(desk, charter_loader, thought_fn=thought_fn)
        if not str(body or "").strip() or meta.get("source") == "no_duty":
            return {
                "ok": False,
                "posted": False,
                "status": "no desk duty to post",
                "schema": "engel_discord_proactive_post_v1",
                "desk": desk,
                "slm_model": meta.get("model"),
                "focus": meta.get("focus"),
            }
    if not str(token or "").strip() or not channel:
        return {
            "ok": False,
            "posted": False,
            "status": "token or CHANNEL_ID missing",
            "schema": "engel_discord_proactive_post_v1",
            "slm_model": meta.get("model"),
        }
    ok, reason = should_post(
        desk_name=desk,
        run_dir=run_dir,
        channel_id=channel,
        token=token,
        force=force or daily,
        daily_board=daily,
    )
    if not ok:
        return {
            "ok": False,
            "posted": False,
            "status": reason,
            "schema": "engel_discord_proactive_post_v1",
            "desk": desk,
            "slm_model": meta.get("model"),
            "focus": meta.get("focus"),
        }
    prior = load_state(run_dir)
    if (
        not force
        and str(prior.get("last_content_hash") or "") == str(meta.get("content_hash") or "")
    ):
        return {
            "ok": False,
            "posted": False,
            "status": "duplicate content skipped",
            "schema": "engel_discord_proactive_post_v1",
            "desk": desk,
            "slm_model": meta.get("model"),
        }
    code, ch = rest("GET", f"/channels/{channel}", token)
    if code != 200 or not isinstance(ch, dict):
        return {
            "ok": False,
            "posted": False,
            "status": f"channel get HTTP {code}",
            "schema": "engel_discord_proactive_post_v1",
            "slm_model": meta.get("model"),
        }
    ctype = int(ch.get("type") or -1)
    state = load_state(run_dir)
    standing = "" if daily else str(state.get("standing_thread_id") or state.get("thread_id") or "").strip()
    message_id = ""
    thread_id = ""
    kind = ""
    if ctype == 15:
        if standing:
            pcode, data = rest(
                "POST",
                f"/channels/{standing}/messages",
                token,
                {"content": body[:1900]},
            )
            if pcode in {200, 201} and isinstance(data, dict):
                kind = "forum_standing_message"
                thread_id = standing
                message_id = str(data.get("id") or "")
            else:
                standing = ""
        if not message_id:
            pcode, data = rest(
                "POST",
                f"/channels/{channel}/threads",
                token,
                {
                    "name": title[:100],
                    "message": {"content": body[:1900]},
                    "auto_archive_duration": 10080,
                },
            )
            if pcode in {200, 201} and isinstance(data, dict):
                kind = "forum_thread"
                thread_id = str(data.get("id") or "")
                msg = data.get("message") if isinstance(data.get("message"), dict) else {}
                message_id = str(msg.get("id") or "")
            else:
                return {
                    "ok": False,
                    "posted": False,
                    "status": f"forum thread HTTP {pcode}",
                    "schema": "engel_discord_proactive_post_v1",
                    "detail": data if isinstance(data, dict) else {},
                    "slm_model": meta.get("model"),
                }
    else:
        pcode, data = rest(
            "POST",
            f"/channels/{channel}/messages",
            token,
            {"content": body[:1900]},
        )
        if pcode in {200, 201} and isinstance(data, dict):
            kind = "text_message"
            message_id = str(data.get("id") or "")
        else:
            return {
                "ok": False,
                "posted": False,
                "status": f"message HTTP {pcode}",
                "schema": "engel_discord_proactive_post_v1",
                "slm_model": meta.get("model"),
            }
    posted = bool(message_id or thread_id)
    if posted:
        prior = load_state(run_dir)
        save_state(
            run_dir,
            {
                "schema": "engel_discord_proactive_state_v1",
                "desk": desk,
                "channel_id": channel,
                "last_post_unix": time.time(),
                "last_post_at_utc": _iso_now(),
                "kind": kind,
                "message_id": message_id,
                "thread_id": thread_id,
                "standing_thread_id": (
                    str(prior.get("standing_thread_id") or "")
                    if meta.get("source") == "daily_public_board"
                    else (thread_id or standing)
                ),
                "standing_thread_title": title,
                "last_content_hash": meta.get("content_hash"),
                "last_focus": meta.get("focus"),
                "last_source": meta.get("source"),
                "last_daily_board_date": (
                    datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    if meta.get("source") == "daily_public_board"
                    else str(prior.get("last_daily_board_date") or "")
                ),
                "last_daily_board_count": (
                    int(meta.get("title_count") or 0)
                    if meta.get("source") == "daily_public_board"
                    else int(prior.get("last_daily_board_count") or 0)
                ),
                "slm_model": meta.get("model"),
                "owner_silenced": bool(prior.get("owner_silenced")),
                "owner_silence_reason": str(prior.get("owner_silence_reason") or ""),
                "owner_silence_at_utc": str(prior.get("owner_silence_at_utc") or ""),
                "owner_silence_until_unix": float(prior.get("owner_silence_until_unix") or 0.0),
                "owner_silence_channel_id": str(prior.get("owner_silence_channel_id") or ""),
            },
        )
        if callable(write_status):
            try:
                write_status(
                    ok=True,
                    status="proactive standing-watch posted",
                    last_message_id=message_id or thread_id,
                    last_channel_id=channel,
                    proactive_desk=desk,
                    proactive_kind=kind,
                    proactive_slm_model=meta.get("model"),
                    proactive_focus=meta.get("focus"),
                    proactive_source=meta.get("source"),
                )
            except Exception:
                logging.exception("proactive write_status failed")
    return {
        "ok": posted,
        "posted": posted,
        "status": "posted standing-watch" if posted else "no message id",
        "schema": "engel_discord_proactive_post_v1",
        "desk": desk,
        "discord_channel_id": channel,
        "kind": kind,
        "discord_message_id": message_id,
        "discord_thread_id": thread_id,
        "content_preview": body[:200],
        "slm_model": meta.get("model"),
        "focus": meta.get("focus"),
        "source": meta.get("source"),
    }


async def initiate_loop(
    client: Any,
    *,
    desk_name: str,
    run_dir: Path,
    channel_id: str,
    token: str,
    charter_loader: Callable[[str], dict[str, Any]] | None = None,
    write_status: Callable[..., Any] | None = None,
    thought_fn: Callable[..., str] | None = None,
) -> None:
    interval = proactive_interval()
    stagger = int(DESK_STAGGER_SECONDS.get(str(desk_name or "").strip().lower(), 0))
    model = desk_slm_model(desk_name)
    logging.info(
        "Discord PROACTIVE/INITIATE armed desk=%s interval=%ss stagger=%ss slm=%s channel=%s",
        desk_name,
        int(interval),
        stagger,
        model,
        channel_id,
    )
    # Settle + stagger only. Never force-post on restart (that caused identical spam).
    await asyncio.sleep(90.0 + float(stagger))
    while True:
        try:
            if getattr(client, "is_closed", lambda: False)():
                return
            silenced, silence_reason = owner_silence_active(run_dir)
            if silenced:
                logging.info(
                    "Discord proactive desk=%s skipped owner silenced (%s)",
                    desk_name,
                    silence_reason,
                )
            else:
                from engel_discord_desk_manager import initiative_open, note_spoke

                open_now, decision = initiative_open(desk_name, run_dir)
                phase = str(decision.get("evaluation_state") or "")
                # A quiet room scores Hold because nobody has said this desk's
                # topic. That is when the scheduled check-in should still post.
                # Owner silence and the post cooldown stay quiet.
                if phase in {"OwnerSilence", "Cooldown"} or (
                    not open_now and phase != "Hold"
                ):
                    logging.info(
                        "Discord initiative hold desk=%s state=%s score=%s margin=%s",
                        desk_name,
                        decision.get("evaluation_state"),
                        decision.get("initiative_score"),
                        decision.get("activation_margin"),
                    )
                    result = {
                        "posted": False,
                        "status": f"initiative {decision.get('evaluation_state')}",
                        "slm_model": model,
                        "focus": decision.get("evaluation_state"),
                    }
                else:
                    result = await asyncio.to_thread(
                        post_ping,
                        desk_name=desk_name,
                        run_dir=run_dir,
                        channel_id=channel_id,
                        token=token,
                        charter_loader=charter_loader,
                        write_status=write_status,
                        thought_fn=thought_fn,
                        force=False,
                    )
                    if result.get("posted"):
                        note_spoke(run_dir, reason="initiative")
                logging.info(
                    "Discord proactive desk=%s posted=%s status=%s slm=%s focus=%s",
                    desk_name,
                    result.get("posted"),
                    result.get("status"),
                    result.get("slm_model"),
                    result.get("focus"),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Discord proactive loop failed desk=%s", desk_name)
        await asyncio.sleep(interval)


def start_if_enabled(
    client: Any,
    *,
    desk_name: str,
    run_dir: Path,
    channel_id: str,
    token: str,
    charter_loader: Callable[[str], dict[str, Any]] | None = None,
    write_status: Callable[..., Any] | None = None,
    thought_fn: Callable[..., str] | None = None,
) -> None:
    global _PROACTIVE_TASK
    if not proactive_enabled(desk_name):
        logging.info(
            "Discord PROACTIVE/INITIATE idle desk=%s",
            desk_name or "(main/no-desk)",
        )
        return
    if _PROACTIVE_TASK and not _PROACTIVE_TASK.done():
        return
    loop = getattr(client, "loop", None)
    if loop is None:
        return
    _PROACTIVE_TASK = loop.create_task(
        initiate_loop(
            client,
            desk_name=desk_name,
            run_dir=run_dir,
            channel_id=channel_id,
            token=token,
            charter_loader=charter_loader,
            write_status=write_status,
            thought_fn=thought_fn,
        ),
        name=f"engel-discord-proactive-{desk_name or 'unknown'}",
    )


async def daily_public_board_loop(
    client: Any,
    *,
    desk_name: str,
    run_dir: Path,
    channel_id: str,
    token: str,
    charter_loader: Callable[[str], dict[str, Any]] | None = None,
    write_status: Callable[..., Any] | None = None,
    thought_fn: Callable[..., str] | None = None,
) -> None:
    """Hard-wired UTC-day pull for Research competitions and Sales credits."""
    desk = str(desk_name or "").strip().lower()
    logging.info("Discord DAILY BOARD hard-wired desk=%s channel=%s", desk, channel_id)
    await asyncio.sleep(45.0)
    while True:
        try:
            if getattr(client, "is_closed", lambda: False)():
                return
            silenced, silence_reason = owner_silence_active(run_dir)
            if silenced:
                logging.info(
                    "Discord daily board desk=%s held owner silenced (%s)",
                    desk,
                    silence_reason,
                )
            elif daily_board_due(load_state(run_dir), desk):
                result = await asyncio.to_thread(
                    post_ping,
                    desk_name=desk,
                    run_dir=run_dir,
                    channel_id=channel_id,
                    token=token,
                    charter_loader=charter_loader,
                    write_status=write_status,
                    thought_fn=thought_fn,
                    force=False,
                )
                logging.info(
                    "Discord daily board desk=%s posted=%s status=%s source=%s",
                    desk,
                    result.get("posted"),
                    result.get("status"),
                    result.get("source"),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Discord daily board loop failed desk=%s", desk)
        await asyncio.sleep(900.0)


def start_daily_public_board(
    client: Any,
    *,
    desk_name: str,
    run_dir: Path,
    channel_id: str,
    token: str,
    charter_loader: Callable[[str], dict[str, Any]] | None = None,
    write_status: Callable[..., Any] | None = None,
    thought_fn: Callable[..., str] | None = None,
) -> None:
    """Always arm Research and Sales. Not gated by ENGEL_DISCORD_PROACTIVE."""
    global _DAILY_BOARD_TASK
    desk = str(desk_name or "").strip().lower()
    if desk not in DAILY_PUBLIC_BOARDS:
        return
    if _DAILY_BOARD_TASK and not _DAILY_BOARD_TASK.done():
        return
    loop = getattr(client, "loop", None)
    if loop is None:
        return
    _DAILY_BOARD_TASK = loop.create_task(
        daily_public_board_loop(
            client,
            desk_name=desk,
            run_dir=run_dir,
            channel_id=channel_id,
            token=token,
            charter_loader=charter_loader,
            write_status=write_status,
            thought_fn=thought_fn,
        ),
        name=f"engel-discord-daily-board-{desk}",
    )


def default_charter_loader(name: str) -> dict[str, Any]:
    roots = [
        Path("/opt/engel/memory/ENGEL_DISCORD_DESK_CHARTERS_V1.json"),
        Path(__file__).resolve().parents[1] / "memory" / "ENGEL_DISCORD_DESK_CHARTERS_V1.json",
    ]
    for path in roots:
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                mouths = data.get("mouths") if isinstance(data, dict) else {}
                row = mouths.get(str(name or "").strip().lower()) if isinstance(mouths, dict) else None
                if isinstance(row, dict):
                    return row
        except Exception:
            continue
    return {}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Engel Discord desk collab initiate")
    parser.add_argument("--now", action="store_true", help="Post one collab idea immediately.")
    parser.add_argument("--desk", default=os.environ.get("ENGEL_DISCORD_DESK_NAME", ""))
    args = parser.parse_args(argv)
    if not args.now:
        print(json.dumps({"ok": False, "error": "pass --now"}))
        return 2
    desk = str(args.desk or "").strip().lower()
    token = str(
        os.environ.get("ENGEL_DISCORD_BOT_TOKEN")
        or os.environ.get("ENGELCODE_DISCORD_BOT_TOKEN")
        or ""
    )
    channel = str(
        os.environ.get("ENGEL_DISCORD_CHANNEL_ID")
        or os.environ.get("ENGELCODE_DISCORD_CHANNEL_ID")
        or ""
    )
    run_dir = Path(
        os.environ.get("ENGEL_DISCORD_RUN_DIR")
        or f"/opt/engel/desks/{desk}/run/discord_bridge"
    )
    os.environ["ENGEL_DISCORD_PROACTIVE"] = "1"
    result = post_ping(
        desk_name=desk,
        run_dir=run_dir,
        channel_id=channel,
        token=token,
        charter_loader=default_charter_loader,
        force=True,
    )
    print(
        json.dumps(
            {
                "ok": bool(result.get("ok")),
                "posted": bool(result.get("posted")),
                "status": result.get("status"),
                "desk": result.get("desk") or desk,
                "kind": result.get("kind"),
                "focus": result.get("focus"),
            },
            sort_keys=True,
        )
    )
    return 0 if result.get("posted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
