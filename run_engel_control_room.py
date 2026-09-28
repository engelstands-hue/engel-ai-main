#!/usr/bin/env python3
"""Launch Engel Control Room with conical CT246 wiring."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(r"D:\EngelControlRoom_build\dist\data")
if DATA.is_dir():
    os.environ.setdefault("ENGEL_CR_DATA", str(DATA))


def _already_running() -> bool:
    try:
        from urllib.request import urlopen
        import json

        raw = urlopen("http://127.0.0.1:24787/status", timeout=1.5).read()
        data = json.loads(raw.decode("utf-8", errors="replace"))
        models = data.get("models") or []
        names = [
            str(m.get("name") if isinstance(m, dict) else m)
            for m in models
        ]
        # July EngelControlRoom.exe still seeds Llama 3 70B. Refuse to reuse it.
        if any(name == "Llama 3 70B" for name in names):
            return False
        if not any("engel-ct246" in name.lower() or "engel-conical" in name.lower() for name in names):
            # Unknown/empty catalogue — still treat health as live only if /health is up
            # and models are empty (early boot). Prefer bringing conical window forward
            # when CT246 chat model is present.
            urlopen("http://127.0.0.1:24787/health", timeout=1.0).read()
            return "engel-ct246-chat" in names or not names
        return True
    except Exception:
        return False


def _bring_to_front() -> None:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "Engel AI Control Room")
        if not hwnd:
            return
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        return


if __name__ == "__main__":
    if _already_running():
        _bring_to_front()
        raise SystemExit(0)
    try:
        from engel_control_room.app import main

        raise SystemExit(main())
    except Exception:
        import traceback

        crash = Path(os.environ.get("ENGEL_CR_DATA") or ROOT / "data") / "control_room_crash.txt"
        crash.parent.mkdir(parents=True, exist_ok=True)
        crash.write_text(traceback.format_exc(), encoding="utf-8")
        raise
