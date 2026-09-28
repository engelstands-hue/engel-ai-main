#!/usr/bin/env python3
"""Management module for the Engel Discord desk fleet.

Each desk process asks this module whether it understands a room line and
whether it may speak without being summoned. The score matches the initiative
matrix: sentiment, topic relevance, and inactivity, combined against a
threshold. Cooldown negates the margin so a hot score still stays quiet.
Josh silence always wins. This module does not post, does not call providers,
and does not start its own loop.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any


DESK_IDS = (
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
)
UI_PATH = Path(__file__).resolve().parent / "engel_discord_desk_manager_ui.html"
ACTIVATION_THRESHOLD = float(os.environ.get("ENGEL_DESK_INITIATIVE_THRESHOLD", "61") or "61")
SENTIMENT_WEIGHT = float(os.environ.get("ENGEL_DESK_SENTIMENT_WEIGHT", "0.20") or "0.20")
TOPIC_WEIGHT = float(os.environ.get("ENGEL_DESK_TOPIC_WEIGHT", "0.60") or "0.60")
INACTIVITY_WEIGHT = float(os.environ.get("ENGEL_DESK_INACTIVITY_WEIGHT", "0.20") or "0.20")
COOLDOWN_SECONDS = float(os.environ.get("ENGEL_DESK_INITIATIVE_COOLDOWN_SECONDS", "900") or "900")
INACTIVITY_FULL_SECONDS = float(os.environ.get("ENGEL_DESK_INACTIVITY_FULL_SECONDS", "1800") or "1800")
ROOM_MEMORY_LINES = 12

_POSITIVE = ("good", "thanks", "thank you", "yes", "great", "works", "nice", "please", "help")
_NEGATIVE = ("broken", "error", "fail", "stuck", "bug", "wrong", "down", "crash", "hate")
_ASK = ("?", "what", "how", "why", "can you", "should we", "need")


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def manager_state_path(run_dir: Path) -> Path:
    return Path(run_dir) / "desk_manager_state.json"


def _charter_path() -> Path:
    env = str(os.environ.get("ENGEL_DISCORD_CHARTER_PATH") or "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent.parent / "memory" / "ENGEL_DISCORD_DESK_CHARTERS_V1.json"
    if here.is_file():
        return here
    return Path("/opt/engel/memory/ENGEL_DISCORD_DESK_CHARTERS_V1.json")


def load_desk_charter(desk_name: str) -> dict[str, Any]:
    desk = str(desk_name or "").strip().lower()
    try:
        data = json.loads(_charter_path().read_text(encoding="utf-8"))
    except Exception:
        return {}
    mouths = data.get("mouths") if isinstance(data, dict) else None
    row = mouths.get(desk) if isinstance(mouths, dict) else None
    return row if isinstance(row, dict) else {}


def desk_markers(desk_name: str) -> tuple[str, ...]:
    row = load_desk_charter(desk_name)
    raw = row.get("markers") if isinstance(row.get("markers"), list) else []
    markers = [str(item).strip().lower() for item in raw if str(item).strip()]
    addressed = str(row.get("addressed_as") or "").strip().lower()
    if addressed:
        markers.append(addressed)
    return tuple(dict.fromkeys(markers))


def load_manager_state(run_dir: Path) -> dict[str, Any]:
    path = manager_state_path(run_dir)
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def save_manager_state(run_dir: Path, payload: dict[str, Any]) -> None:
    path = manager_state_path(run_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        return


def _owner_silenced(run_dir: Path) -> bool:
    path = Path(run_dir) / "proactive_state.json"
    try:
        if not path.is_file():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict) or not data.get("owner_silenced"):
        return False
    until = float(data.get("owner_silence_until_unix") or 0.0)
    return until <= 0.0 or time.time() < until


def note_room_line(
    run_dir: Path,
    *,
    author: str,
    text: str,
    author_kind: str = "peer",
) -> dict[str, Any]:
    """Remember a line this desk read, including other bots and Josh."""
    state = load_manager_state(run_dir)
    lines = state.get("room_lines")
    if not isinstance(lines, list):
        lines = []
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()[:500]
    if not cleaned:
        return state
    now = time.time()
    lines.append(
        {
            "at_unix": now,
            "author": str(author or "")[:80],
            "author_kind": str(author_kind or "peer")[:20],
            "text": cleaned,
        }
    )
    state["room_lines"] = lines[-ROOM_MEMORY_LINES:]
    if author_kind == "human":
        state["last_human_unix"] = now
    state["last_line_unix"] = now
    state["updated_at_utc"] = _iso_now()
    save_manager_state(run_dir, state)
    return state


def note_spoke(run_dir: Path, *, reason: str) -> None:
    state = load_manager_state(run_dir)
    state["last_spoke_unix"] = time.time()
    state["last_spoke_reason"] = str(reason or "initiative")[:80]
    state["updated_at_utc"] = _iso_now()
    save_manager_state(run_dir, state)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _sentiment(text: str) -> float:
    low = str(text or "").casefold()
    if not low:
        return 0.0
    pos = sum(1 for word in _POSITIVE if word in low)
    neg = sum(1 for word in _NEGATIVE if word in low)
    ask = sum(1 for word in _ASK if word in low)
    raw = 0.35 + (0.2 * pos) + (0.15 * ask) - (0.1 * neg)
    return _clamp01(raw)


def _topic_relevance(desk_name: str, text: str) -> float:
    low = str(text or "").casefold()
    markers = desk_markers(desk_name)
    if not low or not markers:
        return 0.0
    hits = sum(1 for marker in markers if marker and marker in low)
    return _clamp01(hits / 3.0)


def _inactivity(state: dict[str, Any], now: float) -> float:
    last_human = float(state.get("last_human_unix") or 0.0)
    if last_human <= 0.0:
        return 0.0
    quiet = max(0.0, now - last_human)
    full = max(60.0, INACTIVITY_FULL_SECONDS)
    return _clamp01(quiet / full)


def _cooldown_left(state: dict[str, Any], now: float) -> float:
    last = float(state.get("last_spoke_unix") or 0.0)
    if last <= 0.0:
        return 0.0
    return max(0.0, COOLDOWN_SECONDS - (now - last))


def evaluate_initiative(
    desk_name: str,
    run_dir: Path,
    text: str = "",
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Score one desk. Speak only when the margin is positive and cooldown is clear."""
    desk = str(desk_name or "").strip().lower()
    state = load_manager_state(run_dir)
    clock = float(now if now is not None else time.time())
    recent = state.get("room_lines") if isinstance(state.get("room_lines"), list) else []
    remembered = "\n".join(str(row.get("text") or "") for row in recent if isinstance(row, dict))
    blob = (remembered + "\n" + str(text or "")).strip()
    sentiment = _sentiment(blob)
    topic = _topic_relevance(desk, blob)
    inactivity = _inactivity(state, clock)
    weight_sum = SENTIMENT_WEIGHT + TOPIC_WEIGHT + INACTIVITY_WEIGHT
    scale = weight_sum if weight_sum > 0 else 1.0
    combined = (
        (sentiment * SENTIMENT_WEIGHT) + (topic * TOPIC_WEIGHT) + (inactivity * INACTIVITY_WEIGHT)
    ) / scale
    score = round(combined * 100.0, 1)
    raw_margin = round(score - ACTIVATION_THRESHOLD, 1)
    silenced = _owner_silenced(run_dir)
    cooling = _cooldown_left(state, clock)
    if silenced:
        phase = "OwnerSilence"
        margin = -abs(raw_margin) if raw_margin else -ACTIVATION_THRESHOLD
        speak = False
    elif cooling > 0.0:
        phase = "Cooldown"
        margin = -abs(raw_margin) if raw_margin else -1.0
        speak = False
    elif raw_margin >= 0.0 and topic > 0.0:
        phase = "Activate"
        margin = raw_margin
        speak = True
    else:
        phase = "Hold"
        margin = raw_margin
        speak = False
    return {
        "schema": "engel_discord_desk_initiative_v1",
        "desk": desk,
        "addressed_as": str(load_desk_charter(desk).get("addressed_as") or desk),
        "sentiment_shift": round(sentiment, 2),
        "topic_relevance": round(topic, 2),
        "inactivity_interval": round(inactivity, 2),
        "sentiment_weight": SENTIMENT_WEIGHT,
        "topic_relevance_weight": TOPIC_WEIGHT,
        "inactivity_weight": INACTIVITY_WEIGHT,
        "initiative_score": score,
        "activation_threshold": ACTIVATION_THRESHOLD,
        "activation_margin": margin,
        "evaluation_state": phase,
        "speak": speak,
        "cooldown_seconds_left": int(cooling),
        "understands_text": topic >= (1.0 / 3.0),
        "room_lines": len(recent),
    }


def allow_unsummoned_reply(desk_name: str, run_dir: Path, text: str) -> bool:
    """True when this desk understands another bot or Josh without an @mention."""
    decision = evaluate_initiative(desk_name, run_dir, text)
    if decision.get("evaluation_state") == "OwnerSilence":
        return False
    if decision.get("evaluation_state") == "Cooldown":
        return False
    return bool(decision.get("understands_text"))


def initiative_open(desk_name: str, run_dir: Path) -> tuple[bool, dict[str, Any]]:
    """True when the desk may start a turn without being spoken to."""
    decision = evaluate_initiative(desk_name, run_dir, "")
    return bool(decision.get("speak")), decision


def render_manager_status(desk_name: str, run_dir: Path) -> str:
    decision = evaluate_initiative(desk_name, run_dir, "")
    lines = [
        f"Engel desk manager — {decision.get('addressed_as')}",
        f"Initiative score: {decision.get('initiative_score')}",
        f"Evaluation state: {decision.get('evaluation_state')}",
        f"Activation margin: {decision.get('activation_margin')}",
        f"Activation threshold: {decision.get('activation_threshold')}%",
        f"Sentiment {decision.get('sentiment_shift')} weight {decision.get('sentiment_weight')}",
        f"Topic relevance {decision.get('topic_relevance')} weight {decision.get('topic_relevance_weight')}",
        f"Inactivity {decision.get('inactivity_interval')} weight {decision.get('inactivity_weight')}",
        f"Understands the room: {decision.get('understands_text')}",
        f"May speak unprompted: {decision.get('speak')}",
        "Authority: Josh > Guardian > Engel/runtime. Silence still stops every desk.",
    ]
    return "\n".join(lines) + "\n"
