#!/usr/bin/env python3
"""Verify smart standing-watch + distinct per-desk SLM lanes."""
from __future__ import annotations

import importlib.util
import os
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


EXPECTED_DESK_MODELS = {
    "research": "nvidia/nemotron-3-super-120b-a12b",
    "product": "nvidia/nemotron-3-ultra-550b-a55b",
    "community": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "support": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "sales": "nvidia/nemotron-3-nano-30b-a3b",
    "ops": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
}


class SmartStandingWatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.proactive = _load(
            "engel_discord_desk_proactive_sw",
            TOOLS / "engel_discord_desk_proactive.py",
        )
        cls.discover = _load(
            "engel_nvidia_discover_sw",
            TOOLS / "engel_nvidia_discover.py",
        )

    def test_default_interval_is_six_hours(self) -> None:
        os.environ.pop("ENGEL_DISCORD_PROACTIVE_INTERVAL_SECONDS", None)
        self.assertGreaterEqual(self.proactive.proactive_interval(), 21600.0)

    def test_desk_models_are_distinct(self) -> None:
        models = set()
        for desk, expected in EXPECTED_DESK_MODELS.items():
            os.environ.pop("ENGEL_NVIDIA_CHAT_MODEL", None)
            got = self.proactive.desk_slm_model(desk)
            self.assertEqual(got, expected, desk)
            models.add(got)
            disc = self.discover.DEFAULT_MOUTH_MODELS.get(desk)
            self.assertEqual(disc, expected, f"discover {desk}")
        self.assertEqual(len(models), 6)

    def test_charter_rotate_differs_by_desk(self) -> None:
        def loader(name: str) -> dict:
            return {
                "addressed_as": f"Engel {name.title()}",
                "duty": f"{name} duty",
                "works_on": [f"{name}-a", f"{name}-b", f"{name}-c"],
            }

        bodies = set()
        for desk in EXPECTED_DESK_MODELS:
            _title, body, meta = self.proactive.ping_for_desk(desk, loader)
            bodies.add(body)
            self.assertEqual(meta["model"], EXPECTED_DESK_MODELS[desk])
            self.assertTrue(meta["focus"])
            self.assertIn("collab", body.casefold())
            self.assertNotIn("on standing watch", body.casefold())
        self.assertGreaterEqual(len(bodies), 4)
        self.assertTrue(self.proactive.desk_is_invited_to_collab("Engel Product — collab if this is your lane", "product"))
        self.assertTrue(self.proactive.is_desk_collab_idea("Collab idea: ship a clearer product story"))

    def test_owner_silence_permanent_until_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self.proactive.note_owner_silence(run_dir, reason="owner_stop", hold_seconds=0.0)
            silenced, _ = self.proactive.owner_silence_active(run_dir)
            self.assertTrue(silenced)
            state = self.proactive.load_state(run_dir)
            self.assertIn("owner_silence_until_unix", state)
            self.assertEqual(float(state["owner_silence_until_unix"]), 0.0)
            self.proactive.clear_owner_silence(run_dir, reason="owner_resume")
            silenced, _ = self.proactive.owner_silence_active(run_dir)
            self.assertFalse(silenced)

    def test_no_force_on_restart_in_source(self) -> None:
        text = (TOOLS / "engel_discord_desk_proactive.py").read_text(encoding="utf-8")
        self.assertIn("force=False", text)
        self.assertIn("Never force-post on restart", text)
        self.assertIn("thought_fn", text)
        bridge = (TOOLS / "engel_discord_bridge.py").read_text(encoding="utf-8")
        self.assertIn("generate_proactive_standing_thought", bridge)
        self.assertIn("thought_fn=generate_proactive_standing_thought", bridge)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
