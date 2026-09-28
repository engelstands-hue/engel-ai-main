#!/usr/bin/env python3
"""Lock the 2026-08-16 chat-starvation MoE skip.

Discord peer chatter and prefer_fast_local_chat callers must not auto-route
onto the sparse MoE expert lane. Explicit operator selection still wins.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "tools" / "engel_main_server_chat_http_service.py"
DISCORD = ROOT / "tools" / "engel_discord_bridge.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    service = SERVICE.read_text(encoding="utf-8")
    discord = DISCORD.read_text(encoding="utf-8")
    skip_reason = (
        "caller requested fast local chat; sparse MoE auto-route skipped"
    )
    require(skip_reason in service, "MoE fast-chat skip reason missing")
    require(
        'request.get("prefer_fast_local_chat") is True' in service,
        "prefer_fast_local_chat skip missing",
    )
    require(
        '.casefold() == "discord"' in service
        or '== "discord"' in service.split(skip_reason, 1)[0][-400:],
        "discord source skip missing next to the fast-chat reason",
    )
    require(
        "operator explicitly selected CT246 sparse MoE" in service,
        "explicit MoE selection must still win",
    )
    require(
        service.find("operator explicitly selected CT246 sparse MoE")
        < service.find(skip_reason),
        "explicit MoE selection must be checked before the fast-chat skip",
    )
    require("prefer_fast_local_chat" in discord, "Discord bridge must request the fast lane")
    require(
        '"prefer_fast_local_chat": bool(peer_turn)' in discord,
        "Josh Discord turns must not force the tiny fast lane",
    )
    require(
        '"discord_owner_turn": owner_turn' in discord,
        "Josh Discord turns must mark the full CT246 brain",
    )
    require("_is_discord_owner_turn" in service, "chat service must recognize Josh Discord turns")
    require(
        "not _is_discord_owner_turn(request)" in service,
        "MoE skip must not blanket-block Josh Discord turns",
    )
    require(
        '"allow_provider_fallback": owner_turn' in discord,
        "Josh Discord turns must enable existing provider pipes after local failure",
    )
    require(
        '"automatic_provider_after_local_failure_only": owner_turn' in discord,
        "Josh Discord provider pipes must stay behind a proved local failure",
    )
    require(
        'decision["discord_owner_full_brain"] = "large_local_model"' in service,
        "mode-gate reflex must not keep Josh Discord on the 0.5B lane",
    )
    require(
        "_is_discord_owner_turn(request) and _prompt_requires_large_local_reasoning(prompt)"
        in service,
        "Josh Discord reasoning turns must be able to use the 14B lane",
    )
    require(
        "timeout = max(timeout, 90)" in service,
        "Josh Discord must keep the 90s model timeout instead of the 45s cap",
    )
    require(
        "apply_standing_chat_brain(payload, owner_turn=owner_turn)" in discord,
        "Josh Discord must apply the Cosmic Swarm standing brain",
    )
    require("peer_message_is_substantive" in discord, "peer GIF/ack filter missing")
    print("PASS verify_engel_moe_fast_chat_skip")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL verify_engel_moe_fast_chat_skip: {exc}")
        raise SystemExit(2) from exc
