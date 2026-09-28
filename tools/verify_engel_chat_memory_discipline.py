#!/usr/bin/env python3
"""Verify engel-main-chat memory/thread discipline (CT246 OOM guard)."""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
CHAT = TOOLS / "engel_main_server_chat_http_service.py"
WATCHDOG = TOOLS / "engel_chat_health_watchdog.py"


class ChatMemoryDisciplineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.chat = CHAT.read_text(encoding="utf-8")
        cls.watch = WATCHDOG.read_text(encoding="utf-8")

    def test_chat_source_has_bounds(self) -> None:
        for needle in (
            "BoundedThreadingHTTPServer",
            "ENGEL_CHAT_HTTP_MAX_THREADS",
            "ENGEL_CHAT_MAX_IN_FLIGHT",
            "_chat_admission_allowed",
            "_acquire_chat_slot",
            "_process_resource_snapshot",
            "resource_pressure",
            "chat-resource-growth",
        ):
            self.assertIn(needle, self.chat, needle)

    def test_chat_parses(self) -> None:
        ast.parse(self.chat)

    def test_defaults_are_finite(self) -> None:
        self.assertIn('"64"', self.chat)
        self.assertIn('"4"', self.chat)
        self.assertIn('"200"', self.chat)

    def test_watchdog_pressure_restart(self) -> None:
        for needle in (
            "should_restart_for_pressure",
            "RSS_ANON_HARD_KB",
            "THREADS_HARD",
            "rss_anon_hard",
            "threads_hard",
        ):
            self.assertIn(needle, self.watch, needle)

    def test_watchdog_selftest(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "engel_chat_health_watchdog_verify", WATCHDOG
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.selftest(), 0)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
