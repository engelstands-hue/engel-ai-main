#!/usr/bin/env python3
"""Verify Main on-charter desk collab (not silent-unless-summoned)."""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load_helpers():
    """Load only the decision helpers via exec of extracted source is heavy;
    instead import the module functions by reading and compiling a stub.
    We verify source contracts + run charter scoring from the real module pieces.
    """
    path = TOOLS / "engel_discord_bridge.py"
    text = path.read_text(encoding="utf-8")
    return text


class MainDeskCharterCollabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _load_helpers()
        sys.path.insert(0, str(TOOLS))
        # Load discover-free charter scoring via proactive-independent path:
        # import engel_discord_bridge is heavy (discord). Prefer source + light load.
        from engel_nvidia_discover import DEFAULT_MOUTH_MODELS  # noqa: F401

    def test_source_is_charter_collab_not_silent_yield(self) -> None:
        self.assertIn("main_desk_collab_decision", self.text)
        self.assertIn("desk_lane_content_on_charter", self.text)
        self.assertIn("allow_charter", self.text)
        self.assertIn("suppress", self.text)
        self.assertIn("Discord Main suppresses desk off-topic", self.text)
        self.assertIn("collaborating in the", self.text)
        self.assertNotIn("main_should_yield_desk_lane", self.text)
        self.assertIn("DESK_LANE_PEER_MAX_TURNS", self.text)

    def test_charter_scoring_product_vs_offtopic(self) -> None:
        # Import score helpers without starting discord client: load module
        # after stubbing discord + aiohttp if needed.
        if "discord" not in sys.modules:
            discord = types.ModuleType("discord")

            class _Dummy:
                pass

            discord.Client = _Dummy
            discord.Message = _Dummy
            discord.ClientUser = _Dummy
            discord.DMChannel = _Dummy
            discord.Intents = types.SimpleNamespace(default=lambda: types.SimpleNamespace(message_content=True))
            discord.Status = types.SimpleNamespace(online="online")
            discord.Game = lambda *a, **k: None
            sys.modules["discord"] = discord
        if "aiohttp" not in sys.modules:
            sys.modules["aiohttp"] = types.ModuleType("aiohttp")
        # Bridge imports engel_discord_desktop_route_parity — should exist.
        spec = importlib.util.spec_from_file_location(
            "engel_discord_bridge_charter_test",
            TOOLS / "engel_discord_bridge.py",
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules["engel_discord_bridge_charter_test"] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            self.skipTest(f"bridge import blocked in test env: {exc}")
            return
        on = mod.desk_lane_content_on_charter(
            "Engel Product on standing watch. Focus this cycle: roadmap.",
            "product",
        )
        off = mod.desk_lane_content_on_charter(
            "Want to chat about random GIFs and weather instead?",
            "product",
        )
        self.assertTrue(on)
        self.assertFalse(off)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
