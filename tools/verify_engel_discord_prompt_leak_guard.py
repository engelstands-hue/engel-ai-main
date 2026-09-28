#!/usr/bin/env python3
"""Verify Discord prompt-leak replies are blocked before send."""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

LEAK_SAMPLE = """@Engel Sales We are in a Discord conversation. The sender is Engel Sales.
Current Discord sender (locked, machine-read):
sender_id: 1545931615673385020
resolved_actor: engel_desk_sales
authority_level: peer
identity_rule: sender_id is ground truth.
One or two sentences, then a relevant GIF and one library favicon. Rotate the favicon library.
If Joshua attached a still image plus_hex.png, look at it.
NVIDIA NIM is preferred. Do not pile onto a line another mouth already answered.
Answer as Engel AI Main in one real Discord chat turn.
Recent Discord context:
...lots of meta...
Current user message:
hello
"""

GOOD_SAMPLE = (
    "I'm on the sales lane — if you want a clean pitch for Engel AI Labs, "
    "tell me the audience and I'll frame the value prop in two lines."
)


class DiscordPromptLeakGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if "discord" not in sys.modules:
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
            discord.File = _Dummy
            sys.modules["discord"] = discord
        if "aiohttp" not in sys.modules:
            sys.modules["aiohttp"] = types.ModuleType("aiohttp")
        sys.path.insert(0, str(TOOLS))
        spec = importlib.util.spec_from_file_location(
            "engel_discord_bridge_leak_test",
            TOOLS / "engel_discord_bridge.py",
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules["engel_discord_bridge_leak_test"] = mod
        spec.loader.exec_module(mod)
        cls.b = mod

    def test_leak_sample_detected(self) -> None:
        self.assertTrue(self.b.discord_reply_looks_like_prompt_leak(LEAK_SAMPLE))

    def test_good_sales_answer_passes(self) -> None:
        self.assertFalse(self.b.discord_reply_looks_like_prompt_leak(GOOD_SAMPLE))
        out = self.b.finalize_discord_public_reply(GOOD_SAMPLE)
        self.assertEqual(out, GOOD_SAMPLE)

    def test_leak_is_replaced_not_posted(self) -> None:
        out = self.b.finalize_discord_public_reply(LEAK_SAMPLE)
        self.assertEqual(out, self.b.DISCORD_LEAK_FALLBACK_REPLY)
        self.assertNotIn("We are in a Discord conversation", out)
        self.assertNotIn("plus_hex", out.casefold())
        self.assertNotIn("favicon", out.casefold())

    def test_sanitize_blocks_leak(self) -> None:
        out = self.b.sanitize_discord_public_reply(LEAK_SAMPLE)
        self.assertEqual(out, self.b.DISCORD_LEAK_FALLBACK_REPLY)

    def test_source_wires_finalize(self) -> None:
        text = (TOOLS / "engel_discord_bridge.py").read_text(encoding="utf-8")
        self.assertIn("def finalize_discord_public_reply(", text)
        self.assertIn("discord_reply_looks_like_prompt_leak", text)
        self.assertIn("Blocked Discord prompt-leak", text)
        self.assertIn("nonsense or prompt-leak reply suppressed", text)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
