#!/usr/bin/env python3
"""Verify owner stop silences Discord proactive standing-watch posts."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class OwnerQuietProactiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.proactive = _load(
            "engel_discord_desk_proactive_under_test",
            TOOLS / "engel_discord_desk_proactive.py",
        )

    def test_stop_phrases_block_should_post(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self.proactive.note_owner_silence(run_dir, reason="owner_stop", channel_id="1")
            silenced, reason = self.proactive.owner_silence_active(run_dir)
            self.assertTrue(silenced)
            self.assertIn("owner_stop", reason)
            # Env may or may not enable proactive; silence must still win when enabled.
            import os

            os.environ["ENGEL_DISCORD_PROACTIVE"] = "1"
            ok, status = self.proactive.should_post(
                desk_name="research",
                run_dir=run_dir,
                channel_id="123",
                token="fake",
                force=True,
            )
            self.assertFalse(ok)
            self.assertIn("owner silenced", status)

    def test_resume_clears_silence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self.proactive.note_owner_silence(run_dir, reason="owner_stop")
            self.proactive.clear_owner_silence(run_dir, reason="owner_resume")
            silenced, _ = self.proactive.owner_silence_active(run_dir)
            self.assertFalse(silenced)

    def test_bridge_owner_quiet_helpers(self) -> None:
        # Import bridge helpers without connecting Discord (module import is heavy
        # but must stay offline and must not require BOT_TOKEN).
        bridge_path = TOOLS / "engel_discord_bridge.py"
        text = bridge_path.read_text(encoding="utf-8")
        self.assertIn("owner_requested_full_quiet", text)
        self.assertIn("apply_owner_full_quiet", text)
        self.assertIn("note_proactive_owner_silence", text)
        self.assertIn("OWNER_QUIET_ACK_REPLY", text)
        # Lightweight phrase checks without importing the full bridge.
        from engel_discord_desk_proactive import note_owner_silence, owner_silence_active  # noqa: F401

        sys.path.insert(0, str(TOOLS))
        # Parse exact silence set from source for regression without full import.
        self.assertIn('"stop"', text)
        self.assertIn('"quiet"', text)
        self.assertIn('"enough"', text)
        self.assertIn('"done"', text)
        self.assertIn('"finished"', text)
        self.assertIn("owner full quiet", text)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
