#!/usr/bin/env python3
"""Verify shared Android worker / LAN pairing prompt classification."""
from __future__ import annotations

import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    module_path = ROOT / "engel_android_worker_prompt_signals.py"
    py_compile.compile(str(module_path), doraise=True)
    from engel_android_worker_prompt_signals import (
        is_android_lan_pairing_request,
        mentions_android_worker_lane,
    )

    require(
        is_android_lan_pairing_request("give me pairing code for wifi"),
        "WiFi pairing-code phrase not detected",
    )
    require(
        is_android_lan_pairing_request("give me pairing code for widi"),
        "WiFi typo pairing-code phrase not detected",
    )
    require(
        not is_android_lan_pairing_request("write python code for pairing helper"),
        "code-artifact phrase must not look like LAN pairing",
    )
    require(
        mentions_android_worker_lane("pair phones connected to usb"),
        "USB phone pair lane not detected",
    )
    require(
        not mentions_android_worker_lane("call my phone tomorrow"),
        "generic phone mention must not trigger worker lane",
    )
    print("OK: Engel Android worker prompt signals verified")


if __name__ == "__main__":
    main()
