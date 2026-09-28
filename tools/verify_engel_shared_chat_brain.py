#!/usr/bin/env python3
"""Cosmic Swarm chat and Josh Discord share one standing brain."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from engel_discord_desktop_route_parity import (  # noqa: E402
    apply_standing_chat_brain,
    standing_chat_brain,
)


DISCORD = ROOT / "tools" / "engel_discord_bridge.py"
SERVICE = ROOT / "tools" / "engel_main_server_chat_http_service.py"
FLUTTER = ROOT / "engel_flutter_main" / "lib" / "main.dart"
SHARED = ROOT / "memory" / "personality" / "ENGEL_SHARED_CHAT_BRAIN.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    discord = DISCORD.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")
    flutter = FLUTTER.read_text(encoding="utf-8")
    shared = SHARED.read_text(encoding="utf-8")
    require("apply_standing_chat_brain(payload, owner_turn=owner_turn)" in discord, "Discord must apply the standing Cosmic Swarm brain")
    require("apply_standing_chat_brain(request, owner_turn=True)" in service, "chat service must apply standing brain on Josh Discord")
    require("remember_desktop_standing_chat_brain(request)" in service, "desktop chat must remember the standing pipe for Discord")
    require('"/brain/standing"' in service, "standing brain HTTP path missing")
    require("engelMainStandingBrainUrl" in flutter, "Cosmic Swarm must publish standing brain to CT246")
    require("_publishStandingChatBrain" in flutter, "Cosmic Swarm standing-brain publisher missing")
    require("engel_shared_chat_brain_v1" in shared, "shared brain file schema missing")
    require("grok-4.6" in shared or "auto-best" in shared, "shared brain must name the standing model")
    require("peers_use_fast_local" in shared, "Sub-Engel/future subs must stay on the fast lane")
    require("def _discord_room_memory(" in service, "chat service must keep Discord room context")
    require("def _prompt_with_discord_room(" in service, "provider path must see Discord room context")
    require('"prefer_fast_local_chat": bool(peer_turn)' in discord, "only peer bots stay on the tiny Discord lane")

    owner = apply_standing_chat_brain(
        {"source": "discord", "prefer_fast_local_chat": True, "metadata": {}},
        owner_turn=True,
    )
    standing = standing_chat_brain()
    require(owner.get("prefer_fast_local_chat") is False, "Josh Discord must not stay on the tiny lane")
    require(owner.get("discord_owner_turn") is True, "Josh Discord must mark owner brain")
    require(owner["metadata"].get("shared_engel_brain") is True, "Josh Discord must stamp the shared brain")
    if standing.get("force") is True:
        require(owner.get("force_provider") is True, "Josh Discord must follow the Cosmic Swarm provider pipe")
        require(owner.get("provider") == standing.get("selected_chat_provider"), "Josh Discord provider must match Cosmic Swarm")
    peer = apply_standing_chat_brain(
        {"source": "discord", "prefer_fast_local_chat": True, "metadata": {}},
        owner_turn=False,
    )
    require(peer.get("force_provider") is not True, "Sub-Engel must not steal the owner standing pipe")
    require(peer.get("prefer_fast_local_chat") is True, "Sub-Engel/future subs stay on the fast lane")
    print("PASS verify_engel_shared_chat_brain")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL verify_engel_shared_chat_brain: {exc}")
        raise SystemExit(2) from exc
