#!/usr/bin/env python3
"""Verify Engel AI Main can see and route NVIDIA Nemotron 3.5 Lightning."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "tools" / "engel_nemotron_lightning_runtime.py"
CHAT = ROOT / "tools" / "engel_main_server_chat_http_service.py"
UNIT = ROOT / "scripts" / "systemd" / "engel-nemotron-lightning.service"
DROPIN = ROOT / "scripts" / "systemd" / "engel-main-chat.service.d" / "85-nemotron-3-5-lightning.conf"


def main() -> int:
    failures: list[str] = []

    def require(ok: bool, message: str) -> None:
        if ok:
            print("[PASS]", message)
        else:
            failures.append(message)
            print("[FAIL]", message)

    require(RUNTIME.is_file(), "runtime module present")
    require(CHAT.is_file(), "chat service present")
    require(UNIT.is_file(), "systemd unit present")
    require(DROPIN.is_file(), "chat service drop-in present")
    runtime = RUNTIME.read_text(encoding="utf-8")
    chat = CHAT.read_text(encoding="utf-8")
    unit = UNIT.read_text(encoding="utf-8")
    dropin = DROPIN.read_text(encoding="utf-8")
    require("NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf" in runtime, "runtime names the Lightning GGUF")
    require("nemotron_h_moe" in runtime, "runtime records the hybrid MoE arch")
    require("127.0.0.1:8905" in runtime, "runtime uses the local llama-server port")
    require("def dedicated_server_resident(" in runtime, "runtime detects a live llama-server")
    require(
        "dedicated_server_resident()" in runtime.split("def generate(", 1)[-1],
        "generate refuses a second llama-cli while the server is resident",
    )
    require(
        "paused-for-training" in runtime.split("def generate(", 1)[-1],
        "generate does not load Nemotron again while weekly training is paused",
    )
    require("huggingface.co" not in runtime, "runtime does not download weights")
    require("def _nemotron_lightning_local_model_receipt(" in chat, "chat service has the Lightning receipt")
    require("engel_nemotron_lightning_runtime" in chat, "chat service imports the Lightning runtime")
    require("ct_nemotron_lightning" in chat, "chat service exposes the Lightning provider id")
    require("llama-server" in unit and "8905" in unit, "unit starts llama-server on 8905")
    require("ngl 0" in unit, "unit stays on CT CPU")
    require("ENGEL_NEMOTRON_LANE_ENABLED=1" in dropin, "drop-in enables the Lightning lane")
    require("ENGEL_NEMOTRON_MODEL=" in dropin, "drop-in points at the Lightning GGUF")
    if failures:
        print("ENGEL_NEMOTRON_3_5_LIGHTNING_VERIFIER_FAILED")
        return 1
    print("ENGEL_NEMOTRON_3_5_LIGHTNING_VERIFIER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
