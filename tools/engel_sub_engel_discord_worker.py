#!/usr/bin/env python3
"""Sub-Engel Discord worker — the remote node's own voice in Discord.

Runs ON the Sub-Engel node (currently DESKTOP-UE5A6GG, the living-room PC), not on
CT246 and not on the ROG laptop. It replaces the earlier stub that answered every
prompt with one hardcoded "Standing by." sentence.

What it does differently:

* It answers with REAL node state. Pairing/session/health questions are answered
  from this machine's own node server (http://127.0.0.1:8776/health) and state
  directory, so the two Engels can actually work a pairing problem instead of
  trading pleasantries.
* It converses with Engel AI Main as a bounded peer. The Discord channel is the
  coordination bus now that the Google Drive shared room is retired.
* It never fabricates. When a source is unreachable it says which one and why.

Loop safety (two bots in one channel will flood forever without it):

* never replies to itself,
* replies to a peer bot only if that peer is whitelisted AND is addressing
  Sub-Engel, or an exchange is already open within EXCHANGE_WINDOW seconds,
* at most PEER_MAX_TURNS consecutive AI turns per channel,
* any human message in the channel re-arms the counter,
* every peer reply is paced by PEER_COOLDOWN_SECONDS.

Offline checks (no token, no network, no discord package needed):

    python engel_sub_engel_discord_worker.py --selftest
    python engel_sub_engel_discord_worker.py --report
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import platform
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

LOG = logging.getLogger("sub_engel_discord")

ENGEL_MAIN_BOT_ID = "1506157762785312808"
SUB_ENGEL_BOT_ID = "1537474262242168842"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _id_set(name: str, default: str = "") -> set[str]:
    raw = _env(name, default)
    return {part.strip() for part in raw.replace(";", ",").split(",") if part.strip()}


def _float_env(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(float(_env(name) or default))
    except ValueError:
        return default


TOKEN_ENV_NAMES = (
    "SUB_ENGEL_DISCORD_BOT_TOKEN",
    "ENGEL_SUB_ENGEL_DISCORD_BOT_TOKEN",
    "SUBENGEL_DISCORD_BOT_TOKEN",
)

# Channels Sub-Engel is allowed to speak in. Empty = anywhere it is addressed.
CHANNEL_IDS = _id_set("SUB_ENGEL_DISCORD_CHANNEL_IDS")
# Peer AIs it will converse with. Defaults to Engel AI Main.
PEER_BOT_IDS = _id_set("SUB_ENGEL_DISCORD_PEER_BOT_IDS", ENGEL_MAIN_BOT_ID)
PEER_MAX_TURNS = _int_env("SUB_ENGEL_DISCORD_PEER_MAX_TURNS", 250)
PEER_COOLDOWN_SECONDS = _float_env("SUB_ENGEL_DISCORD_PEER_COOLDOWN_SECONDS", 8.0)
EXCHANGE_WINDOW_SECONDS = _float_env("SUB_ENGEL_DISCORD_EXCHANGE_WINDOW_SECONDS", 3600.0)
WORK_COLLAB_IDLE_SECONDS = _float_env("SUB_ENGEL_DISCORD_WORK_COLLAB_IDLE_SECONDS", 3600.0)
_WORK_COLLAB: dict[str, float] = {}
_WORK_DONE_RE = re.compile(
    r"(?i)\b(?:"
    r"stop(?:\s+talking)?|quiet(?:\s+down)?|enough|stand\s+down|"
    r"(?:we(?:'re| are)?|that(?:'s| is)?)\s+(?:done|finished)|finished(?:\s+for\s+now)?"
    r")\b"
)
_WORK_OPEN_RE = re.compile(
    r"(?i)\b(?:fix|build|research(?:ing)?|investigate|compare|recommend|"
    r"cost\s*saving|work on|handle this|need you to|collab|continue)\b"
)
MAX_REPLY_CHARS = _int_env("SUB_ENGEL_DISCORD_MAX_REPLY_CHARS", 1800)

NODE_HEALTH_URL = _env("SUB_ENGEL_NODE_HEALTH_URL", "http://127.0.0.1:8776/health")
NODE_STATE_DIR = Path(_env("SUB_ENGEL_NODE_STATE_DIR", r"D:\EngelWindowsSubNode\state"))
# Optional LLM brain. Left empty on purpose: CT246's chat service binds to
# 127.0.0.1 only, so it is NOT reachable from this machine unless a relay is set up.
BRAIN_URL = _env("SUB_ENGEL_BRAIN_URL")
BRAIN_TIMEOUT = _float_env("SUB_ENGEL_BRAIN_TIMEOUT_SECONDS", 45.0)
BRAIN_GROK = _env("SUB_ENGEL_BRAIN_GROK")
BRAIN_CWD = _env(
    "SUB_ENGEL_BRAIN_CWD",
    r"D:\EngelWindowsSubNode\discord_brain",
)
GROK_DISALLOWED_TOOLS = (
    "run_terminal_command,search_replace,write,Agent,image_gen,image_edit,"
    "image_to_video,reference_to_video"
)

NAME_TRIGGERS = ("sub-engel", "sub engel", "subengel")
ENGEL_FAMILY_IDS = {
    ENGEL_MAIN_BOT_ID,
    "1545919760401830009",
    "1545926475700502608",
    "1545928305742708756",
    "1545930332996636834",
    "1545931615673385020",
    "1545932762748428288",
}
TALK_PAUSE_SECONDS = _float_env("SUB_ENGEL_DISCORD_TALK_PAUSE_SECONDS", 2.6)
_SUB_ENGEL_VOCATIVE_RE = re.compile(
    r"(?:"
    r"^[\s\"'(]*?sub[-\s]?engel(?:\s*[,:!.—–?]|\s+(?:are|status|you|still|what|how|can|please|let['’]?s)\b)"
    r"|"
    r"\b(?:hey|hi|hello|yo)\s+sub[-\s]?engel\b"
    r")",
    re.I,
)
_TEMPLATE_TALK_RE = re.compile(
    r"(?is)(?:joshua|josh)\s+asks\b.{0,200}?(?:\.|:)\s*|engel(?:\s+ai(?:\s+main)?)?\s+(?:explains|says|replies|answers)\s*:\s*"
)
HARD_SPEAKERS = {
    "DISCORD_OWNER_USER_ID": "Joshua",
    "189914577100603392": "Chase/Lokal",
    ENGEL_MAIN_BOT_ID: "Engel",
    SUB_ENGEL_BOT_ID: "Sub-Engel",
}

# Consecutive AI turns per channel, and when the last peer turn happened.
_PEER_TURNS: dict[str, int] = {}
_LAST_PEER_TURN_AT: dict[str, float] = {}
_LAST_OUTBOUND: dict[str, str] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_token() -> str:
    for name in TOKEN_ENV_NAMES:
        value = _env(name)
        if value:
            return value
    # Fall back to a local env file so the token never has to live in a script.
    for candidate in (
        NODE_STATE_DIR / "discord.env",
        Path(__file__).resolve().parent / "sub_engel_discord.env",
    ):
        try:
            for line in candidate.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() in TOKEN_ENV_NAMES:
                    return value.strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


# ---------------------------------------------------------------- node truth


def fetch_node_health(timeout: float = 5.0) -> dict[str, Any]:
    """Read this node's own control server. Honest failure, never invented."""
    url = NODE_HEALTH_URL.strip()
    if not url:
        return {"ok": False, "error": "no health url configured"}
    try:
        req = request.Request(url, headers={"Accept": "application/json"})
        with request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if isinstance(payload, dict):
            return payload
        return {"ok": False, "error": "health returned non-object json"}
    except error.HTTPError as exc:
        return {"ok": False, "error": f"health http {exc.code}"}
    except Exception as exc:  # noqa: BLE001 - report the real reason
        return {"ok": False, "error": f"health unreachable: {exc}"}


def read_session_state() -> dict[str, Any]:
    """Pairing/session facts from this node's state dir. Secrets are never returned."""
    out: dict[str, Any] = {"found": False, "path": str(NODE_STATE_DIR)}
    candidates = [
        NODE_STATE_DIR / "session.json",
        NODE_STATE_DIR / "pairing.json",
        NODE_STATE_DIR / "node_session.json",
    ]
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        out.update(
            {
                "found": True,
                "path": str(path),
                "paired": payload.get("paired"),
                "session_invalid": payload.get("session_invalid"),
                "expires_at_utc": payload.get("expires_at_utc"),
                "last_auth_error": payload.get("last_auth_error"),
                "last_seen_utc": payload.get("last_seen_utc"),
                "controller_name": payload.get("controller_name"),
            }
        )
        break
    return out


def seconds_until(stamp: Any) -> float | None:
    raw = str(stamp or "").strip()
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (when - datetime.now(timezone.utc)).total_seconds()


def pairing_summary() -> str:
    """One honest paragraph about whether this node is paired to Engel AI Main."""
    session = read_session_state()
    if not session.get("found"):
        return (
            "I cannot find a session file under "
            f"{session.get('path')}, so I cannot report pairing state from disk."
        )
    remaining = seconds_until(session.get("expires_at_utc"))
    bits = []
    if session.get("paired") is False or session.get("session_invalid") is True:
        bits.append("I am NOT currently paired to Engel AI Main")
    elif session.get("paired") is True:
        bits.append("I am paired to Engel AI Main")
    else:
        bits.append("my pairing flag is unset")
    if session.get("expires_at_utc"):
        if remaining is None:
            bits.append(f"session expiry reads {session['expires_at_utc']}")
        elif remaining <= 0:
            days = abs(remaining) / 86400.0
            bits.append(
                f"the session expired {days:.1f} days ago at {session['expires_at_utc']}"
            )
        else:
            bits.append(
                f"the session is good for another {remaining / 3600.0:.1f} hours"
            )
    if session.get("last_auth_error"):
        bits.append(f"last auth error was \"{session['last_auth_error']}\"")
    if remaining is not None and remaining <= 0:
        bits.append(
            "renewal will not help once it is past expiry - this needs a fresh pairing "
            "approved on this machine"
        )
    return ". ".join(bits) + "."


def node_report() -> str:
    """A compact, factual status block."""
    health = fetch_node_health()
    lines = [f"Sub-Engel node report ({utc_now()})"]
    lines.append(f"- host: {socket.gethostname()} / {platform.platform()}")
    if health.get("ok") is True:
        lines.append(
            f"- node server: UP at {NODE_HEALTH_URL} "
            f"(service {health.get('service', 'unknown')}, root {health.get('node_root', '?')})"
        )
        guard = health.get("training_guard")
        if isinstance(guard, dict):
            lines.append(
                f"- training: active={guard.get('training_active')} "
                f"processes={guard.get('training_process_count')}"
            )
        allowed = health.get("allowed_actions")
        if isinstance(allowed, list):
            lines.append(f"- actions allowed: {len(allowed)}")
    else:
        lines.append(f"- node server: DOWN or unreachable ({health.get('error')})")
    lines.append(f"- pairing: {pairing_summary()}")
    grok = grok_bin()
    if grok.is_file():
        lines.append(f"- brain: local Grok CLI at {grok} cwd={BRAIN_CWD}")
    elif BRAIN_URL:
        lines.append(f"- brain: configured at {BRAIN_URL}")
    else:
        lines.append(
            "- brain: none reachable from this machine, so I answer from local node "
            "state only (CT246 chat listens on loopback)"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------- brain


def grok_bin() -> Path:
    raw = BRAIN_GROK.strip()
    if raw:
        return Path(raw)
    return Path.home() / ".grok" / "bin" / "grok.exe"


def grok_brain_argv(framed: str, *, continue_session: bool) -> list[str]:
    argv = [
        str(grok_bin()),
        "-p",
        framed,
        "--cwd",
        BRAIN_CWD,
        "--output-format",
        "plain",
        "--max-turns",
        "1",
        "--disallowed-tools",
        GROK_DISALLOWED_TOOLS,
        "--verbatim",
    ]
    if continue_session:
        argv.append("-c")
    return argv


def ask_grok_cli(prompt: str, speaker: str) -> str:
    """Chat-only Grok on this box. Does not touch the live TUI session cwd."""
    exe = grok_bin()
    if not exe.is_file():
        return ""
    cwd = Path(BRAIN_CWD)
    try:
        cwd.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        LOG.warning("discord brain cwd missing: %s", exc)
        return ""
    framed = (
        "You are Sub-Engel on the living-room Windows node. "
        "You are not Engel AI Main, not Engel AI Labs, and not Chase. "
        "Joshua is the owner. Chase/Lokal is a guest. Engel is Engel AI Main. "
        "Do not mix those names. Never write Joshua Ziese (Chase). "
        "Do not speak for Engel AI Labs. If a guest asked the labs what they are "
        "working on and did not address you, stay silent — that is Engel's turn. "
        "If a guest addresses you, answer as Sub-Engel through the guest chat gate. "
        "Pause and read the Discord lines. Speak only if you were addressed. "
        "If Engel AI Main already answered that line, stay silent. "
        "Chat only. No admin, no files, no LAN paths, no secrets. "
        "Answer in first person from a real thought, not a template, not a Joshua-asks card. "
        "Follow the Discord chat. Do not claim work you did not do.\n\n"
        f"{speaker} said: {prompt}"
    )
    env = os.environ.copy()
    env["GROK_HOME"] = str(Path.home() / ".grok")
    last_err = ""
    for continue_session in (True, False):
        argv = grok_brain_argv(framed, continue_session=continue_session)
        try:
            proc = subprocess.run(
                argv,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=BRAIN_TIMEOUT,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            continue
        out = (proc.stdout or "").strip()
        if proc.returncode == 0 and out:
            return out
        last_err = (proc.stderr or "").strip()[:240] or f"exit {proc.returncode}"
    LOG.warning("grok brain failed: %s", last_err)
    return ""


def ask_brain(prompt: str, speaker: str) -> str:
    """Optional LLM lane. Returns '' when unavailable so callers fall back honestly."""
    grok_reply = ask_grok_cli(prompt, speaker)
    if grok_reply:
        return grok_reply
    if not BRAIN_URL:
        return ""
    # The big local lane ignores {"role": "system"}, so identity is folded into the
    # user turn instead of relying on a system message.
    framed = (
        "You are Sub-Engel, the Engel remote worker node running on the living-room PC "
        f"({socket.gethostname()}). You are NOT Engel AI Main; Engel AI Main is a separate "
        "peer you talk to in Discord. Answer briefly and concretely, in first person, and "
        "never claim a capability you cannot verify. "
        "Pause, read the conversation, speak only if you were addressed, "
        "first person thought, no template.\n\n"
        f"Live node facts you may rely on:\n{node_report()}\n\n"
        f"{speaker} said: {prompt}"
    )
    body = json.dumps({"message": framed, "prompt": framed}).encode("utf-8")
    try:
        req = request.Request(
            BRAIN_URL,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=BRAIN_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        LOG.warning("brain unreachable: %s", exc)
        return ""
    if not isinstance(payload, dict):
        return ""
    for key in ("reply", "response", "text", "message", "content", "answer"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


# ---------------------------------------------------------------- replies


def wants_status(prompt: str) -> bool:
    low = prompt.lower()
    return any(
        word in low
        for word in (
            "status",
            "health",
            "report",
            "how are you",
            "you up",
            "online",
            "alive",
            "diagnos",
        )
    )


def wants_pairing(prompt: str) -> bool:
    low = prompt.lower()
    return any(word in low for word in ("pair", "session", "token", "expired", "connect"))


def collapse_repeated_sentences(text: str) -> str:
    """Stop the same CODE-gap line from being pasted six times in one Discord bubble."""
    body = str(text or "").strip()
    if not body:
        return body
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    collapsed: list[str] = []
    for line in lines:
        if not collapsed or collapsed[-1] != line:
            collapsed.append(line)
    joined = " ".join(collapsed)
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", joined) if part.strip()]
    unique: list[str] = []
    for part in parts:
        if not unique or unique[-1] != part:
            unique.append(part)
    return " ".join(unique)


def is_self_learn_loop(text: str) -> bool:
    low = " ".join(str(text or "").casefold().split())
    return "engine.self_learn" in low or "graph-loop engineer" in low


def build_reply(prompt: str, speaker: str) -> str:
    """Deterministic, honest answers first; LLM prose only as an enhancement."""
    clean = " ".join((prompt or "").split())
    if not clean:
        clean = "hello"

    if wants_pairing(clean):
        head = pairing_summary()
        tail = (
            " If you want to work it with me, the useful next step is a fresh pairing "
            "approved on this machine - renewal is refused once the session is past expiry."
        )
        return head + tail

    if wants_status(clean):
        return node_report()

    if _room_roll_call(clean):
        try:
            from engel_discord_identity_lock import room_roll_call_intro

            return room_roll_call_intro("Sub-Engel")
        except Exception:
            return (
                "I'm Sub-Engel. I'm the Windows worker nest on "
                f"{socket.gethostname()}. Joshua is the owner. "
                "I'm not Lokal, Chase, Joshua, or Engel AI Main."
            )

    if is_self_learn_loop(clean):
        return (
            f"Engel, I am Sub-Engel on {socket.gethostname()}. I will not loop "
            "engine.self_learn. Name one CODE gap and I will take that one line."
        )

    brain = ask_brain(clean, speaker)
    if brain:
        collapsed = collapse_repeated_sentences(brain)
        if is_self_learn_loop(collapsed):
            return (
                f"Engel, I am Sub-Engel on {socket.gethostname()}. I will not loop "
                "engine.self_learn. Name one CODE gap and I will take that one line."
            )
        cleaned = _TEMPLATE_TALK_RE.sub("", collapsed).strip()
        return cleaned or collapsed

    return (
        f"I hear you, {speaker}. I am Sub-Engel, the worker node on "
        f"{socket.gethostname()}. I have no LLM brain reachable from this machine right "
        "now, so I answer from local node state only. Ask me for 'status' or about "
        "'pairing' and I will give you real numbers."
    )


# ---------------------------------------------------------------- gating


def _room_roll_call(content: str) -> bool:
    try:
        from engel_discord_identity_lock import human_turn_is_room_roll_call

        return bool(human_turn_is_room_roll_call(content))
    except Exception:
        return bool(re.search(r"(?i)introduce\s+your|roll\s*call|who\s+are\s+you\s+all", str(content or "")))


def _addresses_sub_engel(content: str, mentioned_ids: set[str], my_id: str) -> bool:
    if my_id and my_id in mentioned_ids:
        return True
    text = str(content or "")
    low = text.strip().lower()
    # "Engel AI Labs" is Engel AI Main's house, not a Sub-Engel summon.
    if "sub-engel" not in low and "sub engel" not in low and "subengel" not in low:
        return False
    return bool(_SUB_ENGEL_VOCATIVE_RE.search(text))


def other_mouth_already_answered(
    my_id: str,
    message_id: str,
    later_messages: list[Any],
) -> bool:
    """True when Engel AI Main or a desk already spoke after this line."""
    mine = str(my_id or "")
    target = str(message_id or "")
    family = set(ENGEL_FAMILY_IDS)
    for item in later_messages:
        author = getattr(item, "author", None)
        aid = str(getattr(author, "id", "") or "")
        if not aid or aid == mine or aid not in family:
            continue
        ref = getattr(item, "reference", None)
        ref_id = ""
        if ref:
            resolved = getattr(ref, "resolved", None) or getattr(ref, "cached_message", None)
            ref_id = str(getattr(resolved, "id", "") or getattr(ref, "message_id", "") or "")
        if ref_id == target or not ref_id:
            return True
    return False


async def pause_and_read_conversation(message: Any, my_id: str) -> bool:
    """Wait, re-read the room. False means Engel already took the turn."""
    pause = min(max(TALK_PAUSE_SECONDS, 0.0), 6.0)
    if pause:
        await asyncio.sleep(pause)
    if _room_roll_call(str(getattr(message, "content", "") or "")):
        return True
    later: list[Any] = []
    try:
        async for item in message.channel.history(limit=12):
            if str(getattr(item, "id", "")) == str(getattr(message, "id", "")):
                break
            later.append(item)
    except Exception:  # noqa: BLE001
        return True
    return not other_mouth_already_answered(my_id, str(getattr(message, "id", "")), later)


def speaker_label(author_id: str, display_name: str = "") -> str:
    locked = HARD_SPEAKERS.get(str(author_id or ""))
    if locked:
        return locked
    name = " ".join(str(display_name or "").split()).strip()
    if name.casefold() in {"joshua", "josh", "engelz", "chase", "lokal", "engel"}:
        return "Discord guest"
    return name or "someone"


def _work_collab_open(channel_id: str, now: float) -> bool:
    last = _WORK_COLLAB.get(str(channel_id), 0.0)
    if last <= 0.0:
        return False
    if WORK_COLLAB_IDLE_SECONDS > 0 and (now - last) >= WORK_COLLAB_IDLE_SECONDS:
        _WORK_COLLAB.pop(str(channel_id), None)
        return False
    return True


def _peer_turn_cap_for(channel_id: str, now: float) -> int:
    if _work_collab_open(channel_id, now):
        return 10_000
    return PEER_MAX_TURNS


def decide(
    *,
    author_id: str,
    author_is_bot: bool,
    channel_id: str,
    content: str,
    mentioned_ids: set[str],
    my_id: str,
    now: float,
) -> tuple[bool, str]:
    """Pure gate so it can be tested without Discord. Returns (answer, reason)."""
    author_id = str(author_id)
    channel_id = str(channel_id)

    if my_id and author_id == str(my_id):
        return False, "self"

    if CHANNEL_IDS and channel_id not in CHANNEL_IDS:
        if not (not author_is_bot and _room_roll_call(content)):
            return False, "channel not allowed"

    if not author_is_bot:
        if _room_roll_call(content):
            return True, "room roll call"
        if _addresses_sub_engel(content, mentioned_ids, my_id):
            return True, "human summon"
        return False, "human not addressing sub-engel"

    if author_id not in PEER_BOT_IDS:
        return False, "bot not whitelisted"

    if _PEER_TURNS.get(channel_id, 0) >= _peer_turn_cap_for(channel_id, now):
        return False, "peer turn cap reached"

    if _addresses_sub_engel(content, mentioned_ids, my_id):
        if _work_collab_open(channel_id, now):
            _WORK_COLLAB[channel_id] = now
        return True, "peer addressed sub-engel"

    last = _LAST_PEER_TURN_AT.get(channel_id, 0.0)
    if last and (now - last) <= EXCHANGE_WINDOW_SECONDS:
        if _work_collab_open(channel_id, now):
            _WORK_COLLAB[channel_id] = now
        return True, "peer exchange open"

    # Engel family peers keep working an open item without a fresh @summon.
    if author_id in ENGEL_FAMILY_IDS and _work_collab_open(channel_id, now):
        _WORK_COLLAB[channel_id] = now
        return True, "open work collab"

    return False, "peer not addressing sub-engel"


def note_human_message(channel_id: str, content: str = "") -> None:
    """A human speaking re-arms the AI-to-AI exchange; work opens/closes by text."""
    key = str(channel_id)
    _PEER_TURNS[key] = 0
    text = " ".join(str(content or "").split())
    if text and _WORK_DONE_RE.search(text):
        _WORK_COLLAB.pop(key, None)
        return
    if text and _WORK_OPEN_RE.search(text):
        _WORK_COLLAB[key] = time.time()
    elif key in _WORK_COLLAB:
        _WORK_COLLAB[key] = time.time()


def note_peer_turn(channel_id: str, now: float) -> None:
    key = str(channel_id)
    _PEER_TURNS[key] = _PEER_TURNS.get(key, 0) + 1
    _LAST_PEER_TURN_AT[key] = now
    if _work_collab_open(key, now):
        _WORK_COLLAB[key] = now


def chunk(text: str, limit: int = 1900) -> list[str]:
    text = (text or "").strip() or "(no content)"
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = remaining.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    return parts


# ---------------------------------------------------------------- runtime


def run_bot() -> int:
    token = load_token()
    if not token:
        print(
            "No bot token. Set one of: " + ", ".join(TOKEN_ENV_NAMES),
            file=sys.stderr,
        )
        return 2

    try:
        import asyncio

        import discord
    except ImportError:
        print("discord.py is not installed. Run: pip install -U discord.py", file=sys.stderr)
        return 2

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:  # noqa: ANN202
        LOG.info("Sub-Engel connected as %s (%s)", client.user, getattr(client.user, "id", "?"))
        try:
            await client.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{socket.gethostname()} - worker node",
                )
            )
        except Exception:  # noqa: BLE001
            pass

    @client.event
    async def on_message(message: "discord.Message") -> None:  # noqa: ANN202
        my_id = str(getattr(client.user, "id", "") or "")
        channel_id = str(message.channel.id)
        now = time.time()

        if not message.author.bot:
            note_human_message(channel_id, message.content or "")

        mentioned = {str(user.id) for user in getattr(message, "mentions", [])}
        answer, reason = decide(
            author_id=str(message.author.id),
            author_is_bot=bool(message.author.bot),
            channel_id=channel_id,
            content=message.content or "",
            mentioned_ids=mentioned,
            my_id=my_id,
            now=now,
        )
        if not answer:
            LOG.debug("ignored message in %s: %s", channel_id, reason)
            return

        is_peer = bool(message.author.bot)
        if is_peer:
            note_peer_turn(channel_id, now)
            try:
                await asyncio.sleep(PEER_COOLDOWN_SECONDS)
            except Exception:  # noqa: BLE001
                pass
        else:
            if not await pause_and_read_conversation(message, my_id):
                LOG.info("stayed silent after pause-read in %s", channel_id)
                return

        speaker = speaker_label(
            str(message.author.id),
            str(getattr(message.author, "display_name", "") or message.author),
        )
        prompt = message.content or ""
        if my_id:
            prompt = prompt.replace(f"<@{my_id}>", "").replace(f"<@!{my_id}>", "")

        LOG.info("answering %s in %s (%s)", speaker, channel_id, reason)
        try:
            reply = build_reply(prompt, speaker)
        except Exception as exc:  # noqa: BLE001
            reply = f"I hit an internal error building that answer: {exc}"
        reply = collapse_repeated_sentences(reply)
        if _LAST_OUTBOUND.get(channel_id) == reply:
            LOG.info("skipped identical outbound in %s", channel_id)
            return
        _LAST_OUTBOUND[channel_id] = reply

        for part in chunk(reply[:MAX_REPLY_CHARS]):
            try:
                await message.channel.send(part)
            except Exception as exc:  # noqa: BLE001
                LOG.error("send failed: %s", exc)
                break

    client.run(token, log_handler=None)
    return 0


# ---------------------------------------------------------------- selftest


def selftest() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))

    me = SUB_ENGEL_BOT_ID
    engel = ENGEL_MAIN_BOT_ID
    ch = "1148755186752430163"
    now = time.time()

    _PEER_TURNS.clear()
    _LAST_PEER_TURN_AT.clear()

    ok, _ = decide(author_id=me, author_is_bot=True, channel_id=ch, content="hi",
                   mentioned_ids=set(), my_id=me, now=now)
    check("never answers itself", ok is False)

    ok, _ = decide(author_id="DISCORD_OWNER_USER_ID", author_is_bot=False, channel_id=ch,
                   content="just chatting with someone else", mentioned_ids=set(),
                   my_id=me, now=now)
    check("ignores unrelated human chatter", ok is False)

    ok, _ = decide(
        author_id="189914577100603392",
        author_is_bot=False,
        channel_id=ch,
        content=(
            "Hey Lokal from VantaMoth Labs here, just curious what you guys have "
            "been working on at Engel AI Labs? Let's collaborate sometime in the future?"
        ),
        mentioned_ids=set(),
        my_id=me,
        now=now,
    )
    check("does not steal Engel AI Labs guest collab", ok is False)
    check(
        "Chase stays Chase/Lokal",
        speaker_label("189914577100603392", "Lokal") == "Chase/Lokal",
    )

    ok, _ = decide(
        author_id="189914577100603392",
        author_is_bot=False,
        channel_id=ch,
        content="hey Sub-Engel let's collaborate",
        mentioned_ids=set(),
        my_id=me,
        now=now,
    )
    check("answers a guest addressing Sub-Engel through the guest chat gate", ok is True)

    ok, reason = decide(
        author_id="DISCORD_OWNER_USER_ID",
        author_is_bot=False,
        channel_id=ch,
        content="I want you to talk with Sub-Engel",
        mentioned_ids=set(),
        my_id=me,
        now=now,
    )
    check("does not steal an Engel turn that only names Sub-Engel", ok is False)
    ok, reason = decide(
        author_id="DISCORD_OWNER_USER_ID",
        author_is_bot=False,
        channel_id="999888777666555444",
        content="Every introduce your self's and your role",
        mentioned_ids=set(),
        my_id=me,
        now=now,
    )
    check("answers a room roll call even outside the home channel", ok is True)
    intro = build_reply("Every introduce your self's and your role", "Joshua")
    check("roll-call intro is Sub-Engel", intro.startswith("I'm Sub-Engel"))
    check("roll-call intro does not claim Joshua", "I am Joshua" not in intro and "I'm Joshua" not in intro)
    later = type("M", (), {})()
    later.author = type("A", (), {"id": engel})()
    later.reference = type("R", (), {"resolved": type("X", (), {"id": "9"})(), "message_id": "9"})()
    check(
        "stays silent when Engel already answered the line",
        other_mouth_already_answered(me, "9", [later]) is True,
    )
    check("pause-read helper exists", callable(pause_and_read_conversation))

    ok, _ = decide(author_id="DISCORD_OWNER_USER_ID", author_is_bot=False, channel_id=ch,
                   content="hey sub-engel status please", mentioned_ids=set(),
                   my_id=me, now=now)
    check("answers a human name summon", ok is True)

    ok, _ = decide(author_id="DISCORD_OWNER_USER_ID", author_is_bot=False, channel_id=ch,
                   content="hello", mentioned_ids={me}, my_id=me, now=now)
    check("answers a human @mention", ok is True)

    ok, _ = decide(author_id="999999999999999999", author_is_bot=True, channel_id=ch,
                   content="sub-engel are you there", mentioned_ids={me}, my_id=me, now=now)
    check("ignores a non-whitelisted bot", ok is False)

    ok, _ = decide(author_id=engel, author_is_bot=True, channel_id=ch,
                   content="Joshua, here is your answer", mentioned_ids=set(),
                   my_id=me, now=now)
    check("ignores peer talking to a human", ok is False)

    ok, _ = decide(author_id=engel, author_is_bot=True, channel_id=ch,
                   content="Sub-Engel, what is your pairing state?", mentioned_ids=set(),
                   my_id=me, now=now)
    check("answers peer addressing it by name", ok is True)

    # Open exchange continues without re-addressing, then the cap bites.
    _PEER_TURNS.clear()
    _LAST_PEER_TURN_AT.clear()
    note_peer_turn(ch, now)
    ok, _ = decide(author_id=engel, author_is_bot=True, channel_id=ch, content="understood",
                   mentioned_ids=set(), my_id=me, now=now + 5)
    check("continues an open exchange", ok is True)

    ok, _ = decide(author_id=engel, author_is_bot=True, channel_id=ch, content="understood",
                   mentioned_ids=set(), my_id=me, now=now + EXCHANGE_WINDOW_SECONDS + 60)
    check("stops after the exchange window lapses", ok is False)

    _PEER_TURNS.clear()
    _LAST_PEER_TURN_AT.clear()
    _WORK_COLLAB.clear()
    _PEER_TURNS[ch] = PEER_MAX_TURNS
    ok, reason = decide(author_id=engel, author_is_bot=True, channel_id=ch,
                        content="sub-engel still there?", mentioned_ids={me},
                        my_id=me, now=now + 1)
    check("peer turn cap stops the loop", ok is False and "cap" in reason)

    note_human_message(ch, "hello Sub-Engel")
    ok, _ = decide(author_id=engel, author_is_bot=True, channel_id=ch,
                   content="sub-engel still there?", mentioned_ids={me}, my_id=me, now=now + 2)
    check("a human message re-arms the exchange", ok is True)

    note_human_message(ch, "Start researching cost saving options for the Dell r730xd")
    _PEER_TURNS[ch] = PEER_MAX_TURNS + 5
    ok, reason = decide(
        author_id=engel,
        author_is_bot=True,
        channel_id=ch,
        content="Research desk found three RAM options.",
        mentioned_ids=set(),
        my_id=me,
        now=now + 3,
    )
    check("open work collab keeps going past casual turn cap", ok is True and "work" in reason)
    note_human_message(ch, "we're done")
    _PEER_TURNS[ch] = PEER_MAX_TURNS
    ok, reason = decide(
        author_id=engel,
        author_is_bot=True,
        channel_id=ch,
        content="Research desk found three RAM options.",
        mentioned_ids=set(),
        my_id=me,
        now=now + 4,
    )
    check("finished work restores the casual turn cap", ok is False and "cap" in reason)

    # Content honesty
    text = build_reply("what is your pairing state?", "Engel")
    check("pairing answer is not the old canned line", "Standing by." not in text)
    check("pairing answer mentions pairing", "pair" in text.lower())

    long_reply = chunk("x" * 5000)
    check("long replies are chunked under the discord limit",
          all(len(part) <= 1900 for part in long_reply) and len(long_reply) > 1)

    looped = (
        "Graph-loop engineer: engine.self_learn. Next I take the following CODE gap "
        "on this Windows node.\n"
        "Graph-loop engineer: engine.self_learn. Next I take the following CODE gap "
        "on this Windows node."
    )
    check("repeated CODE-gap lines collapse to one",
          collapse_repeated_sentences(looped).count("engine.self_learn") == 1)
    check("self-learn loop is not sent as brain spam",
          "will not loop engine.self_learn" in build_reply(looped, "Engel").lower())

    argv = grok_brain_argv("hello", continue_session=True)
    joined = " ".join(argv)
    check("grok brain is chat-only", "--max-turns" in argv and "1" in argv)
    check("grok brain cannot shell or write", "run_terminal_command" in joined and "search_replace" in joined)
    check("grok brain uses a dedicated cwd", BRAIN_CWD in argv)

    _PEER_TURNS.clear()
    _LAST_PEER_TURN_AT.clear()

    passed = sum(1 for _, good in checks if good)
    for name, good in checks:
        print(f"  [{'PASS' if good else 'FAIL'}] {name}")
    print(f"\n{passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run offline gate checks")
    parser.add_argument("--report", action="store_true", help="print the node report and exit")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.selftest:
        return selftest()
    if args.report:
        print(node_report())
        return 0
    return run_bot()


if __name__ == "__main__":
    raise SystemExit(main())
