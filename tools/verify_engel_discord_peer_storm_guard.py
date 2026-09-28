#!/usr/bin/env python3
"""Verify Discord desk peer-storm guards (7-bridge cascade hardening)."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
BRIDGE = TOOLS / "engel_discord_bridge.py"


def _stub_discord() -> None:
    if "discord" in sys.modules:
        return
    discord = types.ModuleType("discord")

    class _Dummy:
        pass

    discord.Client = _Dummy
    discord.Message = _Dummy
    discord.ClientUser = _Dummy
    discord.DMChannel = _Dummy
    discord.Intents = types.SimpleNamespace(
        default=lambda: types.SimpleNamespace(message_content=True)
    )
    discord.Status = types.SimpleNamespace(online="online")
    discord.Game = lambda *a, **k: None
    sys.modules["discord"] = discord
    if "aiohttp" not in sys.modules:
        sys.modules["aiohttp"] = types.ModuleType("aiohttp")


class PeerStormGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = BRIDGE.read_text(encoding="utf-8")

    def test_source_needles(self) -> None:
        for needle in (
            "DESK_PEER_MAX_TURNS",
            "DESK_PEER_COOLDOWN_SECONDS",
            "PEER_STORM_WINDOW_SECONDS",
            "PEER_STORM_BOT_MSG_THRESHOLD",
            "channel_peer_storm_active",
            "try_claim_peer_message",
            "standing_watch_loop_text",
            "WORK_COLLAB_MAX_TURNS",
            "peer-storm suppress",
            "standing-watch loop suppress",
            "build_desk_colony_status_pack",
            "discord_local_first",
            "read_only_device_status_lines",
            # Preserve prior contracts
            "main_desk_collab_decision",
            "owner_requested_full_quiet",
            "finalize_discord_public_reply",
            "discord_reply_looks_like_prompt_leak",
        ):
            self.assertIn(needle, self.text, needle)
        self.assertNotIn("return 10_000", self.text)
        self.assertIn('"32"', self.text)  # work collab default
        self.assertIn('"4"', self.text)  # peer max turns default
        self.assertIn('metadata["discord_nvidia_first"] = False', self.text)
        self.assertIn('metadata["discord_local_first"] = True', self.text)

    def test_colony_status_pack_readonly(self) -> None:
        _stub_discord()
        name = "engel_discord_bridge_colony_status_test"
        if name in sys.modules:
            del sys.modules[name]
        spec = importlib.util.spec_from_file_location(name, BRIDGE)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"bridge import blocked: {exc}")
            return
        mod.DESK_NAME = "ops"
        pack = mod.build_desk_colony_status_pack("android workers status please", force=True)
        self.assertIn("ENGEL COLONY STATUS", pack)
        self.assertIn("read-only", pack.casefold())
        self.assertTrue(mod.prompt_wants_colony_status("check android worker alpha"))
        self.assertTrue(mod.desk_asks_main("ask Engel AI Main for help"))
        payload = {
            "prefer_fast_local_chat": True,
            "metadata": {},
        }
        mod.apply_discord_mouth_nvidia_brain(payload, desk_name="main", prompt="hello")
        self.assertFalse(payload.get("force_provider"))
        self.assertTrue(payload.get("automatic_provider_after_local_failure_only"))
        self.assertEqual(payload["metadata"].get("discord_nvidia_first"), False)
        self.assertEqual(payload["metadata"].get("discord_local_first"), True)

    def test_runtime_caps_and_claim(self) -> None:
        _stub_discord()
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["ENGEL_DISCORD_STORM_DIR"] = tmp
            # Force fresh import under temp storm dir.
            name = "engel_discord_bridge_peer_storm_test"
            if name in sys.modules:
                del sys.modules[name]
            spec = importlib.util.spec_from_file_location(name, BRIDGE)
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            try:
                spec.loader.exec_module(mod)
            except Exception as exc:  # noqa: BLE001
                self.skipTest(f"bridge import blocked: {exc}")
                return

            self.assertEqual(mod.PEER_MAX_TURNS, 4)
            self.assertEqual(mod.WORK_COLLAB_MAX_TURNS, 32)
            self.assertEqual(mod.DESK_PEER_MAX_TURNS, 2)
            self.assertEqual(mod.HOUSE_PEER_MAX_TURNS_DEFAULT, 6)
            self.assertLessEqual(mod.peer_max_turns_for("x"), 32)
            self.assertTrue(
                mod.standing_watch_loop_text(
                    "Engel Product on standing watch. Focus this cycle: roadmap."
                )
            )
            self.assertFalse(
                mod.standing_watch_loop_text("What is the product roadmap for Q3?")
            )

            class FakeMsg:
                def __init__(self, mid: str) -> None:
                    self.id = mid
                    self.channel = types.SimpleNamespace(id="chan1")
                    self.content = "hello"
                    self.author = types.SimpleNamespace(id="1", bot=True)

            ok1, reason1 = mod.try_claim_peer_message(FakeMsg("m1"))
            ok2, reason2 = mod.try_claim_peer_message(FakeMsg("m1"))
            self.assertTrue(ok1, reason1)
            # Same mouth reclaim or first claim wins; second call from same process
            # may reclaim. Simulate other mouth by changing mouth id.
            mod.DESK_NAME = "sales"
            ok3, reason3 = mod.try_claim_peer_message(FakeMsg("m1"))
            self.assertFalse(ok3, reason3)
            self.assertIn("lost_to", reason3)

            mod.note_channel_bot_sighting("stormchan")
            mod.note_channel_bot_sighting("stormchan")
            mod.note_channel_bot_sighting("stormchan")
            mod.note_channel_bot_sighting("stormchan")
            self.assertTrue(mod.channel_peer_storm_active("stormchan"))


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
